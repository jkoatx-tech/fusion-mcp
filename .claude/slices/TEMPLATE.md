---
status: template   # draft | active | done  (only "active" slices are injected by the refocus hook)
mission: <mission name from .claude/intent.md>
---

# <Slice title: one concrete change>

## Goal

What changes, and why it serves the mission. One or two sentences.

## Done when

Checkable criteria. When all are met, the slice is finished: stop, do not polish.

- [ ] e.g. `uv run pytest -v` passes
- [ ] e.g. new tool `foo` has a mock handler and appears in `tests/test_tools.py`

## Out of scope

Things that look related but are not part of this slice. New ideas go here or
to the user as a proposal, never into the implementation.

## Proof

Filled in when done: the commands run and their result (test count, output).
One piece of evidence per "Done when" item, nothing more.
