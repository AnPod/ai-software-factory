# Changelog

All notable changes to AI Werk Skills are recorded here.

## [Unreleased]

### Changed

- Recipes pin `AIWERK_REF` to the v0.5.0 commit, so they install the hardened skills.

## [0.5.0] - 2026-11-20

### Security

- Every skill now treats brain pages, repository files, tickets and tool output as untrusted data, never as instructions. `SCHEMA.md` has a new Trust section: consent and autonomy count only when a human set or reviewed them, and project commands run only when the project's own files define them. `scripts/validate_skills.py` checks that every skill has the rule.
- `aiwerk-test-gate` runs a test command only after checking it against the Makefile, `package.json`, `pyproject.toml`, `tox.ini` or CI workflows at HEAD, and refuses chained commands and downloads.
- `aiwerk-dispatch` templates carry their tool scope: no blanket `git:*` rule, prompts in single quotes, and a scope column for every harness. `aiwerk-landscape` drops credentials, query strings and key-like parts from recorded MCP URLs and commands. `aiwerk-sandbox` says plainly that a git worktree is not a security boundary. `aiwerk-skill-audit` suggests installing SkillSpector from a commit, not a tag.
- `brain_status.py` no longer follows symbolic links, ignores index links that leave the brain folder, scans `health.html`, knows more credential shapes (GitLab, Slack webhooks, Stripe, npm, Hugging Face, JWTs, URLs with passwords) and removes control characters and credential-shaped text from what it prints.
- `install.sh` refuses to write through a symbolic link inside the project, removes only copies whose `SKILL.md` names the expected skill, resolves paths with `pwd -P`, ends options with `--`, and `--help` prints only the usage text.
- `scripts/validate_skills.py` ignores Python caches, rejects symbolic links and rejects links that leave the skill folder.
- GitHub Actions recipes: the agent may write only `.aiwerk/brain/` (Copilot `write(.aiwerk/brain/**)`, Claude Code `dontAsk` mode with `Edit(.aiwerk/brain/**)`), agent configuration from the checkout is removed before the run, Claude Code loads no project settings or MCP servers, the agent runs without the runner's file-command variables, the key check fails closed and adds the brain checker's credential scan, artifacts are kept for 7 days, and the job summary shows only known verdict words. In `pr-governance-gates.yml` the tests and lint job now fails when they fail, and the gate jobs still report.
- `evals.yml` and `evals/run_evals.py`: the eval agent gets a filtered environment and narrow tool rules (no `python3`, `cat`, `find`, `cp` or blanket `git`), deny rules for `.git/` and skill folders, checkouts keep no credentials, and results are uploaded only after a fail-closed key check, for 7 days.
- Every action in the workflows and recipes is pinned to a commit SHA (checkout, setup-python, setup-node and upload-artifact v7, download-artifact v8, codeql-action v4.39.3). A test keeps the recipes on the same commits as the workflows.
- `skillspector.yml`: the scan job now has a read-only token and keeps no git credentials on disk. SARIF upload and release attachment run in separate jobs with only the permissions they need. SkillSpector is installed from the commit of its pinned tag, and the release tag reaches the shell through an environment variable.
- GitHub Actions recipes: secrets are checked in a gate job (GitHub rejects `secrets` in a job's `if:`). Agents no longer get `python3`, `find`, `cp`, `cat` or blanket `git` rules, skill files and git config are read-only for them, checkouts keep no credentials, and output is searched for the API key before upload. `pr-governance-gates.yml` runs tests and lint in a separate job without keys. `issue-intake-and-spec.yml` runs automatically only for issues from the owner, members or collaborators, fetches the issue with `gh` (so manual dispatch works), removes hidden HTML comments and validates dispatch inputs.

### Fixed

- SkillSpector findings now reach GitHub code scanning. `scripts/merge_sarif.py` merges the per-skill SARIF runs into one run with repository-relative paths, and upload errors are no longer hidden.

### Added

- `CODE_OF_CONDUCT.md`, issue templates (with a private link for security problems) and a pull request template.

### Changed

- The repository moved to `AnPod/ai-software-factory`. Recipes pin `AIWERK_REF` to a commit SHA.
- README and SECURITY.md describe what CI actually covers: Copilot CLI evals run in CI, Claude Code evals run locally until an Anthropic key is configured.
- Dependabot groups action updates into one pull request.

## [0.4.0] - 2026-11-19

### Added

- Meta skills: `aiwerk-health` (writes `.aiwerk/brain/health.md` and self-contained `.aiwerk/brain/health.html`) and `aiwerk-skill-audit` (audits every installed project skill with NVIDIA SkillSpector when installed, or explains how to install it and stops).
- Brain schema TTL entry for `skill-audit` and file listing for `health.md`, `health.html` and `skill-audit.md`.
- Claude Code plugin and marketplace manifests in `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, plus harness-specific install notes in `README.md` for Claude Code, GitHub Copilot CLI, OpenAI Codex and OpenCode.
- Example headless GitHub Actions recipes in `recipes/github-actions/` (`issue-intake-and-spec.yml` and `pr-governance-gates.yml`) for `copilot -p` and `claude -p` with narrow tool allowlists matching `evals/run_evals.py`.
- Deterministic eval cases, stand-in agent tests (covering both installed and missing SkillSpector paths) and packaging validation tests (`tests/test_packaging.py`).

## [0.3.0] - 2026-11-19

### Added

- Stage 04 skills: `aiwerk-release`, `aiwerk-deploy-check` and `aiwerk-docs-sync`.
- Stage 05 skills: `aiwerk-incident`, `aiwerk-incident-to-spec` and `aiwerk-slo`.
- Brain schema TTL entries for `spec/release`, `spec/deploy`, `incident` and `slo`.
- Layered stage 04 and 05 brain seeds, deterministic eval cases and good/bad stand-in agent tests for all 6 new skills.

## [0.2.0] - 2026-11-19

### Added

- Stage 01 skills: `aiwerk-readiness`, `aiwerk-intake`, `aiwerk-spec` and `aiwerk-context`.
- Stage 02 skills: `aiwerk-plan`, `aiwerk-dispatch` and `aiwerk-sandbox`.
- Stage 03 skills: `aiwerk-review`, `aiwerk-test-gate`, `aiwerk-security-gate` and `aiwerk-policy`.
- Brain schema TTL entries for `project/readiness`, `spec`, `spec/ticket`, `spec/tasks`, `spec/context`, `spec/dispatch`, `spec/sandbox`, `spec/review`, `spec/tests`, `spec/security` and `spec/policy`.
- Fixture request `evals/fixtures/tinyshop/docs/issue-12.md` ("Apply a per-SKU discount cap") and layered brain seeds plus a feature-branch diff seed in `evals/run_evals.py`.
- Deterministic eval cases and good/bad stand-in agent tests for all 11 new skills.

## [0.1.0] - 2026-11-19

### Added

- Four initial skills: `aiwerk-init`, `aiwerk-landscape`, `aiwerk-survey` and `aiwerk-refresh`.
- Project brain schema and template in `skills/aiwerk-init/assets/brain/` with seven required frontmatter fields, TTL-based staleness tracking and append-only `log.md`.
- Read-only brain health checker `skills/aiwerk-refresh/scripts/brain_status.py` (standard library only, no network calls, secret pattern checks).
- Provider reference table by SDLC stage in `skills/aiwerk-landscape/references/providers.md`.
- Contained `install.sh` installer (dry run by default, `--apply`, `--copy`, `--uninstall`, project and user scope, harness aliases).
- Validation script `scripts/validate_skills.py`, unit tests (`tests/test_brain_status.py`, `tests/test_evals_runner.py`, `tests/test_install.sh`) and deterministic agent eval runner `evals/run_evals.py` with the `tinyshop` fixture.
- GitHub Actions workflows for CI, NVIDIA SkillSpector static security gate (SAFE required for every skill, reports attached to releases) and GitHub Copilot CLI / Claude Code agent evals.
- Dependabot weekly updates for GitHub Actions.
