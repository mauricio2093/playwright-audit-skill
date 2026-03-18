#!/usr/bin/env bash
# =============================================================================
# install.sh — Playwright Auto-Installer
# =============================================================================
# Detects environment, validates Node.js version, installs Playwright and
# browser binaries. Idempotent — safe to run multiple times.
#
# Usage:
#   bash scripts/install.sh [--browsers chromium,firefox,webkit] [--no-deps]
#
# Options:
#   --browsers  Comma-separated list of browsers to install (default: all)
#   --no-deps   Skip system dependency install (useful in Docker images)
#   --help      Show this help message
# =============================================================================

set -euo pipefail

# ── Colors ────────────────────────────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()    { echo -e "${BLUE}[playwright-auditor]${NC} $1"; }
success(){ echo -e "${GREEN}[✓]${NC} $1"; }
warn()   { echo -e "${YELLOW}[!]${NC} $1"; }
error()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

# ── Defaults ──────────────────────────────────────────────────────────────────
BROWSERS="chromium,firefox,webkit"
INSTALL_DEPS=true

# ── Argument parsing ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case $1 in
    --browsers) BROWSERS="$2"; shift 2 ;;
    --no-deps)  INSTALL_DEPS=false; shift ;;
    --help)
      grep '^#' "$0" | grep -v '#!/' | sed 's/^# //' | sed 's/^#//'
      exit 0
      ;;
    *) warn "Unknown option: $1"; shift ;;
  esac
done

# ── Step 1: Node.js version check ─────────────────────────────────────────────
log "Checking Node.js version..."

if ! command -v node &>/dev/null; then
  error "Node.js is not installed. Install Node.js ≥ 18 from https://nodejs.org"
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [[ "$NODE_VERSION" -lt 18 ]]; then
  error "Node.js ≥ 18 is required. Current version: $(node -v)"
fi
success "Node.js $(node -v) detected"

# ── Step 2: npm check ─────────────────────────────────────────────────────────
if ! command -v npm &>/dev/null; then
  error "npm is not installed. It should come with Node.js."
fi
success "npm $(npm -v) detected"

# ── Step 3: Install Playwright ────────────────────────────────────────────────
log "Installing @playwright/test..."

if [[ -f "package.json" ]]; then
  log "Existing package.json detected — adding @playwright/test as dev dependency"
  npm install -D @playwright/test
  npm install -D @axe-core/playwright
else
  log "No package.json found — initializing a new Node project"
  npm init -y >/dev/null
  npm install -D @playwright/test
  npm install -D @axe-core/playwright
fi

success "@playwright/test and @axe-core/playwright installed"

# ── Step 4: Install browser binaries ─────────────────────────────────────────
log "Installing browser binaries: $BROWSERS"

IFS=',' read -ra BROWSER_LIST <<< "$BROWSERS"
for browser in "${BROWSER_LIST[@]}"; do
  browser=$(echo "$browser" | xargs)  # trim whitespace
  log "Installing $browser..."
  if [[ "$INSTALL_DEPS" == true ]]; then
    npx playwright install "$browser" --with-deps
  else
    npx playwright install "$browser"
  fi
  success "$browser installed"
done

# ── Step 5: Generate baseline config if missing ───────────────────────────────
if [[ ! -f "playwright.config.ts" && ! -f "playwright.config.js" ]]; then
  log "Generating playwright.config.ts..."
  cat > playwright.config.ts << 'CONFIG'
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
  ],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    { name: 'firefox',  use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit',   use: { ...devices['Desktop Safari'] } },
  ],
});
CONFIG
  success "playwright.config.ts created"
else
  warn "playwright.config already exists — skipping generation"
fi

# ── Step 6: Create test directory ─────────────────────────────────────────────
mkdir -p tests test-results

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
success "Playwright installation complete!"
echo ""
echo "  Next steps:"
echo "    python scripts/fetch_docs.py --all          # fetch latest docs"
echo "    python scripts/scaffold_tests.py --url <URL> --scenario full"
echo "    bash scripts/run_audit.sh                   # run the audit"
