"""Meta Ads DRY_RUN 테스트"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Avoid circular import from platforms.__init__
import importlib.util
spec = importlib.util.spec_from_file_location("meta", Path(__file__).parent.parent / "platforms" / "meta.py")
meta_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meta_module)
MetaAds = meta_module.MetaAds

from config.settings import settings

def main():
    print("=" * 60)
    print("Meta Ads DRY_RUN 테스트")
    print("=" * 60)

    print("\n[1] 설정 확인")
    print(f"  APP_ID:          {'OK' if settings.META_APP_ID else 'MISSING'}")
    print(f"  ACCESS_TOKEN:    {'OK' if settings.META_ACCESS_TOKEN else 'MISSING'}")
    print(f"  AD_ACCOUNT_ID:   {settings.META_AD_ACCOUNT_ID}")
    print(f"  DRY_RUN:         {settings.DRY_RUN}")

    meta = MetaAds()
    if not meta.is_configured():
        print("\n[ERROR] Meta 설정 미완료")
        return

    print("\n[2] DRY_RUN 캠페인 생성")
    result = meta.create_campaign(
        name="Crypto Inheritance Protection",
        daily_budget=5.0,
        targeting={
            "countries": ["US", "GB", "KR"],
            "age_min": 25,
            "age_max": 65,
        },
        creatives={
            "title": "Protect Your Bitcoin Inheritance",
            "body": "Secure your crypto assets for your family with OneMessage.",
            "link": "https://onemsg.net",
            "image_url": "https://onemsg.net/og-image.png",
        },
        dry_run=True,
    )
    print(f"  결과: {result}")
    print(f"  상태: DRY_RUN이므로 실제 API 호출 안 됨 ✓")

    print("\n[3] DRY_RUN=False 모드는 어떻게?")
    print(f"  현재 .env 설정: DRY_RUN={settings.DRY_RUN}")
    if not settings.DRY_RUN:
        print("  ⚠️  DRY_RUN=false 이므로 다음 실행부터 실제 Meta API 호출됨!")
        print("  ⚠️  Google Ads Basic Access 승인 전이므로 아직 비활성화 권장")
    else:
        print("  ✓  DRY_RUN=true 상태 — 테스트 안전")

    print("\n" + "=" * 60)
    print("테스트 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
