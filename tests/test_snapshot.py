import os
import shutil
import tempfile
import unittest
import subprocess
import zipfile
from pathlib import Path

class TestSnapshotAndQuery(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "scripts", "condense.py")
        )
        # Initialize context in test_dir
        subprocess.run(
            ["python", self.script_path, "init", "--dir", self.test_dir],
            check=True,
            capture_output=True,
            text=True
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_snapshot_creates_valid_zip_archive(self):
        # Update active state with some mock data
        subprocess.run(
            [
                "python", self.script_path, "update",
                "--dir", self.test_dir,
                "--goal", "Test snapshot feature",
                "--gate", "CONTRACT",
                "--next", "Verify zip output"
            ],
            check=True,
            capture_output=True,
            text=True
        )

        # Run snapshot command
        res = subprocess.run(
            [
                "python", self.script_path, "snapshot",
                "--dir", self.test_dir,
                "--msg", "Snapshot epoch 1 milestone"
            ],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0, f"Snapshot command failed: {res.stderr}")

        snapshots_dir = Path(self.test_dir) / ".context" / "snapshots"
        self.assertTrue(snapshots_dir.exists(), "Snapshots directory must exist")
        
        zip_files = list(snapshots_dir.glob("*.zip"))
        self.assertGreaterEqual(len(zip_files), 1, "At least one zip snapshot must be created")
        
        # Verify zip contents
        target_zip = zip_files[0]
        with zipfile.ZipFile(target_zip, "r") as zf:
            namelist = zf.namelist()
            self.assertIn("active_state.md", namelist)
            self.assertIn("snapshot_meta.json", namelist)

    def test_query_searches_past_milestones(self):
        # Create a checkpoint
        subprocess.run(
            [
                "python", self.script_path, "checkpoint",
                "--dir", self.test_dir,
                "--msg", "Implemented PBKDF2 Password Hashing Engine"
            ],
            check=True,
            capture_output=True,
            text=True
        )
        
        # Query for PBKDF2
        res = subprocess.run(
            [
                "python", self.script_path, "query",
                "--dir", self.test_dir,
                "--keyword", "PBKDF2"
            ],
            capture_output=True,
            text=True
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("PBKDF2", res.stdout)
        self.assertIn("Epoch [001]", res.stdout)

if __name__ == "__main__":
    unittest.main()
