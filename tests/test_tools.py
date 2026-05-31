import httpx

import playflow_mcp.app as app
from playflow_mcp.client import PlayFlowAPIError
from playflow_mcp.tools import builds, lobbies, projects, servers


class FakeClient:
    def __init__(self):
        self.calls = []

    # servers
    def list_servers(self, include_launching=False, include_pool=False, limit=50, offset=0):
        self.calls.append(("list_servers", include_launching, include_pool, limit, offset))
        return {"total": 1, "servers": [{"instance_id": "srv-1"}]}

    def start_server(self, body):
        self.calls.append(("start_server", body))
        return {"instance_id": "srv-9", "status": "launching"}

    def stop_server(self, instance_id, shutdown_reason=None):
        self.calls.append(("stop_server", instance_id, shutdown_reason))
        return {"status": "Server stopped successfully"}

    def get_server(self, instance_id):
        raise PlayFlowAPIError(404, "no such server")

    def get_server_metrics(self, instance_id, period="1h", step="60s"):
        raise httpx.ConnectError("connection refused")

    # builds
    def delete_build(self, build_id):
        self.calls.append(("delete_build", build_id))
        return {"status": "deleted"}

    def upload_build(self, file_path, name="default", executable_path="Server.x86_64"):
        self.calls.append(("upload_build", file_path, name, executable_path))
        return {"build_id": "b-1"}

    def create_build_from_docker(self, body):
        self.calls.append(("create_build_from_docker", body))
        return {"build_id": "b-2"}

    # projects
    def get_project_settings(self):
        self.calls.append(("get_project_settings",))
        return {"port_configs": []}

    # lobbies
    def create_lobby(self, config, player_id, body):
        self.calls.append(("create_lobby", config, player_id, body))
        return {"id": "lob-1"}

    def delete_lobby(self, config, lobby_id):
        self.calls.append(("delete_lobby", config, lobby_id))
        return {"status": "lobby_deleted"}


def use_fake(monkeypatch):
    fake = FakeClient()
    monkeypatch.setattr(app, "_client", fake)
    return fake


# --- result shaping ------------------------------------------------------


def test_list_servers_wraps_success(monkeypatch):
    use_fake(monkeypatch)
    out = servers.list_servers()
    assert out["ok"] is True
    assert out["data"]["total"] == 1


def test_api_error_is_shaped(monkeypatch):
    use_fake(monkeypatch)
    out = servers.get_server("srv-1")
    assert out["ok"] is False
    assert out["error"] == "playflow_api_error"
    assert out["status"] == 404
    assert out["detail"] == "no such server"


def test_transport_error_is_shaped(monkeypatch):
    use_fake(monkeypatch)
    out = servers.get_server_metrics("srv-1")
    assert out["ok"] is False
    assert out["error"] == "request_failed"
    assert "connection refused" in out["detail"]


# --- body assembly -------------------------------------------------------


def test_start_server_assembles_body_and_omits_unset(monkeypatch):
    fake = use_fake(monkeypatch)
    servers.start_server(name="arena", region="us-east", ttl=600)
    (_, body) = fake.calls[-1]
    assert body["name"] == "arena"
    assert body["region"] == "us-east"
    assert body["ttl"] == 600
    assert body["compute_size"] == "small"  # default included
    assert "match_id" not in body  # unset optional omitted


def test_create_lobby_maps_camel_case_body(monkeypatch):
    fake = use_fake(monkeypatch)
    lobbies.create_lobby("casual", "host-1", name="room", max_players=4, is_private=True)
    (_, config, player_id, body) = fake.calls[-1]
    assert config == "casual"
    assert player_id == "host-1"
    assert body["maxPlayers"] == 4
    assert body["isPrivate"] is True


# --- confirmation gating -------------------------------------------------


def test_stop_server_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    out = servers.stop_server("srv-1")
    assert out["error"] == "confirmation_required"
    assert fake.calls == []


def test_stop_server_with_confirm_calls_client(monkeypatch):
    fake = use_fake(monkeypatch)
    out = servers.stop_server("srv-1", confirm=True)
    assert out["ok"] is True
    assert ("stop_server", "srv-1", None) in fake.calls


def test_delete_build_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    assert builds.delete_build("b-1")["error"] == "confirmation_required"
    assert fake.calls == []


def test_upload_build_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    assert builds.upload_build("/x.zip")["error"] == "confirmation_required"
    assert fake.calls == []


def test_create_build_from_docker_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    assert builds.create_build_from_docker("img:tag")["error"] == "confirmation_required"
    assert fake.calls == []


def test_delete_lobby_requires_confirmation(monkeypatch):
    fake = use_fake(monkeypatch)
    assert lobbies.delete_lobby("casual", "lob-1")["error"] == "confirmation_required"
    assert fake.calls == []


def test_create_build_from_docker_with_confirm_builds_credentials(monkeypatch):
    fake = use_fake(monkeypatch)
    out = builds.create_build_from_docker(
        "img:tag", name="prod", registry_username="u", registry_password="p", confirm=True
    )
    assert out["ok"] is True
    (_, body) = fake.calls[-1]
    assert body["image_url"] == "img:tag"
    assert body["registry_credentials"] == {"username": "u", "password": "p"}


def test_get_project_settings_passes_through(monkeypatch):
    fake = use_fake(monkeypatch)
    out = projects.get_project_settings()
    assert out["ok"] is True
    assert ("get_project_settings",) in fake.calls
