"""Unit tests for scripts/merge_sarif.py."""

import importlib.util
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
spec = importlib.util.spec_from_file_location("merge_sarif", os.path.join(ROOT, "scripts", "merge_sarif.py"))
ms = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ms)

WORK = "/work/repo"


def run(skill, results, rules=None):
    driver = {"name": "skillspector", "version": "1.0"}
    if rules:
        driver["rules"] = rules
    return {
        "tool": {"driver": driver},
        "results": results,
        "invocations": [{"executionSuccessful": True, "toolExecutionNotifications": [
            {"message": {"text": "note"}, "locations": [{"physicalLocation": {"artifactLocation": {"uri": "SKILL.md"}}}]}
        ]}],
        "originalUriBaseIds": {
            "SCANROOT": {"uri": "file://" + WORK + "/skills/"},
            "SKILLROOT": {"uri": skill + "/", "uriBaseId": "SCANROOT"},
        },
    }


def result(rule, uri="SKILL.md"):
    return {"ruleId": rule, "ruleIndex": 0, "message": {"text": rule},
            "locations": [{"physicalLocation": {"artifactLocation": {"uri": uri, "uriBaseId": "SKILLROOT"},
                                                "region": {"startLine": 1}}}]}


class MergeSarifTest(unittest.TestCase):
    def test_runs_become_one_with_repository_paths(self):
        sarif = {"version": "2.1.0", "runs": [
            run("aiwerk-a", [result("LP3")], rules=[{"id": "LP3"}]),
            run("aiwerk-b", [result("LP3", "scripts/x.py"), result("E1")], rules=[{"id": "LP3"}, {"id": "E1"}]),
        ]}
        out = ms.merge(sarif, WORK)
        self.assertEqual(out["version"], "2.1.0")
        self.assertEqual(len(out["runs"]), 1)
        merged = out["runs"][0]
        self.assertNotIn("originalUriBaseIds", merged)
        self.assertEqual([r["id"] for r in merged["tool"]["driver"]["rules"]], ["E1", "LP3"])
        uris = [r["locations"][0]["physicalLocation"]["artifactLocation"] for r in merged["results"]]
        self.assertEqual([u["uri"] for u in uris],
                         ["skills/aiwerk-a/SKILL.md", "skills/aiwerk-b/scripts/x.py", "skills/aiwerk-b/SKILL.md"])
        self.assertTrue(all("uriBaseId" not in u for u in uris))
        self.assertTrue(all("ruleIndex" not in r for r in merged["results"]))
        notes = [i["toolExecutionNotifications"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
                 for i in merged["invocations"]]
        self.assertEqual(notes, ["skills/aiwerk-a/SKILL.md", "skills/aiwerk-b/SKILL.md"])

    def test_paths_outside_the_repository_are_not_kept(self):
        bad = run("aiwerk-a", [result("LP3", "../../../../etc/passwd")])
        out = ms.merge({"runs": [bad]}, WORK)
        loc = out["runs"][0]["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]
        self.assertEqual(loc["uri"], "unknown")


if __name__ == "__main__":
    unittest.main()
