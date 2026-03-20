import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .config import get_settings, Settings
from .models import Attachment, EmailMessage, EmailThread, ProcessThreadRequest, ProcessThreadResponse
from .service import process_email_thread_from_raw, process_email_thread_from_graph_payload
from .graph_client import GraphClient
from .subscription_renewal import subscription_renewal_loop

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    task: Optional[asyncio.Task[None]] = None
    settings = get_settings()
    if settings.graph_subscription_renew_enabled and settings.graph_webhook_url:
        task = asyncio.create_task(subscription_renewal_loop())
        logger.info(
            "Graph subscription-fornyelse startet (intervall %s s, webhook-filter: %s)",
            settings.graph_subscription_renew_interval_seconds,
            settings.graph_webhook_url,
        )
    yield
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Arctic Email Assistant", lifespan=lifespan)


def get_app_settings() -> Settings:
    return get_settings()


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.post("/test/process-thread", response_model=ProcessThreadResponse)
async def test_process_thread(payload: ProcessThreadRequest) -> ProcessThreadResponse:
    """
    Lokal testing uten Microsoft Graph.
    """
    return await process_email_thread_from_raw(
        subject=payload.subject,
        body=payload.body,
        attachments=payload.attachments,
    )


async def _graph_webhook_validation(validation_token: Optional[str]) -> PlainTextResponse:
    """
    Graph krever 200 OK og ren tekst med token i body innen ~10 sekunder.
    Noen valideringsflyter bruker GET, andre POST med ?validationToken=...
    """
    if not validation_token:
        raise HTTPException(
            status_code=400,
            detail="Mangler validationToken for subscription-validering.",
        )
    return PlainTextResponse(content=validation_token, media_type="text/plain")


@app.get("/graph/webhook")
async def graph_webhook_validation_get(
    validation_token: Optional[str] = Query(default=None, alias="validationToken"),
):
    """Håndter GET-validering fra Microsoft Graph (noen tenant-/flyt-versjoner)."""
    return await _graph_webhook_validation(validation_token)


@app.post("/graph/webhook")
async def graph_webhook(
    request: Request,
    validation_token: Optional[str] = Query(default=None, alias="validationToken"),
    settings: Settings = Depends(get_app_settings),
):
    """
    Endepunkt for Microsoft Graph-subscription.
    - Ved handshake sender Graph ?validationToken=...
    - Ved vanlige kall mottar vi notifications om nye e‑poster.
    """
    if validation_token is not None:
        return await _graph_webhook_validation(validation_token)

    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Forventet JSON-body med notifications.") from None
    notifications: List[Dict[str, Any]] = data.get("value", [])

    results: List[Dict[str, Any]] = []

    for notification in notifications:
        resource_data = notification.get("resourceData") or {}
        subject = resource_data.get("subject")
        body = None
        body_content_type = "html"

        body_obj = resource_data.get("body")
        if isinstance(body_obj, dict):
            body = body_obj.get("content")
            body_content_type = body_obj.get("contentType", "html")

        message_id = resource_data.get("id")

        if not body and not message_id:
            continue

        if not body and message_id:
            try:
                graph = GraphClient()
                graph_msg = await graph.get_message(message_id)
            except Exception as exc:
                raise HTTPException(status_code=500, detail=str(exc))

            subject = graph_msg.get("subject", subject)
            body_obj = graph_msg.get("body", {}) or {}
            body = body_obj.get("content")
            body_content_type = body_obj.get("contentType", "html")

        if not body:
            continue

        msg = EmailMessage(
            id=message_id,
            subject=subject,
            body=body,
            attachments=[],
        )
        thread = EmailThread(
            conversation_id=resource_data.get("conversationId"),
            messages=[msg],
        )
        response = await process_email_thread_from_graph_payload(thread)

        if response.action == "create_draft_reply" and response.reply_draft and message_id:
            try:
                graph = GraphClient()
                await graph.create_draft_reply(message_id, response.reply_draft.replace("\n", "<br/>"))
            except Exception:
                pass

        results.append(response.dict())

    return {"results": results}

