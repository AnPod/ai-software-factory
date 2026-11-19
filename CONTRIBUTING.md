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
