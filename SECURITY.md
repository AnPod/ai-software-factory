# Security policy

Agent skills run with the permissions of the coding agent that loads them. We treat a skill that misleads an agent the same way we treat a vulnerability in code.

## Report a problem

Use GitHub's private vulnerability reporting: **Security** tab, then **Report a vulnerability**. Please do not open a public issue for security problems.

Include the skill and file, what an agent could be led to do, and how to reproduce it. We aim to acknowledge reports within three working days.

## In scope

- Instructions that could make an agent leak data, read or send secrets, or act outside what the user approved
- Prompt-injection paths, for example a skill trusting text from a ticket, web page or MCP response as instructions
- `install.sh`, `brain_status.py` or `scripts/merge_sarif.py` doing anything beyond what their headers describe
- Gaps in the CI checks that would let one of the above through

## What we already do

- Every pull request, push to `main`, weekly run and release is scanned with NVIDIA SkillSpector (static analysis, no LLM stage, pinned to a commit). Reports are attached to each workflow run and release, and non-PR runs upload findings to code scanning.
- CodeQL, secret scanning with push protection, and Dependabot alerts and security updates are on.
- `scripts/validate_skills.py` rejects risky shell patterns, binary files, symbolic links, links that leave the skill folder, and skills without the untrusted-data rule.
- Workflows default to read-only tokens, keep no git credentials, and use only GitHub-owned actions pinned to a commit. Narrow write permissions are granted only to separate post-scan jobs in `skillspector.yml` (`security-events: write` for non-PR SARIF uploads, and `contents: write` to attach reports to published releases). `main` accepts changes only through pull requests whose checks pass. Workflow runs from outside contributors need approval.
- Agent evals check that skills write nothing outside `.aiwerk/`, never copy secrets from MCP configuration, and change nothing in report-only mode. The eval agent gets a filtered environment and narrow tool rules. Raw transcripts stay on the runner; CI stages and uploads only `results.json` and `summary.md` after symlink and key checks pass.

A clean scan is evidence, not proof. Read the skills you install.
