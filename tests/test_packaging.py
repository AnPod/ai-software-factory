"""Tests for Claude Code plugin/marketplace manifests and GitHub Actions recipes."""

import json
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class PackagingTest(unittest.TestCase):
    def test_claude_plugin_manifests(self):
        plugin_path = os.path.join(ROOT, ".claude-plugin", "plugin.json")
        market_path = os.path.join(ROOT, ".claude-plugin", "marketplace.json")
        self.assertTrue(os.path.isfile(plugin_path))
        self.assertTrue(os.path.isfile(market_path))

        with open(plugin_path, encoding="utf-8") as fh:
            plugin = json.load(fh)
        with open(market_path, encoding="utf-8") as fh:
            market = json.load(fh)

        self.assertEqual(plugin["name"], "aiwerk-skills")
        self.assertEqual(plugin["license"], "Apache-2.0")
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")

        self.assertEqual(market["name"], "aiwerk-skills")
        self.assertIsInstance(market["plugins"], list)
        self.assertGreaterEqual(len(market["plugins"]), 1)
        entry = market["plugins"][0]
        self.assertEqual(entry["name"], plugin["name"])
        self.assertEqual(entry["version"], plugin["version"])
        self.assertNotIn("..", entry["source"])
        self.assertTrue(os.path.isdir(os.path.join(ROOT, entry["source"], "skills")))

    def test_github_actions_recipes(self):
        recipes_dir = os.path.join(ROOT, "recipes", "github-actions")
        expected = ("issue-intake-and-spec.yml", "pr-governance-gates.yml")
        self.assertTrue(os.path.isfile(os.path.join(recipes_dir, "README.md")))
        for name in expected:
            path = os.path.join(recipes_dir, name)
            self.assertTrue(os.path.isfile(path), "missing recipe " + name)
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            self.assertIn("copilot ", text)
            self.assertIn("claude -p", text)
            self.assertIn("contents: read", text)
            self.assertIn("--allow-tool=write", text)
            self.assertIn("--deny-tool=shell(git push)", text)
            self.assertIn("--allowedTools", text)
            self.assertIn("--permission-mode acceptEdits", text)
            self.assertNotRegex(text, r"dangerously-skip-permissions|--allow-all|--yolo")
            self.assertNotIn("\u2014", text)

        with open(os.path.join(recipes_dir, "issue-intake-and-spec.yml"), encoding="utf-8") as fh:
            issue_wf = fh.read()
        self.assertIn("types: [labeled]", issue_wf)
        self.assertNotRegex(issue_wf, r"run:.*\$\{\{\s*github\.event\.issue\.body")

        with open(os.path.join(recipes_dir, "pr-governance-gates.yml"), encoding="utf-8") as fh:
            pr_wf = fh.read()
        self.assertIn("pull_request:", pr_wf)
        self.assertIn("head.repo.full_name == github.repository", pr_wf)

    def test_recipes_limit_what_the_agent_can_do(self):
        recipes_dir = os.path.join(ROOT, "recipes", "github-actions")
        for name in ("issue-intake-and-spec.yml", "pr-governance-gates.yml"):
            with open(os.path.join(recipes_dir, name), encoding="utf-8") as fh:
                text = fh.read()
            # No allow rule for interpreters, project code or blanket git.
            self.assertNotRegex(
                text,
                r"(--allow-tool=shell|\"Bash)\((python3?|node|git|command|find|cp|cat|head|pytest|make)(:\*)?\)",
                name + " allows a command that can run arbitrary code",
            )
            self.assertNotIn("Bash(python3:*)", text)
            # Every checkout keeps no credentials on disk.
            self.assertEqual(
                text.count("uses: actions/checkout@"), text.count("persist-credentials: false"), name
            )
            # Secrets only appear as step env values, never in an if: condition.
            for line in text.splitlines():
                if "secrets." in line:
                    self.assertRegex(line, r"^\s+[A-Z_]+: \$\{\{ secrets\.[A-Z_]+( != '')? \}\}$", name + ": " + line)
            self.assertIn("needs: gate", text)
            self.assertRegex(text, r'AIWERK_REF: "[0-9a-f]{40}"', name + " should pin AIWERK_REF to a commit")
            self.assertIn('grep -rqF -- "$KEY" .aiwerk/', text)

        with open(os.path.join(recipes_dir, "issue-intake-and-spec.yml"), encoding="utf-8") as fh:
            issue_wf = fh.read()
        self.assertIn("github.event.issue.author_association", issue_wf)

        with open(os.path.join(recipes_dir, "pr-governance-gates.yml"), encoding="utf-8") as fh:
            pr_wf = fh.read()
        checks_job = pr_wf.split("\n  checks:\n", 1)[1].split("\n  copilot:\n", 1)[0]
        self.assertIn("TEST_COMMAND", checks_job)
        self.assertNotIn("secrets.", checks_job)

    def test_skillspector_scan_has_no_write_token(self):
        with open(os.path.join(ROOT, ".github", "workflows", "skillspector.yml"), encoding="utf-8") as fh:
            text = fh.read()
        scan_job = text.split("\n  scan:\n", 1)[1].split("\n  sarif:\n", 1)[0]
        self.assertNotRegex(scan_job, r"^\s+[a-z-]+: write\b", "the scan job must not get a write permission")
        self.assertRegex(text, r"(?m)^permissions:\n  contents: read$")
        self.assertIn("persist-credentials: false", scan_job)
        self.assertRegex(text, r"SKILLSPECTOR_SHA: [0-9a-f]{40}")
        self.assertIn("skillspector.git@${SKILLSPECTOR_SHA}", scan_job)
        self.assertNotRegex(text, r"run:.*\$\{\{")


if __name__ == "__main__":
    unittest.main()
