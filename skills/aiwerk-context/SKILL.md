---
name: aiwerk-context
description: Assemble the smallest set of files, docs, commands and allowed data-catalog entries an agent needs to implement a spec, within a strict 25-entry budget. Writes .aiwerk/brain/specs/<id>/context.md. Use after aiwerk-spec or before planning and dispatching implementation tasks.
license: Apache-2.0
---

# aiwerk-context

Build a compact, high-signal context pack for one spec so implementing agents read only what they need and stay within budget.

## Rules

- Read-only on the repository. Write only inside `.aiwerk/brain/`.
- Check `.aiwerk/brain/aiwerk.md` first. If stage 01 (`01 Intake and context`) is `off`, say so and stop unless the user explicitly tells you to proceed anyway.
- Respect `.aiwerk/brain/landscape.md`: query data catalogs (Atlan, DataHub, Alation, Unity Catalog) or external docs only if marked `read` or `write`. Ask for `ask`. Never query `denied` or `not-asked` sources.
- Enforce a hard budget of **at most 25 entries total** across files, docs, commands and external/lineage references combined.
- Never install tools, read files outside the project folder, copy secret values or edit `## Human notes` sections.
- In non-interactive mode ("non-interactive", "CI", "use defaults"), ask nothing, skip `ask` sources and record assumptions under `## Assumptions`.

## Step 1: Read the brain

Read:

1. `.aiwerk/brain/index.md`, `.aiwerk/brain/aiwerk.md` and `.aiwerk/brain/landscape.md`.
2. `.aiwerk/brain/specs/<id>/spec.md` (if missing, tell the user to run `aiwerk-spec` first and stop).
3. `.aiwerk/brain/project/commands.md`, `architecture.md`, `conventions.md` and `.aiwerk/brain/decisions/index.md` (when present).

If `specs/<id>/context.md` already exists, preserve its `## Human notes` section.

## Step 2: Select minimal entries (max 25)

Start from the affected modules and constraints in `spec.md` and verify every path exists in the current commit (`git rev-parse --short HEAD`, `git branch --show-current`):

1. **Code files:** files directly modified by the spec plus direct callers, interfaces or types they depend on.
2. **Test files:** existing test files covering those modules and fixtures they use.
3. **Docs and decisions:** ADRs, README sections, brain pages or policies that constrain the implementation.
4. **Commands:** exact build, test and lint commands from `project/commands.md` needed to verify the change.
5. **Data lineage and catalog entries:** only if the spec touches data models/pipelines and a catalog source is allowed (`read` or `write`) in `landscape.md`.

Count every entry across all sections. If the count exceeds 25, drop lower-priority files first (generated files, unrelated modules, indirect references) and note what was excluded and why. Every kept entry must state **why it matters** for this spec in one concise phrase.

## Step 3: Write `.aiwerk/brain/specs/<id>/context.md`

Use all seven frontmatter fields from `SCHEMA.md`:

```markdown
---
title: "<id> context pack"
kind: spec/context
gathered_at: <now, UTC ISO 8601>
gathered_by: aiwerk-context
sources:
  - file:.aiwerk/brain/specs/<id>/spec.md
  - file:.aiwerk/brain/project/commands.md
  - git:<branch>@<commit>
ttl_days: 7
confidence: high
---

# <id> context pack

Budget: **<N> / 25 entries**

## Files and docs

| # | Category | Path | Why it matters |
|---|---|---|---|
| 1 | code | `src/...` | <one-line reason> |
| 2 | test | `tests/...` | <one-line reason> |
| 3 | doc | `docs/adr/...` | <one-line reason> |

## Commands

| # | Command | Source | Why it matters |
|---|---|---|---|
| 4 | `make test` | `Makefile` | Verify acceptance criteria and prevent regressions |

## Data lineage and external context
- <Allowed catalog entries numbered within the 25-entry budget, or "none">

## Excluded
- <Files or sources intentionally left out to stay minimal, or "none">

## Assumptions
- <defaults used, or "none">

## Human notes
<!-- Skills never edit this section. -->
```

## Step 4: Update index and log

- Add or update the `specs/<id>/context.md` row in `.aiwerk/brain/index.md`. In the frontmatter of `index.md`, change only `gathered_at` and keep the other six fields exactly as they are.
- Append one line to `.aiwerk/brain/log.md`: `<now> | aiwerk-context | <created|updated> specs/<id>/context.md | <N>/25 entries`.

## Step 5: Check your work

If `python3` is available, run the brain checker that ships with the `aiwerk-refresh` skill, from the project root. `<skills folder>` is the folder that contains this skill's folder:

```bash
python3 <skills folder>/aiwerk-refresh/scripts/brain_status.py .aiwerk/brain --strict
```

Fix every problem it reports, for example a missing frontmatter field or a page missing from `index.md`, and run it again until it reports 0 problems. If Python or `aiwerk-refresh` is not available, check by hand that every page you wrote or changed, `index.md` included, has all seven frontmatter fields from `SCHEMA.md` and a row in `index.md`.

## Step 6: Report

In under 8 lines: report the entry count (`N / 25`), highlight the key files and verification command, and suggest `aiwerk-plan` next to split the spec into tasks.
