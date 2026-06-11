"""
pipeline/observability.py
──────────────────────────
LangSmith observability layer.

Exposes:
  • @traced — drop-in replacement for langsmith.traceable that no-ops when
    langsmith isn't installed or LANGSMITH_TRACING is disabled.
  • wrap_anthropic_client / wrap_openai_client — client wrappers that emit
    detailed LLM-level traces when available, transparent passthrough otherwise.
  • make_session_id — generates a unique, human-readable session identifier.
  • attach_session_metadata — attaches session_id/thread_id to the current run
    tree so LangSmith's Threads UI groups all six pipeline stages together.

Environment variables (all optional):
  LANGSMITH_TRACING=true              enable tracing
  LANGSMITH_API_KEY=ls_...            your API key
  LANGSMITH_PROJECT=research-pipeline (optional, defaults to "default")
  LANGSMITH_ENDPOINT=...              (optional, self-hosted only)
"""

from __future__ import annotations

import os
import re
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

# ── Soft imports — degrade gracefully when langsmith isn't installed ──
try:
    from langsmith import traceable as _ls_traceable
    from langsmith.run_helpers import get_current_run_tree
    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    _ls_traceable = None

    def get_current_run_tree():  # type: ignore
        return None

try:
    from langsmith.wrappers import wrap_openai as _ls_wrap_openai
except ImportError:
    _ls_wrap_openai = None

try:
    from langsmith.wrappers import wrap_anthropic as _ls_wrap_anthropic
except ImportError:
    _ls_wrap_anthropic = None


def _tracing_enabled() -> bool:
    """True iff langsmith is installed AND credentials are present AND tracing is on."""
    if not _LANGSMITH_AVAILABLE:
        return False
    if not os.getenv("LANGSMITH_API_KEY"):
        return False
    return os.getenv("LANGSMITH_TRACING", "").lower() in ("true", "1", "yes")


# ─────────────────────────────────────────────────────────────────
#  @traced decorator
# ─────────────────────────────────────────────────────────────────

def traced(*, run_type: str = "chain", name: Optional[str] = None,
           tags: Optional[list] = None, **kwargs) -> Callable:
    """
    Decorator that traces a function with LangSmith when available; no-ops
    when langsmith is missing or LANGSMITH_TRACING is disabled.

    Usage:
        @traced(run_type="llm", name="claude_lens")
        async def my_func(...): ...
    """
    def decorator(func: Callable) -> Callable:
        if _ls_traceable is None:
            return func
        return _ls_traceable(
            run_type=run_type,
            name=name or func.__name__,
            tags=tags,
            **kwargs,
        )(func)
    return decorator


# ─────────────────────────────────────────────────────────────────
#  Client auto-instrumentation
# ─────────────────────────────────────────────────────────────────

def wrap_anthropic_client(client):
    """Wrap an anthropic.Anthropic or anthropic.AsyncAnthropic for autolog."""
    if _ls_wrap_anthropic is None or not _tracing_enabled():
        return client
    try:
        return _ls_wrap_anthropic(client)
    except Exception:
        return client


def wrap_openai_client(client):
    """Wrap an openai.OpenAI or openai.AsyncOpenAI for autolog."""
    if _ls_wrap_openai is None or not _tracing_enabled():
        return client
    try:
        return _ls_wrap_openai(client)
    except Exception:
        return client


# ─────────────────────────────────────────────────────────────────
#  Session helpers
# ─────────────────────────────────────────────────────────────────

def _slugify(text: str, max_len: int = 30) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return s[:max_len].rstrip("-") or "session"


def make_session_id(domain: str) -> str:
    """
    Build a unique, human-readable session ID for this pipeline run.
    Example: "ai-creativity-homogenization-20260609-143012-a7b3f1"
    """
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{_slugify(domain)}-{ts}-{uuid.uuid4().hex[:6]}"


def attach_session_metadata(session_id: str, **extra: Any) -> None:
    """
    Attach session_id + thread_id (and optional extras) to the current
    LangSmith run tree so all six pipeline stages group under one thread.

    Must be called from inside a @traced function. Safe no-op when tracing
    is disabled or no current run exists.
    """
    if not _tracing_enabled():
        return
    try:
        rt = get_current_run_tree()
        if rt is None:
            return
        if rt.metadata is None:
            rt.metadata = {}
        rt.metadata["session_id"] = session_id
        rt.metadata["thread_id"]  = session_id     # LangSmith Threads UI groups by this
        for k, v in extra.items():
            rt.metadata[k] = v
        existing_tags = list(rt.tags or [])
        new_tag = f"session:{session_id}"
        if new_tag not in existing_tags:
            existing_tags.append(new_tag)
        rt.tags = existing_tags
    except Exception:
        pass


def langsmith_status() -> str:
    """One-line human-readable status — used by the orchestrator + sidebar."""
    if not _LANGSMITH_AVAILABLE:
        return "LangSmith: package not installed (pip install langsmith)"
    if not _tracing_enabled():
        return "LangSmith: disabled (set LANGSMITH_TRACING=true + LANGSMITH_API_KEY)"
    project = os.getenv("LANGSMITH_PROJECT", "default")
    return f"LangSmith: ✓ active (project: {project})"