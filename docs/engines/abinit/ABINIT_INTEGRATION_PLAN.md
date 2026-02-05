# ABINIT Engine Integration Plan for QMatSuite

## Status: IMPLEMENTED (2026-02-04)

---

## Lessons Learned from Yambo Integration

**CRITICAL**: Before implementing, review these issues encountered during yambo integration:

### Issue 1: Two StepTypeSpec Classes
QMatSuite has TWO separate `StepTypeSpec` dataclasses:
- `quantumvitas.core.driver_protocol.StepTypeSpec` — used by engine drivers. **No `step_type_gen` field.**
- `quantumvitas.workflow.registry.StepTypeSpec` — used by workflow system. Has `step_type_gen`.

**Solution**: Register step types in BOTH places:
1. `src/quantumvitas/drivers/abinit/driver.py` → `get_step_type_specs()` (driver protocol)
2. `src/quantumvitas/workflow/registry.py` → `_STEP_TYPES` dict (workflow registry)

### Issue 2: Hardcoded Engine Lists in Tests
Two test files have hardcoded engine/prefix lists:
- `tests/unit/test_engine_discovery.py` — `expected` set
- `tests/unit/test_step_type_mapping.py` — `valid_prefixes` tuple (2 locations)

**Solution**: Add "abinit" / "abinit_" to all three hardcoded lists.

### Issue 3: Registry Reset in Gate Tests
`tests/gates/test_registry_routing.py::TestDriverValidation.setup_method` calls `DriverRegistry.reset()` and removes specific driver modules. New drivers MUST be added to `modules_to_remove` list.

### Issue 4: ENGINE_PREFIXES Lists
Two ENGINE_PREFIXES locations must be updated:
- `src/quantumvitas/workflow/step_type_convert.py` — `ENGINE_PREFIXES` frozenset
- `src/quantumvitas/workflow/registry.py` — `ENGINE_PREFIXES` tuple in `normalize_step_type_to_gen()`

### Issue 5: Project Root for Engine Discovery
Integration tests using `discover_engine()` MUST pass `project_root` explicitly due to pytest-xdist worker CWD issues.

---

## 1. Overview

ABINIT is a plane-wave DFT code similar to Quantum ESPRESSO. This integration follows the QE driver pattern.

**Engine family**: `abinit`
**PREFIX**: `abinit`
**Recipe archetype**: Directory-state (QE-like, SHARED WorkdirPolicy)

---

## 2. Implementation Checklist

### Files to Create (in `src/quantumvitas/drivers/abinit/`)

| File | Contents | Status |
|------|----------|--------|
| `__init__.py` | `DriverRegistry.register(AbinitDriver())` | ✅ Done |
| `driver.py` | AbinitDriver class (7-item MUST interface) | ✅ Done |
| `handler.py` | `abinit_step_handler` function | ✅ Done |
| `recipe.py` | AbinitRecipe class (Directory-state archetype) | ✅ Done |
| `writer.py` | Input file generation (copy from `docs/engines/abinit/abinit_writer.py`) | ✅ Done |
| `parser.py` | Output parsing (copy from `docs/engines/abinit/abinit_parser.py`) | ✅ Done |

### Files to Modify

| File | Change | Status |
|------|--------|--------|
| `src/quantumvitas/drivers/__init__.py` | Add `from quantumvitas.drivers import abinit` | ✅ Done |
| `src/quantumvitas/workflow/step_type_convert.py` | Add "abinit" to ENGINE_PREFIXES | ✅ Done |
| `src/quantumvitas/workflow/registry.py` | Add abinit_scf/nscf/relax StepTypeSpecs + "abinit_" prefix | ✅ Done |
| `src/quantumvitas/core/engines/discovery.py` | Add abinit EngineProbe | ✅ Done |
| `tests/unit/test_engine_discovery.py` | Add "abinit" to expected set | ✅ Done |
| `tests/unit/test_step_type_mapping.py` | Add "abinit_" to valid_prefixes (2 places) | ✅ Done |
| `tests/gates/test_registry_routing.py` | Add 'quantumvitas.drivers.abinit' to modules_to_remove | ✅ Done |

### Integration Tests Created

| File | Description | Status |
|------|-------------|--------|
| `tests/integration/test_abinit_execution.py` | Full integration test suite | ✅ Done |

### Files NOT to Modify (Hard Ban)

Per ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md §10.2:
- `calculation/runner.py`
- `execution/executor.py`
- `execution/handlers.py`
- `core/driver_registry.py`
- `core/driver_protocol.py`

---

## 3. Step Types

### Phase 1 (Implemented)

| GEN Step | SPEC Step | Executable | Description |
|----------|-----------|------------|-------------|
| `scf` | `abinit_scf` | `abinit` | Ground state SCF |
| `nscf` | `abinit_nscf` | `abinit` | Non-self-consistent |
| `relax` | `abinit_relax` | `abinit` | Structure relaxation |

### SUPPORTED_GEN_STEPS

```python
SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
    "scf", "nscf", "relax"
})
```

### Future Phases

- `bandspw`, `dos`, `md` (Phase 2)
- `dfpt`, `screening`, `gw` (Phase 3)

---

## 4. Driver Class Design

```python
class AbinitDriver(BaseEngineDriver):
    PREFIX: str = "abinit"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"scf", "nscf", "relax"})

    @property
    def engine_family(self) -> str:
        return "abinit"

    @property
    def display_name(self) -> str:
        return "ABINIT"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> list[StepTypeSpec]:
        return [
            StepTypeSpec(
                step_type_spec="abinit_scf",
                engine="abinit",
                executable="abinit",
                description="ABINIT ground state SCF",
            ),
            StepTypeSpec(
                step_type_spec="abinit_nscf",
                engine="abinit",
                executable="abinit",
                description="ABINIT non-self-consistent calculation",
            ),
            StepTypeSpec(
                step_type_spec="abinit_relax",
                engine="abinit",
                executable="abinit",
                description="ABINIT structure relaxation",
            ),
        ]

    def get_handler(self):
        from .handler import abinit_step_handler
        return abinit_step_handler

    def get_recipe_class(self):
        from .recipe import AbinitRecipe
        return AbinitRecipe

    def get_materialization_map(self) -> dict[str, str]:
        return {gen: f"{self.PREFIX}_{gen}" for gen in self.SUPPORTED_GEN_STEPS}
```

---

## 5. Recipe Design (Directory-State)

### WorkdirPolicy: SHARED

All steps execute in `calc/raw/`. Sequential chaining via file dependencies:
- SCF produces: `{prefix}o_DEN`, `{prefix}o_WFK`
- NSCF reads: `getden` pointing to SCF density
- Relax produces: `{prefix}o_HIST.nc`, final structure

### Working Directory Layout

```
calc/raw/
├── step_00.abi          # SCF input
├── step_00.abo          # SCF output
├── step_00o_DEN         # Density
├── step_00o_WFK         # Wavefunctions
├── step_00o_EIG         # Eigenvalues
├── step_01.abi          # NSCF input (if applicable)
├── step_01.abo          # NSCF output
└── ...
```

### Input Generation

```python
def materialize(self, steps, calc_raw_dir, ...):
    jobs = []
    for i, step in enumerate(steps):
        step_prefix = f"step_{i:02d}"
        input_file = calc_raw_dir / f"{step_prefix}.abi"

        # Generate input based on step type
        gen_type = gen_from(step.step_type_spec)
        if gen_type == "scf":
            write_scf_input(...)
        elif gen_type == "nscf":
            write_nscf_input(..., getden=prev_step_prefix)
        elif gen_type == "relax":
            write_relax_input(...)

        jobs.append(Job(
            id=step_prefix,
            command=["abinit", f"{step_prefix}.abi"],
            working_dir=calc_raw_dir,
        ))

    return JobGraph(jobs=jobs, ...)
```

---

## 6. Handler Design

```python
def abinit_step_handler(
    job: Job,
    calculation: Calculation,
    engine_registry: EngineRegistry,
    context: dict,
) -> JobResult:
    """Execute an ABINIT step."""
    # 1. Find step in calculation
    step = find_step_by_job_id(calculation, job.id)

    # 2. Execute subprocess
    result = subprocess.run(
        job.command,
        cwd=job.working_dir,
        capture_output=True,
        text=True,
    )

    # 3. Parse output
    output_file = job.working_dir / f"{job.id}.abo"
    if output_file.exists():
        parsed = parse_abinit_output(output_file)
        artifacts = {
            "total_energy": parsed.datasets[1].total_energy,
            "n_iterations": parsed.datasets[1].n_iterations,
        }
    else:
        artifacts = {}

    # 4. Return result
    return JobResult(
        job_id=job.id,
        success=(result.returncode == 0),
        stdout=result.stdout,
        stderr=result.stderr,
        artifacts=artifacts,
    )
```

---

## 7. Engine Discovery Probe

```python
EngineProbe(
    engine_name="abinit",
    binary_names=["abinit"],
    env_vars=["ABINIT_HOME", "ABI_HOME"],
    brew_name="abinit",
    python_module=None,  # Not a Python engine
)
```

---

## 8. Workflow Registry Entries

Add to `_STEP_TYPES` in `registry.py`:

```python
"abinit_scf": StepTypeSpec(
    step_type_spec="abinit_scf",
    step_type_gen="scf",
    engine="abinit",
    executable="abinit",
    description="ABINIT ground state SCF calculation",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=True,
),
"abinit_nscf": StepTypeSpec(
    step_type_spec="abinit_nscf",
    step_type_gen="nscf",
    engine="abinit",
    executable="abinit",
    description="ABINIT non-self-consistent calculation",
    requires_structure=True,
    requires_charge_density=True,
    produces_charge_density=False,
),
"abinit_relax": StepTypeSpec(
    step_type_spec="abinit_relax",
    step_type_gen="relax",
    engine="abinit",
    executable="abinit",
    description="ABINIT structure relaxation",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    is_structure_transform=True,
),
```

---

## 9. Testing Plan

### Unit Tests (`tests/drivers/abinit/`)

- `test_abinit_driver.py`: Driver registration, step type specs, handler/recipe
- `test_abinit_writer.py`: Input file generation
- `test_abinit_parser.py`: Output parsing with golden refs

### Integration Tests (`tests/integration/`)

- `test_abinit_execution.py`:
  - Raw execution smoke test (Si SCF)
  - Raw execution relaxation test
  - Driver registration tests (no binary)
  - Parser/writer tests with golden references

### Gate Test Updates

Ensure all gate tests pass after adding abinit:
- `test_registry_routing.py` - driver validation
- `test_step_type_declared_sets.py` - GEN/SPEC sets

---

## 10. Pseudopotential Handling

ABINIT supports multiple PSP formats:
- `.pspnc` - Troullier-Martins NC
- `.psp8` - ONCVPSP format
- `.hgh` - Hartwigsen-Goedecker-Hutter
- `.xml` - XML format

### species_map Integration

Use existing `species_map` pattern in `calculation.yaml`:

```yaml
species_map:
  Si: Si.psp8
  O: O.psp8
```

Recipe stages PSPs to `calc/raw/pseudo/` and sets:
```
pp_dirpath "./pseudo"
pseudos "Si.psp8, O.psp8"
```

---

## 11. Known Pitfalls

### 1. Symmetry Checking
ABINIT is strict about k-point symmetry. Always include:
```
chksymbreak 0
```

### 2. Multi-Dataset Confusion
ABINIT's multi-dataset mode (`ndtset`) is powerful but complicates step tracking. We use **separate input files** for each step instead.

### 3. Convergence Criteria
Only ONE tolerance can be specified:
- `toldfe` — energy (SCF)
- `tolvrs` — potential residual (SCF)
- `tolwfr` — wavefunction (NSCF)
- `toldff` — force (relax)

### 4. File Naming
ABINIT uses `{outdata_prefix}_*` for outputs. We set this explicitly per step.

---

## 12. Implementation Order

1. ✅ **Create driver bundle skeleton** (`__init__.py`, `driver.py`)
2. ✅ **Add to registry.py** (workflow StepTypeSpecs)
3. ✅ **Add to step_type_convert.py** (ENGINE_PREFIXES)
4. ✅ **Add to discovery.py** (EngineProbe)
5. ✅ **Add to drivers/__init__.py** (import)
6. ✅ **Implement handler.py** (execution)
7. ✅ **Implement recipe.py** (materialization)
8. ✅ **Copy writer.py and parser.py** from docs/engines/abinit/
9. ✅ **Update test hardcoded lists**
10. ✅ **Write tests** (`tests/integration/test_abinit_execution.py`)
11. ✅ **Run full test suite** (3256 passed, 19 skipped)
12. ✅ **Add Si pseudopotential** (`docs/engines/abinit/pseudopotentials/14si.pspnc`)

---

## 13. Files Ready for Implementation

Pre-built utilities in `docs/engines/abinit/`:
- `abinit_writer.py` — Copy to `src/quantumvitas/drivers/abinit/writer.py`
- `abinit_parser.py` — Copy to `src/quantumvitas/drivers/abinit/parser.py`
- `golden_refs/` — Use for test fixtures
- `pseudopotentials/14si.pspnc` — Si pseudopotential for integration tests

---

## 14. Estimated Changes Summary

| Category | Files |
|----------|-------|
| **New files** | 6 (driver bundle) |
| **Modified files** | 7 (registries, tests) |
| **Kernel files** | 0 (prohibited) |
| **Test files** | 3+ (new + modified) |

---

## Appendix: Complete File List

### New Files
```
src/quantumvitas/drivers/abinit/
├── __init__.py
├── driver.py
├── handler.py
├── recipe.py
├── writer.py
└── parser.py
```

### Modified Files
```
src/quantumvitas/drivers/__init__.py
src/quantumvitas/workflow/step_type_convert.py
src/quantumvitas/workflow/registry.py
src/quantumvitas/core/engines/discovery.py
tests/unit/test_engine_discovery.py
tests/unit/test_step_type_mapping.py
tests/gates/test_registry_routing.py
```
