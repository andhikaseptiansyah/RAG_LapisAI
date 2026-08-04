"""Regression tests for resilient and auditable semantic judging."""

from __future__ import annotations

import tempfile
import unittest
import sys
from pathlib import Path
from typing import Any

from evaluation.generation import evaluate_generation, run_three_model_evaluation


class FakeResponse:
    def __init__(self, payload: dict[str, Any], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers: dict[str, str] = {}

    def json(self) -> dict[str, Any]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = RuntimeError(f"HTTP {self.status_code}")
            error.response = self  # type: ignore[attr-defined]
            raise error


class JudgeResilienceTests(unittest.TestCase):
    def test_payload_requires_all_metrics(self) -> None:
        with self.assertRaises(evaluate_generation.JudgePayloadError):
            evaluate_generation.validate_judge_payload(
                {"faithfulness": 5, "answer_relevance": 5}
            )
        with self.assertRaises(evaluate_generation.JudgePayloadError):
            evaluate_generation.validate_judge_payload(
                {
                    "faithfulness": 6,
                    "answer_relevance": 5,
                    "is_hallucination": False,
                }
            )

    def test_read_timeout_is_retried(self) -> None:
        class FakeTimeout(RuntimeError):
            pass

        class FakeConnectionError(RuntimeError):
            pass

        class FakeRequests:
            class exceptions:
                Timeout = FakeTimeout
                ConnectionError = FakeConnectionError

            calls = 0

            @classmethod
            def post(cls, *_args: Any, **_kwargs: Any) -> FakeResponse:
                cls.calls += 1
                if cls.calls == 1:
                    raise FakeTimeout("read timed out")
                return FakeResponse({})

        original_requests = evaluate_generation.requests
        original_retries = evaluate_generation.JUDGE_MAX_RETRIES
        original_sleep = evaluate_generation.time.sleep
        try:
            evaluate_generation.requests = FakeRequests
            evaluate_generation.JUDGE_MAX_RETRIES = 1
            evaluate_generation.time.sleep = lambda _seconds: None
            response = evaluate_generation._post_judge_request(
                "http://judge.test/chat/completions",
                {},
                {},
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(FakeRequests.calls, 2)
        finally:
            evaluate_generation.requests = original_requests
            evaluate_generation.JUDGE_MAX_RETRIES = original_retries
            evaluate_generation.time.sleep = original_sleep

    def test_invalid_payload_is_retried_and_not_silently_accepted(self) -> None:
        invalid = {
            "choices": [{"message": {"content": '{"faithfulness":5,"answer_relevance":5}'}}]
        }
        valid = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"faithfulness":5,"answer_relevance":4,'
                            '"is_hallucination":false,"reason":"grounded"}'
                        )
                    }
                }
            ]
        }

        class FakeRequests:
            calls = 0

            @classmethod
            def post(cls, *_args: Any, **_kwargs: Any) -> FakeResponse:
                cls.calls += 1
                return FakeResponse(invalid if cls.calls == 1 else valid)

        original_requests = evaluate_generation.requests
        original_http_retries = evaluate_generation.JUDGE_MAX_RETRIES
        original_format_retries = evaluate_generation.JUDGE_MAX_FORMAT_RETRIES
        original_circuit = evaluate_generation._JUDGE_CIRCUIT_ERROR
        try:
            evaluate_generation.requests = FakeRequests
            evaluate_generation.JUDGE_MAX_RETRIES = 0
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = 1
            evaluate_generation._JUDGE_CIRCUIT_ERROR = ""
            result = evaluate_generation.llm_judge(
                question="Question",
                expected_answer="Expected",
                context="Context",
                answer="Answer",
                answerable=True,
            )
            self.assertEqual(result["faithfulness"], 5.0)
            self.assertEqual(result["answer_relevance"], 4.0)
            self.assertIs(result["is_hallucination"], False)
            self.assertEqual(result["judge_error"], "")
            self.assertEqual(FakeRequests.calls, 2)
        finally:
            evaluate_generation.requests = original_requests
            evaluate_generation.JUDGE_MAX_RETRIES = original_http_retries
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = original_format_retries
            evaluate_generation._JUDGE_CIRCUIT_ERROR = original_circuit

    def test_qwen3_judge_disables_thinking_with_schema_fallback(self) -> None:
        valid = {
            "choices": [
                {
                    "message": {
                        "content": (
                            '{"faithfulness":5,"answer_relevance":4,'
                            '"is_hallucination":false,"reason":"grounded"}'
                        )
                    }
                }
            ]
        }

        class FakeRequests:
            request_keys: list[set[str]] = []
            system_messages: list[str] = []

            @classmethod
            def post(cls, *_args: Any, **kwargs: Any) -> FakeResponse:
                request = kwargs["json"]
                cls.request_keys.append(set(request))
                cls.system_messages.append(request["messages"][0]["content"])
                if len(cls.request_keys) == 1:
                    return FakeResponse({}, status_code=400)
                return FakeResponse(valid)

        original_requests = evaluate_generation.requests
        original_model = evaluate_generation.LLM_MODEL
        original_mode = evaluate_generation.JUDGE_DISABLE_THINKING_MODE
        original_http_retries = evaluate_generation.JUDGE_MAX_RETRIES
        original_format_retries = evaluate_generation.JUDGE_MAX_FORMAT_RETRIES
        original_circuit = evaluate_generation._JUDGE_CIRCUIT_ERROR
        try:
            evaluate_generation.requests = FakeRequests
            evaluate_generation.LLM_MODEL = "qwen3:8b"
            evaluate_generation.JUDGE_DISABLE_THINKING_MODE = "auto"
            evaluate_generation.JUDGE_MAX_RETRIES = 0
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = 0
            evaluate_generation._JUDGE_CIRCUIT_ERROR = ""
            result = evaluate_generation.llm_judge(
                question="Question",
                expected_answer="Expected",
                context="Context",
                answer="Answer",
                answerable=True,
            )
            self.assertEqual(result["judge_error"], "")
            self.assertIn("reasoning_effort", FakeRequests.request_keys[0])
            self.assertIn("response_format", FakeRequests.request_keys[0])
            self.assertNotIn("reasoning_effort", FakeRequests.request_keys[1])
            self.assertNotIn("response_format", FakeRequests.request_keys[1])
            self.assertTrue(
                all("/no_think" in text for text in FakeRequests.system_messages)
            )
        finally:
            evaluate_generation.requests = original_requests
            evaluate_generation.LLM_MODEL = original_model
            evaluate_generation.JUDGE_DISABLE_THINKING_MODE = original_mode
            evaluate_generation.JUDGE_MAX_RETRIES = original_http_retries
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = original_format_retries
            evaluate_generation._JUDGE_CIRCUIT_ERROR = original_circuit

    def test_empty_judge_content_has_actionable_error(self) -> None:
        empty = {
            "choices": [
                {
                    "finish_reason": "length",
                    "message": {"content": "", "reasoning": "thinking"},
                }
            ]
        }

        class FakeRequests:
            @classmethod
            def post(cls, *_args: Any, **_kwargs: Any) -> FakeResponse:
                return FakeResponse(empty)

        original_requests = evaluate_generation.requests
        original_model = evaluate_generation.LLM_MODEL
        original_mode = evaluate_generation.JUDGE_DISABLE_THINKING_MODE
        original_http_retries = evaluate_generation.JUDGE_MAX_RETRIES
        original_format_retries = evaluate_generation.JUDGE_MAX_FORMAT_RETRIES
        original_circuit = evaluate_generation._JUDGE_CIRCUIT_ERROR
        try:
            evaluate_generation.requests = FakeRequests
            evaluate_generation.LLM_MODEL = "qwen3:8b"
            evaluate_generation.JUDGE_DISABLE_THINKING_MODE = "auto"
            evaluate_generation.JUDGE_MAX_RETRIES = 0
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = 0
            evaluate_generation._JUDGE_CIRCUIT_ERROR = ""
            result = evaluate_generation.llm_judge(
                question="Question",
                expected_answer="Expected",
                context="Context",
                answer="Answer",
                answerable=True,
            )
            self.assertIn("empty assistant content", result["judge_error"])
            self.assertIn("finish_reason=length", result["judge_error"])
            self.assertIn("reasoning_chars=8", result["judge_error"])
        finally:
            evaluate_generation.requests = original_requests
            evaluate_generation.LLM_MODEL = original_model
            evaluate_generation.JUDGE_DISABLE_THINKING_MODE = original_mode
            evaluate_generation.JUDGE_MAX_RETRIES = original_http_retries
            evaluate_generation.JUDGE_MAX_FORMAT_RETRIES = original_format_retries
            evaluate_generation._JUDGE_CIRCUIT_ERROR = original_circuit

    def test_incomplete_row_does_not_count_as_success(self) -> None:
        complete = {
            "Judge Error": "",
            "Faithfulness": 5,
            "Answer Relevance": 4,
            "Hallucination": 0,
        }
        incomplete = {**complete, "Faithfulness": None}
        self.assertTrue(evaluate_generation.has_complete_judge_result(complete))
        self.assertFalse(evaluate_generation.has_complete_judge_result(incomplete))

    def test_resume_requires_matching_inputs(self) -> None:
        item = {"context_fingerprint": "abc123"}
        ground_truth = {
            "question": "Question",
            "expected_answer": "Expected",
            "answerable": True,
        }
        row = {
            "Model Name": "model:v1",
            "Question": "Question",
            "Expected Answer": "Expected",
            "Generated Answer": "Answer",
            "Answerable": "True",
            "Context Fingerprint": "abc123",
            "Faithfulness": "5",
            "Answer Relevance": "4",
            "Hallucination": "0",
            "Judge Reason": "grounded",
            "Judge Error": "",
        }
        reused = evaluate_generation.reusable_judge_result(
            row,
            item=item,
            ground_truth=ground_truth,
            model_name="model:v1",
            generated_answer="Answer",
        )
        self.assertIsNotNone(reused)
        changed = evaluate_generation.reusable_judge_result(
            row,
            item=item,
            ground_truth=ground_truth,
            model_name="model:v1",
            generated_answer="Changed answer",
        )
        self.assertIsNone(changed)

    def test_json_writer_uses_lf_on_every_platform(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "summary.json"
            evaluate_generation.write_json_lf(path, {"line": "one\ntwo"})
            payload = path.read_bytes()
            self.assertNotIn(b"\r\n", payload)
            self.assertTrue(payload.endswith(b"\n"))

    def test_runner_forwards_resume_to_semantic_judge(self) -> None:
        commands: list[list[str]] = []
        original_run = run_three_model_evaluation.run
        original_argv = sys.argv
        try:
            run_three_model_evaluation.run = (
                lambda command, **_kwargs: commands.append(command) or 0
            )
            with tempfile.TemporaryDirectory() as directory:
                sys.argv = [
                    "run_three_model_evaluation.py",
                    "--models",
                    "ollama",
                    "--resume",
                    "--output-dir",
                    directory,
                ]
                run_three_model_evaluation.main()
        finally:
            run_three_model_evaluation.run = original_run
            sys.argv = original_argv

        evaluate_command = next(
            command
            for command in commands
            if Path(command[1]).name == "evaluate_generation.py"
        )
        self.assertIn("--resume-judge", evaluate_command)


if __name__ == "__main__":
    unittest.main()
