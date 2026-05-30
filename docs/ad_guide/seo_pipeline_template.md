# SEO 파이프라인 표준 템플릿 — 표면 무관 추상화

> **출처**: `truck.qcat.kr` 2026-05-28~05-30 (3일, 14 commit) 구축 경험 → 추상화
> **대상 표면**: `qcat-guide` · `qcat-business` · `liveon` · 신규 QCat 표면 · OneMessage 랜딩
> **목표**: 새 표면이 SEO 시작할 때 **순서·체크리스트·코드 패턴 재사용**

---

## 0. 핵심 원칙

| 원칙 | 의미 |
|---|---|
| 콘텐츠 자산 = SEO 자산 | 위키·가이드·법률 등 정적 문서가 자연 유입의 80% (truck 검증: Yeti 크롤 60% / 사람 진입 67% = 콘텐츠 페이지) |
| 봇 차단 ≠ SEO 차단 | anon 가입 같은 *액션* 만 막고, robots/페이지/HTML 은 모두 통과시킴 |
| 측정 가시화가 1순위 | 색인 진행·크롤 빈도·전환률 측정 인프라 *먼저* 박음. 그 다음 콘텐츠 최적화 |
| GPT 외부 fetch + Claude 내부 read | 두 도구 strength 결합 (자기 한계 명시가 협업 효율 ↑) |

---

## 1. 적용 순서 (5 phase)

```
Phase 1 (1일)  →  메타 표준화          → SEO foundation
Phase 2 (1일)  →  발견성 인프라        → robots·sitemap·feed·IndexNow
Phase 3 (1일)  →  SSR/SSG 보장        → 동적 페이지 정적 생성
Phase 4 (1일)  →  측정 가시화          → referrer·UTM·web_vitals·/admin
Phase 5 (상시)  →  봇 차단·콘텐츠 보강 → 좀비 사고 fix + WikiFooterCTA 같은 funnel
```

각 phase 끝나면 검증 (다음 phase 진입 조건 명시).

---

## 2. Phase 1 — 메타 표준화

### 2.1 layout.tsx 표준 메타데이터

```typescript
// app/layout.tsx
export const metadata: Metadata = {
  metadataBase: new URL('https://<도메인>'),
  title: {
    default: '<표면 디폴트 제목>',
    template: '%s — <표면 brand>',
  },
  description: '<표면 한 줄 설명>',
  verification: {
    other: {
      'naver-site-verification': '<NAVER_KEY>',
      'google-site-verification': '<GOOGLE_KEY>',
    },
  },
  openGraph: {
    type: 'website',
    locale: 'ko_KR',
    siteName: '<표면 brand>',
    images: [{ url: '/og-default.png', width: 1200, height: 630 }],
  },
  alternates: {
    canonical: '/',
    types: { 'application/rss+xml': '/feed.xml' },
  },
}
```

### 2.2 페이지별 generateMetadata 통일

```typescript
// app/wiki/[type]/[slug]/page.tsx
export async function generateMetadata({ params }): Promise<Metadata> {
  const entry = await loadEntry(params.type, params.slug)
  return {
    title: entry.title,                              // template 가 자동으로 "— <brand>" 추가
    description: entry.summary.slice(0, 160),
    alternates: { canonical: `/wiki/${params.type}/${params.slug}` },
    openGraph: { title: entry.title, type: 'article' },
    twitter: { card: 'summary_large_image' },
  }
}
```

**lib/seo.ts 헬퍼** (재사용 가능):
- `jsonLdArticle(entry)` → `<script type="application/ld+json">` Article 스키마
- `jsonLdBreadcrumb([...])` → BreadcrumbList 스키마
- `pageMetadata(entry, type)` → 위 메타 객체 생성

### 2.3 noindex 처리 — 작성·동적 화면

```typescript
// app/<surface>/edit/page.tsx, /vehicle/new 등
export const metadata: Metadata = { robots: { index: false, follow: false } }
export const dynamic = 'force-dynamic'
```

### ✅ Phase 1 완료 체크리스트

- [ ] `metadataBase` + `template` 설정
- [ ] 모든 콘텐츠 페이지 `generateMetadata` 통일 (title 이중 suffix 제거)
- [ ] 카테고리 허브 페이지 openGraph 추가
- [ ] 작성·관리 화면 `noindex`
- [ ] `lib/seo.ts` 헬퍼 작성 + JSON-LD 적용

---

## 3. Phase 2 — 발견성 인프라

### 3.1 robots.ts — 한국 봇 명시

```typescript
// app/robots.ts
const COMMON_DISALLOW = ['/admin', '/api/', '/me', '/onboarding', '/login', '/settings', '/edit', '/chatroom', '/<auth-required>']

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      { userAgent: '*',          allow: '/', disallow: [...COMMON_DISALLOW, '/_next/'] },
      { userAgent: 'Yeti',       allow: '/', disallow: COMMON_DISALLOW },  // 네이버
      { userAgent: 'Googlebot',  allow: '/', disallow: COMMON_DISALLOW },
      { userAgent: 'Daumoa',     allow: '/', disallow: COMMON_DISALLOW },
      { userAgent: 'Ads-Naver',  allow: '/', disallow: COMMON_DISALLOW },  // 네이버 광고 봇
      { userAgent: 'Blueno',     allow: '/', disallow: COMMON_DISALLOW },  // 네이버 모바일
    ],
    sitemap: `${BASE_URL}/sitemap.xml`,
  }
}
```

### 3.2 sitemap.ts — 동적 생성

`docs/ad_guide/` 참고: truck.qcat.kr 사이트맵 — `src/app/sitemap.ts` 패턴.

핵심:
- 단일 데이터 소스 (`search_index.json` 또는 카테고리별 json)
- `encodeURIComponent(slug)` 한글 slug 처리
- priority 차등 (qaCount/relatedQACount 기반 0.5~0.9)
- 카테고리 허브는 floor 0.8 (구조적 중요도)

### 3.3 RSS feed.xml

```typescript
// app/feed.xml/route.ts
export async function GET() {
  const entries = await loadRecentEntries(50)
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>...</title>
    <link>...</link>
    <description>...</description>
    ${entries.map(e => `<item>
      <title>${escape(e.title)}</title>
      <link>${BASE_URL}/wiki/${e.type}/${e.slug}</link>
      <pubDate>${new Date(e.updated).toUTCString()}</pubDate>
      <description>${escape(e.summary)}</description>
    </item>`).join('')}
  </channel>
</rss>`
  return new Response(xml, { headers: { 'Content-Type': 'application/rss+xml' } })
}
```

### 3.4 IndexNow API — 색인 ping 자동화

```javascript
// scripts/seo/indexnow.mjs
const NAVER_ENDPOINT = 'https://searchadvisor.naver.com/indexnow'
const BING_ENDPOINT = 'https://www.bing.com/indexnow'

const urls = collectAllUrls()  // sitemap 과 동일 소스
const batches = chunk(urls, 100)

for (const batch of batches) {
  for (const endpoint of [NAVER_ENDPOINT, BING_ENDPOINT]) {
    await fetch(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        host: '<도메인>',
        key: process.env.INDEXNOW_KEY,
        urlList: batch,
      }),
    })
    await sleep(1000)  // throttle
  }
}
```

`package.json` 에 `npm run indexnow` 추가.

### ✅ Phase 2 완료 체크리스트

- [ ] `robots.ts` 6 봇 명시 + COMMON_DISALLOW
- [ ] `sitemap.ts` 동적 생성 + priority 차등
- [ ] `/feed.xml` RSS 2.0 dynamic
- [ ] `scripts/seo/indexnow.mjs` + `npm run indexnow`
- [ ] 사이트맵 URL 수 검증 (`tsx -e "import s from ...; console.log(s().length)"`)

---

## 4. Phase 3 — SSR/SSG 보장

### 4.1 정적 생성 — generateStaticParams

```typescript
// app/wiki/[type]/[slug]/page.tsx
export async function generateStaticParams() {
  const out = []
  for (const type of VALID_TYPES) {
    for (const e of loadEntries(type)) {
      out.push({ type, slug: e.slug })
    }
  }
  return out  // build 시 모든 페이지 정적 생성 → 봇 + 사람 모두 빠른 초기 HTML
}
```

### 4.2 동적 페이지 명시

작성·검색·내정보 등 매번 변하는 페이지:
```typescript
export const dynamic = 'force-dynamic'
export const metadata = { robots: { index: false, follow: false } }
```

### 4.3 초기 HTML 검증

빌드 후 색인 가능성 검증:
```bash
npm run build
curl -s http://localhost:3000/wiki/<type>/<slug> | grep -E "<title>|<meta name=\"description\""
# 본문·title·meta 가 초기 HTML 에 있어야 함 (JS 실행 전)
```

### ✅ Phase 3 완료 체크리스트

- [ ] 콘텐츠 페이지 `generateStaticParams` 적용
- [ ] 동적 페이지 `dynamic = 'force-dynamic'` 명시
- [ ] 초기 HTML 에 title·meta·본문·내부 링크 포함 확인
- [ ] 빌드 사이즈 점검 (대량 페이지 시 빌드 시간 길어짐)

---

## 5. Phase 4 — 측정 가시화

### 5.1 첫 진입 referrer + UTM 캡처 (client)

```typescript
// app/components/FirstReferrerCapture.tsx
'use client'
export function FirstReferrerCapture() {
  useEffect(() => {
    if (sessionStorage.getItem('first-referrer-captured')) return
    const ref = document.referrer
    const url = new URL(window.location.href)
    const utm = {
      source: url.searchParams.get('utm_source'),
      medium: url.searchParams.get('utm_medium'),
      campaign: url.searchParams.get('utm_campaign'),
      content: url.searchParams.get('utm_content'),
      term: url.searchParams.get('utm_term'),
    }
    fetch('/api/events/first', {
      method: 'POST',
      body: JSON.stringify({ first_referrer: ref, utm, landing_path: window.location.pathname }),
    })
    sessionStorage.setItem('first-referrer-captured', '1')
  }, [])
  return null
}
```

### 5.2 Web Vitals 자동 계측

```typescript
// app/components/WebVitals.tsx
'use client'
import { useReportWebVitals } from 'next/web-vitals'
export function WebVitals() {
  useReportWebVitals(metric => {
    fetch('/api/events/web-vitals', {
      method: 'POST',
      body: JSON.stringify({
        name: metric.name,  // LCP·FID·CLS·INP·FCP·TTFB
        value: metric.value,
        rating: metric.rating,
        path: window.location.pathname,
      }),
    })
  })
  return null
}
```

### 5.3 /admin/audience 대시보드 4 섹션

```typescript
// 🎯 첫 진입 path TOP
SELECT meta->>'landing_path' AS path, COUNT(*) AS sessions
FROM events
WHERE name = 'first_visit' AND created_at > NOW() - INTERVAL '7 days'
GROUP BY path ORDER BY sessions DESC LIMIT 20;

// 📄 인기 page
SELECT path, COUNT(*) AS views
FROM events
WHERE name = 'page_view' AND created_at > NOW() - INTERVAL '7 days'
GROUP BY path ORDER BY views DESC LIMIT 20;

// 🌐 referrer host
SELECT
  CASE
    WHEN meta->>'first_referrer' = '' THEN '직접 진입'
    ELSE regexp_replace(meta->>'first_referrer', '^https?://([^/]+).*', '\\1')
  END AS host,
  COUNT(*) AS sessions
FROM events WHERE name = 'first_visit' GROUP BY host;

// 📊 UTM 캠페인
SELECT
  meta->'utm'->>'source' AS source,
  meta->'utm'->>'campaign' AS campaign,
  COUNT(*) AS sessions
FROM events
WHERE name = 'first_visit' AND meta->'utm'->>'source' IS NOT NULL
GROUP BY source, campaign;
```

### 5.4 라이브 봇/사람 카드 (5초 refresh)

```typescript
// /admin 홈 — 최근 1시간 UA 분류
const CATEGORIES = {
  '🧑 사람': ua => !isBotUA(ua),
  '🟢 Yeti': ua => /Yeti/i.test(ua),
  '🔵 Googlebot': ua => /Googlebot/i.test(ua),
  '🟡 Daumoa': ua => /Daumoa/i.test(ua),
  '🟠 Bingbot': ua => /Bingbot/i.test(ua),
  '🤖 기타봇': ua => isBotUA(ua) && !/(Yeti|Googlebot|Daumoa|Bingbot)/i.test(ua),
}
```

### ✅ Phase 4 완료 체크리스트

- [ ] `FirstReferrerCapture` + `WebVitals` 컴포넌트 layout 에 mount
- [ ] `/api/events/first` + `/api/events/web-vitals` endpoint
- [ ] `/admin/audience` 4 섹션 + 정렬·기간 필터
- [ ] `/admin` 홈 라이브 봇/사람 카드 (5s refresh)
- [ ] events 테이블 인덱스 점검 (created_at, name, path)

---

## 6. Phase 5 — 봇 차단 (anon 가입만)

### 6.1 lib/bot-detect.ts

```typescript
const BOT_UA_PATTERN = /(Yeti|Googlebot|Bingbot|Daumoa|Baiduspider|YandexBot|SemrushBot|HeadlessChrome|PhantomJS|curl|wget|python-requests)/i

export function isBotUA(ua: string | null | undefined): boolean {
  if (!ua) return true   // UA 빈 값 = 봇으로 간주
  return BOT_UA_PATTERN.test(ua)
}

export function isBotRequest(req: Request): boolean {
  const ua = req.headers.get('user-agent')
  if (isBotUA(ua)) return true
  // 추가 신호 — Sec-Fetch-Site 가 없으면 의심
  if (!req.headers.get('sec-fetch-site')) return true
  return false
}
```

### 6.2 적용 위치 — *액션* 만 차단

| API | 차단? | 이유 |
|---|---|---|
| `/api/me/auto-nickname` | ✅ | 봇이 user 생성 트리거 |
| `/api/anon-session` | ✅ | anon user 생성 |
| `/api/nickname/set` | ✅ | user 메타 수정 |
| `/wiki/<slug>` (페이지) | ❌ | 봇이 읽어야 색인 |
| `/sitemap.xml`, `/robots.txt`, `/feed.xml` | ❌ | 봇 전용 endpoint |

### 6.3 좀비 cleanup (1회 작업)

봇 차단 도입 시 기존 좀비 데이터 cleanup:
```sql
-- 좀비 = events 0건 AND vehicles 0건 (또는 표면별 활동 0건)
DELETE FROM users WHERE id IN (
  SELECT u.id FROM users u
  LEFT JOIN events e ON e.user_id = u.id
  LEFT JOIN <activity_table> a ON a.user_id = u.id
  GROUP BY u.id
  HAVING COUNT(e.id) = 0 AND COUNT(a.id) = 0
);
```

⚠️ 한 번에 전수 X. 백업 후 작은 batch 로.

### ✅ Phase 5 완료 체크리스트

- [ ] `lib/bot-detect.ts` 작성
- [ ] anon 가입 API 분기 적용 (페이지는 절대 차단 X)
- [ ] 좀비 cleanup 1회 (백업 후)
- [ ] 차단 효과 검증 (좀비율 기간별 비교 SQL)

---

## 7. 측정 baseline (1~3일 후)

| 지표 | 측정 SQL / 위치 |
|---|---|
| 색인된 페이지 수 | search-advisor.naver.com 색인 현황 |
| Yeti 일일 크롤 빈도 | `events WHERE ua~Yeti AND name='page_view'` 시간별 |
| 검색어별 노출·CTR | search-advisor.naver.com 검색 노출 리포트 |
| 콘텐츠 → 홈 도달률 | `events session` 별 path sequence |
| Footer CTA 클릭률 | `events WHERE path IN (<entry>) AND referrer LIKE %<content>%` |
| Web Vitals 분포 | `events.meta.web_vitals.{name,value,rating}` 그룹 |
| RSS 구독 | `/feed.xml` 요청 로그 |

---

## 8. 표면별 적용 검토 (운영 우선순위)

| 표면 | SEO 우선순위 | 콘텐츠 자산 | 기대 효과 |
|---|---|---|---|
| `truck.qcat.kr` | ✅ 완료 (2026-05-30) | 위키 696 + 법률 90 | 검증됨 |
| `qcat-guide` | 🟡 P1 | 캠핑·배터리·무시동 히터 가이드 | 자연 유입 — 트럭 패턴 재사용 |
| `qcat-business` | 🟢 P2 | B2B 사업자 가이드 | 한정 검색량, 강한 의도 |
| `qcat-shop` | 🟢 P2 | 상품 페이지 | 네이버 쇼핑 색인이 더 중요할 수도 |
| `qcat-wiki` (`bridge`) | 🟡 P1 | 위키 정본 | RAG 응답 출처 ↔ SEO 시너지 |
| `liveon` (`shoppingliveon.com`) | 🟢 P2 | 셀러 모집 LP | 광고 의존도 높음 |
| `onemsg.net` 랜딩 | 🟢 P3 | 단일 LP | LPV 측정만 우선 |

각 표면 도입 시 이 템플릿의 5 phase 순차 적용 + 표면별 콘텐츠 자산 인벤토리.

---

## 9. 핵심 인사이트 (truck 검증)

1. **콘텐츠 = SEO 자산** — 696 페이지 정적 생성이 자연 유입 만듦. 위키 + 지도가 압도적
2. **봇 차단 ≠ SEO 차단** — anon 가입만 application-level UA 차단. robots·페이지·HTML 모두 통과. 색인 영향 0
3. **측정 신뢰도 회복이 첫걸음** — 좀비 cleanup 전엔 active 의 75%가 봇. 진짜 funnel 측정 불가
4. **intent → purchase 7.5%** (truck 사례) — 도메인 콘텐츠가 영업·SEO 양쪽 자산으로 작동
5. **외부 fetch (GPT) + 내부 read (Claude) 결합** — 자기 한계 명시가 좋은 협업 패턴

---

## 10. 운영 체크리스트 (표면 통과 후)

- [ ] 매주: search-advisor.naver.com 검증 > URL 검사 (콘텐츠 페이지 샘플 5건)
- [ ] 매주: 리포트 > 검색 노출 검색어 베스트 5 추적
- [ ] 신규 콘텐츠 추가 시: `npm run indexnow` 1회
- [ ] 매월: `npm run lighthouse:mobile` 베이스라인
- [ ] 분기: 좀비율 점검 + cleanup (필요 시)

---

## 11. 변경 로그

| 날짜 | 변경 |
|---|---|
| 2026-05-30 | 최초 작성 — `truck/docs/seo-pipeline.md` 추상화. QCat 감독 세션 제안 (`marketing_capabilities.md` Section 8.2). 5 phase + 표면별 우선순위 + 운영 체크리스트 |
