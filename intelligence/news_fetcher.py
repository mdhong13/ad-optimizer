"""
크립토 관련 뉴스 RSS 수집 및 키워드 분석
해킹/보안 사건 감지 시 에이전트 트리거
"""
import logging
from datetime import datetime

import feedparser

from storage.db import insert_market_event

logger = logging.getLogger(__name__)

RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptonews.com/news/feed/",
]

HACK_KEYWORDS = [
    "hack", "hacked", "exploit", "breach", "stolen", "theft",
    "vulnerability", "attack", "security incident", "drain", "rug pull",
]

SECURITY_KEYWORDS = [
    "private key", "seed phrase", "cold wallet", "hardware wallet",
    "self-custody", "crypto estate", "inheritance", "dead man",
]

ATH_KEYWORDS = ["all-time high", "ath", "new record", "bitcoin record"]


def fetch_recent_news(max_per_feed: int = 10) -> list[dict]:
    """RSS에서 최신 뉴스 수집"""
    articles = []
    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:max_per_feed]:
                articles.append({
                    "title": entry.get("title", ""),
                    "summary": entry.get("summary", "")[:500],
                    "link": entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source": feed.feed.get("title", feed_url),
                })
        except Exception as e:
            logger.warning(f"RSS feed error ({feed_url}): {e}")
    return articles


def classify_article(article: dict) -> str | None:
    """기사 분류: hack_news / security_interest / ath / None"""
    text = (article["title"] + " " + article["summary"]).lower()
    if any(kw in text for kw in HACK_KEYWORDS):
        return "hack_news"
    if any(kw in text for kw in ATH_KEYWORDS):
        return "ath"
    if any(kw in text for kw in SECURITY_KEYWORDS):
        return "security_interest"
    return None


def run_news_check() -> tuple[list[dict], bool]:
    """
    뉴스 체크 실행
    Returns:
        (relevant_articles, should_trigger_agent)
    """
    logger.info("News check started")
    articles = fetch_recent_news()
    relevant = []
    should_trigger = False

    for article in articles:
        event_type = classify_article(article)
        if not event_type:
            continue

        relevant.append(article)
        severity = "high" if event_type == "hack_news" else "medium"
        triggered = event_type in ("hack_news", "ath")

        insert_market_event({
            "event_type": event_type,
            "asset": "CRYPTO",
            "title": article["title"][:200],
            "detail": f"Source: {article['source']}\n{article['summary'][:300]}",
            "severity": severity,
            "price_usd": None,
            "change_24h": None,
            "triggered_agent": 1 if triggered else 0,
        })

        if triggered:
            should_trigger = True
            logger.warning(f"News triggered agent: [{event_type}] {article['title']}")

    logger.info(f"News check complete: {len(relevant)} relevant articles, trigger={should_trigger}")
    return relevant, should_trigger


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    articles, trigger = run_news_check()
    for a in articles:
        print(f"- [{classify_article(a)}] {a['title']}")
    print(f"Should trigger agent: {trigger}")
