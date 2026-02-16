/**
 * Pair 5 E2E: Al DOS Real-Run Smoke Test — FROM SCRATCH
 *
 * Workflow:
 * create project -> import Al CIF -> create QE calculation ->
 * set pseudo mapping -> add steps (scf,nscf,dos) ->
 * set metallic occupation preset + practical parameters -> run QE ->
 * verify non-empty DOS analysis plot.
 */

import * as fs from 'fs';
import * as path from 'path';
import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { clearE2EProjectsRoot, createUniqueProjectDir, getRepoRoot } from './helpers/paths';
import { waitForHomeWelcome } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Pair 5 E2E: Al DOS Real-Run (from scratch)', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('realrun-al-dos');
  });

  test('from-scratch Al DOS workflow with non-empty DOS plot', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    const captureStepState = async (name: string) => {
      const screenshotPath = testInfo.outputPath(`${name}.png`);
      await appPage.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(name, { path: screenshotPath, contentType: 'image/png' });
    };

    const repoRoot = getRepoRoot();
    const alCif = path.join(repoRoot, 'tests', 'data', 'structures', 'al_fcc.cif');
    expect(fs.existsSync(alCif), `Missing structure file at ${alCif}`).toBeTruthy();

    // 1) Create project
    await waitForHomeWelcome(appPage);
    await appPage.getByTestId('qv-welcome-btn-create-new-project').click();
    await appPage.getByTestId('qv-input-parent-dir').fill(projectDir);
    await appPage.getByTestId('qv-input-project-name').fill('al-dos-e2e');
    await appPage.getByTestId('qv-btn-confirm-create').click();
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 15000 });

    // 2) Import Al structure (local CIF)
    await navigateToView(appPage, 'structures');
    await appPage.getByTestId('qv-btn-import-structure').click();
    await appPage.getByTestId('qv-import-structure-file').fill(alCif);
    await appPage.getByTestId('qv-import-structure-name').fill('Al');
    await appPage.getByTestId('qv-btn-confirm-import-structure').click();
    await appPage.waitForTimeout(2000);

    // 3) Create QE calculation
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    await appPage.getByTestId('qv-btn-new-calculation').click();
    await appPage.getByTestId('qv-create-calc-name').fill('Al DOS Test');

    const structureSelect = appPage.getByTestId('qv-create-calc-structure');
    const structureOptions = structureSelect.locator('option');
    const structureCount = await structureOptions.count();
    let selectedStructure = false;
    for (let i = 0; i < structureCount; i++) {
      const text = await structureOptions.nth(i).textContent();
      if (text && text.includes('Al')) {
        await structureSelect.selectOption({ index: i });
        selectedStructure = true;
        break;
      }
    }
    expect(selectedStructure).toBeTruthy();

    await appPage.getByTestId('qv-create-calc-engine').selectOption({ value: 'qe' });
    await appPage.getByTestId('qv-btn-confirm-create-calc').click();
    await appPage.waitForTimeout(2000);

    // 4) Select calculation
    const calcRow = appPage.getByTestId('qv-calculation-row').first();
    await expect(calcRow).toBeVisible({ timeout: 5000 });
    await calcRow.click();
    await expect(appPage.getByTestId('qv-calc-tab-overview')).toHaveClass(/calculations-workspace-tab--active/);
    await expect(appPage.getByTestId('qv-calc-overview-panel')).toBeVisible({ timeout: 5000 });
    await appPage.waitForTimeout(1000);

    // 5) Configure pseudo mapping (Al)
    const editPseudoBtn = appPage.getByTestId('qv-btn-edit-pseudos');
    await expect(editPseudoBtn).toBeVisible({ timeout: 10000 });
    await editPseudoBtn.click();

    const pseudoSelectAl = appPage.getByTestId('qv-pseudo-select-Al');
    await expect(pseudoSelectAl).toBeVisible({ timeout: 10000 });
    const pseudoOptions = pseudoSelectAl.locator('option');
    await expect
      .poll(async () => pseudoOptions.count(), {
        timeout: 15000,
        message: 'Pseudo dropdown did not populate for Al',
      })
      .toBeGreaterThan(1);

    const currentPseudoValue = await pseudoSelectAl.inputValue();
    if (!currentPseudoValue) {
      await pseudoSelectAl.selectOption({ index: 1 });
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

    const addStep = async (stepType: string) => {
      const stepRows = appPage.locator('.step-item-container');
      const beforeCount = await stepRows.count();

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
          message: 'Add-step dropdown is empty',
        })
        .toBeGreaterThan(1);

      const stepTypeValues = await stepTypeOptions.evaluateAll((options) =>
        options.map((opt) => (opt as HTMLOptionElement).value),
      );
      expect(stepTypeValues).toContain(stepType);

      await stepTypeSelect.selectOption({ value: stepType });
      const confirmAddStepBtn = appPage.getByTestId('qv-confirm-add-step');
      await expect(confirmAddStepBtn).toBeEnabled();
      await confirmAddStepBtn.click({ timeout: 5000 });

      await expect
        .poll(async () => stepRows.count(), {
          timeout: 15000,
          message: `Step ${stepType} was not added`,
        })
        .toBe(beforeCount + 1);
    };

    // 6) Add workflow steps: scf -> nscf -> dos
    try {
      await addStep('scf');
      await addStep('nscf');
      await addStep('dos');
    } catch (e) {
      await captureStepState('add-steps-failure-al-dos');
      throw e;
    }

    const normalizeStepType = (value: string) => value.toLowerCase().replace(/[_\s-]/g, '');
    const buildStepRegex = (stepType: string) => new RegExp(`\\b${stepType}\\b`, 'i');
    const currentStepPanel = () => appPage.locator('.step-detail-panel:visible').first();

    const enterFocusModeForStep = async (stepType: string) => {
      const focusTab = appPage.getByTestId('qv-calc-overview-tab-focus');
      if (await focusTab.isVisible().catch(() => false)) {
        return;
      }

      const targetPattern = buildStepRegex(stepType);
      const overviewStepButtons = appPage.locator('[data-testid^="qv-step-button-"]');
      await expect
        .poll(async () => overviewStepButtons.count(), {
          timeout: 15000,
          message: 'Overview step buttons were not rendered',
        })
        .toBeGreaterThan(0);

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
        dos: 2,
      };

      const waitForDetailStepType = async (expectedStepType: string, timeoutMs = 12000) => {
        try {
          const expected = normalizeStepType(expectedStepType);
          await expect
            .poll(async () => {
              const stepTypeValue = currentStepPanel().getByTestId('qv-step-type-value');
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
        if (!(await appPage.getByTestId('qv-calc-overview-tab-focus').isVisible().catch(() => false))) {
          await enterFocusModeForStep(stepType);
        }

        const focusContainer = appPage.getByTestId('qv-calc-overview-tab-focus');
        await expect(focusContainer).toBeVisible({ timeout: 15000 });
        const focusSteps = focusContainer.locator('.compact-step-list__step-item');
        await expect
          .poll(async () => focusSteps.count(), {
            timeout: 10000,
            message: 'Focus-mode step list is empty',
          })
          .toBeGreaterThan(0);

        if (await waitForDetailStepType(stepType, 3000)) {
          return;
        }

        const selectedFocusStep = focusContainer.locator('.compact-step-list__step-item--selected').first();
        if (await selectedFocusStep.isVisible().catch(() => false)) {
          const selectedText = normalizeStepType((await selectedFocusStep.textContent()) || '');
          if (selectedText.includes(normalizeStepType(stepType))) {
            if (await waitForDetailStepType(stepType, 5000)) {
              return;
            }
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
      const applyParamsBtn = currentStepPanel().getByTestId('qv-btn-apply-step-params');
      await expect(applyParamsBtn).toBeVisible({ timeout: 5000 });
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
      const applyParamsBtn = currentStepPanel().getByTestId('qv-btn-apply-step-params');
      if (await applyParamsBtn.isVisible().catch(() => false)) {
        return;
      }
      const editParamsBtn = currentStepPanel().getByTestId('qv-btn-edit-step-params');
      await expect(editParamsBtn).toBeVisible({ timeout: 10000 });
      await editParamsBtn.click();
      await expect(applyParamsBtn).toBeVisible({ timeout: 10000 });
    };

    const ensureKPointsEditorVisible = async () => {
      const panel = currentStepPanel();
      const panelContent = panel.locator('.panel-content').first();
      const kPointsEditor = panel.getByTestId('qv-kpoints-editor');
      const kPointsLoading = panel.getByTestId('qv-kpoints-loading');
      const stepTypeValue = panel.getByTestId('qv-step-type-value');

      const start = Date.now();
      const mountTimeoutMs = 15000;
      while (Date.now() - start < mountTimeoutMs) {
        const editorCount = await kPointsEditor.count();
        if (editorCount > 0) {
          break;
        }
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

      for (const ratio of [0, 0.2, 0.4, 0.6, 0.8, 1]) {
        await panelContent.evaluate((el, r) => {
          const node = el as HTMLElement;
          node.scrollTop = Math.floor(node.scrollHeight * r);
        }, ratio);
        const visible = await kPointsEditor.isVisible().catch(() => false);
        if (visible) {
          return;
        }
        await appPage.waitForTimeout(150);
      }

      await kPointsEditor.scrollIntoViewIfNeeded().catch(() => {});
      if (await kPointsEditor.isVisible().catch(() => false)) {
        return;
      }

      throw new Error('K_POINTS editor is mounted but not visible/actionable in the step panel');
    };

    const setAutomaticKMesh = async (nk1: number, nk2: number, nk3: number) => {
      const panel = currentStepPanel();
      await ensureKPointsEditorVisible();

      const modeSelect = panel.getByTestId('qv-kpoints-mode-select');
      await expect(modeSelect).toBeVisible({ timeout: 5000 });
      await modeSelect.selectOption('automatic');

      const nk1Input = panel.getByTestId('qv-kpoints-auto-nk1');
      const nk2Input = panel.getByTestId('qv-kpoints-auto-nk2');
      const nk3Input = panel.getByTestId('qv-kpoints-auto-nk3');
      await nk1Input.fill(String(nk1));
      await nk2Input.fill(String(nk2));
      await nk3Input.fill(String(nk3));

      await expect(nk1Input).toHaveValue(String(nk1));
      await expect(nk2Input).toHaveValue(String(nk2));
      await expect(nk3Input).toHaveValue(String(nk3));
    };

    const ensureDosParam = async (paramName: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      let input = panel.getByTestId(`qv-param-input-dos-${lower}`);
      if ((await input.count()) > 0) {
        return input;
      }

      const addParamBtn = panel.getByTestId('qv-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = panel.getByTestId('qv-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill(lower);

      const result = panel.getByTestId(`qv-add-parameter-result-${lower}`).first();
      await expect(result).toBeVisible({ timeout: 10000 });
      await result.click();

      input = panel.getByTestId(`qv-param-input-dos-${lower}`);
      await expect(input).toBeVisible({ timeout: 10000 });
      return input;
    };

    const ensureSystemParam = async (paramName: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      const existingRow = panel.getByTestId(`qv-param-row-system-${lower}`);
      if ((await existingRow.count()) > 0) {
        return existingRow.first();
      }

      const addParamBtn = panel.getByTestId('qv-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = panel.getByTestId('qv-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill(lower);

      const result = panel.getByTestId(`qv-add-parameter-result-${lower}`).first();
      await expect(result).toBeVisible({ timeout: 10000 });
      await result.click();

      const addedRow = panel.getByTestId(`qv-param-row-system-${lower}`).first();
      await expect(addedRow).toBeVisible({ timeout: 10000 });
      return addedRow;
    };

    const setSystemRealParam = async (paramName: string, value: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      let input = panel.getByTestId(`qv-param-input-system-${lower}`);
      if ((await input.count()) === 0) {
        await ensureSystemParam(lower);
        input = panel.getByTestId(`qv-param-input-system-${lower}`);
      }
      await expect(input.first()).toBeVisible({ timeout: 10000 });
      await input.first().fill(value);
      await input.first().press('Tab');
      const expected = Number.parseFloat(value);
      await expect
        .poll(async () => {
          const raw = await input.first().inputValue();
          const parsed = Number.parseFloat(raw);
          return Number.isFinite(parsed) ? parsed : NaN;
        }, { timeout: 10000 })
        .toBeCloseTo(expected, 8);
    };

    const setSystemCharacterRawParam = async (paramName: string, value: string) => {
      const row = await ensureSystemParam(paramName);
      const rawToggle = row.locator('button[title="Edit raw value"]').first();
      if (await rawToggle.isVisible().catch(() => false)) {
        await rawToggle.click();
      }
      const rawInput = row.getByTestId(`qv-param-input-system-${paramName.toLowerCase()}`).first();
      await expect(rawInput).toBeVisible({ timeout: 10000 });
      await rawInput.fill(value);
      await rawInput.press('Tab');
      await expect(rawInput).toHaveValue(value);
    };

    // 7) Set parameters per step (mirror Pair 5 RPC setup)
    await openStepByType('scf');
    await ensureEditMode();
    await setSystemRealParam('ecutwfc', '30.0');
    await setSystemRealParam('ecutrho', '240.0');
    await setSystemCharacterRawParam('occupations', 'smearing');
    await setSystemCharacterRawParam('smearing', 'gaussian');
    await setSystemRealParam('degauss', '0.02');
    await setAutomaticKMesh(4, 4, 4);
    await applyStepParams();

    await openStepByType('nscf');
    await ensureEditMode();
    await setSystemRealParam('ecutwfc', '30.0');
    await setSystemRealParam('ecutrho', '240.0');
    await setSystemCharacterRawParam('occupations', 'smearing');
    await setSystemCharacterRawParam('smearing', 'gaussian');
    await setSystemRealParam('degauss', '0.02');
    await setAutomaticKMesh(6, 6, 6);
    await applyStepParams();

    await openStepByType('dos');
    await ensureEditMode();
    const dosFildos = await ensureDosParam('fildos');
    await dosFildos.fill('al.dos.dat');
    await dosFildos.press('Tab');
    await applyStepParams();

    // 8) Run calculation
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

    const runLogsPanel = appPage.getByTestId('qv-calc-run-logs-panel');
    await expect(runLogsPanel).toBeVisible({ timeout: 10000 });

    // 9) Wait for completion
    const statusBadge = runLogsPanel.getByTestId('qv-job-status');
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
        throw new Error(`QE Al DOS calculation failed: ${errorText}`);
      }
      if (status === 'completed' && sawActiveState) {
        completed = true;
        break;
      }

      await appPage.waitForTimeout(2000);
    }
    if (!completed) {
      throw new Error(`Al DOS job did not complete within ${timeoutMs}ms`);
    }

    const runError = runLogsPanel.locator('.calculation-run-tab__error');
    if (await runError.isVisible().catch(() => false)) {
      const errorText = (await runError.textContent()) || 'unknown run error';
      throw new Error(`Al DOS run reported error: ${errorText}`);
    }

    // 10) Analysis tab, select DOS
    const analysisTab = appPage.getByTestId('qv-calc-tab-analysis');
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qv-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });

    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });

    const referenceToggle = appPage.getByTestId('qv-analysis-reference-toggle');
    if ((await referenceToggle.count()) > 0) {
      await expect(referenceToggle).toBeVisible({ timeout: 10000 });
      for (let attempt = 0; attempt < 3; attempt += 1) {
        if (!(await referenceToggle.isChecked())) {
          break;
        }
        await referenceToggle.uncheck({ force: true });
        await appPage.waitForTimeout(300);
      }
      await expect(referenceToggle).not.toBeChecked({ timeout: 10000 });
    }
    await expect(appPage.getByTestId('qv-analysis-reference-banner')).toHaveCount(0, { timeout: 10000 });

    const waitForDosState = async (timeoutMs: number): Promise<'chart' | 'tile' | 'none' | 'timeout'> => {
      const start = Date.now();
      let noObjectsSince: number | null = null;
      while (Date.now() - start < timeoutMs) {
        const loadingVisible = await analysisPanel.getByTestId('qv-analysis-loading').isVisible().catch(() => false);
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

        const chartVisible = await analysisPanel.getByTestId('qv-analysis-dos-chart').isVisible().catch(() => false);
        if (chartVisible) {
          return 'chart';
        }
        const dosTileVisible = await analysisPanel
          .locator('.analysis-viz__tile')
          .filter({ hasText: /^dos$/i })
          .first()
          .isVisible()
          .catch(() => false);
        if (dosTileVisible) {
          return 'tile';
        }
        const noneVisible = await analysisPanel.getByTestId('qv-analysis-no-objects').isVisible().catch(() => false);
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

    const candidateStepTabs = ['dos', 'nscf', 'scf'] as const;
    let selectedStepTab: (typeof candidateStepTabs)[number] | null = null;
    for (const stepTab of candidateStepTabs) {
      const stepChip = analysisPanel.locator(`[data-testid="qv-analysis-step-tab-${stepTab}"]`);
      if (!(await stepChip.isVisible().catch(() => false))) {
        continue;
      }
      await stepChip.click();
      await expect(stepChip).toHaveClass(/--active/, { timeout: 5000 });
      let state = await waitForDosState(20000);
      if (state === 'tile') {
        const dosTile = analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^dos$/i }).first();
        await dosTile.click();
        state = await waitForDosState(10000);
      }
      if (state === 'chart') {
        selectedStepTab = stepTab;
        break;
      }
    }

    expect(selectedStepTab, 'No renderable DOS chart found in analysis for any candidate step').not.toBeNull();

    const loadingIndicator = appPage.getByTestId('qv-analysis-loading');
    const dosChart = appPage.getByTestId('qv-analysis-dos-chart');
    await expect(async () => {
      const isLoading = await loadingIndicator.isVisible().catch(() => false);
      const hasChart = await dosChart.isVisible().catch(() => false);
      if (isLoading && !hasChart) {
        throw new Error('Still loading Al DOS analysis...');
      }
    }).toPass({ timeout: 30000 });
    await expect(dosChart).toBeVisible({ timeout: 5000 });

    // 11) Assert non-empty curve(s), axes, and Fermi marker
    const curvePaths = dosChart.locator('.recharts-line .recharts-line-curve');
    await expect
      .poll(async () => curvePaths.count(), {
        timeout: 10000,
        message: 'Al DOS plot has no line curves',
      })
      .toBeGreaterThan(0);

    const nonEmptyCurves = await curvePaths.evaluateAll((paths) =>
      paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
    );
    expect(nonEmptyCurves).toBeGreaterThan(0);

    const xAxisTicks = dosChart.locator(
      '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value',
    );
    await expect
      .poll(async () => xAxisTicks.count(), {
        timeout: 10000,
        message: 'Al DOS plot x-axis ticks did not render',
      })
      .toBeGreaterThan(1);

    const fermiMarker = appPage.getByTestId('qv-analysis-fermi');
    await expect(fermiMarker).toBeVisible({ timeout: 5000 });
    await expect(fermiMarker).not.toHaveText(/^\s*$/);
  });
});
