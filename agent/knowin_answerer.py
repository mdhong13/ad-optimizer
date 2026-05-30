"""
네이버 지식인 답변 초안 생성기

흐름:
  WikiMatch (matcher.py 결과)
    + LLM (Claude or 로컬 d4win)
    → 답변 본문 (5문장 이상, 구체 정보)
    + 출처 박스 (truck.qcat.kr URL)
    → posting-ready markdown

⚠️ 가드레일 (위반 시 스팸 처리 위험):
  1. 본문 5문장 이상 + 구체 정보 (수치·예시·절차) — "자세한 건 링크" 금지
  2. 답변 첫 문장에 링크 X — 본문 먼저
  3. 출처 표기 형식 통일 — "출처: 트럭의 기사 위키 [URL]"
  4. 광고성 멘트 금지 ("최고", "1위", "절대 안전")
  5. 페르소나 박지 X (양자냥/도라미/자체 브랜드 X — 익명 정보 제공자 톤)
  6. 일 최대 5~10건 + throttle 30분 (호출 측에서 처리)

LLM 선택:
  - 본문 길이 + 도메인 정확도 중요 → Claude API (claude-sonnet-4-6) 권장
  - 비용 절감 시 → 로컬 d4win gemma4-e4b-it (16k context)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from .knowin_matcher import WikiMatch

logger = logging.getLogger(__name__)


# 출처 박스 포맷 — 모든 답변 공통
SOURCE_BOX_TEMPLATE = """\

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
출처: 트럭의 기사 위키
{url}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# 답변 생성 프롬프트 — 가드레일 강제
ANSWER_PROMPT_TEMPLATE = """\
당신은 트럭 운전자 커뮤니티에 답변하는 도메인 전문가입니다.
네이버 지식인 질문에 답하려고 합니다.

[질문]
{question}

[참고 자료 — truck.qcat.kr 위키 발췌]
{context}

[작성 규칙 — 모두 지킬 것]
1. 답변 본문은 **반드시 5문장 이상**. 첫 문장은 질문에 대한 직접 답.
2. **구체적인 수치·예시·절차**를 포함 (참고 자료에서 직접 인용).
3. **모르는 부분은 솔직히** — "정확한 견적은 정비소 문의" 같은 표현 권장.
4. **광고성 표현 금지** — "최고", "1위", "절대 안전", "단연" 등.
5. **답변자 페르소나 박지 X** — "안녕하세요" 같은 일반 인사 OK, 캐릭터 이름 (양자냥/도라미 등) 금지.
6. **본문에 링크 박지 X** — 출처 박스는 별도 영역에서 자동 추가됨.
7. 톤은 차분하고 정보 중심. 친근하지만 과하지 않게.

답변 본문만 작성. 출처 박스는 자동 추가.
"""


@dataclass
class DraftAnswer:
    body: str               # 답변 본문 (출처 박스 제외)
    full_text: str          # 본문 + 출처 박스 (지식인 게시 시 그대로 복붙)
    source_url: str
    source_title: str
    match_score: float
    word_count: int
    sentence_count: int
    llm_model: str          # 사용한 LLM (감사용)
    warnings: list[str]     # 가드레일 위반 경고

    @property
    def safe_to_post(self) -> bool:
        return len(self.warnings) == 0


def _build_prompt(question: str, match: WikiMatch) -> str:
    return ANSWER_PROMPT_TEMPLATE.format(question=question, context=match.rag_context)


def _check_guardrails(body: str) -> list[str]:
    """답변 본문 가드레일 검증"""
    warnings = []
    # 문장 수 — '.', '!', '?', '다.' 카운트
    import re
    sentences = re.split(r"[.!?。]+", body.strip())
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) < 5:
        warnings.append(f"문장 수 부족 ({len(sentences)}/5)")

    # 광고성 단어
    banned = ["최고", "1위", "절대 안전", "단연", "유일한", "100% 보장"]
    for w in banned:
        if w in body:
            warnings.append(f"광고성 표현 포함: '{w}'")

    # 페르소나 이름
    persona_names = ["양자냥", "도라미", "라미", "OneMessage"]
    for p in persona_names:
        if p in body:
            warnings.append(f"페르소나 이름 포함: '{p}' (답변자 익명 유지 원칙 위반)")

    # 길이 — 너무 짧으면 광고로 분류 위험
    if len(body) < 200:
        warnings.append(f"본문 길이 부족 ({len(body)}자/200자)")

    # 본문에 URL 박지 X (출처 박스에만)
    if "http" in body or "truck.qcat.kr" in body:
        warnings.append("본문에 URL 포함 — 출처 박스에만 박을 것")

    return warnings


def _call_claude(prompt: str) -> tuple[str, str]:
    """Claude API 호출 → (답변 텍스트, model id)"""
    try:
        from anthropic import Anthropic
    except ImportError:
        raise RuntimeError("anthropic 패키지 미설치. 'pip install anthropic'")

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY 미설정")

    client = Anthropic(api_key=api_key)
    model = "claude-sonnet-4-6"
    resp = client.messages.create(
        model=model,
        max_tokens=1200,
        messages=[{"role": "user", "content": prompt}],
    )
    # Anthropic SDK 응답 — content blocks
    text = "".join(b.text for b in resp.content if hasattr(b, "text"))
    return text.strip(), model


def _call_local_llm(prompt: str) -> tuple[str, str]:
    """로컬 d4win vLLM 호출 → (답변 텍스트, model id)"""
    import requests
    base = os.getenv("LOCAL_LLM_BASE_URL", "http://d4win.iptime.org:31088")
    url = base.rstrip("/") + "/v1/chat/completions"
    body = {
        "model": "host",  # vLLM 자동 (현재 gemma4-e4b-it)
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1200,
        "temperature": 0.6,
    }
    r = requests.post(url, json=body, timeout=60)
    r.raise_for_status()
    data = r.json()
    text = data["choices"][0]["message"]["content"].strip()
    model = data.get("model", "local-vllm")
    return text, model


def generate_answer(
    question: str,
    match: WikiMatch,
    llm: str = "claude",  # 'claude' or 'local'
) -> DraftAnswer:
    """질문 + 매칭 결과 → 답변 초안 (게시 전 검토용)"""
    if not match.matched:
        raise ValueError(f"WikiMatch 미매칭 (score={match.top_score}) — 답변 생성 불가")

    prompt = _build_prompt(question, match)

    if llm == "local":
        body, model = _call_local_llm(prompt)
    else:
        body, model = _call_claude(prompt)

    # 출처 박스 부착
    source_box = SOURCE_BOX_TEMPLATE.format(url=match.url)
    full_text = body.rstrip() + "\n" + source_box

    # 가드레일 검증
    warnings = _check_guardrails(body)

    # 통계
    import re
    sentences = [s for s in re.split(r"[.!?。]+", body.strip()) if s.strip()]

    return DraftAnswer(
        body=body,
        full_text=full_text,
        source_url=match.url or "",
        source_title=match.title,
        match_score=match.top_score,
        word_count=len(body),
        sentence_count=len(sentences),
        llm_model=model,
        warnings=warnings,
    )


if __name__ == "__main__":
    from .knowin_matcher import match_question
    q = "5톤 윙탑 9.8m 와 10.2m 차이가 뭐예요?"
    m = match_question(q)
    print(f"matched: {m.matched} | url: {m.url}")
    if m.matched:
        draft = generate_answer(q, m, llm="local")
        print(f"\n=== body ({draft.word_count}자, {draft.sentence_count}문장) ===")
        print(draft.body[:500])
        print(f"\nwarnings: {draft.warnings}")
        print(f"safe_to_post: {draft.safe_to_post}")
