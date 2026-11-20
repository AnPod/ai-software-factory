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
            self.assertIn('"--allow-tool=write(.aiwerk/brain/**)"', text)
            self.assertNotRegex(text, r"--allow-tool=write\s")
            self.assertIn("--deny-tool=shell(git push)", text)
            self.assertIn("--allowedTools", text)
            self.assertIn("--permission-mode dontAsk", text)
            self.assertIn('Skill "Edit(.aiwerk/brain/**)"', text)
            self.assertNotRegex(text, r"acceptEdits|\bRead Write Edit\b")
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
            self.assertIn('grep -rqF -- "$KEY" .aiwerk/; rc=$?', text)
            self.assertIn('[ "$rc" -ne 1 ]', text)
            # Upload only after the key check passed, and keep artifacts briefly.
            self.assertIn("steps.leak.outcome == 'success'", text)
            self.assertIn("retention-days: 7", text)
            # Agent configuration from the checkout is removed and runner file commands are unset.
            self.assertEqual(text.count("rm -rf .claude .agents .copilot .mcp.json"), 2, name)
            self.assertEqual(text.count("env -u GITHUB_ENV"), 2, name)
            self.assertIn("--setting-sources user --strict-mcp-config", text)
            self.assertIn('"Read(//proc/**)"', text)
            # Every action is pinned to a full commit SHA.
            self.assertNotRegex(text, r"uses: [^@\s]+@(?![0-9a-f]{40}\b)")

        with open(os.path.join(recipes_dir, "issue-intake-and-spec.yml"), encoding="utf-8") as fh:
            issue_wf = fh.read()
        self.assertIn("github.event.issue.author_association", issue_wf)

        with open(os.path.join(recipes_dir, "pr-governance-gates.yml"), encoding="utf-8") as fh:
            pr_wf = fh.read()
        checks_job = pr_wf.split("\n  checks:\n", 1)[1].split("\n  copilot:\n", 1)[0]
        self.assertIn("TEST_COMMAND", checks_job)
        self.assertNotIn("secrets.", checks_job)
        self.assertIn("Fail when tests or lint failed", checks_job)
        self.assertIn("--no-custom-instructions", pr_wf)
        # The gate summary only shows known verdict words.
        self.assertEqual(pr_wf.count('pass|"pass with fixes"|gaps|warn|needs-approval|fail)'), 2)

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
        self.assertIn("scripts/merge_sarif.py", scan_job)
        self.assertNotIn("continue-on-error", text)

    def test_workflows_pin_actions_and_guard_eval_uploads(self):
        wf_dir = os.path.join(ROOT, ".github", "workflows")
        for name in sorted(os.listdir(wf_dir)):
            with open(os.path.join(wf_dir, name), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotRegex(text, r"uses: [^@\s]+@(?![0-9a-f]{40}\b)", name + " has an action not pinned to a SHA")
            self.assertEqual(text.count("uses: actions/checkout@"), text.count("persist-credentials: false"), name)
        with open(os.path.join(wf_dir, "evals.yml"), encoding="utf-8") as fh:
            evals = fh.read()
        self.assertEqual(evals.count("steps.leak.outcome == 'success'"), 2)
        self.assertEqual(evals.count("retention-days: 7"), 2)
        self.assertNotIn("if: always()", evals)

    def test_recipes_use_the_same_action_commits_as_the_workflows(self):
        import glob
        pin = re.compile(r"uses: ([^@\s]+)@([0-9a-f]{40})")
        used = {}
        for path in glob.glob(os.path.join(ROOT, ".github", "workflows", "*.yml")):
            with open(path, encoding="utf-8") as fh:
                for action, sha in pin.findall(fh.read()):
                    used.setdefault(action, set()).add(sha)
        for action, shas in used.items():
            self.assertEqual(len(shas), 1, action + " is pinned to different commits across workflows")
        for path in glob.glob(os.path.join(ROOT, "recipes", "github-actions", "*.yml")):
            with open(path, encoding="utf-8") as fh:
                for action, sha in pin.findall(fh.read()):
                    if action in used:
                        self.assertIn(sha, used[action], "%s: %s differs from the workflows" % (os.path.basename(path), action))

    def test_skills_run_the_brain_checker_by_path(self):
        # Copilot CLI matches python3 by name only, so agents get a rule for this exact script path.
        script = os.path.join(ROOT, "skills", "aiwerk-refresh", "scripts", "brain_status.py")
        self.assertTrue(os.access(script, os.X_OK), "brain_status.py must stay executable")
        with open(script, encoding="utf-8") as fh:
            self.assertEqual(fh.readline().strip(), "#!/usr/bin/env python3")
        skills = os.path.join(ROOT, "skills")
        for name in sorted(os.listdir(skills)):
            with open(os.path.join(skills, name, "SKILL.md"), encoding="utf-8") as fh:
                text = fh.read()
            self.assertNotRegex(text, r"(?m)^python3 <", name + " should run brain_status.py by its path")


if __name__ == "__main__":
    unittest.main()
