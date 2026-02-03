# GPAW Engine Integration Plan

**Date**: 2026-02-03
**Target**: QMatSuite v2 (Python branch)
**References**: ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md, ENGINE_INTEGRATION_CONSTITUTION.md, CONSTITUTION.md §17

---

## 0. Summary

Integrate GPAW as a new engine driver following the plug-in architecture. GPAW is Python-native (like PySCF) but handles periodic DFT (like QE). The driver will use the **Directory-State recipe archetype** with **SHARED WorkdirPolicy** because GPAW's multi-step workflows chain through `.gpw` restart files in a shared directory.

**No kernel/runner modifications are needed.**

---

## 1. Driver Bundle Structure

```
src/quantumvitas/drivers/gpaw/
├── __init__.py          # DriverRegistry.register(GPAWDriver())
├── driver.py            # GPAWDriver class (PREFIX + SUPPORTED_GEN_STEPS + 7 MUST items)
├── handler.py           # gpaw_step_handler() function
├── recipe.py            # GPAWRecipe class (Directory-State, one job per step)
├── writer.py            # Python script generator (YAML params → Python script)
└── parser.py            # Output parser (results.json + .txt log fallback)
```

---

## 2. Driver Declaration (`driver.py`)

### 2.1 Class Attributes (SSOT)

```python
class GPAWDriver(BaseEngineDriver):
    PREFIX: str = "gpaw"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "nscf", "relax", "bandspw", "dos", "md",
    })
```

### 2.2 Step Types

| step_type_spec | GEN | executable | Description |
|----------------|-----|-----------|-------------|
| `gpaw_scf` | `scf` | `python` | GPAW ground state SCF |
| `gpaw_nscf` | `nscf` | `python` | GPAW non-self-consistent (fixed density) |
| `gpaw_relax` | `relax` | `python` | GPAW geometry relaxation via ASE optimizer |
| `gpaw_bandspw` | `bandspw` | `python` | GPAW band structure (fixed density) |
| `gpaw_dos` | `dos` | `python` | GPAW density of states |
| `gpaw_md` | `md` | `python` | GPAW molecular dynamics via ASE |

**Notes**:
- `executable` is `"python"` since GPAW is Python-native (like PySCF).
- `mpi_aware=True` for all step types (GPAW supports MPI via `gpaw python`).
- Band structure uses `bandspw` (not `bands`) because it is a computation step that runs a GPAW calculation (eigenvalue solve along k-path), consistent with QE/VASP semantics (Constitution §7.5).

### 2.3 Materialization Map (Pure Derivation)

Auto-derived from `PREFIX` + `SUPPORTED_GEN_STEPS`:
```python
{
    "scf": "gpaw_scf",
    "nscf": "gpaw_nscf",
    "relax": "gpaw_relax",
    "bandspw": "gpaw_bandspw",
    "dos": "gpaw_dos",
    "md": "gpaw_md",
}
```

### 2.4 Properties

```python
engine_family = "gpaw"
display_name = "GPAW"
driver_api_version = "1.0.0"
```

### 2.5 WorkdirPolicy

```python
def get_workdir_policy(self) -> WorkdirPolicy:
    return WorkdirPolicy.SHARED
```

Rationale: GPAW multi-step workflows chain through `.gpw` files in the same directory. Bands/DOS steps read SCF `.gpw` from the shared working directory, exactly like QE steps read from shared outdir.

### 2.6 Capabilities

```python
def get_capabilities(self) -> set[str]:
    return {
        "scf", "nscf", "relax", "bandspw", "dos", "md",
        "periodic", "molecular",
        "mpi",
        "python_native",
    }
```

### 2.7 Error Classification

```python
def classify_error(self, stderr: str, exit_code: int) -> ErrorClass:
    stderr_lower = stderr.lower()
    if "convergence" in stderr_lower or "not converged" in stderr_lower:
        return ErrorClass.CONVERGENCE
    if "memory" in stderr_lower or "memoryerror" in stderr_lower:
        return ErrorClass.MEMORY
    if "no such file" in stderr_lower or "filenotfound" in stderr_lower:
        return ErrorClass.MISSING_FILE
    if "import" in stderr_lower and "gpaw" in stderr_lower:
        return ErrorClass.EXECUTABLE_NOT_FOUND
    return ErrorClass.UNKNOWN
```

---

## 3. Recipe Design (`recipe.py`)

### 3.1 Archetype: Directory-State

Like QE, GPAW uses a shared working directory where steps accumulate output files. The `.gpw` restart files serve the same role as QE's `outdir/` — shared state that downstream steps read.

### 3.2 Materialization

```python
class GPAWRecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas=None):
        # One job per step, all sharing calc_raw_dir
        jobs = []
        for idx, step in enumerate(steps):
            job_id = f"step_{idx:02d}"
            gen_type = extract_gen_from_spec(step.step_type_spec)

            # Input: generated Python script
            script_name = f"{gen_type}.py"

            # Command: python script.py (or gpaw python script.py for MPI)
            command = ["python", script_name]

            # Expected outputs depend on step type
            expected_outputs = [
                calc_raw_dir / "results.json",    # Always: structured results
                calc_raw_dir / f"{gen_type}.txt",  # Always: text log
            ]
            if gen_type in ("scf", "nscf", "relax", "md"):
                expected_outputs.append(calc_raw_dir / f"{gen_type}.gpw")
            if gen_type == "bandspw":
                expected_outputs.append(calc_raw_dir / "bandstructure.json")
            if gen_type == "dos":
                expected_outputs.append(calc_raw_dir / "dos.json")

            job = Job(
                id=job_id,
                step_ulids=[step.meta.ulid],
                working_dir=calc_raw_dir,  # SHARED
                command=command,
                input_files=[calc_raw_dir / script_name],
                expected_outputs=expected_outputs,
                deps=[],
                fingerprint=self._get_step_sha(step, step_shas),
                metadata={
                    "engine": "gpaw",
                    "step_type_spec": step.step_type_spec,
                    "step_type_gen": gen_type,
                    "script_name": script_name,
                },
            )
            jobs.append(job)
        return JobGraph(jobs=jobs)
```

### 3.3 Script Generation During Materialization

The recipe (or handler) generates a Python script for each step from the YAML step parameters. The script:

1. Reads structure from `structure.json` (written by runner from calculation.yaml)
2. Sets up GPAW calculator with parameters from step.yaml
3. Executes the calculation
4. Writes `results.json` with structured output
5. Writes `.gpw` restart file
6. Writes `{gen_type}.txt` log

### 3.4 File Layout

```
calc/raw/
├── structure.json          # Written by runner (from calculation.yaml)
├── scf.py                  # Generated SCF script
├── scf.txt                 # SCF log output
├── scf.gpw                 # SCF restart file (shared artifact)
├── results.json            # Latest step results
├── bandspw.py              # Generated bands script
├── bandspw.txt             # Bands log
├── bandstructure.json      # Band structure data
├── dos.py                  # Generated DOS script
├── dos.json                # DOS data
└── step_artifacts/
    └── <step_ulid>/
        └── results.json    # Per-step results copy
```

---

## 4. Handler Design (`handler.py`)

### 4.1 Handler Signature

```python
def gpaw_step_handler(
    job: Job,
    calculation: Calculation,
    engine_registry: EngineRegistry,
    context: Dict[str, Any],
) -> JobResult:
```

### 4.2 Handler Flow

```
1. Find step by ULID from job.step_ulids[0]
2. Extract step parameters from step.yaml
3. Determine step type (scf, bands, dos, relax, etc.)
4. Generate Python calculation script (writer.py)
5. Write structure.json if needed
6. Execute: subprocess.run(["python", "script.py"], cwd=working_dir)
7. Parse results.json (written by the script)
8. Handle relax artifacts if relax step
9. Return JobResult
```

### 4.3 Execution

GPAW steps are executed as Python subprocess calls:

```python
# Serial
result = subprocess.run(
    ["python", script_name],
    cwd=working_dir,
    capture_output=True, text=True,
    timeout=timeout,
)

# MPI (if configured)
result = subprocess.run(
    ["gpaw", "python", script_name],
    cwd=working_dir,
    capture_output=True, text=True,
)
```

### 4.4 Result Extraction

The generated script writes `results.json` with standardized keys:
```json
{
    "total_energy_eV": -10.787,
    "fermi_level_eV": 5.596,
    "forces_eV_per_ang": [[...], [...]],
    "n_bands": 8,
    "n_spins": 1,
    "converged": true
}
```

The handler reads this JSON directly — no GPAW dependency needed at parse time.

### 4.5 Chaining Mechanism

- SCF writes `scf.gpw` to `calc/raw/`
- Bands/DOS/NSCF scripts load `scf.gpw` from the same directory
- The restart file path is determined by convention: `scf.gpw` for SCF results

This is analogous to QE's outdir mechanism where NSCF reads charge density from the shared outdir written by SCF.

---

## 5. Input Writer (`writer.py`)

### 5.1 Approach

The writer takes step parameters (from step.yaml) and generates a Python script:

```
step.yaml parameters → writer.py → {gen_type}.py (Python script)
```

### 5.2 Key Mappings

| step.yaml key | GPAW parameter |
|---------------|---------------|
| `mode` | `mode=PW(ecut)` / `'fd'` / `'lcao'` |
| `ecut` | `PW(ecut)` (PW mode only) |
| `xc` | `xc='PBE'` |
| `kpoints` | `kpts=(n1,n2,n3)` |
| `kpath` | `kpts={'path':'GXWK','npoints':60}` (bands only) |
| `nbands` | `nbands=N` |
| `convergence.*` | `convergence={...}` |
| `smearing_width` | `occupations=FermiDirac(width)` |
| `spin_polarized` | `spinpol=True/False` |
| `grid_spacing` | `h=0.2` (FD/LCAO modes) |
| `basis` | `basis='dzp'` (LCAO mode) |
| `optimizer` | ASE optimizer class (relax only) |
| `fmax` | Force convergence criterion (relax only) |
| `parallel` | `parallel={'domain':n,'band':n,'kpt':n}` |

### 5.3 Runtime-Managed Keys

These are set by the runner/recipe, not user-editable:

| Key | Value | Reason |
|-----|-------|--------|
| `txt` | `'{gen_type}.txt'` | Log filename follows step type convention |
| restart path | `'scf.gpw'` | Convention for chaining |
| structure source | `'structure.json'` | Written by runner from calculation.yaml |

---

## 6. Output Parser (`parser.py`)

### 6.1 Primary Parser: results.json

The generated script writes `results.json`. The parser reads this JSON directly. No GPAW dependency needed.

### 6.2 Text Log Parser (Fallback)

Regex-based parser for `.txt` log files. Extracts:
- Convergence status and iteration count
- Total energy (extrapolated)
- Fermi level
- Band gap (indirect and direct)
- Forces
- SCF convergence history
- Memory usage

### 6.3 Band Structure Parser

Reads `bandstructure.json` (ASE BandStructure.write() format):
- K-path labels
- Number of k-points, bands, spins
- Reference energy (Fermi level)
- Energies array (shape: [nspins, nkpts, nbands])

### 6.4 DOS Parser

Reads `dos.json`:
- Energy array
- DOS array
- Fermi level

---

## 7. Registration

### 7.1 Driver Registration (`drivers/gpaw/__init__.py`)

```python
from quantumvitas.core.driver_registry import DriverRegistry
from .driver import GPAWDriver

DriverRegistry.register(GPAWDriver())

__all__ = ["GPAWDriver"]
```

### 7.2 Central Import (`drivers/__init__.py`)

Add one line:
```python
from quantumvitas.drivers import gpaw
```

This is the ONLY change outside `drivers/gpaw/`.

---

## 8. What MUST NOT Be Modified (Enforcement)

Per ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md §10.2:

- `calculation/runner.py` — NO CHANGE
- `execution/executor.py` — NO CHANGE
- `execution/handlers.py` — NO CHANGE
- `core/driver_registry.py` — NO CHANGE
- `core/driver_protocol.py` — NO CHANGE
- Any kernel routing/dispatch code — NO CHANGE

**The only file modified outside `drivers/gpaw/` is `drivers/__init__.py` (one import line).**

---

## 9. Kernel Change Assessment

### 9.1 Changes Needed: NONE

After thorough analysis, GPAW can be integrated with **zero kernel modifications**:

1. **Runner**: Already engine-agnostic. Dispatches through DriverRegistry.
2. **Executor**: Already handles subprocess execution and `<internal>` jobs.
3. **Recipes**: BaseRecipe supports the Directory-State pattern.
4. **Step types**: GEN/SPEC derivation works automatically from PREFIX + SUPPORTED_GEN_STEPS.
5. **Registry**: Already validates and registers new engines.
6. **Assets**: GPAW PAW setups are auto-discovered (no `species_map` needed in calculation.yaml).

### 9.2 Potential Future Enhancements (NOT for initial integration)

These would be nice-to-have but are NOT required:

- **GPAW installation detection**: Add GPAW to `engine/installation.py` for UI engine availability display. This is informational, not kernel logic.
- **ParamSpace for GPAW**: Add GPAW parameter dimensions to the ParamSpace system. This is a workflow/preset concern, not kernel.
- **GW/TDDFT step types**: Advanced step types could be added later by extending `SUPPORTED_GEN_STEPS`.

---

## 10. Testing Strategy

### 10.1 Unit Tests (`tests/drivers/test_gpaw_driver.py`)

1. Driver registration succeeds
2. All step types resolve via DriverRegistry
3. Handler is retrievable
4. Recipe materializes valid JobGraph
5. Materialization map matches expected gen→spec mapping
6. Unknown types still raise errors

### 10.2 Integration Tests

1. SCF calculation: generate script, execute, parse results
2. SCF → Bands multi-step: verify chaining via `.gpw` files
3. Relaxation: verify trajectory and optimized structure output
4. Error handling: invalid parameters, convergence failure

### 10.3 Gate Tests

Existing gate tests should pass without modification:
- `test_engine_no_ssot_import.py` — GPAW driver doesn't import SSOT
- `test_no_deep_domain_import.py` — No forbidden imports
- `test_yaml_write_single_entry.py` — No YAML writes from driver

---

## 11. Implementation Phases

### Phase 1: Minimal Driver (SCF only)
- `driver.py` with `SUPPORTED_GEN_STEPS = frozenset({"scf"})`
- `recipe.py` with Directory-State materialization
- `handler.py` with subprocess execution
- `writer.py` for SCF script generation
- `parser.py` for results.json parsing
- Registration in `drivers/__init__.py`
- Unit tests

### Phase 2: Multi-Step (Bands, DOS, NSCF)
- Add `bandspw`, `dos`, `nscf` to SUPPORTED_GEN_STEPS
- Writer support for fixed_density() chaining
- Bandstructure.json and dos.json parsers
- Integration tests for multi-step workflows

### Phase 3: Relaxation & MD
- Add `relax`, `md` to SUPPORTED_GEN_STEPS
- Writer support for ASE optimizer loop
- Trajectory parsing
- RelaxArtifactSpec for structure output

### Phase 4: Advanced Features
- MPI execution support
- LCAO mode support
- Spin-polarized calculations
- GW/TDDFT step types (if needed)

---

## 12. Deliverables Summary

| Deliverable | Location | Status |
|-------------|----------|--------|
| Exploration report | `scratchpad/GPAW_EXPLORATION.md` | Complete |
| Integration plan | `scratchpad/GPAW_INTEGRATION_PLAN.md` | Complete (this file) |
| Input writer utility | `scratchpad/gpaw_utils/gpaw_input_writer.py` | Complete, tested |
| Output parser utility | `scratchpad/gpaw_utils/gpaw_output_parser.py` | Complete, tested (7/7 pass) |
| Si SCF artifacts | `scratchpad/gpaw_test_resources/calc1_si_scf/` | Complete |
| Si Bands+DOS artifacts | `scratchpad/gpaw_test_resources/calc2_si_bands/` | Complete |
| H2O Relax artifacts | `scratchpad/gpaw_test_resources/calc3_relax/` | Complete |
| Calculation scripts | `scratchpad/gpaw_calcs/calc{1,2,3}_*/run_*.py` | Complete |

---

## End of Integration Plan
