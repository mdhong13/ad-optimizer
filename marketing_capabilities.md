# Marketing Capabilities — 다른 세션이 활용 가능한 자원 카탈로그

> **이 문서의 목적**: ad-optimizer 가 **이미 구축해둔 마케팅 자산**(LLM 엔드포인트, 광고 플랫폼 API, 분석 산출물, 스킬, 데이터)을 다른 Claude Code 세션이 **import / call / read** 형태로 활용할 수 있도록 안내.
>
> 인수인계 아님. 활용 가능 여부 확인 + 호출 패턴 가이드.
>
> | 다른 문서 비교 | 역할 |
> |---|---|
> | [ad_pipeline.md](ad_pipeline.md) | 광고 파이프라인 **구조** (변하지 않음) |
> | [handoff.md](handoff.md) | 현재 **진행 상태** (누적 갱신) |
> | **이 문서** | 다른 세션 입장에서의 **활용 가능 자원 목록** |

---

## 0. 한 줄 정체성

ad-optimizer = OneMessage(앱) + QCat 생태계의 **마케팅 자동화 플랫폼**.
위치: `D:\0_Dotcell\ad-optimizer\`
주요 기능: LLM 기반 광고 카피·전략 생성 + 멀티플랫폼 API + 캠페인 자동 최적화 + 성과 리포팅.

---

## 1. 빠른 룩업 — "내가 X 하고 싶다 → Y 써"

| 하고 싶은 것 | 사용할 것 | 위치 |
|---|---|---|
| 광고 카피 쓰기 | `ad-copy` 스킬 | `~/.claude/skills/ad-copy/` |
| 타겟 오디언스 분석 | `audience-analysis` 스킬 | `~/.claude/skills/audience-analysis/` |
| A/B 실험 설계 | `ab-test` 스킬 | `~/.claude/skills/ab-test/` |
| 영상/이미지 브리프 | `creative-brief` 스킬 | `~/.claude/skills/creative-brief/` |
| 매일 광고 성과 요약 | `daily-report` 스킬 | `~/.claude/skills/daily-report/` |
| 광고 이상 감지 | `anomaly-alert` 스킬 | `~/.claude/skills/anomaly-alert/` |
| 예산 감사 | `spend-audit` 스킬 | `~/.claude/skills/spend-audit/` |
| 캠페인 회고 | `campaign-retro` 스킬 | `~/.claude/skills/campaign-retro/` |
| Claude API 호출 (전략 판단) | `agent.claude.py` 또는 직접 ANTHROPIC_API_KEY | `agent/claude.py` |
| 로컬 LLM (대량 카피 생성) | d4win OpenAI-compatible 엔드포인트 | `LOCAL_LLM_BASE_URL` |
| Meta 광고 API 호출 | `platforms/meta.py` | `platforms/meta.py` |
| Google Ads API 호출 | `platforms/google_ads.py` | `platforms/google_ads.py` (Basic Access 승인 대기) |
| 캠페인 성과 데이터 읽기 | `storage/db.py` 헬퍼 | `storage/db.py` |
| AI 캐릭터 페르소나 | MongoDB `characters` 컬렉션 | DB=ad_optimizer |
| 크립토 시장 이벤트 | MongoDB `market_events` 컬렉션 | DB=ad_optimizer |
| 오디언스 페르소나 (분석 결과) | `docs/audiences/` | `docs/audiences/meta_kr_*.md` |
| 플랫폼별 타겟팅 스펙 | `config/platforms/*.yaml` | `config/platforms/meta.yaml` (완성) |
| 광고 기법 가이드 | `docs/ad_guide/` | `docs/ad_guide/ad_<platform>.md` 누적 |

---

## 2. 사용 가능한 자원

### 2.1 LLM 엔드포인트

#### Claude API (전략 판단·리포트 분석)
```python
# 직접 사용
from anthropic import Anthropic
import os
client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
# 모델: claude-sonnet-4-6
```
또는 `agent/claude.py` 래퍼 사용.

#### 로컬 LLM (d4win — 대량 카피·바이럴 생성)
```python
# OpenAI 호환 인터페이스
import openai
client = openai.OpenAI(
    base_url=os.getenv("LOCAL_LLM_BASE_URL"),  # http://d4win.iptime.org:31088
    api_key="not-required",
)
resp = client.chat.completions.create(
    model="auto",  # /v1/models 에서 자동 감지
    messages=[...],
)
```
- ⚠️ d4win 서버 접속 전 사용자 승인 받기 (`feedback_d4win_access.md` 정책)
- 용도: 광고 카피 20개 대량 변형, 바이럴 댓글, 캐릭터 대화

### 2.2 광고 플랫폼 API

| 플랫폼 | 클래스 | 상태 | env 변수 prefix |
|---|---|---|---|
| Meta (FB+IG) | `platforms.meta.Meta` | ✅ 연동 완료 | `META_*` |
| Google Ads | `platforms.google_ads.GoogleAds` | ⚠️ Basic Access 심사 중 (테스트 계정만 가능) | `GOOGLE_ADS_*` |
| Twitter/X | `platforms.twitter` (미작성) | ✅ Ads API 승인됨 | `TWITTER_*` |
| Reddit | `platforms.reddit` (미작성) | ⚠️ 미연동 | `REDDIT_*` |
| Brave | `platforms.brave` (미작성) | ❌ 미연동 | — |

공통 ABC: `platforms/base.py` 의 `AdPlatform` 상속.

```python
from platforms.meta import MetaAds
meta = MetaAds()  # .env.global 의 META_* 자동 로드
campaigns = meta.list_campaigns(status="ACTIVE")
```

### 2.3 MongoDB 컬렉션 + 헬퍼

DB 이름: **`ad_optimizer`** (절대 `lastmessage` 와 공유 금지. `storage/db.py` 에 forbidden 가드 있음.)

| 컬렉션 | 헬퍼 함수 | 용도 |
|---|---|---|
| `performance_snapshots` | `insert_performance`, `get_recent_performance`, `aggregate_campaign_performance`, `get_total_spend`, `get_campaign_timeseries`, `get_campaign_summary` | 캠페인 성과 (impressions/clicks/spend/conversions/revenue) |
| `agent_decisions` | `insert_decision`, `get_pending_decisions`, `update_decision_status` | LLM 에이전트 결정 이력 |
| `market_events` | `insert_market_event`, `get_recent_market_events` | 크립토 시장 이벤트 |
| `campaign_cycles` | `insert_cycle`, `update_cycle`, `get_latest_cycle`, `get_cycle_by_id` | 8h 캠페인 사이클 |
| `characters` | `upsert_character`, `get_active_characters` | AI 캐릭터 페르소나 |
| `viral_activities` | `insert_viral_activity` | 바이럴 봇 활동 |
| `published_content` | `insert_published_content` | 콘텐츠 배포 로그 |
| `daily_reports` | `upsert_daily_report` | 일간 리포트 |
| `app_settings` | `get_app_setting`, `set_app_setting`, `get_active_meta_account`, `set_active_meta_account` | 가변 설정 (활성 광고 계정 등) |

사용 예:
```python
from storage.db import get_recent_performance, aggregate_campaign_performance

# 다른 프로젝트에서 ad-optimizer 데이터 조회
import sys; sys.path.insert(0, r"D:\0_Dotcell\ad-optimizer")
rows = get_recent_performance(platform="meta", days=7)
agg = aggregate_campaign_performance(platform="meta", days=30)
```

⚠️ **import 가능하지만 DB write 는 신중** — 다른 프로젝트에서 ad-optimizer 컬렉션에 쓸 일은 거의 없음. read-only 권장.

### 2.4 분석·전략 산출물 (읽기 전용)

| 파일 | 내용 | 누가 쓸 만한가 |
|---|---|---|
| `docs/audiences/meta_kr_audiences.md` | OneMessage 3 페르소나 × 14 variant Meta 타겟팅 | OneMessage 마케팅 / 시니어 콘텐츠 / 크립토 콘텐츠 |
| `docs/audiences/meta_kr_targeting_strategy.md` | Phase 1~4 순차 깔때기 실험 설계 + 예산 모델 | 광고 launch 직전 검토 |
| `docs/platforms/README.md` | 4 플랫폼 (Meta/Google/Reddit/X) 비교표 | 신규 플랫폼 진입 시 |
| `docs/api_access/google_ads_design_doc.md` + `.pdf` | Google Ads API Basic Access 신청서 v2.0 | 재신청 / 유사 신청 참고 |
| `docs/ad_guide/ad_coupang.md` | 쿠팡 End ROAS 전략 (손익분기 광고 수익률) | qcat-shop 광고 / Coupang 입점 시 |
| `docs/ad_guide/seo_pipeline_template.md` | **truck.qcat.kr 검증 → 추상화** 5 phase SEO 표준 (메타·발견성·SSR·측정·봇차단) | 신규 표면 SEO 진입 시 필수 |
| `docs/ad_guide/cross_surface_framework.md` | **다중 표면 협업 framework** 4-Layer 모델 + 새 capability 추가 11단계 체크리스트 + 표면×capability 매트릭스 | 새 cross-surface 기능 추가 전 필수 |

### 2.5 안전 설정 (config/settings.py)

| 변수 | 기본값 | 효과 |
|---|---|---|
| `DRY_RUN` | true | 모든 mutating API 호출 차단 |
| `AUTO_ACTIVATE` | false | 캠페인 항상 PAUSED 생성 |
| `AUTO_START_SCHEDULER` | false | **2026-05-28 신규** — Railway 배포 시 자동 가동 차단. 명시적 opt-in 필요 |
| `DAILY_BUDGET_CAP` | 40,000 KRW | 계정 일 예산 상한 |
| `MAX_DAILY_BUDGET_PER_CAMPAIGN` | 4,000 KRW | 캠페인당 상한 |
| `MIN_DAILY_BUDGET_PER_CAMPAIGN` | 1,500 KRW | 학습 망가짐 방어 |
| `BUDGET_CHANGE_LIMIT_PCT` | 30 | 사이클당 예산 변경폭 |
| `CANARY_MODE` + `CANARY_COUNT` | true / 3 | 첫 사이클 N개만 |

다른 프로젝트가 ad-optimizer 코드를 호출할 때 이 값들이 자동 적용됨.

### 2.6 외부 계정 ID (참조용)

| 계정 | ID | 메모리 |
|---|---|---|
| Google Ads MCC | 489-423-4221 (QCat Manager) | `reference_google_ads.md` |
| Google Ads Customer | 795-864-8888 (OneMessage) | 동 |
| Meta Ad Account | act_659784790884319 | — |
| YouTube ([ONEMSG]) | mdhong13@gmail.com | `reference_onemsg_github.md` |
| Twitter | @onemsgx | — |
| AdMob 활성 | pub-5578859717946803 | — |
| AdMob 폐기 | pub-1097551985052292 (비활성화 무시 OK) | — |

⚠️ 모든 비밀 키는 `D:\0_Dotcell\.env.global` 중앙. **이 문서에 절대 복사 금지**.

---

## 3. 다른 프로젝트에서 호출 패턴

### 3.1 ad-optimizer 코드를 그냥 import

```python
import sys
sys.path.insert(0, r"D:\0_Dotcell\ad-optimizer")

# 환경변수 로드 (ad-optimizer 가 자동으로 .env.global 폴백 해주지만 명시 권장)
from dotenv import load_dotenv
load_dotenv(r"D:\0_Dotcell\.env.global")

# 이후 자유롭게 import
from config.settings import settings
from storage.db import aggregate_campaign_performance
from platforms.meta import MetaAds
```

### 3.2 스킬 호출 (대화형)

다른 세션에서:
```
/audience-analysis  → 페르소나 분석 결과 .md 자동 작성
/ad-copy            → 광고 카피 생성 (audience-analysis 결과 입력)
/creative-brief     → 이미지/영상/TTS 브리프 (ad-copy 결과 입력)
/ab-test            → 통계적 유효 실험 설계
/daily-report       → 어제 광고 성과 요약
/anomaly-alert      → 이상 징후 즉시 감지
/spend-audit        → 예산 집행 감사
/campaign-retro     → 종료 캠페인 회고
```

위 스킬은 시스템 전역(모든 세션) 에서 사용 가능. ad-optimizer 프로젝트와 무관하게 호출 가능.

### 3.3 산출물 .md 만 참조

광고 작업 안 하는 세션이라도, ad-optimizer가 정리해둔 페르소나/전략 문서를 **읽기**만 해도 도움:
```python
# 예: OneMessage 앱 세션이 "이 타겟이 누구지?" 궁금할 때
from pathlib import Path
audiences = Path(r"D:\0_Dotcell\ad-optimizer\docs\audiences\meta_kr_audiences.md").read_text(encoding="utf-8")
```

---

## 4. 미준비 — 다른 세션이 가정하면 안 되는 것

| 미준비 항목 | 상태 | 차단 사유 |
|---|---|---|
| Google Ads 실제 캠페인 launch | ❌ | Basic Access 거절 (도메인 이메일 부재) |
| Meta 캠페인 자동 launch | ⚠️ DRY_RUN | Meta App ID 미정 (실제 OneMessage 앱 연동 안 됨) |
| 앱 install 어트리뷰션 | ❌ | firebase_analytics + facebook_app_events SDK 미설치 |
| Twitter Ads launch 스크립트 | ❌ | API 승인은 됐으나 launch 코드 미작성 |
| Reddit Ads launch 스크립트 | ❌ | API 연동 자체 안 됨 |
| TikTok 광고 | ❌ | 미연동 |
| Naver 브랜드검색 / GFA | ❌ | 미연동 |
| Coupang 광고 자동화 | ❌ | UI 운영만. Partners API 미신청 |
| 캠페인 자동 사이클 (production) | ❌ | `AUTO_START_SCHEDULER=false` 기본. 의도적 opt-in 필요 |

⚠️ 위 항목은 "이거 ad-optimizer 가 해줄 거야" 가정하지 말 것. handoff.md "차단 사항" 도 함께 확인.

---

## 5. 다른 세션이 ad-optimizer 에 기여할 때

### 자기 영역과 겹치는 부분 발견 시

| 다른 프로젝트가 손대고 싶은 영역 | 권장 행동 |
|---|---|
| OneMessage 앱 SDK 설치 | ad-optimizer handoff.md "차단 사항" 의 Meta SDK 작업과 같이 진행 (협의) |
| onemsg.net 랜딩 페이지 | ad-optimizer 의 UTM 컨벤션 (`launch_kr_*.py` 의 utm_source/medium/campaign) 준수 |
| qcat-shop 광고 진입 | `docs/ad_guide/ad_coupang.md` End ROAS 계산 그대로 활용 |
| LLM 카피 생성 | 로컬 LLM (d4win) 우선. Claude API는 전략 판단용 |
| 분석 .md 작성 | `docs/audiences/` 컨벤션 따라가기 |
| MongoDB 데이터 추가 | 새 컬렉션 만들지 말고 기존 활용. 새 컬렉션 필요 시 `storage/models.py` INDEXES 추가 + handoff.md 기록 |

### handoff.md 업데이트 의무

다른 세션이 ad-optimizer 자산을 **mutate** 한 경우 (코드 수정, env 변경, 스키마 변경 등):
- `handoff.md` "최근 변경" 에 한 줄 추가
- 형식: `[YYYY-MM-DD] 한 줄 요약 (담당 세션: <누구>)`

읽기만 한 경우는 기록 불필요.

---

## 6. 안전·조정 가드레일 (위반 금지)

다른 세션이 ad-optimizer 와 같이 일할 때 **절대 어기지 말 것**:

1. **`.env.global` 의 키 값을 다른 .md/메모리에 복사 금지** — CLAUDE.md 정책
2. **`lastmessage` DB 에 ad-optimizer 컬렉션 만들지 말 것** — OneMessage 백엔드 전용. `storage/db.py` 에 forbidden 가드 있음
3. **`DRY_RUN=false` 로 바꾸는 건 명시적·일시적으로만** — 2026-05-28 Railway 자동 가동 사고 재발 방지
4. **`AUTO_START_SCHEDULER=true` 도 동일** — 명시적 운영 의도 표시만
5. **Google Ads / Meta 캠페인 수동 생성 시 일 예산 ₩4,000 이하** — UI 수동 캠페인은 우리 캡 무시함. 결제 한도로만 방어 가능
6. **AdMob `pub-1097551985052292`** (비활성화된 옛 계정) **건드리지 말 것** — OneMessage는 `pub-5578859717946803` 사용
7. **이 카탈로그 문서에 비밀번호/토큰 적지 말 것**
8. **페르소나 도메인 격리** — `/ad-copy`·`/creative-brief` 호출 시 *target_product* 또는 *campaign_name* 입력 의무. 카피에 페르소나 이름 박기 전 표면 확인:
   - LiveOn (shoppingliveon.com) → **도라미 (라미)**
   - truck.qcat.kr / qcat-guide / qcat-business / qcat-shop / qcat-wiki → **양자냥**
   - OneMessage (앱) → **자체 브랜드** (도라미·양자냥 둘 다 X)
   - Dotcell 회사 중립 광고 → 페르소나 박지 말 것
   - 위반 시 production 사용자에게 mascot 혼동 노출 (2026-05-27 truck 표면 사고 사례). 룰 출처: `feedback_persona_domain_isolation.md`
9. **OneMessage 인프라를 마케팅 채널로 쓰지 말 것** — 안심메시지 본문·푸시·SMS 인프라 모두 광고 송출 금지. 사후 메시지 비밀 유지가 제품 핵심 약속 (`feedback_onemsg_no_body_exposure.md`)

---

## 7. 메모리 참조 — 더 자세한 컨텍스트

다음 메모리 항목들이 마케팅 시스템과 직접 관련:

| 메모리 | 다루는 내용 |
|---|---|
| `project_ad_optimizer.md` | ad-optimizer 프로젝트 전반 |
| `project_ad_optimizer_assets.md` | 에셋 폴더 규칙 |
| `project_ad_optimizer_platforms.md` | 플랫폼 타겟팅 스펙 위치 |
| `project_ad_optimizer_language_split.md` | 크리에이티브 KR/EN 언어 분리 |
| `project_onemessage_product.md` | OneMessage 제품 사양 (광고 메시지 작성 시 필수) |
| `project_onemsg_safety_sms_spec.md` | 안심 메시지 동작 (광고 카피와 직결) |
| `reference_google_ads.md` | Google Ads 계정 정보 |
| `reference_custom_skills.md` | 광고 8 스킬 인벤토리 |
| `feedback_d4win_access.md` | 로컬 LLM 접속 전 승인 정책 |

새 세션이 마케팅 작업하려면 위 메모리 우선 로드 권장.

---

## 8. 자매 세션 협업 카탈로그 (다른 표면이 우리에게 제공하는 것)

ad-optimizer 가 *호출자* 가 되어 활용 가능한 자매 표면의 자원.

### 8.1 LiveOn (닷셀 라이브 쇼핑 솔루션)

| 자원 | 위치 | 용도 |
|---|---|---|
| LiveOn capabilities 카탈로그 | `D:\0_Dotcell\0_live_shopping_server\documents\liveon_capabilities.md` | LiveOn 자원·API·페르소나·funnel 전체 |
| 도라미 메타휴먼 영상 생성 | LiveOn 씬 파이프라인 v2 | LiveOn 광고 영상 in-house batch (광고비 절감) |
| Qwen3-TTS 음성 합성 | LiveOn TTS 엔진 | 한국어 광고 보이스오버 |
| 카메라·조명 프리셋 10+7 | LiveOn 메모리 `reference_liveon_camera_lighting.md` | 광고 영상 connection 카메라 워크 |
| 셀러 funnel 데이터 | LiveOn `showhost_live` / `live_shopping_server` DB | LiveOn 광고 LAL 시드, retention 분석 |

**첫 공동 캠페인 후보**: 광고 영상 in-house batch (페이업 통과 전 콘텐츠 라이브러리 미리 생성) — LiveOn 측 cross-link commit `mdhong13/live_shopping_server 6adf585`.

### 8.2 QCat 생태계 (트럭·가이드·비즈니스·쇼핑·위키)

| 표면 | 마스코트 | 도메인 | 우리가 받을 수 있는 자산 |
|---|---|---|---|
| `truck.qcat.kr` | 양자냥 | 화물 트럭 운전자 | SEO 파이프라인 (`docs/seo-pipeline.md`), 화물·교통·운송 법률 콘텐츠 |
| `qcat-guide` | 양자냥 | 캠핑·배터리·무시동 히터 | 위키 본문 → 광고 랜딩 + 콘텐츠 마케팅 시드 |
| `qcat-business` | 양자냥 | B2B 사업자 가이드 | 사업자 타겟 콘텐츠 |
| `qcat-shop` | 양자냥 | 사업자 전용 헤드리스 쇼핑몰 | Cafe24+Next.js 거래 funnel |
| `qcat-wiki` (`bridge.qcat.kr`) | 양자냥 | 위키 정본 | 광고 랜딩 + RAG 응답 출처 |

**자산 6건 1차 목록**:
1. 네이버 검색 SEO 파이프라인 (truck) — guide·liveon·business 표면에 재사용 가능
2. 한국 화물·교통·운송 법률 콘텐츠 (`truck-law-kr` 스킬) — 트럭 광고 랜딩·블로그 소재
3. 50대 사용자 디자인 룰 (truck·liveon 메모리 2건) — 카피·이미지 가독성 가드
4. 도라미 페르소나 (LiveOn) — LiveOn 광고 톤·매너
5. 캠핑·배터리·무시동 히터 가이드 (qcat-guide) — 광고 랜딩 + 콘텐츠 마케팅 시드
6. (예정) 네이버 지식인 자동 댓글 인프라 (truck → 분업 협의 중)

### 8.3 협업 원칙 — "광고 운영 = 표면 자율"

QCat 감독 세션 측 결정 (2026-05-30):
- **광고 채널 운영권은 각 표면이 보유** — ad-optimizer 가 100% 받지 않음
- ad-optimizer 는 **마케팅 인프라·실행·모니터링** 제공자 역할
- 각 표면이 직접 집행하거나 ad-optimizer 에 *의뢰* (위임 X)
- spend-audit / anomaly-alert / daily-report 는 안전망으로 항상 적용

### 8.4 D-30 신표면 출시 협업 루틴 (QCat 측 약속)

신규 QCat 표면 출시 시 ad-optimizer 에 ping:
- D-30: `/audience-analysis` 호출
- D-14: `/ad-copy` 후보 + `/creative-brief`
- D-7: `/ab-test` 설계
- D+7: `/daily-report` + `/anomaly-alert` 가동
- D+30: `/campaign-retro` 회고

### 8.5 QCat 감독 세션 연락점

- **거버넌스 문서**: `D:\2_QuantumCat\QCAT_REGISTRY.md` (외부 도구 섹션에 ad-optimizer 등록 예정)
- **표면별 SESSION_HANDOFF.md**: "마케팅 자원 = ad-optimizer 세션" 참조 예정
- **합의 메모리**: `reference_ad_optimizer_collab.md` 생성 예정 (QCat 측)

---

## 9. 변경 로그

| 날짜 | 변경 |
|---|---|
| 2026-05-30 | 최초 작성 — 다른 세션 활용 카탈로그 |
| 2026-05-30 | LiveOn cross-link — `D:\0_Dotcell\0_live_shopping_server\documents\liveon_capabilities.md` 작성됨. 도라미 메타휴먼 영상·TTS·셀러 funnel·페르소나 룰 카탈로그. 페르소나 도메인 격리 (도라미 ≠ 양자냥) 룰 적용 필수 — `feedback_persona_domain_isolation.md` 갱신됨 |
| 2026-05-30 | Section 8 신설 — LiveOn + QCat 5 표면 + 자산 6건. 가드레일에 페르소나 격리 + OneMessage 인프라 금지 2건 추가. "광고 운영 = 표면 자율" 협업 원칙 명시 |
| 2026-05-30 | **Cross-Surface 협업이 framework 로 격상** — (1) `docs/ad_guide/seo_pipeline_template.md` (truck 추상화). (2) `docs/ad_guide/cross_surface_framework.md` (4-Layer 모델 + 11단계 체크리스트). (3) 대시보드 nav 확장 — `/seo` SEO 최적화 + `/knowin` 지식인 답글 (둘 다 다중 표면 인벤토리 내장). 자매 세션과의 ad-hoc 액션 → 표준 패턴화. |
