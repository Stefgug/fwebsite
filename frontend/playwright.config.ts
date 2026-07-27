import { defineConfig, devices } from '@playwright/test';

const isCI = !!process.env.CI;
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? 3000);
const mockStrapiPort = Number(process.env.MOCK_STRAPI_PORT ?? 1999);

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
    baseURL: `http://localhost:${frontendPort}`,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },

  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],

  webServer: [
    {
      // Mock Strapi (avoids conflict with the real Strapi dev server)
      command: 'node ../scripts/mock-strapi.js',
      port: mockStrapiPort,
      timeout: 10_000,
      reuseExistingServer: !isCI,
      env: { MOCK_STRAPI_PORT: String(mockStrapiPort) },
    },
    {
      // In CI: pre-compile all routes (eliminates lazy-compile race conditions)
      // Locally: dev mode for fast iteration
      command: isCI
        ? `npm run build && npm start -- -p ${frontendPort}`
        : `npm run dev -- -p ${frontendPort}`,
      port: frontendPort,
      timeout: isCI ? 180_000 : 60_000,
      reuseExistingServer: !isCI,
      env: {
        NEXT_PUBLIC_STRAPI_URL: `http://localhost:${mockStrapiPort}`,
        STRAPI_API_TOKEN: 'mock-token',
      },
    },
  ],
});
