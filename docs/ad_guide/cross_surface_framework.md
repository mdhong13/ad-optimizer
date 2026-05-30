# Cross-Surface Marketing Framework — ad-optimizer 가 다중 표면을 지원하는 패턴

> **목적**: ad-optimizer 가 OneMessage·QCat 5 표면·LiveOn 등 **다중 표면의 공유 마케팅 인프라** 가 되도록 표준화. 새 cross-surface 기능 추가 시 따라야 할 패턴.
>
> **배경**: 2026-05-30 이전엔 다른 세션과의 협업이 *세션 안에서 ad-hoc 액션*. 이걸 **반복 가능한 framework** 로 격상.
>
> **첫 적용**: SEO 최적화 (`/seo`) + 네이버 지식인 답글 (`/knowin`) — 2026-05-30

---

## 0. 핵심 모델 — 4-Layer

```
┌─────────────────────────────────────────────────────────┐
│  Layer 4. 표면 (Surface)                                │
│  truck · guide · business · shop · wiki · liveon · onemsg│
│  → 도메인 콘텐츠·고객·funnel 자기 책임                  │
└─────────────────────┬───────────────────────────────────┘
                      │ 의뢰 (위임 X)
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 3. Cross-Surface Capability                       │
│  SEO 최적화 · 지식인 답글 · 광고 캠페인 · 콘텐츠 배포 ·   │
│  바이럴 · 시장 인텔리전스 · 분석·회고                    │
│  → ad-optimizer 가 표면 무관 도구로 제공                 │
└─────────────────────┬───────────────────────────────────┘
                      │ 표준 패턴 따름
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 2. 표준 자원 (Standard Resources)                  │
│  LLM (Claude · 로컬 d4win) · 광고 플랫폼 API · MongoDB · │
│  스킬 (8 광고 스킬) · 분석 산출물                         │
│  → marketing_capabilities.md Section 2 카탈로그            │
└─────────────────────┬───────────────────────────────────┘
                      │ 가드레일 적용
                      ↓
┌─────────────────────────────────────────────────────────┐
│  Layer 1. 안전·격리 가드                                  │
│  DRY_RUN · AUTO_START_SCHEDULER · forbidden DB ·         │
│  페르소나 도메인 격리 · 예산 캡 · OneMessage 인프라 금지  │
│  → marketing_capabilities.md Section 6                    │
└─────────────────────────────────────────────────────────┘
```

---

## 1. Cross-Surface Capability 표준 패턴

새 capability (예: "유튜브 쇼츠 자동 발행", "구글 검색 노출 추적", "경쟁사 광고 모니터링") 추가 시:

### 1.1 5 산출물 세트

| # | 산출물 | 위치 | 역할 |
|---|---|---|---|
| 1 | **라우트** | `web/routes/<name>.py` | API + 페이지 핸들러 |
| 2 | **템플릿** | `web/templates/<name>.html` | 대시보드 UI |
| 3 | **nav 항목** | `web/templates/base.html` | 진입점 추가 |
| 4 | **표면 인벤토리** | 라우트 안 `SURFACES` 또는 `CAMPAIGNS` 리스트 (추후 MongoDB 컬렉션 이관) | 표면별 상태 추적 |
| 5 | **가이드 문서** | `docs/ad_guide/<name>_<topic>.md` | 사용 패턴·운영 체크리스트 |

### 1.2 표면 인벤토리 표준 필드

```python
{
    "id": "<surface-slug>",          # 표면 식별자
    "name": "<표시명>",
    "domain": "<URL>",
    "priority": "P0|P1|P2|P3",
    "status": "✅ 완료 | 🟡 대기 | 🟢 미진입",
    "content_assets": "<핵심 콘텐츠 설명>",
    "phases_done": [...],            # capability 별 단계
    "last_update": "YYYY-MM-DD",
    "notes": "<자유 노트>",
}
```

### 1.3 가드레일 적용 의무

새 capability 가 광고비·외부 노출·자동화를 동반하면:
- ✅ `DRY_RUN` 환경변수 존중
- ✅ 표면별 페르소나 확인 (`feedback_persona_domain_isolation`)
- ✅ 네이버 비공식 endpoint 시 `feedback_naver_unofficial_caution`
- ✅ OneMessage 인프라 마케팅 채널 사용 금지
- ✅ 새 가드 추가 시 `marketing_capabilities.md` Section 6 + capability 페이지에 노출

---

## 2. 현재 Cross-Surface Capability 목록

| Capability | Route | 표면 지원 | 가이드 문서 | 상태 |
|---|---|---|---|---|
| 광고 캠페인 (Meta·Google·X·Reddit) | `/campaigns` | OneMessage (현재) · LiveOn (예정) · qcat-shop (예정) | `docs/audiences/`, `docs/ad_guide/` 누적 | 🟡 OneMessage live, 다른 표면 대기 |
| 크리에이티브 (스토리보드·이미지·영상) | `/creative/*` | 표면 무관 (target_product 명시) | — | ✅ 작동 |
| 바이럴 봇 (Reddit·트위터·디스코드 etc.) | `/viral` | OneMessage 위주 | — | 🟢 인프라 있음, 표면별 캐릭터 정의 대기 |
| **SEO 최적화** | `/seo` | 7 표면 (truck 완료, guide·wiki 대기, 나머지 미진입) | `docs/ad_guide/seo_pipeline_template.md` | ✅ **신설 (2026-05-30)** |
| **지식인 답글** | `/knowin` | 4 표면 (truck·guide·liveon·onemsg) | (이 문서 + capability 페이지) | ✅ **신설 (2026-05-30)** |
| 콘텐츠 배포 (YouTube·IG·Threads·TikTok·blog) | `/publisher` | 표면 무관 | — | 🟢 인프라, 표면 매핑 대기 |
| 시장 인텔리전스 (크립토·뉴스·경쟁사) | `/events` | OneMessage 위주 (크립토) | — | ✅ 작동 |
| 일간 리포트·이상 감지·예산 감사 | (스킬: `/daily-report` `/anomaly-alert` `/spend-audit`) | 표면 무관 | — | ✅ 스킬로 작동 |
| 캠페인 회고 (학습 누적) | `/decisions` + `/campaign-retro` 스킬 | 표면 무관 | — | ✅ 작동 |

---

## 3. 표면 × Capability 매트릭스

`x` = 적용 / `-` = 해당 없음 / `?` = 검토 중

| 표면 \\ Capability | 광고 | 크리에이티브 | 바이럴 | SEO | 지식인 | 배포 | 인텔리전스 | 리포트 | 회고 |
|---|---|---|---|---|---|---|---|---|---|
| **OneMessage 앱** | x | x | x | x (랜딩) | x | x | x | x | x |
| **truck.qcat.kr** | ? | ? | ? | ✅완료 | ? | ? | - | x | x |
| **qcat-guide** | ? | x | x | 🟡대기 | 🟢대기 | x | - | x | x |
| **qcat-business** | ? | - | - | 🟢미진입 | - | - | - | x | - |
| **qcat-shop** | ? | x | x | 🟢미진입 | - | x | - | x | x |
| **qcat-wiki (bridge)** | - | - | - | 🟡대기 | - | - | - | - | - |
| **LiveOn** | x (PG 통과 후) | x (메타휴먼) | ? | 🟢미진입 | 🟢대기 | x | - | x | x |

→ 빈칸은 향후 표면 자율 결정. ad-optimizer 가 강요 X.

---

## 4. 새 Capability 추가 절차 (체크리스트)

```
1. [ ] 필요성 검증 — 최소 2 표면 활용 시나리오 명확한가?
2. [ ] handoff.md "진행 중" 에 추가
3. [ ] web/routes/<name>.py 작성 (표면 인벤토리 포함)
4. [ ] web/templates/<name>.html 작성 (가드레일 박스 포함)
5. [ ] base.html nav 항목 추가
6. [ ] web/main.py 라우터 등록
7. [ ] docs/ad_guide/<name>_*.md 가이드 작성
8. [ ] marketing_capabilities.md Section 8 또는 신규 섹션에 등록
9. [ ] 가드레일 필요 시 Section 6 추가
10. [ ] handoff.md "최근 변경" 누적 + "진행 중" 에서 제거
11. [ ] git commit + push
```

---

## 5. 표면 추가 절차 (새 표면이 ad-optimizer 활용 시작 시)

```
1. [ ] 해당 표면 세션이 marketing_capabilities.md 읽음
2. [ ] 표면 식별자·도메인·우선순위 결정
3. [ ] 활용할 capability 선택 (SEO만? SEO + 지식인? 전체?)
4. [ ] capability 별 표면 인벤토리에 항목 추가
   - 예: SEO 신규 표면 → web/routes/seo.py SURFACES 에 dict 1개 추가
5. [ ] capability 별 phase 진행 (capability 가이드 문서 따라)
6. [ ] 진행 상태 정기 갱신 (last_update + phases_done)
```

---

## 6. 협업 원칙 재확인 (QCat 감독 세션 2026-05-30 결정)

- **광고 운영권 = 표면 자율** — ad-optimizer 가 100% 받지 않음
- ad-optimizer = **인프라·실행·모니터링 제공자** (위임 X, 의뢰 O)
- 각 표면은 capability 사용 여부·시점·범위 자율 결정
- spend-audit / anomaly-alert / daily-report 안전망은 표면 무관 적용

---

## 7. 진화 방향 (향후)

### 7.1 MongoDB 컬렉션 이관

현재 라우트 안 `SURFACES = [...]` 하드코딩 → MongoDB 컬렉션:
- `seo_surfaces` — SEO 표면 상태
- `knowin_campaigns` — 지식인 캠페인 상태
- `cross_surface_registry` — 통합 표면 인벤토리

→ 각 표면 세션이 자기 표면 상태를 직접 update 가능 (REST endpoint).

### 7.2 표면 자가 등록 API

```
POST /api/surfaces/register
{
  "id": "qcat-guide",
  "name": "qcat-guide",
  "domain": "https://guide.qcat.kr",
  "capabilities_used": ["seo", "knowin", "creative"],
  "contact_session": "<세션 ID 또는 메모리 참조>"
}
```

→ 표면 세션이 "지금부터 ad-optimizer 활용 시작" 신호 보냄.

### 7.3 capability 별 표면 자동 발견

각 capability 페이지가 등록된 모든 표면 자동 표시. 표면 입장에서 "내가 어떤 capability 쓰는지" 한 번에 확인.

---

## 8. 변경 로그

| 날짜 | 변경 |
|---|---|
| 2026-05-30 | 최초 작성 — Cross-Surface Marketing Framework 4-Layer 모델 + 표준 패턴 + 매트릭스. SEO 최적화 + 지식인 답글 신설을 첫 적용 사례로 박음. 새 capability 추가 11단계 체크리스트 |
