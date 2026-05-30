"""
네이버 지식인 검색 → MongoDB 적재

API:
  https://openapi.naver.com/v1/search/kin.json
  헤더: X-Naver-Client-Id, X-Naver-Client-Secret
  파라미터: query, display(1-100), start(1-1000), sort(sim|date)

한도:
  일 25,000 호출 (앱 단위)
  → 키워드 풀 ~4,000 × 1 호출/일 OK 또는
  → batch 작게 (300~500 키워드/일) 분산

흐름:
  1. build_keyword_pool() — 검색 키워드 풀
  2. 각 키워드 → /v1/search/kin.json (sort=date, display=20)
  3. 결과 → MongoDB knowin_questions (link 기반 dedup upsert)
  4. (별도) matcher → RAG score → status=matched/rejected 갱신

⚠️ 가드레일:
  - 일 한도 분산 (배치 throttle)
  - 사용자 행동 데이터 X (그냥 공개 검색 결과)
  - 자기 사이트 트래픽 분석에만 사용 — feedback_naver_unofficial_caution 정책 준수
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests

logger = logging.getLogger(__name__)

NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/kin.json"
DEFAULT_DISPLAY = 20
THROTTLE_SECONDS = 0.2  # 5 RPS (네이버 한도 10 RPS 보수적)


@dataclass
class KinResult:
    """검색 결과 1건"""
    title: str          # 강조 태그 (<b>) 포함, 그대로 저장
    title_plain: str    # 태그 제거된 평문
    link: str           # https://kin.naver.com/qna/detail.naver?d1id=...&dirId=...&docId=...
    description: str    # 본문 일부 (태그 포함)
    description_plain: str
    post_date: str      # YYYYMMDD 또는 ""
    keyword: str        # 검색 시 사용한 키워드
    question_id: str    # link 에서 docId 추출
    dir_id: str         # 카테고리 dirId

    def to_doc(self) -> dict:
        """MongoDB 문서로 변환"""
        from datetime import datetime, timezone
        return {
            "question_id": self.question_id,
            "dir_id": self.dir_id,
            "title": self.title,
            "title_plain": self.title_plain,
            "link": self.link,
            "description": self.description,
            "description_plain": self.description_plain,
            "post_date": self.post_date,
            "keyword": self.keyword,
            "status": "pending",   # pending | matched | rejected | answered
            "matched_url": None,
            "matched_score": None,
            "draft_id": None,
            "created_at": datetime.now(timezone.utc),
        }


def _strip_html(text: str) -> str:
    """<b> 등 태그 제거"""
    import re
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _parse_link(link: str) -> tuple[str, str]:
    """지식인 link 에서 (question_id=docId, dir_id) 추출"""
    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    docid = (qs.get("docId") or [""])[0]
    dirid = (qs.get("dirId") or [""])[0]
    return docid, dirid


class NaverKinSearch:
    """네이버 지식인 검색 API 클라이언트"""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.getenv("NAVER_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("NAVER_CLIENT_SECRET", "")
        if not self.client_id or not self.client_secret:
            raise RuntimeError("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 미설정")

    def _headers(self) -> dict:
        return {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }

    def search(
        self,
        query: str,
        display: int = DEFAULT_DISPLAY,
        start: int = 1,
        sort: str = "date",
    ) -> list[KinResult]:
        """단일 키워드 검색

        sort: 'sim' (정확도) | 'date' (최신순)
        display: 1~100, default 20
        start: 1~1000
        """
        params = {"query": query, "display": display, "start": start, "sort": sort}
        try:
            r = requests.get(NAVER_SEARCH_URL, params=params, headers=self._headers(), timeout=10)
            r.raise_for_status()
        except requests.RequestException as e:
            logger.warning("Naver Kin search '%s' failed: %s", query, e)
            return []

        data = r.json()
        items = data.get("items", []) or []
        results = []
        for it in items:
            link = it.get("link", "")
            docid, dirid = _parse_link(link)
            if not docid:
                continue  # link 파싱 실패는 dedup 불가 → 폐기
            results.append(
                KinResult(
                    title=it.get("title", ""),
                    title_plain=_strip_html(it.get("title", "")),
                    link=link,
                    description=it.get("description", ""),
                    description_plain=_strip_html(it.get("description", "")),
                    post_date=it.get("postdate", ""),
                    keyword=query,
                    question_id=docid,
                    dir_id=dirid,
                )
            )
        return results

    def batch_search(
        self,
        keywords: list[str],
        display: int = DEFAULT_DISPLAY,
        throttle: float = THROTTLE_SECONDS,
        on_progress: Optional[callable] = None,
    ) -> list[KinResult]:
        """여러 키워드 순차 검색 (throttle 적용)"""
        all_results = []
        for i, kw in enumerate(keywords):
            results = self.search(kw, display=display)
            all_results.extend(results)
            if on_progress:
                on_progress(i + 1, len(keywords), kw, len(results))
            time.sleep(throttle)
        return all_results


def crawl_to_mongo(
    keywords: list[str],
    display: int = DEFAULT_DISPLAY,
    throttle: float = THROTTLE_SECONDS,
) -> dict:
    """키워드 풀 검색 → MongoDB knowin_questions 컬렉션 upsert

    Returns:
        {searched: int, found: int, inserted: int, updated: int}
    """
    from storage.db import get_collection
    coll = get_collection("knowin_questions")

    api = NaverKinSearch()
    stats = {"searched": 0, "found": 0, "inserted": 0, "updated": 0}

    for kw in keywords:
        results = api.search(kw, display=display)
        stats["searched"] += 1
        stats["found"] += len(results)
        for r in results:
            doc = r.to_doc()
            # link 의 docId 기준 dedup
            res = coll.update_one(
                {"question_id": r.question_id},
                {
                    "$setOnInsert": doc,
                    # 기존 doc 있으면 keyword 만 append (중복 검색됐다는 신호)
                    "$addToSet": {"matched_keywords": kw},
                },
                upsert=True,
            )
            if res.upserted_id:
                stats["inserted"] += 1
            elif res.modified_count:
                stats["updated"] += 1
        time.sleep(throttle)

    return stats


if __name__ == "__main__":
    # smoke test — 1 키워드만 검색
    logging.basicConfig(level=logging.INFO)
    from dotenv import load_dotenv
    load_dotenv(r"D:/0_Dotcell/.env.global")

    api = NaverKinSearch()
    results = api.search("화물차 DPF 클리닝", display=5)
    print(f"검색 결과 {len(results)}건")
    for r in results[:3]:
        print(f"\n--- [{r.post_date}] {r.title_plain[:50]} ---")
        print(f"  link: {r.link}")
        print(f"  desc: {r.description_plain[:100]}")
        print(f"  qid:  {r.question_id}")
