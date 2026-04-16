from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_collection, get_active_characters

router = APIRouter(prefix="/viral")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def viral_page(request: Request):
    # 캐릭터 목록
    characters = get_active_characters()

    # 최근 바이럴 활동 50건
    cursor = get_collection("viral_activities").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(50)
    activities = list(cursor)

    # 플랫폼별 통계
    platform_stats = {}
    for a in activities:
        plat = a.get("platform", "unknown")
        if plat not in platform_stats:
            platform_stats[plat] = {"count": 0, "generated": 0, "posted": 0}
        platform_stats[plat]["count"] += 1
        if a.get("status") == "generated":
            platform_stats[plat]["generated"] += 1
        elif a.get("status") == "posted":
            platform_stats[plat]["posted"] += 1

    return templates.TemplateResponse(request, "viral.html", {
        "characters": characters,
        "activities": activities,
        "platform_stats": platform_stats,
    })


@router.post("/scan/reddit")
async def scan_reddit(background_tasks: BackgroundTasks):
    """Reddit 스캔 → 댓글 생성 (백그라운드)"""
    def _run():
        from viral.manager import ViralManager
        mgr = ViralManager()
        mgr.scan_and_engage(platform="reddit")
    background_tasks.add_task(_run)
    return {"triggered": True, "task": "reddit_scan"}


@router.post("/scan/all")
async def scan_all(background_tasks: BackgroundTasks):
    """전체 플랫폼 스캔 (OpenClaw 병렬)"""
    def _run():
        from agent.openclaw import OpenClawManager
        mgr = OpenClawManager()
        mgr.scan_and_engage_all()
    background_tasks.add_task(_run)
    return {"triggered": True, "task": "openclaw_scan_all"}


@router.get("/api/activities")
async def api_activities(limit: int = 20, platform: str = None):
    query = {}
    if platform:
        query["platform"] = platform
    cursor = get_collection("viral_activities").find(
        query, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)


@router.get("/api/characters")
async def api_characters(platform: str = None):
    return get_active_characters(platform)
