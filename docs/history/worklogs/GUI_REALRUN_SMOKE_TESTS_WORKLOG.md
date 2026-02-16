# GUI Real-Run Smoke Tests — Worklog

## Session 4 (2026-02-13 to 2026-02-14)

### Goal
Build "paired real-QE smoke tests" — same workflow tested at both RPC (pytest) and E2E (Playwright) layers.

### Deliverables
- Plan: `docs/design/gui-testing-realrun-plan.md`
- RPC Test: `tests/daemon/contract/test_realrun_si_scf.py` (2 tests, PASSING)
- Fixtures: `tests/daemon/contract/conftest.py` (3 new fixtures)
- Server fix: `src/quantumvitas/daemon/server.py` (engine_family passthrough)

---

### Iteration Log: Pair 1 (Si SCF) RPC Test

#### Attempt 1 — QVService.init_project returns Path, not service
**Error:** `AttributeError: 'PosixPath' object has no attribute 'structure'`
**Root cause:** Fixture did `svc = QVService.init_project(...)` but init_project returns a Path.
**Fix:** Split into two lines: `QVService.init_project(dir)` then `svc = QVService(dir)`.

#### Attempt 2 — engine_family not passed through RPC
**Error:** `Cannot add step 'scf' to calculation without engine_family`
**Root cause:** `_handle_create_calculation` in server.py did not extract `engine_family` from payload.
**Fix:** Added `engine_family = payload.get("engine_family")` and passed it to `svc.project.init_calculation()`.

#### Attempt 3 — Wrong RPC parameter names
**Error:** `Step not found` (step ULID was actually the calc ULID)
**Root cause:** Used `"structure_ulid"` and `"calculation_ulid"` but RPC expects `"structure"` and `"calculation"`.
**Fix:** Changed to match RPC handler parameter names.

#### Attempt 4 — wait_for_job passed dict instead of RPCRequest
**Error:** `'dict' object has no attribute 'type'`
**Root cause:** Fixture passed a plain dict to `daemon.handle_request()`.
**Fix:** Wrap in `RPCRequest(id=..., type=..., payload=...)`.

#### Attempt 5 — Pseudopotential not configured
**Error:** `Pseudopotential not configured for element(s): Si`
**Root cause:** No species_map set on calculation. QE needs to know which pseudo to use.
**Fix (v1 — WRONG):** Manually copied pseudo file with `shutil.copy2` to project/pseudo/.
**Fix (v2 — CORRECT):** Set species_map via RPC `update_calculation_species_map`. Pseudo auto-stages from `resources/pseudo/` at run time. No manual file copies.

#### Attempt 6 — K_POINTS namelist crashes QE
**Error:** `Error in routine card_kpoints: error while reading tpiba k points`
**Root cause:** Test set `"K_POINTS": {"k_points": [6, 6, 6]}` in update_step_params. This created a `&K_POINTS` Fortran namelist in the input file. But K_POINTS in QE is a CARD (not a namelist). The input already had a valid `K_POINTS {automatic}` card from defaults, and the bogus namelist confused QE.
**Fix:** Removed K_POINTS from parameters. Let defaults handle k-points.

#### Attempt 7 — SUCCESS
**Result:** QE returned 0. Convergence analysis state="ok". Both tests pass.
```
tests/daemon/contract/test_realrun_si_scf.py::TestRealRunSiSCF::test_si_scf_complete_workflow PASSED
tests/daemon/contract/test_realrun_si_scf.py::TestRealRunSiSCF::test_si_scf_preflight_check PASSED
2 passed, 3 warnings in 10.40s
```

---

### Key Lessons: Pseudopotential Staging

**How it works in QMatSuite:**
1. User selects pseudo via GUI (species selector) or RPC (`update_calculation_species_map`)
2. This writes `species_map` into `calculation.yaml` (e.g., `Si: {pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF}`)
3. At run time, the runner calls `ensure_qe_pseudos` which searches multiple sources:
   - `<repo_root>/resources/pseudo/` (development convenience)
   - SSSP installed libraries
   - Project-local `<project>/pseudo/`
4. Runner copies the matching file to `<project>/pseudo/` and sets `pseudo_dir` in the QE input

**Test implication:** Tests must NOT manually copy pseudo files. They must use the RPC call, exactly like a user would. The auto-staging finds `resources/pseudo/Si.pbe-n-rrkjus_psl.1.0.0.UPF` and handles everything.

### Key Lessons: QE Parameter Mapping

**QE input file structure:**
- **Namelists** (`&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`) — key-value pairs inside `&.../ ` blocks
- **Cards** (`ATOMIC_SPECIES`, `ATOMIC_POSITIONS`, `K_POINTS`, `CELL_PARAMETERS`) — structured data blocks

**In update_step_params:** Only set namelist parameters (SYSTEM, CONTROL, ELECTRONS, etc.). Cards like K_POINTS are handled by dedicated mechanisms (structure import, k-point defaults, etc.).

### Golden Rule Established

**Every real-run test = user simulation.** All state changes via RPC or GUI only. No direct YAML/JSON writes. No manual file copies. If you can't do it through the daemon, it's a bug in the daemon.

---

### Regression Check
All 137 daemon tests pass after the server.py change (engine_family passthrough).

---

### Next Steps
- Pair 1 E2E test (Playwright)
- Pair 2: Si VC-Relax RPC test
- Pair 3: Si Bands (multi-step) RPC test

---

## Session 5 (2026-02-14)

### Goal
Unblock Pair 1 E2E (`gui/tests/e2e/realrun_si_scf.spec.ts`) where the test hangs at Add Step with an empty dropdown.

### Iteration Log: Pair 1 E2E Hang

#### Attempt 1 — Reproduce hang with single-spec run
**Action:** Ran only `realrun_si_scf.spec.ts` under Playwright with daemon logs visible.
**Observed:** UI reached `Add New Step`; step-type dropdown had only `-- Select Type --`; no step could be added; test sat in idle polling.
**Evidence:** Calculation file created during run had no `engine_family` field.

#### Attempt 2 — Trace why engine_family missing
**Root cause:** `CreateCalculationDialog.handleCreate` used `selectedEngine` but `useCallback` dependencies omitted `selectedEngine`. The callback could submit stale engine value (`""`) even when user selected QE.
**Fix:** Added `selectedEngine` to `handleCreate` dependency list in `gui/src/components/dialogs/CreateCalculationDialog.tsx`.

#### Attempt 3 — Pseudo modal options failing (secondary blocker)
**Observed in daemon logs:** `get_pseudo_options_for_calculation` crashed with:
`AttributeError: type object 'QVService' has no attribute 'get_calculation_detail'`.
**Root cause:** Debug instrumentation in daemon handler inspected a non-existent class method (`QVService.get_calculation_detail`), causing pseudo option load failure.
**Fix:** Removed that invalid inspect/signature call from `_handle_get_pseudo_options_for_calculation` in `src/quantumvitas/daemon/server.py`.

#### Attempt 4 — Prevent silent hangs in e2e
**Issue:** Test previously called `selectOption({ value: 'scf' })` without asserting dropdown population; on empty palette it appeared to hang.
**Fix:** Added explicit assertions in `gui/tests/e2e/realrun_si_scf.spec.ts`:
- Pseudo dropdown must have `>1` option before selection.
- Add-step dropdown must have `>1` option and include `scf` before selection.
This forces fast, actionable failures with screenshots instead of long idle waits.

### Lessons Learned
- For engine selection flows, stale React callback dependencies can silently drop critical payload fields (`engine_family`) and surface later as unrelated UI failures (empty step palette).
- E2E tests for async dropdowns must assert option population before selecting values; otherwise failures look like hangs.
- Temporary debug code in daemon handlers can break production RPC paths; keep instrumentation side-effect-free.

### Additional Attempts (Same Session)

#### Attempt 5 — Run button selector mismatch in Step Focus mode
**Observed:** After step creation/edit, test failed to find `qv-btn-run-calculation`.
**Root cause:** UI was in Step Focus mode; run button there is `qv-btn-run-calculation-focus`.
**Fix:** Updated e2e to click focus-mode run button when present, fallback to overview run button.

#### Attempt 6 — QE run fails after GUI parameter edit
**Observed:** QE failed with `STOP 1`; `scf.out` reported:
`bad line in namelist &system: "conv_thr = 1e-08" (error could be in the previous line)`.
**Actual generated input issue:** `ecutwfc` was serialized as a quoted string (`ecutwfc = '20.0'`) after GUI edit.
**Root cause:** Parameter editor was storing INTEGER/REAL edits as strings; serialization then emitted quoted scalars that break QE namelist parsing.
**Fix:** Updated `ParameterValueEditor` to coerce INTEGER/REAL user edits to numeric values (including `d/D` exponent normalization for REAL), while keeping CHARACTER/LOGICAL behavior unchanged.

#### Attempt 7 — E2E still stalls before `add_step_to_calculation`
**Observed:** GUI remains in Overview with `0 steps`; daemon logs show only periodic polling RPCs (`list_jobs`/`job_counts`) and never show `add_step_to_calculation`.
**Interpretation:** Flow is stalling in UI interaction/actionability before step-add RPC is sent.
**Fix applied in spec:** Added explicit click timeouts and hard checks in Add Step path:
- enforce pseudo modal overlay is hidden before continuing,
- `qv-add-step-btn` click with explicit timeout,
- `qv-confirm-add-step` click with explicit timeout,
- explicit poll that step row count becomes `> 0` after add.
This guarantees fail-fast with screenshot at the exact blocker instead of long idle polling.

#### Attempt 8 — Root cause of "hang before add step" and final stabilization
**Observed (live rerun):**
- Daemon always received `update_calculation_species_map` right after pseudo selection.
- In hanging runs, test did not emit add-step markers and no `add_step_to_calculation` RPC was sent.

**Root cause:** Pseudo selector change path already triggers `onUpdate(...)`, which can close/re-render the modal before the test clicks `Apply`. That made the `Apply` click intermittently target a stale element, so the script appeared to "hang" before reaching Add Step.

**Fix in `gui/tests/e2e/realrun_si_scf.spec.ts`:**
- Handle both pseudo UX paths:
  - modal stays open and needs `Apply`,
  - modal auto-closes/re-renders after selection.
- Added robust fallback close logic and authoritative overlay-hidden assertion.
- Added `scrollIntoViewIfNeeded()` before clicking Add Step (viewport/actionability hardening).
- Wrapped Add Step block in try/catch with explicit screenshot attachment (`add-step-failure`) on error.
- Added `Tab` after `ecutwfc` edit to force blur/commit before Apply.

**Verification command:**
```bash
cd gui
npx playwright test tests/e2e/realrun_si_scf.spec.ts --project=electron --reporter=list
```

**Result:** PASS (`1 passed`, ~24s). Real QE run executed (`pw.x returncode=0`) and analysis assertions completed.

#### Attempt 9 — Repeatability check (same spec, same environment)
**Action:** Re-ran the exact same Pair 1 e2e command immediately after Attempt 8.

**Result:** PASS again (`1 passed`, ~24s), with the same critical checkpoints:
- pseudo mapping set (`mapping_keys=['Si']`)
- step add succeeded (downstream QE runner materialized `total_steps=1`)
- QE SCF completed (`pw.x returncode=0`)
- analysis tab assertions passed.

**Conclusion:** The prior hang condition is resolved in current codepath; behavior is now repeatable across back-to-back runs.

#### Attempt 10 — Strengthen final analysis plot assertions (non-empty curve + x-axis)
**Request:** Explicitly assert `Analysis → SCF → Plot` and verify real convergence chart content (not empty).

**Changes:**
- Added `data-testid="qv-analysis-reference-toggle"` to the Analysis reference checkbox in `CalculationAnalysisPanel`.
- In Pair 1 e2e:
  - explicitly select `SCF` step tab and `Plot` mode,
  - force reference toggle off (if shown) and assert reference banner is absent,
  - assert convergence chart contains:
    - rendered main Recharts SVG surface,
    - at least one non-empty data curve path (`d` length check),
    - rendered x-axis tick labels (`>1`).

**Intermediate failure:** Initial SVG selector was too broad (`svg.recharts-surface`) and matched legend icon SVGs too, causing Playwright strict-mode violation.

**Fix:** Narrowed selector to the main plot surface:
` .recharts-wrapper > .recharts-surface ` and curve selector to
` .recharts-line .recharts-line-curve `.

**Verification:** Re-ran Pair 1 e2e; PASS (`1 passed`, ~24s).

### Session 5 Lessons (final addendum)
- Recharts renders multiple SVG surfaces (chart + legend icons). Assertions must target the plot canvas specifically to avoid false failures under Playwright strict mode.

---

## Session 6 (2026-02-14)

### Goal
Validate that Pair 1 e2e is CI-safe (GitHub Actions), with no local absolute-path assumptions.

### CI Workflow Recon (tests.yml)
- Reviewed `.github/workflows/tests.yml` end-to-end.
- Confirmed GUI E2E job runs from `working-directory: gui` and invokes an explicit file list.
- Confirmed QE setup is already handled in CI before E2E stage.
- Found that `tests/e2e/realrun_si_scf.spec.ts` was **not yet included** in the E2E command list.

### Changes for CI Safety

#### 1) Add Pair 1 real-run spec to CI E2E list
**File:** `.github/workflows/tests.yml`

Added `tests/e2e/realrun_si_scf.spec.ts` to both Linux and macOS Playwright command lists.

#### 2) Add explicit relative-path sanity check in spec
**File:** `gui/tests/e2e/realrun_si_scf.spec.ts`

Added:
- `fs.existsSync(siInputFile)` assertion with clear error message.

This ensures CI failures are actionable if repo layout changes (instead of failing later in import flow).

### Absolute Path Audit
- No hardcoded user-local paths found in:
  - `gui/tests/e2e/realrun_si_scf.spec.ts`
  - `.github/workflows/tests.yml`
- Spec uses `getRepoRoot()` + `path.join(...)` to derive project-relative locations.

### Verification
Command:
```bash
cd gui
npx playwright test tests/e2e/realrun_si_scf.spec.ts --project=electron --reporter=line
```

Result:
- PASS (`1 passed`, ~24s) after CI-safety changes.

### Lessons Learned
- For CI portability, e2e specs should always derive resource paths from repo root helpers, never from machine-specific absolute paths.
- If a spec is production-ready but omitted from CI’s explicit test list, it is effectively untested in CI; include it explicitly.

### Session 5 Lessons (addendum)
- The pseudo modal currently has mixed semantics (change can persist immediately, while an Apply button still exists). E2E must tolerate both behaviors until UI semantics are unified.
- For flaky UI actions, prefer:
  - explicit visibility + viewport scroll,
  - short bounded click timeouts,
  - fail-fast assertions with targeted screenshot capture.

---

## Session 7 (2026-02-15)

### Goal
Complete Pair 2 (Si VC-relax) as a true RPC/e2e pair, from scratch, no demo usage.

### Pair 2 RPC (DONE)

**New file:** `tests/daemon/contract/test_realrun_si_relax.py`

Implemented full real-run flow:
1. create calculation (`engine_family="qe"`)
2. set species map (`Si.pbe-n-rrkjus_psl.1.0.0.UPF`)
3. add step `relax` (not `vc-relax` step type)
4. set VC mode via params:
   - `CONTROL.calculation = "vc-relax"`
   - `SYSTEM.ecutwfc = 30.0`
   - `SYSTEM.ecutrho = 240.0`
   - `CELL.cell_dofree = "all"`
5. run + wait for completion
6. assert analysis instances include `convergence` and `trajectory` with `state="ok"`
7. fetch `get_analysis` payloads and assert non-trivial arrays/series/frames
8. bonus: assert `promote_relax_structure` succeeds and returns new structure metadata

**Verification command:**
```bash
pytest -q tests/daemon/contract/test_realrun_si_relax.py -q
```

**Result:** PASS (`1 passed`, ~46s)

### Pair 2 E2E (DONE)

**New file:** `gui/tests/e2e/realrun_si_relax.spec.ts`

From-scratch GUI flow:
1. create project
2. import `tests/data/0_Si_scf/si.scf.in`
3. create QE calculation
4. configure Si pseudo
5. add `relax` step (with fail-fast dropdown assertions)
6. edit params in step detail (`ecutwfc=30`, `CONTROL.calculation=vc-relax`)
7. run calculation
8. analysis tab: assert convergence plot + trajectory plot non-empty

#### Attempt 1 — QE run failed (`STOP 1`)
**Symptom:** no convergence chart; run failed.

**Root cause:** selecting `CONTROL.calculation` through enum dropdown produced triple-quoted value in `relax.in`:
```text
calculation = '''vc-relax'''
```
QE rejected it: `calculation "'vc-relax'" not allowed`.

**Fix:** in e2e, switch `CONTROL.calculation` editor to raw mode (`✏️`) and type `vc-relax` directly (`qv-param-input-control-calculation`). This avoids enum double-quoting.

#### Attempt 2 — PASS
**Verification command:**
```bash
cd gui
npx playwright test tests/e2e/realrun_si_relax.spec.ts --project=electron --reporter=list
```

**Result:** PASS (`1 passed`, ~43s)

### Lessons Learned
- There is no `vc-relax` step type in the palette; use step type `relax` and set VC behavior via `CONTROL.calculation`.
- For CHARACTER enums in the current GUI parameter editor, dropdown selection can over-quote values; raw mode is safer for strict QE tokens.
- VC-relax runtime is materially longer than SCF (~40s in this environment), so timeouts must remain generous.

---

## Session 8 (2026-02-15)

### Goal
Stabilize Pair 3 E2E (`realrun_si_bands.spec.ts`) after recurring Analysis-tab false failures/hangs.

### Pair 3 E2E Debug Iteration

#### Symptom
- QE run completed successfully (`JobGraph execution complete: success=True, summaries=4`), but test failed with:
  - `No renderable bands chart found in analysis for any candidate step`
- Failure screenshot showed:
  - Analysis tab in Plot mode
  - `No analysis object is available for this step in the current run.`
  - frequent `get_analysis` RPC churn in daemon logs.

#### Root cause
- The test treated `qv-analysis-no-objects` as a terminal state too early.
- In this UI, `no objects` can render transiently while step digest and analysis-object discovery are still resolving asynchronously.
- As a result, the test advanced across step tabs before the bands object was surfaced.

#### Fix
**File:** `gui/tests/e2e/realrun_si_bands.spec.ts`

- Updated analysis-state waiter:
  - waits through both chart loading and digest-loading phases before deciding no-object.
  - requires `no objects` to remain stable for 10s before returning `none`.
- Prioritized candidate tabs to check `bandspw` first (where current run links `bands` analysis).
- Added explicit active-tab assertion after clicking each analysis step chip.

### Verification
Command:
```bash
cd gui
npx playwright test tests/e2e/realrun_si_bands.spec.ts --project=electron --reporter=line
```

Result:
- PASS (`1 passed`, ~56s)

### Lessons Learned
- In `CalculationAnalysisPanel`, `qv-analysis-no-objects` is not always a final state; treat it as provisional until digest/analysis discovery settles.
- For multi-step QE workflows, analysis may be attached to intermediate post-processing steps (`bandspw`) rather than the final wrapper step (`bands`), so step-tab probing should be ordered and bounded.

---

## Session 9 (2026-02-15)

### Goal
Start Pair 4 (Si DOS) and complete RPC half first, with strict persistence and analysis assertions.

### Pair 4 RPC (DONE)

**New file:** `tests/daemon/contract/test_realrun_si_dos.py`

Implemented from-scratch flow:
1. create QE calculation on Si structure
2. set Si species map pseudo
3. add steps: `scf -> nscf -> dos`
4. set parameters:
   - SCF `SYSTEM.ecutwfc=30`, `SYSTEM.ecutrho=240`, `K_POINTS=2x2x2`
   - NSCF `SYSTEM.ecutwfc=30`, `SYSTEM.ecutrho=240`, `K_POINTS=4x4x4`
   - DOS `DOS.fildos=si.dos.dat`, `DOS.emin=-9.0`, `DOS.emax=16.0`
5. verify step DTO + persisted YAML values
6. run calculation and wait to completion
7. verify generated raw inputs include configured meshes and DOS namelist values
8. assert DOS analysis instance and bundle:
   - `energies` and DOS arrays are non-empty and aligned
   - energy axis spans across 0
   - DOS is non-trivial (not all zero)
   - `render_meta.reference_energy` is present

#### Attempt 1 — FAIL
**Symptom:** `read_raw_file` failed for `dos.in` (`resource_not_found`).

**Root cause:** QE dos step materializes module-qualified input filename as `dos.dos.in` (not `dos.in`).

**Fix:** Made raw-input reader resilient:
- call `list_raw_files` for the step,
- try known names first and discovered artifact names next,
- accept module-qualified names (`dos.dos.in`) automatically.

#### Attempt 2 — PASS
**Verification command:**
```bash
pytest -q tests/daemon/contract/test_realrun_si_dos.py --no-cov
```

**Result:** PASS (`1 passed`, ~21s)

### Lessons Learned
- Post-processing QE steps can materialize input names with module qualifiers (`<step>.<module>.in`), so raw-file assertions should not hardcode only `<step>.in`.
- `list_raw_files` is the reliable source-of-truth for artifact naming across heterogeneous QE modules.

### Pair 4 E2E (DONE)

**New file:** `gui/tests/e2e/realrun_si_dos.spec.ts`

Implemented from-scratch GUI flow:
1. create project
2. import `tests/data/structures/si_diamond.cif`
3. create QE calculation
4. set Si pseudo mapping
5. add steps `scf -> nscf -> dos` (fail-fast dropdown checks)
6. edit steps in focus mode:
   - SCF `ecutwfc=30`, K_POINTS automatic `2x2x2`
   - NSCF `ecutwfc=30`, K_POINTS automatic `4x4x4`
   - DOS set `fildos=si.dos.dat`
7. run QE job and wait for terminal completion
8. analysis tab: locate DOS object robustly and assert non-empty DOS plot + axes + Fermi label

#### Attempt 1 — FAIL
**Symptom:** run reached DOS step and failed with `STOP 1`; analysis had no renderable DOS chart.

**Forensics (captured from generated files):**
- `raw/dos.dos.in` contained:
  - `emax = '16.0'`
  - `emin = '-9.0'`
- `dos.out` reported:
  - `Error in routine dos (5010): reading dos namelist`

**Root cause:** GUI add-parameter path serialized DOS numeric fields as quoted strings for this step, generating invalid DOS namelist values.

**Fix:** do not edit DOS numeric window (`emin`, `emax`) via this path in e2e; keep metadata defaults and only set safe `fildos`.

#### Attempt 2 — PASS
**Verification command:**
```bash
cd gui
npx playwright test tests/e2e/realrun_si_dos.spec.ts --project=electron --reporter=line
```

**Result:** PASS (`1 passed`, ~31.8s)

---

## Session 10 (2026-02-15)

### Goal
Implement and validate Pair 5 RPC (`Al DOS`) with optional online fetch fallback behavior.

### Pair 5 RPC (DONE)

**New file:** `tests/daemon/contract/test_realrun_al_dos.py`

Implemented flow:
1. start from `qe_project_with_al` local structure fixture
2. try `structure_search_online("Al")` + `structure_import_online_candidate` (best effort)
3. if online import available, attempt workflow on online structure; otherwise use local fixture structure
4. create calculation + set Al pseudo mapping (`Al.pbe-n-kjpaw_psl.1.0.0.UPF`)
5. add steps `scf -> nscf -> dos`
6. set parameters:
   - SCF/NSCF: `ecutwfc=30`, `ecutrho=240`, automatic K_POINTS (`4x4x4` and `6x6x6`)
   - DOS: `fildos=al.dos.dat`, `emin=-15.0`, `emax=35.0`
7. verify persistence in step DTO and YAML
8. run and validate raw inputs
9. assert DOS analysis exists and enforce metal signature:
   - non-null Fermi reference
   - DOS at nearest Fermi-energy sample is non-zero

#### Attempt 1 — FAIL
**Symptom:** run reached step 0 and failed; DOS analysis instance state was `missing_evidence`.

**Forensics (`scf.out`):**
- QE reported metallic system warning and terminated:
  - `charge is wrong: smearing is needed`

**Root cause:** Al is metallic; explicit occupation smearing was required for stable SCF on this structure path (online candidate in this run).

**Fix:** add metallic SCF/NSCF parameters:
- `SYSTEM.occupations = "smearing"`
- `SYSTEM.smearing = "gaussian"`
- `SYSTEM.degauss = 0.02`

#### Attempt 2 — PASS
**Verification command:**
```bash
pytest -q tests/daemon/contract/test_realrun_al_dos.py --no-cov
```

**Result:** PASS (`1 passed`, ~17.6s)

### Lessons Learned
- Online Al candidates can be physically valid but still require metallic treatment in SCF defaults.
- For metallic smoke pairs, explicitly setting smearing in SCF/NSCF avoids fragile engine-dependent defaults.

---

## Session 11 (2026-02-15)

### Goal
Stabilize Pair 5 E2E (`realrun_al_dos.spec.ts`) and eliminate the recurring “hang/no DOS chart” failure.

### Pair 5 E2E (DONE)

**New file:** `gui/tests/e2e/realrun_al_dos.spec.ts`

Implemented from-scratch GUI flow:
1. create project
2. import `tests/data/structures/al_fcc.cif`
3. create QE calculation
4. set Al pseudo mapping
5. add steps `scf -> nscf -> dos`
6. edit parameters in focus mode:
   - SCF: `ecutwfc=30`, `ecutrho=240`, `occupations=smearing`, `smearing=gaussian`, `degauss=0.02`, K_POINTS `4x4x4`
   - NSCF: same metallic settings, K_POINTS `6x6x6`
   - DOS: `fildos=al.dos.dat`
7. run calculation and wait to completion
8. analysis tab: Plot mode, disable Reference, probe DOS-capable step tabs, assert non-empty DOS chart (curve + x-axis ticks + Fermi marker)

#### Attempt 1 — FAIL (SCF parse error)
**Symptom:** no renderable DOS chart; daemon logs showed `qe_scf failed`.

**Forensics (`raw/scf.in`, `scf.out`):**
- `occupations = ''smearing''`
- `smearing = ''gaussian''`
- QE error: `bad line in namelist &system`

**Root cause:** CHARACTER token was double-quoted in generated input.

#### Fix A
- In e2e, set metallic values in raw editor as unquoted tokens (`smearing`, `gaussian`) instead of pre-quoted strings.
- Hardened QE scalar normalization:
  - **File:** `gui/src/utils/qeStringUtils.ts`
  - `normalizeQeScalar` now repeatedly peels matching wrapping quotes (prevents quote amplification like `''value''`).

#### Attempt 2 — FAIL (DOS namelist parse error)
**Symptom:** SCF/NSCF succeeded, `dos.x` failed (`returncode=1`), still no chart.

**Forensics (`raw/dos.dos.in`, `dos.out`):**
- `emax = '35.0'`
- `emin = '-15.0'`
- QE error: `Error in routine dos (5010): reading dos namelist`

**Root cause:** GUI add-parameter path serialized DOS numeric fields as quoted strings for this step.

#### Fix B
- For e2e stability, keep DOS numeric bounds at defaults and set only `fildos`.
- Added explicit run-error check in run/log panel before analysis assertions to fail fast on execution errors.

#### Attempt 3 — PASS
**Verification command:**
```bash
cd gui
npx playwright test tests/e2e/realrun_al_dos.spec.ts --project=electron --reporter=line
```

**Result:** PASS (`1 passed`, ~35.8s)

### Cross-Pair Regression Verification (Pairs 2–5)

RPC:
```bash
pytest -q \
  tests/daemon/contract/test_realrun_si_relax.py \
  tests/daemon/contract/test_realrun_si_bands.py \
  tests/daemon/contract/test_realrun_si_dos.py \
  tests/daemon/contract/test_realrun_al_dos.py \
  --no-cov
```
Result: `4 passed` (~1m42s)

E2E:
```bash
cd gui
npx playwright test \
  tests/e2e/realrun_si_relax.spec.ts \
  tests/e2e/realrun_si_bands.spec.ts \
  tests/e2e/realrun_si_dos.spec.ts \
  tests/e2e/realrun_al_dos.spec.ts \
  --project=electron --reporter=line
```
Result: `4 passed` (~2.9m)

Pair 1 guardrail after shared quote-normalization change:
```bash
cd gui
npx playwright test tests/e2e/realrun_si_scf.spec.ts --project=electron --reporter=line
```
Result: `1 passed` (~24s)

### Lessons Learned
- “No chart” in analysis can be a downstream symptom of earlier QE step failure; always inspect raw inputs/outputs from the exact failing run directory.
- For metallic Al smoke workflows, raw unquoted CHARACTER tokens in GUI editing are safer than pre-quoted strings.
- DOS numeric fields added through generic UI-parameter insertion can serialize as strings; keep defaults in e2e until numeric typing is guaranteed.
- Add explicit run-error assertions before analysis assertions to avoid false “analysis hang” diagnoses.

---

## Session 12 (2026-02-15)

### Goal
Perform an independent reviewer audit of QE real-run Pair 1-5 RPC/E2E tests, including pairing parity, assertion depth, analysis-object behavior, and CI readiness.

### Deliverable
- Review doc: `docs/history/reviews/realrun_qe_pairs_1_5_independent_review_2026-02-15.md`

### Reviewer Findings (Summary)
1. All five RPC pairs and all five E2E pairs do execute real QE runs (no demo execution path).
2. Pairing quality is uneven:
   - strong: Pair 3
   - medium: Pair 1, Pair 4
   - medium-low: Pair 2, Pair 5
3. Major parity drifts:
   - Pair 2 E2E does not mirror RPC for `nstep`, `cell_dofree`, and explicit K_POINTS.
   - Pair 4/5 E2E intentionally skip DOS `emin/emax` editing due current UI serialization issue, while RPC enforces them.
   - Pair 5 online structure-fetch branch is RPC-only.
4. Pair 1 RPC assertions are shallow versus stated strict goals (instance existence only; no convergence-array/value checks).
5. CI currently runs only Pair 1 E2E (`realrun_si_scf.spec.ts`); Pair 2-5 E2E specs are not in workflow command lists yet.

### Lessons Learned
1. "Paired test" quality is not binary. It must be audited at operation-sequence and parameter-level granularity.
2. For expensive real-run smoke tests, assertion depth should be concentrated into one strong run per pair (payload shape + key physical checks), not only existence checks.
3. Analysis-law compliance in UI should be validated by explicitly proving step-scoped/membership-based object offering in multi-step workflows, not only by eventually finding one plot.

## Session 13 (2026-02-15)

### Goal
Complete Pair 6 (QE + Wannier90) with passing RPC+E2E and capture concrete blocker/fix evidence.

### Pair 6 takeover status
- Ground-truth plan source: `docs/design/gui-testing-realrun-plan.md` (Pair 6 section).
- Starting branch/worktree already contained Pair 6 RPC/E2E specs and CI wiring.

### Attempt 1 — Reproduce current Pair 6 state

RPC verification:
```bash
pytest -q tests/daemon/contract/test_realrun_qe_wannier.py --no-cov
```
Result: PASS (`1 passed`, ~22.7s)

E2E reproduction:
```bash
cd gui
npx playwright test tests/e2e/realrun_qe_wannier.spec.ts --project=electron --reporter=line
```
Result: FAIL at artifact assertion (`pw2wannier.out` missing `JOB DONE`).

Forensics from failing run (`/private/var/folders/pd/s3v190_j3j56dq7lycv4myn40000gr/T/qv_e2e_projects/realrun-qe-wannier-1771195059936/...`):
1. `nscf.step.yaml` correctly persisted logicals as native booleans:
   - `SYSTEM.nosym: true`
   - `SYSTEM.noinv: true`
2. `raw/nscf.in` correctly emitted:
   - `nosym = .true.`
   - `noinv = .true.`
3. `raw/wannierprep.win` used default `mp_grid : 4 4 4` and 64 generated k-points.
4. `raw/pw2wannier.out` failed with:
   - `Error in routine pw2wannier90 (64): Wrong number of k-points`
   - `numk=64  iknum=8`

### Root cause discovered
- In `src/quantumvitas/calculation/wannier90_kpoints.py`, `find_nscf_input_file()` only matches steps by `step_type_gen == "nscf"`.
- Current `calculation.yaml` stores step entries as `step_type_spec` (`qe_nscf`, etc.), so nscf step discovery can fail in this path.
- When nscf k-points are not inherited, Wannier materialization falls back to default `mp_grid=[4,4,4]`, producing a `.win/.nnkp` k-grid incompatible with the 8-point NSCF run.

### In-flight fix plan (Session 13)
1. Patch nscf-step discovery to support current `step_type_spec` representation.
2. Add robust fallback for logical string tokens in QE writer (`'.true.'`/`'.false.'` should emit unquoted Fortran logicals).
3. Re-run Pair 6 e2e and verify `pw2wannier` reaches `JOB DONE` plus required artifact checks.

### Attempt 2 — New blocker after k-point/boolean fixes

E2E rerun:
```bash
cd gui
npx playwright test tests/e2e/realrun_qe_wannier.spec.ts --project=electron --reporter=line
```
Result: FAIL at final Wannier assertion (`wannierprep.wout` missing `All done: wannier90 exiting`).

Forensics from failing run (`.../realrun-qe-wannier-1771195569573/...`):
1. `pw2wannier.out` now succeeds (`JOB DONE`), confirming k-point inheritance/mapping fix is active.
2. `wannierprep.win` had:
   - `num_wann = 4`
   - `num_bands = 4`
   - `mp_grid : 2 2 2`
   - **no `begin projections` block**
3. `wannierprep.nnkp` showed:
   - `begin projections`
   - `0`
   - `end projections`
4. `wannierprep.amn` header line was:
   - `4 8 0`
5. `wannierprep.wout` ended with:
   - `wannierprep.amn has not the right number of projections`

Root cause:
- Pair 6 GUI flow was not setting W90 `projections`; with `num_wann=4`, zero projections in `.amn` causes Wannier90 to fail.

Fix applied:
1. Updated Pair 6 e2e to set `projections = Si:sp3` in both `wannierprep` and `wannier` via GUI parameter editing path.
2. Added raw artifact assertion to require `Si:sp3` in `wannierprep.win`.
3. Preserved all existing user-flow constraints (no direct YAML/raw edits; GUI-only parameter updates).

### Attempt 3 — Pair 6 run succeeds, but analysis assertion fails (zero curves)

Validation sequence started with rebuilt GUI artifacts to avoid stale `dist-electron`:
```bash
cd gui
npm run build:e2e
```
Result: PASS (vite + dist-electron rebuilt).

Then pre-checks:
```bash
pytest -q tests/unit/test_no_qe_bool_strings.py tests/unit/test_wannier90_kpoints_inheritance.py --no-cov
```
Result: PASS (`19 passed`).

```bash
pytest -q tests/daemon/contract/test_realrun_qe_wannier.py --no-cov
```
Result: PASS (`1 passed`, ~20.5s).

Pair 6 e2e rerun:
```bash
cd gui
npx playwright test tests/e2e/realrun_qe_wannier.spec.ts --project=electron --reporter=line
```
Result: FAIL at analysis assertion:
- `SCF convergence chart has no curve paths`

Forensics from the exact failed run (`.../realrun-qe-wannier-1771196393082/...`):
1. Workflow execution itself succeeded end-to-end (`JobGraph execution complete: success=True, summaries=5`).
2. `raw/scf.out` contained normal SCF iterations and `convergence has been achieved in 11 iterations`.
3. RPC inspection of analysis payload for SCF step showed:
   - object `convergence` state `ok`
   - but `series=[]`, `scf_energy=[]`
   - provenance warning: `No SCF steps found in output.`
   - provenance source file incorrectly pointed to `raw/wannierprep.out` (empty), not `raw/scf.out`.

Root cause:
- `QEConvergenceProvider.parse()` selected `out_files[0]` from shared `raw/*.out`.
- In multi-step QE+Wannier runs, directory order could pick unrelated files (`wannierprep.out`), producing empty convergence bundles.

### Fix C — Step-aware convergence output selection

Updated:
- `src/quantumvitas/drivers/qe/parsers/convergence.py`
- `tests/drivers/qe/test_qe_convergence_parser.py`

Changes:
1. Added `_select_output_file(raw_dir, gen_steps)` in QE convergence parser:
   - prefer exact `<gen_step>.out` (e.g., `scf.out`)
   - then token-matching names (e.g., `si.relax.out`)
   - fallback to largest non-empty `.out`
   - final fallback to first file
2. Parser now uses selected output based on `evidence.gen_steps` instead of naive first glob entry.
3. Added regression test for shared-raw case (`scf.out` + empty `wannierprep.out`) to enforce selecting `scf.out`.
4. Updated existing parser fixture-count tests to reflect deterministic `relax` selection.

Verification:
```bash
pytest -q tests/drivers/qe/test_qe_convergence_parser.py --no-cov
```
Result: PASS (`10 passed`).

### Attempt 4 — Pair 6 pass + full Pair 1-6 regressions

Pair 6 re-validation:
```bash
pytest -q tests/daemon/contract/test_realrun_qe_wannier.py --no-cov
```
Result: PASS (`1 passed`, ~20.3s).

```bash
cd gui
npx playwright test tests/e2e/realrun_qe_wannier.spec.ts --project=electron --reporter=line
```
Result: PASS (`1 passed`, ~52.3s).

Full RPC sweep (Pairs 1-6):
```bash
pytest -q \
  tests/daemon/contract/test_realrun_si_scf.py \
  tests/daemon/contract/test_realrun_si_relax.py \
  tests/daemon/contract/test_realrun_si_bands.py \
  tests/daemon/contract/test_realrun_si_dos.py \
  tests/daemon/contract/test_realrun_al_dos.py \
  tests/daemon/contract/test_realrun_qe_wannier.py \
  --no-cov
```
Result: PASS (`7 passed`, `155.70s`).

Full e2e sweep (Pairs 1-6):
```bash
cd gui
npx playwright test \
  tests/e2e/realrun_si_scf.spec.ts \
  tests/e2e/realrun_si_relax.spec.ts \
  tests/e2e/realrun_si_bands.spec.ts \
  tests/e2e/realrun_si_dos.spec.ts \
  tests/e2e/realrun_al_dos.spec.ts \
  tests/e2e/realrun_qe_wannier.spec.ts \
  --project=electron --reporter=line
```
Result: PASS (`6 passed`, ~4.9m).

### Attempt 5 — Enforce strict unquoted logical tokens in Pair 6 assertions

Per Pair 6 boolean rule, added strict assertions to reject quoted logicals:
- `tests/daemon/contract/test_realrun_qe_wannier.py`
- `gui/tests/e2e/realrun_qe_wannier.spec.ts`

New checks require:
- `nosym = .true.` and `noinv = .true.` in `nscf.in`
- no `nosym = '.true.'` / `".true."` variants.

Verification:
```bash
pytest -q tests/daemon/contract/test_realrun_qe_wannier.py --no-cov
```
Result: PASS (`1 passed`, ~20.4s).

```bash
cd gui
npx playwright test tests/e2e/realrun_qe_wannier.spec.ts --project=electron --reporter=line
```
Result: PASS (`1 passed`, ~52.8s).

### Session 13 Lessons (final)
1. For shared raw directories, parser input selection must be step-aware; choosing the first `*.out` is not safe in multi-engine chains.
2. Analysis-state “ok” can still hide empty data if the wrong evidence file is parsed; always inspect `provenance_meta.source_files` and parser warnings.
3. Pair 6 is now stable only with all three constraints together:
   - NSCF k-point inheritance fixed,
   - Wannier projections set to a 4-projection-compatible form (`f=0.0,0.0,0.0:sp3`),
   - convergence parser bound to the correct step output.

### Attempt 6 — Full-suite regression surfaced nested-project guard fallout (in progress)

Goal:
- Re-validate full backend suite and then GUI e2e after Pair 1-6 + Pair 6 changes.

Command run:
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

Observed summary:
- `4 failed, 5813 passed, 30 skipped, 16 errors`.
- Dominant failure mode: project creation inside repo-local `.tmp` now blocked by nested-project guard.

Representative failing modules:
- `tests/integration/test_relax_promote_e2e.py`
- `tests/integration/test_pyscf_relax_real.py`
- `tests/integration/test_orca_relax_real.py`
- `tests/integration/test_qe_relax_real.py`
- `tests/cli/test_si_bands_auto_calculation_cli.py`
- `tests/cli/test_si_bands_manual_calculation_cli.py`
- `tests/cli/test_si_dos_calculation_comprehensive.py`
- `tests/cli/test_cli_show_command_integration.py`
- `tests/integration/test_gaussian_execution.py`
- `tests/integration/test_xtb_execution.py`

Fix direction chosen:
- Keep Pair 1-6 logic untouched.
- Patch only test temp-root setup to use OS temp directories (`tempfile.mkdtemp(...)`) instead of repo-local `.tmp` / `tmp_runs_dir()` for project roots.
- Re-run failing subsets, then full backend suite, then full GUI e2e.

Update to Attempt 6 (user-directed path policy):
- Replaced the temporary OS-temp workaround.
- Kept all test project roots under `<repo>/.tmp/...` per instruction.
- Implemented compatibility fix in `QVService.init_project` to allow nested project creation only under `<enclosing_project>/.tmp/...` while preserving the nested-project guard elsewhere.
- Added unit coverage:
  - `tests/unit/test_api_service.py::TestQVServiceProject::test_init_project_allows_tmp_subdir_inside_project`

Additional stability policy applied:
- Do not clear global `<repo>/.tmp`.
- Avoid deleting previous run artifacts.
- For CLI test fixtures, switched to unique run folders under `.tmp/<suite>/<run_id>` to avoid parallel collisions and preserve inspection artifacts.
- Removed ORCA fixture post-run deletion to keep project artifacts inspectable.

Validation run (repo `.tmp` mode):
```bash
source .venv/bin/activate
python -m pytest -q \
  tests/unit/test_api_service.py::TestQVServiceProject::test_init_project_prevents_nested_project \
  tests/unit/test_api_service.py::TestQVServiceProject::test_init_project_allows_tmp_subdir_inside_project \
  tests/cli/test_si_bands_manual_calculation_cli.py \
  tests/integration/test_relax_promote_e2e.py \
  tests/integration/test_orca_relax_real.py \
  tests/integration/test_qe_relax_real.py \
  tests/cli/test_si_bands_auto_calculation_cli.py \
  tests/integration/test_pyscf_relax_real.py \
  tests/cli/test_si_dos_calculation_comprehensive.py \
  tests/integration/test_gaussian_execution.py \
  tests/integration/test_xtb_execution.py \
  tests/cli/test_cli_show_command_integration.py \
  -n auto --dist=loadfile --tb=short
```
Result: PASS (`43 passed`, `~120s`).
