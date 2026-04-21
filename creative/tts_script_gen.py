"""
스토리 → N샷 TTS 대사 라인 (KR 또는 EN).

각 라인은 8초 샷에 맞춘 voiceover 길이. 생성된 라인은 UI 에서 사용자가
수동으로 다듬을 수 있도록 그대로 노출.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Literal

from creative.copy_gen import _extract_json, call_llm_text

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "tts_script_gen.txt"


def _load_system() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _user_message(story: str, n_shots: int, language: str) -> str:
    lang_label = "Korean (한국어)" if language == "kr" else "English"
    return (
        f"Story / scene context:\n{story.strip()}\n\n"
        f"Number of 8-second shots (= N voiceover lines needed): {n_shots}\n"
        f"Output language: {lang_label}\n\n"
        f"Produce EXACTLY {n_shots} voiceover line(s) following all rules. Return JSON only."
    )


async def generate_script(
    story: str,
    n_shots: int = 3,
    language: Literal["kr", "en"] = "en",
    provider_id: str = "claude-sonnet",
) -> dict:
    """
    반환: {"lines": [str,...], "_meta": {provider, model, language, n_shots}}
    """
    story = (story or "").strip()
    if not story:
        raise ValueError("story 필수")
    n_shots = max(1, min(int(n_shots), 3))
    if language not in ("kr", "en"):
        language = "en"

    system = _load_system()
    user = _user_message(story, n_shots, language)
    result = await call_llm_text(provider_id, system, user)
    raw = result["text"]

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as e:
        log.error("[tts_script] JSON parse failed: %s\nraw=%s", e, raw[:500])
        raise

    lines = parsed.get("lines") or []
    if not isinstance(lines, list):
        lines = []
    lines = [str(l).strip() for l in lines if str(l).strip()]
    # 강제 N 길이 맞추기 (부족하면 빈 문자열 패딩해서 UI 에서 편집 가능하게)
    while len(lines) < n_shots:
        lines.append("")
    lines = lines[:n_shots]

    return {
        "lines": lines,
        "_meta": {
            "provider": result["provider"],
            "model": result["model"],
            "provider_id": result["provider_id"],
            "language": language,
            "n_shots": n_shots,
        },
    }
