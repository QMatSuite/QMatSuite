# GUI Testing: Real QE Smoke Test Pairs — Plan

## Document Status
- **Created:** 2026-02-13
- **Updated:** 2026-02-14
- **Session:** 4
- **Status:** Pair 1 RPC DONE, E2E pending

---

## Golden Rule: You Are a User

**Every real-run test must behave exactly as a GUI user would.**

- All state changes go through **RPC calls** (daemon.handle_request) or **GUI interactions** (Playwright).
- **Never** directly write/patch/modify YAML, YML, or JSON files.
- **Never** manually copy files into project directories (pseudo, structure, etc.).
- Structures are imported via `svc.structure.import_file()` (API) or RPC `import_structure`.
- Pseudopotentials are selected via RPC `update_calculation_species_map` — the runner auto-stages from `<repo_root>/resources/pseudo/` at run time.
- You may **read** YAML/JSON for debugging, but the test itself must not write them.
- If a test needs something configured, there must be an RPC call that does it.

**Why:** If a test bypasses the API layer, it doesn't prove the user journey works. The whole point of these tests is to validate that a real user can do this through the GUI/daemon.

---

## Reconnaissance Findings

### QE Installation Status

**QE Home:** `<ENGINE_ROOT>/qe/q-e-qe-7.5`

**Available Executables:**
- `pw.x` — Self-consistent field, relaxation, MD
- `dos.x` — Density of states post-processing
- `bands.x` — Band structure post-processing
- `projwfc.x` — Projected DOS
- `pp.x` — Post-processing (charge density, potentials)
- `ph.x` — Phonons (not needed for smoke tests)

**Detection Status:** QE auto-detected, ready to use

### QE Step Types Available

**Core calculation types:**
- `qe_scf` — Self-consistent field (ground state)
- `qe_relax` — Atomic positions relaxation
- `qe_nscf` — Non-self-consistent field (for DOS/bands)
- `qe_bands` — Band structure calculation
- `qe_dos` — Density of states
- `qe_pdos` — Projected DOS

**Additional types (not needed for smoke tests):**
- `qe_ph`, `qe_gipaw`, `qe_q2r`, `qe_matdyn`, `qe_dynmat`, `qe_pp`, `qe_plotband`, `qe_hp`

### Test Data Available

**Existing QE test inputs:**
- `tests/data/0_Si_scf/si.scf.in` — Simple Si SCF (2 atoms, FCC diamond)
- `tests/data/3_Si_vc_relax/si.vc_relax.in` — Si variable-cell relaxation
- `tests/data/6_Al_DOS/al.{1..4}.in` — Al DOS workflow (relax -> SCF -> NSCF -> DOS)

**Structure extraction:** Import directly from QE `.in` files using `svc.structure.import_file()`.

### Pseudopotential Strategy (RESOLVED)

**Pseudos are auto-staged.** The runner resolves pseudopotentials from multiple sources, including `<repo_root>/resources/pseudo/`. The user only needs to:

1. Ensure the `.UPF` file exists in `resources/pseudo/` (already true for Si, Al)
2. Call `update_calculation_species_map` RPC with the filename

**Available in `resources/pseudo/`:**
- `Si.pbe-n-rrkjus_psl.1.0.0.UPF` (1.5 MB, SSSP)
- `Si.pbe-n-van.UPF`, `Si.pbe-tm-gipaw.UPF`, `Si.pz-vbc.UPF`
- `Al.pbe-n-van.UPF` (for Al tests)

**No manual file copies needed.** No SSSP installation needed. The test just sets the species_map via RPC.

### Timing (Measured)

- **Si SCF (ecutwfc=20 Ry, default k-grid):** ~3 seconds QE, ~10s total test
- **Timeout strategy:** 120s per job (generous)

---

## Paired Smoke Test Design

### Philosophy

Each pair consists of:
1. **RPC test** — Tests the API/daemon layer with Python pytest
2. **E2E test** — Tests the GUI workflow with Playwright

Both tests perform the IDENTICAL workflow **as a user would**:
- Create project from scratch
- Import structure (from file)
- Create calculation (with engine_family)
- Select pseudopotential (update_calculation_species_map)
- Add step(s) (step_type_gen)
- Set parameters (update_step_params)
- Run QE (run_calculation)
- Poll job status (get_job_status)
- Validate analysis outputs (get_analysis_instances_for_step)

### RPC Call Sequence (Canonical for All Pairs)

```
1. init_project (fixture)           -- QVService.init_project()
2. import_structure (fixture)       -- svc.structure.import_file()
3. create_calculation               -- engine_family="qe", structure=ulid
4. update_calculation_species_map   -- species_map={element: {pseudopot: filename}}
5. add_step_to_calculation          -- step_type_gen="scf"|"relax"|...
6. update_step_params               -- parameters={SYSTEM: {ecutwfc: ...}, ...}
7. run_calculation                  -- calculation=calc_ulid
8. get_job_status (poll loop)       -- until completed/failed
9. get_analysis_instances_for_step  -- validate instances exist
```

### Parameter Pitfalls (Discovered)

- **K_POINTS is a QE CARD, not a namelist.** Do NOT set `"K_POINTS": {"k_points": ...}` in update_step_params — it creates a bogus `&K_POINTS` namelist that crashes QE. K-points are set automatically from defaults, or use the `k_points` top-level parameter.
- **engine_family must be "qe"**, not "quantum_espresso". The driver is registered as "qe".
- **RPC parameter names**: `structure` (not `structure_ulid`), `calculation` (not `calculation_ulid`).

### Success Criteria

**RPC test passes if:**
- Structure import succeeds
- Calculation creation succeeds (engine_family stored)
- Pseudopotential configured via species_map RPC
- Step parameters can be set and read back
- `run_calculation` completes (job_status = completed)
- QE exits with returncode=0
- `get_analysis_instances_for_step` returns convergence instance with state="ok"

**E2E test passes if:**
- All GUI interactions succeed (clicks, inputs, navigation)
- Calculation runs to completion (monitored via Run & Logs tab)
- Analysis tab displays results (charts/tables visible)

---

## Smoke Test Pairs

### Pair 1: Si SCF — DONE (RPC)

**What it tests:** Absolute minimum — create project, run single SCF step, get convergence analysis.

**Workflow (RPC):**
1. Fixture: init project, import Si structure from `tests/data/0_Si_scf/si.scf.in`
2. `create_calculation` (engine_family="qe", structure=ulid)
3. `update_calculation_species_map` (Si -> Si.pbe-n-rrkjus_psl.1.0.0.UPF)
4. `add_step_to_calculation` (step_type_gen="scf")
5. `update_step_params` (SYSTEM.ecutwfc=20.0) — k-points use defaults
6. `run_calculation` -> poll `get_job_status`
7. `get_analysis_instances_for_step` -> assert convergence instance exists

**Measured duration:** ~10 seconds total

**RPC test file:** `tests/daemon/contract/test_realrun_si_scf.py` -- 2 tests, PASSING
**E2E test file:** `gui/tests/e2e/realrun_si_scf.spec.ts` -- TODO

---

### Pair 2: Si VC-Relax

**What it tests:** Structural relaxation with variable cell.

**Workflow:**
Same as Pair 1 but step_type_gen="vc_relax", assert trajectory + convergence.

**RPC test file:** `tests/daemon/contract/test_realrun_si_relax.py`
**E2E test file:** `gui/tests/e2e/realrun_si_relax.spec.ts`

---

### Pair 3: Si Bands (Multi-step)

**What it tests:** Multi-step workflow, band structure analysis.

**Workflow:**
Add 3 steps: scf -> nscf -> bands. Assert band structure analysis instance.

**RPC test file:** `tests/daemon/contract/test_realrun_si_bands.py`
**E2E test file:** `gui/tests/e2e/realrun_si_bands.spec.ts`

---

### Pair 4: Si DOS

**What it tests:** DOS calculation and analysis.

**Workflow:**
Add 3 steps: scf -> nscf -> dos. Assert DOS analysis instance.

**RPC test file:** `tests/daemon/contract/test_realrun_si_dos.py`
**E2E test file:** `gui/tests/e2e/realrun_si_dos.spec.ts`

---

### Pair 5: Al DOS (Metal)

**What it tests:** Different element (metal), DOS at Fermi level.

**Workflow:**
Import Al structure, same as Pair 4 but with Al pseudo and metallic assertions.

**RPC test file:** `tests/daemon/contract/test_realrun_al_dos.py`
**E2E test file:** `gui/tests/e2e/realrun_al_dos.spec.ts`

---

## Infrastructure (DONE)

### RPC Test Fixtures (`tests/daemon/contract/conftest.py`)

```python
@pytest.fixture
def qe_available() -> bool:
    """Ensure QE is available (fail if not)."""

@pytest.fixture
def wait_for_job():
    """Poll get_job_status every 2s until complete/failed/timeout."""

@pytest.fixture
def qe_project_with_si(tmp_path, qe_available) -> tuple[Path, str]:
    """Create project with Si structure imported from test data.
    NOTE: Does NOT copy pseudo files. Auto-staging handles that."""
```

### Daemon Server Fix

Added `engine_family` parameter passthrough in `_handle_create_calculation` (server.py).

---

## Session 4 Progress

- [x] Tier 1 RPC tests (61/68 = 90%)
- [x] Reconnaissance complete
- [x] Plan document
- [x] Infrastructure fixtures
- [x] Pair 1 RPC test passing (2 tests, QE returncode=0)
- [ ] Pair 1 E2E test
- [ ] Pair 2+

---

**End of Plan**
