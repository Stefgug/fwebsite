import { test, expect } from '@playwright/test';

test.describe('Navigation', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
  });

  test('logo links to homepage', async ({ page }) => {
    await page.getByRole('link', { name: 'ShopGeneric' }).click();
    await expect(page).toHaveURL('/');
  });

  test('navbar has Shop link', async ({ page }) => {
    const shopLink = page.getByRole('navigation').getByRole('link', { name: 'Shop' });
    await expect(shopLink).toBeVisible();
    await shopLink.click();
    await expect(page).toHaveURL('/products');
  });

  test('navbar has Blog link', async ({ page }) => {
    await page.goto('/');
    const blogLink = page.getByRole('navigation').getByRole('link', { name: 'Blog' });
    await expect(blogLink).toBeVisible();
    await blogLink.click();
    await expect(page).toHaveURL('/blog');
  });

  test('navbar has Contact link', async ({ page }) => {
    await page.goto('/');
    const contactLink = page.getByRole('navigation').getByRole('link', { name: 'Contact' });
    await expect(contactLink).toBeVisible();
    await contactLink.click();
    await expect(page).toHaveURL('/contact');
  });

  test('cart icon is visible in the navbar', async ({ page }) => {
    // CartIcon renders an SVG link with no text — locate by href
    const header = page.locator('header');
    await expect(header).toBeVisible();
    const cartLink = header.locator('a[href="/cart"]');
    await expect(cartLink).toBeVisible();
  });

  test('login link is visible when not logged in', async ({ page }) => {
    // Navbar shows "Login" (not "Sign In") when user is not authenticated
    const loginLink = page.getByRole('link', { name: /^Login$/i });
    await expect(loginLink).toBeVisible();
  });

  test('404 page shows not-found message', async ({ page }) => {
    await page.goto('/this-page-does-not-exist-at-all');
    await expect(page.getByRole('heading', { name: /not found/i })).toBeVisible();
  });
});
