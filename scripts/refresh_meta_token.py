"""
Meta 장기 토큰 자동 갱신
- 현재 토큰으로 새 장기 토큰(60일) 발급
- .env.global 파일 자동 업데이트
- 스케줄러에서 매주 실행 권장 (만료 전 갱신)
"""
import httpx
import re
import os
from datetime import datetime

ENV_FILE = "D:/0_Dotcell/.env.global"
APP_ID = "26414252244902498"
APP_SECRET = "4c62b28b5f2c071f6137f5f542b90ba7"


def get_current_token():
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.search(r"META_ACCESS_TOKEN=(\S+)", content)
    return match.group(1) if match else None


def refresh_token(current_token):
    r = httpx.get(
        "https://graph.facebook.com/v25.0/oauth/access_token",
        params={
            "grant_type": "fb_exchange_token",
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "fb_exchange_token": current_token,
        },
        timeout=30,
    )
    if r.status_code != 200:
        print(f"Error: {r.status_code} {r.text}")
        return None
    data = r.json()
    return data.get("access_token"), data.get("expires_in")


def update_env(new_token):
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 만료일 계산
    from datetime import timedelta
    expire_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")

    # 토큰 줄 교체
    content = re.sub(
        r"# 장기 토큰 \(60일.*\)\nMETA_ACCESS_TOKEN=\S+",
        f"# 장기 토큰 (60일, 만료: {expire_date} 경)\nMETA_ACCESS_TOKEN={new_token}",
        content,
    )

    with open(ENV_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  .env.global 업데이트 완료 (만료: {expire_date})")


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] Meta 토큰 갱신")

    current = get_current_token()
    if not current:
        print("  현재 토큰을 찾을 수 없습니다.")
        return

    # 토큰 유효성 확인
    r = httpx.get(
        "https://graph.facebook.com/v25.0/debug_token",
        params={"input_token": current, "access_token": f"{APP_ID}|{APP_SECRET}"},
        timeout=15,
    )
    if r.status_code == 200:
        info = r.json().get("data", {})
        expires = info.get("expires_at", 0)
        if expires:
            from datetime import timezone
            exp_dt = datetime.fromtimestamp(expires)
            days_left = (exp_dt - datetime.now()).days
            print(f"  현재 토큰 만료: {exp_dt.strftime('%Y-%m-%d')} ({days_left}일 남음)")
        else:
            days_left = -1
            print("  만료일 확인 불가")

    result = refresh_token(current)
    if result:
        new_token, expires_in = result
        print(f"  새 토큰 발급 성공 (유효: {expires_in // 86400}일)")
        update_env(new_token)
    else:
        print("  토큰 갱신 실패!")


if __name__ == "__main__":
    main()
