import { test, expect } from '@playwright/test';

test.describe('Homepage', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('displays the hero section with correct heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Shop Smarter/i })).toBeVisible();
  });

  test('has working Shop Now CTA button', async ({ page }) => {
    await page.getByRole('link', { name: /Shop Now/i }).click();
    await expect(page).toHaveURL('/products');
  });

  test('has working Read Our Blog button', async ({ page }) => {
    await page.getByRole('link', { name: /Read Our Blog/i }).click();
    await expect(page).toHaveURL('/blog');
  });

  test('shows the 4 feature badges (shipping, returns, payment, support)', async ({ page }) => {
    await expect(page.getByText('Free Shipping')).toBeVisible();
    await expect(page.getByText('Easy Returns')).toBeVisible();
    await expect(page.getByText('Secure Payment')).toBeVisible();
    await expect(page.getByText('24/7 Support')).toBeVisible();
  });

  test('shows category shortcuts', async ({ page }) => {
    // Scope to the "Shop by Category" section to avoid matching product card category labels
    const categorySection = page.locator('section').filter({ hasText: 'Shop by Category' });
    await expect(categorySection.getByRole('link', { name: /Electronics/i })).toBeVisible();
    await expect(categorySection.getByRole('link', { name: /Clothing/i })).toBeVisible();
    await expect(categorySection.getByRole('link', { name: /Books/i })).toBeVisible();
  });

  test('category links navigate to filtered products', async ({ page }) => {
    // Scope to the "Shop by Category" section to avoid clicking product card links
    const categorySection = page.locator('section').filter({ hasText: 'Shop by Category' });
    await categorySection.getByRole('link', { name: /Electronics/i }).click();
    await expect(page).toHaveURL(/\/products\?category=electronics/);
  });

  test('shows the Featured Products section', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Featured Products/i })).toBeVisible();
  });

  test('shows the From Our Blog section', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /From Our Blog/i })).toBeVisible();
  });

  test('bottom CTA has Create Free Account and Browse Products links', async ({ page }) => {
    await expect(page.getByRole('link', { name: /Create Free Account/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Browse Products/i })).toBeVisible();
  });

  test('page title contains ShopGeneric', async ({ page }) => {
    await expect(page).toHaveTitle(/ShopGeneric/i);
  });
});
