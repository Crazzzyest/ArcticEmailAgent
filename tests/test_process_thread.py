from app.models import Attachment, ProcessThreadRequest
from app.service import process_email_thread_from_raw
import pytest


@pytest.mark.anyio
async def test_process_thread_basic_flow():
    payload = ProcessThreadRequest(
        subject="Innbytte",
        body="Hei, kan jeg få et tilbud?",
        attachments=[Attachment(name="bilde.jpg", content_type="image/jpeg")],
    )

    result = await process_email_thread_from_raw(
        subject=payload.subject,
        body=payload.body,
        attachments=payload.attachments,
    )
    assert result.action in ("forward_to_human", "create_draft_reply")

