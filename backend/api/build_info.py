"""Non-secret build metadata used to verify the active backend deployment."""

from __future__ import annotations

import hashlib
from pathlib import Path

BUILD_VERSION = "rag-bilingual-eval-v15-20260801"
BUILD_FEATURES = (
    "evidence-first-context-selection-over-heading-only-hybrid-hits",
    "complementary-locked-requirement-context-bundling",
    "bilingual-policy-relation-grounding-with-strict-fact-binding",
    "evaluation-only-rejected-native-answer-and-citation-diagnostics",
    "markdown-answer-label-normalization",
    "failure-stage-specific-refusal-payloads-with-evaluation-context-preservation",
    "native-refusal-versus-citation-validation-diagnostics",
    "hard-subject-first-evidence-scoring-with-soft-hint-isolation",
    "claim-local-bilingual-relation-equivalence-validation",
    "direct-identity-checklist-supporting-document-recognition",
    "compact-procurement-table-approver-recognition",
    "consecutive-duration-bilingual-fact-normalization",
    "modified-leave-day-quantity-normalization",
    "relative-monthly-payroll-time-recognition",
    "generic-password-requirements-multi-chunk-retrieval",
    "interchangeable-ground-truth-source-or-metrics",
    "content-hash-verified-snapshot-replay",
    "strict-gate-state-preserved-without-snapshot-revalidation",
    "snapshot-question-and-candidate-contract-validation",
    "snapshot-reranker-lexical-and-coherence-signal-preservation",
    "evaluation-pipeline-failure-taxonomy",
    "citation-precision-recall-f1-and-ndcg-reporting",
    "structured-refusal-aware-abstention-detection",
    "english-corpus-first-retrieval-for-indonesian-queries",
    "direct-english-production-path-reused-for-language-bridge",
    "stale-evidence-and-answerability-annotations-cleared-before-live-bridge-validation",
    "original-indonesian-question-final-live-retrieval-validation",
    "bilingual-generation-grounding-canonical-alias-coverage",
    "deterministic-verified-duration-answer-before-llm",
    "remote-provider-empty-answer-fallback-to-local-ollama",
    "merged-pdf-p1-p2-row-duration-disambiguation",
    "failure-stage-diagnostics",
    "real-time-rag-progress-sse",
    "progress-cancellation-and-offline-lifecycle",
    "strict-only-context-selection-before-generation",
    "enterprise-intent-natural-english-bridges",
    "snapshot-locked-model-evaluation-contexts",
    "calibrated-verified-evidence-score-override",
)


def _fingerprint(filename: str) -> str:
    path = Path(__file__).with_name(filename)
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    except OSError:
        return "unavailable"


def public_build_info() -> dict[str, object]:
    return {
        "buildVersion": BUILD_VERSION,
        "buildFeatures": list(BUILD_FEATURES),
        "chatServiceSha256": _fingerprint("chat_service.py"),
        "answerFormatterSha256": _fingerprint("answer_formatter.py"),
        "groundingValidatorSha256": _fingerprint("grounding_validator.py"),
    }
