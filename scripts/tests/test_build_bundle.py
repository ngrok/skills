"""Tests for scripts/build_bundle.sh and scripts/check_bundle.sh.

    python3 -m unittest discover -s scripts/tests

Each test builds a throwaway git repo and runs the scripts in it. Each test
names the one-line change in the scripts that turns it red.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
GIT = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]
COMMIT_TIME = "1700000000"  # far from now, so a missing --mtime shows


class Repo(unittest.TestCase):
    def setUp(self):
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        skill = self.repo / "skills" / "one"
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text("one\n")
        (skill / "references" / "a.md").write_text("a\n")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)

    def commit(self):
        env = {**os.environ, "GIT_COMMITTER_DATE": f"@{COMMIT_TIME} +0000", "GIT_AUTHOR_DATE": f"@{COMMIT_TIME} +0000"}
        subprocess.run([*GIT, "add", "-A"], cwd=self.repo, check=True)
        subprocess.run([*GIT, "commit", "-qm", "test"], cwd=self.repo, check=True, env=env)

    def run_script(self, name, *args):
        return subprocess.run(["bash", str(SCRIPTS / name), *args], cwd=self.repo, capture_output=True, text=True)

    def build(self):
        return self.run_script("build_bundle.sh", "out")

    def members(self):
        with tarfile.open(self.repo / "out" / "skills.tar.gz") as tar:
            return {m.name: m for m in tar.getmembers()}


class BuildBundle(Repo):
    def test_builds_from_the_committed_tree(self):
        # Red if `"$tree"` is changed to `"$rev"` in the git archive call: the
        # entries then sit under a wrapping skills/ directory.
        self.commit()
        (self.repo / "skills" / "one" / "untracked.md").write_text("not committed\n")
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(self.members()), ["one", "one/SKILL.md", "one/references", "one/references/a.md"])
        self.assertRegex((self.repo / "out" / "skills.tar.gz.sha256").read_text(), r"^[0-9a-f]{64}  skills\.tar\.gz\n$")

    def test_mtime_is_the_commit_time(self):
        # Red if the `--mtime=...` line is removed: git archive of a tree then
        # stamps entries with the current time.
        self.commit()
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual({m.mtime for m in self.members().values()}, {int(COMMIT_TIME)})

    def test_modes_are_fixed_and_keep_the_executable_bit(self):
        # Red if `-c tar.umask=022` is removed: git's default umask 002 gives
        # 0664 files and 0775 directories.
        tool = self.repo / "skills" / "one" / "tool.sh"
        tool.write_text("#!/bin/sh\n")
        tool.chmod(0o755)
        self.commit()
        self.assertEqual(self.build().returncode, 0)
        modes = {name: m.mode for name, m in self.members().items()}
        self.assertEqual(modes["one"], 0o755)
        self.assertEqual(modes["one/SKILL.md"], 0o644)
        self.assertEqual(modes["one/tool.sh"], 0o755)

    def test_refuses_symlink(self):
        # Red if the mode check is widened to accept any mode
        # (`100644 | 100755) ;;` -> `*) ;;`): the symlink is then archived.
        os.symlink("../../secret.txt", self.repo / "skills" / "one" / "link.md")
        self.commit()
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skills/one/link.md", result.stderr)
        self.assertFalse((self.repo / "out" / "skills.tar.gz").exists())

    def test_refuses_file_outside_skill_directories(self):
        # Red if the `*) echo ... file outside the skill directories` branch is removed.
        (self.repo / "skills" / "stray.md").write_text("stray\n")
        self.commit()
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("skills/stray.md", result.stderr)
        self.assertFalse((self.repo / "out" / "skills.tar.gz").exists())

    def test_bad_rev_fails_once_with_a_clear_error(self):
        # Red if the `git cat-file -t` guard is removed: the error then
        # comes from git, twice, instead of naming the tree.
        self.commit()
        result = self.run_script("build_bundle.sh", "out", "no-such-rev")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr.count("error:"), 1)
        self.assertIn("no-such-rev:skills is not a tree", result.stderr)


class CheckBundle(Repo):
    def setUp(self):
        super().setUp()
        self.commit()
        self.assertEqual(self.build().returncode, 0)

    def test_accepts_a_fresh_build(self):
        result = self.run_script("check_bundle.sh", "out")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rejects_a_bundle_that_differs_from_skills(self):
        # Red if the `diff -r skills "$tmp"` line is removed.
        (self.repo / "skills" / "one" / "SKILL.md").write_text("changed\n")
        self.assertNotEqual(self.run_script("check_bundle.sh", "out").returncode, 0)

    def test_rejects_a_bad_checksum(self):
        # Red if the `shasum -a 256 -c` line is removed.
        (self.repo / "out" / "skills.tar.gz.sha256").write_text("0" * 64 + "  skills.tar.gz\n")
        self.assertNotEqual(self.run_script("check_bundle.sh", "out").returncode, 0)

    def test_rejects_wrong_modes(self):
        # Red if the mode check (`if [ -n "$wrong" ]`) is removed.
        # Rebuild by hand with git's default umask, giving 0664/0775 entries.
        subprocess.run(["git", "-c", "tar.umask=002", "archive", "--format=tar.gz", "-o", "out/skills.tar.gz",
                        "HEAD:skills"], cwd=self.repo, check=True)
        subprocess.run("shasum -a 256 skills.tar.gz > skills.tar.gz.sha256", shell=True, cwd=self.repo / "out", check=True)
        result = self.run_script("check_bundle.sh", "out")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unexpected entry types or modes", result.stderr)


if __name__ == "__main__":
    unittest.main()
