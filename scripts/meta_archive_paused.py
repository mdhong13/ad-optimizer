"""Meta 일괄 아카이브 — PAUSED/CAMPAIGN_PAUSED 캠페인 전부 ARCHIVED로 전환.

사용법:
  python scripts/meta_archive_paused.py            # dry-run (목록만 출력)
  python scripts/meta_archive_paused.py --apply    # 실제 아카이브 실행
  python scripts/meta_archive_paused.py --apply --keep "사본"   # 이름에 '사본' 포함된 건 제외
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config.settings import settings
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign as FBCampaign


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 아카이브 실행 (기본은 dry-run)")
    ap.add_argument("--keep", default="", help="이름에 이 문자열이 포함된 캠페인은 제외")
    ap.add_argument("--statuses", nargs="+",
                    default=["PAUSED", "CAMPAIGN_PAUSED", "ADSET_PAUSED"],
                    help="대상 effective_status (기본: PAUSED/CAMPAIGN_PAUSED/ADSET_PAUSED)")
    args = ap.parse_args()

    FacebookAdsApi.init(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=settings.META_ACCESS_TOKEN,
    )
    account = AdAccount(settings.META_AD_ACCOUNT_ID)

    print(f"\n=== Meta Archive — {settings.META_AD_ACCOUNT_ID} ===")
    print(f"대상 상태: {args.statuses}")
    print(f"제외 키워드: '{args.keep}'" if args.keep else "제외 키워드: (없음)")
    print(f"모드: {'APPLY (실제 아카이브)' if args.apply else 'DRY-RUN (목록만)'}\n")

    # 대상 수집
    targets = []
    for status in args.statuses:
        try:
            campaigns = account.get_campaigns(
                fields=[FBCampaign.Field.id, FBCampaign.Field.name,
                        FBCampaign.Field.effective_status, FBCampaign.Field.created_time],
                params={"effective_status": [status], "limit": 500},
            )
            for c in campaigns:
                name = c.get("name", "")
                if args.keep and args.keep in name:
                    continue
                targets.append({
                    "id": c["id"],
                    "name": name,
                    "status": c.get("effective_status", ""),
                    "created": c.get("created_time", "")[:10],
                })
        except Exception as e:
            print(f"[WARN] {status} 조회 실패: {e}")

    # 중복 제거 (ID 기준)
    seen = set()
    unique = []
    for t in targets:
        if t["id"] not in seen:
            seen.add(t["id"])
            unique.append(t)
    targets = unique

    print(f"대상 캠페인 총 {len(targets)}개\n")
    for t in targets[:20]:
        print(f"  [{t['status']:<18}] {t['id']}  {t['name'][:50]}  ({t['created']})")
    if len(targets) > 20:
        print(f"  ...외 {len(targets) - 20}개")
    print()

    if not targets:
        print("아카이브할 캠페인 없음.")
        return

    if not args.apply:
        print("--apply 안 붙였으므로 실제 실행은 생략. 목록 확인 후 재실행하세요.")
        return

    # 실행
    print(f"{len(targets)}개 아카이브 진행 중...\n")
    ok, fail = 0, 0
    for i, t in enumerate(targets, 1):
        try:
            c = FBCampaign(t["id"])
            c.api_update(params={FBCampaign.Field.status: "ARCHIVED"})
            ok += 1
            print(f"  [{i:3d}/{len(targets)}] OK     {t['id']}  {t['name'][:40]}")
        except Exception as e:
            fail += 1
            print(f"  [{i:3d}/{len(targets)}] FAIL   {t['id']}  {t['name'][:40]}  → {e}")
        # rate limit 여유
        if i % 20 == 0:
            time.sleep(1)

    print(f"\n완료: 성공 {ok} / 실패 {fail}")


if __name__ == "__main__":
    main()
