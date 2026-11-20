#!/usr/bin/env python3
"""Merge the runs of a SARIF file into one run with paths relative to the repository root.

GitHub code scanning rejects a file with several runs under one category. SkillSpector writes
one run per skill, with paths relative to that skill, so this script:
  - keeps one run with the first run's tool (rules from every run, de-duplicated by id)
  - rewrites every location to a path relative to the repository root (a relative path without
    a base id is read against the run's most specific base, the skill folder for SkillSpector)
  - keeps every result and invocation

Usage:
  python3 scripts/merge_sarif.py IN.sarif OUT.sarif [--root DIR]

--root is the repository root (default: current folder). Standard library only, no network.
"""

import argparse
import json
import os
import sys
from urllib.parse import unquote, urljoin, urlparse


def base_uris(run):
    """Resolve originalUriBaseIds (which may refer to each other) to absolute URIs."""
    raw = run.get("originalUriBaseIds") or {}
    resolved = {}

    def resolve(name, depth=0):
        if name in resolved:
            return resolved[name]
        entry = raw.get(name) or {}
        uri = entry.get("uri", "")
        parent = entry.get("uriBaseId")
        if parent and depth < 10:
            uri = urljoin(resolve(parent, depth + 1), uri)
        resolved[name] = uri
        return uri

    for name in raw:
        resolve(name)
    return resolved


def relative_uri(location, bases, root):
    """Return the location's URI relative to root, or None when it lies outside root."""
    uri = location.get("uri", "")
    base = location.get("uriBaseId")
    if base:
        uri = urljoin(bases.get(base, ""), uri)
    elif not urlparse(uri).scheme and bases:
        # A relative path without a base belongs to the run's most specific base (the skill folder).
        uri = urljoin(max(bases.values(), key=len), uri)
    parsed = urlparse(uri)
    if parsed.scheme == "file":
        path = unquote(parsed.path)
    elif parsed.scheme:
        return None
    else:
        path = os.path.join(root, unquote(uri))
    path = os.path.normpath(path)
    if os.path.commonpath([root, path]) != root:
        return None
    return os.path.relpath(path, root).replace(os.sep, "/")


def fix_locations(node, bases, root):
    """Rewrite every artifactLocation below node in place."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "artifactLocation" and isinstance(value, dict):
                rel = relative_uri(value, bases, root)
                value.pop("uriBaseId", None)
                value.pop("index", None)
                value["uri"] = rel if rel is not None else "unknown"
            else:
                fix_locations(value, bases, root)
    elif isinstance(node, list):
        for item in node:
            fix_locations(item, bases, root)


def merge(sarif, root):
    runs = sarif.get("runs") or []
    if not runs:
        return sarif
    root = os.path.normpath(os.path.abspath(root))
    driver = dict(runs[0].get("tool", {}).get("driver", {}))
    rules, results, invocations = {}, [], []
    for run in runs:
        bases = base_uris(run)
        for rule in run.get("tool", {}).get("driver", {}).get("rules", []) or []:
            rules.setdefault(rule.get("id"), rule)
        for result in run.get("results", []) or []:
            result.pop("ruleIndex", None)
            fix_locations(result, bases, root)
            results.append(result)
        for invocation in run.get("invocations", []) or []:
            fix_locations(invocation, bases, root)
            invocations.append(invocation)
    driver.pop("rules", None)
    if rules:
        driver["rules"] = [rules[k] for k in sorted(rules, key=str)]
    merged = {"tool": {"driver": driver}, "results": results}
    if invocations:
        merged["invocations"] = invocations
    if "columnKind" in runs[0]:
        merged["columnKind"] = runs[0]["columnKind"]
    out = {k: v for k, v in sarif.items() if k != "runs"}
    out["runs"] = [merged]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Merge SARIF runs into one run with repository-relative paths.")
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    with open(args.input, encoding="utf-8") as fh:
        sarif = json.load(fh)
    merged = merge(sarif, args.root)
    with open(args.output, "w", encoding="utf-8") as fh:
        json.dump(merged, fh, indent=2)
    run = merged["runs"][0] if merged.get("runs") else {"results": []}
    print("%d run(s) merged into 1 with %d result(s)" % (len(sarif.get("runs") or []), len(run["results"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
