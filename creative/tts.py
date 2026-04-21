"""
TTS 합성 — ElevenLabs / Typecast 통합.

합성 결과 MP3 는 assets/generated/creative/tts/ 에 저장, `/assets/...` URL 반환.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from pathlib import Path

import httpx

from config.settings import settings
from creative.voices import find_preset

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BASE_DIR / "assets" / "generated" / "creative" / "tts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_mp3(content: bytes, preset_id: str) -> tuple[str, str]:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    uid = uuid.uuid4().hex[:8]
    fname = f"{ts}_{preset_id}_{uid}.mp3"
    fpath = OUTPUT_DIR / fname
    fpath.write_bytes(content)
    return str(fpath), f"/assets/generated/creative/tts/{fname}"


async def _synth_elevenlabs(voice_id: str, text: str, settings_: dict) -> bytes:
    if not settings.ELEVENLABS_API_KEY:
        raise RuntimeError("ELEVENLABS_API_KEY 미설정")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    payload = {
        "text": text,
        "model_id": settings_.get("model_id", "eleven_multilingual_v2"),
        "voice_settings": {
            "stability": float(settings_.get("stability", 0.5)),
            "similarity_boost": float(settings_.get("similarity_boost", 0.75)),
            "style": float(settings_.get("style", 0.0)),
            "use_speaker_boost": True,
        },
    }
    headers = {"xi-api-key": settings.ELEVENLABS_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            body = r.text[:500]
            log.error("[tts.elevenlabs] %s: %s", r.status_code, body)
            raise RuntimeError(f"ElevenLabs {r.status_code}: {body}")
        return r.content


async def _synth_typecast(voice_id: str, text: str, settings_: dict) -> bytes:
    """Typecast speak v2 — polling 방식.

    POST https://api.typecast.ai/v1/text-to-speech
      body: {"voice_id": ..., "text": ..., "language": "kor"|"eng", ...}
    동기 바이트 응답 (audio/mpeg) 또는 speak_v2_url polling.
    """
    if not settings.TYPECAST_API_KEY:
        raise RuntimeError("TYPECAST_API_KEY 미설정")
    # voice_id 는 "tc_" prefix 포함해서 저장. API 호출 시 prefix 제거.
    vid = voice_id[3:] if voice_id.startswith("tc_") else voice_id
    url = "https://api.typecast.ai/v1/text-to-speech"
    payload = {
        "voice_id": vid,
        "text": text,
        "model": settings_.get("model", "ssfm-v21"),
        "language": settings_.get("language", "kor"),
        "prompt": {
            "emotion_preset": settings_.get("emotion", "normal"),
            "emotion_intensity": float(settings_.get("emotion_intensity", 1.0)),
        },
        "output": {"volume": 100, "audio_pitch": 0, "audio_tempo": 1.0,
                   "audio_format": "mp3"},
        "seed": 0,
    }
    headers = {"X-API-KEY": settings.TYPECAST_API_KEY, "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload, headers=headers)
        if r.status_code >= 400:
            body = r.text[:500]
            log.error("[tts.typecast] %s: %s", r.status_code, body)
            raise RuntimeError(f"Typecast {r.status_code}: {body}")
        # 응답이 바로 MP3 바이트이거나, JSON 으로 audio_download_url 을 돌려줄 수 있음
        ctype = r.headers.get("content-type", "")
        if "audio" in ctype:
            return r.content
        data = r.json()
        dl = data.get("audio_download_url") or data.get("url") or (data.get("audio") or {}).get("url")
        if not dl:
            raise RuntimeError(f"Typecast 응답에 audio URL 없음: {str(data)[:300]}")
        rr = await client.get(dl)
        rr.raise_for_status()
        return rr.content


async def synthesize(preset_id: str, text: str, options: dict | None = None) -> dict:
    """프리셋으로 TTS 합성 → MP3 저장 후 path/url 반환."""
    text = (text or "").strip()
    if not text:
        raise ValueError("text 필수")
    preset = find_preset(preset_id)
    if not preset:
        raise ValueError(f"preset '{preset_id}' 없음")
    opts = options or {}
    provider = preset["provider"]
    voice_id = preset["voice_id"]
    if provider == "elevenlabs":
        audio = await _synth_elevenlabs(voice_id, text, opts)
    elif provider == "typecast":
        # 언어 힌트: preset id 에 _kr_ 포함되면 kor, 아니면 eng
        opts = {**opts, "language": "kor" if "_kr_" in preset_id else "eng"}
        audio = await _synth_typecast(voice_id, text, opts)
    else:
        raise ValueError(f"unknown provider: {provider}")

    fpath, furl = _save_mp3(audio, preset_id)
    return {
        "preset_id": preset_id, "provider": provider, "voice_id": voice_id,
        "text": text, "path": fpath, "url": furl,
        "size_bytes": len(audio),
    }
