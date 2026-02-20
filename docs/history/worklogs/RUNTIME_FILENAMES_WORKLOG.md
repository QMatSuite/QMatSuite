# Runtime-Managed Output Filenames: filband + fildos

**Date**: 2026-02-19
**Status**: Complete

## Problem

The previous C2 fix made `filband` injection **conditional** — if the user already set filband, it was preserved. This is wrong: `filband` and `fildos` must be **unconditionally** runtime-managed (same as `prefix` and `outdir`) so that analysis evidence globs reliably find output files.

## Solution

### Core Change

`_inject_calculation_prefix_outdir()` in `structure_steps.py` now:
1. Accepts an `input_name` parameter (the materialized input filename)
2. Derives `input_stem = Path(input_name).stem` (e.g. `"bands.bands"` from `"bands.bands.in"`)
3. **Unconditionally** sets `filband = "{input_stem}.dat"` for BANDS module steps
4. **Unconditionally** sets `fildos = "{input_stem}.dat"` for DOS module steps
5. Logs a warning if overriding a user-set value

### Naming Convention

| Step type | Input file | Stem | fil* value | Output file |
|-----------|-----------|------|------------|-------------|
| bands (bands.x) | `bands.bands.in` | `bands.bands` | `filband=bands.bands.dat` | `bands.bands.dat.gnu` |
| dos (dos.x) | `dos.dos.in` | `dos.dos` | `fildos=dos.dos.dat` | `dos.dos.dat` |

### Evidence Glob Coverage

- Bands: `*.bands.dat.gnu` matches `bands.bands.dat.gnu`
- DOS: `*.dos.dat` matches `dos.dos.dat`

## Files Modified

| File | Change |
|------|--------|
| `src/quantumvitas/calculation/structure_steps.py` | `input_name` param, unconditional filband+fildos injection, `RUNTIME_KEYS` expanded |
| `src/quantumvitas/calculation/step_defaults.py` | Removed `fildos: "dos.dat"` default from `qe_dos` (now runtime-managed) |
| `tests/mcp/test_bands_workflow.py` | Rewrote `TestC2FilbandInjection`: 8 tests for unconditional injection + fildos + override + no-input-name edge case |
| `tests/cli/test_si_bands_manual_calculation_cli.py` | Glob-based bands output discovery (replaces hardcoded filename) |
| `tests/cli/test_si_bands_auto_calculation_cli.py` | Glob-based bands output discovery (replaces hardcoded filename) |
| `tests/cli/test_si_dos_calculation_comprehensive.py` | Glob-based DOS output discovery (replaces hardcoded filename) |
| `tests/daemon/contract/test_realrun_si_dos.py` | Updated materialized input assertion (fildos presence, not specific value) |
| `tests/daemon/contract/test_realrun_al_dos.py` | Updated materialized input assertion (fildos presence, not specific value) |

## Test Results

- Full suite: 6215 passed, 4 skipped, 0 failed
- Zero regressions

## Design Notes

- **YAML vs materialized**: The step YAML still stores whatever the user set. The override happens at materialization time in `_inject_calculation_prefix_outdir()`.
- **Standalone mode**: When `input_name` is None (standalone CLI runs), filband/fildos injection is skipped — users retain full control.
- **Project runs**: `input_name` is always provided by `CalculationFileNaming.input_filename()` via `calculation.py`, so injection always happens.
