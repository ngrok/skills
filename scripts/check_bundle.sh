#!/usr/bin/env bash
# Check a skills bundle against the checked-out skills/ directory.
#
#     scripts/check_bundle.sh DIR     # DIR holds skills.tar.gz and skills.tar.gz.sha256
#
# Fails unless:
#   - skills.tar.gz matches skills.tar.gz.sha256
#   - it unpacks to exactly the directories under skills/, with the same files
#     and contents
#   - every file is mode 0644 or 0755, and every directory is 0755
#
# PR CI runs it on the bundle it builds, and the release workflow runs it on the
# bundle before upload and again on the published assets after download.
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "usage: $0 DIR" >&2
  exit 2
fi
dir="$1"

# shasum ships with macOS and Ubuntu; sha256sum is not on macOS by default.
(cd "$dir" && shasum -a 256 -c skills.tar.gz.sha256)

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
tar -xzf "$dir/skills.tar.gz" -C "$tmp"

diff <(cd skills && find . -mindepth 1 -maxdepth 1 -type d | sort) \
     <(cd "$tmp" && find . -mindepth 1 -maxdepth 1 | sort)
diff -r skills "$tmp"

# Read the modes from the archive itself; extraction applies the local umask.
wrong="$(tar -tvzf "$dir/skills.tar.gz" | awk '
  /^d/ && $1 != "drwxr-xr-x" { print }
  /^-/ && $1 != "-rw-r--r--" && $1 != "-rwxr-xr-x" { print }
  !/^[d-]/ { print }')"
if [ -n "$wrong" ]; then
  echo "error: unexpected entry types or modes:" >&2
  echo "$wrong" >&2
  exit 1
fi

echo "bundle matches skills/"
