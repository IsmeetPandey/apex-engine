import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

class TestGatekeeper(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "gatekeeper.py")
        )
        self.condense_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "condense.py")
        )
        # Initialize git repo in test_dir
        subprocess.run(["git", "init"], cwd=self.test_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "Test User"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)
        # Initialize context
        subprocess.run(["python", self.condense_path, "init", "--dir", self.test_dir], check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gatekeeper_blocks_placeholders(self):
        # Create a file with forbidden TODO placeholder
        bad_file = Path(self.test_dir) / "service.py"
        bad_file.write_text("def process_payment():\n    # TODO: implement later\n    pass\n", encoding="utf-8")
        subprocess.run(["git", "add", "service.py"], cwd=self.test_dir, check=True)

        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir],
            capture_output=True,
            text=True
        )
        self.assertNotEqual(res.returncode, 0, "Gatekeeper must block code containing TODO and pass")
        self.assertIn("Gatekeeper Rejected", res.stdout + res.stderr)
        self.assertIn("TODO", res.stdout + res.stderr)

    def test_gatekeeper_passes_clean_code(self):
        # Create a clean file with full implementation
        good_file = Path(self.test_dir) / "math_util.py"
        good_file.write_text("def add(a: int, b: int) -> int:\n    return a + b\n", encoding="utf-8")
        
        # Create a test file
        test_file = Path(self.test_dir) / "test_math.py"
        test_file.write_text("def test_add():\n    assert add(1, 2) == 3\n", encoding="utf-8")
        
        subprocess.run(["git", "add", "math_util.py", "test_math.py"], cwd=self.test_dir, check=True)

        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Gatekeeper should pass clean code: {res.stdout}\n{res.stderr}")
        self.assertIn("Gatekeeper Approved", res.stdout)

    def test_gatekeeper_blocks_type_mismatch_on_bounded_invariant_cleanly(self):
        # Bind bounded numeric invariant
        inv_script = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "invariant_store.py")
        )
        sys.path.insert(0, os.path.dirname(inv_script))
        from invariant_store import InvariantStore
        store = InvariantStore(os.path.join(self.test_dir, ".context"))
        store.bind_immutable("TARGET_PORT", 8080, val_type="int", bounds={"min": 1024, "max": 65535})

        # Add code assigning string literal '8080' to integer invariant with bounds
        app_file = Path(self.test_dir) / "app.py"
        app_file.write_text('TARGET_PORT = "8080"\n', encoding="utf-8")
        test_file = Path(self.test_dir) / "test_app.py"
        test_file.write_text('def test_app():\n    assert True\n', encoding="utf-8")
        subprocess.run(["git", "add", "app.py", "test_app.py"], cwd=self.test_dir, check=True)

        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir],
            capture_output=True,
            text=True
        )
        combined_output = res.stdout + res.stderr
        self.assertNotEqual(res.returncode, 0, "Gatekeeper must reject type mismatch on invariant")
        self.assertNotIn("TypeError", combined_output, "Gatekeeper must not crash with unhandled TypeError")
        self.assertIn("INV001", combined_output)
        self.assertIn("INV003", combined_output)
        self.assertIn("Gatekeeper Rejected", combined_output)

if __name__ == "__main__":
    unittest.main()
