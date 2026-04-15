"""
광고 플랫폼 추상 기본 클래스
모든 플랫폼은 이 인터페이스를 구현해야 합니다.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


@dataclass
class Campaign:
    campaign_id: str
    campaign_name: str
    status: str          # 'ACTIVE', 'PAUSED', 'DELETED'
    daily_budget: float  # USD
    lifetime_budget: Optional[float] = None
    platform: str = ""


@dataclass
class AdSet:
    ad_set_id: str
    ad_set_name: str
    campaign_id: str
    status: str
    daily_budget: Optional[float] = None
    bid_amount: Optional[float] = None
    platform: str = ""


@dataclass
class PerformanceData:
    platform: str
    campaign_id: str
    campaign_name: str
    date: str           # YYYY-MM-DD
    hour: Optional[int] = None
    ad_set_id: str = ""
    ad_set_name: str = ""
    impressions: int = 0
    clicks: int = 0
    spend: float = 0.0
    conversions: int = 0
    revenue: float = 0.0

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0

    @property
    def cpc(self) -> float:
        return self.spend / self.clicks if self.clicks else 0.0

    @property
    def cpm(self) -> float:
        return (self.spend / self.impressions * 1000) if self.impressions else 0.0

    @property
    def roas(self) -> float:
        return self.revenue / self.spend if self.spend else 0.0

    def to_db_dict(self) -> dict:
        return {
            "platform": self.platform,
            "campaign_id": self.campaign_id,
            "campaign_name": self.campaign_name,
            "ad_set_id": self.ad_set_id,
            "ad_set_name": self.ad_set_name,
            "date": self.date,
            "hour": self.hour,
            "impressions": self.impressions,
            "clicks": self.clicks,
            "spend": self.spend,
            "conversions": self.conversions,
            "revenue": self.revenue,
            "ctr": round(self.ctr, 6),
            "cpc": round(self.cpc, 4),
            "cpm": round(self.cpm, 4),
            "roas": round(self.roas, 4),
        }


class AdPlatform(ABC):
    """모든 광고 플랫폼이 구현해야 하는 인터페이스"""

    platform_name: str = "base"

    @abstractmethod
    def get_campaigns(self) -> list[Campaign]:
        """활성 캠페인 목록 반환"""

    @abstractmethod
    def get_ad_sets(self, campaign_id: str) -> list[AdSet]:
        """캠페인의 광고세트 목록 반환"""

    @abstractmethod
    def get_performance(
        self,
        campaign_id: str,
        start_date: date,
        end_date: date,
    ) -> list[PerformanceData]:
        """기간별 성과 데이터 반환"""

    @abstractmethod
    def update_campaign_budget(
        self,
        campaign_id: str,
        new_daily_budget: float,
        dry_run: bool = True,
    ) -> bool:
        """캠페인 일간 예산 변경"""

    @abstractmethod
    def update_ad_set_bid(
        self,
        ad_set_id: str,
        new_bid: float,
        dry_run: bool = True,
    ) -> bool:
        """광고세트 입찰가 변경"""

    @abstractmethod
    def create_campaign(
        self,
        name: str,
        daily_budget: float,
        targeting: dict,
        creatives: dict,
        dry_run: bool = True,
    ) -> Optional[str]:
        """캠페인 생성, campaign_id 반환"""

    @abstractmethod
    def delete_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        """캠페인 삭제 (또는 REMOVED 처리)"""

    @abstractmethod
    def pause_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        """캠페인 일시정지"""

    @abstractmethod
    def activate_campaign(self, campaign_id: str, dry_run: bool = True) -> bool:
        """캠페인 재개"""

    def is_configured(self) -> bool:
        """API 키가 설정되어 있는지 확인"""
        return True
