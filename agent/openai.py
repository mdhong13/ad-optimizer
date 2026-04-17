"""
OpenAI GPT-4o 클라이언트 — 전략 판단용 (Claude 대체)
"""
import json
import logging
from pathlib import Path
from openai import OpenAI
from config.settings import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


class OpenAIAgent:
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o"  # GPT-4o (최신, 가장 강력)

    def _load_prompt(self, name: str) -> str:
        path = PROMPTS_DIR / f"{name}.md"
        if path.exists():
            return path.read_text(encoding="utf-8")
        return ""

    def ask(self, system: str, user_message: str, max_tokens: int = 4096) -> str:
        """GPT-4o로 텍스트 생성"""
        resp = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user_message}],
        )
        return resp.choices[0].message.content

    def ask_json(self, system: str, user_message: str, max_tokens: int = 4096) -> dict:
        """GPT-4o로 JSON 생성"""
        text = self.ask(system, user_message, max_tokens)
        # JSON 블록 추출
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    def optimize_budget(self, performance_data: list[dict], market_events: list[dict]) -> list[dict]:
        """성과 데이터 + 시장 이벤트 → 예산 조정 결정 리스트"""
        system = self._load_prompt("budget_optimizer") or (
            "You are an ad budget optimizer for OneMessage, a safety messaging app. "
            "Analyze campaign performance and market events, then recommend budget adjustments. "
            "Return JSON array of decisions."
        )
        user_msg = json.dumps({
            "performance": performance_data[:50],
            "market_events": market_events[:10],
        }, ensure_ascii=False, indent=2)

        return self.ask_json(system, user_msg)

    def generate_campaign_variants(
        self,
        survivors: list[dict],
        count: int = 20,
        market_context: str = "",
    ) -> list[dict]:
        """
        상위 캠페인 기반 변형 생성
        반환: [{name, headlines, descriptions, keywords, targeting}]
        """
        system = self._load_prompt("creative_analyzer") or (
            "You are a creative strategist for OneMessage, a safety messaging app "
            "for crypto wallet holders. Generate ad campaign variants based on "
            "top-performing campaigns. Return JSON array."
        )
        user_msg = json.dumps({
            "survivors": survivors,
            "count": count,
            "market_context": market_context,
            "product": "OneMessage — sends your pre-written messages when you become unresponsive",
            "target_audience": "Crypto holders who want to protect access to their wallets",
        }, ensure_ascii=False, indent=2)

        return self.ask_json(system, user_msg)

    def analyze_market_event(self, event: dict) -> dict:
        """시장 이벤트 → 광고 전략 대응 결정"""
        system = self._load_prompt("market_responder") or (
            "You are a market event responder for OneMessage ads. "
            "Analyze crypto market events and recommend ad strategy changes. "
            "Return JSON with actions."
        )
        return self.ask_json(system, json.dumps(event, ensure_ascii=False))

    def score_campaigns(self, campaigns: list[dict]) -> list[dict]:
        """캠페인 성과 점수 매기기 (0-100)"""
        system = (
            "Score each campaign from 0 to 100 based on performance metrics. "
            "Consider CTR, CPC, conversions, and spend efficiency. "
            "Return JSON array with campaign_id and score fields, sorted by score descending."
        )
        return self.ask_json(system, json.dumps(campaigns, ensure_ascii=False))
