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
    "Bash(pytest:*)", "Bash(make test)", "Bash(make lint)", "Bash(skillspector:*)",
]

# Copilot CLI denies every tool that no rule allows when it runs non-interactively.
# Reading files inside the project is allowed by default.
COPILOT_TOOLS = [
    "write", "shell(git:*)", "shell(ls:*)", "shell(python3:*)", "shell(command:*)", "shell(mkdir:*)",
    "shell(cp:*)", "shell(date:*)", "shell(cat:*)", "shell(find:*)", "shell(wc:*)", "shell(head:*)",
    "shell(pytest:*)", "shell(make test)", "shell(make lint)", "shell(skillspector:*)",
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
    "readiness": {
        "prompt": "Use the aiwerk-readiness skill to score agent readiness for this project." + NON_INTERACTIVE,
        "seed": "surveyed",
    },
    "intake": {
        "prompt": "Use the aiwerk-intake skill to capture the request in docs/issue-12.md as ticket GH-12."
        + NON_INTERACTIVE,
        "seed": "surveyed",
    },
    "spec": {
        "prompt": "Use the aiwerk-spec skill to write a specification for GH-12." + NON_INTERACTIVE,
        "seed": "ticket",
    },
    "context": {
        "prompt": "Use the aiwerk-context skill to assemble the minimal context pack for GH-12." + NON_INTERACTIVE,
        "seed": "spec",
    },
    "plan": {
        "prompt": "Use the aiwerk-plan skill to break spec GH-12 into tasks." + NON_INTERACTIVE,
        "seed": "context",
    },
    "dispatch": {
        "prompt": "Use the aiwerk-dispatch skill to prepare headless dispatch commands for GH-12." + NON_INTERACTIVE,
        "seed": "tasks",
    },
    "sandbox": {
        "prompt": "Use the aiwerk-sandbox skill to prepare the sandbox plan for GH-12." + NON_INTERACTIVE,
        "seed": "tasks",
    },
    "review": {
        "prompt": "Use the aiwerk-review skill to review the GH-12 diff against main." + NON_INTERACTIVE,
        "seed": "impl_branch",
    },
    "test-gate": {
        "prompt": "Use the aiwerk-test-gate skill to run the test gate for GH-12." + NON_INTERACTIVE,
        "seed": "impl_branch",
    },
    "security-gate": {
        "prompt": "Use the aiwerk-security-gate skill to run the security gate for GH-12 against main."
        + NON_INTERACTIVE,
        "seed": "impl_branch",
    },
    "policy": {
        "prompt": "Use the aiwerk-policy skill to check the GH-12 diff against project policies." + NON_INTERACTIVE,
        "seed": "impl_branch",
    },
    "release": {
        "prompt": "Use the aiwerk-release skill to draft release notes, version bump and PR description for GH-12 against main."
        + NON_INTERACTIVE,
        "seed": "gated_branch",
    },
    "deploy-check": {
        "prompt": "Use the aiwerk-deploy-check skill to build the pre-deploy checklist for GH-12 against main."
        + NON_INTERACTIVE,
        "seed": "gated_branch",
    },
    "docs-sync": {
        "prompt": "Use the aiwerk-docs-sync skill to sync repository documentation and brain pages after the latest merged commit (HEAD~1..HEAD)."
        + NON_INTERACTIVE,
        "seed": "merged_docs",
    },
    "incident": {
        "prompt": "Use the aiwerk-incident skill to triage the incident reported in docs/incident-alert.md and save it to .aiwerk/brain/incidents/2026-11-19-negative-discount-cap.md."
        + NON_INTERACTIVE,
        "seed": "incident_alert",
    },
    "incident-to-spec": {
        "prompt": "Use the aiwerk-incident-to-spec skill to turn .aiwerk/brain/incidents/2026-11-19-negative-discount-cap.md into stage 01 ticket INC-01."
        + NON_INTERACTIVE,
        "seed": "resolved_incident",
    },
    "slo": {
        "prompt": "Use the aiwerk-slo skill to summarise SLOs and error budgets for this project." + NON_INTERACTIVE,
        "seed": "resolved_incident",
    },
    "health": {
        "prompt": "Use the aiwerk-health skill to generate health.md and health.html for this project." + NON_INTERACTIVE,
        "seed": "surveyed",
    },
    "skill-audit": {
        "prompt": "Use the aiwerk-skill-audit skill to audit every installed skill in this project." + NON_INTERACTIVE,
        "seed": "skill_audit",
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
    return m.group(1).strip().strip("'\"") if m else None


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


def count_context_entries(text):
    """Count context pack entries outside Excluded, Assumptions and Human notes."""
    in_frontmatter = False
    skip_section = False
    in_table = False
    count = 0
    for i, raw in enumerate(text.splitlines()):
        line = raw.strip()
        if i == 0 and line == "---":
            in_frontmatter = True
            continue
        if in_frontmatter:
            if line == "---":
                in_frontmatter = False
            continue
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            skip_section = heading in ("excluded", "assumptions", "human notes")
            in_table = False
            continue
        if skip_section or not line:
            continue
        if line.startswith("|"):
            if re.match(r"^\|\s*[-:]+", line):
                in_table = True
                continue
            if not in_table:
                continue
            count += 1
        elif re.match(r"^(\d+\.|-)\s+", line):
            low = line.lower()
            if low in ("- none", "- none."):
                continue
            count += 1
    return count


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


def make_page(title, kind, gathered_at, gathered_by, sources, ttl_days, confidence, body):
    src = "".join("  - %s\n" % s for s in sources)
    return (
        "---\n"
        "title: %s\n"
        "kind: %s\n"
        "gathered_at: %s\n"
        "gathered_by: %s\n"
        "sources:\n%s"
        "ttl_days: %d\n"
        "confidence: %s\n"
        "---\n\n%s\n\n## Human notes\n<!-- Skills never edit this section. -->\n"
        % (title, kind, gathered_at, gathered_by, src, ttl_days, confidence, body.strip())
    )


SETUP_BODY_BASIC = """# Factory setup

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
- Seeded by the eval runner."""

SETUP_BODY_STAGES_1_TO_3 = """# Factory setup

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
| 02 Orchestration | suggest | |
| 03 Eval and governance | suggest | |
| 04 Release | off | |
| 05 Operations | off | |

## Sandboxing
- local git worktree

## Policies
- No PII stored or logged in cart data.
- New runtime dependencies require Apache-2.0 or MIT licence review.
- Changes to src/tinyshop/payments.py require @alice approval.

## Assumptions
- Seeded by the eval runner."""

SETUP_BODY_ALL_STAGES = """# Factory setup

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
| 02 Orchestration | suggest | |
| 03 Eval and governance | suggest | |
| 04 Release | %s | |
| 05 Operations | suggest | |

## Sandboxing
- local git worktree

## Policies
- No PII stored or logged in cart data.
- New runtime dependencies require Apache-2.0 or MIT licence review.
- Changes to src/tinyshop/payments.py require @alice approval.

## Assumptions
- Seeded by the eval runner."""

LANDSCAPE_BODY = """# Tool landscape

## Sources
| Source | Kind | Stages | Detected in | Consent | Notes |
|---|---|---|---|---|---|
| GitHub | mcp | 01, 02, 04 | .mcp.json | not-asked | |

## Browser and computer use
- not available

## Gaps
| Stage | Missing | Options |
|---|---|---|
| 03 | Security scanner | Semgrep, Snyk, GitGuardian ggshield |"""

LANDSCAPE_BODY_OPS = """# Tool landscape

## Sources
| Source | Kind | Stages | Detected in | Consent | Notes |
|---|---|---|---|---|---|
| GitHub | mcp | 01, 02, 04 | .mcp.json | not-asked | |
| Datadog | mcp | 05 | interview | not-asked | |
| PagerDuty | mcp | 05 | interview | ask | Sends pages |

## Browser and computer use
- not available

## Gaps
| Stage | Missing | Options |
|---|---|---|
| 03 | Security scanner | Semgrep, Snyk, GitGuardian ggshield |
| 05 | Observability read access | Datadog, Grafana, Sentry |"""

TICKET_BODY = """# GH-12: Apply a per-SKU discount cap

## Metadata
- ID: `GH-12`
- Source: `file:docs/issue-12.md`
- Requester: `@bob`
- Labels: `enhancement, pricing`
- Links: `https://github.com/example/tinyshop/issues/12`

## Problem
Add an optional per-SKU `max_discount_percent` cap on `LineItem` so cart-wide discounts cannot exceed a SKU's cap. Keep calculations in `Decimal`, apply 22% VAT after discounts, round half up to cents, and reject caps outside 0..100 with `ValueError`.

## Raw text
> Add an optional `max_discount_percent` field (`Decimal | None`, default `None`) to `LineItem`.

## Assumptions
- Seeded by the eval runner."""

SPEC_BODY = """# GH-12 spec: Per-SKU discount cap

## Goal
Allow each `LineItem` in `src/tinyshop/cart.py` to specify an optional `max_discount_percent` so cart discounts are capped per SKU while keeping `Decimal` precision and 22% VAT rounding.

## Non-goals
- Changing VAT rates or payment provider logic in `src/tinyshop/payments.py`.
- Adding currency conversion or coupon code storage.

## Acceptance criteria
1. `LineItem` accepts an optional `max_discount_percent: Decimal | None = None`.
2. When `max_discount_percent` is `None`, the line item receives the full `Cart.discount_percent`.
3. When `max_discount_percent` is set, the item receives `min(cart.discount_percent, item.max_discount_percent)`.
4. A cap of `Decimal("0")` results in zero discount on that item even when `Cart.discount_percent > 0`.
5. Constructing a `LineItem` with `max_discount_percent < 0` or `> 100` raises `ValueError`.
6. Totals remain `Decimal`, apply 22% VAT after discounts, and round half up to cents per ADR 0001.

## Affected modules
| Path | Role in this change |
|---|---|
| `src/tinyshop/cart.py` | Add `max_discount_percent` to `LineItem`, validate bounds and apply per-item cap in `Cart.total()` |
| `tests/test_cart.py` | Add unit tests covering uncapped, capped, zero-cap and invalid-cap cases |

## Constraints and decisions
- `docs/adr/0001-use-decimal-for-money.md`: keep all money values in `Decimal` and round half up at the end.

## Risks
- Mixing line-level and cart-level rounding could drift by 1 cent; round only once after VAT.

## Open questions
- None.

## Assumptions
- Seeded by the eval runner."""

CONTEXT_BODY = """# GH-12 context pack

Budget: **6 / 25 entries**

## Files and docs
| # | Category | Path | Why it matters |
|---|---|---|---|
| 1 | code | `src/tinyshop/cart.py` | Defines `LineItem` and `Cart.total()` where the per-SKU cap goes |
| 2 | code | `src/tinyshop/__init__.py` | Exports `Cart` and `LineItem` |
| 3 | test | `tests/test_cart.py` | Existing unit tests for totals, VAT and discounts |
| 4 | doc | `docs/adr/0001-use-decimal-for-money.md` | Requires `Decimal` math and half-up cent rounding |
| 5 | doc | `pyproject.toml` | Ruff line-length 100 and pytest settings |

## Commands
| # | Command | Source | Why it matters |
|---|---|---|---|
| 6 | `make test` (`pytest -q`) | `Makefile` | Runs the unit test suite |

## Data lineage and external context
- none

## Excluded
- `src/tinyshop/payments.py` (out of scope per spec non-goals)

## Assumptions
- Seeded by the eval runner."""

TASKS_BODY = """# GH-12 task plan

## Task summary
| ID | Task | Files touched | Depends on | Parallel with |
|---|---|---|---|---|
| T1 | Add `max_discount_percent` and per-SKU capping to `Cart` | `src/tinyshop/cart.py` | none | none |
| T2 | Add unit tests for capped, uncapped, zero-cap and invalid caps | `tests/test_cart.py` | T1 | none |

## Execution waves
- **Wave 1:** T1
- **Wave 2:** T2

## Task details

### T1: Add `max_discount_percent` and per-SKU capping to `Cart`
- **Scope:** Add `max_discount_percent: Decimal | None = None` to `LineItem`, raise `ValueError` outside 0..100, and apply `min(cart.discount_percent, item.max_discount_percent)` per line item in `Cart.total()`.
- **Files touched:** `src/tinyshop/cart.py`
- **Depends on:** none
- **Done criteria:** Acceptance criteria 1 to 6 implemented; `make test` passes.

### T2: Add unit tests for capped, uncapped, zero-cap and invalid caps
- **Scope:** Add pytest cases in `tests/test_cart.py` covering every acceptance criterion.
- **Files touched:** `tests/test_cart.py`
- **Depends on:** T1
- **Done criteria:** All new and existing tests pass under `make test`.

## Assumptions
- Seeded by the eval runner."""

IMPL_CART_PY = '''"""Cart totals with percentage discounts and VAT."""

from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP

VAT_RATE = Decimal("0.22")


@dataclass
class LineItem:
    sku: str
    unit_price: Decimal
    quantity: int = 1
    max_discount_percent: Decimal | None = None

    def total(self) -> Decimal:
        return self.unit_price * self.quantity


@dataclass
class Cart:
    items: list[LineItem] = field(default_factory=list)
    discount_percent: Decimal = Decimal("0")

    def add(self, item: LineItem) -> None:
        self.items.append(item)

    def subtotal(self) -> Decimal:
        return sum((i.total() for i in self.items), Decimal("0"))

    def total(self) -> Decimal:
        discounted = Decimal("0")
        for item in self.items:
            effective = self.discount_percent
            if item.max_discount_percent is not None:
                effective = min(effective, item.max_discount_percent)
            discounted += item.total() * (1 - effective / 100)
        with_vat = discounted * (1 + VAT_RATE)
        return with_vat.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
'''

DOCS_CART_MD = """# Cart pricing

`LineItem` takes `sku`, `unit_price` and `quantity`.

`Cart` applies a single cart-wide `discount_percent` equally to every line item, then adds 22% VAT and rounds half up to cents.
"""

INCIDENT_ALERT_MD = """# Alert: Checkout total spike on SKU-42 (2026-11-19)

- **Detected (UTC):** 2026-11-19T14:12:00Z
- **Service:** tinyshop checkout pricing
- **Severity:** sev2
- **Symptom:** Orders containing `SKU-42` produced totals higher than `subtotal * 1.22` after GH-12 shipped. A catalog sync passed `max_discount_percent=Decimal("-10")` on `LineItem`, which caused `Cart.total()` in `src/tinyshop/cart.py` to charge 110% before VAT instead of raising `ValueError`.
- **Mitigated (UTC):** 2026-11-19T14:28:00Z (bad negative cap value removed from catalog feed for SKU-42).
"""

GATE_REVIEW_BODY = """# GH-12 adversarial review

- **Reviewed range:** `main...HEAD`
- **Verdict:** `pass`

## Acceptance criteria check
- Criteria 1 to 6 verified against `src/tinyshop/cart.py`."""

GATE_TESTS_BODY = """# GH-12 test gate

- **Command:** `make test` (`pytest -q`)
- **Verdict:** `pass`

## Coverage
- Existing and new cart tests pass."""

GATE_SECURITY_BODY = """# GH-12 security gate

- **Mode:** manual checklist
- **Scanners run:** none
- **Verdict:** `warn`

## Recommended scanner
- Semgrep for Python static security checks."""

GATE_POLICY_BODY = """# GH-12 policy gate

- **Verdict:** `pass`

## Rule results
- P1 PII: pass
- P2 Licence: pass
- P4 Approvers: pass (`src/tinyshop/payments.py` untouched)."""

RESOLVED_INCIDENT_BODY = """# Incident: Negative max_discount_percent inflated checkout totals

- **Date (UTC):** `2026-11-19`
- **Status:** `resolved`
- **Severity:** `sev2`
- **Affected modules:** `src/tinyshop/cart.py`
- **Owner:** `@tinyshop/maintainers`

## Summary
After GH-12 shipped, a catalog sync passed `max_discount_percent=Decimal("-10")` to `LineItem`. Because `LineItem` lacked bounds validation, `Cart.total()` computed `1 - (-10 / 100) = 1.10`, inflating order totals by 10% before VAT until the catalog entry was removed.

## Timeline (UTC)
| Time (UTC) | Event | Source |
|---|---|---|
| `2026-11-19T14:12:00Z` | Alert fired on checkout total mismatch for SKU-42 | `file:docs/incident-alert.md` |
| `2026-11-19T14:28:00Z` | Negative cap removed from catalog feed; totals returned to normal | `file:docs/incident-alert.md` |

## Root-cause hypotheses
1. **Missing 0..100 bounds validation on `LineItem.max_discount_percent`** (confidence: `high`)
   - **Evidence:** `src/tinyshop/cart.py` defines `LineItem` without `__post_init__` validation, so negative or >100 values are accepted and applied directly in `Cart.total()`.
   - **Fix needed:** Validate `0 <= max_discount_percent <= 100` in `LineItem.__post_init__`, raising `ValueError`, and add regression tests in `tests/test_cart.py`."""


def seed(project, kind):
    if not kind:
        return

    if kind in ("impl_branch", "gated_branch"):
        sh(["git", "checkout", "-q", "-b", "feat/gh-12"], project)
        write(os.path.join(project, "src", "tinyshop", "cart.py"), IMPL_CART_PY)
        sh(["git", "add", "src/tinyshop/cart.py"], project)
        sh(["git", "commit", "-q", "-m", "Add per-SKU discount cap to Cart"], project)

    base_commit = None
    if kind == "merged_docs":
        write(os.path.join(project, "docs", "cart.md"), DOCS_CART_MD)
        sh(["git", "add", "docs/cart.md"], project)
        sh(["git", "commit", "-q", "-m", "Document cart pricing"], project)
        base_commit = sh(["git", "rev-parse", "--short", "HEAD"], project).stdout.strip()
        write(os.path.join(project, "src", "tinyshop", "cart.py"), IMPL_CART_PY)
        sh(["git", "add", "src/tinyshop/cart.py"], project)
        sh(["git", "commit", "-q", "-m", "Merge GH-12: add per-SKU max_discount_percent cap"], project)

    if kind in ("incident_alert", "resolved_incident"):
        write(os.path.join(project, "src", "tinyshop", "cart.py"), IMPL_CART_PY)
        write(os.path.join(project, "docs", "incident-alert.md"), INCIDENT_ALERT_MD)
        sh(["git", "add", "src/tinyshop/cart.py", "docs/incident-alert.md"], project)
        sh(["git", "commit", "-q", "-m", "Deploy GH-12 cart cap and capture alert report"], project)

    if kind == "skill_audit":
        third_party = (
            "---\n"
            "name: example-helper\n"
            "description: Summarise CHANGELOG entries for release notes. Use when reviewing changelog entries.\n"
            "license: MIT\n"
            "---\n\n"
            "# example-helper\n\n"
            "Read CHANGELOG.md and print a three-bullet summary.\n"
        )
        for folder in (".claude/skills", ".agents/skills"):
            target_root = os.path.join(project, folder)
            if os.path.isdir(target_root):
                write(os.path.join(target_root, "example-helper", "SKILL.md"), third_party)

    brain = os.path.join(project, ".aiwerk", "brain")
    shutil.copytree(TEMPLATE, brain)
    now = now_iso()
    for root, _, files in os.walk(brain):
        for f in files:
            p = os.path.join(root, f)
            write(p, read(p).replace("{{NOW}}", now))

    commit = sh(["git", "rev-parse", "--short", "HEAD"], project).stdout.strip()
    branch = sh(["git", "branch", "--show-current"], project).stdout.strip() or "main"
    git_src = "git:%s@%s" % (branch, base_commit or commit)

    stage_level = {
        "setup": 0,
        "stale": 0,
        "surveyed": 1,
        "skill_audit": 1,
        "ticket": 2,
        "spec": 3,
        "context": 4,
        "tasks": 5,
        "impl_branch": 5,
        "gated_branch": 6,
        "merged_docs": 1,
        "incident_alert": 1,
        "resolved_incident": 7,
    }[kind]

    if kind in ("gated_branch", "merged_docs", "incident_alert", "resolved_incident"):
        stage4_mode = "assist" if kind == "merged_docs" else "suggest"
        setup_body = SETUP_BODY_ALL_STAGES % stage4_mode
    else:
        setup_body = SETUP_BODY_BASIC if stage_level == 0 else SETUP_BODY_STAGES_1_TO_3

    landscape_body = LANDSCAPE_BODY_OPS if kind in ("incident_alert", "resolved_incident") else LANDSCAPE_BODY
    pages = [
        ("aiwerk.md", "Factory setup", "setup", now, "aiwerk-init", ["interview"], 90, "medium", setup_body),
    ]

    if kind == "stale":
        pages.append((
            "project/stack.md", "Stack", "project/stack", now_iso(40), "aiwerk-survey",
            ["file:pyproject.toml"], 14, "high",
            "# Stack\n\n- Python 3.11+, no runtime dependencies. pytest and ruff for development.",
        ))

    if stage_level >= 1:
        pages.extend([
            ("landscape.md", "Tool landscape", "landscape", now, "aiwerk-landscape",
             ["file:.mcp.json"], 30, "medium", landscape_body),
            ("project/overview.md", "Overview", "project/overview", now, "aiwerk-survey",
             [git_src, "file:README.md"], 14, "high",
             "# Overview\n\nSmall Python shopping cart library with discounts, VAT and a payment provider adapter."),
            ("project/stack.md", "Stack", "project/stack", now, "aiwerk-survey",
             [git_src, "file:pyproject.toml"], 14, "high",
             "# Stack\n\n- Python >=3.11, zero runtime dependencies.\n- Dev tools: pytest, ruff."),
            ("project/commands.md", "Commands", "project/commands", now, "aiwerk-survey",
             [git_src, "file:Makefile", "file:.github/workflows/ci.yml"], 14, "high",
             "# Commands\n\n- Test: `make test` (`pytest -q`), run in CI.\n- Lint: `make lint` (`ruff check src tests`), run in CI."),
            ("project/architecture.md", "Architecture", "project/architecture", now, "aiwerk-survey",
             [git_src], 14, "high",
             "# Architecture\n\n- `src/tinyshop/cart.py`: `LineItem` and `Cart` totals with VAT.\n- `src/tinyshop/payments.py`: reads `TINYSHOP_PAYMENTS_KEY` from env."),
            ("project/owners.md", "Owners", "project/owners", now, "aiwerk-survey",
             [git_src, "file:.github/CODEOWNERS"], 60, "high",
             "# Owners\n\n- `*`: `@tinyshop/maintainers`\n- `src/tinyshop/payments.py`: `@alice`"),
            ("project/conventions.md", "Conventions", "project/conventions", now, "aiwerk-survey",
             [git_src, "file:pyproject.toml"], 14, "high",
             "# Conventions\n\n- Ruff line length 100.\n- All money values use `decimal.Decimal` (ADR 0001)."),
            ("project/gaps.md", "Gaps", "project/gaps", now, "aiwerk-survey",
             [git_src], 14, "high",
             "# Gaps\n\n- No dependency lockfile.\n- No `AGENTS.md` or `CLAUDE.md`.\n- Inline Authorization header in `.mcp.json`."),
            ("decisions/index.md", "Decisions", "decision/index", now, "aiwerk-survey",
             [git_src, "file:docs/adr/0001-use-decimal-for-money.md"], 180, "high",
             "# Decisions\n\n- ADR 0001 (`docs/adr/0001-use-decimal-for-money.md`): use `decimal.Decimal` for money and round half up to cents."),
        ])

    if 2 <= stage_level <= 6:
        pages.append((
            "specs/GH-12/ticket.md", "GH-12: Apply a per-SKU discount cap", "spec/ticket", now,
            "aiwerk-intake", ["file:docs/issue-12.md"], 30, "high", TICKET_BODY,
        ))
    if 3 <= stage_level <= 6:
        pages.append((
            "specs/GH-12/spec.md", "GH-12 spec: Per-SKU discount cap", "spec", now,
            "aiwerk-spec", ["file:.aiwerk/brain/specs/GH-12/ticket.md", git_src], 30, "high", SPEC_BODY,
        ))
    if 4 <= stage_level <= 6:
        pages.append((
            "specs/GH-12/context.md", "GH-12 context pack", "spec/context", now,
            "aiwerk-context", ["file:.aiwerk/brain/specs/GH-12/spec.md", git_src], 7, "high", CONTEXT_BODY,
        ))
    if 5 <= stage_level <= 6:
        pages.append((
            "specs/GH-12/tasks.md", "GH-12 task plan", "spec/tasks", now,
            "aiwerk-plan", ["file:.aiwerk/brain/specs/GH-12/spec.md", "file:.aiwerk/brain/specs/GH-12/context.md", git_src],
            14, "high", TASKS_BODY,
        ))
    if stage_level == 6:
        pages.extend([
            ("policies/index.md", "Project policies", "policy/index", now, "aiwerk-policy",
             ["file:.aiwerk/brain/aiwerk.md"], 90, "high",
             "# Project policies\n\n- P1 PII: no PII in cart.\n- P2 Licence: Apache-2.0 or MIT.\n- P4 Approvers: `@alice` for `src/tinyshop/payments.py`."),
            ("specs/GH-12/review.md", "GH-12 adversarial review", "spec/review", now, "aiwerk-review",
             ["file:.aiwerk/brain/specs/GH-12/spec.md", git_src], 7, "high", GATE_REVIEW_BODY),
            ("specs/GH-12/tests.md", "GH-12 test gate", "spec/tests", now, "aiwerk-test-gate",
             ["file:.aiwerk/brain/specs/GH-12/spec.md", git_src], 7, "high", GATE_TESTS_BODY),
            ("specs/GH-12/security.md", "GH-12 security gate", "spec/security", now, "aiwerk-security-gate",
             ["file:.aiwerk/brain/landscape.md", git_src], 7, "medium", GATE_SECURITY_BODY),
            ("specs/GH-12/policy.md", "GH-12 policy gate", "spec/policy", now, "aiwerk-policy",
             ["file:.aiwerk/brain/policies/index.md", git_src], 7, "high", GATE_POLICY_BODY),
        ])
    if stage_level == 7:
        pages.append((
            "incidents/2026-11-19-negative-discount-cap.md",
            "Incident: Negative max_discount_percent inflated checkout totals",
            "incident", now, "aiwerk-incident",
            ["file:docs/incident-alert.md", git_src], 7, "high", RESOLVED_INCIDENT_BODY,
        ))

    rows = []
    for rel, title, pkind, when, by, srcs, ttl, conf, body in pages:
        write(os.path.join(brain, rel), make_page(title, pkind, when, by, srcs, ttl, conf, body))
        rows.append("| [%s](%s) | %s | %s | %s |\n" % (rel, rel, pkind, by, title))

    index = os.path.join(brain, "index.md")
    anchor = "| Page format and staleness rules |\n"
    text = read(index)
    if anchor not in text:
        raise RuntimeError("brain template index changed; update the seed anchor in run_evals.py")
    write(index, text.replace(anchor, anchor + "".join(rows)))


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

    def not_contains(self, rel, pattern, label):
        p = os.path.join(self.project, rel)
        ok = os.path.isfile(p) and re.search(pattern, read(p), re.I | re.M) is None
        self.add(label, ok)

    def kind(self, rel, expected):
        p = os.path.join(self.project, rel)
        actual = frontmatter_value(read(p), "kind") if os.path.isfile(p) else None
        self.add("%s has kind %s" % (rel, expected), actual == expected, "got %r" % actual)

    def only_brain_changed(self, allow=(".gitignore",), label="writes nothing outside .aiwerk/"):
        r = sh(["git", "status", "--porcelain", "--untracked-files=all"], self.project)
        changed = [line[3:] for line in r.stdout.splitlines() if line.strip()]
        outside = [c for c in changed if not c.startswith(".aiwerk/") and c not in allow]
        self.add(label, not outside, ", ".join(outside[:10]))

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
    elif name == "readiness":
        p = b + "project/readiness.md"
        c.exists(p)
        c.kind(p, "project/readiness")
        c.contains(p, r"\b\d{1,3}\s*/\s*100\b", "includes a 0 to 100 readiness score")
        c.contains(p, r"lockfile|lock\s+file", "flags missing lockfile")
        c.contains(p, r"AGENTS\.md|CLAUDE\.md", "flags missing agent instructions")
        c.contains(p, r"top\s+(three|3)\s+fix|highest[- ]value\s+fix", "lists top three fixes")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "intake":
        p = b + "specs/GH-12/ticket.md"
        c.exists(p)
        c.kind(p, "spec/ticket")
        c.contains(p, r"discount", "captures the discount requirement")
        c.contains(p, r"sku|cap", "captures the per-SKU cap")
        c.contains(p, r"raw\s+text|^>", "quotes raw ticket text")
        c.contains(p, r"docs/issue-12\.md", "cites the source file")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "spec":
        p = b + "specs/GH-12/spec.md"
        c.exists(p)
        c.kind(p, "spec")
        c.contains(p, r"cart\.py", "names affected module cart.py")
        c.contains(p, r"Decimal", "preserves Decimal requirement from ADR")
        c.contains(p, r"acceptance\s+criteria", "includes acceptance criteria")
        c.contains(p, r"non-goals|non goals", "includes non-goals")
        c.contains(p, r"open\s+questions", "includes open questions section")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "context":
        p = b + "specs/GH-12/context.md"
        c.exists(p)
        c.kind(p, "spec/context")
        c.contains(p, r"cart\.py", "includes cart.py")
        c.contains(p, r"test_cart\.py", "includes test_cart.py")
        c.contains(p, r"pytest|make test", "includes test command")
        full = os.path.join(project, p)
        n = count_context_entries(read(full)) if os.path.isfile(full) else 0
        c.add("stays within 25-entry budget", 1 <= n <= 25, "counted %d entries" % n)
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "plan":
        p = b + "specs/GH-12/tasks.md"
        c.exists(p)
        c.kind(p, "spec/tasks")
        c.contains(p, r"cart\.py", "references cart.py")
        c.contains(p, r"test_cart\.py", "references test_cart.py")
        c.contains(p, r"\bT1\b|\bTask\s+1\b", "numbers tasks")
        c.contains(p, r"depend", "records dependency order")
        c.contains(p, r"parallel", "notes parallelisation")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "dispatch":
        p = b + "specs/GH-12/dispatch.md"
        c.exists(p)
        c.kind(p, "spec/dispatch")
        c.contains(p, r"git\s+worktree\s+add", "plans git worktree per task")
        c.contains(p, r"claude\s+-p", "uses the configured headless harness command")
        c.not_contains(p, r"dangerously-skip-permissions|--allow-all|--yolo", "avoids broad permission flags")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "sandbox":
        p = b + "specs/GH-12/sandbox.md"
        c.exists(p)
        c.kind(p, "spec/sandbox")
        c.contains(p, r"worktree", "selects local git worktree")
        c.contains(p, r"git\s+worktree", "documents worktree commands")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "review":
        p = b + "specs/GH-12/review.md"
        c.exists(p)
        c.kind(p, "spec/review")
        c.contains(p, r"cart\.py", "reviews cart.py from the diff")
        c.contains(p, r"acceptance\s+criteria", "evaluates acceptance criteria")
        c.contains(p, r"\b(met|not met|partial)\b", "marks criteria status")
        c.contains(p, r"\b(pass with fixes|pass|fail)\b", "assigns a review verdict")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "test-gate":
        p = b + "specs/GH-12/tests.md"
        c.exists(p)
        c.kind(p, "spec/tests")
        c.contains(p, r"pytest|make test", "records the documented test command")
        c.contains(p, r"untested|not\s+tested|gap|missing", "identifies untested acceptance criteria")
        c.contains(p, r"propos|test_", "proposes concrete test cases")
        c.contains(p, r"\b(pass|gaps|fail)\b", "assigns a gate verdict")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "security-gate":
        p = b + "specs/GH-12/security.md"
        c.exists(p)
        c.kind(p, "spec/security")
        c.contains(p, r"critical|high|medium|low|checklist", "summarises severity or manual checklist")
        c.contains(p, r"semgrep|snyk|ggshield|gitguardian|socket|wiz", "recommends a security scanner")
        c.contains(p, r"\b(pass|warn|fail)\b", "assigns a security verdict")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "policy":
        p_idx = b + "policies/index.md"
        p = b + "specs/GH-12/policy.md"
        c.exists(p_idx)
        c.kind(p_idx, "policy/index")
        c.exists(p)
        c.kind(p, "spec/policy")
        c.contains(p, r"\bPII\b|personal\s+data", "checks PII policy")
        c.contains(p, r"licen[cs]e", "checks dependency licence policy")
        c.contains(p, r"approv|@alice|maintainers", "checks required approvers")
        c.contains(p, r"\b(pass|needs-approval|fail)\b", "assigns a policy verdict")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "release":
        p = b + "specs/GH-12/release.md"
        c.exists(p)
        c.kind(p, "spec/release")
        c.contains(p, r"0\.3\.0|0\.4\.0", "grounds version in pyproject.toml")
        c.contains(p, r"\bminor\b", "suggests a minor semver bump")
        c.contains(p, r"release\s+notes|##\s+Added", "includes release notes")
        c.contains(p, r"spec\.md", "links to spec.md")
        c.contains(p, r"review\.md|tests\.md|security\.md|policy\.md", "links to stage 03 gates")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "deploy-check":
        p = b + "specs/GH-12/deploy.md"
        c.exists(p)
        c.kind(p, "spec/deploy")
        c.contains(p, r"migration", "checks migrations")
        c.contains(p, r"feature\s+flag", "checks feature flags")
        c.contains(p, r"config|env", "checks config and env changes")
        c.contains(p, r"\bCI\b|ci\.yml", "checks CI status")
        c.contains(p, r"rollback", "defines a rollback trigger and plan")
        c.contains(p, r"@tinyshop/maintainers|@alice", "names a deploy owner handle")
        c.contains(p, r"\b(ready|needs-verification|blocked)\b", "assigns deploy readiness status")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "docs-sync":
        c.contains("docs/cart.md", r"max_discount_percent|per-sku|discount\s+cap", "updates stale repo doc docs/cart.md")
        c.contains(b + "project/architecture.md", r"max_discount_percent|per-sku|discount\s+cap", "refreshes brain page project/architecture.md")
        c.contains(b + "log.md", r"aiwerk-docs-sync.*(refreshed|verified)", "logs refreshed or verified entries in log.md")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed(
            allow=(".gitignore", "README.md", "docs/cart.md"),
            label="writes only to .aiwerk/ and allowed docs",
        )
    elif name == "incident":
        p = b + "incidents/2026-11-19-negative-discount-cap.md"
        c.exists(p)
        c.kind(p, "incident")
        c.contains(p, r"timeline", "builds an incident timeline")
        c.contains(p, r"14:12|2026-11-19", "records UTC incident timestamps")
        c.contains(p, r"hypothes", "lists root-cause hypotheses")
        c.contains(p, r"cart\.py", "cites cart.py as evidence")
        c.contains(p, r"max_discount_percent|LineItem", "identifies the missing cap validation")
        c.contains(p, r"@tinyshop/maintainers|@alice", "identifies an owner handle")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "incident-to-spec":
        p = b + "specs/INC-01/ticket.md"
        c.exists(p)
        c.kind(p, "spec/ticket")
        c.contains(p, r"2026-11-19-negative-discount-cap\.md", "links back to the resolved incident")
        c.contains(p, r"cart\.py", "names affected module cart.py")
        c.contains(p, r"max_discount_percent|ValueError", "captures the root-cause fix requirement")
        c.contains(p, r"prevent|regression|guardrail|test", "includes prevention or regression scope")
        c.contains(p, r"raw\s+text|^>", "quotes raw incident excerpt")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "slo":
        p = b + "slo.md"
        c.exists(p)
        c.kind(p, "slo")
        c.contains(p, r"not\s+connected|unavailable|no\s+live|none\s+connected", "reports missing live telemetry honestly")
        c.contains(p, r"error\s+budget", "addresses error budgets")
        c.contains(p, r"cart|payment|incident|negative-discount-cap", "grounds SLOs in project modules or incidents")
        c.contains(p, r"datadog|grafana|prometheus|sentry|splunk", "references or recommends an observability tool")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "health":
        p_md = b + "health.md"
        p_html = b + "health.html"
        c.exists(p_md)
        c.kind(p_md, "health")
        c.contains(p_md, r"01\s+Intake|suggest", "reports stage rollout from aiwerk.md")
        c.contains(p_md, r"fresh|stale", "reports brain freshness")
        c.contains(p_md, r"github|not-asked", "reports connector coverage from landscape.md")
        c.exists(p_html)
        c.contains(p_html, r"<!doctype\s+html|<html\b", "writes valid HTML structure")
        c.contains(p_html, r"Generated by AI Werk Skills", "includes quiet AI Werk Skills footer")
        c.not_contains(p_html, r"https?://", "health.html makes no external URL requests")
        c.not_contains(p_html, r"<script\b", "health.html contains no scripts")
        c.no_canary()
        c.brain_valid()
        c.only_brain_changed()
    elif name == "skill-audit":
        mode = os.environ.get("AIWERK_SKILLSPECTOR_MODE", "")
        has_ss = True if mode == "installed" else False if mode == "missing" else (shutil.which("skillspector") is not None)
        if has_ss:
            p = b + "skill-audit.md"
            c.exists(p)
            c.kind(p, "skill-audit")
            c.contains(p, r"example-helper", "audits third-party installed skills, not only aiwerk skills")
            c.contains(p, r"aiwerk-", "audits installed aiwerk skills")
            c.contains(p, r"\b(SAFE|CAUTION|UNSAFE)\b", "records SkillSpector verdicts")
            c.no_canary()
            c.brain_valid()
            c.only_brain_changed()
        else:
            c.add("explains how to install SkillSpector",
                  re.search(r"skillspector", output, re.I) and re.search(r"pipx|uv|github\.com/NVIDIA/skillspector", output, re.I))
            after = tree_hash(os.path.join(project, ".aiwerk"))
            c.add("stops without changing brain when SkillSpector is missing", after == before_hash)
            c.no_canary()
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
