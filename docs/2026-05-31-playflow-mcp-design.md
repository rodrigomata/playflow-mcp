# PlayFlow MCP Server — Design

**Date:** 2026-05-31
**Status:** Implemented — **retargeted to the PlayFlow v3 API** (see "v3 revision" below)
**Repo:** `/Users/rodrigomata/Documents/Development/playflow-mcp` (standalone)

> ## ⚠️ v3 revision (supersedes the legacy specifics below)
>
> The original design targeted the legacy API at `api.cloud.playflow.app` with a `token`
> header and RPC-style endpoints. That is an older API generation. The MCP was retargeted to
> the **current PlayFlow v3 API**:
>
> - **Base URL:** `https://api.computeflow.cloud` (paths under `/api/v3`); overridable via
>   `PLAYFLOW_BASE_URL`.
> - **Auth header:** `api-key` (server key `pf_...`), from `PLAYFLOW_API_KEY`
>   (legacy `PLAYFLOW_API_TOKEN` still accepted as a fallback).
> - **Errors:** PlayFlow already returns `{error, detail, status}`; surfaced via
>   `PlayFlowAPIError` → normalized to `{ok: False, error, status, detail}`.
> - **Params:** proper path / query / JSON body (not all-headers). Server identity is the
>   `instance_id` path param; builds use `build_id`; lobbies use a `{config}` path segment and
>   an `x-player-id` header for player-scoped ops.
>
> **Tool surface: 33 tools** — Servers (8), Builds (6), Projects (2), Lobbies/matchmaking (17).
> Destructive tools (`stop_server`, `delete_build`, `upload_build`, `create_build_from_docker`,
> `delete_lobby`) keep the `confirm=True` gate. The lobby SSE stream
> (`/lobbies/{config}/me/events`) is intentionally not wrapped — a long-lived
> `text/event-stream` connection can't be a request/response tool.
>
> **Code layout (revised):** `config.py` → `client.py` (single HTTP boundary, all v3 methods)
> → `app.py` (shared `mcp`, `get_client`, `call`, `needs_confirmation`) → `tools/{servers,
> builds,projects,lobbies}.py` (register tools) → `server.py` (`main()`). Tools were split by
> resource because 33 tools in one file is unwieldy.

## Purpose

A local [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the
[PlayFlow Cloud](https://playflowcloud.com) REST API, so an agent (Claude Code) can deploy,
inspect, and tear down PlayFlow game servers — and manage builds, logs, and matchmaking —
directly from a development session. Built for the Spellpaws project's PlayFlow hosting, but
kept project-agnostic so it is reusable.

No official or community PlayFlow MCP exists (verified against the MCP registry and GitHub on
2026-05-31), so this is built from scratch over PlayFlow's documented REST API.

## Approach

**Curated hand-written tools** (chosen over OpenAPI auto-generation). One FastMCP tool per
meaningful PlayFlow operation, with hand-tuned names, descriptions, typed parameters, and
guardrails on destructive calls. The API surface is small (~13 operations), so hand-writing is
cheap and yields far better agent ergonomics than raw passthrough of names like
`get_workflow` / `upload_server_files`.

## Architecture & layout

```
playflow-mcp/
  pyproject.toml          # uv-managed; console entry point `playflow-mcp`
  src/playflow_mcp/
    __init__.py
    server.py             # FastMCP app + tool registration (no HTTP logic)
    client.py             # thin httpx wrapper around the PlayFlow REST API (owns auth)
    config.py             # env: PLAYFLOW_API_TOKEN, base URL, timeouts
    models.py             # pydantic types for params / returns
  tests/
    test_client.py        # httpx mocked
    test_tools.py         # tools against a fake client
  README.md
  .env.example
```

- **`client.py`** is the only module that talks HTTP. It owns auth (the `token` header), the
  base URL `https://api.cloud.playflow.app`, timeouts, and error normalization.
- **`server.py`** defines FastMCP tools that delegate to the client. No HTTP logic here.
- **`config.py`** reads `PLAYFLOW_API_TOKEN` (required), plus optional `PLAYFLOW_BASE_URL` and
  `PLAYFLOW_TIMEOUT` overrides. Token is never a tool parameter.
- Runs over **stdio**, launched via `uvx --from . playflow-mcp` or `uv run playflow-mcp`, and
  registered in Claude Code's MCP config.

## Tool surface (~13 tools)

### Server lifecycle
- `list_servers()` → all servers for the project with status.
- `get_server_status(server_id)` → details for one server.
- `start_game_server(region, server_size, mode, tag?, custom_args?)` → deploy a new server.
- `restart_game_server(server_id, custom_args?)` → restart, optionally with new args.
- `stop_game_server(server_id, confirm=False)` → **destructive**; terminate + clean up.

### Monitoring
- `get_server_logs(server_id, lines?)` → fetch logs (volume-capped via `lines`).
- `get_performance_metrics(server_id)` → CPU / memory / etc. for a running server.

### Builds & tags
- `upload_server_files(path, tag?, confirm=False)` → **destructive-ish**; upload a server image.
- `list_server_tags()` → server tags on the plan.
- `delete_server_tag(name, confirm=False)` → **destructive**; remove a tag.
- `get_upload_version()` → current upload version info.

### Players & matchmaking
- `add_player(match_id, ticket_id)` / `remove_player(match_id, ticket_id)`.
- `run_workflow(workflow_id, payload?)` → execute a named workflow.

Exact parameter names/shapes are pinned from the live OpenAPI spec
(`https://api.cloud.playflow.app/openapi.json`) during implementation rather than guessed here.

## Safety, errors, data flow

- **Confirmation gate** on destructive tools (`stop_game_server`, `delete_server_tag`,
  `upload_server_files`): each takes `confirm: bool = False` and refuses with a clear message
  unless `confirm=True`. Prevents an agent from tearing down a live Room on a loose instruction.
- **Error normalization**: the client maps non-2xx responses into a structured
  `{error, status, detail}` result, surfacing PlayFlow's own message so the agent gets
  actionable text rather than a raw stack trace. Missing `PLAYFLOW_API_TOKEN` fails fast at
  startup with a pointer to `.env.example`.
- **Data flow**: tool → `client` method → httpx call with `token` header → JSON → trimmed/typed
  result. Logs/metrics responses are lightly summarized (logs capped via `lines`) to avoid
  flooding agent context.

## Testing

- `client.py` unit-tested against mocked httpx: auth header present, error mapping, timeout
  handling.
- Tools tested against a fake client: parameter validation, confirmation gating, result shaping.
  No live API calls in the default suite.
- One optional, env-gated smoke test against the real API, skipped unless `PLAYFLOW_API_TOKEN`
  **and** `PLAYFLOW_LIVE_TESTS=1` are set.

## Out of scope

- C#/.NET or Node implementations (Python/FastMCP chosen).
- Auto-generation from OpenAPI.
- Lobby/SDK features beyond the documented REST endpoints.
- Publishing to a package index or the MCP registry (local dev tool for now).

## Open questions / to confirm during implementation

- Exact request/response field names for each endpoint (pin from live OpenAPI).
- Whether `get_server_logs` keys on `server_id` or `match_id` (docs reference "match").
- Whether `run_workflow` needs the optional authorization header in practice.
