#!/usr/bin/env python3
"""
End-to-End Simulation Test Suite for ApexEngine.

Verifies the full developer lifecycle across all 4 Hard Gates:
1. Init / Scaffolding (.context/ setup)
2. Gate 1: Context Invariant Lock (INSPECT)
3. Gate 2: Contract-First TDD (CONTRACT - Red state)
4. Gate 3: Defensive Production Rigor (IMPLEMENT - Green state)
5. Gate 4: Empirical Terminal Verification & Milestone Checkpoint (VERIFY - Passed & Checkpoint)

Invariants verified:
- Zero external dependencies (Python 3.8+ stdlib only).
- Strict memory bounds (active_state.md < 2,500 bytes at all times).
- Faithful git status and commit integration.
- Sequential append-only epoch history logging.
"""

import os
import sys
import shutil
import tempfile
import unittest
import subprocess
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
CONDENSE_SCRIPT = os.path.join(SCRIPTS_DIR, "condense.py")

if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

import condense


class TestEndToEndSimulation(unittest.TestCase):
    def setUp(self):
        self.repo_dir = tempfile.mkdtemp(prefix="apex_e2e_repo_")
        self.context_dir = os.path.join(self.repo_dir, ".context")
        self.active_state_path = os.path.join(self.context_dir, "active_state.md")
        self.history_log_path = os.path.join(self.context_dir, "history.log")

        # Initialize git repo in the temporary directory
        subprocess.run(["git", "init"], cwd=self.repo_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        subprocess.run(["git", "config", "user.name", "ApexSimulationBot"], cwd=self.repo_dir, check=True)
        subprocess.run(["git", "config", "user.email", "apex-sim@example.com"], cwd=self.repo_dir, check=True)

        # Create initial commit
        readme_file = os.path.join(self.repo_dir, "README.md")
        with open(readme_file, "w", encoding="utf-8") as f:
            f.write("# Apex Project\nSimulation repo for ApexEngine lifecycle.\n")
        subprocess.run(["git", "add", "README.md"], cwd=self.repo_dir, check=True)
        subprocess.run(["git", "commit", "-m", "chore: initial repository scaffolding"], cwd=self.repo_dir, check=True)

    def tearDown(self):
        shutil.rmtree(self.repo_dir, ignore_errors=True)

    def _run_cli(self, *args, cwd=None):
        """Helper to execute condense.py CLI command."""
        cmd = [sys.executable, CONDENSE_SCRIPT] + list(args)
        proc = subprocess.run(
            cmd,
            cwd=cwd or self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        return proc

    def test_full_four_gate_developer_lifecycle_simulation(self):
        """Simulate a complete feature development lifecycle through all 4 gates."""

        # -----------------------------------------------------------------
        # STEP 1: Scaffolding via CLI: `python condense.py init`
        # -----------------------------------------------------------------
        res_init = self._run_cli("init", "--dir", self.repo_dir)
        self.assertEqual(res_init.returncode, 0, f"Init failed: {res_init.stderr}")
        self.assertTrue(os.path.isdir(self.context_dir))
        self.assertTrue(os.path.isfile(self.active_state_path))
        self.assertTrue(os.path.isfile(self.history_log_path))

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            init_state = f.read()
        self.assertIn("# ACTIVE CONTEXT BUFFER", init_state)
        self.assertLess(len(init_state.encode("utf-8")), 2500)

        # -----------------------------------------------------------------
        # STEP 2: Gate 1 - Context Invariant Lock (INSPECT)
        # -----------------------------------------------------------------
        res_gate1 = self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Build cryptographic user authentication module",
            "--gate", "INSPECT",
            "--gate-status", "PENDING",
            "--invariants", "Zero external dependencies\nPBKDF2 key derivation\nConstant-time comparison",
            "--next", "Write contract tests for password hashing in tests/test_auth.py",
            "--task", "Auth Module Spike",
            "--status", "IN_PROGRESS"
        )
        self.assertEqual(res_gate1.returncode, 0, f"Gate 1 update failed: {res_gate1.stderr}")

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            gate1_state = f.read()

        self.assertIn("Build cryptographic user authentication module", gate1_state)
        self.assertIn("Gate**: INSPECT", gate1_state)
        self.assertIn("Zero external dependencies", gate1_state)
        self.assertIn("PBKDF2 key derivation", gate1_state)
        self.assertIn("Constant-time comparison", gate1_state)
        self.assertIn("Write contract tests for password hashing", gate1_state)
        self.assertLess(len(gate1_state.encode("utf-8")), 2500)

        # -----------------------------------------------------------------
        # STEP 3: Gate 2 - Contract-First TDD (CONTRACT - Red)
        # -----------------------------------------------------------------
        # Agent authors contract test before writing any implementation
        test_auth_path = os.path.join(self.repo_dir, "test_auth.py")

        test_code = (
            "import unittest\n"
            "from auth import hash_password, verify_password\n\n"
            "class TestAuthModule(unittest.TestCase):\n"
            "    def test_hash_and_verify_correct_password(self):\n"
            "        hashed = hash_password('ApexSecurePass!')\n"
            "        self.assertTrue(verify_password('ApexSecurePass!', hashed))\n\n"
            "    def test_verify_incorrect_password_fails(self):\n"
            "        hashed = hash_password('ApexSecurePass!')\n"
            "        self.assertFalse(verify_password('WrongPass', hashed))\n\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )
        with open(test_auth_path, "w", encoding="utf-8") as f:
            f.write(test_code)

        # Verify contract test fails (Red state) because auth.py does not exist yet
        red_test_run = subprocess.run(
            [sys.executable, "-m", "unittest", "test_auth.py"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertNotEqual(red_test_run.returncode, 0, "Gate 2 requires test failure before implementation (Red)")

        # Update active state for Gate 2
        res_gate2 = self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Build cryptographic user authentication module",
            "--gate", "CONTRACT",
            "--gate-status", "PENDING",
            "--invariants", "Zero external dependencies\nPBKDF2 key derivation\nConstant-time comparison",
            "--next", "Implement auth.py to satisfy contract tests",
            "--task", "Auth Contract Authoring",
            "--status", "IN_PROGRESS"
        )
        self.assertEqual(res_gate2.returncode, 0, f"Gate 2 update failed: {res_gate2.stderr}")

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            gate2_state = f.read()

        self.assertIn("Gate**: CONTRACT", gate2_state)
        # Git diff section must detect the newly added untracked contract test
        self.assertIn("test_auth.py", gate2_state)
        self.assertLess(len(gate2_state.encode("utf-8")), 2500)

        # -----------------------------------------------------------------
        # STEP 4: Gate 3 - Defensive Production Rigor (IMPLEMENT - Green)
        # -----------------------------------------------------------------
        # Write production-grade implementation satisfying invariants
        auth_impl_path = os.path.join(self.repo_dir, "auth.py")
        auth_code = (
            "import os\n"
            "import hashlib\n"
            "import hmac\n\n"
            "def hash_password(password: str, salt: bytes = None) -> str:\n"
            "    if not isinstance(password, str) or not password:\n"
            "        raise ValueError('Password must be a non-empty string')\n"
            "    if salt is None:\n"
            "        salt = os.urandom(16)\n"
            "    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)\n"
            "    return salt.hex() + ':' + dk.hex()\n\n"
            "def verify_password(password: str, hashed: str) -> bool:\n"
            "    if not isinstance(password, str) or not isinstance(hashed, str):\n"
            "        return False\n"
            "    try:\n"
            "        salt_hex, key_hex = hashed.split(':', 1)\n"
            "        salt = bytes.fromhex(salt_hex)\n"
            "        expected_dk = bytes.fromhex(key_hex)\n"
            "        actual_dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)\n"
            "        return hmac.compare_digest(actual_dk, expected_dk)\n"
            "    except Exception:\n"
            "        return False\n"
        )
        with open(auth_impl_path, "w", encoding="utf-8") as f:
            f.write(auth_code)

        # Update active state for Gate 3
        res_gate3 = self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Build cryptographic user authentication module",
            "--gate", "IMPLEMENT",
            "--gate-status", "PENDING",
            "--invariants", "Zero external dependencies\nPBKDF2 key derivation\nConstant-time comparison",
            "--next", "Execute test suite to empirically verify pass",
            "--task", "Auth Implementation",
            "--status", "IN_PROGRESS"
        )
        self.assertEqual(res_gate3.returncode, 0, f"Gate 3 update failed: {res_gate3.stderr}")

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            gate3_state = f.read()

        self.assertIn("Gate**: IMPLEMENT", gate3_state)
        self.assertIn("auth.py", gate3_state)
        self.assertIn("test_auth.py", gate3_state)
        self.assertLess(len(gate3_state.encode("utf-8")), 2500)

        # -----------------------------------------------------------------
        # STEP 5: Gate 4 - Empirical Terminal Verification & Checkpoint
        # -----------------------------------------------------------------
        # Run test suite to verify tests pass (Green state)
        green_test_run = subprocess.run(
            [sys.executable, "-m", "unittest", "test_auth.py"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.assertEqual(green_test_run.returncode, 0, f"Tests should pass: {green_test_run.stderr}")
        self.assertIn("OK", green_test_run.stderr)

        # Git commit the new feature
        subprocess.run(["git", "add", "."], cwd=self.repo_dir, check=True)
        commit_res = subprocess.run(
            ["git", "commit", "-m", "feat(auth): implement user authentication with pbkdf2"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )

        expected_commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=self.repo_dir,
            stdout=subprocess.PIPE,
            text=True,
            check=True
        ).stdout.strip()

        # Update Gate 4 status to PASSED
        res_gate4 = self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Build cryptographic user authentication module",
            "--gate", "VERIFY",
            "--gate-status", "PASSED",
            "--invariants", "Zero external dependencies\nPBKDF2 key derivation\nConstant-time comparison",
            "--next", "Feature verified and committed; log epoch milestone checkpoint",
            "--task", "Auth Feature Verification",
            "--status", "COMPLETED"
        )
        self.assertEqual(res_gate4.returncode, 0, f"Gate 4 update failed: {res_gate4.stderr}")

        # Execute Checkpoint
        res_checkpoint = self._run_cli(
            "checkpoint",
            "--dir", self.repo_dir,
            "--msg", "Completed user auth feature",
            "--status", "COMPLETED"
        )
        self.assertEqual(res_checkpoint.returncode, 0, f"Checkpoint failed: {res_checkpoint.stderr}")

        # -----------------------------------------------------------------
        # VERIFICATION: Final state integrity and history ledger
        # -----------------------------------------------------------------
        with open(self.active_state_path, "r", encoding="utf-8") as f:
            final_active_state = f.read()

        self.assertIn("- **Last Status**: PASSED", final_active_state)
        self.assertIn("- **Status**: COMPLETED", final_active_state)
        self.assertLess(
            len(final_active_state.encode("utf-8")),
            2500,
            "active_state.md must strictly adhere to the < 2,500 byte bounded invariant"
        )

        with open(self.history_log_path, "r", encoding="utf-8") as f:
            history_content = f.read()

        self.assertIn("## Epoch [001]: Completed user auth feature", history_content)
        self.assertIn(f"- **Commit**: `{expected_commit}`", history_content)
        self.assertIn("- **Status**: COMPLETED", history_content)
        self.assertIn("Completed user auth feature", history_content)

        # Status CLI validation
        res_status = self._run_cli("status", "--dir", self.repo_dir)
        self.assertEqual(res_status.returncode, 0)
        self.assertEqual(res_status.stdout.strip(), final_active_state.strip())

    def test_multi_epoch_history_accumulation_and_bound_maintenance(self):
        """Verify multiple milestone checkpoints accumulate in history.log while active state remains bounded."""
        self._run_cli("init", "--dir", self.repo_dir)

        # Milestone 1
        self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Milestone 1: Database Migration",
            "--gate", "MIGRATE",
            "--gate-status", "PASSED",
            "--invariants", "Schema backward compatibility",
            "--next", "Proceed to Milestone 2",
            "--status", "COMPLETED"
        )
        self._run_cli("checkpoint", "--dir", self.repo_dir, "--msg", "Database schema migration v1", "--status", "COMPLETED")

        # Milestone 2
        self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Milestone 2: User Service API",
            "--gate", "API_CONTRACT",
            "--gate-status", "PASSED",
            "--invariants", "REST endpoints strictly typed",
            "--next", "Proceed to Milestone 3",
            "--status", "COMPLETED"
        )
        self._run_cli("checkpoint", "--dir", self.repo_dir, "--msg", "User Service API routes", "--status", "COMPLETED")

        # Milestone 3
        self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Milestone 3: Billing Gateway Integration",
            "--gate", "PAYMENT_GATEWAY",
            "--gate-status", "PASSED",
            "--invariants", "Idempotent webhooks",
            "--next", "All milestones deployed",
            "--status", "COMPLETED"
        )
        self._run_cli("checkpoint", "--dir", self.repo_dir, "--msg", "Stripe payment integration", "--status", "COMPLETED")

        with open(self.history_log_path, "r", encoding="utf-8") as f:
            history = f.read()

        self.assertIn("## Epoch [001]: Database schema migration v1", history)
        self.assertIn("## Epoch [002]: User Service API routes", history)
        self.assertIn("## Epoch [003]: Stripe payment integration", history)

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            active = f.read()

        self.assertIn("Milestone 3: Billing Gateway Integration", active)
        self.assertLess(len(active.encode("utf-8")), 2500)

    def test_massive_diff_churn_strictly_bounded_under_2500_bytes(self):
        """Simulate huge git churn across 80 files and verify active_state.md is bounded and truncated safely."""
        self._run_cli("init", "--dir", self.repo_dir)

        # Create 80 untracked files in the root repo directory to produce a massive git status output (> 4,000 bytes)
        for i in range(80):
            filename = f"churn_overflow_guard_test_module_long_identifier_{i:04d}.py"
            with open(os.path.join(self.repo_dir, filename), "w", encoding="utf-8") as f:
                f.write(f"# Auto-generated module {i}\nprint('churn {i}')\n")

        res_update = self._run_cli(
            "update",
            "--dir", self.repo_dir,
            "--goal", "Stress test git diff overflow handler",
            "--gate", "STRESS_GATE",
            "--gate-status", "PENDING",
            "--invariants", "Strict bounded buffer <= 2500 bytes",
            "--next", "Verify truncation marker exists",
            "--status", "IN_PROGRESS"
        )
        self.assertEqual(res_update.returncode, 0, f"Update failed under churn: {res_update.stderr}")

        with open(self.active_state_path, "r", encoding="utf-8") as f:
            content = f.read()

        content_bytes = len(content.encode("utf-8"))
        self.assertLess(
            content_bytes,
            2500,
            f"Active state exceeded 2,500 bytes under churn: actual size {content_bytes} bytes"
        )
        self.assertIn("... (truncated)", content)


if __name__ == "__main__":
    unittest.main()
