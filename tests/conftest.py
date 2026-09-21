"""Shared fixtures.

The pipeline is exercised against a stub chat model and stubbed network calls, so
the suite runs offline, deterministically, and without spending API credits.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from typing import Any

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult

os.environ.setdefault("TAVILY_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")

from argus.tools import SearchResult

CRITIQUE = """Overall Score: 7.5/10

Category Scores:
- Factual Accuracy: 8/10
- Depth of Analysis: 7/10
- Structure & Clarity: 9/10
- Use of Sources: 6/10
- Completeness: 7/10
- Professional Quality: 8/10

One-Line Verdict: Well organised but thinly sourced.

Recommendation: NEEDS REVISION - needs primary sources.
"""

FACT_CHECK = "Fact Check Score: 7/10\nVerdict: MOSTLY RELIABLE\n\nVerified Claims:\n- None found"
CREDIBILITY = (
    "Overall Quality: 8/10\nVerdict: RELIABLE\n\n"
    "Sources:\n- example.com - Score: 8/10 - Established outlet."
)
FOLLOWUPS = "\n".join(
    f"{i}. A specific follow-up question number {i} worth researching?" for i in range(1, 6)
)
REPORT = "## Executive Summary\nA synthesised report body.\n\n## Sources\n- [Example](https://example.com/a)"


class FakeChatModel(BaseChatModel):
    """Returns a canned response chosen by which prompt it was handed."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    @staticmethod
    def _respond(messages: list[BaseMessage]) -> str:
        blob = " ".join(str(m.content) for m in messages).lower()
        if "fact-check" in blob or "fact check" in blob:
            return FACT_CHECK
        if "credibility" in blob:
            return CREDIBILITY
        if "follow-up research questions" in blob:
            return FOLLOWUPS
        if "evaluate this research report" in blob:
            return CRITIQUE
        if "write a research report" in blob:
            return REPORT
        return "Found several relevant sources."

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return ChatResult(
            generations=[ChatGeneration(message=AIMessage(content=self._respond(messages)))]
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        from langchain_core.messages import AIMessageChunk

        for word in self._respond(messages).split(" "):
            yield ChatGenerationChunk(message=AIMessageChunk(content=word + " "))


@pytest.fixture
def fake_llm() -> FakeChatModel:
    return FakeChatModel()


@pytest.fixture
def fake_sources() -> list[SearchResult]:
    return [
        SearchResult(
            title="Rare earth supply chains",
            url="https://example.com/a",
            snippet="Refining is concentrated.",
            score=0.9,
            domain="example.com",
        ),
        SearchResult(
            title="Mineral policy review",
            url="https://example.org/b",
            snippet="Policy responses vary.",
            score=0.8,
            domain="example.org",
        ),
    ]


@pytest.fixture
def fake_search(monkeypatch, fake_sources):
    """Replace the search agent and the direct search with deterministic stubs."""

    class StubAgent:
        def invoke(self, _payload: dict) -> dict:
            tool_output = "\n-----\n".join(
                f"Title: {s.title}\nURL: {s.url}\nSnippet: {s.snippet}" for s in fake_sources
            )
            return {
                "messages": [
                    ToolMessage(content=tool_output, tool_call_id="1"),
                    AIMessage(content="Found two strong sources."),
                ]
            }

    monkeypatch.setattr("argus.pipeline.create_agent", lambda **_k: StubAgent())
    monkeypatch.setattr("argus.pipeline.search_web", lambda *_a, **_k: fake_sources)
    return fake_sources


@pytest.fixture
def fake_fetch(monkeypatch):
    def _fetch(url: str) -> dict:
        if "example.org" in url:
            raise ValueError("403 Forbidden")
        return {
            "url": url,
            "title": "Rare earth supply chains",
            "text": "Refining capacity is concentrated in a small number of countries.",
            "chars": 64,
            "truncated": False,
        }

    monkeypatch.setattr("argus.pipeline.fetch_page", _fetch)
    return _fetch
