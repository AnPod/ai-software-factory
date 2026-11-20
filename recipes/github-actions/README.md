# GitHub Actions recipes

Example workflows that run AI Werk Skills headless in GitHub Actions with either GitHub Copilot CLI (`copilot -p`) or Claude Code (`claude -p`).

## Workflows

| File | Trigger | Skills run | Output |
|---|---|---|---|
| `issue-intake-and-spec.yml` | Issue labelled `aiwerk:spec` and opened by the owner, a member or a collaborator (or manual dispatch) | `aiwerk-intake`, `aiwerk-spec` | `.aiwerk/brain/specs/GH-<n>/ticket.md` and `spec.md` uploaded as an artifact |
| `pr-governance-gates.yml` | Same-repository pull request (or manual dispatch) | `aiwerk-review`, `aiwerk-test-gate`, `aiwerk-security-gate`, `aiwerk-policy` | `.aiwerk/brain/specs/PR-<n>/` gate pages uploaded as an artifact and summarised in the job summary |

## How to use

1. Copy the workflow you want into your project's `.github/workflows/` folder.
2. Set `AIWERK_REF` to the full commit SHA of the `AnPod/ai-software-factory` release you reviewed. A tag can be moved later; a commit cannot.
3. Add one (or both) repository secrets under **Settings > Secrets and variables > Actions**:
   - `COPILOT_GITHUB_TOKEN`: fine-grained personal access token with the **Copilot Requests** permission.
   - `ANTHROPIC_API_KEY`: Anthropic API key for Claude Code. Use a key only for this workflow, with a low spend limit.
4. In `pr-governance-gates.yml`, set `TEST_COMMAND` and `LINT_COMMAND` to your project's commands.
5. Make sure your project already has `.aiwerk/brain/` initialised (run `aiwerk-init`, `aiwerk-landscape` and `aiwerk-survey` once and commit `.aiwerk/brain/`).

## What the workflows do to limit risk

- **Read-only repository access.** Both workflows use `permissions: contents: read` (plus `issues: read` to fetch the issue). Checkouts keep no git credentials on disk. The workflows never commit, push or merge.
- **Secrets are checked in a gate job.** GitHub does not allow `secrets` in a job's `if:`, so a first job checks which keys are set and the agent jobs depend on it.
- **The agent writes only `.aiwerk/brain/`.** Copilot CLI gets `write(.aiwerk/brain/**)`. Claude Code runs in `dontAsk` mode, which denies every tool call that no rule allows, with `Edit(.aiwerk/brain/**)` (Edit rules also cover the Write tool). Claude Code may not read `/proc`.
- **No interpreters or project code for the agent.** The agent may read files in the checkout and run a few read-only commands (`git status`, `git log`, `git diff`, `git show`, `git rev-parse`, `git branch`, `git ls-files`, `ls`, `date`, `mkdir`, `wc`). Both may run the brain checker by its exact path (it is executable; Copilot CLI matches `python3` by name only, so `python3` itself stays denied). There is no `python3`, `node`, `make`, `pytest`, `find`, `cp` or `cat` rule, and blocking `curl` alone would not help while an interpreter is allowed.
- **Tests run without keys.** `pr-governance-gates.yml` runs your test and lint commands in a separate job that has no API key, and hands the output to the agent jobs as an artifact. That job fails when tests or lint fail, so the pull request shows it; the agent jobs still run and report on the failure.
- **Only the pinned skills steer the agent.** Before the run, the workflow deletes agent configuration that came with the checkout (`.claude/`, `.agents/`, `.copilot/`, `.mcp.json`, `.vscode/mcp.json`, `.github/hooks`, `.github/skills`, `.github/agents`), so a branch cannot add hooks, MCP servers or its own copy of a skill. Claude Code loads no project settings or MCP servers (`--setting-sources user --strict-mcp-config`), and on pull requests Copilot CLI loads no custom instructions (`--no-custom-instructions`).
- **Skill files and git config are read-only for the agent.** The installed skills, `.git/config` and `.git/hooks` are made read-only before the agent starts, and deny rules block writes to `.git/`, `.github/` and the skill folders.
- **The agent cannot change later steps.** The agent command runs without `GITHUB_ENV`, `GITHUB_PATH`, `GITHUB_OUTPUT`, `GITHUB_STEP_SUMMARY` and `GITHUB_STATE`, and later steps run Python with `-I` so files in the checkout cannot be imported. The job summary shows only known verdict words (`pass`, `pass with fixes`, `gaps`, `warn`, `needs-approval`, `fail`), never free text from the agent.
- **Untrusted issue authors do not trigger runs.** A labelled issue runs automatically only when its author is the owner, a member or a collaborator. HTML comments, which GitHub does not show, are removed before the agent sees the text.
- **Leaked keys are not uploaded.** Before any upload, the workflow searches the agent's output for the exact API key and runs the brain checker's credential scan. A match, or an error while searching, stops the upload. Artifacts are kept for 7 days.
- **No secrets on fork pull requests.** `pr-governance-gates.yml` runs only for pull requests from the same repository. Dispatch inputs are checked against strict patterns.
- **Pinned versions.** Every action is pinned to a commit SHA. Update `COPILOT_CLI_VERSION` and `CLAUDE_CODE_VERSION` deliberately, picking releases at least two weeks old.

## What is still your risk

An agent that reads text written by someone else can be steered by that text (prompt injection). The limits above make it hard to turn that into stolen keys or changed code, but they cannot rule it out. Before you run a workflow on someone else's issue, read the raw text, including anything hidden. Give the workflow keys that you can rotate quickly and that have spend limits.
