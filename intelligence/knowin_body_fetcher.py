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
import os
import re
import time
from dataclasses import dataclass
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

# 외부 답변 차단 영역 안내 문구
BLOCKED_PHRASES = [
    "답변을 등록할 수 없",
    "답변 등록이 제한",
    "이 질문은 답변할 수 없",
    "전문 답변자가 답변",
]

# 본인 답변자 ID prefix (네이버 마스킹: 앞 4자 + ****).
# norsunglae → "nors****", livecanvas → "live****" 형식.
# env 로 override 가능 (쉼표 구분).
_OWN_ANSWERER_PREFIXES = [
    p.strip().lower()
    for p in os.getenv("KNOWIN_OWN_ANSWERER_PREFIXES", "nors,live").split(",")
    if p.strip()
]
# 매칭 정규식: `\bnors\w*\*+` (단어 시작 + prefix + 임의 문자 + 별표).
# 일반 영문 본문에 "live" 같은 일반어 false positive 회피.
_OWN_ANSWERER_PATTERNS = [
    re.compile(rf"\b{re.escape(p)}\w*\*+", re.IGNORECASE) for p in _OWN_ANSWERER_PREFIXES
]


@dataclass
class FetchedQuestion:
    """페이지 fetch 결과 — body + 답변 차단 + 본인 이미 답변 여부"""
    body: Optional[str] = None
    answer_blocked: bool = False
    blocked_reason: Optional[str] = None
    already_answered: bool = False
    answered_by: Optional[str] = None   # 매칭된 prefix (nors 또는 live)

    @property
    def ok(self) -> bool:
        return self.body is not None or self.answer_blocked or self.already_answered


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


def _detect_own_answer(page_text: str) -> tuple[bool, Optional[str]]:
    """본인 답변자 ID 가 페이지 답변자 목록에 박혀있는지.

    마스킹 형식 (`nors****`, `live****`) 정규식 매칭.
    """
    for prefix, pattern in zip(_OWN_ANSWERER_PREFIXES, _OWN_ANSWERER_PATTERNS):
        if pattern.search(page_text):
            return True, prefix
    return False, None


def _detect_answer_blocked(soup, page_text: str) -> tuple[bool, Optional[str]]:
    """페이지 시그널에서 외부 답변 차단 여부 검출.

    탐지 우선순위:
      1. 지식파트너 영역 (정부·공공기관 FAQ)
      2. FAQ 라벨 (class 또는 텍스트)
      3. 명시적 차단 안내 문구
    """
    # 1) 지식파트너 영역 — 답변자 영역에 박힘
    if "지식파트너" in page_text:
        return True, "지식파트너 영역 (정부·공공기관 FAQ — 외부 답변 차단)"

    # 2) FAQ 카테고리 라벨 — class 에 'faq' 포함 + 텍스트 'FAQ'
    for el in soup.select('[class*="faq"]'):
        txt = el.get_text(strip=True).upper()
        if txt == "FAQ":
            return True, "FAQ 카테고리 (외부 답변 차단)"

    # 3) 명시적 차단 안내
    for phrase in BLOCKED_PHRASES:
        if phrase in page_text:
            return True, f"안내문 감지: '{phrase}'"

    return False, None


def fetch_question_meta(
    link: str,
    *,
    timeout: int = FETCH_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> FetchedQuestion:
    """지식인 질문 페이지 → 본문 + 답변 차단 여부 추출.

    body 추출 실패해도 answer_blocked 만 신뢰 가능. 호출자는 둘 다 처리.
    """
    result = FetchedQuestion()

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 미설치 — pip install beautifulsoup4")
        return result

    if not link or "kin.naver.com" not in link:
        return result

    url = to_mobile_url(link)
    sess = session or requests
    try:
        r = sess.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
        r.raise_for_status()
    except requests.RequestException as e:
        logger.warning("body fetch '%s' failed: %s", link, e)
        return result

    soup = BeautifulSoup(r.text, "html.parser")
    page_text = soup.get_text(" ", strip=True)

    # 본인 이미 답변 검출 (norsunglae/livecanvas) — 가장 강한 종료 신호
    own, prefix = _detect_own_answer(page_text)
    if own:
        result.already_answered = True
        result.answered_by = prefix

    # 답변 차단 검출 — body 추출 무관하게 표시
    blocked, reason = _detect_answer_blocked(soup, page_text)
    result.answer_blocked = blocked
    result.blocked_reason = reason

    # body 추출 (차단 영역이라도 본문 자체는 보관 — 카드 미리보기용)
    # 1) 우선 셀렉터 순차 시도
    for sel in QUESTION_BODY_SELECTORS:
        node = soup.select_one(sel)
        if node:
            text = _clean_text(node.get_text(separator=" "))
            if len(text) >= 10:
                result.body = text
                return result

    # 2) ld+json (schema.org Question) fallback
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or ""
        try:
            import json as _json
            data = _json.loads(raw)
            if isinstance(data, dict) and data.get("@type") == "Question":
                txt = data.get("text") or ""
                if txt:
                    result.body = _clean_text(txt)
                    return result
        except Exception:
            continue

    # 3) og:description 최후 fallback
    og = soup.find("meta", attrs={"property": "og:description"})
    if og and og.get("content"):
        result.body = _clean_text(og["content"])

    return result


def fetch_question_body(
    link: str,
    *,
    timeout: int = FETCH_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> Optional[str]:
    """body 만 반환하는 wrapper (하위 호환). 차단 여부 필요 시 fetch_question_meta 사용."""
    meta = fetch_question_meta(link, timeout=timeout, session=session)
    return meta.body


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
