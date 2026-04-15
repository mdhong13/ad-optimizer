"""
크립토 시장 모니터링 - CoinGecko API (무료)
이벤트 감지 후 DB 저장 및 에이전트 트리거 여부 판단
"""
import logging
from datetime import datetime

import httpx

from storage.db import insert_market_event

logger = logging.getLogger(__name__)

COINGECKO_API = "https://api.coingecko.com/api/v3"
WATCH_ASSETS = ["bitcoin", "ethereum"]

# 이벤트 트리거 임계값
PRICE_SURGE_THRESHOLD = 10.0   # 24h +10% 이상
PRICE_CRASH_THRESHOLD = -10.0  # 24h -10% 이하


def fetch_prices() -> list:
    """CoinGecko에서 현재 가격 및 24h 변동률 조회"""
    ids = ",".join(WATCH_ASSETS)
    url = f"{COINGECKO_API}/simple/price"
    params = {
        "ids": ids,
        "vs_currencies": "usd",
        "include_24hr_change": "true",
        "include_ath": "true",
    }
    with httpx.Client(timeout=15) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def fetch_global_data() -> dict:
    """글로벌 크립토 시장 데이터 조회"""
    url = f"{COINGECKO_API}/global"
    with httpx.Client(timeout=15) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json().get("data", {})


def detect_events(prices: dict) -> list:
    """가격 데이터에서 주요 이벤트 감지"""
    events = []

    asset_name_map = {
        "bitcoin": "BTC",
        "ethereum": "ETH",
    }

    for coin_id, data in prices.items():
        asset = asset_name_map.get(coin_id, coin_id.upper())
        price_usd = data.get("usd", 0)
        change_24h = data.get("usd_24h_change", 0)

        if change_24h >= PRICE_SURGE_THRESHOLD:
            events.append({
                "event_type": "price_surge",
                "asset": asset,
                "title": f"{asset} 24시간 {change_24h:.1f}% 급등",
                "detail": f"현재가: ${price_usd:,.0f} | 24h 변동: +{change_24h:.2f}%",
                "severity": "high" if change_24h >= 20 else "medium",
                "price_usd": price_usd,
                "change_24h": change_24h,
                "triggered_agent": 1,
            })
        elif change_24h <= PRICE_CRASH_THRESHOLD:
            events.append({
                "event_type": "price_crash",
                "asset": asset,
                "title": f"{asset} 24시간 {change_24h:.1f}% 급락",
                "detail": f"현재가: ${price_usd:,.0f} | 24h 변동: {change_24h:.2f}%",
                "severity": "high" if change_24h <= -20 else "medium",
                "price_usd": price_usd,
                "change_24h": change_24h,
                "triggered_agent": 1,
            })
        else:
            # 일반 가격 업데이트 (트리거 없음)
            events.append({
                "event_type": "price_update",
                "asset": asset,
                "title": f"{asset} 가격 업데이트: ${price_usd:,.0f}",
                "detail": f"24h 변동: {change_24h:+.2f}%",
                "severity": "low",
                "price_usd": price_usd,
                "change_24h": change_24h,
                "triggered_agent": 0,
            })

    return events


def run_check() -> tuple:
    """
    크립토 시장 체크 실행
    Returns:
        (events, should_trigger_agent)
    """
    logger.info("Crypto market check started")
    try:
        prices = fetch_prices()
        events = detect_events(prices)
        should_trigger = False

        for event in events:
            insert_market_event(event)
            if event.get("triggered_agent"):
                should_trigger = True
                logger.warning(f"Market event triggered agent: {event['title']}")

        logger.info(f"Crypto check complete: {len(events)} events, trigger_agent={should_trigger}")
        return events, should_trigger

    except httpx.HTTPError as e:
        logger.error(f"CoinGecko API error: {e}")
        return [], False
    except Exception as e:
        logger.error(f"Crypto monitor error: {e}", exc_info=True)
        return [], False


def get_market_context() -> dict:
    """에이전트에 전달할 현재 시장 요약 생성"""
    try:
        prices = fetch_prices()
        btc = prices.get("bitcoin", {})
        eth = prices.get("ethereum", {})
        return {
            "btc_price_usd": btc.get("usd", 0),
            "btc_change_24h": btc.get("usd_24h_change", 0),
            "eth_price_usd": eth.get("usd", 0),
            "eth_change_24h": eth.get("usd_24h_change", 0),
            "checked_at": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get market context: {e}")
        return {}


if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO)
    events, trigger = run_check()
    print(json.dumps(events, indent=2, ensure_ascii=False, default=str))
    print(f"Should trigger agent: {trigger}")
