/**
 * E2E test for Structures view rendering
 * 
 * Verifies that clicking a project structure shows Details + 3D Viewer.
 * This test does not rely on OPTIMADE/network.
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/structures_view.test.ts --project=electron
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import { createDemoProject } from './helpers/demo_project';
import { createUniqueProjectDir } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Structures View Rendering', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  test('project structure renders Details and 3D Viewer', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Create a demo project with structures
    const projectDir = createUniqueProjectDir('structures-view-test');
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo', // This demo includes a structure
      parentDir: projectDir,
    });
    
    // Wait for project to load
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
    
    // Navigate to Structures view
    await navigateToView(appPage, 'structures');
    
    // Wait for structures list to load
    // Look for structure cards or list items
    const structuresList = appPage.locator('.structures-list, .structure-card').first();
    await expect(structuresList).toBeVisible({ timeout: 10000 });
    
    // Click first structure card
    const firstStructure = appPage.locator('.structure-card, .structures-list-item').first();
    await expect(firstStructure).toBeVisible({ timeout: 3000 });
    await firstStructure.click();
    
    // Wait a bit for RPC to complete and state to update
    await appPage.waitForTimeout(1000);
    
    // Verify Details panel is visible (using testid)
    const detailsPanel = appPage.getByTestId('qv-structure-detail');
    await expect(detailsPanel).toBeVisible({ timeout: 5000 });
    
    // Verify Details panel contains non-empty atom count text
    // This ensures the structure data was actually loaded and rendered
    const detailsText = await detailsPanel.textContent();
    expect(detailsText).toMatch(/atoms/i);
    expect(detailsText?.trim().length).toBeGreaterThan(0);
    
    // Verify 3D Viewer wrapper is visible (using testid)
    const viewerWrapper = appPage.getByTestId('qv-structure-viewer');
    await expect(viewerWrapper).toBeVisible({ timeout: 5000 });
    
    // Verify 3D Viewer container has content (canvas or WebGL container with children)
    // This is a hard invariant: if payload is valid, viewer must render
    const viewerCanvas = viewerWrapper.locator('canvas');
    const webglContainer = viewerWrapper.locator('[class*="webgl"], [class*="viewer"], [class*="canvas"]');
    
    // Either canvas is visible OR WebGL container has children
    const canvasVisible = await viewerCanvas.count() > 0 && await viewerCanvas.first().isVisible().catch(() => false);
    const webglHasChildren = await webglContainer.count() > 0 && 
      (await webglContainer.first().locator('*').count()) > 0;
    
    expect(canvasVisible || webglHasChildren).toBe(true);
    
    // Verify structure info is displayed (atoms/bonds count) - additional check
    const structureInfo = appPage.locator('.viewer-info, [class*="info"]');
    if (await structureInfo.count() > 0) {
      const infoText = await structureInfo.first().textContent();
      expect(infoText).toMatch(/atoms/i);
    }
    
    // Verify no error panel is shown (blank state regression check)
    const errorPanel = appPage.locator('.error-panel, .structures-view__detail--error');
    await expect(errorPanel).not.toBeVisible();
    
    // Verify no loading spinner is stuck (another blank state regression check)
    const loadingPanel = appPage.locator('.loading-panel, .structures-view__detail--loading');
    await expect(loadingPanel).not.toBeVisible({ timeout: 3000 });
  });
  
  test('single click triggers exactly one load, repeated clicks increment count', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Create a demo project with structures
    const projectDir = createUniqueProjectDir('structures-view-single-click-test');
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      parentDir: projectDir,
    });
    
    // Wait for project to load
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
    
    // Navigate to Structures view
    await navigateToView(appPage, 'structures');
    
    // Wait for structures list to load
    const structuresList = appPage.locator('.structures-list, .structure-card').first();
    await expect(structuresList).toBeVisible({ timeout: 10000 });
    
    // Get first structure
    const firstStructure = appPage.locator('.structure-card, .structures-list-item').first();
    await expect(firstStructure).toBeVisible({ timeout: 3000 });
    
    // Capture console messages for [LOAD_START]
    const loadStartMessages: string[] = [];
    appPage.on('console', (msg) => {
      const text = msg.text();
      if (text.includes('[LOAD_START]')) {
        loadStartMessages.push(text);
      }
    });
    
    // Click structure once
    await firstStructure.click();
    await appPage.waitForTimeout(1500);  // Wait for load to complete
    
    // Assert: [LOAD_START] should appear exactly once
    expect(loadStartMessages.length).toBe(1);
    expect(loadStartMessages[0]).toContain('[LOAD_START]');
    
    // Click the same structure again (refresh semantics)
    await firstStructure.click();
    await appPage.waitForTimeout(1500);
    
    // Assert: [LOAD_START] should now appear twice (refresh worked)
    expect(loadStartMessages.length).toBe(2);
    expect(loadStartMessages[1]).toContain('[LOAD_START]');
    
    // Click a third time
    await firstStructure.click();
    await appPage.waitForTimeout(1500);
    
    // Assert: [LOAD_START] should now appear three times
    expect(loadStartMessages.length).toBe(3);
  });
  
  test('renders project structure without console ReferenceError', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);
    
    // Create a demo project with structures
    const projectDir = createUniqueProjectDir('structures-view-reference-error-test');
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo', // This demo includes a structure
      parentDir: projectDir,
    });
    
    // Wait for project to load
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
    
    // Navigate to Structures view
    await navigateToView(appPage, 'structures');
    
    // Wait for structures list to load
    const structuresList = appPage.locator('.structures-list, .structure-card').first();
    await expect(structuresList).toBeVisible({ timeout: 10000 });
    
    // Click first structure card
    const firstStructure = appPage.locator('.structure-card, .structures-list-item').first();
    await expect(firstStructure).toBeVisible({ timeout: 3000 });
    
    // Capture ALL console messages to detect any ReferenceError
    const consoleMessages: Array<{ type: string; text: string }> = [];
    appPage.on('console', (msg) => {
      const text = msg.text();
      const type = msg.type();
      consoleMessages.push({ type, text });
      
      // Fail immediately if we see ANY ReferenceError
      if (type === 'error' && text.includes('ReferenceError')) {
        throw new Error(`Detected console ReferenceError: ${text}`);
      }
    });
    
    // Also capture page errors (uncaught exceptions)
    const pageErrors: string[] = [];
    appPage.on('pageerror', (error) => {
      const errorText = error.message || String(error);
      pageErrors.push(errorText);
      if (errorText.includes('ReferenceError')) {
        throw new Error(`Detected page ReferenceError: ${errorText}`);
      }
    });
    
    // Click the structure
    await firstStructure.click();
    
    // Wait for structure to load and render
    await appPage.waitForTimeout(2000);
    
    // Assert: Details panel is visible
    const detailsPanel = appPage.getByTestId('qv-structure-detail');
    await expect(detailsPanel).toBeVisible({ timeout: 5000 });
    
    // Assert: Viewer wrapper is visible
    const viewerWrapper = appPage.getByTestId('qv-structure-viewer');
    await expect(viewerWrapper).toBeVisible({ timeout: 5000 });
    
    // Assert: Viewer contains canvas/WebGL element
    const viewerCanvas = viewerWrapper.locator('canvas');
    const webglContainer = viewerWrapper.locator('[class*="webgl"], [class*="viewer"], [class*="canvas"]');
    const canvasVisible = await viewerCanvas.count() > 0 && await viewerCanvas.first().isVisible().catch(() => false);
    const webglHasChildren = await webglContainer.count() > 0 && 
      (await webglContainer.first().locator('*').count()) > 0;
    expect(canvasVisible || webglHasChildren).toBe(true);
    
    // Assert: No error panel is visible
    const errorPanel = appPage.locator('.error-panel, .structures-view__detail--error');
    await expect(errorPanel).not.toBeVisible();
    
    // Assert: No "Failed to Load Structure" error panel text
    const errorPanelText = await errorPanel.isVisible().then(async (visible) => {
      if (visible) {
        return await errorPanel.textContent();
      }
      return null;
    });
    if (errorPanelText) {
      expect(errorPanelText).not.toContain('Failed to load structure');
      expect(errorPanelText).not.toMatch(/Failed.*load.*structure/i);
    }
    
    // Assert: No console ReferenceError messages
    const referenceErrors = consoleMessages.filter(msg => 
      msg.type === 'error' && msg.text.includes('ReferenceError')
    );
    expect(referenceErrors).toHaveLength(0);
    
    // Assert: No page ReferenceError exceptions
    const pageReferenceErrors = pageErrors.filter(err => err.includes('ReferenceError'));
    expect(pageReferenceErrors).toHaveLength(0);
  });
});

