---
name: aiwerk-landscape
description: Map which tools the coding agents in this project can reach, such as MCP servers, CLIs, plugins, connectors, browser and computer use, place them on the SDLC stages, and ask the user for consent per source before any of them is used. Writes .aiwerk/brain/landscape.md. Use after aiwerk-init, when the user asks which tools or integrations agents can use, when a new MCP server or CLI was added, or when landscape.md is stale.
license: Apache-2.0
---

# aiwerk-landscape

Find out what the agents can reach, decide with the user what they may use, and record it. Other aiwerk skills only use sources that this page marks as allowed.

## Rules

- This skill only looks. It does not install, connect or log in to anything, and it makes no API requests.
- Check whether a CLI exists with `command -v <name>`. Do not run the CLI itself.
- When reading MCP configuration files, record server names, transport and URL or command only. Never copy `env` values, headers, tokens or keys into the brain or into your reply.
- Never read files outside the project folder. User-level agent configuration can hold keys, so ask the user instead (Step 2).
- In non-interactive mode ("non-interactive", "CI", "use defaults"), record what you detected with consent `not-asked` and use nothing.

## Step 1: Read the brain

Read `.aiwerk/brain/index.md` and `.aiwerk/brain/aiwerk.md`. If the brain does not exist, tell the user to run `aiwerk-init` first, or continue with all stages treated as enabled if they prefer. If `landscape.md` exists, read it so you keep earlier consent decisions.

## Step 2: Detect

**MCP servers, project level.** Look for these files and list the servers they define:
`.mcp.json`, `.claude/settings.json`, `.cursor/mcp.json`, `.vscode/mcp.json`, `opencode.json`, `.codex/config.toml`, `.gemini/settings.json`, `.factory/mcp.json`.

**Tools in this session.** List the MCP servers, connectors and plugins that you, the running agent, can call right now, and whether you have browser or computer-use tools. This covers servers the user configured globally, without opening their configuration files.

**MCP servers, user level.** Do not read them. If the user uses other harnesses too, ask them to run that harness's own list command (for example `claude mcp list`, `codex mcp list` or `opencode mcp list`) and paste only the server names.

**CLIs.** Check with `command -v` for the CLIs listed in [references/providers.md](references/providers.md), plus `git`, `docker`, `kubectl`, `terraform`.

**Other signals.** CI files, `Dockerfile`, `.devcontainer/`, infrastructure code (`*.tf`, Helm charts, Kubernetes manifests). Never open credential files or cloud login folders; if you notice one in the project, note its presence as a risk in `landscape.md`, without reading it.

## Step 3: Map to stages

Use [references/providers.md](references/providers.md) to place each source on the stage where agents would use it. One source can serve several stages. Mark the providers list as a snapshot: if the user asks whether a vendor offers an MCP server or CLI that you did not detect, check the vendor's own documentation when you have web access, and say when you could not check.

## Step 4: Ask for consent

Only for sources relevant to stages that `aiwerk.md` enables. Group the questions by stage, at most three questions at a time. For each source offer:

- `read`: agents may read from it.
- `write`: agents may also create or change things in it (comments, tickets, branches).
- `ask`: agents must ask each time.
- `denied`: agents must not use it.

Default to `read` for code hosts and observability, `ask` for anything that sends messages to people (Slack, email, PagerDuty) or touches production.

## Step 5: Find gaps

For each enabled stage with no allowed source, say what is missing and list two or three options from the providers reference with their kind (MCP, CLI, plugin). Explain how the user would add one (the vendor's official MCP server or CLI install page), but do not install or configure anything. The user decides.

## Step 6: Write `.aiwerk/brain/landscape.md`

```markdown
---
title: Tool landscape
kind: landscape
gathered_at: <now, UTC ISO 8601>
gathered_by: aiwerk-landscape
sources:
  - file:.mcp.json
  - cli:command -v
  - interview
ttl_days: 30
confidence: medium
---

# Tool landscape

## Sources
| Source | Kind | Stages | Detected in | Consent | Notes |
|---|---|---|---|---|---|
| GitHub | mcp + cli (gh) | 01, 02, 04 | .mcp.json, PATH | read | |

## Browser and computer use
- <available or not, and consent>

## Gaps
| Stage | Missing | Options |
|---|---|---|

## Human notes
<!-- Skills never edit this section. -->
```

Consent values: `read`, `write`, `ask`, `denied`, `not-asked`. Keep earlier decisions unless the user changed them.

## Step 7: Update index and log, then hand over

- Add or update the `landscape.md` row in `.aiwerk/brain/index.md`.
- Append to `.aiwerk/brain/log.md`: `<now> | aiwerk-landscape | <created|updated> landscape.md | <n> sources, <n> allowed`.
- Summarise in a few lines: what is connected, what is allowed, the biggest gap. Suggest `aiwerk-survey` next if the project has not been surveyed.
