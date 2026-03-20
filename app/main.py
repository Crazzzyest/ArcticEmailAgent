import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .config import get_settings, Settings
from .email_signature import plain_reply_to_outlook_html
from .models import Attachment, EmailMessage, EmailThread, ProcessThreadRequest, ProcessThreadResponse
from .service import process_email_thread_from_raw, process_email_thread_from_graph_payload
from .graph_client import GraphClient
from .graph_resource import extract_mailbox_user_from_notification
from .subscription_renewal import subscription_renewal_loop
from .webhook_dedupe import (
    abort_message_processing,
    complete_message_processing,
    should_skip_change_type,
    try_begin_message_processing,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for log_name in ("app", "app.main", "app.subscription_renewal", "app.graph_client"):
        logging.getLogger(log_name).setLevel(logging.INFO)
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

    logger.info(
        "Graph webhook: mottatt %d notification(s)",
        len(notifications),
    )
    results: List[Dict[str, Any]] = []
    batch_message_ids: set[str] = set()

    for idx, notification in enumerate(notifications):
        acquired_for_message: bool = False
        mid: Optional[str] = None
        try:
            change_type = notification.get("changeType")
            subscription_id = notification.get("subscriptionId")
            resource = notification.get("resource")
            tenant_id = notification.get("tenantId")
            resource_data = notification.get("resourceData") or {}
            odata_id = resource_data.get("@odata.id") or resource_data.get("id")
            subject = resource_data.get("subject")

            mailbox_user = extract_mailbox_user_from_notification(
                notification, resource_data
            ) or settings.graph_default_mailbox

            logger.info(
                "Graph notification #%s: changeType=%s subscriptionId=%s tenantId=%s resource=%s mailbox=%s resourceData.id=%s",
                idx + 1,
                change_type,
                subscription_id,
                tenant_id,
                resource,
                mailbox_user,
                str(odata_id) if odata_id else None,
            )

            if should_skip_change_type(
                change_type, settings.graph_webhook_only_created
            ):
                logger.info(
                    "Graph notification #%s: hopper over (kun 'created' tillatt, changeType=%s)",
                    idx + 1,
                    change_type,
                )
                results.append(
                    {
                        "ok": True,
                        "skipped": "change_type_not_created",
                        "change_type": change_type,
                        "notification_index": idx + 1,
                    }
                )
                continue

            body = None
            body_content_type = "html"

            body_obj = resource_data.get("body")
            if isinstance(body_obj, dict):
                body = body_obj.get("content")
                body_content_type = body_obj.get("contentType", "html")

            message_id = resource_data.get("id")
            mid = message_id if isinstance(message_id, str) else None

            if not body and not message_id:
                logger.warning(
                    "Graph notification #%s: hopper over (ingen body og ingen meldings-id i resourceData)",
                    idx + 1,
                )
                continue

            if not body and message_id:
                if not mailbox_user:
                    logger.error(
                        "Graph notification #%s: kan ikke hente melding uten postboks (sett GRAPH_DEFAULT_MAILBOX eller sjekk resource i notification)",
                        idx + 1,
                    )
                    results.append(
                        {
                            "ok": False,
                            "error": "missing_mailbox_for_graph_fetch",
                            "notification_index": idx + 1,
                            "message_id": message_id,
                        }
                    )
                    continue
                logger.info(
                    "Graph notification #%s: henter full melding mailbox=%s id=%s",
                    idx + 1,
                    mailbox_user,
                    message_id,
                )
                try:
                    graph = GraphClient()
                    graph_msg = await graph.get_message(message_id, mailbox=mailbox_user)
                except Exception as exc:
                    logger.exception(
                        "Graph notification #%s: feil ved get_message: %s",
                        idx + 1,
                        exc,
                    )
                    results.append(
                        {
                            "ok": False,
                            "error": str(exc),
                            "notification_index": idx + 1,
                            "message_id": message_id,
                        }
                    )
                    continue

                subject = graph_msg.get("subject", subject)
                body_obj = graph_msg.get("body", {}) or {}
                body = body_obj.get("content")
                body_content_type = body_obj.get("contentType", "html")

            if not body:
                logger.warning(
                    "Graph notification #%s: hopper over (ingen body etter henting) id=%s",
                    idx + 1,
                    message_id,
                )
                continue

            if message_id:
                if message_id in batch_message_ids:
                    logger.info(
                        "Graph notification #%s: hopper over (duplikat message_id i samme webhook-batch) id=%s",
                        idx + 1,
                        message_id,
                    )
                    results.append(
                        {
                            "ok": True,
                            "skipped": "duplicate_in_batch",
                            "message_id": message_id,
                            "notification_index": idx + 1,
                        }
                    )
                    continue
                dedupe_ttl = float(settings.graph_webhook_message_dedupe_ttl_seconds)
                if not await try_begin_message_processing(message_id, dedupe_ttl):
                    logger.info(
                        "Graph notification #%s: hopper over (samme melding behandles allerede eller er ferdig nylig) id=%s ttl_s=%s",
                        idx + 1,
                        message_id,
                        int(dedupe_ttl),
                    )
                    results.append(
                        {
                            "ok": True,
                            "skipped": "duplicate_concurrent_or_recent",
                            "message_id": message_id,
                            "notification_index": idx + 1,
                        }
                    )
                    continue
                acquired_for_message = True
                batch_message_ids.add(message_id)

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

            if message_id:
                await complete_message_processing(
                    message_id,
                    float(settings.graph_webhook_message_dedupe_ttl_seconds),
                )
            acquired_for_message = False

            subj_preview = (subject or "")[:120]
            logger.info(
                "Graph notification #%s: behandlet category=%s action=%s confidence=%s subject=%r message_id=%s",
                idx + 1,
                response.category.value,
                response.action,
                response.confidence,
                subj_preview,
                message_id,
            )

            if response.action == "create_draft_reply" and response.reply_draft and message_id:
                if not mailbox_user:
                    logger.error(
                        "Graph notification #%s: kan ikke opprette kladd uten postboks (mailbox)",
                        idx + 1,
                    )
                else:
                    try:
                        graph = GraphClient()
                        await graph.create_draft_reply(
                            message_id,
                            plain_reply_to_outlook_html(response.reply_draft),
                            mailbox=mailbox_user,
                        )
                        logger.info(
                            "Graph notification #%s: kladd-svar opprettet for message_id=%s mailbox=%s",
                            idx + 1,
                            message_id,
                            mailbox_user,
                        )
                    except Exception:
                        logger.exception(
                            "Graph notification #%s: klarte ikke opprette kladd for message_id=%s",
                            idx + 1,
                            message_id,
                        )

            results.append(
                {"ok": True, "data": response.model_dump(mode="json")}
            )
        except Exception as exc:
            if acquired_for_message and mid:
                await abort_message_processing(mid)
            logger.exception(
                "Graph notification #%s: uventet feil: %s", idx + 1, exc
            )
            results.append(
                {
                    "ok": False,
                    "error": str(exc),
                    "notification_index": idx + 1,
                }
            )

    return {"results": results}

