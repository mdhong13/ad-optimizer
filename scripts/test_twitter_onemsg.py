"""X (Twitter) ONEMSG 클라이언트 동작 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from publisher.platforms.twitter import TwitterClient
from config.settings import settings


def main():
    print("=" * 60)
    print("X (Twitter) ONEMSG 테스트")
    print("=" * 60)

    print("\n[1] 설정 확인")
    print(f"  API Key:        {'OK' if settings.TWITTER_API_KEY else 'MISSING'}")
    print(f"  API Secret:     {'OK' if settings.TWITTER_API_SECRET else 'MISSING'}")
    print(f"  Access Token:   {'OK' if settings.TWITTER_ACCESS_TOKEN else 'MISSING'}")
    print(f"  Access Secret:  {'OK' if settings.TWITTER_ACCESS_TOKEN_SECRET else 'MISSING'}")
    print(f"  Bearer:         {'OK' if settings.TWITTER_BEARER_TOKEN else 'MISSING'}")
    print(f"  OAuth2 Client:  {'OK' if settings.TWITTER_CLIENT_ID else 'MISSING'}")

    tw = TwitterClient()
    if not tw.is_configured():
        print("\n[ERROR] 설정 미완료")
        return

    print("\n[2] 내 계정 정보")
    try:
        me = tw.get_me()
        print(f"  @{me['username']} ({me['name']})")
        print(f"  ID:         {me['id']}")
        print(f"  팔로워:     {me['followers']:,}")
        print(f"  팔로잉:     {me['following']:,}")
        print(f"  트윗수:     {me['tweets']:,}")
        print(f"  가입일:     {me['created_at']}")
        print(f"  bio:        {me['description'][:80]}")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")

    print("\n[3] 검색 테스트 ('crypto inheritance')")
    try:
        results = tw.search_recent("crypto inheritance", max_results=10)
        if not results:
            print("  결과 없음")
        for i, r in enumerate(results[:5], 1):
            print(f"  {i}. @{r['author_username']} ({r['author_followers']:,}팔로워)")
            print(f"     {r['text'][:80]}...")
            print(f"     좋아요 {r['likes']} / 리트윗 {r['retweets']}")
    except Exception as e:
        print(f"  [ERROR] {type(e).__name__}: {e}")

    print("\n" + "=" * 60)
    print("읽기/쓰기 권한 테스트는 실제 트윗이 올라가므로 생략")
    print("포스팅 테스트는 'py scripts/test_twitter_post.py' 로 별도 실행")
    print("=" * 60)


if __name__ == "__main__":
    main()
