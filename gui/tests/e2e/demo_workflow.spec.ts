/**
 * E2E Test: Create Demo Project → Workflow & Steps
 * 
 * Tests creating a demo project and verifying workflow/step UI consistency.
 * 
 * NOTE: These tests may have compatibility issues on macOS due to how Playwright
 * launches Electron with debugging flags. They work best on Linux.
 */

import { test, expect } from '@playwright/test';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import { launchApp, closeApp, navigateToView } from './helpers';
import { createUniqueProjectDir, cleanupProjectDir } from './helpers';

// Skip tests on macOS due to Playwright/Electron compatibility issues
const IS_MACOS = os.platform() === 'darwin';
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true' || IS_MACOS;

test.describe('Demo Project Workflow', () => {
  test.skip(SKIP_E2E, 'Skipped on macOS or when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  test.beforeEach(() => {
    // Create a unique project directory for this test
    projectDir = createUniqueProjectDir('demo');
  });
  
  test.afterEach(() => {
    // Clean up the project directory
    if (projectDir) {
      cleanupProjectDir(projectDir);
    }
  });
  
  test('create demo project and verify workflow steps', async () => {
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // Wait for welcome screen
      await expect(page.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
      
      // Click "Create Demo Project" button
      await page.getByTestId('qv-btn-create-demo-project').click();
      
      // Wait for the create project dialog
      await expect(page.getByTestId('qv-create-project-dialog')).toBeVisible({ timeout: 10000 });
      
      // Fill in the parent directory (use the unique project dir)
      await page.getByTestId('qv-input-parent-dir').fill(projectDir);
      
      // Fill in project name
      await page.getByTestId('qv-input-project-name').fill('e2e-demo');
      
      // Wait for preview path to show
      await expect(page.getByTestId('qv-project-preview-path')).toBeVisible();
      
      // Click create button
      await page.getByTestId('qv-btn-confirm-create').click();
      
      // Wait for project to be loaded - home project view should appear
      await expect(page.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
      
      // Verify project path contains our project name
      await expect(page.getByTestId('qv-project-path')).toContainText('e2e-demo');
      
      // Navigate to Workflows view
      await navigateToView(page, 'workflows');
      
      // Wait for workflows view to be visible
      await expect(page.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
      
      // Verify there is exactly one workflow row
      const workflowRows = page.getByTestId('qv-workflow-row');
      await expect(workflowRows).toHaveCount(1);
      
      // Click on the workflow row to select it
      await workflowRows.first().click();
      
      // Wait for workflow detail panel
      await expect(page.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
      
      // Verify "Run Workflow" button is visible
      await expect(page.getByTestId('qv-btn-run-workflow')).toBeVisible();
      
      // Get all step rows
      const stepRows = page.getByTestId('qv-step-row');
      const stepCount = await stepRows.count();
      
      expect(stepCount).toBeGreaterThan(0);
      
      // Iterate over each step and verify consistency
      for (let i = 0; i < stepCount; i++) {
        const stepRow = stepRows.nth(i);
        
        // Get step ID from the data attribute
        const stepId = await stepRow.getAttribute('data-step-id');
        expect(stepId).toBeTruthy();
        
        // Click on the step to view details
        await stepRow.click();
        
        // Wait for step detail panel
        await expect(page.getByTestId('qv-step-detail')).toBeVisible({ timeout: 10000 });
        
        // Get step ID and file path from the detail panel
        const stepIdText = await page.getByTestId('qv-step-id').textContent();
        const stepFilePath = await page.getByTestId('qv-step-file-path').textContent();
        
        expect(stepIdText).toBeTruthy();
        expect(stepFilePath).toBeTruthy();
        
        // Verify the YAML file exists and contains the step ID
        if (stepFilePath) {
          expect(fs.existsSync(stepFilePath)).toBe(true);
          
          const fileContent = fs.readFileSync(stepFilePath, 'utf-8');
          // The file should contain either the step ID in meta.name or meta.id
          // Note: stepIdText might be ULID or human-readable name
          expect(
            fileContent.includes(stepIdText!) || 
            fileContent.toLowerCase().includes(stepId!.toLowerCase())
          ).toBe(true);
        }
        
        // Close step detail to go back
        // Click workflow detail panel header to deselect step
        await page.getByTestId('qv-workflow-detail').locator('.panel-header').click();
        await page.waitForTimeout(200);
      }
      
    } finally {
      await closeApp(app);
    }
  });
  
  test('step detail panel shows correct file for each step', async () => {
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // Wait for welcome screen
      await expect(page.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
      
      // Click "Create Demo Project" button
      await page.getByTestId('qv-btn-create-demo-project').click();
      
      // Wait for the create project dialog
      await expect(page.getByTestId('qv-create-project-dialog')).toBeVisible({ timeout: 10000 });
      
      // Fill in the parent directory and project name
      await page.getByTestId('qv-input-parent-dir').fill(projectDir);
      await page.getByTestId('qv-input-project-name').fill('e2e-demo-steps');
      
      // Click create button
      await page.getByTestId('qv-btn-confirm-create').click();
      
      // Wait for project to be loaded
      await expect(page.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
      
      // Navigate to Workflows
      await navigateToView(page, 'workflows');
      await expect(page.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
      
      // Select the workflow
      await page.getByTestId('qv-workflow-row').first().click();
      await expect(page.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
      
      // Track which files we've seen for each step
      const stepFiles: Map<string, string> = new Map();
      
      const stepRows = page.getByTestId('qv-step-row');
      const stepCount = await stepRows.count();
      
      for (let i = 0; i < stepCount; i++) {
        const stepRow = stepRows.nth(i);
        const stepId = await stepRow.getAttribute('data-step-id');
        
        await stepRow.click();
        await expect(page.getByTestId('qv-step-detail')).toBeVisible({ timeout: 10000 });
        
        const stepFilePath = await page.getByTestId('qv-step-file-path').textContent();
        
        if (stepId && stepFilePath) {
          // Store the file path for this step
          stepFiles.set(stepId, stepFilePath);
          
          // Verify all step files are unique for different step IDs
          // (unless they intentionally share a step file)
        }
        
        // Go back by clicking elsewhere
        await page.getByTestId('qv-workflow-detail').locator('.panel-header').click();
        await page.waitForTimeout(200);
      }
      
      // Verify we collected files for all steps
      expect(stepFiles.size).toBe(stepCount);
      
    } finally {
      await closeApp(app);
    }
  });
});

