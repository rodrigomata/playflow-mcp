"""Project-level tools (settings and aggregated logs)."""

from __future__ import annotations

from typing import Any

from ..app import call, get_client, mcp


@mcp.tool()
def get_project_settings() -> dict[str, Any]:
    """Get the project's full configuration: port_configs, auth_config, environment
    variables, pool_config, and lobby_configs."""
    return call(get_client().get_project_settings)


@mcp.tool()
def get_project_logs(
    start_time: str, end_time: str | None = None, limit: int = 500
) -> dict[str, Any]:
    """Get aggregated runtime logs across all servers in the project.

    start_time (required): ISO 8601 or relative (e.g. "-1h"). end_time: defaults to now.
    limit: 1-1000 (default 500). The response's next_token paginates.
    """
    return call(get_client().get_project_logs, start_time, end_time, limit)
