#!/usr/bin/env python3
"""Validate every skill in skills/ against the Agent Skills format and this repo's rules.

Checks per skill folder:
  - SKILL.md exists and starts with frontmatter
  - name: lowercase letters, digits and hyphens, at most 64 chars, equals the folder name,
    starts with "aiwerk-"
  - description: present, at most 1024 chars, says when to use the skill ("Use when" / "Use after")
  - license is Apache-2.0
  - body under 500 lines
  - relative links in SKILL.md point to files that exist
  - no risky shell patterns (pipe to shell, base64 decode to shell, eval of downloads)
  - the skill appears in the README skill table

Standard library only. Exit 1 on any error.
"""

import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILLS = os.path.join(ROOT, "skills")
NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
RISKY = [
    (re.compile(r"curl[^\n|]*\|\s*(ba|z)?sh\b"), "pipes a download into a shell"),
    (re.compile(r"wget[^\n|]*\|\s*(ba|z)?sh\b"), "pipes a download into a shell"),
    (re.compile(r"base64\s+(-d|--decode)[^\n]*\|\s*(ba|z)?sh\b"), "decodes base64 into a shell"),
    (re.compile(r"\beval\s+\"?\$\((curl|wget)"), "evaluates a download"),
]


def frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, 0
    data = {}
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return data, i + 1
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if m:
            data[m.group(1)] = m.group(2).strip().strip("'\"")
    return None, 0


def check_skill(folder, readme):
    errors = []
    name = os.path.basename(folder)
    path = os.path.join(folder, "SKILL.md")
    if not os.path.isfile(path):
        return ["%s: SKILL.md is missing" % name]
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    fm, body_start = frontmatter(text)
    if fm is None:
        return ["%s: SKILL.md has no closed frontmatter block" % name]

    n = fm.get("name", "")
    if not n:
        errors.append("name is missing")
    else:
        if not NAME_RE.match(n) or len(n) > 64:
            errors.append("name must be lowercase letters, digits and hyphens, max 64 chars")
        if n != name:
            errors.append("name '%s' does not match folder '%s'" % (n, name))
        if not n.startswith("aiwerk-"):
            errors.append("name must start with 'aiwerk-'")

    d = fm.get("description", "")
    if not d:
        errors.append("description is missing")
    elif len(d) > 1024:
        errors.append("description is %d chars, max 1024" % len(d))
    elif not re.search(r"\bUse (when|after|before|for)\b", d):
        errors.append("description should say when to use the skill ('Use when ...')")

    if fm.get("license") != "Apache-2.0":
        errors.append("license must be Apache-2.0")

    body = text.splitlines()[body_start:]
    if len(body) > 500:
        errors.append("body has %d lines, keep it under 500 (move detail to references/)" % len(body))

    for target in re.findall(r"\]\(([^)\s]+)\)", text):
        if re.match(r"^[a-z]+:", target) or target.startswith("#"):
            continue
        if not os.path.exists(os.path.join(folder, target.split("#")[0])):
            errors.append("broken link: %s" % target)

    for root, _, files in os.walk(folder):
        for f in files:
            fp = os.path.join(root, f)
            try:
                with open(fp, encoding="utf-8") as fh:
                    content = fh.read()
            except UnicodeDecodeError:
                errors.append("binary file not allowed: %s" % os.path.relpath(fp, folder))
                continue
            for pattern, why in RISKY:
                if pattern.search(content):
                    errors.append("%s %s" % (os.path.relpath(fp, folder), why))

    if "`%s`" % name not in readme:
        errors.append("not listed in README.md")

    return ["%s: %s" % (name, e) for e in errors]


def main():
    with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
        readme = fh.read()
    folders = sorted(
        os.path.join(SKILLS, d) for d in os.listdir(SKILLS) if os.path.isdir(os.path.join(SKILLS, d))
    )
    if not folders:
        print("no skills found in skills/")
        return 1
    errors = []
    for folder in folders:
        errors.extend(check_skill(folder, readme))
    for e in errors:
        print("error: " + e)
    print("%d skills checked, %d errors" % (len(folders), len(errors)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
