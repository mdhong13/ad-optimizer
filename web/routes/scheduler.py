from fastapi import APIRouter, Request, BackgroundTasks
from fastapi.templating import Jinja2Templates
from pathlib import Path

from scheduler.tasks import (
    collect_performance,
    check_market_events,
    run_campaign_cycle,
    generate_report,
    refresh_meta_token,
)

router = APIRouter(prefix="/scheduler")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))

TASKS = {
    "collect_performance": ("성과 데이터 수집", collect_performance),
    "check_market_events": ("크립토 시장 체크", check_market_events),
    "run_campaign_cycle": ("캠페인 최적화 사이클", run_campaign_cycle),
    "generate_report": ("일간 리포트 생성", generate_report),
    "refresh_meta_token": ("Meta 토큰 갱신", refresh_meta_token),
}

SCHEDULE_INFO = [
    {"id": "collect_performance", "name": "성과 데이터 수집", "cron": "0 */2 * * *", "period": "매 2시간"},
    {"id": "run_campaign_cycle", "name": "캠페인 최적화 사이클", "cron": "0 */8 * * *", "period": "매 8시간"},
    {"id": "check_market_events", "name": "크립토 시장 체크", "cron": "0 */1 * * *", "period": "매 1시간"},
    {"id": "generate_report", "name": "일간 리포트", "cron": "0 20 * * *", "period": "매일 20:00"},
    {"id": "refresh_meta_token", "name": "Meta 토큰 갱신", "cron": "0 3 * * 1", "period": "매주 월 03:00"},
]


@router.get("")
async def scheduler_page(request: Request):
    return templates.TemplateResponse(request, "scheduler.html", {
        "schedules": SCHEDULE_INFO,
    })


@router.post("/trigger/{task_id}")
async def trigger_task(task_id: str, background_tasks: BackgroundTasks):
    if task_id not in TASKS:
        return {"error": f"Unknown task: {task_id}"}
    name, func = TASKS[task_id]
    background_tasks.add_task(func)
    return {"triggered": True, "task": task_id, "name": name}
