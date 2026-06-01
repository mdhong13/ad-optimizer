"""
Telegram 알림 헬퍼 — Dotcell 운영 알림 채널.

채널: "Dotcell 마케팅" (비공개)
봇: @dotcell_mkt_bot
chat_id: env TELEGRAM_CHAT_ID

사용 패턴:
    from agent.telegram import notify
    notify("knowin 매칭 큐 3건 갱신")
    notify("⚠️ Meta CPA 어제 ₩890 → 오늘 ₩2400 (+170%)", sender="anomaly")

설계:
- env TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID 미설정 시 silent no-op (로컬 dev 안전)
- sender prefix 박음 — "[knowin] 매칭 큐 3건"
- plain text 박음 (Markdown escape 함정 회피)
- HTTP 실패 시 로그만 — 운영 흐름 깨지 X
- DRY_RUN env 박혀있으면 실제 전송 안 함 (테스트용)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import requests

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.telegram.org"
_TIMEOUT = 5


def _get_token() -> Optional[str]:
    return os.getenv("TELEGRAM_BOT_TOKEN", "").strip() or None


def _get_chat_id() -> Optional[str]:
    return os.getenv("TELEGRAM_CHAT_ID", "").strip() or None


def _is_dry_run() -> bool:
    return os.getenv("TELEGRAM_DRY_RUN", "").lower() in ("true", "1", "yes")


def notify(
    text: str,
    sender: Optional[str] = None,
    chat_id: Optional[str] = None,
    silent: bool = False,
) -> bool:
    """채널에 메시지 박음.

    Args:
        text: 본문 (plain text)
        sender: prefix 박을 시스템 이름 (예: "knowin", "anomaly", "cmo")
        chat_id: override (None 이면 env TELEGRAM_CHAT_ID)
        silent: True 면 notification 소리 안 박힘

    Returns:
        True = 전송 성공, False = 실패 또는 미설정
    """
    token = _get_token()
    target_chat = chat_id or _get_chat_id()
    if not token or not target_chat:
        logger.info("telegram notify skip (token or chat_id 미설정): %s", text[:60])
        return False

    body = f"[{sender}] {text}" if sender else text

    if _is_dry_run():
        logger.info("telegram DRY_RUN: %s", body[:120])
        return False

    try:
        r = requests.post(
            f"{_BASE_URL}/bot{token}/sendMessage",
            data={
                "chat_id": target_chat,
                "text": body,
                "disable_notification": "true" if silent else "false",
            },
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            logger.warning("telegram notify HTTP %s: %s", r.status_code, r.text[:200])
            return False
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("telegram notify 실패: %s", e)
        return False


def notify_safe(text: str, **kwargs) -> bool:
    """notify 의 예외 안전 버전 — 운영 코드에서 try/except 안 박아도 됨."""
    try:
        return notify(text, **kwargs)
    except Exception as e:  # noqa: BLE001
        logger.warning("notify_safe 예외: %s", e)
        return False


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    try:
        from dotenv import load_dotenv
        load_dotenv(r"D:/0_Dotcell/.env.global")
    except ImportError:
        pass

    msg = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else "🧪 ad-optimizer telegram 헬퍼 smoke test"
    ok = notify(msg, sender="test")
    print("sent:", ok)
