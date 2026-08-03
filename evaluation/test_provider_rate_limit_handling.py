"""Focused regression checks for provider quota and judge retry handling."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.provider_errors import ProviderAPIError
from evaluation.generation import (
    build_generation_dataset,
    evaluate_generation,
    run_three_model_evaluation,
)


class FakeHTTPError(RuntimeError):
    def __init__(self, response: "FakeResponse") -> None:
        super().__init__(f"{response.status_code} response")
        self.response = response


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        *,
        payload: dict[str, Any] | None = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text
        self.headers = headers or {}

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise FakeHTTPError(self)


def test_gemini_daily_quota_is_structured() -> None:
    error = RuntimeError(
        "429 RESOURCE_EXHAUSTED: quota metric "
        "GenerateRequestsPerDayPerProjectPerModel-FreeTier; "
        "retryDelay: '42s'"
    )
    structured = ProviderAPIError.from_exception("gemini", error)
    assert structured.upstream_status == 429
    assert structured.error_code == "RESOURCE_EXHAUSTED"
    assert structured.quota_scope == "daily"
    assert structured.retry_after_seconds == 42.0
    assert structured.http_status == 429


def test_groq_retry_after_is_preserved() -> None:
    response = FakeResponse(
        429,
        text='{"error":{"message":"rate limit reached per minute"}}',
        headers={"Retry-After": "7.5"},
    )
    structured = ProviderAPIError.from_http_response("groq", response)
    assert structured.quota_scope == "minute"
    assert structured.retry_after_seconds == 7.5
    assert structured.as_detail()["provider"] == "groq"


def test_evaluation_client_recognises_backend_429() -> None:
    response = FakeResponse(
        429,
        payload={
            "detail": {
                "provider": "gemini",
                "message": "Gemini daily API quota is exhausted.",
                "quota_scope": "daily",
                "retry_after_seconds": 15,
            }
        },
    )

    class FakeRequests:
        @staticmethod
        def post(*_args: Any, **_kwargs: Any) -> FakeResponse:
            return response

    original_requests_module = build_generation_dataset.requests_module
    original_token = build_generation_dataset._AUTH_TOKEN
    try:
        build_generation_dataset.requests_module = lambda: FakeRequests
        build_generation_dataset._AUTH_TOKEN = "test-token"
        try:
            build_generation_dataset.post_json("http://test/chat", {"model": "gemini"})
        except build_generation_dataset.ProviderRateLimitError as error:
            assert error.provider == "gemini"
            assert error.quota_scope == "daily"
            assert error.retry_after_seconds == 15.0
        else:
            raise AssertionError("HTTP 429 must become ProviderRateLimitError")
    finally:
        build_generation_dataset.requests_module = original_requests_module
        build_generation_dataset._AUTH_TOKEN = original_token


def test_judge_429_does_not_trigger_format_fallback_or_more_rows() -> None:
    response = FakeResponse(429, headers={"Retry-After": "999"})

    class FakeRequests:
        calls = 0

        @classmethod
        def post(cls, *_args: Any, **_kwargs: Any) -> FakeResponse:
            cls.calls += 1
            return response

    original_requests = evaluate_generation.requests
    original_retries = evaluate_generation.JUDGE_MAX_RETRIES
    original_circuit = evaluate_generation._JUDGE_CIRCUIT_ERROR
    try:
        evaluate_generation.requests = FakeRequests
        evaluate_generation.JUDGE_MAX_RETRIES = 0
        evaluate_generation._JUDGE_CIRCUIT_ERROR = ""
        first = evaluate_generation.llm_judge(
            question="Question",
            expected_answer="Expected",
            context="Context",
            answer="Answer",
            answerable=True,
        )
        second = evaluate_generation.llm_judge(
            question="Question 2",
            expected_answer="Expected",
            context="Context",
            answer="Answer",
            answerable=True,
        )
        assert FakeRequests.calls == 1
        assert first["judge_error"]
        assert "rate limit" in second["judge_error"].casefold()
    finally:
        evaluate_generation.requests = original_requests
        evaluate_generation.JUDGE_MAX_RETRIES = original_retries
        evaluate_generation._JUDGE_CIRCUIT_ERROR = original_circuit


def test_pause_checkpoint_keeps_later_successful_resume_rows() -> None:
    rows = [
        {"id": "QA-001", "question": "One", "language": "EN"},
        {"id": "QA-002", "question": "Two", "language": "EN"},
        {"id": "QA-003", "question": "Three", "language": "EN"},
    ]
    successful_rows = [
        {
            "id": qid,
            "model": "gemini",
            "evaluation_context_mode": build_generation_dataset.CONTEXT_MODE,
            "pipeline_failed": False,
            "generation_failed": False,
        }
        for qid in ("QA-001", "QA-003")
    ]

    original_preflight = build_generation_dataset.preflight
    original_post_json = build_generation_dataset.post_json
    original_key = os.environ.get("GEMINI_API_KEY")
    try:
        os.environ["GEMINI_API_KEY"] = "test-key"
        build_generation_dataset.preflight = lambda: None

        def blocked_post(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
            raise build_generation_dataset.ProviderRateLimitError(
                "Gemini daily API quota is exhausted.",
                provider="gemini",
                quota_scope="daily",
            )

        build_generation_dataset.post_json = blocked_post
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "answers.json"
            output.write_text(json.dumps(successful_rows), encoding="utf-8")
            try:
                build_generation_dataset.build_dataset(
                    rows,
                    output,
                    model="gemini",
                    top_k=5,
                    resume=True,
                    retries=2,
                )
            except build_generation_dataset.ProviderEvaluationPaused:
                saved = json.loads(output.read_text(encoding="utf-8"))
                assert [item["id"] for item in saved] == ["QA-001", "QA-003"]
            else:
                raise AssertionError("Daily quota must pause the provider")
    finally:
        build_generation_dataset.preflight = original_preflight
        build_generation_dataset.post_json = original_post_json
        if original_key is None:
            os.environ.pop("GEMINI_API_KEY", None)
        else:
            os.environ["GEMINI_API_KEY"] = original_key


def test_three_model_runner_continues_after_one_provider_pauses() -> None:
    commands: list[list[str]] = []
    original_run = run_three_model_evaluation.run
    original_argv = sys.argv

    def fake_run(
        command: list[str],
        *,
        allowed_return_codes: tuple[int, ...] = (0,),
    ) -> int:
        commands.append(command)
        if (
            Path(command[1]).name == "build_generation_dataset.py"
            and "--model" in command
            and command[command.index("--model") + 1] == "gemini"
        ):
            assert 75 in allowed_return_codes
            return 75
        return 0

    try:
        with tempfile.TemporaryDirectory() as directory:
            sys.argv = [
                "run_three_model_evaluation.py",
                "--models",
                "gemini",
                "groq",
                "--skip-llm-judge",
                "--output-dir",
                directory,
            ]
            run_three_model_evaluation.run = fake_run
            try:
                run_three_model_evaluation.main()
            except SystemExit as error:
                assert error.code == 75
            else:
                raise AssertionError("A paused provider must produce exit code 75")
    finally:
        run_three_model_evaluation.run = original_run
        sys.argv = original_argv

    evaluated_models = [
        command[command.index("--model") + 1]
        for command in commands
        if Path(command[1]).name == "build_generation_dataset.py"
        and "--model" in command
    ]
    assert evaluated_models == ["gemini", "groq"]
    assert any(
        Path(command[1]).name == "evaluate_generation.py"
        and command[command.index("--output-prefix") + 1] == "groq"
        for command in commands
    )


def main() -> None:
    test_gemini_daily_quota_is_structured()
    test_groq_retry_after_is_preserved()
    test_evaluation_client_recognises_backend_429()
    test_judge_429_does_not_trigger_format_fallback_or_more_rows()
    test_pause_checkpoint_keeps_later_successful_resume_rows()
    test_three_model_runner_continues_after_one_provider_pauses()
    print("Provider rate-limit regression tests passed.")


if __name__ == "__main__":
    main()
