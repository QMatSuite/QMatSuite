/**
 * Run si_bands_demo and verify ALL analysis outputs in one test.
 *
 * Loads the demo ONCE, runs QE ONCE, then asserts:
 * - Run & Logs: status transitions, job completion, logs visible
 * - SCF convergence: step chip, convergence chart, converged badge
 * - Band structure: step chip, bands chart, Fermi energy, k-path labels
 *
 * Consolidates: demo_calculation_run, analysis_convergence specs.
 *
 * REQUIRES: QE installed and available.
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_project_run.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Demo Project Run: si_bands_demo comprehensive', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('run');
  });

  test('run once and verify convergence + bands analysis', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    // === Create demo project ===
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-run',
      parentDir: projectDir,
    });
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 10000 });

    // === Navigate to Calculations and select ===
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByRole('heading', { name: /All Calculations/i })).toBeVisible();

    const calcRow = appPage.getByTestId('qms-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();

    // Verify Overview & Steps tab is active
    const overviewTab = appPage.getByTestId('qms-calc-tab-overview');
    await expect(overviewTab).toHaveClass(/calculations-workspace-tab--active/);
    await expect(appPage.getByTestId('qms-calc-overview-panel')).toBeVisible({ timeout: 5000 });

    // =============================================
    // PHASE 1: Run calculation
    // =============================================
    const runButton = appPage.getByTestId('qms-btn-run-calculation');
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();

    // Verify auto-switch to Run & Logs tab
    const runLogsTab = appPage.getByTestId('qms-calc-tab-run');
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    const runLogsPanel = appPage.getByTestId('qms-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // Wait for job status to appear
    const statusBadge = runLogsPanel.getByTestId('qms-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

    // Poll for completion
    const startTime = Date.now();
    const jobTimeout = 2.5 * 60 * 1000;
    let completed = false;

    while (Date.now() - startTime < jobTimeout && !completed) {
      const raw = await statusBadge.textContent();
      const status = (raw || '').toLowerCase().replace(/^[^a-z]+/, '').trim();

      if (status.includes('failed')) {
        let errorText = 'Unknown error';
        try {
          const errorEl = runLogsPanel.locator('.calculation-run-tab__error');
          if (await errorEl.count() > 0) {
            errorText = await errorEl.textContent() || errorText;
          }
        } catch { /* use default */ }
        throw new Error(`QE calculation failed: ${errorText}`);
      }
      if (status.includes('completed')) {
        completed = true;
        break;
      }
      await appPage.waitForTimeout(2000);
    }
    if (!completed) {
      const currentStatus = await statusBadge.textContent();
      throw new Error(`Job did not complete within ${jobTimeout}ms. Status: ${currentStatus}`);
    }

    // Verify logs are visible
    await expect(runLogsPanel.getByTestId('qms-calc-job-logs')).toBeVisible();

    // =============================================
    // PHASE 2: Convergence analysis (SCF step)
    // =============================================
    const analysisTab = appPage.getByTestId('qms-calc-tab-analysis');
    await expect(analysisTab).toBeVisible({ timeout: 5000 });
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qms-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    // Select SCF step chip
    const scfChip = analysisPanel.locator('[data-testid="qms-analysis-step-tab-scf"]');
    await expect(scfChip).toBeVisible({ timeout: 5000 });
    await scfChip.click();

    // Click Plot tab
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // Ensure we validate run output, not reference
    const referenceToggle = appPage.getByTestId('qms-analysis-reference-toggle');
    if (await referenceToggle.isVisible().catch(() => false)) {
      if (await referenceToggle.isChecked()) {
        await referenceToggle.uncheck();
      }
      await expect(referenceToggle).not.toBeChecked();
    }
    await expect(appPage.getByTestId('qms-analysis-reference-banner')).toHaveCount(0);

    // Wait for convergence chart
    const loadingIndicator = appPage.getByTestId('qms-analysis-loading');
    const convergenceChart = appPage.getByTestId('qms-analysis-convergence-chart');

    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await convergenceChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading convergence...');
      }
    }).toPass({ timeout: 30000 });

    await expect(convergenceChart).toBeVisible({ timeout: 5000 });

    // Verify SVG + curve + axis ticks
    await expect(convergenceChart.locator('.recharts-wrapper > .recharts-surface').first()).toBeVisible({ timeout: 5000 });

    const curvePaths = convergenceChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => curvePaths.count(), {
        timeout: 10000,
        message: 'Convergence plot has no rendered line curve',
      })
      .toBeGreaterThan(0);

    const xAxisTicks = convergenceChart.locator(
      '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value, .recharts-xAxis .recharts-cartesian-axis-tick-value',
    );
    await expect
      .poll(async () => xAxisTicks.count(), {
        timeout: 10000,
        message: 'Convergence plot x-axis ticks did not render',
      })
      .toBeGreaterThan(1);

    // Verify convergence info bar + badge
    const convergenceInfo = appPage.getByTestId('qms-analysis-convergence-info');
    await expect(convergenceInfo).toBeVisible({ timeout: 5000 });
    const convergedBadge = convergenceInfo.locator('.analysis-viz__convergence-badge');
    await expect(convergedBadge).toBeVisible({ timeout: 5000 });
    const badgeText = await convergedBadge.textContent();
    expect(badgeText).toMatch(/[Cc]onverged/);

    // =============================================
    // PHASE 3: Bands analysis (bandspw step)
    // =============================================
    const bandsChip = analysisPanel.locator('[data-testid="qms-analysis-step-tab-bandspw"]');
    await expect(bandsChip).toBeVisible({ timeout: 5000 });
    await bandsChip.click();

    // Click Plot tab again (it may have reset)
    const plotTab2 = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab2).toBeVisible({ timeout: 5000 });
    await plotTab2.click();
    await expect(plotTab2).toHaveClass(/--active/, { timeout: 5000 });

    // Wait for bands chart
    const bandsChart = appPage.getByTestId('qms-analysis-bands-chart');

    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await bandsChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading bands...');
      }
    }).toPass({ timeout: 30000 });

    await expect(bandsChart).toBeVisible({ timeout: 5000 });

    // Verify chart has content
    const chartChildren = bandsChart.locator('*');
    expect(await chartChildren.count()).toBeGreaterThan(0);

    // Verify Fermi energy displayed
    const fermiElement = appPage.getByTestId('qms-analysis-fermi');
    await expect(fermiElement).toBeVisible();
    await expect(fermiElement).not.toHaveText(/^\s*$/, { timeout: 5000 });

    // Verify k-path with special point labels
    const kpathElement = appPage.getByTestId('qms-analysis-kpath');
    await expect(kpathElement).toBeVisible();
    const kpathText = await kpathElement.textContent();
    expect(kpathText).toBeTruthy();
    expect(/[ΓXLWK]/.test(kpathText || '')).toBe(true);
  });
});
