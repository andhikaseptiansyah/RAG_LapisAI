from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_DIR = PROJECT_ROOT / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from api.document_store import create_document_record, upsert_document  # noqa: E402
from ingestion.indexer import get_collection, reset_collection  # noqa: E402
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


def _sync_document_store(path: Path, ingest_result: dict) -> None:
    """Synchronize each document's latest chunk count with the dashboard store."""
    record = create_document_record(
        filename=path.name,
        filepath=str(path.resolve()),
        size_bytes=path.stat().st_size,
        ingest_result=ingest_result,
    )
    upsert_document(record)


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
        chunks = int(result.get("chunks") or 0)
        total_chunks += chunks

        # Keep documents_store.json aligned with the newly indexed Chroma data.
        _sync_document_store(path, result)

    chroma_total = int(get_collection().count())

    print()
    print(
        f"Finished. Indexed {len(files)} documents and "
        f"{total_chunks} chunks."
    )
    print(f"ChromaDB count : {chroma_total}")
    print("Dashboard store synchronized.")

    if chroma_total != total_chunks:
        raise SystemExit(
            "Chunk count mismatch: "
            f"script={total_chunks}, chroma={chroma_total}"
        )


if __name__ == "__main__":
    main()
