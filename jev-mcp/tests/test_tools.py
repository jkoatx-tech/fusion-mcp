"""Tool definitions, request building and response shaping."""

import pytest

from jev_mcp.tools import (
    TOOLS,
    build_questions,
    get_tool_by_name,
    get_tool_list,
    shape_response,
)

EXPECTED_TOOLS = {
    "jev_check",
    "jev_classify",
    "jev_score",
    "jev_ask",
    "jev_list_models",
}


def test_tool_names():
    assert {t["name"] for t in TOOLS} == EXPECTED_TOOLS


def test_tool_list_builds_mcp_tools():
    tools = get_tool_list()
    assert len(tools) == len(EXPECTED_TOOLS)
    for tool in tools:
        assert tool.description
        assert tool.inputSchema["type"] == "object"


@pytest.mark.parametrize("name", sorted(EXPECTED_TOOLS))
def test_annotations_read_only(name):
    ann = get_tool_by_name(name)["annotations"]
    assert ann == {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }


def test_unknown_tool():
    assert get_tool_by_name("nope") is None


# ── build_questions ──────────────────────────────────────────────────


def test_check_minimal():
    q = build_questions("jev_check", {"state": "x", "question": "Is it spam?"})
    assert q == {"check": {"type": "noul", "instructions": "Is it spam?"}}


def test_check_with_criteria():
    q = build_questions("jev_check", {
        "state": "x", "question": "Spam?", "yes_means": "ads", "no_means": "",
    })
    assert q["check"]["criteria"] == {"true": "ads"}


def test_classify_object_options():
    q = build_questions("jev_classify", {
        "state": "x",
        "question": "Which team?",
        "options": {"billing": "Money", "tech": None},
    })
    assert q == {"classify": {
        "type": "choice",
        "criteria": {"billing": "Money", "tech": None},
        "instructions": "Which team?",
    }}


def test_classify_list_options():
    q = build_questions("jev_classify", {"state": "x", "options": ["a", "b"]})
    assert q == {"classify": {"type": "choice", "criteria": {"a": None, "b": None}}}


def test_score():
    q = build_questions("jev_score", {
        "state": "x", "question": "Risk?", "levels": ["low", "mid", "high"],
    })
    assert q == {"score": {
        "type": "score",
        "criteria": ["low", "mid", "high"],
        "instructions": "Risk?",
    }}


def test_ask_passthrough():
    questions = {
        "urgent": {"type": "noul", "instructions": "Urgent?"},
        "team": {"type": "choice", "criteria": {"a": None, "b": None}},
    }
    assert build_questions("jev_ask", {"state": "x", "questions": questions}) == (
        questions
    )


def test_list_models_has_no_questions():
    with pytest.raises(ValueError):
        build_questions("jev_list_models", {})


# ── shape_response ───────────────────────────────────────────────────

META = {"model": "jev-1", "usage": {"input_tokens": 10, "output_tokens": 1}}


def test_shape_noul_yes():
    raw = {**META, "answers": {"check": {"type": "noul", "noul": 0.97}}}
    out = shape_response("jev_check", raw, 0.8)
    assert out["answer"] == "yes"
    assert out["p_yes"] == 0.97
    assert out["confidence"] == 0.97
    assert out["needs_review"] is False
    assert out["model"] == "jev-1"
    assert "type" not in out


def test_shape_noul_no_is_confident():
    raw = {**META, "answers": {"check": {"type": "noul", "noul": 0.05}}}
    out = shape_response("jev_check", raw, 0.8)
    assert out["answer"] == "no"
    assert out["confidence"] == pytest.approx(0.95)
    assert out["needs_review"] is False


def test_shape_noul_uncertain_needs_review():
    raw = {**META, "answers": {"check": {"type": "noul", "noul": 0.55}}}
    assert shape_response("jev_check", raw, 0.8)["needs_review"] is True


def test_shape_choice():
    raw = {**META, "answers": {"classify": {
        "type": "choice", "choice": "a", "confidence": 0.6,
        "probabilities": {"a": 0.6, "b": 0.4},
    }}}
    out = shape_response("jev_classify", raw, 0.8)
    assert out["choice"] == "a"
    assert out["probabilities"] == {"a": 0.6, "b": 0.4}
    assert out["needs_review"] is True


def test_shape_ask_lists_review_names():
    raw = {**META, "answers": {
        "sure": {"type": "noul", "noul": 0.99},
        "unsure": {"type": "noul", "noul": 0.5},
    }}
    out = shape_response("jev_ask", raw, 0.8)
    assert out["needs_review"] == ["unsure"]
    assert out["answers"]["sure"]["type"] == "noul"
    assert out["answers"]["sure"]["answer"] == "yes"
