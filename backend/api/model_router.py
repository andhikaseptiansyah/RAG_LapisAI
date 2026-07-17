from typing import Any

from api.ollama_client import build_ollama_grounded_answer
from api.gemini_client import build_gemini_grounded_answer
from api.openai_client import build_openai_grounded_answer
from uploads.config import DEFAULT_LLM_PROVIDER

PROVIDERS = {
    "ollama": build_ollama_grounded_answer,
    "gemini": build_gemini_grounded_answer,
    "openai": build_openai_grounded_answer,
}


def build_grounded_answer(
    question: str,
    chunks: list[dict[str, Any]],
    language: str = "ID",
    model: str | None = None,
) -> str:
    """Route to the correct LLM provider based on model parameter."""
    provider = (model or DEFAULT_LLM_PROVIDER).lower().strip()

    if provider not in PROVIDERS:
        print(f"[MODEL_ROUTER] unknown provider '{provider}', falling back to ollama")
        provider = "ollama"

    return PROVIDERS[provider](question, chunks, language=language)
