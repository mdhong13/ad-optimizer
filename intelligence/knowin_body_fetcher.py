"""
네이버 지식인 질문 본문 fetcher

네이버 검색 API 의 `description` 은 검색어에 맞춘 발췌(snippet) 라
질문 본문이 아닌 답변 본문이 잡히는 경우가 많음. 동문서답 위험.

해결: 검색 결과의 link 페이지를 직접 fetch → 진짜 질문 본문 추출.

전략:
  - 모바일 URL 변환 (m.kin.naver.com — 파싱 안정)
  - bs4 로 questionDetail 영역 선택
  - 여러 fallback 셀렉터 시도
  - 실패 시 og:description (제목·발췌 머지)

⚠️ 가드레일:
  - throttle 1초/요청 (네이버 차단 회피)
  - User-Agent 일반 브라우저 표시
  - 단발 호출 — 큐 백필 시에도 batch 안에서 직렬
"""
from __future__ import annotations

import logging
import re
import time
from typing import Optional
from urllib.parse import urlparse, urlunparse

import requests

logger = logging.getLogger(__name__)

# 일반 브라우저 위장 (지식인은 봇 차단 약하지만 매너상)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 13; SM-S918N) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "ko-KR,ko;q=0.9",
}

FETCH_TIMEOUT = 8
DEFAULT_THROTTLE = 1.0

# 본문이 들어있는 영역 셀렉터 (네이버 페이지 구조 변경 대비 다중 fallback)
QUESTION_BODY_SELECTORS = [
    "div.questionDetail",
    "div#questionDetail",
    "div.c-heading__content",
    "div.end_question__content",
    "div.qna_content",
    "div._questionContentsArea",
]


def to_mobile_url(link: str) -> str:
    """데스크탑 link → 모바일 link 변환 (파싱 안정성)

    예: https://kin.naver.com/qna/detail.naver?...
        → https://m.kin.naver.com/qna/detail.naver?...
    """
    p = urlparse(link)
    host = p.netloc
    if host == "kin.naver.com":
        host = "m.kin.naver.com"
    return urlunparse((p.scheme, host, p.path, p.params, p.query, p.fragment))


def _clean_text(text: str) -> str:
    """공백·줄바꿈 정리"""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_question_body(
    link: str,
    *,
    timeout: int = FETCH_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    """지식인 질문 페이지 → 본문 텍스트 추출.

    Returns:
        본문 텍스트 (실패 시 None)
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 미설치 — pip install beautifulsoup4")
        return None

    if not link or "kin.naver.com" not in link:
        return None

    url = to_mobile_url(link)
    sess = session or requests
    try:
        r = sess.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("body fetch '%s' failed: %s", link, e)
        return None

    soup = BeautifulSoup(r.text, "html.parser")

    # 1) 우선 셀렉터 순차 시도
    for sel in QUESTION_BODY_SELECTORS:
        node = soup.select_one(sel)
        if node:
            text = _clean_text(node.get_text(separator=" "))
            if len(text) >= 10:
                return text

    # 2) ld+json (schema.org Question) fallback
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or ""
        try:
            import json as _json
            data = _json.loads(raw)
            if isinstance(data, dict) and data.get("@type") == "Question":
                txt = data.get("text") or ""
                if txt:
                    return _clean_text(txt)
        except Exception:
            continue

    # 3) og:description 최후 fallback (질문·답변 머지 가능 — 신뢰도 낮음)
    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        return _clean_text(og["content"])

    return None


def batch_fetch(
    links: list[str],
    *,
    throttle: float = DEFAULT_THROTTLE,
    on_progress: Optional[callable] = None,
) -> dict[str, Optional[str]]:
    """여러 link 직렬 fetch (throttle 적용)

    Returns:
        {link: body or None}
    """
    sess = requests.Session()
    out: dict[str, Optional[str]] = {}
    for i, link in enumerate(links):
        body = fetch_question_body(link, session=sess)
        out[link] = body
        if on_progress:
            on_progress(i + 1, len(links), link, body is not None)
        time.sleep(throttle)
    return out


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        for link in sys.argv[1:]:
            print(f"\n=== {link} ===")
            body = fetch_question_body(link)
            print(body[:500] if body else "(추출 실패)")
    else:
        print("usage: python -m intelligence.knowin_body_fetcher <link> [link...]")
