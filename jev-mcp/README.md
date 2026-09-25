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
uv run pytest -q              # 63 tests, no network or key needed
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

## Guard: Jev check before destructive Fusion tools and sending mail

`jev-guard` is a Claude Code **PreToolUse hook** for the Fusion server's
destructive tools. Before the tool runs, Jev answers one yes/no question:

| Tool | Question Jev answers |
|---|---|
| `delete_all` | Did the user explicitly ask to delete, clear or reset the entire design? |
| `delete_parameter` | Did the user explicitly ask to delete the parameter named in `tool_input.name`? |
| `undo` | Did the user ask to undo, revert or roll back the last operation? |

The parameter name reaches Jev only as data in the state and is never
inserted into the question, so the caller cannot rewrite the question.

The state Jev judges is made of the **user's own last messages** from the
session transcript. Assistant text, tool results, system reminders and task
notifications are filtered out, so Claude cannot argue its way past the
check.

The guard only restricts and never grants permission:

| Jev `p(yes)` | Decision | Effect |
|---|---|---|
| ≥ 0.9 (`--allow-above`) | none | normal permission flow (your settings apply) |
| between the thresholds | `ask` | you confirm in Claude Code |
| < 0.2 (`--deny-below`) | `deny` | call blocked; the reason goes to Claude (`undo`: `ask` instead) |
| error / no key / no user messages | `ask` | fail safe: you decide |

`undo` is never blocked outright. It is Claude's normal way to fix its own
last step, so when Jev is confident the user did not ask for it, the guard
still only asks you to confirm (`on_no: "ask"` in the policy).

Register it in `~/.claude/settings.json`. The matcher catches these tools
under any server name (e.g. `mcp__fusion360__delete_parameter`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "mcp__.*(delete_all|delete_parameter|undo|send_message|send_e?mail|send-mail|reply|reply_all|reply-mail|reply_to_message|forward|forward_message|forward-mail)$",
        "hooks": [
          {
            "type": "command",
            "command": "uv run --directory /ABSOLUTE/PATH/TO/fusion-mcp/jev-mcp jev-guard",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

`TYPESAFE_API_KEY` must be set in the environment Claude Code runs in (hooks
inherit it). Test without a key with `jev-guard --mode mock`. Each request
times out after 5 s (`--timeout`) with one retry. The hook timeout of 30 s
leaves headroom for that.

Notes:

- The transcript format is not an official Claude Code API. If it changes
  and no user messages are found, the guard falls back to `ask`, never to
  allow.
- `ask` behaves like a normal permission prompt. In unattended runs
  (`claude -p`), what happens to it depends on your permission mode, so test
  that setup before you rely on it.
- More destructive tools can be added in `POLICIES` in
  `src/jev_mcp/guard.py`.

## Guard: Jev check before sending mail

The same hook guards mail tools (send, reply, forward) of any mail MCP server
(Gmail, Microsoft 365, SMTP). Jev answers: *Did the user explicitly ask to
send this email now, to the recipients in `tool_input`?* Recipients, subject
and body reach Jev only as data in the state.

| Jev `p(yes)` | Decision |
|---|---|
| ≥ 0.9 | normal permission flow |
| between | `ask` |
| < 0.2 | `deny`: "show the user the draft and ask before sending" |
| error / no key / no user messages | `ask` |

Guarded names (the part after the last `__`, or the end of the tool name):
`send_message`, `send_email`, `send_mail`, `send-mail`, `reply`, `reply_all`,
`reply-mail`, `reply_to_message`, `forward`, `forward_message`,
`forward-mail`. Drafts are not guarded. `send_message` also names chat and
agent-to-agent tools, so it counts as mail only when `tool_input` carries a
recipient (`to`, `recipients`, `toRecipients`, `cc`, `bcc`). Add names in
`MAIL_TOOLS` in `src/jev_mcp/guard.py`.

For Claude Code, the matcher in the `settings.json` snippet above already
covers the mail tools.

## GitHub Copilot (VS Code agent mode and Copilot CLI)

Copilot's PreToolUse input has no transcript the guard can read (the CLI sends
none, VS Code writes its own format with a delay). Its prompt hook does carry
the user's text, so `jev-guard` also handles that event: it records the last
5 prompts per session in `~/.jev-guard/sessions/` (override with
`JEV_GUARD_STATE_DIR`) and reads them back at PreToolUse. Output follows the
client: flat `permissionDecision` for the CLI, `hookSpecificOutput` for
VS Code.

1. Set up the package (`uv sync`) and `TYPESAFE_API_KEY` as above.
2. Copy `copilot-hooks.example.json` to `~/.copilot/hooks/jev-guard.json`
   (Windows: `%USERPROFILE%\.copilot\hooks\`) and fix the path. Both the
   CLI and VS Code read that folder.
3. VS Code: `chat.useHooks` is on by default. Hooks there are in preview.

Notes:

- Copilot runs the hook before **every** tool call (VS Code ignores
  matchers). The guard answers unguarded tools in about 0.3 s without loading
  the backend. The example calls `.venv/Scripts/jev-guard.exe` directly
  because `uv run` adds startup time.
- In the Copilot CLI a hook **timeout lets the tool run**. Keep `timeoutSec`
  (30) well above the guard's worst case (5 s request, one retry).
- Under the Copilot cloud agent, `ask` becomes `deny` (no user to ask).
- The prompt store is a plain file. An agent with file-write access could
  forge it; the transcript path in Claude Code does not have that gap.
- Everything Jev judges (your prompts, recipients, mail body) goes to
  `api.typesafe.ai`. Check that this is allowed where you use it.

To use Jev's decision tools in Copilot as well, register the MCP server in
VS Code (`MCP: Open User Configuration`):

```json
{
  "servers": {
    "jev": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "C:/ABSOLUTE/PATH/TO/fusion-mcp/jev-mcp", "jev-mcp"],
      "env": { "TYPESAFE_API_KEY": "${env:TYPESAFE_API_KEY}" }
    }
  }
}
```

## Design notes

- Uses the official `typesafe-sdk` (MIT) instead of raw HTTP: wire format,
  retries and error types stay in sync with the API.
- `mcp` is pinned to `>=1.26,<2` to match the Fusion server's low-level API.
- `tests/test_server.py` checks the exact request/response wire format of
  `POST /v1/systemone` through the SDK with a mock HTTP transport.
- Self-contained package (own `pyproject.toml`, `uv.lock`); it can be moved to
  its own repository unchanged.
