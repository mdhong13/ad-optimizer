"""
Facebook Page 클라이언트 — OneMessage 페이지에 텍스트/이미지 포스팅

토큰: META_ACCESS_TOKEN (User access token) 에서 Page access token 교환해 사용.
권한: pages_manage_posts, pages_read_engagement 필요.

사용:
  page = FacebookPage()
  page.post_photo(image_path="assets/generated/fb/story_01.png",
                  message="...영문 스토리...",
                  link="https://onemsg.net")
"""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from config.settings import settings

logger = logging.getLogger(__name__)
GRAPH = "https://graph.facebook.com/v21.0"


class FacebookPage:
    def __init__(self):
        self._page_token: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(settings.META_ACCESS_TOKEN and settings.META_PAGE_ID)

    def _get_page_token(self) -> str:
        """User token → Page access token. 캐시됨 (Page token은 long-lived)."""
        if self._page_token:
            return self._page_token
        if not self.is_configured():
            raise RuntimeError("META_ACCESS_TOKEN / META_PAGE_ID 미설정")

        # 1) /me/accounts 에서 페이지별 토큰 조회
        r = httpx.get(
            f"{GRAPH}/me/accounts",
            params={"access_token": settings.META_ACCESS_TOKEN, "fields": "id,name,access_token"},
            timeout=30,
        )
        r.raise_for_status()
        for p in r.json().get("data", []):
            if str(p.get("id")) == str(settings.META_PAGE_ID):
                self._page_token = p["access_token"]
                logger.info(f"Facebook: page token acquired for {p.get('name')}")
                return self._page_token
        raise RuntimeError(
            f"META_PAGE_ID={settings.META_PAGE_ID} 가 /me/accounts 에 없음. "
            "pages_manage_posts 권한 또는 페이지 관리자 여부 확인."
        )

    def post_text(self, message: str, link: Optional[str] = None) -> str:
        """텍스트 포스트 (선택: 링크 카드 포함). 반환: post_id"""
        token = self._get_page_token()
        params = {"message": message, "access_token": token}
        if link:
            params["link"] = link
        r = httpx.post(f"{GRAPH}/{settings.META_PAGE_ID}/feed", data=params, timeout=60)
        r.raise_for_status()
        post_id = r.json().get("id", "")
        logger.info(f"Facebook: text post created {post_id}")
        return post_id

    def post_photo(
        self,
        image_path: str,
        message: str,
        link: Optional[str] = None,
        published: bool = True,
    ) -> str:
        """이미지 + 캡션 포스트. 반환: post_id"""
        token = self._get_page_token()
        with open(image_path, "rb") as f:
            files = {"source": (image_path.rsplit("/", 1)[-1], f, "image/png")}
            data = {
                "message": message,
                "access_token": token,
                "published": "true" if published else "false",
            }
            # link 가 있으면 caption 에 URL 추가 (photo 포스트는 link 카드 미지원)
            if link and link not in message:
                data["message"] = f"{message}\n\n{link}"
            r = httpx.post(
                f"{GRAPH}/{settings.META_PAGE_ID}/photos",
                data=data,
                files=files,
                timeout=120,
            )
        r.raise_for_status()
        body = r.json()
        # photos 엔드포인트는 {id, post_id} 반환. post_id 우선.
        result = body.get("post_id") or body.get("id", "")
        logger.info(f"Facebook: photo post created {result}")
        return result

    def recent_posts(self, limit: int = 20) -> list[dict]:
        """최근 포스트 조회 (중복 주제 회피용)"""
        token = self._get_page_token()
        r = httpx.get(
            f"{GRAPH}/{settings.META_PAGE_ID}/posts",
            params={"access_token": token, "fields": "id,message,created_time", "limit": limit},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("data", [])

    def delete_post(self, post_id: str) -> bool:
        token = self._get_page_token()
        r = httpx.delete(f"{GRAPH}/{post_id}", params={"access_token": token}, timeout=30)
        return r.status_code == 200 and r.json().get("success", False)
