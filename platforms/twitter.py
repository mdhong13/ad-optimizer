"""
X (Twitter) Ads API 플랫폼 클라이언트
X Ads API v12 — https://developer.x.com/en/docs/x-ads-api

선행조건:
  1. X Developer Portal에서 Ads API 접근 신청 & 승인
  2. 광고 계정 생성 (ads.x.com)
  3. TWITTER_ADS_ACCOUNT_ID env 에 계정 ID 설정

인증: OAuth 1.0a User Context (TWITTER_API_KEY/SECRET + TWITTER_ACCESS_TOKEN/SECRET)
"""
import logging
from datetime import date, datetime, timezone
from typing import Optional

from config.settings import settings
from platforms.base import AdPlatform, Campaign, AdSet, PerformanceData

logger = logging.getLogger(__name__)

ADS_API_BASE = "https://ads-api.x.com/12"


class TwitterAds(AdPlatform):
    platform_name = "twitter"

    def __init__(self):
        self._session = None

    def _get_session(self):
        if self._session:
            return self._session
        if not self.is_configured():
            raise RuntimeError("Twitter Ads API not configured (check TWITTER_ADS_ACCOUNT_ID & OAuth keys)")
        from requests_oauthlib import OAuth1Session
        self._session = OAuth1Session(
            client_key=settings.TWITTER_API_KEY,
            client_secret=settings.TWITTER_API_SECRET,
            resource_owner_key=settings.TWITTER_ACCESS_TOKEN,
            resource_owner_secret=settings.TWITTER_ACCESS_TOKEN_SECRET,
        )
        return self._session

    def is_configured(self) -> bool:
        return bool(
            settings.TWITTER_API_KEY
            and settings.TWITTER_API_SECRET
            and settings.TWITTER_ACCESS_TOKEN
            and settings.TWITTER_ACCESS_TOKEN_SECRET
            and settings.TWITTER_ADS_ACCOUNT_ID
        )

    def _account_url(self, path: str = "") -> str:
        return f"{ADS_API_BASE}/accounts/{settings.TWITTER_ADS_ACCOUNT_ID}{path}"

    def _request(self, method: str, url: str, **kwargs) -> dict:
        sess = self._get_session()
        resp = sess.request(method, url, timeout=30, **kwargs)
        if resp.status_code >= 400:
            logger.error(f"X Ads API {method} {url} → {resp.status_code}: {resp.text[:400]}")
            resp.raise_for_status()
        return resp.json() if resp.content else {}

    # --- 계정/캠페인 조회 ---

    def list_accounts(self) -> list[dict]:
        """접근 가능한 광고 계정 목록 (TWITTER_ADS_ACCOUNT_ID 확인용)"""
        sess = self._get_session()
        if not (settings.TWITTER_API_KEY and settings.TWITTER_ACCESS_TOKEN):
            raise RuntimeError("OAuth keys missing")
        resp = sess.get(f"{ADS_API_BASE}/accounts", timeout=30)
        resp.raise_for_status()
        return resp.json().get("data", [])

    def get_campaigns(self) -> list[Campaign]:
        data = self._request("GET", self._account_url("/campaigns"), params={"count": 200})
        out = []
        for c in data.get("data", []):
            total_budget_micros = c.get("total_budget_amount_local_micro") or 0
            daily_budget_micros = c.get("daily_budget_amount_local_micro") or 0
            out.append(Campaign(
                campaign_id=c["id"],
                campaign_name=c.get("name", ""),
                status=("ACTIVE" if c.get("entity_status") == "ACTIVE"
                        else "PAUSED" if c.get("entity_status") == "PAUSED"
                        else "DELETED"),
                daily_budget=daily_budget_micros / 1_000_000,
                lifetime_budget=(total_budget_micros / 1_000_000) or None,
                platform=self.platform_name,
            ))
        return out

    def get_ad_sets(self, campaign_id: str) -> list[AdSet]:
        """X의 line_items = Meta의 ad_sets"""
        data = self._request(
            "GET",
            self._account_url("/line_items"),
            params={"campaign_ids": campaign_id, "count": 200},
        )
        out = []
        for li in data.get("data", []):
            bid_micros = li.get("bid_amount_local_micro") or 0
            out.append(AdSet(
                ad_set_id=li["id"],
                ad_set_name=li.get("name", ""),
                campaign_id=campaign_id,
                status=("ACTIVE" if li.get("entity_status") == "ACTIVE"
                        else "PAUSED" if li.get("entity_status") == "PAUSED"
                        else "DELETED"),
                bid_amount=(bid_micros / 1_000_000) or None,
                platform=self.platform_name,
            ))
        return out

    def get_performance(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PerformanceData]:
        """GET /stats/accounts/:id — entity=LINE_ITEM granularity=DAY"""
        line_items = self.get_ad_sets(campaign_id)
        if not line_items:
            return []
        ids = [li.ad_set_id for li in line_items]

        start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = datetime.combine(end_date, datetime.min.time()).replace(tzinfo=timezone.utc)

        params = {
            "entity": "LINE_ITEM",
            "entity_ids": ",".join(ids),
            "start_time": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "granularity": "DAY",
            "metric_groups": "ENGAGEMENT,BILLING,WEB_CONVERSION",
            "placement": "ALL_ON_TWITTER",
        }
        data = self._request("GET", f"{ADS_API_BASE}/stats/accounts/{settings.TWITTER_ADS_ACCOUNT_ID}", params=params)

        line_item_map = {li.ad_set_id: li for li in line_items}
        out = []
        for entry in data.get("data", []):
            li_id = entry["id"]
            li = line_item_map.get(li_id)
            series = entry.get("id_data", [{}])[0].get("metrics", {})
            impressions = (series.get("impressions") or [0])
            clicks = (series.get("clicks") or [0])
            spend_micros = (series.get("billed_charge_local_micro") or [0])
            conversions = (series.get("conversion_purchases") or [{"post_view": 0}])

            days = (end_date - start_date).days + 1
            for i in range(days):
                d = start_date.fromordinal(start_date.toordinal() + i)
                imps = int(impressions[i] or 0) if i < len(impressions) else 0
                clk = int(clicks[i] or 0) if i < len(clicks) else 0
                spend = (int(spend_micros[i] or 0) if i < len(spend_micros) else 0) / 1_000_000
                conv_raw = conversions[i] if i < len(conversions) else {}
                conv = int((conv_raw or {}).get("post_view", 0)) if isinstance(conv_raw, dict) else 0
                if imps == 0 and clk == 0 and spend == 0:
                    continue
                out.append(PerformanceData(
                    platform=self.platform_name,
                    campaign_id=campaign_id,
                    campaign_name="",
                    ad_set_id=li_id,
                    ad_set_name=li.ad_set_name if li else "",
                    date=d.strftime("%Y-%m-%d"),
                    impressions=imps,
                    clicks=clk,
                    spend=spend,
                    conversions=conv,
                ))
        return out

    # --- 캠페인 생성/수정/삭제 ---

    def create_campaign(
        self,
        name: str,
        daily_budget: float,
        targeting: dict,
        creatives: dict,
        dry_run: bool = True,
    ) -> Optional[str]:
        """
        X 캠페인 생성 (캠페인만 — line_item/promoted_tweet은 별도 호출 필요)
        targeting/creatives는 상위 orchestrator가 별도 API 호출로 붙인다.
        """
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: create campaign '{name}' ${daily_budget}/day")
            return "dry_run_campaign_id"

        data = self._request("POST", self._account_url("/campaigns"), params={
            "name": name[:255],
            "funding_instrument_id": targeting.get("funding_instrument_id", ""),
            "daily_budget_amount_local_micro": int(daily_budget * 1_000_000),
            "entity_status": "PAUSED",
        })
        cid = data.get("data", {}).get("id")
        logger.info(f"X Ads: campaign created {cid}")
        return cid

    def delete_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: delete campaign {campaign_id}")
            return True
        self._request("DELETE", self._account_url(f"/campaigns/{campaign_id}"))
        logger.info(f"X Ads: campaign {campaign_id} deleted")
        return True

    def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: update campaign {campaign_id} budget → ${new_daily_budget:.2f}/day")
            return True
        self._request("PUT", self._account_url(f"/campaigns/{campaign_id}"), params={
            "daily_budget_amount_local_micro": int(new_daily_budget * 1_000_000),
        })
        logger.info(f"X Ads: campaign {campaign_id} budget → ${new_daily_budget:.2f}/day")
        return True

    def update_ad_set_bid(
        self,
        ad_set_id: str,
        new_bid: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: line_item {ad_set_id} bid → ${new_bid:.4f}")
            return True
        self._request("PUT", self._account_url(f"/line_items/{ad_set_id}"), params={
            "bid_amount_local_micro": int(new_bid * 1_000_000),
        })
        return True

    def pause_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: pause campaign {campaign_id}")
            return True
        self._request("PUT", self._account_url(f"/campaigns/{campaign_id}"), params={"entity_status": "PAUSED"})
        return True

    def activate_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] X Ads: activate campaign {campaign_id}")
            return True
        self._request("PUT", self._account_url(f"/campaigns/{campaign_id}"), params={"entity_status": "ACTIVE"})
        return True
