"""
cache.py — Lightweight in-process TTL cache.

Drop-in pattern: works on Render free tier (no Redis needed).
If you later upgrade, swap _store for a redis.Redis client
and keep the same get/set/delete interface.
"""
import time
import logging
import threading
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ── Internal store: { key: (value, expires_at) } ─────────
_store: dict[str, tuple[Any, float]] = {}
_lock  = threading.Lock()


def get(key: str) -> Optional[Any]:
    """Return cached value or None if missing / expired."""
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del _store[key]
            logger.debug("Cache MISS (expired): %s", key)
            return None
        logger.debug("Cache HIT: %s", key)
        return value


def set(key: str, value: Any, ttl: int) -> None:
    """Store value with a TTL (seconds)."""
    with _lock:
        _store[key] = (value, time.time() + ttl)
    logger.debug("Cache SET: %s  TTL=%ds", key, ttl)


def delete(key: str) -> None:
    with _lock:
        _store.pop(key, None)


def flush_all() -> None:
    """Wipe cache entirely (e.g. for admin /refresh commands)."""
    with _lock:
        _store.clear()
    logger.info("Cache flushed.")


def ttl_remaining(key: str) -> int:
    """Seconds left before key expires; -1 if missing/expired."""
    with _lock:
        entry = _store.get(key)
        if not entry:
            return -1
        _, expires_at = entry
        remaining = int(expires_at - time.time())
        return max(remaining, -1)
