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
