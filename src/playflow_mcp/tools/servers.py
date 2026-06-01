"""Server lifecycle, monitoring, and metadata tools."""

from __future__ import annotations

from typing import Any

from ..app import call, get_client, mcp, needs_confirmation


@mcp.tool()
def list_servers(
    include_launching: bool = False,
    include_pool: bool = False,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List game servers (paginated).

    include_launching: also include servers still starting up.
    include_pool: also include pre-provisioned pool servers.
    limit: page size, 1-100 (default 50). offset: pagination offset.
    """
    return call(get_client().list_servers, include_launching, include_pool, limit, offset)


@mcp.tool()
def get_server(instance_id: str) -> dict[str, Any]:
    """Get one server's full details, including network_ports for client connections."""
    return call(get_client().get_server, instance_id)


@mcp.tool()
def start_server(
    name: str,
    region: str,
    compute_size: str = "small",
    version_tag: str = "default",
    version: int | None = None,
    startup_args: str | None = None,
    ttl: int | None = None,
    auto_restart: bool = False,
    custom_data: dict[str, Any] | None = None,
    match_id: str | None = None,
    environment_variables: dict[str, str] | None = None,
    port_configs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Deploy a new game server.

    name (required): display name. region (required): e.g. us-east, us-west, eu-west,
    eu-north, eu-uk, ap-south, ap-north, sea, ap-southeast, south-america, south-africa.
    compute_size: micro|small|medium|large|xlarge|dedicated-*|persistent-* (default small).
    version_tag: build name to deploy (default "default"). version: pin a build version.
    ttl: time-to-live seconds, 60-86400. port_configs: list of
    {name, internal_port, protocol(udp|tcp), tls_enabled?}.
    """
    body: dict[str, Any] = {
        "name": name,
        "region": region,
        "compute_size": compute_size,
        "version_tag": version_tag,
        "auto_restart": auto_restart,
    }
    if version is not None:
        body["version"] = version
    if startup_args is not None:
        body["startup_args"] = startup_args
    if ttl is not None:
        body["ttl"] = ttl
    if custom_data is not None:
        body["custom_data"] = custom_data
    if match_id is not None:
        body["match_id"] = match_id
    if environment_variables is not None:
        body["environment_variables"] = environment_variables
    if port_configs is not None:
        body["port_configs"] = port_configs
    return call(get_client().start_server, body)


@mcp.tool()
def stop_server(
    instance_id: str, shutdown_reason: str | None = None, confirm: bool = False
) -> dict[str, Any]:
    """Stop and tear down a server.

    DESTRUCTIVE: kills the server and any live match on it. Pass confirm=True to proceed.
    shutdown_reason: optional, e.g. PROCESS_EXITED, TTL_EXPIRED, SHUTDOWN_SIGNAL.
    """
    if not confirm:
        return needs_confirmation("stop_server", instance_id)
    return call(get_client().stop_server, instance_id, shutdown_reason)


@mcp.tool()
def restart_server(
    instance_id: str,
    name: str | None = None,
    startup_args: str | None = None,
    version_tag: str | None = None,
    version: int | None = None,
    ttl: int | None = None,
    auto_restart: bool | None = None,
    custom_data: dict[str, Any] | None = None,
    match_id: str | None = None,
    environment_variables: dict[str, str] | None = None,
    port_configs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Restart a server. All fields optional; omitted fields keep current values.

    Use version_tag/version to switch builds. Pool servers cannot be restarted.
    """
    body: dict[str, Any] = {}
    for key, value in {
        "name": name,
        "startup_args": startup_args,
        "version_tag": version_tag,
        "version": version,
        "ttl": ttl,
        "auto_restart": auto_restart,
        "custom_data": custom_data,
        "match_id": match_id,
        "environment_variables": environment_variables,
        "port_configs": port_configs,
    }.items():
        if value is not None:
            body[key] = value
    return call(get_client().restart_server, instance_id, body)


@mcp.tool()
def get_server_metrics(
    instance_id: str, period: str = "1h", step: str = "60s"
) -> dict[str, Any]:
    """Get CPU/memory/network/load/connection time-series metrics for a server.

    period: 5m|15m|1h|6h|24h (default 1h). step: 15s|30s|60s|300s (default 60s).
    """
    return call(get_client().get_server_metrics, instance_id, period, step)


@mcp.tool()
def get_server_logs(
    instance_id: str, start_time: str | None = None, limit: int = 200
) -> dict[str, Any]:
    """Get runtime logs for a server.

    start_time: ISO 8601 or relative (e.g. "-1h", "-30m"). limit: 1-1000 (default 200).
    The response's next_token can be passed as the next start_time to paginate.
    """
    return call(get_client().get_server_logs, instance_id, start_time, limit)


@mcp.tool()
def update_server_custom_data(
    instance_id: str, custom_data: dict[str, Any]
) -> dict[str, Any]:
    """Replace a server's custom_data (arbitrary metadata: match state, player counts, etc.)."""
    return call(get_client().update_server_custom_data, instance_id, custom_data)
