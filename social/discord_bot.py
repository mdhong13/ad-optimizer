"""
Discord 봇 — 크립토 서버 바이럴 활동
discord.py 라이브러리 사용
"""
import logging
import os

from agent.local_llm import LocalLLM
from viral.character import Character, get_preset_characters
from storage import db

logger = logging.getLogger(__name__)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

# 모니터링 채널 (채널 ID)
MONITOR_CHANNELS = os.getenv("DISCORD_MONITOR_CHANNELS", "").split(",")

MONITOR_KEYWORDS = [
    "crypto inheritance", "bitcoin lost", "wallet security",
    "dead man switch", "seed phrase backup", "private key",
    "crypto estate planning", "digital assets after death",
]


class DiscordViralBot:
    """디스코드 크립토 서버 바이럴 봇"""

    def __init__(self):
        self.llm = LocalLLM()
        self.character = self._load_character()

    def _load_character(self) -> Character:
        """디스코드 전용 캐릭터 로드"""
        chars = get_preset_characters(platform="discord")
        if chars:
            return chars[0]
        return Character(
            name="SecurityMaxi_DC",
            platform="discord",
            persona="A cybersecurity professional who trades crypto on the side. "
                    "Passionate about operational security and backup strategies.",
            tone="professional",
            interests=["opsec", "hardware wallets", "security"],
        )

    def _is_relevant(self, text: str) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in MONITOR_KEYWORDS)

    def generate_response(self, message_text: str) -> str:
        context = f"Discord message: {message_text[:300]}"
        return self.character.generate_comment(context, self.llm)

    def start(self):
        """봇 시작"""
        if not DISCORD_BOT_TOKEN:
            logger.error("DISCORD_BOT_TOKEN not set")
            return

        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            client = discord.Client(intents=intents)

            @client.event
            async def on_ready():
                logger.info(f"Discord bot connected as {client.user}")

            @client.event
            async def on_message(message):
                # 자기 메시지 무시
                if message.author == client.user:
                    return

                # 모니터링 채널 필터 (설정된 경우)
                if MONITOR_CHANNELS and MONITOR_CHANNELS[0]:
                    if str(message.channel.id) not in MONITOR_CHANNELS:
                        return

                text = message.content
                if not text or not self._is_relevant(text):
                    return

                response = self.generate_response(text)
                await message.channel.send(response)

                # DB 기록
                db.insert_viral_activity({
                    "character_id": self.character.name,
                    "platform": "discord",
                    "task_type": "reply",
                    "context": text[:500],
                    "generated_text": response[:1000],
                    "status": "posted",
                    "server_id": str(message.guild.id) if message.guild else "",
                    "channel_id": str(message.channel.id),
                })
                logger.info(f"[DC] Replied in #{message.channel.name}: {text[:50]}...")

            client.run(DISCORD_BOT_TOKEN)

        except ImportError:
            logger.error("discord.py not installed. Run: pip install discord.py")
        except Exception as e:
            logger.error(f"Discord bot error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot = DiscordViralBot()
    print(f"Character: {bot.character.name}")
    print(f"Token set: {bool(DISCORD_BOT_TOKEN)}")
    if DISCORD_BOT_TOKEN:
        bot.start()
    else:
        print("Set DISCORD_BOT_TOKEN to start the bot")
