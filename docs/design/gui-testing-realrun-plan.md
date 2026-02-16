# GUI Testing: Real QE Smoke Test Pairs — Plan

## Document Status
- Created: 2026-02-13
- Updated: 2026-02-15
- Session: 13
- Scope: Pair 1-6 (QE real-run smoke pairs)

## Non-Negotiable Rules

## End-User Only Simulation
1. Never load demo projects for these pairs.
2. Never write/patch YAML, SSOT, `.in`, `.win`, or any raw files directly.
3. All state changes must come from:
   - RPC calls (`daemon.handle_request`) for RPC tests.
   - GUI interactions only for e2e tests.
4. You may read YAML/raw files only for verification that user/RPC actions propagated correctly.

## Pairing Process
1. Build and pass RPC test first.
2. Then build GUI e2e test that mirrors the RPC operation sequence as closely as practical.
3. Run both and verify they pass before moving to next pair.

## QE Availability Policy
1. QE tests are never skipped.
2. If QE is missing or cannot execute, the test fails.

## CI Enforcement Rule
1. When a pair is finished and passing locally, add both RPC and e2e coverage to CI enforcement.
2. For e2e, include each realrun spec explicitly in `.github/workflows/tests.yml` Playwright command list.

## Validation Depth Requirements
1. Assert workflow success and deep analysis payloads, not only "response ok".
2. For step parameter edits made via RPC/GUI, verify persistence in both:
   - step YAML (`get_step_detail.absolute_path` read-only), and
   - generated raw inputs in `raw/` (`read_raw_file` / GUI Reveal path read-only).
3. For e2e analysis validation, explicitly:
   - select Analysis tab,
   - select the expected step chip,
   - click Plot,
   - disable Reference,
   - assert non-empty chart curves and axis/tick evidence.
4. For multi-step workflows, verify all expected analysis objects are reachable by step selection (for example SCF convergence plus bands/DOS objects where applicable).

## Parameter Guidance
1. Keep smoke settings practical and fast (not publication quality).
2. Use explicit k-mesh and k-path assertions where the pair intends to validate those editing capabilities.
3. Demos may be used only for parameter inspiration; never as loaded test content.

## Pair Inventory

## Pair 1: Si SCF
- RPC: `tests/daemon/contract/test_realrun_si_scf.py`
- E2E: `gui/tests/e2e/realrun_si_scf.spec.ts`
- Focus: single-step SCF creation/run/analysis from scratch.

## Pair 2: Si Relax (VC via parameter)
- RPC: `tests/daemon/contract/test_realrun_si_relax.py`
- E2E: `gui/tests/e2e/realrun_si_relax.spec.ts`
- Focus: `relax` step with `CONTROL.calculation=vc-relax`, convergence + trajectory.

## Pair 3: Si Bands
- RPC: `tests/daemon/contract/test_realrun_si_bands.py`
- E2E: `gui/tests/e2e/realrun_si_bands.spec.ts`
- Focus: `scf -> nscf -> bandspw -> bands`, automatic k-mesh plus custom `crystal_b` k-path editing.

## Pair 4: Si DOS
- RPC: `tests/daemon/contract/test_realrun_si_dos.py`
- E2E: `gui/tests/e2e/realrun_si_dos.spec.ts`
- Focus: `scf -> nscf -> dos`, DOS analysis integrity.

## Pair 5: Al DOS
- RPC: `tests/daemon/contract/test_realrun_al_dos.py`
- E2E: `gui/tests/e2e/realrun_al_dos.spec.ts`
- Focus: metallic DOS behavior, species/pseudo variation, optional online import in RPC.

## Pair 6: QE + Wannier90 Multi-Engine Workflow
- RPC: `tests/daemon/contract/test_realrun_qe_wannier.py`
- E2E: `gui/tests/e2e/realrun_qe_wannier.spec.ts`
- Focus: cross-engine chain from scratch:
  1. project + structure import (local C structure)
  2. QE steps: `scf -> nscf`
  3. Wannier steps: `wannierprep -> pw2wannier -> wannier`
  4. run full chain and validate generated artifacts

### Pair 6 Required Assertions
1. Step chain exists in expected order.
2. Key parameters edited through RPC/GUI are persisted in YAML and raw input/output artifacts.
3. Raw artifacts exist after run:
   - `wannierprep.nnkp`
   - `wannierprep.amn`
   - `wannierprep.mmn`
   - `wannierprep.wout`
   - `pw2wannier.out`
4. Job completes successfully with no failed step.
5. Analysis panel validation includes at least one real-run plotted object (for example SCF convergence) after disabling Reference.

## CI Notes
1. Keep all realrun e2e tests repo-relative for file paths (no machine-absolute paths).
2. Keep explicit test list in CI synchronized with available realrun specs (Pairs 1-6).

## Known Risk Notes
1. Some DOS numeric add-parameter GUI paths may serialize numbers as quoted strings depending on metadata hydration; keep tests aligned with currently valid UI paths and assert generated raw input validity.
2. Focus-mode navigation can be flaky if step selection exits focus mode; keep guarded selection logic and fail-fast assertions.

## Completion Checklist Per Pair
1. RPC test implemented and passing.
2. GUI e2e implemented and passing.
3. YAML/raw propagation assertions included (read-only checks).
4. Analysis plot assertions included (non-empty curve + axis/ticks).
5. Worklog updated with attempts/failures/lessons.
6. CI workflow updated to include the e2e spec.

