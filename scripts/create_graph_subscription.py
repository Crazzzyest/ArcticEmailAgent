#!/usr/bin/env python3
"""
Opprett Microsoft Graph subscription for meldinger i innboks til en postboks.

Kjør fra rot i repo (med .env lastet via pydantic-settings):

  python scripts/create_graph_subscription.py --mailbox service@arcticmotor.no

Krav i miljø / .env:
  GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET
  GRAPH_WEBHOOK_URL – samme offentlige URL som i produksjon (inkl. /graph/webhook)
  GRAPH_SUBSCRIPTION_CLIENT_STATE – hemmelig streng (lagre trygt; sendes tilbake i webhook)

Valgfritt:
  GRAPH_SUBSCRIPTION_EXTEND_MINUTES – utløp relativt til nå (default 4180, likt fornyelse i appen)
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Repo root på path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _expiration_iso_utc(minutes_from_now: int) -> str:
    dt = datetime.now(timezone.utc) + timedelta(minutes=minutes_from_now)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.0000000Z")


async def _run() -> int:
    parser = argparse.ArgumentParser(
        description="Opprett Graph subscription for users/{mailbox}/mailFolders('Inbox')/messages"
    )
    parser.add_argument(
        "--mailbox",
        required=True,
        help="UPN til postboks, f.eks. service@arcticmotor.no",
    )
    parser.add_argument(
        "--change-type",
        default="created",
        help="Graph changeType, f.eks. created (anbefalt med GRAPH_WEBHOOK_ONLY_CREATED)",
    )
    parser.add_argument(
        "--extend-minutes",
        type=int,
        default=None,
        help="Minutter til expirationDateTime (default: fra GRAPH_SUBSCRIPTION_EXTEND_MINUTES eller 4180)",
    )
    args = parser.parse_args()

    from app.config import get_settings
    from app.graph_client import GraphClient

    settings = get_settings()
    webhook = settings.graph_webhook_url
    if not webhook:
        print("Sett GRAPH_WEBHOOK_URL i .env", file=sys.stderr)
        return 1

    client_state = (settings.graph_subscription_client_state or "").strip()
    if not client_state:
        print(
            "Sett GRAPH_SUBSCRIPTION_CLIENT_STATE (hemmelig, maks 255 tegn) i .env eller miljøet.",
            file=sys.stderr,
        )
        return 1

    extend = args.extend_minutes
    if extend is None:
        extend = max(60, int(settings.graph_subscription_extend_minutes))

    mailbox = args.mailbox.strip()
    resource = f"users/{mailbox}/mailFolders('Inbox')/messages"

    payload = {
        "changeType": args.change_type,
        "notificationUrl": str(webhook).rstrip("/"),
        "resource": resource,
        "expirationDateTime": _expiration_iso_utc(extend),
        "clientState": client_state,
    }

    try:
        client = GraphClient()
        result = await client.create_subscription(payload)
    except Exception as exc:
        print(f"Feil: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
