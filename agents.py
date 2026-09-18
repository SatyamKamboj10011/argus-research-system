"""Backwards-compatible shim. Use :mod:`argus.llm` and :mod:`argus.prompts`."""

from langchain.agents import create_agent

from argus.llm import get_llm
from argus.prompts import (
    CREDIBILITY_PROMPT,
    CRITIC_PROMPT,
    FACT_CHECK_PROMPT,
    FOLLOWUP_PROMPT,
    WRITER_PROMPT,
    build_chain,
)
from argus.tools import scrape_url, web_search


def build_search_agent(llm):
    return create_agent(model=llm, tools=[web_search])


def build_read_agent(llm):
    return create_agent(model=llm, tools=[scrape_url])


def build_writer_chain(llm):
    return build_chain(WRITER_PROMPT, llm)


def build_critic_chain(llm):
    return build_chain(CRITIC_PROMPT, llm)


def build_fact_checker_chain(llm):
    return build_chain(FACT_CHECK_PROMPT, llm)


def build_followup_chain(llm):
    return build_chain(FOLLOWUP_PROMPT, llm)


def build_credibility_chain(llm):
    return build_chain(CREDIBILITY_PROMPT, llm)


__all__ = [
    "get_llm",
    "build_search_agent",
    "build_read_agent",
    "build_writer_chain",
    "build_critic_chain",
    "build_fact_checker_chain",
    "build_followup_chain",
    "build_credibility_chain",
]
