"""
이미지 → 플랫폼별 사이즈 변형.

원본 픽셀 보존 (center-crop + resize only, 재생성 아님).
프롬프트 단계에서 safe-area composition 지시로 중앙 60% 안에 피사체 배치됨 →
center crop 으로도 주요 피사체 잘림 없음.
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable

from PIL import Image

log = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
RESIZE_OUT = ASSETS_DIR / "generated" / "creative" / "image_resized"
RESIZE_OUT.mkdir(parents=True, exist_ok=True)


# 플랫폼별 주요 광고 사이즈 (width, height, description)
# 출처: 각 플랫폼 광고 사양 (2026-04 기준, 일반적 권장)
PLATFORM_SIZES: dict[str, dict] = {
    # Meta (Facebook + Instagram)
    "meta_feed_1_1":     {"label": "Meta Feed 1:1",          "w": 1080, "h": 1080, "platform": "meta"},
    "meta_feed_4_5":     {"label": "Meta Feed 4:5",          "w": 1080, "h": 1350, "platform": "meta"},
    "meta_reels_9_16":   {"label": "Meta Reels/Stories 9:16","w": 1080, "h": 1920, "platform": "meta"},
    "meta_link_1_91_1":  {"label": "Meta Link 1.91:1",       "w": 1200, "h": 628,  "platform": "meta"},
    # Google Ads (Display / Discovery)
    "google_square":     {"label": "Google Square 1:1",      "w": 1200, "h": 1200, "platform": "google"},
    "google_landscape":  {"label": "Google Landscape 1.91:1","w": 1200, "h": 628,  "platform": "google"},
    "google_portrait":   {"label": "Google Portrait 4:5",    "w": 960,  "h": 1200, "platform": "google"},
    # X (Twitter)
    "x_timeline_16_9":   {"label": "X Timeline 16:9",        "w": 1200, "h": 675,  "platform": "x"},
    "x_timeline_1_1":    {"label": "X Timeline 1:1",         "w": 1200, "h": 1200, "platform": "x"},
    # Reddit
    "reddit_square":     {"label": "Reddit 1:1",             "w": 1200, "h": 1200, "platform": "reddit"},
    "reddit_landscape":  {"label": "Reddit 1.91:1",          "w": 1200, "h": 628,  "platform": "reddit"},
}


def _resolve_source(source_url_or_path: str) -> Path:
    """
    /assets/... 경로 또는 절대 경로를 로컬 파일시스템 경로로 변환.
    """
    s = source_url_or_path.strip()
    if s.startswith("/assets/"):
        rel = s[len("/assets/"):]
        p = ASSETS_DIR / rel
    else:
        p = Path(s)
    if not p.exists():
        raise FileNotFoundError(f"원본 이미지 없음: {p}")
    return p


def _center_crop_resize(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    """
    원본 이미지 → 타겟 비율로 중앙 크롭 → 타겟 사이즈로 리샘플링.
    """
    src_w, src_h = img.size
    src_ratio = src_w / src_h
    tgt_ratio = target_w / target_h

    if abs(src_ratio - tgt_ratio) < 0.001:
        # 비율 동일 → 리사이즈만
        return img.resize((target_w, target_h), Image.LANCZOS)

    if src_ratio > tgt_ratio:
        # 원본이 더 넓음 → 양옆 크롭
        new_w = int(src_h * tgt_ratio)
        left = (src_w - new_w) // 2
        box = (left, 0, left + new_w, src_h)
    else:
        # 원본이 더 높음 → 위아래 크롭
        new_h = int(src_w / tgt_ratio)
        top = (src_h - new_h) // 2
        box = (0, top, src_w, top + new_h)

    cropped = img.crop(box)
    return cropped.resize((target_w, target_h), Image.LANCZOS)


def resize_to_platforms(source: str, platform_keys: Iterable[str]) -> list[dict]:
    """
    원본 이미지 → 선택된 플랫폼 사이즈들로 변환.
    반환: [{"key", "label", "width", "height", "url", "path"}]
    """
    src_path = _resolve_source(source)
    results: list[dict] = []
    with Image.open(src_path) as img:
        img = img.convert("RGB")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        stem = src_path.stem
        for key in platform_keys:
            spec = PLATFORM_SIZES.get(key)
            if not spec:
                log.warning("[image_resize] unknown platform key: %s", key)
                continue
            w, h = spec["w"], spec["h"]
            try:
                out = _center_crop_resize(img, w, h)
            except Exception as e:
                log.exception("[image_resize] resize failed key=%s", key)
                results.append({"key": key, "label": spec["label"], "error": str(e)})
                continue
            uid = uuid.uuid4().hex[:6]
            fname = f"{ts}_{stem}_{key}_{uid}.jpg"
            out_path = RESIZE_OUT / fname
            out.save(out_path, format="JPEG", quality=92, optimize=True)
            results.append({
                "key": key,
                "label": spec["label"],
                "platform": spec["platform"],
                "width": w,
                "height": h,
                "url": f"/assets/generated/creative/image_resized/{fname}",
                "path": str(out_path),
            })
    return results
