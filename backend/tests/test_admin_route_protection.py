import ast
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ROUTES_FILE = PROJECT_ROOT / "backend" / "api" / "routes_compat.py"


class AdminRouteProtectionTests(unittest.TestCase):
    def test_every_admin_route_requires_admin(self) -> None:
        tree = ast.parse(ROUTES_FILE.read_text(encoding="utf-8"))
        missing_protection: list[str] = []

        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            admin_paths: list[str] = []
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call) or not decorator.args:
                    continue
                first_argument = decorator.args[0]
                if isinstance(first_argument, ast.Constant) and isinstance(first_argument.value, str):
                    if first_argument.value.startswith("/admin"):
                        admin_paths.append(first_argument.value)

            if not admin_paths:
                continue

            requires_admin = any(
                isinstance(call, ast.Call)
                and isinstance(call.func, ast.Name)
                and call.func.id == "_require_admin"
                for call in ast.walk(node)
            )
            if not requires_admin:
                missing_protection.extend(admin_paths)

        self.assertEqual(missing_protection, [])

    def test_legacy_router_modules_are_removed(self) -> None:
        self.assertFalse((PROJECT_ROOT / "backend" / "api" / "routes_admin.py").exists())
        self.assertFalse((PROJECT_ROOT / "backend" / "api" / "routes_chat.py").exists())
        self.assertFalse((PROJECT_ROOT / "python-service").exists())

    def test_frontend_staff_route_is_registered(self) -> None:
        main_source = (PROJECT_ROOT / "src" / "main.tsx").read_text(encoding="utf-8")
        self.assertIn('path="/admin/staff"', main_source)
        self.assertIn("<AdminStaffManagement />", main_source)


if __name__ == "__main__":
    unittest.main()
