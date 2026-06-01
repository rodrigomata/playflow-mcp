"""Build image management tools (zip upload + docker image)."""

from __future__ import annotations

from typing import Any

from ..app import call, get_client, invalid_args, mcp, needs_confirmation


@mcp.tool()
def list_builds(name: str | None = None, limit: int = 50, offset: int = 0) -> dict[str, Any]:
    """List builds (paginated). name: filter to a specific build name. limit 1-100."""
    return call(get_client().list_builds, name, limit, offset)


@mcp.tool()
def get_build(build_id: str) -> dict[str, Any]:
    """Get one build's details, including status (uploading|processing|ready|failed|deleted)."""
    return call(get_client().get_build, build_id)


@mcp.tool()
def get_build_logs(build_id: str, limit: int = 100, offset: int = 0) -> dict[str, Any]:
    """Get build-pipeline processing logs for a build. limit 1-500 (default 100)."""
    return call(get_client().get_build_logs, build_id, limit, offset)


@mcp.tool()
def upload_build(
    file_path: str,
    name: str = "default",
    executable_path: str = "Server.x86_64",
    confirm: bool = False,
) -> dict[str, Any]:
    """Upload a zipped server build: requests a presigned URL then PUTs the zip to it.

    DESTRUCTIVE-ish: creates a new (billable) build version under `name`. Pass confirm=True.
    name: build identifier (default "default"). executable_path: path to the server
    executable inside the zip (default "Server.x86_64"). Processing starts automatically;
    poll get_build(build_id) until status is ready or failed.
    """
    if not confirm:
        return needs_confirmation("upload_build", name)
    return call(get_client().upload_build, file_path, name, executable_path)


@mcp.tool()
def create_build_from_docker(
    image_url: str,
    name: str = "default",
    executable_path: str | None = None,
    registry_username: str | None = None,
    registry_password: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Create a build from a Docker image URL.

    DESTRUCTIVE-ish: creates a new (billable) build version. Pass confirm=True.
    image_url (required): full image URL with tag. registry_username/registry_password:
    only for private registries. Processing starts automatically; poll get_build(build_id).
    """
    if (registry_username is None) != (registry_password is None):
        return invalid_args(
            "registry_username and registry_password must be provided together."
        )
    if not confirm:
        return needs_confirmation("create_build_from_docker", name)
    body: dict[str, Any] = {"image_url": image_url, "name": name}
    if executable_path is not None:
        body["executable_path"] = executable_path
    if registry_username is not None and registry_password is not None:
        body["registry_credentials"] = {
            "username": registry_username,
            "password": registry_password,
        }
    return call(get_client().create_build_from_docker, body)


@mcp.tool()
def delete_build(build_id: str, confirm: bool = False) -> dict[str, Any]:
    """Soft-delete a build (running servers using it are unaffected).

    DESTRUCTIVE: the build can no longer start new servers. Pass confirm=True to proceed.
    """
    if not confirm:
        return needs_confirmation("delete_build", build_id)
    return call(get_client().delete_build, build_id)
