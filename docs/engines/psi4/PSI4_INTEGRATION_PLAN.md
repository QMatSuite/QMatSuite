# Psi4 Engine Integration Plan

**Date**: 2026-02-03
**Governing Law**: `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` §10, `ENGINE_INTEGRATION_CONSTITUTION.md`
**Reference Engines**: PySCF (closest analog), ORCA (strong-chain recipe)

---

## 0. Goal

Integrate Psi4 as a plug-in engine driver in QMatSuite, following the same pattern as existing engines. Only one central declaration spot (the driver bundle). No kernel modifications except the minimal required registration.

---

## 1. Engine Identity

| Property | Value |
|----------|-------|
| **engine_family** | `"psi4"` |
| **display_name** | `"Psi4"` |
| **PREFIX** | `"psi4"` |
| **driver_api_version** | `"1.0.0"` |
| **WorkdirPolicy** | `ISOLATED` |
| **Recipe Archetype** | Strong-Chain (like ORCA/PySCF) |
| **Execution Model** | Subprocess (Python script → results.json) |

---

## 2. Supported Step Types

### 2.1 Initial Integration (no kernel changes needed)

| GEN | SPEC | Function | Executable |
|-----|------|----------|------------|
| `scf` | `psi4_scf` | `psi4.energy('scf')` | `python` |
| `hf` | `psi4_hf` | `psi4.energy('hf')` | `python` |
| `mp2` | `psi4_mp2` | `psi4.energy('mp2')` | `python` |
| `relax` | `psi4_relax` | `psi4.optimize(method)` | `python` |
| `td` | `psi4_td` | `tdscf_excitations(wfn)` | `python` |

`SUPPORTED_GEN_STEPS = frozenset({"scf", "hf", "mp2", "relax", "td"})`

### 2.2 Future Extensions (need GenStepRegistry update)

| GEN | SPEC | Notes |
|-----|------|-------|
| `freq` | `psi4_freq` | Needs `"freq"` added to `gen_steps.py` |
| `ccsd` | `psi4_ccsd` | Needs `"ccsd"` added to `gen_steps.py` |

---

## 3. Driver Bundle Structure

```
src/qmatsuite/drivers/psi4/
├── __init__.py          # DriverRegistry.register(Psi4Driver())
├── driver.py            # Psi4Driver (PREFIX, SUPPORTED_GEN_STEPS, 7 MUST items)
├── recipe.py            # Psi4Recipe (strong-chain, subchain jobs)
├── handler.py           # psi4_chain_handler (subprocess execution)
├── writer.py            # Psi4 Python script generation
├── parser.py            # Parse results.json + fallback text parsing
└── step_types.py        # StepTypeSpec declarations (optional, can be in driver.py)
```

---

## 4. Implementation Details

### 4.1 `driver.py` — Psi4Driver

```python
class Psi4Driver(BaseEngineDriver):
    PREFIX: str = "psi4"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "hf", "mp2", "relax", "td"
    })

    @property
    def engine_family(self) -> str: return "psi4"

    @property
    def display_name(self) -> str: return "Psi4"

    @property
    def driver_api_version(self) -> str: return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(step_type_spec="psi4_scf", engine="psi4",
                        executable="python", description="Psi4 SCF calculation",
                        mpi_aware=False),
            StepTypeSpec(step_type_spec="psi4_hf", engine="psi4",
                        executable="python", description="Psi4 Hartree-Fock"),
            StepTypeSpec(step_type_spec="psi4_mp2", engine="psi4",
                        executable="python", description="Psi4 MP2 calculation"),
            StepTypeSpec(step_type_spec="psi4_relax", engine="psi4",
                        executable="python", description="Psi4 geometry optimization"),
            StepTypeSpec(step_type_spec="psi4_td", engine="psi4",
                        executable="python", description="Psi4 TDDFT excited states"),
        ]

    def get_handler(self):
        from .handler import psi4_chain_handler
        return psi4_chain_handler

    def get_recipe_class(self):
        from .recipe import Psi4Recipe
        return Psi4Recipe

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def get_capabilities(self) -> set[str]:
        return {"scf", "hf", "relax", "mp2", "tddft",
                "molecular", "chain", "python_native"}

    def classify_error(self, stderr, exit_code) -> ErrorClass:
        stderr_lower = stderr.lower()
        if "convergence" in stderr_lower or "not converged" in stderr_lower:
            return ErrorClass.CONVERGENCE
        if "memory" in stderr_lower:
            return ErrorClass.MEMORY
        if "import" in stderr_lower and "psi4" in stderr_lower:
            return ErrorClass.EXECUTABLE_NOT_FOUND
        return ErrorClass.UNKNOWN

    def get_artifact_patterns(self) -> dict[str, str]:
        return {
            "output": "*.dat",
            "wavefunction": "*.npy",
            "results": "results.json",
        }
```

### 4.2 `recipe.py` — Psi4Recipe (Strong-Chain)

Follow ORCA recipe pattern exactly:

```python
class Psi4Recipe(BaseRecipe):
    """Strong-chain recipe for Psi4. One job per subchain target."""

    def materialize(self, steps, calc_raw_dir, step_shas=None) -> JobGraph:
        # 1. Verify QC topology
        verify_qc_topology(steps, get_registry())

        # 2. Get SCF root, compute namespace folder
        scf_root = steps[0]
        namespace_folder = get_chain_namespace_folder(scf_root.meta.ulid)
        working_dir = calc_raw_dir / namespace_folder

        # 3. For each target step, build cumulative subchain job
        jobs = []
        for target_idx, target_step in enumerate(steps):
            subchain_steps = steps[:target_idx + 1]
            gen_types = [gen_from(str(s.step_type_spec)) for s in subchain_steps]
            basename = generate_subchain_basename(gen_types)

            job = Job(
                id=basename,
                step_ulids=[s.meta.ulid for s in subchain_steps],
                working_dir=working_dir,
                command=["python", f"{basename}_input.py"],
                input_files=[working_dir / f"{basename}_input.py"],
                expected_outputs=[
                    working_dir / f"{basename}_results.json",
                ],
                deps=[],
                fingerprint=compute_job_fingerprint(...),
                metadata={
                    "engine": "psi4",
                    "subchain_basename": basename,
                    "chain_key": namespace_folder,
                    "gen_types": gen_types,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
```

### 4.3 `handler.py` — psi4_chain_handler

Follow PySCF handler pattern (subprocess execution):

```python
def psi4_chain_handler(job, calculation, engine_registry, context) -> JobResult:
    # 1. Resolve steps from job.step_ulids
    # 2. Create working directory
    # 3. Resolve structure (molecule) from calculation
    # 4. Build step specs from step.yaml parameters
    # 5. Generate Python script via writer.py
    # 6. Execute: subprocess.run(["python", "script.py"], cwd=working_dir)
    # 7. Parse results.json
    # 8. Return JobResult with per-step results
    # 9. Handle relax artifacts (if optimization step)
```

### 4.4 `writer.py` — Psi4 Input Script Generator

Generates a self-contained Python script that:
1. Sets up psi4 (memory, threads, output file)
2. Defines molecule from structure data
3. Sets calculation options from step parameters
4. Executes chain (SCF → post-SCF with ref_wfn passing)
5. Writes `{basename}_results.json` with all variables

Key design: The script is **self-contained** — it imports psi4, does the calculation, and writes results. The handler only needs to read the JSON output.

### 4.5 `parser.py` — Result Parser

Primary: Parse `{basename}_results.json` (structured JSON from script)
Fallback: Parse `{basename}_output.dat` (text output) using regex

The parser extracts:
- Energy (total, correlation, components)
- Convergence status
- Geometry (for optimization)
- Frequencies (for frequency calc)
- Excitations (for TDDFT)
- Thermochemistry

---

## 5. Data Flow

```
Runner
  │
  ├──→ DriverRegistry.get_recipe_class("psi4") → Psi4Recipe
  │
  ├──→ recipe.materialize(steps, raw_dir) → JobGraph
  │         │
  │         └── Creates subchain jobs: "s", "s_m2", "s_t"
  │             Each job: command=["python", "{basename}_input.py"]
  │
  ├──→ create_handler_map() → {"psi4": psi4_chain_handler}
  │
  └──→ JobExecutor.execute(job_graph)
           │
           └── For each job:
                 │
                 ├── handler = handlers["psi4"]
                 │
                 └── psi4_chain_handler(job, calc)
                       │
                       ├── Resolve steps + structure
                       ├── writer.generate_script(steps, molecule, working_dir)
                       │     → writes {basename}_input.py
                       ├── subprocess.run(["python", "{basename}_input.py"])
                       ├── parser.parse_results("{basename}_results.json")
                       └── Return JobResult
```

---

## 6. File System Layout

```
calc/raw/
└── scf_ABCDEF/                    # Namespace folder (from SCF ULID)
    ├── s_input.py                 # Generated script: SCF only
    ├── s_output.dat               # Psi4 output
    ├── s_results.json             # Structured results
    ├── s_wfn.npy                  # SCF wavefunction (checkpoint)
    ├── s_m2_input.py              # Generated script: SCF + MP2
    ├── s_m2_output.dat
    ├── s_m2_results.json
    ├── s_m2_wfn.npy
    ├── s_t_input.py               # Generated script: SCF + TD
    ├── s_t_output.dat
    ├── s_t_results.json
    └── step_artifacts/
        ├── <scf_ulid>/
        │   └── results.json       # Per-step artifacts
        ├── <mp2_ulid>/
        │   └── results.json
        └── <td_ulid>/
            └── results.json
```

---

## 7. Kernel Changes Required

### 7.1 Mandatory (1 change)

| File | Change | Reason |
|------|--------|--------|
| `src/qmatsuite/drivers/__init__.py` | Add `from qmatsuite.drivers.psi4 import *` | Register Psi4Driver |

This is NOT a kernel logic change — it's adding an import to the driver loading module, which is the designated registration point per `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` §2.3.

### 7.2 Optional (for future step types)

| File | Change | Reason |
|------|--------|--------|
| `src/qmatsuite/workflow/gen_steps.py` | Add `"freq"`, `"ccsd"` to `GEN_STEPS` | Enable frequency and CCSD as first-class GEN steps |

This is a policy decision: these are generic computational intents that other engines (ORCA, PySCF, CP2K) could also declare. The change is additive (2 strings to a frozenset) and benefits all engines.

### 7.3 NOT Required

| File | Status |
|------|--------|
| `calculation/runner.py` | ❌ No change (engine-agnostic) |
| `execution/executor.py` | ❌ No change |
| `execution/handlers.py` | ❌ No change (handler from registry) |
| `execution/recipes.py` | ❌ No change (BaseRecipe used) |
| `core/driver_protocol.py` | ❌ No change |
| `core/driver_registry.py` | ❌ No change |
| Any kernel routing code | ❌ No change |

---

## 8. Testing Plan

### 8.1 Unit Tests

```
tests/drivers/test_psi4_driver.py
├── test_driver_registration()          # Verify Psi4Driver registers correctly
├── test_step_type_specs()              # All 5 step types declared
├── test_materialization_map()          # gen→spec mapping correct
├── test_prefix_no_underscore()         # "psi4" has no underscore
├── test_supported_gen_subset()         # SUPPORTED_GEN_STEPS ⊆ GenStepRegistry
├── test_workdir_policy()               # ISOLATED
└── test_error_classification()         # stderr patterns → ErrorClass
```

### 8.2 Recipe Tests

```
tests/drivers/test_psi4_recipe.py
├── test_materialize_single_scf()       # Single step → 1 job
├── test_materialize_scf_mp2_chain()    # 2 steps → 2 subchain jobs
├── test_materialize_scf_td_chain()     # Chain with TD
├── test_relax_standalone()             # Relax → standalone job
├── test_topology_validation()          # TopologyError for invalid chains
└── test_namespace_folder()             # Correct folder naming
```

### 8.3 Writer Tests

```
tests/drivers/test_psi4_writer.py
├── test_generate_scf_script()          # Script has correct psi4 calls
├── test_generate_chain_script()        # Chain with ref_wfn passing
├── test_molecule_geometry_format()     # Correct charge/multiplicity/coords
├── test_options_passed_correctly()     # Basis, convergence, etc.
└── test_td_script_generation()         # TDDFT-specific options
```

### 8.4 Parser Tests

```
tests/drivers/test_psi4_parser.py
├── test_parse_scf_results_json()       # Golden ref: calc1
├── test_parse_mp2_results_json()       # Golden ref: calc1
├── test_parse_opt_results_json()       # Golden ref: calc2
├── test_parse_freq_results_json()      # Golden ref: calc2
├── test_parse_td_results_json()        # Golden ref: calc3
├── test_parse_output_file_scf()        # Text fallback parser
└── test_parse_output_file_opt()        # Text fallback parser
```

### 8.5 Integration Tests (require psi4 installed)

```
tests/integration/test_psi4_integration.py
├── test_psi4_scf_water()               # Full end-to-end SCF
├── test_psi4_scf_mp2_chain()           # Full chain execution
├── test_psi4_optimize()                # Geometry optimization
└── test_psi4_tddft()                   # Excited states
```

Mark integration tests with `@pytest.mark.skipif(not psi4_available)`.

---

## 9. Implementation Order

1. **Phase 1: Driver skeleton** — `driver.py`, `__init__.py`, registration
2. **Phase 2: Recipe** — `recipe.py` (strong-chain materialization)
3. **Phase 3: Writer** — `writer.py` (Python script generation)
4. **Phase 4: Parser** — `parser.py` (results.json + text fallback)
5. **Phase 5: Handler** — `handler.py` (subprocess orchestration)
6. **Phase 6: Tests** — All test files
7. **Phase 7: Registration** — Add import to `drivers/__init__.py`
8. **Phase 8: Verification** — Full test suite passes, gate tests pass

---

## 10. Risk Assessment

| Risk | Mitigation |
|------|------------|
| Circular import from registration | Lazy import in `__init__.py` (proven pattern) |
| Psi4 not installed on CI | `@pytest.mark.skipif` guards on integration tests |
| Psi4 global state conflicts | Subprocess execution (isolated process) |
| Large output files | Only keep results.json + output.dat; wfn.npy optional |
| TDDFT API changes | Pin to Psi4 ≥1.8 API (`tdscf_excitations`) |
| Gate test failures | No new step type mappings outside driver bundle |

---

## 11. Deliverables Summary

### From This Exploration Phase

| Deliverable | Location | Description |
|-------------|----------|-------------|
| Exploration report | `PSI4_ENGINE_EXPLORATION.md` | This document |
| Integration plan | `PSI4_INTEGRATION_PLAN.md` | This document |
| Input writer utility | `psi4_utils/psi4_input_writer.py` | Temporary, will become `drivers/psi4/writer.py` |
| Output parser utility | `psi4_utils/psi4_parser.py` | Temporary, will become `drivers/psi4/parser.py` |
| Golden refs: SCF+MP2 | `psi4_golden_refs/calc1_scf_mp2/` | Input, output, results.json |
| Golden refs: Opt+Freq | `psi4_golden_refs/calc2_opt_freq/` | Input, output, results.json |
| Golden refs: TDDFT | `psi4_golden_refs/calc3_tddft/` | Input, output, results.json |

### From Implementation Phase (future)

| Deliverable | Location |
|-------------|----------|
| Driver bundle | `src/qmatsuite/drivers/psi4/` (6 files) |
| Unit tests | `tests/drivers/test_psi4_*.py` (5 files) |
| Integration tests | `tests/integration/test_psi4_integration.py` |
| Registration | One line in `drivers/__init__.py` |

---

**End of Integration Plan**
