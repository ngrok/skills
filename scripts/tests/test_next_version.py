"""Tests for scripts/next_version.py.

    python3 -m unittest discover -s scripts/tests

Each test names the one-line change in next_version.py that turns it red.
"""

from __future__ import annotations

import contextlib
import io
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from next_version import main, next_tag, version_key  # noqa: E402

DATE = "2026.11.04"


def quiet(fn, *args):
    """Call fn, returning (result, stderr)."""
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        result = fn(*args)
    return result, err.getvalue()


class NextTag(unittest.TestCase):
    def test_no_tag_for_date(self):
        # Red if `version = date if not same_day` always appends a suffix.
        self.assertEqual(next_tag(DATE, ["v2026.11.03", "v2026.11.03.2"]), "v2026.11.04")

    def test_bare_tag_counts_as_suffix_zero(self):
        # Red if version_key() stops padding the missing suffix with 0
        # (`+ [0] * (4 - len(parts))` removed): the bare tag then has no
        # index 3 and next_tag raises IndexError.
        self.assertEqual(next_tag(DATE, ["v2026.11.04"]), "v2026.11.04.1")

    def test_suffix_9_goes_to_10(self):
        # Red if version_key() keeps segments as strings (`int(p)` -> `p`):
        # "10" < "9" as text, so .9 looks like the highest suffix.
        tags = [f"v{DATE}"] + [f"v{DATE}.{n}" for n in range(1, 10)]
        self.assertEqual(next_tag(DATE, tags), "v2026.11.04.10")
        self.assertEqual(next_tag(DATE, tags + ["v2026.11.04.10"]), "v2026.11.04.11")

    def test_suffix_follows_highest_not_count(self):
        # Red if `max(same_day) + 1` becomes `len(same_day)`: with a gap in
        # the suffixes, the count is lower than the highest suffix.
        self.assertEqual(next_tag(DATE, [f"v{DATE}", f"v{DATE}.5"]), "v2026.11.04.6")

    def test_newer_tag_exists_is_an_error(self):
        # Red if the `if newest is not None and ... <= ...: raise` check is removed.
        with self.assertRaises(ValueError):
            next_tag(DATE, ["v2026.11.05"])

    def test_malformed_tag_is_ignored_with_warning(self):
        # Red if malformed tags are not skipped (`continue` after the warning
        # removed): version_key("2026.11.4-rc1") raises ValueError.
        # Red if the warning `print(...)` is removed: stderr is empty.
        tag, err = quiet(next_tag, DATE, ["v2026.11.4-rc1", "v2026.11.03"])
        self.assertEqual(tag, "v2026.11.04")
        self.assertIn("v2026.11.4-rc1", err)

    def test_unpadded_and_padded_suffix_tags_are_ignored(self):
        # Red if valid_date() loosens `\d{2}` to `\d{1,2}` (v2026.11.5 is then
        # newest, and next_tag raises), or VERSION loosens `[1-9]\d*` to `\d+`
        # (v2026.11.04.01 is then a same-day suffix, giving .2).
        tag, err = quiet(next_tag, DATE, ["v2026.11.5", "v2026.11.04.01"])
        self.assertEqual(tag, "v2026.11.04")
        self.assertIn("v2026.11.5", err)
        self.assertIn("v2026.11.04.01", err)

    def test_impossible_date_tag_is_ignored(self):
        # Red if `or not valid_date(m.group(1))` is removed from the tag check:
        # v2026.13.01 is then newest, and next_tag raises.
        tag, err = quiet(next_tag, DATE, ["v2026.13.01"])
        self.assertEqual(tag, "v2026.11.04")
        self.assertIn("v2026.13.01", err)

    def test_impossible_date_is_an_error(self):
        # Red if valid_date() drops the strptime check (`return True` early).
        for bad in ("2026.02.30", "2026.11.4", "2026-11-04"):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                next_tag(bad, [])


class Ordering(unittest.TestCase):
    def test_ordering_rule(self):
        # Red if version_key() returns the string instead of integer segments.
        ordered = ["2026.11.04", "2026.11.04.1", "2026.11.04.9", "2026.11.04.10", "2026.11.05"]
        self.assertEqual(sorted(reversed(ordered), key=version_key), ordered)


class Main(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = main(list(argv))
        return rc, out.getvalue(), err.getvalue()

    def test_prints_tag(self):
        # Red if main() stops printing the tag (`print(next_tag(...))` removed).
        self.assertEqual(self.run_main("--date", DATE, "--tags", "v2026.11.04"), (0, "v2026.11.04.1\n", ""))

    def test_error_exits_1(self):
        # Red if main() stops catching ValueError: the exception escapes.
        rc, out, err = self.run_main("--date", DATE, "--tags", "v2026.11.05")
        self.assertEqual((rc, out), (1, ""))
        self.assertIn("not greater", err)

    def test_reads_tags_from_git(self):
        # Red if git_tags() stops returning the tags (`return out.split()` ->
        # `return []`): the date then looks unreleased, giving v2026.11.04.
        repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, repo)
        git = ["git", "-c", "user.name=test", "-c", "user.email=test@example.com", "-c", "commit.gpgsign=false"]
        subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
        subprocess.run([*git, "commit", "-q", "--allow-empty", "-m", "test"], cwd=repo, check=True)
        for tag in ("v2026.11.04", "v2026.11.04.1"):
            subprocess.run([*git, "tag", tag], cwd=repo, check=True)
        cwd = os.getcwd()
        os.chdir(repo)
        self.addCleanup(os.chdir, cwd)
        self.assertEqual(self.run_main("--date", DATE), (0, "v2026.11.04.2\n", ""))


if __name__ == "__main__":
    unittest.main()
