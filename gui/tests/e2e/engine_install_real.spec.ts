/**
 * Real xTB engine install/uninstall E2E test
 *
 * Exercises the full install → verify → uninstall → verify pipeline
 * through the Electron UI against the real daemon (no mocks).
 *
 * Isolation:
 *  - QMATSUITE_HOME → fresh temp dir (isolated registry + install prefix)
 *  - PATH filtered to remove dirs containing an existing `xtb` binary,
 *    so the engine manager sees xTB as "not installed" and shows the
 *    Install button.
 *
 * Both env vars are set in test.beforeAll (NOT module-level — module-level
 * side effects would poison the entire Playwright process during test
 * discovery) and restored in test.afterAll.
 *
 * Requires network access (conda-forge download).
 */

import * as fs from 'fs';
import * as os from 'os';
import * as path from 'path';

import { electronTest as test, expect, navigateToView } from './fixtures/electronTest';

const xtbBinaryName = os.platform() === 'win32' ? 'xtb.exe' : 'xtb';

// Saved originals — written by beforeAll, read by afterAll
let origPath: string;
let tmpHome: string;

test.describe('E2E: Real xTB Install / Uninstall', () => {

  test.beforeAll(() => {
    origPath = process.env.PATH || '';

    // 1. Fresh QMATSUITE_HOME so the daemon uses an empty engine registry
    tmpHome = fs.mkdtempSync(path.join(os.tmpdir(), 'qms-e2e-real-'));
    process.env.QMATSUITE_HOME = tmpHome;

    // 2. Remove directories that contain an `xtb` binary from PATH so the
    //    daemon's system-PATH scan doesn't find a pre-existing install.
    process.env.PATH = origPath
      .split(path.delimiter)
      .filter((dir) => {
        try {
          return !fs.existsSync(path.join(dir, xtbBinaryName));
        } catch {
          return true;
        }
      })
      .join(path.delimiter);
  });

  test.afterAll(() => {
    // Restore env but keep temp dir for post-failure inspection
    process.env.PATH = origPath;
    delete process.env.QMATSUITE_HOME;
  });

  test('Install xTB via conda, verify binary, uninstall, verify removal', async ({ appPage }, testInfo) => {
    // Real conda install: micromamba bootstrap + package download
    testInfo.setTimeout(3 * 60 * 1000);

    // ── 1. Wait for app ready ───────────────────────────────────────────
    await expect(appPage.getByTestId('qms-welcome-title')).toBeVisible({ timeout: 30_000 });

    // ── 2. Navigate to Settings → Engine Manager ────────────────────────
    await navigateToView(appPage, 'settings');
    const manager = appPage.getByTestId('qms-engine-manager-section');
    await expect(manager).toBeVisible({ timeout: 20_000 });

    // ── 3. Scroll xTB row into view (it's near the bottom of the list) ──
    const xtbRow = appPage.getByTestId('qms-engine-row-xtb');
    await xtbRow.scrollIntoViewIfNeeded();
    await expect(xtbRow).toBeVisible({ timeout: 10_000 });

    // Install button should be present (xTB not installed)
    const installBtn = appPage.getByTestId('qms-engine-install-xtb');
    await expect(installBtn).toBeVisible({ timeout: 5_000 });

    // Uninstall button should NOT be visible
    await expect(appPage.getByTestId('qms-engine-uninstall-xtb')).not.toBeVisible();

    // ── 4. Click Install ────────────────────────────────────────────────
    await installBtn.click();

    // ── 5. Assert progress bar appears ──────────────────────────────────
    const progress = appPage.getByTestId('qms-engine-progress-xtb');
    await expect(progress).toBeVisible({ timeout: 15_000 });
    await expect(progress.locator('.engine-progress-bar')).toBeVisible();

    // Stage text should eventually become non-empty (don't assert specific text)
    await expect(progress.locator('.engine-progress-info__stage')).not.toBeEmpty({ timeout: 30_000 });

    // ── 6. Wait for progress bar to disappear (install complete) ────────
    await expect(progress).not.toBeVisible({ timeout: 150_000 });

    // ── 7. Assert success notice ────────────────────────────────────────
    const notice = appPage.getByTestId('qms-engine-notice-xtb');
    await expect(notice).toBeVisible({ timeout: 10_000 });

    // ── 8. Scroll back to xTB row and assert button state ───────────────
    await xtbRow.scrollIntoViewIfNeeded();
    await expect(appPage.getByTestId('qms-engine-uninstall-xtb')).toBeVisible({ timeout: 10_000 });
    await expect(appPage.getByTestId('qms-engine-install-xtb')).not.toBeVisible();

    // ── 9. Verify binary on disk via RPC ────────────────────────────────
    const engineList = await appPage.evaluate(async () => {
      const qms = (window as any).qms;
      if (!qms?.request) return null;
      const resp = await qms.request('engine.list', {});
      return resp?.data ?? resp;
    });

    // Extract xTB installation path from the engine list response
    let xtbInstallPath: string | null = null;
    if (engineList?.engines) {
      for (const eng of engineList.engines) {
        if (eng.engine === 'xtb' && eng.installed) {
          xtbInstallPath = eng.active?.path
            ?? eng.installations?.[0]?.path
            ?? null;
          break;
        }
      }
    }

    // Verify binary exists and is executable
    if (xtbInstallPath) {
      const binaryPath = path.join(xtbInstallPath, xtbBinaryName);
      expect(fs.existsSync(binaryPath)).toBe(true);

      // Check executable permission (skip on Windows — always true)
      if (os.platform() !== 'win32') {
        expect(() => fs.accessSync(binaryPath, fs.constants.X_OK)).not.toThrow();
      }
    }

    // ── 10. Uninstall xTB ───────────────────────────────────────────────
    // Auto-accept the window.confirm() dialog
    appPage.on('dialog', async (dialog) => {
      await dialog.accept();
    });

    await appPage.getByTestId('qms-engine-uninstall-xtb').click();

    // ── 11. Wait for Install button to reappear (uninstall complete) ────
    await expect(appPage.getByTestId('qms-engine-install-xtb')).toBeVisible({ timeout: 30_000 });
    await expect(appPage.getByTestId('qms-engine-uninstall-xtb')).not.toBeVisible();

    // ── 12. Verify binary removed from disk ─────────────────────────────
    if (xtbInstallPath) {
      const binaryPath = path.join(xtbInstallPath, xtbBinaryName);
      expect(fs.existsSync(binaryPath)).toBe(false);
    }

    // ── 13. RPC confirms xTB no longer installed ────────────────────────
    const afterList = await appPage.evaluate(async () => {
      const qms = (window as any).qms;
      if (!qms?.request) return null;
      const resp = await qms.request('engine.list', {});
      return resp?.data ?? resp;
    });

    if (afterList?.engines) {
      const xtbEntry = afterList.engines.find((e: any) => e.engine === 'xtb');
      expect(xtbEntry?.installed).toBe(false);
    }
  });
});
