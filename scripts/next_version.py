#!/usr/bin/env python3
"""Print the next release tag for the skills bundle.

    python3 scripts/next_version.py                      # today (UTC), tags from git
    python3 scripts/next_version.py --date 2026.11.04    # a given date
    python3 scripts/next_version.py --tags v2026.11.04 v2026.11.04.1

A version is the UTC date of the release run as YYYY.MM.DD. The first release
of a day has no suffix; each later one that day appends .1, .2, and so on. The
tag is "v" followed by the version. See "Releases" in README.md.

Exits 1 if the next tag would not be greater than every existing v* tag, which
catches a wrong clock or a hand-made tag. Tags that do not match the format
(including impossible dates such as v2026.02.30) are ignored, with a warning on
stderr. An ignored tag is not part of that check, so a malformed tag cannot
block a release; the warning is the signal to delete it.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone

# A date, optionally + .N, used with fullmatch. valid_date() checks the date's
# shape (zero-padded YYYY.MM.DD, a real day). N has no leading zero, so each
# version has exactly one spelling.
VERSION = re.compile(r"(\d+\.\d+\.\d+)(?:\.([1-9]\d*))?")


def valid_date(date: str) -> bool:
    """True if date is a real calendar date written as YYYY.MM.DD."""
    if not re.fullmatch(r"\d{4}\.\d{2}\.\d{2}", date):
        return False
    try:
        datetime.strptime(date, "%Y.%m.%d")
    except ValueError:
        return False
    return True


def version_key(version: str) -> tuple[int, ...]:
    """The ordering rule for skills versions. Clients must implement the same rule.

    Compare segment by segment as integers; a missing segment counts as 0.
    So 2026.11.04 < 2026.11.04.1 < 2026.11.04.10 < 2026.11.05.

    The key pads to four segments (YYYY, MM, DD, N), so a tuple comparison is
    the whole rule.
    """
    parts = [int(p) for p in version.split(".")]
    return tuple(parts + [0] * (4 - len(parts)))


def git_tags() -> list[str]:
    out = subprocess.run(
        ["git", "tag", "--list", "v*"], check=True, capture_output=True, text=True
    ).stdout
    return out.split()


def next_tag(date: str, tags: list[str]) -> str:
    """Return the next tag for `date`. Raise ValueError if it would not be newest."""
    if not valid_date(date):
        raise ValueError(f"date {date!r} is not a real date written as YYYY.MM.DD")

    versions: list[str] = []
    for tag in tags:
        if not tag.startswith("v"):
            continue
        m = VERSION.fullmatch(tag[1:])
        if not m or not valid_date(m.group(1)):
            print(f"warning: ignoring tag {tag!r}: not v<YYYY.MM.DD>[.N]", file=sys.stderr)
            continue
        versions.append(tag[1:])

    same_day = [version_key(v)[3] for v in versions if v == date or v.startswith(date + ".")]
    version = date if not same_day else f"{date}.{max(same_day) + 1}"

    newest = max(versions, key=version_key, default=None)
    if newest is not None and version_key(version) <= version_key(newest):
        raise ValueError(
            f"next version {version} is not greater than existing tag v{newest}; "
            "check the clock, or look for a hand-made tag"
        )
    return f"v{version}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", help="UTC date as YYYY.MM.DD (default: today in UTC)")
    ap.add_argument("--tags", nargs="*", help="existing tags (default: git tag --list 'v*')")
    args = ap.parse_args(argv)

    date = args.date or datetime.now(timezone.utc).strftime("%Y.%m.%d")
    try:
        tags = args.tags if args.tags is not None else git_tags()
        print(next_tag(date, tags))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
