"""End-to-end tool routing: mock backend, SDK wire format, MCP session."""

import json

import anyio
import httpx2
import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from jev_mcp.backend import JevError, MockBackend, TypeSafeBackend
from jev_mcp.server import create_server, run_tool


def run(coro_fn, *args, **kwargs):
    return anyio.run(lambda: coro_fn(*args, **kwargs))


# ── mock backend ─────────────────────────────────────────────────────


def test_mock_check():
    out = run(run_tool, MockBackend(), "jev_check",
              {"state": "hello", "question": "Greeting?"}, min_confidence=0.8)
    assert out["answer"] == "yes"
    assert out["model"] == "jev-mock"


def test_mock_classify():
    out = run(run_tool, MockBackend(), "jev_classify",
              {"state": "x", "options": ["a", "b", "c"]}, min_confidence=0.8)
    assert out["choice"] == "a"
    assert sum(out["probabilities"].values()) == pytest.approx(1.0)
    assert out["needs_review"] is True  # 0.7 < 0.8


def test_mock_score():
    out = run(run_tool, MockBackend(), "jev_score",
              {"state": "x", "levels": ["low", "mid", "high"]},
              min_confidence=0.8)
    assert out["score"] == pytest.approx(1.0)
    assert out["legend"] == {"0": "low", "1": "mid", "2": "high"}
    assert out["needs_review"] is False


def test_mock_ask():
    out = run(run_tool, MockBackend(), "jev_ask", {
        "state": "x",
        "questions": {
            "ok": {"type": "noul"},
            "team": {"type": "choice", "criteria": {"a": None, "b": None}},
        },
    }, min_confidence=0.8)
    assert set(out["answers"]) == {"ok", "team"}
    assert out["needs_review"] == ["team"]


def test_mock_list_models():
    out = run(run_tool, MockBackend(), "jev_list_models", {}, min_confidence=0.8)
    assert out["models"][0]["name"] == "jev-mock"


def test_mock_rejects_bad_score():
    with pytest.raises(JevError):
        run(run_tool, MockBackend(), "jev_ask", {
            "state": "x", "questions": {"s": {"type": "score", "criteria": []}},
        }, min_confidence=0.8)


def test_unknown_tool():
    with pytest.raises(ValueError):
        run(run_tool, MockBackend(), "nope", {}, min_confidence=0.8)


# ── TypeSafe backend against the SDK wire format ─────────────────────


def api_backend(handler) -> TypeSafeBackend:
    return TypeSafeBackend(
        api_key="test-key",
        base_url="https://api.test",
        transport=httpx2.MockTransport(handler),
    )


def test_api_request_and_response_wire_format():
    seen = {}

    def handler(request: httpx2.Request) -> httpx2.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json={
            "model": "jev-1",
            "usage": {"input_tokens": 42, "output_tokens": 3},
            "answers": {"score": {
                "type": "score",
                "score": 1.7,
                "confidence": 0.9,
                "legend": {"0": "low", "1": "mid", "2": "high"},
                "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
            }},
        })

    out = run(run_tool, api_backend(handler), "jev_score", {
        "state": {"diff": "rm -rf build"},
        "question": "How risky?",
        "levels": ["low", "mid", "high"],
        "model": "jev-1",
    }, min_confidence=0.8)

    assert seen["url"] == "https://api.test/v1/systemone"
    assert seen["auth"] == "Bearer test-key"
    assert seen["body"] == {
        "state": {"diff": "rm -rf build"},
        "model": "jev-1",
        "questions": {"score": {
            "type": "score",
            "criteria": ["low", "mid", "high"],
            "instructions": "How risky?",
        }},
    }
    assert out == {
        "score": 1.7,
        "confidence": 0.9,
        "legend": {"0": "low", "1": "mid", "2": "high"},
        "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8},
        "needs_review": False,
        "model": "jev-1",
        "usage": {"input_tokens": 42, "output_tokens": 3},
    }


def test_api_error_becomes_jev_error():
    def handler(request):
        return httpx2.Response(401, json={"error": "Invalid API key"})

    with pytest.raises(JevError, match="Invalid API key"):
        run(run_tool, api_backend(handler), "jev_check",
            {"state": "x", "question": "?"}, min_confidence=0.8)


def test_missing_api_key_is_explained(monkeypatch):
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevError, match="TYPESAFE_API_KEY"):
        run(run_tool, TypeSafeBackend(), "jev_check",
            {"state": "x", "question": "?"}, min_confidence=0.8)


# ── MCP protocol ─────────────────────────────────────────────────────


async def _session_roundtrip():
    app = create_server(MockBackend(), min_confidence=0.8)
    async with create_connected_server_and_client_session(app) as client:
        tools = await client.list_tools()
        ok = await client.call_tool(
            "jev_check", {"state": "x", "question": "Yes?"})
        bad = await client.call_tool("jev_score", {"state": "x"})
    return tools, ok, bad


def test_mcp_session_structured_content_and_errors():
    tools, ok, bad = anyio.run(_session_roundtrip)
    assert {t.name for t in tools.tools} >= {"jev_check", "jev_ask"}

    assert ok.isError is False
    assert ok.structuredContent["answer"] == "yes"
    assert json.loads(ok.content[0].text) == ok.structuredContent

    # Missing required "levels" fails input validation.
    assert bad.isError is True
