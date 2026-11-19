# AI Werk Skills

**Set up a software factory inside the coding agent you already use.**

[![CI](https://github.com/AnPod/softwarefactory/actions/workflows/ci.yml/badge.svg)](https://github.com/AnPod/softwarefactory/actions/workflows/ci.yml)
[![SkillSpector scan](https://github.com/AnPod/softwarefactory/actions/workflows/skillspector.yml/badge.svg)](https://github.com/AnPod/softwarefactory/actions/workflows/skillspector.yml)
[![Agent evals](https://github.com/AnPod/softwarefactory/actions/workflows/evals.yml/badge.svg)](https://github.com/AnPod/softwarefactory/actions/workflows/evals.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Agent Skills standard](https://img.shields.io/badge/format-Agent%20Skills-black.svg)](https://agentskills.io)

AI Werk Skills is a set of plain-Markdown [Agent Skills](https://agentskills.io) that turn Claude Code, GitHub Copilot CLI, Codex, OpenCode, Pi, Cursor, Gemini CLI or Factory Droid into a repeatable software delivery line. The skills interview your team, map which tools your agents can reach, ask before they touch anything, and keep a timestamped project memory (the *brain*) that every later step reads first.

No server, no database, no account. Clone it, link the skills, ask your agent to run `aiwerk-init`.

## Quick start

```bash
git clone https://github.com/AnPod/softwarefactory.git ~/aiwerk-skills
cd your-project
~/aiwerk-skills/install.sh            # dry run: shows what it would link
~/aiwerk-skills/install.sh --apply    # links the skills into .claude/skills and .agents/skills
```

Then, in your coding agent:

> Use the aiwerk-init skill to set up the software factory for this project.

Other harnesses: `--harness copilot,opencode,cursor,gemini,droid` or `--harness all`. Install for every project with `--scope user`. Remove with `--uninstall --apply`.

## How it works

```
 install ─▶ aiwerk-init ─▶ aiwerk-landscape ─▶ aiwerk-survey ─▶ stage skills ─▶ health
             interview      tools + consent     first full read   01 … 05
                 │                │                   │                │
                 └────────────────┴──────── .aiwerk/brain/ ◀───────────┘
                                  timestamped Markdown pages, read first, written back
```

1. **`aiwerk-init`** asks which harnesses you use, where work comes in (Slack, Jira, Confluence, Linear, GitHub), what may trigger an agent, which stages to switch on and how autonomous agents may be.
2. **`aiwerk-landscape`** finds the MCP servers, CLIs, plugins and browser tools your agents can reach, places them on the delivery stages and asks for your consent per source.
3. **`aiwerk-survey`** reads the project into the brain: stack, commands, architecture, owners, conventions and gaps, each with sources.
4. **Stage skills** (rolling out, see below) take work from intake to operations. Each reads the brain first and writes what it learns back.

### The brain

`.aiwerk/brain/` is a folder of Markdown pages, versioned with your code, readable by people and agents. Every page records when it was gathered, by which skill, from which sources and how long it stays valid:

```yaml
---
title: Payments service
kind: project/service
gathered_at: 2026-11-19T10:42:00Z
gathered_by: aiwerk-survey
sources:
  - git:main@27c54c6
  - mcp:atlassian/confluence:PAY
ttl_days: 14
confidence: medium
---
```

When a skill needs a page older than its `ttl_days`, it tells you its age and asks whether to refresh it. `aiwerk-refresh` checks the whole brain at once. The idea follows Andrej Karpathy's LLM Wiki pattern: a maintained knowledge base instead of re-discovering the project on every task.

## Skills

The stages follow a five-station delivery line. Stage skills are released in order.

| Skill | Stage | What it does | Status |
|---|---|---|---|
| `aiwerk-init` | Setup | Interview, factory settings, creates the brain | available |
| `aiwerk-landscape` | Setup | Maps MCP servers, CLIs and plugins to stages, asks consent per source | available |
| `aiwerk-survey` | 01 Intake and context | First full read of the project into the brain | available |
| `aiwerk-refresh` | Setup | Finds stale or broken knowledge and renews it with your approval | available |
| `aiwerk-readiness` | 01 Intake and context | Scores how ready the repository is for agents | available |
| `aiwerk-intake` | 01 Intake and context | Turns a Jira, Linear, Slack or GitHub item into a ticket | available |
| `aiwerk-spec` | 01 Intake and context | Writes a spec with acceptance criteria grounded in the brain | available |
| `aiwerk-context` | 01 Intake and context | Assembles the minimal context one task needs | available |
| `aiwerk-plan` | 02 Orchestration | Splits a spec into independent tasks | available |
| `aiwerk-dispatch` | 02 Orchestration | Runs tasks headless in the chosen harness | available |
| `aiwerk-sandbox` | 02 Orchestration | Runs a task in a worktree, container or sandbox service | available |
| `aiwerk-review` | 03 Eval and governance | Adversarial review of a diff against its spec | available |
| `aiwerk-test-gate` | 03 Eval and governance | Runs and extends tests, blocks regressions | available |
| `aiwerk-security-gate` | 03 Eval and governance | Runs the scanners you have (Snyk, Semgrep, GitGuardian, Socket, Wiz) | available |
| `aiwerk-policy` | 03 Eval and governance | Checks PII, licence and data rules from the brain | available |
| `aiwerk-release` | 04 Release | Release notes, version, PR description | planned |
| `aiwerk-deploy-check` | 04 Release | Pre-deploy checklist with rollback trigger | planned |
| `aiwerk-docs-sync` | 04 Release | Updates docs and brain after a merge | planned |
| `aiwerk-incident` | 05 Operations | Triage from Datadog, Sentry, PagerDuty, Grafana | planned |
| `aiwerk-incident-to-spec` | 05 Operations | Turns a resolved incident into a new spec | planned |
| `aiwerk-slo` | 05 Operations | Summarises SLOs and error budgets | planned |
| `aiwerk-health` | Meta | Stage rollout, brain freshness, connector coverage | planned |
| `aiwerk-skill-audit` | Meta | Scans every installed skill with SkillSpector | planned |

## Harness support

| Harness | Skill folder | Headless run |
|---|---|---|
| Claude Code | `.claude/skills` | `claude -p` |
| GitHub Copilot CLI | `.agents/skills` (also reads `.github/skills` and `.claude/skills`) | `copilot -p` |
| OpenAI Codex | `.agents/skills` | `codex exec` |
| OpenCode | `.opencode/skills` (also reads `.claude` and `.agents`) | `opencode run` |
| Pi | `.agents/skills` | `pi -p` |
| Cursor CLI | `.cursor/skills` | `cursor-agent -p` |
| Gemini CLI | `.gemini/skills` | `gemini -p` |
| Factory Droid | `.factory/skills` | `droid exec` |

Claude Code and GitHub Copilot CLI are tested end to end in CI. The others read the same `SKILL.md` format; reports from users are welcome.

## Safety

Skills run with your agent's permissions, so they deserve the same scrutiny as code. What this repository does about it:

- **Scanned.** Every pull request, every push to `main` and every release is scanned with [NVIDIA SkillSpector](https://github.com/NVIDIA/skillspector), static analysis for prompt injection, data exfiltration, credential access and other risky patterns. The report is attached to every run and release. A clean scan lowers risk; it does not prove a skill is safe, so read what you install.
- **Readable.** Skills are Markdown. The only script is a read-only Python checker (`aiwerk-refresh/scripts/brain_status.py`): standard library, no network, writes nothing.
- **Asks first.** Skills never install, connect or authenticate tools. `aiwerk-landscape` records your consent per source, and other skills only use what you allowed.
- **No secrets in the brain.** Skills record where knowledge came from, never tokens or keys. `brain_status.py` flags anything that looks like a credential.
- **Contained installer.** `install.sh` is a dry run unless you pass `--apply`, makes no network calls, only creates links or copies in skill folders, and never overwrites a folder it did not create.

Found a problem? See [SECURITY.md](SECURITY.md).

## Tests

Three layers, all in GitHub Actions:

| Workflow | What it checks | When |
|---|---|---|
| **CI** | Skill format (name, description, links, risky shell patterns), brain template, unit tests for the checker and the eval runner, installer end to end on Linux and macOS, ShellCheck | every push and PR |
| **SkillSpector scan** | Static security scan of all skills, SARIF and JSON reports | every push and PR, weekly, every release |
| **Agent evals** | Runs GitHub Copilot CLI and Claude Code with the skills on a sample project and checks what they wrote: required pages, valid frontmatter, nothing written outside `.aiwerk/`, no secrets copied from MCP config, report-only mode changes nothing | weekly, on demand, and on PRs that change skills |

Run locally:

```bash
python3 scripts/validate_skills.py
python3 -m unittest discover -s tests -v
bash tests/test_install.sh
COPILOT_GITHUB_TOKEN=... python3 evals/run_evals.py --harness copilot   # needs the copilot CLI
ANTHROPIC_API_KEY=... python3 evals/run_evals.py --harness claude       # needs the claude CLI
```

## Contributing

Issues and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) for how skills are written and tested.

## About

AI Werk Skills is maintained by [AI WERK](https://aiwerk.si), a software engineering consultancy in Ljubljana that builds governed software factories for engineering teams. These skills are the open, single-repository version of that work. Teams that want it across many repositories, with their own integrations, hardened access and a shared brain, sometimes ask us to set it up with them.

Licensed under the [Apache License 2.0](LICENSE).
