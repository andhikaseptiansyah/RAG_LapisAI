"""Generate source-locked answers for one LLM provider.

This script supports the bilingual 50-English + 50-Indonesian CSV dataset and
both answerable and deliberately unanswerable questions. Each output row stores
the requested model, response latency, citations, exact generation contexts,
and a context fingerprint for fair cross-model comparison.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

try:
    from .dataset_utils import (
        context_fingerprint,
        dataset_summary,
        load_ground_truth_files,
    )
except ImportError:  # Direct script execution.
    from dataset_utils import (
        context_fingerprint,
        dataset_summary,
        load_ground_truth_files,
    )

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.language import detect_question_language


def detect_language(question: str) -> str:
    """Compatibility helper used by evaluation builders and tests."""
    return detect_question_language(question, fallback="EN")


def load_ground_truth(path: Path) -> list[dict[str, Any]]:
    """Load the legacy three-column official CSV used by older tests/tools."""
    resolved = Path(path).resolve()
    with resolved.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    items: list[dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        items.append({
            "id": f"QA-{index:03d}",
            "question": str(row.get("question") or "").strip(),
            "expected_answer": str(row.get("expected_answer") or "").strip(),
            "answerable": True,
            "language": detect_language(str(row.get("question") or "")),
            "references": [{
                "document": str(row.get("source_document") or "").strip(),
                "page": "",
            }],
            "source_dataset": resolved.name,
        })
    return items


load_dotenv(PROJECT_ROOT / ".env")
EVALUATION_DIR = PROJECT_ROOT / "evaluation"
DEFAULT_DATASETS = [
    EVALUATION_DIR / "datasets" / "qna_english_user.csv",
    EVALUATION_DIR / "datasets" / "qna_indonesia_user.csv",
]
CHAT_URL = os.getenv(
    "LAPISAI_EVALUATION_CHAT_URL",
    "http://localhost:8000/api/admin/evaluation/chat",
)
HEALTH_URL = os.getenv("LAPISAI_HEALTH_URL", "http://localhost:8000/health")
LOGIN_URL = os.getenv("LAPISAI_LOGIN_URL", "http://localhost:8000/api/auth/login")
TIMEOUT_SECONDS = int(os.getenv("LAPISAI_EVAL_TIMEOUT", "240"))
CONTEXT_MODE = "source_locked_snapshot_native_model_v5"
SNAPSHOT_SCHEMA_VERSION = 2
VALID_MODELS = ("ollama", "gemini", "groq")
MODEL_ENV = {
    "ollama": ("OLLAMA_MODEL", "qwen3-custom:latest"),
    "gemini": ("GEMINI_MODEL", "gemini-3.5-flash"),
    "groq": ("GROQ_MODEL", "llama-3.3-70b-versatile"),
}


class NonRetryableEvaluationError(RuntimeError):
    """A deterministic backend outcome that another identical retry cannot fix."""

    def __init__(self, message: str, *, category: str):
        super().__init__(message)
        self.category = category


def classify_chat_failure(response: dict[str, Any]) -> str:
    """Map structured backend diagnostics to one stable benchmark category."""
    stage = str(response.get("failure_stage") or "").strip().casefold()
    generation_mode = str(response.get("generation_mode") or "").strip().casefold()
    retrieval_mode = str(response.get("retrieval_mode") or "").strip().casefold()

    if (
        generation_mode == "retrieval_refusal"
        or retrieval_mode == "refused"
        or any(
            marker in stage
            for marker in ("retrieval", "context", "answerability", "confidence")
        )
    ):
        return "retrieval_or_context"
    if "answer_or_source" in stage:
        return "answer_postprocessing"
    if generation_mode and generation_mode != "native_model":
        return "pipeline_contract"
    return "generation_or_provider"


def candidate_value(candidate: dict[str, Any], snake: str, camel: str) -> Any:
    """Read snapshot v5 snake_case fields with compatibility for older snapshots."""
    value = candidate.get(snake)
    return candidate.get(camel) if value is None else value


def resolved_model_name(provider: str) -> str:
    env_name, default = MODEL_ENV[provider]
    return os.getenv(env_name, default)


def validate_provider_configuration(provider: str) -> None:
    key_env = {
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
    }.get(provider)
    if key_env and not os.getenv(key_env, "").strip():
        raise RuntimeError(
            f"{key_env} is not configured. Add it to the project-root .env "
            f"before evaluating provider={provider}."
        )


_AUTH_TOKEN: str | None = None


def resolve_evaluation_token() -> str:
    """Return an explicit token or authenticate with evaluation credentials."""
    global _AUTH_TOKEN
    if _AUTH_TOKEN:
        return _AUTH_TOKEN

    configured_token = os.getenv("LAPISAI_AUTH_TOKEN", "").strip()
    if configured_token:
        _AUTH_TOKEN = configured_token
        return configured_token

    username = os.getenv(
        "LAPISAI_EVAL_USERNAME",
        os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin"),
    ).strip()
    password = os.getenv(
        "LAPISAI_EVAL_PASSWORD",
        os.getenv("BOOTSTRAP_ADMIN_PASSWORD", ""),
    ).strip()
    if not username or not password:
        raise RuntimeError(
            "Evaluasi memerlukan autentikasi. Atur LAPISAI_AUTH_TOKEN, atau "
            "atur LAPISAI_EVAL_USERNAME dan LAPISAI_EVAL_PASSWORD di .env."
        )

    response = requests.post(
        LOGIN_URL,
        json={"username": username, "password": password},
        timeout=min(TIMEOUT_SECONDS, 30),
    )
    response.raise_for_status()
    payload = response.json()
    token = str(payload.get("token") or "").strip() if isinstance(payload, dict) else ""
    if not token:
        raise RuntimeError("Endpoint login tidak mengembalikan token autentikasi.")
    _AUTH_TOKEN = token
    return token


def post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = requests.post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {resolve_evaluation_token()}"},
        timeout=TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Respons tidak terduga dari {url}: objek JSON diperlukan")
    return data


def preflight() -> None:
    try:
        response = requests.get(HEALTH_URL, timeout=10)
        response.raise_for_status()
    except Exception as error:
        raise RuntimeError(
            "Backend LapisAI tidak dapat dijangkau. Jalankan: "
            "python -m uvicorn api.main:app --reload --host 127.0.0.1 "
            "--port 8000 --app-dir backend. "
            f"Pemeriksaan kesehatan gagal: {error}"
        ) from error

    # Fail before a long benchmark when protected chat credentials are missing.
    resolve_evaluation_token()


def normalize_source(item: Any) -> dict[str, str] | None:
    if not isinstance(item, dict):
        return None
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    document = (
        item.get("documentName")
        or item.get("document_name")
        or item.get("document")
        or item.get("file_name")
        or item.get("file")
        or item.get("source")
        or metadata.get("filename")
        or metadata.get("source")
        or metadata.get("document")
        or ""
    )
    page = (
        item.get("page")
        or item.get("page_number")
        or item.get("page_no")
        or metadata.get("page")
        or ""
    )
    if not document:
        return None
    return {"document": str(document), "page": str(page)}


def normalize_chat_citations(response: dict[str, Any]) -> list[dict[str, str]]:
    raw_sources = (
        response.get("sources")
        or response.get("source_documents")
        or response.get("retrieved_sources")
        or []
    )
    citations: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_sources:
        source = normalize_source(item)
        if source is None:
            continue
        key = (source["document"], source["page"])
        if key not in seen:
            seen.add(key)
            citations.append(source)
    return citations


def normalize_generation_context(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    text = str(
        item.get("text")
        or item.get("content")
        or item.get("excerpt")
        or item.get("page_content")
        or ""
    ).strip()
    if not text:
        return None
    return {
        "text": text,
        "document_name": str(
            item.get("document_name")
            or item.get("documentName")
            or item.get("document")
            or metadata.get("filename")
            or ""
        ).strip(),
        "page": item.get("page", metadata.get("page")),
        "chunk_id": str(
            item.get("chunk_id")
            or item.get("chunkId")
            or metadata.get("chunk_id")
            or ""
        ),
    }


def contexts_from_chat(response: dict[str, Any]) -> list[dict[str, Any]]:
    raw_contexts = response.get("generation_contexts") or []
    contexts = [
        normalized
        for item in raw_contexts
        if (normalized := normalize_generation_context(item)) is not None
    ]
    if contexts:
        return contexts
    return [
        normalized
        for item in (response.get("sources") or [])
        if (normalized := normalize_generation_context(item)) is not None
    ]


def build_context(contexts: list[dict[str, Any]]) -> str:
    blocks: list[str] = []
    for index, context in enumerate(contexts, start=1):
        blocks.append(
            f"[CONTEXT {index}]\n"
            f"Document: {context.get('document_name', '')}\n"
            f"Page: {context.get('page', '') or ''}\n"
            f"Evidence: {context.get('text', '')}"
        )
    return "\n\n".join(blocks)


def retrieved_sources_from_contexts(contexts: list[dict[str, Any]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for context in contexts:
        document = str(context.get("document_name") or "").strip()
        page = str(context.get("page") or "")
        if not document:
            continue
        key = (document, page)
        if key not in seen:
            seen.add(key)
            output.append({"document": document, "page": page})
    return output


def load_retrieval_snapshot(
    path: Path | None,
) -> dict[str, dict[str, Any]] | None:
    if path is None:
        return None
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION
    ):
        raise ValueError(
            "Retrieval snapshot uses an obsolete contract. Rebuild it with "
            "build_retrieval_snapshot.py before generating answers."
        )
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("Retrieval snapshot must contain an items array")
    return {
        str(item.get("id") or ""): item
        for item in items
        if isinstance(item, dict) and item.get("id")
    }


def _existing_results(output: Path, model: str) -> dict[str, dict[str, Any]]:
    if not output.exists():
        return {}
    try:
        payload = json.loads(output.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, list):
        return {}
    return {
        str(item.get("id")): item
        for item in payload
        if (
            isinstance(item, dict)
            and item.get("model") == model
            and item.get("id")
            and item.get("evaluation_context_mode") == CONTEXT_MODE
            and not item.get("pipeline_failed")
            and not item.get("generation_failed")
        )
    }


def build_dataset(
    ground_truth: list[dict[str, Any]],
    output: Path,
    *,
    model: str,
    top_k: int,
    resume: bool,
    retries: int,
    retrieval_snapshot: dict[str, dict[str, Any]] | None = None,
) -> None:
    if model not in VALID_MODELS:
        raise ValueError(f"Unsupported model {model!r}; choose from {VALID_MODELS}")

    validate_provider_configuration(model)
    preflight()
    previous = _existing_results(output, model) if resume else {}
    results: list[dict[str, Any]] = []
    errors: list[str] = []
    summary = dataset_summary(ground_truth)
    print(f"Dataset: {summary}")
    print(f"Generate {len(ground_truth)} answers with model={model} ({CONTEXT_MODE})")
    snapshot_locked = retrieval_snapshot is not None
    retrieval_snapshot = retrieval_snapshot or {}

    for index, item in enumerate(ground_truth, start=1):
        qid = str(item["id"])
        if qid in previous:
            print(f"[{index}/{len(ground_truth)}] {qid} resume")
            results.append(previous[qid])
            continue

        question = str(item["question"])
        language = str(item.get("language") or "EN").upper()
        print(f"[{index}/{len(ground_truth)}] {qid} ({language}, {model})")
        retrieval_item = retrieval_snapshot.get(qid, {})
        ranked_candidates = list(retrieval_item.get("ranked_candidates") or [])

        last_error: Exception | None = None
        last_answer = ""
        last_chat_response: dict[str, Any] = {}
        last_client_elapsed_ms = 0.0
        last_failure_category = "generation_or_provider"
        for attempt in range(1, retries + 2):
            try:
                request_started = time.perf_counter()
                chat_payload: dict[str, Any] = {
                    "question": question,
                    "topK": top_k,
                    "language": language,
                    "model": model,
                    "evaluation_mode": True,
                }
                if snapshot_locked:
                    chat_payload["retrievalCandidates"] = [
                        {
                            "chunkId": candidate.get("chunk_id") or candidate.get("chunkId"),
                            "documentName": candidate.get("document") or candidate.get("documentName"),
                            "page": candidate.get("page"),
                            "score": candidate.get("score"),
                            "contentSha256": candidate_value(
                                candidate, "content_sha256", "contentSha256"
                            ),
                            "baseScore": candidate_value(
                                candidate, "base_score", "baseScore"
                            ),
                            "semanticScore": candidate_value(
                                candidate, "semantic_score", "semanticScore"
                            ),
                            "keywordScore": candidate_value(
                                candidate, "keyword_score", "keywordScore"
                            ),
                            "exactTokenCoverage": candidate_value(
                                candidate, "exact_token_coverage", "exactTokenCoverage"
                            ),
                            "inventoryFieldScore": candidate_value(
                                candidate, "inventory_field_score", "inventoryFieldScore"
                            ),
                            "rerankerApplied": candidate_value(
                                candidate, "reranker_applied", "rerankerApplied"
                            ),
                            "rerankerScore": candidate_value(
                                candidate, "reranker_score", "rerankerScore"
                            ),
                            "rerankerRawScore": candidate_value(
                                candidate, "reranker_raw_score", "rerankerRawScore"
                            ),
                            "rerankerRank": candidate_value(
                                candidate, "reranker_rank", "rerankerRank"
                            ),
                            "snapshotRetrievalMode": retrieval_item.get(
                                "retrieval_mode"
                            ),
                            "snapshotRetrievalQuery": (
                                retrieval_item.get("retrieval_query")
                                or question
                            ),
                        }
                        for candidate in ranked_candidates
                        if isinstance(candidate, dict)
                        and (candidate.get("chunk_id") or candidate.get("chunkId"))
                    ]
                chat_response = post_json(
                    CHAT_URL,
                    chat_payload,
                )
                client_elapsed_ms = round((time.perf_counter() - request_started) * 1000, 2)
                last_client_elapsed_ms = client_elapsed_ms
                last_chat_response = chat_response
                snapshot_build = str(
                    retrieval_item.get("build_version") or ""
                ).strip()
                active_build = str(
                    chat_response.get("buildVersion") or ""
                ).strip()
                if (
                    snapshot_locked
                    and snapshot_build
                    and active_build
                    and snapshot_build != active_build
                ):
                    raise NonRetryableEvaluationError(
                        "Backend build changed after retrieval snapshot capture "
                        f"({snapshot_build} != {active_build}). Rebuild the snapshot.",
                        category="pipeline_contract",
                    )
                answer = str(
                    chat_response.get("answer")
                    or chat_response.get("result")
                    or chat_response.get("response")
                    or ""
                ).strip()
                last_answer = answer
                if not answer:
                    raise RuntimeError("The chat endpoint returned an empty answer")

                contexts = contexts_from_chat(chat_response)
                answerable = bool(item.get("answerable"))
                if answerable and not contexts:
                    raise NonRetryableEvaluationError(
                        "Answerable question returned no generation contexts. "
                        "Inspect failure_stage and retrieval diagnostics.",
                        category=classify_chat_failure(chat_response),
                    )
                if answerable and chat_response.get("generation_mode") != "native_model":
                    raise NonRetryableEvaluationError(
                        "Backend did not return native model output. "
                        "Inspect generation_mode and failure_stage.",
                        category=classify_chat_failure(chat_response),
                    )
                # Empty context is correct for a properly refused unanswerable question.
                retrieved_context = build_context(contexts)
                citations = normalize_chat_citations(chat_response)
                retrieved_sources = retrieved_sources_from_contexts(contexts)

                results.append(
                    {
                        "id": qid,
                        "model": model,
                        "model_name": resolved_model_name(model),
                        "backend_model": chat_response.get("model"),
                        "generation_mode": chat_response.get("generation_mode"),
                        "question": question,
                        "language": language,
                        "answerable": answerable,
                        "expected_answer": str(item.get("expected_answer") or ""),
                        "expected_answer_keywords": list(
                            item.get("expected_answer_keywords") or []
                        ),
                        "expected_sources": list(item.get("references") or []),
                        "retrieved_context": retrieved_context,
                        "retrieved_sources": retrieved_sources,
                        "retrieved_chunks": [
                            {
                                "document": context["document_name"],
                                "page": str(context.get("page") or ""),
                                "chunk_id": context.get("chunk_id", ""),
                                "content": context["text"],
                                "generation_context": True,
                            }
                            for context in contexts
                        ],
                        "generation_contexts": contexts,
                        "context_fingerprint": context_fingerprint(contexts),
                        "generated_answer": answer,
                        "citation": citations,
                        "system_confidence": chat_response.get("confidence", 0),
                        "backend_response_time_ms": chat_response.get("response_time_ms"),
                        "client_response_time_ms": client_elapsed_ms,
                        "evaluation_context_mode": CONTEXT_MODE,
                        "source_dataset": item.get("source_dataset"),
                        "retrieval_top_k": retrieval_item.get("top_k", top_k),
                        "ranked_candidates": ranked_candidates,
                        "retrieval_time_ms": retrieval_item.get("retrieval_time_ms"),
                        "retrieval_snapshot_build": retrieval_item.get("build_version"),
                        "snapshot_retrieval_mode": retrieval_item.get("retrieval_mode"),
                        "snapshot_retrieval_query": retrieval_item.get("retrieval_query"),
                        "backend_build_version": chat_response.get("buildVersion"),
                        "retrieval_mode": chat_response.get("retrieval_mode"),
                        "retrieval_query": chat_response.get("retrieval_query"),
                        "failure_stage": chat_response.get("failure_stage"),
                        "pipeline_failed": False,
                        "failure_category": None,
                        "generation_failed": False,
                        "generation_error": "",
                    }
                )
                last_error = None
                break
            except NonRetryableEvaluationError as error:
                last_error = error
                last_failure_category = error.category
                break
            except Exception as error:
                last_error = error
                last_failure_category = "generation_or_provider"
                if attempt <= retries:
                    delay = min(2 ** (attempt - 1), 8)
                    print(f"  retry {attempt}/{retries} after error: {error}")
                    time.sleep(delay)

        if last_error is not None:
            message = f"{qid}: {last_error}"
            errors.append(message)
            print(f"[ERROR] {message}")

            # A retrieval/generation failure is an evaluation outcome, not a reason
            # to abort the entire three-model benchmark. Store a complete failure row
            # so downstream metrics can count it and the remaining models can run.
            failure_contexts = contexts_from_chat(last_chat_response) if last_chat_response else []
            failure_citations = normalize_chat_citations(last_chat_response) if last_chat_response else []
            failure_sources = retrieved_sources_from_contexts(failure_contexts)
            generation_failed = last_failure_category == "generation_or_provider"
            results.append(
                {
                    "id": qid,
                    "model": model,
                    "model_name": resolved_model_name(model),
                    "backend_model": last_chat_response.get("model") if last_chat_response else None,
                    "generation_mode": last_chat_response.get("generation_mode") if last_chat_response else None,
                    "question": question,
                    "language": language,
                    "answerable": bool(item.get("answerable")),
                    "expected_answer": str(item.get("expected_answer") or ""),
                    "expected_answer_keywords": list(item.get("expected_answer_keywords") or []),
                    "expected_sources": list(item.get("references") or []),
                    "retrieved_context": build_context(failure_contexts),
                    "retrieved_sources": failure_sources,
                    "retrieved_chunks": [],
                    "generation_contexts": failure_contexts,
                    "context_fingerprint": context_fingerprint(failure_contexts),
                    "generated_answer": last_answer,
                    "citation": failure_citations,
                    "system_confidence": last_chat_response.get("confidence", 0) if last_chat_response else 0,
                    "backend_response_time_ms": last_chat_response.get("response_time_ms") if last_chat_response else None,
                    "client_response_time_ms": last_client_elapsed_ms,
                    "evaluation_context_mode": CONTEXT_MODE,
                    "source_dataset": item.get("source_dataset"),
                    "retrieval_top_k": retrieval_item.get("top_k", top_k),
                    "ranked_candidates": ranked_candidates,
                    "retrieval_time_ms": retrieval_item.get("retrieval_time_ms"),
                    "retrieval_snapshot_build": retrieval_item.get("build_version"),
                    "snapshot_retrieval_mode": retrieval_item.get("retrieval_mode"),
                    "snapshot_retrieval_query": retrieval_item.get("retrieval_query"),
                    "backend_build_version": (
                        last_chat_response.get("buildVersion")
                        if last_chat_response
                        else None
                    ),
                    "retrieval_mode": (
                        last_chat_response.get("retrieval_mode")
                        if last_chat_response
                        else retrieval_item.get("retrieval_mode")
                    ),
                    "retrieval_query": (
                        last_chat_response.get("retrieval_query")
                        if last_chat_response
                        else retrieval_item.get("retrieval_query")
                    ),
                    "failure_stage": (
                        last_chat_response.get("failure_stage")
                        if last_chat_response
                        else None
                    ),
                    "pipeline_failed": True,
                    "failure_category": last_failure_category,
                    "pipeline_error": str(last_error),
                    "generation_failed": generation_failed,
                    "generation_error": str(last_error) if generation_failed else "",
                }
            )

        # Save progress after every completed item so a long 100-question run can resume.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    # Always rewrite the complete ordered result set at the end. During --resume,
    # resumed rows use ``continue`` and therefore skip the per-item checkpoint write.
    # Without this final write, a run that only reprocesses one failed item can leave
    # the JSON truncated at that item even though all remaining rows were resumed.
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")

    if errors:
        preview = "\n".join(f"- {item}" for item in errors[:10])
        print(
            f"\n[WARNING] Generation completed with {len(errors)}/{len(ground_truth)} "
            "recorded failures. These rows remain in the benchmark and count as failures."
        )
        print(preview)

    print("\n[SUCCESS]")
    print(f"Saved       : {output}")
    print(f"Provider    : {model}")
    print(f"Model       : {resolved_model_name(model)}")
    print(f"Answers     : {len(results)}")
    print(f"Context mode: {CONTEXT_MODE}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--ground-truth",
        type=Path,
        action="append",
        dest="ground_truth_files",
        help="Repeat this option for multiple CSV/JSON files.",
    )
    parser.add_argument("--model", choices=VALID_MODELS, default="ollama")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--retrieval-snapshot", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()

    datasets = args.ground_truth_files or DEFAULT_DATASETS
    ground_truth = load_ground_truth_files(datasets)
    print(json.dumps(dataset_summary(ground_truth), indent=2, ensure_ascii=False))
    if args.validate_only:
        print("Dataset validation passed.")
        return

    output = args.output or (
        Path(__file__).resolve().parent / f"input_answers_{args.model}.json"
    )
    build_dataset(
        ground_truth,
        output.resolve(),
        model=args.model,
        top_k=max(1, args.top_k),
        resume=args.resume,
        retries=max(0, args.retries),
        retrieval_snapshot=load_retrieval_snapshot(args.retrieval_snapshot),
    )


if __name__ == "__main__":
    main()
