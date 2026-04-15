"""
FastAPI 웹 대시보드 진입점
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

from storage.db import init_db
from web.routes import dashboard, campaigns, decisions, scheduler, events, viral, publisher, settings

app = FastAPI(title="OneMessage Ad Optimizer", version="2.0.0")

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Static files (CSS, JS, PWA)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(dashboard.router)
app.include_router(campaigns.router)
app.include_router(decisions.router)
app.include_router(scheduler.router)
app.include_router(events.router)
app.include_router(viral.router)
app.include_router(publisher.router)
app.include_router(settings.router)


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
async def health():
    return {"status": "ok", "app": "OneMessage Ad Optimizer", "version": "2.0.0"}
