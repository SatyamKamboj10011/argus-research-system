"""LLM provider registry.

A single declarative catalogue of every model ARGUS can drive. The frontend reads
this over ``GET /api/models`` rather than hard-coding a list, so the two can never
drift apart.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from argus.config import settings

logger = logging.getLogger(__name__)


class ModelNotFoundError(ValueError):
    """The requested model id is not in the registry."""


class MissingCredentialsError(ValueError):
    """No API key is available for the requested provider."""


@dataclass(frozen=True)
class ModelSpec:
    id: str
    label: str
    provider: str
    model_name: str
    description: str
    context_window: int
    supports_tools: bool = True
    reasoning: bool = False
    """Reasoning models bill their hidden chain of thought against the same
    token-per-minute budget, so ARGUS asks them to keep it short."""

    is_local: bool = False
    recommended: bool = False
    aliases: tuple[str, ...] = field(default_factory=tuple)

    @property
    def settings_key_attr(self) -> str | None:
        return {
            "groq": "groq_api_key",
            "cerebras": "cerebras_api_key",
            "google": "google_api_key",
        }.get(self.provider)

    def server_key(self) -> str | None:
        attr = self.settings_key_attr
        return getattr(settings, attr, None) if attr else None

    @property
    def key_env_var(self) -> str | None:
        attr = self.settings_key_attr
        return attr.upper() if attr else None


REGISTRY: tuple[ModelSpec, ...] = (
    ModelSpec(
        id="groq-gpt-oss-120b",
        label="GPT-OSS 120B",
        provider="groq",
        model_name="openai/gpt-oss-120b",
        description="Best overall quality. Strong tool use and long-form synthesis.",
        context_window=131_072,
        reasoning=True,
        recommended=True,
        # The Llama 3.x models this project originally shipped were retired by Groq.
        # Their labels are kept as aliases so old links and clients still resolve.
        aliases=(
            "Groq — Llama 3.3 70B",
            "Groq - Llama 3.3 70B",
            "groq-llama-3.3-70b",
        ),
    ),
    ModelSpec(
        id="groq-gpt-oss-20b",
        label="GPT-OSS 20B",
        provider="groq",
        model_name="openai/gpt-oss-20b",
        description="Fastest option. Shallower analysis, good for quick scans.",
        context_window=131_072,
        reasoning=True,
        aliases=("Groq — Llama 3.1 8B", "Groq - Llama 3.1 8B", "groq-llama-3.1-8b"),
    ),
    ModelSpec(
        id="groq-qwen3-27b",
        label="Qwen 3.8 27B",
        provider="groq",
        model_name="qwen/qwen3.8-27b",
        description="Balanced reasoning model. A useful second opinion on the same topic.",
        context_window=131_042,
        reasoning=True,
    ),
    ModelSpec(
        id="google-gemini-2.5-flash",
        label="Gemini 2.5 Flash",
        provider="google",
        model_name="gemini-2.5-flash",
        description="Very large context and fast. Good at structured report formats.",
        context_window=1_000_000,
        aliases=("Gemini — 2.0 Flash", "Gemini - 2.0 Flash", "google-gemini-2.0-flash"),
    ),
    ModelSpec(
        id="cerebras-llama-3.3-70b",
        label="Llama 3.3 70B (Cerebras)",
        provider="cerebras",
        model_name="llama-3.3-70b",
        description="Very high throughput inference on Cerebras wafer-scale hardware.",
        context_window=65_536,
        aliases=("Cerebras — Llama 3.1 8B", "Cerebras - Llama 3.1 8B"),
    ),
    ModelSpec(
        id="ollama-llama3",
        label="Llama 3 (local)",
        provider="ollama",
        model_name="llama3:latest",
        description="Runs entirely on your machine via Ollama. No API key, no data leaves.",
        context_window=8_192,
        is_local=True,
        aliases=("Local — Ollama Llama 3", "Local - Ollama Llama 3"),
    ),
    ModelSpec(
        id="ollama-qwen2.5-7b",
        label="Qwen 2.5 7B (local)",
        provider="ollama",
        model_name="qwen2.5:7b",
        description="Local model with solid tool-calling for its size.",
        context_window=32_768,
        is_local=True,
        aliases=("Local — Qwen 2.5 7B", "Local - Qwen 2.5 7B"),
    ),
)

_BY_ID: dict[str, ModelSpec] = {}
for _spec in REGISTRY:
    _BY_ID[_spec.id] = _spec
    for _alias in _spec.aliases:
        _BY_ID[_alias] = _spec
    _BY_ID[_spec.label] = _spec


def resolve_spec(model_id: str) -> ModelSpec:
    """Look a model up by id, label, or legacy alias."""
    spec = _BY_ID.get(model_id) or _BY_ID.get(model_id.strip())
    if spec is None:
        raise ModelNotFoundError(
            f"Unknown model {model_id!r}. Available: {', '.join(s.id for s in REGISTRY)}"
        )
    return spec


def list_models() -> list[dict[str, Any]]:
    """Public model catalogue. Never leaks key material — only whether one exists."""
    out: list[dict[str, Any]] = []
    for spec in REGISTRY:
        if spec.is_local and not settings.allow_local_models:
            continue
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "provider": spec.provider,
                "description": spec.description,
                "context_window": spec.context_window,
                "is_local": spec.is_local,
                "recommended": spec.recommended,
                "ready": spec.is_local or bool(spec.server_key()),
                "key_env_var": spec.key_env_var,
            }
        )
    return out


def _build_groq(spec: ModelSpec, key: str) -> Any:
    from langchain_groq import ChatGroq

    extra: dict[str, Any] = {"reasoning_effort": "low"} if spec.reasoning else {}
    return ChatGroq(model=spec.model_name, api_key=key, temperature=0.2, max_retries=2, **extra)


def _build_google(spec: ModelSpec, key: str) -> Any:
    from langchain_google_genai import ChatGoogleGenerativeAI

    return ChatGoogleGenerativeAI(model=spec.model_name, google_api_key=key, temperature=0.2)


def _build_cerebras(spec: ModelSpec, key: str) -> Any:
    from langchain_cerebras import ChatCerebras

    return ChatCerebras(model=spec.model_name, api_key=key, temperature=0.2)


def _build_ollama(spec: ModelSpec, _key: str) -> Any:
    from langchain_ollama import ChatOllama

    return ChatOllama(model=spec.model_name, temperature=0.2, base_url=settings.ollama_base_url)


_BUILDERS: dict[str, Callable[[ModelSpec, str], Any]] = {
    "groq": _build_groq,
    "google": _build_google,
    "cerebras": _build_cerebras,
    "ollama": _build_ollama,
}


def get_llm(model_id: str, api_key: str | None = None) -> Any:
    """Instantiate a chat model.

    Key resolution order: caller-supplied key, then the server's own key for that
    specific provider. The previous implementation passed ``api_key=None`` straight
    through, which made the OpenAI-compatible providers silently fall back to
    ``OPENAI_API_KEY`` and fail.
    """
    spec = resolve_spec(model_id)

    if spec.is_local and not settings.allow_local_models:
        raise MissingCredentialsError(
            f"{spec.label} is disabled on this server. Run ARGUS locally with "
            "ALLOW_LOCAL_MODELS=true and an Ollama instance to use local models."
        )

    key = (api_key or "").strip() or spec.server_key()
    if not key and not spec.is_local:
        raise MissingCredentialsError(
            f"No API key available for {spec.label}. Provide your own key, or set "
            f"{spec.key_env_var} on the server."
        )

    logger.info("Initialising %s via %s", spec.model_name, spec.provider)
    return _BUILDERS[spec.provider](spec, key or "")


DEFAULT_MODEL = "groq-gpt-oss-120b"
