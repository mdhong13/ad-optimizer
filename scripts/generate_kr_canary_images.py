"""
KR Meta Canary 광고 이미지 자동 생성 - Gemini Imagen 4.0

9 변형 (C1/C2/C3 × A/B/C) × Meta Feed 4:5 포맷
출력: assets/generated/meta/c{1,2,3}{a,b,c}_feed_45.png

브리프 출처: docs/campaigns/kr_canary_creative_brief.md

사용법:
  python -m scripts.generate_kr_canary_images              # 9개 전부
  python -m scripts.generate_kr_canary_images --only A     # A 변형만 3개
  python -m scripts.generate_kr_canary_images --only C1-A  # 1개만
  python -m scripts.generate_kr_canary_images --ratio 1:1  # 정사각 대안
"""
import argparse
import base64
import io
import os
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

# Windows cp949 콘솔에서 유니코드 한글/특수문자 출력 보장
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

OUTPUT_DIR = Path("D:/0_Dotcell/ad-optimizer/assets/generated/meta")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

IMAGEN_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/imagen-4.0-generate-001:predict"
)

# Imagen 4.0 공식 지원 비율: 1:1, 3:4, 4:3, 9:16, 16:9
# Meta Feed 4:5(1080x1350)가 네이티브 미지원 → 3:4로 폴백 (1.33 vs 1.25, 거의 유사)
DEFAULT_RATIO = "3:4"


# 9개 프롬프트 (kr_canary_creative_brief.md 기반)
PROMPTS = {
    "C1-A": {
        "angle": "사랑",
        "campaign": "자녀-부모걱정",
        "prompt": (
            "A Korean woman in her mid-40s at a modern office desk, warm "
            "afternoon sunlight through the window, looking at her smartphone "
            "with a gentle relieved smile. The phone screen shows a simple "
            "notification preview. Soft focus background, warm color palette "
            "of cream and soft peach, photorealistic, natural skin tones, "
            "shallow depth of field, emotional mood, intimate composition. "
            "Empty space in upper right for text overlay. Korean features, "
            "natural makeup, business casual attire in muted beige tones. "
            "No text, no letters, no watermark."
        ),
    },
    "C1-B": {
        "angle": "편의",
        "campaign": "자녀-부모걱정",
        "prompt": (
            "Extreme close-up of a modern smartphone held in a woman's hand, "
            "lock screen showing a subtle peaceful notification badge, "
            "defocused warm kitchen background with afternoon light, Korean "
            "home interior, cream and sage green color palette, photorealistic, "
            "minimalist composition, calm and reassuring mood. Shallow depth "
            "of field, soft bokeh. No text, no letters, no watermark."
        ),
    },
    "C1-C": {
        "angle": "사회증명",
        "campaign": "자녀-부모걱정",
        "prompt": (
            "Three generations of a Korean family gathered warmly in a cozy "
            "living room, grandmother in her 70s showing her smartphone to "
            "her daughter in her 40s, granddaughter watching nearby, soft "
            "evening light, home interior with warm wood tones and beige "
            "fabrics, photorealistic, emotional connection, candid natural "
            "expressions, shallow depth of field, cream and soft amber color "
            "palette. No text, no letters, no watermark."
        ),
    },
    "C2-A": {
        "angle": "재프레임",
        "campaign": "1인가구",
        "prompt": (
            "A Korean person in their 30s lying on a bed in a small urban "
            "apartment at night, holding a smartphone showing a peaceful "
            "notification, city lights blurred through window, warm bedside "
            "lamp glow, minimalist 1인 가구 Korean studio apartment, cream "
            "sheets and soft amber lamp light, photorealistic, introspective "
            "peaceful mood, shallow depth of field, intimate framing. "
            "No text, no letters, no watermark."
        ),
    },
    "C2-B": {
        "angle": "효율",
        "campaign": "1인가구",
        "prompt": (
            "Clean minimalist desk setup in a modern Korean studio apartment, "
            "open laptop, ceramic coffee cup, smartphone with a small status "
            "widget on screen, morning light through blinds, scandi-korean "
            "interior style, muted sage green and oatmeal beige palette, "
            "photorealistic, flat lay from above with slight tilt, shallow "
            "depth of field, calm productive mood, generous negative space "
            "top-right. No text, no letters, no watermark."
        ),
    },
    "C2-C": {
        "angle": "호기심",
        "campaign": "1인가구",
        "prompt": (
            "Modern Korean studio apartment living room with scattered smart "
            "home devices: air purifier, robot vacuum, smart speaker arranged "
            "in casual composition, a smartphone prominently placed in center "
            "on a wooden table, soft afternoon light, warm wood and muted "
            "white palette, photorealistic, editorial magazine style, shallow "
            "depth of field. Questioning curious mood. No text, no letters, "
            "no watermark."
        ),
    },
    "C3-A": {
        "angle": "사랑/가족",
        "campaign": "65+본인",
        "prompt": (
            "Korean grandmother in her early 70s sitting in her cozy living "
            "room, warm afternoon sunlight, holding a smartphone and looking "
            "at it with a tender loving smile, family photos on wall behind "
            "her, traditional Korean home interior with modern touches, cream "
            "and soft amber palette, natural grey hair, gentle wrinkles, "
            "authentic and dignified expression, photorealistic, shallow "
            "depth of field, emotional intimate composition. No text, no "
            "letters, no watermark."
        ),
    },
    "C3-B": {
        "angle": "자립",
        "campaign": "65+본인",
        "prompt": (
            "Active Korean grandfather in his late 60s to early 70s in a "
            "modern kitchen, morning light, wearing casual sportswear after "
            "exercise, holding a coffee mug in one hand and checking "
            "smartphone in other, confident and independent vibe, fit "
            "appearance, silver hair, Korean senior man, modern minimalist "
            "kitchen with plants, warm wood and sage green palette, "
            "photorealistic, shallow depth of field, dignified everyday "
            "moment. No text, no letters, no watermark."
        ),
    },
    "C3-C": {
        "angle": "편의",
        "campaign": "65+본인",
        "prompt": (
            "Close-up of two Korean hands, an elderly woman's hand with "
            "delicate wrinkles and a younger woman's hand guiding her through "
            "a smartphone app setup, warm living room background blurred, "
            "cream and peach tones, photorealistic, emotional connection "
            "shot, shallow depth of field, focus on the hands and phone, "
            "teaching moment mood, generous negative space for text overlay. "
            "No text, no letters, no watermark."
        ),
    },
}


def generate_image(variant_id: str, prompt: str, ratio: str) -> bool:
    """Imagen 4.0 이미지 1장 생성 + 파일 저장"""
    if not settings.GEMINI_API_KEY:
        print("  ERROR: GEMINI_API_KEY 미설정 (.env.global 확인)")
        return False

    filename = f"{variant_id.lower().replace('-', '')}_feed_{ratio.replace(':', '')}.png"
    filepath = OUTPUT_DIR / filename

    payload = {
        "instances": [{"prompt": prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": ratio,
        },
    }
    url = f"{IMAGEN_URL}?key={settings.GEMINI_API_KEY}"

    try:
        resp = httpx.post(url, json=payload, timeout=180)
    except httpx.TimeoutException:
        print(f"  TIMEOUT (180s)")
        return False

    if resp.status_code != 200:
        print(f"  HTTP {resp.status_code}: {resp.text[:300]}")
        return False

    data = resp.json()
    predictions = data.get("predictions") or data.get("generatedImages") or []
    if not predictions:
        print(f"  응답 구조 예외: keys={list(data.keys())}, preview={str(data)[:200]}")
        return False

    pred = predictions[0]
    img_b64 = (
        pred.get("bytesBase64Encoded")
        or pred.get("image", {}).get("bytesBase64Encoded", "")
    )
    if not img_b64:
        print(f"  이미지 데이터 없음 pred={str(pred)[:200]}")
        return False

    filepath.write_bytes(base64.b64decode(img_b64))
    kb = filepath.stat().st_size // 1024
    print(f"  OK {filename} ({kb} KB)")
    return True


def select_variants(only_arg):
    """--only 플래그 해석"""
    all_ids = list(PROMPTS.keys())
    if not only_arg:
        return all_ids

    upper = only_arg.upper()
    # C1-A 같은 정확 지정
    if upper in PROMPTS:
        return [upper]
    # "A" 또는 "B" 또는 "C" — 앵글 변형 전체
    if upper in ("A", "B", "C"):
        return [v for v in all_ids if v.endswith(f"-{upper}")]
    # "C1" 또는 "C2" 또는 "C3" — 캠페인 전체
    if upper in ("C1", "C2", "C3"):
        return [v for v in all_ids if v.startswith(upper)]
    raise SystemExit(f"--only 인식 실패: {only_arg} (예: C1-A, A, C2)")


def main():
    parser = argparse.ArgumentParser(description="KR Canary Imagen 생성")
    parser.add_argument(
        "--only",
        help="특정 변형만 (C1-A, A, C2 등)",
        default="",
    )
    parser.add_argument(
        "--ratio",
        help=f"비율 (기본 {DEFAULT_RATIO}; 대안 1:1, 9:16)",
        default=DEFAULT_RATIO,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="API 호출 없이 선택 대상만 출력",
    )
    args = parser.parse_args()

    variants = select_variants(args.only)
    print(f"KR Canary 이미지 생성")
    print(f"  대상: {len(variants)}개 — {', '.join(variants)}")
    print(f"  비율: {args.ratio}")
    print(f"  출력: {OUTPUT_DIR}")
    print()

    if args.dry_run:
        for vid in variants:
            info = PROMPTS[vid]
            print(f"[DRY] {vid} ({info['angle']}/{info['campaign']})")
            print(f"     {info['prompt'][:100]}...")
        return

    success = 0
    for i, vid in enumerate(variants, 1):
        info = PROMPTS[vid]
        print(f"[{i}/{len(variants)}] {vid} ({info['angle']}/{info['campaign']})")
        if generate_image(vid, info["prompt"], args.ratio):
            success += 1
        time.sleep(1)  # 레이트 리밋 완충

    print(f"\n완료: {success}/{len(variants)} 성공")


if __name__ == "__main__":
    main()
