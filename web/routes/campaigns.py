from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_latest_cycle, get_collection, get_recent_performance
from config.settings import settings

router = APIRouter(prefix="/campaigns")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

# 플랫폼별 사용 가능 상태
PLATFORM_CONFIG = {
    "meta": {
        "name": "Meta (Facebook + Instagram)",
        "enabled": True,
        "task": "run_campaign_cycle_meta",
    },
    "google": {
        "name": "Google Ads",
        "enabled": False,  # Basic Access 승인 후 True로 변경
        "task": "run_campaign_cycle_google",
        "note": "Basic Access 승인 대기",
    },
    "twitter": {
        "name": "X (Twitter) Ads",
        "enabled": bool(settings.TWITTER_ADS_ACCOUNT_ID),
        "task": "run_campaign_cycle_twitter",
        "note": "Ads API 승인 + TWITTER_ADS_ACCOUNT_ID 설정 필요",
    },
    "reddit": {
        "name": "Reddit Ads (크립토 서브레딧 타겟팅)",
        "enabled": bool(settings.REDDIT_ADS_ACCOUNT_ID and settings.REDDIT_REFRESH_TOKEN),
        "task": "run_campaign_cycle_reddit",
        "note": "REDDIT_* 설정 필요 (scripts/reddit_oauth.py)",
    },
}


@router.get("")
async def campaigns_page(request: Request):
    # 최근 사이클
    latest_cycle = get_latest_cycle()

    # 최근 사이클 10건
    cursor = get_collection("campaign_cycles").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(10)
    cycles = list(cursor)

    # 최근 성과
    performance = get_recent_performance(days=3)

    # 플랫폼별 캠페인 수
    platform_counts = {}
    for p in performance:
        plat = p.get("platform", "unknown")
        cid = p.get("campaign_id", "")
        if plat not in platform_counts:
            platform_counts[plat] = set()
        platform_counts[plat].add(cid)
    platform_summary = {k: len(v) for k, v in platform_counts.items()}

    return templates.TemplateResponse(request, "campaigns.html", {
        "latest_cycle": latest_cycle,
        "cycles": cycles,
        "performance": performance[:20],
        "platform_summary": platform_summary,
        "platforms": PLATFORM_CONFIG,
        "dry_run": settings.DRY_RUN,
    })


@router.post("/run-cycle/{platform}")
async def run_cycle(platform: str, background_tasks: BackgroundTasks):
    """플랫폼별 캠페인 최적화 사이클 수동 실행"""
    if platform not in PLATFORM_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown platform: {platform}")
    cfg = PLATFORM_CONFIG[platform]
    if not cfg["enabled"]:
        raise HTTPException(status_code=403, detail=f"{cfg['name']} 비활성화: {cfg.get('note', '')}")

    task_name = cfg["task"]

    def _run():
        import scheduler.tasks as t
        func = getattr(t, task_name)
        func()

    background_tasks.add_task(_run)
    return {"triggered": True, "task": task_name, "platform": platform, "platform_name": cfg["name"]}


@router.get("/api/cycles")
async def api_cycles(limit: int = 10):
    cursor = get_collection("campaign_cycles").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)


@router.get("/api/performance")
async def api_campaign_performance(days: int = 7, platform: str = None):
    return get_recent_performance(platform=platform, days=days)
