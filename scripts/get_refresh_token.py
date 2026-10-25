"""
Google Ads API OAuth2 Refresh Token 생성
브라우저에서 Google 로그인 → 권한 승인 → refresh_token 출력
"""
import os

from dotenv import load_dotenv

# 10-25 — 비밀값은 코드에 두지 않는다(공개 저장소에 6개월 박혀 있었음 · 교체 대상). 값은 .env.global 에만.
load_dotenv("D:/0_Dotcell/.env.global")
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = os.environ["GOOGLE_ADS_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_ADS_CLIENT_SECRET"]

SCOPES = ["https://www.googleapis.com/auth/adwords"]

client_config = {
    "installed": {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"],
    }
}

flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
creds = flow.run_local_server(port=8080, prompt="consent", access_type="offline")

print("\n" + "=" * 50)
print("Refresh Token (아래 값을 .env.global에 저장):")
print("=" * 50)
print(creds.refresh_token)
print("=" * 50)
