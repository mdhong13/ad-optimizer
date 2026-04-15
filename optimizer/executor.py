"""
에이전트 결정 → 실제 광고 플랫폼 API 호출
"""
import logging

from config.settings import settings
from platforms.meta import MetaAds
from platforms.google_ads import GoogleAds
from storage.db import update_decision_status

logger = logging.getLogger(__name__)

_meta = MetaAds()
_google = GoogleAds()

PLATFORM_MAP = {
    "meta": _meta,
    "google": _google,
}


def execute_decision(decision: dict) -> bool:
    """
    단일 결정 실행
    Returns: 성공 여부
    """
    dry_run = bool(decision.get("dry_run", 1))
    action = decision.get("action", "")
    platform_name = decision.get("platform", "")
    target_id = decision.get("target_id", "")
    decision_id = decision.get("id")

    if action == "no_action":
        if decision_id:
            update_decision_status(decision_id, "executed")
        return True

    platform = PLATFORM_MAP.get(platform_name)
    if not platform:
        logger.error(f"Unknown platform: {platform_name}")
        if decision_id:
            update_decision_status(decision_id, "rejected")
        return False

    try:
        success = _dispatch_action(platform, action, target_id, decision, dry_run)
        if decision_id:
            update_decision_status(decision_id, "executed" if success else "rejected")
        return success
    except Exception as e:
        logger.error(f"Execution error for decision {decision_id}: {e}", exc_info=True)
        if decision_id:
            update_decision_status(decision_id, "rejected")
        return False


def _dispatch_action(platform, action: str, target_id: str, decision: dict, dry_run: bool) -> bool:
    new_value_str = decision.get("new_value", "")

    if action == "increase_budget" or action == "decrease_budget":
        new_budget = _parse_dollar_value(new_value_str)
        if new_budget is None:
            logger.error(f"Cannot parse budget value: {new_value_str}")
            return False
        return platform.update_campaign_budget(target_id, new_budget, dry_run=dry_run)

    elif action == "pause_campaign":
        return platform.pause_campaign(target_id, dry_run=dry_run)

    elif action == "activate_campaign":
        return platform.activate_campaign(target_id, dry_run=dry_run)

    elif action in ("increase_bid", "decrease_bid"):
        new_bid = _parse_dollar_value(new_value_str)
        if new_bid is None:
            logger.error(f"Cannot parse bid value: {new_value_str}")
            return False
        return platform.update_ad_set_bid(target_id, new_bid, dry_run=dry_run)

    else:
        logger.warning(f"Unknown action: {action}")
        return False


def _parse_dollar_value(value_str: str) -> float | None:
    """'$50/day', '$0.5 CPC', '50.0' 등에서 숫자 추출"""
    import re
    match = re.search(r"[\d.]+", str(value_str).replace(",", ""))
    return float(match.group()) if match else None


def execute_all_pending(decisions: list[dict]) -> dict:
    """
    대기 중인 모든 결정 실행
    Returns: {'executed': N, 'failed': N}
    """
    executed = 0
    failed = 0
    for d in decisions:
        if execute_decision(d):
            executed += 1
        else:
            failed += 1
    logger.info(f"Execution complete: {executed} executed, {failed} failed")
    return {"executed": executed, "failed": failed}
