"""
Gmail API OAuth2 Refresh Token 생성
bungbungcar13@gmail.com으로 로그인하세요
"""
from google_auth_oauthlib.flow import InstalledAppFlow

CLIENT_ID = "352203835844-ia1id3gvn4il2snqkjeu1l2f2mlejr4g.apps.googleusercontent.com"
CLIENT_SECRET = "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"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
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
