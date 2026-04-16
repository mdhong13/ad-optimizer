"""
X (Twitter) 클라이언트 — OneMessage 계정 (@onemsgx, mdhong13@gmail.com)
포스팅, 바이럴(검색/답글), 통계 조회

의존성: tweepy (OAuth 1.0a User Context + v2 API 통합)
"""
import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class TwitterClient:
    """X API v2 클라이언트 (OAuth 1.0a + Bearer 겸용)"""

    def __init__(self):
        self._client = None
        self._api = None  # v1.1 API (미디어 업로드용)

    def is_configured(self) -> bool:
        return bool(
            settings.TWITTER_API_KEY
            and settings.TWITTER_API_SECRET
            and settings.TWITTER_ACCESS_TOKEN
            and settings.TWITTER_ACCESS_TOKEN_SECRET
        )

    def _get_client(self):
        """tweepy.Client (v2 API, OAuth 1.0a User Context)"""
        if self._client:
            return self._client
        if not self.is_configured():
            raise RuntimeError("Twitter OAuth not configured")

        import tweepy
        self._client = tweepy.Client(
            bearer_token=settings.TWITTER_BEARER_TOKEN or None,
            consumer_key=settings.TWITTER_API_KEY,
            consumer_secret=settings.TWITTER_API_SECRET,
            access_token=settings.TWITTER_ACCESS_TOKEN,
            access_token_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
            wait_on_rate_limit=False,
        )
        return self._client

    def _get_api_v1(self):
        """tweepy.API (v1.1, 미디어 업로드 전용)"""
        if self._api:
            return self._api
        if not self.is_configured():
            raise RuntimeError("Twitter OAuth not configured")

        import tweepy
        auth = tweepy.OAuth1UserHandler(
            settings.TWITTER_API_KEY,
            settings.TWITTER_API_SECRET,
            settings.TWITTER_ACCESS_TOKEN,
            settings.TWITTER_ACCESS_TOKEN_SECRET,
        )
        self._api = tweepy.API(auth)
        return self._api

    # --- 계정 정보 ---

    def get_me(self) -> dict:
        """인증된 사용자 정보"""
        client = self._get_client()
        resp = client.get_me(user_fields=["public_metrics", "description", "created_at"])
        u = resp.data
        if not u:
            return {}
        metrics = u.public_metrics or {}
        return {
            "id": u.id,
            "username": u.username,
            "name": u.name,
            "description": u.description or "",
            "created_at": str(u.created_at) if u.created_at else "",
            "followers": metrics.get("followers_count", 0),
            "following": metrics.get("following_count", 0),
            "tweets": metrics.get("tweet_count", 0),
            "listed": metrics.get("listed_count", 0),
        }

    # --- 포스팅 ---

    def post_tweet(
        self,
        text: str,
        media_paths: Optional[list] = None,
        reply_to_tweet_id: Optional[str] = None,
        quote_tweet_id: Optional[str] = None,
    ) -> dict:
        """
        트윗 작성 (280자 제한, Premium은 25000자)
        media_paths: 로컬 파일 경로 리스트 (이미지 4개 or 영상 1개)
        """
        client = self._get_client()

        media_ids = []
        if media_paths:
            api = self._get_api_v1()
            for path in media_paths[:4]:
                media = api.media_upload(filename=path)
                media_ids.append(media.media_id_string)

        kwargs = {"text": text[:280]}
        if media_ids:
            kwargs["media_ids"] = media_ids
        if reply_to_tweet_id:
            kwargs["in_reply_to_tweet_id"] = reply_to_tweet_id
        if quote_tweet_id:
            kwargs["quote_tweet_id"] = quote_tweet_id

        resp = client.create_tweet(**kwargs)
        tweet_id = resp.data["id"]
        username = self._get_username()
        return {
            "tweet_id": tweet_id,
            "url": f"https://twitter.com/{username}/status/{tweet_id}",
            "text": text,
        }

    def delete_tweet(self, tweet_id: str) -> bool:
        client = self._get_client()
        resp = client.delete_tweet(tweet_id)
        return bool(resp.data and resp.data.get("deleted"))

    def reply(self, tweet_id: str, text: str) -> dict:
        """답글"""
        return self.post_tweet(text=text, reply_to_tweet_id=tweet_id)

    def retweet(self, tweet_id: str) -> dict:
        client = self._get_client()
        me = self.get_me()
        resp = client.retweet(tweet_id)
        return {"retweeted": bool(resp.data and resp.data.get("retweeted"))}

    def like(self, tweet_id: str) -> dict:
        client = self._get_client()
        resp = client.like(tweet_id)
        return {"liked": bool(resp.data and resp.data.get("liked"))}

    # --- 검색/조회 ---

    def search_recent(self, query: str, max_results: int = 20) -> list:
        """최근 7일 내 트윗 검색 (Bearer 토큰 권장)"""
        client = self._get_client()
        resp = client.search_recent_tweets(
            query=query,
            max_results=min(max(max_results, 10), 100),
            tweet_fields=["public_metrics", "created_at", "author_id", "lang"],
            expansions=["author_id"],
            user_fields=["username", "name", "public_metrics"],
        )
        if not resp.data:
            return []

        users = {u.id: u for u in (resp.includes or {}).get("users", [])}
        out = []
        for t in resp.data:
            m = t.public_metrics or {}
            author = users.get(t.author_id)
            out.append({
                "tweet_id": t.id,
                "text": t.text,
                "lang": t.lang,
                "created_at": str(t.created_at) if t.created_at else "",
                "author_id": t.author_id,
                "author_username": author.username if author else "",
                "author_name": author.name if author else "",
                "author_followers": (author.public_metrics or {}).get("followers_count", 0) if author else 0,
                "likes": m.get("like_count", 0),
                "retweets": m.get("retweet_count", 0),
                "replies": m.get("reply_count", 0),
                "impressions": m.get("impression_count", 0),
            })
        return out

    def get_tweet(self, tweet_id: str) -> dict:
        client = self._get_client()
        resp = client.get_tweet(
            tweet_id,
            tweet_fields=["public_metrics", "created_at", "author_id"],
        )
        t = resp.data
        if not t:
            return {}
        m = t.public_metrics or {}
        return {
            "tweet_id": t.id,
            "text": t.text,
            "created_at": str(t.created_at) if t.created_at else "",
            "author_id": t.author_id,
            "likes": m.get("like_count", 0),
            "retweets": m.get("retweet_count", 0),
            "replies": m.get("reply_count", 0),
            "impressions": m.get("impression_count", 0),
        }

    def get_user_tweets(self, username: str, max_results: int = 10) -> list:
        """특정 사용자의 최근 트윗"""
        client = self._get_client()
        user_resp = client.get_user(username=username)
        if not user_resp.data:
            return []
        user_id = user_resp.data.id

        resp = client.get_users_tweets(
            user_id,
            max_results=min(max(max_results, 5), 100),
            tweet_fields=["public_metrics", "created_at"],
            exclude=["retweets", "replies"],
        )
        if not resp.data:
            return []
        return [
            {
                "tweet_id": t.id,
                "text": t.text,
                "created_at": str(t.created_at) if t.created_at else "",
                "likes": (t.public_metrics or {}).get("like_count", 0),
                "retweets": (t.public_metrics or {}).get("retweet_count", 0),
            }
            for t in resp.data
        ]

    # --- 내부 ---

    def _get_username(self) -> str:
        if not hasattr(self, "_cached_username"):
            try:
                self._cached_username = self.get_me().get("username", "i")
            except Exception:
                self._cached_username = "i"
        return self._cached_username
