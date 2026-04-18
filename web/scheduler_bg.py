"""
FastAPI 프로세스 내에서 돌아가는 BackgroundScheduler.
별도 워커 프로세스 없이 웹 서비스 한 개만 돌려도 자동 스케줄이 동작.
"""
import logging
import os
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from scheduler.tasks import (
    collect_performance,
    run_campaign_cycle,
    check_market_events,
    generate_report,
    refresh_meta_token,
)

logger = logging.getLogger(__name__)

_scheduler: Optional[BackgroundScheduler] = None

JOB_DEFS = [
    {
        "id": "collect_performance",
        "name": "성과 데이터 수집",
        "func": collect_performance,
        "trigger": CronTrigger(minute=0, hour="*/2"),
        "period": "매 2시간",
    },
    {
        "id": "run_campaign_cycle",
        "name": "캠페인 최적화 사이클 (20→2)",
        "func": run_campaign_cycle,
        "trigger": CronTrigger(minute=0, hour="*/8"),
        "period": "매 8시간",
    },
    {
        "id": "check_market_events",
        "name": "크립토 시장 체크",
        "func": check_market_events,
        "trigger": CronTrigger(minute=0),
        "period": "매 1시간",
    },
    {
        "id": "generate_report",
        "name": "일간 리포트",
        "func": generate_report,
        "trigger": CronTrigger(hour=20, minute=0),
        "period": "매일 20:00",
    },
    {
        "id": "refresh_meta_token",
        "name": "Meta 토큰 갱신",
        "func": refresh_meta_token,
        "trigger": CronTrigger(day_of_week="mon", hour=3),
        "period": "매주 월 03:00",
    },
]


def start() -> None:
    global _scheduler
    if _scheduler is not None:
        return
    if os.environ.get("DISABLE_BG_SCHEDULER") == "1":
        logger.info("BackgroundScheduler disabled via DISABLE_BG_SCHEDULER=1")
        return

    tz = os.environ.get("SCHEDULER_TZ", "Asia/Seoul")
    sched = BackgroundScheduler(timezone=tz)
    for job in JOB_DEFS:
        sched.add_job(
            func=job["func"],
            trigger=job["trigger"],
            id=job["id"],
            name=job["name"],
            replace_existing=True,
            max_instances=1,
            misfire_grace_time=300,
            coalesce=True,
        )
        logger.info(f"[bg-scheduler] registered: {job['id']} ({job['period']})")
    sched.start()
    _scheduler = sched
    logger.info("[bg-scheduler] started")


def shutdown() -> None:
    global _scheduler
    if _scheduler is None:
        return
    try:
        _scheduler.shutdown(wait=False)
    finally:
        _scheduler = None
    logger.info("[bg-scheduler] shutdown")


def status() -> dict:
    if _scheduler is None:
        return {"running": False, "jobs": []}
    jobs = []
    for j in _scheduler.get_jobs():
        next_run: Optional[datetime] = j.next_run_time
        jobs.append({
            "id": j.id,
            "name": j.name,
            "next_run": next_run.isoformat() if next_run else None,
        })
    return {"running": _scheduler.running, "jobs": jobs}
