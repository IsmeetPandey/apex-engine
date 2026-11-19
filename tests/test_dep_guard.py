import os
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

class TestDepGuard(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "dep_guard.py")
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dep_guard_detects_hallucinated_import(self):
        # Create a file importing a non-existent package
        bad_code = Path(self.test_dir) / "app.py"
        bad_code.write_text("import hallucinated_fake_lib\nimport os\n", encoding="utf-8")

        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0, "DepGuard must fail on unknown/hallucinated import")
        self.assertIn("hallucinated_fake_lib", res.stdout + res.stderr)

    def test_dep_guard_passes_standard_library_and_local_imports(self):
        # Create a local module
        helper = Path(self.test_dir) / "helper.py"
        helper.write_text("def greet(): return 'hello'\n", encoding="utf-8")

        # Create main app importing stdlib and local helper
        app = Path(self.test_dir) / "main.py"
        app.write_text("import sys\nimport os\nimport helper\n", encoding="utf-8")

        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"DepGuard should approve stdlib + local imports: {res.stdout}\n{res.stderr}")
        self.assertIn("All imports verified", res.stdout)

if __name__ == "__main__":
    unittest.main()
