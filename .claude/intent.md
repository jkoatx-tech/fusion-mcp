# Intent

The chain of intent from project down to the current mission. The refocus hook
injects this file at session start, after every compaction and every few
prompts. Keep it short: it is a compass, not a spec.

## Project (why this repo exists)

A reliable bridge that lets AI agents drive Autodesk Fusion 360 for CAD
automation. Focus of this fork: parametric construction against imported
reference meshes, and setups where Fusion runs on another machine in the LAN.

Good means: every tool does one Fusion operation predictably, works in
`--mode mock` without Fusion, and is covered by tests.

## Non-goals

- No CAD logic in the MCP server. It forwards tool calls 1:1 to the add-in.
- No batching of several Fusion operations into one tool call.
- No new tools, options or abstractions nobody asked for. Propose them instead.
- Do not rename `delete_all`, `delete_parameter` or `undo` (jev-guard matches them).

## Current mission

<!-- One mission at a time. Replace this block when it changes. -->
None set. Ask the user before starting work that is larger than one slice.
