import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel

from api.conversation_store import (
    append_chat_turn,
    delete_conversation,
    get_conversation,
    list_summaries,
    update_conversation,
)
from api.document_store import (
    create_document_record,
    delete_document,
    filter_documents,
    get_document,
    read_documents,
    to_repository_document,
    to_trained_document,
    to_upload_item,
    upsert_document,
)
from api.chat_service import run_chat
from api.logger import delete_log, get_logs, save_log
from ingestion.indexer import delete_document_chunks, get_collection
from uploads.config import UPLOAD_DIR, public_rag_config
from uploads.ingest import ingest

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
DEV_TOKEN_PREFIX = "lapisai-dev-token"

DEV_USERS: dict[str, dict[str, str]] = {
    "admin": {
        "id": "dev-admin",
        "username": "admin",
        "name": "Admin",
        "role": "admin",
        "password": "admin",
    },
    "dhika": {
        "id": "dev-staff-dhika",
        "username": "dhika",
        "name": "Dhika",
        "role": "staff",
        "password": "dhika",
    },
    "staff": {
        "id": "dev-staff",
        "username": "staff",
        "name": "Staff User",
        "role": "staff",
        "password": "staff",
    },
}

os.makedirs(UPLOAD_DIR, exist_ok=True)


class LoginPayload(BaseModel):
    username: str = "admin"
    password: str = "admin"


class IndexPayload(BaseModel):
    documentIds: list[str] | None = None


class ConversationUpdatePayload(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    language: str | None = None


class QueryLogParams(BaseModel):
    range: str | None = None
    page: int = 1
    limit: int = 25
    status: str | None = None
    search: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _normalize_username(username: str | None) -> str:
    return (username or "").strip().lower()


def _public_user(user: dict[str, str]) -> dict[str, str]:
    return {
        "id": user["id"],
        "username": user["username"],
        "name": user["name"],
        "role": user["role"],
    }


def _build_token(username: str) -> str:
    return f"{DEV_TOKEN_PREFIX}:{username}"


def _token_to_user(token: str | None) -> dict[str, str] | None:
    clean_token = (token or "").strip()

    # Backward compatibility untuk token lama yang sudah pernah tersimpan di browser.
    if clean_token == DEV_TOKEN_PREFIX:
        return DEV_USERS["admin"]

    prefix = f"{DEV_TOKEN_PREFIX}:"
    if not clean_token.startswith(prefix):
        return None

    username = _normalize_username(clean_token.removeprefix(prefix))
    return DEV_USERS.get(username)


def _get_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _require_user(request: Request) -> dict[str, str]:
    user = _token_to_user(_get_bearer_token(request))
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sesi tidak valid atau sudah berakhir.",
        )
    return user


def _can_admin(user: dict[str, str]) -> bool:
    return user.get("role") == "admin"


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name or f"document_{uuid.uuid4().hex}.txt"


def _save_upload_file(file: UploadFile) -> tuple[str, str, int]:
    filename = _safe_filename(file.filename or "")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = file.file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 25 MB limit")

    filepath = os.path.join(UPLOAD_DIR, filename)

    if os.path.exists(filepath):
        stem = Path(filename).stem
        filepath = os.path.join(UPLOAD_DIR, f"{stem}_{uuid.uuid4().hex[:8]}{ext}")
        filename = os.path.basename(filepath)

    with open(filepath, "wb") as f:
        f.write(content)

    return filename, filepath, len(content)


def _upload_and_index(file: UploadFile) -> dict[str, Any]:
    filename, filepath, size_bytes = _save_upload_file(file)

    try:
        result = ingest(filepath)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(exc)}") from exc

    record = create_document_record(
        filename=filename,
        filepath=filepath,
        size_bytes=size_bytes,
        ingest_result=result,
    )
    return upsert_document(record)


def _paginate(items: list[Any], page: int, limit: int) -> tuple[list[Any], int, int, int]:
    safe_page = max(int(page or 1), 1)
    safe_limit = max(min(int(limit or 25), 100), 1)
    total = len(items)
    start = (safe_page - 1) * safe_limit
    end = start + safe_limit
    total_pages = max((total + safe_limit - 1) // safe_limit, 1)
    return items[start:end], total, safe_page, total_pages


def _map_query_log(log: dict[str, Any]) -> dict[str, Any]:
    sources = log.get("sources") or []
    confidence = float(log.get("confidence") or 0.0)
    latency_ms = float(log.get("latency_ms") or 0.0)
    status = "ANSWERED" if sources or confidence >= 0.80 else "NOT_FOUND"

    return {
        "queryId": log.get("id", ""),
        "userName": log.get("user_name") or "User",
        "userQuestion": log.get("question", ""),
        "timestamp": log.get("timestamp") or _now_iso(),
        "retrievedDocuments": [
            {
                "documentName": source.get("documentName") or source.get("document_name") or "-",
                "page": (
                    str(source.get("page"))
                    if source.get("page") not in (None, "", "-")
                    else ""
                ),
                "chunkId": source.get("chunkId") or source.get("chunk_id") or "-",
                "relevanceScore": float(source.get("relevanceScore") or source.get("score") or 0.0),
                "excerpt": source.get("excerpt") or "",
                "section": source.get("section"),
                "paragraphStart": source.get("paragraph_start") or source.get("paragraphStart"),
                "paragraphEnd": source.get("paragraph_end") or source.get("paragraphEnd"),
                "lineStart": source.get("line_start") or source.get("lineStart"),
                "lineEnd": source.get("line_end") or source.get("lineEnd"),
            }
            for source in sources
        ],
        "answerGenerated": log.get("answer", ""),
        "confidenceScore": confidence,
        "responseTime": f"{latency_ms / 1000:.2f}s",
        "status": status,
    }


def _filter_logs(
    current_user: dict[str, str],
    range_value: str | None = None,
    status: str | None = None,
    search: str | None = None,
) -> list[dict[str, Any]]:
    mapped = [
        _map_query_log(log)
        for log in reversed(
            get_logs(
                user_id=current_user["id"],
                include_all=_can_admin(current_user),
            )
        )
    ]
    search_lower = (search or "").strip().lower()

    filtered = []
    for log in mapped:
        if status and log.get("status") != status:
            continue
        if search_lower and search_lower not in log.get("userQuestion", "").lower():
            continue
        filtered.append(log)

    return filtered


@router.post("/auth/login")
def compat_login(payload: LoginPayload):
    username = _normalize_username(payload.username)
    password = payload.password or ""

    user = DEV_USERS.get(username)
    if not user or password != user["password"]:
        raise HTTPException(
            status_code=401,
            detail="Username atau password salah.",
        )

    return {
        "token": _build_token(username),
        "user": _public_user(user),
    }


@router.get("/auth/me")
def compat_current_user(request: Request):
    user = _token_to_user(_get_bearer_token(request))
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sesi tidak valid atau sudah berakhir.",
        )

    return {
        "user": _public_user(user),
    }


@router.get("/health")
def compat_health():
    return {"status": "ok"}


@router.post("/chat")
async def compat_chat(request: Request):
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        question = str(form.get("message") or form.get("question") or "").strip()
        conversation_id = str(form.get("conversationId") or "").strip() or None
        language = str(form.get("language") or "ID").strip() or "ID"
    else:
        payload = await request.json()
        question = str(payload.get("message") or payload.get("question") or "").strip()
        conversation_id = payload.get("conversationId") or None
        language = payload.get("language") or "ID"

    if not question:
        raise HTTPException(status_code=400, detail="Message is required")

    current_user = _require_user(request)

    try:
        result = run_chat(
            question,
            top_k=5,
            language=language,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc

    answer = result["answer"]
    sources = result["sources"]
    confidence = result["confidence"]
    response_time_ms = result["response_time_ms"]
    follow_up_question = result.get("follow_up_question")

    save_log(
        question=question,
        answer=answer,
        sources=sources,
        latency_ms=response_time_ms,
        confidence=confidence,
        user_id=current_user["id"],
        user_name=current_user["name"],
        user_role=current_user["role"],
    )
    conversation, assistant_message = append_chat_turn(
        question=question,
        answer=answer,
        confidence=confidence,
        sources=sources,
        conversation_id=conversation_id,
        language=language,
        user_id=current_user["id"],
        user_name=current_user["name"],
        follow_up_question=follow_up_question,
    )

    primary_source = sources[0] if sources else None

    return {
        # Compatibility identifiers are kept until the frontend migration step.
        "conversationId": conversation["id"],
        "messageId": assistant_message["id"],
        # Canonical chat response contract.
        "answer": answer,
        "confidence": confidence,
        "sources": sources,
        "follow_up_question": follow_up_question,
        "followUpQuestion": follow_up_question,
        "response_time_ms": response_time_ms,
        # Temporary compatibility fields used by the current frontend.
        "source": primary_source.get("document_name") if primary_source else None,
        "page": primary_source.get("page") if primary_source else None,
        "createdAt": assistant_message["created_at"],
        "language": language,
    }


@router.get("/conversations")
def compat_list_conversations(request: Request):
    current_user = _require_user(request)
    return list_summaries(user_id=current_user["id"])


@router.get("/conversations/{conversation_id}")
def compat_get_conversation(conversation_id: str, request: Request):
    current_user = _require_user(request)
    conversation = get_conversation(conversation_id, user_id=current_user["id"])
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "conversation": {
            "id": conversation.get("id"),
            "title": conversation.get("title"),
            "language": conversation.get("language", "ID"),
            "is_pinned": conversation.get("is_pinned", False),
            "pinned": conversation.get("pinned", False),
            "last_message": conversation.get("last_message", ""),
            "last_user_message": conversation.get("last_user_message", ""),
            "last_message_at": conversation.get("last_message_at"),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
        },
        "messages": conversation.get("messages", []),
    }


@router.patch("/conversations/{conversation_id}")
def compat_update_conversation(conversation_id: str, payload: ConversationUpdatePayload, request: Request):
    current_user = _require_user(request)
    updated = update_conversation(
        conversation_id,
        payload.model_dump(exclude_none=True),
        user_id=current_user["id"],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return {
        "id": updated.get("id"),
        "title": updated.get("title"),
        "language": updated.get("language", "ID"),
        "is_pinned": updated.get("is_pinned", False),
        "pinned": updated.get("pinned", False),
        "last_message": updated.get("last_message", ""),
        "last_user_message": updated.get("last_user_message", ""),
        "last_message_at": updated.get("last_message_at"),
        "created_at": updated.get("created_at"),
        "updated_at": updated.get("updated_at"),
    }


@router.delete("/conversations/{conversation_id}")
def compat_delete_conversation(conversation_id: str, request: Request):
    current_user = _require_user(request)
    deleted = delete_conversation(conversation_id, user_id=current_user["id"])
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"message": "Conversation deleted"}


@router.get("/admin/documents")
def compat_get_documents(
    search: str | None = None,
    page: int = 1,
    limit: int = 10,
    status: str | None = None,
    type: str | None = None,
):
    documents = [to_repository_document(doc) for doc in filter_documents(search=search, doc_type=type, status=status)]
    page_items, total, safe_page, total_pages = _paginate(documents, page, limit)
    return {
        "documents": page_items,
        "total": total,
        "page": safe_page,
        "limit": max(min(int(limit or 10), 100), 1),
        "totalPages": total_pages,
    }


@router.post("/admin/documents")
async def compat_upload_documents(files: list[UploadFile] = File(...)):
    records = [_upload_and_index(file) for file in files]
    return {
        "message": f"{len(records)} dokumen berhasil diupload dan di-index.",
        "uploadItems": [to_upload_item(record) for record in records],
    }


@router.get("/admin/documents/uploads")
def compat_upload_queue():
    return [to_upload_item(doc) for doc in read_documents()]


@router.get("/admin/documents/trained")
def compat_trained_documents():
    documents = [doc for doc in read_documents() if int(doc.get("chunks") or 0) > 0]
    return {
        "documents": [to_trained_document(doc) for doc in documents],
        "total": len(documents),
    }


@router.post("/admin/documents/index")
def compat_start_indexing(payload: IndexPayload | None = None):
    ids = set((payload.documentIds if payload else None) or [])
    documents = read_documents()
    selected = [doc for doc in documents if not ids or doc.get("id") in ids]
    return {
        "message": "Dokumen sudah diproses oleh Python RAG pipeline.",
        "uploadItems": [to_upload_item(doc) for doc in selected],
    }


@router.get("/admin/documents/{document_id}/status")
def compat_document_status(document_id: str):
    document = get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return to_upload_item(document)


@router.post("/admin/documents/{document_id}/reindex")
def compat_reindex_document(document_id: str):
    document = get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    filepath = document.get("filepath")
    if not filepath or not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Original uploaded file not found")

    try:
        result = ingest(filepath)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Re-index failed: {str(exc)}") from exc

    updated = create_document_record(
        filename=document.get("filename", os.path.basename(filepath)),
        filepath=filepath,
        size_bytes=int(document.get("sizeBytes") or os.path.getsize(filepath)),
        ingest_result=result,
    )
    updated["id"] = document_id
    upsert_document(updated)
    return to_upload_item(updated)


@router.delete("/admin/documents/{document_id}")
def compat_delete_document(document_id: str):
    document = delete_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    try:
        delete_document_chunks(document.get("filename", ""))
    except Exception:
        pass

    return None


@router.get("/admin/query-logs")
def compat_query_logs(
    request: Request,
    range: str | None = None,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    search: str | None = None,
):
    current_user = _require_user(request)
    logs = _filter_logs(current_user, range_value=range, status=status, search=search)
    page_items, total, safe_page, total_pages = _paginate(logs, page, limit)
    return {
        "logs": page_items,
        "total": total,
        "page": safe_page,
        "limit": max(min(int(limit or 25), 100), 1),
        "totalPages": total_pages,
    }


@router.get("/admin/query-logs/dashboard")
def compat_query_logs_dashboard(
    request: Request,
    range: str | None = None,
    page: int = 1,
    limit: int = 25,
    status: str | None = None,
    search: str | None = None,
):
    current_user = _require_user(request)
    logs = _filter_logs(current_user, range_value=range, status=status, search=search)
    page_items, total, safe_page, total_pages = _paginate(logs, page, limit)
    answered = len([log for log in logs if log["status"] == "ANSWERED"])
    not_found = len([log for log in logs if log["status"] == "NOT_FOUND"])
    errors = len([log for log in logs if log["status"] == "ERROR"])
    need_review = len([log for log in logs if log["status"] == "NEED_REVIEW"])
    avg_conf = sum(log["confidenceScore"] for log in logs) / len(logs) if logs else 0.0

    return {
        "logs": page_items,
        "performance": {
            "totalQueries": len(logs),
            "answered": answered,
            "notFound": not_found,
            "needReview": need_review,
            "errors": errors,
            "averageConfidence": round(avg_conf, 4),
            "averageResponseTime": 0.0,
        },
        "total": total,
        "page": safe_page,
        "limit": max(min(int(limit or 25), 100), 1),
        "totalPages": total_pages,
    }


@router.get("/admin/query-logs/{query_id}")
def compat_query_log_detail(query_id: str, request: Request):
    current_user = _require_user(request)
    for log in _filter_logs(current_user):
        if log["queryId"] == query_id:
            return log
    raise HTTPException(status_code=404, detail="Query log not found")


@router.delete("/admin/query-logs/{query_id}")
def compat_delete_query_log(query_id: str, request: Request):
    current_user = _require_user(request)
    deleted = delete_log(
        query_id,
        user_id=current_user["id"],
        include_all=_can_admin(current_user),
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Query log not found")
    return None


def _logs_for_dashboard_user(current_user: dict[str, str]) -> list[dict[str, Any]]:
    return get_logs(
        user_id=current_user["id"],
        include_all=_can_admin(current_user),
    )


@router.get("/admin/dashboard")
def compat_dashboard(
    request: Request,
    range: str = "daily",
    documentSearch: str | None = None,
    documentPage: int = 1,
    documentLimit: int = 5,
):
    current_user = _require_user(request)
    logs = _logs_for_dashboard_user(current_user)
    summary = _dashboard_summary(logs)
    analytics = _chat_analytics(range, logs)
    docs = [to_repository_document(doc) for doc in filter_documents(search=documentSearch)]
    page_docs, _, _, _ = _paginate(docs, documentPage, documentLimit)

    return {
        "summary": summary,
        "chatSummary": _chat_summary(analytics),
        "analytics": analytics,
        "documents": page_docs,
        "ragConfig": public_rag_config(),
    }


@router.get("/admin/dashboard/summary")
def compat_dashboard_summary(request: Request):
    current_user = _require_user(request)
    return _dashboard_summary(_logs_for_dashboard_user(current_user))


@router.get("/admin/dashboard/chat-analytics")
def compat_dashboard_analytics(request: Request, range: str = "daily"):
    current_user = _require_user(request)
    return _chat_analytics(range, _logs_for_dashboard_user(current_user))


def _dashboard_summary(logs: list[dict[str, Any]]) -> dict[str, Any]:
    documents = read_documents()

    # ChromaDB is the authoritative source for the number of indexed chunks.
    # documents_store.json may contain an older per-document chunk count after
    # a bulk re-index, so use it only as a fallback when ChromaDB is unavailable.
    stored_total_chunks = sum(
        int(document.get("chunks") or 0)
        for document in documents
    )

    try:
        total_chunks = int(get_collection().count())
    except Exception:
        total_chunks = stored_total_chunks

    avg_latency = (
        sum(float(log.get("latency_ms") or 0.0) for log in logs) / len(logs)
        if logs
        else 0.0
    )
    unique_users = {
        str(log.get("user_id") or "dev-admin")
        for log in logs
    }

    return {
        "totalDocuments": len(documents),
        "totalChunks": total_chunks,
        "averageResponseTime": round(avg_latency / 1000, 2),
        "totalChats": len(logs),
        "totalUniqueUsers": len(unique_users),
    }


def _chat_analytics(range_value: str = "daily", logs: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    # Lightweight analytics for the frontend chart. It groups visible chats by date.
    counts: dict[str, int] = {}
    unique_users_by_label: dict[str, set[str]] = {}

    for log in logs or []:
        timestamp = str(log.get("timestamp") or "")
        label = timestamp[:10] if len(timestamp) >= 10 else "Unknown"
        counts[label] = counts.get(label, 0) + 1
        unique_users_by_label.setdefault(label, set()).add(str(log.get("user_id") or "dev-admin"))

    if not counts:
        return []

    return [
        {
            "label": label,
            "totalChats": total,
            "uniqueUsers": len(unique_users_by_label.get(label, set())),
        }
        for label, total in sorted(counts.items())
    ]


def _chat_summary(analytics: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(item["totalChats"] for item in analytics)
    peak = max(analytics, key=lambda item: item["totalChats"], default={"label": "-", "totalChats": 0})
    average = total / len(analytics) if analytics else 0.0

    return {
        "totalChatCount": total,
        "totalUniqueUsers": 1 if total else 0,
        "averageChatCount": round(average, 2),
        "peakLabel": peak.get("label", "-"),
        "peakTotalChats": peak.get("totalChats", 0),
    }
