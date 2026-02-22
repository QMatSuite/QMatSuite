/**
 * E2E: Step defaults and import button verification.
 *
 * Loads si_bands_demo ONCE and verifies:
 * A. From-scratch step creation uses QMS defaults (CONTROL, ELECTRONS, conv_thr)
 * B. Import QE input button exists with correct tooltip
 *
 * Does NOT run any calculations.
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/step_defaults.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { createUniqueProjectDir, clearE2EProjectsRoot, getRepoRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Step Defaults & Import', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('step-defaults');
  });

  test('from-scratch step defaults and import button', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(60 * 1000);

    // Create demo project (once for all assertions)
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-step-defaults',
      parentDir: projectDir,
    });
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 10000 });

    // Navigate to Calculations and select
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });

    const calculationRows = appPage.getByTestId('qms-calculation-row');
    await expect(calculationRows).toHaveCount(1);
    await calculationRows.first().click();
    await expect(appPage.getByTestId('qms-calculation-detail')).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qms-calc-overview-tab')).toBeVisible();

    // =============================================
    // PART A: Verify import button exists
    // =============================================
    const importBtn = appPage.getByTestId('qms-import-step-btn');
    await expect(importBtn).toBeVisible();
    await expect(importBtn).toHaveAttribute('title', 'Import QE input file as step (preserves original parameters)');

    // =============================================
    // PART B: Add from-scratch SCF step and verify defaults
    // =============================================
    await appPage.getByTestId('qms-add-step-btn').click();
    await expect(appPage.getByTestId('qms-add-step-form')).toBeVisible({ timeout: 5000 });

    const stepTypeSelect = appPage.locator('.add-step-form select').first();
    await stepTypeSelect.selectOption('scf');
    await appPage.getByTestId('qms-confirm-add-step').click();

    // Wait for step to be added
    await expect(appPage.getByTestId('qms-steps-list')).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qms-add-step-form')).not.toBeVisible({ timeout: 10000 });

    const stepRows = appPage.locator('[data-testid^="qms-step-row-"]');
    await expect(stepRows.first()).toBeVisible({ timeout: 10000 });

    // Find the new scf step
    const scfStepRow = stepRows.filter({
      has: appPage.locator('.step-type-badge').filter({ hasText: /^scf$/i })
    }).last();
    await expect(scfStepRow).toBeVisible({ timeout: 10000 });

    const stepButton = scfStepRow.locator('button.step-item');
    await expect(stepButton).toBeEnabled({ timeout: 5000 });
    await stepButton.click({ timeout: 5000 });

    // Verify Step Focus mode
    await expect(appPage.getByTestId('qms-calc-overview-tab-focus')).toBeVisible({ timeout: 10000 });
    const stepDetailPanel = appPage.getByTestId('qms-step-detail');
    await expect(stepDetailPanel).toBeVisible({ timeout: 10000 });
    await expect(stepDetailPanel.locator('.step-type-badge')).toContainText('scf');

    // Read step file and verify defaults
    const stepFilePath = stepDetailPanel.getByTestId('qms-step-file-path');
    await expect(stepFilePath).toBeVisible({ timeout: 5000 });
    const filePathText = await stepFilePath.textContent();
    expect(filePathText).toBeTruthy();

    const projectPath = path.join(projectDir, 'e2e-step-defaults');
    const resolvedPath = path.isAbsolute(filePathText!)
      ? filePathText!
      : path.join(projectPath, filePathText!);

    await appPage.waitForTimeout(1000);
    const content = fs.readFileSync(resolvedPath, 'utf-8');

    expect(content).toContain('CONTROL');
    expect(content).toMatch(/calculation:\s*['"]?scf['"]?/);
    expect(content).toContain('ELECTRONS');
    expect(content).toMatch(/conv_thr:\s*1\.?0*e?-?0*8/i);
  });
});
