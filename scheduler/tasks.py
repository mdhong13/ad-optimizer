"""
스케줄러 태스크 정의
"""
import logging
from datetime import date, timedelta

from config.settings import settings

logger = logging.getLogger(__name__)


def collect_performance():
    """매 2시간: 모든 플랫폼에서 성과 데이터 수집 → DB 저장"""
    from platforms.meta import MetaAds
    from platforms.google_ads import GoogleAds
    from storage import db

    logger.info("Task: collect_performance started")
    today = date.today()
    yesterday = today - timedelta(days=1)
    total = 0

    for PlatformClass in [MetaAds, GoogleAds]:
        p = PlatformClass()
        if not p.is_configured():
            continue
        try:
            campaigns = p.get_campaigns()
            for c in campaigns:
                perf = p.get_performance(c.campaign_id, yesterday, today)
                for snap in perf:
                    db.insert_performance(snap.to_db_dict())
                    total += 1
            logger.info(f"[{p.platform_name}] {len(campaigns)} campaigns collected")
        except Exception as e:
            logger.error(f"[{p.platform_name}] Collection failed: {e}")

    logger.info(f"Task: collect_performance done ({total} snapshots)")


def run_campaign_cycle_meta():
    """Meta Ads 전용 캠페인 최적화 사이클"""
    from platforms.meta import MetaAds
    from campaign.manager import CampaignManager

    logger.info("Task: run_campaign_cycle_meta started")
    meta = MetaAds()
    if not meta.is_configured():
        logger.warning("Meta Ads not configured, skipping")
        return None
    mgr = CampaignManager(meta)
    cycle_id = mgr.run_cycle()
    logger.info(f"Meta campaign cycle: {cycle_id}")
    return cycle_id


def run_campaign_cycle_google():
    """Google Ads 전용 캠페인 최적화 사이클 (Basic Access 필요)"""
    from platforms.google_ads import GoogleAds
    from campaign.manager import CampaignManager

    logger.info("Task: run_campaign_cycle_google started")
    google = GoogleAds()
    if not google.is_configured():
        logger.warning("Google Ads not configured, skipping")
        return None
    mgr = CampaignManager(google)
    cycle_id = mgr.run_cycle()
    logger.info(f"Google campaign cycle: {cycle_id}")
    return cycle_id


# 스케줄러용: 모든 플랫폼 순차 실행
def run_campaign_cycle():
    """매 8시간: 모든 플랫폼 캠페인 사이클 순차 실행"""
    logger.info("Task: run_campaign_cycle (all platforms) started")
    run_campaign_cycle_meta()
    # Google Ads Basic Access 승인 후 주석 해제
    # run_campaign_cycle_google()
    logger.info("Task: run_campaign_cycle done")


def check_market_events():
    """매 1시간: 크립토 가격/뉴스 체크"""
    from intelligence.crypto_monitor import check_crypto_market
    from storage import db

    logger.info("Task: check_market_events started")
    try:
        events = check_crypto_market()
        for event in events:
            db.insert_market_event(event)
            if event.get("severity") in ("high", "critical"):
                logger.warning(f"High severity: {event['title']}")
                _trigger_event_response(event)
        logger.info(f"Task: check_market_events done ({len(events)} events)")
    except Exception as e:
        logger.error(f"Market events check failed: {e}")


def _trigger_event_response(event: dict):
    """시장 이벤트 즉시 대응"""
    from agent.claude import ClaudeAgent
    from storage import db

    agent = ClaudeAgent()
    try:
        decisions = agent.analyze_market_event(event)
        if isinstance(decisions, dict):
            decisions = [decisions]
        for d in decisions:
            db.insert_decision(d)
        logger.info(f"Event response: {len(decisions)} decisions")
    except Exception as e:
        logger.error(f"Event response failed: {e}")


def generate_report():
    """매일 20:00: 일간 리포트 생성 + Gmail 발송"""
    from storage import db

    logger.info("Task: generate_report started")
    today = date.today().isoformat()

    # 성과 집계
    perf = db.get_recent_performance(days=1)
    total_spend = sum(p.get("spend", 0) for p in perf)
    total_clicks = sum(p.get("clicks", 0) for p in perf)
    total_impressions = sum(p.get("impressions", 0) for p in perf)
    total_conversions = sum(p.get("conversions", 0) for p in perf)

    report = {
        "total_spend": total_spend,
        "total_clicks": total_clicks,
        "total_impressions": total_impressions,
        "total_conversions": total_conversions,
        "avg_ctr": total_clicks / total_impressions if total_impressions else 0,
        "avg_cpc": total_spend / total_clicks if total_clicks else 0,
    }
    db.upsert_daily_report(today, report)
    logger.info(f"Report: spend=${total_spend:.2f}, clicks={total_clicks}, conv={total_conversions}")

    # Gmail 발송
    try:
        from reporter.gmail import send_report_email
        send_report_email(report)
    except Exception as e:
        logger.warning(f"Report email skipped: {e}")

    logger.info("Task: generate_report done")


def refresh_meta_token():
    """매주 월요일: Meta 장기 토큰 갱신"""
    import subprocess
    import sys

    logger.info("Task: refresh_meta_token started")
    result = subprocess.run(
        [sys.executable, "scripts/refresh_meta_token.py"],
        capture_output=True, text=True,
    )
    if result.returncode == 0:
        logger.info(f"Meta token refreshed: {result.stdout.strip()}")
    else:
        logger.error(f"Meta token refresh failed: {result.stderr}")
