import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for QuantumVITAS Electron E2E tests
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Electron tests should run sequentially
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Single worker for Electron
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 120000, // 2 minutes per test (QE runs can be slow)
  expect: {
    timeout: 10000,
  },
  use: {
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    {
      name: 'electron',
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
  outputDir: './test-results',
});

