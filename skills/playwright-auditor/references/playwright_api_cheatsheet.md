# Playwright API Cheatsheet

> **Source:** https://playwright.dev/docs  
> **Note:** Run `python scripts/fetch_docs.py --all` to refresh with latest version

---

## Selector Priority (Most → Least Resilient)

```typescript
// 1. Role-based (ARIA) — most resilient to DOM changes
page.getByRole('button', { name: 'Submit' })
page.getByRole('link', { name: 'Home' })
page.getByRole('heading', { level: 1 })
page.getByRole('textbox', { name: 'Email' })
page.getByRole('checkbox', { name: 'Accept terms' })

// 2. Label-based
page.getByLabel('Email address')

// 3. Placeholder
page.getByPlaceholder('Search...')

// 4. Text content
page.getByText('Welcome back')
page.getByText(/partial match/i)

// 5. Alt text (images)
page.getByAltText('Company logo')

// 6. Test ID (requires data-testid attribute)
page.getByTestId('submit-button')

// 7. CSS / XPath — last resort
page.locator('.submit-btn')
page.locator('//button[@type="submit"]')
```

---

## Locator Chaining & Filtering

```typescript
// Filter by text
page.getByRole('listitem').filter({ hasText: 'Product A' })

// Filter by child element
page.getByRole('listitem').filter({ has: page.getByRole('heading') })

// First / last / nth
page.getByRole('button').first()
page.getByRole('button').last()
page.getByRole('button').nth(2)

// Logical operators
const saveOrCancel = page.getByRole('button', { name: 'Save' })
  .or(page.getByRole('button', { name: 'Cancel' }));

// Chaining (narrowing scope)
const row = page.getByRole('row').filter({ hasText: 'John' });
row.getByRole('cell').nth(2);
```

---

## Assertions (expect)

```typescript
// Visibility
await expect(locator).toBeVisible();
await expect(locator).toBeHidden();
await expect(locator).toBeAttached();

// Text
await expect(locator).toHaveText('Exact match');
await expect(locator).toHaveText(/regex match/i);
await expect(locator).toContainText('partial');
await expect(locator).toHaveInnerHTML('<b>html</b>');

// Values & state
await expect(locator).toHaveValue('input value');
await expect(locator).toBeChecked();
await expect(locator).toBeDisabled();
await expect(locator).toBeEnabled();
await expect(locator).toBeEditable();
await expect(locator).toBeEmpty();

// Attributes & classes
await expect(locator).toHaveAttribute('aria-expanded', 'true');
await expect(locator).toHaveClass(/active/);
await expect(locator).toHaveCSS('color', 'rgb(255, 0, 0)');

// Count
await expect(locator).toHaveCount(5);

// Page-level
await expect(page).toHaveURL('/dashboard');
await expect(page).toHaveURL(/\/dashboard/);
await expect(page).toHaveTitle('Dashboard — MyApp');

// Screenshot regression
await expect(page).toHaveScreenshot('page.png', { maxDiffPixelRatio: 0.02 });
await expect(locator).toHaveScreenshot('component.png');

// Soft assertions (collect all failures, don't stop on first)
await expect.soft(locator).toHaveText('text');
await expect.soft(locator).toBeVisible();
// At end of test, all soft failures are reported together
```

---

## Navigation & Waiting

```typescript
// Navigation
await page.goto('https://example.com');
await page.goto('/relative-path');
await page.goBack();
await page.goForward();
await page.reload();

// Wait strategies
await page.waitForLoadState('networkidle');    // No network for 500ms
await page.waitForLoadState('domcontentloaded');
await page.waitForLoadState('load');

// Wait for URL change
await page.waitForURL('/dashboard');
await page.waitForURL(/\/dashboard/);

// Wait for element
await locator.waitFor({ state: 'visible' });
await locator.waitFor({ state: 'hidden' });
await locator.waitFor({ state: 'attached' });

// Wait for response
const response = await page.waitForResponse('**/api/users');
const response = await page.waitForResponse(
  resp => resp.url().includes('/api') && resp.status() === 200
);
```

---

## Actions

```typescript
// Click
await locator.click();
await locator.click({ button: 'right' });
await locator.click({ modifiers: ['Shift'] });
await locator.dblclick();
await locator.hover();

// Keyboard & typing
await locator.fill('text to fill');      // Clears first, then fills
await locator.type('char by char');      // Simulates keystrokes
await locator.press('Enter');
await locator.press('Control+a');
await locator.clear();

// Select
await locator.selectOption('value');
await locator.selectOption({ label: 'Option Label' });
await locator.selectOption(['multi', 'select']);

// Checkboxes & radios
await locator.check();
await locator.uncheck();
await locator.setChecked(true);

// File upload
await locator.setInputFiles('path/to/file.pdf');
await locator.setInputFiles(['file1.jpg', 'file2.jpg']);

// Drag and drop
await locator.dragTo(targetLocator);
```

---

## Network Interception

```typescript
// Mock a route
await page.route('**/api/users', async route => {
  await route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify([{ id: 1, name: 'Mock User' }]),
  });
});

// Abort requests
await page.route('**/*.png', route => route.abort());

// Modify response
await page.route('**/api/data', async route => {
  const response = await route.fetch();
  const json = await response.json();
  json.extra = 'injected';
  await route.fulfill({ response, json });
});

// Capture requests
page.on('request', request => console.log(request.url()));
page.on('response', response => console.log(response.status()));

// Wait for specific API call
const [response] = await Promise.all([
  page.waitForResponse('**/api/submit'),
  page.getByRole('button', { name: 'Submit' }).click(),
]);
const data = await response.json();
```

---

## Auth with storageState

```typescript
// auth.setup.ts — runs once, saves session
import { test as setup } from '@playwright/test';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');
  await page.getByLabel('Email').fill(process.env.TEST_EMAIL!);
  await page.getByLabel('Password').fill(process.env.TEST_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('/dashboard');
  await page.context().storageState({ path: 'auth.json' });
});

// playwright.config.ts — wire up the dependency
projects: [
  { name: 'setup', testMatch: /auth\.setup/ },
  {
    name: 'chromium',
    dependencies: ['setup'],
    use: { storageState: 'auth.json' },
  },
]
```

---

## Fixtures & Hooks

```typescript
// test.beforeEach / afterEach
test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

// test.beforeAll / afterAll (shared across tests in describe block)
test.beforeAll(async ({ browser }) => {
  const context = await browser.newContext();
  // ...
});

// Custom fixtures
import { test as base } from '@playwright/test';

const test = base.extend<{ loggedInPage: Page }>({
  loggedInPage: async ({ page }, use) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('test@example.com');
    await page.getByLabel('Password').fill('password');
    await page.getByRole('button', { name: 'Sign in' }).click();
    await use(page);
  },
});

test('uses logged-in fixture', async ({ loggedInPage }) => {
  await expect(loggedInPage).toHaveURL('/dashboard');
});
```

---

## Configuration Reference (playwright.config.ts)

```typescript
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  timeout: 30_000,           // Per-test timeout (ms)
  expect: { timeout: 5_000 }, // Assertion timeout (ms)

  reporter: [
    ['html'],
    ['json', { outputFile: 'test-results/results.json' }],
    ['list'],
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },

  projects: [
    // Setup project (auth)
    { name: 'setup', testMatch: /.*\.setup\.ts/ },

    // Browser projects
    {
      name: 'chromium',
      dependencies: ['setup'],
      use: {
        ...devices['Desktop Chrome'],
        storageState: 'auth.json',
      },
    },
    { name: 'firefox', use: { ...devices['Desktop Firefox'] } },
    { name: 'webkit',  use: { ...devices['Desktop Safari'] } },

    // Mobile
    { name: 'mobile-chrome', use: { ...devices['Pixel 5'] } },
    { name: 'mobile-safari', use: { ...devices['iPhone 12'] } },
  ],

  // Auto-start dev server for local runs
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
  },
});
```

---

## CLI Reference

```bash
# Run all tests
npx playwright test

# Run specific file
npx playwright test tests/smoke.spec.ts

# Run by tag
npx playwright test --grep @smoke
npx playwright test --grep-invert @slow

# Run in specific browser
npx playwright test --project=chromium

# Run headed (see the browser)
npx playwright test --headed

# Debug mode
npx playwright test --debug

# UI mode (interactive)
npx playwright test --ui

# Update snapshots
npx playwright test --update-snapshots

# Show HTML report
npx playwright show-report

# Show trace
npx playwright show-trace test-results/trace.zip

# Code generation (record interactions)
npx playwright codegen https://example.com
```
