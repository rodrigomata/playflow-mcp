# PlayFlow MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local FastMCP (Python) server that wraps the PlayFlow Cloud REST API so an agent can deploy, inspect, and tear down PlayFlow game servers, manage builds/tags, fetch logs/metrics, and manage matchmaking players.

**Architecture:** Three layers — `config.py` (env-based settings), `client.py` (the only module that talks HTTP; owns the `token` header, base URL, timeouts, error normalization), and `server.py` (FastMCP tools that delegate to the client and add confirmation gating on destructive ops). Runs over stdio via `uv run playflow-mcp`.

**Tech Stack:** Python ≥3.10, `mcp` SDK (FastMCP), `httpx`, `pytest`, `pytest-httpx`. Managed with `uv`.

**API facts (pinned from `https://api.cloud.playflow.app/openapi.json`, 2026-05-31):**
- All requests authenticate with a `token` request header.
- Base URL: `https://api.cloud.playflow.app`.
- Most parameters are passed as **HTTP headers** (e.g. `match-id`, `region`, `type`, `server-mode`, `server-tag`, `ttl`, `arguments`, `update`, `include-launching`). `players/add` and `players/remove` use **query** params `match_id` and `ticket_id`. `upload_server_files` uses a multipart `file` body.
- Server identity throughout is `match-id`.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `pyproject.toml` | uv project metadata, deps, `playflow-mcp` console entry point |
| `.env.example` | Documents `PLAYFLOW_API_TOKEN` (+ optional overrides) |
| `src/playflow_mcp/__init__.py` | Package marker, version |
| `src/playflow_mcp/config.py` | `Config` dataclass + `load_config()` from env |
| `src/playflow_mcp/client.py` | `PlayFlowClient` httpx wrapper + `PlayFlowAPIError` |
| `src/playflow_mcp/server.py` | FastMCP app, `_call` helper, all tools, `main()` |
| `tests/test_config.py` | Config loading / missing-token failure |
| `tests/test_client.py` | HTTP behavior against mocked httpx |
| `tests/test_tools.py` | Tool result shaping + confirmation gating against a fake client |
| `README.md` | Setup, env, Claude Code registration, smoke test |

---

## Task 1: Project scaffold + config

**Files:**
- Create: `pyproject.toml`
- Create: `src/playflow_mcp/__init__.py`
- Create: `src/playflow_mcp/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "playflow-mcp"
version = "0.1.0"
description = "MCP server wrapping the PlayFlow Cloud REST API"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.2.0",
    "httpx>=0.27",
]

[project.scripts]
playflow-mcp = "playflow_mcp.server:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/playflow_mcp"]

[dependency-groups]
dev = [
    "pytest>=8",
    "pytest-httpx>=0.30",
]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 2: Create `src/playflow_mcp/__init__.py`**

```python
"""PlayFlow MCP server package."""

__version__ = "0.1.0"
```

- [ ] **Step 3: Write the failing config test**

`tests/test_config.py`:

```python
import pytest

from playflow_mcp.config import Config, ConfigError, load_config


def test_load_config_reads_token(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_TOKEN", "tok-123")
    monkeypatch.delenv("PLAYFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("PLAYFLOW_TIMEOUT", raising=False)
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.api_token == "tok-123"
    assert cfg.base_url == "https://api.cloud.playflow.app"
    assert cfg.timeout == 30.0


def test_load_config_applies_overrides(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_TOKEN", "tok-123")
    monkeypatch.setenv("PLAYFLOW_BASE_URL", "https://api.test/")
    monkeypatch.setenv("PLAYFLOW_TIMEOUT", "5")
    cfg = load_config()
    assert cfg.base_url == "https://api.test"  # trailing slash stripped
    assert cfg.timeout == 5.0


def test_load_config_missing_token_raises(monkeypatch):
    monkeypatch.delenv("PLAYFLOW_API_TOKEN", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_config()
    assert "PLAYFLOW_API_TOKEN" in str(exc.value)
```

- [ ] **Step 4: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'playflow_mcp.config'`

- [ ] **Step 5: Implement `src/playflow_mcp/config.py`**

```python
"""Environment-based configuration for the PlayFlow MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.cloud.playflow.app"
DEFAULT_TIMEOUT = 30.0


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_token: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT


def load_config() -> Config:
    token = os.environ.get("PLAYFLOW_API_TOKEN")
    if not token:
        raise ConfigError(
            "PLAYFLOW_API_TOKEN is not set. Copy .env.example to .env and set your "
            "PlayFlow API token, or export PLAYFLOW_API_TOKEN in your environment."
        )
    base_url = os.environ.get("PLAYFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    timeout = float(os.environ.get("PLAYFLOW_TIMEOUT", DEFAULT_TIMEOUT))
    return Config(api_token=token, base_url=base_url, timeout=timeout)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (3 passed)

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/playflow_mcp/__init__.py src/playflow_mcp/config.py tests/test_config.py
git commit -m "feat: scaffold project and env-based config"
```

---

## Task 2: HTTP client core (request + error normalization)

**Files:**
- Create: `src/playflow_mcp/client.py`
- Test: `tests/test_client.py`

- [ ] **Step 1: Write the failing test**

`tests/test_client.py`:

```python
import pytest

from playflow_mcp.client import PlayFlowAPIError, PlayFlowClient
from playflow_mcp.config import Config


@pytest.fixture
def config():
    return Config(api_token="test-token", base_url="https://api.test", timeout=5.0)


def test_request_sends_token_header_and_returns_json(httpx_mock, config):
    httpx_mock.add_response(
        url="https://api.test/list_servers",
        json={"total_servers": 0, "servers": []},
    )
    client = PlayFlowClient(config)
    result = client.list_servers()
    assert result == {"total_servers": 0, "servers": []}
    request = httpx_mock.get_request()
    assert request.headers["token"] == "test-token"


def test_error_response_raises_with_detail(httpx_mock, config):
    httpx_mock.add_response(status_code=404, json={"detail": "no such server"})
    client = PlayFlowClient(config)
    with pytest.raises(PlayFlowAPIError) as exc:
        client.get_server_status("m1")
    assert exc.value.status == 404
    assert "no such server" in exc.value.detail


def test_empty_body_returns_empty_dict(httpx_mock, config):
    httpx_mock.add_response(status_code=200, content=b"")
    client = PlayFlowClient(config)
    assert client.get_upload_version() == {}


def test_none_headers_are_omitted(httpx_mock, config):
    httpx_mock.add_response(json={"servers": []})
    client = PlayFlowClient(config)
    client.start_game_server()  # all optional args None / default
    request = httpx_mock.get_request()
    assert "region" not in request.headers
    assert request.headers["type"] == "small"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'playflow_mcp.client'`

- [ ] **Step 3: Implement the client core + methods used by the tests**

`src/playflow_mcp/client.py`:

```python
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

    def close(self) -> None:
        self._http.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/playflow_mcp/client.py tests/test_client.py
git commit -m "feat: add PlayFlow HTTP client core and lifecycle methods"
```

---

## Task 3: Remaining client methods (monitoring, builds/tags, players, workflow)

**Files:**
- Modify: `src/playflow_mcp/client.py` (add methods)
- Test: `tests/test_client.py` (add cases)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_client.py`:

```python
def test_get_server_logs_posts_match_id(httpx_mock, config):
    httpx_mock.add_response(json={"logs": "line1\nline2"})
    client = PlayFlowClient(config)
    result = client.get_server_logs("m1")
    assert result == {"logs": "line1\nline2"}
    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.headers["match-id"] == "m1"


def test_upload_server_files_sends_multipart(httpx_mock, tmp_path, config):
    httpx_mock.add_response(json={"status": "uploaded"})
    image = tmp_path / "server.zip"
    image.write_bytes(b"binary-data")
    client = PlayFlowClient(config)
    result = client.upload_server_files(str(image), server_tag="prod")
    assert result == {"status": "uploaded"}
    request = httpx_mock.get_request()
    assert request.headers["server-tag"] == "prod"
    assert b"binary-data" in request.content


def test_delete_server_tag_uses_delete(httpx_mock, config):
    httpx_mock.add_response(json={"status": "deleted"})
    client = PlayFlowClient(config)
    client.delete_server_tag("prod")
    request = httpx_mock.get_request()
    assert request.method == "DELETE"
    assert request.headers["server-tag"] == "prod"


def test_add_player_uses_query_params(httpx_mock, config):
    httpx_mock.add_response(json={"status": "added"})
    client = PlayFlowClient(config)
    client.add_player(match_id="m1", ticket_id="t1")
    request = httpx_mock.get_request()
    assert request.url.params["match_id"] == "m1"
    assert request.url.params["ticket_id"] == "t1"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL — `AttributeError: 'PlayFlowClient' object has no attribute 'get_server_logs'`

- [ ] **Step 3: Add the methods to `client.py`**

Insert before `def close` in `PlayFlowClient`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_client.py -v`
Expected: PASS (8 passed)

- [ ] **Step 5: Commit**

```bash
git add src/playflow_mcp/client.py tests/test_client.py
git commit -m "feat: add monitoring, builds, players, and workflow client methods"
```

---

## Task 4: FastMCP server, `_call` helper, and lifecycle tools

**Files:**
- Create: `src/playflow_mcp/server.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tools.py`:

```python
import playflow_mcp.server as server
from playflow_mcp.client import PlayFlowAPIError


class FakeClient:
    def __init__(self):
        self.calls = []

    def list_servers(self, include_launching=False):
        self.calls.append(("list_servers", include_launching))
        return {"total_servers": 1, "servers": [{"match_id": "m1"}]}

    def stop_game_server(self, match_id):
        self.calls.append(("stop_game_server", match_id))
        return {"status": "Server stopped"}

    def get_server_status(self, match_id):
        raise PlayFlowAPIError(404, "no such server")


def use_fake(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(server, "_client", fake)
    return fake


def test_list_servers_wraps_success(monkeypatch):
    use_fake(monkeypatch)
    out = server.list_servers()
    assert out["ok"] is True
    assert out["data"]["total_servers"] == 1


def test_api_error_is_shaped(monkeypatch):
    use_fake(monkeypatch)
    out = server.get_server_status("m1")
    assert out["ok"] is False
    assert out["error"] == "playflow_api_error"
    assert out["status"] == 404
    assert out["detail"] == "no such server"


def test_stop_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.stop_game_server("m1")
    assert out["ok"] is False
    assert out["error"] == "confirmation_required"
    assert fake.calls == []  # client never called


def test_stop_with_confirm_calls_client(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.stop_game_server("m1", confirm=True)
    assert out["ok"] is True
    assert ("stop_game_server", "m1") in fake.calls
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'playflow_mcp.server'`

- [ ] **Step 3: Implement `src/playflow_mcp/server.py` (app, helpers, lifecycle tools)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS (4 passed)

> Note: FastMCP's `@mcp.tool()` returns the original function, so the tools are directly callable in tests. If a future SDK version changes this, access the underlying callable via `list_servers.fn`.

- [ ] **Step 5: Commit**

```bash
git add src/playflow_mcp/server.py tests/test_tools.py
git commit -m "feat: add FastMCP server with lifecycle tools and confirmation gating"
```

---

## Task 5: Remaining tools (monitoring, builds/tags, players, workflow)

**Files:**
- Modify: `src/playflow_mcp/server.py`
- Test: `tests/test_tools.py`

- [ ] **Step 1: Add failing tests**

Extend `FakeClient` in `tests/test_tools.py` with these methods (add inside the class):

```python
    def get_server_logs(self, match_id):
        self.calls.append(("get_server_logs", match_id))
        return {"logs": "l1\nl2"}

    def upload_server_files(self, file_path, server_tag=None):
        self.calls.append(("upload_server_files", file_path, server_tag))
        return {"status": "uploaded"}

    def delete_server_tag(self, server_tag):
        self.calls.append(("delete_server_tag", server_tag))
        return {"status": "deleted"}

    def add_player(self, match_id, ticket_id):
        self.calls.append(("add_player", match_id, ticket_id))
        return {"status": "added"}
```

Add these test functions:

```python
def test_get_server_logs_passes_through(monkeypatch):
    use_fake(monkeypatch)
    out = server.get_server_logs("m1")
    assert out["ok"] is True
    assert out["data"]["logs"] == "l1\nl2"


def test_delete_tag_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.delete_server_tag("prod")
    assert out["error"] == "confirmation_required"
    assert fake.calls == []


def test_upload_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.upload_server_files("/tmp/x.zip")
    assert out["error"] == "confirmation_required"
    assert fake.calls == []


def test_upload_with_confirm_calls_client(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.upload_server_files("/tmp/x.zip", server_tag="prod", confirm=True)
    assert out["ok"] is True
    assert ("upload_server_files", "/tmp/x.zip", "prod") in fake.calls


def test_add_player_passes_through(monkeypatch):
    fake = use_fake(monkeypatch)
    out = server.add_player(match_id="m1", ticket_id="t1")
    assert out["ok"] is True
    assert ("add_player", "m1", "t1") in fake.calls
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL — `AttributeError: module 'playflow_mcp.server' has no attribute 'get_server_logs'`

- [ ] **Step 3: Add tools to `server.py`**

Insert before `def main()`:

```python
# --- monitoring ----------------------------------------------------------

@mcp.tool()
def get_server_logs(match_id: str) -> dict[str, Any]:
    """Fetch logs for a running server / match by match_id."""
    return _call(get_client().get_server_logs, match_id)


@mcp.tool()
def get_performance_metrics(match_id: str) -> dict[str, Any]:
    """Fetch CPU/memory/performance metrics for a running server by match_id."""
    return _call(get_client().get_performance_metrics, match_id)


# --- builds & tags -------------------------------------------------------

@mcp.tool()
def upload_server_files(
    file_path: str, server_tag: str | None = None, confirm: bool = False
) -> dict[str, Any]:
    """Upload a built server image (zip) to PlayFlow under an optional tag.

    DESTRUCTIVE: overwrites the image for the given tag. Pass confirm=True to proceed.
    """
    if not confirm:
        return _needs_confirmation("upload_server_files", server_tag or "<default tag>")
    return _call(get_client().upload_server_files, file_path, server_tag)


@mcp.tool()
def list_server_tags() -> dict[str, Any]:
    """List all server image tags available on the current plan."""
    return _call(get_client().list_server_tags)


@mcp.tool()
def delete_server_tag(server_tag: str, confirm: bool = False) -> dict[str, Any]:
    """Delete a server image tag.

    DESTRUCTIVE: removes the tagged image. Pass confirm=True to proceed.
    """
    if not confirm:
        return _needs_confirmation("delete_server_tag", server_tag)
    return _call(get_client().delete_server_tag, server_tag)


@mcp.tool()
def get_upload_version() -> dict[str, Any]:
    """Get the current server-image upload version information."""
    return _call(get_client().get_upload_version)


# --- players & matchmaking ----------------------------------------------

@mcp.tool()
def add_player(match_id: str, ticket_id: str) -> dict[str, Any]:
    """Add a player (by matchmaking ticket_id) to a match."""
    return _call(get_client().add_player, match_id=match_id, ticket_id=ticket_id)


@mcp.tool()
def remove_player(match_id: str, ticket_id: str) -> dict[str, Any]:
    """Remove a player (by matchmaking ticket_id) from a match."""
    return _call(get_client().remove_player, match_id=match_id, ticket_id=ticket_id)


@mcp.tool()
def run_workflow(authorization: str | None = None) -> dict[str, Any]:
    """Execute the configured PlayFlow workflow, with an optional authorization header."""
    return _call(get_client().run_workflow, authorization)
```

- [ ] **Step 4: Run the full suite to verify it passes**

Run: `uv run pytest -v`
Expected: PASS (all config + client + tools tests green)

- [ ] **Step 5: Commit**

```bash
git add src/playflow_mcp/server.py tests/test_tools.py
git commit -m "feat: add monitoring, builds, players, and workflow tools"
```

---

## Task 6: Docs, env example, and Claude Code registration

**Files:**
- Create: `.env.example`
- Create/Modify: `README.md`
- Create: `.gitignore`

- [ ] **Step 1: Create `.env.example`**

```bash
# Your PlayFlow API token (required). Find it in the PlayFlow dashboard.
PLAYFLOW_API_TOKEN=

# Optional overrides:
# PLAYFLOW_BASE_URL=https://api.cloud.playflow.app
# PLAYFLOW_TIMEOUT=30
```

- [ ] **Step 2: Create `.gitignore`**

```gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
.env
dist/
*.egg-info/
```

- [ ] **Step 3: Write `README.md`**

```markdown
# playflow-mcp

A local [MCP](https://modelcontextprotocol.io) server that wraps the
[PlayFlow Cloud](https://playflowcloud.com) REST API, giving an agent tools to deploy,
inspect, and tear down PlayFlow game servers, manage build images/tags, fetch logs and
metrics, and manage matchmaking players.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then set PLAYFLOW_API_TOKEN
```

## Run

```bash
PLAYFLOW_API_TOKEN=... uv run playflow-mcp
```

## Register with Claude Code

```bash
claude mcp add playflow \
  --env PLAYFLOW_API_TOKEN=your-token-here \
  -- uv run --directory /Users/rodrigomata/Documents/Development/playflow-mcp playflow-mcp
```

## Tools

Server lifecycle: `list_servers`, `get_server_status`, `start_game_server`,
`restart_game_server`, `stop_game_server`.
Monitoring: `get_server_logs`, `get_performance_metrics`.
Builds & tags: `upload_server_files`, `list_server_tags`, `delete_server_tag`,
`get_upload_version`.
Players & matchmaking: `add_player`, `remove_player`, `run_workflow`.

Destructive tools (`stop_game_server`, `delete_server_tag`, `upload_server_files`) require
`confirm=True`.

## Tests

```bash
uv run pytest
```
```

- [ ] **Step 4: Verify the server starts and lists tools**

Run: `PLAYFLOW_API_TOKEN=dummy uv run python -c "from playflow_mcp.server import mcp; import asyncio; print(sorted(t.name for t in asyncio.run(mcp.list_tools())))"`
Expected: prints the 14 tool names (add_player, delete_server_tag, get_performance_metrics, get_server_logs, get_server_status, get_upload_version, list_server_tags, list_servers, remove_player, restart_game_server, run_workflow, start_game_server, stop_game_server, upload_server_files).

- [ ] **Step 5: Commit**

```bash
git add .env.example .gitignore README.md
git commit -m "docs: add README, env example, and gitignore"
```

---

## Task 7: Optional env-gated live smoke test

**Files:**
- Create: `tests/test_live_smoke.py`

- [ ] **Step 1: Write the gated smoke test**

`tests/test_live_smoke.py`:

```python
import os

import pytest

from playflow_mcp.client import PlayFlowClient
from playflow_mcp.config import load_config

pytestmark = pytest.mark.skipif(
    not (os.environ.get("PLAYFLOW_API_TOKEN") and os.environ.get("PLAYFLOW_LIVE_TESTS") == "1"),
    reason="set PLAYFLOW_API_TOKEN and PLAYFLOW_LIVE_TESTS=1 to run live smoke tests",
)


def test_list_servers_live():
    client = PlayFlowClient(load_config())
    try:
        result = client.list_servers()
    finally:
        client.close()
    assert "servers" in result
```

- [ ] **Step 2: Verify it is skipped by default**

Run: `uv run pytest tests/test_live_smoke.py -v`
Expected: SKIPPED (1 skipped) — no live token configured.

- [ ] **Step 3: Commit**

```bash
git add tests/test_live_smoke.py
git commit -m "test: add optional env-gated live smoke test"
```

---

## Task 8: Final review and wrap-up

- [ ] **Step 1: Run the full suite once more**

Run: `uv run pytest -v`
Expected: all pass except the live smoke test (skipped).

- [ ] **Step 2: Invoke the `pre-merge-review` skill**

This is mandatory before finalizing. It performs the principal-level review, fixes any findings, and handles the final git state.

- [ ] **Step 3: Register the server with Claude Code** (see README Task 6 Step 3 command) and confirm the tools appear via `/mcp` or `claude mcp list`.

---

## Self-Review (completed by plan author)

- **Spec coverage:** All four tool groups (lifecycle, monitoring, builds/tags, players/matchmaking) → Tasks 4–5. Config/token handling → Task 1. Client/auth/error normalization → Tasks 2–3. Confirmation gating on the three destructive tools → Tasks 4–5. Testing strategy (mocked client, fake-client tools, env-gated live) → Tasks 2–5, 7. Docs/registration → Task 6.
- **Placeholder scan:** No TBD/TODO; every code step contains complete code.
- **Type/name consistency:** `match_id` used consistently for server identity across client and tools; client method names match the calls in `server.py` and in both test files; `_call` / `_needs_confirmation` signatures match their call sites.
- **Resolved spec open-questions:** logs/metrics key on `match-id` (not a separate id); `run_workflow` exposes the optional `authorization` header and takes no workflow id (matches the live API).
