---
name: aiwerk-survey
description: Read the whole project into the AI Werk brain on the first run (the initial pour), and update it on later runs. Records what the project is, its stack, build and test commands, architecture, owners, conventions and gaps as timestamped pages in .aiwerk/brain/project/, using only sources the user allowed. Use after aiwerk-init, when the user asks to survey, map, onboard or learn a codebase, or when project pages in the brain are stale.
license: Apache-2.0
---

# aiwerk-survey

Learn the project once, write it down with sources and timestamps, so every later agent starts from the same picture instead of rediscovering it.

## Rules

- Read, do not change. The only files you write are under `.aiwerk/brain/`.
- Do not run builds, tests, installs or migrations unless the user approves it in this session. Find commands by reading files.
- Use external sources (MCP servers, CLIs, browser) only if `.aiwerk/brain/landscape.md` marks them `read` or `write`. If a source is `ask`, ask. If there is no landscape page, use the repository only.
- If you find something that looks like a secret, do not copy it. Record the file path in `project/gaps.md` as a finding.
- Record contributor handles only as they appear in CODEOWNERS or the git log. No emails, no other personal data.

## Step 1: Read the brain

Read `.aiwerk/brain/index.md`, `aiwerk.md` and `landscape.md` if they exist. If the brain does not exist, ask whether to run `aiwerk-init` first or to create only `.aiwerk/brain/project/` now. If project pages exist, this is an update: compare instead of rewriting, and keep every `## Human notes` section unchanged.

## Step 2: Survey the repository

Note the current commit with `git rev-parse --short HEAD` and branch with `git branch --show-current`. Use them in `sources` as `git:<branch>@<commit>`.

1. **Map.** `git ls-files` for the file list. Count files per top-level folder and per extension. Find entry points.
2. **Stack.** Read manifests: `package.json`, `pyproject.toml`, `requirements*.txt`, `go.mod`, `Cargo.toml`, `pom.xml`, `build.gradle*`, `Gemfile`, `composer.json`, `*.csproj`, `Dockerfile`, `docker-compose*.yml`, `*.tf`. Record languages, frameworks, main dependencies, runtime versions.
3. **Commands.** Find how to install, build, test, lint and run, from `Makefile`, `justfile`, package scripts, CI workflow files, `README`, `CONTRIBUTING`. Record each command with the file it came from. Mark which ones CI actually runs.
4. **Architecture.** Modules or services, how they talk, data stores, external APIs, configuration and environments. Read existing architecture docs first and cite them.
5. **Owners.** `CODEOWNERS`, and the top ten handles of `git shortlog -sn --since="1 year ago"` if git history is available.
6. **Decisions.** ADR folders (`docs/adr`, `docs/decisions`, `adr/`), design docs. One line per decision.
7. **Conventions.** Lint and format configs, commit message style from `git log --oneline -30`, branch and PR rules from CI and templates, existing `AGENTS.md` or `CLAUDE.md`.
8. **Gaps.** Missing tests, missing CI, no README, no lockfile, no agent instructions, outdated docs, possible secrets in the repo. These feed the readiness score later.

## Step 3: Survey allowed external sources

Only those allowed in `landscape.md`, and only at summary level: for example the Confluence space home page and its page tree, the Jira or Linear project's open epics, the catalog entries for this repository's tables. Cite each source with its prefix (`mcp:`, `cli:`, `url:`). Skip anything that would take more than a few calls and note it as a follow-up.

## Step 4: Write pages

Write these pages in `.aiwerk/brain/project/`, each with the frontmatter from `SCHEMA.md`, `gathered_by: aiwerk-survey`, `ttl_days` from the schema defaults, and a `## Human notes` section at the end:

| Page | kind | Content |
|---|---|---|
| `overview.md` | `project/overview` | What the project is, for whom, main parts, in under 40 lines |
| `stack.md` | `project/stack` | Languages, frameworks, key dependencies, runtimes |
| `commands.md` | `project/commands` | Install, build, test, lint, run, with source file for each |
| `architecture.md` | `project/architecture` | Modules or services, data, integrations |
| `owners.md` | `project/owners` | Code owners and active contributors (handles only) |
| `conventions.md` | `project/conventions` | Style, commits, branches, review rules |
| `gaps.md` | `project/gaps` | Findings that make agent work harder or riskier |

If ADRs exist, also write `.aiwerk/brain/decisions/index.md` (kind `decision/index`) listing them with links.

Set `confidence` honestly: `high` when read directly from files, `medium` when inferred, `low` when guessed. Every statement that matters gets a source.

## Step 5: Update index and log

- Add or update one row per page in `.aiwerk/brain/index.md`, then update its `gathered_at`.
- Append one line per page to `.aiwerk/brain/log.md`: `<now> | aiwerk-survey | <created|updated|verified> <page> | git:<branch>@<commit>`.

## Step 6: Report

In under 15 lines: what the project is, how to test it, the three most important gaps, and which stage the user should enable or improve first. Do not paste the pages.
