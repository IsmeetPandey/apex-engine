import os
import shutil
import tempfile
import unittest
import urllib.request
import json
import time
import subprocess
from pathlib import Path

class TestStudio(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "studio.py")
        )
        self.condense_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "condense.py")
        )
        subprocess.run(["python", self.condense_path, "init", "--dir", self.test_dir], check=True, capture_output=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_studio_html_rendering(self):
        # Import studio module directly to test HTML generation
        import sys
        scripts_dir = os.path.dirname(self.script_path)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import studio

        html = studio.render_studio_html(self.test_dir)
        self.assertIn("ApexEngine Studio", html)
        self.assertIn("ACTIVE CONTEXT BUFFER", html)
        self.assertIn("APEX EPOCH HISTORY LOG", html)

    def test_studio_api_data_structure(self):
        import sys
        scripts_dir = os.path.dirname(self.script_path)
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        import studio

        data = studio.get_studio_data(self.test_dir)
        self.assertIn("active_state", data)
        self.assertIn("history", data)
        self.assertIn("byte_size", data)
        self.assertIn("snapshots", data)

if __name__ == "__main__":
    unittest.main()
