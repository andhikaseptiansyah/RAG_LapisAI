import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import conversation_store, document_store, logger
from ingestion import indexer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROUTES_FILE = PROJECT_ROOT / "backend" / "api" / "routes_compat.py"
UPLOAD_COMPONENT = PROJECT_ROOT / "src" / "components" / "AdminUploadFile.tsx"
API_SERVICE = PROJECT_ROOT / "src" / "services" / "api.ts"


class ConversationDeletionSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)
        self.original_conversation_file = conversation_store.CONVERSATION_STORE_FILE
        self.original_log_file = logger.LOG_FILE
        conversation_store.CONVERSATION_STORE_FILE = temporary_path / "conversations.json"
        logger.LOG_FILE = temporary_path / "query_logs.json"

    def tearDown(self) -> None:
        conversation_store.CONVERSATION_STORE_FILE = self.original_conversation_file
        logger.LOG_FILE = self.original_log_file
        self.temporary_directory.cleanup()

    def test_deleting_conversation_can_delete_linked_query_log(self) -> None:
        query_id = "query-linked-to-conversation"
        logger.save_log(
            query_id=query_id,
            question="Apa kebijakan cuti?",
            answer="Jawaban",
            sources=[],
            latency_ms=10,
            user_id="staff-1",
        )
        conversation, _ = conversation_store.append_chat_turn(
            query_id=query_id,
            question="Apa kebijakan cuti?",
            answer="Jawaban",
            confidence=0.5,
            sources=[],
            user_id="staff-1",
        )

        self.assertTrue(
            conversation_store.delete_conversation(
                conversation["id"],
                user_id="staff-1",
            )
        )
        deleted_log_ids = logger.delete_logs_for_conversations(
            [conversation],
            user_id="staff-1",
        )

        self.assertEqual(deleted_log_ids, [query_id])
        self.assertEqual(logger.get_logs(include_all=True), [])

    def test_legacy_conversation_is_matched_by_owner_question_and_time(self) -> None:
        legacy_conversation = {
            "id": "legacy-conversation",
            "user_id": "staff-legacy",
            "messages": [
                {
                    "id": "legacy-message",
                    "role": "user",
                    "content": "Pertanyaan lama",
                    "created_at": "2026-07-31T09:00:00+00:00",
                    "metadata": {"user_id": "staff-legacy"},
                }
            ],
        }
        logger.write_logs([
            {
                "id": "legacy-log",
                "user_id": "staff-legacy",
                "question": "  PERTANYAAN   LAMA ",
                "timestamp": "2026-07-31T09:00:01+00:00",
            },
            {
                "id": "another-user-log",
                "user_id": "staff-other",
                "question": "Pertanyaan lama",
                "timestamp": "2026-07-31T09:00:01+00:00",
            },
        ])

        deleted_log_ids = logger.delete_logs_for_conversations(
            [legacy_conversation],
            user_id="staff-legacy",
        )

        self.assertEqual(deleted_log_ids, ["legacy-log"])
        self.assertEqual(
            [item["id"] for item in logger.get_logs(include_all=True)],
            ["another-user-log"],
        )


class ConversationChatTotalsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.original_conversation_file = conversation_store.CONVERSATION_STORE_FILE
        conversation_store.CONVERSATION_STORE_FILE = (
            Path(self.temporary_directory.name) / "conversations.json"
        )

    def tearDown(self) -> None:
        conversation_store.CONVERSATION_STORE_FILE = self.original_conversation_file
        self.temporary_directory.cleanup()

    def test_totals_count_user_questions_from_active_conversation_history(self) -> None:
        conversation_store.append_chat_turn(
            question="Pertanyaan pertama",
            answer="Jawaban",
            confidence=0.8,
            sources=[],
            user_id="admin-active",
        )
        conversation_store.append_chat_turn(
            question="Pertanyaan kedua",
            answer="Jawaban",
            confidence=0.8,
            sources=[],
            user_id="admin-active",
        )
        conversation_store.append_chat_turn(
            question="Pertanyaan akun yang sudah dihapus",
            answer="Jawaban",
            confidence=0.8,
            sources=[],
            user_id="deleted-user",
        )

        totals = conversation_store.conversation_chat_totals(
            {"admin-active", "staff-active"}
        )

        self.assertEqual(totals, {"admin-active": 2})

    def test_conversation_list_includes_user_question_summaries(self) -> None:
        conversation_store.append_chat_turn(
            question="Apa kebijakan cuti?",
            answer="Jawaban",
            confidence=0.8,
            sources=[],
            user_id="staff-1",
        )

        summaries = conversation_store.list_summaries(user_id="staff-1")

        self.assertEqual(len(summaries), 1)
        self.assertEqual(
            [item["content"] for item in summaries[0]["user_messages"]],
            ["Apa kebijakan cuti?"],
        )

    def test_admin_endpoints_use_conversation_history_as_chat_source(self) -> None:
        source = ROUTES_FILE.read_text(encoding="utf-8")
        self.assertIn("conversation_chat_totals(active_user_ids)", source)
        self.assertIn("conversation_chat_records(", source)
        self.assertIn('"totalChats": len(chat_records or [])', source)


class DocumentDeletionSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        temporary_path = Path(self.temporary_directory.name)
        self.original_document_file = document_store.DOCUMENT_STORE_FILE
        self.original_upload_dir = document_store.UPLOAD_DIR
        document_store.DOCUMENT_STORE_FILE = (
            temporary_path / "documents.json"
        )
        self.upload_dir = temporary_path / "uploads"
        self.upload_dir.mkdir()
        document_store.UPLOAD_DIR = str(self.upload_dir)

    def tearDown(self) -> None:
        document_store.DOCUMENT_STORE_FILE = self.original_document_file
        document_store.UPLOAD_DIR = self.original_upload_dir
        self.temporary_directory.cleanup()

    def test_stale_absolute_filepath_is_rebased_to_active_upload_directory(self) -> None:
        source_path = self.upload_dir / "Policy.PDF"
        source_path.write_bytes(b"%PDF-test")
        document_store.write_documents([
            {
                "id": "portable-document",
                "filename": "Policy.PDF",
                "filepath": "C:\\Users\\someone\\old-project\\Policy.PDF",
                "chunks": 3,
            }
        ])

        documents = document_store.read_documents()

        self.assertEqual(documents[0]["filepath"], str(source_path.resolve()))
        self.assertEqual(
            document_store.resolve_document_source_path(documents[0]),
            source_path.resolve(),
        )

    def test_upsert_uses_case_insensitive_filename_identity(self) -> None:
        document_store.write_documents([
            {"id": "existing", "filename": "Policy.PDF", "chunks": 1}
        ])

        updated = document_store.upsert_document({
            "id": "replacement",
            "filename": "policy.pdf",
            "filepath": str(self.upload_dir / "policy.pdf"),
            "chunks": 2,
        })

        documents = document_store.read_documents()
        self.assertEqual(len(documents), 1)
        self.assertEqual(updated["id"], "existing")
        self.assertEqual(documents[0]["chunks"], 2)

    def test_delete_by_filename_removes_case_variant_metadata(self) -> None:
        document_store.write_documents([
            {"id": "one", "filename": "Policy.PDF"},
            {"id": "two", "filename": "policy.pdf"},
            {"id": "three", "filename": "other.pdf"},
        ])

        removed = document_store.delete_documents_by_filename("POLICY.pdf")

        self.assertEqual({item["id"] for item in removed}, {"one", "two"})
        self.assertEqual(
            [item["id"] for item in document_store.read_documents()],
            ["three"],
        )

    def test_vector_cleanup_removes_all_filename_case_variants(self) -> None:
        class FakeCollection:
            def __init__(self) -> None:
                self.deleted_ids: list[str] = []

            def get(self, include):
                self.include = include
                return {
                    "ids": ["a", "b", "c"],
                    "metadatas": [
                        {"filename": "Policy.PDF"},
                        {"filename": "policy.pdf"},
                        {"filename": "other.pdf"},
                    ],
                }

            def delete(self, ids=None, where=None):
                if ids:
                    self.deleted_ids.extend(ids)

        collection = FakeCollection()
        with patch.object(indexer, "get_collection", return_value=collection):
            deleted_count = indexer.delete_document_chunks(
                "POLICY.pdf",
                case_insensitive=True,
            )

        self.assertEqual(deleted_count, 2)
        self.assertEqual(collection.deleted_ids, ["a", "b"])

    def test_delete_endpoint_removes_vectors_files_and_metadata(self) -> None:
        source = ROUTES_FILE.read_text(encoding="utf-8")
        self.assertIn("case_insensitive=True", source)
        self.assertIn("source_path.unlink(missing_ok=True)", source)
        self.assertIn("delete_documents_by_filename(filename)", source)


class AdminRefreshAndIndexingTests(unittest.TestCase):
    def test_get_requests_bypass_browser_cache(self) -> None:
        source = API_SERVICE.read_text(encoding="utf-8")
        self.assertIn("requestMethod === 'GET'", source)
        self.assertIn("'no-store'", source)

    def test_index_all_does_not_force_indexed_upload_back_to_repository(self) -> None:
        source = UPLOAD_COMPONENT.read_text(encoding="utf-8")
        self.assertNotIn("pendingUploadNamesRef", source)
        self.assertNotIn("click Index All again", source)
        self.assertIn("setQueuePage(1)", source)
        self.assertIn("continue indexing automatically", source)

    def test_evaluation_requires_exact_active_index_readiness(self) -> None:
        source = ROUTES_FILE.read_text(encoding="utf-8")
        self.assertIn('"/admin/evaluation/readiness"', source)
        self.assertIn("_evaluation_corpus_readiness(payload.expectedDocuments)", source)
        self.assertIn("resolve_document_source_path(document)", source)


if __name__ == "__main__":
    unittest.main()
