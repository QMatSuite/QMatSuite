# Demo Store Post-Implementation Audit Worklog

## Context
Post-implementation audit of Wave 1 (01c96cb5) and Wave 2 (49237c81) demo store work.

## Audit Findings

### PASS — No fixes needed
- Bug A: GPAW bands ref pack - `gpaw_si_bands/manifest.json` has convergence + bands
- Bug B: Siesta trajectory ref pack - `siesta_si_relax/manifest.json` has convergence + trajectory
- Bug C: qe_fe_dos→qe_fe_scf rename - old file gone, new file correct
- Method field accuracy verified across 5 engines
- Spin treatment accuracy verified (ISPIN=2, noncolin=.true.)
- All _summarize_bundle convergence/bands fields present
- MCP tool structure correct (7 filters, compact scalars, load hints)
- 32 contract tests use .fn() pattern correctly
- All 14 new metadata fields propagated via generate_all.py

### FIX 1: Trajectory _summarize_bundle returns None for energy
- Root cause: `_summarize_bundle` reads `arrays.energy` but trajectory bundles store energy in `series` list
- Fix: Added series fallback in `_summarize_bundle` for trajectory type
- File: `src/quantumvitas/mcp/tools/demo_store.py` lines 88-101
- Test strengthened: `test_get_demo_results_trajectory_summary` now asserts energy is not None

### FIX 2: subtitle + difficulty for all 52 demo case.yaml files
- 26/52 had subtitle+difficulty, 26 didn't. Quality inconsistent.
- Rewrote all 52 with fresh, physics-informed values.
- Difficulty criteria: runtime thresholds, physics complexity, engine complexity

## Files Modified
- `src/quantumvitas/mcp/tools/demo_store.py` - trajectory energy series fallback
- `tests/mcp/test_demo_store_mcp.py` - trajectory energy assertions
- 52x `tests/inputformat/samples/<engine>/<case>/case.yaml` - subtitle + difficulty
