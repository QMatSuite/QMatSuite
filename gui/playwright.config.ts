import { defineConfig, devices } from '@playwright/test';

/**
 * Playwright configuration for QuantumVITAS Electron E2E tests
 */
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false, // Electron tests MUST run sequentially (one instance at a time)
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  workers: 1, // Single worker ensures only one Electron instance runs at a time
  reporter: process.env.CI ? 'github' : 'list',
  timeout: 30 * 1000, // 30 seconds default timeout (tests with QE jobs override to 3 minutes)
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
      testIgnore: /integrity\//,
      use: {
        ...devices['Desktop Chrome'],
      },
    },
    {
      name: 'integrity',
      testDir: './tests/e2e/integrity',
      timeout: 10 * 60 * 1000, // 10 minutes for full sweep
      use: {
        ...devices['Desktop Chrome'],
      },
    },
  ],
  outputDir: './test-results',
});

