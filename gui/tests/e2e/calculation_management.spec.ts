/**
 * E2E Test: Calculation Management
 *
 * Tests calculation CRUD operations (create, rename, view).
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Calculation Management', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('calc-mgmt');
  });

  test('creates calculation and displays in calculations list', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    // Create demo project
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-calc-mgmt',
      parentDir: projectDir,
    });

    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });

    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');

    // Verify calculations view loads
    const calcView = appPage.getByTestId('qv-calculations-view');
    await expect(calcView).toBeVisible({ timeout: 10000 });

    // Verify at least one calculation exists (from demo project)
    const calcRows = appPage.getByTestId('qv-calculation-row');
    await expect(calcRows).toHaveCount(1, { timeout: 10000 });

    // Verify calculation count is displayed
    const calcCount = appPage.getByTestId('qv-calculations-count');
    await expect(calcCount).toBeVisible();
    await expect(calcCount).toContainText('1');
  });

  test('clicking calculation shows detail panel', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    // Create demo project
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-calc-detail',
      parentDir: projectDir,
    });

    // Navigate to Calculations
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });

    // Click on first calculation row
    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 10000 });
    await calcRow.click();

    // Wait for calculation detail panel to appear
    const detailPanel = appPage.getByTestId('qv-calculation-detail');
    await expect(detailPanel).toBeVisible({ timeout: 15000 });

    // Verify detail panel shows calculation name
    await expect(detailPanel).toContainText('Si bands', { timeout: 5000 });

    // Verify steps list is visible
    const stepsList = appPage.getByTestId('qv-steps-list');
    await expect(stepsList).toBeVisible({ timeout: 10000 });
  });
});
