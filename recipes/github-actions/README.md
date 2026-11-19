# GitHub Actions recipes

Example workflows that run AI Werk Skills headless in GitHub Actions with either GitHub Copilot CLI (`copilot -p`) or Claude Code (`claude -p`).

## Workflows

| File | Trigger | Skills run | Output |
|---|---|---|---|
| `issue-intake-and-spec.yml` | Issue labelled `aiwerk:spec` (or manual dispatch) | `aiwerk-intake`, `aiwerk-spec` | `.aiwerk/brain/specs/GH-<n>/ticket.md` and `spec.md` uploaded as an artifact and summarised in the job summary |
| `pr-governance-gates.yml` | Same-repository pull request (or manual dispatch) | `aiwerk-review`, `aiwerk-test-gate`, `aiwerk-security-gate`, `aiwerk-policy` | `.aiwerk/brain/specs/PR-<n>/` gate pages uploaded as an artifact and summarised in the job summary |

## How to use

1. Copy the workflow you want into your project's `.github/workflows/` folder.
2. Pin `AIWERK_REF` to a tagged release of `AnPod/softwarefactory` (for example `v0.4.0`).
3. Add one (or both) repository secrets under **Settings > Secrets and variables > Actions**:
   - `COPILOT_GITHUB_TOKEN`: fine-grained personal access token with the **Copilot Requests** permission.
   - `ANTHROPIC_API_KEY`: Anthropic API key for Claude Code.
4. Make sure your project already has `.aiwerk/brain/` initialised (run `aiwerk-init`, `aiwerk-landscape` and `aiwerk-survey` once and commit `.aiwerk/brain/`).

## Safety defaults

- **Read-only repository permissions:** both workflows use `permissions: contents: read`. They never commit, push or merge directly.
- **Narrow tool allowlists:** tool rules match `evals/run_evals.py` (`COPILOT_TOOLS`, `COPILOT_DENY` and `CLAUDE_TOOLS`). Broad flags such as `--dangerously-skip-permissions` or `--allow-all` are never used.
- **No shell injection from issue text:** issue titles and bodies are passed through environment variables into a file rather than interpolated directly into shell scripts.
- **No secrets on fork PRs:** `pr-governance-gates.yml` runs only when the pull request comes from the same repository (`github.event.pull_request.head.repo.full_name == github.repository`).
- **Pinned CLI versions:** update `COPILOT_CLI_VERSION` and `CLAUDE_CODE_VERSION` deliberately, picking releases at least two weeks old.
