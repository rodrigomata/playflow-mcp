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
