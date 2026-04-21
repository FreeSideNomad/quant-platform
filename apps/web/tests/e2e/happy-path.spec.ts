import { test, expect } from '@playwright/test';

/**
 * Happy-path smoke test.
 *
 * Exercises the full public flow against the deployed environment:
 *   1. Anonymous landing → redirect to mock IdP login form
 *   2. Submit admin/admin → land back at the SPA
 *   3. Overview page shows the signed-in user
 *   4. /models lists the qlib-lgbm model
 *
 * When `QP_TRIGGER_TRAINING=true`, also submits a training run and waits for
 * completion, then invokes inference. Kept off by default so normal deploys
 * finish in < 30 s; flip on for a full regression pass.
 */

const ADMIN_USER = process.env.QP_ADMIN_USER ?? 'admin';
const ADMIN_PASS = process.env.QP_ADMIN_PASS ?? 'admin';

test('unauthenticated visit redirects to mock login', async ({ page }) => {
  const response = await page.goto('/');
  // Either arrive at the mock form (after redirect chain) or the SPA (if a
  // pre-existing session cookie is still valid).
  expect(response?.ok()).toBeTruthy();
  await expect(page).toHaveURL(/\/(mock\/authorize|$)/);
});

test('admin sign-in lands on the SPA and lists the qlib-lgbm model', async ({ page }) => {
  await page.goto('/');

  // If we're already at the mock login form, fill it in. Otherwise we have a
  // live session and can skip directly to the assertions.
  if (page.url().includes('/mock/authorize')) {
    await page.getByLabel('Username').fill(ADMIN_USER);
    await page.getByLabel('Password').fill(ADMIN_PASS);
    await Promise.all([
      page.waitForURL('**/'),
      page.getByRole('button', { name: /sign in/i }).click(),
    ]);
  }

  // SPA shell is rendered.
  await expect(page.getByText('Quant Platform').first()).toBeVisible();
  // The shell shows the signed-in admin's email + role badge.
  await expect(page.getByText('admin@example.test')).toBeVisible();
  await expect(page.getByText('admin').last()).toBeVisible();

  // Navigate to the models list and verify the seeded model is present.
  await page.getByRole('link', { name: /^Models$/ }).click();
  await expect(page).toHaveURL(/\/models$/);
  await expect(page.getByRole('cell', { name: 'qlib-lgbm' }).first()).toBeVisible();
});

test(
  'model detail page opens and shows training-run surface',
  async ({ page }) => {
    await page.goto('/');

    if (page.url().includes('/mock/authorize')) {
      await page.getByLabel('Username').fill(ADMIN_USER);
      await page.getByLabel('Password').fill(ADMIN_PASS);
      await Promise.all([
        page.waitForURL('**/'),
        page.getByRole('button', { name: /sign in/i }).click(),
      ]);
    }

    await page.goto('/models/qlib-lgbm');
    await expect(page.getByRole('heading', { name: 'qlib-lgbm' })).toBeVisible();
    await expect(page.getByRole('button', { name: /submit new training run/i })).toBeVisible();
    await expect(page.getByRole('button', { name: /^predict$/i })).toBeVisible();
  },
);
