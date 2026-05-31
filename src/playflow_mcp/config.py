"""Environment-based configuration for the PlayFlow MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_BASE_URL = "https://api.cloud.playflow.app"
DEFAULT_TIMEOUT = 30.0


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_token: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT


def load_config() -> Config:
    token = os.environ.get("PLAYFLOW_API_TOKEN")
    if not token:
        raise ConfigError(
            "PLAYFLOW_API_TOKEN is not set. Copy .env.example to .env and set your "
            "PlayFlow API token, or export PLAYFLOW_API_TOKEN in your environment."
        )
    base_url = os.environ.get("PLAYFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    timeout = float(os.environ.get("PLAYFLOW_TIMEOUT", DEFAULT_TIMEOUT))
    return Config(api_token=token, base_url=base_url, timeout=timeout)
