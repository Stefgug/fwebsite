import { test, expect } from '@playwright/test';

test.describe('About page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/about');
  });

  test('page title contains ShopGeneric', async ({ page }) => {
    await expect(page).toHaveTitle(/ShopGeneric/i);
  });

  test('displays the hero heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /About ShopGeneric/i })).toBeVisible();
  });

  test('displays the hero description text', async ({ page }) => {
    await expect(page.getByText(/We started ShopGeneric in 2018/i)).toBeVisible();
  });

  test('displays all four stats', async ({ page }) => {
    await expect(page.getByText('50K+')).toBeVisible();
    await expect(page.getByText('Happy customers')).toBeVisible();
    await expect(page.getByText('1,200+')).toBeVisible();
    await expect(page.getByText('Products in catalog')).toBeVisible();
    await expect(page.getByText('24/7')).toBeVisible();
    await expect(page.getByText('Customer support')).toBeVisible();
    await expect(page.getByText('4.8/5')).toBeVisible();
    await expect(page.getByText('Average rating')).toBeVisible();
  });

  test('displays the Our values section heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Our values/i })).toBeVisible();
  });

  test('displays all three value cards', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Quality first/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Fair pricing/i })).toBeVisible();
    await expect(page.getByRole('heading', { name: /Customer-first/i })).toBeVisible();
  });

  test('displays the CTA section heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Ready to start shopping/i })).toBeVisible();
  });

  test('Browse Products CTA link navigates to /products', async ({ page }) => {
    await page.getByRole('link', { name: /Browse Products/i }).click();
    await expect(page).toHaveURL('/products');
  });

  test('Contact Us CTA link navigates to /contact', async ({ page }) => {
    await page.getByRole('link', { name: /Contact Us/i }).click();
    await expect(page).toHaveURL('/contact');
  });
});
