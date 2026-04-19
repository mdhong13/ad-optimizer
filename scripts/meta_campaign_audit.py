"""Meta 캠페인 감사 — 모든 상태(ACTIVE/PAUSED/ARCHIVED/DELETED) 개수 조회"""
import sys
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from config.settings import settings
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign as FBCampaign

FacebookAdsApi.init(
    app_id=settings.META_APP_ID,
    app_secret=settings.META_APP_SECRET,
    access_token=settings.META_ACCESS_TOKEN,
)
account = AdAccount(settings.META_AD_ACCOUNT_ID)

print(f"\n=== Meta Campaign Audit — {settings.META_AD_ACCOUNT_ID} ===\n")

# 모든 상태 명시적으로 조회
ALL_STATUSES = [
    "ACTIVE", "PAUSED",
    "ARCHIVED", "DELETED",
    "CAMPAIGN_PAUSED", "ADSET_PAUSED",
    "IN_PROCESS", "WITH_ISSUES",
]

for status in ALL_STATUSES:
    try:
        campaigns = account.get_campaigns(
            fields=[FBCampaign.Field.id, FBCampaign.Field.name,
                    FBCampaign.Field.status, FBCampaign.Field.effective_status,
                    FBCampaign.Field.created_time],
            params={"effective_status": [status], "limit": 500},
        )
        items = list(campaigns)
        print(f"[{status:<20}] {len(items)}개")
        if items and status in ("ARCHIVED", "DELETED"):
            for c in items[:5]:
                print(f"   {c.get('id')}  {c.get('name', '')[:50]}  created={c.get('created_time', '')[:10]}")
            if len(items) > 5:
                print(f"   ...외 {len(items)-5}개")
    except Exception as e:
        print(f"[{status:<20}] 조회 실패: {e}")

# 최근 생성된 것(90일) 모든 상태
print("\n--- 최근 생성 캠페인 (status 무관, effective_status DELETED/ARCHIVED 포함) ---")
try:
    from datetime import datetime, timedelta
    since = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
    campaigns = account.get_campaigns(
        fields=["id", "name", "status", "effective_status", "created_time"],
        params={
            "effective_status": ["ACTIVE", "PAUSED", "ARCHIVED", "DELETED", "IN_PROCESS"],
            "limit": 100,
        },
    )
    by_eff = {}
    for c in campaigns:
        k = c.get("effective_status", "?")
        by_eff[k] = by_eff.get(k, 0) + 1
    for k, v in sorted(by_eff.items()):
        print(f"  {k:<20} {v}")
except Exception as e:
    print(f"  조회 실패: {e}")

print()
