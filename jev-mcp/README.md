# jev-mcp

MCP server that exposes **TypeSafe Jev** (a "System One" decision model) as
tools for Claude Code. Jev does not generate text: it returns typed answers
(yes/no, one of N labels, a score on a rubric) with calibrated probabilities,
typically in 70–500 ms.

Division of labour: **Claude plans and writes, Jev makes fast single
decisions** (gates, routing, triage, verification checks).

```
Claude Code ←(stdio MCP)→ jev-mcp ←(HTTPS, typesafe-sdk)→ api.typesafe.ai/v1/systemone
```

## Tools

| Tool | Jev primitive | Returns |
|---|---|---|
| `jev_check` | noul | `answer` yes/no, `p_yes`, `confidence` |
| `jev_classify` | choice | `choice`, `confidence`, `probabilities` per label |
| `jev_score` | score | `score` (expected value), `confidence`, `legend`, `probabilities` |
| `jev_ask` | mixed | several questions on one state in one call (input billed once) |
| `jev_list_models` | – | models available to the API key |

Every result is returned as MCP structured content (plus the same JSON as
text) and carries `needs_review: true` when confidence is below
`--min-confidence` (default 0.8). Treat such answers as "ask Claude or the
user" instead of acting on them. For `jev_check`, confidence is
`max(p_yes, 1 - p_yes)`.

All tools are annotated read-only, non-destructive, idempotent and open-world
(they call an external, billed API).

## Setup

Prerequisites: [uv](https://docs.astral.sh/uv/), a TypeSafe API key.

```bash
cd jev-mcp
uv sync --dev
uv run pytest -q              # 31 tests, no network or key needed
uv run jev-mcp --mode mock    # manual run without API key
```

### Register with Claude Code

User scope (available in every project); the key stays in your shell
environment, not in a file:

```bash
claude mcp add jev --scope user \
  -e TYPESAFE_API_KEY="$TYPESAFE_API_KEY" \
  -- uv run --directory /ABSOLUTE/PATH/TO/fusion-mcp/jev-mcp jev-mcp
```

Windows (PowerShell):

```powershell
claude mcp add jev --scope user `
  -e TYPESAFE_API_KEY=$env:TYPESAFE_API_KEY `
  -- uv run --directory C:\ABSOLUTE\PATH\TO\fusion-mcp\jev-mcp jev-mcp
```

Try without a key first by appending `--mode mock`. Check with `claude mcp
list` and `/mcp` inside Claude Code.

Project scope alternative: a `.mcp.json` in the project root. Claude Code
expands `${TYPESAFE_API_KEY}` from the environment, so no secret is committed:

```json
{
  "mcpServers": {
    "jev": {
      "command": "uv",
      "args": ["run", "--directory", "/ABSOLUTE/PATH/TO/fusion-mcp/jev-mcp", "jev-mcp"],
      "env": { "TYPESAFE_API_KEY": "${TYPESAFE_API_KEY}" }
    }
  }
}
```

### Configuration

| Option | Environment | Default |
|---|---|---|
| `--mode api\|mock` | – | `api` |
| `--model` | `TYPESAFE_DEFAULT_MODEL` | `jev-latest` (SDK) |
| `--min-confidence` | `JEV_MCP_MIN_CONFIDENCE` | `0.8` |
| `--timeout` | – | 10 s (SDK) |
| – | `TYPESAFE_API_KEY` | required in `api` mode |
| – | `TYPESAFE_BASE_URL` | `https://api.typesafe.ai` |

The server starts without a key; the first tool call then fails with a clear
message. Retries, rate limits (429) and typed errors come from the official
`typesafe-sdk`.

## Usage examples

Ask Claude in natural language; it picks the tool. Examples of what Claude
sends:

```jsonc
// jev_check: gate before a destructive step
{"state": {"diff": "..."}, "question": "Does this change remove a public API?"}

// jev_classify: route a Fusion error
{"state": "Extrude failed: profile not closed",
 "question": "Which fix applies?",
 "options": {"close_sketch": "Close the sketch profile",
             "change_plane": "Sketch on another plane",
             "other": null}}

// jev_score: rate risk
{"state": "...", "question": "How risky is this change?",
 "levels": ["trivial", "needs review", "dangerous"]}
```

Tips: Jev only sees `state`, so put everything the decision depends on into
it. Add a catch-all label (`other`) to classifications. Use `jev_ask` to ask
several questions about the same state in one billed call.

## Design notes

- Uses the official `typesafe-sdk` (MIT) instead of raw HTTP: wire format,
  retries and error types stay in sync with the API.
- `mcp` is pinned to `>=1.26,<2` to match the Fusion server's low-level API.
- `tests/test_server.py` checks the exact request/response wire format of
  `POST /v1/systemone` through the SDK with a mock HTTP transport.
- Self-contained package (own `pyproject.toml`, `uv.lock`); it can be moved to
  its own repository unchanged.
