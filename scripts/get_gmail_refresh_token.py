"""
Gmail API OAuth2 Refresh Token 생성
bungbungcar13@gmail.com으로 로그인하세요
"""
import os

from dotenv import load_dotenv

# 10-25 — 비밀값은 코드에 두지 않는다(공개 저장소에 6개월 박혀 있었음 · 교체 대상). 값은 .env.global 에만.
load_dotenv("D:/0_Dotcell/.env.global")
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = os.environ["GOOGLE_ADS_CLIENT_ID"]
CLIENT_SECRET = os.environ["GOOGLE_ADS_CLIENT_SECRET"]

# 10-25 — 보내기만(리포트·알림 메일). 읽기 권한은 쓰지 않아서 뺐다.
SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]

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
creds = flow.run_local_server(port=8081, prompt="consent", access_type="offline")

print("\n" + "=" * 50)
print("Gmail Refresh Token:")
print("=" * 50)
print(creds.refresh_token)
print("=" * 50)
