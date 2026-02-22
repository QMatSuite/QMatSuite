/**
 * Helper functions for creating demo projects in E2E tests
 * 
 * Provides a unified way to create demo projects via the Demo Gallery flow.
 */

import type { Page } from '@playwright/test';
import { expect } from '@playwright/test';
import { createUniqueProjectDir } from './paths';

export interface CreateDemoProjectOptions {
  /** Demo ID (e.g., 'si_bands_demo', 'si_dos_demo'). Defaults to 'si_bands_demo' */
  demoId?: string;
  /** Project name. If not provided, will be auto-generated from demo title */
  projectName?: string;
  /** Parent directory for the project. If not provided, will create a unique temp directory */
  parentDir?: string;
}

/**
 * Wait for the Home welcome screen to be ready
 */
export async function waitForHomeWelcome(page: Page): Promise<void> {
  await expect(page.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30000 });
  await expect(page.getByTestId('qms-welcome')).toBeVisible();
}

/**
 * Create a demo project via the Demo Gallery flow
 * 
 * Flow:
 * 1. Wait for Home welcome screen
 * 2. Click "Browse Demo Gallery" button
 * 3. Wait for gallery panel to load
 * 4. Click the specified demo card's "Create Project" button
 * 5. Handle workspace selection (file picker)
 * 6. Wait for project to load
 * 
 * @param page - Playwright page object
 * @param options - Options for creating the demo project
 * @returns The parent directory where the project was created
 */
export async function createDemoProject(
  page: Page,
  options: CreateDemoProjectOptions = {}
): Promise<string> {
  const { demoId = 'si_bands_demo', projectName, parentDir } = options;
  
  // Step 1: Wait for Home welcome screen
  await waitForHomeWelcome(page);
  
  // Step 2: Click "Browse Demo Gallery" button
  // Use namespaced test ID (welcome-* instead of generic qms-btn-*)
  const welcomeContainer = page.getByTestId('qms-welcome');
  await expect(welcomeContainer).toBeVisible({ timeout: 10000 });
  const demoGalleryBtn = welcomeContainer.getByTestId('qms-welcome-btn-demo-gallery');
  await expect(demoGalleryBtn).toBeVisible({ timeout: 10000 });
  await demoGalleryBtn.click();
  
  // Step 3: Wait for gallery panel to appear (inline, not modal)
  await expect(page.getByTestId('qms-demo-gallery-view')).toBeVisible({ timeout: 10000 });
  
  // Step 4: Wait for loading to complete
  const loadingState = page.getByTestId('qms-demo-gallery-loading');
  await expect(loadingState).not.toBeVisible({ timeout: 15000 });
  
  // Step 5: Verify gallery loaded successfully by waiting for a demo card to appear
  // This is the correct feature to detect - when cards are rendered, gallery has loaded
  // Use a known demo card that should always exist (si-bands-demo)
  const siBandsCard = page.getByTestId('qms-demo-card-si-bands-demo');
  await expect(siBandsCard).toBeVisible({ timeout: 10000 });
  
  // If card appears, gallery loaded successfully
  // If it doesn't appear, check for error state to provide better error message
  const errorState = page.getByTestId('qms-demo-gallery-error');
  const hasError = await errorState.isVisible().catch(() => false);
  if (hasError) {
    const errorText = await errorState.textContent();
    throw new Error(`Demo gallery failed to load: ${errorText}`);
  }
  
  // Step 6: Find and click the demo card's "Create Project" button
  // Convert demo ID to test ID format (replace underscores with hyphens)
  const demoTestId = demoId.replace(/_/g, '-');
  const createBtn = page.getByTestId(`qms-demo-card-btn-create-${demoTestId}`);
  await expect(createBtn).toBeVisible({ timeout: 5000 });
  await expect(createBtn).toBeEnabled();
  
  // Determine parent directory
  const finalParentDir = parentDir || createUniqueProjectDir('demo');
  
  // Step 7: Handle file picker
  // In E2E tests, we can't directly interact with native file dialogs.
  // We use IPC to set the test directory before the dialog is called.
  // The main process checks for this IPC-set value when E2E_TEST_MODE is enabled.
  
  // Set the test directory via IPC before clicking
  // This will be read by the main process when the dialog handler is called
  await page.evaluate(async (dir) => {
    // Use the IPC API exposed by preload to set the test directory
    if ((window as any).qms?.setE2ETestDirectory) {
      await (window as any).qms.setE2ETestDirectory(dir);
    }
  }, finalParentDir);
  
  // Click the "Create Project" button
  // The file picker will open, but in E2E test mode, the main process
  // will use the directory we set via IPC instead of showing the dialog
  await createBtn.click();
  
  // Wait a bit for the dialog to be handled and project creation to start
  await page.waitForTimeout(2000);
  
  // Step 8: Wait for project to be created and loaded
  // The app should switch back to Home view with project loaded
  await expect(page.getByTestId('qms-home-project')).toBeVisible({ timeout: 60000 });
  
  // Verify project is loaded (project name should be visible)
  // Note: The project name is auto-generated from the demo title, not from projectName parameter
  // So we just verify the element exists rather than checking for a specific name
  const projectNameElement = page.getByTestId('qms-project-name');
  await expect(projectNameElement).toBeVisible({ timeout: 10000 });
  
  return finalParentDir;
}

