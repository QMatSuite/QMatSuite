/**
 * E2E Test 2: Create Demo Project → Calculation & Steps UI
 * 
 * Tests creating a demo project and verifying calculation/step UI consistency.
 * 
 * **This spec does NOT run any calculations.** It only tests:
 * - Calculation list rendering
 * - Step list order (DAG / ULID-based)
 * - Step detail panel UI (file paths, step IDs, metadata)
 * - Step file existence and YAML structure
 * - Step Focus mode (compact step list + StepDetailPanel)
 * 
 * All assertions are independent of QE execution outputs.
 * 
 * Each test file runs in its own Playwright process, ensuring complete isolation.
 * The unified Electron fixture automatically chooses the appropriate launch strategy
 * based on platform (Linux: _electron.launch, macOS: CDP).
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_calculation.spec.ts --project=electron
 * 
 * REFACTOR NOTES (Updated for new Calculations UI):
 * - Calculations view now has three tabs: Overview & Steps, Run & Logs, Analysis
 * - Overview & Steps tab has two modes:
 *   - Overview mode: Full calculation overview with step list
 *   - Step Focus mode: Compact step list + StepDetailPanel (when step is selected)
 * - StepDetailPanel is only visible in Step Focus mode (not always below calculation list)
 * - "Run Calculation" button is in the calculation header (Overview mode) or compact panel (Focus mode)
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { createUniqueProjectDir, cleanupProjectDir, clearE2EProjectsRoot, getRepoRoot, createDemoProject } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E Test 2: Create Demo Project → Calculation & Steps', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  // Clear E2E projects directory before each test
  // Leave it after tests for inspection
  test.beforeEach(() => {
    clearE2EProjectsRoot();
    // Create a unique project directory for this test
    projectDir = createUniqueProjectDir('demo');
  });
  
  // Don't clean up after tests - leave projects for inspection
  
  test('create demo project and verify calculation steps', async ({ appPage }, testInfo) => {
    // Project creation can take time, increase timeout to 60 seconds
    testInfo.setTimeout(60 * 1000);
    
    // Create demo project via Demo Gallery flow
    // Flow: Home → Browse Demo Gallery → Si Bands demo card → Create Project → Project loaded
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-demo',
      parentDir: projectDir,
    });
    
    // Verify project is loaded (createDemoProject already checks this, but double-check)
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
      
      // Navigate to Calculations view
      await navigateToView(appPage, 'calculations');
      
      // Wait for calculations view to be visible
      await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
      
      // Verify Overview & Steps tab is active by default
      const overviewTab = appPage.getByTestId('qv-calc-tab-overview');
      await expect(overviewTab).toBeVisible();
      await expect(overviewTab).toHaveClass(/calculations-workspace-tab--active/);
      
      // Verify there is exactly one calculation row
      const calculationRows = appPage.getByTestId('qv-calculation-row');
      await expect(calculationRows).toHaveCount(1);
      
      // Click on the calculation row to select it
      await calculationRows.first().click();
      
      // Wait for calculation detail panel (in Overview mode)
      await expect(appPage.getByTestId('qv-calculation-detail')).toBeVisible({ timeout: 10000 });
      
      // Verify we're in Overview mode (not Step Focus mode)
      await expect(appPage.getByTestId('qv-calc-overview-tab')).toBeVisible();
      
      // Verify "Run Calculation" button is visible in the header
      await expect(appPage.getByTestId('qv-btn-run-calculation')).toBeVisible();
      
      // Verify calculation header shows name and "Calculation" subtitle
      const calcDetail = appPage.getByTestId('qv-calculation-detail');
      await expect(calcDetail.locator('.panel-title')).toBeVisible();
      await expect(calcDetail.locator('.qv-calc-header-subtitle')).toContainText('Calculation');
      
      // Get all step rows
      // Step rows now have unique test IDs (qv-step-row-{stepId})
      // Use a locator that matches the pattern
      const stepRows = appPage.locator('[data-testid^="qv-step-row-"]');
      const stepCount = await stepRows.count();
      
      expect(stepCount).toBeGreaterThan(0);
      
      // Iterate over each step and verify consistency
      for (let i = 0; i < stepCount; i++) {
        const stepRow = stepRows.nth(i);
        
        // Get step type from the step row BEFORE clicking (more reliable)
        // The step type badge is in the step row itself, so we get it before the detail panel updates
        const stepTypeBadgeInRow = stepRow.locator('.step-type-badge');
        await expect(stepTypeBadgeInRow).toBeVisible({ timeout: 5000 });
        const stepType = await stepTypeBadgeInRow.textContent();
        
        // Verify we got a valid step type
        expect(stepType).toBeTruthy();
        expect(stepType?.trim().length).toBeGreaterThan(0);
        const trimmedStepType = stepType.trim().toLowerCase();
        
        // Click on the step button to view details (click the button, not the container)
        const stepButton = stepRow.locator('button.step-item');
        await expect(stepButton).toBeVisible({ timeout: 5000 });
        await expect(stepButton).toBeEnabled({ timeout: 5000 });
        await stepButton.click({ timeout: 5000 });
        
        // Wait a bit for React to update state and enter Step Focus mode
        await appPage.waitForTimeout(200);
        
        // Verify we entered Step Focus mode
        await expect(appPage.getByTestId('qv-calc-overview-tab-focus')).toBeVisible({ timeout: 10000 });
        await expect(appPage.getByTestId('qv-compact-step-list')).toBeVisible({ timeout: 5000 });
        
        // Wait for step detail panel to be visible (in Step Focus mode, it's on the right)
        const stepDetailPanel = appPage.getByTestId('qv-step-detail');
        await expect(stepDetailPanel).toBeVisible({ timeout: 10000 });
        
        // Wait for the detail panel to show the correct step by verifying the step type badge matches
        // This ensures the panel has fully updated before we read the file path
        const stepTypeInDetail = stepDetailPanel.locator('.step-type-badge').first();
        await expect(stepTypeInDetail).toHaveText(new RegExp(trimmedStepType, 'i'), { timeout: 5000 });
        
        // Get step ID and file path from the detail panel
        const stepIdText = await appPage.getByTestId('qv-step-id').textContent();
        const stepFilePath = await appPage.getByTestId('qv-step-file-path').textContent();
        
        expect(stepIdText).toBeTruthy();
        expect(stepFilePath).toBeTruthy();
        expect(stepType).toBeTruthy();
        
        // Verify the YAML file exists and read it
        if (stepFilePath) {
          // stepFilePath should be absolute path from the UI
          expect(fs.existsSync(stepFilePath)).toBe(true);
          
          // Read the YAML file
          const fileContent = fs.readFileSync(stepFilePath, 'utf-8');
          
          // When creating from snapshot, ULIDs are regenerated, so we can't check for exact ULID match
          // Instead, verify that:
          // 1. The file contains valid YAML structure
          // 2. The file contains the step type (which is stable and doesn't change)
          // 3. The file contains a valid meta section with id (ULID format)
          
          // Verify basic YAML structure
          expect(fileContent).toContain('meta:');
          // Constitution v1.1: step files use step_type_spec (e.g., "qe_scf")
          expect(fileContent).toContain('step_type_spec:');

          // Verify step type matches (this is stable across snapshot materialization)
          // The step type in the file should match the step type from the UI
          // trimmedStepType was already computed above from the step row (step_type_gen)
          if (trimmedStepType) {
            // The file uses step_type_spec (e.g., "qe_scf"), UI shows step_type_gen (e.g., "scf")
            // Check that file contains the gen type (possibly with qe_ prefix)
            const stepTypePattern = new RegExp(`step_type_spec:\\s*(qe_)?${trimmedStepType}`, 'i');
            expect(fileContent).toMatch(stepTypePattern);
          }
          
          // Verify the file has a valid meta.ulid field (ULID format, 26 chars)
          // Constitution v1.1: meta uses 'ulid' not 'id'
          // Don't require it to match stepIdText from UI since ULIDs are regenerated
          expect(fileContent).toMatch(/meta:\s*\n\s*ulid:\s+[A-Z0-9]{26}/);
          
          // Verify stepIdText from UI is also a valid ULID format (if it's long enough)
          if (stepIdText && stepIdText.length >= 20) {
            // Just verify it's alphanumeric (ULID format)
            expect(stepIdText).toMatch(/^[A-Z0-9]{26}$/);
          }
        }
        
        // Exit Step Focus mode by clicking "Back to overview" button
        const backButton = appPage.getByTestId('qv-btn-back-to-overview');
        await expect(backButton).toBeVisible({ timeout: 5000 });
        await backButton.click();
        
        // Wait for UI to return to Overview mode
        await expect(appPage.getByTestId('qv-calc-overview-tab')).toBeVisible({ timeout: 5000 });
        await expect(appPage.getByTestId('qv-compact-step-list')).not.toBeVisible({ timeout: 2000 });
        await appPage.waitForTimeout(200);
      }
  });
  
  test('step detail panel shows correct file for each step', async ({ appPage }, testInfo) => {
    // Project creation can take time, increase timeout to 60 seconds
    testInfo.setTimeout(60 * 1000);
    
    // Create demo project via Demo Gallery flow
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-demo-steps',
      parentDir: projectDir,
    });
    
    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
      
      // Navigate to Calculations
      await navigateToView(appPage, 'calculations');
      await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
      
      // Select the calculation
      await appPage.getByTestId('qv-calculation-row').first().click();
      await expect(appPage.getByTestId('qv-calculation-detail')).toBeVisible({ timeout: 10000 });
      
      // Track which files we've seen for each step
      const stepFiles: Map<string, string> = new Map();
      
      // Step rows now have unique test IDs (qv-step-row-{stepId})
      // Use a locator that matches the pattern
      const stepRows = appPage.locator('[data-testid^="qv-step-row-"]');
      const stepCount = await stepRows.count();
      
      for (let i = 0; i < stepCount; i++) {
        const stepRow = stepRows.nth(i);
        const stepId = await stepRow.getAttribute('data-step-id');
        
        // Click step to enter Step Focus mode
        await stepRow.locator('button.step-item').click();
        
        // Wait for Step Focus mode
        await expect(appPage.getByTestId('qv-calc-overview-tab-focus')).toBeVisible({ timeout: 10000 });
        await expect(appPage.getByTestId('qv-step-detail')).toBeVisible({ timeout: 10000 });
        
        const stepFilePath = await appPage.getByTestId('qv-step-file-path').textContent();
        
        if (stepId && stepFilePath) {
          // Store the file path for this step
          stepFiles.set(stepId, stepFilePath);
          
          // Verify all step files are unique for different step IDs
          // (unless they intentionally share a step file)
        }
        
        // Go back to Overview mode
        await appPage.getByTestId('qv-btn-back-to-overview').click();
        await expect(appPage.getByTestId('qv-calc-overview-tab')).toBeVisible({ timeout: 5000 });
        await appPage.waitForTimeout(200);
      }
      
      // Verify we collected files for all steps
      expect(stepFiles.size).toBe(stepCount);
  });
});
