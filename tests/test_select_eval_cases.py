"""Unit tests for evals/select_eval_cases.py."""

import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from evals.run_evals import CASES
from evals import select_eval_cases as sec

ALL_ORDERED = list(CASES.keys())
SMOKE = ["init", "review", "skill-audit"]


class CasesFromChangedFilesTest(unittest.TestCase):
    def test_single_skill_change(self):
        cases, mode, _ = sec.cases_from_changed_files(["skills/aiwerk-review/SKILL.md"])
        self.assertEqual(cases, ["review"])
        self.assertEqual(mode, "changed")

    def test_two_skills_in_cases_order(self):
        cases, _, _ = sec.cases_from_changed_files([
            "skills/aiwerk-survey/foo.md",
            "skills/aiwerk-init/bar.md",
        ])
        self.assertEqual(cases, ["init", "survey"])

    def test_infra_run_evals_smoke(self):
        cases, mode, _ = sec.cases_from_changed_files(["evals/run_evals.py"])
        self.assertEqual(cases, SMOKE)
        self.assertEqual(mode, "smoke")

    def test_infra_fixture_smoke(self):
        cases, _, _ = sec.cases_from_changed_files(["evals/fixtures/tinyshop/README.md"])
        self.assertEqual(cases, SMOKE)

    def test_infra_install_sh(self):
        cases, _, _ = sec.cases_from_changed_files(["install.sh"])
        self.assertEqual(cases, SMOKE)

    def test_infra_workflow(self):
        cases, _, _ = sec.cases_from_changed_files([".github/workflows/evals.yml"])
        self.assertEqual(cases, SMOKE)

    def test_infra_selector_script(self):
        cases, _, _ = sec.cases_from_changed_files(["evals/select_eval_cases.py"])
        self.assertEqual(cases, SMOKE)

    def test_shared_brain_files_select_smoke_and_union_other_skills(self):
        for path in (
            "skills/aiwerk-init/assets/brain/SCHEMA.md",
            "skills/aiwerk-refresh/scripts/brain_status.py",
        ):
            with self.subTest(path=path):
                cases, mode, _ = sec.cases_from_changed_files([path])
                self.assertEqual((cases, mode), (SMOKE, "smoke"))
                cases, mode, _ = sec.cases_from_changed_files([
                    path, "skills/aiwerk-plan/SKILL.md",
                ])
                self.assertEqual((cases, mode), (
                    ["init", "plan", "review", "skill-audit"], "smoke"
                ))

    def test_other_init_and_refresh_files_select_only_their_skill(self):
        for path, expected in (
            ("skills/aiwerk-init/SKILL.md", "init"),
            ("skills/aiwerk-init/assets/brainstorm.md", "init"),
            ("skills/aiwerk-refresh/SKILL.md", "refresh"),
            ("skills/aiwerk-refresh/scripts/other.py", "refresh"),
        ):
            with self.subTest(path=path):
                cases, mode, _ = sec.cases_from_changed_files([path])
                self.assertEqual((cases, mode), ([expected], "changed"))

    def test_infra_plus_skill_unions(self):
        cases, mode, _ = sec.cases_from_changed_files([
            "evals/run_evals.py",
            "skills/aiwerk-plan/x.md",
        ])
        self.assertEqual(mode, "smoke")
        self.assertEqual(cases, ["init", "plan", "review", "skill-audit"])

    def test_unrelated_selects_nothing(self):
        cases, mode, _ = sec.cases_from_changed_files([
            "README.md",
            "tests/test_foo.py",
            "skills/README.md",
        ])
        self.assertEqual(cases, [])
        self.assertEqual(mode, "skip")

    def test_unknown_skill_dir_selects_nothing_for_that_path(self):
        cases, mode, _ = sec.cases_from_changed_files(["skills/aiwerk-unknown/foo.md"])
        self.assertEqual(cases, [])
        self.assertEqual(mode, "skip")

    def test_mixed_unknown_skill_and_unrelated(self):
        cases, _, _ = sec.cases_from_changed_files([
            "docs/foo.md",
            "skills/aiwerk-not-a-case/x",
        ])
        self.assertEqual(cases, [])


class SelectForEventTest(unittest.TestCase):
    def test_schedule_all_cases(self):
        cases, mode, _ = sec.select_cases_for_event("schedule", [], "")
        self.assertEqual(cases, ALL_ORDERED)
        self.assertEqual(mode, "all")

    def test_dispatch_empty_all_cases(self):
        cases, mode, _ = sec.select_cases_for_event("workflow_dispatch", [], "")
        self.assertEqual(cases, ALL_ORDERED)
        self.assertEqual(mode, "all")

    def test_dispatch_explicit(self):
        cases, mode, _ = sec.select_cases_for_event(
            "workflow_dispatch", [], "survey,init"
        )
        self.assertEqual(cases, ["init", "survey"])
        self.assertEqual(mode, "dispatch")

    def test_dispatch_unknown_raises(self):
        with self.assertRaises(sec.SelectError):
            sec.select_cases_for_event("workflow_dispatch", [], "nosuch")

    def test_push_changed_files(self):
        cases, mode, _ = sec.select_cases_for_event(
            "push", ["skills/aiwerk-health/a.md"], ""
        )
        self.assertEqual(cases, ["health"])
        self.assertEqual(mode, "changed")

    def test_pull_request_changed_files(self):
        cases, _, _ = sec.select_cases_for_event(
            "pull_request", ["skills/aiwerk-intake/x"], ""
        )
        self.assertEqual(cases, ["intake"])


class GitChangedFilesTest(unittest.TestCase):
    def test_pr_style_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            p = os.path.join(tmp, "skills", "aiwerk-review")
            os.makedirs(p)
            with open(os.path.join(p, "a.txt"), "w") as fh:
                fh.write("1")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            base = subprocess.run(
                ["git", "commit", "-m", "base"], cwd=tmp, check=True, capture_output=True, text=True
            )
            base_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            with open(os.path.join(p, "a.txt"), "w") as fh:
                fh.write("2")
            subprocess.run(["git", "commit", "-am", "head"], cwd=tmp, check=True, capture_output=True)
            head_sha = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            files = sec.git_diff_name_only(tmp, f"{base_sha}...{head_sha}")
            self.assertIn("skills/aiwerk-review/a.txt", files)

    def test_zero_before_lists_full_tree_at_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            p = os.path.join(tmp, "skills", "aiwerk-survey")
            os.makedirs(p)
            with open(os.path.join(p, "x"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "m"], cwd=tmp, check=True, capture_output=True)
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            cases, mode, _ = sec.select_push_cases(
                tmp, before_sha=sec.ZERO_SHA, after_sha=after, default_branch="main"
            )
            self.assertEqual(cases, ["survey"])
            self.assertEqual(mode, "changed")

    def test_zero_before_when_default_tip_equals_after(self):
        """Zero before on a first push: full tree at after must select skills, not skip."""
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            p = os.path.join(tmp, "skills", "aiwerk-review")
            os.makedirs(p)
            with open(os.path.join(p, "SKILL.md"), "w") as fh:
                fh.write("skill")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "initial"], cwd=tmp, check=True, capture_output=True)
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            cases, mode, _ = sec.select_push_cases(tmp, sec.ZERO_SHA, after, "main")
            self.assertIn("review", cases)
            self.assertNotEqual(mode, "skip")
            self.assertTrue(cases)

    def test_force_push_rewind_selects_after_to_before_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            survey = os.path.join(tmp, "skills", "aiwerk-survey")
            review = os.path.join(tmp, "skills", "aiwerk-review")
            os.makedirs(survey)
            os.makedirs(review)
            with open(os.path.join(survey, "a.txt"), "w") as fh:
                fh.write("1")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=tmp, check=True, capture_output=True)
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            with open(os.path.join(review, "b.txt"), "w") as fh:
                fh.write("2")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "ahead"], cwd=tmp, check=True, capture_output=True)
            before = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            cases, mode, _ = sec.select_push_cases(tmp, before, after, "main")
            self.assertIn("review", cases)
            self.assertNotEqual(cases, [])
            self.assertNotEqual(mode, "skip")

    def test_unreachable_before_returns_smoke_not_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            with open(os.path.join(tmp, "README.md"), "w") as fh:
                fh.write("r")
            subprocess.run(["git", "add", "README.md"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "c1"], cwd=tmp, check=True, capture_output=True)
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            before = "a" * 40
            cases, mode, _ = sec.select_push_cases(tmp, before, after, "main")
            self.assertEqual(cases, SMOKE)
            self.assertEqual(mode, "smoke")

    def test_git_diff_failure_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(sec.SelectError):
                sec.git_diff_name_only(tmp, "notasha...noteither")

    def test_zero_before_non_skill_tree_skips(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "feat"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            with open(os.path.join(tmp, "only.txt"), "w") as fh:
                fh.write("x")
            subprocess.run(["git", "add", "only.txt"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "solo"], cwd=tmp, check=True, capture_output=True)
            after = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            cases, mode, _ = sec.select_push_cases(tmp, sec.ZERO_SHA, after, "main")
            self.assertEqual(cases, [])
            self.assertEqual(mode, "skip")

    def test_invalid_after_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            with self.assertRaises(sec.SelectError):
                sec.resolve_push_changed_files(tmp, sec.ZERO_SHA, "b" * 40, "main")

    def test_non_ascii_path_in_diff(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["git", "init", "-b", "main"], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=tmp, check=True)
            subprocess.run(["git", "config", "user.name", "T"], cwd=tmp, check=True)
            subprocess.run(
                ["git", "config", "core.quotePath", "true"], cwd=tmp, check=True, capture_output=True
            )
            p = os.path.join(tmp, "skills", "aiwerk-plan")
            os.makedirs(p)
            u_name = "caf\u00e9.txt"
            with open(os.path.join(p, u_name), "w") as fh:
                fh.write("1")
            subprocess.run(["git", "add", "."], cwd=tmp, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "base"], cwd=tmp, check=True, capture_output=True)
            base = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            with open(os.path.join(p, u_name), "w") as fh:
                fh.write("2")
            subprocess.run(["git", "commit", "-am", "head"], cwd=tmp, check=True, capture_output=True)
            head = subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=tmp, check=True, capture_output=True, text=True
            ).stdout.strip()
            files = sec.git_diff_name_only(tmp, "%s..%s" % (base, head))
            expected = "skills/aiwerk-plan/%s" % u_name
            self.assertIn(expected, files)
            cases, _, _ = sec.cases_from_changed_files(files)
            self.assertEqual(cases, ["plan"])

    def test_split_nul_paths_parses_git_z_output(self):
        u_name = "caf\u00e9.txt"
        raw = ("skills/aiwerk-init/a.txt\0skills/aiwerk-plan/%s\0" % u_name).encode("utf-8")
        paths = sec._split_nul_paths(raw)
        self.assertEqual(len(paths), 2)
        self.assertTrue(paths[1].endswith(u_name))


class GitHubOutputTest(unittest.TestCase):
    def test_write_output_for_selection(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            out_path = fh.name
        prev = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = out_path
        try:
            sec.write_github_output(["init", "review"])
            with open(out_path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("run=true\n", body)
            self.assertIn("cases=init,review\n", body)
        finally:
            if prev is None:
                os.environ.pop("GITHUB_OUTPUT", None)
            else:
                os.environ["GITHUB_OUTPUT"] = prev
            os.unlink(out_path)

    def test_write_output_for_skip(self):
        with tempfile.NamedTemporaryFile("w", delete=False) as fh:
            out_path = fh.name
        prev = os.environ.get("GITHUB_OUTPUT")
        os.environ["GITHUB_OUTPUT"] = out_path
        try:
            sec.write_github_output([])
            with open(out_path, encoding="utf-8") as fh:
                body = fh.read()
            self.assertIn("run=false\n", body)
            self.assertIn("cases=\n", body)
        finally:
            if prev is None:
                os.environ.pop("GITHUB_OUTPUT", None)
            else:
                os.environ["GITHUB_OUTPUT"] = prev
            os.unlink(out_path)


class CliTest(unittest.TestCase):
    def test_cli_changed_files_flag(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".lst") as fh:
            fh.write("skills/aiwerk-review/SKILL.md\n")
            path = fh.name
        try:
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "evals", "select_eval_cases.py"),
                 "--event", "push", "--changed-files", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Selected cases: review", r.stdout)
        finally:
            os.unlink(path)

    def test_cli_skip_prints_none(self):
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".lst") as fh:
            fh.write("README.md\n")
            path = fh.name
        try:
            r = subprocess.run(
                [sys.executable, os.path.join(ROOT, "evals", "select_eval_cases.py"),
                 "--event", "pull_request", "--changed-files", path],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(r.returncode, 0)
            self.assertIn("Selected cases: (none)", r.stdout)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
