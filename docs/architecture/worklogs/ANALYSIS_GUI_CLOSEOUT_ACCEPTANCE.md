# Analysis Pipeline & GUI Closeout — Acceptance Report

## Date: 2026-02-11

## Summary

All backend gaps and GUI visualization work from the Analysis Pipeline Review are now complete.

## Acceptance Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| DOS PDOS emits per-atom per-orbital Series1D | PASS | `test_pdos_emits_per_atom_orbital_series` |
| PDOS series naming follows "{atom} {orbital}" | PASS | `test_pdos_series_name_pattern` |
| Spin-down DOS flipped to negative y | PASS | `test_spin_polarized_total_dos_down_flipped` |
| Spin-polarized PDOS with total DOS | PASS | `test_pdos_spin_polarized_series` |
| PDOS raw array still in bundle.arrays | PASS | `test_pdos_still_in_arrays` |
| Default labels when atom/orbital labels None | PASS | `test_pdos_default_labels_when_none` |
| GUI TypeScript types for geometry frames | PASS | `PrimitiveGeometryFrame`, `PrimitiveGeometryFrames` in qv.ts |
| GUI object types expanded to 6 | PASS | bands, dos, convergence, trajectory, neb_trajectory, field3d |
| GUI dispatches trajectory to TrajectoryVizPanel | PASS | `CalculationAnalysisPanel.tsx` |
| GUI dispatches fatbands to FatbandsVizPanel | PASS | `CalculationAnalysisPanel.tsx` |
| GUI PDOS element filter | PASS | `AnalysisVizPanel.tsx` |
| GUI convergence info bar | PASS | `AnalysisVizPanel.tsx` |
| GUI field3d metadata card | PASS | `AnalysisVizPanel.tsx` |
| GUI conditional Fermi shift | PASS | Only shown for bands/dos |
| TrajectoryVizPanel with playback | PASS | Play/pause, slider, FPS, frame info |
| FatbandsVizPanel with SVG overlay | PASS | Recharts Customized, atom/orbital selector |
| Backend tests pass | PASS | 5094 passed, 19 skipped |
| GUI build passes | PASS | tsc + vite build:e2e |

## Invariant Compliance

| Invariant | Status |
|-----------|--------|
| A2: AnalysisObjects engine-agnostic | Maintained — no new domain objects |
| A6: No view params in bundles | Maintained — PDOS uses data labels only |
| A7: Transforms pure math | Maintained — no new transforms |
| A8: Viz uses only PrimitiveBundles | Maintained — all panels read PrimitiveBundleData |
| A13: No engine branching in viz | Maintained — dispatch on object_type only |

## Test Counts
- **Before:** 5085 passed, 19 skipped
- **After:** 5094 passed, 19 skipped (+9 new)
