"""
AI 캐릭터 — 바이럴 활동용 페르소나
각 캐릭터는 고유한 성격, 어투, 관심사를 가짐
"""
import logging
from dataclasses import dataclass, field
from agent.local_llm import LocalLLM

logger = logging.getLogger(__name__)


@dataclass
class Character:
    name: str
    platform: str          # reddit, youtube, telegram, discord
    persona: str           # 캐릭터 설명
    tone: str = ""         # casual, professional, nerdy, friendly
    interests: list = field(default_factory=list)
    language: str = "en"   # en, ko, ja
    active: bool = True

    def generate_comment(self, context: str, llm: LocalLLM = None) -> str:
        """컨텍스트에 맞는 댓글 생성"""
        if llm is None:
            llm = LocalLLM()
        return llm.generate_viral_comment(context, self.persona)

    def generate_post(self, topic: str, llm: LocalLLM = None) -> dict:
        """커뮤니티 글 생성 (title + body)"""
        if llm is None:
            llm = LocalLLM()
        return llm.generate_community_post(topic, self.persona, self.platform)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "platform": self.platform,
            "persona": self.persona,
            "tone": self.tone,
            "interests": self.interests,
            "language": self.language,
            "active": self.active,
        }


# 프리셋 캐릭터
PRESET_CHARACTERS = [
    Character(
        name="CryptoGuardian",
        platform="reddit",
        persona="A security-conscious crypto investor who has been in the space since 2017. "
                "Passionate about self-custody and protecting digital assets. "
                "Experienced a close call when a friend passed away without sharing wallet access.",
        tone="helpful",
        interests=["bitcoin", "cold storage", "estate planning", "security"],
    ),
    Character(
        name="BlockchainDad",
        platform="reddit",
        persona="A 45-year-old father who got into crypto in 2020. "
                "Concerned about what happens to his portfolio if something happens to him. "
                "Pragmatic, family-oriented, not super technical.",
        tone="casual",
        interests=["family", "inheritance", "bitcoin", "financial planning"],
    ),
    Character(
        name="DefiSarah",
        platform="youtube",
        persona="A DeFi enthusiast and content creator who focuses on wallet security. "
                "Technical but approachable. Often shares tips about protecting crypto assets.",
        tone="friendly",
        interests=["defi", "wallet security", "yield farming", "tutorials"],
    ),
    Character(
        name="WhaleWatcher_KR",
        platform="telegram",
        persona="한국의 크립토 투자자. 비트코인과 이더리움 장기 홀더. "
                "디지털 자산 보호와 상속에 관심이 많음. 커뮤니티에서 활발히 활동.",
        tone="friendly",
        interests=["비트코인", "이더리움", "자산보호", "상속"],
        language="ko",
    ),
    Character(
        name="SecurityMaxi",
        platform="discord",
        persona="A cybersecurity professional who moonlights as a crypto trader. "
                "Always talks about operational security, cold storage, and backup strategies. "
                "Skeptical of cloud-based solutions but pragmatic.",
        tone="professional",
        interests=["opsec", "hardware wallets", "multisig", "security audits"],
    ),
]


def get_preset_characters(platform: str = None) -> list:
    """프리셋 캐릭터 목록 (플랫폼 필터 가능)"""
    if platform:
        return [c for c in PRESET_CHARACTERS if c.platform == platform]
    return PRESET_CHARACTERS
