/**
 * Pair 2 E2E: Si VC-Relax Real-Run Smoke Test — FROM SCRATCH
 *
 * Workflow:
 * create project → import Si structure → create QE calculation →
 * set pseudo mapping → add RELAX step → set VC-relax parameters →
 * run QE → verify convergence + trajectory analysis plots.
 *
 * No demo usage. All actions are GUI user operations.
 */

import * as fs from 'fs';
import * as path from 'path';
import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { clearE2EProjectsRoot, createUniqueProjectDir, getRepoRoot } from './helpers/paths';
import { waitForHomeWelcome } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Pair 2 E2E: Si VC-Relax Real-Run (from scratch)', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('realrun-si-relax');
  });

  test('from-scratch Si VC-relax with convergence + trajectory analysis', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    const captureStepState = async (name: string) => {
      const screenshotPath = testInfo.outputPath(`${name}.png`);
      await appPage.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(name, { path: screenshotPath, contentType: 'image/png' });
    };

    const repoRoot = getRepoRoot();
    const siCifFile = path.join(repoRoot, 'tests', 'data', 'structures', 'si_diamond.cif');
    expect(fs.existsSync(siCifFile), `Missing test structure file at ${siCifFile}`).toBeTruthy();

    // 1) Create project
    await waitForHomeWelcome(appPage);
    await appPage.getByTestId('qv-welcome-btn-create-new-project').click();
    await appPage.getByTestId('qv-input-parent-dir').fill(projectDir);
    await appPage.getByTestId('qv-input-project-name').fill('si-relax-e2e');
    await appPage.getByTestId('qv-btn-confirm-create').click();
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 15000 });

    // 2) Import Si structure (local CIF)
    await navigateToView(appPage, 'structures');
    await appPage.getByTestId('qv-btn-import-structure').click();
    await appPage.getByTestId('qv-import-structure-file').fill(siCifFile);
    await appPage.getByTestId('qv-import-structure-name').fill('Si');
    await appPage.getByTestId('qv-btn-confirm-import-structure').click();
    await appPage.waitForTimeout(2000);

    // 3) Create QE calculation
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    await appPage.getByTestId('qv-btn-new-calculation').click();
    await appPage.getByTestId('qv-create-calc-name').fill('Si Relax Test');

    const structureSelect = appPage.getByTestId('qv-create-calc-structure');
    const structureOptions = structureSelect.locator('option');
    const structureCount = await structureOptions.count();
    let selectedStructure = false;
    for (let i = 0; i < structureCount; i++) {
      const text = await structureOptions.nth(i).textContent();
      if (text && text.includes('Si')) {
        await structureSelect.selectOption({ index: i });
        selectedStructure = true;
        break;
      }
    }
    expect(selectedStructure).toBeTruthy();

    await appPage.getByTestId('qv-create-calc-engine').selectOption({ value: 'qe' });
    await appPage.getByTestId('qv-btn-confirm-create-calc').click();
    await appPage.waitForTimeout(2000);

    // 4) Select calculation row
    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();
    await expect(appPage.getByTestId('qv-calc-tab-overview')).toHaveClass(/calculations-workspace-tab--active/);
    await expect(appPage.getByTestId('qv-calc-overview-panel')).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(1000);

    // 5) Configure pseudo mapping
    const editPseudoBtn = appPage.getByTestId('qv-btn-edit-pseudos');
    await expect(editPseudoBtn).toBeVisible({ timeout: 10000 });
    await editPseudoBtn.click();

    const pseudoSelectSi = appPage.getByTestId('qv-pseudo-select-Si');
    await expect(pseudoSelectSi).toBeVisible({ timeout: 10000 });
    const pseudoOptions = pseudoSelectSi.locator('option');
    await expect
      .poll(async () => pseudoOptions.count(), {
        timeout: 15000,
        message: 'Pseudo dropdown did not populate for Si',
      })
      .toBeGreaterThan(1);

    const currentPseudoValue = await pseudoSelectSi.inputValue();
    if (!currentPseudoValue) {
      await pseudoSelectSi.selectOption({ index: 1 });
    }

    const pseudoOverlay = appPage.locator('.pseudo-edit-modal-overlay');
    if (await pseudoOverlay.isVisible().catch(() => false)) {
      const pseudoApplyBtn = appPage.getByTestId('qv-pseudo-apply');
      if (await pseudoApplyBtn.isVisible().catch(() => false)) {
        await pseudoApplyBtn.click({ timeout: 3000 }).catch(() => {});
      }
      if (await pseudoOverlay.isVisible().catch(() => false)) {
        const pseudoModalClose = appPage.locator('.pseudo-edit-modal-close');
        if (await pseudoModalClose.isVisible().catch(() => false)) {
          await pseudoModalClose.click({ timeout: 3000 }).catch(() => {});
        }
      }
    }
    await expect(pseudoOverlay).toBeHidden({ timeout: 15000 });

    // 6) Add RELAX step
    try {
      const addStepBtn = appPage.getByTestId('qv-add-step-btn');
      await expect(addStepBtn).toBeVisible({ timeout: 5000 });
      await addStepBtn.scrollIntoViewIfNeeded();
      await addStepBtn.click({ timeout: 5000 });

      const addStepForm = appPage.getByTestId('qv-add-step-form');
      await expect(addStepForm).toBeVisible({ timeout: 5000 });

      const stepTypeSelect = appPage.getByTestId('qv-add-step-type-select');
      const stepTypeOptions = stepTypeSelect.locator('option');
      await expect
        .poll(async () => stepTypeOptions.count(), {
          timeout: 15000,
          message: 'Add-step dropdown is empty (engine_family/palette issue)',
        })
        .toBeGreaterThan(1);

      const stepTypeValues = await stepTypeOptions.evaluateAll((options) =>
        options.map((opt) => (opt as HTMLOptionElement).value),
      );
      expect(stepTypeValues).toContain('relax');
      await stepTypeSelect.selectOption({ value: 'relax' });

      const confirmAddStepBtn = appPage.getByTestId('qv-confirm-add-step');
      await expect(confirmAddStepBtn).toBeEnabled();
      await confirmAddStepBtn.click({ timeout: 5000 });

      const stepRows = appPage.locator('[data-testid^="qv-step-row-"]');
      await expect
        .poll(async () => stepRows.count(), {
          timeout: 15000,
          message: 'Relax step was not added after clicking Add Step',
        })
        .toBeGreaterThan(0);
    } catch (e) {
      await captureStepState('add-step-failure-relax');
      throw e;
    }

    // 7) Open step detail
    const stepsContainer = appPage.getByTestId('qv-steps-list');
    await expect(stepsContainer).toBeVisible({ timeout: 5000 });
    const stepButton = stepsContainer.locator('[data-testid^="qv-step-button-"]').first();
    await expect(stepButton).toBeVisible({ timeout: 5000 });
    await stepButton.click();
    await expect(appPage.getByTestId('qv-step-detail')).toBeVisible({ timeout: 10000 });

    const ensureParamRow = async (section: string, param: string) => {
      const sectionLower = section.toLowerCase();
      const paramLower = param.toLowerCase();
      const row = appPage.getByTestId(`qv-param-row-${sectionLower}-${paramLower}`);
      if ((await row.count()) > 0) {
        return row.first();
      }

      const addParamBtn = appPage.getByTestId('qv-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = appPage.getByTestId('qv-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill(paramLower);

      const result = appPage.getByTestId(`qv-add-parameter-result-${paramLower}`).first();
      await expect(result).toBeVisible({ timeout: 10000 });
      await result.click();

      const addedRow = appPage.getByTestId(`qv-param-row-${sectionLower}-${paramLower}`).first();
      await expect(addedRow).toBeVisible({ timeout: 10000 });
      return addedRow;
    };

    const setNumericParam = async (section: string, param: string, value: string) => {
      await ensureParamRow(section, param);
      const input = appPage.getByTestId(`qv-param-input-${section.toLowerCase()}-${param.toLowerCase()}`).first();
      await expect(input).toBeVisible({ timeout: 10000 });
      await input.fill(value);
      await input.press('Tab');
    };

    const setRawParam = async (section: string, param: string, value: string) => {
      const row = await ensureParamRow(section, param);
      const rawToggle = row.locator('.parameter-value-editor__raw-toggle, button[title=\"Edit raw value\"]').first();
      if (await rawToggle.isVisible().catch(() => false)) {
        await rawToggle.click();
      }
      const input = appPage.getByTestId(`qv-param-input-${section.toLowerCase()}-${param.toLowerCase()}`).first();
      await expect(input).toBeVisible({ timeout: 10000 });
      await input.fill(value);
      await input.press('Tab');
      await expect(input).toHaveValue(value);
    };

    const setAutomaticKMesh = async (nk1: number, nk2: number, nk3: number) => {
      const kPointsEditor = appPage.getByTestId('qv-kpoints-editor');
      await expect(kPointsEditor).toBeVisible({ timeout: 10000 });
      await kPointsEditor.scrollIntoViewIfNeeded();

      const modeSelect = appPage.getByTestId('qv-kpoints-mode-select');
      await expect(modeSelect).toBeVisible({ timeout: 5000 });
      await modeSelect.selectOption('automatic');

      const nk1Input = appPage.getByTestId('qv-kpoints-auto-nk1');
      const nk2Input = appPage.getByTestId('qv-kpoints-auto-nk2');
      const nk3Input = appPage.getByTestId('qv-kpoints-auto-nk3');
      await nk1Input.fill(String(nk1));
      await nk2Input.fill(String(nk2));
      await nk3Input.fill(String(nk3));
      await expect(nk1Input).toHaveValue(String(nk1));
      await expect(nk2Input).toHaveValue(String(nk2));
      await expect(nk3Input).toHaveValue(String(nk3));

      const kPointsApply = appPage.getByTestId('qv-kpoints-apply');
      if (await kPointsApply.isVisible().catch(() => false)) {
        if (await kPointsApply.isEnabled().catch(() => false)) {
          await kPointsApply.click();
        }
      }
    };

    // 8) Edit step params to mirror Pair 2 RPC:
    // CONTROL.calculation=vc-relax, CONTROL.nstep=3,
    // SYSTEM.ecutwfc=30, SYSTEM.ecutrho=240, CELL.cell_dofree=all, K_POINTS 2x2x2.
    await appPage.getByTestId('qv-btn-edit-step-params').click();
    await appPage.waitForTimeout(1000);

    await setNumericParam('SYSTEM', 'ecutwfc', '30.0');
    await setNumericParam('SYSTEM', 'ecutrho', '240.0');
    await setRawParam('CONTROL', 'calculation', 'vc-relax');
    await setNumericParam('CONTROL', 'nstep', '3');
    await setRawParam('CELL', 'cell_dofree', 'all');
    await setAutomaticKMesh(2, 2, 2);

    const applyParamsBtn = appPage.getByTestId('qv-btn-apply-step-params');
    await expect(applyParamsBtn).toBeVisible({ timeout: 5000 });
    await applyParamsBtn.click();
    await appPage.waitForTimeout(1000);

    // 9) Run calculation
    const runButtonFocus = appPage.getByTestId('qv-btn-run-calculation-focus');
    const runButtonOverview = appPage.getByTestId('qv-btn-run-calculation');
    if (await runButtonFocus.isVisible().catch(() => false)) {
      await expect(runButtonFocus).toBeEnabled();
      await runButtonFocus.click();
    } else {
      await expect(runButtonOverview).toBeVisible({ timeout: 5000 });
      await expect(runButtonOverview).toBeEnabled();
      await runButtonOverview.click();
    }

    const runLogsTab = appPage.getByTestId('qv-calc-tab-run');
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    const runLogsPanel = appPage.getByTestId('qv-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // 10) Wait for completion
    const statusBadge = runLogsPanel.getByTestId('qv-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

    const startTime = Date.now();
    const timeoutMs = 2.5 * 60 * 1000;
    let completed = false;
    while (Date.now() - startTime < timeoutMs && !completed) {
      const raw = await statusBadge.textContent();
      const status = (raw || '').toLowerCase().replace(/^[^a-z]+/, '').trim();

      if (status.includes('failed')) {
        let errorText = 'Unknown error';
        const errorEl = runLogsPanel.locator('.calculation-run-tab__error');
        if (await errorEl.count() > 0) {
          errorText = (await errorEl.textContent()) || errorText;
        }
        throw new Error(`QE relax calculation failed: ${errorText}`);
      }
      if (status.includes('completed')) {
        completed = true;
        break;
      }
      await appPage.waitForTimeout(2000);
    }
    if (!completed) {
      throw new Error(`Relax job did not complete within ${timeoutMs}ms`);
    }

    // 11) Analysis tab + relax step
    const analysisTab = appPage.getByTestId('qv-calc-tab-analysis');
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qv-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    const relaxStepChip = analysisPanel.locator('[data-testid="qv-analysis-step-tab-relax"]');
    await expect(relaxStepChip).toBeVisible({ timeout: 5000 });
    await relaxStepChip.click();

    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // Ensure real run output, not reference
    const referenceToggle = appPage.getByTestId('qv-analysis-reference-toggle');
    if (await referenceToggle.isVisible().catch(() => false)) {
      if (await referenceToggle.isChecked()) {
        await referenceToggle.uncheck();
      }
      await expect(referenceToggle).not.toBeChecked();
    }
    await expect(appPage.getByTestId('qv-analysis-reference-banner')).toHaveCount(0);

    const loadingIndicator = appPage.getByTestId('qv-analysis-loading');
    const convergenceChart = appPage.getByTestId('qv-analysis-convergence-chart');
    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await convergenceChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading relax analysis...');
      }
    }).toPass({ timeout: 30000 });
    await expect(convergenceChart).toBeVisible({ timeout: 5000 });

    // Convergence plot content
    const convergenceCurves = convergenceChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => convergenceCurves.count(), {
        timeout: 10000,
        message: 'Relax convergence plot has no line curve',
      })
      .toBeGreaterThan(0);
    const nonEmptyConv = await convergenceCurves.evaluateAll((paths) =>
      paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
    );
    expect(nonEmptyConv).toBeGreaterThan(0);

    // 12) Switch analysis object to trajectory and assert plot content
    const trajectoryTile = analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^trajectory$/i });
    await expect(trajectoryTile).toBeVisible({ timeout: 5000 });
    await trajectoryTile.click();

    const trajectoryChart = appPage.getByTestId('qv-analysis-trajectory-chart');
    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await trajectoryChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading trajectory analysis...');
      }
    }).toPass({ timeout: 30000 });
    await expect(trajectoryChart).toBeVisible({ timeout: 5000 });

    const trajectoryCurves = trajectoryChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => trajectoryCurves.count(), {
        timeout: 10000,
        message: 'Trajectory plot has no line curve',
      })
      .toBeGreaterThan(0);
    const nonEmptyTraj = await trajectoryCurves.evaluateAll((paths) =>
      paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
    );
    expect(nonEmptyTraj).toBeGreaterThan(0);

    const frameCounter = appPage.locator('.trajectory-viz__frame-counter');
    await expect(frameCounter).toBeVisible({ timeout: 5000 });
    await expect(frameCounter).toContainText('/');
  });
});
