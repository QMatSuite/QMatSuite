/**
 * E2E Test: Structure Viewer - Basic Functionality
 * 
 * Tests that the Structures view displays correctly and the viewer loads.
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Structure Viewer Basic', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('structure-viewer');
  });
  
  test('structures view loads and displays structure list', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Create demo project (Si bands - contains Si structure)
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-structures',
      parentDir: projectDir,
    });
    
    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Structures view
    await navigateToView(appPage, 'structures');
    
    // Wait for structures view to be visible (new test ID we just added)
    await expect(appPage.getByTestId('qv-structures-view')).toBeVisible({ timeout: 10000 });
    
    // Verify at least one structure row is present
    const structureRows = appPage.getByTestId('qv-structure-row');
    await expect(structureRows).toHaveCount(1, { timeout: 10000 });
    
    // Verify structure count is displayed
    const structureCount = appPage.getByTestId('qv-structures-count');
    await expect(structureCount).toBeVisible();
    await expect(structureCount).toContainText('1 total');
  });

  test('clicking structure shows 3D viewer panel', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Create demo project
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-viewer',
      parentDir: projectDir,
    });
    
    // Navigate to Structures
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    await navigateToView(appPage, 'structures');
    await expect(appPage.getByTestId('qv-structures-view')).toBeVisible({ timeout: 10000 });
    
    // Click on first structure row
    const structureRow = appPage.getByTestId('qv-structure-row').first();
    await expect(structureRow).toBeVisible({ timeout: 10000 });
    await structureRow.click();
    
    // Wait for structure viewer panel to appear
    const viewerPanel = appPage.getByTestId('qv-structure-viewer-panel');
    await expect(viewerPanel).toBeVisible({ timeout: 15000 });
    
    // Verify viewer panel shows structure name
    await expect(viewerPanel).toContainText('Si', { timeout: 5000 });
    
    // Verify 3D viewer container is present
    const viewer3D = appPage.getByTestId('qv-structure-viewer');
    await expect(viewer3D).toBeVisible({ timeout: 10000 });
  });
});
