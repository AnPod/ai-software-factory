"""Self-test for evals/run_evals.py: a fake agent must pass every case, a misbehaving one must fail."""

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


def run(mode, extra_args=(), skillspector_mode="installed"):
    env = dict(os.environ, FAKE_AGENT_MODE=mode, AIWERK_SKILLSPECTOR_MODE=skillspector_mode)
    env.pop("GITHUB_STEP_SUMMARY", None)
    r = subprocess.run([sys.executable, RUNNER, "--agent-cmd", FAKE] + list(extra_args), cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=300)
    with open(os.path.join(ROOT, "evals", "results", "results.json"), encoding="utf-8") as fh:
        return r, json.load(fh)


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


if __name__ == "__main__":
    unittest.main()
