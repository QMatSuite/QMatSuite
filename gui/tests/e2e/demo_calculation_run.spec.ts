/**
 * E2E Test 3: Run calculation → Run & Logs → Analysis (within calculation)
 * 
 * **This is the ONLY spec file that actually RUNS QE calculations.**
 * All other specs only inspect UI state, metadata, and default parameters.
 * 
 * This spec tests the full per-calculation execution flow:
 * 1. Create a demo project (e.g. "Si bands")
 * 2. Navigate to Calculations view
 * 3. Select a calculation in the "All Calculations" list
 * 4. Verify Overview & Steps tab is active and overview panel is visible
 * 5. Click "Run Calculation" button in Overview & Steps tab
 * 6. Verify auto-switch to Run & Logs tab
 * 7. Monitor job progress in the per-calculation Run & Logs tab until completion
 * 8. Switch to Analysis tab for the same calculation
 * 9. Verify analysis outputs (band plots, DOS plots, Fermi energy, k-path)
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
 *   npx playwright test tests/e2e/demo_calculation_run.spec.ts --project=electron
 * 
 * REFACTOR NOTES (Updated for new Calculations UI):
 * - NO global "Analysis" page anymore - all analysis is per-calculation
 * - NO global "Jobs" navigation in this test - focus on per-calculation Run & Logs tab
 * - Running a calculation auto-switches to "Run & Logs" tab within the calculation
 * - Analysis is accessed via Calculations → Analysis tab (scoped to selected calculation)
 * - The test follows: Calculations → Overview & Steps → Run → Run & Logs → Analysis
 * - NO dependency on qv-calculation-detail - uses tab-based panels instead
 */

import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, cleanupProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

// Extended timeout for QE calculation execution (3 minutes)
const QE_TIMEOUT = QE_JOB_TEST_TIMEOUT;

test.describe('E2E Test 3: Run calculation → Run & Logs → Analysis (within calculation)', () => {
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
  
  test('run calculation once and verify all computation-dependent behavior', async ({ appPage }, testInfo) => {
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
    
    // === PHASE 1: Select calculation and verify Overview ===
    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    
    // Verify "All Calculations" list is visible (use heading role to avoid strict mode violation)
    await expect(appPage.getByRole('heading', { name: /All Calculations/i })).toBeVisible();
    
    // Select the calculation from the list (e.g. "Si bands")
    const calculationRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calculationRow).toBeVisible({ timeout: 5000 });
    await calculationRow.click();
    
    // Assert that Overview & Steps tab is selected
    const overviewTab = appPage.getByTestId('qv-calc-tab-overview');
    await expect(overviewTab).toBeVisible({ timeout: 5000 });
    await expect(overviewTab).toHaveClass(/calculations-workspace-tab--active/);
    
    // Assert that the overview panel is visible
    const overviewPanel = appPage.getByTestId('qv-calc-overview-panel');
    await expect(overviewPanel).toBeVisible({ timeout: 5000 });
    
    // === PHASE 2: Run calculation and verify Run & Logs ===
    // In the Overview & Steps tab, click the "Run Calculation" button
    const runButton = appPage.getByTestId('qv-btn-run-calculation');
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();
    
    // Assert that the UI automatically switches to the Run & Logs tab
    const runLogsTab = appPage.getByTestId('qv-calc-tab-run');
    await expect(runLogsTab).toBeVisible({ timeout: 5000 });
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    
    // Assert that the per-calculation run logs panel is visible
    const runLogsPanel = appPage.getByTestId('qv-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });
    
    // Wait for job summary to appear
    const jobSummary = runLogsPanel.getByTestId('qv-calc-job-summary');
    await expect(jobSummary).toBeVisible({ timeout: 30000 });
    
    // Get the status badge - it's in the header of the Run & Logs panel
    const statusBadge = runLogsPanel.getByTestId('qv-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 5000 });
    
    // Check initial status (should be running or pending)
    // Status may include emoji/icon, so extract just the text
    const initialStatus = await statusBadge.textContent();
    const statusText = initialStatus?.toLowerCase().trim() || '';
    // Remove common emoji/icon prefixes and check status
    const cleanStatus = statusText.replace(/^[⚡▶⏸✓✗\s]+/, '').trim();
    expect(['pending', 'running']).toContain(cleanStatus);
    
    // Track status transitions
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
      // Error details should be visible in the Run & Logs tab
      await appPage.waitForTimeout(1000);
      
      // Try to capture error text from the Run & Logs panel
      let errorText = 'Unknown error';
      try {
        // Look for the error section in the Run & Logs tab
        const errorElement = runLogsPanel.locator('.calculation-run-tab__section--error');
        if (await errorElement.count() > 0) {
          errorText = await errorElement.textContent() || 'Error text not available';
        } else {
          // Fallback: try to get error from job summary
          const errorPre = runLogsPanel.locator('.calculation-run-tab__error');
          if (await errorPre.count() > 0) {
            errorText = await errorPre.textContent() || 'Error section found but no text';
          }
        }
      } catch (e) {
        // If we can't get error text, use the status
        errorText = `Status: ${await statusBadge.textContent()}`;
      }
      
      // Assert with the actual error message
      throw new Error(`Calculation job failed with error: ${errorText}`);
    }
    
    // If job didn't complete or fail, throw timeout error
    if (!completed && !failed) {
      const currentStatus = await statusBadge.textContent();
      throw new Error(`Job did not complete within ${jobCompletionTimeout}ms. Current status: ${currentStatus}`);
    }
    
    // Verify status transitions
    // Should include at least one of: pending, running
    // Should end with: completed
    expect(observedStatuses.length).toBeGreaterThan(0);
    const finalObservedStatus = observedStatuses[observedStatuses.length - 1];
    expect(finalObservedStatus).toBe('completed');
    
    // Wait a bit for UI to stabilize after completion
    await appPage.waitForTimeout(1000);
    
    // Re-query the status badge to get the latest element (in case DOM was updated)
    const finalStatusBadge = runLogsPanel.getByTestId('qv-job-status');
    const finalStatus = await finalStatusBadge.textContent();
    
    // Verify we actually got "completed" status (may include emoji/icon)
    const finalStatusText = finalStatus?.toLowerCase().trim() || '';
    const cleanFinalStatus = finalStatusText.replace(/^[⚡▶⏸✓✗\s]+/, '').trim();
    expect(cleanFinalStatus).toContain('completed');
    
    // Verify logs are visible
    const jobLogs = runLogsPanel.getByTestId('qv-calc-job-logs');
    await expect(jobLogs).toBeVisible();
    
    // === PHASE 3: Switch to Analysis tab for the same calculation ===
    // After the job completes, click the Analysis tab
    const analysisTab = appPage.getByTestId('qv-calc-tab-analysis');
    await expect(analysisTab).toBeVisible({ timeout: 5000 });
    await analysisTab.click();
    
    // Wait for Analysis tab to be active
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    
    // Assert that the per-calculation Analysis panel is visible
    const analysisPanel = appPage.getByTestId('qv-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    
    // Wait a bit for the analysis view to fully render
    // The calculation should already be selected (from when we clicked it earlier)
    await appPage.waitForTimeout(2000);
    
    // With the new step-driven Analysis UX, we need to:
    // 1. Select the 'bandspw' step chip - this step runs bands.x and produces bands.dat.gnu
    // 2. Click the "Plot" view mode tab
    // 3. Wait for the bands chart to appear

    // Find and click the 'bandspw' step chip (step_type_gen is "bandspw", no underscore)
    // Note: The 'bandspw' step actually produces the band structure data (runs bands.x)
    // The analysis bundle's step_ulids contains the bandspw step, not the bands step
    const bandsStepChip = analysisPanel.locator('[data-testid="qv-analysis-step-tab-bandspw"]');
    await expect(bandsStepChip).toBeVisible({ timeout: 5000 });

    // Verify it's the correct step
    const stepTypeGen = await bandsStepChip.getAttribute('data-step-type-gen');
    expect(stepTypeGen?.toLowerCase()).toBe('bandspw');

    await bandsStepChip.click();
    
    // Wait for the view mode tabs to appear
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    
    // Click the Plot tab to switch to plot view
    await plotTab.click();

    // Wait for the Plot tab to become active (React state update)
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // Wait for loading to complete - the loading indicator should disappear
    // or the chart should appear. Use a polling approach to handle the async chain.
    const loadingIndicator = appPage.getByTestId('qv-analysis-loading');
    const bandsChart = appPage.getByTestId('qv-analysis-bands-chart');
    const errorIndicator = appPage.getByTestId('qv-analysis-error');
    const noObjectsIndicator = appPage.getByTestId('qv-analysis-no-objects');

    // Wait up to 30 seconds for either the chart to appear or loading to finish
    await expect(async () => {
      // Check if any terminal state is reached
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await bandsChart.isVisible().catch(() => false);
      const hasError = await errorIndicator.isVisible().catch(() => false);
      const hasNoObjects = await noObjectsIndicator.isVisible().catch(() => false);

      // If still loading, throw to retry
      if (isLoading && !hasChart && !hasError && !hasNoObjects) {
        throw new Error('Still loading analysis...');
      }
    }).toPass({ timeout: 30000 });

    // Now verify the chart is visible
    await expect(bandsChart).toBeVisible({ timeout: 5000 });
    
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
    // The demo Si calculation typically has a path like Γ → X → W → L → Γ
    const kpathText = await kpathElement.textContent();
    expect(kpathText).toBeTruthy();
    // Check for common special point labels
    const hasSpecialPoints = /[ΓXLWK]/.test(kpathText || '');
    expect(hasSpecialPoints).toBe(true);
  });
});
