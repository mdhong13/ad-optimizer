from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

from config.settings import settings

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


def _mask(value: str) -> str:
    """API 키 마스킹"""
    if not value or len(value) < 8:
        return "미설정" if not value else "***"
    return value[:4] + "****" + value[-4:]


@router.get("")
async def settings_page(request: Request):
    api_status = {
        "Anthropic (Claude)": bool(settings.ANTHROPIC_API_KEY),
        "Local LLM (d4win)": bool(settings.LOCAL_LLM_BASE_URL),
        "Google Ads": bool(settings.GOOGLE_ADS_DEVELOPER_TOKEN),
        "Meta Ads": bool(settings.META_ACCESS_TOKEN),
        "Gmail": bool(settings.GMAIL_REFRESH_TOKEN),
        "Threads": bool(settings.THREADS_APP_ID),
        "Gemini (Google API)": bool(settings.GEMINI_API_KEY),
        "MongoDB": bool(settings.MONGODB_URI),
    }

    config_info = {
        "APP_ENV": settings.APP_ENV,
        "DRY_RUN": settings.DRY_RUN,
        "CAMPAIGN_CYCLE_HOURS": settings.CAMPAIGN_CYCLE_HOURS,
        "CAMPAIGNS_PER_CYCLE": settings.CAMPAIGNS_PER_CYCLE,
        "CAMPAIGNS_SURVIVE": settings.CAMPAIGNS_SURVIVE,
        "BUDGET_CHANGE_LIMIT_PCT": settings.BUDGET_CHANGE_LIMIT_PCT,
        "META_AD_ACCOUNT_ID": settings.META_AD_ACCOUNT_ID,
        "GOOGLE_ADS_CUSTOMER_ID": settings.GOOGLE_ADS_CUSTOMER_ID,
        "MONGODB_DB": settings.MONGODB_DB,
    }

    return templates.TemplateResponse("settings.html", {
        "request": request,
        "api_status": api_status,
        "config_info": config_info,
    })
