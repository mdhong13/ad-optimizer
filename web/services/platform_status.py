"""플랫폼 실측 점검 — 「키가 있다」와 「호출이 된다」는 다르다.

왜 필요한가(2026-08-12): QCat 네이버 검색광고의 `stats.mjs` 가 6개월간
  **한 번도 성공한 적이 없었다.** ids 를 JSON 배열로 보내 400 이 났는데,
  아무도 돌려보지 않아 아무도 몰랐다.
  같은 구조가 이 저장소의 `/settings` 화면에도 있었다 —
  `bool(settings.GOOGLE_ADS_DEVELOPER_TOKEN)` 하나로 「연결됨」 초록 배지를 줬는데
  실제 호출은 `PERMISSION_DENIED` 였다(2026-08-17 실측).
  → 초록은 **실호출이 성공했을 때만** 준다.

각 대상에 대해 셋을 **따로** 보고한다 — 뭉치면 원인이 안 보인다:
  ① 키 있음?   ② 클라이언트 생성됨?   ③ 실제 호출 성공?
  (키 O·클라 O·호출 X = 권한 문제 / 키 O·클라 X = 설정·의존성 문제. 뭉치면 둘이 구분 안 된다.)

읽기 전용 원칙:
  - 캠페인 목록 조회처럼 **돈이 안 나가는 호출만** 한다. 생성·수정·삭제 금지.
  - Anthropic·Gemini 는 호출 자체가 과금이라 **실호출을 하지 않는다.**
    화면엔 「키 있음 · 미점검」(노랑) 이라고 정직하게 쓴다. 초록 금지.

성능:
  - 프로브를 매 요청마다 직렬로 돌리면 페이지가 30초씩 걸린다.
    → ThreadPoolExecutor 병렬 + 전체 8초 마감 + 결과 메모리 캐시(TTL 10분).
  - 화면엔 반드시 「마지막 점검: N분 전」을 같이 보여준다.
    언제 잰 숫자인지 안 보이면 낡은 값을 현재로 오해한다.

CLI: `python scripts/platform_healthcheck.py` 가 이 모듈을 그대로 쓴다.
"""
from __future__ import annotations

import importlib
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import wait as futures_wait
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable, Optional

from config.settings import settings

# ── 튜닝 상수 ────────────────────────────────────────────────
CACHE_TTL_SECONDS = 600      # 10분. 이보다 오래된 결과는 다음 요청 때 다시 잰다.
PROBE_BUDGET_SECONDS = 8     # 전체 마감. 병렬이라 개별 프로브 상한과 같다.
HTTP_TIMEOUT_SECONDS = 6     # 8초 예산 안에서 끝나도록 2초 여유
KST = timezone(timedelta(hours=9))

# QCat RAG 는 아직 config/settings.py 에 없을 수 있다(agent/rag_client.py 는 env 직접 읽음).
# settings → env → 기본값 순서로 폴백한다.
DEFAULT_QCAT_RAG_URL = "http://106.253.105.18:3900"

# ── 상태 상수 — 세 축을 따로 둔다 ─────────────────────────────
KEYS_OK = "ok"
KEYS_MISSING = "missing"
KEYS_UNKNOWN = "unknown"        # 클라이언트가 is_configured() 를 안 알려줌

CLIENT_OK = "ok"
CLIENT_FAIL = "fail"
CLIENT_NA = "na"                # 클라이언트 개념이 없는 대상(키만 보는 항목 등)

CALL_OK = "ok"
CALL_FAIL = "fail"
CALL_SKIPPED = "skipped"        # 키가 없어서 부를 필요조차 없었다
CALL_TIMEOUT = "timeout"
CALL_UNCHECKED = "unchecked"    # 일부러 안 불렀다 (과금 회피 등)

# ── 그룹 ────────────────────────────────────────────────────
GROUP_ADS = "광고 플랫폼 — 실제 호출로 점검"
GROUP_INFRA = "인프라 — 실제 호출로 점검"
GROUP_KEYS = "키 보관만 — 실호출 미점검"
GROUP_ORDER = [GROUP_ADS, GROUP_INFRA, GROUP_KEYS]


# ── 문자열 정리 (화면에 그대로 나가는 값) ──────────────────────
_WS_RE = re.compile(r"\s+")
_CODE_RE = re.compile(
    r"\b(PERMISSION_DENIED|UNAUTHENTICATED|UNAVAILABLE|INVALID_ARGUMENT|NOT_FOUND"
    r"|DEADLINE_EXCEEDED|RESOURCE_EXHAUSTED|FAILED_PRECONDITION|QUOTA_EXCEEDED"
    r"|HTTP (?:400|401|403|404|409|429|500|502|503|504))\b"
)

_secrets_cache: Optional[list[str]] = None


def _secret_values() -> list[str]:
    """settings 에 들어있는 실제 비밀값 목록. 화면·로그에 새어나가면 안 된다.

    예외 메시지가 토큰을 그대로 되돌려주는 API 가 있다(네이버·OAuth 계열).
    「앞 160자만 잘라 쓴다」로는 못 막으므로 값 자체를 대조해 지운다."""
    global _secrets_cache
    if _secrets_cache is None:
        marks = ("TOKEN", "SECRET", "KEY", "URI", "PASSWORD", "LICENSE")
        vals = []
        for name in dir(settings):
            if not name.isupper() or not any(m in name for m in marks):
                continue
            v = getattr(settings, name, "")
            if isinstance(v, str) and len(v) >= 8:
                vals.append(v)
        # 긴 것부터 지워야 부분 문자열이 남지 않는다
        _secrets_cache = sorted(set(vals), key=len, reverse=True)
    return _secrets_cache


def _redact(text: str) -> str:
    for v in _secret_values():
        if v and v in text:
            text = text.replace(v, "***")
    return text


def _brief(text: object, limit: int = 160) -> str:
    """줄바꿈을 접고 앞 limit 자만. gRPC 예외는 여러 줄이라 접지 않으면 표가 깨진다."""
    s = _WS_RE.sub(" ", str(text)).strip()
    s = _redact(s)
    return s[:limit] + ("…" if len(s) > limit else "")


def _exc_detail(e: BaseException) -> str:
    """예외 타입 + 메시지 앞 160자. 빨강만 띄우고 이유를 숨기면 또 6개월 간다."""
    return _brief(f"{type(e).__name__}: {e}")


def _error_code(detail: str) -> str:
    """PERMISSION_DENIED / HTTP 401 처럼 한눈에 보이는 코드만 뽑아 칩으로 띄운다."""
    m = _CODE_RE.search(detail or "")
    return m.group(1) if m else ""


# ── 결과 ────────────────────────────────────────────────────
@dataclass
class ProbeResult:
    key: str
    label: str
    group: str
    keys: str = KEYS_UNKNOWN
    client: str = CLIENT_NA
    call: str = CALL_UNCHECKED
    detail: str = ""
    elapsed_ms: int = 0

    # --- 화면·CLI 용 라벨. 라벨은 상태 정의와 1:1 이어야 한다 ---
    @property
    def keys_label(self) -> str:
        return {KEYS_OK: "있음", KEYS_MISSING: "없음", KEYS_UNKNOWN: "—"}[self.keys]

    @property
    def client_label(self) -> str:
        return {CLIENT_OK: "생성됨", CLIENT_FAIL: "실패", CLIENT_NA: "—"}[self.client]

    @property
    def call_label(self) -> str:
        return {
            CALL_OK: "성공",
            CALL_FAIL: "실패",
            CALL_SKIPPED: "건너뜀",
            CALL_TIMEOUT: "시간초과",
            CALL_UNCHECKED: "미점검",
        }[self.call]

    @property
    def badge_class(self) -> str:
        """초록은 실호출 성공에만 준다."""
        if self.call == CALL_OK:
            return "badge-green"
        if self.call in (CALL_FAIL, CALL_TIMEOUT) or self.client == CLIENT_FAIL:
            return "badge-red"
        if self.keys == KEYS_MISSING:
            return "badge-gray"
        return "badge-yellow"   # 키는 있는데 실호출로 확인은 못 한 상태

    @property
    def badge_text(self) -> str:
        if self.call == CALL_OK:
            return "호출 성공"
        if self.call == CALL_TIMEOUT:
            return "시간초과"
        if self.call == CALL_FAIL:
            return "호출 실패"
        if self.client == CLIENT_FAIL:
            return "클라이언트 실패"
        if self.keys == KEYS_MISSING:
            return "키 없음"
        return "키 있음 · 미점검"

    @property
    def error_code(self) -> str:
        if self.call in (CALL_FAIL, CALL_TIMEOUT) or self.client == CLIENT_FAIL:
            return _error_code(self.detail)
        return ""


@dataclass
class Snapshot:
    results: list[ProbeResult] = field(default_factory=list)
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    duration_ms: int = 0

    @property
    def age_seconds(self) -> int:
        return int((datetime.now(timezone.utc) - self.checked_at).total_seconds())

    @property
    def age_text(self) -> str:
        s = self.age_seconds
        if s < 60:
            return "방금 전"
        if s < 3600:
            return f"{s // 60}분 전"
        if s < 86400:
            return f"{s // 3600}시간 전"
        return f"{s // 86400}일 전"

    @property
    def checked_at_kst(self) -> str:
        return self.checked_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S KST")

    @property
    def is_stale(self) -> bool:
        return self.age_seconds >= CACHE_TTL_SECONDS

    @property
    def probed(self) -> list[ProbeResult]:
        """실호출을 시도한 대상만 (미점검 항목은 성공률 분모에서 뺀다)."""
        return [r for r in self.results if r.call != CALL_UNCHECKED]

    @property
    def ok_count(self) -> int:
        return sum(1 for r in self.probed if r.call == CALL_OK)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.probed if r.call in (CALL_FAIL, CALL_TIMEOUT))

    @property
    def probed_count(self) -> int:
        return len(self.probed)

    def by_group(self) -> list[tuple[str, list[ProbeResult]]]:
        out = []
        for g in GROUP_ORDER:
            rows = [r for r in self.results if r.group == g]
            if rows:
                out.append((g, rows))
        return out


@dataclass
class ProbeSpec:
    key: str
    label: str
    group: str
    fn: Callable[[ProbeResult], None]


# ── 프로브 구현 ──────────────────────────────────────────────
def _ad_platform_probe(module_path: str, class_name: str) -> Callable[[ProbeResult], None]:
    """광고 플랫폼 공통: import → 생성 → is_configured() → get_campaigns() 1회.

    셋을 각 단계에서 따로 기록한다. 중간에 죽으면 어디서 죽었는지가 그대로 남는다."""

    def _run(r: ProbeResult) -> None:
        # ① 모듈 — 아직 안 만들어졌을 수도 있다(다른 세션이 작업 중). 기다리지 않는다.
        try:
            mod = importlib.import_module(module_path)
            cls = getattr(mod, class_name)
        except ImportError as e:
            r.keys = KEYS_UNKNOWN
            r.client = CLIENT_FAIL
            r.call = CALL_SKIPPED
            r.detail = f"모듈 없음 — {module_path} ({_brief(e, 100)})"
            return
        except Exception as e:  # noqa: BLE001 — 문법 오류·의존성 등
            r.client = CLIENT_FAIL
            r.call = CALL_SKIPPED
            r.detail = f"import 실패 — {_exc_detail(e)}"
            return

        # ② 클라이언트 생성
        try:
            client = cls()
        except Exception as e:  # noqa: BLE001
            r.client = CLIENT_FAIL
            r.call = CALL_SKIPPED
            r.detail = _exc_detail(e)
            return
        r.client = CLIENT_OK

        # ③ 키 유무는 클라이언트가 스스로 안다
        try:
            r.keys = KEYS_OK if client.is_configured() else KEYS_MISSING
        except Exception:  # noqa: BLE001
            r.keys = KEYS_UNKNOWN
        if r.keys == KEYS_MISSING:
            r.call = CALL_SKIPPED
            r.detail = "키 미설정 — 호출 생략"
            return

        # ④ 실제 호출 1회 (읽기 전용)
        try:
            got = client.get_campaigns()
            r.call = CALL_OK
            n = len(got) if hasattr(got, "__len__") else None
            r.detail = f"캠페인 {n}개" if n is not None else _brief(got, 100)
        except Exception as e:  # noqa: BLE001
            r.call = CALL_FAIL
            r.detail = _exc_detail(e)

    return _run


def _probe_mongodb(r: ProbeResult) -> None:
    r.keys = KEYS_OK if settings.MONGODB_URI else KEYS_MISSING
    if r.keys == KEYS_MISSING:
        r.call = CALL_SKIPPED
        r.detail = "MONGODB_URI 미설정"
        return
    try:
        from storage.db import get_db

        db = get_db()   # 싱글톤 (serverSelectionTimeoutMS=5000)
        r.client = CLIENT_OK
    except Exception as e:  # noqa: BLE001
        r.client = CLIENT_FAIL
        r.call = CALL_SKIPPED
        r.detail = _exc_detail(e)
        return
    try:
        db.command("ping")
        names = db.list_collection_names()
        r.call = CALL_OK
        r.detail = f"ping OK · DB {settings.MONGODB_DB} · 컬렉션 {len(names)}개"
    except Exception as e:  # noqa: BLE001
        r.call = CALL_FAIL
        r.detail = _exc_detail(e)


def _qcat_rag_url() -> str:
    url = getattr(settings, "QCAT_RAG_URL", "") or os.getenv("QCAT_RAG_URL", "") or DEFAULT_QCAT_RAG_URL
    return url.rstrip("/")


def _probe_qcat_rag(r: ProbeResult) -> None:
    import httpx

    url = _qcat_rag_url()
    r.keys = KEYS_OK if url else KEYS_MISSING
    if not url:
        r.call = CALL_SKIPPED
        r.detail = "QCAT_RAG_URL 미설정"
        return
    r.client = CLIENT_OK
    target = f"{url}/health"
    try:
        resp = httpx.get(target, timeout=HTTP_TIMEOUT_SECONDS)
    except Exception as e:  # noqa: BLE001
        r.call = CALL_FAIL
        r.detail = f"{_exc_detail(e)} ({target})"
        return
    if resp.status_code >= 400:
        r.call = CALL_FAIL
        r.detail = f"HTTP {resp.status_code} — {_brief(resp.text, 100)} ({target})"
        return
    try:
        body = resp.json()
        extra = f"status={body.get('status')} chunks={body.get('chunks')}"
    except Exception:  # noqa: BLE001
        extra = _brief(resp.text, 60)
    r.call = CALL_OK
    r.detail = f"HTTP {resp.status_code} · {extra} ({target})"


def _probe_local_llm(r: ProbeResult) -> None:
    import httpx

    base = (settings.LOCAL_LLM_BASE_URL or "").rstrip("/")
    r.keys = KEYS_OK if base else KEYS_MISSING
    if not base:
        r.call = CALL_SKIPPED
        r.detail = "LOCAL_LLM_BASE_URL 미설정"
        return
    r.client = CLIENT_OK
    target = base + (settings.LOCAL_LLM_MODELS_ENDPOINT or "/v1/models")
    try:
        resp = httpx.get(target, timeout=HTTP_TIMEOUT_SECONDS)
    except Exception as e:  # noqa: BLE001
        r.call = CALL_FAIL
        r.detail = f"{_exc_detail(e)} ({target})"
        return
    if resp.status_code >= 400:
        r.call = CALL_FAIL
        r.detail = f"HTTP {resp.status_code} — {_brief(resp.text, 100)} ({target})"
        return
    try:
        models = [m.get("id", "?") for m in resp.json().get("data", [])]
        extra = f"모델 {len(models)}개: " + ", ".join(models[:3])
    except Exception:  # noqa: BLE001
        extra = _brief(resp.text, 60)
    r.call = CALL_OK
    r.detail = f"HTTP {resp.status_code} · {extra}"


def _key_only_probe(has_key: Callable[[], bool], note: str) -> Callable[[ProbeResult], None]:
    """키 유무만 본다. 실호출을 **안 하기로 한** 대상이므로 초록을 주지 않는다."""

    def _run(r: ProbeResult) -> None:
        r.keys = KEYS_OK if has_key() else KEYS_MISSING
        r.client = CLIENT_NA
        r.call = CALL_UNCHECKED if r.keys == KEYS_OK else CALL_SKIPPED
        r.detail = note if r.keys == KEYS_OK else "키 미설정"

    return _run


_PAID_NOTE = "실호출이 과금이라 점검하지 않음 (키 존재만 확인)"
_KEY_NOTE = "키 존재만 확인 — 실제 호출 여부는 모름"


def build_specs() -> list[ProbeSpec]:
    return [
        # ── 광고 플랫폼: get_campaigns() 읽기 1회 ──
        ProbeSpec("google_ads", "Google Ads", GROUP_ADS,
                  _ad_platform_probe("platforms.google_ads", "GoogleAds")),
        ProbeSpec("meta", "Meta Ads", GROUP_ADS,
                  _ad_platform_probe("platforms.meta", "MetaAds")),
        ProbeSpec("twitter", "X (Twitter) Ads", GROUP_ADS,
                  _ad_platform_probe("platforms.twitter", "TwitterAds")),
        ProbeSpec("reddit", "Reddit Ads", GROUP_ADS,
                  _ad_platform_probe("platforms.reddit", "RedditAds")),
        ProbeSpec("naver", "네이버 검색광고", GROUP_ADS,
                  _ad_platform_probe("platforms.naver_ads", "NaverAds")),
        # ── 인프라 ──
        ProbeSpec("mongodb", "MongoDB", GROUP_INFRA, _probe_mongodb),
        ProbeSpec("qcat_rag", "QCat RAG", GROUP_INFRA, _probe_qcat_rag),
        ProbeSpec("local_llm", "Local LLM (d4win)", GROUP_INFRA, _probe_local_llm),
        # ── 키만 보는 대상 ──
        ProbeSpec("anthropic", "Anthropic (Claude)", GROUP_KEYS,
                  _key_only_probe(lambda: bool(settings.ANTHROPIC_API_KEY), _PAID_NOTE)),
        ProbeSpec("gemini", "Gemini (Google API)", GROUP_KEYS,
                  _key_only_probe(lambda: bool(settings.GEMINI_API_KEY), _PAID_NOTE)),
        ProbeSpec("gmail", "Gmail", GROUP_KEYS,
                  _key_only_probe(lambda: bool(settings.GMAIL_REFRESH_TOKEN), _KEY_NOTE)),
        ProbeSpec("threads", "Threads", GROUP_KEYS,
                  _key_only_probe(lambda: bool(settings.THREADS_APP_ID), _KEY_NOTE)),
        ProbeSpec("youtube", "YouTube [ONEMSG] (mdhong13)", GROUP_KEYS,
                  _key_only_probe(lambda: bool(settings.YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN), _KEY_NOTE)),
        ProbeSpec("x_account", "X 계정 [ONEMSG] (@onemsgx)", GROUP_KEYS,
                  _key_only_probe(
                      lambda: bool(settings.TWITTER_API_KEY and settings.TWITTER_ACCESS_TOKEN),
                      _KEY_NOTE)),
    ]


# ── 실행 ────────────────────────────────────────────────────
def _guarded(spec: ProbeSpec) -> ProbeResult:
    """프로브 하나가 터져도 다른 프로브·페이지를 죽이지 않는다."""
    r = ProbeResult(key=spec.key, label=spec.label, group=spec.group)
    t0 = time.monotonic()
    try:
        spec.fn(r)
    except Exception as e:  # noqa: BLE001
        r.call = CALL_FAIL
        r.detail = _exc_detail(e)
    r.elapsed_ms = int((time.monotonic() - t0) * 1000)
    return r


# 🩸 스레드로 흩기 **전에** 메인 스레드에서 플랫폼 모듈을 먼저 올린다.
#    `platforms/__init__.py` 가 meta 와 google_ads 를 함께 끌어오기 때문에, 프로브 스레드 둘이
#    각각 `platforms.meta` / `platforms.google_ads` 를 import 하면 서로 상대의 모듈 락을 물고 기다린다:
#        _DeadlockError: deadlock detected by _ModuleLock('platforms.meta')
#    그러면 화면엔 진짜 상태 대신 「import 실패」가 뜬다 — **고치려던 버그의 재발**이다.
#    스레드 스케줄링에 좌우돼 터졌다 안 터졌다 하므로, 한 번 통과한 건 증거가 못 된다.
#    (2026-08-17 통합 검증에서 재현. 프로브 단독 실행에선 안 났다.)
_PLATFORM_MODULES = (
    "platforms",            # 패키지 __init__ 이 meta·google_ads 를 함께 로드한다
    "platforms.twitter",
    "platforms.reddit",
    "platforms.naver_ads",
)


def _preimport_platforms() -> None:
    """실패는 여기서 삼킨다 — 사유는 각 프로브가 다시 import 하며 제대로 기록한다."""
    for path in _PLATFORM_MODULES:
        try:
            importlib.import_module(path)
        except Exception:  # noqa: BLE001 — 여기서 판정하지 않는다
            pass


def run_probes(
    specs: Optional[list[ProbeSpec]] = None,
    budget: float = PROBE_BUDGET_SECONDS,
) -> tuple[list[ProbeResult], int]:
    """전부 병렬로 돌리고 budget 초에 끊는다.

    병렬이므로 전체 마감 = 개별 타임아웃. 늦게 오는 프로브는 「시간초과」로 표시하고
    결과를 버린다 — 페이지가 느린 API 하나 때문에 30초 걸리면 안 본다, 안 보면 또 6개월 간다.
    (CLI 는 사람이 기다리는 자리라 budget 을 넉넉히 준다.)"""
    specs = specs or build_specs()
    _preimport_platforms()
    t0 = time.monotonic()
    ex = ThreadPoolExecutor(max_workers=min(16, len(specs)), thread_name_prefix="probe")
    futs = {ex.submit(_guarded, s): s for s in specs}
    _, not_done = futures_wait(futs, timeout=budget)

    by_key: dict[str, ProbeResult] = {}
    for fut, spec in futs.items():
        if fut in not_done:
            by_key[spec.key] = ProbeResult(
                key=spec.key, label=spec.label, group=spec.group,
                keys=KEYS_UNKNOWN, client=CLIENT_NA, call=CALL_TIMEOUT,
                detail=f"{budget:g}초 안에 응답이 없어 화면을 먼저 그림 — "
                       f"점검은 계속 돌고 있다. 새로고침하면 진짜 결과가 붙는다.",
                elapsed_ms=int(budget * 1000),
            )
            # 늦게 온 결과도 버리지 않는다. 이유를 못 보면 또 6개월 간다.
            fut.add_done_callback(_late_callback)
            continue
        try:
            by_key[spec.key] = fut.result(timeout=0)
        except Exception as e:  # noqa: BLE001 — _guarded 가 이미 잡지만 이중 안전망
            by_key[spec.key] = ProbeResult(
                key=spec.key, label=spec.label, group=spec.group,
                call=CALL_FAIL, detail=_exc_detail(e),
            )
    # 남은 스레드는 회수만 하고 기다리지 않는다 (페이지를 붙잡으면 안 된다)
    ex.shutdown(wait=False, cancel_futures=True)
    return [by_key[s.key] for s in specs], int((time.monotonic() - t0) * 1000)


# ── 마감을 넘겨 도착한 결과 ───────────────────────────────────
# 첫 요청은 google-ads SDK import 만으로 10초 넘게 걸린다(2026-08-17 실측 16.2초 → 두 번째 4.6초).
# 화면은 8초에 끊어 먼저 그리되, 늦게 온 진짜 결과(예: PERMISSION_DENIED)를 캐시에 붙여
# 다음 새로고침에서 사유가 보이게 한다.
_late_lock = threading.Lock()
_late_results: dict[str, ProbeResult] = {}


def _late_callback(fut) -> None:
    try:
        res = fut.result(timeout=0)
    except Exception:  # noqa: BLE001 — 취소·예외면 시간초과 표시를 유지
        return
    res.detail = f"{res.detail} · 마감 뒤 도착한 결과"
    with _late_lock:
        _late_results[res.key] = res
    _apply_late(_cache)


def _apply_late(snap: Optional[Snapshot]) -> None:
    """시간초과로 남아 있는 행만 늦게 온 결과로 교체한다."""
    if snap is None:
        return
    with _late_lock:
        if not _late_results:
            return
        for i, r in enumerate(snap.results):
            late = _late_results.get(r.key)
            if late is not None and r.call == CALL_TIMEOUT:
                snap.results[i] = late


# ── 캐시 ────────────────────────────────────────────────────
_cache: Optional[Snapshot] = None
_lock = threading.Lock()


def get_snapshot(force: bool = False) -> Snapshot:
    """캐시된 점검 결과. 없거나 10분 지났으면(또는 force) 다시 잰다."""
    global _cache
    snap = _cache
    if not force and snap is not None and not snap.is_stale:
        _apply_late(snap)
        return snap
    with _lock:
        snap = _cache          # 잠금 대기 중 다른 요청이 이미 갱신했을 수 있다
        if snap is not None:
            if not force and not snap.is_stale:
                _apply_late(snap)
                return snap
            if force and snap.age_seconds < 2:
                # [지금 점검] 더블클릭 — 방금 잰 값을 그대로 준다 (중복 호출 방지)
                _apply_late(snap)
                return snap
        with _late_lock:
            _late_results.clear()
        results, duration = run_probes()
        _cache = Snapshot(results=results, checked_at=datetime.now(timezone.utc), duration_ms=duration)
        # 마감 직전에 도착해 캐시가 없던 사이 떨어진 결과를 지금 붙인다
        _apply_late(_cache)
        return _cache


def error_snapshot(exc: BaseException) -> Snapshot:
    """점검 자체가 터졌을 때의 대체 스냅샷. 설정 화면이 500 이 되면 안 된다."""
    return Snapshot(results=[ProbeResult(
        key="_probe_runner", label="점검 실행", group=GROUP_INFRA,
        keys=KEYS_UNKNOWN, client=CLIENT_FAIL, call=CALL_FAIL,
        detail=f"점검기 자체가 실패 — {_exc_detail(exc)}",
    )])


def start_background_warmup() -> None:
    """앱 부팅 직후 백그라운드로 한 번 재둔다.

    운영자가 /settings 를 열었을 때 캐시가 비어 있으면 첫 페이지가 8초 꽉 채운다.
    부팅 때 미리 재두면 화면은 즉시 뜨고, 값도 「방금 전」이다. 실패해도 앱은 계속 뜬다."""
    def _warm():
        try:
            get_snapshot()
        except Exception:  # noqa: BLE001 — 점검 실패가 앱을 죽이면 안 된다
            pass

    threading.Thread(target=_warm, name="platform-status-warmup", daemon=True).start()


def invalidate() -> None:
    global _cache
    with _lock:
        _cache = None


def peek() -> Optional[Snapshot]:
    """점검을 유발하지 않고 캐시만 본다."""
    return _cache
