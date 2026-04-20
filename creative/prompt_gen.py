"""
영문 이미지·영상 프롬프트 생성기.

카피와 별개로, 사용자가 자유 입력한 브리프 → LLM → 여러 개의 매우 상세한
영문 프롬프트 (image 또는 video). 생성된 프롬프트는 이미지/영상 생성
페이지에 바로 전달(handoff)하여 재사용.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Literal

from creative.copy_gen import _extract_json, call_llm_text

log = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / "prompts"


def _load_system(target: str) -> str:
    fname = "image_prompt_gen.txt" if target == "image" else "video_prompt_gen.txt"
    return (PROMPT_DIR / fname).read_text(encoding="utf-8")


def _user_message(brief_text: str, aspect_ratio: str, n: int, target: str) -> str:
    ar_note = f"Aspect ratio: {aspect_ratio}." if aspect_ratio else ""
    return (
        f"User brief:\n{brief_text.strip()}\n\n"
        f"{ar_note}\n"
        f"Produce {n} clearly distinct {target} prompt(s). Return JSON only as specified."
    )


async def generate_prompts(
    target: Literal["image", "video"],
    brief_text: str,
    aspect_ratio: str = "",
    n: int = 2,
    provider_id: str = "claude-sonnet",
) -> dict:
    """
    반환: {"prompts": [str, ...], "_meta": {provider, model, target}}
    """
    if target not in ("image", "video"):
        raise ValueError("target must be 'image' or 'video'")
    if not brief_text.strip():
        raise ValueError("brief_text 필수")
    n = max(1, min(int(n), 5))

    system = _load_system(target)
    user = _user_message(brief_text, aspect_ratio, n, target)
    result = await call_llm_text(provider_id, system, user)
    raw = result["text"]

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as e:
        log.error("[creative.prompt_gen] JSON parse failed: %s\nraw=%s", e, raw[:500])
        raise

    prompts = parsed.get("prompts") or []
    if not isinstance(prompts, list):
        prompts = []
    # 모든 항목을 str 로 정규화
    prompts = [str(p).strip() for p in prompts if str(p).strip()]

    return {
        "prompts": prompts,
        "_meta": {
            "provider": result["provider"],
            "model": result["model"],
            "provider_id": result["provider_id"],
            "target": target,
        },
    }
