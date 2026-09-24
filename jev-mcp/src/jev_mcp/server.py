"""
Jev MCP Server — stdio transport.

Exposes TypeSafe Jev (System One decision model) as typed, calibrated
decision tools for Claude Code.  Supports ``--mode mock`` for testing without
an API key.
"""

import logging
import os

import anyio
import click
import mcp.types as types
from mcp.server.lowlevel import Server

from .backend import Backend, JevError, MockBackend, TypeSafeBackend
from .tools import build_questions, get_tool_by_name, get_tool_list, shape_response

# Logs go to stderr; stdout carries the MCP protocol.
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("jev_mcp.server")


async def run_tool(
    backend: Backend, name: str, arguments: dict, *, min_confidence: float,
) -> dict:
    """Execute one tool call against the backend and shape the result."""
    if not get_tool_by_name(name):
        raise ValueError(f"Unknown tool: {name}")

    if name == "jev_list_models":
        return await backend.list_models()

    questions = build_questions(name, arguments)
    raw = await backend.system_one(
        arguments["state"], questions, arguments.get("model"),
    )
    if not raw.get("answers"):
        raise JevError("Jev returned no answers for this request.")
    return shape_response(name, raw, min_confidence)


def create_server(backend: Backend, *, min_confidence: float) -> Server:
    app = Server("jev-mcp")

    @app.list_tools()
    async def list_tools() -> list[types.Tool]:
        return get_tool_list()

    @app.call_tool()
    async def call_tool(name: str, arguments: dict) -> dict:
        # A returned dict becomes structuredContent plus its JSON as text;
        # a raised exception becomes an isError result with its message.
        return await run_tool(
            backend, name, arguments, min_confidence=min_confidence,
        )

    return app


@click.command()
@click.option("--mode", type=click.Choice(["api", "mock"]), default="api",
              help="'api' calls TypeSafe, 'mock' returns deterministic test data")
@click.option("--model", type=str, default=None,
              help="Default model (env: TYPESAFE_DEFAULT_MODEL, SDK default "
                   "jev-latest)")
@click.option("--min-confidence", type=click.FloatRange(0.5, 1.0),
              default=lambda: float(
                  os.environ.get("JEV_MCP_MIN_CONFIDENCE", "0.8")),
              help="Answers below this confidence get needs_review=true "
                   "(env: JEV_MCP_MIN_CONFIDENCE)")
@click.option("--timeout", type=float, default=None,
              help="Per-request timeout in seconds (SDK default 10)")
def main(mode: str, model: str | None, min_confidence: float,
         timeout: float | None) -> int:
    """Jev MCP Server — typed, calibrated decisions for Claude Code."""
    if mode == "mock":
        backend: Backend = MockBackend()
    else:
        options = {"model": model, "timeout": timeout}
        backend = TypeSafeBackend(
            **{k: v for k, v in options.items() if v is not None})

    app = create_server(backend, min_confidence=min_confidence)

    from mcp.server.stdio import stdio_server

    async def arun():
        try:
            async with stdio_server() as streams:
                await app.run(streams[0], streams[1],
                              app.create_initialization_options())
        finally:
            await backend.aclose()

    log.info("Starting jev-mcp (mode=%s, min_confidence=%s)",
             mode, min_confidence)
    anyio.run(arun)
    return 0
