#!/usr/bin/env python3
"""
scaffold_tests.py — Playwright Test Suite Generator
=====================================================
Generates ready-to-run Playwright test files for any URL, organized by
scenario type. Supports TypeScript (default) and JavaScript. Follows
Page Object Model pattern when --pom is specified.

Usage:
    python scripts/scaffold_tests.py --url https://example.com --scenario smoke
    python scripts/scaffold_tests.py --url https://example.com --scenario full
    python scripts/scaffold_tests.py --url https://example.com --scenario full --js
    python scripts/scaffold_tests.py --url https://example.com --scenario full --pom
    python scripts/scaffold_tests.py --help

Scenarios:
    smoke    Page load, title assertion, main content visible
    form     Input interaction, submit, success/error validation
    auth     Login flow with storageState caching
    a11y     Accessibility audit via axe-core
    perf     Core Web Vitals (LCP, CLS, FID)
    visual   Screenshot regression with diff threshold
    full     All of the above
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import urlparse

# ── Template registry ──────────────────────────────────────────────────────────

def get_extension(use_js: bool) -> str:
    return ".spec.js" if use_js else ".spec.ts"


def get_import(use_js: bool) -> str:
    if use_js:
        return "const { test, expect } = require('@playwright/test');"
    return "import { test, expect } from '@playwright/test';"


def get_a11y_import(use_js: bool) -> str:
    if use_js:
        return "const AxeBuilder = require('@axe-core/playwright').default;"
    return "import AxeBuilder from '@axe-core/playwright';"


def smoke_test(url: str, use_js: bool) -> str:
    imp = get_import(use_js)
    return f"""{imp}

// @smoke
// Validates that the page loads, has a title, and renders the main content.
// This is the fastest check — run it on every deploy.

test.describe('Smoke Tests — {url}', () => {{

  test.beforeEach(async ({{ page }}) => {{
    await page.goto('{url}');
  }});

  test('page loads successfully', async ({{ page }}) => {{
    // Confirm we did not land on an error page
    await expect(page).not.toHaveURL(/error|404|500/);
    await expect(page.locator('body')).toBeVisible();
  }});

  test('page has a meaningful title', async ({{ page }}) => {{
    // Title should not be empty or a default placeholder
    const title = await page.title();
    expect(title.length).toBeGreaterThan(0);
    expect(title).not.toMatch(/untitled|undefined/i);
  }});

  test('primary content is visible', async ({{ page }}) => {{
    // Prefer semantic landmarks, but tolerate simpler layouts in brochure sites.
    const selectors = ['main', '[role="main"]', '#main', '.main', 'article', 'h1'];
    let hasVisibleContent = false;

    for (const selector of selectors) {{
      const candidate = page.locator(selector).first();
      if (await candidate.isVisible().catch(() => false)) {{
        hasVisibleContent = true;
        break;
      }}
    }}

    if (!hasVisibleContent) {{
      const bodyText = (await page.locator('body').innerText()).trim();
      expect(bodyText.length).toBeGreaterThan(80);
      hasVisibleContent = true;
    }}

    expect(hasVisibleContent).toBeTruthy();
  }});

  test('no console errors on load', async ({{ page }}) => {{
    const errors = [];
    page.on('console', msg => {{
      if (msg.type() === 'error') errors.push(msg.text());
    }});
    await page.goto('{url}');
    await page.waitForLoadState('networkidle');
    expect(errors).toHaveLength(0);
  }});

}});
"""


def form_test(url: str, use_js: bool) -> str:
    imp = get_import(use_js)
    return f"""{imp}

// @regression
// Tests form interactions: fill, submit, and validate feedback.
// Customize the selectors and field names to match your actual form.

test.describe('Form Interaction Tests — {url}', () => {{

  async function firstVisible(page, locators) {{
    for (const locator of locators) {{
      if (await locator.count().catch(() => 0) > 0 && await locator.first().isVisible().catch(() => false)) {{
        return locator.first();
      }}
    }}
    return null;
  }}

  async function findForm(page) {{
    return firstVisible(page, [
      page.locator('form'),
      page.locator('[role="form"]'),
      page.locator('.wpcf7 form'),
      page.locator('.contact form'),
      page.locator('.contact-form'),
      page.locator('form[action]'),
    ]);
  }}

  test('fills and submits a contact form', async ({{ page }}) => {{
    await page.goto('{url}');
    const form = await findForm(page);
    test.skip(!form, 'No visible form found on the page');

    const nameField = await firstVisible(page, [
      page.getByLabel(/name|nombre/i),
      form.locator('input[name*="name" i], input[id*="name" i]'),
      page.getByPlaceholder(/name|nombre/i),
    ]);
    const emailField = await firstVisible(page, [
      page.getByLabel(/email|correo/i),
      form.locator('input[type="email"]'),
      form.locator('input[name*="mail" i], input[id*="mail" i]'),
      page.getByPlaceholder(/email|correo/i),
    ]);
    const messageField = await firstVisible(page, [
      page.getByLabel(/message|comment|mensaje|comentario/i),
      form.locator('textarea'),
      page.getByPlaceholder(/message|comment|mensaje/i),
    ]);
    const submitButton = await firstVisible(page, [
      form.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
      form.locator('button[type="submit"], input[type="submit"]'),
      page.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
    ]);

    test.skip(!nameField || !emailField || !submitButton, 'Generic form controls not detected; customize selectors for this site');

    await nameField.fill('Test User');
    await emailField.fill('testuser@example.com');
    if (messageField) {{
      await messageField.fill('This is an automated test submission.');
    }}

    await submitButton.click();
    await page.waitForTimeout(1500);

    const feedback = await firstVisible(page, [
      page.getByRole('alert'),
      page.locator('[aria-live]'),
      page.locator('.wpcf7-response-output, .success, .error, .form-response, .notice'),
      page.getByText(/thank you|success|sent|enviado|recibido|error/i),
    ]);

    const hasFeedback = !!feedback && await feedback.isVisible().catch(() => false);
    const hasValidationState = await page.locator('[aria-invalid="true"], .error, .field-error').count().catch(() => 0);
    expect(hasFeedback || hasValidationState > 0).toBeTruthy();
  }});

  test('shows validation errors for empty required fields', async ({{ page }}) => {{
    await page.goto('{url}');
    const form = await findForm(page);
    test.skip(!form, 'No visible form found on the page');

    const submitButton = await firstVisible(page, [
      form.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
      form.locator('button[type="submit"], input[type="submit"]'),
      page.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
    ]);
    test.skip(!submitButton, 'No generic submit button detected');

    await submitButton.click();
    await page.waitForTimeout(1000);

    // At least one validation error should appear
    const errorMessages = page.locator('[aria-invalid="true"], .error, .field-error');
    const nativeInvalidCount = await form.locator(':invalid').count().catch(() => 0);
    const customInvalidCount = await errorMessages.count().catch(() => 0);
    expect(nativeInvalidCount > 0 || customInvalidCount > 0).toBeTruthy();
  }});

  test('rejects invalid email format', async ({{ page }}) => {{
    await page.goto('{url}');
    const form = await findForm(page);
    test.skip(!form, 'No visible form found on the page');

    const emailField = await firstVisible(page, [
      page.getByLabel(/email|correo/i),
      form.locator('input[type="email"]'),
      form.locator('input[name*="mail" i], input[id*="mail" i]'),
      page.getByPlaceholder(/email|correo/i),
    ]);
    const submitButton = await firstVisible(page, [
      form.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
      form.locator('button[type="submit"], input[type="submit"]'),
      page.getByRole('button', {{ name: /submit|send|contact|enviar|consultar/i }}),
    ]);

    test.skip(!emailField || !submitButton, 'No generic email field or submit button detected');

    await emailField.fill('not-an-email');
    await submitButton.click();
    await page.waitForTimeout(1000);

    const invalidAttr = await emailField.getAttribute('aria-invalid');
    const nativeInvalidCount = await form.locator(':invalid').count().catch(() => 0);
    expect(invalidAttr === 'true' || nativeInvalidCount > 0).toBeTruthy();
  }});

}});
"""


def auth_test(url: str, use_js: bool) -> str:
    if use_js:
        imports = """const fs = require('node:fs');
const { test, expect } = require('@playwright/test');"""
    else:
        imports = """import fs from 'node:fs';
import { test, expect } from '@playwright/test';"""
    return f"""{imports}

// @regression
// Login flow using optional storageState caching.
// Generic auth tests should skip cleanly when the site has no public login flow.

const AUTH_STATE = 'auth.json';
const LOGIN_PATHS = ['/login', '/signin', '/ingreso', '/acceso', '/mi-cuenta', '/account/login'];

async function firstVisible(page, locators) {{
  for (const locator of locators) {{
    if (await locator.count().catch(() => 0) > 0 && await locator.first().isVisible().catch(() => false)) {{
      return locator.first();
    }}
  }}
  return null;
}}

async function detectLoginControls(page) {{
  const usernameField = await firstVisible(page, [
    page.getByLabel(/email|username|correo|usuario/i),
    page.locator('input[type="email"]'),
    page.locator('input[name*="email" i], input[id*="email" i], input[name*="user" i], input[id*="user" i]'),
    page.getByPlaceholder(/email|username|correo|usuario/i),
  ]);
  const passwordField = await firstVisible(page, [
    page.getByLabel(/password|contrase(?:n|ñ)a/i),
    page.locator('input[type="password"]'),
    page.locator('input[name*="pass" i], input[id*="pass" i]'),
    page.getByPlaceholder(/password|contrase(?:n|ñ)a/i),
  ]);
  const submitButton = await firstVisible(page, [
    page.getByRole('button', {{ name: /sign in|log in|login|ingresar|entrar|acceder/i }}),
    page.locator('button[type="submit"], input[type="submit"]'),
    page.getByRole('link', {{ name: /sign in|log in|login|ingresar|entrar|acceder/i }}),
  ]);
  return {{ usernameField, passwordField, submitButton }};
}}

async function gotoLogin(page) {{
  for (const path of LOGIN_PATHS) {{
    await page.goto(`{url}${{path}}`);
    const controls = await detectLoginControls(page);
    if (controls.usernameField && controls.passwordField && controls.submitButton) {{
      return controls;
    }}
  }}

  await page.goto('{url}');
  const loginEntry = await firstVisible(page, [
    page.getByRole('link', {{ name: /sign in|log in|login|ingresar|entrar|mi cuenta|cuenta/i }}),
    page.getByRole('button', {{ name: /sign in|log in|login|ingresar|entrar|mi cuenta|cuenta/i }}),
  ]);
  if (loginEntry) {{
    await loginEntry.click();
    await page.waitForLoadState('networkidle').catch(() => {{}});
    const controls = await detectLoginControls(page);
    if (controls.usernameField && controls.passwordField && controls.submitButton) {{
      return controls;
    }}
  }}

  return null;
}}

test.describe('Auth Flow Tests — {url}', () => {{

  test('authenticate when a public login flow and credentials are available', async ({{ page }}) => {{
    const username = process.env.TEST_EMAIL ?? process.env.TEST_USERNAME;
    const password = process.env.TEST_PASSWORD;
    test.skip(!username || !password, 'Set TEST_EMAIL or TEST_USERNAME, plus TEST_PASSWORD, to exercise authenticated flows');

    const controls = await gotoLogin(page);
    test.skip(!controls, 'No generic public login flow detected; customize selectors or auth URL for this site');

    await controls.usernameField.fill(username);
    await controls.passwordField.fill(password);
    await controls.submitButton.click();
    await page.waitForLoadState('networkidle').catch(() => {{}});

    await expect(page).not.toHaveURL(/login|signin|ingreso|acceso/i);
    await page.context().storageState({{ path: AUTH_STATE }});
    expect(fs.existsSync(AUTH_STATE)).toBeTruthy();
  }});

  test('authenticated user sees dashboard when storage state exists', async ({{ browser }}) => {{
    test.skip(!fs.existsSync(AUTH_STATE), 'No auth state available; run the authenticate test with valid credentials first');

    const context = await browser.newContext({{ storageState: AUTH_STATE }});
    const page = await context.newPage();
    await page.goto('{url}');
    await page.waitForLoadState('networkidle').catch(() => {{}});
    await expect(page).not.toHaveURL(/login|signin|ingreso|acceso/i);
    await expect(page.locator('body')).toBeVisible();
    await context.close();
  }});

  test('logout works correctly when a logout control exists', async ({{ browser }}) => {{
    test.skip(!fs.existsSync(AUTH_STATE), 'No auth state available; run the authenticate test with valid credentials first');

    const context = await browser.newContext({{ storageState: AUTH_STATE }});
    const page = await context.newPage();
    await page.goto('{url}');
    await page.waitForLoadState('networkidle').catch(() => {{}});

    const logoutBtn = await firstVisible(page, [
      page.getByRole('button', {{ name: /logout|sign out|cerrar sesi(?:o|ó)n|salir/i }}),
      page.getByRole('link', {{ name: /logout|sign out|cerrar sesi(?:o|ó)n|salir/i }}),
    ]);
    test.skip(!logoutBtn, 'No generic logout control detected');

    await logoutBtn.click();
    await page.waitForLoadState('networkidle').catch(() => {{}});
    await expect(page).toHaveURL(/login|signin|ingreso|acceso|\\//i);
    await context.close();
  }});

}});
"""


def a11y_test(url: str, use_js: bool) -> str:
    imp = get_import(use_js)
    a11y_import = get_a11y_import(use_js)
    return f"""{imp}
{a11y_import}

// @a11y
// Accessibility audit using axe-core. Tests for WCAG 2.1 AA compliance.
// Install: npm install -D @axe-core/playwright

test.describe('Accessibility Tests — {url}', () => {{

  test('full page passes axe accessibility checks', async ({{ page }}) => {{
    await page.goto('{url}');
    await page.waitForLoadState('networkidle');

    const results = await new AxeBuilder({{ page }})
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
      .analyze();

    // Log violations for debugging
    if (results.violations.length > 0) {{
      console.log('Accessibility violations:');
      results.violations.forEach(v => {{
        console.log(`  [${{v.impact}}] ${{v.id}}: ${{v.description}}`);
        v.nodes.forEach(n => console.log(`    → ${{n.target}}`));
      }});
    }}

    expect(results.violations).toHaveLength(0);
  }});

  test('interactive elements have accessible names', async ({{ page }}) => {{
    await page.goto('{url}');

    // All buttons must have an accessible name
    const buttons = page.getByRole('button');
    const count = await buttons.count();
    for (let i = 0; i < count; i++) {{
      const btn = buttons.nth(i);
      const ariaLabel = await btn.getAttribute('aria-label');
      const textContent = await btn.textContent();
      const name = ariaLabel ?? textContent;
      expect(name?.trim().length).toBeGreaterThan(0);
    }}
  }});

  test('images have alt text', async ({{ page }}) => {{
    await page.goto('{url}');
    const images = page.locator('img');
    const count = await images.count();

    for (let i = 0; i < count; i++) {{
      const img = images.nth(i);
      const alt = await img.getAttribute('alt');
      const role = await img.getAttribute('role');
      // Decorative images should have role="presentation" or alt=""
      expect(alt !== null || role === 'presentation').toBeTruthy();
    }}
  }});

  test('page has logical heading hierarchy', async ({{ page }}) => {{
    await page.goto('{url}');
    const h1 = page.getByRole('heading', {{ level: 1 }});
    await expect(h1).toBeVisible();
    await expect(h1).toHaveCount(1); // Only one H1 per page
  }});

}});
"""


def perf_test(url: str, use_js: bool) -> str:
    imp = get_import(use_js)
    return f"""{imp}

// @perf
// Core Web Vitals measurement using configurable thresholds.
// Defaults: LCP < 4000ms | CLS < 0.15 | response < 5000ms

const LCP_THRESHOLD_MS = Number(process.env.PERF_LCP_MS ?? 4000);
const CLS_THRESHOLD = Number(process.env.PERF_CLS ?? 0.15);
const RESPONSE_THRESHOLD_MS = Number(process.env.PERF_RESPONSE_MS ?? 5000);
const LARGE_IMAGE_THRESHOLD_KB = Number(process.env.PERF_IMAGE_KB ?? 500);

test.describe('Performance Tests — {url}', () => {{

  test('Largest Contentful Paint (LCP) is under the configured threshold', async ({{ page }}) => {{
    await page.addInitScript(() => {{
      window['__pwMetrics'] = {{ lcp: 0, cls: 0 }};
      new PerformanceObserver(list => {{
        const entries = list.getEntries();
        const lastEntry = entries[entries.length - 1];
        if (lastEntry) window['__pwMetrics'].lcp = lastEntry.startTime;
      }}).observe({{ type: 'largest-contentful-paint', buffered: true }});
    }});

    await page.goto('{url}', {{ waitUntil: 'domcontentloaded' }});
    await page.waitForLoadState('networkidle').catch(() => {{}});
    await page.waitForTimeout(1000);
    const metrics = await page.evaluate(() => window['__pwMetrics'] ?? {{ lcp: 0, cls: 0 }});
    const lcp = metrics.lcp || 0;

    if (lcp > 0) {{
      console.log(`LCP: ${{lcp.toFixed(0)}}ms`);
      expect(lcp).toBeLessThan(LCP_THRESHOLD_MS);
    }} else {{
      test.skip(true, 'LCP metric not available for this page or browser run');
    }}
  }});

  test('Cumulative Layout Shift (CLS) is under the configured threshold', async ({{ page }}) => {{
    await page.addInitScript(() => {{
      window['__pwMetrics'] = {{ lcp: 0, cls: 0 }};
      new PerformanceObserver(list => {{
        for (const entry of list.getEntries()) {{
          if (!entry.hadRecentInput) window['__pwMetrics'].cls += entry.value;
        }}
      }}).observe({{ type: 'layout-shift', buffered: true }});
    }});

    await page.goto('{url}', {{ waitUntil: 'domcontentloaded' }});
    await page.waitForLoadState('networkidle').catch(() => {{}});
    await page.waitForTimeout(5000);
    const metrics = await page.evaluate(() => window['__pwMetrics'] ?? {{ lcp: 0, cls: 0 }});
    const cls = metrics.cls || 0;

    console.log(`CLS: ${{cls.toFixed(4)}}`);
    expect(cls).toBeLessThan(CLS_THRESHOLD);
  }});

  test('page response time is under the configured threshold', async ({{ page }}) => {{
    const start = Date.now();
    const response = await page.goto('{url}');
    const elapsed = Date.now() - start;

    console.log(`Response time: ${{elapsed}}ms | Status: ${{response?.status()}}`);
    expect(response?.status()).toBeLessThan(400);
    expect(elapsed).toBeLessThan(RESPONSE_THRESHOLD_MS);
  }});

  test('page weight — images are reasonably sized', async ({{ page }}) => {{
    const largeImages = [];

    page.on('response', async response => {{
      const url = response.url();
      const contentType = response.headers()['content-type'] ?? '';
      if (contentType.includes('image')) {{
        const body = await response.body().catch(() => Buffer.alloc(0));
        const sizeKB = body.length / 1024;
        if (sizeKB > LARGE_IMAGE_THRESHOLD_KB) {{
          largeImages.push({{ url, sizeKB: sizeKB.toFixed(0) }});
        }}
      }}
    }});

    await page.goto('{url}');
    await page.waitForLoadState('networkidle');

    if (largeImages.length > 0) {{
      console.log('Large images detected:');
      largeImages.forEach(img => console.log(`  ${{img.sizeKB}}KB — ${{img.url}}`));
    }}

    expect(largeImages).toHaveLength(0);
  }});

}});
"""


def visual_test(url: str, use_js: bool) -> str:
    if use_js:
        imports = """const fs = require('node:fs');
const path = require('node:path');
const { test, expect } = require('@playwright/test');"""
    else:
        imports = """import fs from 'node:fs';
import path from 'node:path';
import { test, expect, type TestInfo } from '@playwright/test';"""
    return f"""{imports}

// @visual
// Visual regression tests using Playwright's built-in screenshot comparison.
// First run creates baseline snapshots locally unless VISUAL_STRICT=1.
// Subsequent runs diff against the baseline.

async function ensureBaselineOrCompare(target, snapshotName, testInfo, compareOptions = {{}}, screenshotOptions = {{}}) {{
  const snapshotPath = testInfo.snapshotPath(snapshotName);
  const strictMode = process.env.VISUAL_STRICT === '1';

  if (!fs.existsSync(snapshotPath)) {{
    fs.mkdirSync(path.dirname(snapshotPath), {{ recursive: true }});
    await target.screenshot({{
      path: snapshotPath,
      animations: 'disabled',
      ...screenshotOptions,
    }});

    if (strictMode) {{
      throw new Error(`Baseline missing for ${{snapshotName}}. Snapshot created at ${{snapshotPath}}; rerun to compare.`);
    }}

    testInfo.annotations.push({{
      type: 'visual-baseline',
      description: `Created baseline snapshot ${{snapshotName}}; rerun to compare changes.`,
    }});
    return;
  }}

  await expect(target).toHaveScreenshot(snapshotName, compareOptions);
}}

test.describe('Visual Regression Tests — {url}', () => {{

  test('homepage matches visual baseline', async ({{ page }}, testInfo) => {{
    await page.goto('{url}');
    await page.waitForLoadState('networkidle');

    // Mask dynamic content (timestamps, ads, user avatars) to prevent false positives
    await ensureBaselineOrCompare(page, 'homepage.png', testInfo, {{
      maxDiffPixelRatio: 0.02,  // Allow up to 2% pixel difference
      mask: [
        page.locator('[data-testid="timestamp"]'),
        page.locator('.ad-banner'),
        page.locator('[data-testid="user-avatar"]'),
      ],
    }}, {{
      fullPage: true,
    }});
  }});

  test('navigation component matches baseline', async ({{ page }}, testInfo) => {{
    await page.goto('{url}');
    const nav = page.getByRole('navigation');

    if (await nav.isVisible()) {{
      await ensureBaselineOrCompare(nav, 'navigation.png', testInfo, {{
        maxDiffPixelRatio: 0.01,
      }});
    }} else {{
      test.skip(true, 'No visible navigation landmark detected on the page');
    }}
  }});

  test('mobile viewport matches baseline', async ({{ browser }}, testInfo) => {{
    // Test responsive layout at mobile breakpoint
    const context = await browser.newContext({{
      viewport: {{ width: 375, height: 812 }},
      deviceScaleFactor: 2,
    }});
    const mobilePage = await context.newPage();
    await mobilePage.goto('{url}');
    await mobilePage.waitForLoadState('networkidle');

    await ensureBaselineOrCompare(mobilePage, 'homepage-mobile.png', testInfo, {{
      maxDiffPixelRatio: 0.02,
    }}, {{
      fullPage: true,
    }});

    await context.close();
  }});

}});
"""


# ── Page Object Model scaffolding ─────────────────────────────────────────────

def pom_page_object(url: str, use_js: bool) -> str:
    if use_js:
        return f"""class HomePage {{
  constructor(page) {{
    this.page = page;
  }}

  async goto() {{
    await this.page.goto('{url}');
    await this.page.waitForLoadState('networkidle');
  }}

  async getTitle() {{
    return this.page.title();
  }}

  navigation() {{
    return this.page.getByRole('navigation');
  }}

  mainContent() {{
    return this.page.getByRole('main');
  }}

  heading(level = 1) {{
    return this.page.getByRole('heading', {{ level }});
  }}
}}

module.exports = {{ HomePage }};
"""

    return f"""import type {{ Page }} from '@playwright/test';

// Page Object Model for {url}
// Encapsulates selectors and actions for reuse across test files.

export class HomePage {{
  readonly page: Page;

  constructor(page: Page) {{
    this.page = page;
  }}

  async goto() {{
    await this.page.goto('{url}');
    await this.page.waitForLoadState('networkidle');
  }}

  async getTitle() {{
    return this.page.title();
  }}

  navigation() {{
    return this.page.getByRole('navigation');
  }}

  mainContent() {{
    return this.page.getByRole('main');
  }}

  heading(level = 1) {{
    return this.page.getByRole('heading', {{ level }});
  }}
}}
"""


# ── Entry point ───────────────────────────────────────────────────────────────

SCENARIO_MAP = {
    "smoke": smoke_test,
    "form": form_test,
    "auth": auth_test,
    "a11y": a11y_test,
    "perf": perf_test,
    "visual": visual_test,
}


def main():
    parser = argparse.ArgumentParser(
        description="Scaffold Playwright test files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--url", required=True, help="Base URL to test")
    parser.add_argument(
        "--scenario",
        required=True,
        choices=list(SCENARIO_MAP.keys()) + ["full"],
        help="Test scenario type",
    )
    parser.add_argument("--js", action="store_true", help="Output JavaScript instead of TypeScript")
    parser.add_argument("--pom", action="store_true", help="Also generate Page Object Model file")
    parser.add_argument("--output-dir", default="tests", help="Output directory (default: tests/)")
    args = parser.parse_args()

    # Validate URL
    parsed = urlparse(args.url)
    if not parsed.scheme or not parsed.netloc:
        print(f"[✗] Invalid URL: {args.url}")
        sys.exit(1)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ext = get_extension(args.js)
    lang = "JavaScript" if args.js else "TypeScript"

    # Determine which scenarios to generate
    if args.scenario == "full":
        scenarios = list(SCENARIO_MAP.keys())
    else:
        scenarios = [args.scenario]

    print(f"\n[playwright-auditor] Scaffolding {lang} tests for {args.url}\n")

    for scenario in scenarios:
        fn = SCENARIO_MAP[scenario]
        content = fn(args.url, args.js)
        filename = output_dir / f"{scenario}{ext}"
        filename.write_text(content)
        print(f"  [✓] {filename}")

    # Page Object Model
    if args.pom:
        pom_dir = output_dir / "pages"
        pom_dir.mkdir(exist_ok=True)
        pom_content = pom_page_object(args.url, args.js)
        pom_ext = ".js" if args.js else ".ts"
        pom_file = pom_dir / f"HomePage{pom_ext}"
        pom_file.write_text(pom_content)
        print(f"  [✓] {pom_file}  (Page Object Model)")

    print(f"\n[✓] {len(scenarios)} test file(s) written to {output_dir}/")
    print("\nNext step:")
    print("  bash scripts/run_audit.sh\n")


if __name__ == "__main__":
    main()
