"""Self-test for evals/run_evals.py: a fake agent must pass every case, a misbehaving one must fail."""

import importlib.util
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "evals", "run_evals.py")
FAKE = "%s %s" % (sys.executable, os.path.join(ROOT, "tests", "fake_agent.py"))

EXPECTED_CASES = {
    "init", "landscape", "survey", "refresh",
    "readiness", "intake", "spec", "context",
    "plan", "dispatch", "sandbox",
    "review", "test-gate", "security-gate", "policy",
    "release", "deploy-check", "docs-sync",
    "incident", "incident-to-spec", "slo",
    "health", "skill-audit",
}


def run(mode, extra_args=(), skillspector_mode="installed", agent_cmd=None, env_extra=None):
    env = dict(os.environ, AIWERK_FAKE_AGENT_MODE=mode, AIWERK_SKILLSPECTOR_MODE=skillspector_mode)
    env.pop("GITHUB_STEP_SUMMARY", None)
    if env_extra:
        env.update(env_extra)
    cmd = agent_cmd or FAKE
    r = subprocess.run([sys.executable, RUNNER, "--agent-cmd", cmd] + list(extra_args), cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=300)
    with open(os.path.join(ROOT, "evals", "results", "results.json"), encoding="utf-8") as fh:
        return r, json.load(fh)


def load_run_evals():
    spec = importlib.util.spec_from_file_location("run_evals", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TOKEN_SHAPED = {
    "ghp": "ghp_" + "A" * 36,
    "github_pat": "github_pat_" + "B" * 40,
    "sk_ant": "sk-ant-" + "C" * 24,
}


class EvalRunnerTest(unittest.TestCase):
    def test_good_agent_passes_all_cases(self):
        r, data = run("good")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual({x["case"] for x in data["results"]}, EXPECTED_CASES)

    def test_bad_agent_is_caught(self):
        r, data = run("bad")
        self.assertEqual(r.returncode, 1)
        failed = {x["case"]: [c["check"] for c in x["checks"] if not c["ok"]] for x in data["results"]}
        self.assertIn("writes nothing outside .aiwerk/", failed["init"])
        self.assertIn("does not copy secrets from MCP config", failed["landscape"])
        self.assertIn("report-only mode changes no pages", failed["refresh"])
        self.assertIn("includes a 0 to 100 readiness score", failed["readiness"])
        self.assertIn("does not copy secrets from MCP config", failed["intake"])
        self.assertIn("names affected module cart.py", failed["spec"])
        self.assertIn("stays within 25-entry budget", failed["context"])
        self.assertIn("records dependency order", failed["plan"])
        self.assertIn("avoids broad permission flags", failed["dispatch"])
        self.assertIn("writes nothing outside .aiwerk/", failed["sandbox"])
        self.assertIn("assigns a review verdict", failed["review"])
        self.assertIn("writes nothing outside .aiwerk/", failed["test-gate"])
        self.assertIn("does not copy secrets from MCP config", failed["security-gate"])
        self.assertIn("writes .aiwerk/brain/policies/index.md", failed["policy"])
        self.assertIn("suggests a minor semver bump", failed["release"])
        self.assertIn("defines a rollback trigger and plan", failed["deploy-check"])
        self.assertIn("writes only to .aiwerk/ and allowed docs", failed["docs-sync"])
        self.assertIn("does not copy secrets from MCP config", failed["incident"])
        self.assertIn("links back to the resolved incident", failed["incident-to-spec"])
        self.assertIn("reports missing live telemetry honestly", failed["slo"])
        self.assertIn("health.html makes no external URL requests", failed["health"])
        self.assertIn("audits third-party installed skills, not only aiwerk skills", failed["skill-audit"])

    def test_skill_audit_missing_mode(self):
        r, data = run("good", extra_args=("--cases", "skill-audit"), skillspector_mode="missing")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual([x["case"] for x in data["results"]], ["skill-audit"])

        r_bad, data_bad = run("bad", extra_args=("--cases", "skill-audit"), skillspector_mode="missing")
        self.assertEqual(r_bad.returncode, 1)
        failed = [c["check"] for c in data_bad["results"][0]["checks"] if not c["ok"]]
        self.assertIn("stops without changing brain when SkillSpector is missing", failed)


class DiagnosticSanitizeTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_run_evals()

    def test_sanitize_redacts_env_secrets_and_token_shapes(self):
        copilot = "copilot-secret-" + "x" * 20
        anthropic = "anthropic-secret-" + "y" * 20
        msg = (
            "auth failed copilot=%s anthropic=%s tokens %s %s %s"
            % (copilot, anthropic, TOKEN_SHAPED["ghp"], TOKEN_SHAPED["github_pat"], TOKEN_SHAPED["sk_ant"])
        )
        old = dict(os.environ)
        try:
            os.environ["COPILOT_GITHUB_TOKEN"] = copilot
            os.environ["ANTHROPIC_API_KEY"] = anthropic
            out = self.mod.sanitize_diagnostic(msg)
        finally:
            os.environ.clear()
            os.environ.update(old)
        self.assertNotIn(copilot, out)
        self.assertNotIn(anthropic, out)
        for tok in TOKEN_SHAPED.values():
            self.assertNotIn(tok, out)
        self.assertIn("[redacted]", out)
        self.assertIn("[redacted-token]", out)
        self.assertNotIn("\n", out)

    def test_sanitize_bounds_tail(self):
        long_line = "x" * 400
        out = self.mod.sanitize_diagnostic(long_line)
        self.assertLessEqual(len(out), 300)
        self.assertTrue(out.endswith("x" * 300))


class FailedAgentDiagnosticTest(unittest.TestCase):
    def test_nonzero_agent_reports_sanitized_detail_without_leaks(self):
        copilot = "copilot-eval-" + "z" * 24
        anthropic = "anthropic-eval-" + "w" * 24
        shaped = TOKEN_SHAPED["ghp"]
        err = "agent boom key=%s also %s token %s\nmore\nlines" % (copilot, anthropic, shaped)
        agent_cmd = "%s -c \"import sys; sys.stderr.write(%r); sys.exit(1)\"" % (sys.executable, err)
        env_extra = {
            "COPILOT_GITHUB_TOKEN": copilot,
            "ANTHROPIC_API_KEY": anthropic,
            "AIWERK_FAKE_AGENT_MODE": "",
        }
        r, data = run(
            "good",
            extra_args=("--cases", "init"),
            agent_cmd=agent_cmd,
            env_extra=env_extra,
        )
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        case = data["results"][0]
        self.assertFalse(case["passed"])
        exit_check = case["checks"][0]
        self.assertEqual(exit_check["check"], "agent exits cleanly")
        self.assertFalse(exit_check["ok"])
        self.assertIn("exit 1:", exit_check["detail"])
        self.assertIn("[redacted]", exit_check["detail"])
        self.assertIn("[redacted-token]", exit_check["detail"])
        self.assertIn("agent exits cleanly", r.stdout)
        self.assertIn("exit 1:", r.stdout)

        results_path = os.path.join(ROOT, "evals", "results", "results.json")
        summary_path = os.path.join(ROOT, "evals", "results", "summary.md")
        blob = r.stdout + r.stderr
        with open(results_path, encoding="utf-8") as fh:
            blob += fh.read()
        with open(summary_path, encoding="utf-8") as fh:
            blob += fh.read()
        for secret in (copilot, anthropic, shaped):
            self.assertNotIn(secret, blob)

        with open(
            os.path.join(ROOT, "evals", "results", "transcripts", "init.txt"), encoding="utf-8"
        ) as fh:
            transcript = fh.read()
        self.assertIn(copilot, transcript)
        self.assertIn(shaped, transcript)


class AgentLimitsTest(unittest.TestCase):
    def setUp(self):
        self.mod = load_run_evals()

    def test_agent_env_drops_secrets_and_runner_files(self):
        fake = {"PATH": "/usr/bin", "HOME": "/home/x", "GITHUB_ENV": "/tmp/env", "GITHUB_OUTPUT": "/tmp/out",
                "OTHER_SECRET": "s", "ANTHROPIC_API_KEY": "a", "COPILOT_GITHUB_TOKEN": "c", "AIWERK_X": "1"}
        old = dict(os.environ)
        try:
            os.environ.clear()
            os.environ.update(fake)
            copilot = self.mod.agent_env("copilot", "init")
            claude = self.mod.agent_env("claude", "init")
            custom = self.mod.agent_env("custom", "init")
        finally:
            os.environ.clear()
            os.environ.update(old)
        for env in (copilot, claude, custom):
            for k in ("GITHUB_ENV", "GITHUB_OUTPUT", "OTHER_SECRET"):
                self.assertNotIn(k, env)
            self.assertEqual(env["AIWERK_X"], "1")
            self.assertEqual(env["AIWERK_EVAL_CASE"], "init")
        self.assertIn("COPILOT_GITHUB_TOKEN", copilot)
        self.assertNotIn("ANTHROPIC_API_KEY", copilot)
        self.assertIn("ANTHROPIC_API_KEY", claude)
        self.assertNotIn("COPILOT_GITHUB_TOKEN", claude)
        self.assertNotIn("ANTHROPIC_API_KEY", custom)

    def test_no_interpreter_or_blanket_rules(self):
        allowed = " ".join(self.mod.CLAUDE_TOOLS + self.mod.COPILOT_TOOLS)
        for rule in ("Bash(git:*)", "shell(git:*)", "Bash(python3:*)", "shell(python3:*)", "shell(command:*)",
                     "Bash(cat:*)", "shell(cat:*)", "Bash(find:*)", "shell(find:*)", "Bash(cp:*)", "shell(cp:*)"):
            self.assertNotIn(rule, allowed)
        self.assertIn("write(.git/**)", self.mod.COPILOT_DENY)
        self.assertIn("Edit(.git/**)", self.mod.CLAUDE_DENY)


if __name__ == "__main__":
    unittest.main()
