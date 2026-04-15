"""
캠페인 성과 분석 — 점수 매기기, 생존/도태 결정
"""
import logging
from agent.claude import ClaudeAgent

logger = logging.getLogger(__name__)


class CampaignAnalyzer:
    def __init__(self):
        self.claude = ClaudeAgent()

    def score_and_rank(self, performance: list) -> list:
        """
        성과 데이터에 점수를 매기고 순위 정렬
        Returns: [{campaign_id, campaign_name, score, ...}] sorted by score desc
        """
        if not performance:
            return []

        # 데이터 충분하면 Claude로 정성 평가
        if len(performance) >= 3:
            try:
                scored = self.claude.score_campaigns(performance)
                return scored
            except Exception as e:
                logger.warning(f"Claude scoring failed, using rule-based: {e}")

        # fallback: 규칙 기반 점수
        return self._rule_based_score(performance)

    def _rule_based_score(self, performance: list) -> list:
        """규칙 기반 점수 (Claude 없이)"""
        scored = []
        for p in performance:
            score = 0
            impressions = p.get("impressions", 0)
            clicks = p.get("clicks", 0)
            spend = p.get("spend", 0)
            conversions = p.get("conversions", 0)
            ctr = p.get("ctr", 0)
            cpc = p.get("cpc", 0)

            # 노출 충분한지 (최소 100)
            if impressions < 100:
                score = 30  # 데이터 부족, 중간
            else:
                # CTR 점수 (40점 만점)
                if ctr >= 0.03:
                    score += 40
                elif ctr >= 0.02:
                    score += 30
                elif ctr >= 0.01:
                    score += 20
                elif ctr >= 0.005:
                    score += 10

                # CPC 점수 (30점 만점) — 낮을수록 좋음
                if cpc > 0:
                    if cpc <= 0.5:
                        score += 30
                    elif cpc <= 1.0:
                        score += 20
                    elif cpc <= 2.0:
                        score += 10

                # 전환 점수 (30점 만점)
                if conversions >= 5:
                    score += 30
                elif conversions >= 2:
                    score += 20
                elif conversions >= 1:
                    score += 10

            scored.append({**p, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    def select_survivors(self, scored: list, survive_count: int = 2) -> tuple:
        """
        상위 N개 생존, 나머지 도태
        Returns: (survivors, losers)
        """
        survivors = scored[:survive_count]
        losers = scored[survive_count:]

        for s in survivors:
            logger.info(f"  SURVIVE: {s.get('campaign_name', s.get('campaign_id', '?'))} (score: {s.get('score', 0)})")
        for l in losers:
            logger.info(f"  KILL: {l.get('campaign_name', l.get('campaign_id', '?'))} (score: {l.get('score', 0)})")

        return survivors, losers
