import { test, expect } from '@playwright/test';

test('navigate provider dashboard', async ({ page }) => {
  await page.goto('/login');
  // simulate auth logic to bypass real login
  await page.goto('/provider');
  await expect(page.locator('h1')).toContainText('Provider Dashboard');
  await page.click('text=My Nodes');
  await expect(page).toHaveURL('/provider/nodes');
});
