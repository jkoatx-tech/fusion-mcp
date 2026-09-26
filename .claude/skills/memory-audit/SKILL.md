---
name: memory-audit
description: Audit the agent instructions and memory of fusion-mcp (CLAUDE.md, AGENTS.md, intent, slices, agents, skills, Claude memory) for stale, contradicting or unfounded rules, trace where each came from, and propose fixes. Use when agents repeat a mistake you already corrected, after larger changes, or about once a month.
---

# Memory audit

Wrong rules spread: an agent reads a note, follows it, and writes it into the
next note. This audit finds such rules, traces their origin and removes them at
the source. It only reports and proposes. Edit files only after the user agrees.

## 1. Collect the sources

Read each of these that exists:

- `.claude/CLAUDE.md`, `AGENTS.md`, `README.md`, `.claude/intent.md`
- `.claude/agents/*.md`, `.claude/skills/*/SKILL.md`, `docs/skills/*/SKILL.md`
- `.claude/slices/*.md` (active and done)
- Claude memory, if accessible: `~/.claude/CLAUDE.md` and
  `~/.claude/projects/*/memory/` (on Windows: `%USERPROFILE%\.claude\...`)

## 2. Check facts against the code

Every number or claim that code can confirm, check it:

- Tool count: `uv run python -c "import fusion360_mcp.tools as t; print(len(t.TOOLS))"`
- Test count: `uv run pytest -q` (last line)
- Tool names mentioned in the docs exist in `src/fusion360_mcp/tools.py`
- Commands (`uv sync --dev`, `uv run ruff check`, ...) still work
- File paths mentioned in the docs exist

## 3. Find rule problems

- **Contradictions**: two sources say different things (e.g. a unit, a tool name).
- **Stale**: refers to removed code, old counts, finished missions, moved repos.
- **Unfounded**: a "never/always" rule with no reason and no code behind it.
- **Bureaucracy**: a check that only checks another check, or a required step
  whose result nobody uses.
- **Done slices still active**: `status: active` but the Proof is filled in.

## 4. Trace the origin

For each finding, find where it came from:

- `git log -S "<phrase>" --oneline -- <file>` shows the commit that added it.
- `git show <commit>` shows why (message, surrounding change).
- Search the other sources for copies of the same phrase: every copy is a
  carrier and must be fixed together, or the rule comes back.

## 5. Report

A table with one row per finding:

| Source (file:line) | Problem | Origin (commit) | Carriers | Proposed fix |

Then ask the user which fixes to apply. After applying, re-run step 2.
