# QMatSuite Repository Status Report

**Report Type**: Current-State Audit (As-Is)  
**Scan Date**: 2026-02-09 20:36:02 EST  
**Commit Hash**: `5fc4f23a296b7163b46414323be62397ace297ec`  
**Scan Method**: Two-pass audit (broad scan + targeted deep dives)

---

## Audit Log

### Broad Scan (PASS 1)
**Directories scanned:**
- Repository root (`/Users/hh7465/QMatSuite`)
- `src/quantumvitas/` (main source tree)
- `docs/` (documentation tree)
- `tests/` (test suites)
- `gui/` (GUI frontend)
- `resources/` (demo projects, pseudos, templates)

**Key documents read:**
- `CONSTITUTION.md` (v2.1, 2026-02-03)
- `README.md`
- `pyproject.toml`
- `docs/governance/README.md`
- `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md`
- `docs/governance/API_CONSTITUTION.md`
- `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md`
- `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`
- `docs/governance/PARAMSPACE_SPEC.md`
- `docs/governance/KERNEL_DEPENDENCY_SPEC.md`

**Search queries executed:**
- `rg "engine_prefix|supported_gen_steps|get_materialization_map"`
- `rg "step_type_gen|step_type_spec"`
- `rg "\.provenance|\.history|provenance"`
- `rg "parameter_scan|@scan:|ScanRef"`
- `rg "rpc|endpoint|DTO|schema"` (in `gui/`)
- `rg "manifest\.json|\.provenance|\.history"`
- `find resources/demo_projects -name "*.yml"`
- `find tests/gates -name "test_*.py"`
- `find src/quantumvitas/drivers -mindepth 1 -maxdepth 1 -type d`

### Deep Dives (PASS 2)
**Files read per section:**
- SSOT/Provenance: `src/quantumvitas/core/yaml_io.py`, `src/quantumvitas/provenance/`, `src/quantumvitas/calculation/manifest.py`
- Step Types: `src/quantumvitas/workflow/step_type_convert.py`, `src/quantumvitas/workflow/gen_steps.py`, `src/quantumvitas/core/driver_registry.py`
- Engines: All `src/quantumvitas/drivers/*/driver.py` files
- Runner: `src/quantumvitas/calculation/runner.py`, `src/quantumvitas/execution/executor.py`
- GUI/RPC: `src/quantumvitas/daemon/server.py`, `src/quantumvitas/api/service.py`, `gui/src/types/qv.ts`
- Tests: `tests/gates/` inventory, `tests/unit/`, `tests/integration/`, `tests/cli/`
- Demos: `resources/demo_projects/`, `tools/demo_generators/`, `tests/gates/test_demo_integrity.py`

---

## Table of Contents

0. [Repo Snapshot Metadata](#0-repo-snapshot-metadata)
1. [Repo Structure Overview](#1-repo-structure-overview)
2. [Governing Documents Index](#2-governing-documents-index)
3. [Present-Tense SSOT Model](#3-present-tense-ssot-model)
4. [Provenance System Status](#4-provenance-system-status)
5. [Step Type System Status (GEN/SPEC)](#5-step-type-system-status-genspec)
6. [Engine Support Matrix](#6-engine-support-matrix)
7. [Runner + Execution Pipeline](#7-runner--execution-pipeline)
8. [Scan / ParamSpace / Presets](#8-scan--paramspace--presets)
9. [GUI Status](#9-gui-status)
10. [CLI/Daemon/API/Kernel Layering Status](#10-clidaemonapikernel-layering-status)
11. [Tests and Gates Inventory](#11-tests-and-gates-inventory)
12. [Demo Store Status](#12-demo-store-status)
13. [Known Limitations Explicitly Documented](#13-known-limitations-explicitly-documented)

---

## 0. Repo Snapshot Metadata

- **Commit Hash**: `5fc4f23a296b7163b46414323be62397ace297ec`
- **Scan Date/Time**: 2026-02-09 20:36:02 EST
- **Scan Commands**:
  - `git rev-parse HEAD`
  - `date`
  - `find resources/demo_projects -name "*.yml" | wc -l` → 21 demos
  - `find tests/gates -name "test_*.py" | wc -l` → 59 gate tests
  - `find src/quantumvitas/drivers -mindepth 1 -maxdepth 1 -type d | wc -l` → 16 engine drivers

**Evidence pointers:**
- Repository root: `/Users/hh7465/QMatSuite`
- Git state: `git rev-parse HEAD` output

---

## 1. Repo Structure Overview

### Top-Level Directory Map

```
QMatSuite/
├── src/quantumvitas/          # Main Python package
│   ├── api/                   # API facade (QVService, DTOs, utils)
│   ├── calculation/           # Calculation/step models, runner, manifest
│   ├── cli/                   # Typer CLI (qv command)
│   ├── core/                  # Core domain (models, resolution, SSOT I/O, drivers)
│   ├── daemon/                # JSON-RPC daemon server
│   ├── drivers/               # Engine driver bundles (16 engines)
│   ├── engine/                # Legacy engine layer (deprecated, being phased out)
│   ├── execution/             # Execution pipeline (executor, handlers, recipes)
│   ├── provenance/            # Provenance/history system (SQLite + CAS)
│   ├── workflow/              # Workflow layer (step types, templates, presets)
│   ├── analysis/              # Analysis pipeline (parsers, plotting, artifacts)
│   ├── io/                    # I/O utilities (structure, QE input/output)
│   ├── project/               # Project model and snapshot export
│   └── presets/               # Preset/ParamSpace system
├── tests/                      # Test suites
│   ├── gates/                 # Constitutional gate tests (59 files)
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests (require engine binaries)
│   ├── cli/                   # CLI tests
│   ├── daemon/                # Daemon/RPC tests
│   ├── drivers/               # Driver-specific tests
│   └── data/                  # Test data and fixtures
├── gui/                        # Electron GUI frontend (TypeScript/React)
│   ├── src/                   # TypeScript source
│   ├── electron/              # Electron main process
│   └── tests/e2e/             # E2E tests (Playwright)
├── docs/                       # Documentation
│   ├── governance/            # Binding governance specs
│   ├── architecture/           # Architecture design docs
│   ├── engines/               # Engine-specific docs
│   ├── review/                # Review/audit reports
│   └── [various]/             # Other documentation
├── resources/                   # Static resources
│   ├── demo_projects/         # Demo project snapshots (21 YAML files)
│   ├── pseudo/                # Internal pseudopotential library
│   ├── lammps/potentials/     # LAMMPS potential files
│   └── calculation_templates/ # Calculation templates
├── tools/                      # Utility scripts
│   └── demo_generators/       # Demo generation scripts
├── pyproject.toml             # Python package metadata
├── README.md                  # Main README
└── CONSTITUTION.md            # Central constitution (v2.1)
```

### Key Directory Purposes

| Directory | Purpose | Evidence |
|-----------|---------|----------|
| `src/quantumvitas/core/` | Core domain models, SSOT I/O, driver registry, resolution | `src/quantumvitas/core/models.py`, `yaml_io.py`, `driver_registry.py` |
| `src/quantumvitas/drivers/` | Engine driver bundles (one per engine) | 16 subdirectories: `qe/`, `vasp/`, `orca/`, `pyscf/`, etc. |
| `src/quantumvitas/provenance/` | Provenance/history system (SQLite + CAS) | `src/quantumvitas/provenance/db.py`, `cas.py`, `schema.py` |
| `tests/gates/` | Constitutional gate tests enforcing invariants | 59 test files enforcing constitution laws |
| `resources/demo_projects/` | Demo project snapshots (YAML) | 21 `.yml` files + reference artifacts |
| `docs/governance/` | Binding governance specifications | 11 governance spec documents |

**Evidence pointers:**
- Directory structure: `list_dir` outputs
- Engine count: `find src/quantumvitas/drivers -mindepth 1 -maxdepth 1 -type d | wc -l`
- Demo count: `find resources/demo_projects -name "*.yml" | wc -l`
- Gate test count: `find tests/gates -name "test_*.py" | wc -l`

---

## 2. Governing Documents Index

### Constitution (Highest Authority)

| Document | Location | Version | Last Updated | Key Invariants |
|----------|----------|---------|--------------|----------------|
| `CONSTITUTION.md` | Repo root | v2.1 | 2026-02-03 | All high-level invariants (20 sections) |
| `CONSTITUTION_ZH.md` | Repo root | — | 2026-02-03 | **DEPRECATED** (Chinese version, non-authoritative) |

**Constitution Sections (Summary):**
- §1: Language Policy (English default)
- §2: SSOT & Persistence (`calculation.yaml` + `step.yaml` only)
- §3: Present vs Past (History world separation)
- §4: Concurrency & Locks (`edit.lock`, `run.lock`)
- §5: Incremental Run Manifest (non-SSOT bookkeeping)
- §6: Identity (ULID-only)
- §7: Step Type Constitution (GEN/SPEC only)
- §8: Preset/ParamSpace/IR (non-persistent intent layer)
- §9: Species/Pseudopotential SSOT
- §10: Scan Rules (hard law)
- §11: Managed/Injected Parameters UI Policy
- §12: UI Input → YAML → Writer Type Contract
- §13: RELAX Audit Law
- §14: LAMMPS Integration Constitution
- §15: Geometry Constitution
- §16: QE Structure Schema
- §17: Engine Execution Semantics
- §18: API Layering & Facade
- §19: Kernel Internal Dependencies
- §20: Data Root Directories & Temporary Directories

**Evidence pointers:**
- `CONSTITUTION.md` (555 lines)
- `docs/governance/README.md` (document hierarchy)

### Governance Specs (Binding Laws)

| Document | Location | Status | Governs | Constitution Reference |
|----------|----------|--------|---------|------------------------|
| `API_CONSTITUTION.md` | `docs/governance/` | FINAL v2.1 | API surface, import layering, utils policy, DTOs, H9 filesystem control | §18 |
| `KERNEL_DEPENDENCY_SPEC.md` | `docs/governance/` | PROPOSED v3.1 | Kernel 7-domain model, dependency DAG, SSOT writes, engine inputs | §19 |
| `KERNEL_EXCEPTIONS.md` | `docs/governance/` | ACTIVE v3.1 | Approved exceptions to kernel dependency rules (EXC-001 through EXC-004) | §19 |
| `STEP_TYPE_GEN_SPEC_CONSTITUTION.md` | `docs/governance/` | FINAL v1.1 | GEN/SPEC step type namespaces, derivation rule, conversion API, execution layering | §7 |
| `ENGINE_INTEGRATION_CONSTITUTION.md` | `docs/governance/` | SPECIFICATION v1.0 | Engine integration invariants: no guessing, hard error, explicit mapping, driver self-containment | §17 |
| `PARAMSPACE_SPEC.md` | `docs/governance/` | FINAL v1.0 | ParamSpace framework: compiler/detector equivalence, single-writer, cell semantics, Oracle | §8 |
| `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` | `docs/governance/` | FINAL v1.0 | Engine recipe system, runner independence, recipe archetypes, directory contracts, bans | §17 |
| `PROVENANCE_VERSIONED_HISTORY_SPEC.md` | `docs/governance/` | PROPOSED v1.1 | Provenance/history system: SQLite timeline, CAS blobs, OperationContext, rollback, artifact tiers | §3 |
| `PROVENANCE_IMPLEMENTATION_PLAN.md` | `docs/governance/` | IMPLEMENTATION | Code review + phased implementation plan for provenance system | — |

**Evidence pointers:**
- `docs/governance/README.md` (complete index with cross-references)
- Individual spec files in `docs/governance/`

---

## 3. Present-Tense SSOT Model

### SSOT Files (As Implemented)

**Sole Executable Truth** (per Constitution §2.1):
- `calculation.yaml`: Structure, species_map (pseudo triple), step topology
- `step.yaml`: Step parameters (pure input, no workflow/preset/provenance metadata)

**SSOT Location Pattern:**
```
<project_root>/
├── project.qv.yml                    # Project manifest (SSOT)
├── structures/
│   └── <ulid>.json                    # Structure resources (SSOT)
└── calculations/
    └── <calc_ulid>/
        ├── calculation.yaml           # Calculation SSOT
        └── steps/
            └── <step_ulid>.step.yaml # Step SSOT
```

### SSOT I/O Implementation

**Centralized YAML I/O** (per Constitution §2.4):
- All YAML reads/writes go through `quantumvitas.core.yaml_io`
- Uses Doc layer (`quantumvitas.core.yamldoc`) for structured access
- Direct `yaml.safe_load`/`yaml.safe_dump` usage is **forbidden**

**Key Functions:**
- `save_yaml_doc()`: Writes YAML with `edit.lock` (non-reentrant)
- `load_yaml_doc()`: Reads YAML via Doc layer
- `yaml_io.get_project_doc()`, `get_calculation_doc()`, `get_step_doc()`

**Evidence pointers:**
- `src/quantumvitas/core/yaml_io.py` (centralized I/O)
- `src/quantumvitas/core/yamldoc.py` (Doc layer)
- Constitution §2.1, §2.4
- Gate: `tests/gates/test_yaml_write_single_entry.py`, `test_yaml_read_single_entry.py`

### Input Files Are Intermediates

**Materialization Flow** (per Constitution §2.2):
- Input files (e.g., QE `.in` files) written to `raw/` via clean rewrite during materialization
- Run only reads from `raw/`
- Modifying YAML during a run does not affect the current run (only the next run)

**Evidence pointers:**
- `src/quantumvitas/execution/recipes.py` (materialization)
- `src/quantumvitas/calculation/runner.py` (execution reads from `raw/`)

### Species/Pseudopotential SSOT

**Project-Run Pseudo SSOT** (per Constitution §9.1):
- SSOT in `calculation.yaml`: `species_map` (element / mass / pseudo filename + hash)
- Step-level `species_overrides` is warning+ignored (only for legacy/standalone)
- Runtime `pseudo_dir` forced to `project/pseudo`

**Three Pseudo Sources** (per Constitution §9.3):
1. **internal**: `repo/resources/pseudo`
2. **lib**: User-installed at `~/.qmatsuite/libraries/pseudo/`
3. **project runtime**: `project/pseudo`

**Evidence pointers:**
- `src/quantumvitas/core/pseudo.py` (pseudo management)
- `src/quantumvitas/core/pseudo_materialization.py` (staging)
- Constitution §9

---

## 4. Provenance System Status

### Implementation Status

**Provenance System** (per `PROVENANCE_VERSIONED_HISTORY_SPEC.md` v1.1):
- **Status**: PROPOSED spec, **IMPLEMENTED** in codebase
- **Location**: `src/quantumvitas/provenance/`
- **Storage**: SQLite database (`.provenance/provenance.db`) + Content-Addressed Store (`.provenance/.cas/`)

### Database Schema

**SQLite Tables** (per `src/quantumvitas/provenance/schema.py`):
- `operations`: Records all SSOT-writing operations (append-only timeline)
- `runs`: Records calculation run events
- `run_steps`: Normalized per-step execution records
- `analysis_snapshots`: Links run/object analysis snapshots to CAS blobs
- `cas_objects`: Metadata for objects in `.cas/objects/`

**Schema Version**: `CURRENT_SCHEMA_VERSION = 3`

**Evidence pointers:**
- `src/quantumvitas/provenance/schema.py` (DDL)
- `src/quantumvitas/provenance/db.py` (database operations)

### CAS (Content-Addressed Store)

**CAS Implementation** (per `src/quantumvitas/provenance/cas.py`):
- Objects stored by SHA-256 hash: `.cas/objects/<first2>/<rest>`
- Immutable objects (never modified after write)
- Duplicate writes (same hash) are no-ops
- Storage tiers: Tier-0 (run snapshots), Tier-0.5 (reproducibility assets), Tier-1 (derived outputs), Tier-2 (raw artifacts), Tier-3 (large optional outputs)

**Evidence pointers:**
- `src/quantumvitas/provenance/cas.py` (CAS implementation)
- Law P5 (CAS Integrity) in `PROVENANCE_VERSIONED_HISTORY_SPEC.md`

### OperationContext

**OperationContext Required** (per Law P2):
- All YAML writes require `OperationContext` passed through call chain
- Explicit intent tracking (not inferred)
- Located in: `src/quantumvitas/provenance/opctx.py`

**Evidence pointers:**
- `src/quantumvitas/provenance/opctx.py` (OperationContext definitions)
- Gate: `tests/gates/test_provenance_opctx_required.py`

### History World Separation

**Present vs Past** (per Constitution §3):
- **Present**: SSOT files in working directory
- **Past**: `.history/` (sole location for derived narrative artifacts)
- `.history/` is append-only, immutable
- Deleting `.history/` means history UI goes blank (MUST NOT be "rebuilt")

**Legacy `.history/` Status**:
- Gate test: `tests/gates/test_no_legacy_history.py` (enforces no legacy `.history/` usage)
- New system uses `.provenance/` (SQLite + CAS)

**Evidence pointers:**
- Constitution §3
- `tests/gates/test_no_legacy_history.py`
- `tests/gates/test_provenance_independence.py` (Law P1: History world must not participate in runtime logic)

### Provenance Integration Points

**Runner Integration**:
- `src/quantumvitas/calculation/runner.py` calls `update_provenance_after_step()`
- Run recording: `record_run_start()`, `record_run_complete()`, `record_run_step()`

**Evidence pointers:**
- `src/quantumvitas/provenance/recording.py` (recording functions)
- `src/quantumvitas/calculation/runner.py` (runner integration)

---

## 5. Step Type System Status (GEN/SPEC)

### Two Namespaces (As Implemented)

**GEN and SPEC Only** (per Constitution §7.1):
- `step_type_gen`: Intent/UI/workflow/preset/ParamSpace/file naming (engine-agnostic)
- `step_type_spec`: SSOT execution/step.yaml/runner/dispatch/handler (engine-specific)

**Examples:**
- GEN: `scf`, `relax`, `bandspw`, `wannierprep`
- SPEC: `qe_scf`, `vasp_relax`, `w90_wannierprep`, `qe_bandspw`

**Evidence pointers:**
- Constitution §7
- `docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md`

### Derivation Rule (Core Law)

**Canonical Derivation** (per Constitution §7.2):
```
step_type_spec = f"{engine_prefix}_{step_type_gen}"
```

**Implementation**:
- Canonical functions in `src/quantumvitas/workflow/step_type_convert.py`:
  - `spec_from(prefix, gen)` → SPEC
  - `gen_from(spec)` → GEN
  - `prefix_from(spec)` → prefix
  - `is_spec(x)`, `is_gen(x)` → predicates

**Underscore Ban**:
- `engine_prefix` and `step_type_gen` MUST NOT contain underscores
- Reliable splitting at first underscore

**Evidence pointers:**
- `src/quantumvitas/workflow/step_type_convert.py` (canonical conversion)
- Gate: `tests/gates/test_underscore_ban.py`, `test_no_manual_join_split.py`

### GEN Step Registry (SSOT)

**GenStepRegistry** (per `src/quantumvitas/workflow/gen_steps.py`):
- `GenStepRegistry.GEN_STEPS`: Frozen set of all valid GEN steps
- Current count: 30+ GEN steps (scf, hf, nscf, relax, bands, bandspw, dos, wannierprep, pw2wannier, wannier, ph, md, minimize, mp2, td, freq, vmc, dmc, wfopt, setup, gw, bse, optics, custom, etc.)

**Evidence pointers:**
- `src/quantumvitas/workflow/gen_steps.py` (SSOT for GEN steps)
- Gate: `tests/gates/test_step_type_constitution.py`

### Bans (As Enforced)

**Legacy Step Type Aliases Banned**:
- `vc-relax`, `opt`, `w90_preproc`, `w90_run`, etc. are fully banned
- Gate: `tests/gates/test_banned_legacy_aliases.py`

**Bare `step_type` Field Banned**:
- Must explicitly use `step_type_gen` or `step_type_spec`
- Gate: `tests/gates/test_no_bare_step_type.py`

**Manual Split/Join Banned**:
- Code MUST NOT manually split/join underscores
- Must use canonical conversion functions
- Gate: `tests/gates/test_no_manual_join_split.py`

**Evidence pointers:**
- Constitution §7.3
- Gate tests listed above

---

## 6. Engine Support Matrix

### Implemented Engines (16 Total)

**Base Engines (12)**:

| Engine | `engine_family` | `PREFIX` | `SUPPORTED_GEN_STEPS` | Category | Evidence |
|--------|----------------|----------|----------------------|----------|----------|
| Quantum ESPRESSO | `qe` | `qe` | scf, nscf, relax, bands, bandspw, dos, pw2wannier, ph, md, custom | Periodic (PW-DFT) | `drivers/qe/driver.py:10-13` |
| VASP | `vasp` | `vasp` | scf, nscf, relax, md, bandspw | Periodic (PW-DFT) | `drivers/vasp/driver.py:23-25` |
| ABINIT | `abinit` | `abinit` | scf, nscf, relax | Periodic (PW-DFT) | `drivers/abinit/driver.py:21-23` |
| CP2K | `cp2k` | `cp2k` | scf, relax, md, bandspw, dos | Periodic (mixed basis) | `drivers/cp2k/driver.py:25-27` |
| Siesta | `siesta` | `siesta` | scf, relax, md, bands, dos | Periodic (NAO-DFT) | `drivers/siesta/driver.py:26-28` |
| GPAW | `gpaw` | `gpaw` | scf, nscf, relax, bandspw, dos, md | Periodic (PW-DFT) | `drivers/gpaw/driver.py:24-26` |
| ORCA | `orca` | `orca` | scf, hf, relax, td | Molecular (QC) | `drivers/orca/driver.py:21-23` |
| Gaussian | `gaussian` | `gaussian` | scf, hf, relax, freq, mp2, td | Molecular (QC) | `drivers/gaussian/driver.py:27-29` |
| Psi4 | `psi4` | `psi4` | scf, hf, mp2, relax, td | Molecular (QC) | `drivers/psi4/driver.py:22-24` |
| PySCF | `pyscf` | `pyscf` | scf, relax, mp2, td | Molecular (QC) | `drivers/pyscf/driver.py:23-25` |
| xTB | `xtb` | `xtb` | relax | Molecular (semi-empirical) | `drivers/xtb/driver.py:27` |
| LAMMPS | `lammps` | `lammps` | minimize, md, relax | Classical MD | `drivers/lammps/driver.py:29-31` |

**Postprocessing Engines (3)**:

| Engine | `engine_family` | `PREFIX` | `SUPPORTED_GEN_STEPS` | Depends On | Evidence |
|--------|----------------|----------|----------------------|-----------|----------|
| Wannier90 | `w90` | `w90` | wannierprep, pw2wannier, wannier | QE (pw2wannier) | `drivers/w90/driver.py:31-32` |
| QMCPACK | `qmcpack` | `qmcpack` | vmc, dmc, wfopt | DFT (wavefunctions) | `drivers/qmcpack/driver.py:20-21` |
| Yambo | `yambo` | `yambo` | setup, gw, bse, optics | QE/ABINIT (converter) | `drivers/yambo/driver.py:27-28` |

**Legacy Engine Layer (1)**:
- GPAW (also has legacy `engine/gpaw_engine.py`, being phased out)

**Evidence pointers:**
- All `src/quantumvitas/drivers/*/driver.py` files (PREFIX and SUPPORTED_GEN_STEPS declarations)
- `src/quantumvitas/core/driver_registry.py` (registry implementation)
- `docs/architecture/GUI_ENGINE_FAMILY_DEMO_SPEC.md` (engine classification)

### Driver Bundle Structure

**Standard Driver Bundle** (per `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`):
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

**Evidence pointers:**
- `src/quantumvitas/drivers/qe/` (example driver bundle)
- `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` §10.1

### Materialization Rules

**Materialization Maps**:
- Each driver declares `get_materialization_map()` or builds from `PREFIX + SUPPORTED_GEN_STEPS`
- Maps GEN steps to engine-specific parameter keys
- Stored in `DriverRegistry._materialization_maps`

**Evidence pointers:**
- `src/quantumvitas/core/driver_registry.py` (`_build_materialization_map()`)
- Individual driver implementations

### Execution Modes

**Three Execution Modes** (per Constitution §17.1):
1. **Session-chain**: PySCF/ORCA (in-memory state chain, linearly ordered)
2. **Artifact-bridged**: QE/W90/LAMMPS (disk file bridging, steps can be independent)

**Recipe Archetypes** (per `ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md`):
- **Directory-state**: QE (shared `outdir/.save`)
- **Strong-chain**: ORCA/PySCF/CP2K (strict linear dependency)
- **Cleanup**: VASP (clean working directory per step)

**Evidence pointers:**
- `src/quantumvitas/execution/recipes.py` (recipe implementations)
- `docs/governance/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md` §4

---

## 7. Runner + Execution Pipeline

### Runner Implementation

**Calculation Runner** (`src/quantumvitas/calculation/runner.py`):
- Orchestrates step execution and verification
- Integrates with provenance to record run revisions
- Uses `EngineRegistry` for engine lookup (legacy) and `DriverRegistry` (new)

**Key Functions:**
- `run_calculation()`: Full calculation run
- `run_step()`: Single step execution
- `compute_io_dir_from_calculation_model()`: SSOT for I/O directory path

**Evidence pointers:**
- `src/quantumvitas/calculation/runner.py` (790 lines)

### Execution Pipeline

**Executor** (`src/quantumvitas/execution/executor.py`):
- Engine-agnostic executor
- Dispatches through `DriverRegistry`
- Manages job graphs, handlers, recipes

**Handlers** (`src/quantumvitas/execution/handlers.py`):
- Step execution handlers (one per engine)
- Retrieved via `DriverRegistry.get_handler(step_type_spec)`

**Recipes** (`src/quantumvitas/execution/recipes.py`):
- Materialize step parameters → JobGraph
- Three archetypes: Directory-state, Strong-chain, Cleanup

**Evidence pointers:**
- `src/quantumvitas/execution/executor.py`
- `src/quantumvitas/execution/handlers.py`
- `src/quantumvitas/execution/recipes.py`

### Locking (As Implemented)

**Two-Lock Model** (per Constitution §4):
- `edit.lock`: Short duration, YAML writes only (via `save_yaml_doc()`)
- `run.lock`: Long duration, from materialization through execution completion

**Non-Reentrant**:
- Calling `save_yaml_doc()` while holding `edit.lock` → deadlock (portalocker non-reentrant)

**Evidence pointers:**
- `src/quantumvitas/core/locking.py` (lock implementation)
- Constitution §4
- Gate: `tests/gates/test_lock_ordering.py`

### Incremental Run Manifest

**Manifest System** (`src/quantumvitas/calculation/manifest.py`):
- Runtime bookkeeping (non-SSOT, deletable)
- Location: `calculations/<calc_ulid>/.run_tmp_info/manifest.json`
- Schema version: `MANIFEST_SCHEMA_VERSION = 1`

**Skip Decisions** (per Constitution §5.2):
- Uses only: `(kind/step_type, pseudo_set_sha, structure_sha, step_sha, done==true)`
- Output hashes are **never** used

**ManifestStepEntry Fields**:
- `kind`, `step_ulid`, `pseudo_set_sha`, `structure_sha`, `step_sha`
- `effective_structure_sha` (for relax-aware skip logic)
- `run_ulid`, `done`, `started_at`, `done_at`

**Evidence pointers:**
- `src/quantumvitas/calculation/manifest.py` (manifest implementation)
- Constitution §5

### Input Materialization

**Materialization Flow**:
1. Recipe materializes step parameters → JobGraph
2. Input files written to `raw/` via clean rewrite
3. Run reads from `raw/` only

**Raw/Outdir Conventions**:
- Default I/O directory: `raw/` (configurable via `calculation.working_dir`)
- QE: `outdir/.save` (wavefunctions, etc.) — **scanning banned** (Constitution §2.3)
- Output filenames: Fixed at `{step_type}.out/.err` (not derived from input filenames)

**Evidence pointers:**
- `src/quantumvitas/execution/recipes.py` (materialization)
- `src/quantumvitas/calculation/runner.py` (`compute_io_dir_from_calculation_model()`)
- Constitution §2.2, §2.3, §16.2

---

## 8. Scan / ParamSpace / Presets

### Parameter Scan (As Implemented)

**ScanRef Syntax** (per Constitution §10.2):
- Leaf is scalar token string only: `"@scan:<scan_id>"`
- Old `{scan_ref: ...}` format is **forbidden**

**parameter_scan Structure** (per Constitution §10.3):
- `step.yaml` top-level: `parameter_scan.<scan_id>.values:[...]`
- Values are explicit enumerations only
- `linspace/logspace` are UI-only tools, never persisted

**Scan Scope & Ordering** (per Constitution §10.4):
- Scan expansion occurs within a single job
- Scans do not span jobs
- Variant ordering: later-step / faster-changing dimensions go in inner loop

**Evidence pointers:**
- `src/quantumvitas/execution/scan_expansion.py` (scan expansion)
- `src/quantumvitas/calculation/scan_tokens.py` (ScanRef parsing)
- Constitution §10

### ParamSpace System

**ParamSpace Compilation Flow** (per Constitution §8.2):
- ParamSpace compiles preset profiles into IR patches
- Written to `step.yaml` (SSOT)

**Reverse Detection** (per Constitution §8.3):
- Preset inferred only through "exact persistent pattern matching"
- No match → `custom`

**Core ParamSpace Constraints** (per Constitution §8.4):
- **Single-writer principle**: Each YAML key can only be written/deleted by one ParamSpace
- **Three-state Cell**: `VALUE(v)` / `NOT_APPLICABLE` / `WILDCARD`
- **Compiler/Detector equivalence**: `detect(compile_one(step_type, options))` must equal original options value
- **No guessing**: Missing key parameters → Detector returns `CUSTOM`

**Evidence pointers:**
- `src/quantumvitas/presets/compiler.py` (compiler)
- `src/quantumvitas/presets/detector.py` (detector)
- `docs/governance/PARAMSPACE_SPEC.md`

### Preset System

**Preset/Workflow/IR Non-Persistence** (per Constitution §8.1):
- Preset/Workflow/IR **are not persisted**
- Only runtime interpretation of current step DAG
- Forward generation / reverse interpretation of step parameter sets

**Preset Catalog**:
- Located in: `src/quantumvitas/presets/variants_registry.py`
- Presets: precision, space_variant, etc.

**Evidence pointers:**
- `src/quantumvitas/presets/` (preset system)
- Constitution §8

### Owned Keys vs Engine Keys Boundary

**A-class / B-class Key Classification** (per Constitution §12):
- **A-class**: Keys owned/mapped by Preset/IR/ParamSpace (strict typing + canonicalization)
- **B-class**: Free engine keys (no type enforcement, any string allowed)

**A-class Key Set SSOT**:
- Sourced from ParamSpace/IR registry export, **NOT** from `qeparameters.json`

**Evidence pointers:**
- Constitution §12
- `src/quantumvitas/presets/` (ParamSpace registry)

---

## 9. GUI Status

### GUI Implementation

**GUI Technology Stack**:
- Electron + TypeScript + React
- Location: `gui/` directory
- Main process: `gui/electron/main.ts`
- Renderer: `gui/src/` (React components)

**Evidence pointers:**
- `gui/package.json` (dependencies)
- `gui/src/App.tsx` (main React app)

### Multi-Engine Support

**Engine Family Support**:
- GUI supports all 16 engines via `engine_family` field
- Demo gallery shows demos by engine family
- Step parameter panels adapt to engine metadata

**Evidence pointers:**
- `gui/src/components/panels/DemoGalleryPanel.tsx`
- `gui/src/components/panels/StepDetailPanel.tsx`
- `gui/src/types/qv.ts` (TypeScript types)

### Demo Loading

**Demo Gallery**:
- Lists demos from `resources/demo_projects/`
- Calls `list_demo_projects()` RPC endpoint
- `create_demo_project()` RPC creates project from demo snapshot

**Evidence pointers:**
- `gui/src/components/panels/DemoGalleryPanel.tsx`
- `src/quantumvitas/api/service.py` (`list_demo_projects()`, `create_demo_project()`)

### Run Triggers

**Run Calculation**:
- GUI triggers runs via `run_calculation()` RPC endpoint
- Job status tracked via `get_job_status()` RPC
- Job manager: `src/quantumvitas/daemon/jobs.py`

**Evidence pointers:**
- `src/quantumvitas/daemon/server.py` (RPC endpoints)
- `gui/src/hooks/useJobs.ts` (job status hooks)

### Digest Display

**Analysis Display**:
- Analysis panels: `CalculationAnalysisPanel.tsx`, `AnalysisVizPanel.tsx`
- RPC endpoints: `get_analysis_snapshot()`, `list_analysis_snapshots()`
- Supports: SCF energy, DOS, bands, trajectory, field3d, convergence

**Evidence pointers:**
- `gui/src/components/panels/CalculationAnalysisPanel.tsx`
- `src/quantumvitas/api/service.py` (analysis endpoints)

### Backend Contracts (RPC Endpoints)

**JSON-RPC Daemon** (`src/quantumvitas/daemon/server.py`):
- Reads JSON requests from stdin (one per line)
- Writes JSON responses to stdout (one per line)
- Calls `QVService` for all operations (never CLI directly)

**RPC Method Count**: 100+ methods (project, calculation, step, structure, analysis, settings, etc.)

**Evidence pointers:**
- `src/quantumvitas/daemon/server.py` (6455 lines, RPC handler)
- `gui/src/hooks/useQVClient.ts` (RPC client wrapper)

### GUI Field Usage

**New vs Legacy Fields**:
- GUI uses ULID fields: `project_ulid`, `calc_ulid`, `step_ulid`, `run_ulid`
- Legacy fields (`id`, `calc_id`, `step_id`) are **banned** (gate: `test_no_legacy_identity_fields.py`)
- Step types: GUI carries both `step_type_gen` and `step_type_spec` in DTOs

**Evidence pointers:**
- `gui/src/types/qv.ts` (TypeScript DTOs)
- Gate: `tests/gates/test_no_legacy_identity_fields.py`
- Gate: `tests/gates/test_gen_spec_convergence_gate.py` (DTOs must carry both step type fields)

---

## 10. CLI/Daemon/API/Kernel Layering Status

### Three-Layer Model (As Implemented)

**Layer Boundaries** (per Constitution §18.1, `API_CONSTITUTION.md` H1):

| Layer | Package | Import Rules |
|-------|---------|-------------|
| **Frontend** | `daemon`, `cli`, `gui` | May only import from `quantumvitas.api` |
| **API Facade** | `quantumvitas.api` | DTOs + Errors + Utils + Service |
| **Core/Runtime** | All other packages | Frontend MUST NOT import directly |

**Evidence pointers:**
- `docs/governance/API_CONSTITUTION.md` H1
- Gate: `tests/gates/test_import_gate.py`, `test_daemon_kernel_ban.py`

### API Facade

**QVService** (`src/quantumvitas/api/service.py`):
- Single service class with static methods
- 100+ capability methods (project, calculation, step, structure, analysis, settings)
- DTOs in `src/quantumvitas/api/types/`

**Utils Policy** (per `API_CONSTITUTION.md` H2):
- Default: NO reexports in utils
- Exception: Transparent pass-through proxy with docstring justification
- Examples: `is_ulid_like()`, `validate_ulid()`

**Evidence pointers:**
- `src/quantumvitas/api/service.py` (7258 lines)
- `src/quantumvitas/api/utils.py` (utils with justifications)
- Gate: `tests/gates/test_no_service_delegating_utils.py`

### CLI Implementation

**Typer CLI** (`src/quantumvitas/cli/main.py`):
- Entry point: `qv` command (via `pyproject.toml` entry_points)
- Commands: `init`, `run`, `configure`, `analyze`, `import-structure`, etc.
- Calls `QVService` (never core/runtime directly)

**Evidence pointers:**
- `src/quantumvitas/cli/main.py`
- `pyproject.toml` (`[project.scripts] qv = "quantumvitas.cli:app"`)

### Daemon Implementation

**JSON-RPC Daemon** (`src/quantumvitas/daemon/server.py`):
- stdio-based JSON-RPC interface for GUI
- Reads JSON requests from stdin, writes to stdout
- Calls `QVService` for all operations
- Uses `JobManager` for long-running operations

**Evidence pointers:**
- `src/quantumvitas/daemon/server.py` (6455 lines)
- `src/quantumvitas/daemon/jobs.py` (JobManager)

### Kernel Layering

**Kernel → API Ban** (per Constitution §19.1):
- Kernel MUST NOT reverse-import the API facade
- Gate: `tests/gates/test_kernel_no_api_import.py`

**Seven-Domain Model** (per `KERNEL_DEPENDENCY_SPEC.md`):
- Kernel organized into 7 domains: ssot, resources, models, runtime, engines, analysis, workflow
- Each domain has explicit responsibility boundaries and import bans

**Evidence pointers:**
- `docs/governance/KERNEL_DEPENDENCY_SPEC.md`
- Gate: `tests/gates/test_kernel_no_api_import.py`, `test_engine_no_ssot_import.py`

### Filesystem Access Control (Law H9)

**Frontend No YAML Write** (per Constitution §18.4):
- Only kernel is allowed to modify SSOT filesystem
- Frontend MUST NOT directly write YAML / create project structures / modify calculation/step/structure files
- Gate: `tests/gates/test_frontend_no_yaml_write.py`

**Evidence pointers:**
- Constitution §18.4
- `docs/governance/API_CONSTITUTION.md` H9
- Gate: `tests/gates/test_frontend_no_yaml_write.py`

---

## 11. Tests and Gates Inventory

### Test Organization

**Test Suites**:
- `tests/unit/`: Unit tests (161 files)
- `tests/integration/`: Integration tests (70 files, require engine binaries)
- `tests/cli/`: CLI tests
- `tests/daemon/`: Daemon/RPC tests (17 files)
- `tests/drivers/`: Driver-specific tests
- `tests/gates/`: Constitutional gate tests (59 files)

**Test Markers** (per `pytest.ini`):
- `@pytest.mark.unit`: Parser/project tests (no QE binaries)
- `@pytest.mark.qe_core`: QE integration via `run_and_verify_step/calculation` runner
- `@pytest.mark.qe_cli`: QE integration driven through Typer CLI

**Evidence pointers:**
- `tests/` directory structure
- `pytest.ini` (test markers)
- `README.md` (testing overview)

### Key Gates (Constitutional Enforcement)

**SSOT Gates**:
- `test_yaml_write_single_entry.py`: Enforces single entry point for YAML writes
- `test_yaml_read_single_entry.py`: Enforces single entry point for YAML reads

**Identity Gates**:
- `test_no_legacy_identity_fields.py`: Bans legacy `id`, `calc_id`, `step_id` fields

**Step Type Gates**:
- `test_step_type_constitution.py`: GEN/SPEC derivation rule
- `test_no_bare_step_type.py`: Bans bare `step_type` field
- `test_underscore_ban.py`: Enforces underscore ban
- `test_no_manual_join_split.py`: Bans manual split/join
- `test_banned_legacy_aliases.py`: Bans legacy step type aliases
- `test_no_third_namespace.py`: Enforces two-namespace rule

**API Layering Gates**:
- `test_import_gate.py`: Enforces 3-layer import boundary
- `test_daemon_kernel_ban.py`: Bans daemon → kernel imports
- `test_frontend_no_yaml_write.py`: Enforces Law H9 (frontend no YAML write)
- `test_kernel_no_api_import.py`: Bans kernel → API reverse imports

**Provenance Gates**:
- `test_provenance_independence.py`: Law P1 (history world must not participate in runtime logic)
- `test_provenance_opctx_required.py`: Law P2 (OperationContext required)
- `test_provenance_skip_isolation.py`: Law P3 (skip/rerun must not consult provenance)
- `test_cas_integrity.py`: Law P5 (CAS integrity)
- `test_lock_ordering.py`: Law P6 (lock ordering)
- `test_provenance_failure_graceful.py`: Law P7 (graceful degradation)
- `test_no_duplicate_scanners.py`: Law P9 (single artifact scanner)

**Engine Gates**:
- `test_registry_routing.py`: Enforces explicit registry lookup (no guessing)
- `test_no_fallbacks.py`: Bans fallback patterns
- `test_engine_no_ssot_import.py`: Bans engine → SSOT imports

**Evidence pointers:**
- `tests/gates/` directory (59 test files)
- `docs/governance/README.md` (cross-reference: Invariants → Gates)

### How to Run Tests

**Quick Tests** (no QE required):
```bash
pytest tests/unit
pytest -m "not qe_core and not qe_cli"
pytest -m quick
```

**QE Integration Tests** (requires QE installation):
```bash
pytest tests/integration
pytest -m qe_core
pytest -m qe_cli
```

**Gate Tests**:
```bash
pytest tests/gates/
```

**Evidence pointers:**
- `README.md` (testing overview)
- `pytest.ini` (test configuration)

---

## 12. Demo Store Status

### Demo Location

**Demo Projects Directory**:
- Location: `resources/demo_projects/`
- Format: YAML snapshot files (`.yml`)
- Count: 21 demo files (as of scan)

**Demo Files** (partial list):
- `si_bands_demo.yml`, `si_dos_demo.yml` (main QE demos)
- `si_bands_vasp_demo.yml` (VASP demo)
- `water_orca_scf.yml`, `methane_orca_freq.yml`, `formaldehyde_orca_tddft.yml` (ORCA demos)
- `water_pyscf_scf.yml` (PySCF demo)
- `silicon_wannier90_demo.yml`, `copper_wannier90_demo.yml`, `diamond_wannier90_demo.yml` (Wannier90 demos)
- `00_Si_scf.yml`, `04_Si_DOS.yml`, `07_Si_bandStructure.yml`, etc. (tutorial demos)

**Evidence pointers:**
- `resources/demo_projects/` directory listing
- `find resources/demo_projects -name "*.yml" | wc -l` → 21

### Demo Integrity Requirements

**Demo Integrity Gate** (`tests/gates/test_demo_integrity.py`):
- Law EF6: Every demo calculation must have explicit `engine_family`
- Every step's `step_type_spec` prefix must match `engine_family` or companion engines

**Evidence pointers:**
- `tests/gates/test_demo_integrity.py`
- `docs/architecture/GUI_ENGINE_FAMILY_DEMO_SPEC.md` (Law EF6)

### Demo Generation Tooling

**Demo Generator Scripts**:
- `tools/generate_demo_snapshots.py`: Generates main demos (si_bands, si_dos)
- `tools/regenerate_si_bands_demo.py`: Regenerates si_bands_demo.yml only
- `tools/import_tutorial_datasets.py`: Generates demos from `tests/data/` (0_* to 19_*)
- `tools/demo_generators/verified/generate_qe_demos.py`: Verified QE demo generator
- `tools/demo_generators/verified/generate_orca_demos.py`: Verified ORCA demo generator

**Demo Generation Flow**:
1. Export existing project via `export_project_to_snapshot()` (`src/quantumvitas/project/snapshot.py`)
2. Extract reference artifacts (SCF, DOS, bands JSON files)
3. Add demo metadata (title, subtitle, tags, recommended_analysis, difficulty)
4. Write to `resources/demo_projects/<demo_id>.yml`

**Evidence pointers:**
- `tools/generate_demo_snapshots.py`
- `docs/DEMO_GENERATION.md`
- `src/quantumvitas/project/snapshot.py` (`export_project_to_snapshot()`)

### Demo Loading (API)

**Demo API Methods**:
- `QVService.list_demo_projects()`: Lists available demos
- `QVService.create_demo_project()`: Creates project from demo snapshot

**Evidence pointers:**
- `src/quantumvitas/api/service.py` (`list_demo_projects()`, `create_demo_project()`)

---

## 13. Known Limitations Explicitly Documented

### Limitations Found in Docs/Code

**1. Legacy Engine Layer**:
- `src/quantumvitas/engine/` directory exists (legacy layer)
- GPAW has both legacy (`engine/gpaw_engine.py`) and new (`drivers/gpaw/`) implementations
- Status: Being phased out (per architecture docs)

**Evidence**: `src/quantumvitas/engine/` directory, `docs/architecture/KERNEL_REVIEW_REPORT.md`

**2. Provenance System Status**:
- `PROVENANCE_VERSIONED_HISTORY_SPEC.md` is PROPOSED (v1.1), not FINAL
- Implementation exists in codebase but spec is still under review

**Evidence**: `docs/governance/PROVENANCE_VERSIONED_HISTORY_SPEC.md` (Status: PROPOSED v1.1)

**3. Kernel Dependency Spec Status**:
- `KERNEL_DEPENDENCY_SPEC.md` is PROPOSED (v3.1), not FINAL
- Some exceptions documented in `KERNEL_EXCEPTIONS.md`

**Evidence**: `docs/governance/KERNEL_DEPENDENCY_SPEC.md` (Status: PROPOSED v3.1), `KERNEL_EXCEPTIONS.md`

**4. QE Parameter Metadata**:
- QE parameter helper (`qv params`) backed by generated metadata in `src/quantumvitas/data/qe_module_parameters.json`
- Regeneration tool (`tools/extract_qe_parameters_v1.py`) is deprecated
- Note in README: "NOTE: The v1 extractor is deprecated. Use v2 tooling when available."

**Evidence**: `README.md` (QE parameter helper section), `tools/extract_qe_parameters_v1.py`

**5. Demo Reference Artifacts**:
- Reference artifacts (energies, band structures, DOS) stored as engine-specific JSON files
- Long-term direction: engine-agnostic canonical primitives (AnalysisObject → Primitives system)
- Exact artifact schema not locked by spec

**Evidence**: `docs/architecture/GUI_ENGINE_FAMILY_DEMO_SPEC.md` §7.2

**6. Test Warnings Investigation**:
- Documented test warnings investigation in `docs/dev/TEST_WARNINGS_INVESTIGATION.md`
- Some test warnings may be expected/acceptable

**Evidence**: `docs/dev/TEST_WARNINGS_INVESTIGATION.md`

**7. Extended Tests Location**:
- Extended tests live under `extended-tests/` (separate from main `tests/` suite)
- Not included in quick test runs

**Evidence**: `README.md` (extended tests section)

**8. GUI E2E Test Refactor**:
- GUI E2E tests documented in `gui/tests/GUI_E2E_REFACTOR.md`
- Some E2E tests may be in transition

**Evidence**: `gui/tests/GUI_E2E_REFACTOR.md`

**9. Contract Crawler System**:
- Contract crawler system in `tests/contract_crawler/` for GUI RPC contract testing
- Golden contract comparison system exists
- Status: Active testing tool, not a limitation per se, but documented complexity

**Evidence**: `tests/contract_crawler/README.md`, `tests/contract_crawler/WORKLOG.md`

**10. Chinese Constitution Deprecated**:
- `CONSTITUTION_ZH.md` exists but is **DEPRECATED** (non-authoritative)
- English `CONSTITUTION.md` is now authoritative

**Evidence**: `CONSTITUTION.md` (Revision Summary v2.1), `docs/governance/README.md`

---

## Evidence Pointers Summary

### Key Files Reviewed

**Constitution & Governance**:
- `CONSTITUTION.md` (v2.1)
- `docs/governance/README.md`
- All governance spec files in `docs/governance/`

**Core Implementation**:
- `src/quantumvitas/core/yaml_io.py` (SSOT I/O)
- `src/quantumvitas/core/driver_registry.py` (engine registry)
- `src/quantumvitas/workflow/step_type_convert.py` (step type conversion)
- `src/quantumvitas/workflow/gen_steps.py` (GEN step registry)
- `src/quantumvitas/provenance/` (provenance system)
- `src/quantumvitas/calculation/manifest.py` (manifest system)
- `src/quantumvitas/calculation/runner.py` (runner)

**Engines**:
- All `src/quantumvitas/drivers/*/driver.py` files (16 engines)

**API/Frontend**:
- `src/quantumvitas/api/service.py` (QVService)
- `src/quantumvitas/daemon/server.py` (RPC daemon)
- `src/quantumvitas/cli/main.py` (CLI)
- `gui/src/types/qv.ts` (TypeScript DTOs)

**Tests**:
- `tests/gates/` (59 gate test files)
- `tests/gates/test_demo_integrity.py` (demo integrity)

**Demos**:
- `resources/demo_projects/` (21 demo files)
- `tools/demo_generators/` (demo generation scripts)

---

**End of Report**

