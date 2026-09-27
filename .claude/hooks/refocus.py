"""Refocus hook: re-inject the chain of intent (project -> mission -> slice).

Runs as a Claude Code hook on two events:

- SessionStart (startup, resume, clear, compact): always injects.
- UserPromptSubmit: injects every REFOCUS_EVERY prompts (default 8).

The context comes from .claude/intent.md and every slice in .claude/slices/
with `status: active`. Standard library only; never blocks a prompt: on any
error it exits 0 without output.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

DEFAULT_EVERY = 8

QUESTION = (
    "Refocus: is what you are doing right now still aligned with the active "
    "slice, the mission and the project above? If the slice's 'Done when' is "
    "met, stop and report. If you are adding something the intent does not "
    "ask for, stop and propose it to the user instead."
)


def project_dir() -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2]


def status_of(text: str) -> str | None:
    match = re.match(r"---\s*\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "status":
            return value.split("#")[0].strip().lower()
    return None


def active_slices(root: Path) -> list[tuple[str, str]]:
    slices_dir = root / ".claude" / "slices"
    if not slices_dir.is_dir():
        return []
    result = []
    for path in sorted(slices_dir.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        if status_of(text) == "active":
            # The proof is evidence for later, not direction for now.
            body = text.split("\n## Proof", 1)[0].rstrip()
            result.append((path.name, body))
    return result


def build_context(root: Path) -> str:
    parts = ["# Chain of intent (injected by .claude/hooks/refocus.py)"]
    intent = root / ".claude" / "intent.md"
    if intent.is_file():
        parts.append(intent.read_text(encoding="utf-8").strip())
    else:
        parts.append("No .claude/intent.md found.")
    slices = active_slices(root)
    if slices:
        for name, body in slices:
            parts.append(f"## Active slice: .claude/slices/{name}\n\n{body}")
        if len(slices) > 1:
            parts.append("Note: more than one slice is active. Work on one at a time.")
    else:
        parts.append("## Active slice\n\nNone. Work from the user's request.")
    parts.append(QUESTION)
    return "\n\n".join(parts)


def due(root: Path, session_id: str) -> bool:
    """Count prompts per session; True every REFOCUS_EVERY prompts."""
    try:
        every = max(1, int(os.environ.get("REFOCUS_EVERY", DEFAULT_EVERY)))
    except ValueError:
        every = DEFAULT_EVERY
    state_dir = root / ".claude" / ".state"
    state_dir.mkdir(parents=True, exist_ok=True)
    safe_id = re.sub(r"[^A-Za-z0-9_-]", "_", session_id or "default")
    counter = state_dir / f"refocus-{safe_id}.txt"
    try:
        count = int(counter.read_text(encoding="ascii")) + 1
    except (OSError, ValueError):
        count = 1
    counter.write_text(str(count), encoding="ascii")
    return count % every == 0


def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except json.JSONDecodeError:
        payload = {}
    event = payload.get("hook_event_name", "SessionStart")
    root = project_dir()

    if event == "UserPromptSubmit" and not due(root, payload.get("session_id", "")):
        return
    if event not in ("SessionStart", "UserPromptSubmit"):
        return

    output = {
        "hookSpecificOutput": {
            "hookEventName": event,
            "additionalContext": build_context(root),
        }
    }
    # ASCII-escaped JSON: safe on Windows consoles with a non-UTF-8 code page.
    sys.stdout.write(json.dumps(output))


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 - a hook must never block the session
        pass
    sys.exit(0)
