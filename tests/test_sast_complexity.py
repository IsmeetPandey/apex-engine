#!/usr/bin/env python3
"""
Unit Tests for ApexEngine SAST, Complexity & Anti-Tautology Gates (Gatekeeper 3.0)
Verifies static security analysis, McCabe complexity, and test authenticity.
"""

import os
import sys
import tempfile
import unittest
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.gatekeeper import (
    check_sast_and_complexity,
    check_test_authenticity,
    check_placeholders
)


class TestSASTAndComplexity(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_detects_shell_and_code_injection(self):
        bad_file = os.path.join(self.test_dir, "unsafe.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("import os, subprocess\n\ndef run_cmd(user_input):\n    os.system(user_input)\n    eval(user_input)\n")

        violations = check_sast_and_complexity(self.test_dir, ["unsafe.py"])
        self.assertTrue(any("SEC001" in v for v in violations), f"Expected SEC001 in {violations}")
        self.assertTrue(any("SEC005" in v for v in violations), f"Expected SEC005 in {violations}")

    def test_detects_unsafe_deserialization(self):
        bad_file = os.path.join(self.test_dir, "deser.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("import pickle\n\ndef load_data(payload):\n    return pickle.loads(payload)\n")

        violations = check_sast_and_complexity(self.test_dir, ["deser.py"])
        self.assertTrue(any("SEC003" in v for v in violations), f"Expected SEC003 in {violations}")

    def test_detects_sql_injection(self):
        bad_file = os.path.join(self.test_dir, "db.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("def get_user(cursor, user_id):\n    cursor.execute(f'SELECT * FROM users WHERE id = {user_id}')\n")

        violations = check_sast_and_complexity(self.test_dir, ["db.py"])
        self.assertTrue(any("SEC006" in v for v in violations), f"Expected SEC006 in {violations}")

    def test_detects_hardcoded_aws_secrets(self):
        bad_file = os.path.join(self.test_dir, "config.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("AWS_KEY = 'AKIA1234567890ABCDEF'\n")

        violations = check_sast_and_complexity(self.test_dir, ["config.py"])
        self.assertTrue(any("SEC007" in v for v in violations), f"Expected SEC007 in {violations}")

    def test_detects_excessive_complexity(self):
        bad_file = os.path.join(self.test_dir, "complex.py")
        # Function with 12 if branches (CC = 13 > 10)
        lines = ["def evaluate(val):"]
        for i in range(12):
            lines.append(f"    if val == {i}: return {i}")
        lines.append("    return -1")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        violations = check_sast_and_complexity(self.test_dir, ["complex.py"])
        self.assertTrue(any("CMP003" in v for v in violations), f"Expected CMP003 in {violations}")

    def test_detects_test_tautologies_and_empty_bodies(self):
        test_file = os.path.join(self.test_dir, "test_vacuous.py")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("def test_nothing():\n    pass\n\ndef test_tautology():\n    assert True\n")

        violations = check_test_authenticity(self.test_dir, ["test_vacuous.py"])
        self.assertTrue(any("TST001" in v for v in violations), f"Expected TST001 in {violations}")
        self.assertTrue(any("TST003" in v for v in violations), f"Expected TST003 in {violations}")

    def test_detects_commented_placeholders_and_empty_catches(self):
        bad_file = os.path.join(self.test_dir, "worker.py")
        with open(bad_file, "w", encoding="utf-8") as f:
            f.write("def stub():\n    pass  # to be done later\n\ndef handle():\n    try:\n        x = 1\n    except:\n        pass\n")

        violations = check_placeholders(self.test_dir, ["worker.py"])
        self.assertTrue(any("pass" in v for v in violations), f"Expected pass violation in {violations}")
        self.assertTrue(any("silent exception suppression" in v for v in violations), f"Expected except: pass violation in {violations}")


if __name__ == "__main__":
    unittest.main()
