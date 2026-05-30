"""
RAG 쿼리 콘솔 — QCat RAG (배터리·트럭·캠핑·법률) 검색·테스트·광고 prompt enrichment

서버: d4win qcat-rag (외부 3900 ↔ 내부 3901)
인덱스: 57,359 chunks
용도: 광고 카피·지식인 답글·SEO 콘텐츠 시드 prompt enrichment
"""
from fastapi import APIRouter, Request, Form
from fastapi.templating import Jinja2Templates
from pathlib import Path
from typing import Optional

from agent.rag_client import get_rag, RAGError

router = APIRouter(prefix="/rag")
templates = Jinja2Templates(directory=str(Path(__file__).parent.parent / "templates"))


# 표면별 type 매핑 (rag_client.context_for_copy 와 동기)
SURFACE_TYPES = {
    "onemsg": ["truck-qa", "truck-wiki"],
    "guide": ["product", "truck-wiki"],
    "shop": ["product", "cs"],
    "liveon": ["product"],
    "truck": ["truck-qa", "truck-wiki", "truck-law"],
}

ALL_TYPES = ["product", "cs", "truck-qa", "truck-wiki", "truck-law", "camping"]


@router.get("")
async def rag_console(request: Request):
    """RAG 콘솔 진입 — health 상태 + 쿼리 UI"""
    rag = get_rag()
    health = {"status": "?", "chunks": 0, "error": None}
    try:
        health = rag.health()
    except RAGError as e:
        health["error"] = str(e)

    return templates.TemplateResponse(request, "rag.html", {
        "health": health,
        "base_url": rag.base_url,
        "surfaces": list(SURFACE_TYPES.keys()),
        "all_types": ALL_TYPES,
        "result": None,
        "query": "",
        "selected_surface": "",
        "selected_types": [],
        "mode": "search",
        "top_k": 5,
    })


@router.post("")
async def rag_query(
    request: Request,
    query: str = Form(...),
    mode: str = Form("search"),           # 'search' | 'query'
    surface: Optional[str] = Form(None),  # 표면 hint → types 자동 매핑
    types_csv: str = Form(""),            # 수동 type 필터 (콤마 구분)
    top_k: int = Form(5),
):
    """RAG 쿼리 실행 — search (벡터만) 또는 query (LLM 답변 포함)"""
    rag = get_rag()

    # types 결정 — surface 우선, 없으면 수동
    types = None
    if surface and surface in SURFACE_TYPES:
        types = SURFACE_TYPES[surface]
    elif types_csv.strip():
        types = [t.strip() for t in types_csv.split(",") if t.strip()]

    result = {"mode": mode, "ok": False}
    try:
        if mode == "query":
            data = rag.query(query, top_k=top_k, types=types)
            result.update(
                ok=True,
                answer=data.get("answer"),
                needs_human=data.get("needs_human"),
                domain=data.get("domain"),
                intent=data.get("intent"),
                sources=data.get("sources", []),
                chunks=data.get("chunks", []),
            )
        else:
            chunks = rag.search(query, top_k=top_k, types=types)
            result.update(
                ok=True,
                chunks=chunks,
                count=len(chunks),
            )
    except RAGError as e:
        result["error"] = str(e)

    # health 도 같이 보여줌
    health = {"status": "?", "chunks": 0, "error": None}
    try:
        health = rag.health()
    except RAGError:
        pass

    return templates.TemplateResponse(request, "rag.html", {
        "health": health,
        "base_url": rag.base_url,
        "surfaces": list(SURFACE_TYPES.keys()),
        "all_types": ALL_TYPES,
        "result": result,
        "query": query,
        "selected_surface": surface or "",
        "selected_types": types or [],
        "mode": mode,
        "top_k": top_k,
    })


@router.post("/copy-context")
async def rag_copy_context(
    request: Request,
    query: str = Form(...),
    surface: str = Form("onemsg"),
    top_k: int = Form(5),
):
    """광고 카피용 압축 context 추출 — 복사해서 LLM 프롬프트에 박을 수 있게"""
    rag = get_rag()
    try:
        context = rag.context_for_copy(query, target_surface=surface, top_k=top_k)
        result = {"ok": True, "context": context, "char_count": len(context)}
    except RAGError as e:
        result = {"ok": False, "error": str(e)}

    health = {"status": "?", "chunks": 0, "error": None}
    try:
        health = rag.health()
    except RAGError:
        pass

    return templates.TemplateResponse(request, "rag.html", {
        "health": health,
        "base_url": rag.base_url,
        "surfaces": list(SURFACE_TYPES.keys()),
        "all_types": ALL_TYPES,
        "result": None,
        "copy_result": result,
        "query": query,
        "selected_surface": surface,
        "selected_types": SURFACE_TYPES.get(surface, []),
        "mode": "copy",
        "top_k": top_k,
    })
