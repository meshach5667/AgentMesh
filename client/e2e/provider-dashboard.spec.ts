import { test, expect } from '@playwright/test';

test('navigate provider dashboard', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'provider@test.com');
  await page.fill('input[type="password"]', 'password');
  await page.click('button[type="submit"]');
  await expect(page).toHaveURL('/provider');

  await expect(page.locator('h1').first()).toContainText('Overview');
  await page.click('text=Network Nodes');
  await expect(page).toHaveURL('/provider/nodes');
});
