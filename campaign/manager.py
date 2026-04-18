"""
캠페인 자동 최적화 매니저
20개 생성 → 성과 체크 → 2개 생존 → 반복
"""
import logging
import uuid
from datetime import date, timedelta

from config.settings import settings
from platforms.base import AdPlatform, PerformanceData
from agent.claude import ClaudeAgent
from agent.local_llm import LocalLLM
from storage import db
from storage.models import campaign_cycle

logger = logging.getLogger(__name__)


class CampaignManager:
    def __init__(self, platform: AdPlatform):
        self.platform = platform
        self.claude = ClaudeAgent()
        self.local_llm = LocalLLM()
        self.total = settings.CAMPAIGNS_PER_CYCLE
        self.survive = settings.CAMPAIGNS_SURVIVE
        self.dry_run = settings.DRY_RUN
        self.auto_activate = settings.AUTO_ACTIVATE
        self.max_budget = settings.MAX_DAILY_BUDGET_PER_CAMPAIGN_USD
        self.min_budget = settings.MIN_DAILY_BUDGET_PER_CAMPAIGN_USD

    def _preflight(self, campaigns: list) -> tuple[bool, str]:
        """실계정 모드에서 사이클 진입 전 안전 체크. (ok, reason) 반환"""
        if self.dry_run:
            return True, "dry_run"
        active_count = sum(1 for c in campaigns if getattr(c, "status", "") == "ACTIVE")
        if active_count > settings.MAX_ACTIVE_CAMPAIGNS:
            return False, f"active={active_count} > cap={settings.MAX_ACTIVE_CAMPAIGNS}"
        try:
            totals_1d = db.get_total_spend(days=1)
            spent = float(totals_1d.get("spend", 0))
            if spent >= settings.DAILY_BUDGET_CAP_USD:
                return False, f"24h spend=${spent:.2f} >= cap=${settings.DAILY_BUDGET_CAP_USD:.2f}"
        except Exception as e:
            logger.warning(f"Preflight spend check failed: {e}")
        return True, "ok"

    def _clamp_budget(self, v: float) -> float:
        return max(self.min_budget, min(float(v or self.min_budget), self.max_budget))

    def run_cycle(self) -> str:
        """
        전체 최적화 사이클 실행
        1. 이전 사이클 결과 분석 → 상위 N개 선별
        2. 상위 캠페인 기반 새 캠페인 생성
        3. 하위 캠페인 삭제
        Returns: cycle_id
        """
        cycle_id = f"cycle_{uuid.uuid4().hex[:8]}"
        logger.info(f"[{cycle_id}] Starting optimization cycle on {self.platform.platform_name}")

        # 사이클 문서 선행 생성 → 진행률 추적
        cycle_doc = campaign_cycle(
            cycle_id=cycle_id,
            platform=self.platform.platform_name,
            total=self.total,
            survive=0,
        )
        cycle_doc["status"] = "running"
        cycle_doc["step"] = "fetch"
        cycle_doc["step_label"] = "캠페인 목록 조회"
        cycle_doc["progress_pct"] = 5
        db.insert_cycle(cycle_doc)

        # 1. 현재 캠페인 성과 수집
        campaigns = self.platform.get_campaigns()

        # Pre-flight: 활성 수 / 일일 집행액 체크
        ok, reason = self._preflight(campaigns)
        if not ok:
            logger.warning(f"[{cycle_id}] Preflight FAILED: {reason} — aborting")
            db.update_cycle(cycle_id, {
                "status": "aborted", "step": "preflight", "step_label": f"중단: {reason}",
                "progress_pct": 0,
            })
            return cycle_id

        if not campaigns:
            logger.info(f"[{cycle_id}] No existing campaigns, starting fresh")
            return self._initial_cycle(cycle_id)

        # 2. 성과 데이터 수집
        db.update_cycle(cycle_id, {
            "step": "collect", "step_label": "성과 데이터 수집", "progress_pct": 20,
        })
        performance = self._collect_performance(campaigns)

        # 3. Claude로 점수 매기기
        db.update_cycle(cycle_id, {
            "step": "evaluate", "step_label": "Claude 평가 중", "progress_pct": 40,
        })
        survivors, losers = self._evaluate(performance)

        # 4. 사이클 DB 업데이트
        db.update_cycle(cycle_id, {
            "total": len(campaigns),
            "survive": len(survivors),
            "campaigns": [
                {"campaign_id": p["campaign_id"], "name": p.get("campaign_name", ""), "score": p.get("score", 0)}
                for p in performance
            ],
            "survivors": [s["campaign_id"] for s in survivors],
        })

        # 5. 하위 캠페인 삭제
        db.update_cycle(cycle_id, {
            "step": "kill", "step_label": f"하위 {len(losers)}개 삭제", "progress_pct": 55,
        })
        for loser in losers:
            self.platform.delete_campaign(loser["campaign_id"], dry_run=self.dry_run)
            logger.info(f"[{cycle_id}] Killed: {loser.get('campaign_name', loser['campaign_id'])} (score: {loser.get('score', 0)})")

        # 6. 상위 캠페인 기반 새 캠페인 생성
        new_count = self.total - len(survivors)
        db.update_cycle(cycle_id, {
            "step": "generate", "step_label": f"변형 {new_count}개 생성", "progress_pct": 70,
        })
        new_campaigns = self._generate_variants(survivors, new_count)

        db.update_cycle(cycle_id, {
            "step": "create", "step_label": f"플랫폼에 {len(new_campaigns)}개 등록", "progress_pct": 85,
        })
        created_ids = self._create_campaigns(new_campaigns)

        # 7. 새 캠페인 활성화 (AUTO_ACTIVATE=true일 때만; false면 PAUSED로 남겨 사람이 Meta UI에서 확인)
        if self.auto_activate or self.dry_run:
            for cid in created_ids:
                self.platform.activate_campaign(cid, dry_run=self.dry_run)
        else:
            logger.warning(
                f"[{cycle_id}] AUTO_ACTIVATE=false → {len(created_ids)}개 캠페인 PAUSED 유지. "
                "Meta UI에서 수동 활성화 필요"
            )

        # 8. 사이클 완료
        db.update_cycle(cycle_id, {
            "status": "completed",
            "step": "done",
            "step_label": "완료",
            "progress_pct": 100,
            "new_campaigns": created_ids,
        })

        logger.info(
            f"[{cycle_id}] Cycle complete: "
            f"{len(survivors)} survived, {len(losers)} killed, "
            f"{len(created_ids)} created"
        )
        return cycle_id

    def _initial_cycle(self, cycle_id: str) -> str:
        """첫 사이클 — 캠페인 0개에서 시작. 실계정 + CANARY_MODE면 소량만 생성"""
        target_count = self.total
        canary = (not self.dry_run) and settings.CANARY_MODE
        if canary:
            target_count = min(settings.CANARY_COUNT, self.total)
            logger.warning(f"[{cycle_id}] CANARY_MODE: {target_count}개만 생성")

        logger.info(f"[{cycle_id}] Generating initial {target_count} campaigns")

        db.update_cycle(cycle_id, {
            "step": "generate", "step_label": f"초기 {target_count}개 생성", "progress_pct": 30,
            "total": target_count,
        })

        variants = self.claude.generate_campaign_variants(
            survivors=[],
            count=target_count,
            market_context="Initial campaign launch for OneMessage safety messaging app",
        )

        db.update_cycle(cycle_id, {
            "step": "create", "step_label": f"플랫폼에 {len(variants)}개 등록", "progress_pct": 70,
        })
        created_ids = self._create_campaigns(variants)

        if self.auto_activate or self.dry_run:
            for cid in created_ids:
                self.platform.activate_campaign(cid, dry_run=self.dry_run)
        else:
            logger.warning(
                f"[{cycle_id}] AUTO_ACTIVATE=false → {len(created_ids)}개 PAUSED 유지 (수동 활성화 필요)"
            )

        db.update_cycle(cycle_id, {
            "status": "completed",
            "step": "done",
            "step_label": "완료" + (" (CANARY)" if canary else ""),
            "progress_pct": 100,
            "new_campaigns": created_ids,
            "canary": canary,
        })
        logger.info(f"[{cycle_id}] Initial cycle: {len(created_ids)} campaigns created")
        return cycle_id

    def _collect_performance(self, campaigns) -> list[dict]:
        """모든 캠페인의 최근 성과 수집"""
        end = date.today()
        start = end - timedelta(days=1)
        results = []
        for c in campaigns:
            try:
                perf = self.platform.get_performance(c.campaign_id, start, end)
                # 캠페인별 집계
                total = {
                    "campaign_id": c.campaign_id,
                    "campaign_name": c.campaign_name,
                    "impressions": sum(p.impressions for p in perf),
                    "clicks": sum(p.clicks for p in perf),
                    "spend": sum(p.spend for p in perf),
                    "conversions": sum(p.conversions for p in perf),
                    "revenue": sum(p.revenue for p in perf),
                }
                total["ctr"] = total["clicks"] / total["impressions"] if total["impressions"] else 0
                total["cpc"] = total["spend"] / total["clicks"] if total["clicks"] else 0
                results.append(total)

                # DB에 스냅샷 저장
                for p in perf:
                    db.insert_performance(p.to_db_dict())
            except Exception as e:
                logger.warning(f"Failed to collect performance for {c.campaign_id}: {e}")
        return results

    def _evaluate(self, performance: list[dict]) -> tuple[list[dict], list[dict]]:
        """Claude로 캠페인 점수 매기고 상위/하위 분리"""
        if not performance:
            return [], []

        scored = self.claude.score_campaigns(performance)

        # score 기준 정렬
        scored.sort(key=lambda x: x.get("score", 0), reverse=True)

        # campaign_id로 원래 데이터 매핑
        perf_map = {p["campaign_id"]: p for p in performance}
        for s in scored:
            if s["campaign_id"] in perf_map:
                s.update(perf_map[s["campaign_id"]])

        survivors = scored[:self.survive]
        losers = scored[self.survive:]

        logger.info(f"Evaluation: {len(survivors)} survivors, {len(losers)} to kill")
        for s in survivors:
            logger.info(f"  Survivor: {s.get('campaign_name', s['campaign_id'])} (score: {s.get('score', 0)})")

        return survivors, losers

    def _generate_variants(self, survivors: list[dict], count: int) -> list[dict]:
        """상위 캠페인 기반 변형 생성"""
        if count <= 0:
            return []

        # 로컬 LLM 사용 가능하면 대량 카피 생성은 로컬로
        if self.local_llm.is_available():
            logger.info(f"Using local LLM for {count} variant generation")
            try:
                return self.local_llm.generate_ad_copies(
                    {"survivors": survivors, "product": "OneMessage"},
                    count=count,
                )
            except Exception as e:
                logger.warning(f"Local LLM failed, falling back to Claude: {e}")

        # Claude fallback
        return self.claude.generate_campaign_variants(survivors, count)

    def _create_campaigns(self, variants: list[dict]) -> list[str]:
        """변형 캠페인들을 플랫폼에 생성. 예산 clamp + 연속 실패 시 중단"""
        created = []
        consecutive_failures = 0
        for v in variants:
            budget = self._clamp_budget(v.get("daily_budget", self.min_budget))
            try:
                campaign_id = self.platform.create_campaign(
                    name=v.get("name", f"OneMessage Auto {uuid.uuid4().hex[:6]}"),
                    daily_budget=budget,
                    targeting={
                        "countries": v.get("countries", ["US", "KR"]),
                        "keywords": v.get("keywords", []),
                        "age_min": v.get("age_min", 25),
                        "age_max": v.get("age_max", 55),
                    },
                    creatives={
                        "headlines": v.get("headlines", []),
                        "descriptions": v.get("descriptions", []),
                        "final_url": "https://onemsg.net",
                        "title": v.get("headlines", [""])[0] if v.get("headlines") else "",
                        "body": v.get("descriptions", [""])[0] if v.get("descriptions") else "",
                    },
                    dry_run=self.dry_run,
                )
                if campaign_id:
                    created.append(campaign_id)
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"Failed to create campaign '{v.get('name', '?')}': {e}")
            if consecutive_failures >= 3:
                logger.error(f"연속 {consecutive_failures}회 실패 — 생성 중단 (누적 방지)")
                break
        return created


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from platforms.meta import MetaAds
    mgr = CampaignManager(MetaAds())
    print(f"Dry run: {mgr.dry_run}")
    cycle_id = mgr.run_cycle()
    print(f"Cycle completed: {cycle_id}")
