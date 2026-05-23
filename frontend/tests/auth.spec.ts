import { test, expect } from '@playwright/test';

test.describe('Login page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login');
  });

  test('shows the sign in heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Welcome back/i })).toBeVisible();
  });

  test('has email and password fields', async ({ page }) => {
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test('has a submit button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /sign in/i })).toBeVisible();
  });

  test('shows error message on invalid credentials', async ({ page }) => {
    await page.getByRole('textbox', { name: /email/i }).fill('wrong@example.com');
    await page.getByLabel(/password/i).fill('wrongpassword');
    await page.getByRole('button', { name: /sign in/i }).click();
    // Should show an error — mock returns 400 for invalid credentials
    await expect(
      page.getByText(/invalid|incorrect|error/i).or(page.getByRole('alert'))
    ).toBeVisible({ timeout: 8_000 });
  });

  test('redirects to homepage after successful login', async ({ page }) => {
    await page.getByRole('textbox', { name: /email/i }).fill('test@example.com');
    await page.getByLabel(/password/i).fill('password123');
    await page.getByRole('button', { name: /sign in/i }).click();
    await expect(page).toHaveURL('/', { timeout: 10_000 });
  });

  test('has a link to the register page', async ({ page }) => {
    const registerLink = page.getByRole('link', { name: /register|sign up|create account/i });
    await expect(registerLink).toBeVisible();
    await registerLink.click();
    await expect(page).toHaveURL('/register');
  });

  test('page title contains Sign In', async ({ page }) => {
    await expect(page).toHaveTitle(/Sign In/i);
  });
});

test.describe('Register page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/register');
  });

  test('shows the registration heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /create|register|sign up/i })).toBeVisible();
  });

  test('has username, email, and password fields', async ({ page }) => {
    await expect(page.getByRole('textbox', { name: /username/i })).toBeVisible();
    await expect(page.getByRole('textbox', { name: /email/i })).toBeVisible();
    await expect(page.getByLabel(/password/i)).toBeVisible();
  });

  test('has a submit button', async ({ page }) => {
    await expect(page.getByRole('button', { name: /register|sign up|create/i })).toBeVisible();
  });
});
