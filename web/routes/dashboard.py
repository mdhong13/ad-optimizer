from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_recent_performance, get_recent_market_events

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("/")
async def dashboard(request: Request):
    performance = get_recent_performance(days=7)
    events = get_recent_market_events(limit=5)

    totals = {"spend": 0, "clicks": 0, "impressions": 0, "conversions": 0}
    for r in performance:
        totals["spend"] += r.get("spend", 0)
        totals["clicks"] += r.get("clicks", 0)
        totals["impressions"] += r.get("impressions", 0)
        totals["conversions"] += r.get("conversions", 0)

    avg_roas = sum(r.get("roas", 0) for r in performance) / len(performance) if performance else 0
    avg_ctr = sum(r.get("ctr", 0) for r in performance) / len(performance) if performance else 0

    return templates.TemplateResponse(request, "dashboard.html", {
        "performance": performance,
        "events": events,
        "totals": totals,
        "avg_roas": round(avg_roas, 2),
        "avg_ctr": round(avg_ctr * 100, 2),
    })


@router.get("/api/performance")
async def api_performance(days: int = 7, platform: str = None):
    return get_recent_performance(platform=platform, days=days)
