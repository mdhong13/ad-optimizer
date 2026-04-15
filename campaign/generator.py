"""
LLM 기반 광고 카피 자동 생성
Claude(전략) + 로컬 LLM(대량)
"""
import logging
from agent.claude import ClaudeAgent
from agent.local_llm import LocalLLM

logger = logging.getLogger(__name__)


class CampaignGenerator:
    def __init__(self):
        self.claude = ClaudeAgent()
        self.local_llm = LocalLLM()

    def generate_initial(self, count: int = 20) -> list:
        """첫 캠페인 세트 생성 (기존 데이터 없을 때)"""
        return self.claude.generate_campaign_variants(
            survivors=[],
            count=count,
            market_context="Initial launch — OneMessage safety messaging for crypto holders",
        )

    def generate_from_survivors(self, survivors: list, count: int = 18, market_context: str = "") -> list:
        """상위 캠페인 기반 변형 생성"""
        # 전략은 Claude
        strategy = self.claude.generate_campaign_variants(
            survivors=survivors,
            count=min(count, 5),
            market_context=market_context,
        )

        # 나머지는 로컬 LLM으로 대량 변형
        remaining = count - len(strategy)
        if remaining > 0 and self.local_llm.is_available():
            try:
                variants = self.local_llm.generate_ad_copies(
                    {"survivors": survivors, "strategy_examples": strategy[:2]},
                    count=remaining,
                )
                strategy.extend(variants)
            except Exception as e:
                logger.warning(f"Local LLM failed, using Claude for all: {e}")
                extra = self.claude.generate_campaign_variants(
                    survivors=survivors,
                    count=remaining,
                    market_context=market_context,
                )
                strategy.extend(extra)

        return strategy[:count]

    def generate_event_response(self, event: dict, current_campaigns: list) -> list:
        """시장 이벤트 대응 캠페인 생성"""
        event_type = event.get("event_type", "")
        context = f"URGENT: {event.get('title', '')}. {event.get('detail', '')}"

        if event_type == "price_crash":
            context += " Focus on asset protection and security messaging."
        elif event_type == "hack_news":
            context += " Focus on wallet security and posthumous message delivery."
        elif event_type == "ath":
            context += " Focus on new crypto investors entering the market."

        return self.claude.generate_campaign_variants(
            survivors=current_campaigns[:2],
            count=5,
            market_context=context,
        )
