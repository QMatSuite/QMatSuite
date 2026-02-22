# Engine Recipe & Runner Constitution

**Status**: FINAL (binding law)
**Version**: 1.0
**Date**: 2026-02-03
**Parent Law**: `CONSTITUTION.md` §17 (Engine Execution Semantics)
**Related**: `ENGINE_INTEGRATION_CONSTITUTION.md` (integration invariants), `STEP_TYPE_GEN_SPEC_CONSTITUTION.md` (step type law)

---

## 0. Purpose

This document codifies the **engine recipe system** and **runner independence** architecture. It is the authoritative spec for:

- How engines declare their capabilities (one engine → one recipe)
- How the runner stays engine-agnostic
- How to add a new engine without modifying kernel code
- Directory contracts for engine execution
- Engine assets (pseudo, potentials) SSOT maps

**Code SSOT locations**:
- Driver protocol: `src/qmatsuite/core/driver_protocol.py`
- Driver registry: `src/qmatsuite/core/driver_registry.py`
- Recipe base: `src/qmatsuite/execution/recipes.py`
- Driver bundles: `src/qmatsuite/drivers/<engine>/`

---

## 1. Runner is Engine-Agnostic (Hard Law)

### 1.1 Runner reads only SSOT

The runner (`calculation/runner.py`) reads only:
- `calculation.yaml` — project/calc-level config including engine assets maps
- `step.yaml` — per-step engine-specific spec (`step_type_spec` + engine params)

The runner **MUST NOT**:
- Parse old input files and inject/merge
- Import engine-specific modules directly
- Contain `if engine == "..."` conditionals
- Know about engine-specific file formats

### 1.2 Materialization is clean rewrite

Materialize MUST produce input files via clean rewrite (YAML → input files). Never read/parse old input files.

Input files and raw engine artifacts are intermediates, not SSOT.

### 1.3 Execution dispatch

Runner dispatches to engines exclusively through:
```
CalculationRunner._execute_with_jobgraph()
  → get_recipe_for_engine(engine_family)     # Registry lookup
  → recipe.materialize(steps, raw_dir, ...)  # Engine-specific JobGraph
  → JobExecutor.execute(job_graph, handlers)  # Engine-agnostic execution
  → create_handler_map(engine_registry, ctx)  # Registry-based handler lookup
```

No engine-specific logic exists in `runner.py` or `executor.py` beyond the abstraction interfaces.

---

## 2. One Engine → One Recipe (Central Declaration)

### 2.1 EngineDriver Protocol

Each engine has exactly **one driver class** implementing the `EngineDriver` protocol. The driver is the single central declaration for all engine capabilities.

**MUST interface** (7 items — all required):

| Item | Type | Purpose |
|------|------|---------|
| `engine_family` | property → str | Unique identifier (e.g., "qe", "vasp") |
| `display_name` | property → str | Human-readable name |
| `driver_api_version` | property → str | Semver; major must match kernel API |
| `get_step_type_specs()` | method → list[StepTypeSpec] | All step types this engine supports |
| `get_handler()` | method → Callable | Step execution handler function |
| `get_recipe_class()` | method → type | Recipe class for input staging |
| `get_materialization_map()` | method → dict | GEN→SPEC mapping (auto-derived from PREFIX) |

**SHOULD interface** (recommended):

| Item | Purpose |
|------|---------|
| `get_workdir_policy()` | ISOLATED / CLEANUP / SHARED |
| `get_capabilities()` | Declared capability set |
| `supports_incremental_skip()` | Per-step-type skip support |
| `get_preflight_requirements()` | Artifacts needed before execution |
| `classify_error()` | stderr/exit-code → error class |

**PLUGIN interface** (optional extensions):

| Item | Purpose |
|------|---------|
| `get_artifact_patterns()` | Output artifact naming patterns |
| `find_latest_artifact()` | Artifact discovery in workdir |
| `resolve_executable()` | Custom executable resolution |
| `parse_output()` | Structured output parsing |

### 2.2 Class Attributes as SSOT

Each driver class declares two SSOT class attributes:

```python
class MyDriver(BaseEngineDriver):
    PREFIX: str = "myeng"                    # SSOT for spec strings
    SUPPORTED_GEN_STEPS: frozenset[str] = frozenset({"scf", "relax"})
```

- `PREFIX` is the engine prefix used in `step_type_spec = f"{PREFIX}_{gen}"`.
- `SUPPORTED_GEN_STEPS` is the subset of global `GenStepRegistry.GEN_STEPS`.
- The materialization map is **pure derivation**: `{gen: f"{PREFIX}_{gen}" for gen in SUPPORTED_GEN_STEPS}`.

### 2.3 Registration

Drivers register at import time via the driver package `__init__.py`:

```python
# src/qmatsuite/drivers/myeng/__init__.py
from qmatsuite.core.driver_registry import DriverRegistry
from .driver import MyEngDriver
DriverRegistry.register(MyEngDriver())
```

All drivers are imported through `src/qmatsuite/drivers/__init__.py`.

### 2.4 Validation at Registration

`DriverRegistry.register()` validates:
- engine_family is non-empty, lowercase alphanumeric
- driver_api_version is valid semver, compatible with kernel
- At least one step type declared
- All step types match engine prefix pattern
- No duplicate engines or step types

Registration failures are hard errors.

---

## 3. Recipe Responsibilities

The Recipe class is the **only place** engine-specific orchestration lives.

### 3.1 Recipe Interface

```python
class Recipe(Protocol):
    def materialize(
        self,
        steps: List[Step],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Convert calculation steps into a runtime JobGraph."""
```

### 3.2 What a Recipe Declares

| Responsibility | Description |
|---------------|-------------|
| **Job formation** | How steps become jobs (one-per-step vs subchain vs session) |
| **Working directory layout** | Where input/output files go within `calc/raw/` |
| **Artifact chaining** | How outputs of one step feed into next step's inputs |
| **Input file generation** | Writing engine-specific input files from SSOT params |
| **Scratch directory management** | Engine-specific scratch dirs (e.g., QE outdir/) |

### 3.3 What a Recipe MUST NOT Do

- Persist anything (JobGraph is runtime-only)
- Read/write SSOT files (calculation.yaml / step.yaml)
- Perform skip decisions (that's manifest/executor territory)
- Import from other engine drivers
- Modify calculation topology

---

## 4. Recipe Archetypes

Three recipe archetypes exist. Adding a new engine means choosing which archetype fits (or creating a new one with justification).

### 4.1 Directory-State Recipe (QE-like)

**Used by**: QE, Wannier90

| Aspect | Value |
|--------|-------|
| Jobs | One per step |
| Working dir | Shared `calc/raw/` |
| Scratch | `calc/raw/outdir/` (accumulates across steps) |
| WorkdirPolicy | `SHARED` |
| Artifact chaining | Via shared outdir (QE prefix/outdir convention) |
| Job IDs | `step_00`, `step_01`, ... |

**Characteristics**: Steps share a scratch directory; outdir accumulates wavefunction data between steps. Order-dependent execution.

### 4.2 Strong-Chain Recipe (QC engines)

**Used by**: ORCA, PySCF, CP2K

| Aspect | Value |
|--------|-------|
| Jobs | One per **subchain** (not per step) |
| Working dir | Namespace folder `calc/raw/scf_<suffix>/` |
| WorkdirPolicy | `ISOLATED` |
| Artifact chaining | Engine-native artifacts within chain |
| Job IDs | Stable tokens: `"s"`, `"s_m2"`, `"s_t"` |

**Characteristics**: SCF is chain root; non-SCF steps attach to nearest SCF. Full chain replayed each execution. Topology validated before materialization (`verify_qc_topology()`).

**QC topology rules** (hard law):
- Relax steps are standalone (length-1 chains)
- Non-relax, non-SCF steps must trace back to SCF root without crossing relax
- Missing SCF root → `TopologyError` (fail-fast)

### 4.3 Cleanup Recipe (VASP-like)

**Used by**: VASP

| Aspect | Value |
|--------|-------|
| Jobs | One per step |
| Working dir | Isolated `calc/raw/<step_ulid>/` |
| WorkdirPolicy | `CLEANUP` (rm -rf before each step) |
| Artifact chaining | Explicit staging of CHGCAR/WAVECAR from reference SCF |
| Continuation | Via `PreflightRequirement` declarations |

**Characteristics**: Complete cleanup before each step. Continuation artifacts (CHGCAR, WAVECAR) must be explicitly staged from reference steps.

### 4.4 Adding a New Archetype

If none of the above fit, a new archetype MAY be created, but:
- Must be justified with a clear rationale
- Must follow the Recipe protocol
- Must not leak into runner/executor code
- Must be documented in this spec

---

## 5. Directory Contracts

### 5.1 Project-Level Directories

| Directory | Purpose | Writer | SSOT? |
|-----------|---------|--------|-------|
| `project/pseudo/` | QE-like pseudo files | Step0 only (before run) | No (staging area) |
| `project/potentials/` | LAMMPS-like potential files | External | No (staging area) |
| `project/structures/` | Structure files | External tools | No |

### 5.2 Calculation-Level Directories

| Directory | Purpose | Writer |
|-----------|---------|--------|
| `calc/raw/` | Engine I/O (primary execution directory) | Recipe materialization + engine execution |
| `calc/raw/pseudo/` | Per-calc pseudo copies | `materialize_calc_pseudos()` |
| `calc/raw/outdir/` | QE scratch (shared across steps) | QE engine |
| `calc/raw/scf_<suffix>/` | QC chain namespace folder | ORCA/PySCF handler |
| `calc/raw/step_artifacts/<step_ulid>/` | Per-step artifact directory | Handler (post-execution) |
| `calc/.run_tmp_info/manifest.json` | Run manifest (non-SSOT bookkeeping) | Runner/executor |

### 5.3 Raw Directory Contract

`compute_io_dir_from_calculation_model(calculation_dir)` is the **single source of truth** for the raw/ location. Default subdirectory name: `"raw"`.

All materialized input files go into `calc/raw/`. The engine executes within `calc/raw/` or a subdirectory thereof. Output files remain in `calc/raw/`.

---

## 6. Engine Assets Maps (SSOT in calculation.yaml)

### 6.1 Principle

Some engines require project-run SSOT maps in `calculation.yaml`:

| Engine Type | SSOT Map | Location |
|-------------|----------|----------|
| QE-like | `species_map` | `calculation.yaml` |
| LAMMPS-like | `potential_map` | `calculation.yaml` |

### 6.2 Digest Derivation

Runner computes asset digests from these SSOT maps for incremental skip decisions. Digests are **derived** (non-SSOT). Changes to assets → digest changes → skip invalidation.

### 6.3 Recipe Responsibility

The engine recipe owns how assets maps are:
- Interpreted (mapping element → filename → staging path)
- Staged into project directories (`project/pseudo/`, `project/potentials/`)
- Included in fingerprints (`pseudo_set_sha`, `potential_assets_sha`)

---

## 7. Runtime-Managed Keys

### 7.1 Policy Layer

Certain parameters are "runtime-managed" — overridden at materialize time by runner policy. They are NOT user-editable and NOT scannable.

Examples (QE):
- `CONTROL.prefix` — set by runner to step identifier
- `CONTROL.outdir` — set by runner to `./outdir`
- `CONTROL.pseudo_dir` — set by runner to project/pseudo path
- `CONTROL.calculation` — set by step type

### 7.2 Declaration

Engine recipe SHOULD declare which keys are managed and why, via engine metadata (`is_managed` + `managed_reason`). UI renders these as read-only.

### 7.3 Step-Type-Owned Keys

Keys owned by step type (e.g., `CONTROL.calculation` for QE) are also UI read-only. The engine declares these through step type metadata.

---

## 8. Execution Modes

### 8.1 Project Run (Production Path)

Full project structure + `calculation.yaml` + `step.yaml`. This is the only production execution path.

### 8.2 Standalone Step (Testing Only)

Single step execution without full project context. Exists only for testing/compat. MUST NOT leak semantics into project-run.

### 8.3 Compat Playback (Testing Only)

Pre-existing input file replay for tutorial/demo mode. MUST NOT affect SSOT or engine dispatch logic.

---

## 9. Bans (Hard Law)

### 9.1 No Scattered Mapping Dicts

**FORBIDDEN**: Ad-hoc step type → engine mapping dicts outside the recipe/registry SSOT.

No hardcoded mapping tables in:
- Tests (must use registry queries)
- Handlers (must use recipe declarations)
- Runner (must use DriverRegistry)
- Daemon/CLI (must use API)

### 9.2 No Runner Engine Imports

**FORBIDDEN**: Direct imports of engine-specific modules in runner or executor code.

```python
# FORBIDDEN in runner.py / executor.py:
from qmatsuite.drivers.qe.handler import qe_step_handler
from qmatsuite.engine.qe import QEEngine

# REQUIRED: Use registry
handler = DriverRegistry.get_handler(step_type_spec)
recipe_cls = DriverRegistry.get_recipe_class(engine_family)
```

### 9.3 No Prefix Inference

**FORBIDDEN**: Determining engine from step type by prefix pattern matching.

```python
# FORBIDDEN:
if step_type.startswith("vasp_"):
    engine = "vasp"

# REQUIRED: Explicit registry lookup
engine = DriverRegistry.get_engine_for_step_type(step_type_spec)
```

### 9.4 No Silent Fallbacks

**FORBIDDEN**: Defaulting to any engine when lookup fails.

```python
# FORBIDDEN:
engine = mapping.get(step_type, "qe")

# REQUIRED: Hard error
engine = DriverRegistry.get_engine_for_step_type(step_type)
# raises UnknownStepTypeError if not found
```

---

## 10. How to Add a New Engine

### 10.1 Checklist

1. **Create driver bundle**: `src/qmatsuite/drivers/<engine>/`
   ```
   drivers/<engine>/
   ├── __init__.py      # DriverRegistry.register()
   ├── driver.py        # EngineDriver implementation (PREFIX + SUPPORTED_GEN_STEPS)
   ├── handler.py       # Step execution handler
   ├── recipe.py        # Recipe (materialize → JobGraph)
   ├── writer.py        # Input file generation (optional)
   ├── parser.py        # Output parsing (optional)
   └── step_types.py    # StepTypeSpec declarations
   ```

2. **Implement MUST interface** (7 items in driver.py)

3. **Choose recipe archetype**: Directory-state (§4.1), Strong-chain (§4.2), or Cleanup (§4.3)

4. **Register**: Add import to `drivers/__init__.py`

5. **Add tests**: `tests/drivers/test_<engine>_driver.py`

6. **If engine has assets**: Add assets map to `calculation.yaml` schema; implement staging in recipe

7. **If engine has managed keys**: Declare via `is_managed` + `managed_reason` metadata

### 10.2 What You MUST NOT Modify

- `calculation/runner.py`
- `execution/executor.py`
- `execution/handlers.py` (beyond handler map factory)
- `core/driver_registry.py`
- `core/driver_protocol.py`
- Any kernel routing/dispatch code

**CI gate**: PRs adding a new engine that modify files outside `drivers/` and `tests/` are rejected.

### 10.3 Validation

After adding a new engine, verify:
- All step types resolve via `DriverRegistry.get_step_type_spec()`
- Handler is retrievable via `DriverRegistry.get_handler()`
- Recipe materializes valid JobGraph
- No prefix inference patterns introduced
- Unknown types still raise helpful errors
- Existing tests still pass

---

## 11. Registered Engines (Current State)

| Engine | PREFIX | SUPPORTED_GEN_STEPS | WorkdirPolicy | Recipe Archetype |
|--------|--------|---------------------|---------------|-----------------|
| QE | `qe` | scf, nscf, relax, bands, bandspw, dos, pw2wannier, ph, md, custom | SHARED | Directory-state |
| VASP | `vasp` | scf, nscf, relax, md, bandspw | CLEANUP | Cleanup |
| PySCF | `pyscf` | scf, relax, mp2, td | ISOLATED | Strong-chain |
| ORCA | `orca` | scf, hf, relax, td | ISOLATED | Strong-chain |
| LAMMPS | `lammps` | minimize, md, relax | ISOLATED | Directory-state |
| CP2K | `cp2k` | scf, relax, md, bandspw, dos | ISOLATED | Strong-chain |
| W90 | `w90` | wannierprep, wannier | SHARED | Directory-state |

---

## 12. Relationship to Other Governance Docs

| Document | Relationship |
|----------|-------------|
| `CONSTITUTION.md` §17 | Parent law for engine execution semantics |
| `ENGINE_INTEGRATION_CONSTITUTION.md` | Integration invariants (no-guessing, hard-error, driver self-containment) |
| `STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | Step type derivation law that recipes must follow |
| `KERNEL_DEPENDENCY_SPEC.md` §2.4-2.5 | Kernel domain boundaries for runtime and engines |
| `KERNEL_EXCEPTIONS.md` EXC-001 | Allowed workflow→engine capability query exception |

---

**End of Engine Recipe & Runner Constitution**
