"""
Reddit OAuth refresh_token 발급 스크립트 (1회 실행)

사전:
  1. https://reddit.com/prefs/apps 에서 'script' 타입 앱 생성
     - redirect URI: http://localhost:8080
  2. .env.global에 REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET 저장

실행:
  py scripts/reddit_oauth.py

브라우저가 열리면 Reddit 계정으로 로그인 → 권한 승인 → 자동으로 REDDIT_REFRESH_TOKEN이 .env.global에 저장됨.
"""
import sys
import webbrowser
import secrets
import urllib.parse
import http.server
import socketserver
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings import settings

REDIRECT_URI = "http://localhost:8080"
SCOPES = "adsread adsedit adsconversions read identity"
ENV_FILE = Path("D:/0_Dotcell/.env.global")

received_code = {"code": None, "state": None}


class OAuthHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        qs = urllib.parse.parse_qs(parsed.query)
        received_code["code"] = qs.get("code", [None])[0]
        received_code["state"] = qs.get("state", [None])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<h1>OK</h1><p>You can close this window. Returning to terminal...</p>")

    def log_message(self, *args):
        pass


def main():
    if not settings.REDDIT_CLIENT_ID or not settings.REDDIT_CLIENT_SECRET:
        print("ERROR: REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET not in .env.global")
        return

    state = secrets.token_urlsafe(16)
    auth_url = (
        "https://www.reddit.com/api/v1/authorize?"
        + urllib.parse.urlencode({
            "client_id": settings.REDDIT_CLIENT_ID,
            "response_type": "code",
            "state": state,
            "redirect_uri": REDIRECT_URI,
            "duration": "permanent",
            "scope": SCOPES,
        })
    )

    print("=" * 60)
    print("[1/3] 브라우저 인증")
    print(f"URL: {auth_url}")
    print("=" * 60)

    server = socketserver.TCPServer(("localhost", 8080), OAuthHandler)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()

    webbrowser.open(auth_url)
    print("\n브라우저에서 승인을 기다리는 중...")

    while not received_code["code"]:
        import time
        time.sleep(0.3)

    server.shutdown()

    if received_code["state"] != state:
        print("ERROR: state mismatch")
        return

    code = received_code["code"]
    print(f"\n[2/3] Authorization code 수신: {code[:20]}...")

    # code → refresh_token 교환
    import httpx
    resp = httpx.post(
        "https://www.reddit.com/api/v1/access_token",
        auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"User-Agent": settings.REDDIT_USER_AGENT},
        timeout=30,
    )
    if resp.status_code != 200:
        print(f"ERROR: token exchange failed ({resp.status_code}): {resp.text}")
        return

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")
    if not refresh_token:
        print(f"ERROR: no refresh_token in response: {tokens}")
        return

    print(f"\n[3/3] refresh_token 발급 완료")
    print(f"  refresh_token: {refresh_token[:20]}...")

    # .env.global 업데이트
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith("REDDIT_REFRESH_TOKEN="):
            lines[i] = f"REDDIT_REFRESH_TOKEN={refresh_token}"
            updated = True
            break
    if not updated:
        lines.append(f"REDDIT_REFRESH_TOKEN={refresh_token}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n.env.global 업데이트 완료")

    # 즉시 사용자 정보 확인
    me_resp = httpx.get(
        "https://oauth.reddit.com/api/v1/me",
        headers={
            "Authorization": f"Bearer {access_token}",
            "User-Agent": settings.REDDIT_USER_AGENT,
        },
        timeout=15,
    )
    if me_resp.status_code == 200:
        me = me_resp.json()
        print(f"\n로그인 계정: u/{me.get('name', '?')} (karma: {me.get('total_karma', 0)})")
    print("\n다음: ads.reddit.com 에서 Ad Account ID 확인 → REDDIT_ADS_ACCOUNT_ID 에 저장")


if __name__ == "__main__":
    main()
