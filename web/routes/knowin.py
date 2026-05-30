"""
네이버 지식인 자동 답글 — 바이럴 확장 (다중 표면 지원)

목표: 각 표면의 도메인 키워드로 지식인 질문 모니터링 + 자동 답글 생성·게시 (옵션).

표면별 활용:
- truck    — 화물·정비·법률 QA → 위키 페이지 링크
- guide    — 캠핑·배터리·히터 QA → 가이드 페이지 링크
- liveon   — 라이브 쇼호스트 솔루션 QA → 셀러 모집 LP
- onemsg   — 안심메시지·고독사 예방 QA → 앱 스토어

⚠️ 네이버 비공식 endpoint 사용 시 [[feedback_naver_unofficial_caution]] 원칙:
   - 자기 데이터만 자동화
   - 정식 라인 (공식 답변자) 병행
   - 인증·보안 원칙
   - 스팸 의심 패턴 회피 (속도 throttle, 다양성)
"""
from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

router = APIRouter(prefix="/knowin")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# 표면별 지식인 작전 — 추후 MongoDB `knowin_campaigns` 컬렉션으로 이관
SURFACE_CAMPAIGNS = [
    {
        "id": "truck",
        "surface": "truck.qcat.kr",
        "keywords": ["화물차 정비", "트럭 부품", "DPF", "EGR", "5톤 카고", "노부스", "마이티"],
        "answer_link_base": "https://truck.qcat.kr/wiki",
        "persona": "양자냥",
        "status": "🟢 미가동 (인프라 분업 협의 중)",
        "expected_volume": "주 50~100 질문",
        "notes": "truck 세션과 인프라 분업 논의 중",
    },
    {
        "id": "qcat-guide",
        "surface": "qcat-guide",
        "keywords": ["캠핑 배터리", "무시동 히터", "차박 전원", "파워뱅크", "디젤 히터"],
        "answer_link_base": "https://guide.qcat.kr",
        "persona": "양자냥",
        "status": "🟢 미가동",
        "expected_volume": "주 30~50 질문",
        "notes": "캠핑 시즌(3~10월) 집중 운영",
    },
    {
        "id": "liveon",
        "surface": "shoppingliveon.com",
        "keywords": ["라이브 커머스", "쇼호스트 솔루션", "AI 호스트", "라이브 자동화"],
        "answer_link_base": "https://shoppingliveon.com",
        "persona": "도라미",
        "status": "🟢 미가동 (페이업 통과 후)",
        "expected_volume": "주 10~20 질문",
        "notes": "베타 단계라 답변 조심스럽게",
    },
    {
        "id": "onemsg",
        "surface": "onemsg.net",
        "keywords": ["고독사 예방", "독거 노인 안심", "휴대폰 미사용 알림", "자녀에게 자동 메시지"],
        "answer_link_base": "https://onemsg.net",
        "persona": "자체 브랜드",
        "status": "🟢 미가동",
        "expected_volume": "주 5~15 질문",
        "notes": "민감 주제 — 카피 검수 필수, OneMessage 메시지 본문 노출 금지",
    },
]


GUARDRAILS = [
    "네이버 비공식 endpoint 자동화 시 자기 데이터·정식 라인 병행·인증 보안 원칙 (feedback_naver_unofficial_caution)",
    "페르소나 박기 전 표면 확인 — truck/guide=양자냥, liveon=도라미, onemsg=자체 브랜드 (feedback_persona_domain_isolation)",
    "답글에 OneMessage 메시지 본문 노출 금지 (feedback_onemsg_no_body_exposure)",
    "throttle — 답변 간 최소 30분 간격, 일일 최대 20건",
    "다양성 — 동일 카피 반복 금지. LLM 변형 필수",
    "투명성 — 답변 끝 '본인이 운영하는 사이트' 명시 (네이버 광고 규정)",
]


@router.get("")
async def knowin_overview(request: Request):
    return templates.TemplateResponse(
        "knowin.html",
        {
            "request": request,
            "campaigns": SURFACE_CAMPAIGNS,
            "guardrails": GUARDRAILS,
            "active_count": sum(1 for c in SURFACE_CAMPAIGNS if c["status"].startswith("🟢") is False),
            "total_count": len(SURFACE_CAMPAIGNS),
        },
    )
