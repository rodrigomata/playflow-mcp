import pytest

from playflow_mcp.client import PlayFlowAPIError, PlayFlowClient, _clean
from playflow_mcp.config import Config


@pytest.fixture
def config():
    return Config(api_key="pf_test", base_url="https://api.test", timeout=5.0)


# --- helpers -------------------------------------------------------------


def test_clean_drops_none_and_renders_bools():
    assert _clean({"a": None, "b": True, "c": False, "d": 3}) == {
        "b": "true",
        "c": "false",
        "d": "3",
    }
    assert _clean(None) is None


# --- core request behavior ----------------------------------------------


def test_request_uses_api_key_header_and_v3_prefix(httpx_mock, config):
    httpx_mock.add_response(
        url="https://api.test/api/v3/servers?include_launching=false&include_pool=false&limit=50&offset=0",
        json={"total": 0, "servers": []},
    )
    client = PlayFlowClient(config)
    result = client.list_servers()
    assert result == {"total": 0, "servers": []}
    request = httpx_mock.get_request()
    assert request.headers["api-key"] == "pf_test"
    assert "x-player-id" not in request.headers


def test_error_extracts_detail_from_v3_shape(httpx_mock, config):
    httpx_mock.add_response(
        status_code=404, json={"error": "Not found", "detail": "no such server", "status": 404}
    )
    client = PlayFlowClient(config)
    with pytest.raises(PlayFlowAPIError) as exc:
        client.get_server("srv-1")
    assert exc.value.status == 404
    assert exc.value.detail == "no such server"


def test_path_includes_instance_id(httpx_mock, config):
    httpx_mock.add_response(json={"instance_id": "srv-1"})
    client = PlayFlowClient(config)
    client.get_server("srv-1")
    assert httpx_mock.get_request().url.path == "/api/v3/servers/srv-1"


def test_start_server_sends_json_body(httpx_mock, config):
    httpx_mock.add_response(status_code=201, json={"instance_id": "srv-9"})
    client = PlayFlowClient(config)
    client.start_server({"name": "arena-1", "region": "us-east"})
    request = httpx_mock.get_request()
    assert request.method == "POST"
    assert request.url.path == "/api/v3/servers/start"
    import json as _json

    assert _json.loads(request.content) == {"name": "arena-1", "region": "us-east"}


def test_stop_server_uses_delete_with_reason_query(httpx_mock, config):
    httpx_mock.add_response(json={"status": "Server stopped successfully"})
    client = PlayFlowClient(config)
    client.stop_server("srv-1", shutdown_reason="SHUTDOWN_SIGNAL")
    request = httpx_mock.get_request()
    assert request.method == "DELETE"
    assert request.url.params["shutdown_reason"] == "SHUTDOWN_SIGNAL"


# --- lobbies / x-player-id ----------------------------------------------


def test_player_scoped_call_sends_x_player_id(httpx_mock, config):
    httpx_mock.add_response(json={"id": "lob-1"})
    client = PlayFlowClient(config)
    client.get_my_lobby("casual", "player-42")
    request = httpx_mock.get_request()
    assert request.headers["x-player-id"] == "player-42"
    assert request.url.path == "/api/v3/lobbies/casual/me"


def test_start_matchmaking_posts_mode(httpx_mock, config):
    httpx_mock.add_response(json={"status": "in_queue"})
    client = PlayFlowClient(config)
    client.start_matchmaking("ranked", "host-1", "ranked_2v2")
    request = httpx_mock.get_request()
    assert request.headers["x-player-id"] == "host-1"
    import json as _json

    assert _json.loads(request.content) == {"mode": "ranked_2v2"}


def test_kick_player_targets_player_path(httpx_mock, config):
    httpx_mock.add_response(json={"id": "lob-1"})
    client = PlayFlowClient(config)
    client.kick_player("casual", "host-1", "troublemaker")
    request = httpx_mock.get_request()
    assert request.method == "DELETE"
    assert request.url.path == "/api/v3/lobbies/casual/me/players/troublemaker"
    assert request.headers["x-player-id"] == "host-1"


# --- build upload two-step flow -----------------------------------------


def test_upload_build_gets_presigned_url_then_puts_file(httpx_mock, tmp_path, config):
    httpx_mock.add_response(
        url="https://api.test/api/v3/builds/upload-url?name=beta&executable_path=Server.x86_64",
        status_code=201,
        json={"build_id": "b-1", "name": "beta", "upload_url": "https://storage.test/put/b-1"},
    )
    httpx_mock.add_response(url="https://storage.test/put/b-1", status_code=200)
    image = tmp_path / "server.zip"
    image.write_bytes(b"ZIPDATA")
    client = PlayFlowClient(config)

    result = client.upload_build(str(image), name="beta")

    assert result["build_id"] == "b-1"
    put_request = httpx_mock.get_requests()[1]
    assert put_request.method == "PUT"
    assert put_request.url == "https://storage.test/put/b-1"
    assert b"ZIPDATA" in put_request.content
    # The presigned storage URL must NOT receive our api-key.
    assert "api-key" not in put_request.headers
