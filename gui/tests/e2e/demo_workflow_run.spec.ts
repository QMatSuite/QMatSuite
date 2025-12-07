/**
 * E2E Test: Run workflow → Jobs → Analysis
 * 
 * Tests the full workflow execution flow:
 * 1. Create a demo project
 * 2. Run the workflow
 * 3. Monitor job progress until completion
 * 4. Verify analysis results (bands, fermi energy, k-path)
 * 
 * IMPORTANT: This test requires QE to be installed and available on PATH.
 * 
 * NOTE: These tests may have compatibility issues on macOS due to how Playwright
 * launches Electron with debugging flags. They work best on Linux.
 */

import { test, expect } from '@playwright/test';
import * as os from 'os';
import { launchApp, closeApp, navigateToView } from './helpers';
import { createUniqueProjectDir, cleanupProjectDir } from './helpers';

// Skip tests on macOS due to Playwright/Electron compatibility issues
const IS_MACOS = os.platform() === 'darwin';
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true' || IS_MACOS;

// Extended timeout for QE workflow execution (5 minutes)
const QE_TIMEOUT = 5 * 60 * 1000;

test.describe('Demo Workflow Run', () => {
  test.skip(SKIP_E2E, 'Skipped on macOS or when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  test.beforeEach(() => {
    // Create a unique project directory for this test
    projectDir = createUniqueProjectDir('run');
  });
  
  test.afterEach(() => {
    // Clean up the project directory
    if (projectDir) {
      cleanupProjectDir(projectDir);
    }
  });
  
  test('run workflow and verify analysis results', async () => {
    // Use longer test timeout for QE execution
    test.setTimeout(QE_TIMEOUT + 60000);
    
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // === STEP 1: Create Demo Project ===
      await expect(page.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
      
      await page.getByTestId('qv-btn-create-demo-project').click();
      await expect(page.getByTestId('qv-create-project-dialog')).toBeVisible({ timeout: 10000 });
      
      await page.getByTestId('qv-input-parent-dir').fill(projectDir);
      await page.getByTestId('qv-input-project-name').fill('e2e-run');
      await page.getByTestId('qv-btn-confirm-create').click();
      
      await expect(page.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
      
      // === STEP 2: Navigate to Workflows and Run ===
      await navigateToView(page, 'workflows');
      await expect(page.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
      
      // Select the workflow
      await page.getByTestId('qv-workflow-row').first().click();
      await expect(page.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
      
      // Click Run Workflow
      const runButton = page.getByTestId('qv-btn-run-workflow');
      await expect(runButton).toBeVisible();
      await expect(runButton).toBeEnabled();
      await runButton.click();
      
      // === STEP 3: Navigate to Jobs and Monitor ===
      await navigateToView(page, 'jobs');
      await expect(page.getByTestId('qv-jobs-view')).toBeVisible({ timeout: 10000 });
      
      // Wait for job to appear in the list
      await expect(page.getByTestId('qv-job-row')).toBeVisible({ timeout: 30000 });
      
      // Get the status badge - should initially be "running" or "pending"
      const statusBadge = page.getByTestId('qv-job-status').first();
      await expect(statusBadge).toBeVisible();
      
      // Check initial status (should be running or pending)
      const initialStatus = await statusBadge.textContent();
      expect(['pending', 'running']).toContain(initialStatus?.toLowerCase());
      
      // Wait for job to complete (up to 5 minutes)
      // Poll for completion status
      await expect(statusBadge).toHaveText(/completed/i, { timeout: QE_TIMEOUT });
      
      // If we get here, job completed successfully!
      // If status shows "failed", capture error for debugging
      const finalStatus = await statusBadge.textContent();
      if (finalStatus?.toLowerCase().includes('failed')) {
        // Click on the job to see error details
        await page.getByTestId('qv-job-row').first().click();
        await expect(page.getByTestId('qv-job-detail')).toBeVisible();
        
        // Try to capture error text if visible
        const errorText = await page.locator('.job-detail-error').textContent().catch(() => 'Unknown error');
        throw new Error(`Workflow job failed: ${errorText}`);
      }
      
      // === STEP 4: Navigate to Analysis and Verify ===
      await navigateToView(page, 'analysis');
      await expect(page.getByTestId('qv-analysis-view')).toBeVisible({ timeout: 10000 });
      
      // Click on Bands tab
      await page.locator('.type-tab').filter({ hasText: 'Bands' }).click();
      
      // Click Load to load bands data
      await page.locator('.load-button').click();
      
      // Wait for bands chart to appear
      await expect(page.getByTestId('qv-analysis-bands-chart')).toBeVisible({ timeout: 30000 });
      
      // Verify Fermi energy is displayed (not empty)
      const fermiElement = page.getByTestId('qv-analysis-fermi');
      await expect(fermiElement).toBeVisible();
      const fermiText = await fermiElement.textContent();
      expect(fermiText).toBeTruthy();
      expect(fermiText).not.toMatch(/^\s*$/); // Not whitespace-only
      
      // Verify k-path is displayed (should contain special point labels)
      const kpathElement = page.getByTestId('qv-analysis-kpath');
      await expect(kpathElement).toBeVisible();
      const kpathText = await kpathElement.textContent();
      expect(kpathText).toBeTruthy();
      expect(kpathText).not.toMatch(/^\s*$/); // Not whitespace-only
      // K-path should contain some special point labels (Γ, X, L, W, K, etc.)
      // The demo Si workflow typically has a path like Γ → X → W → L → Γ
      
    } finally {
      await closeApp(app);
    }
  });
  
  test('job status transitions correctly during workflow run', async () => {
    // Use longer test timeout for QE execution
    test.setTimeout(QE_TIMEOUT + 60000);
    
    const { app, page } = await launchApp({ timeout: 60000 });
    
    try {
      // Create demo project
      await expect(page.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
      await page.getByTestId('qv-btn-create-demo-project').click();
      await expect(page.getByTestId('qv-create-project-dialog')).toBeVisible({ timeout: 10000 });
      await page.getByTestId('qv-input-parent-dir').fill(projectDir);
      await page.getByTestId('qv-input-project-name').fill('e2e-status');
      await page.getByTestId('qv-btn-confirm-create').click();
      await expect(page.getByTestId('qv-home-project')).toBeVisible({ timeout: 60000 });
      
      // Navigate to workflows and run
      await navigateToView(page, 'workflows');
      await page.getByTestId('qv-workflow-row').first().click();
      await page.getByTestId('qv-btn-run-workflow').click();
      
      // Navigate to jobs
      await navigateToView(page, 'jobs');
      await expect(page.getByTestId('qv-jobs-view')).toBeVisible({ timeout: 10000 });
      
      // Wait for job to appear
      await expect(page.getByTestId('qv-job-row')).toBeVisible({ timeout: 30000 });
      
      // Track status transitions
      const statusBadge = page.getByTestId('qv-job-status').first();
      const observedStatuses: string[] = [];
      
      // Poll for status changes
      let lastStatus = '';
      const startTime = Date.now();
      
      while (Date.now() - startTime < QE_TIMEOUT) {
        const currentStatus = await statusBadge.textContent() || '';
        
        if (currentStatus !== lastStatus) {
          observedStatuses.push(currentStatus.toLowerCase());
          lastStatus = currentStatus;
        }
        
        if (currentStatus.toLowerCase() === 'completed' || currentStatus.toLowerCase() === 'failed') {
          break;
        }
        
        await page.waitForTimeout(2000);
      }
      
      // Verify we saw expected status transitions
      // Should include at least one of: pending, running
      // Should end with: completed
      expect(observedStatuses.length).toBeGreaterThan(0);
      const finalStatus = observedStatuses[observedStatuses.length - 1];
      expect(finalStatus).toBe('completed');
      
    } finally {
      await closeApp(app);
    }
  });
});

