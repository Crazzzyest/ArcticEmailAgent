import asyncio
import logging
import random
from typing import Any, Dict, Optional
from urllib.parse import quote

import httpx
import msal

from .config import get_settings

logger = logging.getLogger(__name__)

# Midlertidige feil fra Graph / gateway – verdt å prøve på nytt (503 er vanlig ved fornyelse).
_RETRYABLE_STATUS = frozenset({429, 502, 503, 504})


class GraphClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        if (
            not self.settings.graph_tenant_id
            or not self.settings.graph_client_id
            or not self.settings.graph_client_secret
        ):
            raise RuntimeError(
                "Graph-konfig mangler (GRAPH_TENANT_ID, GRAPH_CLIENT_ID, GRAPH_CLIENT_SECRET)."
            )
        self._app = msal.ConfidentialClientApplication(
            client_id=self.settings.graph_client_id,
            authority=f"https://login.microsoftonline.com/{self.settings.graph_tenant_id}",
            client_credential=self.settings.graph_client_secret,
        )

    def _acquire_token(self) -> str:
        result = self._app.acquire_token_silent(
            scopes=["https://graph.microsoft.com/.default"], account=None
        )
        if not result:
            result = self._app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )
        if "access_token" not in result:
            raise RuntimeError(f"Kunne ikke hente token fra Azure AD: {result}")
        return result["access_token"]

    async def _request(
        self, method: str, url: str, json: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        token = self._acquire_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        }
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.request(method, url, headers=headers, json=json)
            resp.raise_for_status()
            return resp.json()

    async def _request_transient_retry(
        self,
        method: str,
        url: str,
        json: Optional[Dict[str, Any]] = None,
        *,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Som _request, men prøv på nytt ved 429/502/503/504 med backoff.
        Brukes bl.a. ved subscription-PATCH der Graph av og til svarer 503.
        """
        next_delay = 2.0
        last_resp: Optional[httpx.Response] = None
        for attempt in range(max_retries + 1):
            token = self._acquire_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.request(method, url, headers=headers, json=json)
            last_resp = resp
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code in _RETRYABLE_STATUS and attempt < max_retries:
                ra = resp.headers.get("Retry-After")
                if ra is not None:
                    try:
                        wait_s = float(ra)
                    except ValueError:
                        wait_s = next_delay + random.uniform(0, 0.5)
                else:
                    wait_s = next_delay + random.uniform(0, 0.25)
                    next_delay = min(next_delay * 2.0, 60.0)
                logger.warning(
                    "Graph %s %s → %s; venter %.1f s og prøver igjen (%s/%s)",
                    method,
                    url.partition("?")[0],
                    resp.status_code,
                    wait_s,
                    attempt + 1,
                    max_retries + 1,
                )
                await asyncio.sleep(wait_s)
                continue
            resp.raise_for_status()
        if last_resp is not None:
            last_resp.raise_for_status()
        raise RuntimeError("Graph-kall feilet uten respons")

    async def list_subscriptions(self) -> Dict[str, Any]:
        url = f"{self.settings.graph_base_url}/subscriptions"
        return await self._request("GET", url)

    async def create_subscription(self, body: Dict[str, Any]) -> Dict[str, Any]:
        """
        POST /subscriptions – opprett change notification-abonnement.
        Krever Mail.Read (og ev. tilgang til den konkrete postboksen).
        """
        url = f"{self.settings.graph_base_url}/subscriptions"
        return await self._request("POST", url, json=body)

    async def patch_subscription(
        self, subscription_id: str, expiration_datetime: str
    ) -> Dict[str, Any]:
        url = f"{self.settings.graph_base_url}/subscriptions/{subscription_id}"
        return await self._request_transient_retry(
            "PATCH",
            url,
            json={"expirationDateTime": expiration_datetime},
            max_retries=3,
        )

    def _user_messages_path(self, mailbox: str, message_id: str, suffix: str = "") -> str:
        base = str(self.settings.graph_base_url).rstrip("/")
        enc_user = quote(mailbox, safe=":@")
        enc_msg = quote(message_id, safe="")
        tail = suffix if suffix.startswith("/") else f"/{suffix}" if suffix else ""
        return f"{base}/users/{enc_user}/messages/{enc_msg}{tail}"

    async def get_message(self, message_id: str, mailbox: Optional[str] = None) -> Dict[str, Any]:
        """
        Henter melding. For app-only mot delte postbokser må `mailbox` (UPN) oppgis;
        /me brukes kun hvis mailbox er None (delegert kontekst).
        """
        base = str(self.settings.graph_base_url).rstrip("/")
        if mailbox:
            url = self._user_messages_path(mailbox, message_id)
        else:
            enc_msg = quote(message_id, safe="")
            url = f"{base}/me/messages/{enc_msg}"
        return await self._request("GET", url)

    async def list_attachments(
        self, message_id: str, mailbox: Optional[str] = None
    ) -> list[Dict[str, Any]]:
        """
        Henter vedleggslisten for en melding (metadata + base64-innhold).
        Graph returnerer contentBytes for file-attachments automatisk.
        """
        url = self._user_messages_path(
            mailbox or "me", message_id, "/attachments"
        )
        data = await self._request("GET", url)
        return data.get("value", [])

    async def create_draft_reply(
        self,
        message_id: str,
        body_html: str,
        mailbox: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Oppretter en kladd som svar på en gitt melding.
        """
        base = str(self.settings.graph_base_url).rstrip("/")
        if mailbox:
            url = self._user_messages_path(mailbox, message_id, "/createReply")
            enc_user = quote(mailbox, safe=":@")
            draft = await self._request("POST", url)
            draft_id = draft.get("id")
            if not draft_id:
                raise RuntimeError("Kunne ikke opprette kladd via createReply.")
            update_url = f"{base}/users/{enc_user}/messages/{quote(draft_id, safe='')}"
        else:
            enc_msg = quote(message_id, safe="")
            url = f"{base}/me/messages/{enc_msg}/createReply"
            draft = await self._request("POST", url)
            draft_id = draft.get("id")
            if not draft_id:
                raise RuntimeError("Kunne ikke opprette kladd via createReply.")
            update_url = f"{base}/me/messages/{quote(draft_id, safe='')}"
        await self._request(
            "PATCH",
            update_url,
            json={
                "body": {
                    "contentType": "HTML",
                    "content": body_html,
                }
            },
        )
        return draft

