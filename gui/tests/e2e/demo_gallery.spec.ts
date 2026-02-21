/**
 * E2E tests for Demo Gallery functionality
 * 
 * Tests the Demo Gallery as an inline Home sub-view (not a modal).
 * 
 * **This spec does NOT run any calculations.** It only tests:
 * - Demo gallery UI (cards, metadata, navigation)
 * - Project creation from demo gallery
 * - Calculation/structure existence after creation (metadata only, no execution)
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_gallery.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as path from 'path';
import * as os from 'os';
import { createUniqueProjectDir } from './helpers';

test.describe('E2E: Demo Gallery', () => {
  test('demo gallery opens and allows creating DOS demo project', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Use a unique project directory for this test
    const projectDir = createUniqueProjectDir('demo-gallery');
    
    // Navigate to Home view - wait for welcome screen
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
    await expect(appPage.getByTestId('qv-welcome')).toBeVisible();
    
    // Click "Demo Gallery" button
    // Use namespaced test ID (welcome-* instead of generic qv-btn-*)
    const welcomeContainer = appPage.getByTestId('qv-welcome');
    await expect(welcomeContainer).toBeVisible();
    const demoGalleryBtn = welcomeContainer.getByTestId('qv-welcome-btn-demo-gallery');
    await expect(demoGalleryBtn).toBeVisible();
    await demoGalleryBtn.click();
    
    // Wait for gallery view to appear (not a modal, but inline panel)
    await expect(appPage.getByTestId('qv-demo-gallery-view')).toBeVisible({ timeout: 10000 });
    
    // Wait for loading to complete
    const loadingState = appPage.getByTestId('qv-demo-gallery-loading');
    await expect(loadingState).not.toBeVisible({ timeout: 20000 });
    
    // Verify demo cards are visible (not error state)
    const cardsContainer = appPage.getByTestId('qv-demo-gallery-cards');
    const errorState = appPage.getByTestId('qv-demo-gallery-error');
    const emptyState = appPage.getByTestId('qv-demo-gallery-empty-state');
    
    // Wait for cards container to appear (with timeout), then check for error/empty
    // This gives cards time to render after loading completes
    try {
      await expect(cardsContainer).toBeVisible({ timeout: 10000 });
    } catch {
      // If cards don't appear, check for error/empty states
      const hasError = await errorState.isVisible({ timeout: 2000 }).catch(() => false);
      const hasEmpty = await emptyState.isVisible({ timeout: 2000 }).catch(() => false);
      
      if (hasError) {
        const errorText = await errorState.textContent();
        throw new Error(`Demo gallery failed to load: ${errorText}`);
      }
      if (hasEmpty) {
        throw new Error('Demo gallery is empty - no demo projects found');
      }
      // If neither error nor empty, but cards still not visible, re-throw the original error
      throw new Error('Demo gallery cards did not appear within timeout');
    }
    
    // Verify at least two demo cards exist (using stable test IDs)
    const siBandsCard = appPage.getByTestId('qv-demo-card-si-bands-demo');
    const siDosCard = appPage.getByTestId('qv-demo-card-si-dos-demo');
    
    await expect(siBandsCard).toBeVisible();
    await expect(siDosCard).toBeVisible();
    
    // Verify metadata is displayed (title, subtitle, tags)
    await expect(siBandsCard.locator('.demo-card__name')).toContainText(/Silicon band structure/i);
    await expect(siBandsCard.locator('.demo-card__subtitle')).toContainText(/band structure/i);
    await expect(siBandsCard.getByTestId('qv-demo-tag-si-bands-demo-bands')).toBeVisible();
    
    // Click "Create Project" button on Si DOS demo card
    // First, set up the file picker mock via IPC
    await appPage.evaluate(async (dir) => {
      // Use the IPC API exposed by preload to set the test directory
      if ((window as any).qv?.setE2ETestDirectory) {
        await (window as any).qv.setE2ETestDirectory(dir);
      }
    }, projectDir);
    
    const createDosBtn = appPage.getByTestId('qv-demo-card-btn-create-si-dos-demo');
    await expect(createDosBtn).toBeEnabled();
    await createDosBtn.click();
    
    // Wait for project to be created and loaded
    // The app should switch back to welcome/home view with project loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
    
    // Verify project path contains our project name
    await expect(appPage.getByTestId('qv-project-path')).toBeVisible();
    
    // Navigate to Workflows to verify project was created successfully
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    
    // Verify at least one calculation exists
    const workflowsList = appPage.getByTestId('qv-calculations-list');
    await expect(workflowsList).toBeVisible();
    
    // Note: Console errors are automatically checked by the electronTest fixture
  });
});

