from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_collection

router = APIRouter(prefix="/publisher")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def publisher_page(request: Request):
    # 최근 게시물 50건
    cursor = get_collection("published_content").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(50)
    contents = list(cursor)

    # 플랫폼별 통계
    platform_stats = {}
    for c in contents:
        plat = c.get("platform", "unknown")
        if plat not in platform_stats:
            platform_stats[plat] = {"count": 0, "published": 0, "views": 0, "likes": 0}
        platform_stats[plat]["count"] += 1
        if c.get("status") == "published":
            platform_stats[plat]["published"] += 1
        m = c.get("metrics", {})
        platform_stats[plat]["views"] += m.get("views", 0)
        platform_stats[plat]["likes"] += m.get("likes", 0)

    return templates.TemplateResponse("publisher.html", {
        "request": request,
        "contents": contents,
        "platform_stats": platform_stats,
    })


@router.post("/collect-metrics")
async def collect_metrics(background_tasks: BackgroundTasks):
    """게시물 성과 수집 (백그라운드)"""
    def _run():
        from publisher.monitor import ContentMonitor
        monitor = ContentMonitor()
        monitor.collect_metrics()
    background_tasks.add_task(_run)
    return {"triggered": True, "task": "collect_metrics"}


@router.get("/api/contents")
async def api_contents(limit: int = 20, platform: str = None):
    query = {}
    if platform:
        query["platform"] = platform
    cursor = get_collection("published_content").find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)
