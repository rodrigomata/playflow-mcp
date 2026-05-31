import os

import pytest

from playflow_mcp.client import PlayFlowClient
from playflow_mcp.config import load_config

pytestmark = pytest.mark.skipif(
    not (os.environ.get("PLAYFLOW_API_TOKEN") and os.environ.get("PLAYFLOW_LIVE_TESTS") == "1"),
    reason="set PLAYFLOW_API_TOKEN and PLAYFLOW_LIVE_TESTS=1 to run live smoke tests",
)


def test_list_servers_live():
    client = PlayFlowClient(load_config())
    try:
        result = client.list_servers()
    finally:
        client.close()
    assert "servers" in result
