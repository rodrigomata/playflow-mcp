"""Thin httpx wrapper around the PlayFlow Cloud REST API.

This is the only module that performs HTTP. It owns authentication (the
``token`` header), the base URL, timeouts, and error normalization.
"""

from __future__ import annotations

from typing import Any

import httpx

from .config import Config


class PlayFlowAPIError(Exception):
    """A non-2xx response from the PlayFlow API."""

    def __init__(self, status: int, detail: str) -> None:
        self.status = status
        self.detail = detail
        super().__init__(f"PlayFlow API error {status}: {detail}")


class PlayFlowClient:
    def __init__(self, config: Config, http_client: httpx.Client | None = None) -> None:
        self._config = config
        self._http = http_client or httpx.Client(
            base_url=config.base_url, timeout=config.timeout
        )

    # --- internals -------------------------------------------------------

    def _headers(self, extra: dict[str, Any] | None = None) -> dict[str, str]:
        headers: dict[str, str] = {"token": self._config.api_token}
        if extra:
            for key, value in extra.items():
                if value is not None:
                    headers[key] = str(value)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        *,
        headers: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        files: dict[str, Any] | None = None,
    ) -> Any:
        response = self._http.request(
            method,
            path,
            headers=self._headers(headers),
            params=params,
            files=files,
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
            return str(body.get("detail") or body.get("message") or body)
        return str(body)

    # --- server lifecycle ------------------------------------------------

    def list_servers(self, include_launching: bool = False) -> Any:
        return self._request(
            "GET",
            "/list_servers",
            headers={"include-launching": str(include_launching).lower()},
        )

    def get_server_status(self, match_id: str) -> Any:
        return self._request("GET", "/get_server_status", headers={"match-id": match_id})

    def start_game_server(
        self,
        region: str | None = None,
        server_type: str = "small",
        server_mode: str | None = None,
        server_tag: str | None = None,
        ttl: int | None = None,
        arguments: str | None = None,
    ) -> Any:
        return self._request(
            "POST",
            "/start_game_server",
            headers={
                "region": region,
                "type": server_type,
                "server-mode": server_mode,
                "server-tag": server_tag,
                "ttl": ttl,
                "arguments": arguments,
            },
        )

    def restart_game_server(
        self,
        match_id: str,
        arguments: str | None = None,
        server_tag: str | None = None,
        update: bool = False,
    ) -> Any:
        return self._request(
            "POST",
            "/restart_game_server",
            headers={
                "match-id": match_id,
                "arguments": arguments,
                "server-tag": server_tag,
                "update": str(update).lower(),
            },
        )

    def stop_game_server(self, match_id: str) -> Any:
        return self._request("DELETE", "/stop_game_server", headers={"match-id": match_id})

    def get_upload_version(self) -> Any:
        return self._request("POST", "/get_upload_version")

    # --- monitoring ------------------------------------------------------

    def get_server_logs(self, match_id: str) -> Any:
        return self._request("POST", "/get_server_logs", headers={"match-id": match_id})

    def get_performance_metrics(self, match_id: str) -> Any:
        return self._request(
            "GET", "/get_performance_metrics", headers={"match-id": match_id}
        )

    # --- builds & tags ---------------------------------------------------

    def upload_server_files(self, file_path: str, server_tag: str | None = None) -> Any:
        with open(file_path, "rb") as handle:
            return self._request(
                "POST",
                "/upload_server_files",
                headers={"server-tag": server_tag},
                files={"file": handle},
            )

    def list_server_tags(self) -> Any:
        return self._request("GET", "/server_tags")

    def delete_server_tag(self, server_tag: str) -> Any:
        return self._request("DELETE", "/server_tags", headers={"server-tag": server_tag})

    # --- players & matchmaking ------------------------------------------

    def add_player(self, match_id: str, ticket_id: str) -> Any:
        return self._request(
            "POST", "/players/add", params={"match_id": match_id, "ticket_id": ticket_id}
        )

    def remove_player(self, match_id: str, ticket_id: str) -> Any:
        return self._request(
            "POST",
            "/players/remove",
            params={"match_id": match_id, "ticket_id": ticket_id},
        )

    def run_workflow(self, authorization: str | None = None) -> Any:
        return self._request(
            "POST", "/get_workflow", headers={"authorization": authorization}
        )

    def close(self) -> None:
        self._http.close()
