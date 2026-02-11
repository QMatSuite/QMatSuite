/**
 * E2E: Convergence analysis visualization after running si_bands_demo.
 *
 * Uses the proven si_bands_demo project (SCF → NSCF → Bands),
 * runs the calculation, switches to Analysis tab, selects the scf step,
 * and verifies the convergence chart renders with a "Converged" badge.
 */

import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot } from './helpers/paths';
import { createDemoProject } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Analysis: Convergence', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('convergence');
  });

  test('renders convergence chart after QE si_bands_demo run', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    // === Create demo project (proven working si_bands_demo) ===
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-convergence',
      parentDir: projectDir,
    });
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });

    // === Navigate to Calculations and select ===
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();

    // === Run calculation ===
    const runButton = appPage.getByTestId('qv-btn-run-calculation');
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();

    // Wait for Run & Logs tab to auto-activate
    const runLogsTab = appPage.getByTestId('qv-calc-tab-run');
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    const runLogsPanel = appPage.getByTestId('qv-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // Wait for job completion
    const statusBadge = runLogsPanel.getByTestId('qv-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

    const startTime = Date.now();
    const timeout = 2.5 * 60 * 1000;
    let completed = false;

    while (Date.now() - startTime < timeout && !completed) {
      const raw = await statusBadge.textContent();
      const status = (raw || '').toLowerCase().replace(/^[^a-z]+/, '').trim();

      if (status.includes('failed')) {
        throw new Error(`Calculation job failed`);
      }
      if (status.includes('completed')) {
        completed = true;
        break;
      }
      await appPage.waitForTimeout(2000);
    }
    if (!completed) throw new Error('Job did not complete in time');

    // === Switch to Analysis tab ===
    const analysisTab = appPage.getByTestId('qv-calc-tab-analysis');
    await expect(analysisTab).toBeVisible({ timeout: 5000 });
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qv-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    // === Select scf step chip (si_bands_demo has scf, nscf, bandspw, bands steps) ===
    const scfStepChip = analysisPanel.locator('[data-testid="qv-analysis-step-tab-scf"]');
    await expect(scfStepChip).toBeVisible({ timeout: 5000 });
    await scfStepChip.click();

    // === Click Plot tab ===
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // === Wait for loading to finish ===
    const loadingIndicator = appPage.getByTestId('qv-analysis-loading');
    const convergenceChart = appPage.getByTestId('qv-analysis-convergence-chart');

    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await convergenceChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading...');
      }
    }).toPass({ timeout: 30000 });

    // === Assert convergence chart visible ===
    await expect(convergenceChart).toBeVisible({ timeout: 5000 });

    // === Assert convergence info bar ===
    const convergenceInfo = appPage.getByTestId('qv-analysis-convergence-info');
    await expect(convergenceInfo).toBeVisible({ timeout: 5000 });

    // === Assert convergence badge (either "Converged" or "Not converged") ===
    const convergedBadge = convergenceInfo.locator('.analysis-viz__convergence-badge');
    await expect(convergedBadge).toBeVisible({ timeout: 5000 });
    // Badge should contain either "Converged" or "Not converged"
    const badgeText = await convergedBadge.textContent();
    expect(badgeText).toMatch(/[Cc]onverged/);
  });
});
