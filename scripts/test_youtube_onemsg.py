"""
YouTube ONEMSG 클라이언트 동작 테스트
- 채널 정보 조회 (OAuth)
- 검색 (API key)
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from publisher.platforms.youtube import YouTubeClient
from config.settings import settings


def main():
    print("=" * 60)
    print("YouTube ONEMSG 클라이언트 테스트")
    print("=" * 60)

    # 1. 설정 확인
    print("\n[1] 설정 확인")
    print(f"  API Key:       {'OK' if settings.YOUTUBE_ONEMSG_API_KEY else 'MISSING'}")
    print(f"  Client ID:     {'OK' if settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_ID else 'MISSING'}")
    print(f"  Client Secret: {'OK' if settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET else 'MISSING'}")
    print(f"  Refresh Token: {'OK' if settings.YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN else 'MISSING'}")

    yt = YouTubeClient()
    if not yt.is_configured():
        print("\n[ERROR] 설정이 완전하지 않습니다.")
        return

    # 2. 내 채널 정보 (OAuth 필요)
    print("\n[2] 내 채널 정보 (OAuth 인증)")
    try:
        ch = yt.get_my_channel()
        if ch:
            print(f"  채널명:    {ch['title']}")
            print(f"  채널ID:    {ch['id']}")
            print(f"  URL:       https://youtube.com/{ch['custom_url']}" if ch.get('custom_url') else f"  URL:       https://youtube.com/channel/{ch['id']}")
            print(f"  구독자:    {ch['subscribers']:,}")
            print(f"  영상수:    {ch['videos']:,}")
            print(f"  총 조회수: {ch['views']:,}")
        else:
            print("  [WARN] 채널이 없습니다. youtube.com에서 채널 생성 필요.")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 3. 검색 테스트
    print("\n[3] 영상 검색 테스트 ('crypto wallet security')")
    try:
        results = yt.search_videos("crypto wallet security", max_results=3)
        for i, r in enumerate(results, 1):
            print(f"  {i}. {r['title'][:60]}")
            print(f"     채널: {r['channel']}")
            print(f"     https://youtube.com/watch?v={r['video_id']}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
