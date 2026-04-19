# 광고 플랫폼 비교표

각 플랫폼의 **타겟팅 / 입찰 / 최소 예산 / 특수 조건** 한 눈에 비교.
상세 스펙은 `config/platforms/{platform}.yaml` 참조.

> **범례**: ✅ 완성 / 🟡 작업중 / ⬜ 미착수

| 플랫폼 | YAML 스펙 | 실제 캠페인 경험 | 비고 |
|---|---|---|---|
| Meta | ✅ `config/platforms/meta.yaml` | ✅ KR Canary 3개 집행 중 | v21.0 API |
| Google | ⬜ | ⬜ Basic access 대기 | 크립토 타겟 승인 필요 |
| Reddit | ⬜ | ⬜ | 서브레딧 타겟 |
| X (Twitter) | ⬜ | ⬜ | Ads API 승인 필요 |

---

## 🌍 지역 타겟팅

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 필드명 | `geo_locations.countries` | `geo_target_constants` | `geolocations` | `targeting_locations` |
| 값 형식 | ISO2 (`["KR","US"]`) | Resource name (`geoTargetConstants/2410`) | ISO2 + region | WOEID |
| 도시/우편번호 | ✅ `cities`, `zips` | ✅ | ✅ | ✅ (WOEID) |
| 반경 기반 | ✅ `custom_locations` (lat/lng+radius) | ✅ proximity | ❌ | ❌ |
| 제외 지역 | ✅ `exclusions` | ✅ negative | ✅ | ✅ |

## 👤 인구통계

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 나이 | ✅ `age_min/max` (13~65) | ✅ `age_range` (버킷: 18-24, 25-34…) | ❌ 없음 | ❌ 없음 |
| 성별 | ✅ `genders` [1,2] | ✅ `gender` | ❌ | ❌ |
| 언어 | ✅ `locales` (locale ID) | ✅ `language_constants` | ✅ | ✅ |
| 학력/가족 | ✅ `demographics.*` | 제한적 | ❌ | ❌ |
| 소득 | ✅ (미국만) | ✅ (미국만) | ❌ | ❌ |

## 📱 디바이스

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| OS 타겟 | ✅ `user_os` [Android/iOS] | ✅ `operating_systems` | ✅ `devices` | ✅ `devices` |
| 디바이스 종류 | ✅ `user_device` | ✅ `device.type` (MOBILE/TABLET/DESKTOP) | ✅ | ✅ |
| 통신사 | ❌ | ✅ (mobile carriers) | ❌ | ✅ |
| 접속 방식 | ❌ | ✅ (Wi-Fi / Cellular) | ❌ | ❌ |

## 🎯 관심사 / 행동

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 관심사 | ✅ `flexible_spec.interests` | ✅ `affinity_audiences` | ✅ 서브레딧 기반 | ✅ `interests` |
| 키워드 | ❌ | ✅ `keyword_themes` | ✅ | ✅ |
| 검색어 타겟 | ❌ | ✅ (Search) | ❌ | ✅ (`keywords`) |
| 팔로워/구독자 | ❌ | ❌ | ✅ 서브레딧 구독자 | ✅ `followers_of` |
| 구매 행동 | ✅ `behaviors` | ✅ `in_market_audiences` | ❌ | ✅ (일부) |
| 커스텀 오디언스 | ✅ | ✅ `user_lists` | ✅ | ✅ |
| 유사 타겟 | ✅ (Lookalike 1~10%) | ✅ (Similar audiences) | ❌ | ✅ (tailored audiences) |

## 💰 예산 & 입찰

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 최소 일 예산 | $1 (100 cents) | $0.01 | $5 | $1 |
| 입찰 단위 | AdSet (광고세트) | Campaign | Ad Group | Line Item |
| 자동 최적화 | `LOWEST_COST_WITHOUT_CAP` | `MAXIMIZE_CLICKS / MAXIMIZE_CONVERSIONS` | `CPM / CPC` | `AUTO_BID` |
| 비용 상한 | `COST_CAP` | `TARGET_CPA / TARGET_ROAS` | ❌ | ❌ |
| 입찰가 상한 | `LOWEST_COST_WITH_BID_CAP` | `MAXIMIZE_CLICKS + bid_ceiling` | ❌ | `MAX_BID` |
| 전환 추적 | Pixel + CAPI | Conversion action + gtag | Reddit Pixel | X Pixel |

## 🎨 크리에이티브

| 항목 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 이미지 포맷 | 1:1, 4:5, 9:16 (1080+) | 1:1 1200x1200, 1.91:1 1200x628 | 1.91:1 | 1.91:1 / 1:1 |
| 동영상 | ✅ (최대 240분) | ✅ YouTube 필수 | ✅ | ✅ |
| CTA 종류 | 20+ (LEARN_MORE, INSTALL_MOBILE_APP 등) | 7개 고정 | 5개 | 6개 |
| 헤드라인 길이 | 40자 | 30자 ×3 | 300자 | 280자 (트윗) |
| 본문 길이 | 135자 권장 | 90자 ×2 | 없음 | 280자 |

## 🎯 캠페인 목표

| 목표 | Meta | Google | Reddit | X |
|---|---|---|---|---|
| 트래픽 | `OUTCOME_TRAFFIC` | `SEARCH / DISPLAY` | `CLICKS` | `WEBSITE_CLICKS` |
| 앱 설치 | `OUTCOME_APP_PROMOTION` | `APP` (Universal) | `APP_INSTALLS` | `APP_INSTALLS` |
| 전환 | `OUTCOME_SALES` | `SEARCH + conversion action` | `CONVERSIONS` | `WEBSITE_CONVERSIONS` |
| 인지도 | `OUTCOME_AWARENESS` | `VIDEO / DISPLAY` | `BRAND_AWARENESS` | `AWARENESS` |
| 참여 | `OUTCOME_ENGAGEMENT` | ❌ | `VIDEO_VIEWS` | `ENGAGEMENTS` |

## ⚠️ 플랫폼별 함정

| 플랫폼 | 흔한 실수 | 해결 |
|---|---|---|
| Meta | OUTCOME_TRAFFIC + Play Store URL → 에러 #1815791 | OUTCOME_APP_PROMOTION 사용 |
| Meta | `user_os` 생략 → iPhone 유저에게도 Play Store 광고 노출 | 앱 광고 시 `user_os` 명시 |
| Meta | 65+ 타겟팅 실패 | age_min=60, age_max=65 로 대체 |
| Google | 크립토 키워드 정책 위반 | Basic access 승인 후 크립토 타겟팅 별도 허가 필요 |
| Reddit | 최소 예산 $5/일 — 소액 테스트 불가 | 테스트 예산 최소 $5 확보 |
| X | Ads API 승인 대기 ~2주 | 먼저 Developer approval 받기 |

---

## 📂 파일 맵

```
config/platforms/
  ├── meta.yaml         ✅ 완성
  ├── google.yaml       ⬜ TODO
  ├── reddit.yaml       ⬜ TODO
  └── twitter.yaml      ⬜ TODO

docs/platforms/
  ├── README.md         ← 이 파일 (비교표)
  ├── meta.md           ⬜ 상세 가이드 (TODO)
  ├── google.md         ⬜
  ├── reddit.md         ⬜
  └── twitter.md        ⬜

platforms/
  ├── base.py           AdPlatform ABC
  ├── meta.py           Meta 구현
  ├── google_ads.py     Google 구현
  ├── reddit.py         Reddit 구현
  └── twitter.py        X 구현
```

---

## 🔄 업데이트 규칙

- 새 캠페인 돌리면서 **실제로 겪은 함정**은 `gotchas:` 섹션에 즉시 기록
- 플랫폼이 값 형식 바꾸면 (예: Meta v21→v22) **YAML 먼저 수정** → 코드 따라가기
- 비교표(이 파일)는 요약만. **정확한 값은 YAML 참조**
