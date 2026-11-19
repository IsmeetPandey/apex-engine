import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

# Add scripts directory to sys.path
SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import condense


class TestCondenser(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.context_dir = os.path.join(self.test_dir, ".context")
        self.active_state_path = os.path.join(self.context_dir, "active_state.md")
        self.history_log_path = os.path.join(self.context_dir, "history.log")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_init_creates_context_directory_and_files(self):
        """init should create .context dir, active_state.md, and history.log"""
        condense.init_context(self.test_dir)
        self.assertTrue(os.path.isdir(self.context_dir), ".context directory must exist")
        self.assertTrue(os.path.isfile(self.active_state_path), "active_state.md must exist")
        self.assertTrue(os.path.isfile(self.history_log_path), "history.log must exist")

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# ACTIVE CONTEXT BUFFER", content)
        self.assertLess(len(content.encode("utf-8")), 2500)

        with open(self.history_log_path, "r", encoding="utf-8") as f:
            log_content = f.read()
        self.assertIn("# APEX EPOCH HISTORY LOG", log_content)

    def test_init_does_not_overwrite_existing_active_state_unless_forced(self):
        """init should preserve existing active_state.md unless force=True or --force"""
        condense.init_context(self.test_dir)
        custom_content = "# CUSTOM PRESERVED ACTIVE STATE\n"
        with open(self.active_state_path, "w", encoding="utf-8") as f:
            f.write(custom_content)

        # Re-running init without force must preserve custom content
        condense.init_context(self.test_dir, force=False)
        with open(self.active_state_path, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), custom_content)

        # Re-running init with force=True overwrites
        condense.init_context(self.test_dir, force=True)
        with open(self.active_state_path, "r", encoding="utf-8") as f:
            self.assertIn("# ACTIVE CONTEXT BUFFER", f.read())

    def test_init_uses_embedded_fallback_when_templates_missing(self):
        """init should fall back gracefully if templates directory is absent"""
        # Call with nonexistent template dir by monkeypatching or calling fallback directly
        orig_templates = condense.TEMPLATES_DIR
        try:
            condense.TEMPLATES_DIR = "/nonexistent/path/to/templates"
            target = tempfile.mkdtemp()
            try:
                condense.init_context(target)
                state_file = os.path.join(target, ".context", "active_state.md")
                self.assertTrue(os.path.isfile(state_file))
                with open(state_file, "r", encoding="utf-8") as f:
                    c = f.read()
                self.assertIn("# ACTIVE CONTEXT BUFFER", c)
            finally:
                shutil.rmtree(target, ignore_errors=True)
        finally:
            condense.TEMPLATES_DIR = orig_templates

    def test_status_reads_active_state(self):
        """status should return contents of active_state.md or error if not found"""
        condense.init_context(self.test_dir)
        status_text, ok = condense.get_status(self.test_dir)
        self.assertTrue(ok)
        self.assertIn("# ACTIVE CONTEXT BUFFER", status_text)

        # Non-initialized directory
        empty_dir = tempfile.mkdtemp()
        try:
            err_text, ok = condense.get_status(empty_dir)
            self.assertFalse(ok)
            self.assertIn("not found", err_text.lower())
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_update_modifies_active_state(self):
        """update should refresh active_state.md with goal, gate, invariants, and next action"""
        condense.init_context(self.test_dir)
        condense.update_active_state(
            target_dir=self.test_dir,
            goal="Implement Task 2",
            gate="python -m unittest",
            next_action="Run test suite",
            invariants="Zero external dependencies",
            task="Task 2: condense.py",
            status="IN_PROGRESS"
        )

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("Implement Task 2", content)
        self.assertIn("python -m unittest", content)
        self.assertIn("Run test suite", content)
        self.assertIn("Zero external dependencies", content)
        self.assertIn("## Modified Files & Git Diffs", content)
        self.assertLess(len(content.encode("utf-8")), 2500)

    def test_update_bounded_size_under_2500_bytes(self):
        """update must truncate git diff section if it exceeds 2,500 bytes"""
        condense.init_context(self.test_dir)

        # Huge diff text
        huge_diff = "A" * 10000

        content = condense.build_active_state_content(
            goal="Test Bounded Size",
            gate="pytest",
            next_action="Verify truncation",
            invariants="Bounded memory invariant",
            task="Task Bounded",
            status="IN_PROGRESS",
            git_summary=huge_diff
        )

        encoded_size = len(content.encode("utf-8"))
        self.assertLess(encoded_size, 2500, f"Size {encoded_size} must be < 2500 bytes")
        self.assertIn("... (truncated)", content)

    def test_git_status_and_diff_gathering(self):
        """update should gather git status and diff when inside a git repository"""
        # Initialize a temporary git repo in test_dir
        subprocess.run(["git", "init"], cwd=self.test_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=self.test_dir, check=True)

        # Create an initial commit
        initial_file = os.path.join(self.test_dir, "initial.txt")
        with open(initial_file, "w", encoding="utf-8") as f:
            f.write("initial content\n")
        subprocess.run(["git", "add", "initial.txt"], cwd=self.test_dir, check=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=self.test_dir, check=True)

        condense.init_context(self.test_dir)

        # Modify file and create untracked file
        with open(initial_file, "a", encoding="utf-8") as f:
            f.write("added new line\n")
        new_file = os.path.join(self.test_dir, "untracked.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("print('hello')\n")

        condense.update_active_state(
            target_dir=self.test_dir,
            goal="Test git gathering",
            gate="git status",
            next_action="Check diffs"
        )

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("initial.txt", content)
        self.assertIn("untracked.py", content)

    def test_update_atomicity(self):
        """update should write to a temporary file first and replace atomically"""
        condense.init_context(self.test_dir)
        # Verify active_state.md is not left corrupted or partially written
        condense.update_active_state(
            target_dir=self.test_dir,
            goal="Atomic Update Test",
            gate="gate test",
            next_action="atomic check"
        )
        self.assertTrue(os.path.isfile(self.active_state_path))
        # Ensure no leftover temp files in .context
        temp_files = [f for f in os.listdir(self.context_dir) if f.startswith("active_state.md.tmp")]
        self.assertEqual(temp_files, [], "No temporary update files should remain")

    def test_checkpoint_appends_to_history(self):
        """checkpoint should append epoch records to history.log with timestamp and status"""
        condense.init_context(self.test_dir)

        condense.checkpoint(self.test_dir, msg="First epoch completed", status="COMPLETED")
        condense.checkpoint(self.test_dir, msg="Second epoch in progress", status="IN_PROGRESS")

        with open(self.history_log_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("## Epoch [001]: First epoch completed", content)
        self.assertIn("## Epoch [002]: Second epoch in progress", content)
        self.assertIn("- **Status**: COMPLETED", content)
        self.assertIn("- **Status**: IN_PROGRESS", content)
        self.assertIn("- **Timestamp**:", content)

    def test_cli_execution(self):
        """Full CLI roundtrip using subprocess"""
        condense_script = os.path.join(SCRIPTS_DIR, "condense.py")

        # 1. init
        res = subprocess.run(
            [sys.executable, condense_script, "init", "--dir", self.test_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertTrue(os.path.isfile(self.active_state_path))

        # 2. update with --gate-status PASSED
        res = subprocess.run(
            [
                sys.executable, condense_script, "update",
                "--dir", self.test_dir,
                "--goal", "CLI Goal",
                "--gate", "pytest CLI",
                "--gate-status", "PASSED",
                "--invariants", "CLI Invariant",
                "--next", "CLI Next Action"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(self.active_state_path, "r", encoding="utf-8") as f:
            c = f.read()
        self.assertIn("- **Last Status**: PASSED", c)

        # 3. status
        res = subprocess.run(
            [sys.executable, condense_script, "status", "--dir", self.test_dir],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertIn("CLI Goal", res.stdout)
        self.assertIn("pytest CLI", res.stdout)

        # 4. checkpoint
        res = subprocess.run(
            [
                sys.executable, condense_script, "checkpoint",
                "--dir", self.test_dir,
                "--msg", "CLI Checkpoint record",
                "--status", "COMPLETED"
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(res.returncode, 0, res.stderr)
        with open(self.history_log_path, "r", encoding="utf-8") as f:
            log_c = f.read()
        self.assertIn("CLI Checkpoint record", log_c)


if __name__ == "__main__":
    unittest.main()
