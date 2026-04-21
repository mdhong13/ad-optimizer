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


def _user_message(
    brief_text: str,
    aspect_ratio: str,
    n: int,
    target: str,
    phone_screen_text: str = "",
    must_show: str = "",
    screen_text_language: str = "en",
) -> str:
    ar_note = f"Aspect ratio: {aspect_ratio}." if aspect_ratio else ""

    phone_screen_text = (phone_screen_text or "").strip()
    must_show = (must_show or "").strip()
    lang = (screen_text_language or "en").lower()

    # 기본: 화면/간판 blank — 단, 사용자가 phone_screen_text 를 명시했다면 해당 디바이스
    # 화면만 legible 하게 렌더하되, 배경의 다른 스크린/간판은 여전히 blank.
    if phone_screen_text:
        if lang == "kr":
            script_clause = (
                "The phone/device screen text must be rendered LEGIBLY in KOREAN (hangul). "
                "Hangul is ALLOWED inside this specific device screen only. "
                "All OTHER background signage, labels, and incidental screens must remain blank, "
                "abstract, out-of-focus, or English-only — no non-Latin script anywhere else."
            )
        else:
            script_clause = (
                "The phone/device screen text must be rendered LEGIBLY in ENGLISH only. "
                "NO hangul, hanzi, or kana anywhere in the frame — not on the device, not in background signage."
            )
        legibility_block = (
            "CRITICAL SCENE REQUIREMENT — PHONE/DEVICE SCREEN LEGIBILITY EXCEPTION:\n"
            "The scene MUST feature a device screen (smartphone, tablet, or similar) positioned so the screen is "
            "clearly visible to camera. That screen MUST render the following text legibly, composed as a natural-looking "
            "messaging/notes UI (plain white or soft dark chat/notes interface, no brand marks, no app logos, "
            "no cryptocurrency iconography, no ₿ symbol):\n"
            f"---\n{phone_screen_text}\n---\n"
            f"{script_clause}\n"
            "This exception applies ONLY to this ONE specific device screen. The composition must frame the device "
            "so the screen text is readable (tight over-the-shoulder, close-up of hand holding phone, or macro on device).\n"
        )
    else:
        legibility_block = ""

    if must_show:
        must_show_block = (
            "ADDITIONAL SCENE REQUIREMENTS — the following elements MUST be visually present in the frame "
            "(as props, wardrobe, setting details — NOT as on-screen text):\n"
            f"{must_show}\n"
        )
    else:
        must_show_block = ""

    # 기본 스크립트 가드. phone_screen_text 이 있을 때는 위에서 예외를 걸었으므로,
    # 여기서는 일반적인 "no on-screen text / no non-Latin script" 규칙만 유지.
    if phone_screen_text:
        language_guard = (
            "GENERAL SCRIPT RULE — The entire prompt MUST be in English. "
            "Apart from the SINGLE device screen covered by the LEGIBILITY EXCEPTION above, "
            "ALL other signs, labels, packaging, background screens, and UI elements in the scene "
            "must be blank, abstract, out-of-focus, or in natural-looking English only. "
            "NO logos, NO brand marks, NO cryptocurrency iconography anywhere."
        )
    else:
        language_guard = (
            "CRITICAL SCRIPT RULE — The entire prompt MUST be in English. "
            "Even if the user brief is written in Korean, rewrite all described content in English. "
            "ANY device screens, signs, labels, packaging, or UI elements visible in the scene MUST be blank, "
            "abstract, out-of-focus, or in natural-looking English only. "
            "ABSOLUTELY NO on-screen text in Korean (hangul), Chinese (hanzi), or Japanese (kanji/kana). "
            "If a phone is shown, its screen must either be completely blank, show abstract glow/UI shapes, "
            "or be angled so the screen contents are not legible."
        )

    return (
        f"User brief:\n{brief_text.strip()}\n\n"
        f"{ar_note}\n"
        f"{legibility_block}"
        f"{must_show_block}"
        f"{language_guard}\n"
        f"Produce {n} clearly distinct {target} prompt(s). Return JSON only as specified."
    )


async def generate_prompts(
    target: Literal["image", "video"],
    brief_text: str,
    aspect_ratio: str = "",
    n: int = 2,
    provider_id: str = "claude-sonnet",
    phone_screen_text: str = "",
    must_show: str = "",
    screen_text_language: str = "en",
) -> dict:
    """
    반환: {"prompts": [str, ...], "_meta": {provider, model, target}}

    phone_screen_text: 프레임 안 디바이스 화면에 legibly 표시할 텍스트(있으면).
    must_show: 프레임에 반드시 포함될 소품/배경 요소 설명.
    screen_text_language: "en" | "kr" — 디바이스 화면 텍스트 언어(기본 en).
    """
    if target not in ("image", "video"):
        raise ValueError("target must be 'image' or 'video'")
    if not brief_text.strip():
        raise ValueError("brief_text 필수")
    n = max(1, min(int(n), 5))

    system = _load_system(target)
    user = _user_message(
        brief_text, aspect_ratio, n, target,
        phone_screen_text=phone_screen_text,
        must_show=must_show,
        screen_text_language=screen_text_language,
    )
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
