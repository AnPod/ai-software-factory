# Working in this repository

This repo contains Agent Skills (`skills/*/SKILL.md`), an installer, tests and evals. Read CONTRIBUTING.md for the rules a skill must follow.

- Skill names start with `aiwerk-` and match their folder.
- The brain format is defined in `skills/aiwerk-init/assets/brain/SCHEMA.md`. Keep `brain_status.py`, the template and the evals in sync with it.
- Run `python3 scripts/validate_skills.py`, `python3 -m unittest discover -s tests` and `bash tests/test_install.sh` before committing.
- Do not add network calls, downloads or dependencies to skills or scripts.
- Write plainly. No em dashes in docs or skills.
