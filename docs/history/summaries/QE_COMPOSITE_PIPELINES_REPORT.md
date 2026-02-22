# QE Composite Pipeline Demos — Final Report

## Summary

Created 6 Route-1 composite pipeline demos replacing 7 Route-2 standalone demos
that required prebaked upstream artifacts. All demos now model the full QE->companion
engine chain as multi-step calculations with correct engine ownership per the Step Type
GEN/SPEC Constitution.

## Test Results

- **Baseline**: 5444 passed, 26 skipped
- **Final**: 5445 passed, 25 skipped (+1 pass, -1 skip)
- **Gate tests**: All pass (2 pre-existing api.utils failures unrelated)
- **Demo generation**: 52 demos generated successfully

## New Composite Demos

### QE -> Wannier90 (2 demos)

| Demo | Pipeline | Steps | Species |
|------|----------|-------|---------|
| `qe_diamond_wannier` | SCF -> NSCF -> W90 -pp -> pw2wannier -> W90 | 5 | C |
| `qe_copper_wannier` | SCF -> NSCF -> W90 -pp -> pw2wannier -> W90 | 5 | Cu |

- `.win` files PARSED by W90 `parse_win_text()` -> YAML params (num_wann, projections, mp_grid, etc.)
- W90 steps use `w90_wannierprep` / `w90_wannier` (NOT `qe_wannierprep`)
- QE owns `qe_pw2wannier` converter step
- Source: Wannier90 Tutorial Examples 5 (diamond) and 6 (copper disentangle)

### QE -> QMCPACK (2 demos)

| Demo | Pipeline | Steps | Species |
|------|----------|-------|---------|
| `qe_lih_qmcpack_vmc` | SCF -> pw2qmcpack -> QMCPACK VMC | 3 | Li, H |
| `qe_he_qmcpack_vmc` | SCF -> pw2qmcpack -> QMCPACK VMC | 3 | He |

- New `qe_pw2qmcpack` step type added (QE owns the converter)
- QMCPACK XML parsed by `parse_qmcpack_text()` -> YAML params
- `pw2qmcpack` added to GenStepRegistry, QE SUPPORTED_GEN_STEPS, and EXECUTABLE_MAP

### QE -> Yambo (2 demos)

| Demo | Pipeline | Steps | Species |
|------|----------|-------|---------|
| `qe_si_yambo_gw` | SCF -> NSCF -> yambo_setup -> yambo_gw | 4 | Si |
| `qe_si_yambo_bse` | SCF -> NSCF -> yambo_setup -> yambo_bse | 4 | Si |

- `yambo_setup` step has no input files (p2y runs internally)
- Yambo `.in` files parsed by Yambo engine parser -> YAML params

## Demoted Route-2 Demos (7)

| Engine | Case ID | Reason |
|--------|---------|--------|
| w90 | diamond_pipeline | Requires prebaked .amn/.mmn/.eig |
| w90 | copper_disentangle | Requires prebaked .amn/.mmn/.eig |
| w90 | silicon_bandinterp | Requires prebaked .amn/.mmn/.eig |
| qmcpack | lih_solid_vmc_pp | Requires prebaked HDF5 wavefunction |
| yambo | si_gw_ppa | Requires QE prefix.save/ directory |
| yambo | si_bse_haydock | Requires QE prefix.save/ directory |
| yambo | si_ip_optics | Requires QE prefix.save/ directory |

**Kept as self-contained demos**: `qmcpack/he_vmc_sto`, `qmcpack/h2_ae_vmc`

## Code Changes

### Infrastructure (3 files modified)

1. **`src/qmatsuite/demo_store/translator.py`** — Companion engine dispatch in
   `_translate_multi_step()`. When a step's `step_type_spec` prefix differs from the
   base engine, the companion engine's driver and input_spec are used for parsing.
   Uses `prefix_from()` from `step_type_convert.py` (no manual split).

2. **`src/qmatsuite/workflow/gen_steps.py`** — Added `pw2qmcpack` to
   `GenStepRegistry.GEN_STEPS`.

3. **`src/qmatsuite/drivers/qe/`** — Added `qe_pw2qmcpack` step type:
   - `step_types.py`: New `StepTypeSpec`
   - `driver.py`: Added to `SUPPORTED_GEN_STEPS`
   - `engine/qe_engine.py`: Added to `EXECUTABLE_MAP`

### Corpus (34 files created, 10 files modified)

- 6 new corpus case directories under `tests/inputformat/samples/qe/`
- 7 demoted `case.yaml` files (demo_eligible: false)
- Updated `corpus_index.yaml` (+6 new entries, 7 demoted)
- 6 new generated demo YAMLs in `resources/demo_projects/`

## Acceptance Criteria Verification

- [x] W90: 2 Route-1 composite demos (diamond sp3 + copper disentangle)
- [x] QMCPACK: 2 Route-1 composite demos (LiH solid + He atom)
- [x] Yambo: 2 Route-1 composite demos (Si GW + Si BSE)
- [x] All Route-2 standalone demos demoted (demo_eligible: false)
- [x] `.win` files PARSED into YAML params (not staged as raw files)
- [x] pytest stays green (5445 passed)
- [x] Demo generation succeeds (52 demos)
