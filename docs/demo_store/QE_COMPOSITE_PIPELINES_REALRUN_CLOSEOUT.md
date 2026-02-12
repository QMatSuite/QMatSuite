# QE Composite Pipeline Demos — Real Engine Run Closeout

## Overview

All 6 new QE composite pipeline demos have been validated with real engine runs.
Each demo was tested end-to-end: parse input files -> YAML params -> materialize ->
regenerated input -> real engine execution -> output parsing.

## Test Results

- **Baseline**: 5445 passed, 25 skipped
- **Final**: 5459 passed, 30 skipped, 0 failed
- **Demo count**: 52 YAMLs in `resources/demo_projects/`

## Real Engine Run Results

### Full Sweep Summary

| Demo | Status | Runtime | Engine Chain |
|------|--------|---------|--------------|
| `qe_diamond_wannier` | OK | 6.6s | QE SCF -> NSCF -> W90 -pp -> pw2wannier -> W90 |
| `qe_copper_wannier` | OK | 29.4s | QE SCF -> NSCF -> W90 -pp -> pw2wannier -> W90 |
| `qe_lih_qmcpack_vmc` | OK | 2.1s | QE SCF -> pw2qmcpack -> QMCPACK VMC |
| `qe_he_qmcpack_vmc` | OK | 53.4s | QE SCF -> pw2qmcpack -> QMCPACK VMC |
| `qe_si_yambo_gw` | OK | 68.7s | QE SCF -> NSCF -> yambo_setup -> yambo_gw |
| `qe_si_yambo_bse` | OK | 44.4s | QE SCF -> NSCF -> yambo_setup -> yambo_bse |

All 6 composite demos pass with real engines. Total combined runtime: ~204s.

## Bugs Found and Fixed During Real Runs

### Bug 1: Yambo BSE Empty Parameters (Translator gen_type Dispatch)

**Symptom**: Yambo BSE demo YAML had 0 parameters in the BSE step.

**Root cause**: `translator.py` called `companion_driver.get_input_spec()` without
`gen_type` context. Yambo's `get_input_spec()` defaults to `gen_type="gw"`, which
returns filename `"gw.in"`. Since the actual file was `bse.in`, the parser found no
matching file and returned empty params.

**Fix**: Pass `gen_type=step_gen` to `companion_driver.get_input_spec()` in
`translator.py:_translate_multi_step()`.

### Bug 2: Materializer gen_type Dispatch

**Symptom**: Materializer wrote `gw.in` instead of `bse.in` for the BSE step.

**Root cause**: `structure_steps.py` line 1244 called `driver.get_input_spec()`
without gen_type context, same issue as the translator.

**Fix**: Changed to `driver.get_input_spec(gen_type=step_type_gen)` in
`structure_steps.py`.

### Bug 3: Yambo Handler Overwriting Materialized Input

**Symptom**: Even after fixing gen_type dispatch, the BSE input file had wrong values
(all defaults like BSENGexx=0, BSEBands 1|8).

**Root cause**: `_handle_calculation()` in `handler.py` always regenerated input files
from semantic keys (`bse_bands`, `screening_bands`). But the YAML stores canonical
yambo keys (`BSEBands`, `BndsRnXs`), so all values fell to defaults, overwriting the
materializer's correct output.

**Fix**: Added check: if the materialized input file already exists with non-zero size,
skip regeneration and use it directly. The handler now logs:
```
Using materialized input file <path> (skipping handler regeneration)
```

### Bug 4: Yambo BSE SIGSEGV in SEX Kernel

**Symptom**: yambo crashes with SIGSEGV (exit code -11) at
`[06.01.05.03] Wave-Function Phases` during BSE calculation.

**Investigation**:
- Reduced BSENGexx from 839 to 51 RL -> still crashes
- Tried IP-level optics (no BSE kernel) -> WORKS
- Tried BSE with `BSKmod="HARTREE"` (no screened exchange) -> WORKS (23 iterations)
- Tried BSE with diag solver instead of Haydock -> still crashes

**Conclusion**: yambo 5.3.0 serial+HDF5_IO build has a bug in the Screened Exchange
(SEX) kernel's wave-function phases computation. The HARTREE kernel works correctly.

**Workaround**: Changed corpus `bse.in` from `BSKmod="SEX"` to `BSKmod="HARTREE"`,
and reduced cutoffs (`BndsRnXs` 1|8, `BSENGexx` 51 RL) for faster demo runtime.
The demo still demonstrates the BSE workflow correctly with the Hartree kernel.

### Bug 5: W90 Composite Demos Engine Routing

**Symptom**: W90 composite demos fail with "Failed to resolve Wannier90 input files
from preprocessing".

**Root cause**: QE recipe set `engine=spec.engine` for all steps. For W90 steps,
`spec.engine` is `"w90"`, so the executor dispatched to the standalone W90 handler
which expects prebaked `.amn`/`.mmn`/`.eig` files. But the QE handler
(`qe_calculation.py`) has full support for running `wannier90.x -pp` and
`wannier90.x` as companion steps.

**Fix**: In `recipe.py`, override engine to `"qe"` for W90 companion gen types
(`wannierprep`, `wannier`, `pw2wannier`). This routes execution through the QE
handler which correctly invokes the W90 binaries.

### Bug 6: Managed Keys in Demo Step Parameters

**Symptom**: 6 demos failed `test_no_step_level_prefix_outdir` because QE step
parameters contained `prefix` and `outdir` keys.

**Root cause**: Translator stored all parsed parameters including managed keys
(`prefix`, `outdir`, `pseudo_dir`) which are injected at materialization time.

**Fix**: Added `_strip_managed_params()` helper in `translator.py` to strip
QE managed keys from step parameters during translation.

### Bug 7: Stale Demoted Demo YAML Files

**Symptom**: `test_all_demos_have_manifest_entry` failed because 7 stale `.yml`
files remained after demotion.

**Fix**: Deleted the 7 stale Route-2 demo YAML files:
- `w90_diamond.yml`, `w90_copper.yml`, `w90_silicon.yml`
- `yambo_si_gw.yml`, `yambo_si_bse.yml`, `yambo_si_optics.yml`
- `qmcpack_lih_solid.yml`

### Bug 8: Cross-Domain Deep Imports

**Symptom**: `test_no_cross_domain_deep_imports` failed because `structure_steps.py`
imported directly from `quantumvitas.core.driver_registry` and
`quantumvitas.core.resources`.

**Fix**: Changed to use `quantumvitas.core.public` facade:
- `from quantumvitas.core.public import DriverRegistry`
- `from quantumvitas.core.public import get_resources_dir`

### Bug 9: Golden Contract Count Drift

**Symptom**: `test_matches_golden[list_demo_projects]` expected 53 demos, now have 52.

**Fix**: Updated golden fixture count from 53 to 52 in
`tests/fixtures/golden_0873ebf/daemon/list_demo_projects.json`.

## Engine Binaries Used

| Engine | Binary Path | Version |
|--------|------------|---------|
| QE | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x` | 7.5 |
| QE pw2wannier | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2wannier90.x` | 7.5 |
| QE pw2qmcpack | `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw2qmcpack.x` | 7.5 |
| W90 | `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/wannier90.x` | 3.1 |
| QMCPACK | `.qmatsuite/engines/qmcpack/qmcpack-4.1.0/bin/qmcpack` | 4.1.0 |
| Yambo | `.qmatsuite/engines/yambo/yambo-5.3.0/bin/yambo` | 5.3.0 |
| Yambo p2y | `.qmatsuite/engines/yambo/yambo-5.3.0/bin/p2y` | 5.3.0 |

## Files Modified (Code Changes)

| File | Change |
|------|--------|
| `src/quantumvitas/demo_store/translator.py` | Companion engine dispatch + managed key stripping |
| `src/quantumvitas/calculation/structure_steps.py` | gen_type dispatch + public.py imports |
| `src/quantumvitas/drivers/yambo/handler.py` | Materializer passthrough for pre-existing input files |
| `src/quantumvitas/drivers/qe/recipe.py` | W90 companion step engine routing override |
| `src/quantumvitas/drivers/qe/step_types.py` | Added qe_pw2qmcpack StepTypeSpec |
| `src/quantumvitas/drivers/qe/driver.py` | Added pw2qmcpack to SUPPORTED_GEN_STEPS |
| `src/quantumvitas/drivers/qe/engine/qe_engine.py` | Added pw2qmcpack to EXECUTABLE_MAP |
| `src/quantumvitas/core/public.py` | Added get_resources_dir export |
| `tools/demo_store/generate_all.py` | Managed key stripping during generation |
| `tests/fixtures/golden_0873ebf/daemon/list_demo_projects.json` | Count 53 -> 52 |
| `tests/inputformat/samples/qe/si_yambo_bse/bse.in` | BSKmod SEX -> HARTREE |
| `tests/inputformat/samples/corpus_index.yaml` | 6 new entries, 7 demoted |

## Known Limitations

1. **Yambo BSE SEX kernel**: yambo 5.3.0 serial build SIGSEGV in screened exchange.
   Demo uses HARTREE kernel as workaround. A parallel or newer yambo build may fix this.

2. **Ref packs**: New composite demos have ref_packs with manifest.json but no
   convergence/bands/dos/trajectory data yet (would require full analysis chain on
   companion engine outputs which is a separate task).

## Acceptance Criteria Verification

- [x] W90: 2 Route-1 composite demos pass real runs (diamond 6.6s + copper 29.4s)
- [x] QMCPACK: 2 Route-1 composite demos pass real runs (LiH 2.1s + He 53.4s)
- [x] Yambo: 2 Route-1 composite demos pass real runs (GW 68.7s + BSE 44.4s)
- [x] All 7 Route-2 standalone demos demoted (demo_eligible: false, YAMLs deleted)
- [x] `.win` files parsed into YAML params (not staged as raw files)
- [x] Yambo setup step has no input files (p2y runs internally)
- [x] pytest fully green: 5459 passed, 0 failed, 30 skipped
- [x] Demo generation succeeds: 52 demos
- [x] All 9 test failures from regression resolved
