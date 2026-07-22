import json
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
    delete_conversations,
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
from api.auth_tokens import create_auth_token, resolve_auth_token
from api.chat_service import run_chat
from api.logger import delete_log, get_logs, resolve_query_log_status, save_log
from api.user_store import (
    UserStoreError,
    authenticate_user,
    create_staff_user,
    delete_user,
    get_user_by_id,
    normalize_username,
    public_user,
    read_users,
    update_user_password,
)
from ingestion.indexer import delete_document_chunks, get_collection
from uploads.config import UPLOAD_DIR, public_rag_config
from uploads.ingest import ingest

router = APIRouter()

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 25 * 1024 * 1024
os.makedirs(UPLOAD_DIR, exist_ok=True)


class LoginPayload(BaseModel):
    username: str = "admin"
    password: str = "admin"


class StaffCreatePayload(BaseModel):
    username: str
    name: str
    password: str


class StaffPasswordPayload(BaseModel):
    password: str


class IndexPayload(BaseModel):
    documentIds: list[str] | None = None


class ConversationUpdatePayload(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    language: str | None = None


class ConversationDeleteManyPayload(BaseModel):
    conversationIds: list[str]


class QueryLogParams(BaseModel):
    range: str | None = None
    page: int = 1
    limit: int = 25
    status: str | None = None
    search: str | None = None


class QueryFailurePayload(BaseModel):
    queryId: str
    question: str
    reason: str = "CLIENT_ERROR"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()



def _token_to_user(token: str | None) -> dict[str, Any] | None:
    return resolve_auth_token(token)


def _get_bearer_token(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        return authorization.split(" ", 1)[1].strip()
    return None


def _require_user(request: Request) -> dict[str, Any]:
    user = _token_to_user(_get_bearer_token(request))
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Sesi tidak valid atau sudah berakhir.",
        )
    return user


def _can_admin(user: dict[str, Any]) -> bool:
    return user.get("role") == "admin"


def _require_admin(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    if not _can_admin(user):
        raise HTTPException(
            status_code=403,
            detail="Only administrators can access staff management.",
        )
    return user


def _staff_management_user(
    user: dict[str, Any],
    chat_totals: dict[str, int],
) -> dict[str, Any]:
    user_id = str(user.get("id") or "")
    return {
        **public_user(user),
        "totalChats": chat_totals.get(user_id, 0),
        "createdAt": str(user.get("created_at") or ""),
        "updatedAt": str(user.get("updated_at") or ""),
    }


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    return name or f"document_{uuid.uuid4().hex}.txt"


def _normalize_filename(filename: str) -> str:
    return _safe_filename(filename).casefold()


def _documents_with_filename(filename: str) -> list[dict[str, Any]]:
    normalized_name = _normalize_filename(filename)
    return [
        document
        for document in read_documents()
        if _normalize_filename(str(document.get("filename") or "")) == normalized_name
    ]


def _save_upload_file(
    file: UploadFile,
    *,
    allow_overwrite: bool = False,
) -> tuple[str, str, int]:
    filename = _safe_filename(file.filename or "")
    ext = os.path.splitext(filename)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    content = file.file.read()

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail="File size exceeds 25 MB limit")

    filepath = os.path.join(UPLOAD_DIR, filename)

    if (
        os.path.exists(filepath)
        or _documents_with_filename(filename)
    ) and not allow_overwrite:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Dokumen "{filename}" sudah ada. '
                "Konfirmasi penimpaan sebelum mengunggah file baru."
            ),
        )

    with open(filepath, "wb") as f:
        f.write(content)

    return filename, filepath, len(content)


def _upload_and_index(
    file: UploadFile,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    requested_filename = _safe_filename(file.filename or "")
    existing_documents = _documents_with_filename(requested_filename)
    existing_file_backups: dict[str, bytes] = {}

    if existing_documents and not replace_existing:
        raise HTTPException(
            status_code=409,
            detail=(
                f'Dokumen "{requested_filename}" sudah ada. '
                "Upload dibatalkan karena belum ada persetujuan untuk menimpa file lama."
            ),
        )

    if replace_existing:
        for existing_document in existing_documents:
            old_filepath = str(existing_document.get("filepath") or "")
            if old_filepath and os.path.exists(old_filepath):
                try:
                    with open(old_filepath, "rb") as old_file:
                        existing_file_backups[old_filepath] = old_file.read()
                except OSError:
                    pass

        canonical_filepath = os.path.join(UPLOAD_DIR, requested_filename)
        if (
            canonical_filepath not in existing_file_backups
            and os.path.exists(canonical_filepath)
        ):
            try:
                with open(canonical_filepath, "rb") as old_file:
                    existing_file_backups[canonical_filepath] = old_file.read()
            except OSError:
                pass

    filename, filepath, size_bytes = _save_upload_file(
        file,
        allow_overwrite=replace_existing,
    )

    if (
        replace_existing
        and filepath not in existing_file_backups
        and os.path.exists(filepath)
    ):
        # The new file has already been written. This marker lets the rollback
        # remove it when no previous file existed at the canonical path.
        existing_file_backups.setdefault(filepath, b"")

    if replace_existing:
        for existing_document in existing_documents:
            old_filename = str(existing_document.get("filename") or "")
            if old_filename and old_filename != filename:
                delete_document_chunks(old_filename)

    try:
        result = ingest(filepath)
    except Exception as exc:
        if replace_existing:
            for backup_path, backup_content in existing_file_backups.items():
                try:
                    if backup_content:
                        with open(backup_path, "wb") as backup_file:
                            backup_file.write(backup_content)
                    elif os.path.exists(backup_path):
                        os.remove(backup_path)
                except OSError:
                    pass

            restore_document = next(
                (
                    document
                    for document in existing_documents
                    if str(document.get("filepath") or "")
                    and os.path.exists(str(document.get("filepath") or ""))
                ),
                None,
            )
            if restore_document:
                try:
                    ingest(str(restore_document.get("filepath")))
                except Exception:
                    pass

        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(exc)}") from exc

    record = create_document_record(
        filename=filename,
        filepath=filepath,
        size_bytes=size_bytes,
        ingest_result=result,
    )

    if replace_existing and existing_documents:
        record["id"] = existing_documents[0].get("id") or record["id"]

        for existing_document in existing_documents:
            existing_id = str(existing_document.get("id") or "")
            old_filepath = str(existing_document.get("filepath") or "")

            if existing_id:
                delete_document(existing_id)

            if old_filepath and old_filepath != filepath and os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except OSError:
                    pass

    return upsert_document(record)


def _resolve_pagination_limit(total: int, limit: int | None, default: int = 25) -> int:
    """Return the requested page size without an artificial upper cap.

    A limit of 0 (or a negative value) means: return every matching item.
    """
    requested_limit = default if limit is None else int(limit)
    if requested_limit <= 0:
        return max(total, 1)
    return requested_limit


def _paginate(items: list[Any], page: int, limit: int) -> tuple[list[Any], int, int, int]:
    safe_page = max(int(page or 1), 1)
    total = len(items)
    safe_limit = _resolve_pagination_limit(total, limit)
    start = (safe_page - 1) * safe_limit
    end = start + safe_limit
    total_pages = max((total + safe_limit - 1) // safe_limit, 1)
    return items[start:end], total, safe_page, total_pages


def _map_query_log(log: dict[str, Any]) -> dict[str, Any]:
    sources = log.get("sources") or []
    confidence = float(log.get("confidence") or 0.0)
    latency_ms = float(log.get("latency_ms") or 0.0)
    status = resolve_query_log_status(
        log.get("answer"),
        sources,
        log.get("status"),
    )

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
    username = normalize_username(payload.username)
    password = payload.password or ""

    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Username atau password salah.",
        )

    return {
        "token": create_auth_token(user),
        "user": public_user(user),
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
        "user": public_user(user),
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
        query_id = str(form.get("queryId") or "").strip() or None
        model = str(form.get("model") or "").strip() or None
    else:
        payload = await request.json()
        question = str(payload.get("message") or payload.get("question") or "").strip()
        conversation_id = payload.get("conversationId") or None
        language = payload.get("language") or "ID"
        query_id = str(payload.get("queryId") or "").strip() or None
        model = str(payload.get("model") or "").strip() or None

    if not question:
        raise HTTPException(status_code=400, detail="Message is required")

    current_user = _require_user(request)
    started_at = time.perf_counter()

    try:
        result = run_chat(
            question,
            top_k=5,
            language=language,
            model=model,
        )
    except Exception as exc:
        save_log(
            query_id=query_id,
            question=question,
            answer="",
            sources=[],
            latency_ms=(time.perf_counter() - started_at) * 1000,
            confidence=0.0,
            status="NOT_FOUND",
            failure_reason="SERVER_ERROR",
            user_id=current_user["id"],
            user_name=current_user["name"],
            user_role=current_user["role"],
        )
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(exc)}") from exc

    answer = str(result.get("answer") or "")
    sources = result.get("sources") or []
    confidence = result.get("confidence") or 0.0
    response_time_ms = result.get("response_time_ms") or ((time.perf_counter() - started_at) * 1000)
    follow_up_question = result.get("follow_up_question")

    save_log(
        query_id=query_id,
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
        "model": result.get("model"),
    }


@router.post("/query-logs/failure")
def compat_record_query_failure(payload: QueryFailurePayload, request: Request):
    current_user = _require_user(request)
    reason = str(payload.reason or "CLIENT_ERROR").strip().upper()

    log = save_log(
        query_id=payload.queryId,
        question=payload.question,
        answer="",
        sources=[],
        latency_ms=0.0,
        confidence=0.0,
        status="NOT_FOUND",
        failure_reason=reason,
        user_id=current_user["id"],
        user_name=current_user["name"],
        user_role=current_user["role"],
    )

    return {"status": "recorded", "queryId": log["id"]}


@router.get("/conversations")
def compat_list_conversations(request: Request):
    current_user = _require_user(request)
    return list_summaries(user_id=current_user["id"])


@router.post("/conversations/bulk-delete")
def compat_delete_conversations(
    payload: ConversationDeleteManyPayload,
    request: Request,
):
    current_user = _require_user(request)
    conversation_ids = list(dict.fromkeys(
        str(conversation_id).strip()
        for conversation_id in payload.conversationIds
        if str(conversation_id).strip()
    ))

    if not conversation_ids:
        raise HTTPException(
            status_code=400,
            detail="Choose at least one conversation to delete.",
        )

    deleted_ids = delete_conversations(
        conversation_ids,
        user_id=current_user["id"],
    )

    return {
        "message": f"{len(deleted_ids)} conversation(s) deleted",
        "deletedIds": deleted_ids,
        "deletedCount": len(deleted_ids),
    }


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


@router.get("/admin/users")
def compat_list_staff_users(request: Request):
    _require_admin(request)
    chat_totals: dict[str, int] = {}
    for log in get_logs(include_all=True):
        user_id = str(log.get("user_id") or "dev-admin")
        chat_totals[user_id] = chat_totals.get(user_id, 0) + 1

    users = sorted(
        read_users(),
        key=lambda user: (
            0 if str(user.get("role") or "") == "admin" else 1,
            str(user.get("name") or "").casefold(),
        ),
    )
    items = [
        _staff_management_user(user, chat_totals)
        for user in users
    ]
    return {
        "users": items,
        "total": len(items),
        "totalChats": sum(chat_totals.values()),
    }


@router.post("/admin/users")
def compat_create_staff_user(payload: StaffCreatePayload, request: Request):
    _require_admin(request)
    try:
        user = create_staff_user(
            username=payload.username,
            name=payload.name,
            password=payload.password,
        )
    except UserStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return _staff_management_user(user, {})


@router.patch("/admin/users/{user_id}/password")
def compat_update_staff_password(
    user_id: str,
    payload: StaffPasswordPayload,
    request: Request,
):
    _require_admin(request)
    target_user = get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if str(target_user.get("role") or "") == "admin":
        raise HTTPException(
            status_code=400,
            detail="Administrator passwords cannot be changed from Staff Management.",
        )

    try:
        updated_user = update_user_password(user_id, payload.password)
    except UserStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not updated_user:
        raise HTTPException(status_code=404, detail="User account not found.")

    return {
        "message": "Password updated successfully.",
        "user": public_user(updated_user),
    }


@router.delete("/admin/users/{user_id}")
def compat_delete_staff_user(user_id: str, request: Request):
    current_user = _require_admin(request)
    target_user = get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=404, detail="User account not found.")

    if str(target_user.get("id") or "") == str(current_user.get("id") or ""):
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    if str(target_user.get("role") or "") == "admin":
        raise HTTPException(status_code=400, detail="Administrator accounts cannot be deleted here.")

    deleted = delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="User account not found.")

    return None


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
        "limit": _resolve_pagination_limit(total, limit, default=10),
        "totalPages": total_pages,
    }


@router.post("/admin/documents")
async def compat_upload_documents(
    files: list[UploadFile] = File(...),
    replaceFilenamesJson: str = Form("[]"),
):
    try:
        raw_replace_filenames = json.loads(replaceFilenamesJson or "[]")
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Format konfirmasi penimpaan file tidak valid.",
        ) from exc

    if not isinstance(raw_replace_filenames, list):
        raise HTTPException(
            status_code=400,
            detail="Daftar file yang akan ditimpa harus berupa array.",
        )

    replace_filenames = {
        _normalize_filename(str(filename))
        for filename in raw_replace_filenames
        if str(filename).strip()
    }

    incoming_names = [
        _safe_filename(file.filename or "")
        for file in files
    ]
    normalized_incoming_names = [
        _normalize_filename(filename)
        for filename in incoming_names
    ]

    repeated_names = sorted({
        filename
        for filename in normalized_incoming_names
        if normalized_incoming_names.count(filename) > 1
    })
    if repeated_names:
        raise HTTPException(
            status_code=400,
            detail=(
                "Satu proses upload tidak boleh berisi beberapa file "
                "dengan nama yang sama."
            ),
        )

    existing_names = {
        _normalize_filename(str(document.get("filename") or ""))
        for document in read_documents()
    }
    unauthorized_duplicates = [
        filename
        for filename, normalized_name in zip(
            incoming_names,
            normalized_incoming_names,
        )
        if normalized_name in existing_names
        and normalized_name not in replace_filenames
    ]

    if unauthorized_duplicates:
        duplicate_list = ", ".join(unauthorized_duplicates)
        raise HTTPException(
            status_code=409,
            detail=(
                f"File berikut sudah ada: {duplicate_list}. "
                "Upload dibatalkan karena admin belum menyetujui penimpaan."
            ),
        )

    records = [
        _upload_and_index(
            file,
            replace_existing=(
                _normalize_filename(file.filename or "")
                in replace_filenames
            ),
        )
        for file in files
    ]
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
        "limit": _resolve_pagination_limit(total, limit),
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
    no_reference = len([log for log in logs if log["status"] == "NO_REFERENCE"])
    not_found = len([log for log in logs if log["status"] == "NOT_FOUND"])
    answered_logs = [log for log in logs if log["status"] == "ANSWERED"]
    avg_conf = (
        sum(log["confidenceScore"] for log in answered_logs) / len(answered_logs)
        if answered_logs
        else 0.0
    )

    return {
        "logs": page_items,
        "performance": {
            "totalQueries": len(logs),
            "answered": answered,
            "noReference": no_reference,
            "notFound": not_found,
            "averageConfidence": round(avg_conf, 4),
            "averageResponseTime": 0.0,
        },
        "total": total,
        "page": safe_page,
        "limit": _resolve_pagination_limit(total, limit),
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
