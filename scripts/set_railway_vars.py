"""Railway 환경변수 설정 스크립트 (httpx)"""
import json
import httpx

PROJECT_ID = "36a78a1c-ca46-4ed2-ba9a-ceb64e806647"
ENV_ID = "f8251947-3685-4c55-90e4-0900cef37463"
SERVICE_ID = "be362de3-0b00-4ccf-a7c6-946ff4d9c287"
ENV_FILE = "D:/0_Dotcell/.env.global"

KEYS_TO_SET = [
    # LLM & Core
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "MONGODB_URI",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "GOOGLE_ADS_REFRESH_TOKEN",
    "GMAIL_REFRESH_TOKEN",
    "LOCAL_LLM_BASE_URL",
    # YouTube ONEMSG (mdhong13@gmail.com)
    "YOUTUBE_ONEMSG_API_KEY",
    "YOUTUBE_ONEMSG_OAUTH_CLIENT_ID",
    "YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET",
    "YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN",
    # X/Twitter ONEMSG (@onemsgx, mdhong13@gmail.com)
    "TWITTER_API_KEY",
    "TWITTER_API_SECRET",
    "TWITTER_ACCESS_TOKEN",
    "TWITTER_ACCESS_TOKEN_SECRET",
    "TWITTER_BEARER_TOKEN",
    "TWITTER_CLIENT_ID",
    "TWITTER_CLIENT_SECRET",
    # Reddit Ads
    "REDDIT_CLIENT_ID",
    "REDDIT_CLIENT_SECRET",
    "REDDIT_REFRESH_TOKEN",
    "REDDIT_ADS_ACCOUNT_ID",
    "REDDIT_USER_AGENT",
    # QCat RAG (2026-07-10 감사 · 광명 이전 후 raw IP 정본)
    "QCAT_RAG_URL",
    # Gemini (2026-07-10 감사 · handoff.md 06-02 자체 미커밋 지적 반영)
    "GEMINI_API_KEY",
    # NAVER OpenAPI (SEO 키워드 발견)
    "NAVER_OPENAPI_CLIENT_ID",
    "NAVER_OPENAPI_CLIENT_SECRET",
    # NAVER 검색광고 (platforms/naver_ads.py 읽기 전용 지출 조회 · 2026-08-17)
    "NAVER_SEARCHAD_CUSTOMER_ID",
    "NAVER_SEARCHAD_ACCESS_LICENSE",
    "NAVER_SEARCHAD_SECRET_KEY",
    # Telegram (경보·알림 chatops)
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    # Alerts (내부 알림 API)
    "ALERT_API_KEY",
    # Admin (adteam.onemsg.net 관리자)
    "ADMIN_USERNAME",
    "ADMIN_PASSWORD",
    # Knowin worker (지식인 자동 답글 워커)
    "KNOWIN_WORKER_API_KEY",
]


def load_env(path):
    result = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            k, v = line.split("=", 1)
            result[k] = v
    return result


def set_var(name, value, token):
    query = "mutation($input: VariableUpsertInput!) { variableUpsert(input: $input) }"
    variables = {
        "input": {
            "projectId": PROJECT_ID,
            "environmentId": ENV_ID,
            "serviceId": SERVICE_ID,
            "name": name,
            "value": value,
        }
    }
    for attempt in range(3):
        try:
            r = httpx.post(
                "https://backboard.railway.com/graphql/v2",
                json={"query": query, "variables": variables},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                timeout=60,
            )
            data = r.json()
            if "errors" in data:
                print(f"  FAIL: {name} - {data['errors'][0]['message']}")
            else:
                print(f"  OK: {name}")
            return
        except (httpx.ReadTimeout, httpx.ConnectTimeout) as e:
            if attempt == 2:
                print(f"  TIMEOUT: {name} (3 attempts)")
                return
            print(f"  retry {name} ({attempt+1}/3)...")


if __name__ == "__main__":
    env = load_env(ENV_FILE)
    token = env.get("RAILWAY_TOKEN", "")

    for key in KEYS_TO_SET:
        value = env.get(key, "")
        if value:
            set_var(key, value, token)
        else:
            print(f"  SKIP: {key} (empty)")

    print("Done!")
