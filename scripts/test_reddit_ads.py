"""Reddit Ads API 동작 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from platforms.reddit import RedditAds
from config.settings import settings


def main():
    print("=" * 60)
    print("Reddit Ads API 테스트")
    print("=" * 60)

    print("\n[1] 설정 확인")
    print(f"  CLIENT_ID:       {'OK' if settings.REDDIT_CLIENT_ID else 'MISSING'}")
    print(f"  CLIENT_SECRET:   {'OK' if settings.REDDIT_CLIENT_SECRET else 'MISSING'}")
    print(f"  REFRESH_TOKEN:   {'OK' if settings.REDDIT_REFRESH_TOKEN else 'MISSING'}")
    print(f"  ADS_ACCOUNT_ID:  {settings.REDDIT_ADS_ACCOUNT_ID or 'MISSING'}")

    r = RedditAds()
    if not r.is_configured():
        print("\n[ERROR] 설정 미완료")
        return

    print("\n[2] 토큰 발급")
    try:
        token = r._get_token()
        print(f"  access_token: {token[:20]}...")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")
        return

    print("\n[3] 기존 캠페인 조회")
    try:
        campaigns = r.get_campaigns()
        print(f"  캠페인 {len(campaigns)}개")
        for c in campaigns[:5]:
            print(f"    - {c.campaign_name} [{c.status}] ${c.daily_budget}/day")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")

    print("\n[4] 크립토 서브레딧 ID 조회")
    for sub in ["CryptoCurrency", "Bitcoin", "ethereum", "ethfinance", "defi"]:
        try:
            sid = r.find_subreddit_id(sub)
            print(f"  r/{sub:20s} → {sid or 'NOT FOUND'}")
        except Exception as e:
            print(f"  r/{sub} ERROR: {e}")

    print("\n" + "=" * 60)
    print("테스트 완료. 다음: create_campaign(dry_run=True)로 생성 테스트")
    print("=" * 60)


if __name__ == "__main__":
    main()
