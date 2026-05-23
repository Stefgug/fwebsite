import { test, expect } from '@playwright/test';

test.describe('Products page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/products');
  });

  test('displays the products listing', async ({ page }) => {
    // Wait for products to load (server-side rendered)
    await expect(page.getByText('All Products')).toBeVisible();
  });

  test('shows category sidebar', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Categories/i })).toBeVisible();
  });

  test('shows at least one product card', async ({ page }) => {
    // Products are rendered from mock data — at least one should be visible
    const productLinks = page.locator('a[href*="/products/"]');
    await expect(productLinks.first()).toBeVisible({ timeout: 10_000 });
  });

  test('shows mock product: MacBook Pro 14', async ({ page }) => {
    await expect(page.getByText('MacBook Pro 14')).toBeVisible({ timeout: 10_000 });
  });

  test('filtering by category updates the URL', async ({ page }) => {
    await page.getByRole('link', { name: /Electronics/i }).first().click();
    await expect(page).toHaveURL(/category=electronics/);
  });

  test('product card links to product detail page', async ({ page }) => {
    const firstProduct = page.locator('a[href*="/products/"]').first();
    const href = await firstProduct.getAttribute('href');
    await firstProduct.click();
    await expect(page).toHaveURL(new RegExp(href!.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  });

  test('page has correct title', async ({ page }) => {
    await expect(page).toHaveTitle(/Shop/i);
  });
});

test.describe('Product detail page', () => {
  test('navigates to a product detail page from the listing', async ({ page }) => {
    await page.goto('/products');
    const firstProduct = page.locator('a[href*="/products/"]').first();
    await firstProduct.click();
    // Product detail page should have an "Add to cart" button or similar
    await expect(page.getByRole('button', { name: /add to cart/i }).or(page.getByText(/add to cart/i))).toBeVisible({ timeout: 10_000 });
  });
});
