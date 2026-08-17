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
| 네이버 검색광고 | ✅ 읽기·쓰기 검증(08-12 수리) | `qcat/truck/scripts/ads/` + `scripts/lib/naverAd.mjs` |
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

**08-17 수리 착수** — 화면 둘이 거짓 신호를 내고 있었다:
- `/settings` 「Google Ads 연결됨」 초록 = `bool(GOOGLE_ADS_DEVELOPER_TOKEN)`. **키 문자열 유무일 뿐** 실제로는 `PERMISSION_DENIED`. → 실측 프로브로 교체(§5 도구표)
- `/` 「7일 총 지출 $0.00」 = 로컬 Mongo `performance_snapshots` 만 읽음. 그 표를 채우는 스케줄러는 5/28 사고 후 정지(옳음). **0 은 「안 썼다」가 아니라 「아무도 안 적었다」.** 정작 네이버 월 200만원이 화면 밖. → 네이버 파이썬 클라이언트 신설 + 원/달러 분리 표기

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
| shop / business | 없음 | 0 | sitemap·OG·애널리틱스 전무, shop은 mock 상품 | 🔴 **광고 금지** — 측정 불가 상태 |

### OneMessage 재개 선행조건 (순서대로)
1. Meta App ID 결정 — 앱엔 `26414252244902498` 박혀 있는데 handoff 는 "폐기→신규" 기록. **불일치 해소가 먼저.**
2. onemsg.net 에 Meta Pixel 실설치 (스펙만 존재: `docs/pixel/pixel_event_spec.md`)
3. MMP 또는 Firebase 어트리뷰션 확립 — 없으면 APP_INSTALLS 최적화 불가

## 4. 정례 운영 (통합 세션의 루틴)

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
| `ad-optimizer/scripts/platform_healthcheck.py` | 전 플랫폼 읽기 점검 | 08-14 |
| `liveon-leads/collect.py` | 셀러 리드 수집(차단감지 포함) | 08-12 |
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

**대기 (노대표 액션)**
- [ ] `google-ads-api@dotcell.net` 생성 → Google Ads Basic Access 재신청 (2026-08-16 「며칠 후에」)
- [ ] Meta App ID 폐기/유지 결정 (OneMessage 재개의 첫 단추)
- [ ] 자동 고양이 화장실 첫 판매 — 라이브 방송 검토

**종결된 결정 (2026-08-16 노대표)**
- ✅ 커머스 API 키 로테이션 — **불필요**(이력 잔존분 수용). 앞으로 중앙 저장소 관리 원칙 유지
- ✅ 카페 크롤러 로그인 세션 — **예외 인정**, 계속 사용. 조건은 `naver_crawl_policy.json` 의 `login_session_exceptions` 에 명문화(세션 커밋 금지·속도 정본 준수·차단 시 즉시 정지·공개 게시글만)

**보류 (조건부)**
- [ ] shop/business SEO 기본기(sitemap·robots·OG·GA4) — shop 실상품 연동 후에만 의미
- [ ] X·Reddit Ads 승인 — OneMessage 재개가 먼저
- [ ] 주간 점검 클라우드 루틴화 — 수동 2~3회 돌려 안정 확인 후
