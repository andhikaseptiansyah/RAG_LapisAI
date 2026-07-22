import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROUTES_FILE = PROJECT_ROOT / "backend" / "api" / "routes_compat.py"
UPLOAD_COMPONENT = PROJECT_ROOT / "src" / "components" / "AdminUploadFile.tsx"
API_SERVICE = PROJECT_ROOT / "src" / "services" / "api.ts"
STAFF_COMPONENT = PROJECT_ROOT / "src" / "components" / "AdminStaffManagement.tsx"


class UploadConflictContractTests(unittest.TestCase):
    def test_backend_reports_structured_duplicate_filenames(self) -> None:
        source = ROUTES_FILE.read_text(encoding="utf-8")
        self.assertIn('"code": "DOCUMENT_ALREADY_EXISTS"', source)
        self.assertIn('"duplicateFilenames": unique_filenames', source)
        self.assertIn("existing_names = _known_upload_filenames()", source)
        self.assertIn('@router.post("/admin/documents/conflicts")', source)
        self.assertIn("existing_upload_paths = _upload_file_paths(requested_filename)", source)

    def test_frontend_reopens_replace_confirmation_from_server_conflict(self) -> None:
        component_source = UPLOAD_COMPONENT.read_text(encoding="utf-8")
        api_source = API_SERVICE.read_text(encoding="utf-8")
        document_service_source = (
            PROJECT_ROOT / "src" / "services" / "documentService.ts"
        ).read_text(encoding="utf-8")
        hook_source = (
            PROJECT_ROOT / "src" / "hooks" / "useDocuments.ts"
        ).read_text(encoding="utf-8")
        self.assertIn("getDuplicateFilenamesFromApiError", api_source)
        self.assertIn("/api/admin/documents/conflicts", document_service_source)
        self.assertIn("await checkDocumentConflicts", hook_source)
        self.assertIn("result.duplicateFilenames", component_source)
        self.assertIn("setDuplicateFiles(conflicts)", component_source)

    def test_original_upload_repository_layout_is_present(self) -> None:
        source = UPLOAD_COMPONENT.read_text(encoding="utf-8")
        self.assertIn("Upload & Index", source)
        self.assertIn(">Knowledge Base<", source)
        self.assertIn("Trained Repository", source)
        self.assertIn("Index All", source)
        self.assertIn("Yes, Replace", source)

    def test_username_pattern_is_valid_for_html_v_regex(self) -> None:
        source = STAFF_COMPONENT.read_text(encoding="utf-8")
        self.assertIn('pattern="(?:[a-z0-9._]|-)+"', source)
        self.assertNotIn('pattern="[a-z0-9._-]+"', source)


if __name__ == "__main__":
    unittest.main()
