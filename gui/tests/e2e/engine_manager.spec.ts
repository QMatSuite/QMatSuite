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
    if ((window as any).qv?.setE2ERpcMock) {
      await (window as any).qv.setE2ERpcMock(methodName, body);
    }
  }, { methodName: method, body: payload });
}

async function clearRpcMocks(page: Page): Promise<void> {
  await page.evaluate(async () => {
    if ((window as any).qv?.clearE2ERpcMocks) {
      await (window as any).qv.clearE2ERpcMocks();
    }
  });
}

test.describe('E2E: Engine Manager + Update UI', () => {
  test.beforeEach(async ({ appPage }) => {
    await clearRpcMocks(appPage);
    await appPage.evaluate(async () => {
      if ((window as any).qv?.setE2EUpdaterState) {
        await (window as any).qv.setE2EUpdaterState({
          state: 'idle',
          version: null,
          progress: 0,
          message: null,
        });
      }
    });
  });

  test('Engine Manager section is visible in Settings', async ({ appPage }) => {
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
    await navigateToView(appPage, 'settings');

    const manager = appPage.getByTestId('qv-engine-manager-section');
    await expect(manager).toBeVisible({ timeout: 20000 });
    await expect(manager.locator('[data-testid^="qv-engine-row-"]').first()).toBeVisible();
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
    await setRpcMock(appPage, 'get_job_status', [
      {
        ok: true,
        data: {
          status: 'running',
          last_log_line: 'Resolving dependencies...',
        },
      },
      {
        ok: true,
        data: {
          status: 'running',
          last_log_line: 'Installing xTB package...',
        },
      },
      {
        ok: true,
        data: {
          status: 'completed',
          last_log_line: 'Install completed',
        },
      },
    ]);

    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });
    await navigateToView(appPage, 'settings');
    await expect(appPage.getByTestId('qv-engine-manager-section')).toBeVisible({ timeout: 10000 });

    await appPage.getByTestId('qv-engine-manager-refresh').click();
    await expect(appPage.getByTestId('qv-engine-install-xtb')).toBeVisible();
    await expect(appPage.getByTestId('qv-engine-configure-path-vasp')).toBeVisible();

    await appPage.getByTestId('qv-engine-install-xtb').click();
    await expect(appPage.getByTestId('qv-engine-progress-xtb')).toBeVisible({ timeout: 10000 });
  });

  test('Run flow shows inline missing-engine guidance panel', async ({ appPage }, testInfo) => {
    testInfo.setTimeout(90 * 1000);

    await createDemoProject(appPage, {
      demoId: 'si_bands_demo',
      projectName: 'engine-guidance-demo',
    });

    await navigateToView(appPage, 'calculations');
    await expect(appPage.getByTestId('qv-calculations-view')).toBeVisible({ timeout: 10000 });

    await appPage.getByTestId('qv-calculation-row').first().click();
    await expect(appPage.getByTestId('qv-btn-run-calculation')).toBeVisible({ timeout: 10000 });

    await setRpcMock(appPage, 'preflight_check', {
      ok: true,
      data: {
        ok: false,
        errors: ['pw.x not found in active engine installation'],
        warnings: [],
      },
    });

    await appPage.getByTestId('qv-btn-run-calculation').click();

    const panel = appPage.getByTestId('qv-missing-engine-panel');
    await expect(panel).toBeVisible({ timeout: 10000 });
    await expect(appPage.getByTestId('qv-missing-engine-install')).toBeVisible();
    await expect(appPage.getByTestId('qv-missing-engine-configure-path')).toBeVisible();
    await expect(appPage.getByTestId('qv-missing-engine-open-manager')).toBeVisible();
  });

  test('Updater banner appears when update is available', async ({ appPage }) => {
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });

    await appPage.evaluate(async () => {
      if ((window as any).qv?.setE2EUpdaterState) {
        await (window as any).qv.setE2EUpdaterState({
          state: 'available',
          version: '1.0.2',
          progress: 0,
          message: 'Update 1.0.2 is ready to download',
        });
      }
    });

    const banner = appPage.getByTestId('qv-updater-banner');
    await expect(banner).toBeVisible({ timeout: 10000 });
    await expect(banner).toContainText('1.0.2');
    await expect(appPage.getByTestId('qv-updater-download')).toBeVisible();
    await expect(appPage.getByTestId('qv-updater-later')).toBeVisible();
  });
});
