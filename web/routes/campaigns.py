from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_latest_cycle, get_collection, get_recent_performance

router = APIRouter(prefix="/campaigns")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


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
    })


@router.post("/run-cycle")
async def run_cycle(background_tasks: BackgroundTasks, platform: str = "meta"):
    """캠페인 최적화 사이클 수동 실행"""
    def _run():
        from scheduler.tasks import run_campaign_cycle
        run_campaign_cycle()
    background_tasks.add_task(_run)
    return {"triggered": True, "task": "campaign_cycle", "platform": platform}


@router.get("/api/cycles")
async def api_cycles(limit: int = 10):
    cursor = get_collection("campaign_cycles").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)


@router.get("/api/performance")
async def api_campaign_performance(days: int = 7, platform: str = None):
    return get_recent_performance(platform=platform, days=days)
