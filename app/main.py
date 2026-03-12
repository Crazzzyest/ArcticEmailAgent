from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .config import get_settings, Settings
from .models import Attachment, EmailMessage, EmailThread, ProcessThreadRequest, ProcessThreadResponse
from .service import process_email_thread_from_raw, process_email_thread_from_graph_payload
from .graph_client import GraphClient

app = FastAPI(title="Arctic Email Assistant")


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
        return PlainTextResponse(content=validation_token, media_type="text/plain")

    data = await request.json()
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

