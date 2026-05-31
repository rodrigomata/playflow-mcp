"""Lobby and matchmaking tools.

Player-scoped operations take ``player_id`` (sent as the ``x-player-id`` header)
and act as that player; host-only operations require player_id to be the lobby host.
``config`` is the lobby configuration name (e.g. "casual", "ranked_2v2").

Note: the SSE event stream (GET /lobbies/{config}/me/events) is a long-lived
``text/event-stream`` connection and is intentionally not exposed as a tool — a
single request/response call cannot consume it. Subscribe to it directly from a
client instead.
"""

from __future__ import annotations

from typing import Any

from ..app import call, get_client, mcp, needs_confirmation


@mcp.tool()
def browse_lobbies(
    config: str,
    region: str | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """List public lobbies for a config (no player identity needed).

    status filter: waiting|in_queue|in_game. limit 1-100 (default 50).
    """
    return call(get_client().browse_lobbies, config, region, status, limit, offset)


@mcp.tool()
def get_lobby(config: str, lobby_id: str) -> dict[str, Any]:
    """Get the full state of a lobby by id (admin/server-side; no player identity needed)."""
    return call(get_client().get_lobby, config, lobby_id)


@mcp.tool()
def delete_lobby(config: str, lobby_id: str, confirm: bool = False) -> dict[str, Any]:
    """Admin: delete a lobby by id, removing all players and cancelling matchmaking.

    DESTRUCTIVE: pass confirm=True to proceed.
    """
    if not confirm:
        return needs_confirmation("delete_lobby", lobby_id)
    return call(get_client().delete_lobby, config, lobby_id)


@mcp.tool()
def create_lobby(
    config: str,
    player_id: str,
    name: str,
    region: str = "us-east",
    max_players: int = 2,
    is_private: bool = False,
    allow_late_join: bool = True,
    settings: dict[str, Any] | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a lobby; player_id becomes the host.

    name (required, 1-100 chars). max_players 1-100 (default 2). settings: custom game
    settings. state: this host player's initial state.
    """
    body: dict[str, Any] = {
        "name": name,
        "region": region,
        "maxPlayers": max_players,
        "isPrivate": is_private,
        "allowLateJoin": allow_late_join,
    }
    if settings is not None:
        body["settings"] = settings
    if state is not None:
        body["state"] = state
    return call(get_client().create_lobby, config, player_id, body)


@mcp.tool()
def get_my_lobby(config: str, player_id: str) -> dict[str, Any]:
    """Get the lobby the given player is currently in (404 if none)."""
    return call(get_client().get_my_lobby, config, player_id)


@mcp.tool()
def join_lobby(
    config: str,
    player_id: str,
    lobby_id: str | None = None,
    code: str | None = None,
    state: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Join a lobby by lobby_id OR invite code (provide exactly one).

    state: this player's initial state.
    """
    body: dict[str, Any] = {}
    if lobby_id is not None:
        body["lobbyId"] = lobby_id
    if code is not None:
        body["code"] = code
    if state is not None:
        body["state"] = state
    return call(get_client().join_lobby, config, player_id, body)


@mcp.tool()
def leave_lobby(config: str, player_id: str) -> dict[str, Any]:
    """Leave the current lobby. Host duty transfers; the lobby is deleted if last to leave."""
    return call(get_client().leave_lobby, config, player_id)


@mcp.tool()
def kick_player(config: str, player_id: str, target_player_id: str) -> dict[str, Any]:
    """Host-only: kick target_player_id from the lobby. player_id must be the host."""
    return call(get_client().kick_player, config, player_id, target_player_id)


@mcp.tool()
def update_my_player_state(
    config: str, player_id: str, state: dict[str, Any]
) -> dict[str, Any]:
    """Merge fields into this player's state (e.g. {"ready": true}, {"team": "blue"})."""
    return call(get_client().update_my_player_state, config, player_id, state)


@mcp.tool()
def update_lobby_settings(
    config: str,
    player_id: str,
    name: str | None = None,
    max_players: int | None = None,
    is_private: bool | None = None,
    allow_late_join: bool | None = None,
    region: str | None = None,
    settings: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Host-only: update lobby settings. All fields optional; omitted ones are unchanged.

    settings is merged with existing settings.
    """
    body: dict[str, Any] = {}
    for key, value in {
        "name": name,
        "maxPlayers": max_players,
        "isPrivate": is_private,
        "allowLateJoin": allow_late_join,
        "region": region,
        "settings": settings,
    }.items():
        if value is not None:
            body[key] = value
    return call(get_client().update_lobby_settings, config, player_id, body)


@mcp.tool()
def send_heartbeat(config: str, player_id: str) -> dict[str, Any]:
    """Send a player heartbeat (for polling clients without SSE) to avoid eviction."""
    return call(get_client().send_heartbeat, config, player_id)


@mcp.tool()
def start_matchmaking(config: str, player_id: str, mode: str) -> dict[str, Any]:
    """Host-only: enter the matchmaking queue with the given mode (from the lobby config)."""
    return call(get_client().start_matchmaking, config, player_id, mode)


@mcp.tool()
def cancel_matchmaking(config: str, player_id: str) -> dict[str, Any]:
    """Host-only: leave the matchmaking queue; lobby returns to waiting."""
    return call(get_client().cancel_matchmaking, config, player_id)


@mcp.tool()
def confirm_match(config: str, player_id: str) -> dict[str, Any]:
    """Confirm a found match for this lobby. When all confirm, the game server launches."""
    return call(get_client().confirm_match, config, player_id)


@mcp.tool()
def decline_match(config: str, player_id: str) -> dict[str, Any]:
    """Decline a found match; cancels it for every participating lobby (all return to waiting)."""
    return call(get_client().decline_match, config, player_id)


@mcp.tool()
def start_game(config: str, player_id: str) -> dict[str, Any]:
    """Host-only: directly provision a server and start the game (status -> in_game)."""
    return call(get_client().start_game, config, player_id)


@mcp.tool()
def end_match(config: str, player_id: str) -> dict[str, Any]:
    """Host-only: end the current match; lobby returns to waiting with players preserved."""
    return call(get_client().end_match, config, player_id)
