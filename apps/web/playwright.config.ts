import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright config.
 *
 * Default `BASE_URL` is the production deployment at quant.ledgertm.com.
 * Override with `BASE_URL=http://localhost:5173` for local dev runs.
 *
 * Timeouts are deliberately generous — the happy-path test exercises a full
 * OIDC redirect chain and (when training=true) waits for a ~30-second LightGBM
 * training run to complete.
 */

const BASE_URL = process.env.BASE_URL ?? 'https://quant.ledgertm.com';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: BASE_URL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    ignoreHTTPSErrors: false,
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
});
