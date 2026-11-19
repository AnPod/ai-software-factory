# Changelog

All notable changes to AI Werk Skills are recorded here.

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
