"""
pipeline/clients/perplexity_client.py
─────────────────────────────────────
Thin wrapper around the Perplexity Sonar API.

Perplexity uses an OpenAI-compatible /chat/completions interface, but the
top-level `citations` field is dropped by the OpenAI Python SDK because it
isn't part of the canonical schema. So we hit the endpoint directly with
httpx and surface `{content, citations, raw}`.

Sync and async variants share the same return shape.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from config import PERPLEXITY_BASE_URL
from pipeline.observability import traced


_PERPLEXITY_URL = f"{PERPLEXITY_BASE_URL}/chat/completions"
_DEFAULT_TIMEOUT = 180.0


def _build_payload(
    messages: list[dict],
    model: str,
    temperature: float,
    max_tokens: int,
    extra: Optional[dict] = None,
) -> dict:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if extra:
        payload.update(extra)
    return payload


def _headers(api_key: Optional[str]) -> dict:
    key = api_key or os.getenv("PERPLEXITY_API_KEY")
    if not key:
        raise RuntimeError("PERPLEXITY_API_KEY not set in environment.")
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


def _shape(data: dict) -> dict:
    """Normalize Perplexity response to {content, citations, raw}."""
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        content = ""
    citations = data.get("citations") or data.get("search_results") or []
    # Sometimes citations live under choices[0].message.context — be lenient.
    if not citations:
        try:
            citations = data["choices"][0]["message"].get("citations", []) or []
        except (KeyError, IndexError, TypeError):
            citations = []
    return {"content": content, "citations": citations, "raw": data}


# ─────────────────────────────────────────────────────────────────
#  Sync
# ─────────────────────────────────────────────────────────────────

@traced(run_type="llm", name="perplexity_complete")
def perplexity_complete(
    messages: list[dict],
    model: str = "sonar-pro",
    temperature: float = 0.3,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    extra: Optional[dict] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict:
    """Synchronous Perplexity chat completion."""
    payload = _build_payload(messages, model, temperature, max_tokens, extra)
    headers = _headers(api_key)
    with httpx.Client(timeout=timeout) as client:
        resp = client.post(_PERPLEXITY_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return _shape(resp.json())


# ─────────────────────────────────────────────────────────────────
#  Async (used by Council 2)
# ─────────────────────────────────────────────────────────────────

@traced(run_type="llm", name="perplexity_complete_async")
async def perplexity_complete_async(
    messages: list[dict],
    model: str = "sonar",
    temperature: float = 0.15,
    max_tokens: int = 4096,
    api_key: Optional[str] = None,
    extra: Optional[dict] = None,
    timeout: float = _DEFAULT_TIMEOUT,
) -> dict:
    """Async Perplexity chat completion."""
    payload = _build_payload(messages, model, temperature, max_tokens, extra)
    headers = _headers(api_key)
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(_PERPLEXITY_URL, json=payload, headers=headers)
        resp.raise_for_status()
        return _shape(resp.json())
