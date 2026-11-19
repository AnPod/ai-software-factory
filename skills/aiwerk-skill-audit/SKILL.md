---
name: aiwerk-skill-audit
description: Audit every installed Agent Skill in this project (including third-party skills, not only aiwerk skills) using NVIDIA SkillSpector static analysis when installed, summarising scores and verdicts in the brain, or explain how to install SkillSpector and stop when it is missing. Use when auditing installed skills for prompt injection, credential access or supply-chain risk.
license: Apache-2.0
---

# aiwerk-skill-audit

Run static security checks across every Agent Skill installed in the project so teams see the risk verdict for third-party and in-house skills alike, not only AI Werk Skills.

## Rules

- Read-only on repository code and installed skills. Write only inside `.aiwerk/brain/` (and only when SkillSpector actually ran).
- **Never install, download, upgrade or authenticate SkillSpector or any other tool.** If `skillspector` is missing, explain how the user can install it and stop.
- **Never fabricate scan verdicts, scores or finding counts.**
- Scan only project-local skill folders (`.claude/skills`, `.agents/skills`, `.opencode/skills`, `.cursor/skills`, `.gemini/skills`, `.factory/skills`, `.github/skills`). Never read user-level agent configuration or host credential directories.
- Scan **every** skill present in those folders, including non-`aiwerk-*` skills.
- Always pass `--no-llm` so static analysis runs locally without sending skill files to an LLM API.
- Never copy secret values or personal data into the brain, never read files outside the project folder and never edit `## Human notes` sections.
- In non-interactive mode ("non-interactive", "CI", "use defaults"), ask nothing, scan existing project skill folders if `skillspector` is installed (or print install instructions and stop cleanly if missing) and record assumptions under `## Assumptions`.

## Step 1: Check whether SkillSpector is installed

Check if `skillspector` is on `PATH`:

```bash
command -v skillspector
```

**If `skillspector` is missing:**

1. List any project skill folders found in this repository and how many skill folders exist in each, without claiming they are safe or unsafe.
2. Explain plainly how the user can install NVIDIA SkillSpector themselves (pinned release):
   - With `pipx`: `pipx install "git+https://github.com/NVIDIA/skillspector.git@v2.13.6"`
   - Or with `uv`: `uv tool install --python 3.12 "git+https://github.com/NVIDIA/skillspector.git@v2.13.6"`
   - Source repository: `https://github.com/NVIDIA/skillspector`
3. **Stop immediately.** Do not install anything, do not write or modify files in `.aiwerk/brain/` or anywhere else, and do not guess verdicts.

## Step 2: Read the brain (only when SkillSpector is installed)

Read `.aiwerk/brain/index.md`, `.aiwerk/brain/aiwerk.md` and `.aiwerk/brain/landscape.md` if present. If `.aiwerk/brain/skill-audit.md` already exists, preserve its `## Human notes` section.

## Step 3: Discover installed skill folders

Check which project skill folders exist in the repository root:

- `.claude/skills`
- `.agents/skills`
- `.github/skills`
- `.opencode/skills`
- `.cursor/skills`
- `.gemini/skills`
- `.factory/skills`

Note when multiple folders symlink to the same skill set so you scan every distinct skill folder without double-counting identical symlinks if you want a clean table, while making sure **every** unique installed skill (both `aiwerk-*` and third-party skills) is scanned.

In interactive mode, show the exact `skillspector scan` command(s) and ask for confirmation before running them.

## Step 4: Run SkillSpector static scan

For each existing project skill folder `<skills dir>`, run static analysis without an LLM:

```bash
skillspector scan <skills dir> --recursive --no-llm --format json
```

Never pass `-o /dev/null` (SkillSpector exits with code 2 on `/dev/null`). Reading JSON from stdout keeps the working tree completely clean.

From the JSON output, collect for **every** scanned skill:

- Skill name and folder
- Origin: `aiwerk` (name starts with `aiwerk-`) or `third-party`
- Risk score (`risk_score` or `risk_assessment.score`)
- Verdict (`risk_assessment.recommendation`: `SAFE`, `CAUTION` or `UNSAFE`)
- Finding IDs and severities (for example `LP3 medium`, or `none`)
- Analysis completeness status (`analysis_completeness.status`)

Record `<branch>` (`git branch --show-current`) and `<commit>` (`git rev-parse --short HEAD`) for `sources`.

## Step 5: Write `.aiwerk/brain/skill-audit.md`

Use all seven frontmatter fields from `SCHEMA.md`:

```markdown
---
title: "Installed skill security audit"
kind: skill-audit
gathered_at: <now, UTC ISO 8601>
gathered_by: aiwerk-skill-audit
sources:
  - cli:skillspector scan <skills dir> --recursive --no-llm --format json
  - git:<branch>@<commit>
ttl_days: 7
confidence: high
---

# Installed skill security audit

- **Scanner:** NVIDIA SkillSpector (`--recursive --no-llm`)
- **Folders scanned:** `<list of project skill folders>`
- **Skills scanned:** `<total>` (`<aiwerk count>` AI Werk, `<third-party count>` third-party)
- **Summary:** `<safe> SAFE, <caution> CAUTION, <unsafe> UNSAFE`
- **Completeness:** `<complete | incomplete>`

## Skill verdicts

| Skill | Folder | Origin | Score | Verdict | Findings |
|---|---|---|---|---|---|
| `<name>` | `<folder>` | `<aiwerk / third-party>` | `<score>` | `<SAFE / CAUTION / UNSAFE>` | `<ids or none>` |

## Findings requiring review
- <details for any CAUTION, UNSAFE or high/medium finding, or "none">

## Assumptions
- <project-local scope, skipped duplicate symlink folders or other defaults, or "none">

## Human notes
<!-- Skills never edit this section. -->
```

## Step 6: Update index and log

- Add or update the `skill-audit.md` row in `.aiwerk/brain/index.md`. In the frontmatter of `index.md`, change only `gathered_at` and keep the other six fields exactly as they are.
- Append one line to `.aiwerk/brain/log.md`: `<now> | aiwerk-skill-audit | <created|updated> skill-audit.md | <total> skills (<safe> SAFE, <caution> CAUTION, <unsafe> UNSAFE)`.

## Step 7: Check your work

If `python3` is available, run the brain checker that ships with the `aiwerk-refresh` skill, from the project root. `<skills folder>` is the folder that contains this skill's folder:

```bash
python3 <skills folder>/aiwerk-refresh/scripts/brain_status.py .aiwerk/brain --strict
```

Fix every problem it reports, for example a missing frontmatter field or a page missing from `index.md`, and run it again until it reports 0 problems.

## Step 8: Report

In under 10 lines: list folders scanned, total skills (AI Werk vs third-party), SAFE/CAUTION/UNSAFE counts and any non-SAFE skills that need attention.
