"""
Claude LLM 에이전트 - 광고 최적화 결정
"""
import json
import logging
from pathlib import Path
from datetime import datetime

import anthropic

from config.settings import settings

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_claude(system_prompt: str, user_message: str) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    message = client.messages.create(
        model=settings.AGENT_MODEL,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


def _parse_decisions(raw: str, task_type: str, dry_run: bool) -> list[dict]:
    """에이전트 응답에서 JSON 결정 목록 파싱"""
    raw = raw.strip()
    # 코드 블록 제거
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])

    decisions = json.loads(raw)
    result = []
    for d in decisions:
        change_pct = float(d.get("change_pct", 0))
        clamped = False

        # 예산 변경 안전장치
        if abs(change_pct) > settings.BUDGET_CHANGE_LIMIT_PCT:
            original_pct = change_pct
            change_pct = settings.BUDGET_CHANGE_LIMIT_PCT * (1 if change_pct > 0 else -1)
            clamped = True
            logger.warning(
                f"Budget change clamped: {original_pct:.1f}% → {change_pct:.1f}%"
            )

        result.append({
            "task_type": task_type,
            "platform": d.get("platform", ""),
            "campaign_id": d.get("target_id", ""),
            "action": d.get("action", ""),
            "target_id": d.get("target_id", ""),
            "current_value": str(d.get("current_value", "")),
            "new_value": str(d.get("new_value", "")),
            "change_pct": change_pct,
            "reason": d.get("reason", ""),
            "context": json.dumps({
                "target_name": d.get("target_name", ""),
                "target_type": d.get("target_type", ""),
                "clamped": clamped,
                "urgency": d.get("urgency", "normal"),
                "expires_hours": d.get("expires_hours"),
            }, ensure_ascii=False),
            "status": "pending",
            "dry_run": 1 if dry_run else 0,
        })
    return result


def run_budget_optimization(
    performance_data: list[dict],
    market_context: dict,
    recent_events: list[dict],
    dry_run: bool = None,
) -> list[dict]:
    """
    일간 예산 최적화 실행
    Returns: 결정 목록 (DB 저장 전)
    """
    if dry_run is None:
        dry_run = settings.DRY_RUN

    logger.info("Running budget optimization agent")

    template = _load_prompt("budget_optimizer.md")
    prompt = template.replace("{performance_data}", json.dumps(performance_data, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{market_context}", json.dumps(market_context, ensure_ascii=False, indent=2))

    events_text = "\n".join(
        f"- [{e.get('event_type')}] {e.get('title')} ({e.get('created_at', '')})"
        for e in recent_events[:10]
    )
    prompt = prompt.replace("{recent_events}", events_text or "최근 이벤트 없음")

    system = (
        "당신은 OneMessage 앱의 광고 최적화 전문가입니다. "
        "크립토 시장 이벤트에 민감하게 반응하며, 데이터 기반의 정확한 결정을 내립니다. "
        "반드시 유효한 JSON 배열만 반환하세요."
    )

    try:
        raw = _call_claude(system, prompt)
        decisions = _parse_decisions(raw, "budget_optimization", dry_run)
        logger.info(f"Budget optimization: {len(decisions)} decisions generated")
        return decisions
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response: {e}\nRaw: {raw[:500]}")
        return []
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        return []


def run_market_event_response(
    triggered_event: dict,
    campaign_status: list[dict],
    dry_run: bool = None,
) -> list[dict]:
    """
    시장 이벤트 긴급 대응 에이전트
    """
    if dry_run is None:
        dry_run = settings.DRY_RUN

    logger.info(f"Running market event response: {triggered_event.get('event_type')}")

    template = _load_prompt("market_event_responder.md")
    prompt = template.replace("{triggered_event}", json.dumps(triggered_event, ensure_ascii=False, indent=2))
    prompt = prompt.replace("{campaign_status}", json.dumps(campaign_status, ensure_ascii=False, indent=2))

    system = (
        "당신은 OneMessage 앱의 긴급 광고 대응 전문가입니다. "
        "크립토 시장 이벤트 발생 시 즉각적이고 공격적인 대응 결정을 내립니다. "
        "반드시 유효한 JSON 배열만 반환하세요."
    )

    try:
        raw = _call_claude(system, prompt)
        decisions = _parse_decisions(raw, "event_response", dry_run)
        logger.info(f"Event response: {len(decisions)} decisions generated")
        return decisions
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse agent response: {e}")
        return []
    except Exception as e:
        logger.error(f"Agent error: {e}", exc_info=True)
        return []
