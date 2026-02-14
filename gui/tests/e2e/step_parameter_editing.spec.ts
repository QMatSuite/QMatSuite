/**
 * E2E Test: Step Parameter Editing
 *
 * Tests step selection and parameter display in step detail view.
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Step Parameter Editing', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('step-editing');
  });

  test('clicking step shows step detail panel with parameters', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    // Create demo project with calculation
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-step-edit',
      parentDir: projectDir,
    });

    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });

    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });

    // Click on first calculation
    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 10000 });
    await calcRow.click();

    // Wait for calculation detail to load
    const detailPanel = appPage.getByTestId('qv-calculation-detail');
    await expect(detailPanel).toBeVisible({ timeout: 15000 });

    // Verify steps list is visible
    const stepsList = appPage.getByTestId('qv-steps-list');
    await expect(stepsList).toBeVisible({ timeout: 10000 });

    // Click on first step
    const firstStepRow = stepsList.locator('[data-testid^="qv-step-row-"]').first();
    await expect(firstStepRow).toBeVisible({ timeout: 10000 });

    // Click the step button within the step row
    const firstStepButton = firstStepRow.locator('[data-testid^="qv-step-button-"]');
    await expect(firstStepButton).toBeVisible({ timeout: 5000 });
    await firstStepButton.click();

    // Wait for step detail panel to appear
    const stepDetailPanel = appPage.getByTestId('qv-step-detail');
    await expect(stepDetailPanel).toBeVisible({ timeout: 15000 });

    // Verify step detail panel shows step information
    await expect(stepDetailPanel).toContainText('Step', { timeout: 5000 });

    // Verify step detail content is loaded (check for common UI elements)
    await expect(stepDetailPanel).toContainText('scf', { timeout: 5000 });
  });

  test('step detail panel displays step type and index', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    // Create demo project
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-step-index',
      parentDir: projectDir,
    });

    // Navigate to Calculations and select first calculation
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });

    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await calcRow.click();
    await expect(appPage.getByTestId('qv-calculation-detail')).toBeVisible({ timeout: 15000 });

    // Click on second step (index 2, nscf)
    const stepsList = appPage.getByTestId('qv-steps-list');
    const secondStepRow = stepsList.locator('[data-testid^="qv-step-row-"]').nth(1);
    await expect(secondStepRow).toBeVisible({ timeout: 10000 });

    const secondStepButton = secondStepRow.locator('[data-testid^="qv-step-button-"]');
    await secondStepButton.click();

    // Wait for step detail panel
    const stepDetailPanel = appPage.getByTestId('qv-step-detail');
    await expect(stepDetailPanel).toBeVisible({ timeout: 15000 });

    // Verify step shows index indicator (e.g., "Step 2 of 4" or similar)
    await expect(stepDetailPanel).toContainText('2', { timeout: 5000 });
  });
});
