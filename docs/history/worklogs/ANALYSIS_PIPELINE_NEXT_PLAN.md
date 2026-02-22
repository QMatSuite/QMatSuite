# Analysis Pipeline — Next Implementation Plan

**Author:** Claude Opus 4.6
**Date:** 2026-02-08
**Prerequisite:** `ANALYSIS_PIPELINE_ACCEPTANCE_REVIEW.md` (same directory)
**Spec Reference:** `ANALYSIS_OBJECT_PRIMITIVES_SPEC.md` v1.4 (BINDING)

---

## Overview

This plan covers three sections of work to bring the analysis pipeline from kernel-only prototype to production-ready:

1. **Gap Closure** — Fix broken parser registration, add missing gate tests
2. **Mainline A: Provenance Eager Write + API Wiring** — End-of-run eager pipeline, CAS persistence, API endpoints
3. **Mainline B: GUI Wiring** — Three GUI surfaces (raw viewer, digest, analysis viz)

Each step has a verification command. All steps are mechanical and deterministic.

---

## Section 1: Gap Closure

These steps fix issues discovered in the Acceptance Review. Must be completed before Mainline A.

### Step G1: Fix QE Parser Registration Chain

**Problem:** `src/qmatsuite/drivers/qe/parsers/__init__.py` does not exist. `@register_parser` decorators in `bands.py` and `trajectory.py` never fire at runtime.

**Actions:**
1. Create `src/qmatsuite/drivers/qe/parsers/__init__.py`:
   ```python
   """QE analysis parsers.

   Importing this module triggers parser registration via @register_parser.
   """

   from .bands import QEBandsProvider
   from .trajectory import QETrajectoryParser

   __all__ = ["QEBandsProvider", "QETrajectoryParser"]
   ```
2. Add to `src/qmatsuite/drivers/qe/__init__.py` after the driver import:
   ```python
   from . import parsers  # noqa: F401, E402
   ```

**Verification:**
```bash
python -c "
from qmatsuite.parsers.registry import get_parser
import qmatsuite.drivers.qe
p = get_parser('qe', 'bands')
assert p is not None, 'QE bands parser not registered'
p = get_parser('qe', 'trajectory')
assert p is not None, 'QE trajectory parser not registered'
print('OK: both QE parsers registered')
"
```

### Step G2: Fix Parser Registration for All Affected Engines

**Problem:** VASP, ORCA, ABINIT, CP2K, w90 also lack `from . import parsers` in their `__init__.py`. Only scf_digest parsers are affected today, but the pattern must be consistent.

**Actions:** For each of VASP, ORCA, ABINIT, CP2K, w90:
1. Verify `drivers/<engine>/parsers/__init__.py` exists and imports parser modules
2. If the driver's `__init__.py` lacks `from . import parsers  # noqa: F401, E402`, add it

**Already correct:** LAMMPS, Gaussian, Yambo, xTB, Siesta.

**Verification:**
```bash
python -c "
from qmatsuite.parsers.registry import get_parser
import qmatsuite.drivers
engines = ['vasp', 'orca', 'abinit', 'cp2k', 'w90', 'qe']
for e in engines:
    p = get_parser(e, 'scf_digest')
    assert p is not None, f'{e} scf_digest parser not registered'
print('OK: all engine parsers registered')
"
```

### Step G3: Add Missing High-Priority Gate Tests

**Actions:** Add to `tests/gates/test_analysis_invariants.py`:

1. `test_no_redundant_canonical` (§5.3) — Given a run with GEN steps `[scf, bandspw]` and a capability `["bandspw"]`, verify exactly ONE match. Then with capability `["scf", "bandspw"]`, verify exactly ONE match (not two).

2. `test_unknown_engine_analysis_raises` (Inv-A13) — Call orchestrator with a capability whose `object_type` has no registered parser. Verify that `warnings.warn` is called (current behavior) OR that a hard error is raised (spec says hard error — decide which is correct for batch vs on-demand).

3. `test_no_analysis_disk_cache` (Inv-A10) — AST scan `core/analysis/` for `open(`, `Path.write`, `json.dump`, `pickle.dump`. Must find none.

4. `test_no_lazy_payloads` (Inv-A9) — Grep `core/analysis/` for `LazyArray`, `LateList`, `deferred`, `proxy`. Must find none.

5. `test_no_tmp_corpus_in_runtime` (Inv-A14) — Grep all Python source under `src/qmatsuite/` for `.tmp/` in non-comment lines. Must find none.

**Verification:**
```bash
python -m pytest tests/gates/test_analysis_invariants.py -v
# All tests should pass
```

### Step G4: Add Orchestrator Integration Test with Real QE Driver

**Problem:** `test_orchestrator.py` uses mock providers. Need a test that exercises the real import chain: `QEDriver.ANALYSIS_CAPABILITIES` → `get_parser("qe", "bands")` → `QEBandsProvider.parse()`.

**Actions:** Add `tests/core/analysis/test_orchestrator_integration.py`:
1. Import `QEDriver` (triggers registration chain after G1 fix)
2. Set up ordered_gen_steps with `("ulid1", "bandspw", raw_dir)` pointing to `tests/data/analysis_bands/`
3. Call `run_post_run_analysis("qe", QEDriver(), ordered_gen_steps)`
4. Assert result has exactly 1 entry with `object_type="bands"`
5. Assert `result[0]["canonical"]` is a `CanonicalPrimitiveBundle`
6. Assert `result[0]["canonical"].bundle_kind == "canonical"`

**Verification:**
```bash
python -m pytest tests/core/analysis/test_orchestrator_integration.py -v
```

### Step G5: Add Spin-Polarized BandStructure Test

**Actions:** Add to `tests/core/analysis/test_band_structure.py`:
1. Construct BandStructure with 3D eigenvalues `(2, n_kpoints, n_bands)` — spin up + down
2. Assert `spin_polarized == True`
3. Call `to_primitives()`, verify series names contain `spin_0_band_*` and `spin_1_band_*`
4. Verify determinism of 3D case

**Verification:**
```bash
python -m pytest tests/core/analysis/test_band_structure.py -v
```

---

## Section 2: Mainline A — Provenance Eager Write + API Wiring

### Overview

This section implements the end-of-run eager pipeline and adds API endpoints for operational analysis derivation. The flow is:

```
Run completes
  → run_post_run_analysis() [already exists, kernel]
  → for each result:
      → compute canonical_sha = sha256(canonical.to_dict())
      → write canonical blob to CAS
      → write SQLite linkage row (run_ulid, object_type) → canonical_sha
  → API endpoint: GET /analysis
      → derive from raw evidence (operational, no CAS read)
      → apply requested transforms on-the-fly
      → return PrimitiveBundle JSON
```

### Step A1: Implement canonical_sha Computation

**Location:** `src/qmatsuite/core/analysis/bundles.py`

**Actions:**
1. Add `compute_canonical_sha(bundle: CanonicalPrimitiveBundle) -> str` function
2. Implementation: `hashlib.sha256(json.dumps(bundle.to_dict(), sort_keys=True, separators=(',',':')).encode()).hexdigest()`
3. Only operates on `CanonicalPrimitiveBundle` (raise `TypeError` for `DerivedPrimitiveBundle`)

**Verification:**
```bash
python -c "
from qmatsuite.core.analysis.bundles import compute_canonical_sha, CanonicalPrimitiveBundle, RenderMeta, ProvenanceMeta
import numpy as np
bundle = CanonicalPrimitiveBundle(
    object_type='test', render_meta=RenderMeta(), provenance_meta=ProvenanceMeta(
        schema_version='1.0', object_type='test', parser_name='test', parser_version='1.0'),
    series=[], arrays={'x': np.array([1.0, 2.0])})
sha1 = compute_canonical_sha(bundle)
sha2 = compute_canonical_sha(bundle)
assert sha1 == sha2
assert len(sha1) == 64
print(f'OK: canonical_sha = {sha1}')
"
```

### Step A2: Implement Eager CAS Write Function

**Location:** New file `src/qmatsuite/core/analysis/cas_writer.py`

**Actions:**
1. Create `write_canonical_to_cas(bundle, cas_dir) -> str` — writes serialized bundle to `cas_dir/<sha>.json.gz`, returns sha
2. Create `write_analysis_snapshot_row(db_path, run_ulid, object_type, canonical_sha, step_ulids, gen_steps)` — SQLite INSERT OR REPLACE into `analysis_snapshots`
3. Both functions are pure API-layer utilities — they read from kernel types but write to provenance stores

**Note:** This file is in `core/analysis/` but its functions will only be CALLED from the API layer per Inv-A12. The functions themselves are stateless helpers.

**Verification:**
```bash
python -m pytest tests/core/analysis/test_cas_writer.py -v
# Test with tmp dirs: write blob, read back, verify sha matches
```

### Step A3: Wire Eager Pipeline into End-of-Run

**Location:** The call site depends on architecture. Two options:

**Option A (preferred):** Add to `api/service.py` in the run-completion handler:
```python
def _on_run_complete(self, run_ulid, calc_ulid, engine, driver, ordered_gen_steps, calc_dir):
    results = run_post_run_analysis(engine, driver, ordered_gen_steps,
                                     run_ulid=run_ulid, calc_ulid=calc_ulid, calc_dir=calc_dir)
    for result in results:
        canonical = result["canonical"]
        sha = compute_canonical_sha(canonical)
        write_canonical_to_cas(canonical, self._cas_dir)
        write_analysis_snapshot_row(self._db_path, run_ulid, result["object_type"],
                                    sha, canonical.provenance_meta.step_ulids,
                                    canonical.provenance_meta.gen_steps)
```

**Option B:** Add to daemon's run-complete event handler in `server.py`.

**Actions:**
1. Identify the exact run-completion call site in the daemon or service
2. After step digests are persisted, call `run_post_run_analysis()`
3. For each result, compute sha, write CAS blob, write SQLite row
4. Wrap in try/except — analysis failure MUST NOT block run completion (spec: warnings only)

**Verification:**
```bash
# Integration test: create a mock run, complete it, verify analysis_snapshots row exists
python -m pytest tests/api/test_analysis_eager_write.py -v
```

### Step A4: Add API Endpoint — GET /analysis (Operational Derivation)

**Location:** `src/qmatsuite/api/service.py` and `src/qmatsuite/daemon/server.py`

**Actions:**
1. Add `get_analysis(run_ulid, object_type, transforms=None)` to QMSService
2. Implementation:
   - Load run metadata to get engine, driver, ordered_gen_steps, calc_dir
   - Call `run_post_run_analysis()` (derive from present raw evidence — NOT from CAS)
   - Find result matching `object_type`
   - If `transforms` specified, apply each transform sequentially
   - Serialize bundle to JSON, return
3. Add daemon handler `_handle_get_analysis`
4. Wire to HTTP endpoint `GET /api/analysis/{run_ulid}/{object_type}`

**Key constraint (Inv-A11):** The operational path MUST derive from raw evidence. It MUST NOT read from CAS. In-memory reuse of previously computed canonical bundles within the same process is allowed (optional optimization, not required for correctness).

**Verification:**
```bash
# Unit test: mock raw evidence dir, call get_analysis(), verify PrimitiveBundle JSON returned
python -m pytest tests/api/test_analysis_endpoint.py -v
```

### Step A5: Add API Endpoint — GET /analysis/snapshot (Provenance Replay)

**Location:** `src/qmatsuite/api/service.py`

**Actions:**
1. Add `get_analysis_snapshot(run_ulid, object_type)` to QMSService
2. Implementation:
   - Query `analysis_snapshots` table for `(run_ulid, object_type) → canonical_sha`
   - Read CAS blob by `canonical_sha`
   - Deserialize to `CanonicalPrimitiveBundle`
   - Return (no transforms — snapshots are frozen)
3. This endpoint is for provenance audit only. It reads from CAS, which is the explicit exception allowed by Inv-A11.

**Verification:**
```bash
python -m pytest tests/api/test_analysis_snapshot_endpoint.py -v
```

### Step A6: Add Staleness Detection

**Location:** `src/qmatsuite/core/analysis/base.py` (helper) + `src/qmatsuite/api/service.py` (usage)

**Actions:**
1. Add `check_staleness(meta: AnalysisObjectMeta) -> bool` to base.py
   - For each `SourceFileStat` in `meta.source_files`, compare current file mtime/size
   - Return True if any differ
2. In the operational GET endpoint (Step A4), after retrieving a memoized canonical bundle, call `check_staleness()`. If stale, re-derive.

**Verification:**
```bash
python -m pytest tests/core/analysis/test_staleness.py -v
# Test: parse, touch file, check_staleness returns True
```

### Step A7: Add Gate Tests for CAS/Persistence Invariants

**Actions:** Add to gate tests:

1. `test_derived_never_persisted` (Inv-A11) — AST scan API layer for CAS write calls; verify none pass `DerivedPrimitiveBundle`
2. `test_operational_path_no_cas_read` (Inv-A11) — The operational GET /analysis handler must not call CAS read functions
3. `test_cas_is_content_addressed` (Inv-A11) — Verify `analysis_snapshots` table uses `canonical_sha` as reference, not composite key

**Verification:**
```bash
python -m pytest tests/gates/test_analysis_invariants.py -v
```

---

## Section 3: Mainline B — GUI Wiring

### Overview

Three GUI surfaces from spec §3:

| Surface | Description | Data Source |
|---------|-------------|-------------|
| **A: Raw Text Viewer** | Display raw output files | Filesystem (calc/raw/) |
| **B: Step Digest Display** | Show post-run digest (energy, convergence) | SQLite (eager, already persisted) |
| **C: Analysis Visualization** | Interactive band structure, DOS, trajectory | API operational derivation (Step A4) |

### Step B1: Surface A — Raw Text Viewer

**Location:** GUI component (likely new or extend existing)

**Actions:**
1. Add API endpoint `GET /api/raw-files/{calc_ulid}/{step_ulid}` → list raw files
2. Add API endpoint `GET /api/raw-file/{calc_ulid}/{step_ulid}/{filename}` → file content (text)
3. Add GUI component `RawFileViewer.tsx` — file list + text viewer with syntax highlighting
4. No analysis logic — pure file read + display

**Key constraint:** This surface shares NO code path with Surface B or C (spec §12.2 criterion 12: Surface isolation).

**Verification:**
```bash
# API test: verify file list and content endpoints
python -m pytest tests/api/test_raw_file_endpoints.py -v
# GUI: manual verification or Playwright test
```

### Step B2: Surface B — Step Digest Display

**Location:** Existing `CalculationAnalysisPanel.tsx` or new component

**Actions:**
1. Add API endpoint `GET /api/digest/{run_ulid}/{step_ulid}` → digest JSON
   - Reads from SQLite `run_steps.digest_sha` → CAS blob (or direct SQLite field)
   - Returns flat dict: `{energy, converged, n_iterations, fermi_energy, forces_max, timing_s, ...}`
2. Add GUI component `StepDigestPanel.tsx` — table/card display of digest fields
3. Show for each step when clicked in the step list

**Key constraint:** Digest is NOT an AnalysisObject. It is a flat summary persisted eagerly into SQLite. No PrimitiveBundle involved.

**Verification:**
```bash
python -m pytest tests/api/test_digest_endpoint.py -v
```

### Step B3: Surface C — Analysis Visualization (Band Structure)

**Location:** New GUI component replacing legacy `BandStructurePlot`

**Actions:**
1. Add GUI component `AnalysisVizPanel.tsx`:
   - On step click, check if step_ulid is in any analysis capability's step_ulids
   - If yes, show analysis tiles (one per matched object_type)
   - On tile click, call `GET /api/analysis/{run_ulid}/{object_type}`
   - Receive PrimitiveBundle JSON
   - Render from `series[]` + `render_meta` ONLY
   - Display `provenance_meta` in collapsible info panel (not for rendering)
2. Add transform controls (e.g., "Shift to Fermi level" toggle)
   - When toggled, re-request with `transforms: ["FermiShift"]`
3. Implement band structure renderer consuming Series1D arrays + Marker positions

**Key constraints:**
- Renderer MUST NOT branch on `provenance_meta.engine_name` (Inv-A8)
- Renderer MUST NOT perform transforms locally (Inv-A7) — send transform requests to API
- Step-to-analysis association is by membership: `step_ulid ∈ provenance_meta.step_ulids` (spec §12.2 criterion 13)

**Verification:**
```bash
# Type-check frontend
cd gui && npx tsc --noEmit
# Build check
cd gui && npm run build
# Manual: click a step with bands capability, verify plot renders
```

### Step B4: Remove Legacy Analysis Types from GUI

**Actions:**
1. Remove imports of `BandStructureData`, `DosData`, `ScfConvergenceData` from GUI
2. Replace with PrimitiveBundle JSON consumption
3. Remove legacy `ensure_analysis_artifact()` calls from API service
4. Add deprecation markers on `analysis/artifacts.py` and `analysis/dos.py`

**Key constraint:** Only remove after Surface C is functional and tested.

**Verification:**
```bash
# Verify no legacy type references in new components
rg 'BandStructureData|DosData|ScfConvergenceData' gui/src/
# Should only appear in legacy components marked for removal

# Full test suite still passes
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Step B5: Add Frontend Gate Test

**Actions:** Add `test_frontend_no_kernel_import` (Inv-A12):
- Scan `gui/src/` for imports matching `qmatsuite.core`, `qmatsuite.analysis`, `qmatsuite.drivers`
- Must find none

**Verification:**
```bash
python -m pytest tests/gates/test_analysis_invariants.py::test_frontend_no_kernel_import -v
```

---

## Dependency Graph

```
G1 (QE parser registration)
  ↓
G2 (all engine parser registration)
  ↓
G4 (orchestrator integration test)

G3 (gate tests) — independent
G5 (spin-polarized test) — independent

G1 + G2 → A1 (canonical_sha)
           ↓
           A2 (CAS writer)
           ↓
           A3 (eager pipeline wiring)
           ↓
           A4 (GET /analysis endpoint) ← A6 (staleness detection)
           ↓
           A5 (GET /analysis/snapshot)
           ↓
           A7 (CAS gate tests)

A4 → B3 (analysis viz component)
     ↓
     B4 (remove legacy types)

B1 (raw text viewer) — independent of A*
B2 (step digest) — independent of A*
B5 (frontend gate test) — after B3 + B4
```

---

## Ordering Summary

| Phase | Steps | Estimated Scope |
|-------|-------|-----------------|
| Gap Closure | G1–G5 | Small — fix imports, add tests |
| Mainline A | A1–A7 | Medium — CAS write, 2 API endpoints, staleness |
| Mainline B | B1–B5 | Large — 3 GUI surfaces, legacy removal |

**Recommended execution order:**
1. G1 → G2 → G4 (unblock parser registration, verify)
2. G3 + G5 (parallel, test-only)
3. A1 → A2 → A3 (eager pipeline)
4. A4 + A6 (operational API endpoint)
5. A5 (snapshot endpoint — independent)
6. A7 (CAS gate tests)
7. B1 + B2 (parallel, independent surfaces)
8. B3 (analysis viz — depends on A4)
9. B4 → B5 (legacy removal + gate test)

---

## Constraints Checklist

- [ ] Every step has a verification command
- [ ] No new legacy pipelines — all new code uses CanonicalPrimitiveBundle
- [ ] No engine branching in universal code
- [ ] Provenance writes happen ONLY in API layer (not kernel)
- [ ] Operational UI derives from present raw evidence (no CAS read for correctness)
- [ ] DerivedPrimitiveBundle is NEVER cached or persisted
- [ ] Step-to-analysis association is by membership in `step_ulids` (no owner_step_ulid)
- [ ] Three GUI surfaces are isolated (no shared code paths)
- [ ] Digest (Surface B) is NOT an AnalysisObject — separate path
- [ ] Parser registration chain works for all engines with analysis providers

---

## Progress Log

### 2026-02-08 — Step G1 (QE parser registration chain)
- Changed paths:
  - `src/qmatsuite/drivers/qe/parsers/__init__.py`
  - `src/qmatsuite/drivers/qe/__init__.py`
- Verification command:
  - `source .venv/bin/activate && python -c "from qmatsuite.parsers.registry import get_parser; import qmatsuite.drivers.qe; p = get_parser('qe','bands'); assert p is not None, 'QE bands parser not registered'; p = get_parser('qe','trajectory'); assert p is not None, 'QE trajectory parser not registered'; print('OK: both QE parsers registered')"`
- Result: PASS (`OK: both QE parsers registered`)

### 2026-02-08 — Step G2 (all engine parser registration)
- Changed paths:
  - `src/qmatsuite/drivers/vasp/__init__.py`
  - `src/qmatsuite/drivers/orca/__init__.py`
  - `src/qmatsuite/drivers/abinit/__init__.py`
  - `src/qmatsuite/drivers/cp2k/__init__.py`
  - `src/qmatsuite/drivers/w90/__init__.py`
  - parser package `__init__.py` imports for affected engines
- Verification command:
  - `source .venv/bin/activate && python -c "from qmatsuite.parsers.registry import get_parser; import qmatsuite.drivers; engines=['vasp','orca','abinit','cp2k','w90','qe'];\nfor e in engines:\n p=get_parser(e,'scf_digest'); assert p is not None, f'{e} scf_digest parser not registered';\nprint('OK: all engine parsers registered')"`
- Result: PASS (`OK: all engine parsers registered`)

### 2026-02-08 — Step G3 (missing high-priority gate tests)
- Changed paths:
  - `tests/gates/test_analysis_invariants.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS (18 passed)

### 2026-02-08 — Step G4 (orchestrator integration test)
- Changed paths:
  - `tests/core/analysis/test_orchestrator_integration.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/core/analysis/test_orchestrator_integration.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step G5 (spin-polarized band structure test)
- Changed paths:
  - `tests/core/analysis/test_band_structure.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/core/analysis/test_band_structure.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A1 (canonical_sha computation)
- Changed paths:
  - `src/qmatsuite/core/analysis/bundles.py`
- Plan amendment (minimal):
  - The original one-liner verification instantiated `RenderMeta()` with no args; `RenderMeta` now supports empty defaults via `field(default_factory=dict)` for `axis_labels`/`units`, preserving compatibility and determinism.
- Verification command:
  - `source .venv/bin/activate && python -c "from qmatsuite.core.analysis.bundles import compute_canonical_sha, CanonicalPrimitiveBundle, RenderMeta, ProvenanceMeta; import numpy as np; bundle=CanonicalPrimitiveBundle(object_type='test', render_meta=RenderMeta(), provenance_meta=ProvenanceMeta(schema_version='1.0', object_type='test', parser_name='test', parser_version='1.0'), series=[], arrays={'x': np.array([1.0, 2.0])}); sha1=compute_canonical_sha(bundle); sha2=compute_canonical_sha(bundle); assert sha1==sha2; assert len(sha1)==64; print(f'OK: canonical_sha = {sha1}')"`
- Result: PASS

### 2026-02-08 — Step A2 (eager CAS write helpers)
- Changed paths:
  - `src/qmatsuite/core/analysis/cas_writer.py`
  - `tests/core/analysis/test_cas_writer.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/core/analysis/test_cas_writer.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A3 (end-of-run eager write wiring)
- Changed paths:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/provenance/schema.py`
  - `tests/api/test_analysis_eager_write.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/api/test_analysis_eager_write.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A4 (operational GET /analysis)
- Changed paths:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/daemon/server.py`
  - `tests/api/test_analysis_endpoint.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/api/test_analysis_endpoint.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A5 (provenance replay GET /analysis/snapshot)
- Changed paths:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/daemon/server.py`
  - `tests/api/test_analysis_snapshot_endpoint.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/api/test_analysis_snapshot_endpoint.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A6 (staleness detection)
- Changed paths:
  - `src/qmatsuite/core/analysis/base.py`
  - `src/qmatsuite/api/service.py`
  - `tests/core/analysis/test_staleness.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/core/analysis/test_staleness.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step A7 (CAS/persistence gate tests)
- Changed paths:
  - `tests/gates/test_analysis_invariants.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step B1 (raw text viewer surface)
- Changed paths:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/daemon/server.py`
  - `gui/src/components/panels/RawFileViewer.tsx`
  - `tests/api/test_raw_file_endpoints.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/api/test_raw_file_endpoints.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step B2 (digest display surface)
- Changed paths:
  - `src/qmatsuite/api/service.py`
  - `src/qmatsuite/daemon/server.py`
  - `gui/src/components/panels/StepDigestPanel.tsx`
  - `tests/api/test_digest_endpoint.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/api/test_digest_endpoint.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-08 — Step B3 (analysis visualization surface)
- Changed paths:
  - `gui/src/components/panels/CalculationAnalysisPanel.tsx`
  - `gui/src/components/panels/CalculationAnalysisPanel.css`
  - `gui/src/components/panels/AnalysisVizPanel.tsx`
  - `gui/src/types/qms.ts`
- Verification commands:
  - `cd gui && npx tsc --noEmit`
  - `cd gui && npm run build`
  - `cd gui && npm run build:e2e`
- Result: PASS

### 2026-02-08 — Step B4 (remove legacy GUI analysis types / keep new primitive path)
- Changed paths:
  - `gui/src/components/panels/AnalysisPanel.tsx` (deleted)
  - `gui/src/components/panels/AnalysisPanel.css` (deleted)
  - `gui/src/components/panels/index.ts`
  - `gui/src/types/qms.ts`
  - `src/qmatsuite/api/service.py` (legacy artifact-ensure call sites removed)
  - `src/qmatsuite/analysis/artifacts.py` (deprecated marker)
  - `src/qmatsuite/analysis/dos.py` (deprecated marker)
- Verification commands:
  - `rg -n 'BandStructureData|DosData|ScfConvergenceData' gui/src/`
  - `source .venv/bin/activate && python -m pytest tests/unit/test_api_get_band_structure_data.py -v --tb=short -n auto --dist=loadfile`
- Result: PASS (no GUI legacy type matches; compatibility unit tests pass)

### 2026-02-08 — Step B5 (frontend gate test)
- Changed paths:
  - `tests/gates/test_analysis_invariants.py`
- Verification command:
  - `source .venv/bin/activate && python -m pytest tests/gates/test_analysis_invariants.py::test_frontend_no_kernel_import -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-09 — Post-plan contract alignment fixes (legacy schema/behavior parity)
- Changed paths:
  - `src/qmatsuite/analysis/parsers.py`
  - `src/qmatsuite/api/service.py`
  - `tests/contract_crawler/introspection.py`
  - `tests/contract_crawler/test_coverage.py`
- What changed:
  - Restored JSON-compatible `k_coords` list serialization in bands output.
  - Restored expected `ensure_analysis` contract behavior for SCF default selector and string `artifact_path`.
  - Restored explicit-invalid-run pin behavior to raise `PinError` without fallback inference.
  - Restored legacy not-found reason string for `get_latest_run_for_step`.
  - Classified new analysis RPC methods under the `analysis` contract-crawler category and added explicit coverage exemptions with rationale.
- Verification commands:
  - `source .venv/bin/activate && python -m pytest tests/contract_crawler/test_introspection.py tests/contract_crawler/test_coverage.py tests/contract_crawler/test_golden_contracts.py tests/contract_crawler/test_schema_preservation.py -v --tb=short -n auto --dist=loadfile`
  - `source .venv/bin/activate && python -m pytest tests/contract_crawler/test_schema_preservation.py tests/contract_crawler/test_golden_contracts.py -k ensure_calculation_analysis -v --tb=short -n auto --dist=loadfile`
- Result: PASS

### 2026-02-09 — Final verification (full backend + GUI e2e build)
- Verification commands:
  - `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`
  - `cd gui && npm run build:e2e`
- Result:
  - Backend suite: PASS (`4636 passed, 19 skipped`)
  - GUI e2e build: PASS
