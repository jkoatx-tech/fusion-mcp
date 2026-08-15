# Running this MCP server against a local LLM

The server speaks plain stdio MCP, so nothing about it is tied to a cloud model. This guide covers driving it with a **fully local** agent — no design data leaves your machines.

The reference setup here is [Hermes Agent](https://github.com/NousResearch/hermes-agent) (MIT, Nous Research) as the agent, [llama.cpp](https://github.com/ggml-org/llama.cpp) as the inference server, and Qwen 3.6 27B as the model. Any MCP-capable local agent works the same way — the parts specific to Hermes are the config file paths.

> **Scope note:** hardware figures and model recommendations below come from published third-party testing (see [Sources](#sources)), not from this repo's CI. The MCP-side config — tool counts, token measurements, filter names — is measured against this repo.

## Why bother

CAD files are often the most proprietary thing a company owns. Running the agent locally means part geometry, parameter names, customer part numbers, and imported reference scans never reach a third-party API. For anyone under certification constraints that forbid processing data outside the EU, a local model is the only workable option.

This is not a security guarantee. A local model with shell access on your machine is still a local model with shell access on your machine — see [Caveats](#caveats).

## Architecture

```
Local LLM (llama.cpp :8080)
        ↕ OpenAI-compatible HTTP
Hermes Agent ←(stdio MCP)→ This Server ←(TCP :9876)→ Fusion Add-in
```

All three legs can live on different hosts. A common split: Fusion on a Windows workstation, the LLM on whatever box has the GPU, the agent on either. See [Cross-machine setup](../README.md#cross-machine-setup-lan) for the Fusion leg.

## Hardware and model

Agentic work is unusually demanding on local inference for two reasons: the system prompt is large, and every tool result is fed back into context. That makes **prompt processing throughput** matter as much as token generation — a rig that generates fast but chews on prompts slowly feels terrible in an agent loop.

| Requirement | Value |
|---|---|
| Model | Qwen 3.6 27B, 4-bit — the dense variant, not the 35B MoE |
| Weights on disk | ~17 GB |
| Fast memory needed | **24 GB minimum** (GPU VRAM, or unified memory as on Apple Silicon / Framework Desktop) |
| Context window | 64K minimum for Hermes; 100K+ for comfort; 262,144 max for Qwen 3.6 |
| Recommended quant | Unsloth `UD-Q4_K_XL.GGUF` with MTP |

Notes from testing:

- The **dense 27B beats the 35B MoE** on tool-calling and code quality, despite being slower per token.
- 24 GB of *system* RAM is not the same as 24 GB of VRAM — the OS needs its share, so plan on 32 GB system RAM if you have no discrete GPU.
- Context is not free. The KV cache grows with the window, so the 17 GB of weights plus a 100K+ context is what actually fills a 24 GB card. If you're tight, quantize the KV cache or offload it to system RAM.
- Ollama works and is far easier to install, but it makes layer-offload decisions automatically and gets them wrong often enough to matter — a model that fits entirely in VRAM can end up partially on CPU and crawl. llama.cpp is fussier to set up and predictable once running.
- Multimodal (`mmproj`) weights are a separate download, and are only needed if you want the agent driving GUIs or reading screenshots. Fusion work through this server is pure text — you can skip them.

Benchmark your own box with `llama-bench` (ships with llama.cpp) and watch the `pp512` column, not just `tg128`.

## Setup

### 1. Serve the model

```bash
llama-server \
  -m Qwen3.6-27B-UD-Q4_K_XL.gguf \
  --host 0.0.0.0 --port 8080 \
  -c 131072 \
  -ngl 999 \
  --flash-attn \
  --jinja
```

- `-ngl 999` puts every layer on the GPU. If it OOMs, lower the context before lowering this.
- `--jinja` applies the model's own chat template. **Tool calling will not work reliably without it** — this is the single most common cause of "the agent sees the tools but never calls them."
- Add `--cache-type-k q8_0 --cache-type-v q8_0` to roughly halve KV cache memory at negligible quality cost if you need more context.

Confirm the model name the server reports — you'll need it in the next step:

```bash
curl http://localhost:8080/v1/models
```

### 2. Point Hermes at it

```bash
hermes model
```

Choose **Custom endpoint**, give it `http://localhost:8080` (or the LLM host's LAN IP) and the model name from above. Hermes writes this to `~/.hermes/config.yaml` and `~/.hermes/.env`.

Hermes detects local endpoints and raises its streaming timeouts automatically. If a long prompt-processing pass still trips a timeout on slow hardware, override with `HERMES_STREAM_READ_TIMEOUT`, `HERMES_STREAM_STALE_TIMEOUT`, or `HERMES_API_TIMEOUT`.

### 3. Register this server

Add to `mcp_servers` in `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  fusion360:
    command: "uvx"
    args: ["fusion360-mcp-server", "--mode", "socket"]
    enabled: true
    timeout: 120
```

If Fusion runs on another machine, pass the host through the environment:

```yaml
mcp_servers:
  fusion360:
    command: "uvx"
    args: ["fusion360-mcp-server", "--mode", "socket"]
    env:
      FUSION_MCP_HOST: "192.168.1.42"
```

Then `/reload-mcp` inside a Hermes session, and call `ping`. `{"pong": true}` means the whole chain is up.

## Trim the tool list — this matters on a small model

This server exposes **87 tools**. Serialized, their schemas are about **12.5K tokens**. On a 64K-context model that is roughly a fifth of the window gone before the agent has read a single instruction, and it competes with exactly the thing agentic CAD work needs most: room for accumulated tool results.

It also hurts selection accuracy. A 27B model choosing among 87 similarly-named tools picks wrong more often than one choosing among 16.

Use the `tools.include` filter to expose only what a given workflow needs:

```yaml
mcp_servers:
  fusion360:
    command: "uvx"
    args: ["fusion360-mcp-server", "--mode", "socket"]
    tools:
      include:
        - ping
        - get_scene_info
        - get_object_info
        - get_bounding_box
        - list_components
        - create_sketch
        - draw_rectangle
        - create_box_parametric
        - extrude
        - boolean_operation
        - move_body
        - get_parameters
        - create_parameter
        - set_parameter
        - import_mesh
        - export
      resources: false
      prompts: false
```

That set — enough for parametric box construction against an imported reference mesh — is 16 tools and about **2.1K tokens**, an ~83% reduction. Keep a second profile with the sheet-metal or CAM tools for when you need them rather than loading everything permanently.

`exclude` works too if you'd rather subtract; `include` is the safer default here because the tool list grows over time.

## Running Hermes unattended

Hermes is built to run 24/7 — cron triggers, webhooks, a desktop app that attaches to a backend running elsewhere. That's genuinely useful for CAD chores (nightly STEP exports, re-deriving a parametric family when a spec file changes), but there's a hard constraint specific to this stack:

> **Fusion 360 is a GUI application. It cannot run on a headless server.** The add-in lives inside a running Fusion instance with a logged-in Autodesk session. No amount of agent infrastructure changes that.

So the "put the agent on a VPS" pattern only works if you split the machines:

| Component | Where it can live |
|---|---|
| Fusion + add-in | **A desktop that stays logged in.** Physical workstation or a always-on VM with a real session. Not a container. |
| llama.cpp | Wherever the GPU is |
| Hermes backend | Anywhere — VPS, the Fusion box, a Mac Mini |
| Hermes desktop app | Your laptop, attached to the backend remotely |

The MCP server itself is a short-lived subprocess Hermes spawns, so it lives wherever the backend does, and reaches Fusion over TCP via `FUSION_MCP_HOST`.

A practical arrangement: Fusion on the workstation with `FUSION_MCP_HOST=0.0.0.0`, Hermes backend on a small always-on box, and the desktop app on your laptop pointed at that backend. Scheduled jobs then run whenever the workstation happens to be up — and fail cleanly with a connection error when it isn't, which is the correct behavior. Have the job call `ping` first and bail out rather than starting a modeling sequence it can't finish.

### Attaching the desktop app to a remote backend

The Hermes backend (`hermes serve`) listens on **port 9119** for the desktop app and web dashboard. In the app: **Settings → Gateway → Remote gateway**, then the server address and credentials.

Binding the backend to anything other than loopback automatically engages its auth gate. Do not open 9119 to the internet to make this work — put both machines on a [Tailscale](https://tailscale.com) network and bind to the Tailscale address. That applies doubly here, because the same network is carrying the Fusion socket on 9876, which has **no authentication at all**.

Note that `hermes serve` (the backend) and `hermes gateway run` (Telegram/Discord/Slack channels) are separate processes sharing `~/.hermes/`. You only need the former for desktop-app access.

### Teach it the conventions with `/learn`

Rather than repeating this server's quirks in every prompt, install them once as a skill. Hermes stores skills in `~/.hermes/skills/` and can author one from a source you point it at:

```
/learn https://github.com/jkoatx-tech/fusion-mcp/blob/main/README.md
```

This repo also ships a hand-written skill covering the failure modes a small model hits most often — centimeter units, one operation per call, verify-don't-assume. Install it with:

```bash
cp -r docs/skills/fusion360-mcp ~/.hermes/skills/
```

Then `/reload-mcp` (or restart the session). See [`docs/skills/fusion360-mcp/SKILL.md`](skills/fusion360-mcp/SKILL.md).

### Scheduled and event-driven jobs

Cron triggers and webhooks are configured from the desktop app. Things worth automating here:

- Nightly `export` of a named body to STEP/STL into a synced folder.
- A webhook that fires when a spec changes, then `set_parameter` + re-`export` to regenerate a part family.
- A `ping` health check that tells you the workstation dropped off before you rely on it.

Keep unattended jobs narrow and idempotent. An agent that fails halfway through a modeling sequence leaves a half-built design in the timeline, and an unattended run has nobody to notice — prefer jobs that read and export over jobs that model.

## What works well, what doesn't

Works well:

- Parametric construction driven by User Parameters — `create_parameter` / `set_parameter` / `create_box_parametric` are a good fit for a local model because the operations are named, discrete, and verifiable.
- Measure-then-act loops: `get_bounding_box` on an imported mesh, then size a box from it.
- Batch export via `export`.

Struggles:

- Long unsupervised chains. Context fills, the agent compacts, and it re-derives things it already knew. Break work into shorter sessions with explicit state in User Parameters rather than in the conversation.
- Anything relying on the model's own knowledge of Fusion's API surface. Small models hallucinate confidently here — including inventing plausible-sounding tool names. Keep `execute_code` on a short leash.
- Spatial reasoning without measurement. Have it call `get_bounding_box` rather than guess coordinates.

## Caveats

- **All Fusion API units are centimeters.** This trips up small models constantly, since users speak in mm. State the unit explicitly in your prompts.
- **The TCP socket has no authentication.** Trusted LAN only — never bind `0.0.0.0` on an internet-reachable host.
- **Local does not mean safe from prompt injection.** If the agent has web access, hostile text on a fetched page can still steer it, and a 27B model resists that noticeably less well than a frontier model. Run agents with filesystem and shell access on machines where total data loss would be an inconvenience, not a disaster.
- **Local does not mean private if the agent browses.** The model stays put; the agent's HTTP requests do not.
- Small models hallucinate freely when they can't look something up. Treat unverified factual claims from the agent as noise, and verify geometry in Fusion rather than trusting its summary.

## Sources

- Hermes Agent — [MCP config reference](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/reference/mcp-config-reference.md), [MCP feature guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md), [local LLM guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/local-llm-on-mac.md)
- Hardware, quantization, and model-comparison figures: c't 3003, "Lokale KI mit Hermes-Agent und Qwen 3.6" (2026)
