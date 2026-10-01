#!/usr/bin/env python3
"""Generate the Traffic Policy action catalog from ngrok's published docs.

Two steps, so the check that runs on every PR needs no network:

    python3 scripts/gen_action_catalog.py fetch            # docs -> snapshot JSON
    python3 scripts/gen_action_catalog.py render           # snapshot -> Markdown
    python3 scripts/gen_action_catalog.py render --check   # exit 1 if Markdown is stale

Source of truth: https://ngrok.com/docs/gateway/traffic-policy/actions
Snapshot:        scripts/data/traffic-policy-actions.json (committed)
Output:          skills/ngrok-engine/references/action-catalog.md (index),
                 skills/ngrok-engine/references/actions/*.md (one per action),
                 and the action-names block in skills/ngrok-engine/SKILL.md

`fetch` runs weekly in CI and opens a PR when the docs change. `render --check`
runs on every PR and fails if a generated file was edited by hand.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

DOCS = "https://ngrok.com/docs/gateway/traffic-policy/actions"

REPO = Path(__file__).resolve().parent.parent
SNAPSHOT = REPO / "scripts" / "data" / "traffic-policy-actions.json"
REFS = REPO / "skills" / "ngrok-engine" / "references"
OUT = REFS / "action-catalog.md"
ACTION_DIR = REFS / "actions"
SKILL = REPO / "skills" / "ngrok-engine" / "SKILL.md"

# The always-loaded tier: a bare action vocabulary kept in SKILL.md between
# these markers, so an agent knows what exists before fetching anything.
BEGIN = "<!-- BEGIN generated: action-names -->"
END = "<!-- END generated: action-names -->"

EXAMPLE_MAX_LINES = 40


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "ngrok-agent-skills-gen"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


# --------------------------------------------------------------------------
# text cleanup
# --------------------------------------------------------------------------

def clean(text: str) -> str:
    """Turn a chunk of doc markup into one readable sentence-ish line."""
    # The <ConfigEnum> wrapper only; options are parsed out before this runs.
    text = re.sub(r"<ConfigEnum(?:\s[^>]*)?>|</ConfigEnum>", " ", text)
    text = re.sub(r"</?p>", " ", text)
    text = re.sub(r"<code>(.*?)</code>", r"`\1`", text, flags=re.S)
    text = re.sub(r"<br\s*/?>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    # markdown links -> their text, dropping doc-relative targets
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = text.replace("|", "\\|")
    text = text.replace("\\[", "[").replace("\\]", "]")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def splice_path(ancestors: list[str], child: str) -> str:
    """Resolve a nested doc field name against the ancestors above it.

    ngrok's action pages name nested fields three different ways, and guessing
    wrong produces a path that cannot be translated back to the schema:

    * absolute - "actions.ngrok.oauth.identity.id" under ".../identity"
    * relative to the immediate parent - "tokens[i].header" under "...tokens"
    * relative to a HIGHER ancestor - "keys[*].identification[*].token_claims"
      nested under "jws.keys[*].identification", where the shared segment is
      `keys`, two levels up.

    So: take absolute names as-is, otherwise find the nearest ancestor whose
    leaf matches the child's first segment and splice there.
    """
    if ancestors:
        parent = ancestors[-1]
        if child == parent or child.startswith(parent + "."):
            return child

    first = child.split(".")[0].split("[")[0]
    for anc in reversed(ancestors):
        leaf = anc.split(".")[-1].split("[")[0]
        if leaf and leaf == first:
            return anc.rsplit(leaf, 1)[0] + child

    return f"{ancestors[-1]}.{child}" if ancestors else child


def first_sentence(text: str, limit: int = 240) -> str:
    text = clean(text)
    if len(text) <= limit:
        return text
    cut = text[:limit]
    dot = cut.rfind(". ")
    if dot > 60:
        return cut[: dot + 1]
    space = cut.rfind(" ")
    if space > 60:
        cut = cut[:space]
    return cut.rstrip() + "... (see Field details)"


# --------------------------------------------------------------------------
# index: the ActionHub array
# --------------------------------------------------------------------------

@dataclass
class Action:
    type: str
    name: str
    description: str
    phases: list[str]
    categories: list[str]
    terminating: bool
    config: list["Field"] = field(default_factory=list)
    results: list[tuple[str, str]] = field(default_factory=list)
    example: str = ""
    doc_phases: list[str] = field(default_factory=list)
    policy_type: str = ""  # what you actually write in a policy; may differ from the slug


def parse_index(md: str) -> list[Action]:
    start = md.find("const actions = [")
    if start == -1:
        sys.exit("could not locate the ActionHub action list; docs layout changed")
    end = md.find("];", start)
    blob = md[start:end]

    actions: list[Action] = []
    for chunk in re.split(r"\}\s*,\s*\{", blob):
        t = re.search(r'type:\s*"([^"]+)"', chunk)
        if not t:
            continue
        name = re.search(r'name:\s*"([^"]+)"', chunk)
        desc = re.search(r'description:\s*"((?:[^"\\]|\\.)*)"', chunk)
        phases = re.findall(r'"(on_[a-z_]+)"', chunk)
        cats = re.search(r"categories:\s*\[([^\]]*)\]", chunk)
        actions.append(
            Action(
                type=t.group(1),
                name=name.group(1) if name else t.group(1),
                description=clean(desc.group(1).replace('\\"', '"')) if desc else "",
                phases=phases,
                categories=re.findall(r'"([^"]+)"', cats.group(1)) if cats else [],
                terminating=bool(re.search(r"terminating:\s*true", chunk)),
            )
        )
    if not actions:
        sys.exit("parsed zero actions; docs layout changed")
    return sorted(actions, key=lambda a: a.type)


# --------------------------------------------------------------------------
# per-action page
# --------------------------------------------------------------------------

@dataclass
class Field:
    name: str
    type: str
    required: bool
    cel: bool
    depth: int
    desc: str
    values: list[str]
    raw: str = ""


FIELD_OPEN = re.compile(
    r'<ConfigField\s+title="([^"]*)"(?:\s+type="([^"]*)")?'
    r"(?:\s+required=\{(true|false)\})?(?:\s+cel=\{(true|false)\})?[^>]*>"
)

# Attributes are optional and may appear in any order; `value` wins over the
# tag body when present.
ENUM_OPTION = re.compile(
    r"<ConfigEnumOption(?:\s[^>]*?\bvalue=\"([^\"]*)\")?[^>]*>(.*?)</ConfigEnumOption>",
    re.S,
)


def section(md: str, heading: str, level: str | None = None) -> str:
    """Return the body under a heading, up to the next heading of the same or
    higher level.

    Heading depth is not consistent across ngrok's action pages - some use
    `### Configuration fields`, others `####`. Match whatever depth is used
    and derive the stop condition from it rather than assuming.
    """
    pat = re.compile(rf"^(#{{2,6}})\s+{re.escape(heading)}\s*$", re.M)
    m = pat.search(md)
    if not m:
        return ""
    depth = len(m.group(1))
    rest = md[m.end():]
    nxt = re.search(r"^#{1,%d}\s+" % depth, rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def parse_fields(body: str) -> list[Field]:
    """Stack-based scan so nested ConfigFields keep their parent relationship."""
    fields: list[Field] = []
    stack: list[Field] = []
    pos = 0
    pending: list[str] = []

    def flush(target: Field | None) -> None:
        text = "".join(pending)
        pending.clear()
        if target is None or not text.strip():
            return
        for m in ENUM_OPTION.finditer(text):
            # Some pages show a display label and carry the policy value in an
            # attribute: <ConfigEnumOption value="require-any">Require any<...>.
            v = m.group(1) if m.group(1) is not None else clean(m.group(2))
            if v and v not in target.values:
                target.values.append(v)
        text = ENUM_OPTION.sub(" ", text)
        target.raw += text
        extra = clean(text)
        if extra:
            target.desc = (target.desc + " " + extra).strip() if target.desc else extra

    while pos < len(body):
        m = FIELD_OPEN.search(body, pos)
        c = body.find("</ConfigField>", pos)
        if m and (c == -1 or m.start() < c):
            pending.append(body[pos:m.start()])
            flush(stack[-1] if stack else None)
            f = Field(
                name=m.group(1),
                type=m.group(2) or "",
                required=m.group(3) == "true",
                cel=m.group(4) == "true",
                depth=len(stack),
                desc="",
                values=[],
                raw="",
            )
            fields.append(f)
            stack.append(f)
            pos = m.end()
        elif c != -1:
            pending.append(body[pos:c])
            flush(stack[-1] if stack else None)
            if stack:
                stack.pop()
            pos = c + len("</ConfigField>")
        else:
            break
    return fields


def parse_example(md: str) -> str:
    ex = md.find("## Examples")
    blob = md[ex:] if ex != -1 else md
    m = re.search(r"```ya?ml[^\n]*\n(.*?)```", blob, re.S)
    if not m:
        return ""
    lines = [ln.rstrip() for ln in m.group(1).strip("\n").split("\n")]
    if len(lines) > EXAMPLE_MAX_LINES:
        lines = lines[:EXAMPLE_MAX_LINES] + ["# ...truncated, see the action's docs page"]
    return "\n".join(lines)


def enrich(a: Action) -> None:
    md = fetch(f"{DOCS}/{a.type}.md")
    a.doc_phases = re.findall(r"`(on_[a-z_]+)`", section(md, "Supported phases"))
    # The index's identifier is the docs page slug. The page's own "Type"
    # section is what a policy must use, and the two differ (e.g. slug `oidc`
    # vs policy type `openid-connect`). The page wins.
    m = re.search(r"`([a-z0-9-]+)`", section(md, "Type"))
    a.policy_type = m.group(1) if m else a.type
    a.config = parse_fields(section(md, "Configuration fields"))
    # Rewrite nested field names as full dotted paths. More informative than
    # indentation and far cheaper to tokenize than &nbsp; runs.
    cpath: list[str] = []
    for f in a.config:
        del cpath[f.depth:]
        if f.depth and cpath:
            f.name = splice_path(cpath, f.name)
        cpath.append(f.name)
    path: list[str] = []
    for f in parse_fields(section(md, "Action result variables", level="##")):
        del path[f.depth:]
        name = f.name
        if f.depth and path:
            name = splice_path(path, name)
        path.append(name)
        a.results.append((name, f.type))
    a.example = parse_example(md)


# --------------------------------------------------------------------------
# render
# --------------------------------------------------------------------------

def render_index(actions: list[Action]) -> str:
    """The index. Small on purpose: an agent reads this, then one action file."""
    out: list[str] = []
    w = out.append

    w("# Traffic Policy action catalog")
    w("")
    w("**Generated from ngrok's published Traffic Policy documentation.**")
    w("Do not hand-edit: changes are overwritten when this is regenerated.")
    w(f"Source of truth: <{DOCS}>")
    w("")
    w(
        f"All {len(actions)} Traffic Policy actions. This file is the index only. "
        "Each action's config fields, result variables, and example live in "
        "`actions/<action>.md` - **read only the one(s) you need**, not the whole "
        "directory."
    )
    w("")
    w("## How to read this")
    w("")
    w(
        "- **Phases** - the traffic phases an action may appear in. Putting an action "
        "in the wrong phase is a config error, not a no-op."
    )
    w(
        "- **Ends chain** - a terminating action stops the rule chain when it fires. "
        "Every Cloud Endpoint policy must end with one; agent endpoints need not."
    )
    w(
        "- Field names in the per-action files are full dotted paths, so they can be "
        "read straight into a policy body."
    )
    w("")

    w("## Actions")
    w("")
    w("| Action | Phases | Ends chain | What it does |")
    w("| --- | --- | --- | --- |")
    for a in actions:
        phases = " ".join(f"`{p}`" for p in (a.doc_phases or a.phases)) or "-"
        w(
            f"| [`{a.policy_type or a.type}`](actions/{a.type}.md) | {phases} | "
            f"{'yes' if a.terminating else 'no'} | {a.description} |"
        )
    w("")

    by_cat: dict[str, list[str]] = {}
    for a in actions:
        for c in a.categories:
            by_cat.setdefault(c, []).append(a.policy_type or a.type)
    if by_cat:
        w("## By category")
        w("")
        for c in sorted(by_cat):
            names = ", ".join(f"`{t}`" for t in sorted(set(by_cat[c])))
            w(f"- **{c.replace('-', ' ')}** - {names}")
        w("")

    return "\n".join(out)


def render_names_block(actions: list[Action]) -> str:
    by_cat: dict[str, list[str]] = {}
    for a in actions:
        for c in a.categories or ["other"]:
            by_cat.setdefault(c, []).append(a.policy_type or a.type)
    lines = [BEGIN]
    for c in sorted(by_cat):
        names = ", ".join(f"`{t}`" for t in sorted(set(by_cat[c])))
        lines.append(f"- **{c.replace('-', ' ')}**: {names}")
    lines.append(END)
    return "\n".join(lines)


def inject_names(skill_text: str, block: str) -> str:
    i, j = skill_text.find(BEGIN), skill_text.find(END)
    if i == -1 or j == -1:
        sys.exit(f"markers {BEGIN} / {END} not found in {SKILL}")
    return skill_text[:i] + block + skill_text[j + len(END):]


def render_action(a: Action) -> str:
    out: list[str] = []
    w = out.append

    w(f"# `{a.policy_type or a.type}`")
    w("")
    w("**Generated from ngrok's published documentation - do not hand-edit.**")
    if a.policy_type and a.policy_type != a.type:
        w("")
        w(
            f"Write `type: {a.policy_type}` in a policy. This page is filed under "
            f"the docs slug `{a.type}`, which is not a valid action type."
        )
    w("")
    if a.description:
        w(a.description)
        w("")
    phases = ", ".join(f"`{p}`" for p in (a.doc_phases or a.phases)) or "-"
    w(f"- **Phases:** {phases}")
    w(f"- **Ends chain:** {'yes' if a.terminating else 'no'}")
    if a.categories:
        w(f"- **Categories:** {', '.join(a.categories)}")
    w("")

    if a.config:
        w("## Configuration")
        w("")
        w("| Field | Type | Required | Notes |")
        w("| --- | --- | --- | --- |")
        for f in a.config:
            # Code blocks belong in Field details, not squashed into a table cell.
            notes = first_sentence(
                clean(re.sub(r"```.*?```", " ", f.raw, flags=re.S)) or f.desc
            )
            if f.values:
                vals = ", ".join(v if "`" in v else f"`{v}`" for v in f.values[:8])
                notes = (notes + f" Values: {vals}").strip()
            if f.cel:
                notes = (notes + " Accepts CEL interpolation.").strip()
            w(
                f"| `{f.name}` | {f.type or '-'} | "
                f"{'yes' if f.required else 'no'} | {notes or '-'} |"
            )
        w("")

        # A table cell cannot carry a field whose contract includes a code
        # block or runs long - abbreviating those leaves the action
        # unusable. Print them in full underneath.
        detailed = [
            f for f in a.config
            if "```" in f.raw or len(clean(f.raw)) > 240
        ]
        if detailed:
            w("### Field details")
            w("")
            for f in detailed:
                w(f"**`{f.name}`**")
                w("")
                prose = clean(re.sub(r"```.*?```", " ", f.raw, flags=re.S))
                if prose:
                    w(prose)
                    w("")
                for block in re.findall(r"```[a-z]*[^\n]*\n(.*?)```", f.raw, re.S):
                    # Blocks are indented inside <ConfigField> by varying
                    # amounts; a fixed strip mangles nested YAML.
                    body = textwrap.dedent(block.strip("\n").rstrip())
                    w("```yaml")
                    w(body)
                    w("```")
                    w("")
    else:
        w("## Configuration")
        w("")
        w("None.")
        w("")

    if a.results:
        w("## Result variables")
        w("")
        w("Readable from `expressions` in later rules once this action has run.")
        w("")
        for name, typ in a.results:
            w(f"- `{name}` ({typ or 'unknown'})")
        w("")

    if a.example:
        w("## Example")
        w("")
        w("```yaml")
        w(a.example)
        w("```")
        w("")

    w(f"Docs: <{DOCS}/{a.type}>")
    w("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# snapshot
# --------------------------------------------------------------------------

def save_snapshot(actions: list[Action]) -> None:
    SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(a) for a in actions]
    SNAPSHOT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def load_snapshot() -> list[Action]:
    if not SNAPSHOT.exists():
        sys.exit(f"{SNAPSHOT.relative_to(REPO)} not found; run `fetch` first")
    actions = []
    for d in json.loads(SNAPSHOT.read_text()):
        d["config"] = [Field(**f) for f in d["config"]]
        d["results"] = [tuple(r) for r in d["results"]]
        actions.append(Action(**d))
    return actions


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def cmd_fetch() -> int:
    actions = parse_index(fetch(DOCS + ".md"))
    print(f"found {len(actions)} actions", file=sys.stderr)
    for a in actions:
        print(f"  {a.type}", file=sys.stderr)
        enrich(a)
    save_snapshot(actions)
    print(f"wrote {SNAPSHOT.relative_to(REPO)}; now run `render`", file=sys.stderr)
    return 0


def cmd_render(check: bool) -> int:
    actions = load_snapshot()
    index = render_index(actions)
    pages = {a.type: render_action(a) for a in actions}
    expected = {f"{t}.md" for t in pages}
    skill_now = SKILL.read_text()
    skill_new = inject_names(skill_now, render_names_block(actions))

    if check:
        stale: list[str] = []
        if not OUT.exists() or OUT.read_text() != index:
            stale.append(str(OUT.relative_to(REPO)))
        if skill_now != skill_new:
            stale.append(f"{SKILL.relative_to(REPO)} (generated action-names block)")
        for t, body in pages.items():
            f = ACTION_DIR / f"{t}.md"
            if not f.exists() or f.read_text() != body:
                stale.append(str(f.relative_to(REPO)))
        if ACTION_DIR.exists():
            for f in ACTION_DIR.glob("*.md"):
                if f.name not in expected:
                    stale.append(f"{f.relative_to(REPO)} (not in the snapshot)")
        if stale:
            print(
                "Generated files are stale. Do not edit them by hand; run:\n"
                "  python3 scripts/gen_action_catalog.py render",
                file=sys.stderr,
            )
            for f in stale:
                print(f"::error file={f.split(' ')[0]}::stale generated file")
            return 1
        print(f"action catalog is current ({len(pages) + 2} files)", file=sys.stderr)
        return 0

    ACTION_DIR.mkdir(parents=True, exist_ok=True)
    OUT.write_text(index)
    if skill_now != skill_new:
        SKILL.write_text(skill_new)
    for t, body in pages.items():
        (ACTION_DIR / f"{t}.md").write_text(body)
    removed = 0
    for f in ACTION_DIR.glob("*.md"):
        if f.name not in expected:
            f.unlink()
            removed += 1

    idx_lines = len(index.splitlines())
    biggest = max(len(b.splitlines()) for b in pages.values())
    print(
        f"wrote {OUT.relative_to(REPO)} ({idx_lines} lines) and "
        f"{len(pages)} action files in {ACTION_DIR.relative_to(REPO)} "
        f"(largest {biggest} lines)"
        + (f"; pruned {removed} stale" if removed else ""),
        file=sys.stderr,
    )
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch", help="fetch the docs and write the snapshot JSON")
    r = sub.add_parser("render", help="write the Markdown from the snapshot")
    r.add_argument("--check", action="store_true", help="exit 1 if the Markdown is stale")
    args = ap.parse_args()
    return cmd_fetch() if args.cmd == "fetch" else cmd_render(args.check)


if __name__ == "__main__":
    raise SystemExit(main())
