"""
Unngå flere Claude-kall / kladder for samme Graph-melding når Microsoft sender
flere notifications (created + updated, eller duplikater i samme batch).
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional

_lock = asyncio.Lock()
# Meldinger vi behandler akkurat nå (teksten under samme Request-ID eller to subscriptions).
_in_flight: set[str] = set()
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


async def try_begin_message_processing(message_id: str, ttl_seconds: float) -> bool:
    """
    Reserver message_id for behandling. False hvis den allerede er i gang eller nylig ferdig (TTL).
    Hindrer to samtidige webhook-POST (to subscriptions / omsending) i å kjøre Claude+kladd to ganger.
    """
    async with _lock:
        _prune_expired(ttl_seconds)
        if message_id in _in_flight:
            return False
        t0 = _processed_at.get(message_id)
        if t0 is not None and (time.monotonic() - t0) < ttl_seconds:
            return False
        _in_flight.add(message_id)
        return True


async def complete_message_processing(message_id: str, ttl_seconds: float) -> None:
    """Et vellykket kjør: fjern in-flight og marker som ferdig for TTL-dedupe."""
    async with _lock:
        _in_flight.discard(message_id)
        _prune_expired(ttl_seconds)
        _processed_at[message_id] = time.monotonic()


async def abort_message_processing(message_id: str) -> None:
    """Ved feil før complete: slipp låsen så nytt forsøk er mulig."""
    async with _lock:
        _in_flight.discard(message_id)


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
