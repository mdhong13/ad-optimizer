"""Zombie ARCHIVED 캠페인 진단 — 어떤 조작이 되고 안 되는지 하나씩 테스트.

사용법:
  python scripts/meta_zombie_diagnose.py --id 120244241563160219

테스트 항목:
  1. configured_status / effective_status / 원본 설정 확인
  2. name 필드만 업데이트 (가능해야 함 — Meta 에러 메시지 확인용)
  3. status 업데이트 (ARCHIVED → PAUSED) 재시도
  4. POST /{id}/copies 로 복제 시도 (가장 유망)
  5. Batch API 로 status 업데이트 시도
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests
from config.settings import settings
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.campaign import Campaign as FBCampaign


GRAPH = "https://graph.facebook.com/v25.0"


def hr(title):
    print(f"\n{'=' * 6} {title} {'=' * 6}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="진단할 캠페인 ID")
    ap.add_argument("--skip", nargs="*", default=[],
                    help="건너뛸 테스트 번호 (예: --skip 2 3)")
    args = ap.parse_args()

    cid = args.id
    token = settings.META_ACCESS_TOKEN

    FacebookAdsApi.init(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=token,
    )

    # ---------- 1. 상태 조회 ----------
    hr("1. 현재 상태 전체 조회")
    try:
        r = requests.get(
            f"{GRAPH}/{cid}",
            params={
                "fields": "id,name,status,configured_status,effective_status,"
                          "objective,created_time,updated_time,special_ad_categories,"
                          "daily_budget,lifetime_budget,can_use_spend_cap",
                "access_token": token,
            },
        )
        print(f"HTTP {r.status_code}")
        print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"[ERROR] {e}")

    # ---------- 2. name-only 업데이트 (가능해야 정상) ----------
    if "2" not in args.skip:
        hr("2. name 필드만 업데이트 (Meta 주장대로면 성공해야 함)")
        try:
            r = requests.post(
                f"{GRAPH}/{cid}",
                data={"name": "diag-test-rename", "access_token": token},
            )
            print(f"HTTP {r.status_code}")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[ERROR] {e}")

    # ---------- 3. status 업데이트 재시도 ----------
    if "3" not in args.skip:
        hr("3. status=PAUSED 업데이트 (SDK 방식)")
        try:
            c = FBCampaign(cid)
            c.api_update(params={FBCampaign.Field.status: "PAUSED"})
            print("OK — status 변경 성공!")
        except Exception as e:
            print(f"[FAIL] {e}")

    # ---------- 4. /copies 엔드포인트 (가장 유망) ----------
    if "4" not in args.skip:
        hr("4. POST /{id}/copies — 복제 시도 (수정 막혀도 복제는 가능할 수 있음)")
        try:
            r = requests.post(
                f"{GRAPH}/{cid}/copies",
                data={
                    "deep_copy": "true",
                    "status_option": "PAUSED",
                    "access_token": token,
                },
            )
            print(f"HTTP {r.status_code}")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
            if r.status_code == 200:
                data = r.json()
                new_id = data.get("copied_campaign_id") or data.get("id")
                if new_id:
                    print(f"\n>>> 새 캠페인 ID: {new_id} — 이걸로 재개하면 됩니다!")
        except Exception as e:
            print(f"[ERROR] {e}")

    # ---------- 5. Batch API ----------
    if "5" not in args.skip:
        hr("5. Batch API 로 status 업데이트")
        try:
            batch = [{
                "method": "POST",
                "relative_url": f"{cid}?status=PAUSED",
            }]
            r = requests.post(
                f"{GRAPH}/",
                data={
                    "batch": json.dumps(batch),
                    "access_token": token,
                },
            )
            print(f"HTTP {r.status_code}")
            print(json.dumps(r.json(), indent=2, ensure_ascii=False))
        except Exception as e:
            print(f"[ERROR] {e}")

    print("\n--- 진단 종료 ---")
    print("해석 가이드:")
    print("  - 2번 name 업데이트가 성공 → Meta 주장대로 'name only'. status 변경은 영구 불가.")
    print("  - 4번 /copies 가 성공 → 새 ID로 복제됨 → 일괄 복제 스크립트 만들어 복구 가능.")
    print("  - 2번까지 실패 → 토큰/권한 문제일 가능성, 다른 원인.")


if __name__ == "__main__":
    main()
