"""Unit tests for scripts/check_changelog.py."""

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "check_changelog.py")
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import check_changelog as cc

BASE = "# Changelog\n\n## [Unreleased]\n\n### Added\n\n- One.\n\n## [1.0.0] - 2026-01-01\n\n- Old.\n"
WITH_ENTRY = BASE.replace("- One.\n", "- One.\n- Two.\n")
WHITESPACE = BASE.replace("- One.\n", "-   One.  \n\n\n")
SKILL = ["skills/aiwerk-review/SKILL.md"]


class ExtractTest(unittest.TestCase):
    def test_section_stops_at_next_release(self):
        section = cc.extract_unreleased(BASE)
        self.assertIn("- One.", section)
        self.assertNotIn("Old", section)

    def test_missing_section(self):
        self.assertIsNone(cc.extract_unreleased("# Changelog\n\n## [1.0.0]\n"))
        self.assertIsNone(cc.extract_unreleased(None))

    def test_crlf_text(self):
        section = cc.extract_unreleased(BASE.replace("\n", "\r\n"))
        self.assertIn("- One.", section)
        self.assertNotIn("Old", section)

    def test_section_at_end_of_file(self):
        self.assertIn("- Last.", cc.extract_unreleased("## [Unreleased]\n\n- Last.\n"))


class PathsAndLabelsTest(unittest.TestCase):
    def test_touches_skills(self):
        self.assertTrue(cc.touches_skills(["README.md", "skills/a/x.md"]))
        self.assertFalse(cc.touches_skills(["README.md", "tests/skills/a.py", "myskills/x"]))
        self.assertFalse(cc.touches_skills([]))

    def test_parse_labels(self):
        self.assertEqual(cc.parse_labels('["a", "no-changelog"]'), ["a", "no-changelog"])
        self.assertEqual(cc.parse_labels("a, no-changelog"), ["a", "no-changelog"])
        self.assertEqual(cc.parse_labels(""), [])
        self.assertEqual(cc.parse_labels("[]"), [])
        self.assertEqual(cc.parse_labels(None), [])


class EvaluateTest(unittest.TestCase):
    def test_no_skills_change_passes(self):
        ok, _ = cc.evaluate(["README.md"], BASE, BASE, [])
        self.assertTrue(ok)

    def test_skills_change_without_entry_fails(self):
        ok, msg = cc.evaluate(SKILL, BASE, BASE, [])
        self.assertFalse(ok)
        self.assertIn("no-changelog", msg)

    def test_skills_change_with_entry_passes(self):
        ok, _ = cc.evaluate(SKILL, BASE, WITH_ENTRY, [])
        self.assertTrue(ok)

    def test_label_passes_with_notice(self):
        ok, msg = cc.evaluate(SKILL, BASE, BASE, ["no-changelog"])
        self.assertTrue(ok)
        self.assertIn("Notice", msg)

    def test_whitespace_only_change_fails(self):
        ok, _ = cc.evaluate(SKILL, BASE, WHITESPACE, [])
        self.assertFalse(ok)

    def test_release_section_change_does_not_count(self):
        ok, _ = cc.evaluate(SKILL, BASE, BASE.replace("- Old.", "- Older."), [])
        self.assertFalse(ok)

    def test_missing_section_in_head_fails(self):
        ok, msg = cc.evaluate(SKILL, BASE, "# Changelog\n", [])
        self.assertFalse(ok)
        self.assertIn("no '## [Unreleased]'", msg)

    def test_missing_section_in_base_with_entry_passes(self):
        ok, _ = cc.evaluate(SKILL, "# Changelog\n", BASE, [])
        self.assertTrue(ok)

    def test_changelog_missing_in_base_and_head_fails(self):
        ok, _ = cc.evaluate(SKILL, None, None, [])
        self.assertFalse(ok)

    def test_label_is_case_insensitive(self):
        ok, _ = cc.evaluate(SKILL, BASE, BASE, ["No-Changelog"])
        self.assertTrue(ok)

    def test_deleted_skill_path_counts(self):
        ok, _ = cc.evaluate(["skills/aiwerk-old/SKILL.md"], BASE, BASE, [])
        self.assertFalse(ok)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        self.git("init", "-q", "-b", "main")
        self.write("CHANGELOG.md", BASE)
        self.write("skills/aiwerk-x/SKILL.md", "one\n")
        self.git("add", "-A")
        self.commit("base")
        self.git("tag", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", self.repo] + list(args), check=True, capture_output=True)

    def commit(self, msg):
        self.git("-c", "user.name=t", "-c", "user.email=t@example.com",
                 "-c", "commit.gpgsign=false", "commit", "-q", "-m", msg)

    def write(self, rel, text):
        path = os.path.join(self.repo, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_cli(self, labels="", extra_env=None):
        env = dict(os.environ, CHANGELOG_LABELS=labels)
        env.update(extra_env or {})
        return subprocess.run([sys.executable, "-I", SCRIPT, "base", "HEAD"], cwd=self.repo,
                              env=env, capture_output=True, text=True)

    def test_failing_diff(self):
        self.write("skills/aiwerk-x/SKILL.md", "two\n")
        self.git("add", "-A")
        self.commit("change skill")
        result = self.run_cli()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unreleased", result.stderr)

    def test_failing_diff_passes_with_label(self):
        self.write("skills/aiwerk-x/SKILL.md", "two\n")
        self.git("add", "-A")
        self.commit("change skill")
        result = self.run_cli('["no-changelog"]')
        self.assertEqual(result.returncode, 0)
        self.assertIn("Notice", result.stdout)

    def test_passing_diff(self):
        self.write("skills/aiwerk-x/SKILL.md", "two\n")
        self.write("CHANGELOG.md", WITH_ENTRY)
        self.git("add", "-A")
        self.commit("change skill and changelog")
        self.assertEqual(self.run_cli().returncode, 0)

    def test_deleted_skill_fails(self):
        self.git("rm", "-q", "-r", "skills/aiwerk-x")
        self.commit("delete skill")
        self.assertEqual(self.run_cli().returncode, 1)

    def test_non_skill_change_passes(self):
        self.write("README.md", "hi\n")
        self.git("add", "-A")
        self.commit("docs")
        self.assertEqual(self.run_cli().returncode, 0)

    def test_non_ascii_skill_path_with_quotepath(self):
        self.write("skills/aiwerk-x/caf\u00e9.md", "x\n")
        self.git("add", "-A")
        self.commit("non-ascii skill file")
        quote = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.quotepath",
                 "GIT_CONFIG_VALUE_0": "true"}
        self.assertEqual(self.run_cli(extra_env=quote).returncode, 1)

    def test_base_moved_on_with_unrelated_changelog_entry(self):
        self.git("checkout", "-q", "-b", "feature")
        self.write("skills/aiwerk-x/SKILL.md", "two\n")
        self.git("add", "-A")
        self.commit("change skill")
        self.git("checkout", "-q", "main")
        self.write("CHANGELOG.md", WITH_ENTRY)
        self.git("add", "-A")
        self.commit("unrelated entry on main")
        self.git("checkout", "-q", "feature")
        result = subprocess.run([sys.executable, "-I", SCRIPT, "main", "feature"], cwd=self.repo,
                                env=dict(os.environ, CHANGELOG_LABELS=""),
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)

    def test_renamed_skill_file_fails(self):
        self.git("mv", "skills/aiwerk-x/SKILL.md", "docs-moved.md")
        self.commit("move skill file out of skills/")
        self.assertEqual(self.run_cli().returncode, 1)

    def test_malformed_label_json_does_not_skip(self):
        self.write("skills/aiwerk-x/SKILL.md", "two\n")
        self.git("add", "-A")
        self.commit("change skill")
        self.assertEqual(self.run_cli("[bad").returncode, 1)

    def test_main_usage_error(self):
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(cc.main([], {}), 2)


if __name__ == "__main__":
    unittest.main()
