"""
KR Meta Canary Unified — 1개 Campaign + 3개 AdSet (CBO) + 3개 Ad

기존 `launch_kr_canary.py` 는 캠페인 3개를 따로 만들었지만,
이 버전은 **1개 캠페인** 안에 **3개 AdSet** 을 두어 CBO(Campaign Budget
Optimization)로 예산을 자동 배분. A/B 테스트 표준 구조.

구성:
  - Campaign: KR-Canary-Unified  (OUTCOME_APP_PROMOTION, CBO, PAUSED)
      ├── AdSet: C1-자녀-부모걱정   (age 40-55)  → Ad C1-A
      ├── AdSet: C2-1인가구         (age 25-45)  → Ad C2-A
      └── AdSet: C3-65+본인         (age 60-65)  → Ad C3-A

예산:
  - 캠페인당 일 예산 기본 ₩50,000 (--budget 으로 변경 가능, 사용자 상한)
  - CBO 가 AdSet 간 자동 배분 → 성과 좋은 AdSet 이 더 많이 소진
  - AdSet 별 개별 예산 X

사용:
  python -m scripts.launch_kr_canary_unified                  # DRY_RUN
  python -m scripts.launch_kr_canary_unified --live           # 실제 생성
  python -m scripts.launch_kr_canary_unified --budget 30000   # ₩30k/일
"""
from __future__ import annotations

import argparse
import io
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings
from scripts.launch_kr_canary import COPY, resolve_image_path, PLAY_STORE_URL, APP_PROMOTION

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logger = logging.getLogger(__name__)

DEFAULT_VARIANTS = ["C1-A", "C2-A", "C3-A"]
DEFAULT_BUDGET_KRW = 50000  # 사용자 지정 상한


def build_variant(vid: str) -> dict:
    """COPY[vid] → create_unified_campaign 이 받는 variant dict."""
    if vid not in COPY:
        raise ValueError(f"알 수 없는 변형: {vid}")
    c = COPY[vid]
    image_path = resolve_image_path(vid)
    return {
        "adset_name": f"{vid}-{c['campaign']}",
        "targeting": {
            "countries": ["KR"],
            "age_min": c["age_min"],
            "age_max": c["age_max"],
            "user_os": ["Android"],  # Play Store → Android 전용
        },
        "creatives": {
            "title": c["headline"],
            "body": c["primary"],
            "link": PLAY_STORE_URL,
            "image_path": image_path,
            "cta_type": "INSTALL_MOBILE_APP",
            "app_promotion": APP_PROMOTION,
        },
    }


def launch(variants: list = None, daily_budget_krw: int = None,
           dry_run: bool = True, campaign_name: str = "KR-Canary-Unified") -> dict:
    from platforms.meta import MetaAds

    variants = variants or DEFAULT_VARIANTS
    budget = daily_budget_krw or DEFAULT_BUDGET_KRW

    client = MetaAds()
    if not client.is_configured():
        raise RuntimeError("Meta 미구성")

    variant_specs = []
    errors = []
    for vid in variants:
        try:
            variant_specs.append(build_variant(vid))
        except Exception as e:
            errors.append({"variant_id": vid, "error": str(e)})
            logger.error(f"[{vid}] build 실패: {e}")

    if not variant_specs:
        return {"status": "error", "errors": errors, "campaign_id": None}

    logger.info(f"Unified 런치: budget=₩{budget:,}/day, {len(variant_specs)} variants, dry_run={dry_run}")
    try:
        result = client.create_unified_campaign(
            campaign_name=campaign_name,
            daily_budget=budget,
            variants=variant_specs,
            dry_run=dry_run,
        )
        return {
            "status": "dry_run" if dry_run else "created",
            "campaign_id": result["campaign_id"],
            "adsets": result["adsets"],
            "budget_krw": budget,
            "errors": errors,
        }
    except Exception as e:
        logger.error(f"unified 캠페인 생성 실패: {e}")
        return {"status": "error", "campaign_id": None, "errors": [*errors, {"error": str(e)}]}


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    ap = argparse.ArgumentParser(description="KR Canary Unified — 1캠페인 + 3AdSet CBO")
    ap.add_argument("--variants", default=",".join(DEFAULT_VARIANTS))
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET_KRW, help="캠페인 일 예산 KRW (기본 50000, 최대 권장 50000)")
    ap.add_argument("--name", default="KR-Canary-Unified")
    ap.add_argument("--live", action="store_true", help="DRY_RUN 무시하고 실제 생성")
    args = ap.parse_args()

    if args.budget > 50000:
        logger.warning(f"일 예산 ₩{args.budget:,} — 사용자 상한 ₩50,000 초과")

    variants = [v.strip().upper() for v in args.variants.split(",") if v.strip()]
    dry_run = False if args.live else settings.DRY_RUN

    print(f"KR Canary Unified 생성")
    print(f"  캠페인명: {args.name}")
    print(f"  변형: {variants}")
    print(f"  일 예산 (CBO): ₩{args.budget:,}")
    print(f"  DRY_RUN: {dry_run}")
    print()

    result = launch(variants=variants, daily_budget_krw=args.budget,
                    dry_run=dry_run, campaign_name=args.name)

    print(f"\n상태: {result['status']}")
    if result.get("campaign_id"):
        print(f"  campaign_id: {result['campaign_id']}")
        for a in result.get("adsets", []):
            print(f"    {a['variant_name']}: adset={a['adset_id']} ad={a['ad_id']}")
    for err in result.get("errors", []):
        print(f"  [ERR] {err}")


if __name__ == "__main__":
    main()
