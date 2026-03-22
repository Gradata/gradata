---
name: e2e-testing
description: Use when user wants to Write, run, and fix Playwright E2E tests. Triggers on "write a test", "test the flow", "e2e test", "end to end", "test coverage", "regression test", "test suite", "Page Object", "playwright test". For live browsing and screenshots of external sites, use the playwright-skill instead.
---

# E2E Testing with Playwright

Repeatable test scripts that live in version control and run in CI. Uses Playwright Test runner (not raw node scripts).

## When This Fires vs When Playwright-Skill Fires

This skill handles **repeatable test automation**:
- "Write a test for the campaign builder flow"
- "Add regression tests for onboarding"
- "Run the test suite"
- "Fix the failing login test"
- "Check test coverage"

The playwright-skill (skills/playwright-skill/) handles **live interactive browsing**:
- "Go look at the staging deploy"
- "Screenshot their homepage"
- "Check what tech stack they use"
- "Browse the competitor's pricing page"

If the task produces a .spec.ts file that runs repeatedly, it belongs here.
If the task is a one-off browser action, it belongs in playwright-skill.

## Project Structure

```
tests/
  e2e/
    pages/              # Page Object Models
      BasePage.ts
      LoginPage.ts
      CampaignBuilder.ts
    fixtures/           # Test fixtures and helpers
      auth.fixture.ts
      test-data.ts
    specs/              # Test specs
      login.spec.ts
      campaign-builder.spec.ts
    playwright.config.ts
```

## Setup (first time only)

```bash
cd "C:/Users/olive/OneDrive/Desktop/Sprites Work"
npx playwright install chromium
```

Playwright is already installed in package.json (^1.58.2). No additional install needed.

## Page Object Pattern

Every page gets a class in tests/e2e/pages/. Pages encapsulate selectors and actions. Tests never use raw selectors.

```typescript
// tests/e2e/pages/BasePage.ts
import { Page, Locator } from '@playwright/test';

export class BasePage {
  constructor(protected page: Page) {}

  async navigate(path: string) {
    await this.page.goto(path);
  }

  async waitForLoad() {
    await this.page.waitForLoadState('networkidle');
  }
}
```

```typescript
// tests/e2e/pages/LoginPage.ts
import { BasePage } from './BasePage';

export class LoginPage extends BasePage {
  readonly emailInput = this.page.locator('[data-testid="email"]');
  readonly passwordInput = this.page.locator('[data-testid="password"]');
  readonly submitButton = this.page.locator('[data-testid="submit"]');
  readonly errorMessage = this.page.locator('[data-testid="error"]');

  async login(email: string, password: string) {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }
}
```

## Writing Tests

```typescript
// tests/e2e/specs/login.spec.ts
import { test, expect } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';

test.describe('Login Flow', () => {
  let loginPage: LoginPage;

  test.beforeEach(async ({ page }) => {
    loginPage = new LoginPage(page);
    await loginPage.navigate('/login');
  });

  test('successful login redirects to dashboard', async ({ page }) => {
    await loginPage.login('user@example.com', 'password123');
    await expect(page).toHaveURL(/dashboard/);
  });

  test('invalid credentials show error', async ({ page }) => {
    await loginPage.login('wrong@example.com', 'badpass');
    await expect(loginPage.errorMessage).toBeVisible();
  });
});
```

## Running Tests

```bash
# Run all E2E tests
npx playwright test --config tests/e2e/playwright.config.ts

# Run a specific spec
npx playwright test tests/e2e/specs/login.spec.ts

# Run with visible browser (debugging)
npx playwright test --headed

# Run with trace (for failure analysis)
npx playwright test --trace on

# Show HTML report after run
npx playwright show-report
```

## Playwright Config

```typescript
// tests/e2e/playwright.config.ts
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './specs',
  timeout: 30000,
  retries: 1,
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:3000',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    viewport: { width: 1280, height: 720 },
  },
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
  ],
});
```

## Workflow for Claude Code

When asked to write or fix E2E tests:

1. **Check if tests/e2e/ exists.** If not, scaffold the directory structure and playwright.config.ts.
2. **Check if a Page Object exists for the target page.** If not, create it in tests/e2e/pages/.
3. **Write the test spec** in tests/e2e/specs/ using existing Page Objects.
4. **Run the test** via bash: `npx playwright test tests/e2e/specs/[name].spec.ts --config tests/e2e/playwright.config.ts`
5. **Read the output.** If failures, read the error, fix the test or Page Object, re-run.
6. **Report results** with pass/fail count and any screenshots from failures.

Never use the Playwright MCP for running test suites. The MCP is for live browsing only.

## Fixtures and Test Data

Reusable test setup goes in tests/e2e/fixtures/:

```typescript
// tests/e2e/fixtures/auth.fixture.ts
import { test as base } from '@playwright/test';
import { LoginPage } from '../pages/LoginPage';

export const test = base.extend<{ loggedInPage: LoginPage }>({
  loggedInPage: async ({ page }, use) => {
    const loginPage = new LoginPage(page);
    await loginPage.navigate('/login');
    await loginPage.login(
      process.env.TEST_EMAIL || 'test@example.com',
      process.env.TEST_PASSWORD || 'testpass'
    );
    await page.waitForURL(/dashboard/);
    await use(loginPage);
  },
});
```

## Rules

- Every new page interaction gets a Page Object. No raw selectors in spec files.
- Use data-testid attributes for selectors (not CSS classes or DOM structure).
- Tests must be idempotent. Clean up test data in afterEach/afterAll.
- Screenshots on failure only (configured in playwright.config.ts).
- Never hardcode credentials in test files. Use env vars or fixtures.
- Keep specs focused. One describe block per user flow.
- Run headless by default. Use --headed only for debugging.
