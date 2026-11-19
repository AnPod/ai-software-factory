#!/usr/bin/env python3
"""Report the freshness and health of an AI Werk brain folder.

Read-only: it opens Markdown files under the given folder, makes no network
calls and writes nothing. Standard library only.

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

# Patterns that look like credentials. Only the file and line are reported, never the match.
SECRET_PATTERNS = [
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{40,}\b")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("openai-key", re.compile(r"\bsk-(proj-)?[A-Za-z0-9]{32,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
]


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
    return set(re.findall(r"\]\(([^)#\s]+\.md)\)", index_text))


def scan(brain, now, template=False):
    pages, problems = [], []
    index_path = os.path.join(brain, "index.md")
    index_text = ""
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as fh:
            index_text = fh.read()
    else:
        problems.append({"page": "index.md", "problem": "index.md is missing"})
    linked = index_targets(index_text)

    for root, dirs, files in os.walk(brain):
        dirs[:] = sorted(d for d in dirs if not d.startswith("."))
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            rel = os.path.relpath(path, brain).replace(os.sep, "/")
            with open(path, encoding="utf-8") as fh:
                text = fh.read()

            for lineno, line in enumerate(text.splitlines(), start=1):
                for label, pattern in SECRET_PATTERNS:
                    if pattern.search(line):
                        problems.append({"page": rel, "problem": "possible secret (%s) on line %d" % (label, lineno)})

            if rel in EXEMPT:
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
        if not os.path.isfile(os.path.join(brain, target)):
            problems.append({"page": "index.md", "problem": "links to missing page " + target})

    order = {"stale": 0, "soon": 1, "fresh": 2}
    pages.sort(key=lambda p: (order[p["status"]], -p["age_days"]))
    return pages, problems


def page_row(rel, fm, age, ttl):
    ratio = age / ttl
    status = "stale" if ratio > 1 else "soon" if ratio > 0.75 else "fresh"
    return {
        "page": rel,
        "kind": fm["kind"],
        "gathered_by": fm["gathered_by"],
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
