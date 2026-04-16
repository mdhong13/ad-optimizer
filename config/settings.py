"""
전역 설정 — .env.global 로드
"""
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# .env.global → 프로젝트 .env 순서로 로드 (프로젝트 .env가 override)
load_dotenv("D:/0_Dotcell/.env.global")
load_dotenv(BASE_DIR / ".env", override=True)


class Settings:
    # --- Anthropic ---
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    AGENT_MODEL: str = "claude-sonnet-4-6"

    # --- 로컬 LLM (d4win) ---
    LOCAL_LLM_BASE_URL: str = os.getenv("LOCAL_LLM_BASE_URL", "http://d4win.iptime.org:31088")
    LOCAL_LLM_CHAT_ENDPOINT: str = os.getenv("LOCAL_LLM_CHAT_ENDPOINT", "/v1/chat/completions")
    LOCAL_LLM_MODELS_ENDPOINT: str = os.getenv("LOCAL_LLM_MODELS_ENDPOINT", "/v1/models")

    # --- Gemini ---
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    # --- Meta Ads ---
    META_APP_ID: str = os.getenv("META_APP_ID", "")
    META_APP_SECRET: str = os.getenv("META_APP_SECRET", "")
    META_ACCESS_TOKEN: str = os.getenv("META_ACCESS_TOKEN", "")
    META_AD_ACCOUNT_ID: str = os.getenv("META_AD_ACCOUNT_ID", "act_659784790884319")

    # --- Google Ads ---
    GOOGLE_ADS_DEVELOPER_TOKEN: str = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    GOOGLE_ADS_CLIENT_ID: str = os.getenv("GOOGLE_ADS_CLIENT_ID", "")
    GOOGLE_ADS_CLIENT_SECRET: str = os.getenv("GOOGLE_ADS_CLIENT_SECRET", "")
    GOOGLE_ADS_REFRESH_TOKEN: str = os.getenv("GOOGLE_ADS_REFRESH_TOKEN", "")
    GOOGLE_ADS_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "7958648888")
    GOOGLE_ADS_LOGIN_CUSTOMER_ID: str = os.getenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "4894234221")

    # --- Gmail ---
    GMAIL_REFRESH_TOKEN: str = os.getenv("GMAIL_REFRESH_TOKEN", "")

    # --- Threads ---
    THREADS_APP_ID: str = os.getenv("THREADS_APP_ID", "")
    THREADS_APP_SECRET: str = os.getenv("THREADS_APP_SECRET", "")

    # --- YouTube [ONEMSG] (mdhong13@gmail.com, ad-optimizer용) ---
    YOUTUBE_ONEMSG_API_KEY: str = os.getenv("YOUTUBE_ONEMSG_API_KEY", "")
    YOUTUBE_ONEMSG_OAUTH_CLIENT_ID: str = os.getenv("YOUTUBE_ONEMSG_OAUTH_CLIENT_ID", "")
    YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET: str = os.getenv("YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET", "")
    YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN: str = os.getenv("YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN", "")

    # --- YouTube [QCAT] (bungbungcar13@gmail.com, QuantumCat용 — 참조만) ---
    YOUTUBE_QCAT_API_KEY: str = os.getenv("YOUTUBE_QCAT_API_KEY", "")

    # --- X (Twitter) [ONEMSG] (mdhong13@gmail.com, @onemsgx) ---
    TWITTER_API_KEY: str = os.getenv("TWITTER_API_KEY", "")
    TWITTER_API_SECRET: str = os.getenv("TWITTER_API_SECRET", "")
    TWITTER_ACCESS_TOKEN: str = os.getenv("TWITTER_ACCESS_TOKEN", "")
    TWITTER_ACCESS_TOKEN_SECRET: str = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
    TWITTER_BEARER_TOKEN: str = os.getenv("TWITTER_BEARER_TOKEN", "")
    TWITTER_CLIENT_ID: str = os.getenv("TWITTER_CLIENT_ID", "")
    TWITTER_CLIENT_SECRET: str = os.getenv("TWITTER_CLIENT_SECRET", "")
    TWITTER_ADS_ACCOUNT_ID: str = os.getenv("TWITTER_ADS_ACCOUNT_ID", "")  # X Ads API 계정 ID (승인 후 발급)

    # --- Reddit Ads [ONEMSG] ---
    # Reddit 앱: https://reddit.com/prefs/apps (script 타입)
    # 광고 계정: https://ads.reddit.com (account_id는 a2_xxx 형식)
    REDDIT_CLIENT_ID: str = os.getenv("REDDIT_CLIENT_ID", "")
    REDDIT_CLIENT_SECRET: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    REDDIT_REFRESH_TOKEN: str = os.getenv("REDDIT_REFRESH_TOKEN", "")
    REDDIT_ADS_ACCOUNT_ID: str = os.getenv("REDDIT_ADS_ACCOUNT_ID", "")
    REDDIT_USER_AGENT: str = os.getenv("REDDIT_USER_AGENT", "OneMsg-Ad-Optimizer/1.0 by onemsgx")

    # --- MongoDB ---
    MONGODB_URI: str = os.getenv("MONGODB_URI", "")
    MONGODB_DB: str = os.getenv("AD_OPTIMIZER_DB", "ad_optimizer")

    # --- App ---
    APP_ENV: str = os.getenv("APP_ENV", "development")
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    # --- Campaign Optimizer ---
    CAMPAIGN_CYCLE_HOURS: int = int(os.getenv("CAMPAIGN_CYCLE_HOURS", "8"))
    CAMPAIGNS_PER_CYCLE: int = int(os.getenv("CAMPAIGNS_PER_CYCLE", "20"))
    CAMPAIGNS_SURVIVE: int = int(os.getenv("CAMPAIGNS_SURVIVE", "2"))
    BUDGET_CHANGE_LIMIT_PCT: int = int(os.getenv("BUDGET_CHANGE_LIMIT_PCT", "30"))

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


settings = Settings()
