# Common Playwright Errors & Fixes

Quick reference for the most frequent errors encountered when running
Playwright tests. Each entry includes root cause and a concrete fix.

---

## 1. TimeoutError: waiting for locator to be visible

**Message:**
```
TimeoutError: locator.click: Timeout 30000ms exceeded.
waiting for locator('.submit-btn') to be visible
```

**Root causes:**
- Element doesn't exist in the DOM yet (async render)
- Wrong selector (typo or stale selector after refactor)
- Element is in the DOM but CSS `display:none` or `visibility:hidden`
- Element is inside a shadow DOM

**Fix:**
```typescript
// Option 1: Switch to a resilient selector
await page.getByRole('button', { name: 'Submit' }).click();

// Option 2: Explicit wait before action
await page.getByRole('button', { name: 'Submit' }).waitFor({ state: 'visible' });
await page.getByRole('button', { name: 'Submit' }).click();

// Option 3: Increase timeout for slow renders
await page.getByRole('button', { name: 'Submit' }).click({ timeout: 15_000 });

// Option 4: Shadow DOM
await page.locator('my-component').locator('button').click();
```

---

## 2. Error: browserType.launch — Executable doesn't exist

**Message:**
```
Error: browserType.launch: Executable doesn't exist at
/home/user/.cache/ms-playwright/chromium-1097/chrome-linux/chrome
```

**Root cause:** Browser binaries were not downloaded.

**Fix:**
```bash
# Install all browsers with system dependencies
npx playwright install --with-deps

# Install specific browser only
npx playwright install chromium --with-deps

# In Docker, use the official Playwright image instead
FROM mcr.microsoft.com/playwright:v1.44.0-jammy
```

---

## 3. net::ERR_CONNECTION_REFUSED in CI

**Message:**
```
page.goto: net::ERR_CONNECTION_REFUSED at http://localhost:3000
```

**Root cause:** No web server is running when the tests execute in CI.

**Fix — Option A: Use `webServer` in config:**
```typescript
// playwright.config.ts
webServer: {
  command: 'npm run start',
  url: 'http://localhost:3000',
  reuseExistingServer: !process.env.CI,
  timeout: 120_000,
},
```

**Fix — Option B: Set `BASE_URL` to a deployed staging environment:**
```yaml
# .github/workflows/playwright.yml
env:
  BASE_URL: https://staging.example.com
```

---

## 4. Flaky Tests — Intermittent Pass/Fail

**Symptoms:** Test passes locally and fails in CI, or passes sometimes
and fails on retries.

**Common causes and fixes:**

| Cause | Fix |
|-------|-----|
| `waitForTimeout` too short | Replace with `waitForLoadState` or `expect().toBeVisible()` |
| Animation still running | Add `reducedMotion: 'reduce'` to config |
| Race condition on API response | Use `page.waitForResponse('**/api/endpoint')` |
| State from previous test | Ensure `test.afterEach` clears state |
| Resource exhaustion in CI | Reduce `workers` count |

```typescript
// Pattern: wait for API call before asserting UI update
const [response] = await Promise.all([
  page.waitForResponse(resp => resp.url().includes('/api/save')),
  page.getByRole('button', { name: 'Save' }).click(),
]);
await expect(page.getByRole('alert')).toHaveText('Saved successfully');
```

---

## 5. Cross-Browser Selector Mismatch

**Message:**
```
locator.click: Error: strict mode violation: locator(':text("Submit")') 
resolved to 2 elements
```

**Root cause:** A selector that finds one element in Chromium finds
multiple in Firefox/WebKit due to rendering differences.

**Fix:** Use role-based selectors which are semantically unambiguous:
```typescript
// ❌ Ambiguous text match
await page.locator(':text("Submit")').click();

// ✅ Scoped role match — always unique
await page.getByRole('button', { name: 'Submit' }).click();

// ✅ Or scope to a form
await page.getByRole('form').getByRole('button', { name: 'Submit' }).click();
```

---

## 6. Screenshot Diff Failures (Visual Regression)

**Message:**
```
Screenshot comparison failed: 1532 pixels are different
```

**Root causes:**
- Dynamic content (timestamps, ads, random avatars) changes between runs
- Anti-aliasing differences between Chromium versions
- Font rendering differs across OS

**Fix:**
```typescript
await expect(page).toHaveScreenshot('page.png', {
  maxDiffPixelRatio: 0.02,  // Tolerate 2% pixel difference
  mask: [
    page.locator('[data-testid="timestamp"]'),
    page.locator('.dynamic-banner'),
    page.getByRole('img', { name: /avatar/i }),
  ],
  animations: 'disabled',
});

// Update baseline after intentional visual changes:
// npx playwright test --update-snapshots
```

---

## 7. StorageState Authentication Fails

**Message:**
```
Error: read ECONNRESET / page.goto redirects to /login unexpectedly
```

**Root causes:**
- `auth.json` is stale (session expired)
- Auth file path is incorrect
- Setup project didn't run before dependent project

**Fix:**
```typescript
// playwright.config.ts — ensure correct dependency chain
projects: [
  { name: 'setup', testMatch: /auth\.setup/ },
  {
    name: 'chromium',
    dependencies: ['setup'],           // This forces setup to run first
    use: { storageState: 'playwright/.auth/user.json' },
  },
],

// auth.setup.ts — wait for actual post-login redirect
setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.TEST_EMAIL!);
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  // Wait for a URL that confirms login success
  await page.waitForURL(url => !url.pathname.includes('/login'), { timeout: 15_000 });
  await page.context().storageState({ path: 'playwright/.auth/user.json' });
});
```

---

## 8. Test Isolation — State Leaking Between Tests

**Symptom:** Tests pass in isolation but fail when run in sequence.

**Root cause:** A test leaves shared state (cookies, localStorage, database
records) that affects the next test.

**Fix:**
```typescript
// Each test gets a fresh browser context (Playwright default)
// For database state, reset in beforeEach:
test.beforeEach(async ({ request }) => {
  await request.post('/api/test/reset-db');
});

// For localStorage:
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
});
```

---

## 9. ENOSPC: No space left on device (CI)

**Message:**
```
ENOSPC: no space left on device, write '...trace.zip'
```

**Root cause:** Video recordings and traces fill up CI disk space over time.

**Fix:**
```typescript
// playwright.config.ts — only keep artifacts for failures
use: {
  trace: 'retain-on-failure',     // Not 'on'
  video: 'retain-on-failure',     // Not 'on'
  screenshot: 'only-on-failure',  // Not 'on'
},
```

And clean up old results in your pipeline:
```yaml
- name: Clean old test results
  run: rm -rf test-results/ playwright-report/
  if: always()
```

---

## 10. page.waitForNavigation is Deprecated

**Message:**
```
Warning: page.waitForNavigation is deprecated. Use page.waitForURL instead.
```

**Fix:**
```typescript
// ❌ Deprecated
await Promise.all([
  page.waitForNavigation(),
  page.click('a'),
]);

// ✅ Modern — waitForURL is specific and reliable
await page.getByRole('link', { name: 'Dashboard' }).click();
await page.waitForURL('/dashboard');
// or just assert the URL directly (Playwright auto-waits):
await expect(page).toHaveURL('/dashboard');
```

---

## Quick Diagnostic Checklist

When a test fails unexpectedly, work through this list:

1. **Run with `--headed`** — watch what actually happens in the browser
2. **Run with `--debug`** — step through actions interactively
3. **Check the trace** — `npx playwright show-trace test-results/*/trace.zip`
4. **Add `await page.pause()`** — drop into interactive debug at a specific line
5. **Check the screenshot** — automatic failure screenshot in `test-results/`
6. **Verify the selector** — use Playwright Inspector: `npx playwright codegen`
7. **Check environment** — is `BASE_URL` pointing at the right server?
8. **Check browser version** — run `npx playwright install` to update binaries
