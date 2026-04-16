"""
YouTube 클라이언트 — OneMessage 계정 (mdhong13@gmail.com)
업로드(Shorts/영상), 댓글, 통계 조회

의존성: google-api-python-client, google-auth, google-auth-oauthlib
"""
import logging
from typing import Optional

from config.settings import settings

logger = logging.getLogger(__name__)


class YouTubeClient:
    """OneMessage 계정용 YouTube API 클라이언트 (OAuth2 기반)"""

    def __init__(self):
        self._service = None

    def is_configured(self) -> bool:
        return bool(
            settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_ID
            and settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET
            and settings.YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN
        )

    def _get_service(self):
        """OAuth2 credentials로 youtube 서비스 객체 생성 (지연 초기화)"""
        if self._service:
            return self._service

        if not self.is_configured():
            raise RuntimeError("YouTube OneMessage OAuth not configured")

        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        creds = Credentials(
            token=None,
            refresh_token=settings.YOUTUBE_ONEMSG_OAUTH_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_ID,
            client_secret=settings.YOUTUBE_ONEMSG_OAUTH_CLIENT_SECRET,
            scopes=[
                "https://www.googleapis.com/auth/youtube.upload",
                "https://www.googleapis.com/auth/youtube.force-ssl",
                "https://www.googleapis.com/auth/youtube.readonly",
            ],
        )
        self._service = build("youtube", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # --- 채널 정보 ---

    def get_my_channel(self) -> dict:
        """현재 OAuth 계정의 채널 정보"""
        yt = self._get_service()
        resp = yt.channels().list(part="snippet,statistics,brandingSettings", mine=True).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        ch = items[0]
        return {
            "id": ch["id"],
            "title": ch["snippet"]["title"],
            "description": ch["snippet"].get("description", ""),
            "custom_url": ch["snippet"].get("customUrl", ""),
            "subscribers": int(ch["statistics"].get("subscriberCount", 0)),
            "views": int(ch["statistics"].get("viewCount", 0)),
            "videos": int(ch["statistics"].get("videoCount", 0)),
        }

    # --- 영상 업로드 ---

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        tags: Optional[list] = None,
        category_id: str = "22",   # 22 = People & Blogs, 24 = Entertainment
        privacy_status: str = "public",  # public | private | unlisted
        made_for_kids: bool = False,
        is_short: bool = False,
    ) -> dict:
        """
        영상 업로드 (Shorts 포함)
        Shorts 조건: 세로(9:16), 60초 이하, 제목/설명에 #Shorts 포함 권장
        """
        from googleapiclient.http import MediaFileUpload

        yt = self._get_service()
        if is_short and "#Shorts" not in title and "#Shorts" not in description:
            description = f"{description}\n\n#Shorts".strip()

        body = {
            "snippet": {
                "title": title[:100],  # YouTube 제한 100자
                "description": description[:5000],
                "tags": (tags or [])[:500],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": made_for_kids,
            },
        }

        media = MediaFileUpload(file_path, chunksize=-1, resumable=True)
        request = yt.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        logger.info(f"YouTube upload start: {title}")
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Upload progress: {int(status.progress() * 100)}%")

        video_id = response.get("id")
        logger.info(f"YouTube upload complete: {video_id}")

        return {
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            "status": response.get("status", {}),
        }

    # --- 댓글 작성 ---

    def post_comment(self, video_id: str, text: str) -> dict:
        """영상에 최상위 댓글 작성"""
        yt = self._get_service()
        resp = yt.commentThreads().insert(
            part="snippet",
            body={
                "snippet": {
                    "videoId": video_id,
                    "topLevelComment": {"snippet": {"textOriginal": text[:10000]}},
                }
            },
        ).execute()
        return {
            "comment_id": resp["id"],
            "video_id": video_id,
            "text": text,
        }

    def reply_to_comment(self, parent_comment_id: str, text: str) -> dict:
        """기존 댓글에 답글"""
        yt = self._get_service()
        resp = yt.comments().insert(
            part="snippet",
            body={
                "snippet": {
                    "parentId": parent_comment_id,
                    "textOriginal": text[:10000],
                }
            },
        ).execute()
        return {"comment_id": resp["id"], "parent_id": parent_comment_id}

    # --- 조회/검색 ---

    def search_videos(self, query: str, max_results: int = 10, order: str = "relevance") -> list:
        """영상 검색 (order: relevance, date, viewCount, rating)"""
        yt = self._get_service()
        resp = yt.search().list(
            part="snippet",
            q=query,
            type="video",
            order=order,
            maxResults=max_results,
        ).execute()
        return [
            {
                "video_id": item["id"]["videoId"],
                "title": item["snippet"]["title"],
                "channel": item["snippet"]["channelTitle"],
                "published_at": item["snippet"]["publishedAt"],
                "description": item["snippet"].get("description", ""),
            }
            for item in resp.get("items", [])
        ]

    def get_video_stats(self, video_id: str) -> dict:
        """영상 통계 (조회수/좋아요/댓글수)"""
        yt = self._get_service()
        resp = yt.videos().list(part="snippet,statistics", id=video_id).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        v = items[0]
        s = v["statistics"]
        return {
            "video_id": video_id,
            "title": v["snippet"]["title"],
            "views": int(s.get("viewCount", 0)),
            "likes": int(s.get("likeCount", 0)),
            "comments": int(s.get("commentCount", 0)),
        }

    def get_top_comments(self, video_id: str, max_results: int = 20) -> list:
        """영상의 최상위 댓글 목록"""
        yt = self._get_service()
        resp = yt.commentThreads().list(
            part="snippet",
            videoId=video_id,
            maxResults=max_results,
            order="relevance",
        ).execute()
        return [
            {
                "comment_id": item["id"],
                "author": item["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"],
                "text": item["snippet"]["topLevelComment"]["snippet"]["textDisplay"],
                "likes": item["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0),
                "published_at": item["snippet"]["topLevelComment"]["snippet"]["publishedAt"],
            }
            for item in resp.get("items", [])
        ]
