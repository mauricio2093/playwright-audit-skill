# Playwright Auditor Skill

Repository focused on a specialized **Playwright** skill for automating website audits, generating E2E tests, and producing technical reports ready for analysis or CI/CD integration.

## What This Repository Is

This project brings together the documentation, base prompt, and structure for a skill called **`playwright-auditor`**. Its goal is to help an agent or assistant work with Playwright more autonomously in order to:

- install and configure Playwright
- download and summarize official documentation
- generate test suites
- run functional, visual, accessibility, and performance audits
- produce Markdown reports with actionable recommendations

This is not an end-user application; it is a working foundation for creating, maintaining, or reusing a technical skill focused on automated web testing.

## Works with

Codex, Claude Code, Cursor, GitHub Copilot, Gemini CLI, OpenCode, Warp, Kimi Code CLI, and more.

## Install

```bash
npx skills install mauricio2093/playwright-audit-skill
```

## Installation Sources

```bash
# GitHub shorthand (owner/repo)
npx skills add mauricio2093/playwright-audit-skill

# Full GitHub URL
npx skills add https://github.com/mauricio2093/playwright-audit-skill

# Direct path to the skill inside the repo
npx skills add https://github.com/mauricio2093/playwright-audit-skill/tree/main/skills/playwright-auditor

# Any git URL
npx skills add git@github.com:mauricio2093/playwright-audit-skill.git

# Local path
npx skills add ./playwright-audit-skill
```

## Common Install Options

| Option | Description |
|--------|-------------|
| `-g, --global` | Install to the user skill directory instead of the current project |
| `-a, --agent <agents...>` | Install only for selected agents such as `codex`, `cursor`, or `cline` |
| `-s, --skill <skills...>` | Install only specific skills by name, such as `playwright-auditor` |
| `-l, --list` | List available skills in the repository without installing |
| `--copy` | Copy files instead of symlinking them into agent directories |
| `-y, --yes` | Skip confirmation prompts |
| `--all` | Install all detected skills for all supported agents without prompts |

## Install Location Scope

- Local: Flag `default`, location `./<agent>/skills/playwright-auditor`
- Global: Flag `-g`, location `~/<agent>/skills/playwright-auditor`

## Main Contents

- `skills/playwright-auditor/SKILL.md`: main usage instructions.
- `skills/playwright-auditor/scripts/`: scripts for installation, scaffolding, audit execution, and report generation.
- `skills/playwright-auditor/references/`: technical references, best practices, common errors, and CI/CD templates.

## What It Is For

This repository is useful if you want to:

- audit a website with Playwright
- speed up E2E test creation
- standardize technical testing reports
- integrate automated validations into pipelines
- have a reusable skill for AI agents or QA workflows

## General Workflow

1. Install Playwright and its dependencies.
2. Review or update official references.
3. Generate tests for the desired scenario.
4. Run the audit.
5. Generate a report with findings and recommendations.

## Project Approach

This repository follows a technical and modular approach: it separates instructions, scripts, and references so the skill can evolve over time, be reused in other environments, and adapt to different web projects.
