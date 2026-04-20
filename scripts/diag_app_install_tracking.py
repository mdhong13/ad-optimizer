"""
Meta 앱 설치 추적 진단 — ad-optimizer 앱의 현재 설치 추적 구성 조회.

출력:
  1. 앱 기본 정보 (name, 플랫폼, 네임스페이스)
  2. Android 플랫폼 등록 상태 (package_name)
  3. 앱 이벤트 / Install Referrer 연결 여부
  4. 최근 28일 앱 설치 이벤트 수
  5. KR Canary 캠페인의 optimization_goal 확인
  6. 다음 액션 가이드

사용:
  python -m scripts.diag_app_install_tracking
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config.settings import settings

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

GRAPH = "https://graph.facebook.com/v21.0"
APP_ID = settings.META_APP_ID  # 26414252244902498
TOKEN = settings.META_ACCESS_TOKEN


def api_get(path: str, params: dict = None) -> dict:
    p = {"access_token": TOKEN}
    if params:
        p.update(params)
    r = httpx.get(f"{GRAPH}/{path}", params=p, timeout=30)
    try:
        body = r.json()
    except Exception:
        return {"_status": r.status_code, "_text": r.text[:300]}
    if r.status_code >= 400:
        return {"_error": body.get("error", {})}
    return body


def section(title: str):
    print(f"\n{'='*70}\n{title}\n{'='*70}")


def main():
    print(f"Meta 앱 설치 추적 진단 — App ID: {APP_ID}")
    if not TOKEN:
        print("❌ META_ACCESS_TOKEN 미설정")
        return

    # 1. 앱 기본 정보
    section("1. 앱 기본 정보")
    app_info = api_get(APP_ID, {"fields": "id,name,namespace,category,link,object_store_urls"})
    if "_error" in app_info:
        print(f"❌ 앱 조회 실패: {app_info['_error']}")
        return
    print(f"  name: {app_info.get('name')}")
    print(f"  namespace: {app_info.get('namespace')}")
    print(f"  category: {app_info.get('category')}")
    print(f"  object_store_urls: {json.dumps(app_info.get('object_store_urls', {}), ensure_ascii=False)}")

    # 2. Android 플랫폼 (앱 URL 설정 확인)
    section("2. Android 플랫폼")
    android = api_get(APP_ID, {"fields": "android_sdk_error_categories,supported_platforms"})
    print(f"  supported_platforms: {android.get('supported_platforms', [])}")
    pkg = api_get(APP_ID, {"fields": "app_signals_binding_ios,app_type"})
    print(f"  app_type: {pkg.get('app_type')}")

    # 3. 앱 이벤트 / Install Referrer
    section("3. 앱 이벤트 설정")
    # mmp_auditing_aggregated_report — MMP(Install Referrer 포함) 상태
    events = api_get(f"{APP_ID}/app_event_types")
    if "_error" in events:
        print(f"  (app_event_types 조회 실패: {events['_error'].get('message', '')[:100]})")
    else:
        types = events.get("data", [])
        print(f"  등록된 앱 이벤트 타입: {len(types)}개")
        for t in types[:10]:
            print(f"    - {t.get('event_name')} ({t.get('event_type')})")

    # Install Referrer 직접 확인 (v21 기준 사용 가능한 엔드포인트)
    ref = api_get(f"{APP_ID}/mmp_auditing_aggregated_report")
    if "_error" in ref:
        msg = ref["_error"].get("message", "")
        if "does not exist" in msg or "nonexisting field" in msg:
            print("  ⚠️ Install Referrer 상태는 Events Manager UI 에서만 확인 가능")
        else:
            print(f"  Install Referrer: {msg[:150]}")
    else:
        print(f"  Install Referrer 리포트: {json.dumps(ref, ensure_ascii=False)[:300]}")

    # 4. 최근 28일 앱 설치 이벤트 (광고 계정 단위)
    section("4. 최근 28일 앱 설치 인사이트 (광고 계정)")
    acc_id = settings.META_AD_ACCOUNT_ID  # act_xxx
    insights = api_get(
        f"{acc_id}/insights",
        {
            "fields": "actions,action_values,spend,impressions,clicks",
            "date_preset": "last_28d",
            "level": "account",
        },
    )
    if "_error" in insights:
        print(f"❌ 인사이트 실패: {insights['_error'].get('message', '')[:150]}")
    else:
        rows = insights.get("data", [])
        if not rows:
            print("  (데이터 없음)")
        for row in rows:
            print(f"  spend: ${row.get('spend', 0)}  impressions: {row.get('impressions', 0)}  clicks: {row.get('clicks', 0)}")
            installs = 0
            mobile_installs = 0
            for a in row.get("actions", []) or []:
                t = a.get("action_type", "")
                if t == "mobile_app_install":
                    mobile_installs = int(float(a.get("value", 0)))
                elif t == "app_install":
                    installs = int(float(a.get("value", 0)))
                elif "install" in t:
                    print(f"    [action] {t}: {a.get('value')}")
            print(f"  mobile_app_install (SDK 기반): {mobile_installs}")
            print(f"  app_install (총): {installs}")

    # 5. KR Canary 캠페인 optimization_goal 확인
    section("5. 현재 앱 캠페인의 optimization_goal")
    campaigns = api_get(
        f"{acc_id}/campaigns",
        {"fields": "id,name,objective,status", "effective_status": "['ACTIVE','PAUSED']", "limit": 20},
    )
    for c in campaigns.get("data", []):
        if c.get("objective") != "OUTCOME_APP_PROMOTION":
            continue
        print(f"  {c['name']} ({c['id']}) — {c.get('status')}")
        adsets = api_get(f"{c['id']}/adsets", {"fields": "id,name,optimization_goal,promoted_object"})
        for s in adsets.get("data", []):
            goal = s.get("optimization_goal", "?")
            po = s.get("promoted_object", {}) or {}
            print(f"    └ {s.get('name','')}: goal={goal}, pixel_id={po.get('pixel_id','-')}, "
                  f"custom_event={po.get('custom_event_type','-')}")

    # 6. 가이드
    section("6. 다음 액션")
    print("""
  [현재 상태 해석]
  - mobile_app_install = 0 → SDK 통합 안 됨 → Meta가 설치 이벤트 받지 못함
  - optimization_goal=LINK_CLICKS → '클릭' 최적화 중 (설치 최적화 아님)

  [선택지 A] Google Play Install Referrer (앱 수정 불필요)
    1. https://business.facebook.com/events_manager
    2. 좌측 '데이터 소스' → 'ad-optimizer' 앱 (26414252244902498) 선택
    3. '설정' 탭 → 'Install Referrer' 또는 '앱 설치 추적'
    4. Google Play 연동 활성화 (Play Console 계정 필요)
    → 며칠 내 mobile_app_install 카운트 집계 시작
    → OFFSITE_CONVERSIONS 최적화 가능

  [선택지 B] Facebook Android SDK 통합 (앱 릴리즈 필요)
    build.gradle:
      implementation 'com.facebook.android:facebook-android-sdk:17.0.0'
    AndroidManifest.xml: FACEBOOK_APP_ID 메타데이터 추가
    Application.onCreate():
      FacebookSdk.sdkInitialize(this);
      AppEventsLogger.activateApp(this);
    → OFFSITE_CONVERSIONS + APP_INSTALLS 최적화 모두 가능
    → 커스텀 이벤트(Subscribe/Purchase) 추적 가능

  [권장] 일단 A (Install Referrer) 켜고 데이터 쌓기.
  다음 앱 릴리즈 때 B (SDK) 추가.
""")


if __name__ == "__main__":
    main()
