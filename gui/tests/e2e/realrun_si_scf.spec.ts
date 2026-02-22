/**
 * Pair 1 E2E: Si SCF Real-Run Smoke Test — FROM SCRATCH
 *
 * This is the E2E counterpart of tests/daemon/contract/test_realrun_si_scf.py.
 * Both tests validate the same workflow: create project → import structure →
 * create calculation (engine_family=qe) → configure pseudo → add SCF step →
 * set ecutwfc=20.0 → run QE → verify convergence analysis.
 *
 * The RPC test does it via daemon handle_request calls;
 * this test does it via GUI interactions (Playwright).
 *
 * NO demo projects. Everything from scratch.
 *
 * REQUIRES: QE installed and available.
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/realrun_si_scf.spec.ts --project=electron
 */

import * as path from 'path';
import * as fs from 'fs';
import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { createUniqueProjectDir, clearE2EProjectsRoot, getRepoRoot } from './helpers/paths';
import { waitForHomeWelcome } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Pair 1 E2E: Si SCF Real-Run (from scratch)', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('realrun-si-scf');
  });

  test('from-scratch Si SCF: create project → import structure → create calc → add step → run → verify convergence', async ({ appPage }, testInfo) => {
    // Override timeout to 3 minutes for QE job execution
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);
    const captureStepState = async (name: string) => {
      const screenshotPath = testInfo.outputPath(`${name}.png`);
      await appPage.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(name, { path: screenshotPath, contentType: 'image/png' });
    };

    // Repo root is needed for the structure file path
    const repoRoot = getRepoRoot();
    const siCifFile = path.join(repoRoot, 'tests', 'data', 'structures', 'si_diamond.cif');
    expect(fs.existsSync(siCifFile), `Missing test structure file at ${siCifFile}`).toBeTruthy();

    // =========================================
    // STEP 1: Create new project (from scratch)
    // =========================================
    await waitForHomeWelcome(appPage);

    // Click "Create New Project" on the welcome screen
    const createProjectBtn = appPage.getByTestId('qms-welcome-btn-create-new-project');
    await expect(createProjectBtn).toBeVisible({ timeout: 5000 });
    await createProjectBtn.click();

    // Fill the Create Project dialog
    const parentDirInput = appPage.getByTestId('qms-input-parent-dir');
    await expect(parentDirInput).toBeVisible({ timeout: 5000 });
    await parentDirInput.fill(projectDir);

    const projectNameInput = appPage.getByTestId('qms-input-project-name');
    await projectNameInput.fill('si-scf-e2e');

    // Click "Create Project"
    const confirmCreateBtn = appPage.getByTestId('qms-btn-confirm-create');
    await expect(confirmCreateBtn).toBeEnabled();
    await confirmCreateBtn.click();

    // Wait for project to load
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 15000 });

    // =========================================
    // STEP 2: Import Si structure
    // =========================================
    // Navigate to Structures view
    await navigateToView(appPage, 'structures');

    // Click "Import Structure" button
    const importStructureBtn = appPage.getByTestId('qms-btn-import-structure');
    await expect(importStructureBtn).toBeVisible({ timeout: 5000 });
    await importStructureBtn.click();

    // Fill the Import Structure dialog
    // Type the file path directly into the input (bypass native file picker)
    const fileInput = appPage.getByTestId('qms-import-structure-file');
    await expect(fileInput).toBeVisible({ timeout: 5000 });
    await fileInput.fill(siCifFile);

    const structureNameInput = appPage.getByTestId('qms-import-structure-name');
    await structureNameInput.fill('Si');

    // Click "Import"
    const confirmImportBtn = appPage.getByTestId('qms-btn-confirm-import-structure');
    await expect(confirmImportBtn).toBeEnabled();
    await confirmImportBtn.click();

    // Wait for dialog to close and structure to appear
    await appPage.waitForTimeout(2000);

    // =========================================
    // STEP 3: Create calculation with engine_family=qe
    // =========================================
    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });

    // Click "New Calculation" button
    const newCalcBtn = appPage.getByTestId('qms-btn-new-calculation');
    await expect(newCalcBtn).toBeVisible({ timeout: 5000 });
    await newCalcBtn.click();

    // Fill the Create Calculation dialog
    const calcNameInput = appPage.getByTestId('qms-create-calc-name');
    await expect(calcNameInput).toBeVisible({ timeout: 5000 });
    await calcNameInput.fill('Si SCF Test');

    // Select structure (choose the imported Si structure)
    const structureSelect = appPage.getByTestId('qms-create-calc-structure');
    await expect(structureSelect).toBeVisible();
    // Select the first non-empty option (our imported Si structure)
    const structureOptions = structureSelect.locator('option');
    const optionCount = await structureOptions.count();
    // Find the option that contains "Si"
    for (let i = 0; i < optionCount; i++) {
      const text = await structureOptions.nth(i).textContent();
      if (text && text.includes('Si')) {
        await structureSelect.selectOption({ index: i });
        break;
      }
    }

    // Select engine family = qe
    const engineSelect = appPage.getByTestId('qms-create-calc-engine');
    await expect(engineSelect).toBeVisible();
    // Select QE by finding an option whose value is "qe"
    await engineSelect.selectOption({ value: 'qe' });

    // Click "Create Calculation"
    const confirmCreateCalcBtn = appPage.getByTestId('qms-btn-confirm-create-calc');
    await expect(confirmCreateCalcBtn).toBeEnabled();
    await confirmCreateCalcBtn.click();

    // Wait for calculation to appear in the list
    await appPage.waitForTimeout(2000);

    // =========================================
    // STEP 4: Select the calculation
    // =========================================
    const calcRow = appPage.getByTestId('qms-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();

    // Wait for Overview & Steps tab to be active
    const overviewTab = appPage.getByTestId('qms-calc-tab-overview');
    await expect(overviewTab).toBeVisible({ timeout: 5000 });
    await expect(overviewTab).toHaveClass(/calculations-workspace-tab--active/);

    // Wait for overview panel to be fully loaded
    const overviewPanel = appPage.getByTestId('qms-calc-overview-panel');
    await expect(overviewPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    // =========================================
    // STEP 5: Configure pseudopotential for Si
    // =========================================
    // Click "Edit" button on the pseudo section
    const editPseudoBtn = appPage.getByTestId('qms-btn-edit-pseudos');
    // Wait for pseudos section to load (may take a moment)
    await expect(editPseudoBtn).toBeVisible({ timeout: 10000 });
    await editPseudoBtn.click();

    // The pseudo edit modal should appear with Si element dropdown
    const pseudoSelectSi = appPage.getByTestId('qms-pseudo-select-Si');
    await expect(pseudoSelectSi).toBeVisible({ timeout: 10000 });

    // Select a pseudo for Si
    // The internal library should have Si.pbe-n-rrkjus_psl.1.0.0.UPF
    // Assert options are populated first, so failures are explicit (not silent hangs)
    const pseudoOptions = pseudoSelectSi.locator('option');
    await expect
      .poll(async () => pseudoOptions.count(), {
        timeout: 15000,
        message: 'Pseudo dropdown did not populate for Si',
      })
      .toBeGreaterThan(1);

    const currentPseudoValue = await pseudoSelectSi.inputValue();
    if (!currentPseudoValue) {
      // If no pseudo is selected, pick first concrete option.
      // This may trigger backend write and close modal automatically.
      await pseudoSelectSi.selectOption({ index: 1 });
    }

    const pseudoOverlay = appPage.locator('.pseudo-edit-modal-overlay');
    // Handle both UI behaviors:
    // 1) modal stays open until user clicks Apply
    // 2) selection auto-persists and modal closes/re-renders immediately
    if (await pseudoOverlay.isVisible().catch(() => false)) {
      const pseudoApplyBtn = appPage.getByTestId('qms-pseudo-apply');
      if (await pseudoApplyBtn.isVisible().catch(() => false)) {
        await pseudoApplyBtn.click({ timeout: 3000 }).catch(() => {
          // Ignore stale-click races; we'll confirm closure below.
        });
      }

      if (await pseudoOverlay.isVisible().catch(() => false)) {
        const pseudoModalClose = appPage.locator('.pseudo-edit-modal-close');
        if (await pseudoModalClose.isVisible().catch(() => false)) {
          await pseudoModalClose.click({ timeout: 3000 }).catch(() => {
            // Ignore; final hidden assertion is authoritative.
          });
        }
      }
    }

    await expect(pseudoOverlay).toBeHidden({ timeout: 15000 });
    const siPseudoItem = appPage.locator('.pseudo-list__item', { hasText: /^Si:/ }).first();
    await expect(siPseudoItem).toBeVisible({ timeout: 10000 });
    await expect(siPseudoItem).not.toContainText(/missing/i);
    console.log('[realrun_si_scf] pseudo modal closed');

    // =========================================
    // STEP 6: Add SCF step
    // =========================================
    try {
      const addStepBtn = appPage.getByTestId('qms-add-step-btn');
      await expect(addStepBtn).toBeVisible({ timeout: 5000 });
      await addStepBtn.scrollIntoViewIfNeeded();
      console.log('[realrun_si_scf] clicking add step');
      await addStepBtn.click({ timeout: 5000 });

      // Wait for add step form
      const addStepForm = appPage.getByTestId('qms-add-step-form');
      await expect(addStepForm).toBeVisible({ timeout: 5000 });
      console.log('[realrun_si_scf] add step form visible');

      // Select "scf" step type
      const stepTypeSelect = appPage.getByTestId('qms-add-step-type-select');
      await expect(stepTypeSelect).toBeVisible();

      // Fail fast if step palette is empty, instead of hanging on selectOption()
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
      expect(stepTypeValues).toContain('scf');
      console.log('[realrun_si_scf] step palette loaded');

      // Select by value "scf" (step_type_gen values are lowercase)
      await stepTypeSelect.selectOption({ value: 'scf' });

      // Click "Add Step"
      const confirmAddStepBtn = appPage.getByTestId('qms-confirm-add-step');
      await expect(confirmAddStepBtn).toBeEnabled();
      await confirmAddStepBtn.click({ timeout: 5000 });
      console.log('[realrun_si_scf] add step submitted');

      // Wait for step to appear in the list (fail fast if add-step did not actually apply)
      const stepRows = appPage.locator('[data-testid^="qms-step-row-"]');
      await expect
        .poll(async () => stepRows.count(), {
          timeout: 15000,
          message: 'Step was not added after clicking Add Step',
        })
        .toBeGreaterThan(0);
      console.log('[realrun_si_scf] step row detected');
    } catch (e) {
      await captureStepState('add-step-failure');
      throw e;
    }

    // =========================================
    // STEP 7: Click on the step to view details
    // =========================================
    // The step row should appear in the steps list
    const stepsContainer = appPage.getByTestId('qms-steps-list');
    await expect(stepsContainer).toBeVisible({ timeout: 5000 });

    // Click the first step button to view its details
    const stepButton = stepsContainer.locator('[data-testid^="qms-step-button-"]').first();
    await expect(stepButton).toBeVisible({ timeout: 5000 });
    await stepButton.click();

    // Wait for step detail panel to load
    const stepDetail = appPage.getByTestId('qms-step-detail');
    await expect(stepDetail).toBeVisible({ timeout: 10000 });

    // =========================================
    // STEP 8: Set ecutwfc=20.0 (matching RPC test)
    // =========================================
    // Click "Edit" to enter editing mode
    const editParamsBtn = appPage.getByTestId('qms-btn-edit-step-params');
    await expect(editParamsBtn).toBeVisible({ timeout: 5000 });
    await editParamsBtn.click();

    // Wait for editing mode to activate
    await appPage.waitForTimeout(1000);

    // Find the ecutwfc parameter input and set it to 20.0
    const ecutwfcInput = appPage.getByTestId('qms-param-input-system-ecutwfc');
    await expect(ecutwfcInput).toBeVisible({ timeout: 5000 });
    await ecutwfcInput.fill('20.0');
    await ecutwfcInput.press('Tab');

    // Click "Apply" to save parameters
    const applyParamsBtn = appPage.getByTestId('qms-btn-apply-step-params');
    await expect(applyParamsBtn).toBeVisible({ timeout: 5000 });
    await applyParamsBtn.click();

    // Wait for save to complete
    await appPage.waitForTimeout(1000);

    // =========================================
    // STEP 9: Run calculation
    // =========================================
    // In Step Focus mode, the run button is rendered in the compact step list.
    // In Overview mode, use the standard calculation header run button.
    const runButtonFocus = appPage.getByTestId('qms-btn-run-calculation-focus');
    const runButtonOverview = appPage.getByTestId('qms-btn-run-calculation');
    if (await runButtonFocus.isVisible().catch(() => false)) {
      await expect(runButtonFocus).toBeEnabled();
      await runButtonFocus.click();
    } else {
      await expect(runButtonOverview).toBeVisible({ timeout: 5000 });
      await expect(runButtonOverview).toBeEnabled();
      await runButtonOverview.click();
    }

    // Verify auto-switch to Run & Logs tab
    const runLogsTab = appPage.getByTestId('qms-calc-tab-run');
    await expect(runLogsTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });
    const runLogsPanel = appPage.getByTestId('qms-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // =========================================
    // STEP 10: Wait for job completion
    // =========================================
    const statusBadge = runLogsPanel.getByTestId('qms-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

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
    const jobLogs = runLogsPanel.getByTestId('qms-calc-job-logs');
    await expect(jobLogs).toBeVisible();

    // =========================================
    // STEP 11: Switch to Analysis tab
    // =========================================
    const analysisTab = appPage.getByTestId('qms-calc-tab-analysis');
    await expect(analysisTab).toBeVisible({ timeout: 5000 });
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qms-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(2000);

    // =========================================
    // STEP 12: Verify convergence analysis
    // =========================================
    // Select SCF step chip explicitly
    const scfStepChip = analysisPanel.locator('[data-testid="qms-analysis-step-tab-scf"]');
    await expect(scfStepChip).toBeVisible({ timeout: 5000 });
    await scfStepChip.click();

    // Click Plot tab explicitly
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // Ensure we're validating run output (not reference overlay)
    const referenceToggle = appPage.getByTestId('qms-analysis-reference-toggle');
    if (await referenceToggle.isVisible().catch(() => false)) {
      if (await referenceToggle.isChecked()) {
        await referenceToggle.uncheck();
      }
      await expect(referenceToggle).not.toBeChecked();
    }
    await expect(appPage.getByTestId('qms-analysis-reference-banner')).toHaveCount(0);

    // Wait for loading to finish
    const loadingIndicator = appPage.getByTestId('qms-analysis-loading');
    const convergenceChart = appPage.getByTestId('qms-analysis-convergence-chart');

    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await convergenceChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading analysis...');
      }
    }).toPass({ timeout: 30000 });

    // Verify convergence plot exists
    await expect(convergenceChart).toBeVisible({ timeout: 5000 });

    // Assert chart has rendered SVG + non-empty data curve(s) + axis ticks
    const chartSvg = convergenceChart.locator('.recharts-wrapper > .recharts-surface').first();
    await expect(chartSvg).toBeVisible({ timeout: 5000 });

    const curvePaths = convergenceChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => curvePaths.count(), {
        timeout: 10000,
        message: 'Convergence plot has no rendered line curve',
      })
      .toBeGreaterThan(0);

    const nonEmptyCurveCount = await curvePaths.evaluateAll((paths) =>
      paths.filter((p) => {
        const d = (p as SVGPathElement).getAttribute('d') || '';
        return d.length > 20;
      }).length,
    );
    expect(nonEmptyCurveCount).toBeGreaterThan(0);

    const xAxisTicks = convergenceChart.locator(
      '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value, .recharts-xAxis .recharts-cartesian-axis-tick-value',
    );
    await expect
      .poll(async () => xAxisTicks.count(), {
        timeout: 10000,
        message: 'Convergence plot x-axis ticks did not render',
      })
      .toBeGreaterThan(1);

    // Verify convergence info bar
    const convergenceInfo = appPage.getByTestId('qms-analysis-convergence-info');
    await expect(convergenceInfo).toBeVisible({ timeout: 5000 });

    // Convergence badge should show "Converged"
    const convergedBadge = convergenceInfo.locator('.analysis-viz__convergence-badge');
    await expect(convergedBadge).toBeVisible({ timeout: 5000 });
    const badgeText = await convergedBadge.textContent();
    expect(badgeText).toMatch(/[Cc]onverged/);
  });
});
