# Independent Review: QE Real-Run Pairs 1-5 (RPC + E2E)

Date: 2026-02-15  
Reviewer mode: independent, post-implementation audit

## Scope Reviewed
1. RPC tests:
   - `tests/daemon/contract/test_realrun_si_scf.py`
   - `tests/daemon/contract/test_realrun_si_relax.py`
   - `tests/daemon/contract/test_realrun_si_bands.py`
   - `tests/daemon/contract/test_realrun_si_dos.py`
   - `tests/daemon/contract/test_realrun_al_dos.py`
2. E2E tests:
   - `gui/tests/e2e/realrun_si_scf.spec.ts`
   - `gui/tests/e2e/realrun_si_relax.spec.ts`
   - `gui/tests/e2e/realrun_si_bands.spec.ts`
   - `gui/tests/e2e/realrun_si_dos.spec.ts`
   - `gui/tests/e2e/realrun_al_dos.spec.ts`
3. Supporting fixtures and contracts:
   - `tests/daemon/contract/conftest.py`
   - `gui/src/components/panels/CalculationAnalysisPanel.tsx`
   - `docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`
   - `.github/workflows/tests.yml`

## Executive Verdict
1. The suite does exercise real QE runs for all five pairs at RPC and E2E layers.
2. The suite is strong on "from scratch" user flow and analysis visualization checks.
3. RPC/E2E parity is uneven. Pair 3 is tight. Pair 2, 4, and 5 have meaningful sequence/parameter drift between RPC and E2E.
4. Assertion depth is generally good for expensive real runs in pairs 2-5 RPC and in all E2E chart checks, but Pair 1 RPC is currently shallow relative to the stated plan.
5. CI currently executes only Pair 1 E2E. Pairs 2-5 E2E are not in workflow execution yet.

## Do These Tests Really Call Real QE?
Yes.

Evidence:
1. RPC fixtures enforce QE presence with fail-fast behavior (`qe_available` uses `get_qe_engine_status()` and calls `pytest.fail` if not found) in `tests/daemon/contract/conftest.py`.
2. All Pair 1-5 RPC tests invoke `run_calculation` and wait for terminal job status via polling (`wait_for_job`), then assert analysis outputs.
3. All Pair 1-5 E2E tests invoke GUI "Run Calculation", monitor Run & Logs for completion/failure, then validate plot-mode analysis with reference toggle forced off.
4. No pair relies on demo project loading for execution.

## Pair-by-Pair Review

## Pair 1: Si SCF
RPC (`test_realrun_si_scf.py`) covers:
1. create calculation
2. species map update for Si pseudo
3. add `scf`
4. set `SYSTEM.ecutwfc=20.0`
5. run and wait
6. verify convergence analysis instance exists/state fields exist

E2E (`realrun_si_scf.spec.ts`) covers:
1. create project from welcome flow
2. import structure file
3. create QE calculation
4. set pseudo (with modal race hardening)
5. add `scf` with explicit non-empty step-dropdown assertion
6. edit `ecutwfc=20.0`
7. run and wait
8. analysis: click `SCF` step tab, click Plot, force reference off
9. assert convergence chart visible, non-empty curves, x-axis ticks, converged badge

Parity verdict: Medium.

Key gaps:
1. RPC does not fetch convergence bundle arrays (`get_analysis`) or assert energy sequence properties (length, sign, convergence trend), despite plan expectations.
2. Structure source differs from other pairs and from stated CIF preference. Pair 1 E2E imports `tests/data/0_Si_scf/si.scf.in` while later pairs use CIF.

## Pair 2: Si VC-Relax
RPC (`test_realrun_si_relax.py`) covers:
1. add `relax` and set VC via `CONTROL.calculation="vc-relax"`
2. set `nstep=3`, `ecutwfc/ecutrho`, `CELL.cell_dofree="all"`
3. set K_POINTS automatic `2x2x2`
4. read-back DTO assertions
5. YAML persistence assertions
6. raw input assertions (`relax.in` contains expected K_POINTS and `nstep`)
7. run and wait
8. analysis instance assertions for both `convergence` and `trajectory`
9. deep payload assertions for both objects

E2E (`realrun_si_relax.spec.ts`) covers:
1. same from-scratch setup and pseudo flow
2. add `relax`
3. set `ecutwfc=30.0` and `CONTROL.calculation=vc-relax` (raw editor path)
4. run and wait
5. analysis: verify non-empty convergence plot
6. switch analysis object to trajectory and verify non-empty trajectory plot and frame counter

Parity verdict: Medium-Low.

Key gaps:
1. E2E does not set or verify `nstep=3`, `CELL.cell_dofree="all"`, or explicit K_POINTS `2x2x2` that RPC enforces.
2. Bonus promote flow is not asserted (RPC explicitly documents omission).

## Pair 3: Si Bands
RPC (`test_realrun_si_bands.py`) covers:
1. steps: `scf -> nscf -> bandspw -> bands`
2. explicit K mesh edits:
   - SCF `2x2x2`
   - NSCF `4x4x4`
3. explicit custom `crystal_b` path in `bandspw`
4. set `BANDS.filband="bands.dat"` on bands step
5. DTO and YAML persistence assertions for K_POINTS path/mesh
6. raw input assertions for `scf.in`, `nscf.in`, `bandspw.in`
7. run and wait
8. analysis assertions on bands payload shape/labels/markers/reference energy

E2E (`realrun_si_bands.spec.ts`) covers:
1. same from-scratch setup and pseudo flow
2. add same 4-step chain
3. robust focus-mode navigation to each step
4. set SCF `2x2x2`, NSCF `4x4x4`, and custom `crystal_b` k-path line-by-line
5. set `filband=bands.dat`
6. run with stale-completion guard (`sawActiveState`)
7. analysis: select Plot and force reference off
8. probe candidate step tabs, open bands tile if needed
9. assert non-empty bands chart curves, axis ticks, kpath label, fermi label

Parity verdict: High.

Key gaps:
1. Neither RPC nor E2E additionally verifies SCF convergence analysis object in this multi-step workflow, even though laws allow multiple objects per selected-step membership.
2. No explicit band-gap range assertion (planned "strict" target) yet.

## Pair 4: Si DOS
RPC (`test_realrun_si_dos.py`) covers:
1. steps: `scf -> nscf -> dos`
2. explicit K mesh edits (`2x2x2`, `4x4x4`)
3. DOS params set including `fildos`, `emin`, `emax`
4. DTO + YAML persistence checks
5. raw input checks including DOS namelist values
6. run and wait
7. DOS analysis payload assertions (array length, alignment, axis range, non-zero DOS, reference energy present)

E2E (`realrun_si_dos.spec.ts`) covers:
1. same from-scratch setup and pseudo flow
2. add `scf -> nscf -> dos`
3. set SCF/NSCF K meshes and `ecutwfc`
4. set DOS `fildos` only
5. run with stale-completion guard
6. analysis: locate DOS object across candidate step tabs
7. assert non-empty DOS plot curves, axis ticks, and non-empty fermi label

Parity verdict: Medium.

Key gaps:
1. E2E intentionally does not set DOS `emin/emax` due known current UI serialization issue (quoted numeric strings). RPC does set/verify them.
2. E2E therefore cannot yet prove full user editing path for DOS numeric window fields.

## Pair 5: Al DOS
RPC (`test_realrun_al_dos.py`) covers:
1. optional online structure search/import, fallback to local Al CIF
2. `scf -> nscf -> dos`
3. explicit metallic settings in SCF/NSCF:
   - `occupations=smearing`
   - `smearing=gaussian`
   - `degauss=0.02`
4. explicit K meshes (`4x4x4`, `6x6x6`)
5. DOS params (`fildos`, `emin`, `emax`)
6. DTO + YAML + raw input checks
7. run and wait
8. metallic signature assertion: DOS near Fermi is non-zero

E2E (`realrun_al_dos.spec.ts`) covers:
1. local Al CIF import (no online branch in E2E)
2. same step chain
3. same metallic SCF/NSCF settings
4. same K meshes
5. DOS `fildos` only
6. run and wait with explicit run-error checks
7. analysis: locate DOS chart and assert non-empty curves, axis ticks, fermi marker

Parity verdict: Medium-Low.

Key gaps:
1. Online fetch path is RPC-only; GUI equivalent path not covered.
2. DOS `emin/emax` edit path mismatch same as Pair 4.

## Are RPC and GUI Tests Really in Pairs (Same Operation Footing)?
Partial.

Pairing quality by pair:
1. Pair 1: partially paired
2. Pair 2: materially drifted
3. Pair 3: strongly paired
4. Pair 4: partially paired
5. Pair 5: partially paired

Main parity drifts:
1. Parameter parity drift in Pair 2 (`nstep`, `cell_dofree`, K_POINTS).
2. DOS numeric window drift in Pairs 4 and 5 (`emin/emax` only in RPC).
3. Optional online import branch in Pair 5 exists only in RPC.
4. Pair 1/2 E2E uses `.in` structure import while the newer pattern and most pairs use CIF.

## Real User Workflow Coverage Assessment
If I were an end user creating valid DFT flows from scratch, I would do:
1. Create project.
2. Import local structure.
3. Create QE calculation and choose structure.
4. Pick pseudo for each species.
5. Add required workflow steps.
6. Edit key QE parameters.
7. Edit K_POINTS in automatic and path modes when needed.
8. Run and monitor completion.
9. Inspect analysis per step and per object, in plot mode, real-run data (not reference).

Coverage status:
1. Steps 1-5: covered in all 5 RPC/E2E pairs.
2. Step 6: covered in all pairs, but with some drift (Pair 2/4/5 E2E vs RPC).
3. Step 7: strongly covered in Pair 3 (automatic mesh + custom k-path line-by-line); covered for automatic mesh in Pairs 4/5.
4. Step 8: covered in all pairs.
5. Step 9: covered in all E2E, with strong chart non-empty assertions.
6. Multi-object per-step analysis behavior is only partially validated (best in Pair 2; incomplete in Pair 3 for convergence+bands dual checks).

## Analysis-Object Law Compliance Check
Against `docs/laws/L2/ANALYSIS_OBJECT_PRIMITIVES_SPEC.md`:
1. Good: tests explicitly select analysis step tabs and verify plotting from real-run data with reference toggle off.
2. Good: membership-based behavior is tolerated in E2E by candidate-step probing for bands/dos objects.
3. Gap: tests do not explicitly validate full Domain-B step-scoped enumeration semantics for all expected objects in multi-step workflows.
4. Gap: in current UI implementation (`CalculationAnalysisPanel.tsx`), available object types are detected by global `get_analysis(run_ulid, object_type)` probes then filtered by `bundle.provenance_meta.step_ulids.includes(selectedStepId)`. This enforces membership but does not directly exercise/guarantee a dedicated step-scoped listing endpoint behavior.

## CI Readiness
1. Path safety is good for E2E:
   - Uses repo-relative derivation via `getRepoRoot()` and `path.join(...)`.
   - No hardcoded machine-local absolute paths in pair specs.
2. QE provisioning in CI is already robust in `.github/workflows/tests.yml`.
3. RPC pairs 1-5 should run in CI because pytest runs `tests/` broadly.
4. E2E CI currently includes only `realrun_si_scf.spec.ts`; Pairs 2-5 E2E are not yet executed in workflow command lists.

## High-Impact Improvements (Prioritized)

1. Raise Pair 1 RPC assertion depth:
   - add `get_analysis(..., object_type="convergence")` and assert:
     - non-empty energy arrays (`>1`)
     - negative final energy
     - simple convergence trend checks.
2. Tighten Pair 2 RPC/E2E parity:
   - E2E should set and verify `nstep=3`, `CELL.cell_dofree=all`, and K_POINTS `2x2x2` to mirror RPC.
3. Fix DOS numeric editing path in GUI parameter flow:
   - then update Pair 4/5 E2E to set and verify `emin/emax` exactly as RPC.
4. Add explicit pseudo-file assertions in E2E:
   - verify selected pseudo basename matches expected (`Si.pbe-n-rrkjus...`, `Al.pbe-n-kjpaw...`) instead of "first non-empty option".
5. Expand analysis-object assertions for multi-step workflows:
   - Pair 3 should validate both:
     - SCF step exposes/plots convergence object
     - bandspw/bands step exposes/plots bands object.
6. Wire Pairs 2-5 E2E into `.github/workflows/tests.yml` so they are continuously enforced.
7. Add dedicated Domain-B step-scoped API contract tests:
   - selected step returns only instances whose span includes that step ULID.

## Suggested Pair 6 (High Value): QE + Wannier90 Real-Run Pair
If Wannier90 is guaranteed in environment alongside QE, add a multi-engine workflow pair:
1. RPC:
   - from-scratch project and structure import
   - QE SCF/NSCF + Wannier-related steps through public RPC only
   - run full chain
   - assert Wannier artifacts and analysis objects (for example interpolated bands/centers/spreads depending on current exposed contracts)
2. E2E:
   - same sequence through GUI
   - explicit per-step analysis selection and plot assertions
3. Value:
   - validates cross-engine orchestration, provenance linkage, and analysis object rendering beyond single-engine QE-only chains.

## Final Assessment
1. The Pair 1-5 suite is a strong foundation and demonstrably real-run.
2. It is not yet fully "strictly paired" in operation sequence and parameter parity across all five pairs.
3. The biggest quality lifts now are parity tightening (Pairs 2/4/5), deeper Pair 1 RPC analysis assertions, and CI inclusion of E2E Pairs 2-5.
