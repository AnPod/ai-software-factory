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

## Before you open a pull request

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
bash tests/test_install.sh
```

New skills need a row in the README skill table and, when they write to the brain, an eval case in `evals/run_evals.py`.

## Maintenance

Tool versions are pinned in the workflow files:

- `.github/workflows/skillspector.yml`: `SKILLSPECTOR_REF` (currently `v2.13.6`) and `SKILLSPECTOR_SHA`, the commit that tag points to. Update both together: `git ls-remote https://github.com/NVIDIA/skillspector.git refs/tags/<tag>` prints the commit.
- `recipes/github-actions/*.yml`: `AIWERK_REF`, the full commit SHA of the latest release of this repository.
- `.github/workflows/evals.yml`: `COPILOT_CLI_VERSION` (currently `1.0.105`), `CLAUDE_CODE_VERSION` (currently `2.1.328`) and `PYTEST_VERSION` (currently `8.3.5`)

When bumping a version pin, pick a release that is at least two weeks old so supply-chain issues have time to surface.

The `COPILOT_GITHUB_TOKEN` Actions secret is a fine-grained token with an expiry date. Rotate it before it expires.
