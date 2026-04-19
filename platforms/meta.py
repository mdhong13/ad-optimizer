"""
Meta Ads (Facebook + Instagram) 플랫폼 클라이언트
facebook-business SDK 사용
"""
import logging
from datetime import date
from typing import Optional

from config.settings import settings
from platforms.base import AdPlatform, Campaign, AdSet, PerformanceData

logger = logging.getLogger(__name__)


class MetaAds(AdPlatform):
    platform_name = "meta"

    def __init__(self, account_id: Optional[str] = None):
        """account_id 미지정 시 DB 활성 계정 → settings 기본값 순서로 폴백."""
        self._api = None
        self._account = None
        self._account_id = account_id or self._resolve_account_id()

    @staticmethod
    def _resolve_account_id() -> str:
        try:
            from storage.db import get_active_meta_account
            return get_active_meta_account()
        except Exception:
            return settings.META_AD_ACCOUNT_ID

    @property
    def account_id(self) -> str:
        return self._account_id

    def _init_api(self):
        if self._api:
            return
        try:
            from facebook_business.api import FacebookAdsApi
            from facebook_business.adobjects.adaccount import AdAccount

            FacebookAdsApi.init(
                app_id=settings.META_APP_ID,
                app_secret=settings.META_APP_SECRET,
                access_token=settings.META_ACCESS_TOKEN,
            )
            self._account = AdAccount(self._account_id)
            self._api = True
            logger.info(f"Meta Ads API initialized (account={self._account_id})")
        except Exception as e:
            logger.error(f"Meta API init failed: {e}")
            raise

    def is_configured(self) -> bool:
        base = bool(
            settings.META_APP_ID
            and settings.META_ACCESS_TOKEN
            and self._account_id
        )
        if settings.DRY_RUN:
            return base
        # 실계정 모드는 PAGE_ID 필수
        return base and bool(settings.META_PAGE_ID)

    def get_campaigns(self) -> list[Campaign]:
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign

        fields = [
            FBCampaign.Field.id,
            FBCampaign.Field.name,
            FBCampaign.Field.status,
            FBCampaign.Field.daily_budget,
            FBCampaign.Field.lifetime_budget,
        ]
        params = {"effective_status": ["ACTIVE", "PAUSED"]}
        campaigns = self._account.get_campaigns(fields=fields, params=params)

        result = []
        for c in campaigns:
            result.append(Campaign(
                campaign_id=c["id"],
                campaign_name=c.get("name", ""),
                status=c.get("status", ""),
                daily_budget=float(c.get("daily_budget", 0)) / 100,  # cents → dollars
                lifetime_budget=float(c.get("lifetime_budget", 0)) / 100 or None,
                platform=self.platform_name,
            ))
        return result

    def get_ad_sets(self, campaign_id: str) -> list[AdSet]:
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        from facebook_business.adobjects.adset import AdSet as FBAdSet

        campaign = FBCampaign(campaign_id)
        fields = [
            FBAdSet.Field.id,
            FBAdSet.Field.name,
            FBAdSet.Field.status,
            FBAdSet.Field.daily_budget,
            FBAdSet.Field.bid_amount,
        ]
        ad_sets = campaign.get_ad_sets(fields=fields)

        result = []
        for s in ad_sets:
            result.append(AdSet(
                ad_set_id=s["id"],
                ad_set_name=s.get("name", ""),
                campaign_id=campaign_id,
                status=s.get("status", ""),
                daily_budget=float(s.get("daily_budget", 0)) / 100 or None,
                bid_amount=float(s.get("bid_amount", 0)) / 100 or None,
                platform=self.platform_name,
            ))
        return result

    def get_performance(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PerformanceData]:
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        from facebook_business.adobjects.adsinsights import AdsInsights

        campaign = FBCampaign(campaign_id)
        fields = [
            AdsInsights.Field.campaign_id,
            AdsInsights.Field.campaign_name,
            AdsInsights.Field.adset_id,
            AdsInsights.Field.adset_name,
            AdsInsights.Field.date_start,
            AdsInsights.Field.impressions,
            AdsInsights.Field.clicks,
            AdsInsights.Field.spend,
            AdsInsights.Field.actions,
            AdsInsights.Field.action_values,
        ]
        params = {
            "time_range": {
                "since": start_date.strftime("%Y-%m-%d"),
                "until": end_date.strftime("%Y-%m-%d"),
            },
            "time_increment": 1,
            "level": "adset",
        }
        insights = campaign.get_insights(fields=fields, params=params)

        result = []
        for row in insights:
            conversions = self._extract_action_value(row.get("actions", []), "purchase")
            revenue = self._extract_action_value(row.get("action_values", []), "purchase")
            result.append(PerformanceData(
                platform=self.platform_name,
                campaign_id=row.get("campaign_id", campaign_id),
                campaign_name=row.get("campaign_name", ""),
                ad_set_id=row.get("adset_id", ""),
                ad_set_name=row.get("adset_name", ""),
                date=row.get("date_start", ""),
                impressions=int(row.get("impressions", 0)),
                clicks=int(row.get("clicks", 0)),
                spend=float(row.get("spend", 0)),
                conversions=int(conversions),
                revenue=float(revenue),
            ))
        return result

    def _extract_action_value(self, actions: list, action_type: str) -> float:
        for a in actions:
            if a.get("action_type") == action_type:
                return float(a.get("value", 0))
        return 0.0

    # 광고 이미지 에셋 폴더 (플랫폼별 표준 경로)
    # 규칙: assets/generated/{platform}/ 에서 랜덤 선택
    _ASSETS_DIR = "assets/generated/meta"

    def _resolve_and_upload_image(self, image_path: Optional[str], image_url: Optional[str]) -> Optional[str]:
        """이미지 소스를 결정해서 /adimages 업로드 후 image_hash 반환.

        우선순위:
          1) image_path (로컬 파일) — 바로 업로드
          2) image_url (원격 URL) — 다운로드 후 업로드
          3) assets/generated/meta/ 폴더에서 랜덤 선택
        """
        import os
        import random
        import tempfile

        local_path = None

        # 1) 명시적 로컬 경로
        if image_path and os.path.exists(image_path):
            local_path = image_path
        # 2) 원격 URL
        elif image_url:
            try:
                import requests as _req
                img_bytes = _req.get(image_url, timeout=15).content
                tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                tmp.write(img_bytes)
                tmp.close()
                local_path = tmp.name
            except Exception as e:
                logger.warning(f"Meta: image download failed: {e}")
        # 3) 에셋 폴더 랜덤 폴백
        if not local_path:
            from pathlib import Path
            assets = Path(__file__).resolve().parent.parent / self._ASSETS_DIR
            if assets.is_dir():
                candidates = [p for p in assets.iterdir()
                              if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png")]
                if candidates:
                    local_path = str(random.choice(candidates))
                    logger.info(f"Meta: using asset image {os.path.basename(local_path)}")

        if not local_path:
            logger.warning("Meta: no image available — creative will have no image")
            return None

        try:
            img = self._account.create_ad_image(params={"filename": local_path})
            image_hash = img.get("hash")
            if not image_hash and img.get("images"):
                image_hash = list(img["images"].values())[0].get("hash")
            if image_hash:
                logger.info(f"Meta: image uploaded, hash={image_hash[:10]}...")
                return image_hash
        except Exception as e:
            logger.warning(f"Meta: image upload failed, skipping: {e}")
        return None

    def create_campaign(
        self,
        name: str,
        daily_budget: float,
        targeting: dict,
        creatives: dict,
        dry_run: bool = True,
    ):
        """
        Meta 캠페인 + AdSet + Ad 한 번에 생성
        targeting: {countries: ["US","KR"], age_min: 25, age_max: 55, interests: [...]}
        creatives: {title: str, body: str, link: str, image_url: str}
        """
        if dry_run:
            logger.info(f"[DRY RUN] Meta: create campaign '{name}' ${daily_budget}/day")
            return "dry_run_campaign_id"
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        from facebook_business.adobjects.adset import AdSet as FBAdSet
        from facebook_business.adobjects.ad import Ad as FBAd
        from facebook_business.adobjects.adcreative import AdCreative

        # 실집행 전 필수 값 검증
        page_id = targeting.get("page_id") or settings.META_PAGE_ID
        if not page_id:
            raise RuntimeError("META_PAGE_ID 미설정: AdCreative 생성 불가")
        # Meta 최소 일 예산 = $1 (100 cents). 음수/0 방지
        daily_budget_cents = max(100, int(float(daily_budget) * 100))

        # 1. Campaign (PAUSED로 생성)
        # is_adset_budget_sharing_enabled=False → 예산은 광고세트 레벨에서 관리
        campaign = self._account.create_campaign(params={
            FBCampaign.Field.name: name,
            FBCampaign.Field.objective: "OUTCOME_TRAFFIC",
            FBCampaign.Field.status: "PAUSED",
            FBCampaign.Field.special_ad_categories: [],
            "is_adset_budget_sharing_enabled": False,
        })
        campaign_id = campaign["id"]
        logger.info(f"Meta: campaign created {campaign_id} (PAUSED, ${daily_budget_cents/100:.2f}/day)")

        # 광고세트/광고 생성 실패 시 고아 캠페인 방지 — 캠페인 삭제 롤백
        try:
            # 2. AdSet
            # targeting_automation.advantage_audience=0 → Meta v25 필수 플래그
            countries = targeting.get("countries", ["US"])
            ad_set = self._account.create_ad_set(params={
                FBAdSet.Field.name: f"{name} - AdSet",
                FBAdSet.Field.campaign_id: campaign_id,
                FBAdSet.Field.daily_budget: daily_budget_cents,
                FBAdSet.Field.billing_event: "IMPRESSIONS",
                FBAdSet.Field.optimization_goal: "LINK_CLICKS",
                FBAdSet.Field.bid_strategy: "LOWEST_COST_WITHOUT_CAP",
                FBAdSet.Field.destination_type: "WEBSITE",
                FBAdSet.Field.targeting: {
                    "geo_locations": {"countries": countries},
                    "age_min": targeting.get("age_min", 25),
                    "age_max": targeting.get("age_max", 55),
                    "targeting_automation": {"advantage_audience": 0},
                },
                FBAdSet.Field.status: "PAUSED",
            })
            ad_set_id = ad_set["id"]
            logger.info(f"Meta: adset created {ad_set_id}")

            # 3. Creative + Ad
            # Meta v25: link_data의 image_url 필드 폐지됨 → image_hash 사용
            # 이미지가 있으면 /adimages 업로드 후 해시 참조, 없으면 링크만으로 생성
            link_data = {
                "link": creatives.get("link", "https://onemsg.net"),
            }
            if creatives.get("body"):
                link_data["message"] = creatives["body"]
            if creatives.get("title"):
                link_data["name"] = creatives["title"]

            # 이미지 소스 우선순위:
            #   1) creatives["image_path"] 로컬 파일 경로
            #   2) creatives["image_url"] 원격 URL
            #   3) assets/generated/meta/ 폴더에서 랜덤 선택
            image_hash = self._resolve_and_upload_image(
                creatives.get("image_path"),
                creatives.get("image_url"),
            )
            if image_hash:
                link_data["image_hash"] = image_hash

            creative = self._account.create_ad_creative(params={
                AdCreative.Field.name: f"{name} - Creative",
                AdCreative.Field.object_story_spec: {
                    "page_id": page_id,
                    "link_data": link_data,
                },
            })

            ad = self._account.create_ad(params={
                FBAd.Field.name: f"{name} - Ad",
                FBAd.Field.adset_id: ad_set_id,
                FBAd.Field.creative: {"creative_id": creative["id"]},
                FBAd.Field.status: "PAUSED",
            })
            logger.info(f"Meta: ad created {ad['id']}")

            return campaign_id
        except Exception as e:
            logger.error(f"Meta: adset/ad creation failed, rolling back campaign {campaign_id}: {e}")
            try:
                FBCampaign(campaign_id).api_delete()
                logger.info(f"Meta: rollback — campaign {campaign_id} deleted")
            except Exception as rollback_err:
                logger.error(f"Meta: rollback failed for {campaign_id}: {rollback_err}")
            raise

    def delete_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Meta: delete campaign {campaign_id}")
            return True
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        campaign = FBCampaign(campaign_id)
        campaign.update({FBCampaign.Field.status: "DELETED"})
        campaign.remote_update()
        logger.info(f"Meta: campaign {campaign_id} deleted")
        return True

    def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Meta: update campaign {campaign_id} budget → ${new_daily_budget:.2f}/day")
            return True
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        campaign = FBCampaign(campaign_id)
        campaign.update({
            FBCampaign.Field.daily_budget: int(new_daily_budget * 100),  # dollars → cents
        })
        campaign.remote_update()
        logger.info(f"Meta: campaign {campaign_id} budget updated to ${new_daily_budget:.2f}/day")
        return True

    def update_ad_set_bid(
        self,
        ad_set_id: str,
        new_bid: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Meta: update adset {ad_set_id} bid → ${new_bid:.4f}")
            return True
        self._init_api()
        from facebook_business.adobjects.adset import AdSet as FBAdSet
        ad_set = FBAdSet(ad_set_id)
        ad_set.update({FBAdSet.Field.bid_amount: int(new_bid * 100)})
        ad_set.remote_update()
        logger.info(f"Meta: adset {ad_set_id} bid updated to ${new_bid:.4f}")
        return True

    def pause_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Meta: pause campaign {campaign_id}")
            return True
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        campaign = FBCampaign(campaign_id)
        campaign.update({FBCampaign.Field.status: "PAUSED"})
        campaign.remote_update()
        return True

    def activate_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Meta: activate campaign {campaign_id}")
            return True
        self._init_api()
        from facebook_business.adobjects.campaign import Campaign as FBCampaign
        campaign = FBCampaign(campaign_id)
        campaign.update({FBCampaign.Field.status: "ACTIVE"})
        campaign.remote_update()
        logger.warning(f"Meta: campaign {campaign_id} ACTIVATED (live spend begins)")
        return True
