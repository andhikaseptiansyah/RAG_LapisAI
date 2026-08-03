"""Private, reviewable holdout utilities for final LapisAI evaluation.

The public regression CSVs intentionally remain inside the repository.  A
final benchmark is different: it is authored after the application code is
frozen, stored outside the repository, independently reviewed, and never used
for tuning.  This module implements the common contracts used by the holdout
builder, human review command, and strict final runner.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

try:
    from .generation.atomic_io import replace_file_with_retry
except ImportError:  # Direct script execution.
    from generation.atomic_io import replace_file_with_retry


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
DEFAULT_PRIVATE_HOLDOUT_DIR = PROJECT_ROOT.parent / "LapisAI_Private_Holdout"
HOLDOUT_SCHEMA_VERSION = 1
CSV_FIELDS = (
    "question",
    "expected_answer",
    "source_document",
    "answerable",
    "expected_answer_keywords",
)


def load_project_env(path: Path | None = None) -> None:
    """Load project .env values without overriding the active process."""
    env_path = path or (PROJECT_ROOT / ".env")
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalized_key(value: Any) -> str:
    return normalize_text(value).casefold()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: Any) -> str:
    return sha256_bytes(normalize_text(value).encode("utf-8"))


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def model_reference_is_mutable(model_name: str) -> bool:
    normalized = str(model_name or "").strip().casefold()
    if (
        not normalized
        or normalized.endswith(":latest")
        or normalized in {"latest", "default"}
    ):
        return True
    if "@sha256:" in normalized:
        return False
    if ":" in normalized and normalized.rsplit(":", 1)[-1] not in {"", "latest"}:
        return False
    # Hosted providers often encode the frozen release in the model ID rather
    # than an Ollama-style tag, for example family-3.1 or model-2026-08-02.
    return re.search(r"(?:^|[-_.])v?\d+(?:[.-]\d+)*", normalized) is None


@dataclass(frozen=True)
class ModelEndpoint:
    role: str
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls, role: str, prefix: str) -> "ModelEndpoint":
        return cls(
            role=role,
            base_url=os.getenv(
                f"{prefix}_BASE_URL",
                "http://127.0.0.1:11434/v1",
            ).strip(),
            api_key=os.getenv(f"{prefix}_API_KEY", "ollama").strip(),
            model=os.getenv(f"{prefix}_MODEL", "").strip(),
        )

    def validate(self) -> None:
        if not self.base_url:
            raise ValueError(f"{self.role} base URL is empty")
        if model_reference_is_mutable(self.model):
            raise ValueError(
                f"{self.role} model must be an explicit immutable tag or digest; "
                f"received {self.model or '<empty>'!r}."
            )


def require_distinct_models(
    *,
    author: str,
    reviewer: str,
    judge: str | None = None,
    evaluated: Iterable[str] = (),
) -> None:
    roles: list[tuple[str, str]] = [
        ("holdout author", author),
        ("holdout reviewer", reviewer),
    ]
    if judge is not None:
        roles.append(("evaluation judge", judge))
    roles.extend(("evaluated model", model) for model in evaluated)

    for role, model in roles:
        if model_reference_is_mutable(model):
            raise ValueError(
                f"{role} must use an immutable model tag or digest; got {model!r}."
            )

    by_name: dict[str, list[str]] = {}
    for role, model in roles:
        by_name.setdefault(model.casefold().strip(), []).append(role)
    collisions = [
        f"{model}: {', '.join(collision_roles)}"
        for model, collision_roles in by_name.items()
        if len(collision_roles) > 1
    ]
    if collisions:
        raise ValueError(
            "Author, reviewer, judge, and evaluated models must be distinct. "
            + "; ".join(collisions)
        )


def _flatten_chroma_field(value: Any) -> list[Any]:
    if not isinstance(value, list):
        return []
    if value and isinstance(value[0], list):
        output: list[Any] = []
        for nested in value:
            if isinstance(nested, list):
                output.extend(nested)
        return output
    return value


def load_corpus_chunks() -> list[dict[str, Any]]:
    """Read the active Chroma corpus without needing the physical upload files."""
    import sys

    backend_text = str(BACKEND_DIR)
    if backend_text not in sys.path:
        sys.path.insert(0, backend_text)

    try:
        from ingestion.indexer import get_collection
    except Exception as exc:  # pragma: no cover - depends on local runtime
        raise RuntimeError(
            "Unable to load the active Chroma collection. Start from the project "
            "virtual environment and ensure backend dependencies are installed."
        ) from exc

    collection = get_collection()
    payload = collection.get(include=["documents", "metadatas"])
    ids = _flatten_chroma_field(payload.get("ids") or [])
    documents = _flatten_chroma_field(payload.get("documents") or [])
    metadatas = _flatten_chroma_field(payload.get("metadatas") or [])

    chunks: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for index, chunk_id in enumerate(ids):
        text = normalize_text(documents[index] if index < len(documents) else "")
        metadata = (
            metadatas[index]
            if index < len(metadatas) and isinstance(metadatas[index], dict)
            else {}
        )
        filename = Path(str(metadata.get("filename") or "")).name.strip()
        if not filename or len(text) < 80:
            continue
        key = (filename.casefold(), sha256_text(text))
        if key in seen:
            continue
        seen.add(key)
        chunks.append(
            {
                "chunk_id": str(chunk_id),
                "filename": filename,
                "page": metadata.get("page"),
                "text": text,
                "text_sha256": sha256_text(text),
            }
        )

    if not chunks:
        raise RuntimeError(
            "The active Chroma collection contains no usable document chunks. "
            "Upload and index the corpus first."
        )
    return chunks


def corpus_fingerprint(chunks: list[dict[str, Any]]) -> str:
    canonical = [
        {
            "chunk_id": str(item.get("chunk_id") or ""),
            "filename": str(item.get("filename") or "").casefold(),
            "text_sha256": str(item.get("text_sha256") or sha256_text(item.get("text"))),
        }
        for item in chunks
    ]
    canonical.sort(key=lambda item: (item["filename"], item["chunk_id"]))
    return sha256_bytes(
        json.dumps(canonical, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def record_digest(record: dict[str, Any]) -> str:
    fields = {
        "pair_id": str(record.get("pair_id") or ""),
        "answerable": bool(record.get("answerable")),
        "source_document": str(record.get("source_document") or ""),
        "topic_document": str(record.get("topic_document") or ""),
        "question_en": normalize_text(record.get("question_en")),
        "answer_en": normalize_text(record.get("answer_en")),
        "keywords_en": [normalize_text(item) for item in record.get("keywords_en") or []],
        "question_id": normalize_text(record.get("question_id")),
        "answer_id": normalize_text(record.get("answer_id")),
        "keywords_id": [normalize_text(item) for item in record.get("keywords_id") or []],
        "evidence_quote": normalize_text(record.get("evidence_quote")),
        "evidence_chunk_id": str(record.get("evidence_chunk_id") or ""),
        "evidence_sha256": str(record.get("evidence_sha256") or ""),
        "author_model": str(record.get("author_model") or ""),
        "reviewer_model": str(record.get("reviewer_model") or ""),
        "reviewer_approved": record.get("reviewer_approved") is True,
        "reviewer_reason": normalize_text(record.get("reviewer_reason")),
        "reviewed_evidence": [
            {
                "chunk_id": str(item.get("chunk_id") or ""),
                "filename": str(item.get("filename") or ""),
                "text_sha256": str(item.get("text_sha256") or ""),
                "excerpt": normalize_text(item.get("excerpt")),
            }
            for item in record.get("reviewed_evidence") or []
            if isinstance(item, dict)
        ],
    }
    return sha256_bytes(
        json.dumps(fields, sort_keys=True, ensure_ascii=False).encode("utf-8")
    )


def write_holdout_csvs(
    output_dir: Path,
    records: list[dict[str, Any]],
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    english_path = output_dir / "qna_english_holdout.csv"
    indonesian_path = output_dir / "qna_indonesia_holdout.csv"

    def rows(language: str) -> list[dict[str, Any]]:
        suffix = "en" if language == "EN" else "id"
        return [
            {
                "question": normalize_text(record[f"question_{suffix}"]),
                "expected_answer": normalize_text(record[f"answer_{suffix}"]),
                "source_document": (
                    str(record.get("source_document") or "")
                    if record.get("answerable")
                    else ""
                ),
                "answerable": "TRUE" if record.get("answerable") else "FALSE",
                "expected_answer_keywords": " | ".join(
                    normalize_text(value)
                    for value in record.get(f"keywords_{suffix}") or []
                    if normalize_text(value)
                ),
            }
            for record in records
        ]

    for path, language in ((english_path, "EN"), (indonesian_path, "ID")):
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(rows(language))
        replace_file_with_retry(temporary, path)
    return english_path, indonesian_path


def write_json_atomic(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    replace_file_with_retry(temporary, path)


def package_manifest(
    *,
    output_dir: Path,
    records: list[dict[str, Any]],
    corpus_sha256: str,
    author_model: str,
    reviewer_model: str,
    seed: int,
) -> dict[str, Any]:
    english_path = output_dir / "qna_english_holdout.csv"
    indonesian_path = output_dir / "qna_indonesia_holdout.csv"
    return {
        "schema_version": HOLDOUT_SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "benchmark_role": "holdout",
        "corpus_sha256": corpus_sha256,
        "author_model": author_model,
        "reviewer_model": reviewer_model,
        "seed": seed,
        "pair_count": len(records),
        "answerable_pair_count": sum(bool(item.get("answerable")) for item in records),
        "unanswerable_pair_count": sum(not bool(item.get("answerable")) for item in records),
        "record_digests": {
            str(item.get("pair_id")): record_digest(item) for item in records
        },
        "files": {
            english_path.name: {
                "sha256": sha256_file(english_path),
                "bytes": english_path.stat().st_size,
            },
            indonesian_path.name: {
                "sha256": sha256_file(indonesian_path),
                "bytes": indonesian_path.stat().st_size,
            },
            "holdout_review.json": {
                "sha256": sha256_file(output_dir / "holdout_review.json"),
                "bytes": (output_dir / "holdout_review.json").stat().st_size,
            },
        },
    }


def refresh_manifest_file_hashes(output_dir: Path, manifest: dict[str, Any]) -> None:
    for filename in (
        "qna_english_holdout.csv",
        "qna_indonesia_holdout.csv",
        "holdout_review.json",
    ):
        path = output_dir / filename
        manifest.setdefault("files", {})[filename] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        }
    write_json_atomic(output_dir / "holdout_manifest.json", manifest)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        missing = [field for field in CSV_FIELDS if field not in fields]
        if missing:
            raise ValueError(f"{path.name} is missing columns: {', '.join(missing)}")
        return [dict(row) for row in reader]


def validate_private_holdout(
    output_dir: Path,
    *,
    require_human_approval: bool,
    expected_corpus_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate the frozen private package and return its loaded contents."""
    output_dir = output_dir.resolve()
    manifest_path = output_dir / "holdout_manifest.json"
    review_path = output_dir / "holdout_review.json"
    english_path = output_dir / "qna_english_holdout.csv"
    indonesian_path = output_dir / "qna_indonesia_holdout.csv"
    missing = [
        path.name
        for path in (manifest_path, review_path, english_path, indonesian_path)
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(
            "Private holdout package is incomplete: " + ", ".join(missing)
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    review = json.loads(review_path.read_text(encoding="utf-8"))
    records = review.get("records") if isinstance(review, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError("holdout_review.json contains no records")

    if manifest.get("schema_version") != HOLDOUT_SCHEMA_VERSION:
        raise ValueError("Unsupported private holdout schema version")
    if manifest.get("benchmark_role") != "holdout":
        raise ValueError("Private package is not marked as holdout")
    if review.get("schema_version") != HOLDOUT_SCHEMA_VERSION:
        raise ValueError("Unsupported private review schema version")
    for field in ("corpus_sha256", "author_model", "reviewer_model"):
        if review.get(field) != manifest.get(field):
            raise ValueError(f"Review and manifest disagree on {field}")
    if expected_corpus_sha256 and manifest.get("corpus_sha256") != expected_corpus_sha256:
        raise ValueError(
            "The active corpus differs from the corpus used to author this holdout. "
            "Build a new private holdout after any corpus change."
        )

    manifest_files = manifest.get("files") or {}
    required_files = {
        "qna_english_holdout.csv",
        "qna_indonesia_holdout.csv",
        "holdout_review.json",
    }
    missing_manifest_files = required_files.difference(manifest_files)
    if missing_manifest_files:
        raise ValueError(
            "Manifest is missing artifact hashes: "
            + ", ".join(sorted(missing_manifest_files))
        )
    for filename, metadata in manifest_files.items():
        path = output_dir / filename
        if not path.is_file():
            raise FileNotFoundError(f"Manifest file is missing: {filename}")
        if sha256_file(path) != str(metadata.get("sha256") or ""):
            raise ValueError(f"Holdout artifact changed after freezing: {filename}")

    expected_digests = manifest.get("record_digests") or {}
    if int(manifest.get("pair_count") or 0) != len(records):
        raise ValueError("Manifest pair count does not match the review records")
    answerable_count = sum(bool(record.get("answerable")) for record in records)
    if int(manifest.get("answerable_pair_count") or -1) != answerable_count:
        raise ValueError("Manifest answerable count does not match the review records")
    if int(manifest.get("unanswerable_pair_count") or -1) != len(records) - answerable_count:
        raise ValueError("Manifest unanswerable count does not match the review records")
    record_ids = {str(record.get("pair_id") or "") for record in records}
    if set(expected_digests) != record_ids:
        raise ValueError("Manifest record digests do not match the review record IDs")
    for record in records:
        pair_id = str(record.get("pair_id") or "")
        if not pair_id or record_digest(record) != expected_digests.get(pair_id):
            raise ValueError(f"Holdout record changed or has no digest: {pair_id!r}")
        if str(record.get("author_model") or "") != str(manifest.get("author_model") or ""):
            raise ValueError(f"Holdout author provenance mismatch for {pair_id}")
        if str(record.get("reviewer_model") or "") != str(manifest.get("reviewer_model") or ""):
            raise ValueError(f"Holdout reviewer provenance mismatch for {pair_id}")
        if record.get("reviewer_approved") is not True:
            raise ValueError(f"Independent reviewer rejected or skipped {pair_id}")
        if require_human_approval and record.get("human_approved") is not True:
            raise ValueError(f"Human review is incomplete for {pair_id}")

    english_rows = _read_csv(english_path)
    indonesian_rows = _read_csv(indonesian_path)
    if len(english_rows) != len(records) or len(indonesian_rows) != len(records):
        raise ValueError("CSV row counts do not match the frozen review records")
    if english_rows != _rows_for_validation(records, "EN"):
        raise ValueError("English CSV does not match the frozen review records")
    if indonesian_rows != _rows_for_validation(records, "ID"):
        raise ValueError("Indonesian CSV does not match the frozen review records")

    pair_ids = [str(record.get("pair_id") or "") for record in records]
    if len(pair_ids) != len(set(pair_ids)):
        raise ValueError("Duplicate pair IDs in private holdout")
    questions = [
        normalized_key(record.get(field))
        for record in records
        for field in ("question_en", "question_id")
    ]
    duplicates = [value for value, count in Counter(questions).items() if count > 1]
    if duplicates:
        raise ValueError("Duplicate question text in private holdout")

    return {
        "manifest": manifest,
        "review": review,
        "records": records,
        "english_path": english_path,
        "indonesian_path": indonesian_path,
    }


def _rows_for_validation(
    records: list[dict[str, Any]],
    language: str,
) -> list[dict[str, str]]:
    suffix = "en" if language == "EN" else "id"
    return [
        {
            "question": normalize_text(record[f"question_{suffix}"]),
            "expected_answer": normalize_text(record[f"answer_{suffix}"]),
            "source_document": (
                str(record.get("source_document") or "")
                if record.get("answerable")
                else ""
            ),
            "answerable": "TRUE" if record.get("answerable") else "FALSE",
            "expected_answer_keywords": " | ".join(
                normalize_text(item)
                for item in record.get(f"keywords_{suffix}") or []
                if normalize_text(item)
            ),
        }
        for record in records
    ]


def lexical_rank_chunks(
    question: str,
    chunks: list[dict[str, Any]],
    *,
    limit: int = 12,
) -> list[dict[str, Any]]:
    """Return corpus evidence most likely to contradict an unanswerable item."""
    question_tokens = set(re.findall(r"[a-z0-9]+", question.casefold()))
    stop = {
        "the", "a", "an", "is", "are", "what", "which", "how", "does",
        "berapa", "apa", "yang", "dan", "untuk", "dalam", "apakah",
    }
    question_tokens -= stop
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        text_tokens = set(re.findall(r"[a-z0-9]+", str(chunk.get("text") or "").casefold()))
        overlap = len(question_tokens.intersection(text_tokens))
        score = overlap / max(len(question_tokens), 1)
        if score:
            scored.append((score, chunk))
    scored.sort(
        key=lambda value: (
            value[0],
            len(str(value[1].get("text") or "")),
        ),
        reverse=True,
    )
    return [item for _, item in scored[:limit]]
