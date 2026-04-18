import asyncio
import json
from fastapi import APIRouter, Request, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from web import live_logs

from storage.db import (
    get_latest_cycle,
    get_collection,
    get_recent_performance,
    aggregate_campaign_performance,
    get_total_spend,
    get_cycle_by_id,
    get_campaign_timeseries,
    get_campaign_summary,
)
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


def _fetch_live_campaigns(platform_key: str) -> list[dict]:
    """플랫폼 API에서 활성 캠페인 목록을 실시간 조회 (실패 시 빈 리스트)"""
    try:
        if platform_key == "meta":
            from platforms.meta import MetaAds
            p = MetaAds()
            if not p.is_configured():
                return []
            return [
                {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "status": c.status,
                    "daily_budget": c.daily_budget,
                    "platform": c.platform,
                }
                for c in p.get_campaigns()
            ]
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Live campaign fetch failed ({platform_key}): {e}")
    return []


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

    # 플랫폼별 캠페인 수 (DB 성과 기준)
    platform_counts = {}
    for p in performance:
        plat = p.get("platform", "unknown")
        cid = p.get("campaign_id", "")
        if plat not in platform_counts:
            platform_counts[plat] = set()
        platform_counts[plat].add(cid)
    platform_summary = {k: len(v) for k, v in platform_counts.items()}

    # 활성 캠페인 (플랫폼 API 실시간 조회) + DB 성과 집계 병합
    perf_agg = aggregate_campaign_performance(days=30)
    live_campaigns = []
    for key, cfg in PLATFORM_CONFIG.items():
        if not cfg["enabled"]:
            continue
        for c in _fetch_live_campaigns(key):
            stats = perf_agg.get(c["campaign_id"], {})
            live_campaigns.append({
                **c,
                "impressions": stats.get("impressions", 0),
                "clicks": stats.get("clicks", 0),
                "spend": stats.get("spend", 0.0),
                "conversions": stats.get("conversions", 0),
                "revenue": stats.get("revenue", 0.0),
                "ctr": stats.get("ctr", 0.0),
                "cpc": stats.get("cpc", 0.0),
            })

    # 전체 누적 집행액/성과
    totals = get_total_spend(days=30)

    return templates.TemplateResponse(request, "campaigns.html", {
        "latest_cycle": latest_cycle,
        "cycles": cycles,
        "performance": performance[:20],
        "platform_summary": platform_summary,
        "platforms": PLATFORM_CONFIG,
        "dry_run": settings.DRY_RUN,
        "live_campaigns": live_campaigns,
        "totals": totals,
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
        import logging as _log
        import traceback
        logger = _log.getLogger(f"run-cycle.{platform}")
        try:
            logger.info(f"[run-cycle/{platform}] START")
            import scheduler.tasks as t
            func = getattr(t, task_name)
            func()
            logger.info(f"[run-cycle/{platform}] DONE")
        except Exception as e:
            logger.error(f"[run-cycle/{platform}] FAILED: {e}")
            logger.error(traceback.format_exc())

    background_tasks.add_task(_run)
    return {"triggered": True, "task": task_name, "platform": platform, "platform_name": cfg["name"]}


@router.get("/api/live-logs")
async def api_live_logs(request: Request):
    """Server-Sent Events로 실시간 로그 스트리밍"""
    async def gen():
        # 초기 최근 로그 버퍼 전송
        for entry in live_logs.recent(80):
            yield f"data: {json.dumps(entry)}\n\n"
        q = live_logs.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(q.get(), timeout=15)
                    yield f"data: {json.dumps(entry)}\n\n"
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
        finally:
            live_logs.unsubscribe(q)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/api/cycles")
async def api_cycles(limit: int = 10):
    cursor = get_collection("campaign_cycles").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(limit)
    return list(cursor)


@router.get("/api/active-cycle")
async def api_active_cycle():
    """실행 중(running)인 사이클만 반환"""
    doc = get_collection("campaign_cycles").find_one(
        {"status": "running"},
        {"_id": 0},
        sort=[("created_at", -1)],
    )
    if not doc:
        return {}
    for k in ("created_at", "updated_at"):
        if k in doc and hasattr(doc[k], "isoformat"):
            doc[k] = doc[k].isoformat()
    return doc


@router.get("/api/performance")
async def api_campaign_performance(days: int = 7, platform: str = None):
    return get_recent_performance(platform=platform, days=days)


@router.get("/cycle/{cycle_id}")
async def cycle_detail(cycle_id: str, request: Request):
    cycle = get_cycle_by_id(cycle_id)
    if not cycle:
        raise HTTPException(status_code=404, detail=f"Cycle not found: {cycle_id}")

    survivors_set = set(cycle.get("survivors", []))
    campaigns_raw = cycle.get("campaigns", [])
    new_campaigns = cycle.get("new_campaigns", [])

    # 각 캠페인의 누적 성과 병합
    perf_agg = aggregate_campaign_performance(days=30)
    evaluated = []
    for c in campaigns_raw:
        cid = c.get("campaign_id", "")
        stats = perf_agg.get(cid, {})
        evaluated.append({
            "campaign_id": cid,
            "campaign_name": c.get("name", "") or stats.get("campaign_name", ""),
            "score": c.get("score", 0),
            "survived": cid in survivors_set,
            "impressions": stats.get("impressions", 0),
            "clicks": stats.get("clicks", 0),
            "spend": stats.get("spend", 0.0),
            "conversions": stats.get("conversions", 0),
            "ctr": stats.get("ctr", 0.0),
            "cpc": stats.get("cpc", 0.0),
        })
    evaluated.sort(key=lambda x: x["score"], reverse=True)

    return templates.TemplateResponse(request, "cycle_detail.html", {
        "cycle": cycle,
        "evaluated": evaluated,
        "new_campaigns": new_campaigns,
        "survivors_count": len(survivors_set),
    })


@router.get("/detail/{campaign_id}")
async def campaign_detail(campaign_id: str, request: Request):
    summary = get_campaign_summary(campaign_id, days=30)
    timeseries = get_campaign_timeseries(campaign_id, days=30)
    return templates.TemplateResponse(request, "campaign_detail.html", {
        "campaign_id": campaign_id,
        "summary": summary,
        "timeseries": timeseries,
    })
