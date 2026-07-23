"""Non-secret build metadata used to verify the active backend deployment."""

BUILD_VERSION = "rag-multilingual-v5-20260723"
BUILD_FEATURES = (
    "independent-original-and-english-bridge-retrieval",
    "strict-primary-candidate-bridge-fallback",
    "wide-bridge-retrieval-with-original-question-revalidation",
    "multi-variant-semantic-search",
    "multi-variant-bm25",
    "multi-variant-reranker",
    "strict-thresholds-unchanged",
)


def public_build_info() -> dict[str, object]:
    return {
        "buildVersion": BUILD_VERSION,
        "buildFeatures": list(BUILD_FEATURES),
    }
