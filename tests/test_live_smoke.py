import os

import pytest

from playflow_mcp.client import PlayFlowClient
from playflow_mcp.config import load_config

_has_key = bool(os.environ.get("PLAYFLOW_API_KEY") or os.environ.get("PLAYFLOW_API_TOKEN"))

pytestmark = pytest.mark.skipif(
    not (_has_key and os.environ.get("PLAYFLOW_LIVE_TESTS") == "1"),
    reason="set PLAYFLOW_API_KEY (or legacy PLAYFLOW_API_TOKEN) and PLAYFLOW_LIVE_TESTS=1 to run live smoke tests",
)


def test_list_servers_live():
    client = PlayFlowClient(load_config())
    try:
        result = client.list_servers()
    finally:
        client.close()
    assert "servers" in result
