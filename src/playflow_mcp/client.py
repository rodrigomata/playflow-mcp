"""Thin httpx wrapper around the PlayFlow Cloud v3 REST API.

This is the only module that performs HTTP. It owns authentication (the
``api-key`` header), the base URL + ``/api/v3`` prefix, timeouts, and error
normalization. PlayFlow already returns errors shaped ``{error, detail,
status}``; non-2xx responses are surfaced via :class:`PlayFlowAPIError`.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Config

API_PREFIX = "/api/v3"


class PlayFlowAPIError(Exception):
    """A non-2xx response from the PlayFlow API."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"PlayFlow API error {status}: {detail}")


def _clean(params: dict[str, Any] | None) -> dict[str, str] | None:
    """Drop None values and render booleans as 'true'/'false' for query/header use."""
    if not params:
        return None
    cleaned: dict[str, str] = {}
    for key, value in params.items():
        if value is None:
            continue
        if isinstance(value, bool):
            cleaned[key] = "true" if value else "false"
        else:
            cleaned[key] = str(value)
    return cleaned


class PlayFlowClient:
    def __init__(self, config: Config, http_client: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http_client or httpx.Client(
            base_url=config.base_url, timeout=config.timeout
        )

    # --- internals -------------------------------------------------------

    def _headers(self, player_id: str | None = None) -> dict[str, str]:
        headers = {"api-key": self._config.api_key}
        if player_id is not None:
            headers["x-player-id"] = player_id
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        player_id: str | None = None,
        params: dict[str, Any] | None = None,
        json: Any | None = None,
    ) -> Any:
        response = self._http.request(
            method,
            f"{API_PREFIX}{path}",
            headers=self._headers(player_id),
            params=_clean(params),
            json=json,
        )
        if response.status_code >= 400:
            raise PlayFlowAPIError(response.status_code, self._extract_detail(response))
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    @staticmethod
    def _extract_detail(response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            return response.text or response.reason_phrase
        if isinstance(body, dict):
            return str(body.get("detail") or body.get("error") or body.get("message") or body)
        return str(body)

    # ====================================================================
    # Servers
    # ====================================================================

    def list_servers(
        self,
        include_launching: bool = False,
        include_pool: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        return self._request(
            "GET",
            "/servers",
            params={
                "include_launching": include_launching,
                "include_pool": include_pool,
                "limit": limit,
                "offset": offset,
            },
        )

    def get_server(self, instance_id: str) -> Any:
        return self._request("GET", f"/servers/{instance_id}")

    def start_server(self, body: dict[str, Any]) -> Any:
        return self._request("POST", "/servers/start", json=body)

    def stop_server(self, instance_id: str, shutdown_reason: str | None = None) -> Any:
        return self._request(
            "DELETE",
            f"/servers/{instance_id}",
            params={"shutdown_reason": shutdown_reason},
        )

    def restart_server(self, instance_id: str, body: dict[str, Any] | None = None) -> Any:
        return self._request("POST", f"/servers/{instance_id}/restart", json=body or {})

    def get_server_metrics(
        self, instance_id: str, period: str = "1h", step: str = "60s"
    ) -> Any:
        return self._request(
            "GET",
            f"/servers/{instance_id}/metrics",
            params={"period": period, "step": step},
        )

    def get_server_logs(
        self, instance_id: str, start_time: str | None = None, limit: int = 200
    ) -> Any:
        return self._request(
            "GET",
            f"/servers/{instance_id}/logs",
            params={"start_time": start_time, "limit": limit},
        )

    def update_server_custom_data(
        self, instance_id: str, custom_data: dict[str, Any]
    ) -> Any:
        return self._request(
            "POST", f"/servers/{instance_id}/update", json={"custom_data": custom_data}
        )

    # ====================================================================
    # Builds
    # ====================================================================

    def list_builds(self, name: str | None = None, limit: int = 50, offset: int = 0) -> Any:
        return self._request(
            "GET", "/builds", params={"name": name, "limit": limit, "offset": offset}
        )

    def get_build(self, build_id: str) -> Any:
        return self._request("GET", f"/builds/{build_id}")

    def get_build_logs(self, build_id: str, limit: int = 100, offset: int = 0) -> Any:
        return self._request(
            "GET", f"/builds/{build_id}/logs", params={"limit": limit, "offset": offset}
        )

    def create_build_from_docker(self, body: dict[str, Any]) -> Any:
        return self._request("POST", "/builds/docker-image", json=body)

    def delete_build(self, build_id: str) -> Any:
        return self._request("DELETE", f"/builds/{build_id}")

    def upload_build(
        self,
        file_path: str,
        name: str = "default",
        executable_path: str = "Server.x86_64",
    ) -> Any:
        """Two-step zip upload: request a presigned URL, then PUT the zip to it.

        Returns the presigned-URL response (includes ``build_id``); processing
        starts automatically — poll ``get_build(build_id)`` until status is
        ``ready`` or ``failed``.
        """
        presigned = self._request(
            "POST",
            "/builds/upload-url",
            params={"name": name, "executable_path": executable_path},
        )
        upload_url = presigned.get("upload_url") if isinstance(presigned, dict) else None
        if not upload_url:
            raise PlayFlowAPIError(
                502, f"upload-url response missing 'upload_url': {presigned!r}"
            )
        # The presigned URL is a storage URL that must NOT receive our api-key
        # header; use a bare request that streams the file body.
        with open(file_path, "rb") as handle:
            put_response = httpx.put(
                upload_url, content=handle, timeout=self._config.timeout
            )
        if put_response.status_code >= 400:
            raise PlayFlowAPIError(
                put_response.status_code,
                f"Upload PUT failed: {put_response.text or put_response.reason_phrase}",
            )
        return presigned

    # ====================================================================
    # Projects
    # ====================================================================

    def get_project_settings(self) -> Any:
        return self._request("GET", "/projects/settings")

    def get_project_logs(
        self, start_time: str, end_time: str | None = None, limit: int = 500
    ) -> Any:
        return self._request(
            "GET",
            "/projects/logs",
            params={"start_time": start_time, "end_time": end_time, "limit": limit},
        )

    # ====================================================================
    # Lobbies & matchmaking
    # ====================================================================

    def browse_lobbies(
        self,
        config: str,
        region: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Any:
        return self._request(
            "GET",
            f"/lobbies/{config}",
            params={"region": region, "status": status, "limit": limit, "offset": offset},
        )

    def create_lobby(self, config: str, player_id: str, body: dict[str, Any]) -> Any:
        return self._request("POST", f"/lobbies/{config}", player_id=player_id, json=body)

    def get_lobby(self, config: str, lobby_id: str) -> Any:
        return self._request("GET", f"/lobbies/{config}/{lobby_id}")

    def delete_lobby(self, config: str, lobby_id: str) -> Any:
        return self._request("DELETE", f"/lobbies/{config}/{lobby_id}")

    def get_my_lobby(self, config: str, player_id: str) -> Any:
        return self._request("GET", f"/lobbies/{config}/me", player_id=player_id)

    def join_lobby(self, config: str, player_id: str, body: dict[str, Any]) -> Any:
        return self._request(
            "POST", f"/lobbies/{config}/join", player_id=player_id, json=body
        )

    def leave_lobby(self, config: str, player_id: str) -> Any:
        return self._request("DELETE", f"/lobbies/{config}/me", player_id=player_id)

    def kick_player(self, config: str, player_id: str, target_player_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/lobbies/{config}/me/players/{target_player_id}",
            player_id=player_id,
        )

    def update_my_player_state(
        self, config: str, player_id: str, state: dict[str, Any]
    ) -> Any:
        return self._request(
            "PATCH", f"/lobbies/{config}/me", player_id=player_id, json={"state": state}
        )

    def update_lobby_settings(
        self, config: str, player_id: str, body: dict[str, Any]
    ) -> Any:
        return self._request(
            "PATCH", f"/lobbies/{config}/me/settings", player_id=player_id, json=body
        )

    def send_heartbeat(self, config: str, player_id: str) -> Any:
        return self._request(
            "POST", f"/lobbies/{config}/me/heartbeat", player_id=player_id
        )

    def start_matchmaking(self, config: str, player_id: str, mode: str) -> Any:
        return self._request(
            "POST",
            f"/lobbies/{config}/me/matchmaking",
            player_id=player_id,
            json={"mode": mode},
        )

    def cancel_matchmaking(self, config: str, player_id: str) -> Any:
        return self._request(
            "DELETE", f"/lobbies/{config}/me/matchmaking", player_id=player_id
        )

    def confirm_match(self, config: str, player_id: str) -> Any:
        return self._request(
            "POST", f"/lobbies/{config}/me/confirm-match", player_id=player_id
        )

    def decline_match(self, config: str, player_id: str) -> Any:
        return self._request(
            "DELETE", f"/lobbies/{config}/me/confirm-match", player_id=player_id
        )

    def start_game(self, config: str, player_id: str) -> Any:
        return self._request(
            "POST", f"/lobbies/{config}/me/start", player_id=player_id
        )

    def end_match(self, config: str, player_id: str) -> Any:
        return self._request(
            "POST", f"/lobbies/{config}/me/end-match", player_id=player_id
        )

    def close(self) -> None:
        self._http.close()
