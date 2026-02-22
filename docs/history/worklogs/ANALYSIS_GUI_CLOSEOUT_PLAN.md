# Analysis Pipeline & GUI Closeout Plan

## Date: 2026-02-11

## Context

The analysis pipeline backend was largely complete (53 registered parsers, 5 domain objects, 8 transforms). But:
- GUI only rendered band structure plots
- Missing object type dispatch for DOS, convergence, trajectory, field3d
- PDOS data was in raw arrays but not emitted as renderable Series1D
- Spin-down DOS was not flipped to negative y (py4vasp convention)
- No trajectory playback UI
- No fatband visualization
- TypeScript types for geometry frames were untyped (`Record<string, unknown>`)

## Scope

### Backend Changes
1. **DOS PDOS Series Emission** — `dos/model.py:to_primitives()` now emits individual Series1D per (atom, orbital) pair
2. **Spin-Down Flip** — Total DOS down series y-values are negated (py4vasp convention)

### GUI Changes
1. **Object Type Expansion** — `ANALYSIS_OBJECT_TYPES` expanded from `['bands']` to `['bands', 'dos', 'convergence', 'trajectory', 'neb_trajectory', 'field3d']`
2. **Object-Type Dispatch** — `CalculationAnalysisPanel.tsx` routes trajectory to `TrajectoryVizPanel`, fatbands to `FatbandsVizPanel`, others to `AnalysisVizPanel`
3. **PDOS Rendering** — Element filter toggle buttons, show/hide PDOS checkbox
4. **Convergence Info Bar** — Shows converged/not converged badge, algorithm, ionic step count
5. **Field3D Metadata Card** — Shows grid shape, value range, field kind
6. **Conditional Fermi Shift** — Only shown for bands/dos object types
7. **Reference Energy Line** — Horizontal dashed line at Fermi energy
8. **Legend Auto-Hide** — Legend hidden when >15 series (PDOS can have 50+)
9. **TrajectoryVizPanel** — Observable selector, frame playback, frame slider, FPS control, frame info
10. **FatbandsVizPanel** — Atom/orbital selector, width scale slider, SVG overlay via Recharts Customized
11. **TypeScript Types** — `PrimitiveGeometryFrame`, `PrimitiveGeometryFrames` interfaces

### What Was Explicitly SKIPPED
- Q1 (orphaned ANALYSIS_CAPABILITIES for digest-only parsers) — architecturally incorrect
- Q2-Q3 (scf_digest for Python-script engines) — requires runner/execution changes
- Full Field3D isosurface rendering — out of scope (preview metadata only)
- 3D structure viewer in trajectory panel — too complex, deferred

## Files Changed

### Backend (2 files)
| File | Action |
|------|--------|
| `src/qmatsuite/core/analysis/dos/model.py` | EDIT: PDOS Series1D emission + spin-down flip |
| `tests/core/analysis/test_dos_model.py` | NEW: 9 tests for PDOS series |

### GUI (7 files)
| File | Action |
|------|--------|
| `gui/src/types/qms.ts` | EDIT: Add geometry frame types |
| `gui/src/components/panels/CalculationAnalysisPanel.tsx` | EDIT: Object-type dispatch |
| `gui/src/components/panels/AnalysisVizPanel.tsx` | EDIT: PDOS, convergence, field3d |
| `gui/src/components/panels/TrajectoryVizPanel.tsx` | NEW |
| `gui/src/components/panels/FatbandsVizPanel.tsx` | NEW |
| `gui/src/components/panels/CalculationAnalysisPanel.css` | EDIT: New panel styles |

## Test Results
- Backend: **5094 passed, 19 skipped** (+9 new DOS model tests)
- GUI build: `npm run build:e2e` passes (tsc + vite)
