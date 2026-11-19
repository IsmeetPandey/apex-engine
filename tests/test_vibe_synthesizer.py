import os
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

class TestVibeSynthesizer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "vibe_synthesizer.py")
        )
        self.condense_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "condense.py")
        )
        # Initialize context in test_dir
        subprocess.run(["python", self.condense_path, "init", "--dir", self.test_dir], check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_synthesize_decomposes_vibe_prompt(self):
        prompt = "Build a real-time markdown note editor with tag filtering and auto-save"
        res = subprocess.run(
            ["python", self.script_path, prompt, "--dir", self.test_dir, "--json"],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Synthesizer failed: {res.stderr}")
        self.assertIn("objectives", res.stdout)
        self.assertIn("files", res.stdout)
        self.assertIn("test_plan", res.stdout)
        self.assertIn("invariants", res.stdout)

    def test_synthesize_generates_spec_file_and_updates_context(self):
        prompt = "Create a JWT authentication service with token refresh and redis caching"
        spec_file = os.path.join(self.test_dir, "SPEC.md")
        res = subprocess.run(
            [
                "python", self.script_path, prompt,
                "--dir", self.test_dir,
                "--out", spec_file,
                "--apply-context"
            ],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertTrue(os.path.isfile(spec_file), "SPEC.md must be generated")
        
        spec_content = Path(spec_file).read_text(encoding="utf-8")
        self.assertIn("# Technical Specification", spec_content)
        self.assertIn("Component Architecture", spec_content)
        self.assertIn("Contract-Driven Test Plan", spec_content)

        # Verify active_state.md was updated
        active_state = Path(self.test_dir) / ".context" / "active_state.md"
        active_content = active_state.read_text(encoding="utf-8")
        self.assertIn("jwt authentication", active_content.lower())
        self.assertIn("INSPECT", active_content)

if __name__ == "__main__":
    unittest.main()
