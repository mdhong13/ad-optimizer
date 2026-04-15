"""
콘텐츠 업로더 — assets/ 폴더의 콘텐츠를 각 플랫폼에 업로드
YouTube Shorts, Instagram, Threads, TikTok, Blog
"""
import logging
import os
from datetime import datetime
from pathlib import Path

import httpx

from config.settings import settings
from storage import db

logger = logging.getLogger(__name__)

ASSETS_DIR = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / "assets"


class ContentUploader:
    def __init__(self):
        self.platforms = {
            "threads": self._upload_threads,
            "youtube": self._upload_youtube,
            "instagram": self._upload_instagram,
        }

    def upload(self, content: dict, platform: str, dry_run: bool = None) -> dict:
        """
        콘텐츠를 플랫폼에 업로드
        content: {
            "type": "text" | "image" | "video",
            "text": "...",
            "media_path": "/path/to/file",  (optional)
            "title": "...",                  (optional, for video)
            "tags": ["tag1", "tag2"],        (optional)
        }
        """
        if dry_run is None:
            dry_run = settings.DRY_RUN

        handler = self.platforms.get(platform)
        if not handler:
            logger.warning(f"Unsupported platform: {platform}")
            return {"status": "error", "reason": f"unsupported platform: {platform}"}

        result = handler(content, dry_run)

        # DB 기록
        record = {
            "platform": platform,
            "content_type": content.get("type", "text"),
            "text": content.get("text", "")[:500],
            "media_path": content.get("media_path", ""),
            "status": result.get("status", "unknown"),
            "platform_post_id": result.get("post_id", ""),
            "post_url": result.get("url", ""),
            "dry_run": dry_run,
            "uploaded_at": datetime.now().isoformat(),
        }
        db.insert_published_content(record)
        logger.info(f"[{platform}] Upload {'(DRY RUN) ' if dry_run else ''}status: {result.get('status')}")

        return result

    def upload_batch(self, contents: list, dry_run: bool = None) -> list:
        """여러 콘텐츠를 배치 업로드"""
        results = []
        for item in contents:
            platform = item.pop("platform", None)
            if not platform:
                continue
            result = self.upload(item, platform, dry_run)
            results.append({"platform": platform, **result})
        return results

    # --- Threads ---

    def _upload_threads(self, content: dict, dry_run: bool) -> dict:
        """Threads API로 텍스트/이미지 게시"""
        if dry_run:
            return {"status": "dry_run", "post_id": "dry_run_threads"}

        user_id = "me"
        access_token = settings.META_ACCESS_TOKEN
        if not access_token:
            return {"status": "error", "reason": "META_ACCESS_TOKEN not set"}

        base_url = "https://graph.threads.net/v1.0"
        media_type = "TEXT"
        params = {
            "text": content.get("text", ""),
            "access_token": access_token,
        }

        # 이미지 첨부
        if content.get("media_path") and content.get("type") == "image":
            media_type = "IMAGE"
            params["image_url"] = content["media_path"]  # public URL 필요

        params["media_type"] = media_type

        try:
            # Step 1: Create media container
            r = httpx.post(f"{base_url}/{user_id}/threads", params=params, timeout=30)
            r.raise_for_status()
            container_id = r.json().get("id")

            # Step 2: Publish
            publish_params = {
                "creation_id": container_id,
                "access_token": access_token,
            }
            r2 = httpx.post(f"{base_url}/{user_id}/threads_publish", params=publish_params, timeout=30)
            r2.raise_for_status()
            post_id = r2.json().get("id", "")

            return {
                "status": "published",
                "post_id": post_id,
                "url": f"https://www.threads.net/@me/post/{post_id}",
            }
        except Exception as e:
            logger.error(f"Threads upload error: {e}")
            return {"status": "error", "reason": str(e)}

    # --- YouTube ---

    def _upload_youtube(self, content: dict, dry_run: bool) -> dict:
        """YouTube Data API v3로 영상 업로드 (OAuth2 필요)"""
        if dry_run:
            return {"status": "dry_run", "post_id": "dry_run_youtube"}

        # YouTube 업로드는 OAuth2 + resumable upload 필요
        # 현재는 메타데이터만 기록, 실제 업로드는 별도 스크립트
        media_path = content.get("media_path", "")
        if not media_path or not os.path.exists(media_path):
            return {"status": "error", "reason": "media_path not found"}

        logger.info(f"YouTube upload queued: {media_path}")
        return {
            "status": "queued",
            "post_id": "",
            "reason": "YouTube resumable upload — use scripts/upload_youtube.py",
        }

    # --- Instagram ---

    def _upload_instagram(self, content: dict, dry_run: bool) -> dict:
        """Instagram Graph API로 이미지/릴스 업로드"""
        if dry_run:
            return {"status": "dry_run", "post_id": "dry_run_instagram"}

        access_token = settings.META_ACCESS_TOKEN
        if not access_token:
            return {"status": "error", "reason": "META_ACCESS_TOKEN not set"}

        # Instagram은 Business/Creator 계정 + public URL 필요
        ig_user_id = os.getenv("INSTAGRAM_USER_ID", "")
        if not ig_user_id:
            return {"status": "error", "reason": "INSTAGRAM_USER_ID not set"}

        content_type = content.get("type", "image")
        base_url = "https://graph.facebook.com/v21.0"

        try:
            # Step 1: Create container
            if content_type == "image":
                params = {
                    "image_url": content.get("media_path", ""),
                    "caption": content.get("text", ""),
                    "access_token": access_token,
                }
                r = httpx.post(f"{base_url}/{ig_user_id}/media", params=params, timeout=30)
            elif content_type == "video":
                params = {
                    "video_url": content.get("media_path", ""),
                    "caption": content.get("text", ""),
                    "media_type": "REELS",
                    "access_token": access_token,
                }
                r = httpx.post(f"{base_url}/{ig_user_id}/media", params=params, timeout=60)
            else:
                return {"status": "error", "reason": f"unsupported type: {content_type}"}

            r.raise_for_status()
            container_id = r.json().get("id")

            # Step 2: Publish
            r2 = httpx.post(
                f"{base_url}/{ig_user_id}/media_publish",
                params={"creation_id": container_id, "access_token": access_token},
                timeout=30,
            )
            r2.raise_for_status()
            post_id = r2.json().get("id", "")

            return {
                "status": "published",
                "post_id": post_id,
                "url": f"https://www.instagram.com/p/{post_id}/",
            }
        except Exception as e:
            logger.error(f"Instagram upload error: {e}")
            return {"status": "error", "reason": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    uploader = ContentUploader()

    # Dry run 테스트
    result = uploader.upload(
        {"type": "text", "text": "Protect your crypto legacy. #OneMessage #CryptoSecurity"},
        platform="threads",
        dry_run=True,
    )
    print(f"Threads: {result}")

    result = uploader.upload(
        {"type": "image", "text": "Test post", "media_path": "https://example.com/img.jpg"},
        platform="instagram",
        dry_run=True,
    )
    print(f"Instagram: {result}")
