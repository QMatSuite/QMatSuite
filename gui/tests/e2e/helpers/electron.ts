/**
 * Electron app launch helpers for E2E tests
 * 
 * Note: Due to compatibility issues between Playwright and newer Electron versions
 * on macOS, we use a workaround that enables remote debugging via environment variables.
 */

import { _electron as electron, ElectronApplication, Page } from 'playwright';
import * as path from 'path';
import { createRequire } from 'module';
import { getGuiDir } from './paths';

// Create require function for ES modules
const require = createRequire(import.meta.url);

export interface LaunchResult {
  app: ElectronApplication;
  page: Page;
}

/**
 * Get the path to the Electron executable
 */
function getElectronPath(): string {
  // Use the electron module to get the correct binary path
  return require('electron') as string;
}

/**
 * Launch the Electron app for testing
 * 
 * @param options - Optional launch options
 * @returns The Electron app and main window page
 */
export async function launchApp(options?: {
  timeout?: number;
}): Promise<LaunchResult> {
  const guiDir = getGuiDir();
  const timeout = options?.timeout ?? 30000;
  
  // Path to the main.js file in dist-electron
  const mainPath = path.join(guiDir, 'dist-electron', 'main.js');
  
  // Path to the electron executable
  const electronPath = getElectronPath();
  
  // Launch Electron app using Playwright's electron API
  // The executablePath tells Playwright where the Electron binary is
  // Playwright will handle the remote debugging setup
  const app = await electron.launch({
    executablePath: electronPath,
    args: [mainPath],
    cwd: guiDir,
    timeout,
    env: {
      ...process.env,
      // Ensure QE_HOME is passed through if set
      QE_HOME: process.env.QE_HOME || '',
      // Disable security warnings
      ELECTRON_DISABLE_SECURITY_WARNINGS: 'true',
      // Enable remote debugging via environment variable (alternative to command line flag)
      ELECTRON_ENABLE_STACK_DUMPING: 'true',
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

