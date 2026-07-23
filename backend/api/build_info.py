"""Non-secret build metadata used to verify the active backend deployment."""

from __future__ import annotations

import hashlib
from pathlib import Path

BUILD_VERSION = "rag-multilingual-v8-20260723"
BUILD_FEATURES = (
    "english-corpus-first-retrieval-for-indonesian-queries",
    "direct-english-production-path-reused-for-language-bridge",
    "stale-evidence-and-answerability-annotations-cleared-before-revalidation",
    "original-indonesian-question-final-evidence-validation",
    "bilingual-generation-grounding-canonical-alias-coverage",
    "deterministic-verified-duration-answer-before-llm",
    "remote-provider-empty-answer-fallback-to-local-ollama",
    "merged-pdf-p1-p2-row-duration-disambiguation",
    "failure-stage-diagnostics",
    "strict-evidence-thresholds-unchanged",
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
