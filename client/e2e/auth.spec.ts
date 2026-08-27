import { test, expect } from '@playwright/test';

test('login and redirect to provider dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'provider@test.com');
  await page.fill('input[type="password"]', 'password');
  // Assume default role is provider based on UI.
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/provider');
});
