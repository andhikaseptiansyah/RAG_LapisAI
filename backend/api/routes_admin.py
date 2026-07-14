import os
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from api.logger import get_logs
from api.document_store import create_document_record, upsert_document
from uploads.config import UPLOAD_DIR
from uploads.ingest import ingest

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024

os.makedirs(UPLOAD_DIR, exist_ok=True)


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name or f"document_{uuid.uuid4().hex}.txt"


@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    filename = _safe_filename(file.filename or "")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = await file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 25 MB limit")

    filepath = os.path.join(UPLOAD_DIR, filename)

    # Avoid accidental overwrite while keeping the original name visible in metadata.
    if os.path.exists(filepath):
        stem = Path(filename).stem
        filepath = os.path.join(UPLOAD_DIR, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        filename = os.path.basename(filepath)

    with open(filepath, "wb") as f:
        f.write(content)

    try:
        result = ingest(filepath)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}") from e

    record = create_document_record(
        filename=filename,
        filepath=filepath,
        size_bytes=len(content),
        ingest_result=result,
    )
    upsert_document(record)

    return {
        "id": record["id"],
        "filename": filename,
        "status": result["status"],
        "pages": result["pages"],
        "totalChunks": result["chunks"],
        "collection": result["collection"],
        "embeddingModel": result["embedding_model"],
    }


@router.get("/logs")
def get_query_logs():
    return {"logs": get_logs()}
