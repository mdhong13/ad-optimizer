"""
스토리 → 씬 앵커(Character + Setting) JSON 추출.

3샷 일관성의 Layer 1: 모든 샷 프롬프트에 동일하게 주입될 '고정 블록' 을
LLM 이 스토리에서 뽑아낸다. UI 에서 사용자가 수동으로 다듬을 수 있도록
구조화된 JSON 으로 반환.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path

from creative.copy_gen import _extract_json, call_llm_text

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "anchor_extract.txt"


def _load_system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _user_message(story: str) -> str:
    return (
        f"Story / scene:\n{story.strip()}\n\n"
        "Extract the visual anchor. Return JSON only following the exact shape."
    )


def _clean_anchor(obj: dict) -> dict:
    """LLM 이 돌려준 앵커를 정규화 — 누락 키는 빈 문자열로 채움."""
    c = (obj.get("character") or {}) if isinstance(obj, dict) else {}
    s = (obj.get("setting") or {}) if isinstance(obj, dict) else {}
    CHAR_KEYS = ("identity", "hair", "face_marks", "hands", "wardrobe", "distinctive_prop")
    SET_KEYS = ("location", "palette", "lighting", "lens", "time_weather")
    return {
        "character": {k: str(c.get(k, "") or "").strip() for k in CHAR_KEYS},
        "setting": {k: str(s.get(k, "") or "").strip() for k in SET_KEYS},
    }


async def extract_anchor(story: str, provider_id: str = "claude-sonnet") -> dict:
    """
    반환: {"anchor": {character, setting}, "_meta": {provider, model, provider_id}}
    """
    story = (story or "").strip()
    if not story:
        raise ValueError("story 필수")

    system = _load_system()
    user = _user_message(story)
    result = await call_llm_text(provider_id, system, user)
    raw = result["text"]

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as e:
        log.error("[anchor_gen] JSON parse failed: %s\nraw=%s", e, raw[:1000])
        snippet = raw[:300].replace("\n", " ")
        raise ValueError(f"LLM JSON 파싱 실패 ({e.msg} @ line {e.lineno} col {e.colno}). raw: {snippet!r}") from e

    anchor = _clean_anchor(parsed)
    return {
        "anchor": anchor,
        "_meta": {
            "provider": result["provider"],
            "model": result["model"],
            "provider_id": result["provider_id"],
        },
    }
