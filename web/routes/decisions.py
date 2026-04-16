from fastapi import APIRouter, Request, HTTPException
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import get_pending_decisions, update_decision_status, get_collection

router = APIRouter(prefix="/decisions")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


@router.get("")
async def decisions_page(request: Request):
    pending = get_pending_decisions()

    # 최근 50건 (MongoDB)
    cursor = get_collection("agent_decisions").find(
        {}, {"_id": 0}
    ).sort("created_at", -1).limit(50)
    recent = list(cursor)

    return templates.TemplateResponse(request, "decisions.html", {
        "pending": pending,
        "recent": recent,
    })


@router.post("/approve/{decision_id}")
async def approve_decision(decision_id: str):
    update_decision_status(decision_id, "executed")
    return {"success": True, "decision_id": decision_id}


@router.post("/reject/{decision_id}")
async def reject_decision(decision_id: str):
    update_decision_status(decision_id, "rejected")
    return {"success": True, "decision_id": decision_id}


@router.get("/api/pending")
async def api_pending():
    return get_pending_decisions()
