# Changelog

All notable changes to AI Werk Skills are recorded here.

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
