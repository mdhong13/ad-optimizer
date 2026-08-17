"""설정 화면 — API 연동 「실측」 상태.

2026-08-17 이전 이 화면은 `bool(settings.GOOGLE_ADS_DEVELOPER_TOKEN)` 로
「Google Ads 연결됨」 초록 배지를 띄웠다. 실제 호출은 PERMISSION_DENIED 였다.
화면이 거짓말을 하면 아무도 안 고친다 — 네이버 stats.mjs 가 6개월 방치된 것과 같은 구조.
→ 배지는 web/services/platform_status.py 의 **실제 호출 결과**로만 준다.
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path
from starlette.concurrency import run_in_threadpool

from config.settings import settings
from web.services import platform_status

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# 부팅 직후 백그라운드로 한 번 재둔다. 첫 점검은 google-ads SDK import 때문에 10초를 넘긴다
# (2026-08-17 실측 16.2초 → 두 번째부터 4.6초). 미리 재두면 화면은 캐시로 즉시 뜬다.
platform_status.start_background_warmup()


def _config_info() -> dict:
    """운영 중 헷갈리기 쉬운 값만. 키 값은 절대 넣지 않는다(마스킹본도 금지)."""
    return {
        "APP_ENV": settings.APP_ENV,
        "DRY_RUN": settings.DRY_RUN,
        "AUTO_START_SCHEDULER": settings.AUTO_START_SCHEDULER,
        "CAMPAIGN_CYCLE_HOURS": settings.CAMPAIGN_CYCLE_HOURS,
        "CAMPAIGNS_PER_CYCLE": settings.CAMPAIGNS_PER_CYCLE,
        "CAMPAIGNS_SURVIVE": settings.CAMPAIGNS_SURVIVE,
        "BUDGET_CHANGE_LIMIT_PCT": settings.BUDGET_CHANGE_LIMIT_PCT,
        "META_AD_ACCOUNT_ID": settings.META_AD_ACCOUNT_ID,
        "GOOGLE_ADS_CUSTOMER_ID": settings.GOOGLE_ADS_CUSTOMER_ID,
        "MONGODB_DB": settings.MONGODB_DB,
    }


def _context(snapshot) -> dict:
    return {
        "snapshot": snapshot,
        "groups": snapshot.by_group(),
        "config_info": _config_info(),
        "cache_ttl_min": platform_status.CACHE_TTL_SECONDS // 60,
        "probe_budget_sec": platform_status.PROBE_BUDGET_SECONDS,
    }


async def _snapshot(force: bool = False):
    # 블로킹 IO 라 이벤트 루프 밖(threadpool)에서 돌린다 — 다른 요청이 멈추면 안 된다.
    # 프로브는 개별로 감싸져 있지만, 점검기 자체가 터져도 설정 화면은 떠야 한다.
    try:
        return await run_in_threadpool(platform_status.get_snapshot, force)
    except Exception as e:  # noqa: BLE001
        return platform_status.peek() or platform_status.error_snapshot(e)


@router.get("")
async def settings_page(request: Request):
    # 캐시된 결과를 그대로 렌더한다. 캐시가 비었으면 여기서 1회 점검(마감 8초).
    snapshot = await _snapshot()
    return templates.TemplateResponse(request, "settings.html", _context(snapshot))


@router.post("/probe")
async def settings_probe(request: Request):
    """[지금 점검] — 캐시를 무시하고 다시 잰 뒤 같은 화면을 렌더한다."""
    snapshot = await _snapshot(force=True)
    return templates.TemplateResponse(request, "settings.html", _context(snapshot))
