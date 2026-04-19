"""
APScheduler 기반 스케줄 러너
"""
import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.tasks import (
    collect_performance,
    run_campaign_cycle,
    check_market_events,
    generate_report,
    refresh_meta_token,
    publish_fb_story_en,
)
from storage.db import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

SCHEDULES = [
    {
        "func": collect_performance,
        "trigger": CronTrigger(minute=0, hour="*/2"),     # 매 2시간
        "id": "collect_performance",
        "name": "성과 데이터 수집",
    },
    {
        "func": run_campaign_cycle,
        "trigger": CronTrigger(minute=0, hour="*/8"),     # 매 8시간
        "id": "run_campaign_cycle",
        "name": "캠페인 최적화 사이클 (20→2)",
    },
    {
        "func": check_market_events,
        "trigger": CronTrigger(minute=0),                  # 매 1시간
        "id": "check_market_events",
        "name": "크립토 시장 체크",
    },
    {
        "func": generate_report,
        "trigger": CronTrigger(hour=20, minute=0),         # 매일 20:00
        "id": "generate_report",
        "name": "일간 리포트 생성 + Gmail 발송",
    },
    {
        "func": refresh_meta_token,
        "trigger": CronTrigger(day_of_week="mon", hour=3), # 매주 월 03:00
        "id": "refresh_meta_token",
        "name": "Meta 토큰 갱신",
    },
    {
        "func": publish_fb_story_en,
        # 22:30 KST = 08:30 EST / 09:30 EDT (미국 FB 엔게이지먼트 피크)
        "trigger": CronTrigger(hour=22, minute=30),
        "id": "publish_fb_story_en",
        "name": "OneMessage FB EN 일일 스토리 포스트",
    },
]


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="Asia/Seoul")
    for job in SCHEDULES:
        scheduler.add_job(
            func=job["func"],
            trigger=job["trigger"],
            id=job["id"],
            name=job["name"],
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
        )
        logger.info(f"Scheduled: [{job['id']}] {job['name']}")
    return scheduler


def main():
    init_db()
    logger.info("Ad Optimizer Scheduler v2 starting...")

    scheduler = build_scheduler()

    def _shutdown(signum, frame):
        logger.info("Shutting down scheduler...")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info("Scheduler running. Press Ctrl+C to stop.")
    scheduler.start()


if __name__ == "__main__":
    main()
