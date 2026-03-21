---
name: playwright-auditor
description: >
  Full-cycle Playwright automation skill: installs Playwright and browser
  binaries, fetches and caches official documentation from playwright.dev,
  scaffolds test suites (functional, accessibility, performance, visual
  regression), executes audits with structured reporters, and generates
  Markdown audit reports with AI-driven improvement recommendations. Trigger
  this skill whenever the user mentions Playwright, E2E testing, browser
  automation, web audits, test scaffolding, CI/CD test pipelines, visual
  regression, accessibility testing, or asks to test, audit, or inspect any
  website or web application — even if they do not use the word "skill."
---

# Playwright Auditor

A production-grade skill for installing, configuring, running, and reporting
Playwright web automation audits. Covers functional, accessibility,
performance, and visual regression testing. Outputs structured Markdown
reports with AI-generated recommendations.

---

## Quick Reference

| Task | Command |
|------|---------|
| Install Playwright | `bash scripts/install.sh` |
| Fetch docs | `python3 scripts/fetch_docs.py --all` |
| Scaffold tests | `python3 scripts/scaffold_tests.py --url <URL> --scenario <TYPE>` |
| Run audit | `bash scripts/run_audit.sh` |
| Generate report | `python3 scripts/generate_report.py --input test-results/results.json` |
| Run isolated audit | `python3 scripts/run_isolated_audit.py --url <URL> --scenario full` |

Scenario types: `smoke` · `form` · `auth` · `a11y` · `perf` · `visual` · `full`

Useful environment variables:
- `TEST_EMAIL` / `TEST_USERNAME` and `TEST_PASSWORD` — enable authenticated checks when the site has a public login flow
- `PERF_LCP_MS`, `PERF_CLS`, `PERF_RESPONSE_MS`, `PERF_IMAGE_KB` — tune performance thresholds for dev vs production
- `VISUAL_STRICT=1` — fail when a visual baseline snapshot does not already exist

---

## 1. Environment Detection & Installation

Run `scripts/install.sh` first. It handles Node.js validation, Playwright
install, and browser binary download. The script is idempotent and safe to
run multiple times.

If the audit is for a real external site or a shared project, prefer
`scripts/run_isolated_audit.py` so the skill installs dependencies in an
isolated workspace instead of mixing `package.json`, lockfiles, and
`node_modules` into the current repository.

**Manual install (if preferred):**

```bash
# Requires Node.js ≥ 18
node -v

# New project
npm init playwright@latest

# Existing project
npm install -D @playwright/test
npx playwright install --with-deps
```

After install, a `playwright.config.ts` is generated. The scaffold script
will create a baseline config if none exists. See `references/ci_templates.md`
for Docker and CI environments.

---

## 2. Fetching Documentation

Before writing or debugging tests, fetch the latest Playwright docs:

```bash
python3 scripts/fetch_docs.py --all
# or fetch a specific section:
python3 scripts/fetch_docs.py --section locators
python3 scripts/fetch_docs.py --section assertions
python3 scripts/fetch_docs.py --section network
```

Output is saved to `references/playwright_api_cheatsheet.md`. The script
falls back to the cached version if the network is unavailable. Check the
version tag at the top of the cheatsheet to confirm freshness.

---

## 3. Scaffolding Tests

Generate test files for any URL and scenario type:

```bash
# TypeScript (default)
python3 scripts/scaffold_tests.py --url https://example.com --scenario full

# JavaScript
python3 scripts/scaffold_tests.py --url https://example.com --scenario smoke --js

# Page Object Model output (for multi-page suites)
python3 scripts/scaffold_tests.py --url https://example.com --scenario full --pom
```

Generated files are placed in `tests/`. Each file includes inline comments
explaining every assertion. The `full` scenario generates all six test types.
Generic `auth` and `form` scenarios now skip cleanly when a target site does
not expose a standard public login or form flow, instead of hard-failing on
missing selectors.

**Scenario coverage:**

| Scenario | What it tests |
|----------|---------------|
| `smoke` | Page load, title, main content visible |
| `form` | Input fill, submit, success/error state |
| `auth` | Login flow with `storageState` caching |
| `a11y` | Accessibility via `axe-core/playwright` |
| `perf` | LCP, CLS, FID — Core Web Vitals |
| `visual` | Screenshot regression with diff threshold |
| `full` | All of the above |

---

## 4. Running the Audit

```bash
bash scripts/run_audit.sh
```

This runs `npx playwright test` with JSON and HTML reporters,
4 parallel workers, and 2 retries for flaky tests. On failure, it captures
a full-page screenshot, a video recording, and a Playwright trace zip.

**Tag-based filtering:**

```bash
npx playwright test --grep @smoke
npx playwright test --grep @a11y
npx playwright test --grep @perf
```

Results land in `test-results/`. The HTML report opens automatically after
the run unless `--no-open` is passed.

For visual regression:
- Local development: first run creates missing baselines unless `VISUAL_STRICT=1`
- CI / production: set `VISUAL_STRICT=1` so missing snapshots fail the pipeline

### Recommended Production/Development Flow

Prefer `scripts/run_isolated_audit.py` for real audits. It:
- creates a dedicated run folder under `audit-runs/`
- runs the audit inside an isolated `workspace/`
- exports human-readable HTML plus Markdown and JSON artifacts into `artifacts/`
- keeps only the final reports by default so the run folder stays clean
- removes the temporary workspace by default so `node_modules` and lockfiles do not interfere with other projects

Example:

```bash
python3 scripts/run_isolated_audit.py --url https://example.com --scenario full
```

If you also want raw Playwright evidence such as traces, screenshots, videos, and baselines:

```bash
python3 scripts/run_isolated_audit.py --url https://example.com --scenario full --keep-evidence
```

---

## 5. Generating the Report

```bash
python3 scripts/generate_report.py --input test-results/results.json

# With AI recommendations (calls Claude API)
python3 scripts/generate_report.py --input test-results/results.json --ai-recommendations

# With screenshots embedded as base64
python3 scripts/generate_report.py --input test-results/results.json --embed-screenshots
```

Output: `audit-report-{TIMESTAMP}.md`

**Report structure:**

```
# Playwright Audit Report
## Summary (pass/fail/skip table, pass rate %)
## Test Results (per spec file, per browser)
## Performance Metrics (LCP, CLS, FID vs thresholds)
## Accessibility Violations (rule, impact, element)
## AI Recommendations
## CI/CD Integration Snippet
```

---

## 6. AI Interpretation — What Claude Should Do With Results

When test results are available, analyze them and produce recommendations.
The goal is to explain *why* things failed and suggest concrete fixes —
not just list errors.

**Failure pattern guide:**

| Pattern | Likely cause | Recommended fix |
|---------|-------------|-----------------|
| `TimeoutError: waiting for locator` | Element not in DOM, hidden, or selector too fragile | Use `waitFor`, switch to `getByRole` |
| `Executable doesn't exist` | Browser binaries missing | Run `npx playwright install --with-deps` |
| `ERR_CONNECTION_REFUSED` in CI | No dev server running | Use `webServer` config or mock server |
| Flaky tests (pass/fail alternating) | Animation timing or race conditions | Add `page.waitForLoadState('networkidle')`, use `expect.soft()` |
| Cross-browser selector failures | Browser-specific rendering differences | Prefer ARIA roles; avoid pseudo-selectors |

**Selector improvement priority (highest → lowest quality):**

1. `getByRole('button', { name: 'Submit' })` — most resilient
2. `getByLabel('Email address')` — tied to visible label
3. `getByTestId('submit-btn')` — stable if team controls markup
4. `getByText('Submit')` — fragile to copy changes
5. CSS / XPath — last resort; flag for refactoring

**Code structure suggestions:**

- Extract repeated `page.goto()` + login into `beforeEach`
- Move auth to a `setup` project with `storageState` so login runs once
- Add `test.slow()` to known slow paths instead of raising global timeout
- Group related tests in `test.describe` blocks with shared fixtures

---

## 7. CI/CD Integration

See `references/ci_templates.md` for ready-to-paste snippets:
- GitHub Actions (Chromium + Firefox matrix)
- GitLab CI (parallel browser jobs)
- Docker Compose (local CI parity)
- Artifact upload (HTML report + traces)

---

## References

| File | When to read |
|------|-------------|
| `references/playwright_api_cheatsheet.md` | Writing or debugging tests — locators, assertions, network |
| `references/best_practices.md` | Architecture decisions — POM, auth patterns, tagging |
| `references/common_errors.md` | Troubleshooting failures |
| `references/ci_templates.md` | Setting up CI/CD pipelines |
