"""
YouTube OAuth 인증 — OneMessage 계정 (mdhong13@gmail.com) refresh_token 발급

실행:
  cd D:/0_Dotcell/ad-optimizer
  py scripts/youtube_onemsg_auth.py

흐름:
  1. 브라우저가 자동으로 열림
  2. mdhong13@gmail.com으로 로그인 (다른 계정으로 로그인되어 있으면 "계정 전환")
  3. "확인되지 않은 앱" 경고 → "고급" → "(안전하지 않음)으로 이동"
  4. YouTube 권한 승인
  5. 콘솔에 refresh_token 출력됨
  6. 자동으로 .env.global의 YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN 에 기록
"""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv("D:/0_Dotcell/.env.global")

CLIENT_ID = os.getenv("YOUTUBE_ONEMSG_OAUTH_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET", "")
ENV_PATH = Path("D:/0_Dotcell/.env.global")

# YouTube 권한 scope
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",       # 영상 업로드
    "https://www.googleapis.com/auth/youtube.force-ssl",    # 댓글 작성/수정
    "https://www.googleapis.com/auth/youtube.readonly",     # 채널/영상 읽기
]


def run_oauth_flow():
    if not CLIENT_ID or not CLIENT_SECRET:
        print("[ERROR] CLIENT_ID 또는 CLIENT_SECRET이 설정되지 않았습니다.")
        print("  .env.global의 YOUTUBE_ONEMSG_OAUTH_CLIENT_ID/SECRET을 확인하세요.")
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print("[ERROR] google-auth-oauthlib이 설치되지 않았습니다.")
        print("  py -m pip install google-auth-oauthlib")
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    print("=" * 60)
    print("YouTube OAuth 인증 시작 (OneMessage / mdhong13@gmail.com)")
    print("=" * 60)
    print()
    print("브라우저가 열립니다. mdhong13@gmail.com 으로 로그인하세요.")
    print("(다른 계정으로 로그인되어 있으면 '계정 전환' 필수)")
    print()

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)

    # access_type=offline + prompt=consent → 반드시 refresh_token 포함
    credentials = flow.run_local_server(
        host="localhost",
        port=0,                  # 빈 포트 자동 선택
        open_browser=True,
        access_type="offline",
        prompt="consent",
        authorization_prompt_message="",
        success_message="인증 성공! 이 창을 닫아도 됩니다.",
    )

    refresh_token = credentials.refresh_token
    if not refresh_token:
        print("[ERROR] refresh_token이 반환되지 않았습니다.")
        print("  다시 실행하고 '계정 전환' 후 '동의' 과정을 모두 거치세요.")
        sys.exit(1)

    print()
    print("=" * 60)
    print(f"REFRESH_TOKEN: {refresh_token}")
    print("=" * 60)
    print()

    # .env.global 자동 업데이트
    update_env_file(refresh_token)

    # 간단 API 테스트
    test_channel_info(credentials)


def update_env_file(refresh_token: str):
    content = ENV_PATH.read_text(encoding="utf-8")
    key = "YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN"
    new_line = f"{key}={refresh_token}"

    lines = content.splitlines()
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = new_line
            updated = True
            break

    if not updated:
        print(f"[WARN] .env.global에 {key} 항목이 없습니다. 수동으로 추가하세요.")
        return

    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] .env.global에 {key} 저장 완료")


def test_channel_info(credentials):
    try:
        from googleapiclient.discovery import build
        yt = build("youtube", "v3", credentials=credentials)
        resp = yt.channels().list(part="snippet,statistics", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            print("[WARN] 채널이 없습니다. YouTube 채널을 먼저 만드세요.")
            return
        ch = items[0]
        print("[TEST] 인증된 채널 정보:")
        print(f"  - 채널명: {ch['snippet']['title']}")
        print(f"  - 채널ID: {ch['id']}")
        print(f"  - 구독자: {ch['statistics'].get('subscriberCount', 'hidden')}")
        print(f"  - 영상수: {ch['statistics'].get('videoCount', 0)}")
    except ImportError:
        print("  google-api-python-client 설치 필요: py -m pip install google-api-python-client")
    except Exception as e:
        print(f"  API 테스트 실패: {e}")


if __name__ == "__main__":
    run_oauth_flow()
