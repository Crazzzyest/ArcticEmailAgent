from .business_rules import check_service_requirements, check_trade_in_requirements
from .classifier import classify_text
from .email_parser import normalize_email_body
from .models import (
    Attachment,
    Category,
    EmailThread,
    ProcessThreadResponse,
)
from .reply_drafter import draft_reply_for_category


async def process_email_thread_from_raw(
    subject: str | None,
    body: str,
    attachments: list[Attachment],
) -> ProcessThreadResponse:
    """
    For test-endepunktet: vi får bare emne + tekst + vedlegg.
    """
    normalized = normalize_email_body(body, is_html=False)
    classification = classify_text(f"{subject or ''}\n\n{normalized}")

    if classification.category == Category.TRADE_IN:
        _ = check_trade_in_requirements(normalized, attachments)
    elif classification.category == Category.SERVICE:
        _ = check_service_requirements(normalized, attachments)

    response = await draft_reply_for_category(
        classification.category,
        normalized,
        attachments,
    )

    response.confidence = response.confidence or classification.confidence
    return response


async def process_email_thread_from_graph_payload(
    thread: EmailThread,
) -> ProcessThreadResponse:
    """
    En enkel versjon som bruker siste melding i tråden som basis.
    """
    latest = thread.messages[-1]
    normalized = normalize_email_body(latest.body, is_html=True)
    classification = classify_text(f"{latest.subject or ''}\n\n{normalized}")

    if classification.category == Category.TRADE_IN:
        _ = check_trade_in_requirements(normalized, latest.attachments)
    elif classification.category == Category.SERVICE:
        _ = check_service_requirements(normalized, latest.attachments)

    response = await draft_reply_for_category(
        classification.category,
        normalized,
        latest.attachments,
    )
    response.confidence = response.confidence or classification.confidence
    return response

