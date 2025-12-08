/**
 * E2E tests for Demo Gallery functionality
 */

import { electronTest as test, expect } from './fixtures/electronTest';
import * as path from 'path';
import * as os from 'os';

test.describe('E2E: Demo Gallery', () => {
  test('demo gallery opens and allows creating DOS demo project', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(60 * 1000);
    
    const projectDir = path.join(os.tmpdir(), 'qv_e2e_demo_gallery');
    
    // Navigate to Home view
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
    
    // Click "Demo Gallery" button
    const demoGalleryBtn = appPage.getByTestId('qv-btn-demo-gallery');
    await expect(demoGalleryBtn).toBeVisible();
    await demoGalleryBtn.click();
    
    // Wait for gallery dialog to open (check for modal with "Demo Gallery" title)
    const modal = appPage.locator('.modal').filter({ hasText: 'Demo Gallery' });
    await expect(modal).toBeVisible({ timeout: 10000 });
    
    // Wait for loading to complete (either cards appear or error appears)
    // Check that loading spinner is gone
    await expect(appPage.locator('.demo-gallery-dialog__loading')).not.toBeVisible({ timeout: 15000 });
    
    // Verify either demo cards are visible OR error state is visible
    const cardsContainer = appPage.getByTestId('qv-demo-gallery-cards');
    const errorState = appPage.getByTestId('qv-demo-gallery-error-state');
    const emptyState = appPage.getByTestId('qv-demo-gallery-empty-state');
    
    // At least one should be visible
    const hasCards = await cardsContainer.isVisible().catch(() => false);
    const hasError = await errorState.isVisible().catch(() => false);
    const hasEmpty = await emptyState.isVisible().catch(() => false);
    
    if (!hasCards && !hasError && !hasEmpty) {
      throw new Error('Demo gallery did not load: no cards, error, or empty state visible');
    }
    
    // If error or empty, fail the test
    if (hasError || hasEmpty) {
      const errorText = hasError 
        ? await errorState.textContent() 
        : await emptyState.textContent();
      throw new Error(`Demo gallery failed to load: ${errorText}`);
    }
    
    // Verify demo cards are visible
    await expect(cardsContainer).toBeVisible();
    
    // Verify at least two demo cards exist
    const siBandsCard = appPage.getByTestId('qv-demo-card-si_bands_demo');
    const siDosCard = appPage.getByTestId('qv-demo-card-si_dos_demo');
    
    await expect(siBandsCard).toBeVisible();
    await expect(siDosCard).toBeVisible();
    
    // Click on Si DOS demo card
    await siDosCard.click();
    
    // Verify card is selected
    await expect(siDosCard.locator('.demo-card--selected')).toBeVisible();
    
    // Select workspace folder
    const workspaceInput = appPage.getByTestId('qv-demo-gallery-workspace-input');
    await workspaceInput.fill(projectDir);
    
    // Click "Create Project" button
    const createBtn = appPage.getByTestId('qv-demo-gallery-create-btn');
    await expect(createBtn).toBeEnabled();
    await createBtn.click();
    
    // Wait for project to be created and loaded
    // The app should navigate to home or workflows view
    // Wait for workflows to appear (indicating project was loaded)
    await expect(appPage.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 30000 });
    
    // Verify at least one workflow exists
    const workflowsList = appPage.getByTestId('qv-workflows-list');
    await expect(workflowsList).toBeVisible();
    
    // Note: Console errors are automatically checked by the electronTest fixture
  });
});

