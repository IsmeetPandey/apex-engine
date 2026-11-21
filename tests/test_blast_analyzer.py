#!/usr/bin/env python3
"""
Unit Tests for ApexEngine Blast Radius Analyzer (scripts/blast_analyzer.py)
Verifies import parsing, reverse dependency graph construction, and downstream impact calculation.
"""

import os
import sys
import tempfile
import unittest
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.blast_analyzer import (
    parse_python_imports,
    parse_js_ts_imports,
    build_dependency_graph,
    calculate_blast_radius
)


class TestBlastAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_dir, "src")
        self.tests_dir = os.path.join(self.test_dir, "tests")
        os.makedirs(self.src_dir, exist_ok=True)
        os.makedirs(self.tests_dir, exist_ok=True)

        # Create multi-module dependency chain:
        # auth.py <- api.py <- app.py
        # auth.py companion test: tests/test_auth.py
        self.auth_file = os.path.join(self.src_dir, "auth.py")
        with open(self.auth_file, "w", encoding="utf-8") as f:
            f.write("def verify_token(token: str) -> bool:\n    return len(token) > 5\n")

        self.api_file = os.path.join(self.src_dir, "api.py")
        with open(self.api_file, "w", encoding="utf-8") as f:
            f.write("from src.auth import verify_token\n\ndef handle_login(token: str):\n    return verify_token(token)\n")

        self.app_file = os.path.join(self.src_dir, "app.py")
        with open(self.app_file, "w", encoding="utf-8") as f:
            f.write("from src.api import handle_login\n\ndef run():\n    return handle_login('secret')\n")

        self.test_auth = os.path.join(self.tests_dir, "test_auth.py")
        with open(self.test_auth, "w", encoding="utf-8") as f:
            f.write("from src.auth import verify_token\n\ndef test_auth():\n    assert verify_token('valid_token')\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_python_imports(self):
        imports = parse_python_imports(self.api_file)
        self.assertIn("src.auth", imports)

    def test_parse_js_ts_imports(self):
        ts_file = os.path.join(self.src_dir, "service.ts")
        with open(ts_file, "w", encoding="utf-8") as f:
            f.write("import { Client } from './client';\nconst config = require('./config');\n")
        imports = parse_js_ts_imports(ts_file)
        self.assertIn("./client", imports)
        self.assertIn("./config", imports)

    def test_blast_radius_calculation(self):
        # When auth.py is modified:
        # Direct consumer: src/api.py, tests/test_auth.py
        # Indirect consumer: src/app.py
        report = calculate_blast_radius(self.test_dir, ["src/auth.py"])

        self.assertEqual(report["modified_files"], ["src/auth.py"])
        direct_norm = [f.replace("\\", "/") for f in report["direct_consumers"]]
        indirect_norm = [f.replace("\\", "/") for f in report["indirect_consumers"]]

        self.assertIn("src/api.py", direct_norm)
        self.assertIn("src/app.py", indirect_norm)
        self.assertIn("tests/test_auth.py", [t.replace("\\", "/") for t in report["required_tests"]])


if __name__ == "__main__":
    unittest.main()
