"""
Claude Code PreToolUse hook: let Jev check destructive Fusion tools.

Before a destructive Fusion tool (``delete_all``, ``delete_parameter``) runs,
Jev judges whether the user explicitly asked for exactly that.  The state Jev
sees is built from the *user's own* messages in the session transcript, so
Claude cannot talk its way past the check.

The guard only ever restricts, it never grants permission:

- Jev is confident the user asked for it   → no output, normal permission flow
- Jev is unsure, or the check fails        → ``ask`` (the user confirms)
- Jev is confident the user did not ask    → ``deny`` (reason goes to Claude)

Register it in ``~/.claude/settings.json`` (see README), matching
``mcp__.*__(delete_all|delete_parameter)``.
"""

import json
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import anyio
import click
from typesafe_sdk import RetryPolicy

from .backend import Backend, JevError, MockBackend, TypeSafeBackend

# Tools the guard knows, keyed by the tool name without the mcp__<server>__ prefix.
POLICIES: dict[str, dict] = {
    "delete_all": {
        "action": (
            "delete_all: deletes every timeline item in the open Fusion 360 "
            "design (all bodies, sketches and features)."
        ),
        "question": {
            "type": "noul",
            "instructions": (
                "Did the user explicitly ask to delete, clear or reset the "
                "entire Fusion design?"
            ),
            "criteria": {
                "true": (
                    "The user clearly requested wiping the whole design, e.g. "
                    "'delete everything', 'clear the design', 'start from "
                    "scratch'."
                ),
                "false": (
                    "The user asked for something else, only a partial "
                    "deletion, or never mentioned deleting."
                ),
            },
        },
        "deny_reason": "the user did not ask to clear the whole design",
    },
    "delete_parameter": {
        "action": (
            "delete_parameter: removes the user parameter named in "
            "tool_input.name from the open Fusion 360 design. Features and "
            "expressions that reference it lose their driving value."
        ),
        # The parameter name stays in the state (tool_input), never in the
        # instructions, so the caller cannot rewrite the question.
        "question": {
            "type": "noul",
            "instructions": (
                "Did the user explicitly ask to delete the parameter named in "
                "tool_input.name?"
            ),
            "criteria": {
                "true": (
                    "The user asked to delete or remove this parameter, by "
                    "its name or unambiguously (e.g. 'delete the width "
                    "parameter', 'remove all user parameters')."
                ),
                "false": (
                    "The user asked to change, rename or keep the parameter, "
                    "meant a different parameter, or never mentioned "
                    "deleting it."
                ),
            },
        },
        "deny_reason": "the user did not ask to delete this parameter",
    },
}

MAX_MESSAGES = 5
MAX_MESSAGE_CHARS = 2000
# Harness-injected blocks inside user entries; not typed by the human.
_INJECTED = re.compile(
    r"<(system-reminder|task-notification)>.*?</\1>", re.S)


def policy_for(tool_name: str) -> tuple[str, dict] | None:
    short = tool_name.rsplit("__", 1)[-1]
    policy = POLICIES.get(short)
    return (short, policy) if policy else None


# ── transcript ───────────────────────────────────────────────────────


def _user_text(entry: dict) -> str | None:
    """Text the human typed, or None for tool results and injected entries."""
    if entry.get("type") != "user" or entry.get("isMeta") or entry.get("isSidechain"):
        return None
    # Newer transcripts tag who produced the entry; only a human counts.
    origin = entry.get("origin")
    if isinstance(origin, dict) and origin.get("kind") not in (None, "human"):
        return None
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        if any(block.get("type") == "tool_result" for block in content
               if isinstance(block, dict)):
            return None
        text = "\n".join(
            block.get("text", "") for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        return None
    text = _INJECTED.sub("", text).strip()
    return text[:MAX_MESSAGE_CHARS] or None


def recent_user_messages(lines: Iterable[str], limit: int = MAX_MESSAGES) -> list[str]:
    messages = []
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if isinstance(entry, dict) and (text := _user_text(entry)):
            messages.append(text)
    return messages[-limit:]


def read_transcript(path: str | None) -> list[str]:
    if not path:
        return []
    try:
        with Path(path).expanduser().open(encoding="utf-8") as fh:
            return recent_user_messages(fh)
    except OSError:
        return []


# ── decision ─────────────────────────────────────────────────────────


def _decision(kind: str, reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": kind,
            "permissionDecisionReason": reason,
        },
    }


async def evaluate(
    hook_input: dict,
    backend: Backend,
    *,
    allow_above: float,
    deny_below: float,
) -> dict | None:
    """Return the hook output for one PreToolUse event (None = no opinion)."""
    match = policy_for(hook_input.get("tool_name", ""))
    if match is None:
        return None
    short, policy = match

    messages = read_transcript(hook_input.get("transcript_path"))
    if not messages:
        return _decision(
            "ask", f"Jev guard: no user messages found to verify {short}.")

    state = {
        "action": policy["action"],
        "tool_input": hook_input.get("tool_input") or {},
        "recent_user_messages": messages,
    }
    try:
        raw = await backend.system_one(state, {"requested": policy["question"]}, None)
        p_yes = float(raw["answers"]["requested"]["noul"])
    except (JevError, KeyError, TypeError, ValueError) as exc:
        return _decision("ask", f"Jev guard could not verify {short}: {exc}")

    if p_yes >= allow_above:
        return None
    if p_yes < deny_below:
        return _decision(
            "deny",
            f"Jev guard: {policy['deny_reason']} (p={p_yes:.2f}). Do not "
            f"call {short}; ask the user or use a targeted operation instead.",
        )
    return _decision(
        "ask",
        f"Jev guard: unsure whether the user wants {short} (p={p_yes:.2f}). "
        f"Please confirm.",
    )


@click.command()
@click.option("--mode", type=click.Choice(["api", "mock"]), default="api",
              help="'mock' answers without calling TypeSafe (testing only)")
@click.option("--allow-above", type=click.FloatRange(0.5, 1.0), default=0.9,
              show_default=True, help="p(yes) at or above: normal permission flow")
@click.option("--deny-below", type=click.FloatRange(0.0, 0.5), default=0.2,
              show_default=True, help="p(yes) below: deny")
@click.option("--timeout", type=float, default=5.0, show_default=True,
              help="Seconds per Jev request (keep below the hook timeout)")
def main(mode: str, allow_above: float, deny_below: float, timeout: float) -> None:
    """PreToolUse hook: Jev checks destructive Fusion tools (reads stdin)."""
    try:
        hook_input: Any = json.load(sys.stdin)
    except ValueError:
        hook_input = None
    if not isinstance(hook_input, dict):
        click.echo(json.dumps(_decision("ask", "Jev guard: invalid hook input.")))
        return

    backend: Backend = (
        MockBackend() if mode == "mock"
        else TypeSafeBackend(timeout=timeout, retry=RetryPolicy(max_retries=1))
    )

    async def run() -> dict | None:
        try:
            return await evaluate(hook_input, backend,
                                  allow_above=allow_above, deny_below=deny_below)
        finally:
            await backend.aclose()

    output = anyio.run(run)
    if output is not None:
        click.echo(json.dumps(output))
