from typing import Any, Dict, Optional

import httpx
import msal

from .config import get_settings


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

    async def get_message(self, message_id: str) -> Dict[str, Any]:
        url = f"{self.settings.graph_base_url}/me/messages/{message_id}"
        return await self._request("GET", url)

    async def create_draft_reply(self, message_id: str, body_html: str) -> Dict[str, Any]:
        """
        Oppretter en kladd som svar på en gitt melding.
        """
        url = f"{self.settings.graph_base_url}/me/messages/{message_id}/createReply"
        draft = await self._request("POST", url)
        draft_id = draft.get("id")
        if not draft_id:
            raise RuntimeError("Kunne ikke opprette kladd via createReply.")

        update_url = f"{self.settings.graph_base_url}/me/messages/{draft_id}"
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

