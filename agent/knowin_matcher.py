"""
네이버 지식인 질문 → truck.qcat.kr 위키 매칭

흐름:
  question (text)
    → RAG search (types=['truck-wiki', 'truck-qa'])
    → top-k chunks (score 정렬)
    → 가장 점수 높은 truck-wiki source → 위키 URL 변환
    → return WikiMatch (url, title, score, citation_chunks)

URL 매핑:
  TruckQA/_위키/{카테고리}/{slug}.md → https://truck.qcat.kr/wiki/{type}/{slug}

매핑 표:
  부품 → part
  차종 → model
  증상 → symptom
  Topic → topic
  TruckBrand → brand   (※ slug는 한글 그대로 — 라우트가 308 redirect 처리)

⚠️ 페르소나 도메인 격리 (feedback_persona_domain_isolation):
   truck 표면 = 양자냥. 답변 카피에 도라미 박지 X.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import quote

from .rag_client import get_rag, RAGError

TRUCK_BASE_URL = "https://truck.qcat.kr"

# 위키 디렉토리 (한글) → URL type (영문)
WIKI_TYPE_MAP = {
    "부품": "part",
    "차종": "model",
    "증상": "symptom",
    "Topic": "topic",
    "TruckBrand": "brand",
}

# 매칭 threshold — 너무 낮으면 무관한 답변 자동 생성 위험
DEFAULT_MIN_SCORE = 0.55
DEFAULT_TOP_K = 5


@dataclass
class WikiMatch:
    """매칭 결과 — 답변 생성에 필요한 모든 정보"""
    url: Optional[str]            # truck.qcat.kr 위키 URL (없으면 매칭 실패)
    wiki_type: Optional[str]      # part/model/symptom/topic/brand
    slug: Optional[str]           # URL 의 마지막 segment
    title: str                    # 위키 페이지 제목 (heading 또는 slug)
    top_score: float              # 최상위 chunk score
    citation_chunks: list[dict] = field(default_factory=list)
    # 답변 생성용 raw context (top-k chunks 본문)
    rag_context: str = ""

    @property
    def matched(self) -> bool:
        return self.url is not None and self.top_score >= DEFAULT_MIN_SCORE


def source_to_wiki_url(source: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """source path → (url, wiki_type, slug)

    예: 'TruckQA\\_위키\\Topic\\운송·적재.md'
      → ('https://truck.qcat.kr/wiki/topic/운송·적재', 'topic', '운송·적재')
    """
    parts = source.replace("\\", "/").split("/")
    # 기대 형식: TruckQA/_위키/<카테고리>/<slug>.md
    if len(parts) < 4:
        return None, None, None
    if parts[1] != "_위키":
        # truck-qa 본문 등 위키 아님
        return None, None, None
    category = parts[2]
    wiki_type = WIKI_TYPE_MAP.get(category)
    if not wiki_type:
        return None, None, None
    filename = parts[-1]
    if not filename.endswith(".md"):
        return None, None, None
    slug = filename[:-3]  # .md 제거
    # URL 에선 percent-encode (한글 안전)
    url = f"{TRUCK_BASE_URL}/wiki/{wiki_type}/{quote(slug, safe='')}"
    return url, wiki_type, slug


def match_question(
    question_text: str,
    top_k: int = DEFAULT_TOP_K,
    min_score: float = DEFAULT_MIN_SCORE,
) -> WikiMatch:
    """질문 텍스트로 truck 위키 매칭.

    질문이 위키로 답할 수 없으면 matched=False (url is None 또는 score 미달).
    """
    rag = get_rag()
    try:
        # truck-wiki 우선, truck-qa 보조 (QA 본문에 위키 참조 있을 수 있음)
        chunks = rag.search(question_text, top_k=top_k, types=["truck-wiki", "truck-qa"])
    except RAGError:
        chunks = []

    if not chunks:
        return WikiMatch(url=None, wiki_type=None, slug=None, title="(no match)", top_score=0.0)

    # 최상위 truck-wiki chunk 찾기
    wiki_hits = [c for c in chunks if c.get("type") == "truck-wiki"]
    primary = wiki_hits[0] if wiki_hits else chunks[0]

    source = primary.get("source", "")
    url, wiki_type, slug = source_to_wiki_url(source)
    top_score = float(primary.get("score", 0.0))

    # title — heading 우선, 없으면 slug, 없으면 source basename
    title = primary.get("heading") or slug or source.split("\\")[-1].split("/")[-1]

    # 답변 생성용 context — top-k 본문 압축 (max 200자/chunk)
    ctx_lines = []
    for c in chunks[:top_k]:
        h = c.get("heading") or ""
        t = (c.get("text") or "")[:300]
        ctx_lines.append(f"[{h}]\n{t}")
    rag_context = "\n\n---\n\n".join(ctx_lines)

    return WikiMatch(
        url=url,
        wiki_type=wiki_type,
        slug=slug,
        title=title,
        top_score=top_score,
        citation_chunks=chunks[:top_k],
        rag_context=rag_context,
    )


if __name__ == "__main__":
    # smoke test
    samples = [
        "프리마 280 DPF 클리닝 비용 얼마나 들어요?",
        "5톤 윙탑 차량 9.8m 와 10.2m 차이가 뭐예요?",
        "녹스 센서 교체 주기가 어떻게 되나요?",
    ]
    for q in samples:
        m = match_question(q)
        print(f"\nQ: {q}")
        print(f"   matched: {m.matched}")
        print(f"   url:     {m.url}")
        print(f"   title:   {m.title}")
        print(f"   score:   {m.top_score:.3f}")
