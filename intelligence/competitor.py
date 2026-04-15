"""
경쟁사 광고 추적
- Meta Ad Library API로 경쟁사 광고 조회
- 키워드 기반 크립토 보안 관련 광고 탐색
"""
import logging
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)

META_AD_LIBRARY_URL = "https://graph.facebook.com/v25.0/ads_archive"

COMPETITOR_KEYWORDS = [
    "crypto inheritance",
    "crypto estate planning",
    "digital asset protection",
    "bitcoin dead man switch",
    "crypto will",
    "wallet recovery",
]


def search_competitor_ads(keyword: str, limit: int = 10) -> list:
    """Meta Ad Library에서 경쟁사 광고 검색"""
    params = {
        "access_token": settings.META_ACCESS_TOKEN,
        "search_terms": keyword,
        "ad_type": "ALL",
        "ad_reached_countries": '["US","KR"]',
        "fields": "id,ad_creative_bodies,ad_creative_link_titles,page_name,ad_delivery_start_time,impressions",
        "limit": limit,
    }
    try:
        r = httpx.get(META_AD_LIBRARY_URL, params=params, timeout=30)
        r.raise_for_status()
        return r.json().get("data", [])
    except Exception as e:
        logger.error(f"Ad Library search failed for '{keyword}': {e}")
        return []


def scan_competitors() -> list:
    """모든 키워드로 경쟁사 광고 스캔"""
    all_ads = []
    for kw in COMPETITOR_KEYWORDS:
        ads = search_competitor_ads(kw, limit=5)
        for ad in ads:
            ad["search_keyword"] = kw
        all_ads.extend(ads)
        logger.info(f"Keyword '{kw}': {len(ads)} ads found")

    logger.info(f"Competitor scan: {len(all_ads)} total ads")
    return all_ads


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ads = scan_competitors()
    for ad in ads[:5]:
        print(f"[{ad.get('page_name', '?')}] {ad.get('ad_creative_link_titles', [''])[0] if ad.get('ad_creative_link_titles') else ''}")
