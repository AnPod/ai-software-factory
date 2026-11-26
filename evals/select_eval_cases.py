#!/usr/bin/env python3
"""Choose which eval CASES keys to run in CI based on the GitHub event and changed paths.

Imports CASES from evals.run_evals so the case list cannot drift. On pull_request and push,
only skills whose tree changed run, plus a small smoke set when suite-wide files change.
A CASES key with no matching skills/aiwerk-<case>/ directory is never selected from a path
change; only schedule, empty workflow_dispatch, or an explicit dispatch list includes it.

Smoke set (init, review, skill-audit) runs when evals/run_evals.py, evals/fixtures/**,
install.sh, .github/workflows/evals.yml, or this script changes, union any skill cases from
the same diff. Otherwise a change only to this selector would trigger the workflow via the
evals/** path filter and then skip all agent runs.

Usage:
  python3 evals/select_eval_cases.py --event pull_request --base-sha ... --head-sha ...
  python3 evals/select_eval_cases.py --event push --changed-files paths.txt
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evals.run_evals import CASES

ALL_CASES_ORDER = list(CASES.keys())
SMOKE_CASES = ("init", "review", "skill-audit")
ZERO_SHA = "0" * 40

INFRA_EXACT = frozenset({
    "evals/run_evals.py",
    "install.sh",
    ".github/workflows/evals.yml",
    "evals/select_eval_cases.py",
})
INFRA_PREFIX = ("evals/fixtures/",)


class SelectError(Exception):
    pass


def normalize_path(path: str) -> str:
    p = path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def is_infra_path(path: str) -> bool:
    p = normalize_path(path)
    if p in INFRA_EXACT:
        return True
    return any(p.startswith(pref) for pref in INFRA_PREFIX)


def skill_case_from_path(path: str) -> str | None:
    p = normalize_path(path)
    prefix = "skills/aiwerk-"
    if not p.startswith(prefix):
        return None
    rest = p[len(prefix):]
    if not rest:
        return None
    case = rest.split("/", 1)[0]
    if case in CASES:
        return case
    return None


def order_cases(names) -> list[str]:
    want = set(names)
    return [k for k in ALL_CASES_ORDER if k in want]


def cases_from_changed_files(changed_files: list[str]) -> tuple[list[str], str, str]:
    skills: set[str] = set()
    infra = False
    for raw in changed_files:
        line = raw.strip()
        if not line:
            continue
        if is_infra_path(line):
            infra = True
            continue
        case = skill_case_from_path(line)
        if case:
            skills.add(case)
    if not skills and not infra:
        return [], "skip", "no skill or infra paths in the diff"
    if infra:
        selected = set(SMOKE_CASES) | skills
        reason = "infra paths changed (smoke set"
        if skills:
            reason += " union changed skills)"
        else:
            reason += ")"
        return order_cases(selected), "smoke", reason
    return order_cases(skills), "changed", "skill paths changed"


def parse_explicit_cases(raw: str) -> list[str]:
    names = [x.strip() for x in raw.split(",") if x.strip()]
    if not names:
        return []
    unknown = [n for n in names if n not in CASES]
    if unknown:
        raise SelectError("unknown case name(s): %s" % ", ".join(unknown))
    return order_cases(names)


def select_cases_for_event(
    event: str,
    changed_files: list[str],
    explicit_cases: str,
) -> tuple[list[str], str, str]:
    if event == "schedule":
        return ALL_CASES_ORDER, "all", "scheduled weekly run"
    if event == "workflow_dispatch":
        if explicit_cases and explicit_cases.strip():
            cases = parse_explicit_cases(explicit_cases)
            return cases, "dispatch", "workflow_dispatch cases input"
        return ALL_CASES_ORDER, "all", "workflow_dispatch with empty cases"
    if event in ("pull_request", "push"):
        return cases_from_changed_files(changed_files)
    raise SelectError("unsupported event: %s" % event)


def _split_nul_paths(stdout: bytes) -> list[str]:
    if not stdout:
        return []
    parts = stdout.split(b"\0")
    if parts and parts[-1] == b"":
        parts = parts[:-1]
    return [p.decode("utf-8", errors="surrogateescape") for p in parts if p]


def git_diff_name_only(repo_root: str, range_spec: str) -> list[str]:
    r = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "diff",
            "--name-only",
            "--no-renames",
            "-z",
            range_spec,
        ],
        cwd=repo_root,
        capture_output=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout).decode("utf-8", errors="replace").strip()
        raise SelectError("git diff failed for %s: %s" % (range_spec, err))
    return _split_nul_paths(r.stdout)


def git_ls_tree_name_only(repo_root: str, tree_ref: str) -> list[str]:
    r = subprocess.run(
        [
            "git",
            "-c",
            "core.quotePath=false",
            "ls-tree",
            "-r",
            "--name-only",
            "-z",
            tree_ref,
        ],
        cwd=repo_root,
        capture_output=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout).decode("utf-8", errors="replace").strip()
        raise SelectError("git ls-tree failed for %s: %s" % (tree_ref, err))
    return _split_nul_paths(r.stdout)


def git_rev_parse_verify(repo_root: str, ref: str) -> str:
    r = subprocess.run(
        ["git", "rev-parse", "--verify", ref],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout).strip()
        raise SelectError("cannot resolve git ref %s: %s" % (ref, err))
    return r.stdout.strip()


def _is_zero_or_missing(sha: str | None) -> bool:
    if not sha:
        return True
    return sha.strip() == ZERO_SHA


def git_merge_base(repo_root: str, ref_a: str, ref_b: str) -> str | None:
    r = subprocess.run(
        ["git", "merge-base", ref_a, ref_b],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return None
    out = r.stdout.strip()
    return out or None


def resolve_push_changed_files(
    repo_root: str,
    before_sha: str | None,
    after_sha: str,
    default_branch: str,
) -> list[str] | None:
    """Return changed paths for a push, or None when the diff cannot be computed (smoke fallback)."""
    git_rev_parse_verify(repo_root, after_sha)
    if _is_zero_or_missing(before_sha):
        return git_ls_tree_name_only(repo_root, after_sha)

    before = before_sha.strip()
    mb = git_merge_base(repo_root, before, after_sha)
    if not mb:
        return None
    if mb == after_sha:
        return git_diff_name_only(repo_root, "%s..%s" % (after_sha, before))
    return git_diff_name_only(repo_root, "%s..%s" % (mb, after_sha))


def select_push_cases(
    repo_root: str,
    before_sha: str | None,
    after_sha: str,
    default_branch: str,
) -> tuple[list[str], str, str]:
    files = resolve_push_changed_files(repo_root, before_sha, after_sha, default_branch)
    if files is None:
        reason = "push before SHA unreachable from after; using smoke set"
        print(reason, file=sys.stderr)
        return order_cases(SMOKE_CASES), "smoke", reason
    return cases_from_changed_files(files)


def load_changed_files_file(path: str) -> list[str]:
    with open(path, encoding="utf-8") as fh:
        return fh.read().splitlines()


def format_selected_log(cases: list[str]) -> str:
    if cases:
        return "Selected cases: %s" % ",".join(cases)
    return "Selected cases: (none)"


def write_github_output(cases: list[str]) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        return
    run = "true" if cases else "false"
    joined = ",".join(cases)
    with open(out_path, "a", encoding="utf-8") as fh:
        fh.write("run=%s\n" % run)
        fh.write("cases=%s\n" % joined)


def append_step_summary(cases: list[str], mode: str, reason: str) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as fh:
        fh.write("### Eval case selection\n")
        fh.write("- Mode: %s\n" % mode)
        fh.write("- Reason: %s\n" % reason)
        if cases:
            fh.write("- Cases: %s\n" % ", ".join(cases))
        else:
            fh.write("- Cases: (none, agent jobs skipped)\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Select eval cases for GitHub Actions")
    p.add_argument("--event", required=True)
    p.add_argument("--repo-root", default=ROOT)
    p.add_argument("--base-sha", default="")
    p.add_argument("--head-sha", default="")
    p.add_argument("--before-sha", default="")
    p.add_argument("--after-sha", default="")
    p.add_argument("--default-branch", default="main")
    p.add_argument("--explicit-cases", default="")
    p.add_argument("--changed-files", default="", help="File with one changed path per line (tests/local)")
    args = p.parse_args(argv)

    try:
        if args.changed_files:
            changed = load_changed_files_file(args.changed_files)
            cases, mode, reason = select_cases_for_event(args.event, changed, args.explicit_cases)
        elif args.event == "pull_request":
            if not args.base_sha or not args.head_sha:
                raise SelectError("pull_request needs --base-sha and --head-sha")
            changed = git_diff_name_only(args.repo_root, f"{args.base_sha}...{args.head_sha}")
            cases, mode, reason = select_cases_for_event(args.event, changed, args.explicit_cases)
        elif args.event == "push":
            if not args.after_sha:
                raise SelectError("push needs --after-sha")
            cases, mode, reason = select_push_cases(
                args.repo_root, args.before_sha or None, args.after_sha, args.default_branch
            )
        else:
            cases, mode, reason = select_cases_for_event(args.event, [], args.explicit_cases)
    except SelectError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(format_selected_log(cases))
    write_github_output(cases)
    append_step_summary(cases, mode, reason)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())