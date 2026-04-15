"""
YouTube 바이럴 — 크립토 영상 댓글 모니터링 & 작성
YouTube Data API v3 사용
"""
import logging
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)

YT_API_BASE = "https://www.googleapis.com/youtube/v3"

SEARCH_QUERIES = [
    "crypto security tips",
    "bitcoin inheritance",
    "what happens to crypto when you die",
    "protect your bitcoin",
    "crypto wallet backup",
    "dead man switch crypto",
]


def search_videos(query: str, max_results: int = 5) -> list:
    """크립토 관련 영상 검색"""
    api_key = settings.GEMINI_API_KEY  # Google API key 공용
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "order": "date",
        "relevanceLanguage": "en",
        "key": api_key,
    }
    try:
        r = httpx.get(f"{YT_API_BASE}/search", params=params, timeout=15)
        r.raise_for_status()
        videos = []
        for item in r.json().get("items", []):
            snippet = item.get("snippet", {})
            videos.append({
                "video_id": item.get("id", {}).get("videoId"),
                "title": snippet.get("title"),
                "channel": snippet.get("channelTitle"),
                "published_at": snippet.get("publishedAt"),
                "description": snippet.get("description", "")[:300],
                "url": f"https://youtube.com/watch?v={item.get('id', {}).get('videoId', '')}",
            })
        return videos
    except Exception as e:
        logger.error(f"YouTube search error: {e}")
        return []


def get_video_comments(video_id: str, max_results: int = 20) -> list:
    """영상 댓글 조회"""
    api_key = settings.GEMINI_API_KEY
    params = {
        "part": "snippet",
        "videoId": video_id,
        "maxResults": max_results,
        "order": "relevance",
        "key": api_key,
    }
    try:
        r = httpx.get(f"{YT_API_BASE}/commentThreads", params=params, timeout=15)
        r.raise_for_status()
        comments = []
        for item in r.json().get("items", []):
            snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
            comments.append({
                "comment_id": item.get("id"),
                "author": snippet.get("authorDisplayName"),
                "text": snippet.get("textDisplay", "")[:500],
                "likes": snippet.get("likeCount", 0),
                "published_at": snippet.get("publishedAt"),
            })
        return comments
    except Exception as e:
        logger.error(f"YouTube comments error: {e}")
        return []


def scan_crypto_videos() -> list:
    """모든 검색 쿼리로 최신 크립토 영상 탐색"""
    all_videos = []
    seen = set()
    for query in SEARCH_QUERIES:
        videos = search_videos(query, max_results=3)
        for v in videos:
            vid = v.get("video_id")
            if vid and vid not in seen:
                seen.add(vid)
                v["search_query"] = query
                all_videos.append(v)
    logger.info(f"YouTube scan: {len(all_videos)} unique videos found")
    return all_videos


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    videos = scan_crypto_videos()
    for v in videos[:5]:
        print(f"  [{v['channel']}] {v['title'][:60]}")
        print(f"    {v['url']}")
