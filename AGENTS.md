# Working in this repository

This repository (`AnPod/ai-software-factory`) contains the public AI Werk Agent Skills (`skills/aiwerk-*/SKILL.md`), the installer (`install.sh`), Claude Code plugin manifests (`.claude-plugin/`), headless CI recipes (`recipes/github-actions/`), unit tests (`tests/`), and deterministic agent evals (`evals/`). Read [CONTRIBUTING.md](CONTRIBUTING.md) for the full rules a public skill must follow.

## Core rules

- Public product skills live under `skills/`, named `aiwerk-<what-it-does>`, matching their folder name, with `license: Apache-2.0` and an untrusted-data rule. Every new public skill needs a row in `README.md` and (when it writes to the brain) an eval case in `evals/run_evals.py` plus stand-in coverage in `tests/fake_agent.py` and `tests/test_evals_runner.py`.
- Repo-local maintainer skills live under `.claude/skills/` and are NOT part of the public `skills/` catalog. Keep `.agents/skills/` out of git (it is locally excluded in `.git/info/exclude` for personal workspace skills).
- The brain format is defined in `skills/aiwerk-init/assets/brain/SCHEMA.md`. Keep `skills/aiwerk-refresh/scripts/brain_status.py`, the brain template (`skills/aiwerk-init/assets/brain/`), and the evals in sync with it.
- Do not add network calls, downloads, or third-party dependencies to skills or scripts.
- Keep GitHub Actions `uses:` lines in `.github/workflows/` and `recipes/github-actions/` pinned to full 40-character commit SHAs, using identical SHAs across workflows and recipes.
- Keep `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` versions in sync.
- Write plainly. **No em dashes** in docs, skills, or commit messages.

## Required checks before opening a PR

Run all of these locally before committing or opening a pull request:

```bash
python3 scripts/validate_skills.py
python3 skills/aiwerk-refresh/scripts/brain_status.py skills/aiwerk-init/assets/brain --template --strict
python3 -m unittest discover -s tests -v
bash tests/test_install.sh
shellcheck install.sh tests/test_install.sh
```

To see which agent eval cases CI will run for your branch:

```bash
python3 evals/select_eval_cases.py --event pull_request --base-sha origin/main --head-sha HEAD
```

## Branches, PRs, and CI rulesets

- Never push directly to `main`. Branch from up-to-date `origin/main`, open a PR, and squash merge.
- `main` enforces GitHub rulesets requiring PRs, resolved review threads, and four required status checks:
  - `Skills, brain and unit tests`
  - `Installer on ubuntu-latest`
  - `Installer on macos-latest`
  - `Scan` (NVIDIA SkillSpector static scan; every skill in `skills/` must be `SAFE`)
- Update `CHANGELOG.md` under `## [Unreleased]` whenever files under `skills/` change (or apply the `no-changelog` label if an exemption is intentional).
- **Agent evals (`evals.yml`):** On pull requests and pushes, `evals/select_eval_cases.py` runs only changed skill cases, or the 3-case smoke set (`init`, `review`, `skill-audit`) when shared eval, installer, or brain files change. Scheduled weekly runs and empty manual dispatches run all cases. Note that `GitHub Copilot CLI` is non-required and can fail if the repository secret `COPILOT_GITHUB_TOKEN` hits its monthly quota; check failure logs before treating it as a skill regression.

## Cross-repo coupling with `AnPod/Aiwerk`

The marketing site repository (`AnPod/Aiwerk`, local sibling `../Aiwerk`) pins a commit of this repo via `FACTORY_SHA` in `.github/workflows/pr-checks.yml` and runs `scripts/check-site-facts.mjs` against:
- The count of `skills/*/SKILL.md` directories (currently 23)
- Accepted harnesses and flags in `install.sh`
- `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`

Whenever you add/remove public skills, change accepted harnesses or CLI flags in `install.sh`, or rename plugin identifiers, check `../Aiwerk` and coordinate a follow-up sync PR there.

## Repo-local skills

Maintainer skills for working in this repository live in `.claude/skills/`:

| Skill | When to use |
|---|---|
| `verify-repo` | Running the full local verification suite, checking eval selection, and checking `Aiwerk` cross-repo fact drift before opening or updating a PR |
| `merge-pr` | Reviewing ruleset checks, distinguishing Copilot quota errors from regressions, and squash-merging a PR into `main` |
| `release-prep` | Cutting a new release across `CHANGELOG.md`, `.claude-plugin/` manifests, tags/releases, `recipes/github-actions/` `AIWERK_REF`, and `AnPod/Aiwerk` `FACTORY_SHA` |
