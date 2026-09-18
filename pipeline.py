"""Backwards-compatible shim. Use :mod:`argus.pipeline`."""

import asyncio

from argus.llm import get_llm
from argus.pipeline import run_pipeline, run_pipeline_collected


def run_research_pipeline(topic: str, llm) -> dict:
    """Synchronous wrapper kept for the legacy Streamlit app and CLI use."""
    result = asyncio.run(run_pipeline_collected(topic, llm))
    return {**result, "feedback": result.get("critic", "")}


__all__ = ["run_research_pipeline", "run_pipeline", "run_pipeline_collected", "get_llm"]
