"""
Periodisk fornyelse av Microsoft Graph change notification subscriptions.

Graph tillater ikke «uendelig» utløp — vi må PATCH-e expirationDateTime jevnlig.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from .config import get_settings
from .graph_client import GraphClient

logger = logging.getLogger(__name__)


def _expiration_iso_utc(minutes_from_now: int) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


async def renew_subscriptions_once() -> None:
    settings = get_settings()
    if not settings.graph_subscription_renew_enabled:
        return
    if not settings.graph_webhook_url:
        logger.debug(
            "GRAPH_WEBHOOK_URL er ikke satt; hopper over subscription-fornyelse."
        )
        return
    try:
        client = GraphClient()
    except Exception as exc:
        logger.warning("GraphClient ikke tilgjengelig for fornyelse: %s", exc)
        return

    base = str(settings.graph_webhook_url).rstrip("/")
    extend_min = max(60, int(settings.graph_subscription_extend_minutes))
    new_exp = _expiration_iso_utc(extend_min)

    try:
        data = await client.list_subscriptions()
    except Exception as exc:
        logger.exception("Klarte ikke liste subscriptions: %s", exc)
        return

    items = data.get("value") or []
    renewed = 0
    for sub in items:
        sub_id = sub.get("id")
        nurl = sub.get("notificationUrl") or ""
        if not sub_id:
            continue
        if base not in nurl:
            continue
        try:
            await client.patch_subscription(sub_id, new_exp)
            renewed += 1
            logger.info("Fornyet Graph-subscription %s -> %s", sub_id, new_exp)
        except Exception as exc:
            logger.exception("Klarte ikke fornye subscription %s: %s", sub_id, exc)

    if renewed == 0 and items:
        logger.debug(
            "Ingen subscriptions matchet GRAPH_WEBHOOK_URL=%s (totalt %s subscriptions).",
            base,
            len(items),
        )


async def subscription_renewal_loop() -> None:
    settings = get_settings()
    interval = max(60, int(settings.graph_subscription_renew_interval_seconds))
    while True:
        try:
            await renew_subscriptions_once()
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Feil i subscription-fornyelsesjobb")
        await asyncio.sleep(interval)
