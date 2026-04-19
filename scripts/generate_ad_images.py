"""
OneMessage 광고용 이미지 생성 - Gemini Imagen 4.0
Google Ads: 1200x1200 (1:1), 1200x628 (1.91:1)
"""
import sys
from pathlib import Path

import httpx
import base64
import os
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

GEMINI_API_KEY = settings.GEMINI_API_KEY
OUTPUT_DIR = "D:/0_Dotcell/ad-optimizer/assets/generated/google"
os.makedirs(OUTPUT_DIR, exist_ok=True)

IMAGEN_URL = f"https://generativelanguage.googleapis.com/v1beta/models/imagen-4.0-generate-001:predict?key={GEMINI_API_KEY}"


def generate_image(prompt, filename, aspect_ratio="1:1"):
    """Imagen 4.0으로 이미지 생성"""
    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": aspect_ratio,
        }
    }

    resp = httpx.post(IMAGEN_URL, json=payload, timeout=120)
    if resp.status_code != 200:
        print(f"  Error {resp.status_code}: {resp.text[:200]}")
        return False

    data = resp.json()
    predictions = data.get("predictions", data.get("generatedImages", []))
    if not predictions:
        # 다른 응답 구조 시도
        print(f"  Response keys: {list(data.keys())}")
        print(f"  Response preview: {str(data)[:300]}")
        return False

    for i, pred in enumerate(predictions):
        img_b64 = pred.get("bytesBase64Encoded", pred.get("image", {}).get("bytesBase64Encoded", ""))
        if img_b64:
            filepath = os.path.join(OUTPUT_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(base64.b64decode(img_b64))
            print(f"  -> {filename} saved")
            return True

    print(f"  No image data found")
    return False


# 광고 이미지 프롬프트
AD_IMAGES = [
    {
        "prompt": "Minimalist app advertisement, dark blue gradient background, glowing shield icon protecting a golden bitcoin symbol, floating cloud server nodes connected by light trails, text area on the right side clean and empty, professional fintech aesthetic, high quality digital art, no text no letters no words",
        "filename": "ad_crypto_protect_square.png",
        "ratio": "1:1",
    },
    {
        "prompt": "Minimalist app advertisement, dark blue gradient background, glowing shield icon protecting a golden bitcoin symbol, floating cloud server nodes connected by light trails, wide composition, professional fintech aesthetic, high quality digital art, no text no letters no words",
        "filename": "ad_crypto_protect_wide.png",
        "ratio": "16:9",
    },
    {
        "prompt": "Family safety concept, warm toned background fading to deep blue, a smartphone floating in center with a glowing message bubble and heart icon, soft light rays emanating outward, connected dots forming a safety net pattern, modern clean design, no text no letters no words",
        "filename": "ad_family_safety_square.png",
        "ratio": "1:1",
    },
    {
        "prompt": "Family safety concept, warm toned background fading to deep blue, a smartphone floating with glowing message bubble and heart icon, soft light rays, connected dots forming safety net, wide panoramic composition, modern clean design, no text no letters no words",
        "filename": "ad_family_safety_wide.png",
        "ratio": "16:9",
    },
    {
        "prompt": "Digital countdown timer concept, dark futuristic background, a large circular holographic timer display showing time countdown, a glowing envelope icon below the timer ready to be sent, subtle blockchain pattern in background, neon blue and purple accents, high quality 3D render, no text no letters no words",
        "filename": "ad_deadman_switch_square.png",
        "ratio": "1:1",
    },
    {
        "prompt": "Digital countdown timer concept, dark futuristic background, holographic timer display with countdown, glowing envelope icon, subtle blockchain pattern, neon blue purple accents, wide cinematic composition, high quality 3D render, no text no letters no words",
        "filename": "ad_deadman_switch_wide.png",
        "ratio": "16:9",
    },
]


def main():
    print(f"OneMessage 광고 이미지 생성 ({len(AD_IMAGES)}장)")
    print(f"출력: {OUTPUT_DIR}\n")

    success = 0
    for i, img in enumerate(AD_IMAGES, 1):
        print(f"[{i}/{len(AD_IMAGES)}] {img['filename']} ({img['ratio']})")
        if generate_image(img["prompt"], img["filename"], img["ratio"]):
            success += 1
        print()

    print(f"\n완료: {success}/{len(AD_IMAGES)} 성공")


if __name__ == "__main__":
    main()
