"""
SEO 최적화 — 다중 표면 SEO 파이프라인 모니터링·관리

표면 목록 (capabilities 등록 기반):
- truck.qcat.kr        — ✅ 완료 (2026-05-30)
- qcat-guide           — 🟡 P1 (캠핑·배터리·히터 가이드)
- qcat-business        — 🟢 P2 (B2B 사업자)
- qcat-shop            — 🟢 P2 (상품)
- qcat-wiki (bridge)   — 🟡 P1 (위키 정본)
- liveon               — 🟢 P2 (셀러 모집 LP)
- onemsg.net 랜딩       — 🟢 P3
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/seo")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# 표면 인벤토리 — 추후 MongoDB `seo_surfaces` 컬렉션으로 이관 예정
SURFACES = [
    {
        "id": "truck",
        "name": "truck.qcat.kr",
        "domain": "https://truck.qcat.kr",
        "priority": "P0",
        "status": "✅ 완료",
        "content_assets": "위키 696 + 법률 90 + 휴게소·트럭종류",
        "indexed_pages": 821,
        "phases_done": ["meta", "discovery", "ssr", "measurement", "bot_block"],
        "last_update": "2026-05-30",
        "notes": "Yeti 491 paths 크롤 (sitemap 60%). 7.5% intent→purchase",
    },
    {
        "id": "qcat-guide",
        "name": "qcat-guide",
        "domain": "https://guide.qcat.kr",
        "priority": "P1",
        "status": "🟡 대기",
        "content_assets": "캠핑·배터리·무시동 히터 가이드",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "트럭 패턴 재사용 가능",
    },
    {
        "id": "qcat-wiki",
        "name": "qcat-wiki (bridge)",
        "domain": "https://bridge.qcat.kr",
        "priority": "P1",
        "status": "🟡 대기",
        "content_assets": "위키 정본",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "RAG 응답 출처 ↔ SEO 시너지",
    },
    {
        "id": "qcat-business",
        "name": "qcat-business",
        "domain": "—",
        "priority": "P2",
        "status": "🟢 미진입",
        "content_assets": "B2B 사업자 가이드",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "한정 검색량, 강한 의도",
    },
    {
        "id": "qcat-shop",
        "name": "qcat-shop",
        "domain": "https://shop.quantumcat.co.kr",
        "priority": "P2",
        "status": "🟢 미진입",
        "content_assets": "상품 페이지",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "네이버 쇼핑 색인 우선 검토",
    },
    {
        "id": "liveon",
        "name": "shoppingliveon.com",
        "domain": "https://shoppingliveon.com",
        "priority": "P2",
        "status": "🟢 미진입",
        "content_assets": "셀러 모집 LP",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "광고 의존도 높음, SEO 보조 역할",
    },
    {
        "id": "onemsg",
        "name": "onemsg.net",
        "domain": "https://onemsg.net",
        "priority": "P3",
        "status": "🟢 미진입",
        "content_assets": "단일 LP",
        "indexed_pages": 0,
        "phases_done": [],
        "last_update": "—",
        "notes": "LPV 측정만 우선",
    },
]

PHASES = [
    ("meta", "메타 표준화", "metadataBase + template + JSON-LD"),
    ("discovery", "발견성 인프라", "robots + sitemap + RSS + IndexNow"),
    ("ssr", "SSR/SSG 보장", "generateStaticParams + noindex 분기"),
    ("measurement", "측정 가시화", "referrer + UTM + WebVitals + /admin/audience"),
    ("bot_block", "봇 차단", "anon 가입만 UA 차단 (페이지 X)"),
]


@router.get("")
async def seo_overview(request: Request):
    return templates.TemplateResponse(
        "seo.html",
        {
            "request": request,
            "surfaces": SURFACES,
            "phases": PHASES,
            "total_surfaces": len(SURFACES),
            "done_count": sum(1 for s in SURFACES if s["status"].startswith("✅")),
            "in_progress_count": sum(1 for s in SURFACES if s["status"].startswith("🟡")),
            "pending_count": sum(1 for s in SURFACES if s["status"].startswith("🟢")),
        },
    )
