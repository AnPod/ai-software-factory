# Providers by SDLC stage

Snapshot from November 2026. Vendors add and retire MCP servers and CLIs often, so treat this as a starting point and confirm in the vendor's docs before recommending one.

Legend: **official** = published by the vendor. **partial** = preview, community-maintained or limited. **none** = nothing found. CLI names are what `command -v` should look for.

## 01 Intake and context

| Provider | CLI | MCP | Notes |
|---|---|---|---|
| Atlassian Jira, Confluence | `acli` (official) | Atlassian Remote MCP (official) | Specs, wikis |
| Linear | none | Linear MCP (official) | Specs |
| Slack | none | Slack MCP (official) | Intake and notifications |
| GitHub | `gh` (official) | GitHub MCP (official) | Issues, PRs, Actions |
| GitLab | `glab` (official) | GitLab MCP (partial) | Issues, MRs, CI |
| Notion | none | Notion MCP (official) | Docs |
| Atlan | none | Hosted MCP (official) | Catalog, lineage |
| DataHub | `datahub` (official) | `mcp-server-datahub` (official) | Catalog, lineage |
| Alation | none | Agent SDK / MCP (partial) | Catalog |
| Unity Catalog | `databricks` (official) | Databricks managed MCP (partial, preview) | Catalog |

## 02 Orchestration: agents, labs, sandboxes

| Provider | CLI | MCP | Notes |
|---|---|---|---|
| Anthropic Claude Code | `claude` (official) | client | Headless: `claude -p` |
| OpenAI Codex | `codex` (official) | client | Headless: `codex exec` |
| Google Gemini CLI | `gemini` (official) | client | Headless: `gemini -p` |
| OpenCode | `opencode` (official) | client | Headless: `opencode run` |
| Pi | `pi` (official) | via extensions | Headless: `pi -p` |
| Factory Droid | `droid` (official) | client | Headless: `droid exec` |
| Cursor | `cursor-agent` (official) | client | Background agents API |
| Cognition Devin | Devin for Terminal (official) | partial | Devin API for async tasks |
| Warp | Warp Agent CLI (official) | client | |
| Poolside | Poolside Agent CLI (official) | none | |
| Windsurf | none | client | IDE only |
| Mistral AI | `vibe` (partial) | client | Models also usable via OpenCode or Pi |
| Meta Llama | none | none | Model only, run through an open harness |
| E2B | `e2b` (official) | E2B MCP (official) | Sandboxes |
| Daytona | `daytona` (official) | Daytona MCP (official) | Sandboxes |
| Modal | `modal` (official) | partial | Sandboxes via SDK |
| Vercel Sandbox | `vercel` (official) | Vercel MCP (official) | Sandboxes |
| Cloudflare Sandbox SDK | `wrangler` (official) | Cloudflare MCP (official) | Sandboxes |
| Runloop | partial | partial | Devboxes |
| Northflank | `northflank` (official) | partial | Sandboxes |
| CodeSandbox | partial | none | SDK |

## 03 Eval and governance

| Provider | CLI | MCP | Notes |
|---|---|---|---|
| Snyk | `snyk` (official) | Snyk MCP (official) | Code, dependencies, containers |
| Semgrep | `semgrep` (official) | Semgrep MCP (official) | SAST |
| GitGuardian | `ggshield` (official) | GitGuardian MCP (official) | Secrets |
| Socket | `socket` (official) | Socket MCP (official) | Supply chain |
| Wiz | `wizcli` (official) | Wiz MCP (official) | Cloud posture, IaC |
| Endor Labs | `endorctl` (official) | partial | SCA |
| Chainguard | `chainctl` (official) | none | Hardened images |
| NVIDIA SkillSpector | `skillspector` (official) | SkillSpector MCP (official) | Scans agent skills |

## 04 Release, cloud and data

| Provider | CLI | MCP | Notes |
|---|---|---|---|
| AWS | `aws` (official) | AWS MCP servers (official) | |
| Microsoft Azure | `az` (official) | Azure MCP (official) | |
| Google Cloud | `gcloud` (official) | MCP Toolbox (official) | |
| Databricks | `databricks` (official) | Managed MCP (partial, preview) | |
| Snowflake | `snow` (official) | Managed MCP (official) | Labs MCP deprecated |
| dbt | `dbt` (official) | `dbt-mcp` (official) | |
| BigQuery | `bq` (official) | MCP Toolbox (official) | |
| Microsoft Fabric | `fab` (official) | Fabric MCP (partial) | |
| Apache Iceberg | `pyiceberg` (partial) | none | Reached through the query engine |

## 05 Operations

| Provider | CLI | MCP | Notes |
|---|---|---|---|
| Datadog | `datadog-ci` (official) | Datadog MCP (official) | |
| Grafana | partial | `mcp-grafana` (official) | |
| PagerDuty | `pd` (partial) | PagerDuty MCP (official) | Sends pages: default consent `ask` |
| Sentry | `sentry-cli` (official) | Sentry MCP (official) | |
| Splunk | partial | Splunk MCP (official) | |
| Prometheus | `promtool` (official) | partial | |
| OpenTelemetry | none | none | Reached through the backend that stores the data |
| Traversal | none | none | Web and Slack product, ask the vendor |
| Resolve.ai | none | none | Web and Slack product, ask the vendor |
