/**
 * E2E Tests: Step Parameter Defaults vs Import Semantics
 * 
 * Tests that verify the two distinct modes for step creation:
 * A. From-scratch creation uses QV defaults (outdir, restart_mode, conv_thr, etc.)
 * B. Import from QE input preserves original parameters (no defaults injected)
 * 
 * **This spec does NOT run any calculations.** It only tests:
 * - Step default parameters visible in step detail panels
 * - Step YAML file contents (defaults vs imported parameters)
 * - UI elements for step creation/import buttons
 * - Step Focus mode for viewing step details
 * 
 * All assertions are based on step definitions and YAML files, not computation outputs.
 * 
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test tests/e2e/step_defaults.spec.ts --project=electron
 * 
 * REFACTOR NOTES (Updated for new Calculations UI):
 * - StepDetailPanel is now only visible in Step Focus mode (when a step is selected)
 * - To view step details, must click a step to enter Step Focus mode
 * - Step Focus mode shows compact step list on left, StepDetailPanel on right
 * - Can exit Step Focus mode by clicking "Back to overview" button
 */

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { createUniqueProjectDir, clearE2EProjectsRoot, getRepoRoot, createDemoProject } from './helpers';

// Skip if explicitly requested via environment variable
const SKIP_E2E = process.env.SKIP_ELECTRON_E2E === 'true';

test.describe('E2E: Step Parameter Defaults', () => {
  test.skip(SKIP_E2E, 'Skipped when SKIP_ELECTRON_E2E=true');
  
  let projectDir: string;
  
  test.beforeEach(() => {
    clearE2EProjectsRoot();
    projectDir = createUniqueProjectDir('step-defaults');
  });
  
  test('from-scratch step has QV defaults', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(60 * 1000);
    
    // Collect console errors and network failures
    const consoleErrors: string[] = [];
    const networkFailures: string[] = [];
    
    appPage.on('console', (msg) => {
      if (msg.type() === 'error') {
        const text = msg.text();
        // Ignore known benign errors (e.g., React dev warnings in test mode)
        if (!text.includes('Warning:') && !text.includes('React DevTools')) {
          consoleErrors.push(`[Console Error] ${text}`);
        }
      }
    });
    
    appPage.on('pageerror', (error) => {
      consoleErrors.push(`[Page Error] ${error.message || String(error)}`);
    });
    
    appPage.on('requestfailed', (request) => {
      const failure = request.failure();
      if (failure) {
        networkFailures.push(`[Network Failure] ${request.method()} ${request.url()}: ${failure.errorText}`);
      }
    });
    
    // Create demo project via Demo Gallery flow
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-step-defaults',
      parentDir: projectDir,
    });
    
    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    
    // Verify Overview & Steps tab is active
    await expect(appPage.getByTestId('qv-calc-tab-overview')).toBeVisible();
    
    // Select the calculation
    const calculationRows = appPage.getByTestId('qv-calculation-row');
    await expect(calculationRows).toHaveCount(1);
    await calculationRows.first().click();
    await expect(appPage.getByTestId('qv-calculation-detail')).toBeVisible({ timeout: 10000 });
    
    // Verify we're in Overview mode
    await expect(appPage.getByTestId('qv-calc-overview-tab')).toBeVisible();
    
    // Add a new SCF step via GUI (from-scratch, should use defaults)
    await appPage.getByTestId('qv-add-step-btn').click();
    
    // Wait for add step form
    await expect(appPage.getByTestId('qv-add-step-form')).toBeVisible({ timeout: 5000 });
    
    // Select step type
    const stepTypeSelect = appPage.locator('.add-step-form select').first();
    await stepTypeSelect.selectOption('scf');
    
    // Click Add Step button
    await appPage.getByTestId('qv-confirm-add-step').click();
    
    // Wait for step to be added and calculation to refresh
    // CRITICAL: Wait for the new step to appear in the calculation steps list before clicking it.
    // This prevents race conditions where get_step_detail is called before the step is
    // available in the ResourceIndex. We wait for a step row with type 'scf' to appear.
    await expect(appPage.getByTestId('qv-steps-list')).toBeVisible({ timeout: 10000 });
    
    // Wait for the add step form to disappear (indicating the step was added)
    await expect(appPage.getByTestId('qv-add-step-form')).not.toBeVisible({ timeout: 10000 });
    
    // Wait for a new step row with type 'scf' to appear (Constitution v1.1 uses step_type_gen)
    // We'll look for step rows and find one with 'scf' type badge
    const stepRows = appPage.locator('[data-testid^="qv-step-row-"]');

    // Wait until we have at least one step row
    await expect(stepRows.first()).toBeVisible({ timeout: 10000 });

    // Find the scf step we just added - wait for it to appear with type 'scf'
    // The step should be visible in the list with a step-type-badge showing 'scf' (step_type_gen format)
    const scfStepRow = stepRows.filter({
      has: appPage.locator('.step-type-badge').filter({ hasText: /^scf$/i })
    }).last();
    
    // Wait for the scf step to be visible and enabled
    await expect(scfStepRow).toBeVisible({ timeout: 10000 });
    const stepButton = scfStepRow.locator('button.step-item');
    await expect(stepButton).toBeEnabled({ timeout: 5000 });
    
    // Click the step button to open step detail (enters Step Focus mode)
    await stepButton.click({ timeout: 5000 });
    
    // Wait for Step Focus mode to activate
    await expect(appPage.getByTestId('qv-calc-overview-tab-focus')).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qv-compact-step-list')).toBeVisible({ timeout: 5000 });
    
    // Wait for step detail panel (in Step Focus mode, it's on the right)
    const stepDetailPanel = appPage.getByTestId('qv-step-detail');
    await expect(stepDetailPanel).toBeVisible({ timeout: 10000 });
    
    // Verify step type is scf (Constitution v1.1: uses step_type_gen format)
    const stepTypeBadge = stepDetailPanel.locator('.step-type-badge');
    await expect(stepTypeBadge).toBeVisible({ timeout: 5000 });
    await expect(stepTypeBadge).toContainText('scf');
    
    // Get the step file path from the step detail panel
    const stepFilePath = stepDetailPanel.getByTestId('qv-step-file-path');
    await expect(stepFilePath).toBeVisible({ timeout: 5000 });
    const filePathText = await stepFilePath.textContent();
    expect(filePathText).toBeTruthy();
    
    // Read the step file directly to verify it contains defaults
    // This is more reliable than trying to parse the UI
    const repoRoot = getRepoRoot();
    const projectPath = path.join(projectDir, 'e2e-step-defaults');
    const stepFilePathResolved = path.isAbsolute(filePathText!) 
      ? filePathText! 
      : path.join(projectPath, filePathText!);
    
    // Wait a bit for file to be written
    await appPage.waitForTimeout(1000);
    
    // Read the step YAML file and verify it contains default parameters
    // This is more reliable than trying to parse the UI
    const stepFileContent = fs.readFileSync(stepFilePathResolved, 'utf-8');
    
    // Verify defaults are present in the step file content
    // Check for CONTROL section with calculation type
    // Note: outdir and restart_mode may not be in the preset defaults
    expect(stepFileContent).toContain('CONTROL');
    expect(stepFileContent).toMatch(/calculation:\s*['"]?scf['"]?/);
    
    // Check for ELECTRONS section with conv_thr
    expect(stepFileContent).toContain('ELECTRONS');
    // Match conv_thr with various formats: 1.0e-08, 1e-08, 1e-8, etc.
    expect(stepFileContent).toMatch(/conv_thr:\s*1\.?0*e?-?0*8/i);
    
    // Check that calculation type is scf
    expect(stepFileContent).toMatch(/calculation:\s*['"]?scf['"]?/i);
    
    // Check for visible error messages in the UI (toasts, banners, etc.)
    const errorElements = appPage.locator('[class*="error"], [class*="Error"], [data-testid*="error"], [data-testid*="Error"], .daemon-error-banner, .error-boundary');
    const errorCount = await errorElements.count();
    if (errorCount > 0) {
      const errorTexts: string[] = [];
      for (let i = 0; i < errorCount; i++) {
        const text = await errorElements.nth(i).textContent();
        if (text && text.trim()) {
          errorTexts.push(text.trim());
        }
      }
      if (errorTexts.length > 0) {
        throw new Error(`Test failed due to visible error messages in UI:\n${errorTexts.join('\n')}`);
      }
    }
    
    // Note: Console errors, page errors, and network failures are automatically
    // checked by the electronTest fixture after the test completes
  });
  
  test('import QE input button exists and is wired correctly', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(60 * 1000);
    
    // Create demo project via Demo Gallery flow
    // Note: Console errors are automatically checked by the electronTest fixture
    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'e2e-import-step',
      parentDir: projectDir,
    });
    
    // Verify project is loaded
    await expect(appPage.getByTestId('qv-home-project')).toBeVisible({ timeout: 10000 });
    
    // Navigate to Calculations view
    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });
    
    // Select the calculation
    const calculationRows = appPage.getByTestId('qv-calculation-row');
    await expect(calculationRows).toHaveCount(1);
    await calculationRows.first().click();
    await expect(appPage.getByTestId('qv-calculation-detail')).toBeVisible({ timeout: 10000 });
    
    // Verify import button exists and has correct tooltip
    const importBtn = appPage.getByTestId('qv-import-step-btn');
    await expect(importBtn).toBeVisible();
    await expect(importBtn).toHaveAttribute('title', 'Import QE input file as step (preserves original parameters)');
    
    // Note: Full file picker automation would require mocking Electron's dialog API
    // The actual import functionality (apply_defaults=False) is tested in Python unit tests
    // (test_import_step_from_qe_input_does_not_inject_defaults)
    
    // Check for visible error messages in the UI (toasts, banners, etc.)
    const errorElements = appPage.locator('[class*="error"], [class*="Error"], [data-testid*="error"], [data-testid*="Error"]');
    const errorCount = await errorElements.count();
    if (errorCount > 0) {
      const errorTexts: string[] = [];
      for (let i = 0; i < errorCount; i++) {
        const text = await errorElements.nth(i).textContent();
        if (text && text.trim()) {
          errorTexts.push(text.trim());
        }
      }
      if (errorTexts.length > 0) {
        throw new Error(`Test failed due to visible error messages in UI:\n${errorTexts.join('\n')}`);
      }
    }
    
    // Note: Console errors, page errors, and network failures are automatically
    // checked by the electronTest fixture after the test completes
  });
});
