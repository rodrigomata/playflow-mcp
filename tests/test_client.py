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
