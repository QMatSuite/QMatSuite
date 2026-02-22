/**
 * Pair 6 E2E: QE + Wannier90 Real-Run Smoke Test — FROM SCRATCH
 *
 * Workflow:
 * create project -> import Si CIF -> create QE calculation ->
 * set pseudo mapping -> add steps (scf,nscf,wannierprep,pw2wannier,wannier) ->
 * set key parameters via GUI -> run full chain ->
 * verify raw artifacts and SCF convergence plot.
 */

import * as fs from 'fs';
import * as path from 'path';
import { electronTest as test, expect, navigateToView, QE_JOB_TEST_TIMEOUT } from './fixtures/electronTest';
import { clearE2EProjectsRoot, createUniqueProjectDir, getRepoRoot } from './helpers/paths';
import { waitForHomeWelcome } from './helpers/demo_project';

const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('Pair 6 E2E: QE + Wannier90 Real-Run (from scratch)', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');

  let projectDir: string;

  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('realrun-qe-wannier');
  });

  test('from-scratch QE+Wannier workflow with artifacts and convergence plot', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(QE_JOB_TEST_TIMEOUT);

    const captureStepState = async (name: string) => {
      const screenshotPath = testInfo.outputPath(`${name}.png`);
      await appPage.screenshot({ path: screenshotPath, fullPage: true });
      await testInfo.attach(name, { path: screenshotPath, contentType: 'image/png' });
    };

    const repoRoot = getRepoRoot();
    const siCif = path.join(repoRoot, 'tests', 'data', 'structures', 'si_diamond.cif');
    expect(fs.existsSync(siCif), `Missing structure file at ${siCif}`).toBeTruthy();
    const projectRootPath = path.join(projectDir, 'qe-wannier-e2e');
    const calculationSlug = 'si-wannier-test';

    // 1) Create project
    await waitForHomeWelcome(appPage);
    await appPage.getByTestId('qms-welcome-btn-create-new-project').click();
    await appPage.getByTestId('qms-input-parent-dir').fill(projectDir);
    await appPage.getByTestId('qms-input-project-name').fill('qe-wannier-e2e');
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
    await appPage.getByTestId('qms-create-calc-name').fill('Si Wannier Test');

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

    // 6) Add workflow steps: scf -> nscf -> wannierprep -> pw2wannier -> wannier
    try {
      await addStep('scf');
      await addStep('nscf');
      await addStep('wannierprep');
      await addStep('pw2wannier');
      await addStep('wannier');
    } catch (e) {
      await captureStepState('add-steps-failure-qe-wannier');
      throw e;
    }

    const normalizeStepType = (value: string) => value.toLowerCase().replace(/[_\s-]/g, '');
    const buildStepRegex = (stepType: string) => new RegExp(`\\b${stepType}\\b`, 'i');
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
        wannierprep: 2,
        pw2wannier: 3,
        wannier: 4,
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
      const applyParamsBtn = currentStepPanel().getByTestId('qms-btn-apply-step-params');
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
          return kPointsEditor;
        }
        await appPage.waitForTimeout(150);
      }

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

    const applyKPointsCardIfDirty = async () => {
      const panel = currentStepPanel();
      const cardApplyBtn = panel.getByTestId('qms-kpoints-apply');
      if (await cardApplyBtn.isVisible().catch(() => false)) {
        await expect(cardApplyBtn).toBeEnabled({ timeout: 5000 });
        await cardApplyBtn.click();
        await expect(cardApplyBtn).toBeHidden({ timeout: 10000 });
      }
    };

    const setCrystalKPoints = async (
      points: Array<{ x: number; y: number; z: number; w: number }>,
    ) => {
      const panel = currentStepPanel();
      await ensureKPointsEditorVisible();

      const modeSelect = panel.getByTestId('qms-kpoints-mode-select');
      await expect(modeSelect).toBeVisible({ timeout: 5000 });
      await modeSelect.selectOption('crystal');

      const rawModeBtn = panel.getByTestId('qms-kpoints-editor-raw');
      await expect(rawModeBtn).toBeVisible({ timeout: 5000 });
      await rawModeBtn.click();

      const rawBody = panel.getByTestId('qms-kpoints-raw-body');
      await expect(rawBody).toBeEditable({ timeout: 5000 });
      const body = [
        String(points.length),
        ...points.map((pt) => `${pt.x} ${pt.y} ${pt.z} ${pt.w}`),
      ].join('\n');
      await rawBody.fill(body);
      await expect(rawBody).toHaveValue(body, { timeout: 5000 });

      const preview = panel.locator('.kpoints-card__preview-content');
      await expect(preview).toContainText('K_POINTS crystal', { timeout: 5000 });
      await expect(preview).toContainText(`${points.length}\n`, { timeout: 5000 });

      const structuredModeBtn = panel.getByTestId('qms-kpoints-editor-structured');
      await expect(structuredModeBtn).toBeVisible({ timeout: 5000 });
      await structuredModeBtn.click();
      await expect(panel.getByTestId(`qms-kpoints-point-${points.length - 1}-x`)).toBeVisible({ timeout: 10000 });
      for (let row = 0; row < points.length; row += 1) {
        const pt = points[row];
        await expect(panel.getByTestId(`qms-kpoints-point-${row}-x`)).toHaveValue(String(pt.x), { timeout: 5000 });
        await expect(panel.getByTestId(`qms-kpoints-point-${row}-y`)).toHaveValue(String(pt.y), { timeout: 5000 });
        await expect(panel.getByTestId(`qms-kpoints-point-${row}-z`)).toHaveValue(String(pt.z), { timeout: 5000 });
        await expect(panel.getByTestId(`qms-kpoints-point-${row}-w`)).toHaveValue(String(pt.w), { timeout: 5000 });
      }
    };

    const ensureSystemParam = async (paramName: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      const existingRow = panel.getByTestId(`qms-param-row-system-${lower}`);
      if ((await existingRow.count()) > 0) {
        return existingRow.first();
      }

      const addParamBtn = panel.getByTestId('qms-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = panel.getByTestId('qms-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill(lower);

      const result = panel.getByTestId(`qms-add-parameter-result-${lower}`).first();
      await expect(result).toBeVisible({ timeout: 10000 });
      await result.click();

      const addedRow = panel.getByTestId(`qms-param-row-system-${lower}`).first();
      await expect(addedRow).toBeVisible({ timeout: 10000 });
      return addedRow;
    };

    const setSystemRealParam = async (paramName: string, value: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      let input = panel.getByTestId(`qms-param-input-system-${lower}`);
      if ((await input.count()) === 0) {
        await ensureSystemParam(lower);
        input = panel.getByTestId(`qms-param-input-system-${lower}`);
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

    const setSystemIntegerParam = async (paramName: string, value: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      let input = panel.getByTestId(`qms-param-input-system-${lower}`);
      if ((await input.count()) === 0) {
        await ensureSystemParam(lower);
        input = panel.getByTestId(`qms-param-input-system-${lower}`);
      }
      await expect(input.first()).toBeVisible({ timeout: 10000 });
      await input.first().fill(value);
      await input.first().press('Tab');
      await expect(input.first()).toHaveValue(value, { timeout: 10000 });
    };

    const setSystemLogicalParam = async (paramName: string, enabled: boolean) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      let row = panel.getByTestId(`qms-param-row-system-${lower}`);
      if ((await row.count()) === 0) {
        await ensureSystemParam(lower);
        row = panel.getByTestId(`qms-param-row-system-${lower}`);
      }
      await expect(row.first()).toBeVisible({ timeout: 10000 });
      const logicalSelect = row.first().locator('select.parameter-value-editor--logical');
      await expect(logicalSelect).toBeVisible({ timeout: 10000 });
      await logicalSelect.selectOption(enabled ? '.true.' : '.false.');
      await expect(logicalSelect).toHaveValue(enabled ? '.true.' : '.false.');
    };

    const ensureParameterViaPalette = async (paramName: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();

      const candidateRows = [
        panel.getByTestId(`qms-param-row-system-${lower}`),
        panel.getByTestId(`qms-param-row-parameters-${lower}`),
        panel.getByTestId(`qms-param-row-wannier90-${lower}`),
      ];

      for (const row of candidateRows) {
        if ((await row.count()) > 0) {
          return;
        }
      }

      const addParamBtn = panel.getByTestId('qms-add-parameter-trigger');
      await expect(addParamBtn).toBeVisible({ timeout: 10000 });
      await addParamBtn.click();

      const searchInput = panel.getByTestId('qms-add-parameter-search');
      await expect(searchInput).toBeVisible({ timeout: 10000 });
      await searchInput.fill(lower);

      const result = panel.getByTestId(`qms-add-parameter-result-${lower}`).first();
      await expect(result).toBeVisible({ timeout: 10000 });
      await result.click();

      await expect
        .poll(async () => {
          for (const row of candidateRows) {
            if ((await row.count()) > 0) return true;
          }
          return false;
        }, { timeout: 10000 })
        .toBeTruthy();
    };

    const setGenericIntegerParam = async (paramName: string, value: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      await ensureParameterViaPalette(lower);

      const candidates = [
        panel.getByTestId(`qms-param-input-system-${lower}`),
        panel.getByTestId(`qms-param-input-parameters-${lower}`),
        panel.getByTestId(`qms-param-input-wannier90-${lower}`),
      ];

      let input = candidates[0];
      for (const candidate of candidates) {
        if ((await candidate.count()) > 0) {
          input = candidate;
          break;
        }
      }
      await expect(input.first()).toBeVisible({ timeout: 10000 });
      await input.first().fill(value);
      await input.first().press('Tab');
      await expect(input.first()).toHaveValue(value, { timeout: 10000 });
    };

    const setGenericTextParam = async (paramName: string, value: string) => {
      const panel = currentStepPanel();
      const lower = paramName.toLowerCase();
      await ensureParameterViaPalette(lower);

      const candidates = [
        panel.getByTestId(`qms-param-input-system-${lower}`),
        panel.getByTestId(`qms-param-input-parameters-${lower}`),
        panel.getByTestId(`qms-param-input-wannier90-${lower}`),
      ];

      let input = candidates[0];
      for (const candidate of candidates) {
        if ((await candidate.count()) > 0) {
          input = candidate;
          break;
        }
      }
      await expect(input.first()).toBeVisible({ timeout: 10000 });
      await input.first().fill(value);
      await input.first().press('Tab');
      await expect(input.first()).toHaveValue(value, { timeout: 10000 });
    };

    // 7) Set key parameters through pure GUI editing.
    await openStepByType('scf');
    await ensureEditMode();
    await setSystemRealParam('ecutwfc', '30.0');
    await setSystemRealParam('ecutrho', '240.0');
    await setAutomaticKMesh(2, 2, 2);
    await applyKPointsCardIfDirty();
    await applyStepParams();

    await openStepByType('nscf');
    await ensureEditMode();
    await setSystemRealParam('ecutwfc', '30.0');
    await setSystemRealParam('ecutrho', '240.0');
    await setSystemLogicalParam('nosym', true);
    await setSystemLogicalParam('noinv', true);
    await setSystemIntegerParam('nbnd', '4');
    await setCrystalKPoints([
      { x: 0.0, y: 0.0, z: 0.0, w: 1.0 },
      { x: 0.0, y: 0.0, z: 0.5, w: 1.0 },
      { x: 0.0, y: 0.5, z: 0.0, w: 1.0 },
      { x: 0.0, y: 0.5, z: 0.5, w: 1.0 },
      { x: 0.5, y: 0.0, z: 0.0, w: 1.0 },
      { x: 0.5, y: 0.0, z: 0.5, w: 1.0 },
      { x: 0.5, y: 0.5, z: 0.0, w: 1.0 },
      { x: 0.5, y: 0.5, z: 0.5, w: 1.0 },
    ]);
    await applyKPointsCardIfDirty();
    await applyStepParams();

    // Required Wannier parameters for nnkp generation.
    await openStepByType('wannierprep');
    await ensureEditMode();
    await setGenericIntegerParam('num_wann', '4');
    await setGenericIntegerParam('num_bands', '4');
    await setGenericTextParam('projections', 'f=0.0,0.0,0.0:sp3');
    await applyStepParams();

    await openStepByType('wannier');
    await ensureEditMode();
    await setGenericIntegerParam('num_wann', '4');
    await setGenericIntegerParam('num_bands', '4');
    await setGenericTextParam('projections', 'f=0.0,0.0,0.0:sp3');
    await applyStepParams();

    // 8) Run full chain
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

    const statusBadge = runLogsPanel.getByTestId('qms-job-status');
    await expect(statusBadge).toBeVisible({ timeout: 30000 });

    const parseJobStatus = (raw: string | null): string => {
      const lowered = (raw || '').toLowerCase();
      const match = lowered.match(/\b(pending|running|completed|failed|cancelled)\b/);
      return match?.[1] || '';
    };
    const waitForNoActiveJobs = async (timeoutMs: number) => {
      await expect
        .poll(async () => {
          const texts = await appPage.locator('.status-bar .status-bar__right .status-bar__text').allTextContents();
          return texts.join(' | ').toLowerCase();
        }, { timeout: timeoutMs, message: 'Status bar did not return to "No jobs"' })
        .toContain('no jobs');
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
        throw new Error(`QE+Wannier calculation failed: ${errorText}`);
      }
      if (status === 'completed' && sawActiveState) {
        completed = true;
        break;
      }

      await appPage.waitForTimeout(2000);
    }
    if (!completed) {
      throw new Error(`QE+Wannier job did not complete within ${timeoutMs}ms`);
    }
    await waitForNoActiveJobs(120000);

    const runError = runLogsPanel.locator('.calculation-run-tab__error');
    if (await runError.isVisible().catch(() => false)) {
      const errorText = (await runError.textContent()) || 'unknown run error';
      throw new Error(`QE+Wannier run reported error: ${errorText}`);
    }

    // 9) Analysis tab + raw artifact checks
    const analysisTab = appPage.getByTestId('qms-calc-tab-analysis');
    await analysisTab.click();
    await expect(analysisTab).toHaveClass(/calculations-workspace-tab--active/, { timeout: 5000 });

    const analysisPanel = appPage.getByTestId('qms-calc-analysis-panel');
    await expect(analysisPanel).toBeVisible({ timeout: 5000 });

    const ensureReferenceOff = async () => {
      const referenceToggle = appPage.getByTestId('qms-analysis-reference-toggle');
      if ((await referenceToggle.count()) > 0) {
        await expect(referenceToggle).toBeVisible({ timeout: 10000 });
        if (await referenceToggle.isChecked()) {
          await referenceToggle.uncheck({ force: true });
        }
        await expect(referenceToggle).not.toBeChecked({ timeout: 10000 });
      }
      await expect(appPage.getByTestId('qms-analysis-reference-banner')).toHaveCount(0, { timeout: 10000 });
    };
    await ensureReferenceOff();

    const selectStepInAnalysis = async (step: string) => {
      const stepChip = analysisPanel.locator(`[data-testid="qms-analysis-step-tab-${step}"]`);
      await expect(stepChip).toBeVisible({ timeout: 10000 });
      await stepChip.click();
      await expect(stepChip).toHaveClass(/--active/, { timeout: 5000 });
    };

    const ensureRawMode = async () => {
      const rawTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Raw$/i });
      await expect(rawTab).toBeVisible({ timeout: 5000 });
      await rawTab.click();
      await expect(rawTab).toHaveClass(/--active/, { timeout: 5000 });
    };

    const walkFiles = (root: string): string[] => {
      if (!fs.existsSync(root)) {
        return [];
      }
      const out: string[] = [];
      const stack = [root];
      while (stack.length > 0) {
        const current = stack.pop() as string;
        const entries = fs.readdirSync(current, { withFileTypes: true });
        for (const entry of entries) {
          const nextPath = path.join(current, entry.name);
          if (entry.isDirectory()) {
            stack.push(nextPath);
          } else if (entry.isFile()) {
            out.push(nextPath);
          }
        }
      }
      return out;
    };

    const readArtifactFromCandidates = (stepCandidates: string[], fileMatcher: RegExp): string => {
      const calculationRoot = path.join(projectRootPath, 'calculations', calculationSlug);
      const allFiles = walkFiles(calculationRoot);
      const matchPath = allFiles.find((candidate) => {
        const rel = path.relative(calculationRoot, candidate).replaceAll(path.sep, '/');
        return fileMatcher.test(rel) || fileMatcher.test(path.basename(candidate));
      });
      if (!matchPath) {
        throw new Error(
          `Unable to locate artifact ${fileMatcher} in ${calculationRoot} (step candidates: ${stepCandidates.join(', ')})`,
        );
      }
      return fs.readFileSync(matchPath, 'utf-8');
    };

    const scfIn = readArtifactFromCandidates(['scf', 'nscf'], /(^|\/)scf\.in$/i);
    expect(scfIn).toMatch(/ecutwfc\s*=\s*30(\.0+)?/i);
    expect(scfIn).toMatch(/ecutrho\s*=\s*240(\.0+)?/i);
    expect(scfIn).toMatch(/K_POINTS\s*[{(]automatic[})]?/i);
    expect(scfIn).toMatch(/\b2\s+2\s+2\s+0\s+0\s+0\b/);

    const nscfIn = readArtifactFromCandidates(['nscf'], /(^|\/)nscf\.in$/i);
    expect(nscfIn).toMatch(/ecutwfc\s*=\s*30(\.0+)?/i);
    expect(nscfIn).toMatch(/ecutrho\s*=\s*240(\.0+)?/i);
    expect(nscfIn).toMatch(/^\s*nosym\s*=\s*\.true\.\s*$/im);
    expect(nscfIn).toMatch(/^\s*noinv\s*=\s*\.true\.\s*$/im);
    expect(nscfIn).not.toMatch(/^\s*nosym\s*=\s*['"]\s*\.true\.\s*['"]\s*$/im);
    expect(nscfIn).not.toMatch(/^\s*noinv\s*=\s*['"]\s*\.true\.\s*['"]\s*$/im);
    expect(nscfIn).toMatch(/nbnd\s*=\s*4/i);
    expect(nscfIn).toMatch(/K_POINTS\s*[{(]crystal[})]?/i);
    expect(nscfIn).toMatch(/\n\s*8\s*\n/);

    const wprepWin = readArtifactFromCandidates(['wannierprep', 'wannier'], /wannierprep\.win$/i);
    expect(wprepWin).toMatch(/num_wann\s*=\s*4\b/i);
    expect(wprepWin).toMatch(/num_bands\s*=\s*4\b/i);
    expect(wprepWin).toMatch(/mp_grid\s*[:=]\s*2\s+2\s+2\b/i);
    expect(wprepWin).toMatch(/f=0\.0,0\.0,0\.0:sp3/i);

    const pw2wanIn = readArtifactFromCandidates(['pw2wannier', 'wannierprep'], /pw2wan\.in$/i);
    expect(pw2wanIn.toLowerCase()).toContain('seedname');

    const pw2wanOut = readArtifactFromCandidates(['pw2wannier', 'wannier'], /pw2wannier\.out$/i);
    expect(pw2wanOut).toMatch(/PW2WANNIER/i);
    expect(pw2wanOut).toMatch(/JOB DONE/i);

    const wout = readArtifactFromCandidates(['wannier', 'wannierprep'], /wannierprep\.wout$/i);
    expect(wout).toMatch(/All done:\s*wannier90 exiting/i);

    // 10) Plot mode: verify SCF convergence is renderable and non-empty
    const plotTab = analysisPanel.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: /^Plot$/i });
    await expect(plotTab).toBeVisible({ timeout: 5000 });
    await plotTab.click();
    await expect(plotTab).toHaveClass(/--active/, { timeout: 5000 });
    await ensureReferenceOff();

    await selectStepInAnalysis('scf');

    const waitForConvergenceState = async (timeoutMs: number): Promise<'chart' | 'tile' | 'none' | 'timeout'> => {
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

        const chartVisible = await analysisPanel.getByTestId('qms-analysis-convergence-chart').isVisible().catch(() => false);
        if (chartVisible) {
          return 'chart';
        }
        const tileVisible = await analysisPanel
          .locator('.analysis-viz__tile')
          .filter({ hasText: /^convergence$/i })
          .first()
          .isVisible()
          .catch(() => false);
        if (tileVisible) {
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

    let convergenceState = await waitForConvergenceState(20000);
    if (convergenceState === 'tile') {
      const convergenceTile = analysisPanel.locator('.analysis-viz__tile').filter({ hasText: /^convergence$/i }).first();
      await convergenceTile.click();
      convergenceState = await waitForConvergenceState(10000);
    }

    expect(convergenceState, 'SCF convergence chart was not available').toBe('chart');

    const convergenceChart = analysisPanel.getByTestId('qms-analysis-convergence-chart');
    await expect(convergenceChart).toBeVisible({ timeout: 10000 });
    await convergenceChart.scrollIntoViewIfNeeded();

    const curves = convergenceChart.locator(
      '.recharts-line .recharts-line-curve, .recharts-area .recharts-area-curve, .recharts-line-curve, .recharts-area-curve',
    );
    await expect
      .poll(async () => curves.count(), {
        timeout: 10000,
        message: 'SCF convergence chart has no curve paths',
      })
      .toBeGreaterThan(0);
    const nonEmptyCurves = await curves.evaluateAll((paths) =>
      paths.filter((p) => (((p as SVGPathElement).getAttribute('d') || '').length > 20)).length,
    );
    expect(nonEmptyCurves).toBeGreaterThan(0);

    const xTicks = convergenceChart.locator(
      '.recharts-cartesian-axis.recharts-xAxis .recharts-cartesian-axis-tick-value',
    );
    await expect
      .poll(async () => xTicks.count(), {
        timeout: 10000,
        message: 'SCF convergence x-axis ticks did not render',
      })
      .toBeGreaterThan(1);
  });
});
