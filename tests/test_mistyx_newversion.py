import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mistyx"))
import mock_zenodo


class NewVersionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.api = HTTPServer(("127.0.0.1", 0), mock_zenodo.H)
        self.thread = threading.Thread(target=self.api.serve_forever, daemon=True)
        self.thread.start()
        mock_zenodo.STATE.update({
            "draft": None,
            "published_new": None,
            "files": [],
            "proof_marker": None,
            "proof_seen_at_newversion": None,
        })
        self.metadata = {
            "upload_type": "software",
            "title": "Test software",
            "version": "1.1.0",
            "description": "A test release.",
            "access_right": "open",
            "license": "gpl-3.0-or-later",
            "creators": [{"name": "Researcher"}],
            "repository": "https://github.com/example/project",
            "programming_language": ["Python"],
        }
        self.metadata_path = self.root / "misty.json"
        self.artifact_path = self.root / "artifact.tar.gz"
        self.artifact_path.write_bytes(b"test artifact")
        self.write_metadata()

    def tearDown(self):
        self.api.shutdown()
        self.api.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def write_metadata(self):
        self.metadata_path.write_text(json.dumps(self.metadata), encoding="utf-8")

    def run_newversion(self, *args, input_text=None):
        env = os.environ.copy()
        env["ZENODO_TOKEN"] = "mock-token"
        script = Path(__file__).resolve().parents[1] / "mistyx" / "mistyx.py"
        return subprocess.run(
            [
                sys.executable,
                str(script),
                "--api-base",
                f"http://127.0.0.1:{self.api.server_port}/api",
                "newversion",
                "--concept",
                "10.5281/zenodo.21303400",
                "-m",
                str(self.metadata_path),
                "-f",
                str(self.artifact_path),
                *args,
            ],
            input=input_text,
            text=True,
            capture_output=True,
            env=env,
            cwd=self.root,
            check=False,
        )

    def test_dry_run_does_not_create_draft(self):
        result = self.run_newversion()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY-RUN", result.stdout)
        self.assertIsNone(mock_zenodo.STATE["draft"])
        self.assertIsNone(mock_zenodo.STATE["published_new"])

    def test_mint_keeps_existing_concept_and_uploads_artifact(self):
        result = self.run_newversion("--mint", input_text="MINT\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        published = mock_zenodo.STATE["published_new"]
        self.assertEqual(
            published["conceptdoi"], "10.5281/zenodo.21303400"
        )
        self.assertEqual(published["metadata"]["version"], "1.1.0")
        self.assertIn("Python", published["metadata"]["keywords"])
        self.assertIn(
            {
                "identifier": "https://github.com/example/project",
                "relation": "isSupplementTo",
                "scheme": "url",
            },
            published["metadata"]["related_identifiers"],
        )
        self.assertEqual(
            mock_zenodo.STATE["files"],
            [{"filename": "artifact.tar.gz", "size": len(b"test artifact")}],
        )
        output = json.loads((self.root / "mistyx_result.json").read_text())
        self.assertEqual(output["concept_doi"], "10.5281/zenodo.21303400")

    def test_invalid_api_metadata_fails_before_draft_creation(self):
        self.metadata["unexpected"] = "not a Zenodo API field"
        self.write_metadata()
        result = self.run_newversion()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported misty/Zenodo metadata field", result.stderr)
        self.assertIsNone(mock_zenodo.STATE["draft"])

    def test_version_must_be_bumped_before_draft_creation(self):
        self.metadata["version"] = "1.0.0"
        self.write_metadata()
        result = self.run_newversion()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("matches the latest published version", result.stderr)
        self.assertIsNone(mock_zenodo.STATE["draft"])

    def test_wrong_concept_is_refused(self):
        script = Path(__file__).resolve().parents[1] / "mistyx" / "mistyx.py"
        env = os.environ.copy()
        env["ZENODO_TOKEN"] = "mock-token"
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--api-base",
                f"http://127.0.0.1:{self.api.server_port}/api",
                "newversion",
                "--concept",
                "99999999",
                "-m",
                str(self.metadata_path),
                "-f",
                str(self.artifact_path),
                "--mint",
            ],
            input="MINT\n",
            text=True,
            capture_output=True,
            env=env,
            cwd=self.root,
            check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no published record matching", result.stderr)
        self.assertIsNone(mock_zenodo.STATE["draft"])


if __name__ == "__main__":
    unittest.main()
