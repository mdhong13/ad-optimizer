"""
로컬 LLM 클라이언트 (d4win 서버) — 대량 생성용
OpenAI-compatible API
"""
import json
import logging
import httpx
from config.settings import settings

logger = logging.getLogger(__name__)


class LocalLLM:
    def __init__(self):
        self.base_url = settings.LOCAL_LLM_BASE_URL
        self.chat_url = f"{self.base_url}{settings.LOCAL_LLM_CHAT_ENDPOINT}"
        self.models_url = f"{self.base_url}{settings.LOCAL_LLM_MODELS_ENDPOINT}"
        self._model_id = None

    def get_model(self) -> str:
        """현재 로드된 모델 자동 감지"""
        if self._model_id:
            return self._model_id
        try:
            r = httpx.get(self.models_url, timeout=10)
            models = r.json().get("data", [])
            if models:
                self._model_id = models[0]["id"]
                logger.info(f"Local LLM model: {self._model_id}")
                return self._model_id
        except Exception as e:
            logger.warning(f"Local LLM model detection failed: {e}")
        return "default"

    def is_available(self) -> bool:
        try:
            r = httpx.get(f"{self.base_url}/health", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def chat(self, system: str, user_message: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        payload = {
            "model": self.get_model(),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_message},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        try:
            r = httpx.post(self.chat_url, json=payload, timeout=120)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            raise

    def chat_json(self, system: str, user_message: str, max_tokens: int = 2048) -> dict:
        text = self.chat(system, user_message, max_tokens, temperature=0.3)
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        return json.loads(text.strip())

    def generate_ad_copies(self, base_copy: dict, count: int = 20) -> list[dict]:
        """기존 카피 기반 변형 대량 생성"""
        system = (
            "You are an ad copywriter. Generate variations of the given ad copy. "
            "Each variation should have: headline (max 30 chars), description (max 90 chars). "
            f"Generate exactly {count} variations. Return JSON array."
        )
        return self.chat_json(system, json.dumps(base_copy, ensure_ascii=False))

    def generate_viral_comment(self, context: str, persona: str) -> str:
        """바이럴 댓글 생성"""
        system = (
            f"You are {persona}. Write a natural, engaging comment about "
            "cryptocurrency security and protecting digital assets. "
            "Sound authentic, not like an ad. Keep it under 280 characters."
        )
        return self.chat(system, context, max_tokens=256, temperature=0.9)

    def generate_community_post(self, topic: str, persona: str, platform: str) -> dict:
        """커뮤니티 글 생성"""
        system = (
            f"You are {persona} posting on {platform}. Write a thoughtful post about {topic}. "
            "Sound authentic and knowledgeable. Include personal anecdotes when relevant. "
            "Return JSON with 'title' and 'body' fields."
        )
        return self.chat_json(system, f"Topic: {topic}\nPlatform: {platform}")
