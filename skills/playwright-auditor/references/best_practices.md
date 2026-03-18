# Playwright Best Practices

> Patterns drawn from Microsoft's Playwright repository, Adobe's accessibility
> testing pipelines, and production usage across enterprise engineering teams.

---

## Selector Strategy

**Rule:** Always prefer user-facing attributes over implementation details.
Tests that rely on CSS classes or DOM structure break whenever a developer
refactors the UI — even when behavior hasn't changed.

```typescript
// ✅ Resilient — tied to what the user sees and interacts with
page.getByRole('button', { name: 'Add to cart' })
page.getByLabel('Shipping address')
page.getByText('Order confirmed')

// ⚠️ Fragile — breaks on refactor
page.locator('.btn-primary.add-cart')
page.locator('#shipping-addr-input')
page.locator('div > p:nth-child(3)')
```

When you must use a CSS selector (legacy code, no ARIA support), add a
`data-testid` attribute to the element and use `getByTestId`. This creates
an explicit contract between the test and the markup.

---

## Page Object Model (POM)

For suites with more than 3 test files, extract selectors and actions into
Page Object classes. This prevents selector duplication and makes refactoring
cheap — update one file, not twenty tests.

```typescript
// pages/CheckoutPage.ts
import { type Page, expect } from '@playwright/test';

export class CheckoutPage {
  constructor(private page: Page) {}

  async goto() {
    await this.page.goto('/checkout');
  }

  async fillShippingAddress(address: Address) {
    await this.page.getByLabel('Street').fill(address.street);
    await this.page.getByLabel('City').fill(address.city);
    await this.page.getByLabel('Zip code').fill(address.zip);
  }

  async placeOrder() {
    await this.page.getByRole('button', { name: 'Place order' }).click();
    await expect(this.page).toHaveURL(/\/order-confirmation/);
  }
}

// tests/checkout.spec.ts
import { test } from '@playwright/test';
import { CheckoutPage } from '../pages/CheckoutPage';

test('completes a purchase', async ({ page }) => {
  const checkout = new CheckoutPage(page);
  await checkout.goto();
  await checkout.fillShippingAddress({ street: '123 Main St', city: 'Portland', zip: '97201' });
  await checkout.placeOrder();
});
```

---

## Authentication Caching with storageState

Running a login flow before every test is slow and fragile. Cache the
authenticated session once per test run using `storageState`.

```typescript
// 1. Create auth.setup.ts
const setup = test.extend({});
setup('authenticate as admin', async ({ page }) => {
  await page.goto('/admin/login');
  await page.getByLabel('Email').fill(process.env.ADMIN_EMAIL!);
  await page.getByLabel('Password').fill(process.env.ADMIN_PASSWORD!);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await page.waitForURL('/admin/dashboard');
  await page.context().storageState({ path: 'playwright/.auth/admin.json' });
});

// 2. Reference it in playwright.config.ts
projects: [
  { name: 'setup', testMatch: /auth\.setup\.ts/ },
  {
    name: 'admin tests',
    dependencies: ['setup'],
    use: { storageState: 'playwright/.auth/admin.json' },
  },
]

// 3. Gitignore the auth file
// playwright/.auth/
```

For multi-role apps, create one setup spec per role:
`auth.admin.setup.ts`, `auth.viewer.setup.ts`, etc.

---

## expect.soft() for Non-Blocking Assertions

When you need to validate multiple independent properties and want to see
all failures at once (not just the first one), use `expect.soft()`.

```typescript
test('product page displays all required fields', async ({ page }) => {
  await page.goto('/products/123');

  // These all run regardless of which ones fail
  await expect.soft(page.getByRole('heading')).toBeVisible();
  await expect.soft(page.getByText(/\$\d+\.\d{2}/)).toBeVisible();  // Price
  await expect.soft(page.getByRole('button', { name: 'Add to cart' })).toBeEnabled();
  await expect.soft(page.getByRole('img', { name: /product/i })).toBeVisible();

  // Hard assertion — if stock status is wrong, stop here
  await expect(page.getByTestId('stock-status')).toBeVisible();
});
// All soft failures are reported together at the end
```

---

## Test Tagging Strategy

Tag tests by their purpose and execution frequency. Use `--grep` in CI to
run only the relevant tier.

```typescript
test('@smoke page loads', async ({ page }) => { ... });
test('@regression form validation handles XSS', async ({ page }) => { ... });
test('@a11y navigation is keyboard accessible', async ({ page }) => { ... });
test('@perf LCP under 2.5s', async ({ page }) => { ... });
test('@visual hero image matches snapshot', async ({ page }) => { ... });
```

**CI pipeline tiers:**

| Tier | Tags | When | Duration |
|------|------|------|----------|
| Pre-merge | `@smoke` | Every commit | ~2 min |
| Post-merge | `@smoke @regression` | Every merge to main | ~10 min |
| Nightly | All | Scheduled 2am | ~30 min |
| Release | All + `@visual` | Before deploy | ~45 min |

---

## Handling Flaky Tests

Flakiness is almost always caused by timing assumptions, not randomness.

**Strategy 1 — Use event-driven waits, not `page.waitForTimeout`:**

```typescript
// ❌ Arbitrary delay — will still fail on slow machines
await page.waitForTimeout(2000);
await expect(modal).toBeVisible();

// ✅ Wait for the actual condition
await expect(modal).toBeVisible({ timeout: 10_000 });
// or
await page.waitForLoadState('networkidle');
```

**Strategy 2 — Disable animations in tests:**

```typescript
// playwright.config.ts
use: {
  contextOptions: {
    reducedMotion: 'reduce',
  },
}
// or per-test:
await page.emulateMedia({ reducedMotion: 'reduce' });
```

**Strategy 3 — Mark slow tests explicitly:**

```typescript
test('heavy data export', async ({ page }) => {
  test.slow(); // Triples the timeout automatically
  await page.goto('/export');
  await page.getByRole('button', { name: 'Export all' }).click();
  await expect(page.getByRole('status')).toHaveText('Export complete', {
    timeout: 60_000,
  });
});
```

**Strategy 4 — Configure retries per-test (not globally):**

```typescript
test('third-party widget', async ({ page }) => {
  test.info().annotations.push({ type: 'flaky', description: 'third-party iframe' });
  // Global retry covers this without inflating the whole suite
});
```

---

## Parallel Execution

Playwright runs test files in parallel by default. Tune `workers` based on
your machine and whether tests share state.

```typescript
// playwright.config.ts
fullyParallel: true,   // Also parallelize tests within a file
workers: process.env.CI ? 4 : '50%',  // Use 50% of cores locally
```

**When to disable parallelism:**
- Tests that write to a shared database without cleanup
- Tests that depend on execution order (refactor these instead)
- E2E flows with a real payment gateway

```typescript
// Isolate a single file from parallelism
test.describe.configure({ mode: 'serial' });
```

---

## Visual Regression

```typescript
// Generate baseline: npx playwright test --update-snapshots
// Subsequent runs: npx playwright test (diffs against baseline)

await expect(page).toHaveScreenshot('homepage.png', {
  maxDiffPixelRatio: 0.02,  // 2% pixel diff tolerance
  mask: [
    page.locator('[data-testid="live-clock"]'),  // Mask dynamic content
    page.locator('.ad-slot'),
  ],
  animations: 'disabled',  // Freeze animations for stable screenshots
});
```

Store baseline screenshots in version control. Review diffs in the HTML
report before approving changes with `--update-snapshots`.

---

## CI/CD Checklist

Before adding Playwright to a pipeline, verify:

- [ ] `BASE_URL` environment variable set to staging URL
- [ ] Auth credentials in secrets (`TEST_EMAIL`, `TEST_PASSWORD`)
- [ ] `playwright/.auth/` in `.gitignore`
- [ ] `test-results/` in `.gitignore`
- [ ] HTML report uploaded as CI artifact on every run
- [ ] Traces uploaded as artifact on failure only
- [ ] `--retries=2` in CI to absorb infrastructure flakiness
- [ ] `--workers=4` or less to avoid overwhelming the staging server
- [ ] `forbidOnly: !!process.env.CI` to prevent `test.only` from being merged
