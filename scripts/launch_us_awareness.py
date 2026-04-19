"""
US Meta Awareness — 미국 크립토 지갑 보유자 대상 OneMessage 영상 인지도 캠페인

구성:
  - 1개 Campaign (OUTCOME_AWARENESS, PAUSED)
  - 1개 AdSet (US, 25-55, 영어, 크립토 관심사)
  - 1개 Ad (variant_a_dday_4x5.mp4 피드용 4:5 영상)
  - 랜딩: https://onemsg.net

예산:
  - 기본 $10/day (--budget USD 로 변경 가능)
  - DRY_RUN=true 면 실제 생성 없이 로그만

사용:
  python -m scripts.launch_us_awareness                 # DRY_RUN
  python -m scripts.launch_us_awareness --live          # 실제 생성
  python -m scripts.launch_us_awareness --budget 15 --live
"""
from __future__ import annotations

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

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets" / "generated" / "meta"
VIDEO_PATH = ASSETS_DIR / "variant_a_dday_4x5.mp4"
LANDING_URL = "https://onemsg.net"

# 영어 카피 — 크립토 지갑 보유자 대상 "자산 상속" 앵글
CREATIVE = {
    "title": "What happens to your crypto when you don't come back?",
    "body": (
        "Your wallet is worthless to your family if they can't unlock it. "
        "OneMessage watches your phone silently and, only if something goes wrong, "
        "delivers the words, keys, and access your loved ones need. "
        "No subscription while you're here. Set it and forget it."
    ),
    "cta_type": "LEARN_MORE",
}

# 타겟팅: 미국, 25-55, 영어, 크립토 관심사
# interest IDs (Meta 검색 기반 공개 관심사):
#   6003629266583 — Cryptocurrency
#   6003195797498 — Bitcoin
#   6003311931121 — Blockchain
#   6002931754687 — Ethereum
TARGETING = {
    "countries": ["US"],
    "age_min": 25,
    "age_max": 55,
    "locales": [6],  # 6 = English (US)
    "flexible_spec": [{
        "interests": [
            {"id": "6003629266583", "name": "Cryptocurrency"},
            {"id": "6003195797498", "name": "Bitcoin"},
            {"id": "6003311931121", "name": "Blockchain"},
            {"id": "6002931754687", "name": "Ethereum"},
        ],
    }],
}


def launch(daily_budget_usd: float = 10.0, dry_run: bool = True,
           video_path: str = None) -> dict:
    from platforms.meta import MetaAds

    client = MetaAds()
    if not client.is_configured():
        raise RuntimeError("Meta 미구성 (META_ACCESS_TOKEN/META_PAGE_ID/META_AD_ACCOUNT_ID)")

    video = Path(video_path) if video_path else VIDEO_PATH
    if not video.exists():
        raise FileNotFoundError(f"영상 파일 없음: {video}")

    name = "US-Awareness-CryptoWallet-V1"
    creatives = {
        "objective": "OUTCOME_AWARENESS",
        "optimization_goal": "REACH",
        "title": CREATIVE["title"],
        "body": CREATIVE["body"],
        "link": LANDING_URL,
        "cta_type": CREATIVE["cta_type"],
        "video_path": str(video),
    }

    logger.info(f"US Awareness 런치: budget=${daily_budget_usd}/day, dry_run={dry_run}")
    logger.info(f"  video: {video.name} ({video.stat().st_size/1e6:.1f}MB)")
    logger.info(f"  target: US, 25-55, English, crypto interests (4 IDs)")

    campaign_id = client.create_campaign(
        name=name,
        daily_budget=daily_budget_usd,
        targeting=TARGETING,
        creatives=creatives,
        dry_run=dry_run,
    )
    return {
        "name": name,
        "campaign_id": campaign_id,
        "status": "dry_run" if dry_run else "created",
        "budget_usd": daily_budget_usd,
        "video": str(video),
    }


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="US Meta Awareness 영상 캠페인 1개 생성")
    ap.add_argument("--budget", type=float, default=10.0, help="일 예산 USD (기본 10)")
    ap.add_argument("--video", default=None, help="영상 경로 (기본 variant_a_dday_4x5.mp4)")
    ap.add_argument("--live", action="store_true", help="DRY_RUN 무시하고 실제 생성")
    args = ap.parse_args()

    dry_run = False if args.live else settings.DRY_RUN
    print(f"US Awareness 캠페인 생성")
    print(f"  예산: ${args.budget}/day")
    print(f"  DRY_RUN: {dry_run}")
    print()
    try:
        result = launch(daily_budget_usd=args.budget, dry_run=dry_run, video_path=args.video)
        print(f"\n완료: {result['status']} → {result['campaign_id']}")
        print(f"  campaign: {result['name']}")
    except Exception as e:
        print(f"\n실패: {e}")
        raise


if __name__ == "__main__":
    main()
