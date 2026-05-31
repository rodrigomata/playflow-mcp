import pytest

from playflow_mcp.config import Config, ConfigError, load_config


def test_load_config_reads_api_key(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_KEY", "pf_abc")
    monkeypatch.delenv("PLAYFLOW_API_TOKEN", raising=False)
    monkeypatch.delenv("PLAYFLOW_BASE_URL", raising=False)
    monkeypatch.delenv("PLAYFLOW_TIMEOUT", raising=False)
    cfg = load_config()
    assert isinstance(cfg, Config)
    assert cfg.api_key == "pf_abc"
    assert cfg.base_url == "https://api.computeflow.cloud"
    assert cfg.timeout == 30.0


def test_load_config_falls_back_to_legacy_token_var(monkeypatch):
    monkeypatch.delenv("PLAYFLOW_API_KEY", raising=False)
    monkeypatch.setenv("PLAYFLOW_API_TOKEN", "pf_legacy")
    cfg = load_config()
    assert cfg.api_key == "pf_legacy"


def test_load_config_applies_overrides(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_KEY", "pf_abc")
    monkeypatch.setenv("PLAYFLOW_BASE_URL", "https://api.test/")
    monkeypatch.setenv("PLAYFLOW_TIMEOUT", "5")
    cfg = load_config()
    assert cfg.base_url == "https://api.test"  # trailing slash stripped
    assert cfg.timeout == 5.0


def test_load_config_missing_key_raises(monkeypatch):
    monkeypatch.delenv("PLAYFLOW_API_KEY", raising=False)
    monkeypatch.delenv("PLAYFLOW_API_TOKEN", raising=False)
    with pytest.raises(ConfigError) as exc:
        load_config()
    assert "PLAYFLOW_API_KEY" in str(exc.value)


def test_load_config_invalid_timeout_raises(monkeypatch):
    monkeypatch.setenv("PLAYFLOW_API_KEY", "pf_abc")
    monkeypatch.setenv("PLAYFLOW_TIMEOUT", "not-a-number")
    with pytest.raises(ConfigError) as exc:
        load_config()
    assert "PLAYFLOW_TIMEOUT" in str(exc.value)
