import { defineConfig, devices } from '@playwright/test';

const isCI = !!process.env.CI;

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: 30_000,
  retries: isCI ? 1 : 0,
  workers: isCI ? 1 : undefined,
  reporter: isCI
    ? [['json', { outputFile: 'test-results/results.json' }], ['html', { open: 'never' }], ['list']]
    : [['html', { open: 'on-failure' }], ['list']],

  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],

  webServer: [
    {
      // Mock Strapi on port 1999 (avoids conflict with real Strapi on 1338)
      command: 'node ../scripts/mock-strapi.js',
      port: 1999,
      timeout: 10_000,
      reuseExistingServer: !isCI,
      env: { MOCK_STRAPI_PORT: '1999' },
    },
    {
      // In CI: pre-compile all routes (eliminates lazy-compile race conditions)
      // Locally: dev mode for fast iteration
      command: isCI ? 'npm run build && npm start' : 'npm run dev',
      port: 3000,
      timeout: isCI ? 180_000 : 60_000,
      reuseExistingServer: !isCI,
      env: {
        NEXT_PUBLIC_STRAPI_URL: 'http://localhost:1999',
        STRAPI_API_TOKEN: 'mock-token',
      },
    },
  ],
});
