"""
콘텐츠 자동 생성 — 블로그, Reddit, Twitter, 광고 카피
Claude LLM 기반
"""
import json
import logging
from pathlib import Path
from datetime import datetime

import anthropic

from config.settings import settings
from intelligence.crypto_monitor import get_market_context

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


def _load_prompt(filename: str) -> str:
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def _call_claude(system: str, user_msg: str) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model=settings.AGENT_MODEL,
        max_tokens=4096,
        system=system,
        messages=[{"role": "user", "content": user_msg}],
    )
    return msg.content[0].text


def _parse_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        lines = raw.split("\n")
        raw = "\n".join(lines[1:-1])
    return json.loads(raw)


def _save_output(content: dict, prefix: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{prefix}_{ts}.json"
    path = OUTPUT_DIR / fname
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"Content saved: {path}")
    return path


# ─── 블로그 / Reddit / Twitter 콘텐츠 생성 ───


TOPIC_PRESETS = {
    "foda_btc_lost": "프라이빗 키를 잃어버려 영원히 사라진 비트코인 사례들",
    "foda_sudden_death": "갑작스러운 사고로 사망한 크립토 보유자, 가족은 지갑을 열 수 없었다",
    "edu_crypto_inheritance": "크립토 상속 계획을 세우는 방법 — 법적, 기술적 가이드",
    "edu_hardware_wallet": "하드웨어 지갑 사용자가 반드시 해야 할 비상 대비",
    "edu_dead_mans_switch": "Dead Man's Switch란 무엇인가? 디지털 유산을 위한 자동화",
    "news_hack_response": "최신 크립토 해킹 사건에서 배우는 자산 보호 교훈",
    "solution_onemessage": "스마트폰이 감지하는 마지막 메시지 — OneMessage 소개",
    "tech_how_it_works": "7일 체크인으로 사망을 감지하는 기술 원리",
}


def generate_blog_post(
    topic: str = "foda_sudden_death",
    platform: str = "blog",
    tone: str = "informative",
) -> dict:
    """블로그/Reddit/Twitter 콘텐츠 생성"""
    topic_desc = TOPIC_PRESETS.get(topic, topic)
    template = _load_prompt("blog_post.md")
    prompt = template.replace("{topic}", topic_desc)
    prompt = prompt.replace("{platform}", platform)
    prompt = prompt.replace("{tone}", tone)

    system = (
        "당신은 크립토 보안과 디지털 유산 분야의 전문 콘텐츠 작성자입니다. "
        "자연스럽고 진정성 있는 글을 작성합니다. "
        "광고가 아닌 정보/교육 콘텐츠처럼 작성하되, OneMessage를 자연스럽게 언급합니다. "
        "반드시 유효한 JSON만 반환하세요."
    )

    raw = _call_claude(system, prompt)
    content = _parse_json(raw)
    content["generated_at"] = datetime.now().isoformat()
    content["topic_key"] = topic

    _save_output(content, f"content_{platform}")
    return content


def generate_twitter_thread(
    topic: str = "foda_btc_lost",
    thread_length: int = 5,
) -> dict:
    """Twitter/X 스레드 생성 (5-7개 트윗)"""
    topic_desc = TOPIC_PRESETS.get(topic, topic)
    system = (
        "당신은 크립토 Twitter/X 커뮤니티의 인플루언서입니다. "
        "크립토 보안과 디지털 유산에 대해 임팩트 있는 스레드를 작성합니다. "
        "각 트윗은 280자 이내. 반드시 유효한 JSON만 반환하세요."
    )

    user_msg = f"""다음 주제로 Twitter 스레드를 작성하세요.

주제: {topic_desc}
트윗 수: {thread_length}개

규칙:
- 첫 트윗: 후킹 (충격적 통계 또는 질문)
- 중간 트윗: 문제 설명 + 사례
- 마지막 트윗: 해결책 암시 (OneMessage 직접 언급 없이)
- 해시태그: #Bitcoin #Crypto #PrivateKey 등 자연스럽게
- 한국어 또는 영어 (영어 권장 - 글로벌 타겟)

출력 형식:
```json
{{
  "topic": "주제",
  "tweets": [
    {{"index": 1, "text": "트윗 내용", "hashtags": ["#tag"]}},
    ...
  ],
  "total_thread_length": N
}}
```"""

    raw = _call_claude(system, user_msg)
    content = _parse_json(raw)
    content["generated_at"] = datetime.now().isoformat()
    _save_output(content, "twitter_thread")
    return content


# ─── 광고 카피 생성 ───


def generate_ad_creative(
    platform: str = "meta",
    creative_type: str = "foda",
    market_context: dict = None,
) -> dict:
    """광고 카피 + A/B 변형 자동 생성"""
    if market_context is None:
        try:
            market_context = get_market_context()
        except Exception:
            market_context = {"note": "market data unavailable"}

    template = _load_prompt("ad_creative.md")
    prompt = template.replace("{platform}", platform)
    prompt = prompt.replace("{creative_type}", creative_type)
    prompt = prompt.replace("{market_context}", json.dumps(market_context, ensure_ascii=False))

    system = (
        "당신은 크립토 분야 퍼포먼스 마케팅 전문가입니다. "
        "높은 CTR과 전환율을 기록하는 광고 카피를 작성합니다. "
        "각 플랫폼의 글자수 제한을 반드시 지킵니다. "
        "반드시 유효한 JSON만 반환하세요."
    )

    raw = _call_claude(system, prompt)
    content = _parse_json(raw)
    content["generated_at"] = datetime.now().isoformat()
    _save_output(content, f"creative_{platform}_{creative_type}")
    return content


# ─── 배치 생성 (여러 주제/플랫폼 한번에) ───


def batch_generate_content(
    platforms: list[str] = None,
    topics: list[str] = None,
) -> list[dict]:
    """여러 조합으로 콘텐츠 배치 생성"""
    if platforms is None:
        platforms = ["blog", "reddit", "twitter"]
    if topics is None:
        topics = ["foda_sudden_death", "edu_crypto_inheritance", "edu_dead_mans_switch"]

    results = []
    for platform in platforms:
        for topic in topics:
            try:
                content = generate_blog_post(topic=topic, platform=platform)
                results.append(content)
                logger.info(f"Generated: {platform}/{topic}")
            except Exception as e:
                logger.error(f"Failed: {platform}/{topic} — {e}")
    return results


def batch_generate_creatives(
    platforms: list[str] = None,
    creative_types: list[str] = None,
) -> list[dict]:
    """광고 카피 배치 생성"""
    if platforms is None:
        platforms = ["meta", "google", "twitter"]
    if creative_types is None:
        creative_types = ["foda", "education", "solution"]

    results = []
    market = None
    try:
        market = get_market_context()
    except Exception:
        pass

    for platform in platforms:
        for ctype in creative_types:
            try:
                creative = generate_ad_creative(platform, ctype, market)
                results.append(creative)
                logger.info(f"Generated creative: {platform}/{ctype}")
            except Exception as e:
                logger.error(f"Failed creative: {platform}/{ctype} — {e}")
    return results


# ─── 사용 가능한 주제 목록 ───

def list_topics() -> dict:
    return TOPIC_PRESETS
