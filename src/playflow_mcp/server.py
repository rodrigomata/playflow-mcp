"""FastMCP server exposing PlayFlow Cloud operations as agent tools."""

from __future__ import annotations

from typing import Any, Callable

from mcp.server.fastmcp import FastMCP

from .client import PlayFlowAPIError, PlayFlowClient
from .config import load_config

mcp = FastMCP("playflow")

_client: PlayFlowClient | None = None


def get_client() -> PlayFlowClient:
    global _client
    if _client is None:
        _client = PlayFlowClient(load_config())
    return _client


def _call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> dict[str, Any]:
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


def _needs_confirmation(action: str, target: str) -> dict[str, Any]:
    return {
        "ok": False,
        "error": "confirmation_required",
        "detail": (
            f"{action} on '{target}' is destructive. Re-call with confirm=True to proceed."
        ),
    }


# --- server lifecycle ----------------------------------------------------

@mcp.tool()
def list_servers(include_launching: bool = False) -> dict[str, Any]:
    """List all PlayFlow game servers for the project with status details.

    Set include_launching=True to also include servers that are still starting up.
    """
    return _call(get_client().list_servers, include_launching)


@mcp.tool()
def get_server_status(match_id: str) -> dict[str, Any]:
    """Get the current status and connection details (ip, ports, region) of one server."""
    return _call(get_client().get_server_status, match_id)


@mcp.tool()
def start_game_server(
    region: str | None = None,
    server_type: str = "small",
    server_mode: str | None = None,
    server_tag: str | None = None,
    ttl: int | None = None,
    arguments: str | None = None,
) -> dict[str, Any]:
    """Deploy a new PlayFlow game server.

    region: deployment region (e.g. "us-east"). Omit to use the project default.
    server_type: instance size (default "small").
    server_mode: "persistent_world" or "fast_match".
    server_tag: which uploaded server image/tag to run.
    ttl: optional time-to-live in seconds.
    arguments: optional launch arguments passed to the server process.
    """
    return _call(
        get_client().start_game_server,
        region=region,
        server_type=server_type,
        server_mode=server_mode,
        server_tag=server_tag,
        ttl=ttl,
        arguments=arguments,
    )


@mcp.tool()
def restart_game_server(
    match_id: str,
    arguments: str | None = None,
    server_tag: str | None = None,
    update: bool = False,
) -> dict[str, Any]:
    """Restart a running server, optionally updating its image (update=True) or launch args."""
    return _call(
        get_client().restart_game_server,
        match_id=match_id,
        arguments=arguments,
        server_tag=server_tag,
        update=update,
    )


@mcp.tool()
def stop_game_server(match_id: str, confirm: bool = False) -> dict[str, Any]:
    """Terminate a running game server and clean up its resources.

    DESTRUCTIVE: this kills the server and any live match on it. Pass confirm=True to proceed.
    """
    if not confirm:
        return _needs_confirmation("stop_game_server", match_id)
    return _call(get_client().stop_game_server, match_id)


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
