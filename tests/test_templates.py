import os
import unittest

class TestStateTemplates(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.templates_dir = os.path.join(self.base_dir, "templates")

    def test_active_state_template_exists_and_bounded(self):
        path = os.path.join(self.templates_dir, "active_state_template.md")
        self.assertTrue(os.path.exists(path), "active_state_template.md must exist")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# ACTIVE CONTEXT BUFFER", content)
        self.assertIn("## Current Objective & Milestone", content)
        self.assertIn("## Active Hard Gate", content)
        self.assertIn("## Pinned Invariants & Key Symbols", content)
        self.assertIn("## Modified Files & Git Diffs", content)
        self.assertIn("## Immediate Next Action", content)
        self.assertLess(len(content.encode("utf-8")), 2000, "Template must be under 2KB")

    def test_epoch_log_template_exists(self):
        path = os.path.join(self.templates_dir, "epoch_log_template.md")
        self.assertTrue(os.path.exists(path), "epoch_log_template.md must exist")
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("# APEX EPOCH HISTORY LOG", content)

if __name__ == "__main__":
    unittest.main()
