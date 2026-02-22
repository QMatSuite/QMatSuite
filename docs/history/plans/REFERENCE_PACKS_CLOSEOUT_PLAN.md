# Reference Packs Closeout Plan

## Context

The previous demo store closeout (G1, G4, G10, G8) is done: 57 demos across 15 engines materialize correctly, 11 ref packs exist (convergence-only, scf_digest format), and the GUI integrity sweep passes 57/57.

**Problem**: The user wants to upgrade so that "open demo -> plot reference without running" is truly verified by GUI e2e. Currently:
1. Ref packs contain **scf_digest dicts** (engine-specific, not chart-renderable)
2. Only 11/57 demos have ref packs
3. The GUI "Reference" checkbox exists but **visualization is not wired** — `referenceData` is fetched but never passed to chart components
4. No e2e test verifies that reference data actually renders

**Goal**: Expand ref packs to cover ~25-30 demos in chart-renderable format, wire GUI reference rendering, and verify via e2e that reference plots are non-empty.

---

## Step 1: Upgrade Ref Pack Format & Expand Coverage

### Problem
Current ref packs store `scf_digest.to_dict()` (flat key-value like `{total_energy, converged, ...}`). The frontend charts need `CanonicalPrimitiveBundle.to_dict()` format (has `series`, `render_meta`, `provenance_meta`).

### Key Architecture Insight
All analysis providers follow the same pattern:
```
Provider.parse(evidence: EvidenceBundle) -> AnalysisObject (Convergence|DOS|BandStructure|...)
AnalysisObject.to_primitives() -> CanonicalPrimitiveBundle
CanonicalPrimitiveBundle.to_dict() -> dict (JSON-serializable, chart-ready)
```

### Available Providers & Golden Dirs

**Convergence** (5 engines): VASP, QE, ABINIT, Siesta, CP2K
- VASP: `tests/data/analysis_vasp_convergence/` (OSZICAR)
- QE: `tests/data/analysis_scf/` (si.0_scf.out), `tests/data/calculation_bands/reference_out/`
- ABINIT: `tests/data/analysis_abinit_dos/` (si_dos.abo)
- Siesta: `tests/data/analysis_siesta_dos/` (si_dos.out)
- CP2K: `tests/data/analysis_cp2k_dos/` (si_dos.out)

**DOS** (6 engines): VASP, QE, ABINIT, Siesta, CP2K, GPAW
- VASP: `tests/data/analysis_vasp_dos/` (DOSCAR, vasprun.xml, POSCAR)
- QE: `tests/data/analysis_qe_dos/` (si.dos.dat)
- ABINIT: `tests/data/analysis_abinit_dos/` (si_doso_DS2_DOS, etc.)
- Siesta: `tests/data/analysis_siesta_dos/` (si_dos.DOS)
- CP2K: `tests/data/analysis_cp2k_dos/` (si_dos-k1-1.pdos)
- GPAW: `tests/data/analysis_gpaw_dos/` (dos.json)

**Bands** (6 engines): VASP, QE, ABINIT, Siesta, CP2K, GPAW
- VASP: `tests/data/analysis_vasp_bands/` (EIGENVAL, KPOINTS, POSCAR, vasprun.xml)
- QE: `tests/data/analysis_bands/` (si.bands.dat.gnu, etc.)
- ABINIT: `tests/data/analysis_abinit_bands/` (si_bands_fixedo_DS2_EIG)
- Siesta: `tests/data/analysis_siesta_bands/` (si_bands.EIG)
- CP2K: `tests/data/analysis_cp2k_bands/` (si_bands.bs)
- GPAW: `tests/data/analysis_gpaw_bands/` (bandstructure.json)

### Demo-to-RefPack Mapping (target ~25-30)

Each demo gets ONE ref pack matching its `recommended_analysis`:

| Demo Slug | Engine | Rec Analysis | Ref Pack Type | Golden Dir |
|-----------|--------|-------------|---------------|------------|
| vasp_si_scf | vasp | scf | convergence | analysis_vasp_convergence |
| vasp_si_bands | vasp | bands | bands | analysis_vasp_bands |
| vasp_si_dos | vasp | dos | dos | analysis_vasp_dos |
| vasp_si_relax | vasp | scf | convergence | analysis_vasp_convergence |
| vasp_fe_magnetic | vasp | scf | convergence | analysis_vasp_convergence |
| qe_si_scf | qe | scf | convergence | analysis_scf |
| qe_al_dos | qe | dos | dos | analysis_qe_dos |
| qe_fe_dos | qe | dos | dos | analysis_qe_dos |
| qe_graphene_bands | qe | bands | bands | analysis_bands |
| qe_si_bands_alt | qe | bands | bands | analysis_bands |
| qe_si_dos_alt | qe | dos | dos | analysis_qe_dos |
| qe_si_vc_relax | qe | scf | convergence | analysis_scf |
| qe_si_bulk_modulus | qe | energy | convergence | analysis_scf |
| qe_si_phonon | qe | scf | convergence | analysis_scf |
| qe_nmr_gipaw | qe | scf | convergence | analysis_scf |
| si_bands_demo | qe | bands | bands | analysis_bands |
| si_dos_demo | qe | dos | dos | analysis_qe_dos |
| abinit_si_scf | abinit | scf | convergence | analysis_abinit_dos |
| abinit_si_bands | abinit | bands | bands | analysis_abinit_bands |
| abinit_si_relax | abinit | scf | convergence | analysis_abinit_dos |
| siesta_si_scf | siesta | scf | convergence | analysis_siesta_dos |
| siesta_si_bands | siesta | bands | bands | analysis_siesta_bands |
| siesta_si_relax | siesta | scf | convergence | analysis_siesta_dos |
| cp2k_h2o_energy | cp2k | energy | convergence | analysis_cp2k_dos |
| cp2k_h2o_geo_opt | cp2k | scf | convergence | analysis_cp2k_dos |
| cp2k_si_relax | cp2k | scf | convergence | analysis_cp2k_dos |
| gpaw_si_bands | gpaw | bands | bands | analysis_gpaw_bands |

**Excluded (no provider or no golden data, ~30 demos):**
- Gaussian (3): no convergence/dos/bands provider
- LAMMPS (3): no convergence provider, trajectory only
- ORCA (3): no convergence/dos/bands provider
- xTB (3): no convergence provider
- GPAW al_scf, si_scf (2): no convergence provider
- Psi4 (3): Python-script engine, no providers
- PySCF (3): Python-script engine, no providers
- QMCPACK (3): no chart-renderable provider
- W90 (3): no bands provider (field3d only)
- Yambo (3): no chart-renderable provider
- qe_si_cpmd (1): trajectory type, skip for now

### Files to Modify

- **REWRITE**: `tools/demo_store/generate_ref_packs.py`
  - Replace `_try_parse_scf_digest()` with `_try_parse_bundle()` that uses analysis providers
  - Construct minimal `EvidenceBundle(primary_raw_dir=golden_dir, calc_dir=golden_dir, ...)`
  - Call `provider.parse(evidence).to_primitives().to_dict()`
  - Update `GOLDEN_OUTPUT_MAP` with new entries including `provider_type` (convergence/dos/bands)
  - Bump `GENERATOR_VERSION` to "2.0.0"

- **Regenerate**: `resources/demo_projects/ref_packs/<slug>/` — all packs in new format

### Implementation
1. Rewrite `generate_ref_packs.py` to use analysis providers + EvidenceBundle
2. Expand `GOLDEN_OUTPUT_MAP` to ~27 entries with provider type
3. Run generator: `python tools/demo_store/generate_ref_packs.py`
4. Verify: `python -m pytest tests/gates/test_ref_packs.py -v`
5. Debug any provider parse failures (some golden dirs may lack required files)

---

## Step 2: Wire GUI Reference Rendering

### Problem
`CalculationAnalysisPanel.tsx` fetches `referenceData` via `get_reference_analysis` RPC but:
1. `referenceData` is never passed to child components (AnalysisVizPanel, etc.)
2. When there's no run (no engine executed), `availableObjectTypes` stays empty, so no analysis panel renders
3. The reference data is in the wrong format (old scf_digest, not PrimitiveBundleData)

### Design: Reference-Only Mode
When a demo project has ref packs but no run data:
1. Detect "no run available" state (runInfo is null or has no run_ulid)
2. Probe for available reference types by calling `get_reference_analysis` for each ANALYSIS_OBJECT_TYPE
3. Populate `availableObjectTypes` from reference types
4. Auto-enable `showReference = true`
5. Render reference bundle data using the SAME chart components (AnalysisVizPanel)

### Files to Modify

- **MODIFY**: `gui/src/components/panels/CalculationAnalysisPanel.tsx`
  - Add `useEffect` for "reference-only mode": when no run_ulid, probe for reference types
  - When `showReference && referenceData`, pass `referenceData` as the `bundle` to AnalysisVizPanel
  - Add `data-testid="qms-analysis-reference-banner"` when showing reference data
  - The reference data (now in PrimitiveBundleData format from Step 1) has `series`, `render_meta` — directly usable

- **MODIFY**: `src/qmatsuite/api/service.py` (lines 1122-1175)
  - `get_reference_analysis()` already returns the raw ref pack dict
  - With Step 1's new format, this dict IS in PrimitiveBundleData format
  - Wrap it with `{bundle: data, object_type: analysis_type, _is_reference: true}` to match the `AnalysisResponse` shape the frontend expects

- **MODIFY**: `src/qmatsuite/daemon/server.py` (lines 4639-4678)
  - No changes needed — it just passes through to service

### Frontend Data Flow (after changes)
```
No run → probe ANALYSIS_OBJECT_TYPES via get_reference_analysis
→ matched types populate availableObjectTypes
→ user sees analysis type tabs (convergence/dos/bands)
→ selectedObjectType triggers referenceData fetch
→ referenceData has {bundle: {series, render_meta, ...}, _is_reference: true}
→ AnalysisVizPanel receives bundle → renders chart
```

---

## Step 3: GUI E2E Reference Sweep Test

### Requirements (from user)
- R1: Materialize demos into `<repo>/.tmp/e2e_projects/demo-ref-sweep/`, clean at start, preserve at end
- R2: For demos with ref packs, navigate to analysis panel, enable Reference view, assert plotted data is NON-EMPTY
- R4: Run full sweep locally, debug until clean

### Files to Create/Modify

- **CREATE**: `gui/tests/e2e/integrity/ref_sweep.spec.ts`
  - Read `resources/demo_projects/ref_packs/` to get list of demos with ref packs
  - For each demo with a ref pack:
    1. Create demo project via `qms.request('create_demo_project', {target_dir, demo_id})`
    2. Open the project via `qms.request('open_project', {project_root})`
    3. Navigate to analysis panel (click first calculation, click "Plot" tab)
    4. Wait for reference-only mode to activate (reference types probed)
    5. Assert `data-testid="qms-analysis-reference-banner"` is visible
    6. Assert chart container `data-testid="qms-analysis-{type}-chart"` has at least one `<path>` element (SVG line)
  - For demos WITHOUT ref packs: only assert materialization (like existing integrity sweep)
  - Generate `docs/demo_store/GUI_E2E_REFERENCE_SWEEP_REPORT.md`

- **MODIFY**: `gui/playwright.config.ts`
  - Add "ref-sweep" project under integrity/ (same testDir as integrity, filtered by test name)
  - OR: add the ref sweep test to the existing integrity/ folder alongside demo_sweep.spec.ts

### E2E Test Architecture
```typescript
// Pseudocode
const DEMOS_WITH_REF_PACKS = readRefPackSlugs(); // from resources/demo_projects/ref_packs/*/manifest.json
const ALL_DEMOS = readAllDemoSlugs();             // from resources/demo_projects/*.yml

test('reference sweep', async ({ appPage }) => {
  const sweepDir = path.join(repoRoot, '.tmp', 'e2e_projects', 'demo-ref-sweep');
  rmSync(sweepDir); mkdirSync(sweepDir);

  for (const slug of ALL_DEMOS) {
    // 1. Materialize
    const result = await appPage.evaluate(/* create_demo_project RPC */);
    expect(result.ok).toBe(true);

    if (DEMOS_WITH_REF_PACKS.includes(slug)) {
      // 2. Open project
      await appPage.evaluate(/* open_project RPC */);

      // 3. Navigate to analysis
      await appPage.getByTestId('qms-analysis-step-tab-scf').click(); // or first tab
      await appPage.locator('[data-testid^="qms-analysis-"][data-testid$="-tab--active"]').click();

      // 4. Assert reference banner
      await expect(appPage.getByTestId('qms-analysis-reference-banner')).toBeVisible({ timeout: 10000 });

      // 5. Assert chart has data
      const chartLocator = appPage.locator('[data-testid^="qms-analysis-"][data-testid$="-chart"]');
      await expect(chartLocator).toBeVisible({ timeout: 10000 });
      const pathCount = await chartLocator.locator('path').count();
      expect(pathCount).toBeGreaterThan(0);
    }

    results.push({ slug, status: 'PASS', hasRefPack: DEMOS_WITH_REF_PACKS.includes(slug) });
  }
});
```

---

## Step 4: Reporting

- **CREATE**: `docs/demo_store/GUI_E2E_REFERENCE_SWEEP_REPORT.md`
  - Per-demo table: slug | engine | has_ref_pack | ref_type | status | notes
  - Summary: total, pass, fail, skip, with_ref_pack, without_ref_pack
  - Generated automatically by the sweep test

- **UPDATE**: `docs/demo_store/DEMO_MATRIX.md`
  - Update `has_ref_pack` column with accurate values

---

## Execution Order

```
Step 1: Upgrade ref pack format + expand coverage    (~27 ref packs)
Step 2: Wire GUI reference rendering                 (frontend + backend)
Step 3: Write e2e ref sweep test                     (playwright)
Step 4: Run sweep, debug failures, generate report   (iterate)
Final:  pytest + tsc + playwright verification
```

---

## Verification Checklist

1. `python tools/demo_store/generate_ref_packs.py` produces >=25 ref packs
2. Each ref pack contains PrimitiveBundleData-format JSON (has `series`, `render_meta`)
3. `python -m pytest tests/gates/test_ref_packs.py -v` — all pass
4. `cd gui && npx tsc --noEmit` — clean
5. Open a demo (e.g., vasp_si_scf) in GUI -> analysis panel shows reference chart without running
6. `cd gui && npm run test:e2e` — existing tests still pass
7. `cd gui && npx playwright test --project=integrity` — 57/57 pass (existing integrity)
8. Ref sweep: all demos with ref packs show non-empty reference plots
9. `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile` — 5320+ passed
10. `docs/demo_store/GUI_E2E_REFERENCE_SWEEP_REPORT.md` exists with full matrix
11. `docs/demo_store/DEMO_MATRIX.md` updated with accurate has_ref_pack values

---

## Critical Files Summary

### Python (Backend)
- `tools/demo_store/generate_ref_packs.py` — REWRITE: use analysis providers
- `src/qmatsuite/api/service.py:1122-1175` — MODIFY: wrap ref pack in bundle format
- `src/qmatsuite/demo_store/ref_packs.py` — READ-ONLY (loader, no changes)
- `src/qmatsuite/core/analysis/evidence.py` — REUSE: EvidenceBundle dataclass
- `src/qmatsuite/core/analysis/bundles.py` — REUSE: CanonicalPrimitiveBundle.to_dict()
- `src/qmatsuite/core/analysis/convergence/model.py` — REUSE: Convergence.to_primitives()
- `src/qmatsuite/core/analysis/dos/model.py` — REUSE: DOS.to_primitives()
- `src/qmatsuite/core/analysis/band_structure/model.py` — REUSE: BandStructure.to_primitives()
- `src/qmatsuite/parsers/registry.py` — REUSE: get_parser(engine, object_type)

### TypeScript (Frontend)
- `gui/src/components/panels/CalculationAnalysisPanel.tsx` — MODIFY: reference-only mode
- `gui/tests/e2e/integrity/ref_sweep.spec.ts` — CREATE: reference sweep test
- `gui/playwright.config.ts` — POSSIBLY MODIFY: if separate project needed

### Docs
- `docs/demo_store/GUI_E2E_REFERENCE_SWEEP_REPORT.md` — CREATE: auto-generated
- `docs/demo_store/DEMO_MATRIX.md` — UPDATE: has_ref_pack column
- `docs/demo_store/REFERENCE_PACKS_CLOSEOUT_PLAN.md` — CREATE: this plan
