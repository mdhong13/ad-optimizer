"""
Google Ads 플랫폼 클라이언트
google-ads SDK 사용
"""
import logging
from datetime import date

from config.settings import settings
from platforms.base import AdPlatform, Campaign, AdSet, PerformanceData

logger = logging.getLogger(__name__)


class GoogleAds(AdPlatform):
    platform_name = "google"

    def __init__(self):
        self._client = None

    def _init_client(self):
        if self._client:
            return
        try:
            from google.ads.googleads.client import GoogleAdsClient

            config = {
                "developer_token": settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                "refresh_token": settings.GOOGLE_ADS_REFRESH_TOKEN,
                "login_customer_id": settings.GOOGLE_ADS_LOGIN_CUSTOMER_ID,
                "use_proto_plus": True,
            }
            self._client = GoogleAdsClient.load_from_dict(config)
            logger.info("Google Ads client initialized")
        except Exception as e:
            logger.error(f"Google Ads init failed: {e}")
            raise

    def is_configured(self) -> bool:
        return bool(
            settings.GOOGLE_ADS_DEVELOPER_TOKEN
            and settings.GOOGLE_ADS_CLIENT_ID
            and settings.GOOGLE_ADS_REFRESH_TOKEN
            and settings.GOOGLE_ADS_CUSTOMER_ID
        )

    def _customer_id(self) -> str:
        return settings.GOOGLE_ADS_CUSTOMER_ID.replace("-", "")

    def get_campaigns(self) -> list[Campaign]:
        self._init_client()
        ga_service = self._client.get_service("GoogleAdsService")
        query = """
            SELECT
                campaign.id, campaign.name, campaign.status,
                campaign_budget.amount_micros
            FROM campaign
            WHERE campaign.status IN ('ENABLED', 'PAUSED')
            ORDER BY campaign.id
        """
        response = ga_service.search(customer_id=self._customer_id(), query=query)

        result = []
        for row in response:
            c = row.campaign
            budget_usd = row.campaign_budget.amount_micros / 1_000_000
            result.append(Campaign(
                campaign_id=str(c.id),
                campaign_name=c.name,
                status=c.status.name,
                daily_budget=budget_usd,
                platform=self.platform_name,
            ))
        return result

    def get_ad_sets(self, campaign_id: str) -> list[AdSet]:
        """Google Ads에서는 Ad Group이 Ad Set에 해당"""
        self._init_client()
        ga_service = self._client.get_service("GoogleAdsService")
        query = f"""
            SELECT
                ad_group.id, ad_group.name, ad_group.status,
                ad_group.cpc_bid_micros
            FROM ad_group
            WHERE campaign.id = {campaign_id}
        """
        response = ga_service.search(customer_id=self._customer_id(), query=query)

        result = []
        for row in response:
            ag = row.ad_group
            bid_usd = ag.cpc_bid_micros / 1_000_000 if ag.cpc_bid_micros else None
            result.append(AdSet(
                ad_set_id=str(ag.id),
                ad_set_name=ag.name,
                campaign_id=campaign_id,
                status=ag.status.name,
                bid_amount=bid_usd,
                platform=self.platform_name,
            ))
        return result

    def get_performance(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PerformanceData]:
        self._init_client()
        ga_service = self._client.get_service("GoogleAdsService")
        start = start_date.strftime("%Y-%m-%d")
        end = end_date.strftime("%Y-%m-%d")
        query = f"""
            SELECT
                campaign.id, campaign.name,
                ad_group.id, ad_group.name,
                segments.date,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value
            FROM ad_group
            WHERE campaign.id = {campaign_id}
              AND segments.date BETWEEN '{start}' AND '{end}'
        """
        response = ga_service.search(customer_id=self._customer_id(), query=query)

        result = []
        for row in response:
            result.append(PerformanceData(
                platform=self.platform_name,
                campaign_id=str(row.campaign.id),
                campaign_name=row.campaign.name,
                ad_set_id=str(row.ad_group.id),
                ad_set_name=row.ad_group.name,
                date=row.segments.date,
                impressions=row.metrics.impressions,
                clicks=row.metrics.clicks,
                spend=row.metrics.cost_micros / 1_000_000,
                conversions=int(row.metrics.conversions),
                revenue=row.metrics.conversions_value,
            ))
        return result

    def create_campaign(
        self,
        name: str,
        daily_budget: float,
        targeting: dict,
        creatives: dict,
        dry_run: bool = True,
    ):
        """
        Google Ads 캠페인 + AdGroup + Ad 생성
        targeting: {countries: ["US","KR"], keywords: [...]}
        creatives: {headlines: [...], descriptions: [...], final_url: str}
        """
        if dry_run:
            logger.info(f"[DRY RUN] Google: create campaign '{name}' ${daily_budget}/day")
            return "dry_run_campaign_id"
        self._init_client()
        cid = self._customer_id()

        # 1. Budget
        budget_service = self._client.get_service("CampaignBudgetService")
        budget_op = self._client.get_type("CampaignBudgetOperation")
        budget = budget_op.create
        budget.name = f"{name} Budget"
        budget.amount_micros = int(daily_budget * 1_000_000)
        budget.delivery_method = self._client.enums.BudgetDeliveryMethodEnum.STANDARD
        budget_resp = budget_service.mutate_campaign_budgets(customer_id=cid, operations=[budget_op])
        budget_rn = budget_resp.results[0].resource_name

        # 2. Campaign
        campaign_service = self._client.get_service("CampaignService")
        campaign_op = self._client.get_type("CampaignOperation")
        camp = campaign_op.create
        camp.name = name
        camp.campaign_budget = budget_rn
        camp.advertising_channel_type = self._client.enums.AdvertisingChannelTypeEnum.SEARCH
        camp.status = self._client.enums.CampaignStatusEnum.PAUSED
        camp.manual_cpc.enhanced_cpc_enabled = True
        countries = targeting.get("countries", ["US"])
        for cc in countries:
            target = camp.geo_target_type_setting
            # geo targeting은 별도 CampaignCriterion으로 추가 필요
        camp_resp = campaign_service.mutate_campaigns(customer_id=cid, operations=[campaign_op])
        campaign_rn = camp_resp.results[0].resource_name
        campaign_id = campaign_rn.split("/")[-1]

        # Geo targeting
        criterion_service = self._client.get_service("CampaignCriterionService")
        geo_service = self._client.get_service("GeoTargetConstantService")
        for cc in countries:
            # 국가 코드 → geo target constant 조회
            geo_results = geo_service.suggest_geo_target_constants(
                locale="en",
                country_code=cc,
                location_names=self._client.get_type("SuggestGeoTargetConstantsRequest.LocationNames")(
                    names=[cc]
                ),
            )
            for suggestion in geo_results.geo_target_constant_suggestions:
                geo_rn = suggestion.geo_target_constant.resource_name
                crit_op = self._client.get_type("CampaignCriterionOperation")
                crit = crit_op.create
                crit.campaign = campaign_rn
                crit.location.geo_target_constant = geo_rn
                criterion_service.mutate_campaign_criteria(
                    customer_id=cid, operations=[crit_op]
                )
                break  # 첫 결과만

        # 3. Ad Group
        ag_service = self._client.get_service("AdGroupService")
        ag_op = self._client.get_type("AdGroupOperation")
        ag = ag_op.create
        ag.name = f"{name} - AdGroup"
        ag.campaign = campaign_rn
        ag.status = self._client.enums.AdGroupStatusEnum.ENABLED
        ag.type_ = self._client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        ag_resp = ag_service.mutate_ad_groups(customer_id=cid, operations=[ag_op])
        ag_rn = ag_resp.results[0].resource_name

        # 4. Keywords
        kw_service = self._client.get_service("AdGroupCriterionService")
        for kw in targeting.get("keywords", []):
            kw_op = self._client.get_type("AdGroupCriterionOperation")
            criterion = kw_op.create
            criterion.ad_group = ag_rn
            criterion.keyword.text = kw
            criterion.keyword.match_type = self._client.enums.KeywordMatchTypeEnum.PHRASE
            kw_service.mutate_ad_group_criteria(customer_id=cid, operations=[kw_op])

        # 5. Responsive Search Ad
        ad_service = self._client.get_service("AdGroupAdService")
        ad_op = self._client.get_type("AdGroupAdOperation")
        ad = ad_op.create
        ad.ad_group = ag_rn
        ad.status = self._client.enums.AdGroupAdStatusEnum.ENABLED
        rsa = ad.ad.responsive_search_ad
        for h in creatives.get("headlines", [])[:15]:
            headline = self._client.get_type("AdTextAsset")
            headline.text = h
            rsa.headlines.append(headline)
        for d in creatives.get("descriptions", [])[:4]:
            desc = self._client.get_type("AdTextAsset")
            desc.text = d
            rsa.descriptions.append(desc)
        ad.ad.final_urls.append(creatives.get("final_url", "https://onemsg.net"))
        ad_service.mutate_ad_group_ads(customer_id=cid, operations=[ad_op])

        logger.info(f"Google: campaign created {campaign_id}")
        return campaign_id

    def delete_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Google: delete campaign {campaign_id}")
            return True
        self._init_client()
        return self._set_campaign_status(campaign_id, "REMOVED")

    def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Google: update campaign {campaign_id} budget → ${new_daily_budget:.2f}/day")
            return True
        self._init_client()
        # Google Ads에서 예산은 campaign_budget 리소스로 관리
        # 먼저 캠페인의 budget_resource_name을 조회한 후 업데이트
        ga_service = self._client.get_service("GoogleAdsService")
        query = f"""
            SELECT campaign.campaign_budget
            FROM campaign
            WHERE campaign.id = {campaign_id}
        """
        response = ga_service.search(customer_id=self._customer_id(), query=query)
        budget_resource = None
        for row in response:
            budget_resource = row.campaign.campaign_budget
            break

        if not budget_resource:
            logger.error(f"Google: budget resource not found for campaign {campaign_id}")
            return False

        budget_service = self._client.get_service("CampaignBudgetService")
        budget_op = self._client.get_type("CampaignBudgetOperation")
        budget = budget_op.update
        budget.resource_name = budget_resource
        budget.amount_micros = int(new_daily_budget * 1_000_000)

        field_mask = self._client.get_type("FieldMask")
        field_mask.paths.append("amount_micros")
        budget_op.update_mask.CopyFrom(field_mask)

        budget_service.mutate_campaign_budgets(
            customer_id=self._customer_id(),
            operations=[budget_op],
        )
        logger.info(f"Google: campaign {campaign_id} budget updated to ${new_daily_budget:.2f}/day")
        return True

    def update_ad_set_bid(
        self,
        ad_set_id: str,
        new_bid: float,
        dry_run: bool = True,
    ) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Google: update ad_group {ad_set_id} bid → ${new_bid:.4f}")
            return True
        self._init_client()
        ag_service = self._client.get_service("AdGroupService")
        ag_op = self._client.get_type("AdGroupOperation")
        ag = ag_op.update
        ag.resource_name = self._client.get_service("AdGroupService").ad_group_path(
            self._customer_id(), ad_set_id
        )
        ag.cpc_bid_micros = int(new_bid * 1_000_000)

        field_mask = self._client.get_type("FieldMask")
        field_mask.paths.append("cpc_bid_micros")
        ag_op.update_mask.CopyFrom(field_mask)

        ag_service.mutate_ad_groups(
            customer_id=self._customer_id(),
            operations=[ag_op],
        )
        logger.info(f"Google: ad_group {ad_set_id} bid updated to ${new_bid:.4f}")
        return True

    def pause_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Google: pause campaign {campaign_id}")
            return True
        self._init_client()
        return self._set_campaign_status(campaign_id, "PAUSED")

    def activate_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        if dry_run:
            logger.info(f"[DRY RUN] Google: activate campaign {campaign_id}")
            return True
        self._init_client()
        return self._set_campaign_status(campaign_id, "ENABLED")

    def _set_campaign_status(self, campaign_id: str, status: str) -> bool:
        campaign_service = self._client.get_service("CampaignService")
        campaign_op = self._client.get_type("CampaignOperation")
        campaign = campaign_op.update
        campaign.resource_name = campaign_service.campaign_path(
            self._customer_id(), campaign_id
        )
        status_enum = self._client.enums.CampaignStatusEnum.CampaignStatus[status]
        campaign.status = status_enum

        field_mask = self._client.get_type("FieldMask")
        field_mask.paths.append("status")
        campaign_op.update_mask.CopyFrom(field_mask)

        campaign_service.mutate_campaigns(
            customer_id=self._customer_id(),
            operations=[campaign_op],
        )
        logger.info(f"Google: campaign {campaign_id} status → {status}")
        return True
