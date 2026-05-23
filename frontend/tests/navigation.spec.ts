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
    // Cart icon is present in the header
    const header = page.locator('header');
    await expect(header).toBeVisible();
    // There should be a link to the cart
    const cartLink = page.getByRole('link', { name: /cart/i });
    await expect(cartLink).toBeVisible();
  });

  test('sign in link is visible when not logged in', async ({ page }) => {
    const signInLink = page.getByRole('link', { name: /sign in/i });
    await expect(signInLink).toBeVisible();
  });

  test('404 page shows not-found message', async ({ page }) => {
    await page.goto('/this-page-does-not-exist-at-all');
    await expect(page.getByRole('heading', { name: /not found/i })).toBeVisible();
  });
});
