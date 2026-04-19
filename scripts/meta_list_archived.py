"""Meta 아카이브/상태 조회.

사용법:
  python scripts/meta_list_archived.py                    # ARCHIVED 전체 목록
  python scripts/meta_list_archived.py --status PAUSED    # 특정 상태 목록
  python scripts/meta_list_archived.py --id 123456789     # 특정 캠페인 상태 조회
  python scripts/meta_list_archived.py --all              # 모든 상태 그룹별 표시
"""
import argparse
import sys
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


ALL_STATUSES = [
    "ACTIVE", "PAUSED",
    "CAMPAIGN_PAUSED", "ADSET_PAUSED",
    "ARCHIVED", "DELETED",
    "IN_PROCESS", "WITH_ISSUES",
]


def init():
    FacebookAdsApi.init(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=settings.META_ACCESS_TOKEN,
    )
    return AdAccount(settings.META_AD_ACCOUNT_ID)


def fetch_by_status(account, status):
    campaigns = account.get_campaigns(
        fields=[
            FBCampaign.Field.id,
            FBCampaign.Field.name,
            FBCampaign.Field.status,
            FBCampaign.Field.effective_status,
            FBCampaign.Field.created_time,
            FBCampaign.Field.updated_time,
            FBCampaign.Field.daily_budget,
        ],
        params={"effective_status": [status], "limit": 500},
    )
    return list(campaigns)


def print_list(items, title):
    print(f"\n=== {title} — {len(items)}개 ===")
    if not items:
        print("  (없음)")
        return
    print(f"  {'ID':<18} {'STATUS':<18} {'EFF_STATUS':<18} {'CREATED':<12} {'BUDGET':>10}  NAME")
    for c in items:
        budget = c.get("daily_budget", "")
        budget_str = f"{int(budget):>10,}" if budget else f"{'':>10}"
        print(f"  {c.get('id', ''):<18} {c.get('status', ''):<18} "
              f"{c.get('effective_status', ''):<18} "
              f"{c.get('created_time', '')[:10]:<12} {budget_str}  {c.get('name', '')[:60]}")


def print_one(campaign_id):
    c = FBCampaign(campaign_id)
    info = c.api_get(fields=[
        FBCampaign.Field.id, FBCampaign.Field.name,
        FBCampaign.Field.status, FBCampaign.Field.effective_status,
        FBCampaign.Field.objective, FBCampaign.Field.created_time,
        FBCampaign.Field.updated_time, FBCampaign.Field.daily_budget,
        FBCampaign.Field.lifetime_budget, FBCampaign.Field.start_time,
        FBCampaign.Field.stop_time,
    ])
    print(f"\n=== Campaign {campaign_id} ===")
    for k in ["id", "name", "status", "effective_status", "objective",
              "created_time", "updated_time", "start_time", "stop_time",
              "daily_budget", "lifetime_budget"]:
        v = info.get(k, "")
        print(f"  {k:<18} {v}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--status", default="ARCHIVED",
                    help=f"조회할 effective_status (기본: ARCHIVED). 선택: {', '.join(ALL_STATUSES)}")
    ap.add_argument("--id", default=None, help="특정 캠페인 ID 상세 조회")
    ap.add_argument("--all", action="store_true", help="모든 상태 그룹별로 표시")
    args = ap.parse_args()

    account = init()
    print(f"\n계정: {settings.META_AD_ACCOUNT_ID}")

    if args.id:
        print_one(args.id)
        return

    if args.all:
        for s in ALL_STATUSES:
            try:
                items = fetch_by_status(account, s)
                print_list(items, f"effective_status = {s}")
            except Exception as e:
                print(f"\n[WARN] {s} 조회 실패: {e}")
        return

    try:
        items = fetch_by_status(account, args.status)
        print_list(items, f"effective_status = {args.status}")
    except Exception as e:
        print(f"[ERROR] 조회 실패: {e}")


if __name__ == "__main__":
    main()
