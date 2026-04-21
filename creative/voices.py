"""
TTS 보이스 레지스트리.

.env.global 의 TTS_VOICE_* 엔트리를 파싱해 도구에서 쓸 수 있는 프리셋
리스트로 노출. 포맷: `{provider}|{voice_id}|{label}`
"""
from __future__ import annotations
import os
from typing import Optional


def _parse(entry: str) -> Optional[dict]:
    if not entry or "|" not in entry:
        return None
    parts = entry.split("|", 2)
    if len(parts) != 3:
        return None
    provider, voice_id, label = (p.strip() for p in parts)
    if provider not in ("elevenlabs", "typecast"):
        return None
    if not voice_id:
        return None
    return {"provider": provider, "voice_id": voice_id, "label": label or voice_id}


def load_voice_presets() -> list[dict]:
    """환경변수에서 TTS_VOICE_* 항목을 모두 읽어 프리셋 리스트 반환.
    반환 예: [{"id": "lamin_en_m", "provider": "elevenlabs", "voice_id": "...", "label": "..."}]
    """
    presets = []
    prefix = "TTS_VOICE_"
    for key, raw in os.environ.items():
        if not key.startswith(prefix):
            continue
        parsed = _parse(raw)
        if not parsed:
            continue
        parsed["id"] = key[len(prefix):].lower()
        presets.append(parsed)
    # EN 남성(유언 톤)이 기본값으로 잘 노출되도록 정렬
    order = {"lamin_en_m": 0, "junseong_kr_m": 1, "dohee_kr_f": 2,
             "kristen_en_f": 3, "harper_en_f": 4}
    presets.sort(key=lambda p: order.get(p["id"], 99))
    return presets


def find_preset(preset_id: str) -> Optional[dict]:
    for p in load_voice_presets():
        if p["id"] == preset_id:
            return p
    return None
