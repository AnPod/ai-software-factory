#!/usr/bin/env python3
"""Fail a pull request that changes skills/ without a CHANGELOG.md "Unreleased" entry.

Usage: check_changelog.py BASE_REF [HEAD_REF]

Reads the pull request labels from the environment variable CHANGELOG_LABELS, either a
JSON array of label names or a comma separated list. The label "no-changelog" skips the check.

Runs read-only git commands (diff, merge-base, show) in the current repository.
Standard library only, no network. Exit 1 when the check fails, 0 on pass or skip.
"""

import json
import os
import re
import subprocess
import sys

OPT_OUT_LABEL = "no-changelog"
LABELS_ENV = "CHANGELOG_LABELS"
CHANGELOG = "CHANGELOG.md"
UNRELEASED_RE = re.compile(r"^## \[Unreleased\][ \t]*$", re.MULTILINE | re.IGNORECASE)
NEXT_HEADING_RE = re.compile(r"^## \[", re.MULTILINE)


def touches_skills(paths):
    """True when any changed path is under skills/. Deleted and renamed paths count."""
    return any(p.startswith("skills/") for p in paths)


def extract_unreleased(text):
    """Return the Unreleased section text (heading excluded), or None when it is missing."""
    if text is None:
        return None
    text = text.replace("\r\n", "\n")
    start = UNRELEASED_RE.search(text)
    if not start:
        return None
    rest = text[start.end():]
    nxt = NEXT_HEADING_RE.search(rest)
    return rest[:nxt.start()] if nxt else rest


def normalize(section):
    """Collapse all whitespace so formatting-only edits are not counted as entries."""
    return " ".join((section or "").split())


def unreleased_changed(base_text, head_text):
    """True when the Unreleased section has different content (ignoring whitespace)."""
    base = extract_unreleased(base_text)
    head = extract_unreleased(head_text)
    if head is None:
        return False
    if base is None:
        return bool(normalize(head))
    return normalize(base) != normalize(head)


def parse_labels(raw):
    """Parse a JSON array of names or a comma separated list into a list of names."""
    raw = (raw or "").strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        if isinstance(data, list):
            return [str(x).strip() for x in data if str(x).strip()]
    return [x.strip() for x in raw.split(",") if x.strip()]


def has_opt_out(labels):
    """GitHub label names are case-insensitive, so compare lowercased."""
    return OPT_OUT_LABEL in [label.lower() for label in labels]


def evaluate(changed_paths, base_text, head_text, labels):
    """Return (ok, message)."""
    if not touches_skills(changed_paths):
        return True, "No changes under skills/. No changelog entry needed."
    if has_opt_out(labels):
        return True, "Notice: the '%s' label is set, so the changelog check is skipped." % OPT_OUT_LABEL
    if extract_unreleased(head_text) is None:
        return False, (
            "This pull request changes skills/, but %s has no '## [Unreleased]' section.\n"
            "Add the section with an entry, or add the '%s' label if no entry is needed."
            % (CHANGELOG, OPT_OUT_LABEL))
    if unreleased_changed(base_text, head_text):
        return True, "The '## [Unreleased]' section of %s was updated." % CHANGELOG
    return False, (
        "This pull request changes skills/, but the '## [Unreleased]' section of %s is unchanged.\n"
        "Add an entry there, or add the '%s' label if no entry is needed.\n"
        "Whitespace-only edits do not count." % (CHANGELOG, OPT_OUT_LABEL))


def git(*args):
    return subprocess.run(["git"] + list(args), check=True, capture_output=True, text=True).stdout


def changelog_at(rev):
    try:
        return git("show", "%s:%s" % (rev, CHANGELOG))
    except subprocess.CalledProcessError:
        return None


def main(argv=None, environ=None):
    argv = sys.argv[1:] if argv is None else argv
    environ = os.environ if environ is None else environ
    if not argv or len(argv) > 2:
        print("usage: check_changelog.py BASE_REF [HEAD_REF]", file=sys.stderr)
        return 2
    base_ref = argv[0]
    head_ref = argv[1] if len(argv) > 1 else "HEAD"
    try:
        base = git("merge-base", base_ref, head_ref).strip()
        changed = [p for p in git("diff", "-z", "--name-only", "--no-renames", base, head_ref).split("\0") if p]
    except subprocess.CalledProcessError as exc:
        print("git failed: %s" % (exc.stderr or exc).strip(), file=sys.stderr)
        return 2
    ok, message = evaluate(changed, changelog_at(base), changelog_at(head_ref),
                           parse_labels(environ.get(LABELS_ENV, "")))
    print(message, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
