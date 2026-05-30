"""
QCat RAG 클라이언트 — ad-optimizer 가 도메인 지식 (제품·트럭·법률·캠핑) 활용

서버: d4win `qcat-rag` 컨테이너 (외부 3900 ↔ 내부 3901)
공개 URL: http://d4win.iptime.org:3900
인덱스: 57,359 chunks (Products · CS · TruckQA · TruckLaw · Camping)

용도:
- 광고 카피 생성 시 제품 정확도 ↑ (Q120 1440Wh 같은 정밀 수치)
- 지식인 답글 생성 시 법률·정비 도메인 깊이
- qcat-guide SEO 랜딩 콘텐츠 시드
- OneMessage 트럭 운전자 타겟 카피

⚠️ v2 hybrid+rerank 는 자료 수집 단계 (qcat-rag-v2/). 운영 컨테이너는 v1 (dense).
   카탈로그 쿼리 (제품명) 시 TruckQA 대량 chunks 에 결과 점유 경향 — domain_hint 권장.
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://d4win.iptime.org:3900"
DEFAULT_TIMEOUT = 30  # /query 는 LLM 호출 포함이라 길어질 수 있음


class RAGError(Exception):
    """RAG 호출 실패 (네트워크·서버 오류·잘못된 응답)"""


class RAGClient:
    """qcat-rag v1 REST 래퍼.

    Example:
        >>> rag = RAGClient()
        >>> rag.health()
        {'status': 'ok', 'chunks': 57359}
        >>> hits = rag.search("Q120 배터리 스펙", top_k=5, types=["product"])
        >>> # 제품 도메인 hint 로 TruckQA 노이즈 회피
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = DEFAULT_TIMEOUT,
        admin_token: Optional[str] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("QCAT_RAG_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.timeout = timeout
        # ADMIN_TOKEN: /admin/reload 핫스왑용. 일반 호출엔 불필요
        self.admin_token = admin_token or os.getenv("QCAT_RAG_ADMIN_TOKEN", "")

    # ── 1. 헬스체크 ─────────────────────────────────────────
    def health(self) -> dict:
        """{'status': 'ok', 'chunks': N}"""
        return self._get("/health")

    # ── 2. 벡터 검색 (LLM 비용 0) ─────────────────────────────
    def search(
        self,
        query: str,
        top_k: int = 5,
        types: Optional[list[str]] = None,
        min_score: float = 0.0,
    ) -> list[dict]:
        """순수 벡터 검색. chunks 만 반환 (answer 생성 X).

        types: ['product', 'cs', 'truck-qa', 'truck-wiki', 'truck-law', 'camping'] 부분집합
               None → 전체 도메인
        """
        body = {"query": query, "top_k": top_k, "min_score": min_score}
        if types:
            body["types"] = types
        data = self._post("/search", body)
        return data.get("results") or data.get("chunks") or []

    # ── 3. 검색 + LLM 답변 ───────────────────────────────────
    def query(
        self,
        query: str,
        top_k: int = 5,
        domain_hint: Optional[str] = None,
        types: Optional[list[str]] = None,
    ) -> dict:
        """검색 + vLLM (gemma4-e4b-it) 답변 생성.

        domain_hint: 라우터에 도메인 힌트 전달 ('product', 'qa', 'truck-law' 등)
        types: 검색 단계 type 필터

        반환:
            {
                "answer": str | None,
                "needs_human": bool,
                "domain": str,           # 라우팅 결과
                "intent": str,
                "sources": [str, ...],   # 파일 경로
                "chunks": [{...}, ...],  # 인용된 chunks 본문
            }
        """
        body = {"query": query, "top_k": top_k}
        if domain_hint:
            body["domain"] = domain_hint
        if types:
            body["types"] = types
        return self._post("/query", body)

    # ── 4. 광고용 context 추출 (편의 메서드) ────────────────
    def context_for_copy(
        self,
        product_query: str,
        target_surface: str = "onemsg",
        top_k: int = 5,
    ) -> str:
        """광고 카피 생성용 압축 context 문자열.

        target_surface 별 type 매핑 (Products / TruckQA 등 적절히 선택):
        - 'onemsg'  → 'truck-qa', 'truck-wiki' (트럭 운전자 타겟)
        - 'guide'   → 'product', 'truck-wiki' (캠핑·배터리 가이드)
        - 'shop'    → 'product', 'cs' (B2B 사업자)
        - 'liveon'  → 'product' (셀러 모집)
        - 'truck'   → 'truck-qa', 'truck-wiki', 'truck-law' (트럭 종합)
        """
        type_map = {
            "onemsg": ["truck-qa", "truck-wiki"],
            "guide": ["product", "truck-wiki"],
            "shop": ["product", "cs"],
            "liveon": ["product"],
            "truck": ["truck-qa", "truck-wiki", "truck-law"],
        }
        types = type_map.get(target_surface, ["product"])
        results = self.search(product_query, top_k=top_k, types=types)
        # 압축 — 광고 카피 LLM 프롬프트에 박을 양만
        lines = []
        for r in results[:top_k]:
            heading = r.get("heading") or "(no heading)"
            text = (r.get("text") or "")[:300]
            source = r.get("source", "")
            lines.append(f"[{source}] {heading}\n{text}")
        return "\n\n---\n\n".join(lines)

    # ── 내부 HTTP ────────────────────────────────────────────
    def _get(self, path: str) -> dict:
        try:
            r = requests.get(urljoin(self.base_url + "/", path.lstrip("/")), timeout=self.timeout)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise RAGError(f"GET {path} failed: {e}") from e
        except ValueError as e:
            raise RAGError(f"GET {path} non-JSON response: {e}") from e

    def _post(self, path: str, body: dict) -> dict:
        try:
            r = requests.post(
                urljoin(self.base_url + "/", path.lstrip("/")),
                json=body,
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
            )
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            raise RAGError(f"POST {path} failed: {e}") from e
        except ValueError as e:
            raise RAGError(f"POST {path} non-JSON response: {e}") from e


# 모듈 레벨 싱글톤 (대부분 호출 사이트에서 동일 설정 사용)
_default_client: Optional[RAGClient] = None


def get_rag() -> RAGClient:
    """기본 RAG 클라이언트 (싱글톤)"""
    global _default_client
    if _default_client is None:
        _default_client = RAGClient()
    return _default_client


if __name__ == "__main__":
    # 빠른 검증
    import json
    logging.basicConfig(level=logging.INFO)
    rag = get_rag()
    print("=== health ===")
    print(json.dumps(rag.health(), ensure_ascii=False, indent=2))
    print("\n=== search 'Q120 배터리 스펙' (product type) ===")
    hits = rag.search("Q120 배터리 스펙", top_k=3, types=["product"])
    for h in hits:
        print(f"  - {h.get('source')} | score={h.get('score', 0):.3f}")
