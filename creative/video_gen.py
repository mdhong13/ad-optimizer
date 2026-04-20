"""
영상 생성 — Gemini API Veo 3.1.

비동기 작업 패턴:
  1. start_job(prompt, model_id) → operation_name (long-running operation)
  2. poll_job(operation_name) → {"done": bool, "video_url": ..., "error": ...}
  3. 완료 시 MP4 파일을 assets/generated/creative/video/ 에 저장

Gemini Veo API 흐름:
  POST /v1beta/models/{model}:predictLongRunning → {name, metadata}
  GET  /v1beta/{operation_name}                    → {done, response?, error?}
"""
from __future__ import annotations
import asyncio
import base64
import logging
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from config.settings import settings
from creative.models import find_video_model

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "generated" / "creative" / "video"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

API_BASE = "https://generativelanguage.googleapis.com/v1beta"


async def start_video_job(prompt: str, model_id: str, aspect_ratio: str = "9:16", duration_seconds: int = 8) -> dict:
    """
    Veo 비동기 작업 시작.
    반환: {"operation_name": ..., "model": ..., "prompt": ..., "submitted_at": iso}
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 미설정")

    model = find_video_model(model_id)
    model_name = model["model"]

    url = f"{API_BASE}/models/{model_name}:predictLongRunning?key={settings.GEMINI_API_KEY}"
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "aspectRatio": aspect_ratio,
            "durationSeconds": int(duration_seconds),
            "personGeneration": "allow_adult",
        },
    }

    log.info("[creative.video] start model=%s ar=%s dur=%ss", model_name, aspect_ratio, duration_seconds)
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 400:
            body = r.text[:800]
            log.error("[creative.video] start failed %s: %s", r.status_code, body)
            raise RuntimeError(f"Veo {r.status_code}: {body}")
        data = r.json()

    op_name = data.get("name")
    if not op_name:
        raise RuntimeError(f"Veo: operation name 없음. 응답: {data}")

    return {
        "operation_name": op_name,
        "model": model_name,
        "model_id": model["id"],
        "prompt": prompt,
        "aspect_ratio": aspect_ratio,
        "duration_seconds": duration_seconds,
        "submitted_at": datetime.now().isoformat(),
    }


async def poll_video_job(operation_name: str) -> dict:
    """
    Veo 작업 상태 폴링.
    반환:
      {"done": False, "progress": "running"}
      {"done": True,  "video_urls": [...], "video_paths": [...], "model_name": ...}
      {"done": True,  "error": "..."}
    """
    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY 미설정")

    url = f"{API_BASE}/{operation_name}?key={settings.GEMINI_API_KEY}"
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        data = r.json()

    if not data.get("done"):
        return {"done": False, "progress": "running", "raw": data.get("metadata", {})}

    if "error" in data:
        err = data["error"]
        msg = err.get("message") if isinstance(err, dict) else str(err)
        return {"done": True, "error": msg}

    # done=true & success → response 안에 비디오 바이트 또는 URI
    response = data.get("response", {})
    # Veo 응답 포맷: response.generateVideoResponse.generatedSamples[*].video.{uri|bytesBase64Encoded}
    samples = (
        response.get("generateVideoResponse", {}).get("generatedSamples")
        or response.get("generatedSamples")
        or []
    )

    saved_paths = []
    saved_urls = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    async with httpx.AsyncClient(timeout=300.0) as client:
        for i, s in enumerate(samples):
            vid = s.get("video", {})
            uri = vid.get("uri") or vid.get("videoUri")
            b64 = vid.get("bytesBase64Encoded") or vid.get("bytesBase64")
            uid = uuid.uuid4().hex[:8]
            fname = f"{ts}_veo_{i}_{uid}.mp4"
            fpath = OUTPUT_DIR / fname
            if b64:
                fpath.write_bytes(base64.b64decode(b64))
            elif uri:
                # Gemini 파일 다운로드 (key 파라미터 필요)
                dl_url = uri if uri.startswith("http") else f"{API_BASE}/{uri}"
                sep = "&" if "?" in dl_url else "?"
                dl_url = f"{dl_url}{sep}key={settings.GEMINI_API_KEY}"
                rr = await client.get(dl_url)
                rr.raise_for_status()
                fpath.write_bytes(rr.content)
            else:
                log.warning("[creative.video] sample %d 비디오 데이터 없음: %s", i, str(s)[:300])
                continue
            saved_paths.append(str(fpath))
            saved_urls.append(f"/assets/generated/creative/video/{fname}")

    return {
        "done": True,
        "video_urls": saved_urls,
        "video_paths": saved_paths,
        "sample_count": len(saved_paths),
    }


async def wait_for_video(operation_name: str, poll_interval: float = 10.0, max_wait: float = 600.0) -> dict:
    """서버 사이드에서 완료까지 대기 (기본 최대 10분)."""
    elapsed = 0.0
    while elapsed < max_wait:
        status = await poll_video_job(operation_name)
        if status.get("done"):
            return status
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
    return {"done": False, "error": "timeout", "elapsed_seconds": elapsed}
