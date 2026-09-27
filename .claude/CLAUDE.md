# Fusion360 MCP Server

## What this is

An MCP server that bridges Claude Code to Autodesk Fusion 360 for CAD automation. Two components:

1. **This repo** — Python MCP server (stdio transport, 87 tools). Claude talks to this.
2. **Fusion360MCP add-in** — installed in Fusion's AddIns folder. Listens on `localhost:9876`.

The MCP server receives tool calls from Claude, forwards them as JSON over TCP to the add-in, and returns results.

## Architecture

```
Claude Code ←(stdio MCP)→ This Server ←(TCP :9876)→ Fusion360MCP Add-in ←(CustomEvent)→ Fusion Main Thread
```

## Development

```bash
uv sync --dev      # install deps
uv run pytest -v   # run tests (262 tests)
uv run ruff check  # lint
```

## Key files

- `src/fusion360_mcp/server.py` — MCP server entry point (click CLI), resources, prompts
- `src/fusion360_mcp/connection.py` — TCP client to Fusion add-in
- `src/fusion360_mcp/tools.py` — 87 tool definitions with annotations
- `src/fusion360_mcp/mock.py` — mock responses for `--mode mock` testing
- `tests/` — 262 tests covering tools, mock handlers, server routing, connection, annotations

## Adding a new command

1. Add the handler method in the **add-in's** `command_handler.py`
2. Add a tool definition dict in `src/fusion360_mcp/tools.py`
3. Add a mock handler in `src/fusion360_mcp/mock.py` + dispatch entry
4. Add tool name to the annotation sets if read-only/destructive/idempotent
5. Update `tests/test_tools.py` expected set and add mock test in `tests/test_mock.py`
6. The MCP server forwards tool calls 1:1 — no mapping code needed

## Conventions

- Tool names use snake_case and must match the add-in's command names exactly
- All Fusion API units are in **centimeters** (Fusion's internal unit)
- The add-in uses newline-delimited JSON over TCP
- `ping` is the health check — it never touches the Fusion API
- Every tool has annotations (`readOnlyHint`, `destructiveHint`, `idempotentHint`)
- Every tool has a mock handler so `--mode mock` works without Fusion running

## Working with agents

Intent flows project → mission → slice:

- `.claude/intent.md` — project purpose, non-goals, current mission. Maintained by the user.
- `.claude/slices/*.md` — one concrete change each (copy `TEMPLATE.md`): Goal, Done when, Out of scope, Proof. Only `status: active` slices are in play.
- `.claude/hooks/refocus.py` — injects intent plus active slices at session start, after compaction and every 8 prompts (`REFOCUS_EVERY`).

Team: the main session orchestrates (plans slices, delegates, merges results); the `builder` subagent implements one slice; the `qa` subagent verifies it read-only. Subagents cannot start subagents, so delegation always goes through the main session.

Working agreements:

- One active slice at a time. When its "Done when" is met: stop, fill in the Proof, report. No polishing.
- Ideas outside the slice or intent are proposals to the user, never implemented on the side.
- A check must verify the result. No checks of checks, no extra evidence nobody reads.
- Decisions need the context: the agent with the details and the one with the big picture decide together, or it goes to the user. An approval from an agent without that context is not an approval.
- A rule you add to any instruction file needs a reason. Run the `memory-audit` skill when a corrected mistake comes back.

## Jev guard (separate repo)

The Jev MCP server and `jev-guard` (PreToolUse hook that lets Jev check `delete_all`, `delete_parameter` and `undo` of this server, plus mail tools) moved to [jkoatx-tech/jev-mcp](https://github.com/jkoatx-tech/jev-mcp). The guard matches these tools under any server name, so renaming them here breaks the check: keep the names or update `POLICIES` there.
