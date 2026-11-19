import os
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

if __name__ == "__main__":
    unittest.main()
