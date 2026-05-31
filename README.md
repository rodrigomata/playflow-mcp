# playflow-mcp

A local [MCP](https://modelcontextprotocol.io) server that wraps the
[PlayFlow Cloud](https://playflowcloud.com) **v3 REST API**
(`https://api.computeflow.cloud/api/v3`), giving an agent tools to deploy, inspect, and tear
down game servers, manage build images, read logs/metrics, inspect project settings, and
drive lobbies/matchmaking.

## Setup

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env   # then set PLAYFLOW_API_KEY (your "pf_..." server key)
```

Get/regenerate the key in the PlayFlow Dashboard under **Project Settings**. Use the
**server** key (`pf_...`) — never ship it in client code; that's what the client key
(`pfclient_...`) is for.

## Run

```bash
PLAYFLOW_API_KEY=pf_... uv run playflow-mcp
```

## Register with Claude Code

```bash
claude mcp add playflow \
  --env PLAYFLOW_API_KEY=pf_your_key_here \
  -- uv run --directory /Users/rodrigomata/Documents/Development/playflow-mcp playflow-mcp
```

## Tools (33)

**Servers (8):** `list_servers`, `get_server`, `start_server`, `stop_server`,
`restart_server`, `get_server_metrics`, `get_server_logs`, `update_server_custom_data`.

**Builds (6):** `list_builds`, `get_build`, `get_build_logs`, `upload_build` (zip via
presigned URL), `create_build_from_docker`, `delete_build`.

**Projects (2):** `get_project_settings`, `get_project_logs`.

**Lobbies & matchmaking (17):** `browse_lobbies`, `get_lobby`, `delete_lobby`,
`create_lobby`, `get_my_lobby`, `join_lobby`, `leave_lobby`, `kick_player`,
`update_my_player_state`, `update_lobby_settings`, `send_heartbeat`, `start_matchmaking`,
`cancel_matchmaking`, `confirm_match`, `decline_match`, `start_game`, `end_match`.

Player-scoped lobby tools take a `player_id` (sent as the `x-player-id` header). Destructive
tools (`stop_server`, `delete_build`, `upload_build`, `create_build_from_docker`,
`delete_lobby`) require `confirm=True`.

> The lobby SSE event stream (`GET /lobbies/{config}/me/events`, `text/event-stream`) is a
> long-lived connection and is not exposed as a tool — subscribe to it from a client instead.

## Tests

```bash
uv run pytest
```
