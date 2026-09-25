"""Jev MCP Server — TypeSafe Jev decisions as MCP tools."""


def main() -> None:
    # Imported lazily: jev-guard runs on every tool call in some clients and
    # must not pay for loading the MCP server.
    from .server import main as server_main

    server_main()


__all__ = ["main"]
