/**
 * E2E: DOS analysis visualization after running si_dos_demo.
 *
 * Creates the si_dos_demo project, runs the calculation (SCF + NSCF + DOS),
 * switches to Analysis tab, selects the DOS step, and verifies the DOS chart
 * renders with lines and a Fermi energy label.
 */

import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot } from './helpers/paths';
import { createDemoProject } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Analysis: DOS', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('dos');
  });

  test('renders DOS chart after QE si_dos_demo run', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    // === Create demo project ===
    await createDemoProject(appPage, {
      demoId: 'si_dos_demo',
      projectName: 'e2e-dos',
      parentDir: projectDir,
    });
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 10000 });

    // === Navigate to Calculations and select ===
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });
    const calcRow = appPage.getByTestId('qms-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();

    // === Run calculation ===
    const runButton = appPage.getByTestId('qms-btn-run-calculation');
    await expect(runButton).toBeVisible();
    await expect(runButton).toBeEnabled();
    await runButton.click();

    // Wait for Run & Logs tab
    const runLogsTab = appPage.getByTestId('qms-calc-tab-run');
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    const runLogsPanel = appPage.getByTestId('qms-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // Wait for job completion
    const statusBadge = runLogsPanel.getByTestId('qms-job-status');
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
    const analysisTab = appPage.getByTestId('qms-calc-tab-analysis');
    await expect(analysisTab).toBeVisible({ timeout: 5000 });
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qms-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    // === Click DOS step tab ===
    const dosStepChip = analysisPanel.locator('[data-testid="qms-analysis-step-tab-dos"]');
    await expect(dosStepChip).toBeVisible({ timeout: 5000 });
    await dosStepChip.click();

    // === Click Plot tab ===
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // === Wait for loading to finish ===
    const loadingIndicator = appPage.getByTestId('qms-analysis-loading');
    const dosChart = appPage.getByTestId('qms-analysis-dos-chart');

    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await dosChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading...');
      }
    }).toPass({ timeout: 30000 });

    // === Assert DOS chart visible with lines ===
    await expect(dosChart).toBeVisible({ timeout: 5000 });
    const chartChildren = dosChart.locator('*');
    expect(await chartChildren.count()).toBeGreaterThan(0);

    // Recharts renders <path> elements for Line components
    const lineElements = dosChart.locator('.recharts-line');
    expect(await lineElements.count()).toBeGreaterThan(0);

    // === Assert Fermi energy label ===
    const fermiElement = appPage.getByTestId('qms-analysis-fermi');
    await expect(fermiElement).toBeVisible();
    await expect(fermiElement).not.toHaveText(/^\s*$/, { timeout: 5000 });
  });
});
