import { test, expect } from '@playwright/test';

test.describe('Cart page — empty state', () => {
  test.beforeEach(async ({ page }) => {
    // Clear localStorage to ensure empty cart
    await page.addInitScript(() => localStorage.clear());
    await page.goto('/cart');
  });

  test('shows empty cart message', async ({ page }) => {
    await expect(page.getByText(/cart is empty/i)).toBeVisible();
  });

  test('shows a Browse Products button', async ({ page }) => {
    const link = page.getByRole('link', { name: /Browse Products/i });
    await expect(link).toBeVisible();
    await link.click();
    await expect(page).toHaveURL('/products');
  });
});

test.describe('Cart — adding products', () => {
  test('can add a product to cart from the product listing', async ({ page }) => {
    await page.goto('/products');

    // Click the first product
    const firstProduct = page.locator('a[href*="/products/"]').first();
    await firstProduct.click();

    // Click Add to Cart
    const addToCart = page.getByRole('button', { name: /add to cart/i });
    await addToCart.waitFor({ timeout: 10_000 });
    await addToCart.click();

    // Navigate to cart
    await page.goto('/cart');

    // Cart should now have an item
    await expect(page.getByText(/Shopping Cart/i)).toBeVisible();
    await expect(page.getByText(/cart is empty/i)).not.toBeVisible();
  });

  test('cart icon shows item count after adding a product', async ({ page }) => {
    await page.goto('/products');

    const firstProduct = page.locator('a[href*="/products/"]').first();
    await firstProduct.click();

    const addToCart = page.getByRole('button', { name: /add to cart/i });
    await addToCart.waitFor({ timeout: 10_000 });
    await addToCart.click();

    // Cart count badge should appear in header
    const cartBadge = page.locator('header').getByText('1');
    await expect(cartBadge).toBeVisible({ timeout: 5_000 });
  });
});

test.describe('Checkout', () => {
  test('cart has a Checkout button when not empty', async ({ page }) => {
    // Pre-fill cart via localStorage
    await page.addInitScript(() => {
      const cart = {
        state: {
          items: [{ productId: 1, name: 'MacBook Pro 14', price: 1999, quantity: 1, image: null }]
        },
        version: 0,
      };
      localStorage.setItem('cart-store', JSON.stringify(cart));
    });

    await page.goto('/cart');
    const checkout = page.getByRole('link', { name: /checkout/i }).or(page.getByRole('button', { name: /checkout/i }));
    await expect(checkout).toBeVisible({ timeout: 5_000 });
  });
});
