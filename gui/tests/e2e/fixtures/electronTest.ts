/**
 * Unified Electron test fixture for E2E tests
 * 
 * Automatically chooses the appropriate launch strategy based on platform:
 * - Linux: Uses Playwright's native _electron.launch() API
 * - macOS: Uses CDP (Chrome DevTools Protocol) workaround
 * - Windows: Uses Linux path (can be extended if needed)
 * 
 * This allows the same test specs to run on all platforms.
 * 
 * IMPORTANT: The app stays open throughout the entire test and is only closed
 * after the test completes. This ensures long-running jobs can be monitored.
 */

import { test as base, expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import * as os from 'os';
import { launchApp, closeApp } from '../helpers/electron';
import { launchElectronViaCDP } from '../helpers/electron_cdp';
import { assertNoDuplicateTestIds } from '../helpers/testid';

type ElectronFixtures = {
  appPage: Page;
};

// Global timeout: 30 seconds for tests without QE execution
const DEFAULT_TEST_TIMEOUT = 30 * 1000;

// Extended timeout: 3 minutes for tests with QE job execution
const QE_JOB_TEST_TIMEOUT = 3 * 60 * 1000;

// Allowlist of known benign console messages that don't indicate bugs
// Keep this minimal and documented - only add patterns for messages we can't avoid
const BENIGN_CONSOLE_PATTERNS = [
  /^Warning:/,  // React warnings (dev mode)
  /React DevTools/,  // React DevTools messages
  /^\[webpack-dev-server\]/,  // Webpack dev server messages (if in dev mode)
  /^Download the React DevTools/,  // React DevTools suggestion
];

function isBenignConsoleMessage(text: string): boolean {
  return BENIGN_CONSOLE_PATTERNS.some(pattern => pattern.test(text));
}

/**
 * Unified Electron test fixture
 * 
 * Usage:
 *   import { electronTest as test, expect } from './fixtures/electronTest';
 *   
 *   test('my test', async ({ appPage }) => {
 *     await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible();
 *   });
 * 
 * The fixture ensures:
 * - Each test gets a fresh Electron instance (opened at test start, closed at test end)
 * - Only one Electron instance runs at a time (enforced by workers: 1 in playwright.config.ts)
 * - App stays open throughout the entire test (never closes prematurely)
 * - Default 30-second timeout (tests with QE jobs override to 3 minutes)
 * - App is properly closed after test completion
 * - Page connection is monitored to detect unexpected disconnections
 */
export const electronTest = base.extend<ElectronFixtures>({
  appPage: async ({}, use, testInfo) => {
    // Set default timeout for this test (30 seconds)
    // Tests that run QE jobs should override this to QE_JOB_TEST_TIMEOUT (3 minutes)
    // This will cause Playwright to kill the test if it exceeds this time
    testInfo.setTimeout(DEFAULT_TEST_TIMEOUT);
    
    let page: Page | null = null;
    let closeFn: (() => Promise<void>) | null = null;
    let pageClosed = false;
    let isCleaningUp = false;
    
    const platform = os.platform();
    const isLinux = platform === 'linux';
    const isWindows = platform === 'win32';
    
    try {
      // Use native _electron.launch() on Linux and Windows
      // Use CDP workaround on macOS (due to Playwright bug)
      if (isLinux || isWindows) {
        // Linux/Windows: Use Playwright's native _electron.launch()
        const { app, page: appPage } = await launchApp({ timeout: 60000 });
        page = appPage;
        closeFn = async () => {
          await closeApp(app);
        };
      } else {
        // macOS: Use CDP-based launch
        const { page: appPage, close } = await launchElectronViaCDP({ timeout: 60000 });
        page = appPage;
        closeFn = close;
      }
      
      // Ensure we have both page and closeFn before proceeding
      if (!page || !closeFn) {
        throw new Error('Failed to initialize Electron app: page or closeFn is null');
      }
      
      // Monitor page for unexpected closure
      // Note: This might fire if the test times out, so we check testInfo.status
      // However, testInfo.status might not be set yet, so we use a flag to track if we're in cleanup
      page.on('close', () => {
        pageClosed = true;
        // Only throw if we're not in cleanup and the test hasn't already timed out or failed
        if (!isCleaningUp && testInfo.status !== 'timedout' && testInfo.status !== 'failed') {
          throw new Error('Electron page closed unexpectedly during test. This should not happen - the app should stay open throughout the entire test.');
        }
      });
      
      // Monitor for crashes
      page.on('crash', () => {
        throw new Error('Electron page crashed during test.');
      });
      
      // Collect console errors and page errors for auto-assertion
      const consoleErrors: string[] = [];
      const pageErrors: string[] = [];
      const networkFailures: string[] = [];
      
      // Monitor console for errors (including EPIPE)
      page.on('console', (msg) => {
        const text = msg.text();
        const type = msg.type();
        
        // Detect EPIPE errors and fail the test immediately
        if (text.includes('EPIPE') || text.includes('write EPIPE') || text.includes('Uncaught Exception')) {
          const error = new Error(`Electron process encountered EPIPE error during test execution: ${text}. This indicates stdout/stderr streams were closed prematurely. Test will stop immediately.`);
          // Reject the test immediately
          throw error;
        }
        
        // Collect console errors (excluding benign messages)
        if (type === 'error' && !isBenignConsoleMessage(text)) {
          consoleErrors.push(`[Console Error] ${text}`);
        }
        
        // Log other console messages for debugging
        if (type === 'error' && process.env.DEBUG_ELECTRON) {
          console.error('[Page console error]', text);
        }
      });
      
      // Monitor for page errors (uncaught exceptions)
      page.on('pageerror', (error) => {
        const errorMessage = error.message || String(error);
        // Detect EPIPE errors in uncaught exceptions
        if (errorMessage.includes('EPIPE') || errorMessage.includes('write EPIPE')) {
          throw new Error(`Electron process encountered EPIPE error (uncaught exception): ${errorMessage}. Test will stop immediately.`);
        }
        // Collect page errors
        pageErrors.push(`[Page Error] ${errorMessage}`);
      });
      
      // Monitor network failures
      page.on('requestfailed', (request) => {
        const failure = request.failure();
        if (failure) {
          networkFailures.push(`[Network Failure] ${request.method()} ${request.url()}: ${failure.errorText}`);
        }
      });
      
      // Use the page in the test
      // The app will stay open throughout the entire test execution
      await use(page);
      
      // Auto-check: verify no duplicate data-testid values in the DOM
      // Only check if page is still alive (test might have failed earlier)
      if (page && !page.isClosed()) {
        try {
          await assertNoDuplicateTestIds(page);
        } catch (error) {
          // If duplicate test IDs are found, fail the test
          // This check happens after the test logic but before other error checks
          throw error;
        }
      }
      
      // Auto-assert: fail test if there were any unexpected errors
      if (consoleErrors.length > 0 || pageErrors.length > 0 || networkFailures.length > 0) {
        const errorMessages: string[] = [];
        if (consoleErrors.length > 0) {
          errorMessages.push(`Console errors (${consoleErrors.length}):\n${consoleErrors.join('\n')}`);
        }
        if (pageErrors.length > 0) {
          errorMessages.push(`Page errors (${pageErrors.length}):\n${pageErrors.join('\n')}`);
        }
        if (networkFailures.length > 0) {
          errorMessages.push(`Network failures (${networkFailures.length}):\n${networkFailures.join('\n')}`);
        }
        throw new Error(`Test failed due to unexpected errors:\n${errorMessages.join('\n\n')}`);
      }
      
    } catch (error: any) {
      // If test timed out or failed, provide clear error message
      if (error.message?.includes('timeout') || testInfo.status === 'timedout') {
        const timeoutMs = testInfo.timeout;
        const timeoutMinutes = timeoutMs / (60 * 1000);
        throw new Error(`Test exceeded timeout of ${timeoutMs}ms (${timeoutMinutes} minutes). The test has been terminated.`);
      }
      throw error;
    } finally {
      // Cleanup after test - close the app
      // This only happens after the test completes (success or failure)
      isCleaningUp = true;
      try {
        if (!pageClosed && closeFn) {
          await closeFn();
        }
      } catch (e) {
        // Ignore errors during cleanup - app might already be closed
        console.error('Error during app cleanup (this is usually safe to ignore):', e);
      }
    }
  },
});

// Re-export expect for convenience
export { expect };

// Re-export helper functions that work with the fixture
export { navigateToView, waitForDaemonConnection } from '../helpers/electron';

// Export timeout constants for tests that need to override
export { DEFAULT_TEST_TIMEOUT, QE_JOB_TEST_TIMEOUT };

