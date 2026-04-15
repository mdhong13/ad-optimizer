"""
콘텐츠 성과 모니터링 — 게시된 콘텐츠의 조회수, 좋아요, 댓글 수집
Threads, YouTube, Instagram
"""
import logging
from datetime import datetime

import httpx

from config.settings import settings
from storage import db

logger = logging.getLogger(__name__)


class ContentMonitor:
    def __init__(self):
        self.handlers = {
            "threads": self._fetch_threads_metrics,
            "youtube": self._fetch_youtube_metrics,
            "instagram": self._fetch_instagram_metrics,
        }

    def collect_metrics(self, platform: str = None) -> list:
        """
        게시된 콘텐츠의 성과 지표 수집
        platform: 특정 플랫폼만 수집 (None이면 전체)
        """
        coll = db.get_collection("published_content")
        query = {"status": "published"}
        if platform:
            query["platform"] = platform

        posts = list(coll.find(query))
        results = []

        for post in posts:
            plat = post.get("platform")
            handler = self.handlers.get(plat)
            if not handler:
                continue

            post_id = post.get("platform_post_id", "")
            if not post_id:
                continue

            try:
                metrics = handler(post_id)
                if metrics:
                    # DB 업데이트
                    coll.update_one(
                        {"_id": post["_id"]},
                        {"$set": {
                            "metrics": metrics,
                            "metrics_updated_at": datetime.now().isoformat(),
                        }},
                    )
                    results.append({
                        "platform": plat,
                        "post_id": post_id,
                        "metrics": metrics,
                    })
            except Exception as e:
                logger.warning(f"[{plat}] Metrics fetch failed for {post_id}: {e}")

        logger.info(f"Metrics collected: {len(results)} posts updated")
        return results

    def get_performance_summary(self, days: int = 7) -> dict:
        """최근 N일간 콘텐츠 성과 요약"""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        coll = db.get_collection("published_content")
        posts = list(coll.find(
            {"status": "published", "created_at": {"$gte": cutoff}},
            {"_id": 0, "platform": 1, "metrics": 1, "content_type": 1},
        ))

        summary = {
            "total_posts": len(posts),
            "by_platform": {},
        }

        for post in posts:
            plat = post.get("platform", "unknown")
            if plat not in summary["by_platform"]:
                summary["by_platform"][plat] = {
                    "count": 0,
                    "total_views": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                }

            stats = summary["by_platform"][plat]
            stats["count"] += 1
            m = post.get("metrics", {})
            stats["total_views"] += m.get("views", 0)
            stats["total_likes"] += m.get("likes", 0)
            stats["total_comments"] += m.get("comments", 0)

        return summary

    # --- Threads ---

    def _fetch_threads_metrics(self, post_id: str) -> dict:
        """Threads Insights API"""
        access_token = settings.META_ACCESS_TOKEN
        if not access_token:
            return {}

        url = f"https://graph.threads.net/v1.0/{post_id}/insights"
        params = {
            "metric": "views,likes,replies",
            "access_token": access_token,
        }
        try:
            r = httpx.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])
            metrics = {}
            for item in data:
                name = item.get("name", "")
                value = item.get("values", [{}])[0].get("value", 0)
                if name == "views":
                    metrics["views"] = value
                elif name == "likes":
                    metrics["likes"] = value
                elif name == "replies":
                    metrics["comments"] = value
            return metrics
        except Exception as e:
            logger.error(f"Threads insights error: {e}")
            return {}

    # --- YouTube ---

    def _fetch_youtube_metrics(self, video_id: str) -> dict:
        """YouTube Data API v3 — 영상 통계"""
        api_key = settings.GEMINI_API_KEY
        if not api_key:
            return {}

        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "statistics",
            "id": video_id,
            "key": api_key,
        }
        try:
            r = httpx.get(url, params=params, timeout=15)
            r.raise_for_status()
            items = r.json().get("items", [])
            if not items:
                return {}
            stats = items[0].get("statistics", {})
            return {
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
            }
        except Exception as e:
            logger.error(f"YouTube stats error: {e}")
            return {}

    # --- Instagram ---

    def _fetch_instagram_metrics(self, media_id: str) -> dict:
        """Instagram Graph API — 미디어 인사이트"""
        access_token = settings.META_ACCESS_TOKEN
        if not access_token:
            return {}

        url = f"https://graph.facebook.com/v21.0/{media_id}/insights"
        params = {
            "metric": "impressions,reach,likes,comments",
            "access_token": access_token,
        }
        try:
            r = httpx.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json().get("data", [])
            metrics = {}
            for item in data:
                name = item.get("name", "")
                value = item.get("values", [{}])[0].get("value", 0)
                if name == "impressions":
                    metrics["views"] = value
                elif name == "reach":
                    metrics["reach"] = value
                elif name == "likes":
                    metrics["likes"] = value
                elif name == "comments":
                    metrics["comments"] = value
            return metrics
        except Exception as e:
            logger.error(f"Instagram insights error: {e}")
            return {}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    monitor = ContentMonitor()
    summary = monitor.get_performance_summary(days=30)
    print(f"Total posts: {summary['total_posts']}")
    for plat, stats in summary.get("by_platform", {}).items():
        print(f"  [{plat}] {stats['count']} posts, {stats['total_views']} views, {stats['total_likes']} likes")
