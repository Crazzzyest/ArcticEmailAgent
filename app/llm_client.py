from typing import Any, Dict, List, Optional

import httpx

from .config import get_settings
from .models import Attachment

# Bildetyper Claude Vision støtter
_SUPPORTED_IMAGE_TYPES = frozenset({
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
})

# Maks bildestørrelse vi sender til Claude (5 MB base64 ≈ 3.75 MB rå)
_MAX_IMAGE_BYTES_B64 = 5 * 1024 * 1024


def _build_image_content_blocks(
    attachments: Optional[List[Attachment]],
) -> List[Dict[str, Any]]:
    """
    Bygger Claude Vision content-blokker for bildevedlegg.
    Returnerer tom liste hvis ingen bilder er tilgjengelige.
    """
    if not attachments:
        return []
    blocks: List[Dict[str, Any]] = []
    for att in attachments:
        if (
            not att.content_bytes
            or not att.content_type
            or att.content_type not in _SUPPORTED_IMAGE_TYPES
        ):
            continue
        if len(att.content_bytes) > _MAX_IMAGE_BYTES_B64:
            continue
        blocks.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": att.content_type,
                    "data": att.content_bytes,
                },
            }
        )
    return blocks


async def generate_reply(
    prompt: str,
    attachments: Optional[List[Attachment]] = None,
) -> str:
    """
    Wrapper rundt Anthropics Claude API med støtte for multimodalt innhold.
    Sender bildevedlegg sammen med tekst slik at Claude kan analysere dem.
    """
    settings = get_settings()
    if not settings.claude_api_key:
        raise RuntimeError("CLAUDE_API_KEY / claude_api_key mangler i miljøet.")

    headers = {
        "x-api-key": settings.claude_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # Bygg content: bilder først, deretter tekst-prompt
    content_blocks: List[Dict[str, Any]] = _build_image_content_blocks(attachments)
    content_blocks.append({"type": "text", "text": prompt})

    body: Dict[str, Any] = {
        "model": settings.claude_model,
        "max_tokens": 800,
        "messages": [
            {
                "role": "user",
                "content": content_blocks,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=body,
        )
        resp.raise_for_status()
        data = resp.json()

    content = data.get("content", [])
    if content and isinstance(content, list):
        first = content[0]
        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str):
                return text

    raise RuntimeError("Uventet svarformat fra Claude API.")
