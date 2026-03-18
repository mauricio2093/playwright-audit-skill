# CI/CD Templates for Playwright

Ready-to-paste pipeline configurations for GitHub Actions, GitLab CI,
and Docker. Copy the snippet for your platform and adjust the `BASE_URL`
and artifact paths as needed.

---

## GitHub Actions

### Basic (Chromium only, fast)

```yaml
# .github/workflows/playwright-smoke.yml
name: Playwright Smoke Tests

on:
  push:
    branches: [main, develop]
  pull_request:

jobs:
  smoke:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.44.0-jammy

    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: npm ci

      - name: Run smoke tests
        run: npx playwright test --grep @smoke --project=chromium
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
          TEST_EMAIL: ${{ secrets.TEST_EMAIL }}
          TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-smoke-report
          path: playwright-report/
          retention-days: 7
```

---

### Full Matrix (All browsers, all scenarios)

```yaml
# .github/workflows/playwright-full.yml
name: Playwright Full Audit

on:
  schedule:
    - cron: '0 2 * * *'  # Nightly at 2am UTC
  workflow_dispatch:      # Manual trigger

jobs:
  audit:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        browser: [chromium, firefox, webkit]

    container:
      image: mcr.microsoft.com/playwright:v1.44.0-jammy

    steps:
      - uses: actions/checkout@v4

      - name: Install dependencies
        run: npm ci

      - name: Run Playwright audit (${{ matrix.browser }})
        run: bash scripts/run_audit.sh --browser ${{ matrix.browser }}
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
          TEST_EMAIL: ${{ secrets.TEST_EMAIL }}
          TEST_PASSWORD: ${{ secrets.TEST_PASSWORD }}

      - name: Generate Markdown report
        if: always()
        run: |
          python scripts/generate_report.py \
            --input test-results/results.json \
            --base-url "${{ secrets.STAGING_URL }}"

      - name: Upload HTML report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-report-${{ matrix.browser }}
          path: playwright-report/
          retention-days: 14

      - name: Upload traces (failures only)
        uses: actions/upload-artifact@v4
        if: failure()
        with:
          name: playwright-traces-${{ matrix.browser }}
          path: test-results/**/*.zip
          retention-days: 7

      - name: Upload audit Markdown report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: audit-report-${{ matrix.browser }}
          path: audit-report-*.md
          retention-days: 14
```

---

### PR Check with Comment

```yaml
# .github/workflows/playwright-pr.yml
name: Playwright PR Check

on:
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    container:
      image: mcr.microsoft.com/playwright:v1.44.0-jammy
    permissions:
      pull-requests: write

    steps:
      - uses: actions/checkout@v4
      - run: npm ci

      - name: Run tests
        id: playwright
        run: |
          npx playwright test --grep "@smoke|@regression" \
            --reporter=json,list \
            --retries=2
          echo "exit_code=$?" >> $GITHUB_OUTPUT
        env:
          BASE_URL: ${{ secrets.STAGING_URL }}
        continue-on-error: true

      - name: Generate report
        if: always()
        run: |
          python scripts/generate_report.py \
            --input test-results/results.json \
            --output pr-report.md \
            --base-url "${{ secrets.STAGING_URL }}"

      - name: Comment on PR
        uses: actions/github-script@v7
        if: always()
        with:
          script: |
            const fs = require('fs');
            const report = fs.readFileSync('pr-report.md', 'utf8');
            const summary = report.split('---')[1] || report.substring(0, 1000);
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: `## 🎭 Playwright Audit Results\n\n${summary}\n\n[Full Report](${context.serverUrl}/${context.repo.owner}/${context.repo.repo}/actions/runs/${context.runId})`
            });

      - name: Upload report
        uses: actions/upload-artifact@v4
        if: always()
        with:
          name: playwright-pr-report
          path: playwright-report/
```

---

## GitLab CI

```yaml
# .gitlab-ci.yml
stages:
  - test
  - report

variables:
  BASE_URL: $STAGING_URL

.playwright_base:
  image: mcr.microsoft.com/playwright:v1.44.0-jammy
  before_script:
    - npm ci
  artifacts:
    when: always
    paths:
      - playwright-report/
      - test-results/
      - audit-report-*.md
    expire_in: 2 weeks

playwright:smoke:
  extends: .playwright_base
  stage: test
  script:
    - npx playwright test --grep @smoke --project=chromium --retries=2
    - python scripts/generate_report.py --input test-results/results.json
  only:
    - merge_requests
    - main

playwright:regression:
  extends: .playwright_base
  stage: test
  script:
    - bash scripts/run_audit.sh
    - python scripts/generate_report.py --input test-results/results.json
  parallel:
    matrix:
      - BROWSER: [chromium, firefox, webkit]
  script:
    - bash scripts/run_audit.sh --browser $BROWSER
  only:
    - main
    - schedules

playwright:a11y:
  extends: .playwright_base
  stage: test
  script:
    - npx playwright test --grep @a11y
  only:
    - schedules
  allow_failure: true   # Accessibility failures are warnings, not blockers
```

---

## Docker — Local CI Parity

Run tests locally in the exact same environment as CI:

```dockerfile
# Dockerfile.playwright
FROM mcr.microsoft.com/playwright:v1.44.0-jammy

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
```

```yaml
# docker-compose.playwright.yml
version: '3.8'

services:
  playwright:
    build:
      context: .
      dockerfile: Dockerfile.playwright
    environment:
      - BASE_URL=http://app:3000
      - TEST_EMAIL=${TEST_EMAIL}
      - TEST_PASSWORD=${TEST_PASSWORD}
    volumes:
      - ./test-results:/app/test-results
      - ./playwright-report:/app/playwright-report
    command: bash scripts/run_audit.sh
    depends_on:
      - app

  app:
    image: your-app:latest
    ports:
      - "3000:3000"
```

```bash
# Run with Docker Compose
docker-compose -f docker-compose.playwright.yml up --exit-code-from playwright
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `BASE_URL` | Yes | Target URL for tests (e.g., `https://staging.example.com`) |
| `TEST_EMAIL` | For auth tests | Login email for test user account |
| `TEST_PASSWORD` | For auth tests | Login password for test user account |
| `CI` | Auto-set | Enables retries and strict mode |
| `PLAYWRIGHT_BROWSERS_PATH` | Optional | Custom browser binary location |

---

## Artifact Retention Strategy

| Artifact | Condition | Retention |
|----------|-----------|-----------|
| HTML report | Always | 14 days |
| Markdown report | Always | 14 days |
| Screenshots | On failure | 7 days |
| Traces (.zip) | On failure | 7 days |
| Videos | On failure | 7 days |

Keep retention short — Playwright artifacts are large. Use the HTML report
as the primary review tool; download traces only for investigation.
