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
    assert policy_for("mcp__fusion360__undo")[0] == "undo"
    assert policy_for("mcp__fusion360__redo_everything") is None


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
    assert decide(hook(None, tool="mcp__fusion360__extrude"), backend) is None
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
    from jev_mcp.guard import MAIL_TOOLS, POLICIES

    assert set(POLICIES) == {"delete_all", "delete_parameter", "undo",
                             *MAIL_TOOLS}
    for policy in POLICIES.values():
        assert policy["action"] and policy["deny_reason"]
        assert policy["question"]["type"] == "noul"
        assert policy.get("on_no", "deny") in {"deny", "ask"}


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


# ── undo ─────────────────────────────────────────────────────────────


def test_undo_confident_no_asks_instead_of_deny(tmp_path):
    t = write_transcript(tmp_path, [user("Add a 2 mm fillet")])
    out = decide(hook(t, tool="mcp__fusion360__undo"), FakeBackend(p_yes=0.02))
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "ask"
    assert "did not ask to undo" in spec["permissionDecisionReason"]


def test_undo_requested_passes(tmp_path):
    t = write_transcript(tmp_path, [user("mach das rückgängig")])
    assert decide(hook(t, tool="mcp__fusion360__undo"),
                  FakeBackend(p_yes=0.96)) is None


def test_deny_policies_still_deny(tmp_path):
    t = write_transcript(tmp_path, [user("Add a 2 mm fillet")])
    for tool in ("delete_all", "delete_parameter"):
        out = decide(hook(t, tool=f"mcp__fusion360__{tool}"),
                     FakeBackend(p_yes=0.02))
        assert out["hookSpecificOutput"]["permissionDecision"] == "deny"


# ── mail ─────────────────────────────────────────────────────────────

MAIL = {"to": ["zoe@example.com"], "subject": "Angebot", "body": "Hallo Zoe"}


def mail_hook(transcript, tool="mcp__gmail__send_message", tool_input=MAIL):
    h = hook(transcript, tool=tool)
    h["tool_input"] = dict(tool_input)
    return h


def test_mail_draft_only_denies(tmp_path):
    t = write_transcript(tmp_path, [user("Schreib Anna einen Entwurf, nicht senden")])
    out = decide(mail_hook(t), FakeBackend(p_yes=0.04))
    spec = out["hookSpecificOutput"]
    assert spec["permissionDecision"] == "deny"
    assert "send this email" in spec["permissionDecisionReason"]
    assert "show the user the draft" in spec["permissionDecisionReason"]


def test_mail_requested_passes_and_recipients_stay_in_state(tmp_path):
    from jev_mcp.guard import POLICIES

    t = write_transcript(tmp_path, [user("Schick die Mail an Zoe ab")])
    backend = FakeBackend(p_yes=0.95)
    assert decide(mail_hook(t), backend) is None
    state, questions = backend.calls[0]
    assert state["tool_input"] == MAIL
    assert questions == {"requested": POLICIES["send_message"]["question"]}
    assert "zoe" not in json.dumps(questions).lower()


@pytest.mark.parametrize("tool", [
    "mcp__gmail__send_message", "mcp__m365__send-mail", "mcp__x__reply",
    "mcp__x__forward", "mcp__outlook__outlook_send_mail",
    "mcp_gmail_send_message", "send_email",
])
def test_mail_tools_match_across_naming_schemes(tool):
    assert policy_for(tool, MAIL) is not None


def test_send_message_without_recipient_is_not_mail():
    # e.g. a chat or agent-to-agent tool that is also called send_message
    assert policy_for("mcp__ccd_session_mgmt__send_message",
                      {"session_id": "x", "message": "hi"}) is None
    assert policy_for("mcp__teams__teams_send_chat_message", MAIL) is None


# ── prompt store (Copilot) ───────────────────────────────────────────


def test_copilot_cli_prompt_then_tool_call(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_GUARD_STATE_DIR", str(tmp_path))
    runner = CliRunner()
    prompt = {"sessionId": "s-1", "timestamp": 1, "cwd": ".",
              "prompt": "Entwurf an Anna, noch nicht senden"}
    assert runner.invoke(main, ["--mode", "mock"],
                         input=json.dumps(prompt)).output == ""

    from jev_mcp.guard import read_prompts
    assert read_prompts("s-1") == ["Entwurf an Anna, noch nicht senden"]

    backend = FakeBackend(p_yes=0.03)
    call = {"sessionId": "s-1", "timestamp": 2, "cwd": ".",
            "toolName": "send_email", "toolArgs": json.dumps(MAIL)}
    out = decide(call, backend)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    state, _ = backend.calls[0]
    assert state["recent_user_messages"] == ["Entwurf an Anna, noch nicht senden"]
    assert state["tool_input"] == MAIL


def test_copilot_cli_gets_flat_decision(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_GUARD_STATE_DIR", str(tmp_path))
    call = {"sessionId": "none", "toolName": "send_email", "toolArgs": MAIL}
    result = CliRunner().invoke(main, ["--mode", "mock"], input=json.dumps(call))
    out = json.loads(result.output)
    assert out == {"permissionDecision": "ask",
                   "permissionDecisionReason": out["permissionDecisionReason"]}


def test_vscode_prompt_store_used_when_transcript_unreadable(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_GUARD_STATE_DIR", str(tmp_path))
    from jev_mcp.guard import record_prompt
    record_prompt("vs-1", "<system-reminder>x</system-reminder>Send it to Anna")
    vs_transcript = tmp_path / "vscode.json"
    vs_transcript.write_text('{"requests": []}')
    h = mail_hook(str(vs_transcript), tool="mcp_gmail_send_message")
    h["session_id"] = "vs-1"
    backend = FakeBackend(p_yes=0.97)
    assert decide(h, backend) is None
    assert backend.calls[0][0]["recent_user_messages"] == ["Send it to Anna"]


def test_prompt_store_keeps_last_messages(tmp_path, monkeypatch):
    monkeypatch.setenv("JEV_GUARD_STATE_DIR", str(tmp_path))
    from jev_mcp.guard import read_prompts, record_prompt
    for i in range(8):
        record_prompt("../evil/id", str(i))
    assert read_prompts("../evil/id") == ["3", "4", "5", "6", "7"]
    assert all(p.parent == tmp_path for p in tmp_path.iterdir())
