/**
 * Electron app launch helpers for E2E tests
 * 
 * Launches Electron directly using the binary from node_modules, not a wrapper script.
 * This ensures Playwright's debugging flags work correctly on all platforms.
 * 
 * Note: Using Playwright 1.43.1 (pinned due to Electron compatibility issues in newer versions).
 * Even with 1.43.1, there may be issues with --remote-debugging-port flag on macOS.
 */

import { _electron as electron, ElectronApplication, Page } from '@playwright/test';
import * as path from 'path';
import * as os from 'os';
import { getGuiDir, getRepoRoot } from './paths';

export interface LaunchResult {
  app: ElectronApplication;
  page: Page;
}

/**
 * Get the path to the Electron executable binary
 * Computes platform-specific path to the Electron binary in node_modules
 */
function getElectronExecutablePath(): string {
  const repoRoot = getRepoRoot();
  const electronDistDir = path.join(repoRoot, 'gui', 'node_modules', 'electron', 'dist');
  
  if (os.platform() === 'darwin') {
    // macOS: Electron.app/Contents/MacOS/Electron
    return path.join(
      electronDistDir,
      'Electron.app',
      'Contents',
      'MacOS',
      'Electron'
    );
  } else if (os.platform() === 'win32') {
    // Windows: electron.exe
    return path.join(electronDistDir, 'electron.exe');
  } else {
    // Linux: electron
    return path.join(electronDistDir, 'electron');
  }
}

/**
 * Launch the Electron app for testing
 * 
 * Uses Playwright's _electron.launch() with explicit executablePath pointing
 * directly to the Electron binary (not a wrapper script).
 * 
 * The key insight: By providing the explicit executablePath to the actual Electron
 * binary, Playwright's internal connection mechanism should work. Playwright uses
 * CDP (Chrome DevTools Protocol) which Electron supports natively through its
 * Chromium content. The direct binary path ensures Playwright can establish the
 * connection properly on all platforms, including macOS.
 * 
 * Note: Currently using Playwright 1.43.1 due to compatibility issues.
 * There may still be issues with --remote-debugging-port flag on macOS.
 * 
 * To test on macOS:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/welcome.spec.ts --project=electron
 * 
 * @param options - Optional launch options
 * @returns The Electron app and main window page
 */
export async function launchApp(options?: {
  timeout?: number;
}): Promise<LaunchResult> {
  const guiDir = getGuiDir();
  const timeout = options?.timeout ?? 30000;
  
  // Path to the compiled main entry point
  const mainPath = path.join(guiDir, 'dist-electron', 'main.js');
  
  // Explicit path to Electron binary (platform-specific)
  // This is the critical fix: use the actual binary, not a wrapper
  const electronExecutablePath = getElectronExecutablePath();
  
  // Launch Electron app using Playwright's _electron.launch()
  // By providing executablePath explicitly, Playwright knows it's dealing with
  // Electron and will use the appropriate connection method. The direct binary
  // path (especially on macOS: Electron.app/Contents/MacOS/Electron) ensures
  // Playwright's internal debugging setup works correctly.
  
  // On Linux CI environments, we need to disable the sandbox because we don't have
  // root access to configure the SUID sandbox helper (chrome-sandbox)
  const launchArgs = [mainPath];
  if (os.platform() === 'linux') {
    launchArgs.unshift('--no-sandbox');
  }
  
  const app = await electron.launch({
    executablePath: electronExecutablePath,
    args: launchArgs,
    cwd: guiDir,
    timeout,
    env: {
      ...process.env,
      // Ensure QE_HOME is passed through if set
      QE_HOME: process.env.QE_HOME || '',
      // Disable security warnings
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
    },
  });
  
  // Wait for the first window
  const page = await app.firstWindow();
  
  // Wait for the app to be ready
  await page.waitForLoadState('domcontentloaded');
  
  return { app, page };
}

/**
 * Close the Electron app gracefully
 */
export async function closeApp(app: ElectronApplication): Promise<void> {
  await app.close();
}

/**
 * Wait for daemon connection status
 */
export async function waitForDaemonConnection(
  page: Page,
  timeout: number = 30000
): Promise<void> {
  // Wait for daemon to be connected (status indicator turns green)
  await page.waitForSelector('.sidebar__status.connected', { timeout });
}

/**
 * Navigate to a specific view tab
 */
export async function navigateToView(
  page: Page,
  view: 'home' | 'structures' | 'workflows' | 'jobs' | 'analysis' | 'settings' | 'debug'
): Promise<void> {
  await page.getByTestId(`qv-nav-${view}`).click();
  
  // Wait for view to be active
  await page.waitForTimeout(500);
}

