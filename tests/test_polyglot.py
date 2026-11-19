#!/usr/bin/env python3
"""
Unit Tests for ApexEngine Polyglot Engine & Quick Step.
Verifies multi-language support (TypeScript/JavaScript, Go, Rust, Python),
NPM dependency checks, compiler error parsing, and rapid memory updates.
"""

import os
import sys
import json
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.gatekeeper import check_placeholders
from scripts.dep_guard import check_directory, extract_js_ts_imports
from scripts.self_heal import parse_error_log
from scripts.vibe_synthesizer import synthesize_spec
from scripts.condense import init_context, quick_step, get_status


class TestPolyglotEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_gatekeeper_catches_polyglot_placeholders(self):
        # 1. Rust todo!()
        rs_file = os.path.join(self.test_dir, "lib.rs")
        with open(rs_file, "w", encoding="utf-8") as f:
            f.write("fn calculate() -> i32 {\n    todo!()\n}\n")

        # 2. Go empty error handler
        go_file = os.path.join(self.test_dir, "main.go")
        with open(go_file, "w", encoding="utf-8") as f:
            f.write("func check(err error) {\n    if err != nil {\n    }\n}\n")

        # 3. JS swallowed catch
        js_file = os.path.join(self.test_dir, "app.js")
        with open(js_file, "w", encoding="utf-8") as f:
            f.write("fetchData().catch(() => {});\n")

        violations = check_placeholders(self.test_dir, ["lib.rs", "main.go", "app.js"])
        self.assertTrue(any("Rust todo!()" in v for v in violations))
        self.assertTrue(any("Go empty error handler" in v for v in violations))
        self.assertTrue(any("swallowed promise catch" in v for v in violations))

    def test_dep_guard_npm_verification(self):
        # Create package.json with react and lodash
        pkg_json = {
            "name": "sample-app",
            "dependencies": {"react": "^18.0.0", "lodash": "^4.17.21"},
            "devDependencies": {"typescript": "^5.0.0"}
        }
        with open(os.path.join(self.test_dir, "package.json"), "w", encoding="utf-8") as f:
            json.dump(pkg_json, f)

        # Create valid TS file with node builtin and declared deps
        ts_valid = os.path.join(self.test_dir, "valid.ts")
        with open(ts_valid, "w", encoding="utf-8") as f:
            f.write("import * as fs from 'fs';\nimport React from 'react';\nimport { debounce } from 'lodash';\n")

        violations = check_directory(self.test_dir)
        self.assertEqual(len(violations), 0)

        # Create invalid TS file with hallucinated package
        ts_invalid = os.path.join(self.test_dir, "invalid.ts")
        with open(ts_invalid, "w", encoding="utf-8") as f:
            f.write("import { magicUtil } from 'nonexistent-fake-ai-lib';\n")

        violations_after = check_directory(self.test_dir)
        self.assertEqual(len(violations_after), 1)
        self.assertIn("nonexistent-fake-ai-lib", violations_after[0])

    def test_self_heal_polyglot_parsers(self):
        # 1. TypeScript tsc error
        ts_log = "src/components/Header.tsx(42,12): error TS2339: Property 'avatar' does not exist on type 'User'."
        diag_ts = parse_error_log(ts_log)
        self.assertEqual(diag_ts["failing_file"], "src/components/Header.tsx")
        self.assertEqual(diag_ts["line_number"], 42)
        self.assertEqual(diag_ts["error_type"], "TS2339")

        # 2. Go build error
        go_log = "server.go:88:5: cannot use val (variable of type int) as string in assignment"
        diag_go = parse_error_log(go_log)
        self.assertEqual(diag_go["failing_file"], "server.go")
        self.assertEqual(diag_go["line_number"], 88)
        self.assertEqual(diag_go["error_type"], "GoCompilerError")

        # 3. Rust error
        rs_log = "error[E0425]: cannot find value 'buffer' in this scope\n  --> src/network.rs:34:9\n"
        diag_rs = parse_error_log(rs_log)
        self.assertEqual(diag_rs["failing_file"], "src/network.rs")
        self.assertEqual(diag_rs["line_number"], 34)
        self.assertEqual(diag_rs["error_type"], "E0425")

    def test_vibe_synthesizer_polyglot(self):
        # React prompt
        react_spec = synthesize_spec("Build React dashboard for crypto prices with websockets")
        self.assertTrue(any(".tsx" in f["path"] or ".ts" in f["path"] for f in react_spec["files"]))
        self.assertTrue(any("npm test" in s for s in react_spec["test_plan"]))

        # Go prompt
        go_spec = synthesize_spec("Build Go microservice for event streaming")
        self.assertTrue(any(".go" in f["path"] for f in go_spec["files"]))
        self.assertTrue(any("go test" in s for s in go_spec["test_plan"]))

        # Rust prompt
        rust_spec = synthesize_spec("Build Rust memory-safe parser for markdown")
        self.assertTrue(any(".rs" in f["path"] for f in rust_spec["files"]))
        self.assertTrue(any("cargo test" in s for s in rust_spec["test_plan"]))

    def test_quick_step_functionality(self):
        init_context(self.test_dir)
        quick_step(self.test_dir, "Implemented database schema; next is writing unit tests")

        status_text, ok = get_status(self.test_dir)
        self.assertTrue(ok)
        self.assertIn("Implemented database schema; next is writing unit tests", status_text)


if __name__ == "__main__":
    unittest.main()
