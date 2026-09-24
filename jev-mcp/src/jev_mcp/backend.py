"""
Backends that answer ``/v1/systemone`` requests.

``TypeSafeBackend`` uses the official ``typesafe-sdk`` (retries, typed errors,
``TYPESAFE_*`` environment variables).  ``MockBackend`` returns deterministic
answers in the same wire format so ``--mode mock`` works without an API key.
"""

import json
from collections.abc import Mapping
from typing import Any, Protocol

from typesafe_sdk import AsyncTypeSafeClient, TypeSafeError


class Backend(Protocol):
    async def system_one(
        self, state: Any, questions: Mapping[str, dict], model: str | None,
    ) -> dict: ...

    async def list_models(self) -> dict: ...

    async def aclose(self) -> None: ...


class JevError(Exception):
    """A failed Jev call, with a message fit to show the agent."""


class TypeSafeBackend:
    """Calls the TypeSafe API through the official SDK.

    The client is created on first use, so the server starts (and lists its
    tools) even when ``TYPESAFE_API_KEY`` is not set yet.
    """

    def __init__(self, **client_options: Any) -> None:
        self._options = client_options
        self._client: AsyncTypeSafeClient | None = None

    def _get_client(self) -> AsyncTypeSafeClient:
        if self._client is None:
            try:
                self._client = AsyncTypeSafeClient(**self._options)
            except TypeSafeError as exc:
                raise JevError(
                    f"{exc} Set TYPESAFE_API_KEY in the environment Claude Code "
                    "runs in."
                ) from exc
        return self._client

    async def system_one(
        self, state: Any, questions: Mapping[str, dict], model: str | None,
    ) -> dict:
        client = self._get_client()
        try:
            response = await client.system_one(state, questions, model=model)
        except TypeSafeError as exc:
            raise JevError(str(exc)) from exc
        return response.model_dump(mode="json")

    async def list_models(self) -> dict:
        client = self._get_client()
        try:
            response = await client.models.list()
        except TypeSafeError as exc:
            raise JevError(str(exc)) from exc
        return response.model_dump(mode="json")

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


class MockBackend:
    """Deterministic fake answers in the ``/v1/systemone`` wire format."""

    MODEL = "jev-mock"

    async def system_one(
        self, state: Any, questions: Mapping[str, dict], model: str | None,
    ) -> dict:
        if not questions:
            raise JevError("At least one question is required.")
        answers = {
            name: _mock_answer(name, question)
            for name, question in questions.items()
        }
        input_tokens = len(json.dumps([state, questions], default=str)) // 4
        return {
            "model": model or self.MODEL,
            "usage": {"input_tokens": input_tokens, "output_tokens": len(answers)},
            "answers": answers,
        }

    async def list_models(self) -> dict:
        return {
            "models": [
                {
                    "name": self.MODEL,
                    "description": "Mock model (no API calls)",
                    "release_date": "2026-01-01",
                },
            ],
        }

    async def aclose(self) -> None:
        pass


def _mock_answer(name: str, question: Mapping) -> dict:
    kind = question.get("type")
    criteria = question.get("criteria")

    if kind == "noul":
        return {"type": "noul", "noul": 0.9}

    if kind == "choice":
        if not isinstance(criteria, Mapping) or not criteria:
            raise JevError(f'Choice question "{name}" requires criteria.')
        labels = list(criteria)
        rest = 0.3 / (len(labels) - 1) if len(labels) > 1 else 0.0
        probabilities = {label: rest for label in labels}
        probabilities[labels[0]] = 1.0 if len(labels) == 1 else 0.7
        return {
            "type": "choice",
            "choice": labels[0],
            "confidence": probabilities[labels[0]],
            "probabilities": probabilities,
        }

    if kind == "score":
        if not isinstance(criteria, list) or not criteria:
            raise JevError(
                f'Score question "{name}" has no criteria; '
                "at least one score is required."
            )
        top = len(criteria) // 2
        rest = 0.2 / (len(criteria) - 1) if len(criteria) > 1 else 0.0
        probabilities = {
            str(i): (0.8 if len(criteria) > 1 else 1.0) if i == top else rest
            for i in range(len(criteria))
        }
        return {
            "type": "score",
            "score": sum(i * p for i, p in enumerate(probabilities.values())),
            "confidence": probabilities[str(top)],
            "legend": {str(i): text for i, text in enumerate(criteria)},
            "probabilities": probabilities,
        }

    raise JevError(f'Question "{name}" has unknown type {kind!r}.')
