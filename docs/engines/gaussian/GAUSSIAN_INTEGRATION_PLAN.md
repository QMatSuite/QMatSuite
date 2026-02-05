# Gaussian Engine Integration Plan for QMatSuite

## Status: PLANNING

---

## Lessons Learned from Yambo Integration

Before implementing, review these critical lessons to avoid common pitfalls:

### Lesson 1: Dual Registration Requirement

**Problem**: QMatSuite has TWO separate `StepTypeSpec` classes that must BOTH be populated:
1. `quantumvitas.core.driver_protocol.StepTypeSpec` — for DriverRegistry (has `step_type_spec`, `engine`, `executable`, etc.)
2. `quantumvitas.workflow.registry.StepTypeSpec` — for workflow system (has `step_type_gen`, `requires_structure`, etc.)

The gate test `test_step_type_declared_sets.py` builds GEN_SET from the **workflow registry**, not from DriverRegistry.

**Solution**: Register Gaussian step types in BOTH places:
1. `src/quantumvitas/drivers/gaussian/driver.py` → `get_step_type_specs()`
2. `src/quantumvitas/workflow/registry.py` → `_STEP_TYPES` dict

### Lesson 2: Hardcoded Engine Lists in Tests

**Problem**: Several unit test files have hardcoded engine lists:
- `tests/unit/test_engine_discovery.py` — `expected` set
- `tests/unit/test_step_type_mapping.py` — `valid_prefixes` tuple (2 locations)

**Solution**: After adding Gaussian, grep for existing engine lists and update them.

### Lesson 3: Engine Discovery Under pytest-xdist

**Problem**: `discover_engine()` fails in xdist worker processes because `_find_project_root()` uses `Path.cwd()`, which may differ from repo root.

**Solution**: Integration tests must pass explicit `project_root=_REPO_ROOT` to all discovery calls.

### Lesson 4: Recipe Class vs Driver Class

**Discovery**: The `SUPPORTED_GEN_STEPS` attribute belongs on the **Driver** class, not the Recipe class. All existing engines follow this pattern.

### Lesson 5: ENGINE_PREFIXES in step_type_convert.py

**Requirement**: Add `"gaussian"` to the `ENGINE_PREFIXES` frozenset in `step_type_convert.py` for proper GEN↔SPEC conversion.

---

## 1. Overview

Gaussian is an external binary quantum chemistry engine, similar to ORCA. It supports HF, DFT, MP2, CCSD, TDDFT, geometry optimization, and frequency calculations.

**Engine family**: `gaussian`
**PREFIX**: `gaussian`
**Recipe archetype**: Strong-chain + ISOLATED workdir (like ORCA)

---

## 2. Files to MODIFY (7 files)

### 2.1 `src/quantumvitas/workflow/gen_steps.py`

Add 6 new GEN steps to `GenStepRegistry.GEN_STEPS`:

```python
# In GEN_STEPS frozenset, add:
"hf",      # Hartree-Fock (new, not existing)
"mp2",     # MP2 correlation (new)
"td",      # TDDFT excited states (new)
# Note: "scf", "relax", "freq" already exist
```

### 2.2 `src/quantumvitas/workflow/step_type_convert.py`

Add `"gaussian"` to `ENGINE_PREFIXES` frozenset.

### 2.3 `src/quantumvitas/workflow/registry.py`

Add Gaussian step types to `_STEP_TYPES` dict:

```python
"gaussian_scf": StepTypeSpec(
    step_type_gen="scf",
    step_type_spec="gaussian_scf",
    requires_structure=True,
    produces_charge_density=True,
    # ... other fields
),
"gaussian_hf": StepTypeSpec(...),
"gaussian_relax": StepTypeSpec(...),
"gaussian_freq": StepTypeSpec(...),
"gaussian_mp2": StepTypeSpec(...),
"gaussian_td": StepTypeSpec(...),
```

Also add `"gaussian_"` prefix to `normalize_step_type_to_gen()` if needed.

### 2.4 `src/quantumvitas/drivers/__init__.py`

Add import:
```python
from quantumvitas.drivers import gaussian
```

### 2.5 `src/quantumvitas/core/engines/discovery.py`

Add Gaussian EngineProbe to `_ENGINE_PROBES`:

```python
"gaussian": EngineProbe(
    engine_name="gaussian",
    binary_names=["g09", "g16", "g03"],
    env_vars=["g09root", "g16root", "g03root", "GAUSS_EXEDIR"],
),
```

### 2.6 `tests/unit/test_engine_discovery.py`

Add `"gaussian"` to the `expected` engine set.

### 2.7 `tests/unit/test_step_type_mapping.py`

Add `"gaussian_"` to `valid_prefixes` tuple (2 locations).

---

## 3. Files to CREATE (7 files in `src/quantumvitas/drivers/gaussian/`)

### 3.1 `__init__.py`

```python
from quantumvitas.core.driver_registry import DriverRegistry
from quantumvitas.drivers.gaussian.driver import GaussianDriver

DriverRegistry.register(GaussianDriver())
```

### 3.2 `driver.py` — GaussianDriver class

```python
class GaussianDriver(EngineDriver):
    PREFIX = "gaussian"
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({
        "scf", "hf", "relax", "freq", "mp2", "td"
    })

    @property
    def engine_family(self) -> str:
        return "gaussian"

    @property
    def display_name(self) -> str:
        return "Gaussian"

    @property
    def driver_api_version(self) -> str:
        return "1.0.0"

    def get_step_type_specs(self) -> dict[str, StepTypeSpec]:
        # Return specs for all 6 step types
        ...

    def get_handler(self, step_type_spec: str) -> Callable:
        from quantumvitas.drivers.gaussian.handler import gaussian_step_handler
        return gaussian_step_handler

    def get_recipe_class(self) -> type[Recipe]:
        from quantumvitas.drivers.gaussian.recipe import GaussianRecipe
        return GaussianRecipe

    def get_workdir_policy(self) -> WorkdirPolicy:
        return WorkdirPolicy.ISOLATED

    def classify_error(self, exit_code: int, stderr: str) -> ErrorClass:
        if "Out-of-memory" in stderr:
            return ErrorClass.MEMORY
        if "convergence failure" in stderr.lower():
            return ErrorClass.CONVERGENCE
        if exit_code != 0:
            return ErrorClass.UNKNOWN
        return ErrorClass.SUCCESS
```

### 3.3 `handler.py` — `gaussian_step_handler()`

Single handler dispatching by gen type:

```python
def gaussian_step_handler(job: Job, context: RunContext) -> JobResult:
    gen_type = job.step.step_type_gen

    if gen_type in ("scf", "hf", "mp2", "td"):
        return _run_single_point(job, context)
    elif gen_type == "relax":
        return _run_optimization(job, context)
    elif gen_type == "freq":
        return _run_frequency(job, context)
    else:
        raise ValueError(f"Unknown gen type: {gen_type}")
```

Each sub-handler:
1. Creates workdir (`calc/raw/{step_ulid}/`)
2. Writes input file via writer
3. Runs `g09 < input.gjf > output.log`
4. Parses output via parser
5. Returns `JobResult` with parsed data

### 3.4 `recipe.py` — GaussianRecipe

```python
class GaussianRecipe(Recipe):
    def build_jobs(self, step: Step) -> list[Job]:
        # One job per step
        # Command: ["g09"]
        # STDIN: input file content
        # STDOUT: output log
        return [Job(
            command=["g09"],
            workdir=self._make_workdir(step),
            stdin_file="input.gjf",
            stdout_file="output.log",
        )]
```

ISOLATED workdir policy — each step gets `calc/raw/{step_ulid}/`.

### 3.5 `writer.py`

Copy from exploration `gaussian_writer.py`, adapt for driver interface:
- `GaussianParams` dataclass
- `write_input(step, params, path)` function
- Method/basis from step parameters

### 3.6 `parser.py`

Copy from exploration `gaussian_parser.py`, adapt for driver interface:
- `parse_log_file(path) -> dict`
- `parse_scf_energy()`, `parse_mp2_energy()`, etc.
- Return structured `JobResult` data

### 3.7 `step_types.py` (optional)

Define step-type-specific parameter schemas if needed.

---

## 4. Step Types

| GEN Step | SPEC Step | Executable | Description | Category |
|----------|-----------|------------|-------------|----------|
| `scf` | `gaussian_scf` | `g09` | DFT/HF single point | energy |
| `hf` | `gaussian_hf` | `g09` | Hartree-Fock specifically | energy |
| `relax` | `gaussian_relax` | `g09` | Geometry optimization | structure |
| `freq` | `gaussian_freq` | `g09` | Frequency calculation | property |
| `mp2` | `gaussian_mp2` | `g09` | MP2 correlation | energy |
| `td` | `gaussian_td` | `g09` | TDDFT excited states | excitation |

---

## 5. Recipe Archetype

### 5.1 WorkdirPolicy: ISOLATED

Each step gets its own working directory. No shared state between steps (unlike QE's directory-state pattern).

### 5.2 Checkpoint-based Restart

For multi-step workflows:
- First step generates `.chk` file
- Subsequent steps can use `Guess=Read Geom=Checkpoint` to read from checkpoint
- Checkpoint path resolved via artifact system

### 5.3 Working Directory Layout

```
calc/raw/
├── <step_ulid_scf>/
│   ├── input.gjf
│   ├── output.log
│   └── calculation.chk
├── <step_ulid_relax>/
│   ├── input.gjf
│   ├── output.log
│   └── calculation.chk
└── <step_ulid_freq>/
    ├── input.gjf
    ├── output.log
    └── calculation.chk
```

---

## 6. Handler Design

### 6.1 Input Generation

1. Get method/basis from step parameters
2. Get structure from step (atoms, charge, multiplicity)
3. Generate Link0 commands (mem, nproc, chk)
4. Generate route line based on step type
5. Write `.gjf` file

### 6.2 Execution

```python
env = {
    "g09root": discovery.find("gaussian"),
    "GAUSS_EXEDIR": f"{g09root}/g09",
    "GAUSS_SCRDIR": "/tmp",
}
subprocess.run(["g09"], stdin=input_file, stdout=output_file, env=env)
```

### 6.3 Output Parsing

Parse `.log` file for:
- `scf`/`hf`: SCF energy, dipole, charges
- `mp2`: HF energy + MP2 correlation + total
- `relax`: Convergence, final geometry, final energy
- `freq`: Frequencies, ZPE, thermochemistry
- `td`: Excited states (energy, symmetry, oscillator strength)

---

## 7. Integration Test

### File: `tests/integration/test_gaussian_execution.py`

```python
@pytest.mark.skipif(
    not is_engine_available("gaussian", project_root=_REPO_ROOT),
    reason="Gaussian not available"
)
class TestGaussianRawExecution:
    """Raw binary execution tests."""

    def test_water_hf_sp(self, tmp_path):
        """HF/STO-3G single point on water."""
        # Write input, run g09, parse output
        # Assert: normal termination, energy ~ -74.96 Ha

    def test_water_opt(self, tmp_path):
        """B3LYP/6-31G* optimization of water."""
        # Assert: converged, n_steps <= 10

    def test_mp2_ethylene(self, tmp_path):
        """MP2/STO-3G on ethylene."""
        # Assert: MP2 energy < HF energy (correlation lowers energy)

    def test_tddft_formaldehyde(self, tmp_path):
        """B3LYP/STO-3G TDDFT on formaldehyde."""
        # Assert: 3 excited states, first ~4 eV


class TestGaussianDriverRegistration:
    """Driver registration tests (no binary needed)."""

    def test_driver_registry_lookup(self):
        driver = DriverRegistry.get_driver("gaussian")
        assert driver is not None

    def test_step_type_specs(self):
        specs = DriverRegistry.get_all_step_types()
        assert "gaussian_scf" in specs

    def test_materialization(self):
        spec = DriverRegistry.materialize_step_type("gaussian", "scf")
        assert spec == "gaussian_scf"

    def test_engine_discovery(self):
        available = is_engine_available("gaussian", project_root=_REPO_ROOT)
        # Just check the call works


class TestGaussianParser:
    """Parser tests against golden reference files."""

    def test_parse_water_sp(self):
        path = EXPLORATION_DIR / "smoke_tests/water_hf_sp/water_sp.log"
        result = parse_log_file(path)
        assert result["scf_energy"]["energy_hartree"] == pytest.approx(-74.963, abs=0.001)

    def test_parse_mp2(self):
        path = EXPLORATION_DIR / "smoke_tests/ethylene_mp2/ethylene_mp2.log"
        result = parse_log_file(path)
        assert result["mp2"]["mp2_energy_hartree"] < result["mp2"]["hf_energy_hartree"]
```

---

## 8. Execution Order

1. Add GEN steps to `gen_steps.py` (`hf`, `mp2`, `td`)
2. Add `"gaussian"` to `ENGINE_PREFIXES` in `step_type_convert.py`
3. Add step types to `_STEP_TYPES` in `registry.py`
4. Create driver bundle (`driver.py`, `__init__.py`, `recipe.py`, `handler.py`, `writer.py`, `parser.py`)
5. Register driver in `drivers/__init__.py`
6. Add engine probe to `discovery.py`
7. Update hardcoded engine lists in unit tests
8. Create integration test
9. Run tests: `source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

---

## 9. Verification

```bash
# Run all tests
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Run just Gaussian tests
python -m pytest tests/integration/test_gaussian_execution.py -v --tb=long

# Verify gate tests still pass
python -m pytest tests/gates/ -v --tb=short
```

---

## 10. Notes

### No Basis Set Handling

Unlike some engines, Gaussian handles basis sets internally. The basis name (e.g., "6-31G*") is passed in the route line. No external basis set files needed.

### Checkpoint vs Wavefunction

Gaussian uses `.chk` (binary) and `.fchk` (formatted) checkpoint files. For cross-step restarts, we'll use the binary `.chk` with `Guess=Read`.

### Memory and Scratch

Default `%mem=500MB` is sufficient for small molecules. For larger systems, this should be a parameter in the step configuration.

### G09 vs G16

The driver should support both Gaussian 09 and Gaussian 16. The binary name (`g09` or `g16`) will be determined by engine discovery.
