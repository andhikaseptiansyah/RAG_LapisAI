import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from api import user_store


class UserStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_directory = tempfile.TemporaryDirectory()
        self.store_path = Path(self.temp_directory.name) / "users_store.json"
        self.path_patch = patch.object(user_store, "USER_STORE_FILE", self.store_path)
        self.environment_patch = patch.dict(
            "os.environ",
            {
                "BOOTSTRAP_ADMIN_USERNAME": "test-admin",
                "BOOTSTRAP_ADMIN_NAME": "Test Administrator",
                "BOOTSTRAP_ADMIN_PASSWORD": "test-admin-password",
            },
        )
        self.path_patch.start()
        self.environment_patch.start()

    def tearDown(self) -> None:
        self.environment_patch.stop()
        self.path_patch.stop()
        self.temp_directory.cleanup()

    def test_create_update_and_delete_managed_accounts(self) -> None:
        created = user_store.create_managed_user(
            username="sample.user",
            name="Sample User",
            password="secret123",
            role="user",
        )
        self.assertEqual(created["role"], "user")
        self.assertIsNotNone(user_store.authenticate_user("sample.user", "secret123"))

        updated = user_store.update_user(
            created["id"],
            username="sample.staff",
            name="Sample Staff",
            role="staff",
        )
        self.assertIsNotNone(updated)
        self.assertEqual(updated["username"], "sample.staff")
        self.assertEqual(updated["name"], "Sample Staff")
        self.assertEqual(updated["role"], "staff")

        password_updated = user_store.update_user_password(created["id"], "newsecret123")
        self.assertIsNotNone(password_updated)
        self.assertIsNone(user_store.authenticate_user("sample.staff", "secret123"))
        self.assertIsNotNone(user_store.authenticate_user("sample.staff", "newsecret123"))

        deleted = user_store.delete_user(created["id"])
        self.assertIsNotNone(deleted)
        self.assertIsNone(user_store.get_user_by_id(created["id"]))

    def test_duplicate_username_is_rejected(self) -> None:
        user_store.create_managed_user("duplicate.user", "First User", "secret123", "user")
        with self.assertRaises(user_store.UserStoreError):
            user_store.create_managed_user("duplicate.user", "Second User", "secret123", "staff")


if __name__ == "__main__":
    unittest.main()
