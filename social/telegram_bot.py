"""
Telegram 봇 — 크립토 그룹 모니터링 & 바이럴 활동
python-telegram-bot 라이브러리 사용
"""
import logging
import os

from agent.local_llm import LocalLLM
from viral.character import Character, get_preset_characters
from storage import db

logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TARGET_GROUPS = os.getenv("TELEGRAM_TARGET_GROUPS", "").split(",")

# 모니터링 키워드
MONITOR_KEYWORDS = [
    "crypto inheritance", "bitcoin lost", "dead man switch",
    "wallet backup", "seed phrase", "private key security",
    "crypto estate", "digital will",
]


class TelegramViralBot:
    """텔레그램 크립토 그룹 바이럴 봇"""

    def __init__(self):
        self.llm = LocalLLM()
        self.character = self._load_character()
        self.bot = None

    def _load_character(self) -> Character:
        """텔레그램 전용 캐릭터 로드"""
        chars = get_preset_characters(platform="telegram")
        if chars:
            return chars[0]
        return Character(
            name="CryptoHelper_TG",
            platform="telegram",
            persona="A helpful crypto community member who shares tips about "
                    "wallet security and digital asset protection.",
            tone="friendly",
            interests=["bitcoin", "security", "inheritance"],
        )

    def _is_relevant(self, text: str) -> bool:
        """메시지가 관련 키워드를 포함하는지 확인"""
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in MONITOR_KEYWORDS)

    def generate_response(self, message_text: str) -> str:
        """관련 메시지에 대한 자연스러운 응답 생성"""
        context = f"Telegram group message: {message_text[:300]}"
        return self.character.generate_comment(context, self.llm)

    def start(self):
        """봇 시작 (polling 모드)"""
        if not TELEGRAM_BOT_TOKEN:
            logger.error("TELEGRAM_BOT_TOKEN not set")
            return

        try:
            from telegram.ext import ApplicationBuilder, MessageHandler, filters

            app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

            async def handle_message(update, context):
                if not update.message or not update.message.text:
                    return
                text = update.message.text
                if self._is_relevant(text):
                    response = self.generate_response(text)
                    await update.message.reply_text(response)

                    # DB 기록
                    db.insert_viral_activity({
                        "character_id": self.character.name,
                        "platform": "telegram",
                        "task_type": "reply",
                        "context": text[:500],
                        "generated_text": response[:1000],
                        "status": "posted",
                        "chat_id": str(update.message.chat_id),
                    })
                    logger.info(f"[TG] Replied to: {text[:50]}...")

            app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
            logger.info("Telegram bot started (polling)")
            app.run_polling()

        except ImportError:
            logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
        except Exception as e:
            logger.error(f"Telegram bot error: {e}")

    def send_to_group(self, chat_id: str, text: str) -> bool:
        """특정 그룹에 메시지 전송"""
        if not TELEGRAM_BOT_TOKEN:
            return False
        try:
            import httpx
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            r = httpx.post(url, json={"chat_id": chat_id, "text": text}, timeout=15)
            r.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = TelegramViralBot()
    print(f"Character: {bot.character.name}")
    print(f"Token set: {bool(TELEGRAM_BOT_TOKEN)}")
    if TELEGRAM_BOT_TOKEN:
        bot.start()
    else:
        print("Set TELEGRAM_BOT_TOKEN to start the bot")
