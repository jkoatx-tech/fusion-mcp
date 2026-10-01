# Running this MCP server inside a Paperclip organization

Paperclip is a "meta harness": it runs agents from different harnesses (Claude Code, Codex, Hermes, Pi, …) as employees of one organization, with an org chart, tasks, routines, per-agent secrets, and human approvals ("decisions") for the board. This guide covers giving such an organization CAD hands through this server — and the two things Paperclip does **not** solve for you: concurrent access to one Fusion session and tool-level guarding of destructive calls.

> **Scope note:** everything about this repo (socket behavior, annotations, env vars) is checked against the code. Everything about Paperclip itself comes from its public demo material, not from running it against this server. Treat the Paperclip-side config as a sketch and verify it against Paperclip's own docs before relying on it — see [Open questions](#open-questions).

## Architecture

```
                         Paperclip host (Linux VM)
 ┌────────────────────────────────────────────────────────────────┐
 │  Board (you) ── decisions / approvals                          │
 │     │                                                          │
 │  CEO agent (Claude Code)                                       │
 │     ├── CAD engineer  (Claude Code + fusion360, read/write)    │
 │     │      └─ PreToolUse hook: jev-guard                       │
 │     └── CAD reviewer  (any harness, read-only tools only)      │
 │                                                                │
 │  fusion360-mcp-server (stdio, one process per agent)           │
 └────────────────┬───────────────────────────────────────────────┘
                  │ TCP :9876, newline-delimited JSON, no auth
                  ▼
    Windows workstation: Fusion 360 + Fusion360MCP add-in
```

Paperclip runs each agent's harness **on the Paperclip host**, so this server runs there too, as a stdio MCP server in each agent's harness config. Fusion stays on the workstation; the leg between them is the [cross-machine setup](../README.md#cross-machine-setup-lan).

## Design rules

### 1. Exactly one agent writes

The add-in accepts multiple clients, each on its own thread (`addon/server/socket_server.py`), but every command is marshalled onto Fusion's main thread and acts on **the same active document**. Two agents modelling at once interleave their edits in one design — nothing errors, the geometry is just wrong.

Paperclip coordinates *work*, not *resources*; it will happily run two agents against the same socket in parallel. So:

- One agent — the CAD engineer — gets write access.
- Every other agent that touches Fusion gets only the read-only tools (the `_READ_ONLY` set in `src/fusion360_mcp/tools.py`: `ping`, `get_scene_info`, `get_object_info`, `get_bounding_box`, `list_components`, `get_parameters`, `get_physical_properties`, `measure_distance`, `measure_angle`, `check_interference`, `get_design_type`, `cam_list_setups`, `cam_list_operations`, `cam_get_operation_info`).
- Treat the Paperclip task assigned to the CAD engineer as the lock. Reviewers work on the result after that task is done, not alongside it.

Read-only calls from a reviewer while the engineer is mid-task are harmless to the design but may see a half-built state.

### 2. Guard destructive calls at two levels

| Level | Mechanism | Covers | Limit |
|---|---|---|---|
| Single tool call | [jev-guard](https://github.com/jkoatx-tech/jev-mcp) (PreToolUse hook) | `delete_all`, `delete_parameter`, `undo` | Runs **only in Claude Code**. Codex, Hermes and Pi don't execute Claude Code hooks. |
| Task | Paperclip decision | Intent, e.g. "rebuild the design from scratch" | Asynchronous and human; does not block an individual tool call |

Neither replaces the other. Consequence for staffing: the writing agent runs on **Claude Code** with jev-guard installed. Agents on other harnesses — including a local Hermes setup from [local-llm.md](local-llm.md) — only get the read-only tools.

Note that `undo` is not in the `_DESTRUCTIVE` annotation set, so a harness that only looks at `destructiveHint` will not flag it. jev-guard covers it by name.

### 3. Restrict the socket to the Paperclip host

The add-in socket has no authentication (`addon/Fusion360MCP.py`). Binding it to `0.0.0.0` for the cross-machine leg means anyone on the LAN can send `delete_all`. Open port 9876 only to the Paperclip host:

```powershell
# On the Fusion workstation, elevated PowerShell
New-NetFirewallRule -DisplayName "Fusion360MCP from Paperclip" `
  -Direction Inbound -Protocol TCP -LocalPort 9876 `
  -RemoteAddress 192.168.1.50 -Action Allow
```

Check that no broader rule (e.g. an app-wide allow for Fusion created on first launch) opens the port anyway.

## Setup

### 1. Fusion workstation

Follow [Cross-machine setup](../README.md#cross-machine-setup-lan): set `FUSION_MCP_HOST=0.0.0.0` before starting Fusion, start the add-in, confirm `Server listening on 0.0.0.0:9876`. Then add the firewall rule above.

### 2. CAD engineer (Claude Code, read/write)

MCP config for the agent's Claude Code instance on the Paperclip host (`.mcp.json` in its working directory, or however Paperclip injects MCP config per agent):

```json
{
  "mcpServers": {
    "fusion360": {
      "command": "uvx",
      "args": ["fusion360-mcp-server", "--mode", "socket"],
      "env": { "FUSION_MCP_HOST": "192.168.1.42" }
    }
  }
}
```

Install jev-guard as a PreToolUse hook for this agent (see the jev-mcp repo). Check [open question 1](#open-questions) first — the agent runs unattended.

### 3. CAD reviewer (read-only)

Start the reviewer's server with `--read-only` (or `FUSION_MCP_READ_ONLY=1`). The server then lists only the `readOnlyHint` tools, hides the modelling prompts, and refuses every other tool call before it reaches Fusion. This works the same on every harness and doesn't depend on how Paperclip sets permissions:

```yaml
mcp_servers:
  fusion360:
    command: "uvx"
    args: ["fusion360-mcp-server", "--mode", "socket", "--read-only"]
    env:
      FUSION_MCP_HOST: "192.168.1.42"
```

For a Claude Code reviewer, add `"--read-only"` to `args` in the `.mcp.json` from step 2.

On a local model, additionally trim with the harness's `tools.include` filter; 14 tools are still more schema than a small context needs (see [local-llm.md](local-llm.md#trim-the-tool-list--this-matters-on-a-small-model)).

Exports (`export`, `export_step`, `export_stl`) are not annotated read-only and are refused in this mode. If the reviewer should produce artifacts, let the engineer export as the last step of its task and hand the file over.

Put the restriction in the server config, not in the agent's prompt. A prompt is a request; a flag is a boundary.

### 4. Smoke test

Assign the engineer a task: "call `ping`, then `get_scene_info`, report the result." `{"pong": true}` plus a scene summary means the whole chain is up. Do the same for the reviewer, and additionally have it try `create_sketch` — that call must come back `Refused (create_sketch): the server runs in --read-only mode`.

## Paperclip features that fit

- **Artifacts** — the engineer finishes a task with `export_step` / `export_stl` / `export`; the file becomes the task's artifact and the reviewer's input.
- **Review chain** — engineer task → reviewer task (`measure_*`, `check_interference`, `get_physical_properties`) → decision to the board if anything is off.
- **Routines** — a daily health check by a read-only agent: `ping`, `get_scene_info`, report to the board only on failure.
- **Secrets** — not needed for this server; the socket has no credentials. Don't invent one in the prompt.

## Open questions

1. **Does jev-guard work unattended?** If the guard waits for an interactive answer, an agent run by Paperclip has nobody at the terminal: the call either hangs until timeout or gets decided by the fallback path. Verify the guard's non-interactive behavior before giving the engineer write access.
2. **How does Paperclip launch Claude Code?** If it runs agents with permission checks bypassed, Claude Code permission rules don't restrict anything, and hooks plus `--read-only` are the only tool-level controls. That matters for the engineer, not the reviewer.
3. **Per-agent MCP config.** `--read-only` only helps if the reviewer can get its own server entry. How Paperclip scopes MCP servers per agent (per working directory, per agent config, global) decides whether "only the engineer has write tools" is enforceable at all. If the config is global, run every agent read-only and give the engineer a separate one.

## Caveats

- **All Fusion API units are centimeters.** State units explicitly in task descriptions; agents default to mm.
- **The TCP socket has no authentication.** Firewall it to the Paperclip host, trusted LAN only.
- **One Fusion session, one active document.** More agents do not mean more throughput on CAD work; they mean more review, not more modelling.
- Verify geometry in Fusion rather than trusting an agent's report of it.
