# Security policy

Agent skills run with the permissions of the coding agent that loads them. We treat a skill that misleads an agent the same way we treat a vulnerability in code.

## Report a problem

Use GitHub's private vulnerability reporting: **Security** tab, then **Report a vulnerability**. Please do not open a public issue for security problems.

Include the skill and file, what an agent could be led to do, and how to reproduce it. We aim to acknowledge reports within three working days.

## In scope

- Instructions that could make an agent leak data, read or send secrets, or act outside what the user approved
- Prompt-injection paths, for example a skill trusting text from a ticket, web page or MCP response as instructions
- `install.sh` or `brain_status.py` doing anything beyond what their headers describe
- Gaps in the CI checks that would let one of the above through

## What we already do

- Every pull request, push to `main`, weekly run and release is scanned with NVIDIA SkillSpector (static analysis, no LLM stage, pinned version). Reports are attached to each workflow run and release.
- `scripts/validate_skills.py` rejects risky shell patterns, binary files and broken links in skills.
- Agent evals check that skills write nothing outside `.aiwerk/`, never copy secrets from MCP configuration, and change nothing in report-only mode.

A clean scan is evidence, not proof. Read the skills you install.
