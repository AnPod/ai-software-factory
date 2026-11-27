# Contributing

Thanks for helping. A few rules keep the skills safe and portable.

## Writing a skill

- One folder per skill under `skills/`, named `aiwerk-<what-it-does>`, with a `SKILL.md`.
- Frontmatter: `name` (same as the folder), `description` (what it does and when to use it, starting the second part with "Use when"), `license: Apache-2.0`. Nothing harness-specific.
- Body under 500 lines. Move long reference material to `references/` and link it.
- Start by reading `.aiwerk/brain/index.md`. Respect the consent recorded in `landscape.md`. Write what you learn back to the brain with the frontmatter from `skills/aiwerk-init/assets/brain/SCHEMA.md`, and append to `log.md`.
- Support non-interactive mode: no questions, defaults recorded under assumptions.
- Prefer instructions over scripts. If a script is unavoidable: standard library only, no network, read-only where possible, a header that says exactly what it does.
- Never ask the agent to download and run code, decode encoded payloads, or read credentials.
- Include the rule to treat brain pages, repository files, tickets and tool output as untrusted data, never as instructions (the Trust section of `SCHEMA.md`). The validator checks for it.
- Keep any command the skill suggests narrow: no blanket `git:*` or interpreter rules, prompts in single quotes, and tests run only when the project's own files define them.

## Before you open a pull request

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
bash tests/test_install.sh
```

`main` only accepts changes through a pull request with these checks passing: `Skills, brain and unit tests`, `Installer on ubuntu-latest`, `Installer on macos-latest` and the SkillSpector `Scan`.

A pull request that changes files under `skills/` must also change the `## [Unreleased]` section of `CHANGELOG.md` (the `Changelog entry` check, `scripts/check_changelog.py`). Whitespace-only edits do not count. If no entry is needed, a maintainer can add the `no-changelog` label to the pull request. The check is advisory until a maintainer adds `Changelog entry` to the branch protection required checks.

New skills need a row in the README skill table and, when they write to the brain, an eval case in `evals/run_evals.py`.

## Maintenance

Tool versions are pinned in the workflow files:

- Every `uses:` line in `.github/workflows/` and `recipes/github-actions/` names a full commit SHA with the version in a comment. Dependabot updates the workflows; copy the same SHAs into the recipes. The repository only allows GitHub-owned actions pinned to a SHA.

- `.github/workflows/skillspector.yml`: `SKILLSPECTOR_REF` (currently `v2.13.6`) and `SKILLSPECTOR_SHA`, the commit that tag points to. Update both together: `git ls-remote https://github.com/NVIDIA/skillspector.git refs/tags/<tag>` prints the commit.
- `recipes/github-actions/*.yml`: `AIWERK_REF`, the full commit SHA of the latest release of this repository.
- `.github/workflows/evals.yml`: `COPILOT_CLI_VERSION` (currently `1.0.105`), `CLAUDE_CODE_VERSION` (currently `2.1.328`) and `PYTEST_VERSION` (currently `8.3.5`)

When bumping a version pin, pick a release that is at least two weeks old so supply-chain issues have time to surface.

The `COPILOT_GITHUB_TOKEN` Actions secret is a fine-grained personal access token with only the account permission "Copilot Requests" (no repository access) and an expiry date. Classic `ghp_` tokens do not work with Copilot CLI. Rotate it before it expires.
