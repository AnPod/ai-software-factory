"""Unit tests for skills/aiwerk-refresh/scripts/brain_status.py and the brain template."""

import importlib.util
import io
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "aiwerk-refresh", "scripts", "brain_status.py")
TEMPLATE = os.path.join(ROOT, "skills", "aiwerk-init", "assets", "brain")

spec = importlib.util.spec_from_file_location("brain_status", SCRIPT)
bs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bs)

NOW = "2026-11-19T12:00:00Z"


def page(title, kind, gathered_at, ttl, extra=""):
    return (
        "---\n"
        "title: %s\nkind: %s\ngathered_at: %s\ngathered_by: aiwerk-survey\n"
        "sources:\n  - git:main@abc1234\nttl_days: %d\nconfidence: medium\n---\n\n# %s\n%s"
        % (title, kind, gathered_at, ttl, title, extra)
    )


class BrainStatusTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.brain = os.path.join(self.dir, "brain")
        os.makedirs(os.path.join(self.brain, "project"))
        self.write("index.md", page("Brain index", "index", "2026-11-19T11:00:00Z", 1,
                   "| [project/stack.md](project/stack.md) |\n| [project/owners.md](project/owners.md) |\n"))
        self.write("project/stack.md", page("Stack", "project/stack", "2026-11-01T12:00:00Z", 14))
        self.write("project/owners.md", page("Owners", "project/owners", "2026-11-09T12:00:00Z", 60))
        self.write("log.md", "# Brain log\n")

    def tearDown(self):
        shutil.rmtree(self.dir)

    def write(self, rel, text):
        with open(os.path.join(self.brain, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_main(self, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = bs.main([self.brain, "--now", NOW] + list(args))
        return code, buf.getvalue()

    def statuses(self):
        pages, problems = bs.scan(self.brain, bs.parse_time(NOW))
        return {p["page"]: p["status"] for p in pages}, problems

    def test_staleness(self):
        status, problems = self.statuses()
        self.assertEqual(status["project/stack.md"], "stale")  # 18 days, ttl 14
        self.assertEqual(status["project/owners.md"], "fresh")  # 10 days, ttl 60
        self.assertEqual(problems, [])

    def test_soon(self):
        self.write("project/stack.md", page("Stack", "project/stack", "2026-11-07T12:00:00Z", 14))  # 12 of 14
        status, _ = self.statuses()
        self.assertEqual(status["project/stack.md"], "soon")

    def test_stale_only_fails_when_asked(self):
        self.assertEqual(self.run_main()[0], 0)
        self.assertEqual(self.run_main("--fail-on-stale")[0], 1)

    def test_missing_fields_and_index(self):
        self.write("project/new.md", "---\ntitle: New\nkind: project/x\n---\n")
        code, out = self.run_main("--strict")
        self.assertEqual(code, 1)
        self.assertIn("missing fields", out)
        self.assertIn("not listed in index.md", out)

    def test_broken_index_link(self):
        os.remove(os.path.join(self.brain, "project", "owners.md"))
        _, problems = self.statuses()
        self.assertTrue(any("missing page project/owners.md" in p["problem"] for p in problems))

    def test_secret_detection_hides_value(self):
        token = "ghp_" + "a" * 36
        self.write("project/stack.md", page("Stack", "project/stack", "2026-11-18T12:00:00Z", 14, "token " + token + "\n"))
        code, out = self.run_main("--strict")
        self.assertEqual(code, 1)
        self.assertIn("possible secret (github-token)", out)
        self.assertNotIn(token, out)

    def test_new_credential_shapes_and_health_html(self):
        self.write("health.html", "<p>hooks.slack.com/services/T0000/B0000/abcdefabcdef</p>\n")
        _, problems = self.statuses()
        self.assertTrue(any(p["page"] == "health.html" and "slack-webhook" in p["problem"] for p in problems))

    def test_symlinked_page_is_not_followed(self):
        outside = os.path.join(self.dir, "outside.md")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write(page("Outside", "project/outside", "2026-11-18T12:00:00Z", 14, "ghp_" + "b" * 36 + "\n"))
        os.symlink(outside, os.path.join(self.brain, "project", "linked.md"))
        status, problems = self.statuses()
        self.assertNotIn("project/linked.md", status)
        self.assertTrue(any("symbolic link" in p["problem"] for p in problems))
        self.assertFalse(any("github-token" in p["problem"] for p in problems))

    def test_index_links_outside_the_brain_are_not_checked(self):
        self.write("index.md", page("Brain index", "index", "2026-11-19T11:00:00Z", 1,
                   "| [project/stack.md](project/stack.md) |\n| [project/owners.md](project/owners.md) |\n"
                   "| [x](../../etc/passwd.md) |\n| [y](/tmp/abs.md) |\n"))
        _, problems = self.statuses()
        self.assertTrue(any("2 link(s) point outside" in p["problem"] for p in problems))
        self.assertFalse(any("passwd" in p["problem"] or "abs.md" in p["problem"] for p in problems))

    def test_printed_metadata_is_cleaned(self):
        text = page("Stack", "project/stack", "2026-11-18T12:00:00Z", 14).replace(
            "gathered_by: aiwerk-survey", "gathered_by: \x1b[2J ghp_" + "c" * 36)
        self.write("project/stack.md", text)
        code, out = self.run_main()
        self.assertNotIn("\x1b", out)
        self.assertNotIn("c" * 36, out)

    def test_bad_values(self):
        self.write("project/stack.md", page("Stack", "project/stack", "yesterday", 14))
        _, problems = self.statuses()
        self.assertTrue(any("ISO 8601" in p["problem"] for p in problems))

    def test_json_output(self):
        import json
        code, out = self.run_main("--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(len(data["pages"]), 3)

    def test_missing_folder(self):
        self.assertEqual(bs.main([os.path.join(self.dir, "nope")]), 2)


class TemplateTest(unittest.TestCase):
    def test_template_is_valid(self):
        pages, problems = bs.scan(TEMPLATE, bs.parse_time(NOW), template=True)
        self.assertEqual(problems, [])
        self.assertEqual([p["page"] for p in pages], ["index.md"])

    def test_template_needs_placeholder_mode(self):
        _, problems = bs.scan(TEMPLATE, bs.parse_time(NOW), template=False)
        self.assertTrue(any("ISO 8601" in p["problem"] for p in problems))


if __name__ == "__main__":
    unittest.main()
