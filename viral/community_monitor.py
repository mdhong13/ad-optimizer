"""
커뮤니티 모니터링 — Reddit/Twitter에서 관련 키워드 탐지
바이럴 마케팅 기회 포착 + 답변 초안 자동 생성
"""
import json
import logging
from datetime import datetime

import httpx
import anthropic

from config.settings import settings
from storage.db import get_db

logger = logging.getLogger(__name__)

# 모니터링 대상 키워드
MONITOR_KEYWORDS = [
    # 직접 관련
    "crypto inheritance", "crypto estate planning", "dead man switch",
    "dead man's switch", "private key inheritance", "crypto after death",
    "what happens to crypto when you die",
    # 간접 관련
    "lost private key", "lost bitcoin", "forgotten wallet",
    "crypto will", "digital estate", "seed phrase backup",
    "hardware wallet death", "cold wallet security",
    # 한국어
    "크립토 상속", "비트코인 유산", "프라이빗 키 분실",
    "지갑 키 상속", "가상자산 유언",
]

# Reddit 관련 서브레딧
TARGET_SUBREDDITS = [
    "Bitcoin", "CryptoCurrency", "ethereum", "BitcoinBeginners",
    "CryptoTechnology", "ledgerwalletleak", "SecurityCareerAdvice",
]


# ─── Reddit 모니터링 (공개 API, 인증 불필요) ───

def search_reddit(keyword: str, limit: int = 10) -> list[dict]:
    """Reddit 공개 검색 API로 관련 포스트 조회"""
    url = "https://www.reddit.com/search.json"
    params = {
        "q": keyword,
        "sort": "new",
        "limit": limit,
        "t": "week",
    }
    headers = {"User-Agent": "OneMessageBot/1.0"}
    try:
        with httpx.Client(timeout=15) as client:
            resp = client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()
        posts = []
        for child in data.get("data", {}).get("children", []):
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
        logger.error(f"Reddit search error for '{keyword}': {e}")
        return []


def search_reddit_all_keywords(limit_per_kw: int = 5) -> list[dict]:
    """모든 키워드로 Reddit 검색"""
    all_posts = []
    seen_ids = set()
    for kw in MONITOR_KEYWORDS:
        posts = search_reddit(kw, limit=limit_per_kw)
        for p in posts:
            if p["id"] not in seen_ids:
                seen_ids.add(p["id"])
                p["matched_keyword"] = kw
                all_posts.append(p)
    all_posts.sort(key=lambda x: x.get("created_utc", 0), reverse=True)
    return all_posts


# ─── 기회 판단 + 답변 초안 생성 ───

def generate_reply_draft(post: dict) -> dict | None:
    """Reddit 포스트에 대한 자연스러운 답변 초안 생성"""
    if not settings.ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set, skipping reply generation")
        return None

    system = (
        "당신은 크립토 보안에 관심이 많은 Reddit 사용자입니다. "
        "자연스러운 커뮤니티 톤으로 답변합니다. "
        "절대 광고처럼 보이면 안 됩니다. OneMessage를 직접 추천하지 마세요. "
        "대신 'dead man's switch' 개념을 자연스럽게 언급할 수 있습니다. "
        "도움이 되는 정보를 제공하는 데 집중하세요."
    )

    user_msg = f"""Reddit 포스트에 대한 답변 초안을 작성하세요.

서브레딧: r/{post['subreddit']}
제목: {post['title']}
본문: {post['selftext'][:300]}

규칙:
1. 진정성 있고 도움이 되는 답변
2. 앱 이름이나 링크 직접 언급 금지
3. "dead man's switch" 또는 "automated inheritance solution" 개념만 자연스럽게 언급
4. 200자 이내
5. Reddit 커뮤니티 톤 유지

JSON 형식으로 반환:
```json
{{"reply_text": "답변 내용", "relevance_score": 0.0-1.0, "engagement_potential": "low|medium|high"}}
```"""

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model=settings.AGENT_MODEL,
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = msg.content[0].text.strip()
        if raw.startswith("```"):
            lines = raw.split("\n")
            raw = "\n".join(lines[1:-1])
        return json.loads(raw)
    except Exception as e:
        logger.error(f"Reply generation error: {e}")
        return None


# ─── DB 저장 ───

CREATE_COMMUNITY_TABLE = """
CREATE TABLE IF NOT EXISTS community_opportunities (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    platform    TEXT NOT NULL,
    post_id     TEXT UNIQUE,
    subreddit   TEXT,
    title       TEXT,
    url         TEXT,
    keyword     TEXT,
    score       INTEGER DEFAULT 0,
    num_comments INTEGER DEFAULT 0,
    reply_draft TEXT,
    relevance   REAL DEFAULT 0.0,
    engagement  TEXT DEFAULT 'medium',
    status      TEXT DEFAULT 'new',  -- 'new', 'replied', 'skipped'
    created_at  TEXT DEFAULT (datetime('now'))
);
"""


def init_community_table():
    with get_db() as conn:
        conn.executescript(CREATE_COMMUNITY_TABLE)


def save_opportunity(post: dict, reply: dict = None):
    init_community_table()
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO community_opportunities
                (platform, post_id, subreddit, title, url, keyword,
                 score, num_comments, reply_draft, relevance, engagement)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "reddit",
            post.get("id"),
            post.get("subreddit"),
            post.get("title"),
            post.get("url"),
            post.get("matched_keyword"),
            post.get("score", 0),
            post.get("num_comments", 0),
            reply.get("reply_text") if reply else None,
            reply.get("relevance_score", 0) if reply else 0,
            reply.get("engagement_potential", "medium") if reply else "medium",
        ))


def get_opportunities(status: str = None, limit: int = 20) -> list[dict]:
    init_community_table()
    where = ""
    params = []
    if status:
        where = "WHERE status = ?"
        params.append(status)
    with get_db() as conn:
        rows = conn.execute(
            f"SELECT * FROM community_opportunities {where} ORDER BY created_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [dict(r) for r in rows]


# ─── 메인 실행 ───

def run_community_scan(generate_replies: bool = True) -> dict:
    """전체 커뮤니티 스캔 실행"""
    logger.info("Community scan started")
    posts = search_reddit_all_keywords(limit_per_kw=5)
    logger.info(f"Found {len(posts)} unique posts")

    saved = 0
    for post in posts:
        reply = None
        if generate_replies and post.get("selftext"):
            reply = generate_reply_draft(post)
        save_opportunity(post, reply)
        saved += 1

    result = {
        "total_posts": len(posts),
        "saved": saved,
        "timestamp": datetime.now().isoformat(),
    }
    logger.info(f"Community scan complete: {result}")
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_community_scan(generate_replies=False)
    print(json.dumps(result, indent=2))

    posts = search_reddit_all_keywords(limit_per_kw=3)
    for p in posts[:5]:
        print(f"  [{p['subreddit']}] {p['title'][:60]} (score: {p['score']})")
