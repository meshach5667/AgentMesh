import { test, expect } from '@playwright/test';

test('customer deployment flow', async ({ page }) => {
  await page.goto('/login'); // Mocked login to customer role
  await page.goto('/customer/models');
  await page.click('text=Deploy');
  await expect(page.locator('h1')).toContainText('Deploy Model');
  await page.click('text=Deploy Now');
});
