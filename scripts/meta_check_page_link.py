"""Meta 광고 계정 ↔ 페이지 연결 확인.

사용법:
  python scripts/meta_check_page_link.py                           # 기본 계정
  python scripts/meta_check_page_link.py --account 481473468715453 # One MSG
  python scripts/meta_check_page_link.py --account 481473468715453 --page 1119028374620625
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from config.settings import settings

GRAPH = "https://graph.facebook.com/v25.0"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default=None,
                    help="광고 계정 ID (act_ 접두사 생략 가능). 기본: settings.META_AD_ACCOUNT_ID")
    ap.add_argument("--page", default=None,
                    help="연결 확인할 Page ID. 기본: settings.META_PAGE_ID")
    args = ap.parse_args()

    acc = args.account or settings.META_AD_ACCOUNT_ID
    if not acc.startswith("act_"):
        acc = f"act_{acc}"
    page = args.page or settings.META_PAGE_ID
    token = settings.META_ACCESS_TOKEN

    print(f"\n=== 광고 계정 ↔ 페이지 연결 확인 ===")
    print(f"광고 계정: {acc}")
    print(f"확인 페이지: {page or '(미지정)'}\n")

    # 1. 광고 계정 기본 정보
    print("--- 광고 계정 정보 ---")
    r = requests.get(
        f"{GRAPH}/{acc}",
        params={"fields": "name,account_status,currency,timezone_name,business",
                "access_token": token},
    )
    business_id = None
    if r.status_code == 200:
        d = r.json()
        print(f"  이름: {d.get('name')}")
        print(f"  상태: {d.get('account_status')} (1=ACTIVE)")
        print(f"  통화: {d.get('currency')} / 타임존: {d.get('timezone_name')}")
        if d.get("business"):
            b = d["business"]
            business_id = b.get("id")
            print(f"  비즈니스 포트폴리오: {b.get('name')} ({business_id})")
    else:
        print(f"  [ERROR] {r.status_code} {r.text}")
        return

    # 2. 페이지 자체 조회 (토큰으로 접근 가능한지)
    if page:
        print(f"\n--- 페이지 {page} 조회 ---")
        r = requests.get(
            f"{GRAPH}/{page}",
            params={"fields": "id,name,category,link,access_token", "access_token": token},
        )
        if r.status_code == 200:
            d = r.json()
            print(f"  이름: {d.get('name')}")
            print(f"  카테고리: {d.get('category', '')}")
            print(f"  링크: {d.get('link', '')}")
            print(f"  페이지 토큰 발급: {'있음' if d.get('access_token') else '없음 (권한 부족 가능)'}")
        else:
            print(f"  [ERROR] {r.status_code} {r.text}")

    # 3. 비즈니스 포트폴리오 소유 페이지 목록
    if business_id:
        print(f"\n--- 비즈니스 포트폴리오 {business_id} 소유 페이지 ---")
        r = requests.get(
            f"{GRAPH}/{business_id}/owned_pages",
            params={"fields": "id,name,category", "access_token": token},
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            if not data:
                print("  (없음)")
            matched = False
            for p in data:
                mark = " ← 대상" if page and p["id"] == page else ""
                print(f"  {p['id']}  {p.get('name', '')}  [{p.get('category', '')}]{mark}")
                matched = matched or (page and p["id"] == page)
            if page:
                if matched:
                    print(f"\n  [OK] 페이지 {page} 가 비즈니스 포트폴리오 소유 → 광고 집행 가능")
                else:
                    print(f"\n  [WARN] 페이지 {page} 가 비즈니스 포트폴리오에 없음")
                    print(f"         비즈니스 설정 → 계정 → 페이지 → 페이지 추가")
        else:
            print(f"  [ERROR] {r.status_code} {r.text}")

        # 4. client_pages (소유는 아니지만 접근 가능한 페이지)
        print(f"\n--- 비즈니스 포트폴리오 {business_id} 접근 가능 페이지 (client_pages) ---")
        r = requests.get(
            f"{GRAPH}/{business_id}/client_pages",
            params={"fields": "id,name,category", "access_token": token},
        )
        if r.status_code == 200:
            data = r.json().get("data", [])
            if not data:
                print("  (없음)")
            for p in data:
                mark = " ← 대상" if page and p["id"] == page else ""
                print(f"  {p['id']}  {p.get('name', '')}  [{p.get('category', '')}]{mark}")

    # 5. 사용자가 관리하는 페이지 목록 (me/accounts)
    print("\n--- 내가 관리하는 페이지 (me/accounts) ---")
    r = requests.get(
        f"{GRAPH}/me/accounts",
        params={"fields": "id,name,category,tasks", "access_token": token},
    )
    if r.status_code == 200:
        data = r.json().get("data", [])
        if not data:
            print("  (없음)")
        for p in data:
            mark = " ← 대상" if page and p["id"] == page else ""
            print(f"  {p['id']}  {p.get('name', '')}  [{p.get('category', '')}]{mark}")
    else:
        print(f"  [ERROR] {r.status_code}")

    print()


if __name__ == "__main__":
    main()
