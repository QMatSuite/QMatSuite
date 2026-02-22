/**
 * Pair 3 E2E: Si Bands Real-Run Smoke Test — FROM SCRATCH
 *
 * Workflow:
 * create project -> import Si CIF -> create QE calculation ->
 * set pseudo mapping -> add steps (scf,nscf,bandspw,bands) ->
 * set practical parameters -> run QE ->
 * verify non-empty bands analysis plot.
 */

import * as fs from 'fs';
import * as path from 'path';
import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { clearE2EProjectsRoot, createUniqueProjectDir, getRepoRoot } from './helpers/paths';
import { waitForHomeWelcome } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Pair 3 E2E: Si Bands Real-Run (from scratch)', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('realrun-si-bands');
  });

  test('from-scratch Si bands workflow with non-empty bands plot', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    const captureStepState = async (name: string) => {
      const screenshotPath = testInfo.outputPath(`${name}.png`);
      await appPage.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(name, { path: screenshotPath, contentType: 'image/png' });
    };

    const repoRoot = getRepoRoot();
    const siCif = path.join(repoRoot, 'tests', 'data', 'structures', 'si_diamond.cif');
    expect(fs.existsSync(siCif), `Missing structure file at ${siCif}`).toBeTruthy();

    // 1) Create project
    await waitForHomeWelcome(appPage);
    await appPage.getByTestId('qms-welcome-btn-create-new-project').click();
    await appPage.getByTestId('qms-input-parent-dir').fill(projectDir);
    await appPage.getByTestId('qms-input-project-name').fill('si-bands-e2e');
    await appPage.getByTestId('qms-btn-confirm-create').click();
    await expect(appPage.getByTestId('qms-home-project')).toBeVisible({ timeout: 15000 });

    // 2) Import Si structure (local CIF)
    await navigateToView(appPage, 'structures');
    await appPage.getByTestId('qms-btn-import-structure').click();
    await appPage.getByTestId('qms-import-structure-file').fill(siCif);
    await appPage.getByTestId('qms-import-structure-name').fill('Si');
    await appPage.getByTestId('qms-btn-confirm-import-structure').click();
    await appPage.waitForTimeout(2000);

    // 3) Create QE calculation
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });
    await appPage.getByTestId('qms-btn-new-calculation').click();
    await appPage.getByTestId('qms-create-calc-name').fill('Si Bands Test');

    const structureSelect = appPage.getByTestId('qms-create-calc-structure');
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

    await appPage.getByTestId('qms-create-calc-engine').selectOption({ value: 'qe' });
    await appPage.getByTestId('qms-btn-confirm-create-calc').click();
    await appPage.waitForTimeout(2000);

    // 4) Select calculation
    const calcRow = appPage.getByTestId('qms-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();
    await expect(appPage.getByTestId('qms-calc-tab-overview')).toHaveClass(/calculations-workspace-tab--active/);
    await expect(appPage.getByTestId('qms-calc-overview-panel')).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(1000);

    // 5) Configure pseudo mapping
    const editPseudoBtn = appPage.getByTestId('qms-btn-edit-pseudos');
    await expect(editPseudoBtn).toBeVisible({ timeout: 10000 });
    await editPseudoBtn.click();

    const pseudoSelectSi = appPage.getByTestId('qms-pseudo-select-Si');
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
      const pseudoApplyBtn = appPage.getByTestId('qms-pseudo-apply');
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

    const addStep = async (stepType: string) => {
      const stepRows = appPage.locator('.step-item-container');
      const beforeCount = await stepRows.count();

      const addStepBtn = appPage.getByTestId('qms-add-step-btn');
      await expect(addStepBtn).toBeVisible({ timeout: 5000 });
      await addStepBtn.scrollIntoViewIfNeeded();
      await addStepBtn.click({ timeout: 5000 });

      const addStepForm = appPage.getByTestId('qms-add-step-form');
      await expect(addStepForm).toBeVisible({ timeout: 5000 });

      const stepTypeSelect = appPage.getByTestId('qms-add-step-type-select');
      const stepTypeOptions = stepTypeSelect.locator('option');
      await expect
        .poll(async () => stepTypeOptions.count(), {
          timeout: 15000,
          message: 'Add-step dropdown is empty',
        })
        .toBeGreaterThan(1);

      const stepTypeValues = await stepTypeOptions.evaluateAll((options) =>
        options.map((opt) => (opt as HTMLOptionElement).value),
      );
      expect(stepTypeValues).toContain(stepType);

      await stepTypeSelect.selectOption({ value: stepType });
      const confirmAddStepBtn = appPage.getByTestId('qms-confirm-add-step');
      await expect(confirmAddStepBtn).toBeEnabled();
      await confirmAddStepBtn.click({ timeout: 5000 });

      await expect
        .poll(async () => stepRows.count(), {
          timeout: 15000,
          message: `Step ${stepType} was not added`,
        })
        .toBe(beforeCount + 1);
    };

    // 6) Add workflow steps: scf -> nscf -> bandspw -> bands
    try {
      await addStep('scf');
      await addStep('nscf');
      await addStep('bandspw');
      await addStep('bands');
    } catch (e) {
      await captureStepState('add-steps-failure-bands');
      throw e;
    }

    const normalizeStepType = (value: string) => value.toLowerCase().replace(/[_\s-]/g, '');
    const buildStepRegex = (stepType: string) => {
      if (stepType === 'bandspw') {
        return /\bbands?_?pw\b/i;
      }
      return new RegExp(`\\b${stepType}\\b`, 'i');
    };
    const currentStepPanel = () => appPage.locator('.step-detail-panel:visible').first();

    const enterFocusModeForStep = async (stepType: string) => {
      const focusTab = appPage.getByTestId('qms-calc-overview-tab-focus');
      if (await focusTab.isVisible().catch(() => false)) {
        return;
      }

      const targetPattern = buildStepRegex(stepType);
      const overviewStepButtons = appPage.locator('[data-testid^="qms-step-button-"]');
      await expect
        .poll(async () => overviewStepButtons.count(), {
          timeout: 15000,
          message: 'Overview step buttons were not rendered',
        })
        .toBeGreaterThan(0);

      // Prefer the requested step; fallback to the first visible step button
      // to force entry into focus mode when text filtering is brittle.
      let overviewStep = overviewStepButtons.filter({ hasText: targetPattern }).first();
      if (!(await overviewStep.isVisible().catch(() => false))) {
        overviewStep = overviewStepButtons.first();
      }
      await expect(overviewStep).toBeVisible({ timeout: 15000 });

      for (let attempt = 0; attempt < 6; attempt += 1) {
        await overviewStep.scrollIntoViewIfNeeded().catch(() => {});
        await overviewStep.click({ force: true });
        if (await focusTab.isVisible().catch(() => false)) {
          return;
        }
        await appPage.waitForTimeout(400);
      }

      throw new Error(`Failed to enter focus mode using step ${stepType}`);
    };

    const openStepByType = async (stepType: string) => {
      const targetPattern = buildStepRegex(stepType);
      const expectedStepOrder: Record<string, number> = {
        scf: 0,
        nscf: 1,
        bandspw: 2,
        bands: 3,
      };
      const waitForDetailStepType = async (expectedStepType: string, timeoutMs = 12000) => {
        try {
          const expected = normalizeStepType(expectedStepType);
          await expect
            .poll(async () => {
              const stepTypeValue = currentStepPanel().getByTestId('qms-step-type-value');
              if (!(await stepTypeValue.isVisible().catch(() => false))) {
                return '';
              }
              return normalizeStepType((await stepTypeValue.textContent()) || '');
            }, { timeout: timeoutMs })
            .toBe(expected);
          return true;
        } catch {
          return false;
        }
      };
      await enterFocusModeForStep(stepType);

      for (let attempt = 0; attempt < 6; attempt += 1) {
        if (!(await appPage.getByTestId('qms-calc-overview-tab-focus').isVisible().catch(() => false))) {
          await enterFocusModeForStep(stepType);
        }

        const focusContainer = appPage.getByTestId('qms-calc-overview-tab-focus');
        await expect(focusContainer).toBeVisible({ timeout: 15000 });
        const focusSteps = focusContainer.locator('.compact-step-list__step-item');
        await expect
          .poll(async () => focusSteps.count(), {
            timeout: 10000,
            message: 'Focus-mode step list is empty',
          })
          .toBeGreaterThan(0);

        // If detail already shows target step, avoid extra clicks.
        if (await waitForDetailStepType(stepType, 3000)) {
          return;
        }

        // Guard for selected compact-list item: avoid clicking it (would exit focus mode),
        // but require the detail panel to actually match before returning.
        const selectedFocusStep = focusContainer.locator('.compact-step-list__step-item--selected').first();
        if (await selectedFocusStep.isVisible().catch(() => false)) {
          const selectedText = normalizeStepType((await selectedFocusStep.textContent()) || '');
          if (selectedText.includes(normalizeStepType(stepType))) {
            if (await waitForDetailStepType(stepType, 5000)) {
              return;
            }
            // Detail panel is stale; click another step first to force refresh cycle.
            const total = await focusSteps.count();
            if (total > 1) {
              const targetIdx = expectedStepOrder[stepType] ?? 0;
              const alternateIdx = (targetIdx + 1) % total;
              const alternateStep = focusSteps.nth(alternateIdx);
              await alternateStep.scrollIntoViewIfNeeded();
              await alternateStep.click();
              await appPage.waitForTimeout(300);
            }
          }
        }

        let focusStep = focusContainer
          .locator('.compact-step-list__step-item')
          .filter({ hasText: targetPattern })
          .first();
        if (!(await focusStep.isVisible().catch(() => false))) {
          const fallbackIndex = expectedStepOrder[stepType] ?? 0;
          focusStep = focusSteps.nth(fallbackIndex);
        }
        await expect(focusStep).toBeVisible({ timeout: 10000 });
        await focusStep.scrollIntoViewIfNeeded();
        await focusStep.click();

        if (await waitForDetailStepType(stepType, 12000)) {
          return;
        }
        await appPage.waitForTimeout(400);
      }

      throw new Error(`Failed to open step ${stepType}: selection did not change`);
    };

    const applyStepParams = async () => {
      const applyParamsBtn = currentStepPanel().getByTestId('qms-btn-apply-step-params');
      await expect(applyParamsBtn).toBeVisible({ timeout: 5000 });

      // Avoid flake when the panel is auto-saving from blur/change events.
      await expect
        .poll(async () => ((await applyParamsBtn.textContent()) || '').toLowerCase(), {
          timeout: 20000,
          message: 'Step params stayed in Saving... state for too long',
        })
        .not.toContain('saving');

      if (await applyParamsBtn.isEnabled()) {
        await applyParamsBtn.click();
      }

      await expect(applyParamsBtn).toBeDisabled({ timeout: 10000 });
    };

    const ensureEditMode = async () => {
      const applyParamsBtn = currentStepPanel().getByTestId('qms-btn-apply-step-params');
      if (await applyParamsBtn.isVisible().catch(() => false)) {
        return;
      }
      const editParamsBtn = currentStepPanel().getByTestId('qms-btn-edit-step-params');
      await expect(editParamsBtn).toBeVisible({ timeout: 10000 });
      await editParamsBtn.click();
      await expect(applyParamsBtn).toBeVisible({ timeout: 10000 });
    };

    const ensureKPointsEditorVisible = async () => {
      const panel = currentStepPanel();
      const panelContent = panel.locator('.panel-content').first();
      const kPointsEditor = panel.getByTestId('qms-kpoints-editor');
      const kPointsLoading = panel.getByTestId('qms-kpoints-loading');
      const stepTypeValue = panel.getByTestId('qms-step-type-value');

      const start = Date.now();
      const mountTimeoutMs = 15000;
      while (Date.now() - start < mountTimeoutMs) {
        const editorCount = await kPointsEditor.count();
        if (editorCount > 0) {
          break;
        }

        // During card fetch, StepDetailPanel renders a dedicated loading placeholder.
        // Wait through that state before declaring the editor absent.
        const loadingVisible = await kPointsLoading.isVisible().catch(() => false);
        if (!loadingVisible && Date.now() - start > 3000) {
          break;
        }
        await appPage.waitForTimeout(200);
      }

      if ((await kPointsEditor.count()) === 0) {
        const stepTypeText = (await stepTypeValue.textContent().catch(() => '')) || 'unknown';
        const loadingVisible = await kPointsLoading.isVisible().catch(() => false);
        throw new Error(
          `K_POINTS editor missing for step=${stepTypeText.trim() || 'unknown'} loading=${String(loadingVisible)}`,
        );
      }

      // Ensure the mounted editor is actually visible/actionable in the scroll container.
      for (const ratio of [0, 0.2, 0.4, 0.6, 0.8, 1]) {
        await panelContent.evaluate((el, r) => {
          const node = el as HTMLElement;
          node.scrollTop = Math.floor(node.scrollHeight * r);
        }, ratio);
        const visible = await kPointsEditor.isVisible().catch(() => false);
        if (visible) {
          return kPointsEditor;
        }
        await appPage.waitForTimeout(150);
      }

      // As a final attempt, request native scroll to element.
      await kPointsEditor.scrollIntoViewIfNeeded().catch(() => {});
      if (await kPointsEditor.isVisible().catch(() => false)) {
        return kPointsEditor;
      }

      throw new Error('K_POINTS editor is mounted but not visible/actionable in the step panel');
    };

    const setAutomaticKMesh = async (nk1: number, nk2: number, nk3: number) => {
      const panel = currentStepPanel();
      await ensureKPointsEditorVisible();

      const modeSelect = panel.getByTestId('qms-kpoints-mode-select');
      await expect(modeSelect).toBeVisible({ timeout: 5000 });
      await modeSelect.selectOption('automatic');

      const nk1Input = panel.getByTestId('qms-kpoints-auto-nk1');
      const nk2Input = panel.getByTestId('qms-kpoints-auto-nk2');
      const nk3Input = panel.getByTestId('qms-kpoints-auto-nk3');
      await nk1Input.fill(String(nk1));
      await nk2Input.fill(String(nk2));
      await nk3Input.fill(String(nk3));

      await expect(nk1Input).toHaveValue(String(nk1));
      await expect(nk2Input).toHaveValue(String(nk2));
      await expect(nk3Input).toHaveValue(String(nk3));
    };

    const fillKPointRow = async (
      row: number,
      values: { x: number; y: number; z: number; w: number },
    ) => {
      const panel = currentStepPanel();
      await panel.getByTestId(`qms-kpoints-point-${row}-x`).fill(String(values.x));
      await panel.getByTestId(`qms-kpoints-point-${row}-y`).fill(String(values.y));
      await panel.getByTestId(`qms-kpoints-point-${row}-z`).fill(String(values.z));
      await panel.getByTestId(`qms-kpoints-point-${row}-w`).fill(String(values.w));
    };

    const setCrystalBKPath = async () => {
      const panel = currentStepPanel();
      await ensureKPointsEditorVisible();

      const modeSelect = panel.getByTestId('qms-kpoints-mode-select');
      await expect(modeSelect).toBeVisible({ timeout: 5000 });
      await modeSelect.selectOption('crystal_b');

      // First row appears when switching to list mode; add remaining 4 rows.
      const addPointBtn = panel.getByTestId('qms-kpoints-add-point');
      await expect(addPointBtn).toBeVisible({ timeout: 5000 });
      for (let i = 0; i < 4; i += 1) {
        await addPointBtn.click();
      }

      await fillKPointRow(0, { x: 0.0, y: 0.5, z: 0.0, w: 6 });
      await fillKPointRow(1, { x: 0.0, y: 0.0, z: 0.0, w: 8 });
      await fillKPointRow(2, { x: -0.5, y: 0.0, z: -0.5, w: 4 });
      await fillKPointRow(3, { x: -0.375, y: 0.25, z: -0.375, w: 8 });
      await fillKPointRow(4, { x: 0.0, y: 0.0, z: 0.0, w: 0 });

      await expect(panel.getByTestId('qms-kpoints-point-4-x')).toHaveValue('0');
      await expect(panel.getByTestId('qms-kpoints-point-4-w')).toHaveValue('0');
    };

    // 7) Set parameters per step including K_POINTS edits
    await openStepByType('scf');
    await ensureEditMode();
    const scfEcut = appPage.getByTestId('qms-param-input-system-ecutwfc');
    await expect(scfEcut).toBeVisible({ timeout: 5000 });
    await scfEcut.fill('30.0');
    await scfEcut.press('Tab');
    await setAutomaticKMesh(2, 2, 2);
    await applyStepParams();

    await openStepByType('nscf');
    await ensureEditMode();
    const nscfEcut = appPage.getByTestId('qms-param-input-system-ecutwfc');
    await expect(nscfEcut).toBeVisible({ timeout: 5000 });
    await nscfEcut.fill('30.0');
    await nscfEcut.press('Tab');
    await setAutomaticKMesh(4, 4, 4);
    await applyStepParams();

    await openStepByType('bandspw');
    await ensureEditMode();
    const bandspwEcut = appPage.getByTestId('qms-param-input-system-ecutwfc');
    await expect(bandspwEcut).toBeVisible({ timeout: 5000 });
    await bandspwEcut.fill('30.0');
    await bandspwEcut.press('Tab');
    await setCrystalBKPath();
    await applyStepParams();

    // bands step: set filband so bands.x emits *.bands.dat.gnu evidence.
    await openStepByType('bands');
    await ensureEditMode();

    const panelContent = appPage.locator('.step-detail-panel .panel-content').first();
    await panelContent.evaluate((el) => {
      (el as HTMLElement).scrollTop = (el as HTMLElement).scrollHeight;
    });

    let filbandInput = appPage.getByTestId('qms-param-input-bands-filband');
    if ((await filbandInput.count()) === 0) {
      const addParamBtn = appPage.getByTestId('qms-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = appPage.getByTestId('qms-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill('filband');

      const filbandResult = appPage.getByTestId('qms-add-parameter-result-filband').first();
      await expect(filbandResult).toBeVisible({ timeout: 10000 });
      await filbandResult.click();
    }

    filbandInput = appPage.getByTestId('qms-param-input-bands-filband');
    await expect(filbandInput).toBeVisible({ timeout: 10000 });
    await filbandInput.scrollIntoViewIfNeeded();
    await filbandInput.fill('bands.dat');
    await filbandInput.press('Tab');
    await applyStepParams();

    // 8) Run calculation
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

    const runLogsPanel = appPage.getByTestId('qms-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // 9) Wait for completion
    const statusBadge = runLogsPanel.getByTestId('qms-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

    const parseJobStatus = (raw: string | null): string => {
      const lowered = (raw || '').toLowerCase();
      const match = lowered.match(/\b(pending|running|completed|failed|cancelled)\b/);
      return match?.[1] || '';
    };

    const startTime = Date.now();
    const timeoutMs = 3 * 60 * 1000;
    let completed = false;
    let sawActiveState = false;
    while (Date.now() - startTime < timeoutMs && !completed) {
      const raw = await statusBadge.textContent();
      const status = parseJobStatus(raw);

      if (status === 'pending' || status === 'running') {
        sawActiveState = true;
      }

      if (status === 'failed' || status === 'cancelled') {
        let errorText = 'Unknown error';
        const errorEl = runLogsPanel.locator('.calculation-run-tab__error');
        if (await errorEl.count() > 0) {
          errorText = (await errorEl.textContent()) || errorText;
        }
        throw new Error(`QE bands calculation failed: ${errorText}`);
      }

      // Guard against stale "completed" from a previous run: only accept terminal
      // completion after this test has observed an active run state.
      if (status === 'completed' && sawActiveState) {
        completed = true;
        break;
      }

      await appPage.waitForTimeout(2000);
    }
    if (!completed) {
      throw new Error(`Bands job did not complete within ${timeoutMs}ms`);
    }

    // 10) Analysis tab, select step that exposes bands object
    const analysisTab = appPage.getByTestId('qms-calc-tab-analysis');
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qms-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });

    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    // Ensure real run output, not reference
    const referenceToggle = appPage.getByTestId('qms-analysis-reference-toggle');
    if (await referenceToggle.isVisible().catch(() => false)) {
      if (await referenceToggle.isChecked()) {
        await referenceToggle.uncheck();
      }
      await expect(referenceToggle).not.toBeChecked();
    }
    await expect(appPage.getByTestId('qms-analysis-reference-banner')).toHaveCount(0);

    // 10a) Explicitly validate SCF convergence plot in this multi-step workflow.
    const scfStepChip = analysisPanel.locator('[data-testid="qms-analysis-step-tab-scf"]');
    await expect(scfStepChip).toBeVisible({ timeout: 10000 });
    await scfStepChip.click();
    await expect(scfStepChip).toHaveClass(/--active/, { timeout: 5000 });

    const waitForConvergenceState = async (timeoutMs: number): Promise<'chart' | 'tile' | 'none' | 'timeout'> => {
      const start = Date.now();
      while (Date.now() - start < timeoutMs) {
        const loadingVisible = await analysisPanel.getByTestId('qms-analysis-loading').isVisible().catch(() => false);
        const digestLoading = await analysisPanel
          .locator('.analysis-digest.analysis-surface__placeholder')
          .filter({ hasText: /Loading step digest/i })
          .isVisible()
          .catch(() => false);
        if (loadingVisible || digestLoading) {
          await appPage.waitForTimeout(250);
          continue;
        }
        if (await analysisPanel.getByTestId('qms-analysis-convergence-chart').isVisible().catch(() => false)) {
          return 'chart';
        }
        if (await analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^convergence$/i }).first().isVisible().catch(() => false)) {
          return 'tile';
        }
        if (await analysisPanel.getByTestId('qms-analysis-no-objects').isVisible().catch(() => false)) {
          return 'none';
        }
        await appPage.waitForTimeout(250);
      }
      return 'timeout';
    };

    let convergenceState = await waitForConvergenceState(20000);
    if (convergenceState === 'tile') {
      const convergenceTile = analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^convergence$/i }).first();
      await convergenceTile.click();
      convergenceState = await waitForConvergenceState(10000);
    }
    expect(convergenceState, 'SCF convergence analysis state timed out').not.toBe('timeout');

    if (convergenceState === 'chart') {
      const convergenceChart = analysisPanel.getByTestId('qms-analysis-convergence-chart');
      await expect(convergenceChart).toBeVisible({ timeout: 10000 });
      await convergenceChart.scrollIntoViewIfNeeded();
      await appPage.waitForTimeout(250);

      const convergenceCurves = convergenceChart.locator(
        '.recharts-line .recharts-line-curve, .recharts-area .recharts-area-curve, .recharts-line-curve, .recharts-area-curve',
      );
      await expect
        .poll(async () => convergenceCurves.count(), {
          timeout: 10000,
          message: 'SCF convergence chart has no curve paths',
        })
        .toBeGreaterThan(0);
      const nonEmptyConvergenceCurves = await convergenceCurves.evaluateAll((paths) =>
        paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
      );
      expect(nonEmptyConvergenceCurves).toBeGreaterThan(0);
      const convergenceTicks = convergenceChart.locator(
        '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value',
      );
      await expect
        .poll(async () => convergenceTicks.count(), {
          timeout: 10000,
          message: 'SCF convergence x-axis ticks did not render',
        })
        .toBeGreaterThan(1);
    } else {
      // Some valid QE bands workflows expose SCF convergence in digest only.
      await expect(analysisPanel.getByTestId('qms-analysis-no-objects')).toBeVisible({ timeout: 10000 });
      const digestTextRaw = await analysisPanel.locator('.analysis-digest').innerText();
      const digestText = digestTextRaw.replace(/\s+/g, ' ').toLowerCase();
      expect(digestText).toContain('n_iterations');
      expect(digestText).toContain('converged');
      expect(digestText).toContain('total_energy_ry');
      const nIterMatch = digestText.match(/n_iterations\s+([0-9]+)/);
      expect(nIterMatch).not.toBeNull();
      const nIter = Number(nIterMatch?.[1] || '0');
      expect(nIter).toBeGreaterThan(1);
      expect(digestText).toMatch(/converged\s+true/);
      expect(digestText).toMatch(/total_energy_ry\s+-[0-9.]+/);
    }

    const waitForBandsState = async (timeoutMs: number): Promise<'chart' | 'tile' | 'none' | 'timeout'> => {
      const start = Date.now();
      let noObjectsSince: number | null = null;
      while (Date.now() - start < timeoutMs) {
        const loadingVisible = await analysisPanel.getByTestId('qms-analysis-loading').isVisible().catch(() => false);
        const digestLoading = await analysisPanel
          .locator('.analysis-digest.analysis-surface__placeholder')
          .filter({ hasText: /Loading step digest/i })
          .isVisible()
          .catch(() => false);
        if (loadingVisible || digestLoading) {
          noObjectsSince = null;
          await appPage.waitForTimeout(250);
          continue;
        }
        const chartVisible = await analysisPanel.getByTestId('qms-analysis-bands-chart').isVisible().catch(() => false);
        if (chartVisible) {
          return 'chart';
        }
        const bandsTileVisible = await analysisPanel
          .locator('.analysis-viz__tile')
          .filter({ hasText: /^bands$/i })
          .first()
          .isVisible()
          .catch(() => false);
        if (bandsTileVisible) {
          return 'tile';
        }
        const noneVisible = await analysisPanel.getByTestId('qms-analysis-no-objects').isVisible().catch(() => false);
        if (noneVisible) {
          if (noObjectsSince === null) {
            noObjectsSince = Date.now();
          }
          if (Date.now() - noObjectsSince >= 10000) {
            return 'none';
          }
        } else {
          noObjectsSince = null;
        }
        await appPage.waitForTimeout(250);
      }
      return 'timeout';
    };

    const candidateStepTabs = ['bandspw', 'bands', 'nscf', 'scf'] as const;
    let selectedStepTab: (typeof candidateStepTabs)[number] | null = null;
    for (const stepTab of candidateStepTabs) {
      const stepChip = analysisPanel.locator(`[data-testid="qms-analysis-step-tab-${stepTab}"]`);
      if (!(await stepChip.isVisible().catch(() => false))) {
        continue;
      }

      await stepChip.click();
      await expect(stepChip).toHaveClass(/--active/, { timeout: 5000 });
      let state = await waitForBandsState(20000);
      if (state === 'tile') {
        const bandsTile = analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^bands$/i }).first();
        await bandsTile.click();
        state = await waitForBandsState(10000);
      }
      if (state === 'chart') {
        selectedStepTab = stepTab;
        break;
      }
    }

    expect(selectedStepTab, 'No renderable bands chart found in analysis for any candidate step').not.toBeNull();

    const loadingIndicator = appPage.getByTestId('qms-analysis-loading');
    const bandsChart = appPage.getByTestId('qms-analysis-bands-chart');
    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await bandsChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading bands analysis...');
      }
    }).toPass({ timeout: 30000 });
    await expect(bandsChart).toBeVisible({ timeout: 5000 });

    // 11) Assert non-empty curves and axis/tick presence
    const curvePaths = bandsChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => curvePaths.count(), {
        timeout: 10000,
        message: 'Bands plot has no line curves',
      })
      .toBeGreaterThan(0);

    const nonEmptyCurves = await curvePaths.evaluateAll((paths) =>
      paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
    );
    expect(nonEmptyCurves).toBeGreaterThan(0);

    const xAxisTicks = bandsChart.locator(
      '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value',
    );
    await expect
      .poll(async () => xAxisTicks.count(), {
        timeout: 10000,
        message: 'Bands plot x-axis ticks did not render',
      })
      .toBeGreaterThan(1);

    await expect(appPage.getByTestId('qms-analysis-kpath')).toBeVisible({ timeout: 5000 });
    await expect(appPage.getByTestId('qms-analysis-fermi')).toBeVisible({ timeout: 5000 });
  });
});
