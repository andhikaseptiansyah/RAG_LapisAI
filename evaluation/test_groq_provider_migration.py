from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api import groq_client, model_router


class FakeResponse:
    status_code = 200
    headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"choices": [{"message": {"content": "Grounded Groq answer"}}]}


def main() -> None:
    assert set(model_router.PROVIDERS) == {"ollama", "gemini", "groq"}
    assert model_router.resolve_provider("groq") == "groq"
    assert model_router.resolve_provider("openai") == "groq"
    assert model_router.resolve_provider("unknown-provider") == "ollama"

    captured: dict[str, Any] = {}
    original_post = groq_client.requests.post
    original_api_key = groq_client.GROQ_API_KEY
    original_base_url = groq_client.GROQ_BASE_URL
    original_model = groq_client.GROQ_MODEL
    original_retries = groq_client.GROQ_MAX_RETRIES

    def fake_post(url: str, **kwargs: Any) -> FakeResponse:
        captured["url"] = url
        captured.update(kwargs)
        return FakeResponse()

    try:
        groq_client.requests.post = fake_post
        groq_client.GROQ_API_KEY = "test-key"
        groq_client.GROQ_BASE_URL = "https://api.groq.com/openai/v1"
        groq_client.GROQ_MODEL = "llama-3.3-70b-versatile"
        groq_client.GROQ_MAX_RETRIES = 0

        answer = groq_client._groq_chat("system", "user")
        assert answer == "Grounded Groq answer"
        assert captured["url"] == "https://api.groq.com/openai/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer test-key"
        assert captured["json"]["model"] == "llama-3.3-70b-versatile"
        assert captured["json"]["max_completion_tokens"] == 640
        assert captured["json"]["messages"][1]["content"] == "user"
    finally:
        groq_client.requests.post = original_post
        groq_client.GROQ_API_KEY = original_api_key
        groq_client.GROQ_BASE_URL = original_base_url
        groq_client.GROQ_MODEL = original_model
        groq_client.GROQ_MAX_RETRIES = original_retries

    print("Groq provider migration tests passed.")


if __name__ == "__main__":
    main()
