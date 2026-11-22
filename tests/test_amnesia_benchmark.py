#!/usr/bin/env python3
"""
Unit and Integration Test Suite: InvariantStore, AST Verification, and Benchmark Mechanics.
Tests all registers, checksum hashing, bounds checking, AST visitors, and CLI subcommands.
Zero external dependencies: Python 3.8+ standard library only.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
import subprocess
import ast
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from invariant_store import InvariantStore
import condense
import gatekeeper
import apex_cli


class TestInvariantStore(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="apex_inv_test_")
        self.context_dir = os.path.join(self.test_dir, ".context")
        condense.init_context(self.test_dir)
        self.store = InvariantStore(self.context_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_store_initialization_and_schema(self):
        """InvariantStore must create invariants.json with required schema and valid checksum."""
        store_file = os.path.join(self.context_dir, "invariants.json")
        self.assertTrue(os.path.isfile(store_file))

        with open(store_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["version"], "1.0.0")
        self.assertIn("checksum", data)
        self.assertIn("registers", data)
        self.assertIn("immutable", data["registers"])
        self.assertIn("monotonic", data["registers"])
        self.assertIn("ephemeral", data["registers"])

        ok, msg = self.store.verify_integrity()
        self.assertTrue(ok, f"Newly initialized store must pass integrity: {msg}")

    def test_tamper_detection_inv005(self):
        """Manual tampering with invariants.json must be caught by verify_integrity (INV005)."""
        store_file = os.path.join(self.context_dir, "invariants.json")
        with open(store_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Tamper with registers directly on disk without updating checksum
        data["registers"]["immutable"]["HACKED_PORT"] = {"type": "int", "value": 9999}
        with open(store_file, "w", encoding="utf-8") as f:
            json.dump(data, f)

        ok, msg = self.store.verify_integrity()
        self.assertFalse(ok)
        self.assertIn("INV005", msg)
        self.assertIn("Checksum mismatch", msg)

    def test_bind_immutable_primitives_and_idempotency(self):
        """Immutable register must store primitives and allow identical re-binding."""
        self.store.bind_immutable("PORT", 8080, val_type="int")
        self.store.bind_immutable("HOST", "127.0.0.1", val_type="string")
        self.store.bind_immutable("ENABLE_SSL", True, val_type="bool")
        self.store.bind_immutable("LATENCY_THRESHOLD", 15.5, val_type="float")
        self.store.bind_immutable("ALLOWED_METHODS", ["GET", "POST"], val_type="list")

        # Idempotent write of identical values must succeed
        self.store.bind_immutable("PORT", 8080)
        self.store.bind_immutable("HOST", "127.0.0.1")

        regs = self.store.get_invariants()
        self.assertEqual(regs["immutable"]["PORT"]["value"], 8080)
        self.assertEqual(regs["immutable"]["HOST"]["value"], "127.0.0.1")
        self.assertEqual(regs["immutable"]["ENABLE_SSL"]["value"], True)
        self.assertEqual(regs["immutable"]["LATENCY_THRESHOLD"]["value"], 15.5)

    def test_bind_immutable_mutation_rejection_inv001(self):
        """Attempting to mutate an immutable invariant must raise ValueError (INV001)."""
        self.store.bind_immutable("MAX_RETRIES", 3, val_type="int")

        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("MAX_RETRIES", 5)

        self.assertIn("INV001", str(ctx.exception))
        self.assertIn("Cannot mutate immutable symbol 'MAX_RETRIES'", str(ctx.exception))

    def test_bind_immutable_bounds_checking_inv004(self):
        """Bounds violations (min, max, choices, regex) must raise ValueError (INV004)."""
        # Min bound
        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("PORT_MIN", 7999, bounds={"min": 8000, "max": 9000})
        self.assertIn("INV004", str(ctx.exception))
        self.assertIn("below min bound", str(ctx.exception))

        # Max bound
        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("PORT_MAX", 9001, bounds={"min": 8000, "max": 9000})
        self.assertIn("INV004", str(ctx.exception))
        self.assertIn("exceeds max bound", str(ctx.exception))

        # Choices bound
        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("ENV", "staging", bounds={"choices": ["dev", "prod"]})
        self.assertIn("INV004", str(ctx.exception))
        self.assertIn("not in allowed choices", str(ctx.exception))

        # Regex bound
        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("VERSION", "beta-1", bounds={"regex": r"^\d+\.\d+\.\d+$"})
        self.assertIn("INV004", str(ctx.exception))
        self.assertIn("does not match regex", str(ctx.exception))

    def test_bind_immutable_type_mismatch_inv003(self):
        """Type mismatches must raise ValueError (INV003)."""
        with self.assertRaises(ValueError) as ctx:
            self.store.bind_immutable("TIMEOUT", "30s", val_type="int")
        self.assertIn("INV003", str(ctx.exception))

    def test_bind_monotonic_transitions_and_regression_inv002(self):
        """Monotonic variables must follow allowed DAG transitions and block regressions."""
        transitions = {
            "PHASE_1": ["PHASE_2"],
            "PHASE_2": ["PHASE_3", "FAILED"],
            "PHASE_3": ["DONE"]
        }
        self.store.bind_monotonic("LIFECYCLE", "PHASE_1", allowed_transitions=transitions)

        # Valid forward transition
        self.store.transition_monotonic("LIFECYCLE", "PHASE_2")
        regs = self.store.get_invariants()
        self.assertEqual(regs["monotonic"]["LIFECYCLE"]["current_value"], "PHASE_2")
        self.assertEqual(len(regs["monotonic"]["LIFECYCLE"]["history"]), 2)

        # Invalid backwards regression (INV002)
        with self.assertRaises(ValueError) as ctx:
            self.store.transition_monotonic("LIFECYCLE", "PHASE_1")
        self.assertIn("INV002", str(ctx.exception))
        self.assertIn("MonotonicRegressionViolation", str(ctx.exception))

        # Disallowed skip transition (INV002)
        with self.assertRaises(ValueError) as ctx:
            self.store.transition_monotonic("LIFECYCLE", "DONE")
        self.assertIn("INV002", str(ctx.exception))

    def test_ephemeral_register_and_clearing(self):
        """Ephemeral variables must store and be cleared upon milestone checkpoint."""
        self.store.bind_ephemeral("TEMP_TOKEN", "tok_abc123")
        self.store.bind_ephemeral("DEBUG_COUNT", 42)

        regs = self.store.get_invariants()
        self.assertEqual(regs["ephemeral"]["TEMP_TOKEN"]["value"], "tok_abc123")

        self.store.clear_ephemeral()
        regs_after = self.store.get_invariants()
        self.assertEqual(len(regs_after["ephemeral"]), 0)

    def test_render_markdown_table_bounded_size(self):
        """Markdown table must render cleanly and fit within byte budget."""
        self.store.bind_immutable("PORT", 8080)
        self.store.bind_immutable("BASELINE_ACCURACY", 0.9465)
        self.store.bind_monotonic("STATE", "GATE_2", {"GATE_2": ["GATE_3"]})

        table = self.store.render_markdown_table(max_bytes=600)
        self.assertIn("## 🔒 Pinned Invariant Register", table)
        self.assertIn("PORT", table)
        self.assertIn("BASELINE_ACCURACY", table)
        self.assertIn("STATE", table)
        self.assertLessEqual(len(table.encode("utf-8")), 600)

    def test_render_markdown_table_high_count_and_padding_strict_byte_budget(self):
        """Table must strictly satisfy len <= max_bytes across varying padding and counts."""
        for pad_len in [5, 11, 20, 25]:
            sub_dir = tempfile.mkdtemp(prefix=f"pad_{pad_len}_")
            try:
                sub_store = InvariantStore(sub_dir)
                for i in range(50):
                    sub_store.bind_immutable(f"VAR_{i}", "x" * pad_len)
                for budget in [200, 222, 290, 358, 426, 494, 562, 600, 800]:
                    rendered = sub_store.render_markdown_table(max_bytes=budget)
                    encoded_len = len(rendered.encode("utf-8"))
                    self.assertLessEqual(
                        encoded_len,
                        budget,
                        f"Table exceeded budget {budget} with pad {pad_len}: got {encoded_len} bytes"
                    )
            finally:
                shutil.rmtree(sub_dir, ignore_errors=True)


class TestGatekeeperInvariantEnforcement(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="apex_gate_inv_test_")
        self.context_dir = os.path.join(self.test_dir, ".context")
        condense.init_context(self.test_dir)
        self.store = InvariantStore(self.context_dir)
        self.store.bind_immutable("HTTP_PORT", 8080, val_type="int", bounds={"min": 8000, "max": 9000})
        self.store.bind_immutable("BASELINE_F1", 0.9450, val_type="float")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ast_visitor_clean_code_passes(self):
        """AST visitor approves code that conforms to invariants."""
        clean_code = "HTTP_PORT = 8080\nBASELINE_F1 = 0.9450\n"
        visitor = gatekeeper.InvariantASTVisitor("server.py", self.store.get_invariants()["immutable"])
        tree = ast.parse(clean_code)
        visitor.visit(tree)
        self.assertEqual(len(visitor.violations), 0)

    def test_ast_visitor_annotated_and_augmented_mutations(self):
        """AST visitor catches AnnAssign and AugAssign mutations."""
        bad_code_ann = "HTTP_PORT: int = 3000\n"
        visitor1 = gatekeeper.InvariantASTVisitor("server.py", self.store.get_invariants()["immutable"])
        visitor1.visit(ast.parse(bad_code_ann))
        self.assertTrue(any(v[1] == "INV001" for v in visitor1.violations))

        bad_code_aug = "HTTP_PORT += 1\n"
        visitor2 = gatekeeper.InvariantASTVisitor("server.py", self.store.get_invariants()["immutable"])
        visitor2.visit(ast.parse(bad_code_aug))
        self.assertTrue(any(v[1] == "INV001" for v in visitor2.violations))

    def test_check_invariants_cross_module_divergence_inv006(self):
        """check_invariants reports INV006 if code defines conflicting constant values."""
        code_file = os.path.join(self.test_dir, "config.py")
        with open(code_file, "w", encoding="utf-8") as f:
            f.write("HTTP_PORT = 9999\n")

        passed, violations = gatekeeper.check_invariants(self.test_dir)
        self.assertFalse(passed)
        self.assertTrue(any("INV001" in v or "INV006" in v for v in violations))

    def test_ast_visitor_type_mismatch_with_numeric_bounds_no_crash(self):
        """Type mismatch on bounded numeric invariant must not crash with TypeError and must record INV001 & INV003."""
        invariants = {
            "TARGET_PORT": {
                "value": 8080,
                "type": "int",
                "bounds": {"min": 1024, "max": 65535}
            }
        }
        # 1. Standard assignment: TARGET_PORT = '8080'
        tree_assign = ast.parse('TARGET_PORT = "8080"')
        visitor_assign = gatekeeper.InvariantASTVisitor("server.py", invariants)
        visitor_assign.visit(tree_assign)
        codes_assign = [v[1] for v in visitor_assign.violations]
        self.assertIn("INV001", codes_assign)
        self.assertIn("INV003", codes_assign)
        self.assertNotIn("INV004", codes_assign)

        # 2. Annotated assignment: TARGET_PORT: int = '8080'
        tree_ann = ast.parse('TARGET_PORT: int = "8080"')
        visitor_ann = gatekeeper.InvariantASTVisitor("server.py", invariants)
        visitor_ann.visit(tree_ann)
        codes_ann = [v[1] for v in visitor_ann.violations]
        self.assertIn("INV001", codes_ann)
        self.assertIn("INV003", codes_ann)
        self.assertNotIn("INV004", codes_ann)


class TestApexCliInvariantSubcommands(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="apex_cli_inv_test_")
        self.context_dir = os.path.join(self.test_dir, ".context")
        condense.init_context(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_apex_bind_and_check_invariants_cli(self):
        """apex bind and apex check-invariants CLI commands succeed end-to-end."""
        # 1. Bind via CLI
        ret_bind = apex_cli.main(["bind", "CLUSTER_ID", "east-cluster-01", "--dir", self.test_dir, "--desc", "Cluster region identifier"])
        self.assertEqual(ret_bind, 0)

        # 2. Check invariants via CLI
        ret_check = apex_cli.main(["check-invariants", "--dir", self.test_dir])
        self.assertEqual(ret_check, 0)

        # 3. Verify store contents
        store = InvariantStore(self.context_dir)
        regs = store.get_invariants()
        self.assertEqual(regs["immutable"]["CLUSTER_ID"]["value"], "east-cluster-01")


if __name__ == "__main__":
    unittest.main()
