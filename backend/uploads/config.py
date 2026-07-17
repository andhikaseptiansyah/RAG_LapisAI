"""Single source of truth for the RAG runtime configuration.

All backend, evaluation, re-indexing, and legacy Python service modules import
settings from this file. Values are loaded from the project-root ``.env`` and
can still be overridden by process environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"
ENV_FILE = PROJECT_ROOT / ".env"


def _load_project_env(path: Path) -> None:
    """Load a small .env file without making startup depend on python-dotenv."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_project_env(ENV_FILE)


def _env_str(name: str, default: str, *legacy_names: str) -> str:
    for key in (name, *legacy_names):
        raw = os.getenv(key)
        if raw is not None and raw.strip():
            return raw.strip()
    return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be a number, got {raw!r}"
        ) from exc
    return value


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer, got {raw!r}"
        ) from exc


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(
        f"Environment variable {name} must be true/false, got {raw!r}"
    )


def _resolve_project_path(name: str, default: Path, *legacy_names: str) -> str:
    raw = _env_str(name, str(default), *legacy_names)
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    return str(candidate.resolve())


# Canonical storage paths. Relative values in .env are resolved from PROJECT_ROOT,
# so commands work consistently whether they are run from root, backend, or evaluation.
UPLOAD_DIR = _resolve_project_path(
    "UPLOAD_DIR",
    BACKEND_DIR / "uploads" / "files",
)
CHROMA_PATH = _resolve_project_path(
    "CHROMA_PATH",
    BACKEND_DIR / "chroma_db",
    "CHROMA_DIR",
)

# Canonical vector collection. COLLECTION_NAME remains as a compatibility alias for
# existing imports, but CHROMA_COLLECTION is the only name written to .env.
CHROMA_COLLECTION = _env_str(
    "CHROMA_COLLECTION",
    "knowledge_base_multilingual_v1",
    "COLLECTION_NAME",
)
COLLECTION_NAME = CHROMA_COLLECTION

# One multilingual embedding model is used by ingestion, retrieval, evaluation,
# metadata, dashboard, and the legacy Python service.
EMBEDDING_MODEL = _env_str(
    "EMBEDDING_MODEL",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "PYTHON_EMBEDDING_MODEL",
)

# Runtime and evaluation use the same calibrated retrieval cutoff.
MIN_RESULT_SCORE = _env_float("MIN_RESULT_SCORE", 0.24)
if not 0.0 <= MIN_RESULT_SCORE <= 1.0:
    raise ValueError("MIN_RESULT_SCORE must be between 0.0 and 1.0")

# Multilingual cross-encoder reranker. Each retriever contributes its top N
# candidates. Their union (up to 2N chunks) is scored before top-k is selected.
# The reranker is blended conservatively with the hybrid score; it does not
# replace the hybrid ranking outright. If loading fails, retrieval degrades safely.
ENABLE_RERANKER = _env_bool("ENABLE_RERANKER", True)
RERANKER_MODEL = _env_str(
    "RERANKER_MODEL",
    "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
)
RERANKER_CANDIDATES = _env_int("RERANKER_CANDIDATES", 20)
RERANKER_WEIGHT = _env_float("RERANKER_WEIGHT", 0.25)
if RERANKER_CANDIDATES <= 0:
    raise ValueError("RERANKER_CANDIDATES must be greater than zero")
if not 0.0 <= RERANKER_WEIGHT <= 1.0:
    raise ValueError("RERANKER_WEIGHT must be between 0.0 and 1.0")

ENABLE_EVIDENCE_VERIFICATION = _env_bool(
    "ENABLE_EVIDENCE_VERIFICATION",
    True,
)
MIN_EVIDENCE_SCORE = _env_float("MIN_EVIDENCE_SCORE", 0.42)
EVIDENCE_WEIGHT = _env_float("EVIDENCE_WEIGHT", 0.25)

# Separate answerability/rejection gate. A reranker only reorders candidates;
# these settings decide whether the indexed corpus contains enough explicit
# evidence to answer at all.
ENABLE_ANSWERABILITY_GATE = _env_bool("ENABLE_ANSWERABILITY_GATE", True)
ANSWERABILITY_MIN_TOP_SCORE = _env_float("ANSWERABILITY_MIN_TOP_SCORE", 0.35)
# A reranker may raise the blended score, but the original hybrid score must
# still clear this floor. This prevents a confident cross-encoder from turning
# a weak lexical/semantic match into an answerable result by itself.
ANSWERABILITY_MIN_BASE_SCORE = _env_float("ANSWERABILITY_MIN_BASE_SCORE", 0.22)
ANSWERABILITY_MIN_EVIDENCE_SCORE = _env_float("ANSWERABILITY_MIN_EVIDENCE_SCORE", 0.42)
ANSWERABILITY_MIN_SCORE_MARGIN = _env_float("ANSWERABILITY_MIN_SCORE_MARGIN", 0.0)
ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE = _env_bool(
    "ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE",
    False,
)
ANSWERABILITY_STRONG_RETRIEVAL_SCORE = _env_float(
    "ANSWERABILITY_STRONG_RETRIEVAL_SCORE",
    0.68,
)
ANSWERABILITY_STRONG_EXACT_COVERAGE = _env_float(
    "ANSWERABILITY_STRONG_EXACT_COVERAGE",
    0.20,
)
ANSWERABILITY_MAX_CONTEXTS = _env_int("ANSWERABILITY_MAX_CONTEXTS", 5)
# Production safety rule: when the baseline hybrid+evidence gate rejects the
# query, reranking is not allowed to resurrect it. The reranker may reorder an
# answerable candidate set, but it is not an answerability classifier.
ANSWERABILITY_PRE_RERANK_VETO = _env_bool(
    "ANSWERABILITY_PRE_RERANK_VETO",
    False,
)
if ANSWERABILITY_MAX_CONTEXTS <= 0:
    raise ValueError("ANSWERABILITY_MAX_CONTEXTS must be greater than zero")

# Answer/source confidence gates. These settings live here (rather than being
# read directly in answer_formatter.py) so the project-root .env is loaded
# before the values are evaluated, regardless of Python import order.
MIN_ANSWER_CONFIDENCE = _env_float("MIN_ANSWER_CONFIDENCE", 0.48)
MIN_SOURCE_CONFIDENCE = _env_float("MIN_SOURCE_CONFIDENCE", 0.24)
SOURCE_EXCERPT_MAX_CHARS = _env_int("SOURCE_EXCERPT_MAX_CHARS", 360)
if SOURCE_EXCERPT_MAX_CHARS < 120:
    raise ValueError("SOURCE_EXCERPT_MAX_CHARS must be at least 120")

for _name, _value in (
    ("MIN_EVIDENCE_SCORE", MIN_EVIDENCE_SCORE),
    ("EVIDENCE_WEIGHT", EVIDENCE_WEIGHT),
    ("ANSWERABILITY_MIN_TOP_SCORE", ANSWERABILITY_MIN_TOP_SCORE),
    ("ANSWERABILITY_MIN_BASE_SCORE", ANSWERABILITY_MIN_BASE_SCORE),
    ("ANSWERABILITY_MIN_EVIDENCE_SCORE", ANSWERABILITY_MIN_EVIDENCE_SCORE),
    ("ANSWERABILITY_MIN_SCORE_MARGIN", ANSWERABILITY_MIN_SCORE_MARGIN),
    ("ANSWERABILITY_STRONG_RETRIEVAL_SCORE", ANSWERABILITY_STRONG_RETRIEVAL_SCORE),
    ("ANSWERABILITY_STRONG_EXACT_COVERAGE", ANSWERABILITY_STRONG_EXACT_COVERAGE),
    ("MIN_ANSWER_CONFIDENCE", MIN_ANSWER_CONFIDENCE),
    ("MIN_SOURCE_CONFIDENCE", MIN_SOURCE_CONFIDENCE),
):
    if not 0.0 <= _value <= 1.0:
        raise ValueError(f"{_name} must be between 0.0 and 1.0")


# Generation context selection and post-generation grounding. Retrieval still
# returns top-k for evaluation, but only a compact evidence bundle reaches the LLM.
MAX_GENERATION_CONTEXTS = _env_int("MAX_GENERATION_CONTEXTS", 3)
CONTEXT_REDUNDANCY_THRESHOLD = _env_float("CONTEXT_REDUNDANCY_THRESHOLD", 0.82)
CONTEXT_SECONDARY_SCORE_RATIO = _env_float("CONTEXT_SECONDARY_SCORE_RATIO", 0.72)
MAX_SOURCE_CITATIONS = _env_int("MAX_SOURCE_CITATIONS", 2)
ENABLE_GENERATION_GROUNDING_VALIDATION = _env_bool(
    "ENABLE_GENERATION_GROUNDING_VALIDATION",
    True,
)
GENERATION_MIN_CLAIM_SUPPORT = _env_float("GENERATION_MIN_CLAIM_SUPPORT", 0.32)
if MAX_GENERATION_CONTEXTS <= 0:
    raise ValueError("MAX_GENERATION_CONTEXTS must be greater than zero")
if MAX_SOURCE_CITATIONS <= 0:
    raise ValueError("MAX_SOURCE_CITATIONS must be greater than zero")
for _name, _value in (
    ("CONTEXT_REDUNDANCY_THRESHOLD", CONTEXT_REDUNDANCY_THRESHOLD),
    ("CONTEXT_SECONDARY_SCORE_RATIO", CONTEXT_SECONDARY_SCORE_RATIO),
    ("GENERATION_MIN_CLAIM_SUPPORT", GENERATION_MIN_CLAIM_SUPPORT),
):
    if not 0.0 <= _value <= 1.0:
        raise ValueError(f"{_name} must be between 0.0 and 1.0")

RETRIEVAL_WARMUP_QUERY = _env_str(
    "RETRIEVAL_WARMUP_QUERY",
    "How do I reset my employee password?",
)

# LLM provider selection
DEFAULT_LLM_PROVIDER = _env_str("DEFAULT_LLM_PROVIDER", "ollama")

# Gemini configuration
GEMINI_API_KEY = _env_str("GEMINI_API_KEY", "")
GEMINI_MODEL = _env_str("GEMINI_MODEL", "gemini-2.0-flash")

# OpenAI configuration
OPENAI_API_KEY = _env_str("OPENAI_API_KEY", "")
OPENAI_MODEL = _env_str("OPENAI_MODEL", "gpt-4o")


def public_rag_config() -> dict[str, str | float | bool | int]:
    """Return non-secret configuration safe to display in the admin dashboard."""
    return {
        "collection": COLLECTION_NAME,
        "embeddingModel": EMBEDDING_MODEL,
        "minimumResultScore": MIN_RESULT_SCORE,
        "rerankerEnabled": ENABLE_RERANKER,
        "rerankerModel": RERANKER_MODEL,
        "rerankerCandidatesPerRetriever": RERANKER_CANDIDATES,
        "rerankerWeight": RERANKER_WEIGHT,
        "evidenceVerificationEnabled": ENABLE_EVIDENCE_VERIFICATION,
        "minimumEvidenceScore": MIN_EVIDENCE_SCORE,
        "answerabilityGateEnabled": ENABLE_ANSWERABILITY_GATE,
        "answerabilityMinimumTopScore": ANSWERABILITY_MIN_TOP_SCORE,
        "answerabilityMinimumBaseScore": ANSWERABILITY_MIN_BASE_SCORE,
        "answerabilityMinimumEvidenceScore": ANSWERABILITY_MIN_EVIDENCE_SCORE,
        "answerabilityMinimumScoreMargin": ANSWERABILITY_MIN_SCORE_MARGIN,
        "answerabilityRequireSupportedEvidence": ANSWERABILITY_REQUIRE_SUPPORTED_EVIDENCE,
        "answerabilityStrongRetrievalScore": ANSWERABILITY_STRONG_RETRIEVAL_SCORE,
        "answerabilityStrongExactCoverage": ANSWERABILITY_STRONG_EXACT_COVERAGE,
        "answerabilityMaxContexts": ANSWERABILITY_MAX_CONTEXTS,
        "answerabilityPreRerankVeto": ANSWERABILITY_PRE_RERANK_VETO,
        "minimumAnswerConfidence": MIN_ANSWER_CONFIDENCE,
        "minimumSourceConfidence": MIN_SOURCE_CONFIDENCE,
        "sourceExcerptMaxChars": SOURCE_EXCERPT_MAX_CHARS,
        "maxGenerationContexts": MAX_GENERATION_CONTEXTS,
        "contextRedundancyThreshold": CONTEXT_REDUNDANCY_THRESHOLD,
        "contextSecondaryScoreRatio": CONTEXT_SECONDARY_SCORE_RATIO,
        "maxSourceCitations": MAX_SOURCE_CITATIONS,
        "generationGroundingValidationEnabled": ENABLE_GENERATION_GROUNDING_VALIDATION,
        "generationMinimumClaimSupport": GENERATION_MIN_CLAIM_SUPPORT,
    }
