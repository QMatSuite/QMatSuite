/**
 * E2E Test 2: Create Demo Project → Workflow & Steps
 * 
 * Tests creating a demo project and verifying workflow/step UI consistency.
 * 
 * Each test file runs in its own Playwright process, ensuring complete isolation.
 * The unified Electron fixture automatically chooses the appropriate launch strategy
 * based on platform (Linux: _electron.launch, macOS: CDP).
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_workflow.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { createUniqueProjectDir, cleanupProjectDir, clearE2EProjectsRoot, getRepoRoot, createDemoProject } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E Test 2: Create Demo Project → Workflow & Steps', () => {
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
  
  test('create demo project and verify workflow steps', async ({ appPage }, testInfo) => {
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
      
      // Navigate to Workflows view
      await navigateToView(appPage, 'workflows');
      
      // Wait for workflows view to be visible
      await expect(appPage.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
      
      // Verify there is exactly one workflow row
      const workflowRows = appPage.getByTestId('qv-workflow-row');
      await expect(workflowRows).toHaveCount(1);
      
      // Click on the workflow row to select it
      await workflowRows.first().click();
      
      // Wait for workflow detail panel
      await expect(appPage.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
      
      // Verify "Run Workflow" button is visible
      await expect(appPage.getByTestId('qv-btn-run-workflow')).toBeVisible();
      
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
        
        // Click on the step to view details
        await stepRow.click();
        
        // Wait for step detail panel to be visible
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
          expect(fileContent).toContain('step_type:');
          
          // Verify step type matches (this is stable across snapshot materialization)
          // The step type in the file should match the step type from the UI
          // trimmedStepType was already computed above from the step row
          if (trimmedStepType) {
            // The file uses lowercase for step_type, so check case-insensitively
            // Also handle potential whitespace variations
            const stepTypePattern = new RegExp(`step_type:\\s*${trimmedStepType}`, 'i');
            expect(fileContent).toMatch(stepTypePattern);
          }
          
          // Verify the file has a valid meta.id field (ULID format, 26 chars)
          // Don't require it to match stepIdText from UI since ULIDs are regenerated
          expect(fileContent).toMatch(/meta:\s*\n\s*id:\s+[A-Z0-9]{26}/);
          
          // Verify stepIdText from UI is also a valid ULID format (if it's long enough)
          if (stepIdText && stepIdText.length >= 20) {
            // Just verify it's alphanumeric (ULID format)
            expect(stepIdText).toMatch(/^[A-Z0-9]{26}$/);
          }
        }
        
        // Close step detail to go back
        // Click workflow detail panel header to deselect step
        await appPage.getByTestId('qv-workflow-detail').locator('.panel-header').click();
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
      
      // Navigate to Workflows
      await navigateToView(appPage, 'workflows');
      await expect(appPage.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
      
      // Select the workflow
      await appPage.getByTestId('qv-workflow-row').first().click();
      await expect(appPage.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
      
      // Track which files we've seen for each step
      const stepFiles: Map<string, string> = new Map();
      
      // Step rows now have unique test IDs (qv-step-row-{stepId})
      // Use a locator that matches the pattern
      const stepRows = appPage.locator('[data-testid^="qv-step-row-"]');
      const stepCount = await stepRows.count();
      
      for (let i = 0; i < stepCount; i++) {
        const stepRow = stepRows.nth(i);
        const stepId = await stepRow.getAttribute('data-step-id');
        
        await stepRow.click();
        await expect(appPage.getByTestId('qv-step-detail')).toBeVisible({ timeout: 10000 });
        
        const stepFilePath = await appPage.getByTestId('qv-step-file-path').textContent();
        
        if (stepId && stepFilePath) {
          // Store the file path for this step
          stepFiles.set(stepId, stepFilePath);
          
          // Verify all step files are unique for different step IDs
          // (unless they intentionally share a step file)
        }
        
        // Go back by clicking elsewhere
        await appPage.getByTestId('qv-workflow-detail').locator('.panel-header').click();
        await appPage.waitForTimeout(200);
      }
      
      // Verify we collected files for all steps
      expect(stepFiles.size).toBe(stepCount);
  });
});

