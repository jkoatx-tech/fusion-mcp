"""
PreToolUse hook: let Jev check destructive or outward-facing tools.

Before a destructive Fusion tool (``delete_all``, ``delete_parameter``,
``undo``) or a mail tool (send, reply, forward) runs, Jev judges whether the
user explicitly asked for exactly that. The state Jev sees is built from the
*user's own* messages (session transcript, or for GitHub Copilot the prompts
recorded by the same hook), so the agent cannot talk its way past the check.

The guard only ever restricts, it never grants permission:

- Jev is confident the user asked for it   → no output, normal permission flow
- Jev is unsure, or the check fails        → ``ask`` (the user confirms)
- Jev is confident the user did not ask    → ``deny`` (reason goes to Claude);
  policies with ``on_no="ask"`` (``undo``) ask instead

Register it in ``~/.claude/settings.json`` or as a Copilot hook (see
README).
"""

import json
import os
import re
import sys
from collections.abc import Iterable
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

# The backend (typesafe-sdk) is imported only when a guarded tool is called:
# some clients run this hook before every tool call.
if TYPE_CHECKING:
    from .backend import Backend

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
    "undo": {
        "action": (
            "undo: reverts the last operation in the open Fusion 360 design "
            "(may also revert a design-type switch)."
        ),
        "question": {
            "type": "noul",
            "instructions": (
                "Did the user ask to undo, revert or roll back the last "
                "operation?"
            ),
            "criteria": {
                "true": (
                    "The user asked to undo or go back, e.g. 'undo that', "
                    "'mach das rückgängig', 'revert the last step'."
                ),
                "false": (
                    "The user asked for something else or never mentioned "
                    "reverting anything."
                ),
            },
        },
        "deny_reason": "the user did not ask to undo",
        # undo is Claude's normal way to fix its own last step: never block
        # it outright, let the user confirm instead.
        "on_no": "ask",
    },
}

_SEND_MAIL = {
    "action": (
        "Sends an email on the user's behalf with the recipients, subject and "
        "body in tool_input. A sent email cannot be recalled."
    ),
    # Recipients and body stay in the state (tool_input), never in the
    # instructions, so the caller cannot rewrite the question.
    "question": {
        "type": "noul",
        "instructions": (
            "Did the user explicitly ask to send this email now, to the "
            "recipients in tool_input?"
        ),
        "criteria": {
            "true": (
                "The user asked to send, reply or forward this message to "
                "these recipients (by name, address or unambiguously), or "
                "approved a draft they were shown, e.g. 'schick sie ab', "
                "'send it to Anna', 'yes, reply'."
            ),
            "false": (
                "The user only asked for a draft or a review, named other "
                "recipients, wanted to wait, or never mentioned sending."
            ),
        },
    },
    "deny_reason": "the user did not ask to send this email",
    "deny_hint": "show the user the draft and ask before sending.",
}
# Common names of send/reply/forward tools across mail MCP servers (Gmail,
# Microsoft 365, SMTP). Drafts are not listed: they leave nothing.
MAIL_TOOLS = (
    "send_message", "send_email", "send_mail", "send-mail",
    "reply", "reply_all", "reply-mail", "reply_to_message",
    "forward", "forward_message", "forward-mail",
)
# "send_message" also names non-mail tools (chat, agent-to-agent). Guard it
# only when the input carries a mail recipient.
_AMBIGUOUS = {"send_message"}
_RECIPIENT_KEYS = {"to", "recipients", "toRecipients", "cc", "bcc"}
POLICIES.update({name: _SEND_MAIL for name in MAIL_TOOLS})

MAX_MESSAGES = 5
MAX_MESSAGE_CHARS = 2000
# Harness-injected blocks inside user entries; not typed by the human.
_INJECTED = re.compile(
    r"<(system-reminder|task-notification)>.*?</\1>", re.S)


def policy_for(tool_name: str, tool_input: Any = None) -> tuple[str, dict] | None:
    short = tool_name.rsplit("__", 1)[-1]
    if short not in POLICIES:
        # Other clients prefix differently (e.g. "mcp_gmail_send_message"):
        # fall back to the longest known name the tool name ends with.
        known = [k for k in POLICIES
                 if re.search(rf"(^|[_.-]){re.escape(k)}$", short)]
        short = max(known, key=len, default=short)
    policy = POLICIES.get(short)
    if policy and short in _AMBIGUOUS and not (
            isinstance(tool_input, dict) and _RECIPIENT_KEYS & tool_input.keys()):
        return None
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


# ── prompt store (GitHub Copilot) ────────────────────────────────────
# Copilot gives PreToolUse no readable transcript (CLI: none, VS Code: its
# own format). Its prompt hook does carry the user's text, so the guard
# records prompts per session and reads them back at PreToolUse.


def _store_dir() -> Path:
    return Path(os.environ.get("JEV_GUARD_STATE_DIR")
                or Path.home() / ".jev-guard" / "sessions")


def _store_file(session_id: str) -> Path:
    return _store_dir() / (re.sub(r"[^A-Za-z0-9_.-]", "_", session_id) + ".json")


def read_prompts(session_id: str | None) -> list[str]:
    if not session_id:
        return []
    try:
        prompts = json.loads(_store_file(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return [p for p in prompts if isinstance(p, str)][-MAX_MESSAGES:] \
        if isinstance(prompts, list) else []


def record_prompt(session_id: str | None, prompt: Any) -> None:
    if not session_id or not isinstance(prompt, str):
        return
    text = _INJECTED.sub("", prompt).strip()[:MAX_MESSAGE_CHARS]
    if not text:
        return
    path = _store_file(session_id)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps((read_prompts(session_id) + [text])[-MAX_MESSAGES:]),
                        encoding="utf-8")
    except OSError:
        pass  # no stored prompt → PreToolUse falls back to ask


# ── hook input ───────────────────────────────────────────────────────


def normalize(raw: dict) -> dict:
    """Map Claude Code / VS Code (snake_case) and Copilot CLI (camelCase)
    hook input onto one shape."""
    tool_input = raw.get("tool_input", raw.get("toolArgs"))
    if isinstance(tool_input, str):
        try:
            tool_input = json.loads(tool_input)
        except ValueError:
            tool_input = {"raw": tool_input}
    return {
        "tool_name": raw.get("tool_name") or raw.get("toolName") or "",
        "tool_input": tool_input if isinstance(tool_input, dict) else {},
        "transcript_path": raw.get("transcript_path"),
        "session_id": raw.get("session_id") or raw.get("sessionId"),
        "prompt": raw.get("prompt"),
        # Copilot CLI reads a flat decision, Claude Code and VS Code the
        # hookSpecificOutput envelope.
        "flat": "toolName" in raw or "sessionId" in raw,
    }


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
    backend: "Backend",
    *,
    allow_above: float,
    deny_below: float,
) -> dict | None:
    """Return the hook output for one PreToolUse event (None = no opinion)."""
    from .backend import JevError

    hook = normalize(hook_input)
    match = policy_for(hook["tool_name"], hook["tool_input"])
    if match is None:
        return None
    short, policy = match

    # Recorded prompts first: VS Code writes its transcript asynchronously,
    # so the latest prompt may be missing there. Claude Code records none.
    messages = (read_prompts(hook["session_id"])
                or read_transcript(hook["transcript_path"]))
    if not messages:
        return _decision(
            "ask", f"Jev guard: no user messages found to verify {short}.")

    state = {
        "action": policy["action"],
        "tool_input": hook["tool_input"],
        "recent_user_messages": messages,
    }
    try:
        raw = await backend.system_one(state, {"requested": policy["question"]}, None)
        p_yes = float(raw["answers"]["requested"]["noul"])
    except (JevError, KeyError, TypeError, ValueError) as exc:
        return _decision("ask", f"Jev guard could not verify {short}: {exc}")

    if p_yes >= allow_above:
        return None
    if p_yes < deny_below and policy.get("on_no", "deny") == "deny":
        return _decision(
            "deny",
            f"Jev guard: {policy['deny_reason']} (p={p_yes:.2f}). Do not "
            f"call {short}; "
            + policy.get("deny_hint",
                         "ask the user or use a targeted operation instead."),
        )
    if p_yes < deny_below:
        return _decision(
            "ask",
            f"Jev guard: {policy['deny_reason']} (p={p_yes:.2f}). "
            f"Please confirm {short}.",
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

    hook = normalize(hook_input)
    if not hook["tool_name"]:
        # Prompt hook (Copilot): remember what the user typed, decide nothing.
        record_prompt(hook["session_id"], hook["prompt"])
        return

    if policy_for(hook["tool_name"], hook["tool_input"]) is None:
        return  # not a guarded tool: no opinion, and no backend to load

    import anyio
    from typesafe_sdk import RetryPolicy

    from .backend import MockBackend, TypeSafeBackend

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
    if output is not None and hook["flat"]:
        output = {k: v for k, v in output["hookSpecificOutput"].items()
                  if k != "hookEventName"}
    if output is not None:
        click.echo(json.dumps(output))
