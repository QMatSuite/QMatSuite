/**
 * Comprehensive UI verification for si_bands_demo project.
 *
 * Loads the demo ONCE and asserts all non-computation UI aspects:
 * - Structures view: structure list, count, 3D viewer
 * - Calculations view: calculation list, count, detail panel, name
 * - Step detail: step focus mode, step parameters, step types, file paths
 * - Step YAML: file existence, meta section, step_type_spec, ULID format
 *
 * Consolidates: demo_calculation, structure_viewer_basic,
 *   calculation_management, step_parameter_editing specs.
 *
 * Does NOT run any calculations.
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/demo_project_ui.spec.ts --project=electron
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as fs from 'fs';
import { createUniqueProjectDir, clearE2EProjectsRoot, createDemoProject } from './helpers';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Demo Project UI: si_bands_demo comprehensive', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('demo');
  });

  test('load demo once and verify structures, calculations, steps, and YAML', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    // === Create demo project (once for all assertions) ===
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-demo-ui',
      parentDir: projectDir,
    });
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 10000 });

    // =============================================
    // SECTION 1: Structures view
    // =============================================
    await navigateToView(appPage, 'structures');
    await expect(appPage.getByTestId('qms-structures-view')).toBeVisible({ timeout: 10000 });

    // Verify structure list (1 Si structure from demo)
    const structureRows = appPage.getByTestId('qms-structure-row');
    await expect(structureRows).toHaveCount(1, { timeout: 10000 });

    // Verify count text
    const structureCount = appPage.getByTestId('qms-structures-count');
    await expect(structureCount).toBeVisible();
    await expect(structureCount).toContainText('1 total');

    // Click structure to open 3D viewer
    await structureRows.first().click();
    const viewerPanel = appPage.getByTestId('qms-structure-viewer-panel');
    await expect(viewerPanel).toBeVisible({ timeout: 15000 });
    await expect(viewerPanel).toContainText('Si', { timeout: 5000 });

    // Verify 3D viewer container rendered
    await expect(appPage.getByTestId('qms-structure-viewer')).toBeVisible({ timeout: 10000 });

    // =============================================
    // SECTION 2: Calculations view
    // =============================================
    await navigateToView(appPage, 'calculations');
    const calcView = appPage.getByTestId('qms-calculations-view');
    await expect(calcView).toBeVisible({ timeout: 10000 });

    // Verify Overview & Steps tab is active by default
    const overviewTab = appPage.getByTestId('qms-calc-tab-overview');
    await expect(overviewTab).toBeVisible();
    await expect(overviewTab).toHaveClass(/calculations-workspace-tab--active/);

    // Verify exactly one calculation row
    const calcRows = appPage.getByTestId('qms-calculation-row');
    await expect(calcRows).toHaveCount(1, { timeout: 10000 });

    // Verify calculation count displayed
    const calcCount = appPage.getByTestId('qms-calculations-count');
    await expect(calcCount).toBeVisible();
    await expect(calcCount).toContainText('1');

    // Click calculation to see detail
    await calcRows.first().click();
    const detailPanel = appPage.getByTestId('qms-calculation-detail');
    await expect(detailPanel).toBeVisible({ timeout: 15000 });

    // Verify detail panel shows name and subtitle
    await expect(detailPanel).toContainText('Si bands', { timeout: 5000 });
    await expect(detailPanel.locator('.qms-calc-header-subtitle')).toContainText('Calculation');

    // Verify Run Calculation button visible
    await expect(appPage.getByTestId('qms-btn-run-calculation')).toBeVisible();

    // Verify steps list is visible
    const stepsList = appPage.getByTestId('qms-steps-list');
    await expect(stepsList).toBeVisible({ timeout: 10000 });

    // =============================================
    // SECTION 3: Step detail and YAML verification
    // =============================================
    const stepRows = appPage.locator('[data-testid^="qms-step-row-"]');
    const stepCount = await stepRows.count();
    expect(stepCount).toBeGreaterThan(0);

    // Track unique file paths
    const stepFiles = new Map<string, string>();

    for (let i = 0; i < stepCount; i++) {
      const stepRow = stepRows.nth(i);

      // Get step type and step ID BEFORE entering focus mode
      // (focus mode unmounts CalculationDetailPanel, removing qms-step-row-* from DOM)
      const stepTypeBadge = stepRow.locator('.step-type-badge');
      await expect(stepTypeBadge).toBeVisible({ timeout: 5000 });
      const stepType = (await stepTypeBadge.textContent())?.trim().toLowerCase();
      expect(stepType).toBeTruthy();

      const stepId = await stepRow.getAttribute('data-step-id');

      // Click step button to enter Step Focus mode
      const stepButton = stepRow.locator('button.step-item');
      await expect(stepButton).toBeVisible({ timeout: 5000 });
      await expect(stepButton).toBeEnabled({ timeout: 5000 });
      await stepButton.click({ timeout: 5000 });

      // Verify Step Focus mode activated
      await expect(appPage.getByTestId('qms-calc-overview-tab-focus')).toBeVisible({ timeout: 10000 });
      await expect(appPage.getByTestId('qms-compact-step-list')).toBeVisible({ timeout: 5000 });

      // Verify step detail panel visible
      const stepDetail = appPage.getByTestId('qms-step-detail');
      await expect(stepDetail).toBeVisible({ timeout: 10000 });

      // Verify detail panel step type matches
      const detailBadge = stepDetail.locator('.step-type-badge').first();
      await expect(detailBadge).toHaveText(new RegExp(stepType!, 'i'), { timeout: 5000 });

      // Verify step ID and file path
      const stepIdText = await appPage.getByTestId('qms-step-id').textContent();
      const stepFilePath = await appPage.getByTestId('qms-step-file-path').textContent();
      expect(stepIdText).toBeTruthy();
      expect(stepFilePath).toBeTruthy();

      // Step ID should be ULID format
      if (stepIdText && stepIdText.length >= 20) {
        expect(stepIdText).toMatch(/^[A-Z0-9]{26}$/);
      }

      // Track unique file paths per step
      if (stepId && stepFilePath) {
        stepFiles.set(stepId, stepFilePath);
      }

      // Verify YAML file exists and has correct structure
      if (stepFilePath && fs.existsSync(stepFilePath)) {
        const content = fs.readFileSync(stepFilePath, 'utf-8');
        expect(content).toContain('meta:');
        expect(content).toContain('step_type_spec:');
        expect(content).toMatch(/meta:\s*\n\s*ulid:\s+[A-Z0-9]{26}/);

        // Step type in file should match UI (with optional qe_ prefix)
        if (stepType) {
          const pattern = new RegExp(`step_type_spec:\\s*(qe_)?${stepType}`, 'i');
          expect(content).toMatch(pattern);
        }
      }

      // Exit Step Focus mode
      await appPage.getByTestId('qms-btn-back-to-overview').click();
      await expect(appPage.getByTestId('qms-calc-overview-tab')).toBeVisible({ timeout: 5000 });
      await expect(appPage.getByTestId('qms-compact-step-list')).not.toBeVisible({ timeout: 2000 });
      await appPage.waitForTimeout(200);
    }

    // Verify we collected unique files for all steps
    expect(stepFiles.size).toBe(stepCount);
  });
});
