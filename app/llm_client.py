from typing import Any, Dict

import httpx

from .config import get_settings


async def generate_reply(prompt: str) -> str:
    """
    Enkel wrapper rundt Anthropics Claude API.
    Forventer at CLAUDE_API_KEY er satt i miljøet.
    """
    settings = get_settings()
    if not settings.claude_api_key:
        raise RuntimeError("CLAUDE_API_KEY / claude_api_key mangler i miljøet.")

    headers = {
        "x-api-key": settings.claude_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    body: Dict[str, Any] = {
        "model": settings.claude_model,
        "max_tokens": 800,
        "messages": [
            {
                "role": "user",
                "content": prompt,
            }
        ],
    }

    async with httpx.AsyncClient(timeout=30) as client:
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

