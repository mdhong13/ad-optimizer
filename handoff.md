# handoff — ad-optimizer 세션 간 인계

여러 세션·여러 에이전트가 동시 작업할 때 **상태를 공유하기 위한 단일 누적 문서**.

> 구조·워크플로는 [ad_pipeline.md](ad_pipeline.md) 참조 (불변). 이 문서는 **변하는 상태**.

---

## 진행 중 (Working Now)

각 작업자는 시작할 때 한 줄 추가, 끝나면 삭제 (또는 "최근 변경"으로 이동).

| 작업 | 담당 세션 | 시작 | 비고 |
|---|---|---|---|
| _(없음)_ | | | |

---

## 차단 사항 / 대기 (Blocked / Waiting)

해결되어야 다음 단계 가능한 항목.

| 차단 | 차단 이유 | 해소 트리거 | 관련 |
|---|---|---|---|
| Google Ads API Basic Access 재신청 | 거절: `bungbungcar13@gmail.com` 개인 Gmail 사용 불가 | `*@dotcell.net` 도메인 이메일 생성 후 재신청 | 거절 메일 2026-04-25 수신 |
| Meta SDK 설치 (firebase_analytics + facebook_app_events) | Meta App ID 결정 안 됨 | 기존 `26414252244902498` 폐기 → 신규 App 생성 결정 | OneMessage `pubspec.yaml` |
| Meta 타겟 고도화 Phase 1 실험 | MMP 미설치 → 어트리뷰션 불가 | 위 SDK 설치 완료 | `docs/audiences/meta_kr_targeting_strategy.md` |
| OneMessage Search EN KR 캠페인 사후 분석 | 키워드별 CPC 원인 미식별 | 캠페인 → 키워드 탭 캡쳐 → 입찰 전략·고가 키워드 분석 | 일시중지 완료 (2026-05-26). 4-5월 출혈 ₩2.1M 회수 불가 |
| Coupang 광고 진입 | 상품별 End ROAS 계산 미완료 | 판매 상품 손익 구조 확정 | `docs/ad_guide/ad_coupang.md` |
| Railway ad-optimizer 환경변수 `DRY_RUN=true` 설정 | Railway가 .env.global 안 읽음 | 사용자가 Railway 대시보드에서 직접 변경 | 미조치 시 5/28 08:00 다음 사이클 발생 |
| ~~`web/main.py` 의 `scheduler_bg.start()` 가드 추가~~ | ✅ 완료 (2026-05-28) | `AUTO_START_SCHEDULER` env 플래그 기본 false. import 충돌 수정 (`settings as app_settings`). | 재발 방지 |
| Meta 광고 계정 reputation 점검 | 480건 거절 누적 영향 미파악 | Meta Business 알림·notification 확인 | 계정 정지 위험 |

---

## 최근 변경 (Recent Changes, 누적)

> 신규 항목은 **상단에 추가**. 형식: `[YYYY-MM-DD] 한 줄 요약` + (선택) 세부.

### 2026-05-28
- **🚨 Railway 자동 스케줄러 사고 발견·차단** — Railway 배포 ad-optimizer 웹앱(`web/main.py` startup hook)이 `.env.global` 의 `DRY_RUN=false` 와 함께 8시간 사이클로 Meta 캠페인 자동 생성 중. 최소 5/25~5/28 3일간 24 사이클 × 20개 = 480개 캠페인 자동 생성 시도. Meta가 crypto policy로 모두 거절 → 실제 출혈 0. **조치**: (1) `.env.global` `DRY_RUN=true` 로 복원 + 사고 주석. (2) Railway 측 환경변수도 사용자가 직접 변경 필요 (.env.global 안 읽음). **후속**: `web/main.py` `scheduler_bg.start()` 를 `AUTO_START_SCHEDULER` env 플래그 기본 false 로 가드 필요.

### 2026-05-26
- **handoff.md / ad_pipeline.md / docs/ad_guide/ad_coupang.md 신규 작성** — 다중 세션 협업 표준화. ad_guide 폴더는 플랫폼별 광고 기법·전략 누적 위치.
- **.env.ads.example 추가** — ad-optimizer가 사용하는 모든 광고 관련 env 변수 + Coupang 자리 포함한 템플릿.
- **OneMessage Search EN KR 일시중지** — 추가 출혈 차단. 이미 발생한 ₩2.1M (4월 ₩860K + 5월 ₩1,245K) 은 회수 불가. 6/1 자동 청구 예정 잔액 ₩244,995. 사후 분석(키워드별 CPC 원인) 미진행.

### 2026-05-25
- **Google Ads API Basic Access 신청 거절** — 개인 Gmail (`bungbungcar13@gmail.com`) 가 회사 도메인(dotcell.net) 불일치. v2.0 PDF 제출했으나 도메인 alignment 실패.
- **truck.qcat.kr sitemap.ts 개선** — search_index.json stale → 4개 개별 wiki json 직접 사용 + qaCount 기반 priority 차등(0.5~0.9) + brand floor 0.8. 총 712 URL.
- **DB cleanup** — `lastmessage` DB 안의 빈 ad-optimizer 컬렉션 8개 drop. `storage/db.py` 에 forbidden DB 가드 추가. `.env.global` 에 `AD_OPTIMIZER_DB=ad_optimizer` 명시.
- **Shielded VM 인증서 만료 메일** — quantumcat-f7570 영향 0건 확인 (모든 VM Secure Boot OFF + TERMINATED). 메일 무시.

### 2026-05-22 ~ 2026-05-24
- **ad-optimizer Meta 타겟 분석** — `docs/audiences/meta_kr_audiences.md` (3 페르소나 × 14 variant + Lookalike 시드 5종) + `meta_kr_targeting_strategy.md` (Phase 1~4 순차 실험 설계, 14 병렬 ❌ → 3→3→4→2 순차 ✅).

### 2026-04-21 ~ 2026-04-22
- **launch_kr_*.py 3종 작성** — child/crypto Google Search + senior YouTube. Google Ads API DRY_RUN 검증 통과 (실제 실행은 Basic Access 승인 후).
- **`scripts/create_api_design_doc.py` v2.0** — Q11/Q12 정합성 반영한 5페이지 PDF 생성기. 페이지브레이크·X포지션 reset 버그 수정.

### 2026-04-19
- **`config/platforms/meta.yaml` 최초 작성** — 6 objectives, 13 targeting 필드, 4 bid strategies, 함정 5건. KR Canary baseline 정의.
- **`docs/platforms/README.md`** — 4 플랫폼(Meta/Google/Reddit/X) 비교표.

---

## 의사결정 로그 (Decisions, 비자명한 것만)

> 코드/git log로 추적되지 않는 **"왜"** 정보.

### 2026-05-25 / Google Ads 신청 이메일 — 개인 Gmail 사용 결정 → 거절
**무엇**: 첫 신청에 `bungbungcar13@gmail.com` 사용
**왜 그랬나**: "통과 후 변경" 전략을 시도했음
**결과**: Identity verification 거절. 도메인 미일치
**교훈**: 처음부터 회사 도메인 이메일 (`*@dotcell.net`) 준비 후 신청. role-based alias 권장 (`google-ads-api@dotcell.net`)

### 2026-05-22 / Meta 14 variant 병렬 ❌ → 순차 깔때기 ✅
**무엇**: 처음엔 3 페르소나 × 5 variant 병렬 launch 검토
**왜 폐기**: ad set당 ₩1,500/일은 Meta 학습단계 (7일 내 50 전환) 미달. 모두 Learning Limited 상태
**대체**: Phase 1 (3 cells × ₩10,000/일 × 10일 = ₩300K) → Phase 2~4 순차

### 2026-04-19 / Meta yaml 단일 진실 도입
**무엇**: `config/platforms/meta.yaml` + `docs/platforms/README.md` 분리 (실행용 vs 사람 참고용)
**왜**: 플랫폼마다 필드명·형식·제약이 달라 캠페인 작성 시 혼동. 검증·참고를 한 곳으로 통일

---

## 운영 체크리스트 (매일/매주)

다음 항목은 daily-report / spend-audit / anomaly-alert 스킬이 자동화하지만, 수동 점검 시 사용:

### 매일
- [ ] daily_reports MongoDB 컬렉션 갱신 확인 (전날 데이터 있나?)
- [ ] 캠페인별 spend > MAX_DAILY_BUDGET_PER_CAMPAIGN 위반 없나?
- [ ] anomaly-alert 발송 이메일 확인

### 매주
- [ ] spend-audit: 좀비 캠페인(PAUSED+spend>0) 탐지
- [ ] campaign_cycles 진행 상태 확인 (학습 단계 / 정착 / 폐기 분류)
- [ ] 회수된 학습을 `docs/audience/` 또는 메모리에 반영

### 매월
- [ ] `.env.global` 환경 변수 회전 (refresh token 등)
- [ ] Meta Ad Library 경쟁사 광고 캡쳐
- [ ] 다음 달 예산 배분 계획

---

## 다음 세션 권장 진입 순서

새 세션이 들어오면:

1. **이 파일(handoff.md)** "진행 중" + "차단 사항" 먼저 읽기
2. **[ad_pipeline.md](ad_pipeline.md)** 의 Section 10 "우선순위" 확인
3. 차단 사항 중 본인이 풀 수 있는 것 있으면 → "진행 중" 에 본인 항목 추가 후 시작
4. 없으면 → 우선순위 P0/P1 중 미착수 항목 픽업
