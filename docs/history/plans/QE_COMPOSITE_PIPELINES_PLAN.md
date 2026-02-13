# QE Composite Pipeline Demos (W90 / QMCPACK / Yambo) — Progress Plan

**Baseline**: 5444 passed, 26 skipped
**Final**: 5445 passed, 25 skipped

---

## Step 0: Baseline Checks
- [x] Run full test suite — 5444 passed, 26 skipped

## Step 1: Enhance Multi-Step Translator for Companion Engine Steps
- [x] Modify `_translate_multi_step()` in `translator.py` to detect companion engine
- [x] When step_type_spec prefix differs from base engine, use companion's input_spec
- [x] Fallback to raw `parameters` dict if no parser matches

## Step 2: Add `qe_pw2qmcpack` Step Type
- [x] Add StepTypeSpec to `drivers/qe/step_types.py`
- [x] Add `"pw2qmcpack"` to SUPPORTED_GEN_STEPS in `drivers/qe/driver.py`
- [x] Add `"pw2qmcpack": "pw2qmcpack.x"` to EXECUTABLE_MAP in `qe_engine.py`
- [x] Add `"pw2qmcpack"` to GenStepRegistry.GEN_STEPS

## Step 3: Create QE->W90 Composite Corpus Cases
- [x] `tests/inputformat/samples/qe/diamond_wannier/` — Diamond sp3 (example05)
- [x] `tests/inputformat/samples/qe/copper_wannier/` — Copper disentangle (example06)

## Step 4: Create QE->QMCPACK Composite Corpus Cases
- [x] `tests/inputformat/samples/qe/lih_qmcpack_vmc/` — LiH solid VMC
- [x] `tests/inputformat/samples/qe/he_qmcpack_vmc/` — He atom VMC

## Step 5: Create QE->Yambo Composite Corpus Cases
- [x] `tests/inputformat/samples/qe/si_yambo_gw/` — Silicon GW
- [x] `tests/inputformat/samples/qe/si_yambo_bse/` — Silicon BSE

## Step 6: Demote Route-2 Standalone Demos
- [x] w90/diamond_pipeline — demo_eligible: false
- [x] w90/copper_disentangle — demo_eligible: false
- [x] w90/silicon_bandinterp — demo_eligible: false
- [x] qmcpack/lih_solid_vmc_pp — demo_eligible: false
- [x] yambo/si_gw_ppa — demo_eligible: false
- [x] yambo/si_bse_haydock — demo_eligible: false
- [x] yambo/si_ip_optics — demo_eligible: false
- [x] KEEP: qmcpack/he_vmc_sto, qmcpack/h2_ae_vmc (self-contained)

## Step 7: Update Corpus Index
- [x] Add 6 new entries
- [x] Demote 7 entries

## Step 8: Regenerate Demo YAMLs
- [x] Run `python tools/demo_store/generate_all.py` — 52 demos generated
- [x] Verify new demos appear (all 6 composite demos generated)

## Step 9: Real Engine Runs (Best Effort)
- [ ] Deferred — requires engine binaries and runtime environment

## Step 10: Final Verification
- [x] Full pytest green — 5445 passed, 25 skipped
- [x] Gate tests pass (only 2 pre-existing api.utils failures, unrelated)
- [x] Companion resolution check — all 4 cases verified

## Step 11: Write Report
- [x] `docs/demo_store/QE_COMPOSITE_PIPELINES_REPORT.md`
