/**
 * Demo Store Integrity Sweep
 *
 * Verifies that ALL demo projects can be created and materialized correctly.
 * Uses a single Electron instance and calls the backend RPC directly to avoid
 * per-demo UI overhead.
 *
 * This test is NOT included in the default `npx playwright test` run.
 * Run explicitly with: npx playwright test --project=integrity
 *
 * To run locally:
 *   cd gui
 *   npm run build:e2e
 *   npx playwright test --project=integrity --reporter=list
 */

import { electronTest as test, expect } from '../fixtures/electronTest';
import * as fs from 'fs';
import * as path from 'path';
import { getRepoRoot, ensureE2EProjectsRoot } from '../helpers/paths';

// Read all demo slugs from resources/demo_projects/*.yml
function listDemoSlugs(): string[] {
  const repoRoot = getRepoRoot();
  const demoDir = path.join(repoRoot, 'resources', 'demo_projects');

  if (!fs.existsSync(demoDir)) {
    return [];
  }

  return fs.readdirSync(demoDir)
    .filter(f => f.endsWith('.yml') && !f.startsWith('.'))
    .map(f => f.replace(/\.yml$/, ''))
    .sort();
}

const DEMO_SLUGS = listDemoSlugs();

test.describe('Demo Store Integrity Sweep', () => {
  // Allow ample time: ~5s per demo × 57 demos = ~5 minutes
  test.setTimeout(10 * 60 * 1000);

  test('all demos can be materialized via backend RPC', async ({ appPage }) => {
    // Wait for the app to be ready
    await expect(appPage.getByTestId('qv-welcome-title')).toBeVisible({ timeout: 30000 });

    const repoRoot = getRepoRoot();
    const e2eRoot = ensureE2EProjectsRoot();
    const sweepDir = path.join(e2eRoot, `integrity-sweep-${Date.now()}`);
    fs.mkdirSync(sweepDir, { recursive: true });

    const results: Array<{ slug: string; status: 'PASS' | 'FAIL' | 'SKIP'; error?: string }> = [];

    for (const slug of DEMO_SLUGS) {
      const projectParent = path.join(sweepDir, slug);
      fs.mkdirSync(projectParent, { recursive: true });

      try {
        // Call backend RPC to create demo project via preload API (qv.request)
        const result = await appPage.evaluate(async ({ targetDir, demoId }) => {
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

        if (!result.ok) {
          results.push({ slug, status: 'FAIL', error: result.error });
          continue;
        }

        // Verify project files exist
        const projectRoot = result.project_root;
        if (!projectRoot || !fs.existsSync(projectRoot)) {
          results.push({ slug, status: 'FAIL', error: 'project_root does not exist' });
          continue;
        }

        // Check project.qv.yml exists
        const projectYml = path.join(projectRoot, 'project.qv.yml');
        if (!fs.existsSync(projectYml)) {
          results.push({ slug, status: 'FAIL', error: 'project.qv.yml missing' });
          continue;
        }

        // Check calculation.yaml exists under calculations/<name>/
        const calcsDir = path.join(projectRoot, 'calculations');
        let hasCalcYaml = false;
        if (fs.existsSync(calcsDir) && fs.statSync(calcsDir).isDirectory()) {
          const calcSubdirs = fs.readdirSync(calcsDir).filter(d => {
            const fullPath = path.join(calcsDir, d);
            return fs.statSync(fullPath).isDirectory();
          });
          for (const dir of calcSubdirs) {
            const calcYaml = path.join(calcsDir, dir, 'calculation.yaml');
            if (fs.existsSync(calcYaml)) {
              hasCalcYaml = true;
              break;
            }
          }
        }

        if (!hasCalcYaml) {
          results.push({ slug, status: 'FAIL', error: 'no calculation.yaml found' });
          continue;
        }

        // Check demo_source in project.qv.yml
        const projectContent = fs.readFileSync(projectYml, 'utf-8');
        if (!projectContent.includes('demo_source')) {
          results.push({ slug, status: 'FAIL', error: 'demo_source missing from project.qv.yml' });
          continue;
        }

        results.push({ slug, status: 'PASS' });
      } catch (err: any) {
        results.push({ slug, status: 'FAIL', error: err.message || String(err) });
      }
    }

    // Generate report
    const passCount = results.filter(r => r.status === 'PASS').length;
    const failCount = results.filter(r => r.status === 'FAIL').length;
    const skipCount = results.filter(r => r.status === 'SKIP').length;

    // Write report to docs
    const reportLines: string[] = [
      '# GUI Demo Integrity Sweep Report',
      '',
      `**Date**: ${new Date().toISOString()}`,
      `**Total**: ${results.length} demos`,
      `**Pass**: ${passCount} | **Fail**: ${failCount} | **Skip**: ${skipCount}`,
      '',
      '## Results',
      '',
      '| # | Demo Slug | Engine | Status | Notes |',
      '|---|-----------|--------|--------|-------|',
    ];

    results.forEach((r, i) => {
      // Extract engine from slug (first part before underscore, but some are like si_bands_demo)
      const engine = r.slug.split('_')[0];
      const statusEmoji = r.status === 'PASS' ? 'PASS' : r.status === 'FAIL' ? 'FAIL' : 'SKIP';
      const notes = r.error || '';
      reportLines.push(`| ${i + 1} | ${r.slug} | ${engine} | ${statusEmoji} | ${notes} |`);
    });

    reportLines.push('');
    reportLines.push(`## Summary`);
    reportLines.push('');
    reportLines.push(`- Sweep directory: \`<TMPDIR>/e2e_projects/integrity-sweep-*\``);
    reportLines.push(`- Platform: ${process.platform}`);
    reportLines.push(`- Node: ${process.version}`);
    reportLines.push('');

    const reportPath = path.join(repoRoot, 'docs', 'demo_store', 'GUI_E2E_INTEGRITY_REPORT.md');
    fs.writeFileSync(reportPath, reportLines.join('\n'));

    // Log summary
    console.log(`\nIntegrity Sweep: ${passCount} PASS, ${failCount} FAIL, ${skipCount} SKIP out of ${results.length}`);
    if (failCount > 0) {
      console.log('\nFailures:');
      results.filter(r => r.status === 'FAIL').forEach(r => {
        console.log(`  ${r.slug}: ${r.error}`);
      });
    }

    // Assert all passed
    expect(failCount, `${failCount} demos failed integrity check`).toBe(0);
  });
});
