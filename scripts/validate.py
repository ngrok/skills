#!/usr/bin/env python3
"""Structural validation for the ngrok agent skills.

    python3 scripts/validate.py          # offline checks (every PR)
    python3 scripts/validate.py --docs   # also check against ngrok.com/docs
    python3 scripts/validate.py --fix    # fix attribution tags, then check

Offline checks:
  - frontmatter: `name` matches the folder, required fields are present
  - references: every `references/...` or `<skill>/...` path resolves
  - manifests: plugin JSON parses, names and repo URLs agree
  - examples: YAML blocks parse, and use no deprecated agent config syntax
  - attribution: every ngrok command in a shell block carries an
    NGROK_CLIENT_SOURCE tag that names its own skill, except in blocks that
    go into the user's files

Docs checks (--docs):
  - every ngrok.com/docs link returns 200
  - every Traffic Policy action `type` in an example exists in the docs
  - every ERR_NGROK_* code mentioned has a docs page

Exits 1 on any error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS = ROOT / "skills"
REPO_URL = "https://github.com/ngrok/skills"
DOCS = "https://ngrok.com/docs"
ACTIONS_JSON = f"{DOCS}/gateway/traffic-policy/actions.json"

errors: list[str] = []


def fail(path: Path, msg: str, line: int | None = None) -> None:
    rel = path.relative_to(ROOT)
    loc = f"{rel}:{line}" if line else str(rel)
    errors.append(f"{loc}: {msg}")
    # GitHub annotation, so the error shows inline on the PR diff.
    print(f"::error file={rel}{f',line={line}' if line else ''}::{msg}")


def line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def skill_dirs() -> list[Path]:
    return sorted(p for p in SKILLS.iterdir() if p.is_dir())


def markdown_files() -> list[Path]:
    return sorted(SKILLS.rglob("*.md"))


# --------------------------------------------------------------------------
# offline checks
# --------------------------------------------------------------------------

def frontmatter(path: Path) -> dict | None:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        fail(path, "missing YAML frontmatter")
        return None
    try:
        return yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as e:
        fail(path, f"frontmatter is not valid YAML: {e}")
        return None


def check_frontmatter() -> None:
    for d in skill_dirs():
        skill = d / "SKILL.md"
        if not skill.exists():
            fail(d, "folder has no SKILL.md")
            continue
        fm = frontmatter(skill)
        if fm is None:
            continue
        if fm.get("name") != d.name:
            fail(skill, f"name {fm.get('name')!r} does not match folder {d.name!r}", 2)
        if fm.get("license") != "MIT":
            fail(skill, "license must be MIT")
        if (fm.get("metadata") or {}).get("author") != "ngrok":
            fail(skill, "metadata.author must be ngrok")


# `references/x.md` is relative to the current skill; `other-skill/...` is
# relative to skills/. Links inside a references/ file are relative to it.
PATH_REF = re.compile(r"`((?:[a-z0-9-]+/)?(?:references/[\w./-]*|SKILL\.md))`")
MD_LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)(?:#[^)]*)?\)")


def check_references() -> None:
    names = {d.name for d in skill_dirs()}
    for f in markdown_files():
        text = f.read_text()
        skill = f.relative_to(SKILLS).parts[0]
        for m in PATH_REF.finditer(text):
            ref = m.group(1)
            head = ref.split("/", 1)[0]
            target = SKILLS / ref if head in names else SKILLS / skill / ref
            if head not in names and head not in ("references", "SKILL.md"):
                fail(f, f"`{ref}` points at a skill that does not exist", line_of(text, m.start()))
            elif not target.exists():
                fail(f, f"`{ref}` does not exist", line_of(text, m.start()))
        for m in MD_LINK.finditer(text):
            if not (f.parent / m.group(1)).exists():
                fail(f, f"link target {m.group(1)} does not exist", line_of(text, m.start()))


def check_manifests() -> None:
    manifests = sorted(ROOT.glob(".*-plugin/*.json"))
    if not manifests:
        fail(ROOT, "no plugin manifests found")
    for f in manifests:
        try:
            data = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            fail(f, f"invalid JSON: {e}")
            continue
        for key in ("repository", "homepage"):
            if key in data and data[key] != REPO_URL:
                fail(f, f"{key} is {data[key]!r}, expected {REPO_URL!r}")
        if f.name == "marketplace.json":
            plugin = json.loads((f.parent / "plugin.json").read_text())
            listed = [p.get("name") for p in data.get("plugins", [])]
            if plugin.get("name") not in listed:
                fail(f, f"does not list plugin {plugin.get('name')!r} from plugin.json")


YAML_BLOCK = re.compile(r"^```ya?ml\n(.*?)^```", re.M | re.S)

# Deprecated agent config (v2). Skills must teach v3 `endpoints:`.
DEPRECATED = [
    (re.compile(r"^\s*tunnels:", re.M), "`tunnels:` is v2 agent config; use `endpoints:`"),
    (re.compile(r"^version:\s*[\"']?2[\"']?\s*$", re.M), "agent config version 2 is deprecated; use 3"),
]


def yaml_blocks():
    """Yield (file, line, source, parsed) for every YAML example."""
    files = markdown_files() + sorted(SKILLS.rglob("*.yaml")) + sorted(SKILLS.rglob("*.yml"))
    for f in files:
        text = f.read_text()
        if f.suffix == ".md":
            blocks = [(m.group(1), line_of(text, m.start()) + 1) for m in YAML_BLOCK.finditer(text)]
        else:
            blocks = [(text, 1)]
        for src, line in blocks:
            try:
                docs = list(yaml.safe_load_all(src))
            except yaml.YAMLError:
                # Placeholders like <PORT> or ${VAR} can make an example
                # unparseable on purpose; report it, but only in the parse check.
                docs = None
            yield f, line, src, docs


def check_examples() -> None:
    for f, line, src, docs in yaml_blocks():
        if docs is None:
            fail(f, "YAML example does not parse", line)
        for pattern, msg in DEPRECATED:
            if m := pattern.search(src):
                fail(f, msg, line + src.count("\n", 0, m.start()))


# Skill attribution tag on ngrok commands the agent runs (see README "Telemetry").
# Agents copy examples word for word, so the tag lives in every example.
#
#   - Every ngrok command in a shell block, in every skill file, carries the tag.
#   - A block that goes into the user's files (an entrypoint, a startup script)
#     never carries it. Such a block starts with a shebang.
#   - Put a runnable ngrok command in a shell block, not inline code, so this
#     check can see it.
TAG = re.compile(r"NGROK_CLIENT_SOURCE=([^\s`]+)")
TAG_ASSIGN = re.compile(r"NGROK_CLIENT_SOURCE=[^\s`]+\s+")
TAG_VALUE = re.compile(r"^[a-z0-9/._-]{1,64}$")
# Reference skills don't know which task skill loaded them; the agent fills it in.
TAG_PLACEHOLDER = "skills/{SKILL}"
REFERENCE_SKILLS = {"ngrok-surfaces", "ngrok-engine"}
BASH_BLOCK = re.compile(r"^[ \t]*```(?:bash|sh|shell)\n(.*?)^[ \t]*```", re.M | re.S)
# Group 1 is the text before `ngrok`, where --fix inserts the tag.
SERVER_COMMAND = re.compile(r"^(\s*(?:\S+=\S+\s+)*)ngrok (?:http|tcp|tls|start|api)\b")


def expected_tag(skill: str) -> str:
    return TAG_PLACEHOLDER if skill in REFERENCE_SKILLS else f"skills/{skill}"


def is_user_file(src: str) -> bool:
    return src.lstrip().startswith("#!")


def fix_attribution() -> None:
    """Add missing tags, correct wrong ones, and remove tags from user files."""
    for f in markdown_files():
        text = f.read_text()
        skill = f.relative_to(SKILLS).parts[0]
        want = expected_tag(skill)
        valid = {want, f"skills/{skill}"}
        new = TAG.sub(lambda m: m.group(0) if m.group(1) in valid else f"NGROK_CLIENT_SOURCE={want}", text)

        def fix_block(b: re.Match) -> str:
            user_file = is_user_file(b.group(1))
            lines = b.group(1).splitlines(keepends=True)
            for i, line in enumerate(lines):
                if user_file:
                    lines[i] = TAG_ASSIGN.sub("", line)
                elif (m := SERVER_COMMAND.match(line)) and not TAG.search(line):
                    lines[i] = f"{m.group(1)}NGROK_CLIENT_SOURCE={want} {line[m.end(1):]}"
            head = b.string[b.start() : b.start(1)]
            tail = b.string[b.end(1) : b.end()]
            return head + "".join(lines) + tail

        new = BASH_BLOCK.sub(fix_block, new)
        if new != text:
            f.write_text(new)
            print(f"fixed {f.relative_to(ROOT)}")


def check_attribution() -> None:
    for f in markdown_files():
        text = f.read_text()
        skill = f.relative_to(SKILLS).parts[0]
        want = expected_tag(skill)
        for m in TAG.finditer(text):
            value, line = m.group(1), line_of(text, m.start())
            if value == TAG_PLACEHOLDER:
                if skill not in REFERENCE_SKILLS:
                    fail(f, f"use skills/{skill}, not {TAG_PLACEHOLDER}, in a task skill (run with --fix)", line)
            elif value != f"skills/{skill}":
                fail(f, f"attribution tag {value!r} does not name this skill ({want}) (run with --fix)", line)
            elif not TAG_VALUE.match(value):
                fail(f, f"attribution tag {value!r} is not lowercase [a-z0-9/._-], 64 chars max", line)
        for b in BASH_BLOCK.finditer(text):
            user_file = is_user_file(b.group(1))
            start = line_of(text, b.start()) + 1
            for i, cmd in enumerate(b.group(1).splitlines()):
                if user_file and TAG.search(cmd):
                    fail(f, "remove NGROK_CLIENT_SOURCE: this block goes into the user's files (run with --fix)", start + i)
                elif not user_file and SERVER_COMMAND.match(cmd) and not TAG.search(cmd):
                    fail(
                        f,
                        f"ngrok command is missing NGROK_CLIENT_SOURCE={want} (run with --fix). "
                        "If this block goes into the user's files, start it with a shebang",
                        start + i,
                    )


# --------------------------------------------------------------------------
# docs checks
# --------------------------------------------------------------------------

def get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "ngrok-agent-skills-ci"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, ""
    except urllib.error.URLError as e:
        return 0, str(e.reason)


def check_urls(found: dict[str, tuple[Path, int]], label: str) -> None:
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = dict(zip(found, pool.map(lambda u: get(u)[0], found)))
    for url, status in sorted(results.items()):
        if status != 200:
            f, line = found[url]
            fail(f, f"{label} {url} returned {status or 'no response'}", line)


DOCS_URL = re.compile(r"https://ngrok\.com/docs[^\s)>`\"'\]]*")
ERR_CODE = re.compile(r"ERR_NGROK_(\d+)")


def check_docs_links() -> None:
    found: dict[str, tuple[Path, int]] = {}
    for f in markdown_files():
        text = f.read_text()
        for m in DOCS_URL.finditer(text):
            url = m.group(0).rstrip(".,")
            # A template such as err_ngrok_<code>.md is not a page to check.
            if "<" in url or "{" in url:
                continue
            found.setdefault(url, (f, line_of(text, m.start())))
    check_urls(found, "docs link")


def check_error_codes() -> None:
    found: dict[str, tuple[Path, int]] = {}
    for f in markdown_files():
        text = f.read_text()
        for m in ERR_CODE.finditer(text):
            url = f"{DOCS}/errors/err_ngrok_{m.group(1)}.md"
            found.setdefault(url, (f, line_of(text, m.start())))
    check_urls(found, "error code page")


def published_action_types() -> set[str]:
    status, body = get(ACTIONS_JSON)
    try:
        types = {a["type"] for a in json.loads(body)["actions"]}
    except (ValueError, KeyError, TypeError):
        types = set()
    if status != 200 or not types:
        sys.exit(f"could not read the action list from {ACTIONS_JSON} (HTTP {status})")
    return types


def action_types_in(node):
    """Yield every `type` under an `actions:` list, at any depth."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "actions" and isinstance(v, list):
                for a in v:
                    if isinstance(a, dict) and isinstance(a.get("type"), str):
                        yield a["type"]
            yield from action_types_in(v)
    elif isinstance(node, list):
        for v in node:
            yield from action_types_in(v)


def check_action_types() -> None:
    known = published_action_types()
    for f, line, _, docs in yaml_blocks():
        for t in {t for d in docs or [] for t in action_types_in(d)}:
            if t not in known:
                fail(f, f"action type {t!r} is not in the published Traffic Policy actions", line)


# --------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", action="store_true", help="check against ngrok.com/docs")
    ap.add_argument("--fix", action="store_true", help="fix attribution tags in place, then check")
    args = ap.parse_args()

    if args.fix:
        fix_attribution()

    checks = (
        [check_docs_links, check_error_codes, check_action_types]
        if args.docs
        else [check_frontmatter, check_references, check_manifests, check_examples, check_attribution]
    )
    for check in checks:
        before = len(errors)
        check()
        print(f"{'✓' if len(errors) == before else '✗'} {check.__name__.removeprefix('check_')}")

    if errors:
        print(f"\n{len(errors)} error(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
