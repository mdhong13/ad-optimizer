"""
지식인 검색용 키워드 풀 자동 생성

소스:
  1. truck.qcat.kr 위키 entries (RAG meta.json) — name + heading 추출
  2. 일반어 (위키에 없는 검색 트리거)

전략:
  - 너무 짧은 키워드 (1-2자) 제외 — 네이버 검색 노이즈 증가
  - 한글 + 영문 + 숫자 혼합 OK
  - 중복 제거
  - 우선순위: heading > name (heading 이 더 구체적인 질문 패턴)

용도:
  지식인 검색 — 일 25,000 API 한도 안에서 키워드 풀을 batch 검색
  → 매칭 score 높은 질문만 MongoDB 큐에 적재
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional


# 위키 외 일반 검색 트리거 (수동 큐레이션)
GENERAL_KEYWORDS = [
    # 차종 일반어
    "트럭", "화물차", "카고차", "트럭 운전", "화물차 운전",
    "1톤", "1톤차", "1.4톤", "2.5톤", "3.5톤", "5톤", "8톤", "9.5톤",
    "11톤", "14톤", "18톤", "25톤", "25.5톤",
    "윙바디", "윙탑", "탑차", "냉동탑", "냉동차", "냉장차",
    "덤프", "덤프트럭", "카고", "압롤", "압롤차",
    # 행정·자격
    "화물자격증", "화물운송종사자격증", "운수업", "화물자동차운수사업법",
    "톤급", "적재량", "최대적재량", "총중량",
    "축중량", "축하중", "5축", "6축",
    "과적", "과적단속", "축중량단속",
    # 정비·부품 일반
    "DPF", "EGR", "SCR", "요소수", "녹스센서", "녹스",
    "터보", "터보차저", "인젝터", "커먼레일", "디젤필터",
    "타이어", "휠얼라이먼트", "브레이크", "리타더",
    "엔진오일", "미션오일", "냉각수", "부동액",
    # 증상
    "트럭 시동꺼짐", "화물차 시동", "트럭 흰연기", "트럭 검은연기",
    "트럭 잡소리", "출력저하", "엔진경고등",
    # 캠핑·차박 (Camping 카테고리 보조)
    "캠핑카 배터리", "차박 배터리", "캠핑카 충전",
    "무시동히터", "무시동에어컨", "차박 무시동",
    # 배터리·전원 (Products 보조)
    "리튬인산철 배터리", "트럭 배터리", "캠핑카 보조배터리",
    "인버터", "주행충전기", "솔라패널",
]


def _extract_from_rag_meta() -> set[str]:
    """RAG meta.json (로컬 사본) 에서 heading 추출 — 짧고 명사형만"""
    meta_path = Path(r"D:/2_QuantumCat/qcat/QCat_Wiki/_rag/meta.json")
    if not meta_path.exists():
        return set()

    keywords: set[str] = set()
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    for chunk in data:
        ctype = chunk.get("type")
        if ctype not in ("truck-wiki", "product"):
            continue
        heading = (chunk.get("heading") or "").strip()
        # 검색 키워드는 짧고 명사형 위주 — 14자 이하만
        if heading and 3 <= len(heading) <= 14:
            # 공백 너무 많으면 자연어 질문 → 제외
            if heading.count(" ") <= 2:
                keywords.add(heading)

    return keywords


def _extract_from_truck_wiki_json() -> set[str]:
    """truck.qcat.kr 4개 wiki json 의 name + aliases 추출 (있을 때만)"""
    base = Path(r"D:/2_QuantumCat/qcat/truck/src/data/wiki")
    if not base.exists():
        return set()

    keywords: set[str] = set()
    for fname in ("brands.json", "models.json", "parts.json", "symptoms.json", "topics.json"):
        p = base / fname
        if not p.exists():
            continue
        try:
            items = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        for item in items:
            name = item.get("name", "").strip()
            if name and 2 <= len(name) <= 30:
                keywords.add(name)
            for alias in item.get("aliases", []) or []:
                alias = alias.strip()
                if 2 <= len(alias) <= 30:
                    keywords.add(alias)

    return keywords


def build_keyword_pool(include_general: bool = True) -> list[str]:
    """전체 키워드 풀 — dedup + 정렬

    Returns:
        키워드 list (정렬됨, 중복 제거)
    """
    pool: set[str] = set()
    pool |= _extract_from_truck_wiki_json()
    pool |= _extract_from_rag_meta()
    if include_general:
        pool |= set(GENERAL_KEYWORDS)

    # 필터링
    filtered = set()
    for k in pool:
        k = k.strip()
        if not k:
            continue
        # 너무 짧은 단어 (1-2자) 제외 — 노이즈
        if len(k) < 3:
            continue
        # 특수문자만 있는 경우 제외
        if not any(c.isalnum() for c in k):
            continue
        # 너무 긴 — 자연어 질문일 가능성, 키워드로 부적합
        if len(k) > 30:
            continue
        filtered.add(k)

    return sorted(filtered)


def keyword_pool_stats() -> dict:
    """소스별 수치 (디버그용)"""
    wiki_json = _extract_from_truck_wiki_json()
    rag = _extract_from_rag_meta()
    general = set(GENERAL_KEYWORDS)
    total = build_keyword_pool()
    return {
        "from_truck_wiki_json": len(wiki_json),
        "from_rag_meta": len(rag),
        "general_keywords": len(general),
        "total_after_dedup_filter": len(total),
    }


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    stats = keyword_pool_stats()
    print("=== keyword pool stats ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    pool = build_keyword_pool()
    print(f"\n샘플 10 (정렬 후):")
    for k in pool[:10]:
        print(f"  - {k}")
    print(f"\n샘플 마지막 10:")
    for k in pool[-10:]:
        print(f"  - {k}")
