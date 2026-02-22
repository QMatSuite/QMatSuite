# Reference Packs & Demo Expansion Plan

**Status**: In Progress
**Date**: 2026-02-11
**Scope**: Ref pack infrastructure, demo_source field, demo expansion, backend wiring, GUI wiring

## Context

The demo store (Phase 1-5) is complete: 37 demos across 14 engines, translator, corpus index, gate tests all passing. However:

1. **No plot-without-run**: Demo projects materialize but `get_reference_analysis()` (service.py:1122) never works because `create_demo_project()` (service.py:7219) does NOT inject origin/demo_source into materialized project settings.
2. **No reference data**: No pre-computed analysis primitives exist for any demo.
3. **Uneven coverage**: Many engines have only 1-2 demos (target: 3-5).
4. **Legacy generators still on disk**: `tools/demo_generators/` has DEPRECATED.md but scripts remain.
5. **No documentation** of integrity test exclusion rationale or external resource requirements.

This plan addresses all of these via: spec patch, `demo_source` field, ref pack infrastructure, demo expansion, backend refactor, and minimal GUI wiring.

### Hard Constraints
- **C0**: Spec-first — commit spec patch before implementation
- **C1**: No SQLite/CAS/provenance dependency for ref pack lookup — filesystem-only `demo_source` field
- **C2**: Generator determinism (same inputs → same outputs)
- **C3**: Don't break existing tests (`si_bands_demo.yml`, `si_dos_demo.yml` preserved)
- **C4**: Integrity tests excluded from default pytest
- **C5**: Classification by GEN step type (not spec)

---

## Step 0: Closeout Pass (Patch Addendum)

Before expanding, close out the existing migration:

### 0a. Document integrity test exclusion
- **File**: `docs/demo_store/DEMO_STORE_GUIDE.md` — add section explaining WHY integrity tests are excluded from default pytest and CI:
  - They test demo lifecycle (load → materialize → roundtrip) which takes ~30s+
  - Some may require engine binaries or large assets
  - C4 constraint from DEMO_STORE_SPEC.md
  - Mechanism: `pytest_ignore_collect` hook in `tests/conftest.py:16-24`
  - How to run: `python -m pytest tests/integrity/ -v --tb=short`

### 0b. Create Demo Matrix document
- **New file**: `docs/demo_store/DEMO_MATRIX.md`
- Authoritative table of all demos with columns:
  - `demo_slug` | `engine` | `step_type_gen` | `required_engine` | `availability` | `asset_policy` | `has_ref_pack` (initially all "no")
- Generated from `corpus_index.yaml` data (demo_eligible entries only)
- Mark which engines require local install vs. are open-source/bundled

### 0c. Delete legacy generators
- **Delete entire directory**: `tools/demo_generators/` (DEPRECATED.md, migrate_demo_projects.py, verify_demos.py, verified/ subdir)
- These are fully superseded by `tools/demo_store/generate_all.py`
- Verify no imports/references to these files exist elsewhere

---

## Step 1: Spec Patch

### 1a. Add "Reference Packs" section to DEMO_STORE_SPEC.md
- New section S10 (or append to S7) defining:
  - Ref pack = pre-computed `CanonicalPrimitiveBundle.to_dict()` stored as JSON
  - Storage location: `resources/demo_projects/ref_packs/<demo_slug>/`
  - One JSON file per analysis object type: `bands.json`, `dos.json`, `convergence.json`, etc.
  - `manifest.json` per ref pack listing available object types + checksums
  - Generation: `tools/demo_store/generate_ref_packs.py` reads curated outputs, parses via engine output parsers, serializes bundles

### 1b. Add `demo_source` field to project SSOT schema
- New field in `project.qms.yml` → `settings.demo_source`:
  ```yaml
  demo_source:
    demo_id: "vasp_si_scf"          # slug, lookup key
    generator_digest: "abc123..."    # from manifest, for staleness check
    engine: "vasp"                   # engine name
    materialized_at: "2025-..."      # ISO timestamp
  ```
- Written by `create_demo_project()` at materialization time
- Read by `get_reference_analysis()` to locate ref packs
- **No origin/provenance dependency** — pure filesystem field (C1)

---

## Step 2: `demo_source` Infrastructure

### 2a. Modify `create_demo_project()` (service.py:7219)
- After `materialize_project_from_snapshot()`, inject `demo_source` into the materialized project's `project.qms.yml`:
  ```python
  demo_source = {
      "demo_id": demo_id,
      "generator_digest": manifest.get(demo_id, {}).get("sha256", ""),
      "engine": snapshot.project.get("engine", ""),
      "materialized_at": datetime.utcnow().isoformat(),
  }
  # Write to project settings
  project_model.settings["demo_source"] = demo_source
  save_project(project_model, target_dir)
  ```
- **File**: `src/qmatsuite/api/service.py`

### 2b. Refactor `get_reference_analysis()` (service.py:1122)
- Replace `origin.kind == "demo"` check with `settings.demo_source` lookup
- Flow:
  1. Read `project.qms.yml` → `settings.demo_source.demo_id`
  2. Look up ref pack at `resources/demo_projects/ref_packs/<demo_id>/manifest.json`
  3. If ref pack exists for requested object_type, load and return the JSON bundle
  4. Return `None` if no ref pack available
- Remove dependency on `origin` field entirely
- **File**: `src/qmatsuite/api/service.py`

---

## Step 3: Expand Demo Store (3-5 per engine)

### Target demo counts (current → target):

| Engine | Current | Add | New Total | Source |
|--------|---------|-----|-----------|--------|
| QE | 14 | 0 | 14 | Already >5 |
| VASP | 4 | 1 | 5 | si_dos from corpus |
| ABINIT | 2 | 1 | 3 | si_bands from corpus |
| CP2K | 2 | 1 | 3 | h2o_geo_opt from corpus |
| Gaussian | 2 | 1 | 3 | formaldehyde_tddft from corpus |
| LAMMPS | 2 | 1 | 3 | peptide_nvt from corpus |
| ORCA | 3 | 0 | 3 | Already at 3 |
| xTB | 2 | 1 | 3 | caffeine_opt (new corpus) |
| Siesta | 2 | 1 | 3 | si_bands (new corpus) |
| QMCPACK | 1 | 2 | 3 | h2_ae_vmc + lih_solid from corpus |
| Yambo | 1 | 2 | 3 | si_bse + si_optics (new corpus) |
| GPAW | 1 | 2 | 3 | al_scf + si_bands (new direct_snapshot) |
| Psi4 | 1 | 2 | 3 | h2o_opt + ethanol_sp (new direct_snapshot) |
| PySCF | 1 | 2 | 3 | h2o_dft + n2_mp2 (new direct_snapshot) |
| Wannier90 | 0 | 3 | 3 | copper/diamond/silicon (from old demos, create corpus) |

**Total: 37 → ~55 demos** (+18 new)

### Process for each new demo:
1. Mark existing corpus case `demo_eligible: true` (or create new corpus case if needed)
2. Add demo fields to `case.yaml`: `demo_slug`, `asset_policy`, `recommended_analysis`
3. Regenerate `corpus_index.yaml`: `python tools/demo_store/generate_corpus_index.py`
4. Regenerate all demos: `python tools/demo_store/generate_all.py`
5. Update `.generator_manifest.json` checksums

### Wannier90 special handling:
- The 3 old Wannier90 demos (`copper_wannier90_demo.yml`, `diamond_wannier90_demo.yml`, `silicon_wannier90_demo.yml`) were preserved in Phase 3 but don't have corpus entries
- Create `tests/inputformat/samples/w90/{copper,diamond,silicon}/` with `case.yaml` (direct_snapshot or w90 input files)
- Mark demo_eligible and regenerate

---

## Step 4: Ref Pack Infrastructure

### 4a. Ref pack storage layout
```
resources/demo_projects/ref_packs/
    <demo_slug>/
        manifest.json        # {object_types: {bands: {sha256, file}, dos: {...}}, engine, demo_slug}
        bands.json           # CanonicalPrimitiveBundle.to_dict()
        dos.json
        convergence.json
        ...
```

### 4b. Create ref pack generator
- **New file**: `tools/demo_store/generate_ref_packs.py`
- For each demo with curated output files:
  1. Locate output fixtures (golden refs in `tests/inputformat/samples/<engine>/<case>/` or `tests/data/`)
  2. Run engine output parser: `EngineOutputParser.parse()` → analysis primitives
  3. Serialize each `CanonicalPrimitiveBundle.to_dict()` → JSON
  4. Write manifest with SHA256 checksums
- **Engines with output parsers** (12): QE, VASP, ABINIT, CP2K, Gaussian, LAMMPS, ORCA, Siesta, xTB, QMCPACK, Yambo, Wannier90
- **Engines without output parsers** (3): GPAW, Psi4, PySCF — skip ref packs initially

### 4c. Ref pack availability
- Only demos with curated golden output files can have ref packs
- Initially target ref packs for: QE si_scf (convergence), VASP si_scf (convergence), VASP si_bands (bands), a few ORCA/ABINIT cases
- This is incremental — ref packs grow as golden output fixtures are added

### 4d. Gate test for ref packs
- **New file**: `tests/gates/test_ref_packs.py`
- Verify: every ref pack has valid manifest, every JSON is loadable via `CanonicalPrimitiveBundle.from_dict()`, SHA256 matches

---

## Step 5: Backend Service Wiring

### 5a. Ref pack loader utility
- **New file**: `src/qmatsuite/demo_store/ref_packs.py`
- `load_ref_pack(demo_id: str, object_type: str) -> dict | None`
  - Reads `resources/demo_projects/ref_packs/<demo_id>/manifest.json`
  - If object_type present, reads and returns the JSON bundle
  - Returns None otherwise
- `list_ref_pack_types(demo_id: str) -> list[str]`
  - Returns available analysis types for a demo

### 5b. Wire into get_reference_analysis()
- Use `demo_source.demo_id` → `load_ref_pack(demo_id, object_type)`
- Return loaded bundle as `PrimitiveBundleData` for the GUI
- **File**: `src/qmatsuite/api/service.py`

---

## Step 6: Minimal GUI Wiring

### 6a. CalculationAnalysisPanel reference data
- **File**: `gui/src/components/CalculationAnalysisPanel.tsx`
- When `demo_source` is present in project settings:
  - Show "Reference data available" indicator
  - On analysis tab, offer "Show reference" toggle
  - When toggled, call `get_reference_analysis(project_root, calc_ulid, object_type)`
  - Overlay ref data on existing AnalysisVizPanel plots
- This is MINIMAL: just the data fetch and overlay, no new visualization components

### 6b. No new RPC endpoints needed
- `get_reference_analysis()` already exists as an RPC endpoint
- Just needs the backend fixes from Step 2b + 5b to actually return data

---

## Critical Files

| File | Action |
|------|--------|
| `docs/spec/DEMO_STORE_SPEC.md` | Add S10 (ref packs) + demo_source field |
| `docs/demo_store/DEMO_STORE_GUIDE.md` | Add integrity exclusion docs |
| `docs/demo_store/DEMO_MATRIX.md` | NEW — authoritative demo matrix |
| `tools/demo_generators/` | DELETE entire directory |
| `tools/demo_store/generate_ref_packs.py` | NEW — ref pack generator |
| `src/qmatsuite/api/service.py` | Modify create_demo_project + get_reference_analysis |
| `src/qmatsuite/demo_store/ref_packs.py` | NEW — ref pack loader |
| `src/qmatsuite/core/analysis/bundles.py` | READ ONLY — reuse to_dict/from_dict |
| `tests/gates/test_ref_packs.py` | NEW — ref pack gate test |
| `resources/demo_projects/ref_packs/` | NEW directory — ref pack storage |
| `tests/inputformat/samples/corpus_index.yaml` | Update with new demo entries |
| `resources/demo_projects/*.yml` | ~18 new demos |
| `resources/demo_projects/.generator_manifest.json` | Updated checksums |

---

## Execution Order

```
Step 0 (closeout)  ─────────────────────────→ commit
Step 1 (spec patch) ────────────────────────→ commit (C0: spec first)
Step 2 (demo_source infra) ─┐
Step 3 (expand demos)       ├──────────────→ commit
Step 4 (ref pack infra)     ┘
Step 5 (backend wiring) ───────────────────→ commit
Step 6 (GUI wiring) ──────────────────────→ commit
```

Steps 2-4 are parallelizable in implementation but share a commit.

---

## Verification

1. **Existing tests green**: `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
2. **Gate tests pass**: `python -m pytest tests/gates/ -v` (includes new test_ref_packs.py)
3. **Demo regeneration idempotent**: `python tools/demo_store/generate_all.py` produces no diff
4. **Ref pack generation**: `python tools/demo_store/generate_ref_packs.py` produces valid packs
5. **Integrity tests**: `python -m pytest tests/integrity/ -v --tb=short`
6. **Manual verification**:
   - `si_bands_demo.yml` and `si_dos_demo.yml` still exist (C3)
   - `tools/demo_generators/` deleted
   - `docs/demo_store/DEMO_MATRIX.md` exists with all demos listed
   - ~55 total demos in `resources/demo_projects/`
   - `demo_source` field written to project.qms.yml when creating demo project
   - `get_reference_analysis()` returns ref pack data for demos that have them
