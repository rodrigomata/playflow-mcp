# PlayFlow MCP Server — Design

**Date:** 2026-05-31
**Status:** Implemented — targets the **PlayFlow v3 API**
**Repo:** GitHub `rodrigomata/playflow-mcp` (standalone; developed locally under
`~/Documents/Development/playflow-mcp`)

> **History:** the first iteration targeted a legacy API generation
> (`api.cloud.playflow.app`, `token` header, RPC-style endpoints). It was reconciled and
> retargeted to the current **v3** API after verifying the auth header, base URL, and REST
> endpoint shapes against the live v3 docs. This document describes the v3 implementation as
> built. The original step-by-step build is preserved in the companion implementation plan as a
> historical record.

## Purpose

A local [Model Context Protocol](https://modelcontextprotocol.io) server that wraps the
[PlayFlow Cloud](https://playflowcloud.com) v3 REST API, so an agent (Claude Code) can deploy,
inspect, and tear down game servers — and manage builds, logs/metrics, project settings, and
lobbies/matchmaking — directly from a development session. Built for the Spellpaws project's
PlayFlow hosting, but kept project-agnostic so it is reusable.

No official or community PlayFlow MCP exists (verified against the MCP registry and GitHub on
2026-05-31), so this is built from scratch over PlayFlow's documented REST API.

## Approach

**Curated hand-written tools** (chosen over OpenAPI auto-generation). One FastMCP tool per
meaningful PlayFlow operation, with hand-tuned names, descriptions, typed parameters, and
guardrails on destructive calls. This yields far better agent ergonomics than a raw passthrough
of the underlying REST shapes.

## API facts (v3)

- **Base URL:** `https://api.computeflow.cloud`, paths under `/api/v3`; overridable via
  `PLAYFLOW_BASE_URL`.
- **Auth header:** `api-key` with a server key (`pf_...`), read from `PLAYFLOW_API_KEY`
  (legacy `PLAYFLOW_API_TOKEN` accepted as a fallback). Never a tool parameter.
- **Params:** proper path / query / JSON body. Server identity is the `instance_id` path param;
  builds use `build_id`; lobbies use a `{config}` path segment and an `x-player-id` header for
  player-scoped ops.
- **Errors:** PlayFlow returns `{error, detail, status}`; non-2xx raises `PlayFlowAPIError`,
  normalized at the tool layer to `{ok: False, error, status, detail}`.

## Architecture & layout

```
playflow-mcp/
  pyproject.toml          # uv-managed; console entry point `playflow-mcp`
  src/playflow_mcp/
    __init__.py
    config.py             # env: PLAYFLOW_API_KEY, base URL, timeouts
    client.py             # the only HTTP module; api-key auth + all v3 methods
    app.py                # shared FastMCP app + get_client / call / needs_confirmation
    server.py             # entry point: imports tool modules, exposes main()
    tools/
      servers.py          # server lifecycle/monitoring/metadata tools
      builds.py           # build image tools (zip upload + docker)
      projects.py         # project settings & aggregated logs
      lobbies.py          # lobby & matchmaking tools
  tests/
    test_config.py        # env loading
    test_client.py        # httpx mocked
    test_tools.py         # tools against a fake client
    test_live_smoke.py    # env-gated live smoke test
  README.md
  .env.example
```

- **`client.py`** is the only module that talks HTTP. It owns auth (the `api-key` header), the
  base URL + `/api/v3` prefix, timeouts, and error extraction.
- **`app.py`** holds the shared `mcp` app, the lazy `get_client()`, the `call()` result wrapper,
  and the `needs_confirmation()` helper.
- **`tools/*.py`** register FastMCP tools on the shared app, grouped by resource. Tools were
  split by resource because 33 tools in one file is unwieldy.
- **`server.py`** imports the tool modules (registering them) and exposes `main()`.
- Runs over **stdio**, launched via `uv run playflow-mcp`, registered in Claude Code's MCP config.

## Tool surface (33 tools)

**Servers (8):** `list_servers`, `get_server`, `start_server`, `stop_server`*,
`restart_server`, `get_server_metrics`, `get_server_logs`, `update_server_custom_data`.

**Builds (6):** `list_builds`, `get_build`, `get_build_logs`, `upload_build`* (presigned-URL
flow: request URL → PUT zip), `create_build_from_docker`*, `delete_build`*.

**Projects (2):** `get_project_settings`, `get_project_logs`.

**Lobbies & matchmaking (17):** `browse_lobbies`, `get_lobby`, `delete_lobby`*, `create_lobby`,
`get_my_lobby`, `join_lobby`, `leave_lobby`, `kick_player`, `update_my_player_state`,
`update_lobby_settings`, `send_heartbeat`, `start_matchmaking`, `cancel_matchmaking`,
`confirm_match`, `decline_match`, `start_game`, `end_match`.

(* = destructive; gated behind `confirm=True`.) The lobby SSE stream
(`GET /lobbies/{config}/me/events`, `text/event-stream`) is intentionally **not** wrapped — a
long-lived stream can't be a request/response tool.

## Safety, errors, data flow

- **Confirmation gate** on destructive tools (`stop_server`, `delete_build`, `upload_build`,
  `create_build_from_docker`, `delete_lobby`): each takes `confirm: bool = False` and refuses
  with a clear message unless `confirm=True`.
- **Error normalization**: `PlayFlowAPIError` (non-2xx), `httpx.HTTPError` (transport), and
  `OSError` (e.g. a missing upload file) are caught at the tool layer and returned as
  `{ok: False, error, ...}` rather than an uncaught traceback. Missing `PLAYFLOW_API_KEY` fails
  fast at startup with a pointer to `.env.example`.
- **Data flow**: tool → `client` method → httpx call with `api-key` header → JSON → result
  wrapped as `{ok: True, data}`.

## Testing

- `config.py` unit-tested: env loading, fallback var, invalid timeout.
- `client.py` unit-tested against mocked httpx: `api-key` header, `/api/v3` prefix, param
  cleaning, `x-player-id`, JSON bodies, error extraction, and the two-step upload flow.
- Tools tested against a fake client: result shaping, error normalization, body assembly,
  confirmation gating. No live API calls in the default suite.
- One optional, env-gated smoke test against the real API, skipped unless `PLAYFLOW_API_KEY`
  **and** `PLAYFLOW_LIVE_TESTS=1` are set.

## Out of scope

- C#/.NET or Node implementations (Python/FastMCP chosen).
- Auto-generation from OpenAPI.
- The lobby SSE event stream (not a request/response fit).
- Publishing to a package index or the MCP registry (local dev tool for now).

## Known risks / to confirm with a live key

- Whether the presigned-URL `PUT` requires a specific `Content-Type` (the build upload path is
  unverified without a real `pf_` key).
