from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_recent_market_events

router = APIRouter(prefix="/events")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def events_page(request: Request):
    events = get_recent_market_events(limit=50)
    return templates.TemplateResponse(request, "events.html", {
        "events": events,
    })


@router.get("/api")
async def api_events(limit: int = 20):
    return get_recent_market_events(limit=limit)
