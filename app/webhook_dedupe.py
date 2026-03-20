"""
Unngå flere Claude-kall / kladder for samme Graph-melding når Microsoft sender
flere notifications (created + updated, eller duplikater i samme batch).
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

_lock = asyncio.Lock()
# message_id -> monotonic time when vi fullførte behandling (LLM)
_processed_at: dict[str, float] = {}
_MAX_ENTRIES = 10_000


def _prune_expired(ttl_seconds: float) -> None:
    if len(_processed_at) < _MAX_ENTRIES:
        return
    cutoff = time.monotonic() - ttl_seconds
    dead = [k for k, t in _processed_at.items() if t < cutoff]
    for k in dead[:5000]:
        _processed_at.pop(k, None)


async def was_recently_processed(message_id: str, ttl_seconds: float) -> bool:
    async with _lock:
        t0 = _processed_at.get(message_id)
        if t0 is None:
            return False
        return (time.monotonic() - t0) < ttl_seconds


async def mark_processed(message_id: str, ttl_seconds: float) -> None:
    async with _lock:
        _prune_expired(ttl_seconds)
        _processed_at[message_id] = time.monotonic()


def should_skip_change_type(change_type: Optional[str], only_created: bool) -> bool:
    """
    Når only_created er True: ignorer rent 'updated' (vanlig kilde til duplikater).
    Tom change_type behandles ikke som skip (defensivt).
    """
    if not only_created or not change_type:
        return False
    parts = {p.strip().lower() for p in str(change_type).split(",") if p.strip()}
    if not parts:
        return False
    if "created" in parts:
        return False
    # Bare updated / annet
    return True
