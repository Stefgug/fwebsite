import { defineConfig, devices } from '@playwright/test';

const isCI = !!process.env.CI;
// The "Accept & run this test" demo path validates a single new test, so it opts
// out of the production build (~90s) and runs against the dev server instead.
const fastServer = !!process.env.PLAYWRIGHT_FAST_SERVER;
const useProdServer = isCI && !fastServer;
const frontendPort = Number(process.env.PLAYWRIGHT_FRONTEND_PORT ?? 3000);
const mockStrapiPort = Number(process.env.MOCK_STRAPI_PORT ?? 1999);

export default defineConfig({
  testDir: './tests',
  testMatch: '**/*.spec.ts',
  timeout: fastServer ? 60_000 : 30_000,
  retries: isCI ? 1 : 0,
  // Parallel workers cut wall-clock roughly a third; kept conservative in CI
  // because a flaky demo run costs far more than the seconds it would save.
  workers: isCI ? 2 : undefined,
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
      // Locally, and for single-test proposal runs: dev mode for fast feedback
      command: useProdServer
        ? `npm run build && npm start -- -p ${frontendPort}`
        : `npm run dev -- -p ${frontendPort}`,
      port: frontendPort,
      timeout: useProdServer ? 180_000 : 90_000,
      reuseExistingServer: !isCI,
      env: {
        NEXT_PUBLIC_STRAPI_URL: `http://localhost:${mockStrapiPort}`,
        STRAPI_API_TOKEN: 'mock-token',
      },
    },
  ],
});
