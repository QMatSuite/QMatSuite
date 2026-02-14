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
