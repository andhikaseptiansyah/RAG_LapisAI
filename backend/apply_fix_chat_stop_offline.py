from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

STAMP = datetime.now().strftime('%Y%m%d_%H%M%S')


def locate_root() -> tuple[Path, Path]:
    cwd = Path.cwd().resolve()
    candidates = [cwd, cwd.parent]
    for root in candidates:
        backend = root / 'backend'
        if backend.is_dir() and (root / 'src').is_dir():
            return root, backend
    if cwd.name == 'backend' and (cwd.parent / 'src').is_dir():
        return cwd.parent, cwd
    raise SystemExit(
        'Jalankan script dari folder project RAG_LapisAI atau dari folder backend.'
    )


def backup(path: Path) -> None:
    if not path.exists():
        return
    target = path.with_name(path.name + f'.backup_cancel_{STAMP}')
    shutil.copy2(path, target)
    print(f'       backup: {target}')


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    backup(path)
    path.write_text(content, encoding='utf-8')
    print(f'[OK]   {path}')


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text:
        print(f'[SKIP] {label}: sudah terpasang')
        return text
    if old not in text:
        raise RuntimeError(f'Pola tidak ditemukan untuk {label}')
    return text.replace(old, new, 1)


def patch_routes(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text

    if 'import asyncio' not in text:
        text = text.replace('import json\n', 'import asyncio\nimport contextlib\nimport json\n', 1)

    cancellation_import = (
        'from api.cancellation import (\n'
        '    ChatCancelled,\n'
        '    cancel_query,\n'
        '    raise_if_cancelled,\n'
        '    register_query,\n'
        '    unregister_query,\n'
        ')\n'
    )
    if 'from api.cancellation import (' not in text:
        marker = 'from api.build_info import BUILD_VERSION, public_build_info\n'
        text = text.replace(marker, marker + cancellation_import, 1)

    start = text.find('@router.post("/chat")')
    end = text.find('@router.post("/query-logs/failure")', start)
    if start < 0 or end < 0:
        raise RuntimeError('Route /chat atau /query-logs/failure tidak ditemukan.')

    new_chat_route = '''async def _watch_chat_disconnect(request: Request, cancel_event) -> None:
    """Batalkan pekerjaan server ketika browser memutus request."""
    while not cancel_event.is_set():
        if await request.is_disconnected():
            cancel_event.set()
            return
        await asyncio.sleep(0.10)


@router.post("/chat")
async def compat_chat(request: Request):
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        question = str(form.get("message") or form.get("question") or "").strip()
        conversation_id = str(form.get("conversationId") or "").strip() or None
        language = str(form.get("language") or "AUTO").strip() or "AUTO"
        query_id = str(form.get("queryId") or "").strip() or str(uuid.uuid4())
        model = str(form.get("model") or "").strip() or None
    else:
        payload = await request.json()
        question = str(payload.get("message") or payload.get("question") or "").strip()
        conversation_id = payload.get("conversationId") or None
        language = payload.get("language") or "AUTO"
        query_id = str(payload.get("queryId") or "").strip() or str(uuid.uuid4())
        model = str(payload.get("model") or "").strip() or None

    if not question:
        raise HTTPException(status_code=400, detail="Pesan wajib diisi.")

    current_user = _require_user(request)
    started_at = time.perf_counter()
    cancel_event = register_query(query_id, current_user["id"])
    disconnect_task = asyncio.create_task(
        _watch_chat_disconnect(request, cancel_event)
    )

    try:
        # run_chat bersifat sinkron dan berat. Jalankan di worker thread agar
        # event loop tetap bisa menerima endpoint pembatalan.
        result = await asyncio.to_thread(
            run_chat,
            question,
            top_k=5,
            language=language,
            model=model,
            cancel_event=cancel_event,
        )
        raise_if_cancelled(cancel_event)

        answer = str(result.get("answer") or "")
        sources = result.get("sources") or []
        confidence = result.get("confidence") or 0.0
        response_time_ms = result.get("response_time_ms") or ((time.perf_counter() - started_at) * 1000)
        follow_up_question = result.get("follow_up_question")
        resolved_language = str(result.get("language") or language or "ID").upper()

        # Jangan simpan hasil atau percakapan bila stop terjadi sesaat setelah
        # model selesai tetapi sebelum response dikirim ke browser.
        raise_if_cancelled(cancel_event)
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
        raise_if_cancelled(cancel_event)
        conversation, assistant_message = append_chat_turn(
            question=question,
            answer=answer,
            confidence=confidence,
            sources=sources,
            conversation_id=conversation_id,
            language=resolved_language,
            user_id=current_user["id"],
            user_name=current_user["name"],
            follow_up_question=follow_up_question,
        )
        raise_if_cancelled(cancel_event)

        primary_source = sources[0] if sources else None
        return {
            "conversationId": conversation["id"],
            "messageId": assistant_message["id"],
            "answer": answer,
            "confidence": confidence,
            "sources": sources,
            "follow_up_question": follow_up_question,
            "followUpQuestion": follow_up_question,
            "response_time_ms": response_time_ms,
            "source": primary_source.get("document_name") if primary_source else None,
            "page": primary_source.get("page") if primary_source else None,
            "createdAt": assistant_message["created_at"],
            "language": resolved_language,
            "model": result.get("model"),
            "generation_mode": result.get("generation_mode"),
            "buildVersion": result.get("buildVersion") or BUILD_VERSION,
            "chatServiceSha256": public_build_info().get("chatServiceSha256"),
            "retrieval_mode": result.get("retrieval_mode"),
            "retrieval_query": result.get("retrieval_query"),
            "failure_stage": result.get("failure_stage"),
        }
    except ChatCancelled:
        save_log(
            query_id=query_id,
            question=question,
            answer="",
            sources=[],
            latency_ms=(time.perf_counter() - started_at) * 1000,
            confidence=0.0,
            status="NOT_FOUND",
            failure_reason="USER_STOPPED",
            user_id=current_user["id"],
            user_name=current_user["name"],
            user_role=current_user["role"],
        )
        raise HTTPException(
            status_code=499,
            detail={
                "code": "CHAT_CANCELLED",
                "message": "Permintaan dihentikan oleh pengguna.",
            },
        )
    except asyncio.CancelledError:
        cancel_event.set()
        save_log(
            query_id=query_id,
            question=question,
            answer="",
            sources=[],
            latency_ms=(time.perf_counter() - started_at) * 1000,
            confidence=0.0,
            status="NOT_FOUND",
            failure_reason="CLIENT_DISCONNECTED",
            user_id=current_user["id"],
            user_name=current_user["name"],
            user_role=current_user["role"],
        )
        raise
    except HTTPException:
        raise
    except Exception as exc:
        if cancel_event.is_set():
            save_log(
                query_id=query_id,
                question=question,
                answer="",
                sources=[],
                latency_ms=(time.perf_counter() - started_at) * 1000,
                confidence=0.0,
                status="NOT_FOUND",
                failure_reason="USER_STOPPED",
                user_id=current_user["id"],
                user_name=current_user["name"],
                user_role=current_user["role"],
            )
            raise HTTPException(
                status_code=499,
                detail={
                    "code": "CHAT_CANCELLED",
                    "message": "Permintaan dihentikan.",
                },
            ) from exc

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
        raise HTTPException(status_code=500, detail=f"Proses chat gagal: {str(exc)}") from exc
    finally:
        disconnect_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await disconnect_task
        unregister_query(query_id, current_user["id"], cancel_event)


'''
    text = text[:start] + new_chat_route + text[end:]

    failure_start = text.find('@router.post("/query-logs/failure")')
    failure_end = text.find('@router.get("/conversations")', failure_start)
    if failure_start < 0 or failure_end < 0:
        raise RuntimeError('Blok query failure tidak ditemukan.')

    new_failure_route = '''@router.post("/query-logs/failure")\ndef compat_record_query_failure(payload: QueryFailurePayload, request: Request):\n    current_user = _require_user(request)\n    reason = str(payload.reason or "CLIENT_ERROR").strip().upper()\n\n    # USER_STOPPED dan NETWORK_OFFLINE bukan hanya status log. Keduanya juga\n    # mengirim sinyal pembatalan ke worker chat yang sedang aktif.\n    if reason in {"USER_STOPPED", "NETWORK_OFFLINE", "CLIENT_DISCONNECTED"}:\n        cancel_query(payload.queryId, current_user["id"])\n\n    log = save_log(\n        query_id=payload.queryId,\n        question=payload.question,\n        answer="",\n        sources=[],\n        latency_ms=0.0,\n        confidence=0.0,\n        status="NOT_FOUND",\n        failure_reason=reason,\n        user_id=current_user["id"],\n        user_name=current_user["name"],\n        user_role=current_user["role"],\n    )\n\n    return {"status": "recorded", "queryId": log["id"]}\n\n\n'''
    text = text[:failure_start] + new_failure_route + text[failure_end:]

    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_chat_service(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text

    if 'from api.cancellation import raise_if_cancelled' not in text:
        marker = 'from api.build_info import BUILD_VERSION\n'
        text = text.replace(marker, marker + 'from api.cancellation import raise_if_cancelled\n', 1)

    # Tambahkan parameter cancel_event tanpa merusak parameter lama.
    pattern = re.compile(
        r'(def run_chat\(\n\s+question: str,\n\s+\*,\n\s+top_k: int = 5,\n\s+language: str = "AUTO",\n\s+model: str \| None = None,\n\s+evaluation_mode: bool = False,\n)(\) -> dict\[str, Any\]:)'
    )
    if 'cancel_event: Any | None = None' not in text:
        text, count = pattern.subn(
            r'\1    cancel_event: Any | None = None,\n\2', text, count=1
        )
        if count != 1:
            raise RuntimeError('Signature run_chat tidak cocok.')

    text = replace_once(
        text,
        '    started_at = time.perf_counter()\n',
        '    started_at = time.perf_counter()\n    raise_if_cancelled(cancel_event)\n',
        'check awal chat',
    )
    text = replace_once(
        text,
        '    retrieved_chunks, retrieval_mode, retrieval_query = _retrieve_with_language_fallback(\n',
        '    raise_if_cancelled(cancel_event)\n    retrieved_chunks, retrieval_mode, retrieval_query = _retrieve_with_language_fallback(\n',
        'check sebelum retrieval',
    )
    text = replace_once(
        text,
        '    chunks = select_context_bundle(\n',
        '    raise_if_cancelled(cancel_event)\n    chunks = select_context_bundle(\n',
        'check sesudah retrieval',
    )
    text = replace_once(
        text,
        '    native_answer = answer_text_only(\n',
        '    raise_if_cancelled(cancel_event)\n    native_answer = answer_text_only(\n',
        'check sebelum model',
    )
    text = replace_once(
        text,
        '    answer = native_answer\n',
        '    raise_if_cancelled(cancel_event)\n    answer = native_answer\n',
        'check sesudah model',
    )
    text = replace_once(
        text,
        '    sources = build_sources(\n',
        '    raise_if_cancelled(cancel_event)\n    sources = build_sources(\n',
        'check sebelum sitasi',
    )
    text = replace_once(
        text,
        '    follow_up_question = build_dataset_follow_up_question(\n',
        '    raise_if_cancelled(cancel_event)\n    follow_up_question = build_dataset_follow_up_question(\n',
        'check sebelum follow-up',
    )
    # Tambahkan check ke jalur bridge agar tidak lanjut ke pass berikutnya.
    if 'raise_if_cancelled()\n    primary = hybrid_search' not in text:
        text = text.replace(
            '    primary = hybrid_search(question, top_k=requested_k)\n',
            '    raise_if_cancelled()\n    primary = hybrid_search(question, top_k=requested_k)\n',
            1,
        )
    if 'raise_if_cancelled()\n    bridge_candidates = hybrid_search' not in text:
        text = text.replace(
            '    bridge_candidates = hybrid_search(\n',
            '    raise_if_cancelled()\n    bridge_candidates = hybrid_search(\n',
            1,
        )
    if 'raise_if_cancelled()\n    raw_candidates = _base_hybrid_candidates' not in text:
        text = text.replace(
            '    raw_candidates = _base_hybrid_candidates(\n',
            '    raise_if_cancelled()\n    raw_candidates = _base_hybrid_candidates(\n',
            1,
        )

    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_model_router(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text
    if 'from api.cancellation import raise_if_cancelled' not in text:
        text = text.replace(
            'from api.ollama_client import build_ollama_grounded_answer\n',
            'from api.ollama_client import build_ollama_grounded_answer\nfrom api.cancellation import raise_if_cancelled\n',
            1,
        )
    if '    raise_if_cancelled()\n    answer = PROVIDERS[provider](' not in text:
        text = text.replace(
            '    answer = PROVIDERS[provider](\n',
            '    raise_if_cancelled()\n    answer = PROVIDERS[provider](\n',
            1,
        )
    if '    raise_if_cancelled()\n    if answer or evaluation_mode or provider == "ollama":' not in text:
        text = text.replace(
            '    if answer or evaluation_mode or provider == "ollama":\n',
            '    raise_if_cancelled()\n    if answer or evaluation_mode or provider == "ollama":\n',
            1,
        )
    if '    raise_if_cancelled()\n    print(\n        f"[MODEL_ROUTER]' not in text:
        text = text.replace(
            '    print(\n        f"[MODEL_ROUTER] provider={provider} returned no usable answer; "\n',
            '    raise_if_cancelled()\n    print(\n        f"[MODEL_ROUTER] provider={provider} returned no usable answer; "\n',
            1,
        )
    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_provider(path: Path, provider: str) -> None:
    text = path.read_text(encoding='utf-8')
    original = text
    if 'from api.cancellation import raise_if_cancelled' not in text:
        # first api import is a stable insertion location.
        marker = 'from api.answer_formatter import '
        idx = text.find(marker)
        if idx < 0:
            raise RuntimeError(f'Import marker tidak ditemukan pada {path}')
        text = text[:idx] + 'from api.cancellation import raise_if_cancelled\n' + text[idx:]

    if provider == 'groq':
        text = text.replace(
            '    for attempt in range(GROQ_MAX_RETRIES + 1):\n        try:\n',
            '    for attempt in range(GROQ_MAX_RETRIES + 1):\n        raise_if_cancelled()\n        try:\n',
            1,
        )
        text = text.replace(
            '            response = requests.post(\n',
            '            raise_if_cancelled()\n            response = requests.post(\n',
            1,
        )
        text = text.replace(
            '            if response.status_code == 429 or response.status_code >= 500:\n',
            '            raise_if_cancelled()\n            if response.status_code == 429 or response.status_code >= 500:\n',
            1,
        )
    elif provider == 'gemini':
        text = text.replace(
            '    with genai.Client(api_key=GEMINI_API_KEY) as client:\n',
            '    raise_if_cancelled()\n    with genai.Client(api_key=GEMINI_API_KEY) as client:\n',
            1,
        )
        text = text.replace(
            '    print(f"[GEMINI] model={GEMINI_MODEL} status=success")\n',
            '    raise_if_cancelled()\n    print(f"[GEMINI] model={GEMINI_MODEL} status=success")\n',
            1,
        )
    elif provider == 'ollama':
        text = text.replace(
            '    payload = {\n',
            '    raise_if_cancelled()\n    payload = {\n',
            1,
        )
        text = text.replace(
            '    with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:\n',
            '    raise_if_cancelled()\n    with urllib.request.urlopen(request, timeout=OLLAMA_TIMEOUT_SECONDS) as response:\n',
            1,
        )
        text = text.replace(
            '    message = data.get("message") or {}\n',
            '    raise_if_cancelled()\n    message = data.get("message") or {}\n',
            1,
        )
        text = text.replace(
            '        while retry_count < OLLAMA_MAX_RETRIES:\n',
            '        while retry_count < OLLAMA_MAX_RETRIES:\n            raise_if_cancelled()\n',
            1,
        )

    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_chat_service_ts(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text
    if "  | 'NETWORK_OFFLINE'" not in text:
        text = text.replace(
            "  | 'CLIENT_ERROR'\n  | 'EMPTY_RESPONSE';",
            "  | 'CLIENT_ERROR'\n  | 'NETWORK_OFFLINE'\n  | 'EMPTY_RESPONSE';",
            1,
        )
    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_use_chat(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text

    # Import the reason type.
    if 'QueryFailureReason,' not in text:
        text = text.replace(
            'import type {\n  ChatLanguage,\n} from \'../services/chatService\';',
            'import type {\n  ChatLanguage,\n  QueryFailureReason,\n} from \'../services/chatService\';',
            1,
        )

    offline_block = '''\n      if (\n        typeof navigator !== 'undefined' &&\n        !navigator.onLine\n      ) {\n        const queryId = createLocalId();\n        const selectedLanguage = languageOverride ?? language;\n        const userMessage: Message = {\n          id: queryId,\n          role: 'user',\n          content: normalizedContent,\n          time: getCurrentTime(),\n          attachments:\n            attachments.length > 0\n              ? attachments\n              : undefined,\n        };\n        const offlineMessage =\n          selectedLanguage === 'EN'\n            ? 'No internet connection. The request was stopped and no answer was generated.'\n            : 'Tidak ada koneksi internet. Permintaan dihentikan dan jawaban tidak dibuat.';\n\n        setMessages((currentMessages) => [\n          ...currentMessages,\n          userMessage,\n          {\n            id: createLocalId(),\n            role: 'system',\n            content: offlineMessage,\n            time: getCurrentTime(),\n          },\n        ]);\n        setError(offlineMessage);\n        return false;\n      }\n'''
    if 'Tidak ada koneksi internet. Permintaan dihentikan dan jawaban tidak dibuat.' not in text:
        marker = '''      if (\n        !normalizedContent &&\n        attachments.length === 0\n      ) {\n        return false;\n      }\n'''
        if marker not in text:
            raise RuntimeError('Marker validasi pesan useChat tidak ditemukan.')
        text = text.replace(marker, marker + offline_block, 1)

    race_guard = '''\n        // Abort fetch tidak selalu menang terhadap response yang tiba pada saat\n        // bersamaan. Jangan pernah menambahkan jawaban dari query yang sudah stop.\n        if (\n          controller.signal.aborted ||\n          activeQueryRef.current?.queryId !== queryId\n        ) {\n          return false;\n        }\n'''
    if 'Jangan pernah menambahkan jawaban dari query yang sudah stop.' not in text:
        marker = '''        const response = await sendChatMessage(\n          {\n            message: normalizedContent,\n            queryId,\n            conversationId,\n            language: selectedLanguage,\n            model,\n            attachments,\n          },\n          controller.signal\n        );\n'''
        if marker not in text:
            raise RuntimeError('Marker sendChatMessage tidak ditemukan.')
        text = text.replace(marker, marker + race_guard, 1)

    # Better failure reason when the connection disappears during fetch.
    old = '''          await recordQueryFailure(\n            queryId,\n            normalizedContent,\n            'CLIENT_ERROR'\n          );'''
    new = '''          await recordQueryFailure(\n            queryId,\n            normalizedContent,\n            caughtError instanceof ApiError &&\n              caughtError.code === 'NETWORK_ERROR'\n              ? 'NETWORK_OFFLINE'\n              : 'CLIENT_ERROR'\n          );'''
    if old in text and new not in text:
        text = text.replace(old, new, 1)

    # stopGenerating now accepts a reason and logs it before/alongside abort.
    pattern = re.compile(
        r'''  const stopGenerating = useCallback\(\(\) => \{\n    const activeQuery = activeQueryRef\.current;\n\n    abortControllerRef\.current\?\.abort\(\);\n    abortControllerRef\.current = null;\n    activeQueryRef\.current = null;\n    setIsGenerating\(false\);\n\n    if \(activeQuery\) \{\n      void recordQueryFailure\(\n        activeQuery\.queryId,\n        activeQuery\.question,\n        'USER_STOPPED'\n      \)\.catch\(\(loggingError\) => \{\n        console\.error\(\n          'Gagal mencatat query yang dihentikan pengguna:',\n          loggingError\n        \);\n      \}\);\n    \}\n  \}, \[\]\);'''
    )
    replacement = '''  const stopGenerating = useCallback((\n    reason: QueryFailureReason = 'USER_STOPPED'\n  ) => {\n    const activeQuery = activeQueryRef.current;\n\n    // Kirim sinyal pembatalan ke backend. Request ini memakai koneksi terpisah\n    // dari fetch chat yang akan di-abort.\n    if (activeQuery) {\n      void recordQueryFailure(\n        activeQuery.queryId,\n        activeQuery.question,\n        reason\n      ).catch((loggingError) => {\n        console.error(\n          'Gagal mencatat atau membatalkan query aktif:',\n          loggingError\n        );\n      });\n    }\n\n    abortControllerRef.current?.abort();\n    abortControllerRef.current = null;\n    activeQueryRef.current = null;\n    setIsGenerating(false);\n  }, []);'''
    if 'reason: QueryFailureReason = \'USER_STOPPED\'' not in text:
        text, count = pattern.subn(replacement, text, count=1)
        if count != 1:
            raise RuntimeError('Blok stopGenerating tidak cocok.')

    offline_effect = '''\n\n  useEffect(() => {\n    const handleOffline = () => {\n      if (!activeQueryRef.current) {\n        return;\n      }\n\n      stopGenerating('NETWORK_OFFLINE');\n      const message =\n        language === 'EN'\n          ? 'Internet connection was lost. The request was stopped and no answer was generated.'\n          : 'Koneksi internet terputus. Permintaan dihentikan dan jawaban tidak dibuat.';\n\n      setError(message);\n      setMessages((currentMessages) => [\n        ...currentMessages,\n        {\n          id: createLocalId(),\n          role: 'system',\n          content: message,\n          time: getCurrentTime(),\n        },\n      ]);\n    };\n\n    window.addEventListener('offline', handleOffline);\n    return () => window.removeEventListener('offline', handleOffline);\n  }, [language, stopGenerating]);\n'''
    if 'Koneksi internet terputus. Permintaan dihentikan dan jawaban tidak dibuat.' not in text:
        marker = '''  const clearChat = useCallback(() => {'''
        if marker not in text:
            raise RuntimeError('Marker clearChat tidak ditemukan.')
        text = text.replace(marker, offline_effect + '\n' + marker, 1)

    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def patch_app(path: Path) -> None:
    text = path.read_text(encoding='utf-8')
    original = text
    text = text.replace(
        "              '[ Generation Stopped by User ]',",
        "              'Permintaan dihentikan oleh pengguna. Jawaban tidak dibuat.',",
        1,
    )
    if text != original:
        write(path, text)
    else:
        print(f'[SKIP] {path}: tidak ada perubahan')


def main() -> None:
    root, backend = locate_root()
    print(f'Project root: {root}')

    cancellation_py = '''from __future__ import annotations\n\nimport threading\nimport time\nfrom contextlib import contextmanager\nfrom dataclasses import dataclass\nfrom typing import Iterator\n\n\nclass ChatCancelled(RuntimeError):\n    """Raised when a user or disconnected client cancels a chat request."""\n\n\n@dataclass\nclass _ActiveQuery:\n    user_id: str\n    event: threading.Event\n    created_at: float\n\n\n_LOCK = threading.RLock()\n_ACTIVE: dict[str, _ActiveQuery] = {}\n_PENDING: dict[str, tuple[str, float]] = {}\n_LOCAL = threading.local()\n_PENDING_TTL_SECONDS = 120.0\n\n\ndef _clean(value: object) -> str:\n    return str(value or "").strip()\n\n\ndef _purge_pending() -> None:\n    cutoff = time.monotonic() - _PENDING_TTL_SECONDS\n    stale = [key for key, (_, created_at) in _PENDING.items() if created_at < cutoff]\n    for key in stale:\n        _PENDING.pop(key, None)\n\n\ndef register_query(query_id: str, user_id: str) -> threading.Event:\n    query_key = _clean(query_id)\n    owner = _clean(user_id)\n    if not query_key:\n        raise ValueError("query_id wajib diisi")\n\n    with _LOCK:\n        _purge_pending()\n        existing = _ACTIVE.get(query_key)\n        if existing and existing.user_id == owner:\n            return existing.event\n\n        event = threading.Event()\n        pending = _PENDING.pop(query_key, None)\n        if pending and pending[0] == owner:\n            event.set()\n\n        _ACTIVE[query_key] = _ActiveQuery(\n            user_id=owner,\n            event=event,\n            created_at=time.monotonic(),\n        )\n        return event\n\n\ndef cancel_query(query_id: str, user_id: str) -> bool:\n    query_key = _clean(query_id)\n    owner = _clean(user_id)\n    if not query_key:\n        return False\n\n    with _LOCK:\n        _purge_pending()\n        active = _ACTIVE.get(query_key)\n        if active is not None:\n            if active.user_id != owner:\n                return False\n            active.event.set()\n            return True\n\n        # Menangani klik stop yang sangat cepat, sebelum route /chat selesai\n        # mendaftarkan query ke registry.\n        _PENDING[query_key] = (owner, time.monotonic())\n        return False\n\n\ndef unregister_query(\n    query_id: str,\n    user_id: str,\n    event: threading.Event | None = None,\n) -> None:\n    query_key = _clean(query_id)\n    owner = _clean(user_id)\n    with _LOCK:\n        active = _ACTIVE.get(query_key)\n        if active is None or active.user_id != owner:\n            return\n        if event is not None and active.event is not event:\n            return\n        _ACTIVE.pop(query_key, None)\n\n\ndef current_cancel_event() -> threading.Event | None:\n    return getattr(_LOCAL, "event", None)\n\n\ndef raise_if_cancelled(event: threading.Event | None = None) -> None:\n    selected = event or current_cancel_event()\n    if selected is not None and selected.is_set():\n        raise ChatCancelled("Chat request was cancelled")\n\n\n@contextmanager\ndef cancellation_scope(event: threading.Event | None) -> Iterator[None]:\n    previous = current_cancel_event()\n    _LOCAL.event = event\n    try:\n        raise_if_cancelled(event)\n        yield\n    finally:\n        _LOCAL.event = previous\n'''
    write(backend / 'api' / 'cancellation.py', cancellation_py)

    patch_routes(backend / 'api' / 'routes_compat.py')
    patch_chat_service(backend / 'api' / 'chat_service.py')
    patch_model_router(backend / 'api' / 'model_router.py')
    patch_provider(backend / 'api' / 'ollama_client.py', 'ollama')
    patch_provider(backend / 'api' / 'gemini_client.py', 'gemini')
    patch_provider(backend / 'api' / 'groq_client.py', 'groq')
    patch_chat_service_ts(root / 'src' / 'services' / 'chatService.ts')
    patch_use_chat(root / 'src' / 'hooks' / 'useChat.ts')
    patch_app(root / 'src' / 'App.tsx')

    test_file = backend / 'tests' / 'test_chat_cancellation.py'
    test_content = '''from __future__ import annotations\n\nimport threading\n\nimport pytest\n\nfrom api.cancellation import (\n    ChatCancelled,\n    cancel_query,\n    cancellation_scope,\n    raise_if_cancelled,\n    register_query,\n    unregister_query,\n)\n\n\ndef test_registered_query_can_be_cancelled() -> None:\n    event = register_query("cancel-test-1", "user-1")\n    assert not event.is_set()\n    assert cancel_query("cancel-test-1", "user-1") is True\n    assert event.is_set()\n    with pytest.raises(ChatCancelled):\n        raise_if_cancelled(event)\n    unregister_query("cancel-test-1", "user-1", event)\n\n\ndef test_other_user_cannot_cancel_query() -> None:\n    event = register_query("cancel-test-2", "user-a")\n    assert cancel_query("cancel-test-2", "user-b") is False\n    assert not event.is_set()\n    unregister_query("cancel-test-2", "user-a", event)\n\n\ndef test_early_cancel_is_applied_when_query_registers() -> None:\n    assert cancel_query("cancel-test-3", "user-1") is False\n    event = register_query("cancel-test-3", "user-1")\n    assert event.is_set()\n    unregister_query("cancel-test-3", "user-1", event)\n\n\ndef test_thread_local_cancellation_scope() -> None:\n    event = threading.Event()\n    with cancellation_scope(event):\n        raise_if_cancelled()\n        event.set()\n        with pytest.raises(ChatCancelled):\n            raise_if_cancelled()\n'''
    write(test_file, test_content)

    print('\nPatch selesai.')
    print('1. Jalankan: python -m pytest tests/test_chat_cancellation.py -q')
    print('2. Jalankan frontend typecheck/build.')
    print('3. Restart backend dan frontend.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(f'[ERROR] {exc}', file=sys.stderr)
        raise
