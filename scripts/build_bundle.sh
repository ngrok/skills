#!/usr/bin/env bash
# Build the skills bundle that each release carries.
#
#     scripts/build_bundle.sh OUT_DIR [REV]     # REV defaults to HEAD
#
# Writes two files to OUT_DIR:
#
#   skills.tar.gz         one top-level directory per directory under skills/,
#                         with that directory's files, and nothing else
#   skills.tar.gz.sha256  one line in sha256sum format: "<hex>  skills.tar.gz"
#
# The bundle is `git archive` of the committed skills/ tree, so untracked files
# never ship. --mtime pins every entry to the commit time (without it, git uses
# the current time for a tree), and tar.umask=022 gives 0644 files and 0755
# directories, keeping the executable bit. So one commit gives the same bytes
# on the same git version. The release publishes its own sha256, so clients
# never need to rebuild the bytes themselves.
#
# The release workflow and PR CI both call this script, and check the result
# with scripts/check_bundle.sh, so what CI checks is exactly what ships.
set -euo pipefail

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
  echo "usage: $0 OUT_DIR [REV]" >&2
  exit 2
fi
out="$1"
rev="${2:-HEAD}"
tree="$rev:skills"

if [ "$(git cat-file -t "$tree" 2>/dev/null)" != tree ]; then
  echo "error: $tree is not a tree (bad REV, or no skills/ directory)" >&2
  exit 1
fi

# git trees cannot hold absolute or ".." paths, so the cases left to refuse are
# symlinks and submodules (anything but a regular file), and files directly
# under skills/ rather than inside a skill directory. Each skills/ entry is a
# file or a directory, so a tree with no stray files has at least one skill.
bad=0
while IFS=$'\t' read -r -d '' meta path; do
  mode="${meta%% *}"
  case "$mode" in
    100644 | 100755) ;;
    *) echo "error: refusing skills/$path: mode $mode is not a regular file" >&2; bad=1 ;;
  esac
  case "$path" in
    */*) ;;
    *) echo "error: refusing skills/$path: file outside the skill directories" >&2; bad=1 ;;
  esac
done < <(git ls-tree -r -z "$tree")
[ "$bad" = 0 ] || exit 1

mkdir -p "$out"
git -c tar.umask=022 archive \
  --format=tar.gz \
  --mtime="@$(git log -1 --format=%ct "$rev")" \
  -o "$out/skills.tar.gz" \
  "$tree"
# shasum ships with macOS and Ubuntu; sha256sum is not on macOS by default.
(cd "$out" && shasum -a 256 skills.tar.gz > skills.tar.gz.sha256)

echo "archive: $out/skills.tar.gz"
echo "sha256:  $(cut -d' ' -f1 "$out/skills.tar.gz.sha256")"
echo "skills:  $(git ls-tree -d --name-only "$tree" | wc -l | tr -d ' ')"
