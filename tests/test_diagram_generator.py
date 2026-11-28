#!/usr/bin/env python3
"""
Unit Tests for ApexEngine HTML Architecture Visualizer (scripts/diagram_generator.py)
Verifies standalone zero-dependency HTML/SVG generation, component mapping,
and state-machine contract visualizer without chat memory pollution.
"""

import os
import sys
import tempfile
import unittest
import shutil

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts.diagram_generator import generate_architecture_html, build_diagram_model


class TestDiagramGenerator(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.src_dir = os.path.join(self.test_dir, "src")
        os.makedirs(self.src_dir, exist_ok=True)

        # Scaffolding mock workspace files
        with open(os.path.join(self.src_dir, "gateway.py"), "w", encoding="utf-8") as f:
            f.write("import src.auth\ndef route(): return src.auth.verify()\n")
        with open(os.path.join(self.src_dir, "auth.py"), "w", encoding="utf-8") as f:
            f.write("def verify(): return True\n")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_builds_diagram_model_from_workspace(self):
        model = build_diagram_model(self.test_dir)
        self.assertIn("modules", model)
        self.assertIn("states", model)
        self.assertIn("invariants", model)
        module_names = [m["name"].replace("\\", "/") for m in model["modules"]]
        self.assertTrue(any("gateway" in m for m in module_names))
        self.assertTrue(any("auth" in m for m in module_names))

    def test_generates_valid_standalone_html(self):
        out_html = os.path.join(self.test_dir, "docs", "architecture.html")
        res_path = generate_architecture_html(self.test_dir, out_path=out_html)

        self.assertTrue(os.path.isfile(res_path))
        with open(res_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Must be valid self-contained HTML5
        self.assertIn("<!DOCTYPE html>", content)
        self.assertIn("<svg", content)
        self.assertIn("ApexEngine Architecture HUD", content)
        self.assertIn("gateway.py", content)
        self.assertIn("auth.py", content)
        # Verify dark-mode styling is embedded
        self.assertIn("#0d1117", content)


if __name__ == "__main__":
    unittest.main()
