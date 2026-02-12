/**
 * Demo Reference Sweep
 *
 * Verifies that demos with ref packs can display reference analysis plots
 * without running any engine. Uses reference-only mode to render pre-computed
 * analysis data (convergence/dos/bands).
 *
 * This test is NOT included in the default `npx playwright test` run.
 * Run explicitly with: npx playwright test --project=integrity -g "Reference Sweep"
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test --project=integrity --reporter=list -g "Reference"
 */

import { electronTest as test, expect } from '../fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { getRepoRoot, ensureE2EProjectsRoot } from '../helpers/paths';

/** Read all demo slugs that have ref packs */
function listRefPackSlugs(): Array<{ slug: string; types: string[] }> {
  const repoRoot = getRepoRoot();
  const refDir = path.join(repoRoot, 'resources', 'demo_projects', 'ref_packs');

  if (!fs.existsSync(refDir)) {
    return [];
  }

  const slugs: Array<{ slug: string; types: string[] }> = [];
  for (const dir of fs.readdirSync(refDir).sort()) {
    const manifestPath = path.join(refDir, dir, 'manifest.json');
    if (!fs.existsSync(manifestPath)) continue;

    try {
      const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
      const types = Object.keys(manifest.object_types || {});
      if (types.length > 0) {
        slugs.push({ slug: dir, types });
      }
    } catch {
      // Skip invalid manifests
    }
  }

  return slugs;
}

const REF_PACK_DEMOS = listRefPackSlugs();

test.describe('Demo Reference Sweep', () => {
  // Allow ample time: ~10s per demo × 27 demos = ~5 minutes
  test.setTimeout(10 * 60 * 1000);

  test('all demos with ref packs show reference analysis plots', async ({ appPage }) => {
    // Wait for the app to be ready
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });

    const repoRoot = getRepoRoot();
    const e2eRoot = ensureE2EProjectsRoot();
    const sweepDir = path.join(e2eRoot, `ref-sweep-${Date.now()}`);
    fs.mkdirSync(sweepDir, { recursive: true });

    type SweepResult = {
      slug: string;
      status: 'PASS' | 'FAIL' | 'SKIP';
      refTypes: string[];
      error?: string;
    };
    const results: SweepResult[] = [];

    for (const { slug, types } of REF_PACK_DEMOS) {
      const projectParent = path.join(sweepDir, slug);
      fs.mkdirSync(projectParent, { recursive: true });

      try {
        // 1. Create demo project via backend RPC
        const createResult = await appPage.evaluate(async ({ targetDir, demoId }) => {
          const qv = (window as any).qv;
          if (!qv?.request) {
            return { ok: false, error: 'qv.request not available' };
          }
          try {
            const response = await qv.request('create_demo_project', {
              target_dir: targetDir,
              name: demoId,
              demo_id: demoId,
            });
            return {
              ok: response.ok,
              project_root: response.data?.project_root,
              error: response.ok ? undefined : (response.error?.message || JSON.stringify(response.error) || 'Unknown error'),
            };
          } catch (e: any) {
            return { ok: false, error: e.message || String(e) };
          }
        }, { targetDir: projectParent, demoId: slug });

        if (!createResult.ok) {
          results.push({ slug, status: 'FAIL', refTypes: types, error: `Create failed: ${createResult.error}` });
          continue;
        }

        // 2. Open the project
        const openResult = await appPage.evaluate(async ({ projectRoot }) => {
          const qv = (window as any).qv;
          try {
            const response = await qv.request('open_project', { project_root: projectRoot });
            return { ok: response.ok, error: response.ok ? undefined : response.error?.message };
          } catch (e: any) {
            return { ok: false, error: e.message || String(e) };
          }
        }, { projectRoot: createResult.project_root });

        if (!openResult.ok) {
          results.push({ slug, status: 'FAIL', refTypes: types, error: `Open failed: ${openResult.error}` });
          continue;
        }

        // 3. Wait for the analysis panel to be available
        // Click the first calculation in the sidebar to select it
        const calcItem = appPage.locator('[data-testid^="qv-calc-item-"]').first();
        await calcItem.click({ timeout: 10000 }).catch(() => {
          // Calculation may already be selected
        });

        // 4. Click the "Plot" tab to switch to analysis view
        const plotTab = appPage.locator('.calculation-analysis-panel__view-mode-tab').filter({ hasText: 'Plot' });
        if (await plotTab.isVisible({ timeout: 5000 }).catch(() => false)) {
          await plotTab.click();
        }

        // 5. Wait for reference-only mode to activate
        // The reference banner should appear when ref data is probed
        const referenceBanner = appPage.getByTestId('qv-analysis-reference-banner');
        const bannerVisible = await referenceBanner.isVisible({ timeout: 15000 }).catch(() => false);

        if (!bannerVisible) {
          results.push({ slug, status: 'FAIL', refTypes: types, error: 'Reference banner not visible' });
          continue;
        }

        // 6. Verify chart has rendered content (SVG path elements)
        const chartContainer = appPage.locator('.analysis-viz__plot');
        const chartVisible = await chartContainer.isVisible({ timeout: 5000 }).catch(() => false);

        if (!chartVisible) {
          results.push({ slug, status: 'FAIL', refTypes: types, error: 'Chart container not visible' });
          continue;
        }

        // Check for SVG paths (line chart data)
        const pathCount = await chartContainer.locator('svg path').count().catch(() => 0);
        if (pathCount === 0) {
          results.push({ slug, status: 'FAIL', refTypes: types, error: 'Chart has no SVG paths (empty plot)' });
          continue;
        }

        results.push({ slug, status: 'PASS', refTypes: types });
      } catch (err: any) {
        results.push({ slug, status: 'FAIL', refTypes: types, error: err.message || String(err) });
      }
    }

    // Generate report
    const passCount = results.filter(r => r.status === 'PASS').length;
    const failCount = results.filter(r => r.status === 'FAIL').length;
    const skipCount = results.filter(r => r.status === 'SKIP').length;

    const reportLines: string[] = [
      '# GUI Demo Reference Sweep Report',
      '',
      `**Date**: ${new Date().toISOString()}`,
      `**Total with ref packs**: ${results.length} demos`,
      `**Pass**: ${passCount} | **Fail**: ${failCount} | **Skip**: ${skipCount}`,
      '',
      '## Results',
      '',
      '| # | Demo Slug | Ref Types | Status | Notes |',
      '|---|-----------|-----------|--------|-------|',
    ];

    results.forEach((r, i) => {
      const typesStr = r.refTypes.join(', ');
      const notes = r.error || '';
      reportLines.push(`| ${i + 1} | ${r.slug} | ${typesStr} | ${r.status} | ${notes} |`);
    });

    reportLines.push('');
    reportLines.push('## Summary');
    reportLines.push('');
    reportLines.push(`- Sweep directory: \`<TMPDIR>/e2e_projects/ref-sweep-*\``);
    reportLines.push(`- Platform: ${process.platform}`);
    reportLines.push(`- Node: ${process.version}`);
    reportLines.push('');

    const reportPath = path.join(repoRoot, 'docs', 'demo_store', 'GUI_E2E_REFERENCE_SWEEP_REPORT.md');
    fs.writeFileSync(reportPath, reportLines.join('\n'));

    // Log summary
    console.log(`\nReference Sweep: ${passCount} PASS, ${failCount} FAIL, ${skipCount} SKIP out of ${results.length}`);
    if (failCount > 0) {
      console.log('\nFailures:');
      results.filter(r => r.status === 'FAIL').forEach(r => {
        console.log(`  ${r.slug}: ${r.error}`);
      });
    }

    // Assert all passed
    expect(failCount, `${failCount} demos failed reference sweep`).toBe(0);
  });
});
