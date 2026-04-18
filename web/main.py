"""
FastAPI 웹 대시보드 진입점
"""
import logging
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    stream=sys.stdout,
    force=True,
)

from storage.db import init_db
from web import live_logs, scheduler_bg
from web.routes import dashboard, campaigns, decisions, scheduler, events, viral, publisher, settings

live_logs.install_handler()

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
    import asyncio
    live_logs.set_loop(asyncio.get_running_loop())
    init_db()
    scheduler_bg.start()


@app.on_event("shutdown")
async def shutdown():
    scheduler_bg.shutdown()


@app.get("/health")
async def health():
    return {"status": "ok", "app": "OneMessage Ad Optimizer", "version": "2.0.0"}


@app.get("/api/scheduler/status")
async def scheduler_status():
    return scheduler_bg.status()
