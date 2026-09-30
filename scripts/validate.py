#!/usr/bin/env python3
"""Structural validation for the ngrok agent skills.

    python3 scripts/validate.py          # offline checks (every PR)
    python3 scripts/validate.py --docs   # also check against ngrok.com/docs

Offline checks:
  - frontmatter: `name` matches the folder, required fields are present
  - references: every `references/...` or `<skill>/...` path resolves
  - manifests: plugin JSON parses, names and repo URLs agree
  - examples: YAML blocks parse, and use no deprecated agent config syntax

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
            found.setdefault(m.group(0).rstrip(".,"), (f, line_of(text, m.start())))
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
    # The actions index page embeds the action list the docs render from, but
    # its `type` field is the page slug, which is not always the policy type
    # (the `oidc` page documents `openid-connect`). Read each page's "Type"
    # section, and fall back to the slug for pages that do not have one.
    status, body = get(f"{DOCS}/gateway/traffic-policy/actions.md")
    slugs = set(re.findall(r'type:\s*"([a-z0-9-]+)"', body))
    if status != 200 or not slugs:
        sys.exit(f"could not read the action list from the docs (HTTP {status})")

    def type_of(slug: str) -> str:
        _, page = get(f"{DOCS}/gateway/traffic-policy/actions/{slug}.md")
        m = re.search(r"^### Type\s+`([a-z0-9-]+)`", page, re.M)
        return m.group(1) if m else slug

    with ThreadPoolExecutor(max_workers=8) as pool:
        return set(pool.map(type_of, slugs))


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
    args = ap.parse_args()

    checks = (
        [check_docs_links, check_error_codes, check_action_types]
        if args.docs
        else [check_frontmatter, check_references, check_manifests, check_examples]
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
