import { test, expect } from '@playwright/test';

test('customer deployment flow', async ({ page }) => {
  await page.goto('/login');
  await page.fill('input[type="email"]', 'customer@test.com');
  await page.fill('input[type="password"]', 'password');
  // Select customer role
  await page.click('button[role="combobox"]');
  await page.click('div[role="option"]:has-text("Model Customer")');
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL('/customer');
  await page.goto('/customer/models');

  // Verify catalog loads
  await expect(page.locator('h1').first()).toContainText('Model Catalog');
});
