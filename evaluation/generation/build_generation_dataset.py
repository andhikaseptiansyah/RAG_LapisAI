"""Generate source-locked answers for one LLM provider.

This script supports the bilingual 50-English + 50-Indonesian CSV dataset and
both answerable and deliberately unanswerable questions. Each output row stores
the requested model, response latency, citations, exact generation contexts,
and a context fingerprint for fair cross-model comparison.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    # Dataset-only validation must work before runtime dependencies are
    # installed. Real API evaluation still checks ``requests`` explicitly.
    def load_dotenv(*_args: Any, **_kwargs: Any) -> bool:
        return False

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
CONTEXT_MODE = "source_locked_snapshot_native_model_v8"
SNAPSHOT_SCHEMA_VERSION = 4
LATENCY_MEASUREMENT_MODE = "single_strict_retrieval_without_debug_baseline"
VALID_MODELS = ("ollama", "gemini", "groq")
MODEL_ENV = {
    "ollama": ("OLLAMA_MODEL", "qwen3-custom:latest"),
    "gemini": ("GEMINI_MODEL", "gemini-3.5-flash"),
    "groq": ("GROQ_MODEL", "llama-3.3-70b-versatile"),
}
TEMPORARY_PROVIDER_EXIT_CODE = 75
MAX_RATE_LIMIT_WAIT_SECONDS = max(
    0.0,
    float(os.getenv("EVAL_MAX_RATE_LIMIT_WAIT_SECONDS", "90")),
)


class NonRetryableEvaluationError(RuntimeError):
    """A deterministic backend outcome that another identical retry cannot fix."""

    def __init__(self, message: str, *, category: str):
        super().__init__(message)
        self.category = category


class ProviderRateLimitError(RuntimeError):
    """A structured HTTP 429 returned by the evaluation backend."""

    def __init__(
        self,
        message: str,
        *,
        provider: str = "provider",
        quota_scope: str = "unknown",
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.provider = str(provider or "provider").strip().casefold()
        self.quota_scope = (
            quota_scope if quota_scope in {"daily", "minute"} else "unknown"
        )
        self.retry_after_seconds = retry_after_seconds


class ProviderEvaluationPaused(RuntimeError):
    """Stop one provider without converting its remaining rows into failures."""

    def __init__(self, error: ProviderRateLimitError, output: Path) -> None:
        super().__init__(str(error))
        self.provider = error.provider
        self.quota_scope = error.quota_scope
        self.retry_after_seconds = error.retry_after_seconds
        self.output = output


def classify_chat_failure(response: dict[str, Any]) -> str:
    """Map structured backend diagnostics to one stable benchmark category."""
    stage = str(response.get("failure_stage") or "").strip().casefold()
    generation_mode = str(response.get("generation_mode") or "").strip().casefold()
    retrieval_mode = str(response.get("retrieval_mode") or "").strip().casefold()

    if "evaluation_snapshot_contract" in stage:
        return "pipeline_contract"
    # Stage is authoritative. A late failure used to be wrapped by the generic
    # retrieval-refusal payload, causing valid retrieved contexts to be counted
    # as retrieval misses. Check the precise stage before compatibility modes.
    if "citation_validation" in stage or "answer_or_source" in stage:
        return "answer_postprocessing"
    if "native_model_refusal" in stage:
        return "generation_output"
    if "native_answer_empty" in stage or "wrong_output_language" in stage:
        return "generation_or_provider"
    if (
        generation_mode == "retrieval_refusal"
        or retrieval_mode == "refused"
        or any(
            marker in stage
            for marker in ("retrieval", "context", "answerability", "confidence")
        )
    ):
        return "retrieval_or_context"
    if generation_mode and generation_mode != "native_model":
        return "pipeline_contract"
    return "generation_or_provider"


def candidate_value(candidate: dict[str, Any], snake: str, camel: str) -> Any:
    """Read normalized snapshot fields with camelCase API compatibility."""
    value = candidate.get(snake)
    return candidate.get(camel) if value is None else value


def snapshot_candidate_payload(
    candidate: dict[str, Any],
    retrieval_item: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    """Build the complete locked candidate contract sent to the backend."""
    return {
        "chunkId": candidate.get("chunk_id") or candidate.get("chunkId"),
        "documentName": candidate.get("document") or candidate.get("documentName"),
        "page": candidate.get("page"),
        "score": candidate.get("score"),
        "contentSha256": candidate_value(candidate, "content_sha256", "contentSha256"),
        "baseScore": candidate_value(candidate, "base_score", "baseScore"),
        "semanticScore": candidate_value(candidate, "semantic_score", "semanticScore"),
        "keywordScore": candidate_value(candidate, "keyword_score", "keywordScore"),
        "exactTokenCoverage": candidate_value(
            candidate,
            "exact_token_coverage",
            "exactTokenCoverage",
        ),
        "inventoryFieldScore": candidate_value(
            candidate,
            "inventory_field_score",
            "inventoryFieldScore",
        ),
        "rerankerApplied": candidate_value(
            candidate,
            "reranker_applied",
            "rerankerApplied",
        ),
        "rerankerScore": candidate_value(candidate, "reranker_score", "rerankerScore"),
        "rerankerRawScore": candidate_value(
            candidate,
            "reranker_raw_score",
            "rerankerRawScore",
        ),
        "rerankerRank": candidate_value(candidate, "reranker_rank", "rerankerRank"),
        "semanticQueryVariant": candidate_value(
            candidate,
            "semantic_query_variant",
            "semanticQueryVariant",
        ),
        "keywordQueryVariant": candidate_value(
            candidate,
            "keyword_query_variant",
            "keywordQueryVariant",
        ),
        "rerankerQueryVariant": candidate_value(
            candidate,
            "reranker_query_variant",
            "rerankerQueryVariant",
        ),
        "rerankerQueryVariantCount": candidate_value(
            candidate,
            "reranker_query_variant_count",
            "rerankerQueryVariantCount",
        ),
        "evidenceSupported": candidate_value(
            candidate,
            "evidence_supported",
            "evidenceSupported",
        ),
        "evidenceScore": candidate_value(candidate, "evidence_score", "evidenceScore"),
        "evidenceHardFailures": candidate_value(
            candidate,
            "evidence_hard_failures",
            "evidenceHardFailures",
        ),
        "evidenceHardContradictions": candidate_value(
            candidate,
            "evidence_hard_contradictions",
            "evidenceHardContradictions",
        ),
        "evidenceContradictions": candidate_value(
            candidate,
            "evidence_contradictions",
            "evidenceContradictions",
        ),
        "evidenceMissingRequirements": candidate_value(
            candidate,
            "evidence_missing_requirements",
            "evidenceMissingRequirements",
        ),
        "answerabilityAccepted": candidate_value(
            candidate,
            "answerability_accepted",
            "answerabilityAccepted",
        ),
        "answerabilityStrictlySupported": candidate_value(
            candidate,
            "answerability_strictly_supported",
            "answerabilityStrictlySupported",
        ),
        "answerabilityEvidenceSelected": candidate_value(
            candidate,
            "answerability_evidence_selected",
            "answerabilityEvidenceSelected",
        ),
        "answerabilityScore": candidate_value(
            candidate,
            "answerability_score",
            "answerabilityScore",
        ),
        "answerabilityScoreMargin": candidate_value(
            candidate,
            "answerability_score_margin",
            "answerabilityScoreMargin",
        ),
        "answerabilityRequirementCoverage": candidate_value(
            candidate,
            "answerability_requirement_coverage",
            "answerabilityRequirementCoverage",
        ),
        "answerabilityConceptCoverage": candidate_value(
            candidate,
            "answerability_concept_coverage",
            "answerabilityConceptCoverage",
        ),
        "answerabilityRequiresCoherentEvidence": candidate_value(
            candidate,
            "answerability_requires_coherent_evidence",
            "answerabilityRequiresCoherentEvidence",
        ),
        "answerabilityCoherentEvidence": candidate_value(
            candidate,
            "answerability_coherent_evidence",
            "answerabilityCoherentEvidence",
        ),
        "answerabilityDiagnostics": candidate_value(
            candidate,
            "answerability_diagnostics",
            "answerabilityDiagnostics",
        ),
        "snapshotRetrievalMode": retrieval_item.get("retrieval_mode"),
        "snapshotRetrievalQuery": retrieval_item.get("retrieval_query") or question,
    }


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


def requests_module():
    try:
        import requests
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Dependency 'requests' belum terpasang. Jalankan: "
            "python -m pip install -r backend/requirements.txt"
        ) from exc
    return requests


def evaluation_credentials() -> tuple[str, str]:
    """Resolve evaluation credentials, treating blank overrides as unset.

    ``python-dotenv`` loads ``KEY=`` as an empty string. The previous nested
    ``os.getenv`` calls treated that empty value as authoritative and therefore
    never reached the configured bootstrap credentials. This helper preserves
    explicit evaluation credentials while making a blank override fall back to
    the administrator configured for a fresh local installation.
    """
    username = (
        os.getenv("LAPISAI_EVAL_USERNAME", "").strip()
        or os.getenv("BOOTSTRAP_ADMIN_USERNAME", "").strip()
        or "admin"
    )
    password = (
        os.getenv("LAPISAI_EVAL_PASSWORD", "").strip()
        or os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    )
    return username, password


def resolve_evaluation_token() -> str:
    """Return an explicit token or authenticate with evaluation credentials."""
    global _AUTH_TOKEN
    if _AUTH_TOKEN:
        return _AUTH_TOKEN

    configured_token = os.getenv("LAPISAI_AUTH_TOKEN", "").strip()
    if configured_token:
        _AUTH_TOKEN = configured_token
        return configured_token

    username, password = evaluation_credentials()
    if not username or not password:
        raise RuntimeError(
            "Evaluasi memerlukan autentikasi. Atur LAPISAI_AUTH_TOKEN, atau "
            "isi LAPISAI_EVAL_PASSWORD maupun BOOTSTRAP_ADMIN_PASSWORD di "
            f"{PROJECT_ROOT / '.env'}."
        )

    response = requests_module().post(
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
    response = requests_module().post(
        url,
        json=payload,
        headers={"Authorization": f"Bearer {resolve_evaluation_token()}"},
        timeout=TIMEOUT_SECONDS,
    )
    if response.status_code == 429:
        try:
            error_payload = response.json()
        except (TypeError, ValueError):
            error_payload = {}
        detail = (
            error_payload.get("detail", error_payload)
            if isinstance(error_payload, dict)
            else {}
        )
        if not isinstance(detail, dict):
            detail = {}

        retry_after: float | None = None
        raw_retry_after = (
            detail.get("retry_after_seconds")
            or response.headers.get("retry-after")
        )
        try:
            if raw_retry_after is not None:
                retry_after = max(0.0, float(raw_retry_after))
        except (TypeError, ValueError):
            retry_after = None

        message = str(detail.get("message") or "Provider API rate limit reached.")
        raise ProviderRateLimitError(
            message,
            provider=str(detail.get("provider") or payload.get("model") or "provider"),
            quota_scope=str(detail.get("quota_scope") or "unknown"),
            retry_after_seconds=retry_after,
        )

    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError(f"Respons tidak terduga dari {url}: objek JSON diperlukan")
    return data


def preflight() -> None:
    try:
        response = requests_module().get(HEALTH_URL, timeout=10)
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


def validate_snapshot_contract(
    ground_truth: list[dict[str, Any]],
    snapshot: dict[str, dict[str, Any]],
) -> None:
    """Fail before generation when the snapshot and dataset do not match."""
    expected_ids = {str(item.get("id") or "") for item in ground_truth}
    snapshot_ids = set(snapshot)
    missing_ids = sorted(expected_ids - snapshot_ids)
    extra_ids = sorted(snapshot_ids - expected_ids)
    if missing_ids or extra_ids:
        raise ValueError(
            "Retrieval snapshot IDs do not match the evaluation dataset. "
            f"Missing={missing_ids[:10]}, extra={extra_ids[:10]}. "
            "Rebuild the retrieval snapshot."
        )

    required_candidate_fields = (
        ("content_sha256", "contentSha256"),
        ("evidence_supported", "evidenceSupported"),
        ("evidence_hard_failures", "evidenceHardFailures"),
        ("evidence_hard_contradictions", "evidenceHardContradictions"),
        ("answerability_accepted", "answerabilityAccepted"),
        ("answerability_strictly_supported", "answerabilityStrictlySupported"),
        ("answerability_evidence_selected", "answerabilityEvidenceSelected"),
        (
            "answerability_requires_coherent_evidence",
            "answerabilityRequiresCoherentEvidence",
        ),
        ("answerability_coherent_evidence", "answerabilityCoherentEvidence"),
    )

    for item in ground_truth:
        qid = str(item.get("id") or "")
        snapshot_item = snapshot[qid]
        question = str(item.get("question") or "")
        expected_question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        if snapshot_item.get("question") != question:
            raise ValueError(
                f"Retrieval snapshot question changed for {qid}. Rebuild the snapshot."
            )
        if snapshot_item.get("question_sha256") != expected_question_hash:
            raise ValueError(
                f"Retrieval snapshot question hash is invalid for {qid}. "
                "Rebuild the snapshot."
            )
        if str(snapshot_item.get("language") or "").upper() != str(
            item.get("language") or ""
        ).upper():
            raise ValueError(
                f"Retrieval snapshot language changed for {qid}. Rebuild the snapshot."
            )
        if bool(snapshot_item.get("answerable")) != bool(item.get("answerable")):
            raise ValueError(
                f"Retrieval snapshot answerability label changed for {qid}. "
                "Rebuild the snapshot."
            )
        if (
            snapshot_item.get("latency_measurement_mode")
            != LATENCY_MEASUREMENT_MODE
        ):
            raise ValueError(
                f"Retrieval snapshot latency contract is invalid for {qid}. "
                "Rebuild the snapshot."
            )

        for candidate in snapshot_item.get("ranked_candidates") or []:
            chunk_id = str(
                candidate.get("chunk_id") or candidate.get("chunkId") or ""
            )
            missing_fields = [
                snake
                for snake, camel in required_candidate_fields
                if candidate_value(candidate, snake, camel) is None
            ]
            if not chunk_id or missing_fields:
                raise ValueError(
                    f"Retrieval snapshot candidate contract is incomplete for {qid} "
                    f"({chunk_id or 'missing chunk ID'}): {missing_fields}. "
                    "Rebuild the snapshot."
                )

            content_hash = str(
                candidate_value(candidate, "content_sha256", "contentSha256") or ""
            ).lower()
            if len(content_hash) != 64 or any(
                character not in "0123456789abcdef" for character in content_hash
            ):
                raise ValueError(
                    f"Retrieval snapshot content hash is invalid for {qid}/{chunk_id}. "
                    "Rebuild the snapshot."
                )
            if candidate_value(
                candidate,
                "answerability_accepted",
                "answerabilityAccepted",
            ) is not True or candidate_value(
                candidate,
                "answerability_strictly_supported",
                "answerabilityStrictlySupported",
            ) is not True or candidate_value(
                candidate,
                "answerability_evidence_selected",
                "answerabilityEvidenceSelected",
            ) is not True:
                raise ValueError(
                    f"Retrieval snapshot contains a non-strict candidate for "
                    f"{qid}/{chunk_id}. Rebuild the snapshot."
                )
            if candidate_value(
                candidate,
                "evidence_hard_failures",
                "evidenceHardFailures",
            ) or candidate_value(
                candidate,
                "evidence_hard_contradictions",
                "evidenceHardContradictions",
            ):
                raise ValueError(
                    f"Retrieval snapshot contains contradictory evidence for "
                    f"{qid}/{chunk_id}. Rebuild the snapshot."
                )
            requires_coherent = bool(
                candidate_value(
                    candidate,
                    "answerability_requires_coherent_evidence",
                    "answerabilityRequiresCoherentEvidence",
                )
            )
            coherent = candidate_value(
                candidate,
                "answerability_coherent_evidence",
                "answerabilityCoherentEvidence",
            ) is True
            if requires_coherent and not coherent:
                raise ValueError(
                    f"Retrieval snapshot lost coherent evidence for {qid}/{chunk_id}. "
                    "Rebuild the snapshot."
                )


def load_retrieval_snapshot(
    path: Path | None,
) -> dict[str, dict[str, Any]] | None:
    if path is None:
        return None
    payload = json.loads(path.resolve().read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or payload.get("snapshot_schema_version") != SNAPSHOT_SCHEMA_VERSION
        or payload.get("latency_measurement_mode") != LATENCY_MEASUREMENT_MODE
    ):
        raise ValueError(
            "Retrieval snapshot uses an obsolete contract. Rebuild it with "
            "build_retrieval_snapshot.py before generating answers."
        )
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        raise ValueError("Retrieval snapshot must contain an items array")
    mapped: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict) or not item.get("id"):
            raise ValueError("Retrieval snapshot contains an item without a valid ID")
        qid = str(item["id"])
        if qid in mapped:
            raise ValueError(f"Retrieval snapshot contains duplicate ID: {qid}")
        mapped[qid] = item
    return mapped


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


def retrieval_snapshot_fingerprint(item: dict[str, Any]) -> str:
    """Bind a generated answer to the exact retrieval snapshot row it used."""
    canonical = json.dumps(
        item,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def previous_result_matches_snapshot(
    previous: dict[str, Any],
    retrieval_item: dict[str, Any],
    *,
    model: str,
) -> bool:
    """Reject stale resume rows after any model or snapshot change."""
    return bool(
        previous.get("model_name") == resolved_model_name(model)
        and previous.get("retrieval_snapshot_fingerprint")
        == retrieval_snapshot_fingerprint(retrieval_item)
    )


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
    if snapshot_locked:
        validate_snapshot_contract(ground_truth, retrieval_snapshot)

    def save_checkpoint() -> None:
        """Persist new rows without dropping valid later rows from a resume file."""
        current = {str(row.get("id")): row for row in results if row.get("id")}
        checkpoint: list[dict[str, Any]] = []
        for expected in ground_truth:
            expected_id = str(expected.get("id") or "")
            if expected_id in current:
                checkpoint.append(current[expected_id])
                continue
            previous_row = previous.get(expected_id)
            retrieval_row = retrieval_snapshot.get(expected_id, {})
            if previous_row is not None and (
                not snapshot_locked
                or previous_result_matches_snapshot(
                    previous_row,
                    retrieval_row,
                    model=model,
                )
            ):
                checkpoint.append(previous_row)

        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(checkpoint, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    for index, item in enumerate(ground_truth, start=1):
        qid = str(item["id"])
        retrieval_item = retrieval_snapshot.get(qid, {})
        if qid in previous and (
            not snapshot_locked
            or previous_result_matches_snapshot(
                previous[qid],
                retrieval_item,
                model=model,
            )
        ):
            print(f"[{index}/{len(ground_truth)}] {qid} resume")
            results.append(previous[qid])
            continue
        if qid in previous:
            print(
                f"[{index}/{len(ground_truth)}] {qid} stale resume row; regenerate"
            )

        question = str(item["question"])
        language = str(item.get("language") or "EN").upper()
        print(f"[{index}/{len(ground_truth)}] {qid} ({language}, {model})")
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
                        snapshot_candidate_payload(candidate, retrieval_item, question)
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

                if str(chat_response.get("failure_stage") or "").casefold() == (
                    "evaluation_snapshot_contract"
                ):
                    raise NonRetryableEvaluationError(
                        str(chat_response.get("pipeline_error") or "")
                        or "Backend rejected the locked retrieval snapshot contract.",
                        category="pipeline_contract",
                    )

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
                        "retrieval_snapshot_fingerprint": retrieval_snapshot_fingerprint(
                            retrieval_item
                        ),
                        "retrieval_latency_measurement_mode": retrieval_item.get(
                            "latency_measurement_mode"
                        ),
                        "snapshot_retrieval_mode": retrieval_item.get("retrieval_mode"),
                        "snapshot_retrieval_query": retrieval_item.get("retrieval_query"),
                        "backend_build_version": chat_response.get("buildVersion"),
                        "retrieval_mode": chat_response.get("retrieval_mode"),
                        "retrieval_query": chat_response.get("retrieval_query"),
                        "failure_stage": chat_response.get("failure_stage"),
                        "failure_reason": chat_response.get("failure_reason"),
                        "rejected_native_answer": chat_response.get(
                            "rejected_native_answer"
                        ),
                        "citation_validation": chat_response.get(
                            "citation_validation"
                        ),
                        "context_count_before_failure": chat_response.get(
                            "context_count_before_failure",
                            len(contexts),
                        ),
                        "pipeline_error": chat_response.get("pipeline_error"),
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
            except ProviderRateLimitError as error:
                if error.quota_scope != "daily" and attempt <= retries:
                    delay = (
                        error.retry_after_seconds
                        if error.retry_after_seconds is not None
                        else min(2 ** (attempt - 1), 8)
                    )
                    if delay <= MAX_RATE_LIMIT_WAIT_SECONDS:
                        print(
                            f"  provider rate limit; wait {delay:.1f}s "
                            f"before retry {attempt}/{retries}: {error}"
                        )
                        time.sleep(delay)
                        continue

                save_checkpoint()
                raise ProviderEvaluationPaused(error, output) from error
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
                    "retrieval_snapshot_fingerprint": retrieval_snapshot_fingerprint(
                        retrieval_item
                    ),
                    "retrieval_latency_measurement_mode": retrieval_item.get(
                        "latency_measurement_mode"
                    ),
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
                    "failure_reason": (
                        last_chat_response.get("failure_reason")
                        if last_chat_response
                        else None
                    ),
                    "rejected_native_answer": (
                        last_chat_response.get("rejected_native_answer")
                        if last_chat_response
                        else None
                    ),
                    "citation_validation": (
                        last_chat_response.get("citation_validation")
                        if last_chat_response
                        else None
                    ),
                    "context_count_before_failure": (
                        last_chat_response.get(
                            "context_count_before_failure",
                            len(failure_contexts),
                        )
                        if last_chat_response
                        else len(failure_contexts)
                    ),
                    "pipeline_failed": True,
                    "failure_category": last_failure_category,
                    "pipeline_error": (
                        last_chat_response.get("pipeline_error")
                        if last_chat_response
                        and last_chat_response.get("pipeline_error")
                        else str(last_error)
                    ),
                    "generation_failed": generation_failed,
                    "generation_error": str(last_error) if generation_failed else "",
                }
            )

        # Save progress after every completed item so a long 100-question run can resume.
        save_checkpoint()

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
    resolved_output = output.resolve()
    try:
        build_dataset(
            ground_truth,
            resolved_output,
            model=args.model,
            top_k=max(1, args.top_k),
            resume=args.resume,
            retries=max(0, args.retries),
            retrieval_snapshot=load_retrieval_snapshot(args.retrieval_snapshot),
        )
    except ProviderEvaluationPaused as error:
        scope = (
            "kuota harian habis"
            if error.quota_scope == "daily"
            else "batas permintaan belum pulih"
        )
        print(f"\n[PAUSED] {error.provider.title()}: {scope}.")
        print(f"Penyebab     : {error}")
        print(f"Progress aman: {error.output}")
        print("Jalankan lagi perintah yang sama dengan --resume setelah kuota tersedia.")
        raise SystemExit(TEMPORARY_PROVIDER_EXIT_CODE) from None


if __name__ == "__main__":
    main()
