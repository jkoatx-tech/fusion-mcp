"""End-to-end tests for --read-only over a real stdio MCP session (mock mode)."""

import os
import sys

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from fusion360_mcp.tools import TOOLS, is_read_only

_READ_ONLY_NAMES = {t["name"] for t in TOOLS
                    if t["annotations"]["readOnlyHint"]}


def _run(check, *args, env=None):
    """Start the server in mock mode with extra CLI args, run check(session)."""
    params = StdioServerParameters(
        command=sys.executable,
        args=["-c", "from fusion360_mcp.server import main; main()",
              "--mode", "mock", *args],
        env={**os.environ, **(env or {})},
    )

    async def go():
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await check(session)

    return anyio.run(go)


async def _tool_names(session):
    return {t.name for t in (await session.list_tools()).tools}


class TestIsReadOnly:
    def test_matches_annotation(self):
        for t in TOOLS:
            assert is_read_only(t["name"]) is t["annotations"]["readOnlyHint"]

    def test_unknown_tool_is_not_read_only(self):
        assert is_read_only("no_such_tool") is False


class TestReadOnlyFlag:
    def _parsed(self, monkeypatch, value):
        from fusion360_mcp.server import main
        monkeypatch.setenv("FUSION_MCP_READ_ONLY", value)
        return main.make_context("x", ["--mode", "mock"]).params["read_only"]

    def test_env_false_values_stay_writable(self, monkeypatch):
        for v in ("0", "false"):
            assert self._parsed(monkeypatch, v) is False

    def test_env_true_values_enable(self, monkeypatch):
        for v in ("1", "true"):
            assert self._parsed(monkeypatch, v) is True


class TestReadOnlyServer:
    def test_default_lists_all_tools(self):
        assert _run(_tool_names) == {t["name"] for t in TOOLS}

    def test_flag_lists_only_read_only_tools(self):
        assert _run(_tool_names, "--read-only") == _READ_ONLY_NAMES

    def test_env_var_enables_read_only(self):
        names = _run(_tool_names, env={"FUSION_MCP_READ_ONLY": "1"})
        assert names == _READ_ONLY_NAMES

    def test_write_tool_is_refused(self):
        async def check(session):
            return await session.call_tool("delete_all", {})

        result = _run(check, "--read-only")
        assert result.isError is True
        assert "read-only" in result.content[0].text
        # Mock handlers report "mode": "mock" — the call must not reach them.
        assert "mock" not in result.content[0].text

    def test_undo_is_refused(self):
        async def check(session):
            return await session.call_tool("undo", {})

        assert _run(check, "--read-only").isError is True

    def test_read_tool_still_works(self):
        async def check(session):
            return await session.call_tool("ping", {})

        result = _run(check, "--read-only")
        assert result.isError is False
        assert "OK" in result.content[0].text

    def test_prompts_hidden(self):
        async def check(session):
            return (await session.list_prompts()).prompts

        assert _run(check, "--read-only") == []
        assert len(_run(check)) > 0
