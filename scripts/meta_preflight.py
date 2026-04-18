"""
Meta 실계정 전환 전 사전 점검.
- 계정 상태 / 지출 한도 / 잔액
- 연결된 Page 목록
- 현재 활성 캠페인 수
- 최근 30일 집행액
"""
import logging
import sys
from datetime import date, timedelta

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def main():
    from config.settings import settings
    from facebook_business.api import FacebookAdsApi
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.adobjects.user import User

    if not (settings.META_APP_ID and settings.META_ACCESS_TOKEN and settings.META_AD_ACCOUNT_ID):
        logger.error("META_APP_ID / META_ACCESS_TOKEN / META_AD_ACCOUNT_ID 미설정")
        sys.exit(1)

    FacebookAdsApi.init(
        app_id=settings.META_APP_ID,
        app_secret=settings.META_APP_SECRET,
        access_token=settings.META_ACCESS_TOKEN,
    )
    account = AdAccount(settings.META_AD_ACCOUNT_ID)

    print(f"\n=== Meta Preflight — {settings.META_AD_ACCOUNT_ID} ===\n")

    # 계정 정보
    try:
        info = account.api_get(fields=[
            "name", "account_status", "currency", "timezone_name",
            "amount_spent", "balance", "spend_cap", "disable_reason",
        ])
        status_map = {1: "ACTIVE", 2: "DISABLED", 3: "UNSETTLED", 7: "PENDING_RISK_REVIEW",
                      8: "PENDING_SETTLEMENT", 9: "IN_GRACE_PERIOD", 100: "PENDING_CLOSURE",
                      101: "CLOSED", 201: "ANY_ACTIVE", 202: "ANY_CLOSED"}
        status_code = int(info.get("account_status", 0))
        cur = info.get("currency", "USD")
        to_major = lambda c: float(c) / 100 if c else 0.0  # Meta는 minor unit (cents)
        print(f"계정명           : {info.get('name', '')}")
        print(f"상태             : {status_map.get(status_code, status_code)} ({status_code})")
        print(f"통화             : {cur}")
        print(f"타임존           : {info.get('timezone_name', '')}")
        print(f"누적 집행액      : {to_major(info.get('amount_spent', 0)):.2f} {cur}")
        print(f"잔액             : {to_major(info.get('balance', 0)):.2f} {cur}")
        print(f"지출 한도        : {to_major(info.get('spend_cap', 0)):.2f} {cur} (0=무제한)")
        if info.get("disable_reason"):
            print(f"비활성 사유      : {info.get('disable_reason')}")
    except Exception as e:
        print(f"[ERROR] 계정 정보 조회 실패: {e}")

    # 연결된 Pages
    print("\n--- 연결 가능한 Page ---")
    try:
        user = User(fbid="me")
        pages = user.get_accounts(fields=["id", "name", "tasks"])
        page_found = False
        for p in pages:
            marker = " ← META_PAGE_ID" if p["id"] == settings.META_PAGE_ID else ""
            print(f"  {p['id']}  {p.get('name', '')}{marker}")
            page_found = page_found or (p["id"] == settings.META_PAGE_ID)
        if settings.META_PAGE_ID and not page_found:
            print(f"  [WARN] META_PAGE_ID={settings.META_PAGE_ID} 가 목록에 없음 (권한 확인 필요)")
        if not settings.META_PAGE_ID:
            print("  [TODO] 위 목록에서 하나 골라 Railway Variables에 META_PAGE_ID=... 설정")
    except Exception as e:
        print(f"  [ERROR] Page 조회 실패: {e}")

    # 현재 캠페인
    print("\n--- 캠페인 현황 ---")
    try:
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        campaigns = account.get_campaigns(
            fields=[FBCampaign.Field.id, FBCampaign.Field.name,
                    FBCampaign.Field.status, FBCampaign.Field.effective_status,
                    FBCampaign.Field.daily_budget],
            params={"limit": 200},
        )
        by_status = {}
        for c in campaigns:
            s = c.get("effective_status", "UNKNOWN")
            by_status[s] = by_status.get(s, 0) + 1
        for s, n in sorted(by_status.items()):
            print(f"  {s:<25} {n}")
        total = sum(by_status.values())
        print(f"  {'TOTAL':<25} {total}")
    except Exception as e:
        print(f"  [ERROR] 캠페인 조회 실패: {e}")

    # 최근 30일 집행액
    print("\n--- 최근 30일 집행액 ---")
    try:
        end = date.today()
        start = end - timedelta(days=30)
        insights = account.get_insights(
            fields=["spend", "impressions", "clicks"],
            params={"time_range": {"since": start.isoformat(), "until": end.isoformat()}},
        )
        for row in insights:
            print(f"  집행액  : {float(row.get('spend', 0)):.2f}")
            print(f"  노출    : {int(row.get('impressions', 0)):,}")
            print(f"  클릭    : {int(row.get('clicks', 0)):,}")
        if not insights:
            print("  데이터 없음 (신규 계정)")
    except Exception as e:
        print(f"  [ERROR] insights 조회 실패: {e}")

    # 안전장치 요약
    print("\n--- 안전장치 (현재 값) ---")
    print(f"  DRY_RUN                           : {settings.DRY_RUN}")
    print(f"  AUTO_ACTIVATE                     : {settings.AUTO_ACTIVATE}")
    print(f"  CANARY_MODE                       : {settings.CANARY_MODE} (count={settings.CANARY_COUNT})")
    print(f"  DAILY_BUDGET_CAP_USD              : ${settings.DAILY_BUDGET_CAP_USD:.2f}")
    print(f"  MAX_DAILY_BUDGET_PER_CAMPAIGN_USD : ${settings.MAX_DAILY_BUDGET_PER_CAMPAIGN_USD:.2f}")
    print(f"  MAX_ACTIVE_CAMPAIGNS              : {settings.MAX_ACTIVE_CAMPAIGNS}")
    print(f"  CAMPAIGNS_PER_CYCLE               : {settings.CAMPAIGNS_PER_CYCLE}")
    print()


if __name__ == "__main__":
    main()
