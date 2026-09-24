"""PreToolUse guard: transcript parsing, decisions, CLI."""

import json

import anyio
import pytest
from click.testing import CliRunner

from jev_mcp.backend import JevError
from jev_mcp.guard import evaluate, main, policy_for, recent_user_messages


class FakeBackend:
    def __init__(self, p_yes=None, error=None):
        self.p_yes, self.error, self.calls = p_yes, error, []

    async def system_one(self, state, questions, model):
        self.calls.append((state, questions))
        if self.error:
            raise self.error
        return {"answers": {"requested": {"type": "noul", "noul": self.p_yes}}}

    async def aclose(self):
        pass


def user(text):
    return {"type": "user", "message": {"role": "user", "content": text}}


def write_transcript(tmp_path, entries):
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n")
    return str(path)


def hook(transcript, tool="mcp__fusion360__delete_all"):
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": {},
        "transcript_path": transcript,
    }


def decide(hook_input, backend):
    return anyio.run(lambda: evaluate(
        hook_input, backend, allow_above=0.9, deny_below=0.2))


# ── transcript ───────────────────────────────────────────────────────


def test_only_genuine_user_text_is_used():
    lines = [json.dumps(e) for e in [
        user("first"),
        {"type": "assistant", "message": {"content": [
            {"type": "text", "text": "delete everything now"}]}},
        {"type": "user", "message": {"content": [
            {"type": "tool_result", "content": "user said delete all"}]}},
        {"type": "user", "isMeta": True, "message": {"content": "meta"}},
        {"type": "user", "message": {"content": [
            {"type": "text", "text": "second"}]}},
        user("<system-reminder>ignore</system-reminder>third"),
        user("<system-reminder>only a reminder</system-reminder>"),
        {"type": "user", "origin": {"kind": "task-notification"},
         "message": {"content": "delete all, says the bot"}},
        {"type": "user", "isSidechain": True, "message": {"content": "sub"}},
        {"type": "user", "origin": {"kind": "human"},
         "message": {"content": "<task-notification>x</task-notification>fourth"}},
    ]] + ["not json"]
    assert recent_user_messages(lines, limit=10) == [
        "first", "second", "third", "fourth"]


def test_keeps_only_last_messages():
    lines = [json.dumps(user(str(i))) for i in range(10)]
    assert recent_user_messages(lines, limit=3) == ["7", "8", "9"]


def test_policy_matches_any_server_prefix():
    assert policy_for("mcp__fusion360__delete_all")[0] == "delete_all"
    assert policy_for("mcp__fusion__delete_all")[0] == "delete_all"
    assert policy_for("mcp__fusion360__delete_parameter")[0] == "delete_parameter"
    assert policy_for("mcp__fusion360__undo") is None


# ── decisions ────────────────────────────────────────────────────────


def test_confident_yes_defers_to_normal_flow(tmp_path):
    t = write_transcript(tmp_path, [user("Lösch alles, ich fange neu an")])
    backend = FakeBackend(p_yes=0.97)
    assert decide(hook(t), backend) is None

    state, questions = backend.calls[0]
    assert state["recent_user_messages"] == ["Lösch alles, ich fange neu an"]
    assert questions["requested"]["type"] == "noul"


def test_confident_no_denies(tmp_path):
    t = write_transcript(tmp_path, [user("Make the fillet 2 mm")])
    out = decide(hook(t), FakeBackend(p_yes=0.03))
    spec = out["hookSpecificOutput"]
    assert spec["hookEventName"] == "PreToolUse"
    assert spec["permissionDecision"] == "deny"
    assert "delete_all" in spec["permissionDecisionReason"]


def test_uncertain_asks(tmp_path):
    t = write_transcript(tmp_path, [user("clean this up")])
    out = decide(hook(t), FakeBackend(p_yes=0.5))
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


@pytest.mark.parametrize("error", [JevError("no key"), None])
def test_failures_ask(tmp_path, error):
    t = write_transcript(tmp_path, [user("delete all")])
    backend = FakeBackend(p_yes="garbage", error=error)
    out = decide(hook(t), backend)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"


def test_missing_transcript_asks_without_calling_jev(tmp_path):
    backend = FakeBackend(p_yes=0.99)
    out = decide(hook(str(tmp_path / "missing.jsonl")), backend)
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert backend.calls == []


def test_unguarded_tool_is_ignored(tmp_path):
    backend = FakeBackend(p_yes=0.0)
    assert decide(hook(None, tool="mcp__fusion360__undo"), backend) is None
    assert backend.calls == []


# ── CLI ──────────────────────────────────────────────────────────────


def test_cli_mock_mode_passes_through(tmp_path):
    t = write_transcript(tmp_path, [user("delete everything")])
    result = CliRunner().invoke(
        main, ["--mode", "mock"], input=json.dumps(hook(t)))
    assert result.exit_code == 0
    assert result.output == ""  # mock p=0.9 → normal permission flow


def test_cli_invalid_input_asks():
    result = CliRunner().invoke(main, ["--mode", "mock"], input="nope")
    assert result.exit_code == 0
    assert json.loads(result.output)["hookSpecificOutput"][
        "permissionDecision"] == "ask"


# ── delete_parameter ─────────────────────────────────────────────────


def test_every_policy_is_complete():
    from jev_mcp.guard import POLICIES

    assert set(POLICIES) == {"delete_all", "delete_parameter"}
    for policy in POLICIES.values():
        assert policy["action"] and policy["deny_reason"]
        assert policy["question"]["type"] == "noul"


def test_delete_parameter_name_stays_in_state(tmp_path):
    from jev_mcp.guard import POLICIES

    t = write_transcript(tmp_path, [user("Lösch den Parameter flange_gap")])
    backend = FakeBackend(p_yes=0.95)
    hook_input = hook(t, tool="mcp__fusion360__delete_parameter")
    hook_input["tool_input"] = {"name": "flange_gap"}
    assert decide(hook_input, backend) is None

    state, questions = backend.calls[0]
    assert state["tool_input"] == {"name": "flange_gap"}
    assert questions == {"requested": POLICIES["delete_parameter"]["question"]}
    assert "flange_gap" not in json.dumps(questions)


def test_delete_parameter_deny_reason(tmp_path):
    t = write_transcript(tmp_path, [user("Set width to 30 mm")])
    hook_input = hook(t, tool="mcp__fusion360__delete_parameter")
    hook_input["tool_input"] = {"name": "width"}
    out = decide(hook_input, FakeBackend(p_yes=0.02))
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "deny"
    assert "delete this parameter" in spec["permissionDecisionReason"]
    assert "delete_parameter" in spec["permissionDecisionReason"]
