# 닷셀 통합 마케팅 — 헌장 (2026-08-16 위임)

> 노대표 위임(2026-08-16): 프로젝트별로 흩어져 있던 마케팅을 **한 세션이 통합 관리**한다.
> 앞으로 추가되는 프로젝트도 포함. 이 문서 = 자산 지도 + 거버넌스. 상태 변화는 [handoff.md](handoff.md)에 누적.

---

## 1. 원칙 — 집행은 제품별, 감시는 통합

- **집행(카피·타겟·캠페인)은 제품별로 분리한다.** 트럭 기사·앱 사용자·쇼핑라이브 셀러는 다른 사람이다. 합치면 카피가 평균화되고, 평균화된 카피는 아무한테도 안 꽂힌다.
- **감시(지출·성과·연결 상태)는 통합한다.** "이번 달 광고비 총 얼마"에 한 곳에서 답할 수 있어야 한다.
- **ad-optimizer 는 삭제하지 않는다 — 통합 허브로 승격.** 근거: 유일하게 작동하는 Meta 클라이언트, Play 스토어 업로더+등록 자산 전체, 카피 엔진, knowin 시스템, Telegram 알림 인프라, Railway 서버(adteam.onemsg.net, 살아있음 확인 2026-08-16)가 전부 여기 있다. 삭제하면 OneMessage 마케팅 자산이 통째로 사라진다.

## 2. 안전 규칙 (헌법급 — 5/28 사고 재발 방지)

1. **자동 집행 금지.** 2026-05-28 스케줄러 자동 기동 → Meta 거절 480건 사고. `AUTO_START_SCHEDULER` 기본 false 유지. 생성·게시는 사람 승인 후.
2. **돈이 나가는 변경은 dry-run → 노대표 승인 → `--apply`.** 예외 없음.
3. **읽기 점검은 주기적으로 실제 실행.** "코드가 있다 ≠ 작동한다" — 네이버 stats.mjs 는 6개월간 한 번도 성공한 적 없었고(ids 형식 버그), 아무도 몰랐다. → `scripts/platform_healthcheck.py` 주 1회.
4. **네이버 크롤링은 `D:\0_Dotcell\naver_crawl_policy.json` 정본을 따른다.** 차단 페이지는 HTTP 200으로 온다 — 본문 감지 필수.

## 3. 자산 지도 (2026-08-16 실측)

### 플랫폼 연결
| 플랫폼 | 상태 | 위치 |
|---|---|---|
| 네이버 검색광고 | ✅ 읽기·쓰기 검증(08-12 수리) · **08-17 읽기 전용 파이썬 클라이언트 추가 → 통합 대시보드에 연결** | 집행=`qcat/truck/scripts/ads/` + `scripts/lib/naverAd.mjs` · 조회=`ad-optimizer/platforms/naver_ads.py` |
| Meta | ✅ 읽기 검증(08-14 `act_` 수리) — 캠페인 20개 | `ad-optimizer/platforms/meta.py` |
| Google Ads | ❌ PERMISSION_DENIED — **@dotcell.net 이메일로 Basic Access 재신청** 필요(개인 Gmail 거절 이력) | `ad-optimizer/platforms/google_ads.py` |
| X | ❌ Ads API 미승인 (`TWITTER_ADS_ACCOUNT_ID` 없음) | `ad-optimizer/platforms/twitter.py` |
| Reddit | ❌ 키 미발급 | `ad-optimizer/platforms/reddit.py` |
| 네이버 오픈API(지식iN) | ✅ 공식 계약 — 일 25,000 한도, 5 RPS 사용 | `ad-optimizer/intelligence/knowin_*` |
| 네이버 커머스 API | ✅ 실사용 (한정판매 퍼널·재고연동) | `qcat/truck/src/lib/naver-commerce.ts` |
| YouTube Data API | ✅ 댓글 자동수집·답글 + Q&A 위키화 | `qcat/qcat-bridge` + `QCat_Wiki/fetch_youtube.js` |

**추가 자산(08-16 정정 조사)**: qcat-guide `sale.ts` 전환 퍼널(클릭추적·게이트·리다이렉터 방어 — 유료 트래픽 랜딩 전제 설계), 매거진 19편(콘텐츠 마케팅), 네이버 카페 크롤러(`QCat_Wiki/scripts/cafe/` — **로그인 세션 사용. 노대표 예외 인정(08-16)**, 조건은 `naver_crawl_policy.json` 의 `login_session_exceptions`).

### 🖥 운영 콘솔 — adteam.onemsg.net (08-17 실측)

`ad-optimizer/web/` = FastAPI 대시보드, Railway 배포, **화면 16개 전부 정상**. HTTP Basic 인증(`ADMIN_USERNAME/PASSWORD`), `/health`·`/privacy`·`/alerts`·`/assets`·`/static` 만 예외.

| 상태 | 화면 | 실물 |
|---|---|---|
| 🟢 작동 | 지식인 답글 | 수집 957 · 게시 15 · 검수통과 14 · 유령 0 |
| 🟢 작동 | SEO 파이프라인 | 표면 7 추적 · truck.qcat.kr 색인 821p 완료 |
| 🟢 작동 | RAG 콘솔 | 광명 `ok` · 59,209 chunks · 5표면 매핑 |
| ⚪ 빈 통 | 바이럴 · 배포 · 결정 | 0건. 돈도 사고도 안 남 → **그대로 둔다** |
| 🟡 낡음 | 크립토 이벤트 | 마지막 기록 2026-04-15(4개월). 스케줄러엔 「매 1시간」 등록만 돼 있음 |

**08-17 수리 완료·배포됨**(`439c10b`) — 화면 둘이 거짓 신호를 내고 있었다:
- `/settings` 「Google Ads 연결됨」 초록 = `bool(GOOGLE_ADS_DEVELOPER_TOKEN)`. **키 문자열 유무일 뿐** 실제로는 `PERMISSION_DENIED`. → `web/services/platform_status.py` 신설. 초록은 **실호출 성공에만**, 키만 있으면 「키 있음 · 미점검」. 키/클라이언트/실호출 3축 분리 + 실패 사유 노출 + 「마지막 점검 N분 전」 + [지금 점검]
- `/` 「7일 총 지출 $0.00」 = 로컬 Mongo `performance_snapshots` 만 읽음. 그 표를 채우는 스케줄러는 5/28 사고 후 정지(옳음). **0 은 「안 썼다」가 아니라 「아무도 안 적었다」.** 정작 네이버 월 180만원이 화면 밖. → `platforms/naver_ads.py` 신설(읽기 전용) + 원/달러 분리 + 0건이면 숫자 대신 「수집 안 함」
- 🩸 **저장된 Meta 스냅샷도 원화인데 템플릿이 `$` 하드코딩**이었다(cpc 162.99 = 163원). `$0.00` 은 이중으로 틀린 값이었다. 컬렉션에 `currency` 필드가 없어 「통화 미기록」으로 표기

**운영 실측(2026-08-17 16:42, adteam.onemsg.net)** — 실호출 성공 **7/8**, 실패 1건(Google Ads):

| | 결과 |
|---|---|
| 네이버 검색광고 | 🟢 캠페인 28개 · 421ms · **7일 744,153원 / 30일 1,819,945원** (ROAS 31.4배 / 32.9배) |
| Meta · MongoDB · QCat RAG · Local LLM | 🟢 전부 호출 성공 |
| Google Ads | 🔴 `PERMISSION_DENIED` — **MCC 하위 계정 권한 문제**. `User doesn't have permission to access customer`(ClientCustomerId 7958648888, login-customer-id 4894234221). **Basic Access 재신청과 별개 건**이므로 같이 정리할 것 |

**🎁 점검기가 첫날 잡은 것** — Railway 의 `LOCAL_LLM_BASE_URL` 이 `http://d4win.iptime.org:31088` 로 낡아 있었다. iptime DDNS 는 사무실 안에서만 열리므로 클라우드에서는 `No route to host` 로 영영 닿지 않는다. **로컬은 성공 · 운영은 실패** — 화면을 안 보면 알 수 없는 종류다(카피 엔진이 조용히 폴백 중이었을 가능성). `.env.global` 값(`https://api.shoppingliveon.com/infer/vllm`)으로 교정 → 🟢.

⚠️ **Railway 변수는 스테이징된다** — Variables 에 넣기만 하면 반영 안 되고, 상단 배너의 **Deploy** 를 눌러야 적용된다. 누르기 전에는 GraphQL `variables` 조회에도 안 잡힌다(08-17 두 번 헛돌았다).

### 💰 MD홍 Meta 광고계정 — 08-17 발굴 (자산 지도에 없던 것)

`act_659784790884319` (라벨 「MD홍」). 툴엔 계정 2개가 등록돼 있었는데 활성은 One MSG 쪽이라 안 보였다.

```
전체기간 지출  31,782,328원   (2023-07 ~ )
노출          16,247,377      클릭 116,742  → CTR 0.72%
캠페인 28개 · 전부 2026-04-19 정지 · 활성 0 · 90일 지출 0
```

상품군 = **구매대행 시절**(이보드·로봇청소기·물걸레청소기·디지털액자·CD플레이어·미니피아노). 지금 QCat 과 겹치는 건 「주행충전기」 하나뿐.

- 돈은 안 샌다(90일 0) — 급한 건 없다
- **가치는 3,178만원어치 Meta 학습 데이터**: 픽셀 이력·유사타겟 시드가 살아 있다면 OneMessage 재개 때 맨땅 출발을 피할 수 있다 → 재개 선행조건 ③(어트리뷰션)의 실마리
- 참고: One MSG 계정(`act_481473468715453`)은 전체기간 382,373원 · 캠페인 20개 전부 정지(5/28 사고분)
**보안(08-16 수리)**: 커머스 API 키 하드코딩·네이버 세션 파일이 qcat 저장소에 커밋돼 있던 것 제거(`ced748a7`). git 이력에 잔존하나 **노대표 판단으로 로테이션 안 함**(08-16). 앞으로 키는 `.env.global` 중앙 저장소만 사용.

### 제품별 현황
| 제품 | 채널 | 월 지출 | 성과 | 판단 |
|---|---|---|---|---|
| **QCat**(MD홍·퀀텀캣) | 네이버 쇼핑검색 | ~200만원 | ROAS 3,000~6,000% (3월부터 계절 점프) | 🟢 유지+주간 점검 |
| **OneMessage** | Meta(정체)·Google(중단) | ~0 | 4~5월 검색광고 출혈 210만 회수불가 → 중지 | 🟡 재개 전 선행조건 3개 |
| **LiveOn** | 광고 없음 — 콜드메일 영업 | 0 | 리드 100건·열정맨 등급·문안 5종 구축(08-12) | 🟢 발송 실행 단계 |
| **shop**(quantumcat.co.kr) | 없음 | 0 | 🔄 **2026-09-16 분류 정정** — 「mock 상품·측정 0」은 낡았다. 라이브 카페24 몰에 붙어 돌고, AI 상담(용희) **실물 상담 141건** · 업체 네이버 로그인(89명 중 31곳 업체) · 상담 접수함 실사용 | 🟡 **광고 금지의 근거는 사라졌다**(켜자는 뜻 아님 — 켤지는 별도 판단). 지금 가치는 광고 집행보다 **1차 자료**: `shop/config/lexicon.json` |
| business | 없음 | 0 | sitemap·OG·애널리틱스 전무 | 🔴 **광고 금지** — 측정 불가 상태 |

### OneMessage 재개 선행조건 (순서대로)
1. Meta App ID 결정 — 앱엔 `26414252244902498` 박혀 있는데 handoff 는 "폐기→신규" 기록. **불일치 해소가 먼저.**
2. onemsg.net 에 Meta Pixel 실설치 (스펙만 존재: `docs/pixel/pixel_event_spec.md`)
3. MMP 또는 Firebase 어트리뷰션 확립 — 없으면 APP_INSTALLS 최적화 불가

## 4. 정례 운영 (통합 세션의 루틴)

- **매일 (자동)**: LiveOn 리드 수집 — 미니PC(`minipc-owkhu`) 작업 스케줄러 `LiveOnLeadCollect` 매일 10:00. 사람이 기억할 일이 아니다(2026-08-12→08-18 닷새 유실이 그 증거). 빠지면 세션 시작 훅이 한 줄로 알린다
- **주 1회 (월요일)**: ① `platform_healthcheck.py` ② 네이버 `stats.mjs --days 7` ③ Meta 캠페인 지출 확인 → 이상 시 즉시 보고, 아니면 3줄 요약
- **월 1회**: `history.mjs --months 3` — 월별 ROAS·캠페인별 누적, 손익 재계산(마진율 반영)
- **분기 1회**: 죽은 캠페인 정리(전환 0 장기), 계절 상품 ON/OFF (온열매트·무시동히터 11월 ON)

## 5. 도구 인벤토리 (검증일)

| 도구 | 하는 일 | 검증 |
|---|---|---|
| `qcat/truck/scripts/ads/history.mjs` | 네이버 월별 히스토리+ROAS | 08-12 |
| `qcat/truck/scripts/ads/products.mjs` | 쇼핑광고 상품 단위 성과 | 08-14 |
| `qcat/truck/scripts/ads/toggle_product.mjs` | 상품 ON/OFF (dry-run 기본) | 08-14 |
| `qcat/truck/scripts/ads/set_product_bids.mjs` | 상품별 입찰 분리 (10원 단위·type 필수) | 08-14 |
| `ad-optimizer/scripts/platform_healthcheck.py` | 전 플랫폼 읽기 점검(CLI). 로직은 `web/services/platform_status.py` 공유 | 08-17 |
| `ad-optimizer/web/services/platform_status.py` | **연결 상태 정본** — 실호출 판정·3축 분리·병렬·캐시. `/settings` 와 CLI 가 같은 것을 본다 | 08-17 운영 |
| `ad-optimizer/platforms/naver_ads.py` | 네이버 지출·전환 조회(읽기 전용). `get_spend(days)` → 원화 | 08-17 운영 |
| `liveon-leads/collect.py` | 셀러 리드 수집(차단감지 포함). **08-18 미니PC 단독 이관** · 제품 수집기와 HALT 플래그 공유 · 매일 10:00 자동 | 08-18 운영 |
| `liveon-leads/check_today.py` | 「오늘 수집 돌았나」 — 세션 시작 훅이 부른다(Mongo 기준이라 이관에 안 흔들림) | 08-18 |
| `ad-optimizer/.../play-upload.mjs` | Play 스토어 리스팅 업로드 | 미검증(코드만) |
| 스킬 8종(ad-copy·ab-test·spend-audit…) | 카피·실험·감사 | 문서 기반 — API 의존부는 위 상태 따름 |

## 6. 백로그 (우선순위순)

**🎉 첫 성과 (2026-08-16)**
- LiveOn 열정맨 문안으로 메일 발송 → **터치그라운드 미팅 성사**. 리드 수집→등급→문안 파이프라인이 실제 미팅으로 이어진 첫 사례.
  - 터치그라운드 = 라이브 1,407회 · 알림 1,942 · 시청중앙 121 · **주문중앙 0** (전형적 열정맨)
  - 교훈: 「주문 없다」를 말하지 않고 노동을 우리 얘기로 쓴 문안이 먹혔다 → 이 원칙 유지

**진행 중**
- [ ] **900Ah — 노대표 판단으로 유지**(2026-08-16). 8월 매출 0·광고비 계속 나가는 상태이므로 9월 초 재평가 필요
- [x] 돌돌이 정지 완료(2026-08-16 API 실행·실물 확인). ⚠️ 노대표가 콘솔에서 껐다고 인지했으나 실제로는 안 꺼져 있었다 — **콘솔 조작 후에는 API 로 실물 확인**이 필요하다는 사례
- [ ] 텐트 — 노대표 직접 확인 중 (입찰 280원 적용 상태)
- [ ] 숨숨집 — 상품명 수정 확인됨(「퀀텀캣 고양이 숨숨집 터널형」). **여전히 PENDING** → 콘솔에서 「재검토요청」 버튼 눌러야 심사 시작. 입찰 1,300원 대기 중

**🆕 제외 검색어 — 2026-09-16 조사 결과 (승인 대기)**

쇼핑검색광고는 키워드를 우리가 고르지 못하므로 **제외 검색어가 유일한 조준 장치**인데 현재 **0건**(`GET /ncc/adgroups/{id}/restricted-keywords`).

🩸 근거 데이터의 사각지대: 검색어 보고서 `EXPKEYWORD` 는 **파워링크 전용**이다. 우리 활성 파워링크는 30일 **5,866원(0.3%)** 이고, 돈의 99.7% 는 쇼핑검색광고인데 거기는 `AD_DETAIL` 의 검색어 칸이 `-` 로 비어 있고 `master-reports` 에도 검색어 항목이 없다. → **넓은 제외는 여전히 금지**(무엇이 죽었는지 볼 방법이 없다).

✅ 예외적으로 안전한 것 = **「우리가 아예 안 파는 물건 이름」**. 큐캣 세션이 넘긴 `shop/config/lexicon.json` 의 `traps` 는 상담 141건에서 실제로 「우리 물건이 아니다」로 판정된 낱말이고, 광고 소재 **272건 전수 대조에서 충돌 0건**이다:

| 낱말 | 상담에서의 판정 | 우리 상품명 충돌 |
|---|---|---|
| 시동배터리 | 차 시동용 납축 — 우리는 보조(리튬) | 0건 |
| 전기요 · 전기장판 | 깔고 쓰는 매트 — 무시동 히터 아님 | 0건 |
| 등유난로 | 기름 난로 — 무시동 히터 아님 | 0건 |

⛔ **제외하면 안 되는 것**(같은 사전의 `_rejected_terms` + 우리 카탈로그에서 재현): `팬`(무동력팬 8건) · `LED`(11건·노출중 1) · `리퍼`(와이어 스트리퍼) · `버스`(부스바) · `가방`(가방형 파워뱅크). 부분일치로 **우리 상품을 죽인다**.

기대값: 그 검색어로 광고가 떴으면 이득, 안 떴으면 변화 0 → **하방이 없다.**

✅ **매칭 규칙 확인(09-16)** — 쇼핑검색광고 제외 검색어는 **일치**(정확히 같은 검색어만)와 **구문**(같은 순서로 포함된 검색어까지) 두 유형뿐이고 **토큰을 쪼개지 않는다.** 「시동배터리」를 걸어도 「배터리」 단독은 안 막힌다 → 자살골 경로가 구조적으로 없다. 일치로 걸면 거의 안 막히므로 **구문**이 맞다.

🩸 **집행은 API 로 불가 — 콘솔 전용(09-16 실측).** 노대표 승인까지 받고 적용하려다 막혔다:
```
POST /ncc/adgroups/{쇼핑그룹}/restricted-keywords
  → 3728 "campaign type that does not support keyword plus impression restricted keywords"
같은 호출을 파워링크 그룹에 → 1002 Invalid request (유형은 지원, 페이로드만 틀림)
```
이 엔드포인트는 **파워링크의 「키워드 확장 제외」 전용**이다. 대체 경로 6개(`/ncc/ads/{id}/restricted-keywords` · `restricted-shopping-keywords` · `excluded-keywords` …) 전부 404.
→ 돈의 99.7% 를 쓰는 캠페인 유형이 **관측(검색어 보고서)도 집행(제외 등록)도 API 밖**이다. 콘솔에서 사람이 넣어야 한다.

📍 되돌리기 판정용 기준선(적용 전, 2026-09-09~15): AP 벌크그룹 노출 **51,770** · 클릭 772 · 광고비 716,072 · 전환 29(일평균 노출 7,396). 넣은 다음 날 노출이 눈에 띄게 빠지면 즉시 뺀다.

**대기 (노대표 액션)**
- [ ] `google-ads-api@dotcell.net` 생성 → Google Ads Basic Access 재신청 (2026-08-16 「며칠 후에」).
      ⚠️ **08-17 추가 발견**: 승인과 별개로 **MCC 하위 계정 접근 권한 자체가 어긋나 있다**(`PERMISSION_DENIED`).
      재신청할 때 login-customer-id ↔ ClientCustomerId 연결도 같이 정리해야 한 번에 끝난다
- [ ] Meta App ID 폐기/유지 결정 (OneMessage 재개의 첫 단추)
- [ ] 자동 고양이 화장실 첫 판매 — 라이브 방송 검토

**종결된 결정 (2026-08-16 노대표)**
- ✅ 커머스 API 키 로테이션 — **불필요**(이력 잔존분 수용). 앞으로 중앙 저장소 관리 원칙 유지
- ✅ 카페 크롤러 로그인 세션 — **예외 인정**, 계속 사용. 조건은 `naver_crawl_policy.json` 의 `login_session_exceptions` 에 명문화(세션 커밋 금지·속도 정본 준수·차단 시 즉시 정지·공개 게시글만)

**보류 (조건부)**
- [ ] shop/business SEO 기본기(sitemap·robots·OG·GA4) — shop 실상품 연동 후에만 의미
- [ ] X·Reddit Ads 승인 — OneMessage 재개가 먼저
- [ ] 주간 점검 클라우드 루틴화 — 수동 2~3회 돌려 안정 확인 후
