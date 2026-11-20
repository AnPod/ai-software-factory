#!/usr/bin/env python3
"""Report the freshness and health of an AI Werk brain folder.

Read-only: it opens the Markdown pages and health.html under the given folder,
makes no network calls and writes nothing. It does not follow symbolic links and
ignores index links that point outside the folder. Standard library only.

Usage:
  python3 brain_status.py .aiwerk/brain [--json] [--strict] [--fail-on-stale]
                                        [--template] [--now 2026-11-19T00:00:00Z]

Exit codes:
  0  no problems (stale pages alone do not fail unless --fail-on-stale)
  1  problems found and --strict given, or stale pages and --fail-on-stale given
  2  usage error (folder missing)
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

REQUIRED = ("title", "kind", "gathered_at", "gathered_by", "sources", "ttl_days", "confidence")
CONFIDENCE = ("low", "medium", "high")
EXEMPT = ("SCHEMA.md", "log.md")
PLACEHOLDER = "{{NOW}}"

# Shapes of leaked credentials. Only the file, line and shape name are reported, never the match.
LEAK_SHAPES = [
    ("aws-access-key", re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("gitlab-token", re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("slack-webhook", re.compile(r"hooks\.slack\.com/services/T[A-Za-z0-9]+/B[A-Za-z0-9]+/[A-Za-z0-9]+")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9]{32,}\b")),
    ("stripe-key", re.compile(r"\b[rs]k_live_[A-Za-z0-9]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("npm-token", re.compile(r"\bnpm_[A-Za-z0-9]{36}\b")),
    ("huggingface-token", re.compile(r"\bhf_[A-Za-z0-9]{34,}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}")),
    ("url-with-password", re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s@]+@")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]
SAFE_LINK = re.compile(r"^[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*\.md$")
CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f]")


def leak_shapes(text):
    """Return the names of credential shapes found in text."""
    return [name for name, rx in LEAK_SHAPES if rx.search(text)]


def clean(value):
    """Make a value from a page safe to print: no control characters, no credential-shaped text."""
    value = CONTROL.sub("?", str(value))
    return "(hidden: looks like a credential)" if leak_shapes(value) else value


def parse_frontmatter(text):
    """Parse a small YAML subset: `key: value` and `key:` followed by `- item` lines.

    Returns (dict, error). dict is None when there is no frontmatter block.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "no frontmatter"
    data, key = {}, None
    for i, raw in enumerate(lines[1:], start=2):
        line = raw.rstrip()
        if line.strip() == "---":
            return data, None
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and key is not None:
            if not isinstance(data.get(key), list):
                data[key] = []
            data[key].append(strip_value(line.lstrip()[2:]))
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if not m:
            return data, "cannot parse frontmatter line %d" % i
        key, value = m.group(1), strip_value(m.group(2))
        data[key] = value if value != "" else []
    return data, "frontmatter is not closed with ---"


def strip_value(value):
    value = re.sub(r"\s+#.*$", "", value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
        value = value[1:-1]
    return value


def parse_time(value):
    value = value.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    t = dt.datetime.fromisoformat(value)
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return t


def index_targets(index_text):
    """Return (links inside the brain, number of links that are absolute or leave the brain)."""
    inside, outside = set(), 0
    for target in re.findall(r"\]\(([^)#\s]+\.md)\)", index_text):
        if target.startswith("./"):
            target = target[2:]
        if SAFE_LINK.match(target) and ".." not in target.split("/"):
            inside.add(target)
        else:
            outside += 1
    return inside, outside


def scan_for_leaks(rel, text, problems):
    for lineno, line in enumerate(text.splitlines(), start=1):
        for name in leak_shapes(line):
            problems.append({"page": rel, "problem": "possible secret (%s) on line %d" % (name, lineno)})


def scan(brain, now, template=False):
    pages, problems = [], []
    index_path = os.path.join(brain, "index.md")
    index_text = ""
    if os.path.isfile(index_path) and not os.path.islink(index_path):
        with open(index_path, encoding="utf-8") as fh:
            index_text = fh.read()
    else:
        problems.append({"page": "index.md", "problem": "index.md is missing"})
    linked, outside = index_targets(index_text)
    if outside:
        problems.append({"page": "index.md", "problem": "%d link(s) point outside the brain folder" % outside})

    for root, dirs, files in os.walk(brain):
        for d in [d for d in dirs if os.path.islink(os.path.join(root, d))]:
            rel = os.path.relpath(os.path.join(root, d), brain).replace(os.sep, "/")
            problems.append({"page": clean(rel), "problem": "is a symbolic link, not followed"})
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not os.path.islink(os.path.join(root, d)))
        for name in sorted(files):
            if not (name.endswith(".md") or name == "health.html"):
                continue
            path = os.path.join(root, name)
            rel = clean(os.path.relpath(path, brain).replace(os.sep, "/"))
            if os.path.islink(path) or not os.path.isfile(path):
                problems.append({"page": rel, "problem": "is a symbolic link or special file, not read"})
                continue
            with open(path, encoding="utf-8", errors="replace") as fh:
                text = fh.read()

            scan_for_leaks(rel, text, problems)
            if not name.endswith(".md") or rel in EXEMPT:
                continue
            if rel != "index.md" and rel not in linked:
                problems.append({"page": rel, "problem": "not listed in index.md"})

            fm, err = parse_frontmatter(text)
            if fm is None or err:
                problems.append({"page": rel, "problem": err})
                continue
            missing = [k for k in REQUIRED if k not in fm or fm[k] in ("", [])]
            if missing:
                problems.append({"page": rel, "problem": "missing fields: " + ", ".join(missing)})
                continue
            if fm["confidence"] not in CONFIDENCE:
                problems.append({"page": rel, "problem": "confidence must be low, medium or high"})
            if not isinstance(fm["sources"], list):
                problems.append({"page": rel, "problem": "sources must be a list"})
            try:
                ttl = int(fm["ttl_days"])
                if ttl <= 0:
                    raise ValueError
            except ValueError:
                problems.append({"page": rel, "problem": "ttl_days must be a positive integer"})
                continue

            if fm["gathered_at"] == PLACEHOLDER and template:
                pages.append(page_row(rel, fm, 0.0, ttl))
                continue
            try:
                gathered = parse_time(fm["gathered_at"])
            except ValueError:
                problems.append({"page": rel, "problem": "gathered_at is not an ISO 8601 time"})
                continue
            age = (now - gathered).total_seconds() / 86400.0
            if age < -1:
                problems.append({"page": rel, "problem": "gathered_at is in the future"})
            pages.append(page_row(rel, fm, max(age, 0.0), ttl))

    for target in sorted(linked):
        path = os.path.join(brain, target)
        if not os.path.isfile(path) or os.path.islink(path):
            problems.append({"page": "index.md", "problem": "links to missing page " + clean(target)})

    order = {"stale": 0, "soon": 1, "fresh": 2}
    pages.sort(key=lambda p: (order[p["status"]], -p["age_days"]))
    return pages, problems


def page_row(rel, fm, age, ttl):
    ratio = age / ttl
    status = "stale" if ratio > 1 else "soon" if ratio > 0.75 else "fresh"
    return {
        "page": rel,
        "kind": clean(fm["kind"]),
        "gathered_by": clean(fm["gathered_by"]),
        "age_days": round(age, 1),
        "ttl_days": ttl,
        "status": status,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="Report freshness and health of an AI Werk brain.")
    ap.add_argument("brain", nargs="?", default=".aiwerk/brain")
    ap.add_argument("--json", action="store_true", help="print JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 when problems are found")
    ap.add_argument("--fail-on-stale", action="store_true", help="exit 1 when any page is stale")
    ap.add_argument("--template", action="store_true", help="accept {{NOW}} placeholders (for the template)")
    ap.add_argument("--now", help="override the current time (ISO 8601), for tests")
    args = ap.parse_args(argv)

    if not os.path.isdir(args.brain):
        print("brain folder not found: %s" % args.brain, file=sys.stderr)
        return 2
    now = parse_time(args.now) if args.now else dt.datetime.now(dt.timezone.utc)
    pages, problems = scan(args.brain, now, template=args.template)

    if args.json:
        print(json.dumps({"brain": args.brain, "now": now.isoformat(), "pages": pages, "problems": problems}, indent=2))
    else:
        width = max([len(p["page"]) for p in pages] + [4])
        print("%-*s  %8s  %5s  %-6s  %s" % (width, "page", "age (d)", "ttl", "status", "written by"))
        for p in pages:
            print("%-*s  %8.1f  %5d  %-6s  %s" % (width, p["page"], p["age_days"], p["ttl_days"], p["status"], p["gathered_by"]))
        stale = sum(1 for p in pages if p["status"] == "stale")
        print("\n%d pages, %d stale, %d problems" % (len(pages), stale, len(problems)))
        for pr in problems:
            print("  problem: %s: %s" % (pr["page"], pr["problem"]))

    if args.strict and problems:
        return 1
    if args.fail_on_stale and any(p["status"] == "stale" for p in pages):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
