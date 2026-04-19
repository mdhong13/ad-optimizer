"""
KR Meta Canary — AI 생성 우회, 준비된 카피+이미지로 3개 캠페인 즉시 생성

캠페인 구성:
  - 1개 variant ID (예: C1-A) → Meta 캠페인 1개 (PAUSED, Play Store 랜딩)
  - 기본 3개 (C1-A, C2-A, C3-A) 또는 --variants 로 지정
  - 카피: docs/campaigns/kr_canary_copy.md
  - 이미지: assets/generated/meta/{id}_feed_34_overlay.png (폴백: {id}_feed_34.png)

예산:
  - 캠페인당 MIN_DAILY_BUDGET_PER_CAMPAIGN 사용 (기본 1500 KRW)
  - DRY_RUN=true면 실제 생성 없이 로그만

사용:
  python -m scripts.launch_kr_canary                       # C1-A, C2-A, C3-A
  python -m scripts.launch_kr_canary --variants C1-A,C2-B  # 커스텀
  python -m scripts.launch_kr_canary --budget 2000         # 캠페인당 일 예산 (KRW)
"""
import argparse
import io
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

IMAGES_DIR = Path(__file__).resolve().parent.parent / "assets" / "generated" / "meta"
# Meta OUTCOME_TRAFFIC는 Play Store 직링크 거부 (앱 설치 목표만 허용).
# onemsg.net 랜딩에서 Play Store 이동 버튼으로 우회.
LANDING_URL = "https://onemsg.net"

# kr_canary_copy.md 에서 추출한 9 변형
COPY = {
    "C1-A": {
        "campaign": "자녀-부모걱정", "angle": "사랑",
        "age_min": 40, "age_max": 55,
        "headline": "엄마 오늘도 잘 계시죠?",
        "primary": "자주 전화 못 드려 마음 쓰이시죠. 안심메시지가 12시간마다 부모님 스마트폰 사용을 확인하고, 이상이 있을 때만 알려드려요. 오늘도 웃고 계신 어머니, 우리가 조용히 지켜봐요.",
        "description": "12시간 미사용 시 자동으로 알려드려요",
    },
    "C1-B": {
        "campaign": "자녀-부모걱정", "angle": "편의",
        "age_min": 40, "age_max": 55,
        "headline": "걱정 대신 자동 알림",
        "primary": "매일 전화하기는 부담스럽고, 연락이 없으면 불안하죠. 안심메시지는 부모님이 스마트폰을 안 쓰시면 자동으로 알려드려요. 평소엔 조용히, 필요할 때만.",
        "description": "이상 있을 때만 알림이 갑니다",
    },
    "C1-C": {
        "campaign": "자녀-부모걱정", "angle": "사회증명",
        "age_min": 40, "age_max": 55,
        "headline": "가족들이 편해진 앱",
        "primary": "혼자 계신 부모님 걱정에 잠 못 드시나요? 안심메시지는 이상이 있을 때만 SMS를 보내드려요. 지금도 많은 자녀들이 매일 편안하게 잠자리에 들고 있어요.",
        "description": "평범한 날은 조용해요",
    },
    "C2-A": {
        "campaign": "1인가구", "angle": "재프레임",
        "age_min": 30, "age_max": 50,
        "headline": "혼자 살아도 누군가는",
        "primary": "며칠째 연락이 없어도 눈치챌 사람이 없어요. 안심메시지가 대신 확인해 드려요. 12시간 이상 스마트폰 사용이 없을 때 지정한 지인에게 자동 SMS. 1주 1회 무료.",
        "description": "보이지 않는 안전망",
    },
    "C2-B": {
        "campaign": "1인가구", "angle": "효율",
        "age_min": 30, "age_max": 50,
        "headline": "조용한 안전장치",
        "primary": "설치만 하면 끝. 평소 배터리도 거의 안 쓰고, 12시간 이상 사용이 없을 때만 지정한 사람에게 SMS가 가요. 번거로운 알림 없이, 조용한 보험처럼.",
        "description": "매일 확인, 한 번 설정",
    },
    "C2-C": {
        "campaign": "1인가구", "angle": "호기심",
        "age_min": 30, "age_max": 50,
        "headline": "새 1인 가구 필수템",
        "primary": "택배, 배달, 홈 시큐리티. 다음은 뭘까요? 내가 평소처럼 움직이지 않으면 그걸 눈치채는 앱. 12시간 무사용 감지 → 자동 SMS. 한 번만 설정해두면 됩니다.",
        "description": "조용히, 하지만 확실히",
    },
    "C3-A": {
        "campaign": "65+본인", "angle": "사랑/가족",
        "age_min": 60, "age_max": 65,  # Meta 65+ 제약 회피 (60~65)
        "headline": "자식 걱정 덜어드리기",
        "primary": "자주 연락 못 하면 자식들도 마음이 쓰이지요. 안심메시지를 켜두시면 따로 매일 알리지 않아도, 스마트폰을 평소처럼 쓰시면 돼요. 이상 없을 땐 조용히 기다립니다.",
        "description": "평소처럼만 쓰시면 됩니다",
    },
    "C3-B": {
        "campaign": "65+본인", "angle": "자립",
        "age_min": 60, "age_max": 65,
        "headline": "혼자서도 든든하게",
        "primary": "자식한테 매일 연락드리는 것도 일이지요. 안심메시지는 스마트폰을 평소대로 쓰시면 자동으로 '오늘도 괜찮다'는 신호를 가족에게 보냅니다. 조용한 안부.",
        "description": "따로 할 일은 없습니다",
    },
    "C3-C": {
        "campaign": "65+본인", "angle": "편의",
        "age_min": 60, "age_max": 65,
        "headline": "한 번 설정, 평생 안심",
        "primary": "복잡한 설정 필요 없습니다. 자녀 번호 한 번 저장하고, 스마트폰 평소처럼 쓰시면 됩니다. 12시간 이상 사용이 없으면 자녀에게 자동으로 알림이 갑니다. 그 외엔 조용해요.",
        "description": "자녀 번호만 등록하세요",
    },
}

DEFAULT_VARIANTS = ["C1-A", "C2-A", "C3-A"]


def resolve_image_path(vid: str) -> str:
    """오버레이 → 원본 순서로 이미지 경로 결정"""
    key = vid.lower().replace("-", "")
    overlay = IMAGES_DIR / f"{key}_feed_34_overlay.png"
    plain = IMAGES_DIR / f"{key}_feed_34.png"
    if overlay.exists():
        return str(overlay)
    if plain.exists():
        return str(plain)
    raise FileNotFoundError(f"이미지 없음: {overlay} / {plain}")


def launch(variants=None, daily_budget=None, dry_run=None):
    """
    KR Canary 3개 캠페인 생성.
    반환: [{variant_id, campaign_id, name, status, error}, ...]
    """
    variants = variants or DEFAULT_VARIANTS
    if daily_budget is None:
        daily_budget = settings.MIN_DAILY_BUDGET_PER_CAMPAIGN
    if dry_run is None:
        dry_run = settings.DRY_RUN

    from platforms.meta import MetaAds
    client = MetaAds()

    if not client.is_configured():
        return [{
            "variant_id": vid, "campaign_id": None, "name": "",
            "status": "error",
            "error": "Meta 미구성 (META_APP_ID/ACCESS_TOKEN/PAGE_ID 확인)",
        } for vid in variants]

    results = []
    for vid in variants:
        if vid not in COPY:
            results.append({
                "variant_id": vid, "campaign_id": None, "name": "",
                "status": "error", "error": f"알 수 없는 변형: {vid}",
            })
            continue

        c = COPY[vid]
        name = f"KR-Canary-{vid}-{c['campaign']}"
        try:
            image_path = resolve_image_path(vid)
        except FileNotFoundError as e:
            results.append({
                "variant_id": vid, "campaign_id": None, "name": name,
                "status": "error", "error": str(e),
            })
            continue

        targeting = {
            "countries": ["KR"],
            "age_min": c["age_min"],
            "age_max": c["age_max"],
            # Play Store 링크 → Android 사용자만 (iPhone 제외)
            "user_os": ["Android"],
        }
        creatives = {
            "title": c["headline"],
            "body": c["primary"],
            "link": LANDING_URL,
            "image_path": image_path,
            # 랜딩페이지 → DOWNLOAD CTA ('앱 다운로드' 버튼). 랜딩에서 Play Store 이동
            "cta_type": "DOWNLOAD",
        }

        try:
            campaign_id = client.create_campaign(
                name=name,
                daily_budget=daily_budget,
                targeting=targeting,
                creatives=creatives,
                dry_run=dry_run,
            )
            results.append({
                "variant_id": vid, "campaign_id": campaign_id, "name": name,
                "status": "dry_run" if dry_run else "created",
                "error": None,
            })
            logger.info(f"[{vid}] OK → {campaign_id}")
            print(f"[{vid}] OK → {campaign_id}")
        except Exception as e:
            results.append({
                "variant_id": vid, "campaign_id": None, "name": name,
                "status": "error", "error": str(e),
            })
            logger.error(f"[{vid}] FAILED: {e}")
            print(f"[{vid}] FAILED: {e}")

    return results


def main():
    parser = argparse.ArgumentParser(description="KR Meta Canary 3개 즉시 생성")
    parser.add_argument("--variants", default=",".join(DEFAULT_VARIANTS),
                        help="콤마 구분 변형 ID (예: C1-A,C2-A,C3-A)")
    parser.add_argument("--budget", type=float, default=None,
                        help=f"캠페인당 일 예산 (KRW, 기본 {settings.MIN_DAILY_BUDGET_PER_CAMPAIGN})")
    parser.add_argument("--live", action="store_true",
                        help="DRY_RUN 무시하고 실제 생성 (주의)")
    args = parser.parse_args()

    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    dry_run = False if args.live else settings.DRY_RUN

    print(f"KR Canary 생성")
    print(f"  변형: {variants}")
    print(f"  예산: {args.budget or settings.MIN_DAILY_BUDGET_PER_CAMPAIGN} (KRW/일/캠페인)")
    print(f"  DRY_RUN: {dry_run}")
    print()

    results = launch(variants=variants, daily_budget=args.budget, dry_run=dry_run)

    ok = sum(1 for r in results if r["status"] in ("created", "dry_run"))
    print(f"\n완료: {ok}/{len(results)} 성공")
    for r in results:
        mark = "OK" if r["status"] in ("created", "dry_run") else "ERR"
        print(f"  [{mark}] {r['variant_id']:5} {r['status']:10} {r.get('error') or r['campaign_id']}")


if __name__ == "__main__":
    main()
