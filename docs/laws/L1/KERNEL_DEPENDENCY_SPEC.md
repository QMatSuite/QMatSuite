# QMatSuite Kernel Dependency Constitution

**Status**: PROPOSED LAW
**Version**: 3.1
**Date**: 2026-02-03
**Parent Law**: `CONSTITUTION.md` (repo-root)

---

## 0. Constitution Alignment

This spec extends and refines rules from the repo-root `CONSTITUTION.md`. The following clauses are directly relevant:

| Constitution Section | Topic | This Spec | Status |
|----------------------|-------|-----------|--------|
| S2 (ULID-only DAG + Index) | ULID-first identity, project root discovery, index/cache | Domain `resources` (S2.2) | Aligned; spec adds kernel-specific enforcement |
| S10.1 (Single Source of Truth) | step.yaml is the only executable truth | Law K3 (SSOT writes), Domain `ssot` | Aligned |
| S11 (YamlDoc layer + Journal) | All YAML IO must use Doc + yaml_io, no reference leakage | Law K3, Domain `ssot` | Aligned; code has violations (see Review Report) |
| S13.2 (StepTypeRegistry) | machine step_type from step.yaml is execution truth | Domain `workflow` | Aligned |
| S13.2.2 | engine_family only at materialization; execution reads step.yaml only | Law K6 (engine inputs) | Aligned; engines MUST NOT read SSOT |
| S14 (Engine Execution Semantics) | Two engine models (session-chain, artifact-bridged) | Domain `engines` | Aligned |
| S10.2 (Preset/Workflow non-entity) | workflow/preset are runtime interpretation only | Domain `workflow` | Aligned |

**Constitution gaps relevant to this spec** (addressed below):
- Constitution does not define kernel-internal dependency rules (this spec fills that gap).
- Constitution does not address kernel -> API reverse dependency ban (Law K0 below).
- Constitution S11.1 ("YAML IO must use Doc + yaml_io") is violated by ~20 files (see Review Report).

---

## 1. Definitions & Boundaries

### 1.1 What is "Kernel"

**Kernel** is the internal implementation layer below the API facade. It comprises all packages that contain business logic, domain models, and execution machinery:

| Package | Role |
|---------|------|
| `quantumvitas.core` | SSOT (YamlDoc, yaml_io, locking), resolution, models, pseudo management |
| `quantumvitas.calculation` | Calculation/step domain model, runner, manifest, hashing |
| `quantumvitas.execution` | Job graph, executor, recipes, handlers, scan expansion |
| `quantumvitas.engine` | Pluggable engine drivers (QE, PySCF, ORCA, VASP, LAMMPS, CP2K) |
| `quantumvitas.workflow` | Step type registry, step factory, step type conversion |
| `quantumvitas.analysis` | Post-run analysis, artifact parsing, primitives |
| `quantumvitas.io` | File format I/O (CIF, XYZ, POSCAR, etc.) |
| `quantumvitas.presets` | Preset catalog, preset application |
| `quantumvitas.parsers` | Output file parsers |
| `quantumvitas.history` | Project history, run revisions, events |
| `quantumvitas.project` | Project model, storage, snapshots |
| `quantumvitas.data` | Static data (basis sets, pseudo library info) |
| `quantumvitas.drivers` | Recipe/handler implementations (QE, PySCF, ORCA) |
| `quantumvitas.ir` | Intermediate representation |
| `quantumvitas.viz` | Visualization helpers |
| `quantumvitas.legacy` | Migration code (scheduled for deletion; see EXC-003) |

### 1.2 What is "API Facade"

| Package | Role |
|---------|------|
| `quantumvitas.api` | Public entry points, DTOs, errors, utils |

- API MUST NOT expose kernel types directly (use DTOs).
- API MUST map kernel exceptions to API exceptions.
- API MUST be the ONLY stable import path for frontends.

### 1.3 What are "Frontends"

| Package | Role |
|---------|------|
| `quantumvitas.cli` | Command-line interface (Typer) |
| `quantumvitas.daemon` | JSON-RPC daemon (GUI backend) |
| `quantumvitas.frontends.*` | Future frontends (Jupyter, agent adapters) |

---

## 2. Kernel Domains

The kernel SHALL be organized into **7 domains**. Each domain has a clear responsibility, a public entry point, and forbidden responsibilities.

### 2.1 Domain: `ssot` (Single Source of Truth)

**Current location**: `quantumvitas.core.yamldoc`, `quantumvitas.core.yaml_io`, `quantumvitas.core.locking`, `quantumvitas.core.journal`

**Responsibilities**:
- YAML document abstraction with mutation containment (`YamlDoc`, `StepDoc`, `CalcDoc`, `ProjectDoc`)
- Single commit point for all YAML writes (`save_yaml_doc()` in `core/yaml_io.py`)
- Edit lock acquisition for calculation/step files (`calc_edit_lock()`, `calc_run_lock()` in `core/locking.py`)
- Journal integration at save boundary (`core/journal.py`)
- Snapshot management for diff/undo

**Public Surface** (`quantumvitas/core/public.py` — ssot section):
- `load_yaml_doc()`, `save_yaml_doc()`
- `load_step_doc()`, `load_calc_doc()`, `load_project_doc()`
- `YamlDoc`, `StepDoc`, `CalcDoc`, `ProjectDoc`
- `calc_edit_lock()`, `calc_run_lock()`

**Forbidden Responsibilities**:
- MUST NOT perform selector resolution
- MUST NOT know about calculation execution semantics
- MUST NOT import from `workflow`, `execution`, `engine`, `analysis`

**Constitution alignment**: Implements S11.1 ("YAML IO must use Doc + yaml_io") and S11.5 ("Journal hook single entry point").

### 2.2 Domain: `resources` (Resource Resolution & Indexing)

**Current location**: `quantumvitas.core.resolution`, `quantumvitas.core.resources`, `quantumvitas.core.selectors`, `quantumvitas.core.models`

**Responsibilities**:
- **ULID-first resource indexing** (Constitution S2.1): build in-memory index keyed by ULID
- Project root discovery (look for `project.qv.yml` marker per S2.3)
- Selector resolution (ULID > slug > name > path, per `resolution.py` resolve order)
- Ambiguity detection and error handling

**YAML access rules** (binding decision):

Resources/resolution MAY read YAML only through the centralized YAML doc loader. Direct `yaml.safe_load` is FORBIDDEN. *(Current code violates this: `resolution.py` has ~8 direct `yaml.safe_load` calls.)*

Resources/resolution MAY read **all fields under `meta`** (`meta.*` is fully readable): `meta.ulid`, `meta.slug`, `meta.name`, `meta.kind`, and any other sub-keys of the `meta` subtree. "All of `meta.*`, nothing else" is the exact scope.

Resources/resolution MUST NOT read or interpret **any non-meta fields**: `parameters`, `cards`, `step_type_spec`, `engine`, workflow topology, `species_map`, `structure_ulid` (at step level), or any other top-level or nested key outside `meta`. *(Current code violates this: `resolution.py` reads `step_type_spec` at line ~1463 and `structure_ulid` at line ~1036.)*

Resources/resolution MUST be **read-only**: never write SSOT.

**Gate-enforceable helper** (proposed): To enforce the meta-only boundary mechanically, a helper SHALL be introduced:

```python
# In core/yaml_io.py or core/resolution_helpers.py:
def load_yaml_meta_subtree(path: Path) -> dict:
    """Load a YAML file and return ONLY the 'meta' subtree.

    Returns the dict under the 'meta' key (or '__qv_meta__' for
    legacy structure files). All other top-level keys are discarded.
    Uses _load_yaml_raw() internally — never raw yaml.safe_load.
    """
    data = _load_yaml_raw(path)
    return data.get("meta") or data.get("__qv_meta__") or {}
```

Resources domain MUST use `load_yaml_meta_subtree()` for all YAML reads during index building and resolution. This makes the meta-only boundary enforceable: a gate test can verify that `resolution.py` calls only `load_yaml_meta_subtree()`, never `_load_yaml_raw()` or `load_yaml_doc()` (which return full documents).

**Public Surface** (`quantumvitas/core/public.py` — resources section):
- `require_calculation()`, `require_step()`, `require_structure()`
- `list_calculations()`, `list_structures()`
- `build_resource_index()`, `ResourceIndex`

**Forbidden Responsibilities**:
- MUST NOT write YAML or any SSOT files
- MUST NOT interpret step parameters or calculation semantics
- MUST NOT know about execution or engine specifics

**Constitution alignment**: Implements S2.1 (ULID-only reference), S2.2 (index/cache from project root scan), S2.3 (project root marker = `project.qv.yml`), S2.4 (rename/move does not change identity).

### 2.3 Domain: `models` (Domain Models)

**Current location**: `quantumvitas.calculation.calculation`, `quantumvitas.calculation.step`, `quantumvitas.project`

**Responsibilities**:
- In-memory domain models (Calculation, Step, Project)
- Loading models from YAML (using SSOT domain)
- Model validation and integrity checks

**Public Surface** (`quantumvitas/calculation/public.py`):
- `Calculation`, `Step`, model loading methods
- Read-only model attributes

**Forbidden Responsibilities**:
- MUST NOT execute steps
- MUST NOT write SSOT files (delegate to SSOT domain)
- MUST NOT resolve selectors (delegate to Resources domain)

### 2.4 Domain: `runtime` (Execution Orchestration)

**Current location**: `quantumvitas.calculation.runner`, `quantumvitas.execution.*`, `quantumvitas.calculation.manifest`

**Responsibilities**:
- Job graph construction from calculation topology (`execution/job_graph.py`)
- Job execution orchestration (`execution/executor.py`)
- Engine handler dispatch (`execution/handlers.py`)
- Manifest management (the only persisted run-tracking truth per `calculation/manifest.py`)
- Incremental skip logic
- **Materialization**: reading step definitions from SSOT and producing `EngineInput` for engines (see Law K6)
- Side-effect coordination (outdir, raw, pseudo staging)

**Public Surface** (`quantumvitas/execution/public.py`):
- `CalculationRunner`
- `JobExecutor`, `JobGraph`, `SelectionMode`
- `get_recipe_for_engine()`

**Forbidden Responsibilities**:
- MUST NOT know about specific engine internals (delegate to handlers)
- MUST NOT write step.yaml/calculation.yaml directly (delegate to SSOT)
- MUST NOT parse engine output files (delegate to Engines/Analysis)

### 2.5 Domain: `engines` (Pluggable Engine Drivers)

**Current location**: `quantumvitas.engine.*`

**Responsibilities**:
- Engine implementations (QE, PySCF, ORCA, VASP, LAMMPS, CP2K)
- Binary invocation against materialized input files
- Per-engine output file parsing
- Engine capability declaration (`supported_presets`)

**Engine input contract** (binding decision — see Law K6 for full specification):
- Engines MUST NOT import from SSOT domain (`core.yaml_io`, `core.yamldoc`, `core.locking`, `core.journal`).
- Engines MUST NOT read `step.yaml` or `calculation.yaml` directly.
- Engines MUST NOT call `yaml.safe_load` on any SSOT file path.
- Engines SHALL consume only the `EngineInput` port provided by the runtime domain (see Section 4.1).

*(Current code violates this: `pyscf_engine.py` lines 368, 498 and `orca_engine.py` lines 514, 529 both call `yaml.safe_load` on step.yaml. See Review Report for full list.)*

**Public Surface** (`quantumvitas/engine/public.py`):
- `EngineRegistry`, `create_default_registry()`
- `Engine` protocol (abstract interface)

**Forbidden Responsibilities**:
- MUST NOT read SSOT YAML files (step.yaml, calculation.yaml, project.qv.yml)
- MUST NOT import from SSOT domain
- MUST NOT know about calculation topology or manifest
- MUST NOT manage run tracking or history

**Constitution alignment**: Implements S14 (Engine Execution Semantics). Session-chain engines (PySCF/ORCA) execute in-memory chains; artifact-bridged engines (QE) bridge via disk files. Both receive materialized inputs via `EngineInput`, not SSOT YAML.

### 2.6 Domain: `workflow` (Step Type Semantics)

**Current location**: `quantumvitas.workflow.*`

**Responsibilities**:
- Step type registry (`StepTypeRegistry` in `workflow/registry.py`)
- Step type specifications (`StepTypeSpec` dataclass)
- Step type conversion (SPEC <-> GEN via `workflow/step_type_convert.py`)
- Step factory (creating new step YAML files)
- Preset dimension mapping (via engine capability queries)

**Public Surface** (`quantumvitas/workflow/public.py`):
- `get_registry()`, `StepTypeRegistry`, `StepTypeSpec`
- `spec_from()`, `gen_from()`, `prefix_from()`
- `generate_subchain_basename()`

**Forbidden Responsibilities**:
- MUST NOT execute steps
- MUST NOT write SSOT files directly (delegate to SSOT)
- MUST NOT know about engine execution internals

**Constitution alignment**: Implements S13.2 (StepTypeRegistry is single source of truth for step_type semantics), S13.2.1 (machine step_type must be registry-known), S10.2 (workflow is runtime interpretation, not persisted entity).

### 2.7 Domain: `analysis` (Post-Run Analysis)

**Current location**: `quantumvitas.analysis.*`, `quantumvitas.parsers.*`

**Responsibilities**:
- Artifact parsing (SCF, DOS, bands, etc.)
- Analysis primitives (energy differences, band gaps)
- Artifact caching and storage
- Trajectory I/O and analysis

**Public Surface** (`quantumvitas/analysis/public.py`):
- `read_artifact()`, `artifact_exists()`, `AnalysisType`
- Analysis primitive functions

**Forbidden Responsibilities**:
- MUST NOT execute calculations
- MUST NOT modify SSOT YAML files
- MUST NOT know about execution orchestration

---

## 3. Dependency Rules

### 3.1 Import Dependency DAG

This diagram shows **allowed static import directions** between kernel domains. Arrows point from importer to importee.

```
+-------------------------------------------------------------+
|              IMPORT DEPENDENCY DAG (Static Imports)          |
+-------------------------------------------------------------+
|                                                              |
|  Level 0 (Foundation - no kernel imports):                   |
|    [ssot]                                                    |
|                                                              |
|  Level 1 (May import ssot only):                             |
|    [resources] --> [ssot]                                    |
|    [workflow]  --> [ssot]                                    |
|                                                              |
|  Level 2 (May import L1; engines MUST NOT import ssot):      |
|    [models]   --> [ssot], [resources]                        |
|    [engines]  --> [workflow]*                                 |
|                                                              |
|  Level 3 (May import L0 + L1 + L2):                          |
|    [runtime]  --> [ssot], [resources], [models],             |
|                   [workflow], [engines]                      |
|                                                              |
|  Level 4 (May import L0 + L1 + L2):                          |
|    [analysis] --> [ssot], [models]                           |
|                                                              |
|  * = limited scope (step type info only, see S3.2)           |
+-------------------------------------------------------------+
```

**Key constraint**: `[engines]` at Level 2 MUST NOT import `[ssot]`. Engines receive all required data from `[runtime]` via the `EngineInput` port. This is not a footnote exception — it is an absolute prohibition (Law K6).

### 3.2 Explicit Dependency Rules

| From Domain | May Import | MUST NOT Import | Notes |
|-------------|------------|-----------------|-------|
| `ssot` | stdlib, third-party only | All kernel domains | Foundation layer |
| `resources` | `ssot` | `models`, `runtime`, `engines`, `workflow`, `analysis` | Reads meta only |
| `workflow` | `ssot` | `runtime`, `engines` (except EXC-001) | Registry + conversion |
| `models` | `ssot`, `resources` | `runtime`, `engines`, `analysis` | Loaded from YAML |
| `engines` | `workflow` (step type info only) | **`ssot`**, `runtime`, `models`, `resources`, `analysis` | Engines MUST NOT import SSOT — absolute prohibition |
| `runtime` | `ssot`, `resources`, `models`, `workflow`, `engines` | `analysis` | Orchestrator; sole provider of EngineInput |
| `analysis` | `ssot`, `models` | `runtime`, `engines` | Reads artifacts |

### 3.3 Runtime / Dataflow Diagram

This diagram shows **runtime data flow** (what data moves between domains at execution time). This is separate from import dependencies.

```
+-------------------------------------------------------------+
|               RUNTIME DATAFLOW (Execution Time)             |
+-------------------------------------------------------------+
|                                                              |
|  [API facade] ----request----> [runtime]                    |
|       |                            |                         |
|       |                     1. load model                    |
|       |                            |                         |
|       |                     [models] <--read-- [ssot]       |
|       |                            |                         |
|       |                     2. resolve resources             |
|       |                            |                         |
|       |                     [resources] --read meta-- [ssot] |
|       |                            |                         |
|       |                     3. look up step types            |
|       |                            |                         |
|       |                     [workflow] (registry lookup)     |
|       |                            |                         |
|       |                     4. read SSOT, build EngineInput  |
|       |                     (materialize .in files, populate |
|       |                      parameters, chain context)      |
|       |                            |                         |
|       |                     5. dispatch EngineInput to engine|
|       |                            |                         |
|       |                     [engines] <-- EngineInput ---    |
|       |                       (materialized files            |
|       |                        + step_type_spec              |
|       |                        + parameters                  |
|       |                        + chain context               |
|       |                        + working_dir)                |
|       |                            |                         |
|       |                     6. engine writes output          |
|       |                     7. runner updates manifest       |
|       |                            |                         |
|       |                     8. post-run analysis             |
|       |                            |                         |
|       |                     [analysis] <--reads output files--|
|       |                            |                         |
|       v                            v                         |
|  [API facade] <---result--- [runtime]                       |
+-------------------------------------------------------------+
```

### 3.4 Cycle Prohibition

**LAW K1**: The kernel import dependency graph MUST be a DAG. No cycles permitted.

Lazy imports inside function bodies do not create module-load cycles but SHOULD be eliminated in favor of proper DAG layering where possible. See `KERNEL_EXCEPTIONS.md` EXC-002 for the remaining allowed cases.

**Enforcement**: Static import analysis SHALL fail CI if cycles are detected.

### 3.5 Cross-Domain Import Rules

**LAW K2**: Cross-domain imports MUST go through `public.py` entry points.

Each kernel package SHALL have at most one `public.py` file that defines the package's public surface for cross-domain consumers.

> **Terminology note**: `kernel/<domain>/public.py` is a **kernel-internal** cross-domain import entrypoint. Its sole purpose is dependency DAG hygiene — ensuring that cross-domain imports are explicit, auditable, and go through a single file per package. It is **NOT** the facade API (`quantumvitas.api`), is **NOT** an externally stable contract, and is **NOT** visible to frontends (daemon, CLI, GUI). Frontends import only from `quantumvitas.api` per API Constitution H1. Renaming, restructuring, or removing exports in `public.py` does not require frontend migration — only kernel-internal consumers are affected.

```python
# ALLOWED (once public.py exists):
from quantumvitas.core.public import load_yaml_doc, save_yaml_doc
from quantumvitas.engine.public import EngineRegistry

# FORBIDDEN (deep import):
from quantumvitas.core.yamldoc import YamlDoc         # Direct class import
from quantumvitas.execution.executor import JobExecutor # Deep internal import
```

**Phased enforcement**:
- Phase 1: Create `public.py` stubs that re-export current functions.
- Phase 2: Migrate external consumers to import from `public.py`.
- Phase 3: Gate test fails on any cross-domain import not through `public.py`.

---

## 4. Hard Laws

### LAW K0: Kernel MUST NOT Import API Facade

No kernel package SHALL import from `quantumvitas.api`.

**Current violations** (must be fixed):

| File | Import | Remedy |
|------|--------|--------|
| `engine/pyscf_engine.py:385,515,544` | `from quantumvitas.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |
| `workflow/registry.py:930` | `from quantumvitas.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |
| `workflow/templates.py:516` | `from quantumvitas.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |
| `presets/integration.py:314,379` | `from quantumvitas.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |
| `drivers/qe/handler.py:168` | `from quantumvitas.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |
| `calculation/folder_import.py:15` | `from quantumvitas.api import QVService` | Refactor to use kernel-level functions |

**Gate**: `tests/gates/test_kernel_no_api_import.py`

### LAW K3: YAML Writes Through Single Entry Point

All writes to SSOT YAML files (project.qv.yml, calculation.yaml, *.step.yaml) MUST go through `save_yaml_doc()` in `quantumvitas.core.yaml_io`.

**Actual single entry point** (verified in code):
- Function: `save_yaml_doc()` at `core/yaml_io.py:117`
- Lock acquisition: `calc_edit_lock()` at `core/locking.py:112` (acquired inside `save_yaml_doc` for CalcDoc/StepDoc)
- Journal hook: `save_yaml_doc()` records changes to Journal at `core/yaml_io.py:177-206`
- History hook: `save_yaml_doc()` records edit events at `core/yaml_io.py:209-219`

No `yaml.safe_dump()` calls SHALL exist outside `quantumvitas.core.yaml_io`, except for writes to whitelisted non-SSOT export zones (see `KERNEL_EXCEPTIONS.md` EXC-004).

**Gate**: `tests/gates/test_yaml_write_single_entry.py`

**Constitution alignment**: Directly implements S11.1 and S11.5.

### LAW K4: Runner Owns Execution Side Effects

Only the `runtime` domain may:
- Create/modify `raw/` directory contents
- Create/modify `outdir/` directory contents
- Update manifest (`calculation/manifest.py`)
- Stage pseudo files from `project/pseudo`

Engines are pluggable drivers:
- Engines receive `EngineInput` (see Law K6).
- Engines write output to `working_dir` only.
- Engines return `StepResult` / `JobResult`; they do NOT update manifest.

### LAW K5: No Runtime Keys in SSOT YAML

SSOT files (calculation.yaml, step.yaml, project.qv.yml) MUST NOT contain runtime-injected keys (run status, timestamps, last_run_ulid, etc.). Runtime state lives in:

| Data | Location | Format |
|------|----------|--------|
| Run tracking | `manifest.json` | JSON |
| Run history | `.history/events.jsonl` | JSONL |
| Run snapshots | `.history/runs/{ulid}/` | Mixed |

**Constitution alignment**: S10.1.2 ("step.yml must remain pure input").

### LAW K6: Engine Input Contract (EngineInput Port)

**Absolute prohibition**: Engines MUST NOT import from the SSOT domain. Engines MUST NOT read `step.yaml`, `calculation.yaml`, or `project.qv.yml`. Engines MUST NOT call `yaml.safe_load`, `_load_yaml_raw`, `load_yaml_doc`, or any YAML loader on SSOT file paths.

**Step-type safety** (per `step_type_gen_spec_constitution.md` §3.1): Engines/backends MUST NOT implement manual spec/gen conversions. Specifically forbidden in engine code:
- `spec.split("_", 1)` or any manual underscore parsing
- `f"{prefix}_{gen}"` or any manual concatenation for step-type derivation
- `startswith(prefix + "_")`, strip-prefix helpers, or custom `is_spec` checks
- `"_" in step_type` checks to determine gen vs spec (current violation in `pyscf_engine.py:387,518`)

If an engine needs to determine `step_type_gen` from a spec value, it MUST use the canonical `gen_from()` from `workflow.step_type_convert`. However, the preferred approach is for the runner to provide both `step_type_spec` and `step_type_gen` (already resolved) via `EngineInput`, eliminating any need for conversion inside engines.

The `runtime` domain is the sole bridge between SSOT and engines. The runtime reads SSOT, materializes inputs, and provides engines with an `EngineInput` port.

#### 4.1 EngineInput Interface

The runtime domain SHALL provide engines with an `EngineInput` carrying the following fields. This is an **interface specification** — implementations may use a dataclass, TypedDict, protocol, or any structure satisfying these fields.

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_ulid` | `str` | YES | ULID of the target step |
| `step_type_spec` | `str` | YES | Machine step type (e.g., `"pyscf_scf"`, `"qe_relax"`). Pre-loaded from SSOT by the runner. |
| `step_type_gen` | `str` | YES | Engine-agnostic step type (e.g., `"scf"`, `"relax"`). Pre-resolved by the runner via canonical `gen_from()`. Engines MUST NOT re-derive this. |
| `working_dir` | `Path` | YES | Directory containing materialized input files; engine writes output here |
| `parameters` | `dict` | YES | Step parameters. Pre-loaded from SSOT by the runner. |
| `materialized_inputs` | `dict[str, Path]` | YES | Map of input file name → path (e.g., `{"scf.in": Path(...)}` for QE). For session-chain engines, may be empty if the engine generates inputs from `parameters`. |
| `run_ulid` | `str` | YES | Current run identity for correlation |
| `chain` | `list[ChainStepEntry]` | NO | For session-chain engines (PySCF, ORCA): ordered list of chain steps from root to target. `None` for single-step / artifact-bridged engines. |
| `upstream_artifacts` | `dict[str, Path]` | NO | For artifact-bridged engines: references to upstream output files (e.g., `{"gbw": Path("scf.gbw")}` for ORCA GBW bridging). `None` for session-chain engines. |
| `structure_data` | `dict` | NO | Resolved structure data for steps requiring structure input. Contains `structure_path`, `charge`, `spin`, `unit`. `None` for non-structure steps (MP2, TD, etc.). |

#### 4.2 ChainStepEntry Interface

For session-chain engines, each entry in `chain` carries:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `step_ulid` | `str` | YES | ULID of this chain step |
| `step_type_spec` | `str` | YES | Machine step type for this step |
| `step_type_gen` | `str` | YES | Engine-agnostic step type for this step. Pre-resolved by runner. |
| `parameters` | `dict` | YES | Step parameters (pre-loaded from SSOT) |
| `requires_structure` | `bool` | YES | Whether this step consumes structure input |
| `step_artifacts_dir` | `Path` | YES | Directory for this step's output artifacts |

#### 4.3 Session-Chain vs Artifact-Bridged Engines

| Execution Model | Engines | EngineInput Usage | State Propagation |
|-----------------|---------|-------------------|-------------------|
| **Session-chain** (S14.2) | PySCF, ORCA | Uses `chain` field: runner provides full chain context. Engine re-executes chain in a single session/subprocess. | In-memory (`mf` object for PySCF) or session-local files (GBW for ORCA). |
| **Artifact-bridged** (S14.1) | QE, VASP, LAMMPS, CP2K | Uses `materialized_inputs` field: runner writes `.in` files to `working_dir`. Engine invokes binary. | Disk files in `working_dir`. |

**Key invariant**: In both models, the engine receives all required data through `EngineInput`. The engine MUST NOT reach back to SSOT for any data. The runner is responsible for:
1. Loading step definitions from SSOT (via `load_step_doc()` or equivalent)
2. Populating `step_type_spec` and `parameters` from the loaded SSOT data
3. Resolving structure references (via resources domain)
4. Building the chain context (for session-chain engines) by iterating chain steps and populating each `ChainStepEntry`
5. Materializing input files (for artifact-bridged engines) by writing `.in` files to `working_dir`
6. Providing `upstream_artifacts` references when steps depend on prior outputs

#### 4.4 PySCF Remediation Path

**Current violation**: `pyscf_engine.py` reads `step_type_spec` from step.yaml at lines 368 and 498 via `yaml.safe_load`.

**Why it reads YAML**: The engine needs `step_type_spec` for each step in the chain to build `job_chain.json` (the subprocess dispatch spec). Currently, `step.step_type_spec` on the in-memory object is not reliably populated, so the engine falls back to reading the SSOT file directly.

**Constitution-aligned fix**: The runner SHALL populate `EngineInput.chain` with `ChainStepEntry` objects where `step_type_spec` is pre-loaded from SSOT. The PySCF engine reads `step_type_spec` from `ChainStepEntry` instead of from step.yaml. No change to session-chain execution semantics — the engine still builds `job_chain.json` and launches a subprocess, but it builds it from `EngineInput.chain` data rather than YAML reads.

**Specific mapping** (current code → EngineInput):
- `yaml.safe_load(step_yaml_path)["step_type_spec"]` → `chain_entry.step_type_spec`
- `step.parameters` (already from object) → `chain_entry.parameters`
- `structure_data` (already resolved by runner) → `engine_input.structure_data`

#### 4.5 ORCA Remediation Path

**Current violation**: `orca_engine.py` reads `step_type_spec` at line 514 and `parameters` at line 529 from step.yaml via `yaml.safe_load`.

**Why it reads YAML**: The engine wraps each step into a `StepWrapper` for chain detection (`detect_chains`). When `step.step_type_spec` or `step.parameters` is missing/unreliable on the in-memory object, it falls back to reading SSOT.

**Constitution-aligned fix**: The runner SHALL populate `EngineInput.chain` with `ChainStepEntry` objects carrying both `step_type_spec` and `parameters` pre-loaded from SSOT. The ORCA engine builds `StepWrapper` objects from `ChainStepEntry` data instead of YAML reads. No change to strong-chain/artifact-bridged execution semantics — the engine still detects chains, fuses ORCA input, and bridges via GBW files, but builds wrappers from `EngineInput.chain` rather than YAML.

**Specific mapping** (current code → EngineInput):
- `yaml.safe_load(step_yaml_path)["step_type_spec"]` → `chain_entry.step_type_spec`
- `yaml.safe_load(step_yaml_path)["parameters"]` → `chain_entry.parameters`
- `step.meta.ulid` → `chain_entry.step_ulid`

**Constitution alignment**: S13.2.2 ("execution reads step.yaml" is the runner's job, not the engine's), S14.1-14.3 (engine execution semantics).

### LAW K7: YAML Reads Through Centralized Loader

All YAML reads of SSOT files within the kernel MUST use the centralized loader:
- `_load_yaml_raw()` or `load_yaml_doc()` from `core/yaml_io.py`
- Or the type-specific loaders: `StepDoc.load()`, `CalcDoc.load()`, `ProjectDoc.load()`

Direct `yaml.safe_load()` calls on SSOT file paths are FORBIDDEN.

**Exception**: The `resources` domain SHALL use `load_yaml_meta_subtree()` (see Section 2.2) for lightweight meta-only reads during index building. This helper uses `_load_yaml_raw()` internally but returns only the `meta` subtree, enforcing the meta-only access boundary. Resources MUST NOT call `_load_yaml_raw()` directly and MUST NOT use raw `yaml.safe_load`.

**Constitution alignment**: S11.1.

### LAW K9: No "api" Naming in Kernel

Kernel files/modules MUST NOT use "api" in their names:
- **FORBIDDEN**: `kernel_api.py`, `internal_api.py`, `public_api.py`
- **ALLOWED**: `public.py`, `interface.py`, `protocol.py`

**Gate**: `tests/gates/test_kernel_no_api_naming.py`

---

## 5. Side-Effect Control

### 5.1 SSOT Write Path

```
Any Code --> YamlDoc.set/delete/apply_patch --> doc.save()
                                                    |
                                           save_yaml_doc()    [core/yaml_io.py:117]
                                                    |
                                        +-----------+-----------+
                                        |           |           |
                                  edit_lock    _save_yaml_raw   |
                              [locking.py:112]  [yaml_io.py:65] |
                                                    |           |
                                              Journal.record    History.append
                                            [yaml_io.py:177]  [yaml_io.py:209]
```

### 5.2 Execution Ownership

```
+-------------------------------------------------------------+
|  Runner (runtime domain):                                    |
|    - Owns: manifest.json, raw/, pseudo staging, history      |
|    - Reads SSOT: loads step definitions, parameters          |
|    - Builds EngineInput: populates all fields from SSOT      |
|    - Materializes: .in files for artifact-bridged engines    |
|    - Delegates to: JobExecutor -> Engine handlers            |
|                                                              |
|  Engine (engines domain):                                    |
|    - Receives: EngineInput (step_type_spec, parameters,      |
|              working_dir, chain context, materialized files)  |
|    - Produces: output files in working_dir                   |
|    - Returns: JobResult (success/failure, metrics)           |
|    - Does NOT: read SSOT YAML, update manifest               |
+-------------------------------------------------------------+
```

---

## 6. Ports/Interfaces for Extensibility

### 6.1 Engine Protocol

```python
class Engine(Protocol):
    name: str

    def run_step(
        self,
        engine_input: EngineInput,  # All required data (NOT raw YAML)
    ) -> StepResult: ...

    @property
    def supported_presets(self) -> list[str]: ...
```

**Adding a new engine**:
1. Create `quantumvitas.engine.{name}_engine.py` implementing `Engine` protocol
2. Register in `create_default_registry()` (`engine/registry.py`)
3. Add step types to `workflow/registry.py` `_STEP_TYPES` dict
4. Add recipe to `execution/recipes.py` `get_recipe_for_engine()`

No other kernel files need modification. DAG preserved.

### 6.2 Recipe Protocol

```python
class Recipe(Protocol):
    def materialize(
        self,
        steps: list[Step],
        working_dir: Path,
        step_shas: dict[str, str],
    ) -> JobGraph: ...
```

### 6.3 Analysis Parser Protocol

```python
class ArtifactParser(Protocol):
    def can_parse(self, artifact_type: AnalysisType, engine: str) -> bool: ...
    def parse(self, output_path: Path) -> dict: ...
```

---

## 7. Gates & Enforcement

### 7.1 Proposed Gate Tests

| Gate ID | Name | Checks | Priority |
|---------|------|--------|----------|
| G-K0 | Kernel No API Import | kernel MUST NOT import `quantumvitas.api` | P0 |
| G-K1 | Kernel No Frontend Import | kernel MUST NOT import `quantumvitas.cli/daemon` | P0 |
| G-K2 | Frontend No Kernel Import | frontends MUST NOT import kernel directly | P0 (exists) |
| G-K3 | YAML Write Single Entry | `yaml.safe_dump` only in `yaml_io.py` (+ EXC-004 whitelist) | P0 |
| G-K6 | Engine No SSOT Import | engine/ MUST NOT import `core.yaml_io`/`core.yamldoc`/`core.locking`/`core.journal`; engine/ MUST NOT contain `yaml.safe_load` | P1 |
| G-K7 | No Import Cycles | kernel import graph is DAG | P1 |
| G-K9 | No api.py in Kernel | no file named `api.py` inside kernel packages | P2 |
| G-K2b | Deep Import Ban | cross-domain imports via `public.py` only | P2 (phased) |

### 7.2 Enforcement Plan

**PR-K0** implements G-K0, G-K1, G-K3, G-K6 as gate tests. Tests MAY include an explicit allowlist for known violations, with the allowlist shrinking to zero over subsequent PRs.

---

## 8. Risk Assessment

### 8.1 Strictness Evaluation

| Law | Assessment |
|-----|------------|
| K0 (No API import) | Critical. 10 violations exist; all fixable by using `gen_from()` from workflow. |
| K1 (No cycles) | Appropriate. No hard cycles found; lazy imports manageable. |
| K2 (public.py) | Phased rollout realistic. ~200 deep imports exist. |
| K3 (YAML single entry) | Critical for Journal integrity. 10+ violations. |
| K6 (Engine input contract) | Important. 4 violations in PySCF/ORCA. Constitution-aligned fix via EngineInput port. |
| K7 (YAML reads centralized) | Important. ~8 violations in resolution.py. |

### 8.2 Exception Policy

All exceptions MUST be documented in `KERNEL_EXCEPTIONS.md` with:
- Explicit scope constraint
- Quarterly review date or hard deletion deadline
- Expiration policy

See companion document for current exceptions.

---

**End of Kernel Dependency Spec v3.1**
