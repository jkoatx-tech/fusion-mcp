"""
MCP tool definitions for TypeSafe Jev (System One decision model).

Jev never writes text: every tool returns a typed answer with calibrated
probabilities.  Each tool builds one or more *questions* in the wire format of
``POST /v1/systemone`` and shapes the answers for the calling agent, adding a
``needs_review`` flag when confidence is below the configured threshold.
"""

from collections.abc import Mapping

import mcp.types as types

STATE_SCHEMA = {
    "type": ["string", "object", "array"],
    "description": (
        "The input Jev judges: plain text, or a JSON object/array. Jev only "
        "sees this state, so include everything the decision depends on."
    ),
}

MODEL_SCHEMA = {
    "type": "string",
    "description": "Model name or alias (default: server setting, e.g. jev-latest)",
}

TOOLS: list[dict] = [
    {
        "name": "jev_check",
        "title": "Jev: Yes/No Check",
        "description": (
            "Ask Jev a yes/no question about the given state. Returns the "
            "calibrated probability of 'yes' (p_yes), the resulting answer and "
            "needs_review when Jev is unsure. Use for gates and verifications, "
            "e.g. 'Does this change touch the public API?'."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["state", "question"],
            "properties": {
                "state": STATE_SCHEMA,
                "question": {
                    "type": "string",
                    "description": "Yes/no question or statement to evaluate",
                },
                "yes_means": {
                    "type": "string",
                    "description": "Optional: what counts as a yes answer",
                },
                "no_means": {
                    "type": "string",
                    "description": "Optional: what counts as a no answer",
                },
                "model": MODEL_SCHEMA,
            },
        },
    },
    {
        "name": "jev_classify",
        "title": "Jev: Classify",
        "description": (
            "Let Jev pick exactly one label from a fixed set. Returns the "
            "chosen label, its confidence and the probability of every label. "
            "Use for routing and triage. Include a catch-all label such as "
            "'other' when no option may fit."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["state", "options"],
            "properties": {
                "state": STATE_SCHEMA,
                "question": {
                    "type": "string",
                    "description": "What to decide, e.g. 'Which team owns this?'",
                },
                "options": {
                    "anyOf": [
                        {
                            "type": "object",
                            "minProperties": 2,
                            "additionalProperties": {
                                "type": ["string", "null"],
                            },
                        },
                        {
                            "type": "array",
                            "minItems": 2,
                            "items": {"type": "string"},
                        },
                    ],
                    "description": (
                        "Labels to choose from: an object mapping label to a "
                        "description (or null), or a plain list of labels"
                    ),
                },
                "model": MODEL_SCHEMA,
            },
        },
    },
    {
        "name": "jev_score",
        "title": "Jev: Score",
        "description": (
            "Rate the state on an ordered rubric. levels[0] is score 0, "
            "levels[1] is score 1, and so on. Returns the expected score "
            "(may fall between levels), its confidence, the legend and the "
            "probability per level."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["state", "levels"],
            "properties": {
                "state": STATE_SCHEMA,
                "question": {
                    "type": "string",
                    "description": "What to rate, e.g. 'How risky is this change?'",
                },
                "levels": {
                    "type": "array",
                    "minItems": 2,
                    "items": {"type": "string"},
                    "description": "Ordered rubric, lowest level first",
                },
                "model": MODEL_SCHEMA,
            },
        },
    },
    {
        "name": "jev_ask",
        "title": "Jev: Batched Questions",
        "description": (
            "Ask several questions about the same state in one call (billed "
            "once for the input). Each question is {type: 'noul'|'choice'|"
            "'score', instructions?, criteria?}: noul criteria is optional "
            "{true, false}; choice criteria maps label to description; score "
            "criteria is an ordered list of level descriptions."
        ),
        "inputSchema": {
            "type": "object",
            "required": ["state", "questions"],
            "properties": {
                "state": STATE_SCHEMA,
                "questions": {
                    "type": "object",
                    "minProperties": 1,
                    "description": "Questions keyed by the name of their answer",
                    "additionalProperties": {
                        "type": "object",
                        "required": ["type"],
                        "properties": {
                            "type": {"enum": ["noul", "choice", "score"]},
                            "instructions": {
                                "type": ["string", "object", "array"],
                            },
                            "criteria": {"type": ["object", "array"]},
                        },
                    },
                },
                "model": MODEL_SCHEMA,
            },
        },
    },
    {
        "name": "jev_list_models",
        "title": "Jev: List Models",
        "description": "List the TypeSafe models available to this API key",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

# Every tool only reads: Jev returns a judgment and changes nothing.  The calls
# reach an external, billed API, hence openWorldHint.
for _tool in TOOLS:
    _tool["annotations"] = {
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }


def get_tool_list() -> list[types.Tool]:
    return [types.Tool(**tool) for tool in TOOLS]


def get_tool_by_name(name: str) -> dict | None:
    for tool in TOOLS:
        if tool["name"] == name:
            return tool
    return None


# ── request building ─────────────────────────────────────────────────


def build_questions(name: str, args: Mapping) -> dict[str, dict]:
    """Translate a tool call into the ``questions`` map of ``/v1/systemone``."""
    question = args.get("question")

    if name == "jev_check":
        q: dict = {"type": "noul", "instructions": question}
        criteria = {
            key: args[arg]
            for key, arg in (("true", "yes_means"), ("false", "no_means"))
            if args.get(arg)
        }
        if criteria:
            q["criteria"] = criteria
        return {"check": q}

    if name == "jev_classify":
        options = args["options"]
        if isinstance(options, list):
            options = {label: None for label in options}
        q = {"type": "choice", "criteria": dict(options)}
        if question:
            q["instructions"] = question
        return {"classify": q}

    if name == "jev_score":
        q = {"type": "score", "criteria": list(args["levels"])}
        if question:
            q["instructions"] = question
        return {"score": q}

    if name == "jev_ask":
        return {key: dict(value) for key, value in args["questions"].items()}

    raise ValueError(f"Tool {name} does not ask questions")


# ── response shaping ─────────────────────────────────────────────────


def shape_answer(answer: Mapping, min_confidence: float) -> dict:
    """Add an explicit answer/confidence/needs_review to one raw answer."""
    kind = answer["type"]
    if kind == "noul":
        p_yes = answer["noul"]
        confidence = max(p_yes, 1 - p_yes)
        shaped = {
            "type": "noul",
            "answer": "yes" if p_yes >= 0.5 else "no",
            "p_yes": p_yes,
            "confidence": confidence,
        }
    else:
        shaped = dict(answer)
        confidence = answer["confidence"]
    shaped["needs_review"] = confidence < min_confidence
    return shaped


def shape_response(name: str, raw: Mapping, min_confidence: float) -> dict:
    """Turn a raw ``/v1/systemone`` response into the tool's structured result."""
    answers = {
        key: shape_answer(value, min_confidence)
        for key, value in raw.get("answers", {}).items()
    }
    meta = {"model": raw.get("model"), "usage": raw.get("usage")}

    if name == "jev_ask":
        review = [key for key, value in answers.items() if value["needs_review"]]
        return {"answers": answers, "needs_review": review, **meta}

    # Single-question tools return their one answer flat.
    (answer,) = answers.values()
    answer.pop("type")
    return {**answer, **meta}
