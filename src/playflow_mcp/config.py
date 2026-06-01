"""Environment-based configuration for the PlayFlow MCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

# Canonical PlayFlow Cloud v3 API host (backed by "computeflow"). Paths are
# rooted at /api/v3 by the client.
DEFAULT_BASE_URL = "https://api.computeflow.cloud"
DEFAULT_TIMEOUT = 30.0


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


@dataclass(frozen=True)
class Config:
    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT


def load_config() -> Config:
    # Prefer PLAYFLOW_API_KEY (matches PlayFlow's "api-key" header); accept the
    # older PLAYFLOW_API_TOKEN as a fallback for existing setups.
    api_key = os.environ.get("PLAYFLOW_API_KEY") or os.environ.get("PLAYFLOW_API_TOKEN")
    if not api_key:
        raise ConfigError(
            "PLAYFLOW_API_KEY is not set. Copy .env.example to .env and set your "
            "PlayFlow server API key (starts with 'pf_'), or export PLAYFLOW_API_KEY "
            "in your environment."
        )
    base_url = os.environ.get("PLAYFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    raw_timeout = os.environ.get("PLAYFLOW_TIMEOUT")
    if raw_timeout is None:
        timeout = DEFAULT_TIMEOUT
    else:
        try:
            timeout = float(raw_timeout)
        except ValueError as exc:
            raise ConfigError(
                f"PLAYFLOW_TIMEOUT must be a number, got {raw_timeout!r}."
            ) from exc
    return Config(api_key=api_key, base_url=base_url, timeout=timeout)
