# ad-optimizer 광고 파이프라인 (협업용 단일 진실 문서)

여러 세션·여러 에이전트가 동시에 ad-optimizer를 운영하기 위한 **공식 워크플로 + 책임 경계 + 위치 맵**.

> **새 세션 진입 시**: 먼저 [handoff.md](handoff.md) 를 읽고 "현재 진행 중" 상태부터 확인. 이 파이프라인 문서는 변하지 않는 구조.

---

## 1. 광고 파이프라인 5단계

```
[1] 전략 설계        [2] 크리에이티브       [3] 런치          [4] 운영           [5] 회고
─────────────────  ─────────────────  ──────────────  ──────────────  ──────────────
audience-analysis   creative-brief      launch_kr_*.py   daily-report     campaign-retro
   ↓                   ↓                   ↓                ↓                ↓
ab-test            ad-copy              DRY_RUN           anomaly-alert    학습 → DB
   ↓                                       ↓                ↓                ↓
target_spec.yaml                        PAUSED           spend-audit      다음 사이클
                                        ↓
                                     수동 활성화
```

### 각 단계가 만드는 산출물

| 단계 | 도구 (스킬) | 산출물 | 저장 위치 |
|---|---|---|---|
| 1. 전략 설계 | `audience-analysis` → `ab-test` | 타겟 페르소나, 실험 설계 | `docs/audiences/`, `docs/audience/` |
| 2. 크리에이티브 | `creative-brief` → `ad-copy` | 이미지·영상·카피 브리프 | `assets/generated/{platform}/`, `docs/copy/` |
| 3. 런치 | `scripts/launch_kr_*.py` | Google/Meta 캠페인 (PAUSED) | 플랫폼 API |
| 4. 운영 | `daily-report` · `anomaly-alert` · `spend-audit` | 일간 리포트, 이상 알림 | MongoDB `daily_reports`, Gmail |
| 5. 회고 | `campaign-retro` | KPT 분석, 학습 누적 | MongoDB `agent_decisions`, `docs/audience/` |

### 🚨 [2] 크리에이티브 단계 — 페르소나 도메인 격리 (첫 검수 항목)

광고 카피·이미지·TTS 만들 때 **target_product 확인 의무**:

| 광고 표면 | 페르소나 박을 것 |
|---|---|
| LiveOn (shoppingliveon.com 셀러 모집·도라미 메타휴먼 광고) | **도라미 (라미)** |
| truck.qcat.kr · qcat-guide · qcat-business · qcat-shop · qcat-wiki | **양자냥** |
| OneMessage (앱) | **자체 브랜드** (도라미·양자냥 둘 다 X) |
| 공통·중립 (Dotcell 회사 자체) | 페르소나 박지 X |

`/ad-copy`·`/creative-brief` 호출 시 *campaign_name* 또는 *target_product* 명확화 → 카피 검수 시 페르소나 이름 grep 더블 체크. 위반 시 사고 ([[feedback_persona_domain_isolation]]).

---

## 2. 디렉토리 책임 분배

```
ad-optimizer/
├── config/         ← 안전 캡, env 로드 (settings.py 단일 진실)
├── platforms/      ← 각 플랫폼 API 래퍼 (Meta, Google, Twitter, Reddit, Brave)
├── campaign/       ← 캠페인 생성·분석·실행 로직 (20→2 사이클 핵심)
├── intelligence/   ← 크립토 시장 모니터링, 경쟁사 추적
├── viral/          ← 바이럴 봇 매니저, 캐릭터 시스템
├── publisher/      ← 콘텐츠 배포 (YouTube, IG, Threads, TikTok, blog)
├── creative/       ← 이미지·영상·TTS 자동 생성
├── reporter/       ← 일간 리포트 생성, Gmail 발송
├── agent/          ← LLM 에이전트 (Claude·로컬 LLM·OpenClaw)
├── storage/        ← MongoDB 모델·CRUD (DB=ad_optimizer 전용)
├── scheduler/      ← APScheduler (8h 사이클, 2h 성과 수집, etc.)
├── web/            ← FastAPI 대시보드 (내부용)
├── social/         ← Telegram/Line/Discord 봇
├── scripts/        ← launch_kr_*.py 수동 런치 스크립트
├── cli/            ← CLI 도구
├── docs/
│   ├── ad_guide/   ← 플랫폼별 광고 기법·전략 (이 폴더에 누적)
│   ├── audiences/  ← 오디언스 분석 결과
│   ├── audience/   ← (구버전) 오디언스 deep-dive
│   ├── platforms/  ← 플랫폼 스펙 비교표 + yaml 위치
│   ├── api_access/ ← Google Ads API 신청 design doc
│   ├── copy/       ← 카피 라이브러리
│   ├── creative/   ← 크리에이티브 가이드
│   ├── generated/  ← AI 생성 산출물
│   ├── landing/    ← 랜딩 페이지 설계
│   └── pixel/      ← 픽셀·SDK 설치 가이드
├── ad_pipeline.md  ← 이 문서 (불변 구조)
├── handoff.md      ← 세션 간 인계 (변화하는 상태)
├── .env            ← 로컬 비밀 (Git 무시) → .env.global 폴백
└── SESSION_HANDOFF.md ← (있다면) 레거시 핸드오프
```

---

## 3. 플랫폼 지원 상태 (P0=핵심, P3=미래)

| 플랫폼 | 우선순위 | API 연동 | 런치 스크립트 | 실험 상태 |
|---|---|---|---|---|
| Google Ads (Search) | P0 | ⚠️ Basic Access 심사 중 | `launch_kr_child_google_search.py`, `launch_kr_crypto_google_search.py` | 대기 |
| Google Ads (YouTube) | P0 | ⚠️ 동일 | `launch_kr_senior_youtube.py` | 대기 |
| Meta (Facebook+IG) | P0 | ✅ 연동 완료 | `launch_kr_*_meta.py` (미작성) | App ID 결정 대기 |
| Twitter/X | P1 | ✅ Ads API 승인됨 | 미작성 | 대기 |

---

## 5. 외부 자원 통합 (cross-project, 2026-05-30 신설)

ad-optimizer 가 *내부 빌드* 외에 **외부 프로젝트 자원** 을 활용하는 경로. 각 자원은 별 cwd 의 capabilities 카탈로그에 정의됨.

### 5.1 LiveOn (도라미 메타휴먼 콘텐츠 자동 생성)

| 자원 | 활용 단계 | 호출 |
|---|---|---|
| 도라미 메타휴먼 + Qwen3-TTS voice clone (한국어 native) | [2] 크리에이티브 — 광고 영상 in-house batch | `POST https://api.shoppingliveon.com/api/v1/chapters/generate` |
| Qwen3-TTS CustomVoice 9 preset (5 감정 instruct) | [2] 크리에이티브 — 보이스 A/B 변형 | `/api/v1/tts` + customvoice override |
| 9:16 (쇼츠·릴스) + 16:9 (유튜브 교육) 영상 batch | [2] 크리에이티브 — 비율별 자동 | 동 endpoint |
| 카메라 10 + 조명 7 프리셋 (TV 홈쇼핑 컨벤션) | [2] 크리에이티브 — 영상 일관 톤 | scene_options.json |
| 페르소나 4대 절대 규칙 + 50대 타겟 룰 | [2] 크리에이티브 — 카피·소재 검수 | `[[feedback_liveon_persona_rules]]` · `[[feedback_liveon_target_user_50s]]` |
| 셀러 funnel 데이터 (`showhost_live.users` + `brands`) | [4] 운영 — attribution 시드 (외부 셀러 가입 후) | `LIVEON_MONGO_URI` (.env.global) |

상세 카탈로그: [liveon_capabilities.md](file:///D:/0_Dotcell/0_live_shopping_server/documents/liveon_capabilities.md) (8 섹션 — 한 줄 정체성·빠른 룩업·6 카테고리 자원·호출 패턴·미준비·기여 룰·가드레일·메모리 참조)

⚠ **차단점** — LiveOn 페이업 PG 결제 LIVE 미완 (2026-06-01 신청 → 1~2일 심사). 광고 → 가입 → 결제 funnel 검증 불가. 페이업 통과 전에는 *콘텐츠 라이브러리 batch* 까지만 가능.

### 5.2 향후 추가 후보 (별 cycle)

- qcat-shop (Coupang 광고) — `docs/ad_guide/ad_coupang.md` 이미 존재, 자원 카탈로그 미작성
- qcat-business (공개 가이드 + 챗봇) — 광고 input 후보
- OneMessage 앱 본체 (`D:\0_Dotcell\1_OneMSG\`) — 광고 trace 통합 미구축
| Reddit | P1 | ⚠️ Pixel 설치 필요 | 미작성 | 대기 |
| Brave | P1 | 미연동 | 미작성 | — |
| TikTok | P2 | 미연동 | 미작성 | — |
| **Coupang** | P2 (B2C 상품) | UI 운영 (API 별도) | 미작성 | — |
| Naver 브랜드검색 | P2 | 미연동 | 미작성 | — |
| CoinGecko/CMC 배너 | P3 | 미연동 | — | — |
| 스폰서 기사 (CoinDesk/CoinTelegraph) | P3 | 수동 | — | — |

> 플랫폼별 광고 기법 문서는 `docs/ad_guide/` 에 `ad_<platform>.md` 형식으로 누적.

---

## 4. MMP/Attribution 인프라

OneMessage 앱 (Flutter) 측 어트리뷰션:

| 도구 | 비용 | 역할 | 현재 상태 |
|---|---|---|---|
| Firebase Analytics + GA4 | 무료 | Google Ads 어트리뷰션 + 일반 분석 | ⬜ 미설치 (Phase 1 필수) |
| `facebook_app_events` SDK | 무료 | Meta 캠페인 어트리뷰션 | ⬜ 미설치 (Meta App ID 결정 후) |
| Adjust | $99~/월 | 멀티채널 통합 | ❌ 미선택 (월 ₩5M+ 광고비 시 검토) |
| Meta Pixel (웹) | 무료 | LPV 측정용 | ⬜ 미설치 (랜딩 페이지 onemsg.net) |

OneMessage 앱 위치: `D:\0_Dotcell\1_OneMSG\onemessage`

---

## 5. 안전 캡 (config/settings.py)

| 변수 | 기본값 | 역할 |
|---|---|---|
| `DRY_RUN` | true | 비프로덕션에선 모든 mutating 호출 차단 |
| `AUTO_ACTIVATE` | false | 캠페인 항상 PAUSED 로 생성 → 사람이 활성화 |
| `DAILY_BUDGET_CAP` | 40,000 KRW | 계정 전체 일 예산 상한 |
| `MAX_DAILY_BUDGET_PER_CAMPAIGN` | 4,000 KRW | 캠페인당 일 예산 상한 |
| `MIN_DAILY_BUDGET_PER_CAMPAIGN` | 1,500 KRW | 학습 망가지는 최저값 방어 |
| `MAX_ACTIVE_CAMPAIGNS` | 25 | 동시 활성 캠페인 수 |
| `BUDGET_CHANGE_LIMIT_PCT` | 30 | 단일 사이클 예산 변경폭 |
| `CANARY_MODE` | true | 첫 사이클 N개만 (안전 검증) |
| `CANARY_COUNT` | 3 | 카나리 개수 |

⚠️ **Google Ads UI 수동 캠페인은 이 캡과 무관**. 사용자 직접 설정한 캠페인은 무한 예산 가능 → 별도 결제 한도로만 방어.

---

## 6. MongoDB 컬렉션 (DB=`ad_optimizer`)

| 컬렉션 | 역할 |
|---|---|
| `performance_snapshots` | 2시간마다 캠페인 성과 스냅샷 |
| `agent_decisions` | LLM 에이전트 결정 이력 (예산 변경, pause, etc.) |
| `market_events` | 크립토 시장 이벤트 (BTC ±10%, 해킹 등) |
| `campaign_cycles` | 8시간 캠페인 최적화 사이클 |
| `characters` | AI 캐릭터 페르소나 |
| `viral_activities` | 바이럴 봇 활동 로그 |
| `published_content` | 콘텐츠 배포 로그 |
| `daily_reports` | 일간 성과 리포트 |
| `app_settings` | 활성 광고 계정 등 가변 설정 |

> ⚠️ `lastmessage` DB는 OneMessage 백엔드 전용 — 절대 사용 금지. `storage/db.py` 에 가드 있음.

---

## 7. 세션 간 협업 규칙

### 작업 시작 전
1. [handoff.md](handoff.md) "현재 진행 중" 섹션 확인
2. 같은 영역을 다른 세션이 작업 중이면 **회피 또는 합의**
3. 시작 시 handoff.md "진행 중" 에 본인 작업 항목 추가

### 작업 도중
- **DB 스키마 변경** → [storage/models.py](storage/models.py) 수정 + 인덱스 갱신 + handoff.md "최근 변경" 누적 기록
- **새 플랫폼 추가** → `platforms/<name>.py` + `config/platforms/<name>.yaml` + `docs/platforms/` 비교표 갱신 + `docs/ad_guide/ad_<name>.md` 가이드 작성
- **새 launch 스크립트** → `scripts/launch_*.py` + DRY_RUN 검증 + handoff.md 기록
- **안전 캡 변경** → [config/settings.py](config/settings.py) + 이 문서 Section 5 갱신

### 작업 종료
- git commit (granular 단위)
- handoff.md "최근 변경" 누적 항목 1줄 추가
- "진행 중" 에서 본인 항목 삭제 (또는 다음 핸드오프자 명시)

### 절대 하지 말 것
- handoff.md 매번 처음부터 덮어쓰기 (누적이 핵심)
- 작업마다 새 .md 파일 생성 (예: `change_2026_05_18.md`) — 파일 폭증
- `.env.global` 의 키 값을 다른 .md/메모리에 복사

---

## 8. 외부 의존성·계정

| 시스템 | 계정/ID | 용도 |
|---|---|---|
| Google Ads MCC | 489-423-4221 (QCat Manager) | 매니저 계정 |
| Google Ads Customer | 795-864-8888 | OneMessage 광고 계정 |
| Meta Ad Account | act_659784790884319 | Meta 광고 계정 |
| YouTube ([ONEMSG]) | mdhong13@gmail.com | OneMessage 채널 |
| Twitter | @onemsgx | OneMessage 트위터 |
| MongoDB | EC2 (`ec2-15-165-203-70`) | `ad_optimizer` DB |
| AWS Lambda | `lastmessage` 함수 (ap-northeast-2) | OneMessage 서버리스 |
| 로컬 LLM | d4win 서버 | 대량 카피·바이럴 생성 |
| Claude API | claude-sonnet-4-6 | 전략 판단·리포트 |

> 모든 API 키는 `D:\0_Dotcell\.env.global` 중앙 관리. **절대 이 문서에 키 값 복사 금지**.

---

## 9. 빠른 검증 명령

```bash
# DB 연결
python -m storage.db

# 캠페인 사이클 DRY_RUN
python -m campaign.manager --dry-run

# 플랫폼 API 테스트
python -m platforms.meta --test
python -m platforms.google_ads --test

# 웹 대시보드
uvicorn web.main:app --reload --port 8000

# 스케줄러
python -m scheduler.runner
```

---

## 10. 우선순위 (현재 — 2026-05-25 기준 핸드오프와 함께 확인)

| 순위 | 작업 | 상태 |
|---|---|---|
| P0 | Google Ads API Basic Access 재신청 (이메일 도메인 변경 후) | 대기 |
| P0 | OneMessage 앱 MMP/SDK 설치 (firebase_analytics + facebook_app_events) | Meta App ID 결정 대기 |
| P0 | 출혈 캠페인 사후 분석 (OneMessage Search EN KR — ₩1.74M 사고) | 일시중지 확인 필요 |
| P1 | Meta 타겟 고도화 — Phase 1 LPV 실험 설계 | MMP 준비 후 |
| P1 | dotcell.net 회사 정보 푸터 (사업자번호 + 주소) | 미착수 |
| P2 | 시즌 스케줄러 (명절/연말 타이밍) | 미착수 |
| P2 | 시니어 랜딩 모드 (`for=self`) | 미착수 |
| P2 | Coupang 광고 진입 (End ROAS 계산 + 상품별 설정) | 미착수 |
