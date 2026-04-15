"""
Google Ads API 연동 테스트
- 계정 정보 조회
- 캠페인 목록 조회
"""
from google.ads.googleads.client import GoogleAdsClient

config = {
    "developer_token": "44LWhcvDCRFB4bhu_sUd6w",
    "client_id": "352203835844-ia1id3gvn4il2snqkjeu1l2f2mlejr4g.apps.googleusercontent.com",
    "client_secret": "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",
    "refresh_token": "1//0e9cWHrJblTDICgYIARAAGA4SNwF-L9IrOs67o-75fXvISF8b8go9Ev4rNHWKHfxzl0wOyl1a_p-xwrfgs67rffYFE_eU_ys2NlA",
    "login_customer_id": "4894234221",
    "use_proto_plus": True,
}

MCC_ID = "4894234221"
AD_ACCOUNT_ID = "7958648888"

client = GoogleAdsClient.load_from_dict(config)
ga_service = client.get_service("GoogleAdsService")

# 1. MCC에서 하위 계정 목록 조회
print("=" * 50)
print("1. MCC 하위 계정 목록")
print("=" * 50)
try:
    query = """
        SELECT
            customer_client.id,
            customer_client.descriptive_name,
            customer_client.currency_code,
            customer_client.status,
            customer_client.manager,
            customer_client.test_account
        FROM customer_client
    """
    response = ga_service.search_stream(customer_id=MCC_ID, query=query)
    for batch in response:
        for row in batch.results:
            cc = row.customer_client
            print(f"  ID: {cc.id} | {cc.descriptive_name}")
            print(f"    통화: {cc.currency_code} | 상태: {cc.status.name}")
            print(f"    관리자: {cc.manager} | 테스트: {cc.test_account}")
            print()
except Exception as e:
    print(f"  MCC 조회 실패: {e}")

# 2. 광고 계정 직접 조회
print("=" * 50)
print("2. 광고 계정 (795-864-8888) 조회")
print("=" * 50)
try:
    query = """
        SELECT
            customer.id,
            customer.descriptive_name,
            customer.currency_code,
            customer.time_zone,
            customer.status
        FROM customer
        LIMIT 1
    """
    response = ga_service.search_stream(customer_id=AD_ACCOUNT_ID, query=query)
    for batch in response:
        for row in batch.results:
            c = row.customer
            print(f"  ID: {c.id}")
            print(f"  이름: {c.descriptive_name}")
            print(f"  통화: {c.currency_code}")
            print(f"  시간대: {c.time_zone}")
            print(f"  상태: {c.status.name}")
except Exception as e:
    print(f"  광고 계정 조회 실패: {e}")

# 3. 캠페인 목록
print("\n" + "=" * 50)
print("3. 캠페인 목록")
print("=" * 50)
try:
    query = """
        SELECT
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign_budget.amount_micros
        FROM campaign
        ORDER BY campaign.id
    """
    response = ga_service.search_stream(customer_id=AD_ACCOUNT_ID, query=query)
    count = 0
    for batch in response:
        for row in batch.results:
            count += 1
            camp = row.campaign
            budget = row.campaign_budget.amount_micros / 1_000_000
            print(f"  [{count}] {camp.name}")
            print(f"      ID: {camp.id} | 상태: {camp.status.name} | 채널: {camp.advertising_channel_type.name}")
            print(f"      일예산: ${budget:.2f}")
    if count == 0:
        print("  (캠페인 없음)")
    print(f"\n총 {count}개 캠페인")
except Exception as e:
    print(f"  캠페인 조회 실패: {e}")

print("\n테스트 완료!")
