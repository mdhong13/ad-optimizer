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

## 🎯 신규 세션 진입 시 — 즉시 우선순위

새 마케팅 세션이 들어오면 **이 순서대로** 처리:

1. **🚨 외부 cron 박을지 결정** — `/alerts/anomaly`·`/alerts/daily-summary`·`/alerts/spend-audit` endpoint 박혔지만 (`22b5511`) 호출자 없음. 옵션:
   - A. cron-job.org (무료, 매시간 trigger) — 가장 빠름
   - B. GitHub Actions (workflow_dispatch + schedule) — 통합 깔끔
   - C. Railway scheduler 봉인 해제 + 가드 (5/28 사고 가드 박힌 채) — 위험
   - 권장 A — 안전·빠름. ALERT_API_KEY 박은 후 cron 등록.
2. **Railway env 확인** — `TELEGRAM_BOT_TOKEN`·`TELEGRAM_CHAT_ID`·`ALERT_API_KEY` 다 박혀있는지. 사용자 박았다 함 (2026-06-01).
3. **`/knowin` 일 5건 수동 게시 운영** — 사용자 결정 (2026-06-01): worker 자동 게시 보류. 매일 5개 답변 생성 후 클립보드 복사 → 네이버 게시 → `📌 게시 완료`. 게시 완료 시점 Telegram 알림 박힘 (검수 결과).
4. **Phase 3 광고 카피 daily 자동 생성** — 미시작. 메타·구글 카피 N개 매일 → DRY_RUN 박음 → Telegram 검토 큐 → ✅/❌
5. ~~**키워드 풀 확장**~~ ✅ 완료 (`3687bc0`)
6. **Google Ads API Basic Access 재신청** — `google-ads-api@dotcell.net` 만든 후
7. **Meta Business 계정 reputation 점검** — 5/28 사고 거절 480건 영향

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
| SEO 파이프라인 표준 템플릿화 (QCat 감독 제안) | truck `docs/seo-pipeline.md` 추상화 미진행 | (1) truck 원본 read (2) 표면 무관 부분 추출 (3) `docs/ad_guide/seo_pipeline_template.md` 작성 (4) guide·liveon·business 적용 검토 | 가치 큼, 우선순위 P1 |
| 가드 코드 git commit + push | Railway 재배포로 영구 차단 | `git add config/ web/ .env.ads.example handoff.md marketing_capabilities.md` + commit + push | 메모리상 ad-optimizer auto-push OK |
| LiveOn 광고 진입 (셀러 모집·도라미 영상 in-house batch) | LiveOn 페이업 PG 결제 LIVE 미완 — 광고 → 가입 → 결제 funnel 검증 불가 | 페이업 가맹 통과 (2026-06-01 신청 → 1~2일 심사). 통과 전엔 *콘텐츠 라이브러리 batch* 까지만 | [liveon_capabilities.md](file:///D:/0_Dotcell/0_live_shopping_server/documents/liveon_capabilities.md) |

---

## 최근 변경 (Recent Changes, 누적)

> 신규 항목은 **상단에 추가**. 형식: `[YYYY-MM-DD] 한 줄 요약` + (선택) 세부.

### 2026-06-02
- **Phase 3 카피 batch — chunk 1 (백엔드) 완료·라이브 검증** (`a050de5`)
  - 기존 `/creative/copy/generate` 는 생성만·휘발(저장 X). 갭=[저장→검토큐→Telegram]. knowin 검토 흐름 복제.
  - `creative/copy_briefs.json` brief 풀 (시드 2: 무시동히터·트럭배터리 KR). 보이스·앵글=노대표 편집 영역. routine 이 last_used 순 로테이션(상태=copy_brief_state 컬렉션).
  - `POST /creative/copy/batch` — brief 1건 → generate_copy(**local-vllm 무료 d4win**) → copy_review_queue insert(pending) → Telegram "✍️ 검토 대기 N건".
  - `GET /creative/copy/review/list` (JSON) + `POST /creative/copy/review/{vid}/{accept|reject}`.
  - **라이브 검증**: batch 3변형 생성·저장·Telegram·accept 상태전이 전부 OK (batch e03a5087).
  - DRY_RUN 본질: 생성물은 검토 큐까지만. 게시는 사람 ✅ 후(5/28 가드 유지).
  - **남은 chunk**: ② 검토 카드 UI(copy_review.html, knowin 패턴 복제) ③ routine daily 트리거(ad-daily-checks 에 batch POST 추가 or 별 routine). brief 풀 확장(노대표 보이스).
  - 결정 기록: brief 소스=풀 파일(제품DB자동/온디맨드 중). 생성 provider=local-vllm(무료).
- **외부 cron 결정 → Claude `/schedule` 채택 (cron-job.org 폐기)** —
  - alerts endpoint 호출자 문제를 외부 cron 대신 Claude Code `/schedule` remote routine 으로 해결.
  - 근거: 빈도 낮으면(일 1~2회) 비용 논리 증발 → 시스템 1개(Claude) > 2개(Claude+cron-job.org). 외부 의존 0, endpoint 실패 시 맥락까지 보고, Phase 3 확장 공짜.
  - **routine 생성**: `ad-daily-summary` (id `trig_017HSnj8M8qCAdg6U2mwbxLb`) — 매일 KST 09:00(=UTC `0 0 * * *`), `POST https://adteam.onemsg.net/alerts/daily-summary`, sonnet-4-6, Bash only, repo 無. https://claude.ai/code/routines/trig_017HSnj8M8qCAdg6U2mwbxLb
  - **검증**: 로컬 curl 200 + Telegram [daily] 도착 확인. run-now 접수됨. 정기 첫 실행 06-03 09:04 KST.
  - ✅ **ALERT_API_KEY 활성화 완료** (2026-06-02): 키 생성 → `.env.global` + Railway env 저장 → 검증(무헤더 401·헤더 200). routine `ad-daily-checks` 양쪽 curl 에 `X-Alert-Key` 헤더 박음 (cloud routine 은 env 접근 불가 → 키가 routine config 에 embed, low-blast-radius read/notify 전용). 키 값은 `.env.global` 참조 (handoff/memory 에 기록 금지).
  - 🔌 routine 에 Google Drive 커넥터 자동 첨부됨 (curl 작업엔 불필요, 무해). 거슬리면 clear_mcp_connections.
  - 비용 주의: routine 매 실행 = 풀 CCR 세션 (정액제 한도 소비). 빈도 = 비용. anomaly 추가 시 일 1회 권장 (매시간 X).
- **knowin 매칭 "모두 실패" — 진짜 원인=매처 구조 결함 (`9f844d8`), threshold(`9700960`)는 부차적**
  - ⚠️ 첫 진단 오진 정정: "threshold 0.60 회귀"는 cherry-pick 질문 탓 오진. 라이브 30건 돌려도 0.55 배포 후 여전히 0건 → 라이브 실측으로 진짜 원인 규명.
  - **진짜 원인**: 매처가 관련도를 truck-wiki chunk 점수로 게이트. 이 인덱스는 truck-qa(실제 Q&A)가 위키보다 항상 높게 깔림 → ① top5 전부 QA면 url=None 거절(5톤윙바디 0.591) ② 위키가 낮게 깔리면 QA 0.593인데 wiki 0.538 보고 거절(요소수). 대부분 트럭질문이 QA 우세라 전멸. 과거 12건은 위키가 운좋게 0.55 넘은 소수.
  - **RAG 도달성·threshold 둘 다 무죄**: Railway→d4win 정상(거절 항목 score 0.49~0.70 nonzero). threshold 0.55 복귀도 유효하나 부차.
  - **수정**: 게이트=chunks[0] 전체 top 점수, 인용 위키 URL=top-k 매핑 우선+wiki 전용 검색 폴백. 라이브 시뮬 OLD 7→NEW 13(+86%), 회복분 전부 정상 트럭(4.5톤 프리마·중고화물차·15톤 덤프). 정크(이사·면허)는 거절 유지.
  - **라이브 검증**: 배포 후 match 30건 → matched 3+ 증가 (직전 50/50 전멸 대비). 닫힘.
  - 잔존 별건: 토픽 필터 negative 추가 이전의 승용차 잔재가 큐에 남음(신규 크롤은 필터됨).
- **자동 게시 worker 큐 전면 제거** (`9700960`) — 안 씀(일 5건 수동 게시). UI(카드·버튼·폴링·토스트) + 백엔드(queue-post·post-queue next/report/list·_check_worker_auth) 268줄 삭제. worker/knowin_auto_poster.py 로컬 스크립트만 잔존(웹앱 비의존).

### 2026-06-01
- **Telegram 봇 통합 완료 — Phase 1 (Snow W. Lee AI 마케팅팀 패턴 적용)** (`22b5511`)
  - 채널: "Dotcell 마케팅" (비공개, chat_id=`-1004226271829`)
  - 봇: `@dotcell_mkt_bot`, 토큰 `.env.global` 박힘
  - 헬퍼: `agent/telegram.py` — `notify(text, sender)` + `notify_safe`. silent no-op (env 미설정 시), DRY_RUN 옵션, 예외 안전, plain text (Markdown escape 함정 회피)
  - **knowin 통합**: `_task_finish` 가 crawl/match/backfill/verify 완료 시 통계 요약 알림 (silent), failed 시 큰 알림. `knowin_posted` 가 검수 결과 alert (✅ verified / 🚫 차단 / 👻 ghost / 📌 검수 skip)
  - **alerts endpoint 박힘** (`web/routes/alerts.py`, 215줄):
    - `POST /alerts/anomaly` — knowin ghost 비율·차단 임계·spend 폭증 룰 검사
    - `POST /alerts/daily-summary` — 어제 광고 성과 요약
    - `POST /alerts/spend-audit` — DAILY_BUDGET_CAP 위반 감시
    - 인증: `X-Alert-Key` 헤더 (env `ALERT_API_KEY` 미설정 시 우회)
  - Railway env 박음 (사용자 확인): TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID + (선택) ALERT_API_KEY + (선택) DAILY_BUDGET_CAP
  - **다음**: 외부 cron 박을지 (cron-job.org 권장)
- **Snow W. Lee 패턴 적용 결정** — ad-optimizer 가 이미 Snow 패턴 80% 박혀있음 결론. 처음부터 다시 빌드 X.
  - Phase 1 (Telegram 통합) → 진행 중 ⏳
  - Phase 2 (knowin 자동화) → 사용자 결정: worker 보류, 일 5건 수동
  - Phase 3 (광고 카피 daily 자동 생성 + Telegram 검토 큐) → 미시작
  - Phase 4 (자율 cron, 안전망 박힌 채) → 미시작. handoff 가드레일 #4 "수동 검토 첫 2주" 후
- **knowin 자동 게시 worker 박음 — 보류 결정** (`6aafe69`)
  - `worker/knowin_auto_poster.py` — Playwright sync + 본인 PC 로컬
  - 셀렉터 디버그 (네이버 모바일 답변 form 못 찾음 — `answer form not found`) 어려워서 사용자 보류 결정
  - 일 5개 수동 게시로 대체. 코드는 박혀있어서 향후 셀렉터 잡힌 시점에 재개 가능
  - worker README, .env.example, .gitignore 박힘
- **knowin 거절 → 삭제 + 종료 상태 영구 보호** (`4ac5c96`)
  - 라벨 변경 ❌ 거절 → 🗑 삭제
  - answer-pending 카드 (차단·RAG 미달 등 답변 없는 카드) 에도 삭제 버튼
  - `TERMINAL_STATUSES` 확장: `{posted, rejected, blocked, off_topic}` — 재수집 시 자동 skip
  - 백필 candidates 에서 종료 상태 제외 — status 덮어쓰기 방지
  - knowin_generate 자동 격리: 차단 → status=blocked, RAG 미달 → status=rejected
- **knowin Phase 1 → 1.5 진화** (5/30~6/1 누적 — `3687bc0` 부터 `4ac5c96` 까지 19개 커밋)
  - 인라인 카드 (큐 표 → 카드 리스트, 본문·textarea·액션 다 메인에)
  - 본문 fetcher (description 발췌 동문서답 fix) — `intelligence/knowin_body_fetcher.py`
  - 지식파트너/FAQ 차단 영역 자동 감지 + 격리
  - 본인 ID (nors/live) 답변 자동 감지 → posted 마킹
  - 토픽 필터 (외제 승용차 negative + 트럭 positive) — 8/8 단위 통과
  - 메타 발화 가드레일 ("저희가 보유한 자료" 등 8 패턴 차단)
  - RAG 임계점 0.55 → 0.60
  - 승인 trace + 게시 검수 시스템 (모달 + 클립보드 복사 → Claude 채팅 분석)
  - 페이지 마스킹 list 디버그 (ghost 원인 좁히기)

### 2026-05-30
- **knowin 키워드 풀 67 → 2,436 확장 — Railway P0 막힘 해소** (`3687bc0`) —
  - `data/truck_wiki/` 에 brands·models·parts·symptoms·topics.json 5개 사본 (~9.7MB) repo 내장
  - `agent/knowin_keyword_pool.py` 의 truck wiki / RAG meta path 를 **fallback 후보 리스트** 로 (1순위 = 로컬 vault, 2순위 = repo 내부 사본). `_first_existing()` helper.
  - 로컬 (vault 잡힘): 3,858 / Railway 시뮬 (repo fallback): **2,436** (truck_wiki 2,619 + general 82 dedup)
  - 다음 `/knowin` 사이클부터 키워드 다양성 확보 → reject 80% → 30~40% 예상
  - rag_meta 는 repo 사본 미포함 (필요 시 별도 작업으로 누적)
- **knowin Phase 1 Day-1 실운용 — 357 질문 수집, matched 10 자동 draft** —
  - 네이버 공식 검색 API + RAG 매칭 + LLM 답변 자동 흐름 완성 (`pending → matched → approved → posted`)
  - 자동 draft: matched 처리 시 즉시 `generate_answer` 호출 → `knowin_answers` 컬렉션 insert. 사용자 액션 = 검토·복사·게시·`📌 게시 완료` 클릭만
  - 종료 status (posted/rejected) 재수집 자동 skip + skipped 카운터
  - 진행도 실시간 표시 (`/knowin/tasks` 폴링, 3s)
  - **검증 결과**: 377 수집 / 327 pending / matched 10 / rejected 40 — reject 80%
  - **발견된 막힘**: Railway 환경에 vault 파일 없어서 키워드 풀 67개 (위키 0 + RAG meta 0 + 일반어 82 dedup). 일반어 편향으로 "녹스센서" 같은 한 키워드가 결과 독식. **다음 세션 P0 작업**: `D:\2_QuantumCat\qcat\truck\src\data\wiki\*.json` 5개를 `ad-optimizer/data/truck_wiki/` 로 복사 + `knowin_keyword_pool.py` 가 repo 내부 경로 fallback 으로 읽도록 수정 → 풀 67 → ~2,700.
  - **Railway 빌드 OOM 회피**: `requirements.txt` 에 `--prefer-binary` + `grpcio` 명시 (wheel 강제). 이후 정상 배포.
  - **TemplateResponse 시그니처 일괄 통일** (knowin/seo/rag) — 옛 시그니처가 starlette 최신에서 jinja2 cache key 에러 일으킴.
- **marketing_capabilities.md 신규 작성** — 다른 Claude Code 세션 (OneMessage 앱·qcat-shop·LiveOn 등) 이 ad-optimizer 의 자원(LLM·플랫폼 API·DB·스킬·분석 산출물) 을 활용 가능한지 확인하는 카탈로그. handoff.md(상태)·ad_pipeline.md(구조) 와 별개 역할.
- **자매 세션 협업 시작 — LiveOn + QCat 감독** — (1) LiveOn 세션이 `D:\0_Dotcell\0_live_shopping_server\documents\liveon_capabilities.md` mirror 카탈로그 작성 (commit `6adf585`). (2) QCat 감독 세션이 5 표면 + 6 자산 양방향 협업안 제출. (3) marketing_capabilities.md 에 Section 8 (자매 세션 협업 카탈로그) 신설. (4) 페르소나 도메인 격리 + OneMessage 인프라 마케팅 금지 가드레일 2건 추가. **협업 원칙**: 광고 운영권 = 표면 자율, ad-optimizer = 인프라·실행·모니터링 제공자 (위임 X, 의뢰 O).
- **Cross-Surface 협업 framework 격상** — ad-hoc 액션을 반복 가능한 패턴으로 표준화:
  - `docs/ad_guide/seo_pipeline_template.md` — truck 3일 SEO 구축 추상화 (5 phase + 표면별 우선순위)
  - `docs/ad_guide/cross_surface_framework.md` — 4-Layer 모델 + 새 capability 추가 11단계 체크리스트 + 표면×capability 매트릭스
  - 대시보드 `/seo` `/knowin` 라우트 + 페이지 신설 (다중 표면 인벤토리 내장). nav 항목 추가.
  - `web/main.py` 라우터 등록. base.html nav 확장.
- **네이버 지식인 자동 답글 Phase 1 (수동 검토)** —
  - `agent/knowin_keyword_pool.py` 키워드 풀 자동 생성 (위키 names + RAG headings + 일반어 = 3,858개)
  - `intelligence/knowin_crawler.py` 네이버 공식 검색 API (openapi.naver.com/v1/search/kin.json) — 일 25,000 호출 한도, link 기반 dedup, MongoDB `knowin_questions` upsert
  - `agent/knowin_matcher.py` 질문 → RAG 매칭 → `truck.qcat.kr/wiki/{type}/{slug}` URL 변환 (URL 매핑 부품/차종/증상/Topic/TruckBrand)
  - `agent/knowin_answerer.py` 답변 초안 LLM (local vLLM 우선, Claude 폴백) + 출처 박스 박음 + 가드레일 자동 검증 (5문장+, 광고성 표현 X, 페르소나 박지 X, URL 본문 X)
  - `/knowin` UI 확장 — 큐 통계 + 키워드 검색 트리거 + RAG 매칭 트리거 + 매칭 후보 큐 (점수 정렬)
  - `/knowin/draft/{question_id}` — 답변 초안 생성·표시 + 클립보드 복사 + 승인/거절 액션
  - storage/models.py 인덱스 추가 (`knowin_questions`, `knowin_answers`)
  - Phase 2 자동 게시는 보류 — 첫 2주 수동 검토 + 트럭 카테고리 답변자 전문성 누적 후
- **RAG capability 통합 — qcat-rag 57,359 chunks 활용 가능** —
  - `agent/rag_client.py` 신규 (`get_rag()` 싱글톤 + health/search/query/context_for_copy)
  - `web/routes/rag.py` + `templates/rag.html` — `/rag` 콘솔 (쿼리 테스트 + 광고 카피 context 추출 + 표면별 type 자동 매핑)
  - `~/.claude/skills/ad-copy/SKILL.md` 에 RAG 사용 패턴 추가 (target_surface 별 정확도 보강)
  - `marketing_capabilities.md` Section 2.2 RAG 도메인 지식 신설
  - 서버: d4win qcat-rag (외부 3900 ↔ 내부 3901), v1 dense. v2 hybrid+rerank 자료 수집 중 (사용자 결정 — 미적용)
  - LiveOn 측 rag-backend (port 8080) 는 LiveOn 세션 전담 — ad-optimizer 호출 X
- **차단 해소** — git commit/push 완료 (`52105c6` collab framework + DB guard 커밋). Railway DRY_RUN=true 사용자 세팅 완료.

### 2026-05-28
- **🚨 Railway 자동 스케줄러 사고 발견·차단** — Railway 배포 ad-optimizer 웹앱(`web/main.py` startup hook)이 `.env.global` 의 `DRY_RUN=false` 와 함께 8시간 사이클로 Meta 캠페인 자동 생성 중. 최소 5/25~5/28 3일간 24 사이클 × 20개 = 480개 캠페인 자동 생성 시도. Meta가 crypto policy로 모두 거절 → 실제 출혈 0. **조치**: (1) `.env.global` `DRY_RUN=true` 로 복원 + 사고 주석. (2) Railway 측 환경변수도 사용자가 직접 변경 필요 (.env.global 안 읽음). (3) `web/main.py` 에 `AUTO_START_SCHEDULER` env 가드 + import 충돌(`settings as app_settings`) 수정 완료. 명시적 opt-in 없으면 deploy 만으로 가동 안 함.

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

### 2026-06-01 / Snow W. Lee AI 마케팅팀 패턴 — 처음부터 다시 빌드 X
**무엇**: Snow W. Lee 의 "Claude Code 로 코드 한 줄 없이 마케팅팀 만들기" 글 읽고 ad-optimizer 와 비교. 인프라 80% 이미 박혀있음 결론. Telegram 통합 + Slack 의 cron 박는 거만 갭. 4 Phase 점진 적용.
**왜 그랬나**: Snow 의 `.claude/agents/` 5개 ≈ ad-optimizer 8 광고 스킬. CLAUDE.md·docs/·scripts/·MCP 다 박혀있음. 단 Slack(Telegram) 가시화 + 자율 cron 안전망 부족. 5/28 사고 (Meta 480건 자동 거절) 가 cron 봉인 원인 — Telegram 알림 박혀있었으면 즉시 차단 가능.
**결과**: Phase 1 = Telegram + Phase 2 = knowin 자동화 (보류) + Phase 3 = 광고 카피 daily 자동 + Phase 4 = 자율 cron. 작게 시작.
**교훈**: 기존 인프라 위에 갭만 메우는 게 효율적. Snow 패턴 그대로 베끼지 말고 자기 코드 안의 강점 살리기.

### 2026-06-01 / knowin 자동 게시 worker 박았지만 보류
**무엇**: Playwright + 본인 PC 로컬 worker (`worker/knowin_auto_poster.py`) 박았는데 첫 작업에서 `answer form not found` 에러. 네이버 모바일 답변 form 셀렉터 미스.
**왜 보류**: 셀렉터 디버그 시간 든다 + captcha 위험 + 일 5개면 수동도 충분. 사용자 결정.
**결과**: 일 5개 수동 게시 + worker 코드는 박혀있음. 향후 셀렉터 잡으면 재개.
**교훈**: 자동화 ROI 계산 — 일 5건이면 수동 5분 vs worker 디버그 N시간 + 운영 위험. 작은 양은 수동이 빠를 수도.

### 2026-05-30 / 페르소나 도메인 격리 lock — 광고 자동화 첫 검수 항목 격상
**무엇**: 광고 카피·이미지·TTS 만들 때 페르소나 이름 박기 전 **target_product 확인 의무**. `/ad-copy`·`/creative-brief` 호출 시 필수 입력. 카피 검수 시 페르소나 이름 grep 더블 체크. ad_pipeline.md § "[2] 크리에이티브 단계 — 페르소나 도메인 격리" + marketing_capabilities.md Section 8 가드레일.
**왜 그랬나**: 2026-05-30 truck.qcat.kr 의 `WelcomeNudge.tsx`·`PushNudge.tsx` 에 "🐱 도라미" 잘못 박힘 발견 (약 3일간 production 노출). 원인 = LiveOn 도라미 절대 규칙 (CLAUDE.md) 이 truck 표면 작업 중에도 잘못 적용. 한 회사 (Dotcell) 가 여러 제품 (LiveOn·QCat 생태계·OneMessage) 운영 시 페르소나 혼동 위험. 자매 세션 협업 시작과 *동시에* 박지 않으면 광고 자동화에서 같은 사고 반복.
**결과**: `feedback_persona_domain_isolation.md` 메모리에 4 표면 표 추가 (LiveOn=도라미 / truck·qcat-*=양자냥 / OneMessage=자체 / 중립=박지 X). ad_pipeline.md [2] 크리에이티브 단계의 *첫 검수 항목* 으로 격상.
**교훈**: cross-project capability catalog 도입 시 페르소나·브랜드 도메인 격리 룰을 *동시에* 박아야 함. 자원 활용 ≠ 페르소나 공용.

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
