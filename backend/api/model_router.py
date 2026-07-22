from typing import Any

from api.ollama_client import build_ollama_grounded_answer
from api.gemini_client import build_gemini_grounded_answer
from api.groq_client import build_groq_grounded_answer
from uploads.config import DEFAULT_LLM_PROVIDER

PROVIDERS = {
    "ollama": build_ollama_grounded_answer,
    "gemini": build_gemini_grounded_answer,
    "groq": build_groq_grounded_answer,
}

# Existing clients or stored browser state may still send ``openai`` after the
# migration. Route that legacy value to Groq without exposing it in the UI.
PROVIDER_ALIASES = {
    "openai": "groq",
}


def resolve_provider(model: str | None = None) -> str:
    provider = (model or DEFAULT_LLM_PROVIDER).lower().strip()
    provider = PROVIDER_ALIASES.get(provider, provider)

    if provider not in PROVIDERS:
        print(f"[MODEL_ROUTER] unknown provider '{provider}', falling back to ollama")
        return "ollama"

    return provider


def build_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
    model: str | None = None,
    evaluation_mode: bool = False,
) -> str:
    """Route one grounded-generation request to the selected LLM provider."""
    provider = resolve_provider(model)
    print(f"[MODEL_ROUTER] provider={provider}")

    return PROVIDERS[provider](
        question,
        chunks,
        language=language,
        evaluation_mode=evaluation_mode,
    )
