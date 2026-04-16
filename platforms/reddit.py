"""
Reddit Ads API v3 플랫폼 클라이언트
API: https://ads-api.reddit.com/api/v3/

인증: OAuth 2.0 refresh_token → access_token
ID 스키마:
  - Ad Account:  a2_xxx
  - Campaign:    t6_xxx
  - Ad Group:    t7_xxx
  - Ad:          t8_xxx
  - Subreddit:   t5_xxx (커뮤니티 타겟팅용)

크립토 서브레딧 타겟팅 샘플:
  t5_2qh0u = r/CryptoCurrency
  t5_2s3qj = r/Bitcoin
  t5_2zf9n = r/ethereum
"""
import logging
import time
from datetime import date, datetime, timezone, timedelta
from typing import Optional

import httpx

from config.settings import settings
from platforms.base import AdPlatform, Campaign, AdSet, PerformanceData

logger = logging.getLogger(__name__)

API_BASE = "https://ads-api.reddit.com/api/v3"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


class RedditAds(AdPlatform):
    platform_name = "reddit"

    def __init__(self):
        self._access_token: Optional[str] = None
        self._token_expires_at: float = 0

    def is_configured(self) -> bool:
        return bool(
            settings.REDDIT_CLIENT_ID
            and settings.REDDIT_CLIENT_SECRET
            and settings.REDDIT_REFRESH_TOKEN
            and settings.REDDIT_ADS_ACCOUNT_ID
        )

    def _get_token(self) -> str:
        """refresh_token → access_token (1시간 유효, 캐싱)"""
        if self._access_token and time.time() < self._token_expires_at - 60:
            return self._access_token
        if not self.is_configured():
            raise RuntimeError("Reddit Ads API not configured")

        resp = httpx.post(
            TOKEN_URL,
            auth=(settings.REDDIT_CLIENT_ID, settings.REDDIT_CLIENT_SECRET),
            data={
                "grant_type": "refresh_token",
                "refresh_token": settings.REDDIT_REFRESH_TOKEN,
            },
            headers={"User-Agent": settings.REDDIT_USER_AGENT},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 3600)
        return self._access_token

    def _request(self, method: str, path: str, **kwargs) -> dict:
        token = self._get_token()
        url = f"{API_BASE}{path}"
        headers = kwargs.pop("headers", {})
        headers.update({
            "Authorization": f"Bearer {token}",
            "User-Agent": settings.REDDIT_USER_AGENT,
            "Accept": "application/json",
        })
        resp = httpx.request(method, url, headers=headers, timeout=30, **kwargs)
        if resp.status_code >= 400:
            logger.error(f"Reddit Ads {method} {path} → {resp.status_code}: {resp.text[:400]}")
            resp.raise_for_status()
        return resp.json() if resp.content else {}

    def _acct_path(self, suffix: str = "") -> str:
        return f"/ad_accounts/{settings.REDDIT_ADS_ACCOUNT_ID}{suffix}"

    # --- 조회 ---

    def get_campaigns(self) -> list[Campaign]:
        data = self._request("GET", self._acct_path("/campaigns"), params={"page.size": 200})
        out = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            daily = (attrs.get("spend_cap") or 0) / 1_000_000
            total = (attrs.get("total_budget") or 0) / 1_000_000
            out.append(Campaign(
                campaign_id=item["id"],
                campaign_name=attrs.get("name", ""),
                status=_reddit_status(attrs.get("configured_status", "")),
                daily_budget=daily,
                lifetime_budget=total or None,
                platform=self.platform_name,
            ))
        return out

    def get_ad_sets(self, campaign_id: str) -> list[AdSet]:
        """Reddit의 ad_group = Meta/X의 ad_set"""
        data = self._request(
            "GET",
            self._acct_path("/ad_groups"),
            params={"filter.campaign_id": campaign_id, "page.size": 200},
        )
        out = []
        for item in data.get("data", []):
            attrs = item.get("attributes", {})
            bid = (attrs.get("bid_value") or 0) / 1_000_000
            daily = (attrs.get("spend_cap") or 0) / 1_000_000
            out.append(AdSet(
                ad_set_id=item["id"],
                ad_set_name=attrs.get("name", ""),
                campaign_id=campaign_id,
                status=_reddit_status(attrs.get("configured_status", "")),
                daily_budget=daily or None,
                bid_amount=bid or None,
                platform=self.platform_name,
            ))
        return out

    def get_performance(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PerformanceData]:
        """POST /ad_accounts/:id/reports — breakdown by DATE + AD_GROUP"""
        start = datetime.combine(start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        end = datetime.combine(end_date, datetime.max.time()).replace(tzinfo=timezone.utc)

        body = {
            "data": {
                "breakdowns": ["DATE", "AD_GROUP_ID"],
                "fields": [
                    "impressions", "clicks", "spend",
                    "conversion_signup_total_count",
                    "conversion_purchase_total_value",
                ],
                "starts_at": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "ends_at": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "time_zone_id": "UTC",
                "filter": {
                    "filter_field": "CAMPAIGN_ID",
                    "operator": "EQUALS",
                    "values": [campaign_id],
                },
            }
        }
        data = self._request("POST", self._acct_path("/reports"), json=body)

        out = []
        for row in data.get("data", {}).get("metrics", []):
            attrs = row.get("attributes", {}) if isinstance(row, dict) else {}
            # breakdowns come back flattened into attrs
            dt = attrs.get("date", "")[:10]
            ad_group_id = attrs.get("ad_group_id", "")
            spend = (attrs.get("spend") or 0) / 1_000_000
            out.append(PerformanceData(
                platform=self.platform_name,
                campaign_id=campaign_id,
                campaign_name="",
                ad_set_id=ad_group_id,
                ad_set_name="",
                date=dt,
                impressions=int(attrs.get("impressions", 0)),
                clicks=int(attrs.get("clicks", 0)),
                spend=spend,
                conversions=int(attrs.get("conversion_signup_total_count", 0)),
                revenue=(attrs.get("conversion_purchase_total_value") or 0) / 1_000_000,
            ))
        return out

    # --- 생성/수정/삭제 ---

    def create_campaign(
        self,
        name: str,
        daily_budget: float,
        targeting: dict,
        creatives: dict,
        dry_run: bool = True,
    ) -> Optional[str]:
        """
        Campaign + Ad Group (subreddit 타겟팅 포함) + Ad를 한 번에 생성

        targeting: {
          subreddits: ["t5_2qh0u", "t5_2s3qj"],  # r/CryptoCurrency, r/Bitcoin
          countries: ["US", "GB", "CA"],
          devices: ["DESKTOP", "MOBILE"],
          funding_instrument_id: "..." (선택, 없으면 기본 결제수단)
        }
        creatives: {
          post_id: "t3_xxx" (프로모트할 Reddit 포스트)
          # 또는
          headline: str, body: str, link: str, image_url: str
        }
        """
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: create campaign '{name}' ${daily_budget}/day")
            return "dry_run_campaign_id"

        # 1. Campaign
        camp = self._request("POST", self._acct_path("/campaigns"), json={
            "data": {
                "name": name[:255],
                "objective": targeting.get("objective", "CLICKS"),
                "configured_status": "PAUSED",
                "funding_instrument_id": targeting.get("funding_instrument_id"),
            }
        })
        campaign_id = camp.get("data", {}).get("id")
        if not campaign_id:
            raise RuntimeError(f"campaign create failed: {camp}")
        logger.info(f"Reddit: campaign created {campaign_id}")

        # 2. Ad Group with subreddit targeting
        ag = self._request("POST", self._acct_path("/ad_groups"), json={
            "data": {
                "campaign_id": campaign_id,
                "name": f"{name} - AdGroup",
                "configured_status": "PAUSED",
                "bid_strategy": "MAXIMUM_VOLUME",
                "spend_cap": int(daily_budget * 1_000_000),
                "goal_type": "LIFETIME_SPEND",
                "schedule": {
                    "start_time": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                },
                "targeting": {
                    "community_targeting": {
                        "included_communities": targeting.get("subreddits", []),
                    },
                    "geolocations": targeting.get("countries", ["US"]),
                    "devices": targeting.get("devices", ["DESKTOP", "MOBILE"]),
                },
            }
        })
        ad_group_id = ag.get("data", {}).get("id")
        logger.info(f"Reddit: ad_group created {ad_group_id}")

        # 3. Ad — 기존 Reddit 포스트 프로모트 방식 (가장 쉬움)
        post_id = creatives.get("post_id")
        if post_id:
            ad = self._request("POST", self._acct_path("/ads"), json={
                "data": {
                    "ad_group_id": ad_group_id,
                    "name": f"{name} - Ad",
                    "post_id": post_id,  # t3_xxx
                    "configured_status": "PAUSED",
                }
            })
            logger.info(f"Reddit: ad created {ad.get('data', {}).get('id')}")
        else:
            logger.warning("Reddit: no post_id in creatives, skipping ad creation — need to promote a post manually or via publisher")

        return campaign_id

    def delete_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: delete campaign {campaign_id}")
            return True
        self._request("DELETE", self._acct_path(f"/campaigns/{campaign_id}"))
        logger.info(f"Reddit: campaign {campaign_id} deleted")
        return True

    def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
        dry_run: bool = True,
    ) -> bool:
        """Reddit은 Campaign이 아닌 Ad Group에 spend_cap이 있음 → 모든 ad_group 업데이트"""
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: update campaign {campaign_id} budget → ${new_daily_budget:.2f}/day")
            return True
        ad_groups = self.get_ad_sets(campaign_id)
        if not ad_groups:
            logger.warning(f"Reddit: no ad_groups under campaign {campaign_id}")
            return False
        per_group = int((new_daily_budget / len(ad_groups)) * 1_000_000)
        for ag in ad_groups:
            self._request("PATCH", self._acct_path(f"/ad_groups/{ag.ad_set_id}"), json={
                "data": {"spend_cap": per_group}
            })
        logger.info(f"Reddit: campaign {campaign_id} budget → ${new_daily_budget:.2f}/day across {len(ad_groups)} ad_groups")
        return True

    def update_ad_set_bid(
        self,
        ad_set_id: str,
        new_bid: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: ad_group {ad_set_id} bid → ${new_bid:.4f}")
            return True
        self._request("PATCH", self._acct_path(f"/ad_groups/{ad_set_id}"), json={
            "data": {"bid_value": int(new_bid * 1_000_000)}
        })
        return True

    def pause_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: pause campaign {campaign_id}")
            return True
        self._request("PATCH", self._acct_path(f"/campaigns/{campaign_id}"), json={
            "data": {"configured_status": "PAUSED"}
        })
        return True

    def activate_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Reddit: activate campaign {campaign_id}")
            return True
        self._request("PATCH", self._acct_path(f"/campaigns/{campaign_id}"), json={
            "data": {"configured_status": "ACTIVE"}
        })
        return True

    # --- 도우미 ---

    def find_subreddit_id(self, name: str) -> Optional[str]:
        """서브레딧 이름 → t5_xxx ID 조회 (예: 'CryptoCurrency' → 't5_2qh0u')"""
        try:
            token = self._get_token()
            resp = httpx.get(
                f"https://oauth.reddit.com/r/{name.lstrip('r/')}/about",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": settings.REDDIT_USER_AGENT,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            kind = data.get("kind", "")
            sid = data.get("data", {}).get("id", "")
            return f"{kind}_{sid}" if kind and sid else None
        except Exception as e:
            logger.error(f"find_subreddit_id({name}) failed: {e}")
            return None


def _reddit_status(s: str) -> str:
    s = (s or "").upper()
    if s == "ACTIVE":
        return "ACTIVE"
    if s == "PAUSED":
        return "PAUSED"
    return "DELETED"
