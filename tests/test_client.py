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
