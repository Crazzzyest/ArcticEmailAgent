"""
Hjelpefunksjoner for å tolke bruker/postboks fra Microsoft Graph webhooks.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import unquote


def extract_mailbox_user_from_notification(
    notification: Dict[str, Any],
    resource_data: Dict[str, Any],
) -> Optional[str]:
    """
    Finn postboks (UPN eller objekt-id) som meldingen tilhører.

    Graph sender typisk 'resource' som relativ sti, f.eks.
    users/Salg@arcticmotor.no/messages/AAMk...
    eller full @odata.id-URL på resourceData.
    """
    resource = notification.get("resource")
    if isinstance(resource, str) and resource.strip():
        u = _user_from_resource_string(resource.strip())
        if u:
            return u

    odata_id = resource_data.get("@odata.id")
    if isinstance(odata_id, str) and odata_id.strip():
        u = _user_from_odata_id(odata_id.strip())
        if u:
            return u

    return None


def _user_from_odata_id(odata_id: str) -> Optional[str]:
    marker = "/users/"
    lower = odata_id
    idx = lower.find(marker)
    if idx == -1:
        return None
    rest = odata_id[idx + len(marker) :]
    for sep in ("/messages/", "/Messages/"):
        if sep in rest:
            rest = rest.split(sep, 1)[0]
            break
    u = unquote(rest.rstrip("/"))
    return u or None


def _user_from_resource_string(resource: str) -> Optional[str]:
    if resource.lower().startswith("http"):
        return _user_from_odata_id(resource)

    parts = [p for p in resource.replace("\\", "/").split("/") if p]
    for i, p in enumerate(parts):
        if p.lower() == "users" and i + 1 < len(parts):
            raw = parts[i + 1]
            return unquote(raw.strip("'\"")) or None
    return None
