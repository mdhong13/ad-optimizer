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
    get_active_meta_account,
    set_active_meta_account,
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


def _fetch_live_campaigns(platform_key: str, meta_account_id: str = None) -> list[dict]:
    """플랫폼 API에서 활성 캠페인 목록을 실시간 조회 (실패 시 빈 리스트)"""
    try:
        if platform_key == "meta":
            from platforms.meta import MetaAds
            p = MetaAds(account_id=meta_account_id)
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

    # 활성 Meta 광고 계정
    active_meta_id = get_active_meta_account()
    meta_accounts = settings.meta_ad_accounts

    # 활성 캠페인 (플랫폼 API 실시간 조회) + DB 성과 집계 병합
    perf_agg = aggregate_campaign_performance(days=30)
    live_campaigns = []
    for key, cfg in PLATFORM_CONFIG.items():
        if not cfg["enabled"]:
            continue
        for c in _fetch_live_campaigns(key, meta_account_id=active_meta_id):
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
        "meta_accounts": meta_accounts,
        "active_meta_id": active_meta_id,
    })


@router.get("/api/meta-accounts")
async def api_meta_accounts():
    return {
        "accounts": settings.meta_ad_accounts,
        "active": get_active_meta_account(),
    }


@router.post("/api/meta-accounts/active")
async def api_set_active_meta_account(payload: dict):
    account_id = (payload or {}).get("account_id", "")
    try:
        set_active_meta_account(account_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "active": account_id}


@router.post("/canary/kr")
async def launch_kr_canary(payload: dict, background_tasks: BackgroundTasks):
    """
    KR Meta Canary 3개 즉시 생성 (AI 생성 우회, 준비된 카피+이미지 사용).
    payload: {"variants": ["C1-A","C2-A","C3-A"], "budget": 1500, "live": false}
    """
    variants = (payload or {}).get("variants") or ["C1-A", "C2-A", "C3-A"]
    budget = (payload or {}).get("budget")
    live = bool((payload or {}).get("live", False))
    dry_run = False if live else settings.DRY_RUN

    def _run():
        import logging as _log
        import traceback
        logger = _log.getLogger("canary.kr")
        try:
            logger.info(f"[canary/kr] START variants={variants} budget={budget} dry_run={dry_run}")
            from scripts.launch_kr_canary import launch
            results = launch(variants=variants, daily_budget=budget, dry_run=dry_run)
            ok = sum(1 for r in results if r["status"] in ("created", "dry_run"))
            logger.info(f"[canary/kr] DONE {ok}/{len(results)} success")
            for r in results:
                logger.info(f"  [{r['variant_id']}] {r['status']} {r.get('error') or r['campaign_id']}")
        except Exception as e:
            logger.error(f"[canary/kr] FAILED: {e}")
            logger.error(traceback.format_exc())

    background_tasks.add_task(_run)
    return {
        "triggered": True,
        "variants": variants,
        "budget_krw": budget or settings.MIN_DAILY_BUDGET_PER_CAMPAIGN,
        "dry_run": dry_run,
    }


@router.post("/canary/kr-unified")
async def launch_kr_canary_unified(payload: dict, background_tasks: BackgroundTasks):
    """KR Canary 통합 — 1 Campaign + 3 AdSet (CBO), PAUSED."""
    variants = (payload or {}).get("variants") or ["C1-A", "C2-A", "C3-A"]
    budget = int((payload or {}).get("budget") or 50000)
    live = bool((payload or {}).get("live", False))
    dry_run = False if live else settings.DRY_RUN

    def _run():
        import logging as _log, traceback
        logger = _log.getLogger("canary.kr-unified")
        try:
            logger.info(f"[canary/kr-unified] START variants={variants} budget=₩{budget:,} dry_run={dry_run}")
            from scripts.launch_kr_canary_unified import launch
            result = launch(variants=variants, daily_budget_krw=budget, dry_run=dry_run)
            logger.info(f"[canary/kr-unified] DONE status={result['status']} campaign={result.get('campaign_id')}")
            for a in result.get("adsets", []):
                logger.info(f"  {a['variant_name']}: adset={a['adset_id']} ad={a['ad_id']}")
        except Exception as e:
            logger.error(f"[canary/kr-unified] FAILED: {e}")
            logger.error(traceback.format_exc())

    background_tasks.add_task(_run)
    return {"triggered": True, "variants": variants, "budget_krw": budget, "dry_run": dry_run}


@router.post("/canary/us-awareness")
async def launch_us_awareness(payload: dict, background_tasks: BackgroundTasks):
    """US 크립토 지갑 보유자 대상 영상 인지도 캠페인 1개 생성."""
    budget = (payload or {}).get("budget") or 10.0
    live = bool((payload or {}).get("live", False))
    video = (payload or {}).get("video") or None
    dry_run = False if live else settings.DRY_RUN

    def _run():
        import logging as _log
        import traceback
        logger = _log.getLogger("canary.us-awareness")
        try:
            logger.info(f"[canary/us-awareness] START budget=${budget} live={live} dry_run={dry_run}")
            from scripts.launch_us_awareness import launch
            result = launch(daily_budget_usd=float(budget), dry_run=dry_run, video_path=video)
            logger.info(f"[canary/us-awareness] DONE {result['status']} → {result['campaign_id']}")
        except Exception as e:
            logger.error(f"[canary/us-awareness] FAILED: {e}")
            logger.error(traceback.format_exc())

    background_tasks.add_task(_run)
    return {"triggered": True, "budget_usd": budget, "dry_run": dry_run}


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


@router.get("/api/tree")
async def api_campaign_tree(meta_account_id: str = None, days: int = 7):
    """Meta 활성 계정의 Campaign→AdSet→Ad 트리 + 최근 N일 Ad-level 인사이트."""
    import logging
    log = logging.getLogger(__name__)
    account_id = meta_account_id or get_active_meta_account()

    try:
        from platforms.meta import MetaAds
        p = MetaAds(account_id=account_id)
        if not p.is_configured():
            return {"account_id": account_id, "campaigns": [], "error": "Meta 미구성"}
        p._init_api()

        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        from facebook_business.adobjects.adset import AdSet as FBAdSet
        from facebook_business.adobjects.ad import Ad as FBAd
        from facebook_business.adobjects.adsinsights import AdsInsights

        # 1. Ad-level 인사이트 한 방에 (날짜 집계)
        insights_by_ad: dict[str, dict] = {}
        try:
            insights = p._account.get_insights(
                fields=[
                    AdsInsights.Field.ad_id,
                    AdsInsights.Field.impressions,
                    AdsInsights.Field.clicks,
                    AdsInsights.Field.spend,
                    AdsInsights.Field.ctr,
                    AdsInsights.Field.cpc,
                    AdsInsights.Field.actions,
                ],
                params={
                    "level": "ad",
                    "date_preset": f"last_{days}d" if days in (7, 14, 28, 30, 90) else "last_7d",
                },
            )
            for row in insights:
                aid = row.get("ad_id", "")
                if not aid:
                    continue
                link_clicks = 0
                for a in row.get("actions", []) or []:
                    if a.get("action_type") == "link_click":
                        link_clicks = int(float(a.get("value", 0)))
                        break
                insights_by_ad[aid] = {
                    "impressions": int(row.get("impressions", 0)),
                    "clicks": int(row.get("clicks", 0)),
                    "link_clicks": link_clicks,
                    "spend": float(row.get("spend", 0)),
                    "ctr": float(row.get("ctr", 0)),
                    "cpc": float(row.get("cpc", 0)),
                }
        except Exception as e:
            log.warning(f"tree: insights fetch failed: {e}")

        # 2. 계층 구조 조회
        fb_campaigns = p._account.get_campaigns(
            fields=[FBCampaign.Field.id, FBCampaign.Field.name, FBCampaign.Field.status,
                    FBCampaign.Field.objective, FBCampaign.Field.daily_budget],
            params={"effective_status": ["ACTIVE", "PAUSED"], "limit": 50},
        )

        tree = []
        for c in fb_campaigns:
            cid = c["id"]
            fb = FBCampaign(cid)
            adsets_out = []
            try:
                fb_adsets = fb.get_ad_sets(fields=[
                    FBAdSet.Field.id, FBAdSet.Field.name, FBAdSet.Field.status,
                    FBAdSet.Field.daily_budget, FBAdSet.Field.optimization_goal,
                ])
            except Exception as e:
                log.warning(f"tree: adsets fetch failed for {cid}: {e}")
                fb_adsets = []

            for s in fb_adsets:
                sid = s["id"]
                ads_out = []
                try:
                    fb_ads = FBAdSet(sid).get_ads(fields=[
                        FBAd.Field.id, FBAd.Field.name, FBAd.Field.status,
                        FBAd.Field.effective_status,
                    ])
                except Exception as e:
                    log.warning(f"tree: ads fetch failed for {sid}: {e}")
                    fb_ads = []

                for a in fb_ads:
                    aid = a["id"]
                    stats = insights_by_ad.get(aid, {})
                    ads_out.append({
                        "ad_id": aid,
                        "name": a.get("name", ""),
                        "status": a.get("status", ""),
                        "effective_status": a.get("effective_status", ""),
                        "impressions": stats.get("impressions", 0),
                        "clicks": stats.get("clicks", 0),
                        "link_clicks": stats.get("link_clicks", 0),
                        "spend": stats.get("spend", 0.0),
                        "ctr": stats.get("ctr", 0.0),
                        "cpc": stats.get("cpc", 0.0),
                    })

                # AdSet 합계
                totals = _sum_rows(ads_out)
                adsets_out.append({
                    "adset_id": sid,
                    "name": s.get("name", ""),
                    "status": s.get("status", ""),
                    "daily_budget": float(s.get("daily_budget", 0)) / 100,
                    "optimization_goal": s.get("optimization_goal", ""),
                    "ads": ads_out,
                    **totals,
                })

            c_totals = _sum_rows(adsets_out)
            tree.append({
                "campaign_id": cid,
                "name": c.get("name", ""),
                "status": c.get("status", ""),
                "objective": c.get("objective", ""),
                "daily_budget": float(c.get("daily_budget", 0)) / 100,
                "adsets": adsets_out,
                **c_totals,
            })

        return {
            "account_id": account_id,
            "days": days,
            "campaigns": tree,
        }
    except Exception as e:
        log.error(f"tree: failed: {e}")
        return {"account_id": account_id, "campaigns": [], "error": str(e)}


def _sum_rows(rows: list[dict]) -> dict:
    imp = sum(r.get("impressions", 0) for r in rows)
    clk = sum(r.get("clicks", 0) for r in rows)
    spd = sum(r.get("spend", 0.0) for r in rows)
    return {
        "impressions": imp,
        "clicks": clk,
        "spend": round(spd, 2),
        "ctr": round((clk / imp * 100) if imp else 0, 2),
        "cpc": round((spd / clk) if clk else 0, 2),
    }


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
