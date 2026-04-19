"""Meta 아카이브 복구 — ARCHIVED 캠페인을 PAUSED로 되돌림.

사용법:
  python scripts/meta_unarchive.py                          # dry-run, 전체 ARCHIVED 목록
  python scripts/meta_unarchive.py --apply                  # 전체 복구 (PAUSED로)
  python scripts/meta_unarchive.py --id 123 456 --apply     # 특정 ID만 복구
  python scripts/meta_unarchive.py --match "사본" --apply    # 이름에 '사본' 포함된 것만
  python scripts/meta_unarchive.py --apply --to ACTIVE      # ACTIVE로 복구 (주의: 즉시 집행)
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
    ap.add_argument("--apply", action="store_true", help="실제 복구 실행 (기본은 dry-run)")
    ap.add_argument("--id", nargs="+", default=None, help="특정 캠페인 ID만 복구")
    ap.add_argument("--match", default="", help="이름에 이 문자열이 포함된 것만")
    ap.add_argument("--to", default="PAUSED", choices=["PAUSED", "ACTIVE"],
                    help="복구 후 상태 (기본 PAUSED, ACTIVE는 즉시 집행)")
    args = ap.parse_args()

    FacebookAdsApi.init(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=settings.META_ACCESS_TOKEN,
    )
    account = AdAccount(settings.META_AD_ACCOUNT_ID)

    print(f"\n=== Meta Unarchive — {settings.META_AD_ACCOUNT_ID} ===")
    print(f"복구 대상 상태: ARCHIVED → {args.to}")
    if args.id:
        print(f"ID 필터: {args.id}")
    if args.match:
        print(f"이름 필터: '{args.match}' 포함")
    print(f"모드: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    targets = []
    try:
        campaigns = account.get_campaigns(
            fields=[FBCampaign.Field.id, FBCampaign.Field.name,
                    FBCampaign.Field.effective_status, FBCampaign.Field.created_time],
            params={"effective_status": ["ARCHIVED"], "limit": 500},
        )
        for c in campaigns:
            cid = c["id"]
            name = c.get("name", "")
            if args.id and cid not in args.id:
                continue
            if args.match and args.match not in name:
                continue
            targets.append({
                "id": cid,
                "name": name,
                "created": c.get("created_time", "")[:10],
            })
    except Exception as e:
        print(f"[ERROR] 조회 실패: {e}")
        return

    print(f"대상: {len(targets)}개\n")
    for t in targets[:30]:
        print(f"  {t['id']:<18} {t['created']:<12} {t['name'][:60]}")
    if len(targets) > 30:
        print(f"  ...외 {len(targets) - 30}개")
    print()

    if not targets:
        print("복구할 캠페인 없음.")
        return

    if not args.apply:
        print("--apply 안 붙였으므로 실제 실행 생략.")
        return

    if args.to == "ACTIVE":
        print("[WARN] ACTIVE로 복구 — 즉시 집행됩니다. 예산/타겟팅 확인 후 진행하세요.")

    print(f"{len(targets)}개 {args.to}로 복구 중...\n")
    ok, fail = 0, 0
    for i, t in enumerate(targets, 1):
        try:
            c = FBCampaign(t["id"])
            c.api_update(params={FBCampaign.Field.status: args.to})
            ok += 1
            print(f"  [{i:3d}/{len(targets)}] OK     {t['id']}  {t['name'][:40]}")
        except Exception as e:
            fail += 1
            print(f"  [{i:3d}/{len(targets)}] FAIL   {t['id']}  {t['name'][:40]}  → {e}")
        if i % 20 == 0:
            time.sleep(1)

    print(f"\n완료: 성공 {ok} / 실패 {fail}")


if __name__ == "__main__":
    main()
