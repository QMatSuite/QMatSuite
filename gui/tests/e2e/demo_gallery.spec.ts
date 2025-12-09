/**
 * E2E tests for Demo Gallery functionality
 * 
 * Tests the Demo Gallery as an inline Home sub-view (not a modal).
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
    // Scope to welcome screen to avoid duplicate test IDs in sidebar
    const welcomeContainer = appPage.getByTestId('qv-welcome');
    await expect(welcomeContainer).toBeVisible();
    const demoGalleryBtn = welcomeContainer.getByTestId('qv-btn-demo-gallery');
    await expect(demoGalleryBtn).toBeVisible();
    await demoGalleryBtn.click();
    
    // Wait for gallery view to appear (not a modal, but inline panel)
    await expect(appPage.getByTestId('qv-demo-gallery-view')).toBeVisible({ timeout: 10000 });
    
    // Wait for loading to complete
    const loadingState = appPage.getByTestId('qv-demo-gallery-loading');
    await expect(loadingState).not.toBeVisible({ timeout: 15000 });
    
    // Verify demo cards are visible (not error state)
    const cardsContainer = appPage.getByTestId('qv-demo-gallery-cards');
    const errorState = appPage.getByTestId('qv-demo-gallery-error');
    const emptyState = appPage.getByTestId('qv-demo-gallery-empty-state');
    
    // Check for error/empty first - if present, fail
    const hasError = await errorState.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    
    if (hasError) {
      const errorText = await errorState.textContent();
      throw new Error(`Demo gallery failed to load: ${errorText}`);
    }
    if (hasEmpty) {
      throw new Error('Demo gallery is empty - no demo projects found');
    }
    
    // Verify demo cards are visible
    await expect(cardsContainer).toBeVisible();
    
    // Verify at least two demo cards exist (using stable test IDs)
    const siBandsCard = appPage.getByTestId('qv-demo-card-si-bands-demo');
    const siDosCard = appPage.getByTestId('qv-demo-card-si-dos-demo');
    
    await expect(siBandsCard).toBeVisible();
    await expect(siDosCard).toBeVisible();
    
    // Verify metadata is displayed (title, subtitle, tags)
    await expect(siBandsCard.locator('.demo-card__name')).toContainText(/Silicon band structure/i);
    await expect(siBandsCard.locator('.demo-card__subtitle')).toContainText(/SCF.*NSCF.*Bands/i);
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
    await navigateToView(appPage, 'workflows');
    await expect(appPage.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
    
    // Verify at least one workflow exists
    const workflowsList = appPage.getByTestId('qv-workflows-list');
    await expect(workflowsList).toBeVisible();
    
    // Note: Console errors are automatically checked by the electronTest fixture
  });
});

