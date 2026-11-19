---
name: aiwerk-init
description: Set up an AI Werk software factory in the current project. Interviews the user about which coding agents (harnesses) they use, where work comes in (Slack, Jira, Confluence, Linear, GitHub, email), what should trigger agents, which SDLC stages to enable and how much autonomy agents get, then creates the project brain in .aiwerk/brain. Use when the user asks to set up, initialise or reconfigure the software factory, or when another aiwerk skill finds no .aiwerk/brain folder.
license: Apache-2.0
---

# aiwerk-init

Set up the software factory for this project and create its brain: a folder of Markdown pages in `.aiwerk/brain/` that every other aiwerk skill reads first and writes back to.

## Rules

- Write only inside `.aiwerk/`. Do not install, connect, authenticate or configure any tool in this skill.
- Never write secrets, tokens, passwords or personal data (beyond work handles the user gives you) into the brain.
- Ask at most three questions at a time. Offer what you detected as the default so the user can just confirm.
- If the user says "non-interactive", "CI" or "use defaults", do not ask anything. Use detected values, then the defaults below, and record every assumption under `## Assumptions`.

## Step 1: Check for an existing brain

If `.aiwerk/brain/aiwerk.md` exists, read it and show the user the current answers and their age (`gathered_at`). Ask whether to keep, update some answers, or start over. Never delete pages without the user saying so. If they keep everything, stop and suggest `aiwerk-landscape` or `aiwerk-survey`.

## Step 2: Create the brain

If `.aiwerk/brain/` does not exist, copy every file from the `assets/brain/` folder next to this SKILL.md into `.aiwerk/brain/`. Replace each `{{NOW}}` with the current UTC time in ISO 8601 form, for example `2026-11-19T10:42:00Z`.

Ask once whether the brain should be committed to git (recommended: the team shares one memory and changes are reviewable) or ignored. If ignored, add `.aiwerk/` to `.gitignore`.

## Step 3: Detect before you ask

Look, do not run anything that changes state:

- Harnesses: `.claude/`, `CLAUDE.md`, `AGENTS.md`, `.agents/`, `.codex/`, `.opencode/`, `opencode.json`, `.cursor/`, `.gemini/`, `.factory/`, `.pi/`.
- Intake: `.github/ISSUE_TEMPLATE/`, issue keys like `ABC-123` in recent commit messages (`git log --oneline -50`), links to `atlassian.net`, `linear.app` or `slack.com` in README or docs.
- CI and triggers: `.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `azure-pipelines.yml`, `.circleci/`.
- Sandboxing: `Dockerfile`, `.devcontainer/`, `docker-compose.yml`.

## Step 4: Interview

Cover these topics, in this order. Skip any the user already answered.

1. **Harnesses.** Which coding agents does the team use (Claude Code, Codex, OpenCode, Pi, Cursor, Gemini CLI, Factory Droid, T3 Code, other)? Which one should run headless for triggers and CI?
2. **Intake.** Where does work arrive: Slack, Jira, Confluence, Linear, GitHub Issues, GitLab, email, other? Which one is the source of truth for specs?
3. **Triggers.** What may start an agent: manual only, issue label, pull request, schedule, chat mention?
4. **Stages and autonomy.** For each stage, off or one of the autonomy levels below.
5. **Sandboxing.** Where may agents run code: local git worktree, container, a sandbox service (E2B, Daytona, Modal, other)?
6. **Policies.** Regulated data, PII, licence rules, who must approve merges and deploys.

Stages, from the AI Werk assembly line:

| Stage | Name | What agents do |
|---|---|---|
| 01 | Intake and context | Turn requests into specs, gather context |
| 02 | Orchestration | Plan tasks, dispatch them to agents and sandboxes |
| 03 | Eval and governance | Review, test and security gates before a human looks |
| 04 | Release | Release notes, deploy checks, docs sync |
| 05 | Operations | Incident triage, turning incidents into new specs |

Autonomy levels:

- `off`: stage not used.
- `suggest`: agent proposes, a human does the work.
- `assist`: agent does the work, a human approves each change.
- `auto`: agent acts within the gates of stage 03, humans review results.

Defaults for non-interactive mode: harness = the one running this skill; intake = GitHub Issues if the repo is on GitHub, otherwise manual; triggers = manual; stages 01 and 03 = `suggest`, others = `off`; sandbox = local git worktree; policies = none recorded.

## Step 5: Write `.aiwerk/brain/aiwerk.md`

Use this structure. Keep it short; it is read at the start of every aiwerk skill.

```markdown
---
title: Factory setup
kind: setup
gathered_at: <now, UTC ISO 8601>
gathered_by: aiwerk-init
sources:
  - interview
ttl_days: 90
confidence: high
---

# Factory setup

## Harnesses
- Interactive: <list>
- Headless runner: <one>

## Intake
- Source of truth for specs: <tool>
- Other channels: <list>

## Triggers
- <trigger>: <what it starts>

## Stages
| Stage | Autonomy | Notes |
|---|---|---|
| 01 Intake and context | suggest | |
| 02 Orchestration | off | |
| 03 Eval and governance | suggest | |
| 04 Release | off | |
| 05 Operations | off | |

## Sandboxing
- <choice>

## Policies
- <policy or "none recorded">

## Assumptions
- <every default you used instead of an answer>

## Human notes
<!-- Skills never edit this section. -->
```

Set `confidence: high` for answers the user gave, `medium` if most values were detected or assumed.

## Step 6: Update index and log

- Add `aiwerk.md` to the table in `.aiwerk/brain/index.md` and update the `gathered_at` of `index.md`.
- Append one line to `.aiwerk/brain/log.md`: `<now> | aiwerk-init | <created|updated> aiwerk.md | <harness>`.

## Step 7: Hand over

Tell the user in a few lines what was set up, then suggest the next step:

1. `aiwerk-landscape` to find which tools, MCP servers and CLIs the agents can use, with their consent.
2. `aiwerk-survey` to read the project into the brain.
