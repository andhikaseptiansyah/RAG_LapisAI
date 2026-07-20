import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

CONVERSATION_STORE_FILE = "./conversations_store.json"
LEGACY_ADMIN_USER_ID = "dev-admin"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_conversations() -> list[dict[str, Any]]:
    if not os.path.exists(CONVERSATION_STORE_FILE):
        return []

    try:
        with open(CONVERSATION_STORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def write_conversations(conversations: list[dict[str, Any]]) -> None:
    with open(CONVERSATION_STORE_FILE, "w", encoding="utf-8") as f:
        json.dump(conversations, f, indent=2, ensure_ascii=False)


def create_title(message: str) -> str:
    clean = " ".join((message or "").split())
    if not clean:
        return "New Chat"
    return clean[:60] + ("..." if len(clean) > 60 else "")


def _conversation_owner_id(conversation: dict[str, Any]) -> str:
    # Conversation lama yang belum punya user_id dianggap milik admin supaya tidak bocor ke staff baru.
    return str(conversation.get("user_id") or LEGACY_ADMIN_USER_ID)


def _can_access_conversation(
    conversation: dict[str, Any],
    user_id: str | None = None,
    include_all: bool = False,
) -> bool:
    if include_all:
        return True
    if not user_id:
        return False
    return _conversation_owner_id(conversation) == user_id


def append_chat_turn(
    question: str,
    answer: str,
    confidence: float,
    sources: list[dict[str, Any]],
    conversation_id: str | None = None,
    language: str | None = None,
    user_id: str | None = None,
    user_name: str | None = None,
    follow_up_question: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    conversations = read_conversations()
    now = now_iso()
    conversation = None
    owner_id = user_id or LEGACY_ADMIN_USER_ID
    owner_name = user_name or "User"

    if conversation_id:
        for item in conversations:
            if item.get("id") != conversation_id:
                continue

            # Jangan izinkan user lain menulis ke conversation milik user berbeda.
            if _can_access_conversation(item, user_id=owner_id):
                conversation = item
            else:
                conversation_id = None
            break

    if conversation is None:
        conversation = {
            "id": conversation_id or str(uuid.uuid4()),
            "user_id": owner_id,
            "user_name": owner_name,
            "title": create_title(question),
            "language": language or "ID",
            "is_pinned": False,
            "pinned": False,
            "messages": [],
            "created_at": now,
            "updated_at": now,
        }
        conversations.insert(0, conversation)
    else:
        # Migrasi ringan untuk conversation lama.
        conversation.setdefault("user_id", owner_id)
        conversation.setdefault("user_name", owner_name)

    base_metadata = {
        "user_id": owner_id,
        "user_name": owner_name,
    }

    user_message = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation["id"],
        "role": "user",
        "content": question,
        "attachments": [],
        "confidence": None,
        "model_name": None,
        "metadata": base_metadata,
        "created_at": now,
    }
    primary_source = sources[0] if sources else {}
    assistant_message = {
        "id": str(uuid.uuid4()),
        "conversation_id": conversation["id"],
        "role": "assistant",
        "content": answer,
        "attachments": [],
        "confidence": confidence,
        "model_name": "python-rag-ollama",
        "metadata": {
            **base_metadata,
            "sources": sources,
            "source": (
                primary_source.get("document_name")
                or primary_source.get("documentName")
                or None
            ),
            "page": primary_source.get("page"),
            "follow_up_question": follow_up_question,
            "followUpQuestion": follow_up_question,
        },
        "created_at": now,
    }

    conversation.setdefault("messages", []).extend([user_message, assistant_message])
    conversation["last_message"] = answer
    conversation["last_user_message"] = question
    conversation["last_message_at"] = now
    conversation["updated_at"] = now
    conversation["user_id"] = owner_id
    conversation["user_name"] = owner_name
    if language:
        conversation["language"] = language

    write_conversations(conversations)
    return conversation, assistant_message


def list_summaries(user_id: str | None = None, include_all: bool = False) -> list[dict[str, Any]]:
    summaries = []
    for conversation in read_conversations():
        if not _can_access_conversation(conversation, user_id=user_id, include_all=include_all):
            continue

        summaries.append({
            "id": conversation.get("id"),
            "user_id": _conversation_owner_id(conversation),
            "user_name": conversation.get("user_name", "User"),
            "title": conversation.get("title", "New Chat"),
            "language": conversation.get("language", "ID"),
            "is_pinned": bool(conversation.get("is_pinned", False)),
            "pinned": bool(conversation.get("pinned", False)),
            "last_message": conversation.get("last_message", ""),
            "last_user_message": conversation.get("last_user_message", ""),
            "last_message_at": conversation.get("last_message_at"),
            "created_at": conversation.get("created_at"),
            "updated_at": conversation.get("updated_at"),
        })
    return summaries


def get_conversation(
    conversation_id: str,
    user_id: str | None = None,
    include_all: bool = False,
) -> dict[str, Any] | None:
    for conversation in read_conversations():
        if conversation.get("id") == conversation_id and _can_access_conversation(
            conversation,
            user_id=user_id,
            include_all=include_all,
        ):
            return conversation
    return None


def update_conversation(
    conversation_id: str,
    updates: dict[str, Any],
    user_id: str | None = None,
    include_all: bool = False,
) -> dict[str, Any] | None:
    conversations = read_conversations()
    for conversation in conversations:
        if conversation.get("id") != conversation_id:
            continue
        if not _can_access_conversation(conversation, user_id=user_id, include_all=include_all):
            return None

        if "title" in updates and updates["title"]:
            conversation["title"] = updates["title"]
        if "is_pinned" in updates:
            conversation["is_pinned"] = bool(updates["is_pinned"])
            conversation["pinned"] = bool(updates["is_pinned"])
        if "language" in updates and updates["language"] in {"ID", "EN"}:
            conversation["language"] = updates["language"]
        conversation["updated_at"] = now_iso()
        write_conversations(conversations)
        return conversation
    return None


def delete_conversation(
    conversation_id: str,
    user_id: str | None = None,
    include_all: bool = False,
) -> bool:
    conversations = read_conversations()
    remaining = []
    deleted = False

    for item in conversations:
        if item.get("id") == conversation_id and _can_access_conversation(
            item,
            user_id=user_id,
            include_all=include_all,
        ):
            deleted = True
            continue
        remaining.append(item)

    if not deleted:
        return False
    write_conversations(remaining)
    return True

def delete_conversations(
    conversation_ids: list[str],
    user_id: str | None = None,
    include_all: bool = False,
) -> list[str]:
    target_ids = {
        str(conversation_id).strip()
        for conversation_id in conversation_ids
        if str(conversation_id).strip()
    }

    if not target_ids:
        return []

    conversations = read_conversations()
    remaining: list[dict[str, Any]] = []
    deleted_ids: list[str] = []

    for item in conversations:
        conversation_id = str(item.get("id") or "")
        if conversation_id in target_ids and _can_access_conversation(
            item,
            user_id=user_id,
            include_all=include_all,
        ):
            deleted_ids.append(conversation_id)
            continue

        remaining.append(item)

    if deleted_ids:
        write_conversations(remaining)

    return deleted_ids

