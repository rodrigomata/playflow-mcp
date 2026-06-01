"""Entry point for the PlayFlow MCP server.

Importing the tool modules registers their tools on the shared ``mcp`` app.
"""

from __future__ import annotations

from .app import mcp
from .tools import builds, lobbies, projects, servers  # noqa: F401  (registers tools)


def main() -> None:
    """Console entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
