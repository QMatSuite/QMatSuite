/**
 * E2E Test 3: Run workflow → Jobs → Analysis
 * 
 * Tests the full workflow execution flow:
 * 1. Create a demo project
 * 2. Run the workflow
 * 3. Monitor job progress until completion (or failure)
 * 4. Verify analysis results (bands, fermi energy, k-path)
 * 
 * IMPORTANT: This test requires QE to be installed and available on PATH.
 * Do not skip this test on missing QE; failure means real problem.
 * 
 * Each test file runs in its own Playwright process, ensuring complete isolation.
 * The unified Electron fixture automatically chooses the appropriate launch strategy
 * based on platform (Linux: _electron.launch, macOS: CDP).
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_workflow_run.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, cleanupProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

// Extended timeout for QE workflow execution (3 minutes)
const QE_TIMEOUT = QE_JOB_TEST_TIMEOUT;

test.describe('E2E Test 3: Run workflow → Jobs → Analysis', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  // Clear E2E projects directory before each test
  // Leave it after tests for inspection
  test.beforeEach(() => {
    clearE2EProjectsRoot();
    // Create a unique project directory for this test
    projectDir = createUniqueProjectDir('run');
  });
  
  // Don't clean up after tests - leave projects for inspection
  
  test('run workflow, track status transitions, and verify analysis results', async ({ appPage }, testInfo) => {
    // Override timeout to 3 minutes for QE job execution
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);
    
    // === STEP 1: Create Demo Project via Demo Gallery ===
    // Flow: Home → Browse Demo Gallery → Si Bands demo card → Create Project → Project loaded
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-run',
      parentDir: projectDir,
    });
    
    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    
    // === STEP 2: Navigate to Workflows and Run ===
    await navigateToView(appPage, 'workflows');
    await expect(appPage.getByTestId('qv-workflows-view')).toBeVisible({ timeout: 10000 });
    
    // Select the workflow
    await appPage.getByTestId('qv-workflow-row').first().click();
    await expect(appPage.getByTestId('qv-workflow-detail')).toBeVisible({ timeout: 10000 });
    
    // Click Run Workflow
    const runButton = appPage.getByTestId('qv-btn-run-workflow');
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();
    
    // === STEP 3: Navigate to Jobs and Monitor Status Transitions ===
    await navigateToView(appPage, 'jobs');
    await expect(appPage.getByTestId('qv-jobs-view')).toBeVisible({ timeout: 10000 });
    
    // Wait for job to appear in the list
    await expect(appPage.getByTestId('qv-job-row')).toBeVisible({ timeout: 30000 });
    
    // Get the status badge - should initially be "running" or "pending"
    const statusBadge = appPage.getByTestId('qv-job-status').first();
    await expect(statusBadge).toBeVisible();
    
    // Check initial status (should be running or pending)
    // Status may include emoji/icon, so extract just the text
    const initialStatus = await statusBadge.textContent();
    const statusText = initialStatus?.toLowerCase().trim() || '';
    // Remove common emoji/icon prefixes and check status
    const cleanStatus = statusText.replace(/^[⚡▶⏸✓✗\s]+/, '').trim();
    expect(['pending', 'running']).toContain(cleanStatus);
    
    // Track status transitions (from the second test)
    const observedStatuses: string[] = [cleanStatus];
    let lastStatus = cleanStatus;
    
    // Wait for job to complete (up to 2.5 minutes to leave buffer for analysis step)
    // Poll for completion status - wait for the text to match "completed" (case-insensitive)
    // Use a shorter timeout here to leave time for the analysis step within the 3-minute global timeout
    const jobCompletionTimeout = Math.min(QE_TIMEOUT, 2.5 * 60 * 1000);
    
    // Poll for completion with periodic page health checks
    // Also check for "failed" status and assert immediately if detected
    const startTime = Date.now();
    let completed = false;
    let failed = false;
    
    while (Date.now() - startTime < jobCompletionTimeout && !completed && !failed) {
      try {
        // Check if page is still responsive
        await appPage.evaluate(() => document.readyState);
        
        // Check status (may include emoji/icon, so clean it)
        const currentStatusRaw = await statusBadge.textContent();
        const currentStatusText = currentStatusRaw?.toLowerCase().trim() || '';
        // Remove common emoji/icon prefixes
        const currentStatus = currentStatusText.replace(/^[⚡▶⏸✓✗\s]+/, '').trim();
        
        // Track status transitions
        if (currentStatus !== lastStatus) {
          observedStatuses.push(currentStatus);
          lastStatus = currentStatus;
        }
        
        // Check for failed status immediately
        if (currentStatus.includes('failed')) {
          failed = true;
          break;
        }
        
        // Check for completed status
        if (currentStatus.includes('completed')) {
          completed = true;
          break;
        }
        
        // Wait a bit before next check
        await appPage.waitForTimeout(2000);
      } catch (error: any) {
        // If page becomes unresponsive, throw a clear error
        if (error.message?.includes('Target closed') || error.message?.includes('Session closed')) {
          throw new Error('Electron page became unresponsive or closed during job monitoring. The app should stay open throughout the test.');
        }
        throw error;
      }
    }
    
    // If job failed, capture error details and assert
    if (failed) {
      // Click on the job to see error details
      await appPage.getByTestId('qv-job-row').first().click();
      await expect(appPage.getByTestId('qv-job-detail')).toBeVisible({ timeout: 5000 });
      
      // Wait for error section to be visible
      await appPage.waitForTimeout(1000);
      
      // Try to capture error text from the job detail panel
      let errorText = 'Unknown error';
      try {
        // Look for the error section with class 'job-detail-error'
        const errorElement = appPage.locator('.job-detail-error');
        if (await errorElement.count() > 0) {
          errorText = await errorElement.textContent() || 'Error text not available';
        } else {
          // Fallback: try to get any error message from the job detail
          const errorSection = appPage.locator('.job-detail-section--error');
          if (await errorSection.count() > 0) {
            errorText = await errorSection.textContent() || 'Error section found but no text';
          }
        }
      } catch (e) {
        // If we can't get error text, use the status
        errorText = `Status: ${await statusBadge.textContent()}`;
      }
      
      // Assert with the actual error message
      throw new Error(`Workflow job failed with error: ${errorText}`);
    }
    
    // If job didn't complete or fail, throw timeout error
    if (!completed && !failed) {
      const currentStatus = await statusBadge.textContent();
      throw new Error(`Job did not complete within ${jobCompletionTimeout}ms. Current status: ${currentStatus}`);
    }
    
    // Verify status transitions (from the second test)
    // Should include at least one of: pending, running
    // Should end with: completed
    expect(observedStatuses.length).toBeGreaterThan(0);
    const finalObservedStatus = observedStatuses[observedStatuses.length - 1];
    expect(finalObservedStatus).toBe('completed');
    
    // Wait a bit for UI to stabilize after completion
    await appPage.waitForTimeout(1000);
    
    // Re-query the status badge to get the latest element (in case DOM was updated)
    const finalStatusBadge = appPage.getByTestId('qv-job-status').first();
    const finalStatus = await finalStatusBadge.textContent();
    
    // Verify we actually got "completed" status (may include emoji/icon)
    const finalStatusText = finalStatus?.toLowerCase().trim() || '';
    const cleanFinalStatus = finalStatusText.replace(/^[⚡▶⏸✓✗\s]+/, '').trim();
    expect(cleanFinalStatus).toContain('completed');
    
    // === STEP 4: Navigate to Analysis and Verify ===
    await navigateToView(appPage, 'analysis');
    await expect(appPage.getByTestId('qv-analysis-view')).toBeVisible({ timeout: 10000 });
    
    // Wait a bit for the analysis view to fully render and workflow to be selected
    await appPage.waitForTimeout(2000);
    
    // Verify a workflow is selected (should be auto-selected if only one exists)
    const selectedWorkflow = appPage.locator('.workflow-option--selected');
    await expect(selectedWorkflow).toBeVisible({ timeout: 5000 });
    
    // Click on Bands tab (the button with text containing "Bands")
    const bandsTab = appPage.locator('.type-tab').filter({ hasText: /bands/i });
    await expect(bandsTab).toBeVisible({ timeout: 5000 });
    await bandsTab.click();
    
    // Wait for the tab click to register and UI to update
    await appPage.waitForTimeout(1000);
    
    // Find and click the Load button - wait for it to be enabled
    const loadButton = appPage.locator('.load-button');
    await expect(loadButton).toBeVisible({ timeout: 5000 });
    
    // Wait for button to be enabled (not disabled)
    await expect(loadButton).toBeEnabled({ timeout: 10000 });
    
    // Click the Load button
    await loadButton.click();
    
    // Wait for bands chart to appear (this may take time to load data)
    // The chart should appear after data is loaded
    await expect(appPage.getByTestId('qv-analysis-bands-chart')).toBeVisible({ timeout: 30000 });
    
    // Optionally check that the chart container has some child elements (e.g. band paths)
    const chartContainer = appPage.getByTestId('qv-analysis-bands-chart');
    const chartChildren = chartContainer.locator('*');
    const childCount = await chartChildren.count();
    expect(childCount).toBeGreaterThan(0);
    
    // Verify Fermi energy is displayed (not empty)
    const fermiElement = appPage.getByTestId('qv-analysis-fermi');
    await expect(fermiElement).toBeVisible();
    await expect(fermiElement).not.toHaveText(/^\s*$/, { timeout: 5000 });
    
    // Verify k-path is displayed (should contain special point labels)
    const kpathElement = appPage.getByTestId('qv-analysis-kpath');
    await expect(kpathElement).toBeVisible();
    await expect(kpathElement).not.toHaveText(/^\s*$/, { timeout: 5000 });
    
    // K-path should contain some special point labels (Γ, X, L, W, K, etc.)
    // The demo Si workflow typically has a path like Γ → X → W → L → Γ
    const kpathText = await kpathElement.textContent();
    expect(kpathText).toBeTruthy();
    // Check for common special point labels
    const hasSpecialPoints = /[ΓXLWK]/.test(kpathText || '');
    expect(hasSpecialPoints).toBe(true);
  });
});

