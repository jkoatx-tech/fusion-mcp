---
name: fusion360-mcp
description: Conventions and failure modes for driving Autodesk Fusion 360 through the fusion360-mcp-server MCP tools. Use whenever modeling, measuring, or exporting in Fusion 360.
version: 1.0.0
metadata:
  hermes:
    tags: [cad, fusion360, mcp, parametric]
    category: engineering
---

# Fusion 360 via MCP

## When to use

Any task touching Autodesk Fusion 360 through the `fusion360` MCP server — creating geometry, measuring an existing design, importing reference meshes, or exporting.

## Before anything else

Call `ping`. If it does not return `{"pong": true}`, Fusion is not running, the add-in is not started, or the host is unreachable. **Stop and report that** — do not attempt modeling operations, and do not try to diagnose by calling other tools, which will simply time out one by one.

Then call `get_scene_info` to see what is actually in the design. Never assume the design is empty or that a body named in the conversation still exists.

## Units: everything is centimeters

The Fusion API's internal unit is the **centimeter**, and every numeric argument these tools take is in cm. People give dimensions in millimetres. This is the single most common source of silently wrong geometry — a part comes out ten times too large and nothing errors.

Convert explicitly and state the conversion:

- 250 mm → `25.0`
- 1.5 mm wall → `0.15`
- 3 mm hole diameter → `0.3`

Do this arithmetic in the open before the tool call, not in your head. Angles are in degrees, not radians.

The one exception is `import_mesh`, which takes an explicit `units` argument (`mm`/`cm`/`m`/`in`/`ft`) and converts on import. Pass the file's real units there.

## One operation per call

Do not attempt to batch operations. Batching multiple operations into a single tool call crashes the add-in and you will lose the session, not just the call.

Commands time out after 30 seconds. An operation on a heavy design that exceeds this is not necessarily failed — it may have completed inside Fusion after the timeout. Call `get_scene_info` to check before retrying, otherwise you risk applying the same feature twice.

## Measure, don't guess

You cannot see the design. Coordinates guessed from a description will be wrong.

- `get_bounding_box` gives min/max/size/center in cm for a body or component. Use it to size anything against imported reference geometry.
- `measure_distance` and `measure_angle` for relationships between entities.
- `get_physical_properties` for mass, volume, and center of mass.

The reliable pattern for fitting a part to a reference: `import_mesh` → `get_bounding_box` → compute → build.

## Prefer parametric construction

Where the choice exists, drive geometry from User Parameters rather than hardcoded numbers:

1. `create_parameter` for each meaningful dimension (`wall_t`, `outer_w`, …).
2. `create_box_parametric` and similar accept **string expressions** referencing those parameters — `"outer_w - 2 * wall_t"` — not just numbers.
3. `set_parameter` to revise, which rebuilds the whole design coherently.

This survives context compaction: the parameters are state stored in the document, so a later session can read them with `get_parameters` instead of relying on the conversation history.

Also prefer the sketch-and-extrude route (`create_sketch` → `draw_rectangle` → `extrude`) over the direct primitives (`create_box`, `create_cylinder`) when the result needs to stay editable. Direct primitives are built via `TemporaryBRepManager` and produce no timeline history.

## Do not invent tool names

The tool list is what you have. If an operation you want does not appear in it, say so rather than guessing at a plausible name — `create_rib`, `apply_texture`, and similar do not exist, and a hallucinated call wastes a turn.

`execute_code` runs arbitrary Python inside Fusion. It is the escape hatch when no tool fits, but it bypasses every safety guard in the server. Use it only when you have named the specific missing capability, and never as a first attempt.

## Destructive operations

`delete_all` clears the entire design. `undo` reverses the last operation. Confirm with the user before either — an unattended run should generally not call them at all.

Fusion designs have a parametric and a direct-modeling mode, and some operations switch the design between them irreversibly in the timeline. `undo` here carries a safety guard that checks the design type before and after and auto-redoes if the undo would have flipped the mode, but do not rely on that as a general safety net.

## Verify before reporting

After a modeling sequence, call `get_scene_info` — and `get_bounding_box` where dimensions matter — and report what the design actually contains. Do not describe what you intended to build. If the check disagrees with the intent, say so plainly rather than reconciling it in prose.
