"""
생성 모델 레지스트리.

이미지·영상은 "항상 최상위 모델" 원칙 — DEFAULT는 현 시점 최상위.
Gemini `/v1beta/models` 조회로 확인된 실제 ID만 사용 (2026-04 기준).
"""
from __future__ import annotations
from dataclasses import dataclass


# --- Copy (LLM providers) ---
COPY_PROVIDERS = [
    {"id": "claude-opus", "label": "Claude Opus 4.7 (최상)", "model": "claude-opus-4-7", "provider": "anthropic"},
    {"id": "claude-sonnet", "label": "Claude Sonnet 4.6 (권장)", "model": "claude-sonnet-4-6", "provider": "anthropic"},
    {"id": "gpt-4o", "label": "GPT-4o", "model": "gpt-4o", "provider": "openai"},
    {"id": "gemini-pro", "label": "Gemini 3 Pro", "model": "gemini-pro-latest", "provider": "gemini"},
    {"id": "gemini-flash", "label": "Gemini Flash (저렴)", "model": "gemini-flash-latest", "provider": "gemini"},
    {"id": "local-vllm", "label": "Local vLLM (d4win, 무료)", "model": "auto", "provider": "local"},
]
COPY_DEFAULT_ID = "claude-sonnet"


# --- Image (Gemini API, 항상 최상위) ---
IMAGE_MODELS = [
    {"id": "nano-banana-pro", "label": "Nano Banana Pro (최상)", "model": "nano-banana-pro-preview"},
    {"id": "gemini-3-pro-image", "label": "Gemini 3 Pro Image (멀티모달 최상)", "model": "gemini-3-pro-image-preview"},
    {"id": "gemini-3.1-flash-image", "label": "Gemini 3.1 Flash Image", "model": "gemini-3.1-flash-image-preview"},
    {"id": "imagen-4-ultra", "label": "Imagen 4 Ultra", "model": "imagen-4.0-ultra-generate-001"},
    {"id": "gemini-2.5-flash-image", "label": "Nano Banana 1 (안정)", "model": "gemini-2.5-flash-image"},
]
IMAGE_DEFAULT_ID = "nano-banana-pro"


# --- Video (Gemini API Veo, 항상 최상위) ---
VIDEO_MODELS = [
    {"id": "veo-3.1", "label": "Veo 3.1 (최상)", "model": "veo-3.1-generate-preview"},
    {"id": "veo-3.1-fast", "label": "Veo 3.1 Fast", "model": "veo-3.1-fast-generate-preview"},
    {"id": "veo-3.1-lite", "label": "Veo 3.1 Lite (저렴)", "model": "veo-3.1-lite-generate-preview"},
    {"id": "veo-3.0", "label": "Veo 3.0 (안정)", "model": "veo-3.0-generate-001"},
]
VIDEO_DEFAULT_ID = "veo-3.1"


def find_copy_provider(provider_id: str) -> dict:
    for p in COPY_PROVIDERS:
        if p["id"] == provider_id:
            return p
    return next(p for p in COPY_PROVIDERS if p["id"] == COPY_DEFAULT_ID)


def find_image_model(model_id: str) -> dict:
    for m in IMAGE_MODELS:
        if m["id"] == model_id:
            return m
    return next(m for m in IMAGE_MODELS if m["id"] == IMAGE_DEFAULT_ID)


def find_video_model(model_id: str) -> dict:
    for m in VIDEO_MODELS:
        if m["id"] == model_id:
            return m
    return next(m for m in VIDEO_MODELS if m["id"] == VIDEO_DEFAULT_ID)
