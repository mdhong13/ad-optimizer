"""
이미지 생성 — Gemini API (Nano Banana Pro 등).

원칙: 항상 최상위 모델 사용. 모델 ID는 models.py 레지스트리에서 선택.
생성 결과는 assets/generated/creative/image/ 에 PNG로 저장.
"""
from __future__ import annotations
import base64
import logging
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from config.settings import settings
from creative.models import find_image_model

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "generated" / "creative" / "image"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def generate_image(prompt: str, model_id: str, aspect_ratio: str = "4:5", n: int = 1) -> list[dict]:
    """
    Nano Banana / Gemini image 계열 호출.

    aspect_ratio: "1:1" | "4:5" | "9:16" | "16:9" | "3:4" | "2:3"
    반환: [{"path": "<abs path>", "url": "/assets/...", "model": ..., "prompt": ...}]
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 미설정")

    model = find_image_model(model_id)
    model_name = model["model"]

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={settings.GEMINI_API_KEY}"
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect_ratio},
            "candidateCount": max(1, min(int(n), 4)),
        },
    }

    log.info("[creative.image] model=%s ar=%s n=%s", model_name, aspect_ratio, n)
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 400:
            log.error("[creative.image] %s %s", r.status_code, r.text[:500])
            r.raise_for_status()
        data = r.json()

    results = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, cand in enumerate(data.get("candidates", [])):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if not inline:
                continue
            b64 = inline.get("data")
            mime = inline.get("mimeType") or inline.get("mime_type") or "image/png"
            ext = "png" if "png" in mime else ("jpg" if "jpeg" in mime or "jpg" in mime else "bin")
            uid = uuid.uuid4().hex[:8]
            fname = f"{ts}_{model['id']}_{aspect_ratio.replace(':','x')}_{i}_{uid}.{ext}"
            fpath = OUTPUT_DIR / fname
            fpath.write_bytes(base64.b64decode(b64))
            results.append({
                "path": str(fpath),
                "url": f"/assets/generated/creative/image/{fname}",
                "model": model_name,
                "model_id": model["id"],
                "aspect_ratio": aspect_ratio,
                "prompt": prompt,
            })

    if not results:
        log.warning("[creative.image] no image parts in response: %s", str(data)[:500])
    return results
