import json
import os
import uuid
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.storage_paths import DOCUMENT_STORE_FILE
from uploads.config import COLLECTION_NAME, EMBEDDING_MODEL, UPLOAD_DIR

DOCUMENT_STORE_LOCK = threading.RLock()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized_document_filename(value: Any) -> str:
    """Return a safe, cross-platform filename for identity comparisons."""
    normalized_separators = str(value or "").strip().replace("\\", "/")
    return Path(normalized_separators).name.strip()


def resolve_document_source_path(document: dict[str, Any]) -> Path | None:
    """Resolve a document source inside the active upload directory.

    Older metadata may contain an absolute path from a different computer,
    such as ``C:\\Users\\...``. The filename is the portable identity, so the
    active upload directory is checked first. A stored path is accepted only
    when it still points inside that same directory.
    """
    filename = normalized_document_filename(document.get("filename"))
    if not filename:
        return None

    upload_root = Path(UPLOAD_DIR).resolve()
    canonical_path = (upload_root / filename).resolve()
    try:
        canonical_path.relative_to(upload_root)
    except ValueError:
        return None
    if canonical_path.is_file():
        return canonical_path

    # Windows filesystems are case-insensitive. Preserve that behavior when a
    # project is copied to a case-sensitive filesystem.
    try:
        for candidate in upload_root.iterdir():
            if (
                candidate.is_file()
                and candidate.name.casefold() == filename.casefold()
            ):
                return candidate.resolve()
    except OSError:
        pass

    stored_filepath = str(document.get("filepath") or "").strip()
    if not stored_filepath:
        return None

    stored_path = Path(stored_filepath).resolve()
    try:
        stored_path.relative_to(upload_root)
    except ValueError:
        return None
    if (
        stored_path.is_file()
        and stored_path.name.casefold() == filename.casefold()
    ):
        return stored_path
    return None


def read_documents() -> list[dict[str, Any]]:
    if not DOCUMENT_STORE_FILE.exists():
        return []

    try:
        with DOCUMENT_STORE_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                return []

            # Indexed-document metadata always reflects the active vector setup.
            # This prevents the dashboard from showing a model or collection that
            # is no longer used by ingestion and retrieval.
            for document in data:
                if not isinstance(document, dict):
                    continue
                if int(document.get("chunks") or 0) > 0:
                    document["collection"] = COLLECTION_NAME
                    document["embeddingModel"] = EMBEDDING_MODEL
                resolved_source = resolve_document_source_path(document)
                if resolved_source is not None:
                    # Rebase stale absolute paths in memory. A subsequent
                    # re-index/upsert persists this active-machine path.
                    document["filepath"] = str(resolved_source)
            return data
    except (json.JSONDecodeError, OSError):
        return []


def write_documents(documents: list[dict[str, Any]]) -> None:
    with DOCUMENT_STORE_LOCK:
        DOCUMENT_STORE_FILE.parent.mkdir(parents=True, exist_ok=True)
        temporary_file = DOCUMENT_STORE_FILE.with_suffix(".tmp")
        with temporary_file.open("w", encoding="utf-8") as f:
            json.dump(documents, f, indent=2, ensure_ascii=False)
        os.chmod(temporary_file, 0o600)
        os.replace(temporary_file, DOCUMENT_STORE_FILE)


def format_size(size_bytes: int | float | None) -> str:
    size = float(size_bytes or 0)
    units = ["B", "KB", "MB", "GB"]
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"

    return f"{size:.1f} {units[unit_index]}"


def document_type(filename: str) -> str:
    ext = Path(filename).suffix.lower().lstrip(".")
    if ext == "pdf":
        return "PDF"
    if ext == "docx":
        return "DOCX"
    return "TXT"


def create_document_record(
    filename: str,
    filepath: str,
    size_bytes: int,
    ingest_result: dict[str, Any],
) -> dict[str, Any]:
    chunks = int(ingest_result.get("chunks") or ingest_result.get("totalChunks") or 0)
    created_at = now_iso()

    return {
        "id": str(uuid.uuid4()),
        "filename": filename,
        "filepath": filepath,
        "type": document_type(filename),
        "sizeBytes": int(size_bytes or 0),
        "size": format_size(int(size_bytes or 0)),
        "uploadedAt": created_at,
        "indexedAt": created_at,
        "status": "Indexed" if chunks > 0 else "Failed",
        "indexedStatus": "Indexed" if chunks > 0 else "Pending",
        "vectorStatus": "Active" if chunks > 0 else "Pending",
        "progress": 100 if chunks > 0 else 0,
        "chunks": chunks,
        "note": (
            f"Indexed with Python RAG pipeline ({chunks} chunks)."
            if chunks > 0
            else "Document parsed, but no chunks were created."
        ),
        "pages": int(ingest_result.get("pages") or 0),
        "collection": ingest_result.get("collection"),
        "embeddingModel": ingest_result.get("embedding_model") or ingest_result.get("embeddingModel"),
    }


def upsert_document(record: dict[str, Any]) -> dict[str, Any]:
    documents = read_documents()
    filepath = record.get("filepath")
    filename = normalized_document_filename(record.get("filename")).casefold()

    updated = False
    for index, current in enumerate(documents):
        current_filename = normalized_document_filename(
            current.get("filename")
        ).casefold()
        if current.get("filepath") == filepath or (
            filename and current_filename == filename
        ):
            record["id"] = current.get("id") or record.get("id")
            documents[index] = record
            updated = True
            break

    if not updated:
        documents.insert(0, record)

    write_documents(documents)
    return record


def get_document(document_id: str) -> dict[str, Any] | None:
    for document in read_documents():
        if document.get("id") == document_id:
            return document
    return None


def delete_document(document_id: str) -> dict[str, Any] | None:
    documents = read_documents()
    removed = None
    remaining = []

    for document in documents:
        if document.get("id") == document_id:
            removed = document
        else:
            remaining.append(document)

    if removed is not None:
        write_documents(remaining)

    return removed


def delete_documents_by_filename(filename: str) -> list[dict[str, Any]]:
    """Delete every metadata record that resolves to the same safe filename."""
    normalized_filename = Path(filename).name.strip().casefold()
    if not normalized_filename:
        return []

    documents = read_documents()
    removed = [
        document
        for document in documents
        if Path(str(document.get("filename") or "")).name.strip().casefold()
        == normalized_filename
    ]

    if removed:
        removed_ids = {
            str(document.get("id") or "")
            for document in removed
        }
        write_documents([
            document
            for document in documents
            if str(document.get("id") or "") not in removed_ids
        ])

    return removed


def to_upload_item(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document.get("id", ""),
        "filename": document.get("filename", "-"),
        "type": document.get("type", "TXT"),
        "size": document.get("size") or format_size(document.get("sizeBytes")),
        "sizeBytes": int(document.get("sizeBytes") or 0),
        "uploadedAt": document.get("uploadedAt") or now_iso(),
        "status": document.get("status", "Ready"),
        "progress": int(document.get("progress") or 0),
        "chunks": int(document.get("chunks") or 0),
        "note": document.get("note", "Ready to index."),
    }


def to_trained_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document.get("id", ""),
        "filename": document.get("filename", "-"),
        "type": document.get("type", "TXT"),
        "size": document.get("size") or format_size(document.get("sizeBytes")),
        "chunks": int(document.get("chunks") or 0),
        "indexedAt": document.get("indexedAt") or document.get("uploadedAt") or now_iso(),
        "vectorStatus": document.get("vectorStatus", "Pending"),
        "collection": document.get("collection") or COLLECTION_NAME,
        "embeddingModel": document.get("embeddingModel") or EMBEDDING_MODEL,
    }


def to_repository_document(document: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": document.get("id", ""),
        "filename": document.get("filename", "-"),
        "type": document.get("type", "TXT"),
        "size": document.get("size") or format_size(document.get("sizeBytes")),
        "uploadDate": document.get("uploadedAt") or now_iso(),
        "chunks": int(document.get("chunks") or 0),
        "indexedStatus": document.get("indexedStatus", "Pending"),
        "collection": document.get("collection") or COLLECTION_NAME,
        "embeddingModel": document.get("embeddingModel") or EMBEDDING_MODEL,
    }


def filter_documents(search: str | None = None, doc_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    documents = read_documents()
    search_lower = (search or "").strip().lower()

    filtered = []
    for document in documents:
        if search_lower and search_lower not in str(document.get("filename", "")).lower():
            continue
        if doc_type and document.get("type") != doc_type:
            continue
        if status and document.get("indexedStatus") != status:
            continue
        filtered.append(document)

    return filtered
