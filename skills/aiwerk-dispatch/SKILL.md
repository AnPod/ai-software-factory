---
name: aiwerk-dispatch
description: Produce exact headless agent commands and per-task git worktree setup for a task plan using the harness configured in aiwerk.md, and optionally run them when stage 02 autonomy and user confirmation allow. Writes .aiwerk/brain/specs/<id>/dispatch.md. Use after aiwerk-plan when preparing or dispatching headless agent runs in stage 02 orchestration.
license: Apache-2.0
---

# aiwerk-dispatch

Turn a task plan into exact, reproducible headless commands for the project's configured coding harness, isolated in one git worktree per task.

## Rules

- Check `.aiwerk/brain/aiwerk.md` first. If stage 02 (`02 Orchestration`) is `off`, say so and stop unless the user explicitly tells you to proceed anyway.
- Respect the stage 02 autonomy level in `aiwerk.md`:
  - `suggest`: write the commands to `.aiwerk/brain/specs/<id>/dispatch.md` only. Do not create worktrees, branches or run any agent commands.
  - `assist`: write the commands first, then ask for confirmation before running each wave. In non-interactive mode at `assist`, write commands only and do not execute them.
  - `auto`: write the commands first; in interactive mode still confirm before launching headless runs, and in non-interactive mode only execute if the user explicitly requested execution in the prompt.
- **Never add broad permission flags that bypass tool restrictions** to any generated command. Always scope allowed tools narrowly to the files and commands the task requires.
- Never put tokens, API keys or secrets in command lines, prompts or the brain.
- Never install harnesses, never push or merge branches automatically, never read files outside the project folder and never edit `## Human notes` sections.
- In non-interactive mode ("non-interactive", "CI", "use defaults"), ask nothing, default to plan-only (`suggest` behaviour) unless execution was explicitly requested at `auto`, and record assumptions under `## Assumptions`.

## Step 1: Read the brain

Read:

1. `.aiwerk/brain/index.md`, `.aiwerk/brain/aiwerk.md` (Harnesses, Stages, Sandboxing) and `.aiwerk/brain/landscape.md`.
2. `.aiwerk/brain/specs/<id>/tasks.md` (if missing, tell the user to run `aiwerk-plan` first and stop).
3. `.aiwerk/brain/specs/<id>/context.md` and `.aiwerk/brain/specs/<id>/sandbox.md` if they exist.

If `specs/<id>/dispatch.md` already exists, preserve its `## Human notes` section.

## Step 2: Select the headless harness command

Read the configured **Headless runner** from `.aiwerk/brain/aiwerk.md` (fall back to the interactive harness if no headless runner is listed, and record the fallback under `## Assumptions`). Check `command -v` only to note whether the CLI is on `PATH`; do not install anything.

Use the matching headless form:

| Harness | Headless command template |
|---|---|
| Claude Code | `claude -p "<prompt>" --output-format text --permission-mode acceptEdits --allowedTools Read Write Edit Glob Grep "Bash(git:*)"` |
| GitHub Copilot CLI | `copilot -p "<prompt>" --silent --no-ask-user --allow-tool=write --allow-tool="shell(git:*)"` |
| OpenAI Codex | `codex exec "<prompt>"` |
| OpenCode | `opencode run "<prompt>"` |
| Pi | `pi -p "<prompt>"` |
| Cursor CLI | `cursor-agent -p "<prompt>"` |
| Gemini CLI | `gemini -p "<prompt>"` |
| Factory Droid | `droid exec "<prompt>"` |

Add narrow test/lint tool permissions (for example `Bash(pytest:*)` or `shell(pytest:*)`) only when the task's done criteria require running that test command. Never add blanket allow-all flags.

## Step 3: Plan one worktree per task

For each task (`T1`, `T2`, ...) in `tasks.md`, prepare:

1. A dedicated branch name: `aiwerk/<id>/<task-id>` (lowercase).
2. A dedicated worktree directory `<worktrees>/<id>-<task-id>` (where `<worktrees>` is a directory outside the repository root chosen by the operator, for example `$HOME/worktrees`).
3. Worktree setup: `git worktree add <worktrees>/<id>-<task-id> -b aiwerk/<id>/<task-id> <base-branch>`
4. A concise task prompt telling the agent to read `.aiwerk/brain/specs/<id>/spec.md`, `.aiwerk/brain/specs/<id>/context.md` and `.aiwerk/brain/specs/<id>/tasks.md`, implement only `<task-id>`, run its verification command and leave changes ready for review without pushing.
5. Cleanup after merge: `git worktree remove <worktrees>/<id>-<task-id>`.

Respect dependency waves from `tasks.md`: Wave 2 tasks branch from the merged Wave 1 result (or note the base branch explicitly).

## Step 4: Execute only when allowed

- If stage 02 autonomy is `suggest`, or in non-interactive mode without an explicit execute instruction at `auto`, stop at planning and set every task's status to `planned`.
- If autonomy is `assist` or `auto` and the user confirms execution, run Wave 1 first, check exit status, update each task's status (`completed` or `failed`) and stop on failure before starting dependent waves.

## Step 5: Write `.aiwerk/brain/specs/<id>/dispatch.md`

Use all seven frontmatter fields from `SCHEMA.md`:

````markdown
---
title: "<id> dispatch plan"
kind: spec/dispatch
gathered_at: <now, UTC ISO 8601>
gathered_by: aiwerk-dispatch
sources:
  - file:.aiwerk/brain/aiwerk.md
  - file:.aiwerk/brain/specs/<id>/tasks.md
  - git:<branch>@<commit>
ttl_days: 7
confidence: high
---

# <id> dispatch plan

- **Headless runner:** <harness>
- **Stage 02 autonomy:** <suggest|assist|auto>
- **Execution mode:** <planned only | executed>
- **Worktrees root:** `<worktrees>` (set to an empty folder outside the repo)

## Dispatch table

| Wave | Task | Branch | Worktree | Status |
|---|---|---|---|---|
| 1 | T1 | `aiwerk/<id>/t1` | `<worktrees>/<id>-t1` | planned |

## Commands

### Wave 1: T1

    git worktree add <worktrees>/<id>-t1 -b aiwerk/<id>/t1 <base-branch>
    cd <worktrees>/<id>-t1
    <headless command for configured harness>

## Cleanup

    git worktree remove <worktrees>/<id>-t1

## Assumptions
- <any defaults used, or "none">

## Human notes
<!-- Skills never edit this section. -->
````

## Step 6: Update index and log

- Add or update the `specs/<id>/dispatch.md` row in `.aiwerk/brain/index.md`. In the frontmatter of `index.md`, change only `gathered_at` and keep the other six fields exactly as they are.
- Append one line to `.aiwerk/brain/log.md`: `<now> | aiwerk-dispatch | <created|updated> specs/<id>/dispatch.md | <n> tasks (<mode>)`.

## Step 7: Check your work

If `python3` is available, run the brain checker that ships with the `aiwerk-refresh` skill, from the project root. `<skills folder>` is the folder that contains this skill's folder:

```bash
python3 <skills folder>/aiwerk-refresh/scripts/brain_status.py .aiwerk/brain --strict
```

Fix every problem it reports, for example a missing frontmatter field or a page missing from `index.md`, and run it again until it reports 0 problems. If Python or `aiwerk-refresh` is not available, check by hand that every page you wrote or changed, `index.md` included, has all seven frontmatter fields from `SCHEMA.md` and a row in `index.md`.

## Step 8: Report

In under 10 lines: state the chosen harness, autonomy level, how many tasks were planned or executed, and suggest `aiwerk-review` and `aiwerk-test-gate` once tasks complete.
