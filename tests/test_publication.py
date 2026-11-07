"""Exercise the actual publisher against isolated local Git repositories."""

from pathlib import Path
import os
import shutil
import subprocess
import tempfile
import unittest


GIT = shutil.which("git")
BASH = str(Path(GIT).parents[2] / "bin/bash.exe") if GIT and os.name == "nt" else shutil.which("bash")
SCRIPT = Path(__file__).resolve().parents[1] / "scripts/publish_languages.sh"


@unittest.skipUnless(GIT and BASH and Path(BASH).exists(), "Git and Bash are required")
class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="language-publication-test-")
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.remote = root / "remote.git"
        self.work = root / "work"
        self.work.mkdir()
        self.git("init", "--bare", str(self.remote))
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Local Test")
        self.git("config", "user.email", "test@example.invalid")
        (self.work / "assets").mkdir()
        (self.work / "assets/languages.svg").write_text("old SVG\n")
        (self.work / "README.md").write_text("original profile\n")
        self.git("add", ".")
        self.git("commit", "-m", "initial fixture")
        self.git("remote", "add", "origin", str(self.remote))
        self.git("push", "-u", "origin", "main")
        self.initial = self.git("rev-parse", "HEAD")

    def git(self, *args, cwd=None):
        result = subprocess.run([GIT, *args], cwd=cwd or self.work,
                                text=True, capture_output=True, check=True)
        return result.stdout.strip()

    def publish(self):
        return subprocess.run([BASH, SCRIPT.as_posix()], cwd=self.work,
                              env={**os.environ, "DEFAULT_BRANCH": "main"},
                              text=True, capture_output=True)

    def test_unchanged_statistics_create_no_commit(self):
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)
        self.assertIn("nothing to publish", result.stdout)

    def test_only_svg_is_committed_and_second_run_is_noop(self):
        (self.work / "assets/languages.svg").write_text("new SVG\n")
        (self.work / "README.md").write_text("unrelated local edit\n")
        result = self.publish()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"), "assets/languages.svg")
        self.assertEqual(self.git("show", "HEAD:README.md"), "original profile")
        self.assertEqual(self.git("rev-parse", "HEAD"), self.git("--git-dir", str(self.remote), "rev-parse", "main"))
        after = self.git("rev-parse", "HEAD")
        self.assertEqual(self.publish().returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), after)

    def test_unexpected_staged_files_stop_publication(self):
        (self.work / "README.md").write_text("unrelated staged edit\n")
        self.git("add", "README.md")
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.initial)
        self.assertIn("Unexpected staged files", result.stdout)

    def test_concurrent_remote_change_is_not_overwritten(self):
        other = Path(self.temporary.name) / "other"
        self.git("clone", "--branch", "main", str(self.remote), str(other))
        self.git("config", "user.name", "Other Test", cwd=other)
        self.git("config", "user.email", "other@example.invalid", cwd=other)
        (other / "README.md").write_text("newer profile\n")
        self.git("add", "README.md", cwd=other)
        self.git("commit", "-m", "concurrent profile change", cwd=other)
        self.git("push", "origin", "main", cwd=other)
        remote_commit = self.git("rev-parse", "HEAD", cwd=other)
        (self.work / "assets/languages.svg").write_text("new SVG\n")
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("push rejected", result.stdout)
        self.assertEqual(self.git("--git-dir", str(self.remote), "rev-parse", "main"), remote_commit)
        self.assertEqual(self.git("--git-dir", str(self.remote), "show", "main:README.md"), "newer profile")


if __name__ == "__main__":
    unittest.main()
