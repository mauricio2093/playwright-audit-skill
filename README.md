# Playwright Auditor Skill

Repository for a production-oriented **Playwright** skill that installs Playwright, scaffolds audits, runs browser-based checks, and exports technical artifacts for human review or CI/CD workflows.

## What This Repository Is

This project contains the documentation, packaged skill, scripts, and references for **`playwright-auditor`**.

Its purpose is to help an agent or assistant:

- install and validate Playwright in a predictable way
- fetch or reuse official Playwright documentation
- scaffold audit-oriented test suites
- run functional, accessibility, performance, and visual checks
- export JSON, HTML, and Markdown audit artifacts
- work more safely in shared repositories by using isolated audit workspaces

This is not a standalone end-user application. It is a reusable technical skill for agent-driven web testing and audit workflows.

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

- Local: flag `default`, location `./<agent>/skills/playwright-auditor`
- Global: flag `-g`, location `~/<agent>/skills/playwright-auditor`

## Main Contents

- `skills/playwright-auditor/SKILL.md`: main workflow and execution guidance
- `skills/playwright-auditor/scripts/install.sh`: validates Node.js/npm, installs Playwright, browser binaries, and a baseline config
- `skills/playwright-auditor/scripts/scaffold_tests.py`: generates audit-oriented Playwright specs
- `skills/playwright-auditor/scripts/run_audit.sh`: runs Playwright tests and summarizes artifacts
- `skills/playwright-auditor/scripts/run_isolated_audit.py`: performs isolated audits in a disposable workspace and exports final artifacts
- `skills/playwright-auditor/scripts/generate_report.py`: converts Playwright JSON results into Markdown, HTML, and JSON summaries
- `skills/playwright-auditor/references/`: best practices, common errors, CI templates, and Playwright API references
- `skills/playwright-auditor.skill`: packaged version of the skill

## What It Is For

This repository is useful if you want to:

- audit a website with Playwright instead of only static analyzers
- generate reusable E2E-style test suites quickly
- run targeted scenarios such as `smoke`, `a11y`, `visual`, or `full`
- keep audit artifacts organized for stakeholders or CI pipelines
- avoid polluting an existing project with temporary Playwright dependencies
- give an AI agent a more structured Playwright workflow

## Recommended Workflow

For real website audits, the preferred flow is:

1. Validate or install the Playwright environment.
2. Scaffold the tests for the target URL and scenario.
3. Run the audit in an isolated workspace.
4. Export the final artifacts.
5. Summarize failures, risks, and recommendations.

Recommended command:

```bash
python3 scripts/run_isolated_audit.py --url https://example.com --scenario full
```

This approach is safer for shared repositories because it keeps temporary `node_modules`, lockfiles, and generated Playwright state out of the main project by default.

## Direct Script Usage

If you want to run each step manually:

```bash
# Install Playwright and browser binaries
bash scripts/install.sh

# Fetch official docs or refresh the local reference cache
python3 scripts/fetch_docs.py --all

# Scaffold a test suite
python3 scripts/scaffold_tests.py --url https://example.com --scenario full

# Run the audit directly in the current workspace
bash scripts/run_audit.sh --url https://example.com --no-open

# Build a report from the Playwright JSON output
python3 scripts/generate_report.py --input test-results/results.json
```

## Scenario Coverage

- `smoke`: page load, title, and visible main content
- `form`: basic form interaction and submit flow
- `auth`: public login workflow with reusable auth state
- `a11y`: accessibility checks
- `perf`: browser-side performance checks
- `visual`: screenshot-based visual regression
- `full`: all supported scenarios together

## Output and Artifacts

Depending on the flow, the skill can generate:

- `test-results/results.json`
- `playwright-report/`
- screenshots, traces, and videos on failure
- `audit-runs/<name>/artifacts/audit-report.md`
- `audit-runs/<name>/artifacts/audit-report.html`
- `audit-runs/<name>/artifacts/audit-summary.json`

When using `run_isolated_audit.py`, the default behavior is to keep the final report artifacts and remove the temporary workspace unless `--keep-workspace` or `--keep-evidence` is explicitly requested.

## Environment Notes

- Node.js `18+` is required.
- In Linux or WSL, use `python3` when running the Python scripts.
- External audits may require network access to install Playwright packages, browser binaries, and open the target site.
- CI or restricted sandboxes may require elevated permissions for package installs or browser downloads.

## Project Approach

This repository follows a modular approach: instructions live in `SKILL.md`, operational logic lives in `scripts/`, and troubleshooting or CI guidance lives in `references/`. That separation makes the skill easier to maintain, package, and reuse across different agent environments.
