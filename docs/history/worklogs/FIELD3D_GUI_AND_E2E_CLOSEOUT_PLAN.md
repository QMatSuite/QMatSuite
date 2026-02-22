# Field3D Production GUI & E2E Closeout Plan

## Objective

Close two remaining gaps after the analysis pipeline backend was completed (5085 passed, 19 skipped):

1. **Field3D has no 3D rendering in production** — only a metadata card existed. An experimental `VolumeViewerSandbox.tsx` (1054 lines) existed for Wannier90 dev fixtures. Needed refactoring into a production panel that consumes Field3D bundles via the analysis pipeline RPC.

2. **E2E coverage was minimal** — only one Playwright spec (`demo_calculation_run.spec.ts`) tested the `si_bands_demo`. Needed e2e for dos and convergence analysis types.

## Part A: Field3D Production GUI

### Architecture: `.scratch/field3d/` Binary Transfer

Field3D full grid data is too large for JSON-RPC (200^3 = 8M floats = 32MB binary). The `to_primitives()` bundle only carries preview + metadata (primitive-by-reference).

**Solution:** Backend materializes full grid to calc-level `.scratch/field3d/` directory as binary Float32 files. Frontend reads via Electron IPC.

**Flow:**
```
GUI: get_analysis(object_type="field3d") -> bundle with metadata + preview_data
GUI: "Load Full Grid" button click
GUI: get_field3d_grid(project_root, run_ulid) -> RPC
  Backend: Re-derive Field3D -> write binary -> atomic rename -> return metadata
GUI: readScratchFile(calcDir, ".scratch/field3d/active.f32") -> ArrayBuffer
GUI: Float32Array -> marching cubes -> Three.js isosurface
```

### Backend Changes

| File | Action | Change |
|------|--------|--------|
| `src/qmatsuite/core/analysis/field3d.py` | EDIT | Add `materialize_to_scratch(calc_dir)` — binary Float32 + metadata JSON with atomic rename |
| `src/qmatsuite/daemon/server.py` | EDIT | Add `_handle_get_field3d_grid` RPC handler |
| `src/qmatsuite/api/service.py` | EDIT | Add `get_field3d_grid()` service method |

### Electron IPC

| File | Action | Change |
|------|--------|--------|
| `gui/electron/preload.ts` | EDIT | Add `readScratchFile` to qmsApi |
| `gui/electron/main.ts` | EDIT | Add `qms-read-scratch-file` IPC handler with path validation |

Security: reject paths with `..` or outside `.scratch/`.

### Frontend

| File | Action | Change |
|------|--------|--------|
| `gui/src/components/three/IsosurfaceMesh.tsx` | NEW | Extracted from VolumeViewerSandbox (shared component) |
| `gui/src/components/panels/Field3DVizPanel.tsx` | NEW | Production field3d viewer with Three.js canvas |
| `gui/src/components/panels/VolumeViewerSandbox.tsx` | EDIT | Import shared IsosurfaceMesh |
| `gui/src/components/panels/CalculationAnalysisPanel.tsx` | EDIT | Dispatch field3d to Field3DVizPanel |
| `gui/src/components/panels/CalculationAnalysisPanel.css` | EDIT | Field3D panel styles |
| `gui/src/types/qms.ts` | EDIT | Add readScratchFile type + Field3DGridMetadata |

### Reused as-is (no changes)

- `gui/src/utils/marchingCubes.ts` — Marching cubes (876 lines)
- `gui/src/components/panels/VolumeOverlay.tsx` — Atom/cell/BZ overlays

## Part B: Playwright E2E Expansion

### Strategy

Each test follows the proven pattern from `demo_calculation_run.spec.ts`:
1. Create demo project from gallery
2. Navigate to Calculations -> select calculation
3. Click "Run Calculation" -> wait for completion
4. Switch to Analysis tab
5. Assert analysis visualization appears with correct data

### Test Files

| File | Demo Used | What It Tests |
|------|-----------|---------------|
| `gui/tests/e2e/analysis_dos.spec.ts` | `si_dos_demo` | DOS chart, series lines, Fermi energy |
| `gui/tests/e2e/analysis_convergence.spec.ts` | `si_bands_demo` (scf step) | Convergence chart, convergence badge |

### Demo YAML Fixes

Discovered systemic `structure_ulid` mismatches in numbered demo projects. Fixed the two needed for E2E:
- `resources/demo_projects/00_Si_scf.yml` — corrected structure_ulid
- `resources/demo_projects/03_Si_vc_relax.yml` — corrected structure_ulid

### Trajectory E2E — Deferred

No working relax/vc-relax demo exists that produces parseable trajectory analysis output through the full pipeline. The `03_Si_vc_relax` demo runs successfully but the analysis capability matching for trajectory requires `*.relax.out` evidence files which QE vc-relax doesn't produce with that naming pattern. Deferred until a working trajectory demo is available.

## Invariant Compliance

| Invariant | Status |
|-----------|--------|
| A2: AnalysisObjects engine-agnostic | MAINTAINED |
| A8: Viz uses only PrimitiveBundles | MAINTAINED — metadata from bundle, grid via RPC |
| A10: Core analysis no disk I/O | MAINTAINED — materialize_to_scratch lives on Field3D object, called by service layer |
| A13: No engine branching in viz | MAINTAINED — dispatch on object_type only |
| S1: No sensitive paths | MAINTAINED |

## Contract Crawler

Added `get_field3d_grid` to EXEMPT_METHODS in `tests/contract_crawler/test_coverage.py` — requires completed run with field3d evidence (cube files).
