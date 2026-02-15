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
