"""
In-memory log capture + pub/sub for SSE streaming.
Subscribers receive live entries; recent buffer primes new clients.
"""
import asyncio
import logging
import time
from collections import deque
from typing import Any

MAX_BUFFER = 500
MAX_QUEUE = 200

_buffer: deque[dict[str, Any]] = deque(maxlen=MAX_BUFFER)
_subscribers: list[asyncio.Queue] = []
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


class LiveLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = {
                "ts": record.created,
                "iso": time.strftime("%H:%M:%S", time.localtime(record.created)),
                "level": record.levelname,
                "name": record.name,
                "message": self.format(record),
            }
        except Exception:
            return
        _buffer.append(entry)
        if _loop is None or not _subscribers:
            return
        for q in list(_subscribers):
            _loop.call_soon_threadsafe(_try_put, q, entry)


def _try_put(q: asyncio.Queue, entry: dict) -> None:
    try:
        q.put_nowait(entry)
    except asyncio.QueueFull:
        pass


def install_handler() -> None:
    handler = LiveLogHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    handler.setLevel(logging.INFO)
    root = logging.getLogger()
    root.addHandler(handler)


def recent(limit: int = 100) -> list[dict]:
    return list(_buffer)[-limit:]


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=MAX_QUEUE)
    _subscribers.append(q)
    return q


def unsubscribe(q: asyncio.Queue) -> None:
    if q in _subscribers:
        _subscribers.remove(q)
