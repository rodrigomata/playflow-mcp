import pytest

from playflow_mcp.config import Config, ConfigError, load_config


def test_load_config_reads_token(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_TOKEN", "tok-123")
    monkeypatch.delenv("PLAYFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("PLAYFLOW_TIMEOUT", raising=False)
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.api_token == "tok-123"
    assert cfg.base_url == "https://api.cloud.playflow.app"
    assert cfg.timeout == 30.0


def test_load_config_applies_overrides(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_TOKEN", "tok-123")
    monkeypatch.setenv("PLAYFLOW_BASE_URL", "https://api.test/")
    monkeypatch.setenv("PLAYFLOW_TIMEOUT", "5")
    cfg = load_config()
    assert cfg.base_url == "https://api.test"  # trailing slash stripped
    assert cfg.timeout == 5.0


def test_load_config_missing_token_raises(monkeypatch):
    monkeypatch.delenv("PLAYFLOW_API_TOKEN", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_config()
    assert "PLAYFLOW_API_TOKEN" in str(exc.value)
