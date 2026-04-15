"""
Reddit 바이럴 — 글/댓글 작성 (공개 API + 인증 API)
인증 없이: 검색/조회만
인증 있으면: 댓글/글 작성
"""
import logging
import httpx

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "OneMessageBot/1.0"}

MONITOR_KEYWORDS = [
    "crypto inheritance", "crypto estate planning", "dead man switch",
    "private key inheritance", "crypto after death",
    "lost private key", "lost bitcoin", "forgotten wallet",
    "crypto will", "digital estate", "seed phrase backup",
]

TARGET_SUBREDDITS = [
    "Bitcoin", "CryptoCurrency", "ethereum", "BitcoinBeginners",
    "CryptoTechnology", "personalfinance",
]


def search_posts(keyword: str, limit: int = 10) -> list:
    """Reddit 공개 검색 API"""
    url = "https://www.reddit.com/search.json"
    params = {"q": keyword, "sort": "new", "limit": limit, "t": "week"}
    try:
        r = httpx.get(url, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        posts = []
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            posts.append({
                "id": p.get("id"),
                "subreddit": p.get("subreddit"),
                "title": p.get("title"),
                "selftext": (p.get("selftext") or "")[:500],
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
                "created_utc": p.get("created_utc"),
            })
        return posts
    except Exception as e:
        logger.error(f"Reddit search error: {e}")
        return []


def search_all_keywords(limit_per_kw: int = 5) -> list:
    """모든 키워드로 검색, 중복 제거"""
    all_posts = []
    seen = set()
    for kw in MONITOR_KEYWORDS:
        posts = search_posts(kw, limit=limit_per_kw)
        for p in posts:
            if p["id"] not in seen:
                seen.add(p["id"])
                p["matched_keyword"] = kw
                all_posts.append(p)
    all_posts.sort(key=lambda x: x.get("score", 0), reverse=True)
    return all_posts


def get_subreddit_hot(subreddit: str, limit: int = 10) -> list:
    """서브레딧 인기 글 조회"""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json"
    try:
        r = httpx.get(url, params={"limit": limit}, headers=HEADERS, timeout=15)
        r.raise_for_status()
        posts = []
        for child in r.json().get("data", {}).get("children", []):
            p = child.get("data", {})
            posts.append({
                "id": p.get("id"),
                "subreddit": subreddit,
                "title": p.get("title"),
                "selftext": (p.get("selftext") or "")[:500],
                "score": p.get("score", 0),
                "num_comments": p.get("num_comments", 0),
                "url": f"https://reddit.com{p.get('permalink', '')}",
            })
        return posts
    except Exception as e:
        logger.error(f"Subreddit fetch error: {e}")
        return []
