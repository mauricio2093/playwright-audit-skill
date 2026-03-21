#!/usr/bin/env bash
# =============================================================================
# run_audit.sh — Playwright Audit Runner
# =============================================================================
# Executes the full Playwright test suite with JSON and HTML reporters.
# Captures screenshots, videos, and traces on failure. Supports tag-based
# filtering and multi-browser overrides.
#
# Usage:
#   bash scripts/run_audit.sh
#   bash scripts/run_audit.sh --tag @smoke
#   bash scripts/run_audit.sh --browser chromium
#   bash scripts/run_audit.sh --url https://staging.example.com
#   bash scripts/run_audit.sh --workers 2
#   bash scripts/run_audit.sh --help
# =============================================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

log()    { echo -e "${BLUE}[playwright-auditor]${NC} $1"; }
success(){ echo -e "${GREEN}[✓]${NC} $1"; }
warn()   { echo -e "${YELLOW}[!]${NC} $1"; }
error()  { echo -e "${RED}[✗]${NC} $1"; }

# ── Defaults ──────────────────────────────────────────────────────────────────
TAG=""
BROWSER=""
WORKERS=4
RETRIES=2
BASE_URL="${BASE_URL:-}"
NO_OPEN=false
RESULTS_DIR="test-results"
REPORT_DIR="playwright-report"

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --tag)      TAG="$2";      shift 2 ;;
    --browser)  BROWSER="$2";  shift 2 ;;
    --workers)  WORKERS="$2";  shift 2 ;;
    --retries)  RETRIES="$2";  shift 2 ;;
    --url)      BASE_URL="$2"; shift 2 ;;
    --no-open)  NO_OPEN=true;  shift ;;
    --help)
      grep '^#' "$0" | grep -v '#!/' | sed 's/^# //' | sed 's/^#//'
      exit 0
      ;;
    *) warn "Unknown option: $1"; shift ;;
  esac
done

# ── Pre-flight checks ─────────────────────────────────────────────────────────
log "Pre-flight checks..."

if ! command -v npx &>/dev/null; then
  error "npx not found. Run: bash scripts/install.sh"
  exit 1
fi

if [[ ! -f "playwright.config.ts" && ! -f "playwright.config.js" ]]; then
  warn "No playwright.config found. Run: bash scripts/install.sh"
  exit 1
fi

if [[ ! -d "tests" || -z "$(ls -A tests 2>/dev/null)" ]]; then
  warn "No test files found in tests/. Run: python scripts/scaffold_tests.py"
  exit 1
fi

success "Pre-flight checks passed"

# ── Build command ─────────────────────────────────────────────────────────────
mkdir -p "$RESULTS_DIR"

CMD=(npx playwright test)
CMD+=("--workers=$WORKERS")
CMD+=("--retries=$RETRIES")
CMD+=("--output=$RESULTS_DIR")

if [[ -n "$TAG" ]]; then
  CMD+=("--grep=$TAG")
  log "Tag filter: $TAG"
fi

if [[ -n "$BROWSER" ]]; then
  CMD+=("--project=$BROWSER")
  log "Browser: $BROWSER"
fi

# Export base URL if provided via flag
if [[ -n "$BASE_URL" ]]; then
  export BASE_URL
  log "Base URL: $BASE_URL"
fi

if [[ "$NO_OPEN" == true ]]; then
  export PLAYWRIGHT_HTML_OPEN=never
fi

# ── Run the tests ─────────────────────────────────────────────────────────────
echo ""
log "Starting Playwright audit — $(date '+%Y-%m-%d %H:%M:%S')"
printf -v CMD_LOG '%q ' "${CMD[@]}"
log "Command: ${CMD_LOG% }"
echo ""
echo "─────────────────────────────────────────────"

START_TIME=$(date +%s%3N)
set +e
"${CMD[@]}"
EXIT_CODE=$?
set -e
END_TIME=$(date +%s%3N)
DURATION=$(( END_TIME - START_TIME ))

echo "─────────────────────────────────────────────"
echo ""

# ── Post-run summary ──────────────────────────────────────────────────────────
log "Audit completed in ${DURATION}ms"

# Parse results JSON for a quick summary
RESULTS_JSON="$RESULTS_DIR/results.json"
if [[ -f "$RESULTS_JSON" ]]; then
  # Quick stats using node (always available with Playwright)
  node -e "
    const fs = require('fs');
    const data = JSON.parse(fs.readFileSync('$RESULTS_JSON', 'utf8'));
    const suites = data.suites || [];
    let passed = 0, failed = 0, skipped = 0;

    function walk(suite) {
      (suite.specs || []).forEach(spec => {
        spec.tests.forEach(t => {
          const status = t.results[0]?.status;
          if (status === 'passed') passed++;
          else if (status === 'failed') failed++;
          else if (status === 'skipped') skipped++;
        });
      });
      (suite.suites || []).forEach(walk);
    }

    suites.forEach(walk);

    const total = passed + failed + skipped;
    const rate = total > 0 ? ((passed / total) * 100).toFixed(1) : '0.0';
    console.log('');
    console.log('  Results:');
    console.log('  ┌──────────────────────────────┐');
    console.log('  │ Total   : ' + String(total).padEnd(20) + '│');
    console.log('  │ Passed  : ✅ ' + String(passed).padEnd(17) + '│');
    console.log('  │ Failed  : ❌ ' + String(failed).padEnd(17) + '│');
    console.log('  │ Skipped : ⏭  ' + String(skipped).padEnd(16) + '│');
    console.log('  │ Pass rate: ' + String(rate + '%').padEnd(19) + '│');
    console.log('  └──────────────────────────────┘');
    console.log('');
  " 2>/dev/null || true
fi

# ── Artifacts ─────────────────────────────────────────────────────────────────
if [[ -d "$REPORT_DIR" && "$NO_OPEN" != true ]]; then
  success "HTML report: $REPORT_DIR/index.html"
  echo "  Run 'npx playwright show-report' to open in browser"
fi

if [[ -d "$RESULTS_DIR" ]]; then
  TRACE_COUNT=$(find "$RESULTS_DIR" -name "*.zip" 2>/dev/null | wc -l | tr -d ' ')
  SCREENSHOT_COUNT=$(find "$RESULTS_DIR" -name "*.png" 2>/dev/null | wc -l | tr -d ' ')
  if [[ "$TRACE_COUNT" -gt 0 ]]; then
    warn "$TRACE_COUNT trace(s) captured — run 'npx playwright show-trace <path>' to inspect"
  fi
  if [[ "$SCREENSHOT_COUNT" -gt 0 ]]; then
    warn "$SCREENSHOT_COUNT screenshot(s) captured in $RESULTS_DIR"
  fi
fi

echo ""
if [[ -f "$RESULTS_JSON" ]]; then
  log "Generate report: python3 scripts/generate_report.py --input $RESULTS_JSON"
fi

# Return Playwright's exit code so CI pipelines detect failures
exit $EXIT_CODE
