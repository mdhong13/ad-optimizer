"""
대시보드 라우트.

2026-08-17 수정 — 화면이 「7일 총 지출 $0.00」이라고 거짓말하던 걸 고쳤다.

무엇이 거짓말이었나:
  1) 이 카드는 로컬 Mongo `performance_snapshots` 만 읽는다. 그 표를 채우는 스케줄러는
     2026-05-28 자동집행 사고 이후 **의도적으로 정지**돼 있다(AUTO_START_SCHEDULER=false).
     그래서 0 은 「안 썼다」가 아니라 **「아무도 안 적었다」**였다. 두 상태는 다른 상태고,
     화면의 단어는 상태와 1:1이어야 한다. → 0건이면 「수집 안 함」으로 쓴다.
  2) 제일 큰 지출(네이버 검색광고, 월 200만원 규모)이 아예 화면 밖에 있었다.
     → platforms/naver_ads.py 를 직접 호출해 상단에 별도 섹션으로 세운다.

🩸 통화는 절대 합산하지 않는다.
   네이버는 원(KRW), Meta·Google 은 계정마다 다르다. 하나의 「총 지출」로 더하는 순간
   그 숫자는 거짓이 된다. 환율을 임의로 끼워 넣지도 않는다. 섹션을 갈라 놓는 게 정답이다.

🩸 실패를 0 으로 삼키지 않는다.
   네이버 호출이 실패하면 빨간 카드에 사유를 그대로 띄운다. 조용히 0 을 채우면
   지금 고치는 그 버그를 똑같이 재생산하는 것이다.
"""
import asyncio
import logging
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from starlette.concurrency import run_in_threadpool

from storage.db import get_collection, get_recent_market_events, get_recent_performance

logger = logging.getLogger(__name__)

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# A 세션이 만드는 모듈. 아직 없을 수 있으므로 import 실패를 그대로 안고 간다.
# (settings 에 NAVER_SEARCHAD_* 가 아직 없으면 ImportError 가 아니라 AttributeError 로
#  터지므로, 실제 호출부에서도 Exception 을 넓게 받는다.)
try:
    from platforms.naver_ads import NaverAds
    _NAVER_IMPORT_ERROR = None
except Exception as e:  # ImportError 뿐 아니라 설정 로드 실패도 여기로 온다
    NaverAds = None
    _NAVER_IMPORT_ERROR = str(e)


# --- 네이버 조회 캐시 ---
# /stats 는 캠페인 수에 비례해 느리다. 매 페이지 로드마다 부르면 대시보드가 API 대기실이 된다.
# TTL 10분. 대신 화면에 **「기준: N분 전」을 반드시 표시**한다 —
# 언제 잰 값인지 안 보이면 낡은 값을 현재로 오해하고, 그게 이 페이지의 원래 병이었다.
NAVER_CACHE_TTL_SEC = 600
NAVER_PERIODS = (7, 30)  # 월 200만원 규모라 7일만 보면 감이 안 온다

_naver_cache: dict | None = None   # {"fetched_at": aware datetime, "data": {...}}
_naver_cache_lock = threading.Lock()
_naver_fetch_lock: asyncio.Lock | None = None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_aware_utc(value):
    """pymongo 는 tz_aware=False 라 **naive UTC** datetime 을 돌려준다.
    aware 와 그냥 빼면 TypeError 로 페이지가 통째로 죽는다. 여기서 한 번에 정규화한다."""
    if isinstance(value, datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
        except ValueError:
            return None
    return None


def _age_label(fetched_at: datetime) -> str:
    """'방금' / 'N분 전' / 'N시간 전'."""
    minutes = int((_now() - fetched_at).total_seconds() // 60)
    if minutes <= 0:
        return "방금"
    if minutes < 60:
        return f"{minutes}분 전"
    return f"{minutes // 60}시간 {minutes % 60}분 전"


def _fetch_period(days: int) -> dict:
    """스레드 하나에서 도는 단일 기간 조회.

    NaverAds 인스턴스를 호출마다 새로 만든다 — 7일/30일을 서로 다른 스레드에서 동시에
    부르기 때문에, 클라이언트 내부 상태를 공유하지 않게 하려는 것.
    """
    return NaverAds().get_spend(days=days)


def _shape_period(days: int, raw: dict) -> dict:
    """get_spend 결과 → 화면이 바로 쓸 수 있는 모양. ROAS 판정이 여기 들어간다."""
    spend = int(raw.get("spend") or 0)
    revenue = int(raw.get("revenue") or 0)

    # ROAS = 전환매출 / 광고비.
    # spend 가 0 이면 나눌 수 없다 → 「—」.
    # revenue 가 0 이면 계산은 되지만 0.00배로 찍힌다. 그런데 네이버 convAmt 는
    # **전환추적이 설치돼 있어야** 값이 온다(naver_ads.py 주석). 즉 0 은 「한 푼도 못 벌었다」가
    # 아니라 「측정을 안 하고 있다」일 수 있다. 0.00배로 찍으면 그게 또 하나의 거짓말이라
    # 사유를 달아 「—」로 둔다.
    roas = None
    roas_note = ""
    if spend <= 0:
        roas_note = "광고비 0 — 계산 불가"
    elif revenue <= 0:
        roas_note = "전환매출 미기록 (전환추적 확인 필요)"
    else:
        roas = revenue / spend

    return {
        "days": days,
        "ok": True,
        "spend": spend,
        "impressions": int(raw.get("impressions") or 0),
        "clicks": int(raw.get("clicks") or 0),
        "conversions": int(raw.get("conversions") or 0),
        "revenue": revenue,
        "roas": roas,
        "roas_note": roas_note,
        "currency": raw.get("currency", "KRW"),
    }


def _cache_read() -> dict | None:
    with _naver_cache_lock:
        return _naver_cache


def _cache_write(data: dict) -> dict:
    global _naver_cache
    entry = {"fetched_at": _now(), "data": data}
    with _naver_cache_lock:
        _naver_cache = entry
    return entry


def _present(entry: dict, cached: bool) -> dict:
    """캐시 항목 → 템플릿용. 측정 시각을 **항상** 같이 실어 보낸다."""
    out = dict(entry["data"])
    out["age_label"] = _age_label(entry["fetched_at"])
    out["cached"] = cached
    return out


def _bare(state: str, message: str) -> dict:
    return {
        "state": state,
        "message": message,
        "periods": [],
        "age_label": "방금",
        "cached": False,
    }


async def _refresh_naver() -> dict:
    """실제 조회 1회. 7일·30일을 **병렬**로 부른다.

    예외를 밖으로 내보내지 않는다 — 네이버가 죽었다고 대시보드 전체가 500 이 되면 안 된다.
    대신 실패 사유를 state/message 에 담아 화면에 드러낸다. (0 으로 채우지 않는다.)
    """
    if NaverAds is None:
        return _bare("module_pending", f"platforms/naver_ads.py 준비 중 ({_NAVER_IMPORT_ERROR})")

    try:
        configured = await run_in_threadpool(lambda: NaverAds().is_configured())
    except Exception as e:
        logger.exception("Naver Ads 설정 확인 실패")
        return _bare("error", f"설정 확인 실패: {e}")

    if not configured:
        return _bare(
            "not_configured",
            "NAVER_SEARCHAD_CUSTOMER_ID / ACCESS_LICENSE / SECRET_KEY 미설정",
        )

    # get_spend 는 동기(httpx)라 스레드풀로 내보내야 두 기간이 실제로 겹쳐 돈다.
    # 실측: 순차 ~6.5초 → 병렬 ~3.5초.
    results = await asyncio.gather(
        *(run_in_threadpool(_fetch_period, d) for d in NAVER_PERIODS),
        return_exceptions=True,
    )

    periods = []
    for days, res in zip(NAVER_PERIODS, results):
        if isinstance(res, BaseException):
            # 한 기간이 실패해도 다른 기간은 살린다. 대신 실패한 칸은 사유를 그대로 노출.
            logger.error(f"Naver Ads {days}일 조회 실패: {res}")
            periods.append({"days": days, "ok": False, "error": str(res)})
        else:
            periods.append(_shape_period(days, res))

    any_ok = any(p["ok"] for p in periods)
    data = {
        "state": "ok" if any_ok else "error",
        "message": "" if any_ok else "; ".join(p.get("error", "") for p in periods),
        "periods": periods,
    }

    if not any_ok:
        # 전부 실패한 결과는 캐싱하지 않는다 — 일시적 오류를 10분간 붙들고 있을 이유가 없다.
        return {**data, "age_label": "방금", "cached": False}

    return _present(_cache_write(data), cached=False)


def _spawn_naver_refresh() -> None:
    """만료된 캐시를 백그라운드에서 갱신. 이미 갱신 중이면 아무것도 안 한다."""
    if _naver_fetch_lock is None or _naver_fetch_lock.locked():
        return

    async def _run():
        async with _naver_fetch_lock:
            try:
                await _refresh_naver()
            except Exception:
                logger.exception("네이버 백그라운드 갱신 실패")

    try:
        asyncio.get_running_loop().create_task(_run())
    except RuntimeError:
        pass  # 이벤트 루프 밖 — 다음 요청이 어차피 다시 시도한다


async def _load_naver(force: bool = False) -> dict:
    """네이버 7일·30일 지출. 캐시 우선.

    ⏱ 페이지가 네이버 API 를 기다리게 두지 않는다.
       캐시가 만료돼도 **낡은 값을 즉시 돌려주고 갱신은 뒤에서** 한다
       (stale-while-revalidate). 실측 조회가 ~3.5초라 이걸 매번 앞에서 기다리면
       10분에 한 번씩 페이지가 4초짜리가 된다.
       낡은 값을 현재로 오해할 위험은 화면의 「기준: N분 전」이 막는다 —
       age_label 은 캐시 시각을 그대로 말하므로 값과 나이가 항상 같이 움직인다.
       기다리는 경우는 캐시가 아예 없을 때(프로세스 기동 후 첫 1회)뿐이다.
    """
    global _naver_fetch_lock

    if _naver_fetch_lock is None:
        _naver_fetch_lock = asyncio.Lock()

    entry = _cache_read()
    if entry and not force:
        if (_now() - entry["fetched_at"]).total_seconds() < NAVER_CACHE_TTL_SEC:
            return _present(entry, cached=True)
        _spawn_naver_refresh()
        return _present(entry, cached=True)

    async with _naver_fetch_lock:
        # 잠금 기다리는 사이 다른 요청이 이미 채웠을 수 있다.
        entry = _cache_read()
        if entry and not force and (_now() - entry["fetched_at"]).total_seconds() < NAVER_CACHE_TTL_SEC:
            return _present(entry, cached=True)
        return await _refresh_naver()


def _load_local(days: int = 7) -> dict:
    """로컬 수집분(performance_snapshots) 집계 — **수집 여부까지 같이** 돌려준다.

    rows 가 0이면 화면은 숫자 대신 「수집 안 함」을 쓴다. 「0원 썼다」와 「수집한 적 없다」는
    다른 상태다.
    """
    performance = get_recent_performance(days=days)

    totals = {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0}
    for r in performance:
        totals["spend"] += r.get("spend", 0)
        totals["clicks"] += r.get("clicks", 0)
        totals["impressions"] += r.get("impressions", 0)
        totals["conversions"] += r.get("conversions", 0)

    n = len(performance)
    avg_roas = sum(r.get("roas", 0) for r in performance) / n if n else 0
    avg_ctr = sum(r.get("ctr", 0) for r in performance) / n if n else 0

    # 창 밖의 마지막 기록도 찾아 둔다 — 「언제부터 안 적혔는지」가 있어야 0 의 뜻이 읽힌다.
    last_date = ""
    stale_days = None
    try:
        newest = get_collection("performance_snapshots").find_one(
            {}, {"_id": 0, "date": 1}, sort=[("date", -1)]
        )
        if newest and newest.get("date"):
            last_date = newest["date"]
            parsed = _as_aware_utc(f"{last_date}T00:00:00")
            if parsed:
                stale_days = (_now() - parsed).days
    except Exception as e:
        logger.warning(f"마지막 수집일 조회 실패: {e}")

    return {
        "performance": performance,
        "rows": n,
        "collected": n > 0,
        "totals": totals,
        "avg_roas": round(avg_roas, 2),
        "avg_ctr": round(avg_ctr * 100, 2),
        "last_date": last_date,
        "stale_days": stale_days,
        "days": days,
    }


def _annotate_events(events: list, stale_after_days: int = 7) -> list:
    """크립토 이벤트에 「며칠 묵었는지」를 붙인다.

    지우지 않는 이유: 기록 자체는 죄가 없다. 문제는 4개월 묵은 값이 현재처럼 보이는 것.
    """
    out = []
    for e in events:
        e = dict(e)
        created = _as_aware_utc(e.get("created_at"))
        age = (_now() - created).days if created else None
        e["age_days"] = age
        e["is_stale"] = age is not None and age > stale_after_days
        out.append(e)
    return out


@router.get("/")
async def dashboard(request: Request, refresh: int = 0):
    local = _load_local(days=7)
    # ?refresh=1 은 캐시를 무시하고 **기다려서** 새로 잰다 (수동 갱신·검증용).
    naver = await _load_naver(force=bool(refresh))
    events = _annotate_events(get_recent_market_events(limit=5))

    return templates.TemplateResponse(request, "dashboard.html", {
        "local": local,
        "naver": naver,
        "events": events,
        "naver_ttl_min": NAVER_CACHE_TTL_SEC // 60,
        # 하위 호환 — 기존 템플릿/부분템플릿이 참조할 수 있어 남겨 둔다.
        "performance": local["performance"],
        "totals": local["totals"],
        "avg_roas": local["avg_roas"],
        "avg_ctr": local["avg_ctr"],
    })


@router.get("/api/performance")
async def api_performance(days: int = 7, platform: str = None):
    return get_recent_performance(platform=platform, days=days)


@router.get("/api/naver/spend")
async def api_naver_spend():
    """네이버 지출 JSON. 캐시를 그대로 공유하므로 대시보드와 같은 값을 본다."""
    return await _load_naver()
