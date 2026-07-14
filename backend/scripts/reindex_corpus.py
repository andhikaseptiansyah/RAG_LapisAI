from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.indexer import reset_collection  # noqa: E402
from uploads.config import (  # noqa: E402
    CHROMA_PATH,
    COLLECTION_NAME,
    EMBEDDING_MODEL,
    MIN_RESULT_SCORE,
    UPLOAD_DIR,
)
from uploads.ingest import ingest  # noqa: E402

CORPUS_PREFIXES = ("FAQ_", "Policy_", "Report_", "SOP_", "TECH_")
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt"}


def main() -> None:
    upload_dir = Path(UPLOAD_DIR)
    files = sorted(
        (
            path
            for path in upload_dir.iterdir()
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_EXTENSIONS
            and path.name.startswith(CORPUS_PREFIXES)
        ),
        key=lambda path: path.name.lower(),
    )

    if not files:
        raise SystemExit(f"No corpus files found in {upload_dir}")

    print("LapisAI corpus re-index")
    print("=" * 40)
    print(f"Chroma path    : {CHROMA_PATH}")
    print(f"Collection     : {COLLECTION_NAME}")
    print(f"Embedding model: {EMBEDDING_MODEL}")
    print(f"Minimum score  : {MIN_RESULT_SCORE:.2f}")
    print(f"Documents      : {len(files)}")
    print()

    reset_collection()

    total_chunks = 0
    for index, path in enumerate(files, start=1):
        print(f"[{index:02d}/{len(files):02d}] {path.name}")
        result = ingest(str(path))
        total_chunks += int(result.get("chunks") or 0)

    print()
    print(f"Finished. Indexed {len(files)} documents and {total_chunks} chunks.")


if __name__ == "__main__":
    main()
