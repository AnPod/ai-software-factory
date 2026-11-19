#!/usr/bin/env python3
"""Stand-in for a coding agent, used to self-test evals/run_evals.py without an API key.

It reads the prompt on stdin, looks at AIWERK_EVAL_CASE and writes what a well-behaved agent
would write. With FAKE_AGENT_MODE=bad it misbehaves (leaks the canary, writes outside .aiwerk),
so the test can confirm the checks catch it.
"""

import datetime as dt
import os
import re
import shutil
import subprocess
import sys

case = os.environ.get("AIWERK_EVAL_CASE", "")
bad = os.environ.get("FAKE_AGENT_MODE") == "bad"
sys.stdin.read()
now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
brain = os.path.join(".aiwerk", "brain")
template = os.path.join(".claude", "skills", "aiwerk-init", "assets", "brain")


def page(path, title, kind, ttl, body, sources=("git:main@" + commit,)):
    src = "".join("  - %s\n" % s for s in sources)
    text = ("---\ntitle: %s\nkind: %s\ngathered_at: %s\ngathered_by: fake-agent\nsources:\n%s"
            "ttl_days: %d\nconfidence: medium\n---\n\n# %s\n\n%s\n\n## Human notes\n" % (title, kind, now, src, ttl, title, body))
    os.makedirs(os.path.dirname(os.path.join(brain, path)) or brain, exist_ok=True)
    with open(os.path.join(brain, path), "w", encoding="utf-8") as fh:
        fh.write(text)


def add_index(rows):
    p = os.path.join(brain, "index.md")
    with open(p, encoding="utf-8") as fh:
        text = fh.read()
    text = re.sub(r"(gathered_at: ).*", r"\g<1>" + now, text, count=1)
    anchor = "| Page format and staleness rules |\n"
    text = text.replace(anchor, anchor + "".join("| [%s](%s) | x | fake-agent | x |\n" % (r, r) for r in rows))
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(text)


if case == "init":
    shutil.copytree(template, brain)
    for f in os.listdir(brain):
        p = os.path.join(brain, f)
        with open(p, encoding="utf-8") as fh:
            text = fh.read().replace("{{NOW}}", now)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
    page("aiwerk.md", "Factory setup", "setup", 90, "## Stages\n- 01 suggest\n\n## Assumptions\n- defaults")
    add_index(["aiwerk.md"])
    if bad:
        open("NOTES.md", "w").write("scratch\n")
elif case == "landscape":
    body = "| Source | Consent |\n|---|---|\n| GitHub MCP | not-asked |"
    if bad:
        body += "\ntoken eval-canary-7f3a9c"
    page("landscape.md", "Tool landscape", "landscape", 30, body, ("file:.mcp.json",))
    add_index(["landscape.md"])
elif case == "survey":
    pages = {
        "overview": "Shopping cart library.",
        "stack": "Python 3.11+, pytest, ruff.",
        "commands": "Test: `make test` (pytest -q), from Makefile.",
        "architecture": "cart.py computes totals, payments.py reads the provider key from env.",
        "owners": "@tinyshop/maintainers, payments: @alice",
        "conventions": "ruff, line length 100.",
        "gaps": "No lockfile.",
    }
    for name, body in pages.items():
        page("project/%s.md" % name, name.title(), "project/" + name, 14, body)
    add_index(["project/%s.md" % n for n in pages])
elif case == "refresh":
    print("project/stack.md is stale (40 days, ttl 14).")
    if bad:
        page("project/stack.md", "Stack", "project/stack", 14, "changed")
print("fake agent done: " + case)
