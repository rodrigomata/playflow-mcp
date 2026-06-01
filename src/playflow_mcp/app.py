"""Shared FastMCP app instance, client accessor, and result helpers.

Tool modules import from here and register their tools on ``mcp``. ``server.py``
imports the tool modules to trigger registration and exposes ``main()``.
"""

from __future__ import annotations

import threading
from typing import Any, Callable

import httpx
from mcp.server.fastmcp import FastMCP

from .client import PlayFlowAPIError, PlayFlowClient
from .config import load_config

mcp = FastMCP("playflow")

_client: PlayFlowClient | None = None
_client_lock = threading.Lock()


def get_client() -> PlayFlowClient:
    # Double-checked locking: FastMCP can dispatch sync tools on a thread pool,
    # so guard lazy init to avoid racing two PlayFlowClient instances (extra sockets).
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                _client = PlayFlowClient(load_config())
    return _client


def call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Invoke a client method and normalize success/error into a dict."""
    try:
        return {"ok": True, "data": fn(*args, **kwargs)}
    except PlayFlowAPIError as exc:
        return {
            "ok": False,
            "error": "playflow_api_error",
            "status": exc.status,
            "detail": exc.detail,
        }
    except (httpx.HTTPError, OSError) as exc:
        # Network failures (timeout, DNS, connection refused) and local file
        # errors (e.g. a missing upload path) surface as actionable text rather
        # than an uncaught traceback.
        return {"ok": False, "error": "request_failed", "detail": str(exc)}


def needs_confirmation(action: str, target: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "confirmation_required",
        "detail": (
            f"{action} on '{target}' is destructive. Re-call with confirm=True to proceed."
        ),
    }


def invalid_args(detail: str) -> dict[str, Any]:
    """Structured error for client-side argument validation (no API call made)."""
    return {"ok": False, "error": "invalid_arguments", "detail": detail}
