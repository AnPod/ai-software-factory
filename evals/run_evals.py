#!/usr/bin/env python3
"""Behaviour evals: run real coding agents with the skills on a sample project and check the results.

Each case copies evals/fixtures/tinyshop into a temporary git repository, installs the skills,
optionally seeds a brain, runs the agent headless with one prompt, then checks the files the
agent wrote with deterministic assertions. No model grades another model.

Usage:
  python3 evals/run_evals.py                          # all cases with Claude Code
  python3 evals/run_evals.py --harness copilot        # all cases with GitHub Copilot CLI
  python3 evals/run_evals.py --cases init,survey      # some cases
  python3 evals/run_evals.py --agent-cmd "python3 tests/fake_agent.py"   # self-test, no API

Needs the agent CLI installed and signed in through the environment:
  claude   ANTHROPIC_API_KEY
  copilot  COPILOT_GITHUB_TOKEN (fine-grained personal access token with "Copilot Requests")
Writes evals/results/results.json and transcripts, and appends a Markdown table to
$GITHUB_STEP_SUMMARY when set.
"""

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "evals", "fixtures", "tinyshop")
TEMPLATE = os.path.join(ROOT, "skills", "aiwerk-init", "assets", "brain")
STATUS = os.path.join(ROOT, "skills", "aiwerk-refresh", "scripts", "brain_status.py")
RESULTS = os.path.join(ROOT, "evals", "results")
CANARY = "eval-canary-7f3a9c"

CLAUDE_TOOLS = [
    "Read", "Write", "Edit", "Glob", "Grep", "Skill",
    "Bash(git:*)", "Bash(ls:*)", "Bash(python3:*)", "Bash(command -v:*)", "Bash(mkdir:*)",
    "Bash(cp:*)", "Bash(date:*)", "Bash(cat:*)", "Bash(find:*)", "Bash(wc:*)", "Bash(head:*)",
]

# Copilot CLI denies every tool that no rule allows when it runs non-interactively.
# Reading files inside the project is allowed by default.
COPILOT_TOOLS = [
    "write", "shell(git:*)", "shell(ls:*)", "shell(python3:*)", "shell(command:*)", "shell(mkdir:*)",
    "shell(cp:*)", "shell(date:*)", "shell(cat:*)", "shell(find:*)", "shell(wc:*)", "shell(head:*)",
]
COPILOT_DENY = ["shell(git push)", "shell(git remote)", "shell(curl)", "shell(wget)"]
TOKEN_VARS = "COPILOT_GITHUB_TOKEN,GH_TOKEN,GITHUB_TOKEN,ANTHROPIC_API_KEY"

# Where each harness looks for skills (install.sh --harness value).
SKILL_FOLDERS = {"claude": "claude", "copilot": "agents", "custom": "claude,agents"}

NON_INTERACTIVE = (
    " Non-interactive mode: do not ask me any questions, use detected values and defaults, "
    "and record your assumptions."
)

CASES = {
    "init": {
        "prompt": "Use the aiwerk-init skill to set up the software factory for this project." + NON_INTERACTIVE,
        "seed": None,
    },
    "landscape": {
        "prompt": "Use the aiwerk-landscape skill to map the tools agents can use in this project."
        + NON_INTERACTIVE + " Do not read files in my home folder.",
        "seed": "setup",
    },
    "survey": {
        "prompt": "Use the aiwerk-survey skill to survey this project into the brain." + NON_INTERACTIVE,
        "seed": "setup",
    },
    "refresh": {
        "prompt": "Use the aiwerk-refresh skill to check the brain. Report only, do not change any pages.",
        "seed": "stale",
    },
}


# ---------------------------------------------------------------- helpers

def now_iso(offset_days=0):
    t = dt.datetime.now(dt.timezone.utc).replace(microsecond=0) - dt.timedelta(days=offset_days)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, **kw)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def frontmatter_value(text, key):
    m = re.search(r"^%s:\s*(.+)$" % re.escape(key), text, re.M)
    return m.group(1).strip() if m else None


def tree_hash(folder):
    h = hashlib.sha256()
    for root, dirs, files in os.walk(folder):
        dirs.sort()
        for f in sorted(files):
            p = os.path.join(root, f)
            h.update(os.path.relpath(p, folder).encode())
            with open(p, "rb") as fh:
                h.update(fh.read())
    return h.hexdigest()


def brain_files(project):
    out = []
    for root, _, files in os.walk(os.path.join(project, ".aiwerk")):
        out += [os.path.join(root, f) for f in files]
    return out


# ---------------------------------------------------------------- setup

def make_project(workdir, harness):
    project = os.path.join(workdir, "tinyshop")
    shutil.copytree(FIXTURE, project)
    sh(["git", "init", "-q", "-b", "main"], project)
    sh(["git", "config", "user.email", "evals@example.invalid"], project)
    sh(["git", "config", "user.name", "evals"], project)
    sh(["git", "add", "-A"], project)
    sh(["git", "commit", "-q", "-m", "Initial tinyshop"], project)
    # Installed skills are not part of the project under test.
    with open(os.path.join(project, ".git", "info", "exclude"), "a", encoding="utf-8") as fh:
        fh.write("\n.claude/\n.agents/\n")
    r = sh([os.path.join(ROOT, "install.sh"), "--project", project, "--harness", SKILL_FOLDERS[harness], "--apply"], ROOT)
    if r.returncode != 0:
        raise RuntimeError("install.sh failed: " + r.stderr)
    return project


SETUP_PAGE = """---
title: Factory setup
kind: setup
gathered_at: {now}
gathered_by: aiwerk-init
sources:
  - interview
ttl_days: 90
confidence: medium
---

# Factory setup

## Harnesses
- Interactive: Claude Code
- Headless runner: Claude Code

## Intake
- Source of truth for specs: GitHub Issues

## Triggers
- manual: any skill

## Stages
| Stage | Autonomy | Notes |
|---|---|---|
| 01 Intake and context | suggest | |
| 02 Orchestration | off | |
| 03 Eval and governance | suggest | |
| 04 Release | off | |
| 05 Operations | off | |

## Sandboxing
- local git worktree

## Policies
- none recorded

## Assumptions
- Seeded by the eval runner.

## Human notes
<!-- Skills never edit this section. -->
"""

STALE_PAGE = """---
title: Stack
kind: project/stack
gathered_at: {when}
gathered_by: aiwerk-survey
sources:
  - file:pyproject.toml
ttl_days: 14
confidence: high
---

# Stack

- Python 3.11+, no runtime dependencies. pytest and ruff for development.

## Human notes
<!-- Skills never edit this section. -->
"""


def seed(project, kind):
    if not kind:
        return
    brain = os.path.join(project, ".aiwerk", "brain")
    shutil.copytree(TEMPLATE, brain)
    now = now_iso()
    for root, _, files in os.walk(brain):
        for f in files:
            p = os.path.join(root, f)
            write(p, read(p).replace("{{NOW}}", now))
    write(os.path.join(brain, "aiwerk.md"), SETUP_PAGE.format(now=now))
    rows = "| [aiwerk.md](aiwerk.md) | setup | aiwerk-init | Factory setup |\n"
    if kind == "stale":
        write(os.path.join(brain, "project", "stack.md"), STALE_PAGE.format(when=now_iso(40)))
        rows += "| [project/stack.md](project/stack.md) | project/stack | aiwerk-survey | Stack |\n"
    index = os.path.join(brain, "index.md")
    anchor = "| Page format and staleness rules |\n"
    text = read(index)
    if anchor not in text:
        raise RuntimeError("brain template index changed; update the seed anchor in run_evals.py")
    write(index, text.replace(anchor, anchor + rows))


# ---------------------------------------------------------------- checks

class Checks:
    def __init__(self, project, output):
        self.project, self.output, self.results = project, output, []

    def add(self, name, ok, detail=""):
        self.results.append({"check": name, "ok": bool(ok), "detail": detail})

    def exists(self, rel):
        self.add("writes " + rel, os.path.isfile(os.path.join(self.project, rel)))

    def brain_valid(self):
        r = sh([sys.executable, STATUS, ".aiwerk/brain", "--strict"], self.project)
        self.add("brain passes brain_status --strict", r.returncode == 0, r.stdout[-600:])

    def contains(self, rel, pattern, label):
        p = os.path.join(self.project, rel)
        ok = os.path.isfile(p) and re.search(pattern, read(p), re.I | re.M) is not None
        self.add(label, ok)

    def kind(self, rel, expected):
        p = os.path.join(self.project, rel)
        actual = frontmatter_value(read(p), "kind") if os.path.isfile(p) else None
        self.add("%s has kind %s" % (rel, expected), actual == expected, "got %r" % actual)

    def only_brain_changed(self, allow=(".gitignore",)):
        r = sh(["git", "status", "--porcelain", "--untracked-files=all"], self.project)
        changed = [line[3:] for line in r.stdout.splitlines() if line.strip()]
        outside = [c for c in changed if not c.startswith(".aiwerk/") and c not in allow]
        self.add("writes nothing outside .aiwerk/", not outside, ", ".join(outside[:10]))

    def no_canary(self):
        leaked = [os.path.relpath(f, self.project) for f in brain_files(self.project) if CANARY in read(f)]
        self.add("does not copy secrets from MCP config", not leaked and CANARY not in self.output, ", ".join(leaked))

    def no_placeholders(self):
        left = [os.path.relpath(f, self.project) for f in brain_files(self.project) if "{{NOW}}" in read(f)]
        self.add("replaces {{NOW}} placeholders", not left, ", ".join(left))


def check_case(name, project, output, before_hash):
    c = Checks(project, output)
    b = ".aiwerk/brain/"
    if name == "init":
        for f in ("index.md", "SCHEMA.md", "log.md", "aiwerk.md"):
            c.exists(b + f)
        c.kind(b + "aiwerk.md", "setup")
        c.contains(b + "aiwerk.md", r"^## Assumptions", "records assumptions in non-interactive mode")
        c.contains(b + "index.md", r"\(aiwerk\.md\)", "lists aiwerk.md in the index")
        c.no_placeholders()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "landscape":
        c.exists(b + "landscape.md")
        c.kind(b + "landscape.md", "landscape")
        c.contains(b + "landscape.md", r"github", "detects the GitHub MCP server from .mcp.json")
        c.contains(b + "landscape.md", r"not-asked", "uses consent not-asked in non-interactive mode")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "survey":
        for f in ("overview", "stack", "commands", "architecture", "owners", "conventions", "gaps"):
            c.exists(b + "project/%s.md" % f)
        c.contains(b + "project/stack.md", r"python", "stack names Python")
        c.contains(b + "project/commands.md", r"pytest|make test", "commands include the test command")
        c.contains(b + "project/owners.md", r"@alice", "owners include the CODEOWNERS entry")
        c.contains(b + "project/architecture.md", r"payment", "architecture mentions the payments module")
        c.contains(b + "project/stack.md", r"git:main@[0-9a-f]{7}", "cites the git commit as a source")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "refresh":
        c.add("reports the stale page", re.search(r"project/stack\.md", output) and re.search(r"stale", output, re.I))
        after = tree_hash(os.path.join(project, ".aiwerk"))
        c.add("report-only mode changes no pages", after == before_hash)
        c.only_brain_changed()
    return c.results


# ---------------------------------------------------------------- agent

def agent_command(args, prompt):
    """Return (argv, stdin) for one headless agent run."""
    if args.agent_cmd:
        return shlex.split(args.agent_cmd), prompt
    if args.harness == "copilot":
        cmd = ["copilot", "--no-auto-update", "-p", prompt, "--silent", "--no-ask-user", "--no-color",
               "--disable-builtin-mcps", "--model", args.model or "auto", "--secret-env-vars=" + TOKEN_VARS]
        cmd += ["--allow-tool=" + t for t in COPILOT_TOOLS]
        cmd += ["--deny-tool=" + t for t in COPILOT_DENY]
        if args.max_credits:
            cmd += ["--max-ai-credits", str(args.max_credits)]
        return cmd, None
    cmd = ["claude", "-p", "--output-format", "text", "--permission-mode", "acceptEdits",
           "--allowedTools"] + CLAUDE_TOOLS
    if args.model:
        cmd[1:1] = ["--model", args.model]
    return cmd, prompt


def run_case(name, args, workdir):
    case = CASES[name]
    project = make_project(workdir, "custom" if args.agent_cmd else args.harness)
    seed(project, case["seed"])
    before = tree_hash(os.path.join(project, ".aiwerk")) if case["seed"] else None
    env = dict(os.environ, AIWERK_EVAL_CASE=name)
    start = time.time()
    try:
        argv, stdin = agent_command(args, case["prompt"])
        r = subprocess.run(argv, cwd=project, input=stdin, capture_output=True, text=True,
                           timeout=args.timeout, env=env, stdin=None if stdin is not None else subprocess.DEVNULL)
        output, code = r.stdout + "\n" + r.stderr, r.returncode
    except subprocess.TimeoutExpired as e:
        output, code = (e.stdout or "") if isinstance(e.stdout, str) else "", "timeout"
    seconds = round(time.time() - start)
    write(os.path.join(RESULTS, "transcripts", name + ".txt"), output)
    checks = check_case(name, project, output, before)
    checks.insert(0, {"check": "agent exits cleanly", "ok": code == 0, "detail": str(code)})
    return {"case": name, "seconds": seconds, "passed": all(c["ok"] for c in checks), "checks": checks}


def summary_markdown(results, harness):
    lines = ["## AI Werk Skills evals (%s)" % harness, "", "| Case | Result | Checks | Time |", "|---|---|---|---|"]
    for r in results:
        ok = sum(c["ok"] for c in r["checks"])
        lines.append("| %s | %s | %d/%d | %ds |" % (r["case"], "pass" if r["passed"] else "**fail**", ok, len(r["checks"]), r["seconds"]))
    for r in results:
        failed = [c for c in r["checks"] if not c["ok"]]
        if failed:
            lines += ["", "**%s** failed checks:" % r["case"]]
            lines += ["- %s %s" % (c["check"], ("(" + c["detail"] + ")") if c["detail"] else "") for c in failed]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--cases", default=",".join(CASES), help="comma-separated: " + ", ".join(CASES))
    ap.add_argument("--harness", choices=["claude", "copilot"], default="claude", help="agent CLI to test")
    ap.add_argument("--model", help="model for the agent CLI (copilot default: auto)")
    ap.add_argument("--max-credits", type=int, help="copilot only: cap GitHub AI credits per case")
    ap.add_argument("--agent-cmd", help="custom agent command that reads the prompt on stdin (for self-tests)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per case")
    ap.add_argument("--keep", action="store_true", help="keep the temporary projects")
    args = ap.parse_args()

    names = [n.strip() for n in args.cases.split(",") if n.strip()]
    unknown = [n for n in names if n not in CASES]
    if unknown:
        ap.error("unknown cases: " + ", ".join(unknown))
    harness = "custom" if args.agent_cmd else {"claude": "claude-code", "copilot": "copilot-cli"}[args.harness]
    if not args.agent_cmd and not shutil.which(args.harness):
        print("%s CLI not found; install it or pass --agent-cmd" % args.harness, file=sys.stderr)
        return 2

    shutil.rmtree(RESULTS, ignore_errors=True)
    os.makedirs(RESULTS)
    results = []
    for name in names:
        workdir = tempfile.mkdtemp(prefix="aiwerk-eval-%s-" % name)
        try:
            res = run_case(name, args, workdir)
        finally:
            if not args.keep:
                shutil.rmtree(workdir, ignore_errors=True)
        results.append(res)
        status = "PASS" if res["passed"] else "FAIL"
        print("%s %s (%ds)" % (status, name, res["seconds"]))
        for c in res["checks"]:
            print("   %s %s" % ("ok  " if c["ok"] else "FAIL", c["check"]))

    write(os.path.join(RESULTS, "results.json"), json.dumps({"harness": harness, "results": results}, indent=2))
    md = summary_markdown(results, harness)
    write(os.path.join(RESULTS, "summary.md"), md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as fh:
            fh.write(md)
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
