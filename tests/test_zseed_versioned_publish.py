import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import HTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mistyx"))
import mock_zenodo


ROOT = Path(__file__).resolve().parents[1]


class ZseedVersionedPublishTests(unittest.TestCase):
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
            "proof_marker": str(self.root / "proof-created"),
            "proof_seen_at_newversion": None,
        })
        (self.root / "mistyx").mkdir()
        shutil.copy2(ROOT / "zseed.sh", self.root / "zseed.sh")
        shutil.copy2(ROOT / "mistyx" / "mistyx.py", self.root / "mistyx.py")
        (self.root / "artifact.tar.gz").write_bytes(b"release archive")
        metadata = {
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
        (self.root / "misty.json").write_text(json.dumps(metadata), encoding="utf-8")
        manifest = {
            "name": "zseed-integration-test",
            "repo": "example/project",
            "artifact": "artifact.tar.gz",
            "doi_mode": "newversion",
            "concept_doi": "10.5281/zenodo.21303400",
            "mistyx": "mistyx.py",
            "provenance_dir": "provenance",
            "inject_into": [],
            "push_files": [],
            "pages": False,
        }
        (self.root / "seed.json").write_text(json.dumps(manifest), encoding="utf-8")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        ots = self.bin / "ots"
        ots.write_text(
            "#!/bin/sh\n"
            "[ \"$1\" = stamp ] || exit 2\n"
            "printf 'mock OTS proof' > \"$2.ots\"\n"
            "printf 'created' > \"$OTS_MARKER\"\n",
            encoding="utf-8",
        )
        ots.chmod(0o755)
        self.home = self.root / "home"
        self.home.mkdir()
        (self.root / ".seedwork").mkdir()
        (self.root / ".seedwork" / "sentinel").write_text("keep", encoding="utf-8")
        (self.root / ".doi-dryrun").mkdir()
        (self.root / ".doi-dryrun" / "sentinel").write_text("keep", encoding="utf-8")

    def tearDown(self):
        self.api.shutdown()
        self.api.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def test_versioned_publish_stamps_first_and_preserves_unowned_files(self):
        env = os.environ.copy()
        env.update({
            "ZENODO_TOKEN": "mock-token",
            "MISTYX_API_BASE": f"http://127.0.0.1:{self.api.server_port}/api",
            "OTS_MARKER": str(self.root / "proof-created"),
            "HOME": str(self.home),
            "PATH": str(self.bin) + os.pathsep + env.get("PATH", ""),
        })
        result = subprocess.run(
            ["bash", "zseed.sh", "--publish"],
            cwd=self.root,
            input="MINT\n",
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(mock_zenodo.STATE["proof_seen_at_newversion"])
        self.assertEqual(
            mock_zenodo.STATE["published_new"]["conceptdoi"],
            "10.5281/zenodo.21303400",
        )
        proof = self.root / "provenance" / "artifact.tar.gz.ots"
        self.assertEqual(proof.read_text(encoding="utf-8"), "mock OTS proof")
        self.assertEqual(
            (self.root / "ZENODO_DOI.txt").read_text(encoding="utf-8").strip(),
            "10.5281/zenodo.21309999",
        )
        self.assertTrue((self.root / ".seedwork" / "sentinel").is_file())
        self.assertTrue((self.root / ".doi-dryrun" / "sentinel").is_file())
        self.assertEqual(list((self.root / ".seedwork").iterdir()), [
            self.root / ".seedwork" / "sentinel"
        ])
        self.assertLess(
            result.stdout.index("OTS proof preserved before publication"),
            result.stdout.index("PUBLISHED new version"),
        )


if __name__ == "__main__":
    unittest.main()
