"""
KR Canary 이미지에 헤드라인 오버레이 (Pillow)

입력: assets/generated/meta/c{1,2,3}{a,b,c}_feed_34.png (9장)
출력: assets/generated/meta/c{...}_feed_34_overlay.png (9장)

헤드라인 출처: docs/campaigns/kr_canary_copy.md
레이아웃: 하단 1/3 어두운 그라디언트 + 흰색 볼드 텍스트
"""
import io
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

OUTPUT_DIR = Path("D:/0_Dotcell/ad-optimizer/assets/generated/meta")
FONT_PATH = "C:/Windows/Fonts/NanumGothicBold.ttf"

# 9 변형 헤드라인 (kr_canary_copy.md 기반)
HEADLINES = {
    "c1a": "엄마 오늘도\n잘 계시죠?",
    "c1b": "걱정 대신\n자동 알림",
    "c1c": "가족들이\n편해진 앱",
    "c2a": "혼자 살아도\n누군가는",
    "c2b": "조용한\n안전장치",
    "c2c": "새 1인 가구\n필수템",
    "c3a": "자식 걱정\n덜어드리기",
    "c3b": "혼자서도\n든든하게",
    "c3c": "한 번 설정,\n평생 안심",
}

# 각 변형 서브헤드 (더 작게, 헤드라인 아래)
SUBHEADS = {
    "c1a": "12시간 미사용 시 자동 알림",
    "c1b": "이상 있을 때만 알림이 갑니다",
    "c1c": "평범한 날은 조용해요",
    "c2a": "보이지 않는 안전망",
    "c2b": "매일 확인, 한 번 설정",
    "c2c": "조용히, 하지만 확실히",
    "c3a": "평소처럼만 쓰시면 됩니다",
    "c3b": "따로 할 일은 없습니다",
    "c3c": "자녀 번호만 등록하세요",
}


def add_gradient_overlay(img: Image.Image, start_ratio=0.5) -> Image.Image:
    """하단 50%에 투명→검정 그라디언트"""
    w, h = img.size
    gradient = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(gradient)
    start_y = int(h * start_ratio)
    for y in range(start_y, h):
        progress = (y - start_y) / (h - start_y)
        # 부드러운 easing
        alpha = int(220 * (progress ** 1.5))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))
    return Image.alpha_composite(img.convert("RGBA"), gradient)


def draw_text_with_shadow(draw, xy, text, font, fill="white", shadow="black", offset=3):
    x, y = xy
    # 그림자
    draw.multiline_text((x + offset, y + offset), text, font=font, fill=shadow,
                        align="left", spacing=8)
    # 본문
    draw.multiline_text((x, y), text, font=font, fill=fill,
                        align="left", spacing=8)


def process(vid: str):
    """c1a 같은 ID 하나 처리"""
    src = OUTPUT_DIR / f"{vid}_feed_34.png"
    dst = OUTPUT_DIR / f"{vid}_feed_34_overlay.png"
    if not src.exists():
        print(f"  SKIP {vid} (원본 없음: {src.name})")
        return False

    img = Image.open(src).convert("RGBA")
    w, h = img.size

    # 1. 그라디언트 오버레이 (하단 50%)
    img = add_gradient_overlay(img, start_ratio=0.5)

    draw = ImageDraw.Draw(img)

    # 2. 헤드라인 (하단 25% 위치)
    headline = HEADLINES[vid]
    headline_size = int(w * 0.09)  # 이미지 너비의 9%
    headline_font = ImageFont.truetype(FONT_PATH, headline_size)

    # 텍스트 박스 좌상단 기준, 좌측 여백 6%
    left_margin = int(w * 0.06)

    # headline 높이 계산
    bbox = draw.multiline_textbbox((0, 0), headline, font=headline_font, spacing=8)
    headline_h = bbox[3] - bbox[1]

    # 서브헤드 높이
    subhead = SUBHEADS[vid]
    sub_size = int(w * 0.035)
    sub_font = ImageFont.truetype(FONT_PATH, sub_size)
    sub_bbox = draw.textbbox((0, 0), subhead, font=sub_font)
    sub_h = sub_bbox[3] - sub_bbox[1]

    gap = int(h * 0.02)
    total_h = headline_h + gap + sub_h
    bottom_margin = int(h * 0.06)

    headline_y = h - bottom_margin - total_h
    sub_y = headline_y + headline_h + gap

    draw_text_with_shadow(draw, (left_margin, headline_y), headline, headline_font,
                          fill="white", shadow=(0, 0, 0, 180), offset=3)
    draw_text_with_shadow(draw, (left_margin, sub_y), subhead, sub_font,
                          fill=(255, 240, 220), shadow=(0, 0, 0, 180), offset=2)

    img.convert("RGB").save(dst, "PNG", optimize=True)
    kb = dst.stat().st_size // 1024
    print(f"  OK {dst.name} ({kb} KB)")
    return True


def main():
    print(f"KR Canary 헤드라인 오버레이")
    print(f"  출력: {OUTPUT_DIR}\n")
    success = 0
    for vid in HEADLINES:
        print(f"[{vid.upper()}]")
        if process(vid):
            success += 1
    print(f"\n완료: {success}/{len(HEADLINES)} 성공")


if __name__ == "__main__":
    main()
