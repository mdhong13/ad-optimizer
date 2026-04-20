"""
카피 생성 — provider 라우터 (Anthropic / OpenAI / Gemini / Local vLLM).

바이링규얼 페어링 원칙: 번역 금지, 각 언어 독립 작성.
시스템 프롬프트는 prompts/copy_bilingual.txt 에서 로드.
"""
from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

import httpx

from config.settings import settings
from creative.models import find_copy_provider

log = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "copy_bilingual.txt"


def _system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _user_message(brief: dict) -> str:
    """사용자 입력(브리프 + 스토리) → LLM user turn 메시지 구성."""
    campaign = brief.get("campaign", "unspecified")
    angle = brief.get("angle", "any")
    platform = brief.get("platform", "meta_feed")
    n_variants = int(brief.get("n_variants", 3))
    tone = brief.get("tone", "reassurance")
    audience = brief.get("audience", "general")
    # 'story' 가 메인 입력. 하위호환: 'extra_instructions' 도 허용.
    story = (brief.get("story") or brief.get("extra_instructions") or "").strip()

    lines = []
    if story:
        lines.append("# Story / Scene (primary — all variants must express this scene's emotional beat, tone, and setting)")
        lines.append(story)
        lines.append("")
    lines.extend([
        f"Campaign: {campaign}",
        f"Angle preference: {angle}",
        f"Platform: {platform}",
        f"Tone: {tone}",
        f"Audience: {audience}",
        f"Generate {n_variants} variants. All variants share the story above but test DIFFERENT headlines/hypotheses (different number anchors, emotional beats, or entry hooks). Return JSON only.",
    ])
    return "\n".join(lines)


def _extract_json(raw: str) -> dict:
    """LLM 응답에서 JSON 추출 (markdown fence 제거 포함)."""
    s = raw.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else s
        if s.endswith("```"):
            s = s[:-3]
        # ```json ... ``` 대응
        if s.startswith("json\n"):
            s = s[5:]
    # 첫 '{' 부터 마지막 '}' 까지 보정
    l = s.find("{")
    r = s.rfind("}")
    if l >= 0 and r > l:
        s = s[l : r + 1]
    return json.loads(s)


async def _call_anthropic(model: str, system: str, user: str) -> str:
    if not settings.ANTHROPIC_API_KEY:
        raise RuntimeError("ANTHROPIC_API_KEY 미설정")
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": 4096,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")


async def _call_openai(model: str, system: str, user: str) -> str:
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY 미설정")
    headers = {
        "Authorization": f"Bearer {settings.OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]


async def _call_gemini(model: str, system: str, user: str) -> str:
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 미설정")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": user}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.9},
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()
    cand = data.get("candidates", [{}])[0]
    parts = cand.get("content", {}).get("parts", [])
    return "".join(p.get("text", "") for p in parts)


async def _call_local_vllm(system: str, user: str) -> str:
    base = settings.LOCAL_LLM_BASE_URL.rstrip("/")
    # 모델 자동 감지
    async with httpx.AsyncClient(timeout=10.0) as client:
        rm = await client.get(f"{base}{settings.LOCAL_LLM_MODELS_ENDPOINT}")
        rm.raise_for_status()
        models = rm.json().get("data", [])
        if not models:
            raise RuntimeError("Local vLLM: 로드된 모델 없음")
        model = models[0].get("id")
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.9,
        "max_tokens": 3000,
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        r = await client.post(f"{base}{settings.LOCAL_LLM_CHAT_ENDPOINT}", json=payload)
        r.raise_for_status()
        data = r.json()
    return data["choices"][0]["message"]["content"]


async def call_llm_text(provider_id: str, system: str, user: str) -> dict:
    """
    텍스트-only LLM 호출 라우터 (JSON 강제 없음).
    반환: {"text": str, "provider": ..., "model": ..., "provider_id": ...}
    """
    provider = find_copy_provider(provider_id)
    log.info("[creative.llm] provider=%s model=%s", provider["provider"], provider["model"])
    if provider["provider"] == "anthropic":
        text = await _call_anthropic(provider["model"], system, user)
    elif provider["provider"] == "openai":
        text = await _call_openai(provider["model"], system, user)
    elif provider["provider"] == "gemini":
        text = await _call_gemini(provider["model"], system, user)
    elif provider["provider"] == "local":
        text = await _call_local_vllm(system, user)
    else:
        raise ValueError(f"Unknown provider: {provider['provider']}")
    return {"text": text, "provider": provider["provider"], "model": provider["model"], "provider_id": provider["id"]}


async def generate_copy(brief: dict, provider_id: str) -> dict:
    """
    브리프 → LLM 호출 → JSON 파싱.

    반환: {"variants": [...], "_meta": {"provider": ..., "model": ...}}
    """
    system = _system_prompt()
    user = _user_message(brief)
    result = await call_llm_text(provider_id, system, user)
    raw = result["text"]

    try:
        parsed = _extract_json(raw)
    except json.JSONDecodeError as e:
        log.error("[creative.copy] JSON parse failed: %s\nraw=%s", e, raw[:500])
        raise
    parsed["_meta"] = {"provider": result["provider"], "model": result["model"], "provider_id": result["provider_id"]}
    return parsed
