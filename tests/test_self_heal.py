import os
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

class TestSelfHeal(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "self_heal.py")
        )
        self.condense_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "condense.py")
        )
        subprocess.run(["python", self.condense_path, "init", "--dir", self.test_dir], check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_python_traceback_and_extract_culprit(self):
        sample_traceback = """
Traceback (most recent call last):
  File "src/calculator.py", line 42, in divide
    return a / b
ZeroDivisionError: division by zero
"""
        res = subprocess.run(
            ["python", self.script_path, "--dir", self.test_dir, "--error", sample_traceback, "--json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"SelfHeal failed: {res.stderr}")
        self.assertIn("ZeroDivisionError", res.stdout)
        self.assertIn("src/calculator.py", res.stdout)
        self.assertIn("42", res.stdout)

    def test_self_heal_updates_active_state_with_remediation(self):
        sample_error = """
AssertionError: Expected 200 OK but received 401 Unauthorized
  File "tests/test_auth.py", line 18, in test_login
"""
        res = subprocess.run(
            [
                "python", self.script_path,
                "--dir", self.test_dir,
                "--error", sample_error,
                "--apply"
            ],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        
        active_state = Path(self.test_dir) / ".context" / "active_state.md"
        content = active_state.read_text(encoding="utf-8")
        self.assertIn("FAILED", content)
        self.assertIn("tests/test_auth.py", content)
        self.assertIn("AssertionError", content)

if __name__ == "__main__":
    unittest.main()
