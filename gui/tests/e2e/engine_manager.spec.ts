import type { Page } from '@playwright/test';
import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';
import { createDemoProject } from './helpers/demo_project';

type MockResponse = {
  ok: boolean;
  data?: Record<string, unknown>;
  error?: { code: string; message: string };
};

async function setRpcMock(
  page: Page,
  method: string,
  payload: MockResponse | MockResponse[] | null,
): Promise<void> {
  await page.evaluate(async ({ methodName, body }) => {
    if ((window as any).qms?.setE2ERpcMock) {
      await (window as any).qms.setE2ERpcMock(methodName, body);
    }
  }, { methodName: method, body: payload });
}

async function clearRpcMocks(page: Page): Promise<void> {
  await page.evaluate(async () => {
    if ((window as any).qms?.clearE2ERpcMocks) {
      await (window as any).qms.clearE2ERpcMocks();
    }
  });
}

test.describe('E2E: Engine Manager + Update UI', () => {
  test.beforeEach(async ({ appPage }) => {
    await clearRpcMocks(appPage);
    await appPage.evaluate(async () => {
      if ((window as any).qms?.setE2EUpdaterState) {
        await (window as any).qms.setE2EUpdaterState({
          state: 'idle',
          version: null,
          progress: 0,
          message: null,
        });
      }
    });
  });

  test('Engine Manager section is visible in Settings', async ({ appPage }) => {
    await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30000 });
    await navigateToView(appPage, 'settings');

    const manager = appPage.getByTestId('qms-engine-manager-section');
    await expect(manager).toBeVisible({ timeout: 20000 });
    await expect(manager.locator('[data-testid^="qms-engine-row-"]').first()).toBeVisible();
  });

  test('Engine install action shows progress and commercial engine keeps configure path', async ({ appPage }) => {
    await setRpcMock(appPage, 'engine.list', {
      ok: true,
      data: {
        engines: [
          {
            engine: 'xtb',
            installed: false,
            active_installation_id: null,
            active_source: null,
            active: null,
            installations: [],
          },
          {
            engine: 'vasp',
            installed: false,
            active_installation_id: null,
            active_source: null,
            active: null,
            installations: [],
          },
        ],
        count: 2,
        installed_only: false,
      },
    });
    await setRpcMock(appPage, 'engine.list_installable', {
      ok: true,
      data: {
        engines: [
          {
            engine: 'xtb',
            display_name: 'xTB',
            engine_type: 'binary',
            install_methods: ['conda'],
            conda_package: 'xtb',
            conda_channel: 'conda-forge',
            manual_only: false,
          },
          {
            engine: 'vasp',
            display_name: 'VASP',
            engine_type: 'binary',
            install_methods: [],
            conda_package: null,
            conda_channel: null,
            manual_only: true,
          },
        ],
        count: 2,
      },
    });
    await setRpcMock(appPage, 'engine.install', {
      ok: true,
      data: {
        job_id: 'job-xtb-mock',
        status: 'pending',
      },
    });
    await setRpcMock(appPage, 'get_job_status', {
      ok: true,
      data: {
        status: 'running',
        last_log_line: 'Installing xTB package...',
        progress_pct: 45.0,
        progress_bytes: 15000000,
        progress_total: 33000000,
        progress_stage: 'Installing xTB via conda',
        started_at: new Date().toISOString(),
      },
    });

    await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30000 });
    await navigateToView(appPage, 'settings');
    await expect(appPage.getByTestId('qms-engine-manager-section')).toBeVisible({ timeout: 10000 });

    await appPage.getByTestId('qms-engine-manager-refresh').click();
    await expect(appPage.getByTestId('qms-engine-install-xtb')).toBeVisible();
    await expect(appPage.getByTestId('qms-engine-configure-path-vasp')).toBeVisible();

    await appPage.getByTestId('qms-engine-install-xtb').click();
    const progress = appPage.getByTestId('qms-engine-progress-xtb');
    await expect(progress).toBeVisible({ timeout: 10000 });
    // Verify progress bar element exists
    await expect(progress.locator('.engine-progress-bar')).toBeVisible();
    // Verify stage text is shown
    await expect(progress.locator('.engine-progress-info__stage')).toContainText(/Installing|Waiting/);
  });

  test('Engine install progress transitions through pending → running → completed', async ({ appPage }) => {
    // Set up engine list mocks
    await setRpcMock(appPage, 'engine.list', {
      ok: true,
      data: {
        engines: [
          {
            engine: 'xtb',
            installed: false,
            active_installation_id: null,
            active_source: null,
            active: null,
            installations: [],
          },
        ],
        count: 1,
        installed_only: false,
      },
    });
    await setRpcMock(appPage, 'engine.list_installable', {
      ok: true,
      data: {
        engines: [
          {
            engine: 'xtb',
            display_name: 'xTB',
            engine_type: 'binary',
            install_methods: ['conda'],
            conda_package: 'xtb',
            conda_channel: 'conda-forge',
            manual_only: false,
          },
        ],
        count: 1,
      },
    });
    await setRpcMock(appPage, 'engine.install', {
      ok: true,
      data: { job_id: 'job-xtb-flow', status: 'pending' },
    });

    // Phase 1: pending (waiting in queue)
    await setRpcMock(appPage, 'get_job_status', {
      ok: true,
      data: {
        status: 'pending',
        last_log_line: '',
      },
    });

    await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30000 });
    await navigateToView(appPage, 'settings');
    await expect(appPage.getByTestId('qms-engine-manager-section')).toBeVisible({ timeout: 10000 });
    await appPage.getByTestId('qms-engine-manager-refresh').click();
    await expect(appPage.getByTestId('qms-engine-install-xtb')).toBeVisible();
    await appPage.getByTestId('qms-engine-install-xtb').click();

    const progress = appPage.getByTestId('qms-engine-progress-xtb');
    await expect(progress).toBeVisible({ timeout: 10000 });
    // Indeterminate bar should be shown while pending
    await expect(progress.locator('.engine-progress-bar')).toBeVisible();
    await expect(progress.locator('.engine-progress-info__stage')).toContainText(/Waiting/);

    // Phase 2: running with progress
    await setRpcMock(appPage, 'get_job_status', {
      ok: true,
      data: {
        status: 'running',
        last_log_line: 'Extracting package...',
        progress_pct: 60.0,
        progress_bytes: 20000000,
        progress_total: 33000000,
        progress_stage: 'Installing xTB via conda',
        started_at: new Date().toISOString(),
      },
    });
    // Wait for the next poll cycle to pick up new mock
    await expect(progress.locator('.engine-progress-info__stage')).toContainText(/Installing/, { timeout: 10000 });

    // Phase 3: completed
    await setRpcMock(appPage, 'get_job_status', {
      ok: true,
      data: {
        status: 'completed',
        last_log_line: 'Done',
      },
    });
    // After completion, progress bar disappears and notice appears
    await expect(progress).not.toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qms-engine-notice-xtb')).toBeVisible({ timeout: 5000 });
    await expect(appPage.getByTestId('qms-engine-notice-xtb')).toContainText(/completed/);
  });

  test('Run flow shows inline missing-engine guidance panel', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'engine-guidance-demo',
    });

    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qms-calculations-view')).toBeVisible({ timeout: 10000 });

    await appPage.getByTestId('qms-calculation-row').first().click();
    await expect(appPage.getByTestId('qms-btn-run-calculation')).toBeVisible({ timeout: 10000 });

    await setRpcMock(appPage, 'preflight_check', {
      ok: true,
      data: {
        ok: false,
        errors: ['pw.x not found in active engine installation'],
        warnings: [],
      },
    });

    await appPage.getByTestId('qms-btn-run-calculation').click();

    const panel = appPage.getByTestId('qms-missing-engine-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qms-missing-engine-install')).toBeVisible();
    await expect(appPage.getByTestId('qms-missing-engine-configure-path')).toBeVisible();
    await expect(appPage.getByTestId('qms-missing-engine-open-manager')).toBeVisible();
  });

  test('Updater banner appears when update is available', async ({ appPage }) => {
    await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30000 });

    await appPage.evaluate(async () => {
      if ((window as any).qms?.setE2EUpdaterState) {
        await (window as any).qms.setE2EUpdaterState({
          state: 'available',
          version: '1.0.2',
          progress: 0,
          message: 'Update 1.0.2 is ready to download',
        });
      }
    });

    const banner = appPage.getByTestId('qms-updater-banner');
    await expect(banner).toBeVisible({ timeout: 10000 });
    await expect(banner).toContainText('1.0.2');
    await expect(appPage.getByTestId('qms-updater-download')).toBeVisible();
    await expect(appPage.getByTestId('qms-updater-later')).toBeVisible();
  });
});
