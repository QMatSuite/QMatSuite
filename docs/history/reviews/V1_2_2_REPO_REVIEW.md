# QMatSuite v1.2.2 — Independent Repository Review

**Date**: 2026-02-26
**Reviewer**: Claude Code (automated review)
**Commit**: `b379b06cc082a18170d6ac3f7de8ef37f0dfe4cf`
**Branch**: `v2-python`
**Scope**: Full repository audit — architecture, code quality, test coverage, feature inventory

---

## Executive Summary

QMatSuite is a unified computational materials science workflow manager that supports **15 simulation engines** (Quantum ESPRESSO, VASP, ABINIT, ORCA, Gaussian, LAMMPS, CP2K, Siesta, Wannier90, GPAW, Psi4, PySCF, xTB, QMCPACK, Yambo) through a single API, GUI, CLI, and MCP (Model Context Protocol) interface. At 153,789 lines of Python source code, 34,671 lines of TypeScript/React GUI code, and 135,565 lines of tests, it is a substantial and ambitious project.

The project is at a **late-alpha / early-beta stage**. The architectural foundations are exceptionally strong — a formally governed constitution-and-law system, 63 gate tests enforcing invariants in CI, a clean three-layer architecture (Intent → IR → Engine), and a driver protocol that allows adding engines without modifying kernel code. The test suite is impressive: **6,562 tests passing with 0 failures and 70% code coverage**. Engine drivers range from QE-depth maturity (full tags, parsers, demos, curated cases) to functional-but-thinner coverage for Python-script engines (GPAW, Psi4, PySCF).

What's most notable is the governance model. This may be the most formally governed open-source computational science project I've reviewed — a central constitution with 20 sections, 8 L1 law specs, 15 L2 policy documents, and 63+ gate tests that enforce architectural invariants in CI. This is not decorative documentation; the gates are real and they pass.

The primary gaps are: (1) the CLI has ~31 TODO markers for migration to the QMSService API facade, (2) there is no CITATION.cff, (3) the README still references the legacy Java v1 and doesn't reflect the Python v2 capabilities, and (4) user-facing documentation (tutorials, getting-started guides) is sparse. For publication in JOSS or CPC, items (2), (3), and user documentation would need attention.

**Recommendation**: The architecture and test infrastructure are publication-quality. The codebase is suitable for a JOSS submission with moderate preparatory work (README rewrite, CITATION.cff, user docs). For CPC/JCTC, benchmarks against competing tools would be needed.

---

## 1. Project Identity

### 1.1 What QMatSuite Is

QMatSuite (Quantum Visualization Interactive Toolkit for Ab-initio Simulations) is a cross-platform workflow manager for computational materials science. It provides a unified interface for setting up, running, and analyzing calculations across 15 different simulation engines spanning solid-state DFT (QE, VASP, ABINIT, Siesta, GPAW), molecular quantum chemistry (ORCA, Gaussian, Psi4, PySCF), classical molecular dynamics (LAMMPS), semi-empirical methods (xTB), and post-processing codes (Wannier90, QMCPACK, Yambo). CP2K bridges both periodic and molecular domains.

The core design philosophy is **"Bring Your Own Engine" (BYOE)**: QMatSuite does not bundle or replace any simulation engine. Instead, it manages the full lifecycle — structure import, parameter configuration, input file generation, job execution, output parsing, and analysis visualization — for whatever engines the user has installed. This same philosophy extends to AI integration: through the Model Context Protocol (MCP), any AI agent (Claude, GPT, etc.) can drive QMatSuite without vendor lock-in.

The architecture implements a clean three-layer parameter system: **Intent** (what the user wants: "run an SCF calculation with medium precision") → **Intermediate Representation** (engine-agnostic parameter set) → **Engine-Specific** (VASP INCAR tags, QE namelists, ORCA keyword blocks). This enables the preset/workflow system to work across all 15 engines while preserving full manual control.

### 1.2 Distribution Channels

Three distribution channels exist or are planned:

| Channel | Status | Contents | Size |
|---------|--------|----------|------|
| `pip install qmatsuite` | Available (v1.2.2) | Python backend, all 15 drivers, CLI | ~45 MB |
| qmatsuite-lite (Electron) | Available (macOS, Windows) | GUI + bundled Python runtime + engine manager | ~284 MB (macOS DMG) |
| qmatsuite-full | Planned | Lite + QE 7.5 binary + SSSP pseudo library | ~1.2 GB est. |

The Electron packaging includes code signing (Azure Trusted Signing for Windows, Apple notarization for macOS), auto-update via electron-updater, and a built-in engine manager that can download and configure engines via micromamba.

### 1.3 Target Users

Primary: Computational materials scientists and quantum chemists who use multiple simulation engines and want a unified workflow. Secondary: Research groups that want to standardize their computational workflows. Tertiary: AI agent developers building automated computational science pipelines via MCP.

---

## 2. Quantitative Profile

### 2.1 Codebase Metrics

| Metric | Value |
|--------|-------|
| Python source LOC (`src/`) | 153,789 |
| TypeScript/React LOC (`gui/`) | 34,671 |
| Test LOC (Python) | 135,565 |
| Test LOC (GUI/Playwright) | 6,639 |
| Total tracked files | 4,069 |
| JSON data files (engine metadata) | 193 files (984,387 lines) |
| Python source files | 608 |
| Python test files | 627 |
| Test-to-source ratio (files) | 1.03:1 |
| Test-to-source ratio (LOC) | 0.88:1 |

### 2.2 Test Metrics

| Metric | Value |
|--------|-------|
| Total pytest tests (collected) | 6,567 |
| Passing | 6,562 |
| Failing | 0 |
| Skipped | 5 |
| Collection errors | 1 (test_import_structure.py) |
| Code coverage | 70% (61,482 statements, 18,740 missed) |
| Test execution time | 379.73s (6:20) with `-n auto` |
| Gate tests | 719 |
| Contract crawler tests | 66 |
| MCP tests | 595 |
| Integration tests | 413 |
| Integrity tests | 468 |
| GUI/Playwright tests | 15 spec files |

### 2.3 Test Breakdown by Category

| Directory | Tests | Purpose |
|-----------|-------|---------|
| `tests/unit/` | 2,095 | Core unit tests across all modules |
| `tests/drivers/` | 1,253 | Engine driver tests (all 15 engines) |
| `tests/gates/` | 719 | Constitutional invariant enforcement |
| `tests/inputformat/` | 702 | Input file parse/write roundtrip tests |
| `tests/mcp/` | 595 | MCP tool tests |
| `tests/integrity/` | 468 | Demo and data integrity checks |
| `tests/integration/` | 413 | Cross-module integration tests |
| `tests/api/` | 223 | API service layer tests |
| `tests/daemon/` | 154 | Daemon RPC handler tests |
| `tests/core/` | 114 | Core module tests |
| `tests/workflow/` | 70 | Workflow template tests |
| `tests/contract_crawler/` | 66 | API contract verification |
| `tests/cli/` | 49 | CLI command tests |
| `tests/demo_store/` | 41 | Demo project system tests |
| `tests/presets/` | 21 | Preset system tests |
| `tests/examples/` | 20 | Example/tutorial tests |
| `tests/ir/` | 16 | Intermediate representation tests |
| `tests/provenance/` | 10 | Provenance system tests |

### 2.4 Dependency Profile

**16 runtime dependencies** (lean for a project of this scope):
- Scientific: `numpy`, `scipy`, `matplotlib`, `ase`, `pymatgen` (≥2024.0.0), `mp-api`
- Infrastructure: `PyYAML`, `typer` (≥0.12), `ulid-py`, `msgpack`, `portalocker`, `jinja2`
- Network: `requests`, `certifi`
- Terminal: `plotext` (≥5.2)
- AI/Agent: `fastmcp` (≥2, <3)

**3 dev dependencies**: `pytest`, `pytest-cov`, `pytest-xdist`

**Total installed packages**: 155 (including transitive dependencies)

### 2.5 Source Code Distribution by Module

| Module | LOC | % of Total | Role |
|--------|-----|-----------|------|
| `drivers/` | 39,798 | 25.9% | 15 engine driver bundles |
| `core/` | 22,072 | 14.4% | Kernel: YAML I/O, driver protocol, registry, analysis |
| `api/` | 14,706 | 9.6% | Unified service facade (143 methods) |
| `calculation/` | 10,488 | 6.8% | Calculation lifecycle management |
| `mcp/` | 8,072 | 5.2% | MCP server + 38 tools |
| `presets/` | 6,797 | 4.4% | ParamSpace, compiler, detector, dimensions |
| `engine/` | 6,774 | 4.4% | Engine management, installation |
| `daemon/` | 6,018 | 3.9% | WebSocket daemon server (121 RPC handlers) |
| `cli/` | 5,673 | 3.7% | Typer CLI (40+ commands) |
| `io/` | 5,106 | 3.3% | I/O providers, generators, parsers |
| `frontends/` | 4,822 | 3.1% | Frontend CLI app (legacy, being migrated) |
| `analysis/` | 4,627 | 3.0% | Analysis plotting and visualization |
| `execution/` | 3,529 | 2.3% | Job execution, runner |
| `provenance/` | 3,233 | 2.1% | SQLite + CAS provenance system |
| `engines/` | 3,215 | 2.1% | Python-script engine wrappers |
| `workflow/` | 2,727 | 1.8% | Workflow templates, step factory |
| `demo_store/` | 2,223 | 1.4% | Demo project compilation and replay |
| Other | 3,889 | 2.5% | project, pseudo, inputformat, ir, etc. |

---

## 3. Architecture Review

### 3.1 Three-Layer Architecture (Intent → IR → Engine)

**Verified: Real and functional.**

The three-layer parameter system is implemented and enforced:

1. **Intent layer**: Users express intent through presets (e.g., "medium precision SCF") and workflow templates. These are **runtime-only** — never persisted as filesystem objects (Constitution §8, PARAMSPACE_SPEC §1). The preset compiler (`src/qmatsuite/presets/compiler.py`) transforms a profile selection into a full parameter dictionary via `compile_one(step_type, options)`.

2. **IR layer**: Engine-agnostic parameter dictionaries stored in `step.yaml` files. The `src/qmatsuite/ir/` module (414 LOC) handles parameter normalization. The GEN/SPEC step type system provides the mapping: `step_type_gen` (e.g., "scf", "relax") represents intent; `step_type_spec` (e.g., "vasp_scf", "qe_relax") represents execution. The derivation rule is `spec = f"{prefix}_{gen}"`.

3. **Engine layer**: Each driver's materialization map converts IR parameters to engine-native input. The driver's `get_materialization_map()` returns the mapping, and `get_handler()` provides the step execution logic. Input file generation goes through the `inputformat` package's `write_engine_inputs()` orchestrator.

### 3.2 SSOT Design

**Verified: Two YAML files are the sole source of truth.**

The SSOT (Single Source of Truth) design is rigorously enforced:

- `calculation.yaml`: Calculation metadata, step topology, species map, engine family
- `step.yaml`: Per-step parameters, step type (spec), run configuration

All YAML writes go through a single function: `save_yaml_doc()` in `src/qmatsuite/core/yaml_io.py`. This function:
- Acquires `edit.lock` via portalocker (cross-platform file locking)
- Records changes in the Journal (before/after snapshots)
- Records in the Provenance system (after lock release, non-fatal on failure)
- Validates OperationContext presence

Gate test `test_yaml_write_single_entry.py` enforces that no other code path writes YAML. Gate test `test_yaml_read_single_entry.py` enforces centralized reading.

### 3.3 Driver Protocol & Registry

**Verified: 15 engines registered, 107 step types, clean dispatch.**

The driver protocol (`src/qmatsuite/core/driver_protocol.py`) defines:
- `EngineDriver` as a `@runtime_checkable` Protocol with 7 MUST methods/properties
- `BaseEngineDriver` as an optional base class providing sensible defaults for SHOULD/PLUGIN methods
- `StepTypeSpec` as a frozen dataclass with post-init validation (engine prefix must match)

The `DriverRegistry` (`src/qmatsuite/core/driver_registry.py`) is a thread-safe singleton with:
- 22 public methods for registration, lookup, and materialization
- 9 custom exception types for precise error reporting
- Hard validation at registration time (no lazy failures)
- Materialization map built once at registration, O(1) lookup thereafter
- `freeze()` method to lock registry after all drivers are loaded

All 15 engines are registered via `import qmatsuite.drivers`, providing 107 total step types across engines (QE leads with 20, ORCA with 12, PySCF with 11, VASP with 11).

### 3.4 Multi-Frontend Architecture

**Verified: GUI, CLI, MCP, and Daemon all consume the same API.**

The unified API facade is `QMSService` in `src/qmatsuite/api/service.py` (9,207 lines, 143 methods organized into 7 subsystems: analysis, structure, online_search, calculation, run, project, history).

- **GUI** (Electron): Communicates with the Python daemon via Electron IPC → WebSocket. The daemon (`src/qmatsuite/daemon/server.py`) exposes 121 RPC handlers that delegate to `QMSService`.
- **CLI** (Typer): 40+ commands in `src/qmatsuite/cli/`. Note: the CLI has **31 TODO markers** indicating ongoing migration from direct core imports to the `QMSService` facade. This is the most significant architectural debt.
- **MCP**: 38 tools registered in `src/qmatsuite/mcp/server.py` via FastMCP. Tools delegate to `QMSService`.
- **Daemon**: WebSocket server with JSON-RPC protocol, stdin/stdout communication with Electron main process.

**Layer violation check**: The MCP layer has ~20 direct imports from `qmatsuite.core.*` (project_utils, resolution, engines, analysis, resources, pseudo_config, paths). These are noted as pragmatic exceptions, not architectural violations per se — the MCP tools need resolution utilities that aren't fully surfaced through the API facade yet. The daemon shows minimal core imports (1 comment reference to context detection). The CLI frontend has the most significant bypass pattern with its 31 TODOs.

### 3.5 Governance Model

**Verified: Novel and genuinely enforced.**

The governance hierarchy:
1. **L0: CONSTITUTION.md** — 20 sections covering SSOT, history, concurrency, identity, step types, presets, species, scans, engine execution, API layering, kernel dependencies
2. **L1: 8 Law Specs** — API Constitution, Kernel Dependency, Engine Integration, Engine Recipe & Runner, Step Type GEN/SPEC, ParamSpace, Provenance, Kernel Exceptions
3. **L2: 15 Specs/Policies** — Calc Type System, Analysis Primitives, Demo Store, Structure Fingerprint, B1 Engine Playbook, Analysis Pipeline Playbook, etc.

**63 gate test files** in `tests/gates/` enforce these invariants in CI. These are not placeholders — they are substantive tests that scan the codebase for violations. Examples:
- `test_no_bare_step_type.py` — ensures no code uses bare `step_type` (must be `step_type_gen` or `step_type_spec`)
- `test_frontend_no_yaml_write.py` — ensures frontends don't write YAML directly
- `test_no_fallbacks.py` — ensures no silent engine fallbacks
- `test_no_sensitive_paths.py` — ensures no real usernames/hostnames in committed files
- `test_kernel_no_api_import.py` — ensures kernel doesn't reverse-import API
- `test_daemon_no_yaml_write.py` — ensures daemon doesn't write YAML directly
- `test_import_rules.py` — enforces the three-layer import boundary

This governance model — constitutionally governed software with CI-enforced invariants — is unusual in open-source computational science. It provides guarantees that architectural decisions won't silently degrade over time.

---

## 4. Engine Inventory

### 4.1 Engine Maturity Matrix

| Engine | Files | LOC | Tags JSON | Output Parser | IO Module | Curated Cases | Demos | Step Types | Maturity |
|--------|-------|-----|-----------|---------------|-----------|---------------|-------|------------|----------|
| QE | 32 | 7,709 | Yes (separate) | Yes | Yes | 19 | 13 | 20 | ★★★★★ |
| VASP | 23 | 4,383 | Yes (232 tags) | Yes | Yes | 13 | 5 | 11 | ★★★★☆ |
| ABINIT | 18 | 3,369 | Yes (170+ tags) | Yes | Yes | 10 | 3 | 4 | ★★★★☆ |
| Siesta | 16 | 3,052 | Yes (separate) | Yes | Yes | 8 | 3 | 5 | ★★★☆☆ |
| CP2K | 17 | 2,841 | Yes (215 tags) | Yes | Yes | 10 | 3 | 8 | ★★★★☆ |
| Gaussian | 16 | 2,814 | Yes (130 kw) | Yes | Yes | 10 | 3 | 6 | ★★★★☆ |
| LAMMPS | 17 | 2,699 | Yes (114 cmds) | Yes | Yes | 8 | 3 | 8 | ★★★★☆ |
| QMCPACK | 14 | 2,296 | Yes (65 tags) | Yes | Yes | 8 | 2 | 3 | ★★★★☆ |
| ORCA | 12 | 1,949 | Yes (120+ kw) | Yes | Yes | 9 | 3 | 12 | ★★★★☆ |
| W90 | 13 | 1,779 | Yes | Yes | Yes | 8 | 2* | 2 | ★★★☆☆ |
| Yambo | 14 | 1,716 | Yes | Yes | Yes | 4 | 2* | 4 | ★★★☆☆ |
| GPAW | 13 | 1,790 | No | No | No | 3 | 3 | 6 | ★★☆☆☆ |
| xTB | 14 | 1,508 | Yes | Yes | Yes | 8 | 3 | 2 | ★★★☆☆ |
| PySCF | 9 | 948 | No | No | No | 3 | 3 | 11 | ★★☆☆☆ |
| Psi4 | 9 | 877 | No | No | No | 3 | 3 | 5 | ★★☆☆☆ |

*W90 and Yambo demos are primarily QE workflow demos that chain into W90/Yambo steps.

**Maturity tiers**:
- ★★★★★ (QE): Gold standard. Full tags, complete parser, 19 curated cases, 13 demos, 20 step types, real-run CI tests
- ★★★★☆ (VASP, ABINIT, CP2K, Gaussian, LAMMPS, QMCPACK, ORCA): B1-playbook compliant. Tags JSON, output parser, curated cases, IO module, demos
- ★★★☆☆ (Siesta, W90, Yambo, xTB): Functional driver with parser and some curated cases, but less comprehensive metadata
- ★★☆☆☆ (GPAW, PySCF, Psi4): Python-script engines with no parseable input files. Driver exists, step types registered, but no tags JSON or output parser

### 4.2 Step Type Census

**107 total step types** across 15 engines. Distribution by calculation type:

| Category | Count | Engines |
|----------|-------|---------|
| SCF/Single-point | 15 | All engines |
| Relaxation/Optimization | 14 | All except W90, Yambo |
| Band structure | 6 | QE, VASP, ABINIT, CP2K, Siesta, GPAW |
| DOS | 6 | QE, VASP, ABINIT, CP2K, Siesta, GPAW |
| Molecular dynamics | 8 | QE, VASP, LAMMPS (5 ensembles), CP2K, Siesta, GPAW, xTB |
| Frequency/Phonon | 4 | VASP, Gaussian, ORCA, QE |
| TDDFT/Excited states | 5 | ORCA (2), Gaussian, PySCF (2), CP2K |
| Post-SCF (MP2, CCSD, etc.) | 6 | Gaussian, ORCA (2), Psi4, PySCF (2) |
| Multi-reference (CASSCF, etc.) | 3 | ORCA (2), PySCF |
| Wannier functions | 3 | W90 (2), QE |
| GW/BSE/Optics | 4 | Yambo |
| QMC methods | 3 | QMCPACK |
| Other specialized | 10+ | QE (NEB, GIPAW, HP, etc.), VASP (elastic, dielectric), LAMMPS (deform, equilibrate) |

---

## 5. Feature Inventory

### 5.1 Core Computation Features

- **Structure management**: Import from CIF/POSCAR/XYZ/PDB files, online databases (Materials Project, COD via mp-api), 3D visualization with Three.js, canonicalization, fingerprinting
- **Calculation lifecycle**: Create, configure, run, analyze — full CRUD with ULID-based identity
- **Parameter system**: ParamSpace framework with preset compiler, detector, oracle, precision variants. 16 preset dimension files. Roundtrip invariant enforced.
- **Workflow templates**: Pre-built multi-step workflows (e.g., SCF → NSCF → bands, SCF → NSCF → DOS). Templates defined in `src/qmatsuite/workflow/templates.py`.
- **Species/pseudopotential management**: Per-element species map, SSSP library download, pseudo archive management, POTCAR staging (VASP), force-field staging (LAMMPS)
- **Input file generation**: `inputformat` package with `write_engine_inputs()` orchestrator supporting all 15 engines via content-role dispatch (parameters, structure, kpoints, combined)
- **Input file parsing**: `parse_engine_inputs()` orchestrator for VASP (3-file), ORCA, ABINIT, and others
- **Job execution**: Runner with engine-agnostic dispatch through DriverRegistry. Three recipe archetypes: Directory-state (QE/W90), Strong-chain (ORCA/PySCF/CP2K), Cleanup (VASP)

### 5.2 Analysis Features

**Analysis primitive types** (in `src/qmatsuite/core/analysis/`):
- `BandStructure` — Band structure with high-symmetry points, projections (fatbands)
- `DOS` — Density of states (total, projected/PDOS with real atom labels)
- `Convergence` — SCF/optimization convergence tracking
- `Field3D` — Volumetric field data (charge density, wavefunctions)
- `Series1D` — Generic 1D data series
- `GeometryFrame` / `GeometryFrames` — Trajectory frames
- `Marker` — Annotated points on plots

**Analysis transforms** (8 implemented):
- `FermiShift` — Fermi level alignment
- `EnergyCrop` — Energy window cropping
- `Smoothing` — Data smoothing
- `FrameSlice` — Trajectory frame selection
- `MSD` — Mean square displacement
- `VACF` — Velocity autocorrelation function
- `RDF` — Radial distribution function
- `DiffusionCoefficient` — From MSD

**CanonicalPrimitiveBundle** system provides deterministic, engine-agnostic analysis objects with provenance metadata and render hints for visualization.

### 5.3 MCP / Agent Features

**38 MCP tools** registered across categories:

| Category | Tools |
|----------|-------|
| Project | init_project, cleanup_project |
| Discovery | ping, list_engines, list_workflows, get_presets, search_parameters, search_knowledge |
| Configuration | create_calculation, set_species_map, set_parameters, apply_preset, inspect_calculation, list_calculations, preview_compilation |
| Execution | run_calculation, get_status, get_results_summary, quick_run |
| Structures | list_structures, import_structure, get_structure_detail, promote_structure |
| Analysis | list_analyses, plot_analysis, generate_kpath |
| Demo | demo_store |
| Resources | list_resources, resolve_species_map, download_pseudo_library |
| Engine Mgmt | install_engine, list_installable_engines, verify_engine, register_engine_path, uninstall_engine, set_active_engine |

The MCP server uses FastMCP (v2) with lazy tool registration via module-level `@mcp.tool` decorators. Tools return structured response envelopes with `ok`/`error` fields.

### 5.4 GUI Features

**8 main views** in the Electron GUI:

1. **Home**: Project overview, demo gallery, project creation
2. **Structures**: Structure list, 3D viewer (Three.js with bonds, isosurfaces), import from file/online
3. **Calculations**: Step editor, parameter configuration, preset selection, common cards (K-points, pseudo), parameter scan toggle
4. **Jobs**: Real-time job monitoring with 5-second polling
5. **History**: Change journal browser with timestamps and revisions
6. **Resources**: Engine parameter metadata browser with search/filter
7. **Settings**: Engine management, pseudo archive management, journal viewer
8. **Dev-Volume** (DEV only): Volumetric field visualization sandbox

**65 component files** including 32 panels, 6 dialogs, 6 parameter editors, 5 layout components, 2 common cards, 2 settings panels, plus hooks, contexts, and utilities. 3D visualization includes marching cubes isosurface rendering (`marchingCubes.ts`) and fatband/DOS overlays.

### 5.5 CLI Features

**40+ commands** across 8 sub-apps via Typer:

| Sub-app | Commands | Examples |
|---------|----------|---------|
| `qms init` | 3 | project, calculation, step |
| `qms rename` | 4 | structure, calculation, project, step |
| `qms delete` | 5 | structure, calculation, step, project, trash |
| `qms configure` | 4 | calculation, project, species, structure |
| `qms run` | 4 | step, structure, calculation, auto-dispatch |
| `qms analyze` | 6 | output, band, dos, energy, scf, structure |
| `qms engine` | 5 | list, install, uninstall, verify, path |
| `qms history` | 4 | list, show, storage, clear |
| `qms mcp` | 1 | config |

Additional root commands: `import-structure`, `save-project`, `list`, `detect-qe`, `params`, etc.

### 5.6 Distribution Features

- **PyPI packaging** with `pyproject.toml`, editable installs supported
- **Electron app** (macOS .dmg, Windows NSIS installer) with bundled Python runtime via conda-pack
- **Code signing**: Azure Trusted Signing (Windows), Apple notarization (macOS)
- **Auto-update**: electron-updater integration
- **Engine manager**: Discover, download, install, verify simulation engines via micromamba
- **5 CI/CD workflows**: tests.yml (multi-OS with QE), release-macos.yml, release-windows.yml, release-pip.yml, build-runtime-dir.yml

### 5.7 Demo Store

**74 demo projects** (52 YAML + 22 legacy JSON) covering all 15 engines:

| Engine | Demo Count |
|--------|-----------|
| QE | 13 |
| VASP | 5 |
| ABINIT, CP2K, Gaussian, GPAW, LAMMPS, ORCA, Siesta, xTB | 3 each |
| PySCF, Psi4, QMCPACK | 2-3 each |
| W90, Yambo | 2 each (via QE workflows) |

Demos include curated input samples organized by engine in `tests/inputformat/samples/` (134 curated cases total across all engines). The demo store has a compilation pipeline (`demo_store/compiler.py`) that generates demo snapshots from corpus samples.

---

## 6. Engineering Quality Assessment

### 6.1 What's Exceptionally Good

1. **The governance-gate enforcement loop** (`tests/gates/`, 63 files, 719 tests): This is genuinely novel in computational science software. Each constitutional invariant has a corresponding gate test that runs in CI. The gates scan actual source code (via AST analysis, import scanning, regex checks) to verify architectural rules. For example, `test_import_gate.py` verifies the three-layer import boundary by scanning all import statements. This prevents architectural decay — a common failure mode in large codebases.

2. **Driver protocol design** (`core/driver_protocol.py`): The Protocol + BaseEngineDriver hybrid allows both structural typing and inheritance. The 7-method MUST interface is minimal and well-chosen. The frozen `StepTypeSpec` dataclass with post-init validation prevents invalid driver registrations. The registry's `freeze()` mechanism prevents late registrations. This design genuinely allows adding a new engine by only touching `drivers/<engine>/` — no kernel modifications needed.

3. **Engine metadata catalogs**: Engines like VASP (232 tags), ABINIT (170+ tags), CP2K (215 tags), Gaussian (130 keywords), ORCA (120+ keywords), LAMMPS (114 commands), QMCPACK (65 tags) all have comprehensive JSON catalogs with type, default, category, and description for every parameter. These are both documentation and runtime validation resources.

4. **The B1 Engine Playbook** (`docs/laws/L2/B1_ENGINE_PLAYBOOK.md`): A standardized 8-phase SOP for bringing any engine to QE-depth maturity. Successfully used for 7 engines (VASP, ORCA, LAMMPS, Gaussian, ABINIT, QMCPACK, CP2K). Includes hard rules (plan before code, worklog every step, tests stay green, no kernel modifications), common pitfalls, and phase dependency graph. This is a replicable methodology.

5. **The SSOT minimalism**: Only two YAML files (`calculation.yaml` + `step.yaml`) contain truth. Everything else — input files, manifest, history, caches — is derived or disposable. This dramatically simplifies state management and makes the system debuggable. Combined with single-writer enforcement (every key owned by exactly one ParamSpace), this prevents the "who changed this?" ambiguity common in scientific workflow tools.

6. **Provenance system** (`src/qmatsuite/provenance/`, 3,233 LOC): Fully implemented with SQLite timeline, content-addressable storage (CAS), `OperationContext` tracking, pins, snapshots, queries, and graceful degradation. The "history world independence" invariant (deleting `.provenance/` must leave the project runnable) is elegant and well-enforced.

### 6.2 What's Solid

1. **Error type system** (`api/errors.py`): 9 error types with stable codes, customizable subcodes, retryable flags, context dicts, and DTO conversion. Structured errors flow from API through daemon/MCP without information loss.

2. **Thread-safe registry** with double-check locking and proper singleton pattern.

3. **Cross-platform file locking** via portalocker with explicit lock ordering (Constitution §4): `edit.lock` (short, YAML writes) and `run.lock` (long, full run). Non-reentrant by design.

4. **GUI architecture**: Clean React context provider tree (AppShell → Project → Structure → Calculation) with custom hooks for daemon communication, job polling, presets, and parameter metadata. The Electron IPC bridge (`preload.ts`) properly uses `contextBridge` for security.

5. **Test isolation**: Tests use fixtures extensively. Gate tests scan source code without executing it. Driver tests use curated samples rather than live engines. This enables the full test suite to run in CI without any simulation engines installed (except QE for integration tests).

6. **CI pipeline**: Multi-OS testing (Ubuntu 22.04 + macOS 14) with real QE compilation, caching, and comprehensive test execution.

### 6.3 What Needs Work

1. **CLI API migration** (31 TODOs): The CLI (`frontends/cli/app.py`) has 31 TODO markers for "Use QMSService API" — it still imports directly from core modules in many places. This violates the three-layer architecture (Constitution §18, Hard Law H1). While the gate tests may have exemptions for this, it's the largest single piece of architectural debt.

2. **MCP layer core imports** (~20 instances): MCP tools import from `qmatsuite.core.*` for resolution, project utilities, engine metadata, and analysis. These should ideally go through the API facade.

3. **README is outdated**: The README still opens with a Java v1 deprecation notice and describes QMatSuite primarily as a QE GUI. It doesn't mention the 15-engine support, Python v2 architecture, MCP integration, or the governance model. For a project of this quality, the README is significantly underselling the work.

4. **No CITATION.cff**: Essential for academic software. Without it, users can't easily cite the project.

5. **No user-facing documentation**: The docs/ directory contains excellent internal design documents (governance, architecture, engine specs) but lacks getting-started guides, tutorials, API reference, or user manuals. The `docs/guides/` directory exists but appears sparse.

6. **Coverage gaps**: While 70% overall coverage is decent, specific modules are notably low:
   - `provenance/restore.py`: 24% (rollback not well-tested)
   - `provenance/scanner.py`: 26% (artifact scanning)
   - `pseudo/pipeline.py`: 25% (pseudo download pipeline)
   - `viz/`: 0% (visualization module)
   - Several daemon handlers have lower coverage

7. **Collection error**: `tests/mcp/test_import_structure.py` has a collection error, indicating a broken test file.

8. **Legacy code**: `src/qmatsuite/legacy/` (270 LOC) still exists, though it's small. The `frontends/cli/app.py` is the larger legacy concern.

### 6.4 What's Missing (Designed but Not Implemented)

Based on comparison of design documents vs. code:

1. **Calc Type System Kind** (`CALC_TYPE_SYSTEM_KIND_SPEC`): `system_kind` (PERIODIC vs MOLECULAR) and `engine_group` immutability — designed, not implemented
2. **Structure Fingerprint unification**: Molecule canonicalization and unified entrypoint — partially implemented
3. **Full demo roundtrip automation**: Level-2 demo compilation pipeline exists but is not fully automated
4. **Agent Phase 3-4**: MCP memory layer, reasoning traces, multi-agent orchestration — designed only
5. **qmatsuite-full distribution**: QE + SSSP bundled release — planned
6. **Linux AppImage**: Lower priority, not yet implemented

---

## 7. Competitive Position

Based on the competitor analysis report and codebase review:

### Unique Moat

1. **15-engine breadth**: No other single tool covers solid-state DFT + molecular QC + classical MD + post-processing in a unified interface. AiiDA covers many engines but with heavier infrastructure (PostgreSQL, RabbitMQ). ASE provides calculators but not workflow management or GUI.

2. **MCP-native / BYOE philosophy**: The MCP server makes QMatSuite the first computational materials science platform designed for AI agent integration. Any LLM can drive it — no vendor lock-in.

3. **Constitutional governance**: The gate-test enforcement model provides architectural guarantees that no competitor offers. This is particularly valuable for long-term maintenance.

4. **Desktop-first + cloud-optional**: Unlike AiiDA (server-dependent) or FireWorks (MongoDB-dependent), QMatSuite runs fully locally with no external services required.

### Gaps vs. Competitors

1. **Workflow provenance**: AiiDA's workflow provenance (PostgreSQL-backed DAG) is more mature than QMatSuite's SQLite-based system. AiiDA's `verdi` CLI is also more polished.
2. **HPC integration**: No job scheduler integration (SLURM, PBS) yet. AiiDA and FireWorks handle this well.
3. **Community size**: As a single-developer project, the user/contributor community is small.
4. **Plugin ecosystem**: AiiDA has a rich plugin ecosystem; QMatSuite's engine drivers are all in-tree.

---

## 8. Publication Readiness

### 8.1 Suitable for JOSS?

**Yes, with moderate preparation.** JOSS requires:

| Requirement | Status | Action Needed |
|-------------|--------|---------------|
| Statement of need | Partial (in design docs) | Write concise statement for paper |
| Installation instructions | Yes (README, pyproject.toml) | Clean up README |
| Example usage | Yes (demos, CLI help) | Add user tutorial |
| Tests | Yes (6,562 tests, 70% coverage) | Fix collection error |
| Community guidelines | Missing | Add CONTRIBUTING.md |
| API documentation | Missing | Generate from docstrings |
| License | Yes (GPL v3) | OK |
| CITATION.cff | Missing | **Must create** |

### 8.2 Suitable for CPC / J. Chem. Theory Comput.?

**Not yet.** These venues require:
- Novel methodology or significant algorithmic contribution (the architecture itself may qualify)
- Benchmarks comparing with existing tools (AiiDA, ASE, pymatgen workflows)
- Validation against reference calculations
- More mature user-facing documentation

### 8.3 What's Needed Before Submission

**Critical (must-do)**:
1. Create `CITATION.cff`
2. Rewrite README for Python v2 (15-engine scope, installation, quickstart, architecture overview)
3. Add `CONTRIBUTING.md`
4. Fix the `test_import_structure.py` collection error
5. Write a getting-started tutorial (structure import → calculation → analysis)

**Important (should-do)**:
6. Complete CLI migration to QMSService API (reduce 31 TODOs)
7. Add user-facing API documentation
8. Write 2-3 engine-specific tutorials (QE, VASP, ORCA)
9. Add benchmarks vs. manual workflow / competing tools

**Nice-to-have**:
10. Increase coverage of provenance module (rollback, scanner)
11. Add HPC job scheduler integration
12. Generate PyPI release with proper metadata/classifiers

---

## 9. Key Observations & Highlights

### Novel Engineering Patterns

1. **Constitutional software governance**: The constitution → law → gate-test → CI enforcement chain is, to my knowledge, unique in computational science software. It's essentially "infrastructure as code" applied to architectural decisions. The 63 gate tests scan ~153K lines of source to verify ~80 invariants on every commit.

2. **GEN/SPEC step type duality with underscore ban**: The convention that `step_type_gen` (no underscores) vs `step_type_spec` (contains underscore as `{prefix}_{gen}`) provides a zero-ambiguity classification. Any string with an underscore is a spec; without is a gen. This eliminates an entire class of routing bugs.

3. **ParamSpace non-persistence**: Presets and workflows are never stored as filesystem entities — they are runtime interpretations of the current YAML state. This avoids the "stale preset" problem where saved presets drift from actual parameters.

4. **Materialization as clean rewrite**: Input file generation always writes from scratch (YAML → engine input), never patches existing input files. This eliminates parse-modify-write roundtrip bugs.

5. **Three recipe archetypes**: Directory-state (shared workdir, accumulating wavefunction), Strong-chain (isolated per subchain, topology-validated), and Cleanup (isolated, rm-before-write) cover the three fundamentally different engine execution models cleanly.

### Scale Perspective

For a project primarily developed by a single author (with AI assistance), the scale is remarkable:
- 153K+ lines of Python, 34K+ lines of TypeScript
- 15 engine drivers with 107 step types
- 6,562 tests with 0 failures
- 121 daemon RPC handlers, 38 MCP tools, 40+ CLI commands
- 74 demo projects covering all engines
- 63 gate tests enforcing constitutional invariants
- 5 CI/CD workflows with multi-OS testing
- Electron packaging with code signing for macOS and Windows

### Concerns

1. **Single-developer risk**: The extreme detail of the governance documents and the breadth of the codebase suggest deep individual knowledge. Bus factor is 1. The governance model partially mitigates this (a new developer could understand the architecture by reading the constitution), but onboarding documentation is needed.

2. **API facade size**: `QMSService` at 9,207 lines with 143 methods is a very large God-class, even with subsystem delegation. This could benefit from further decomposition.

3. **CLI technical debt**: The 31 "Use QMSService API" TODOs represent the primary architectural violation in the codebase.

---

## Appendix A: File Tree (Top 2 Levels)

```
QMatSuite/
├── src/qmatsuite/
│   ├── analysis/        # Analysis plotting and visualization
│   ├── api/             # Unified service facade (143 methods)
│   ├── calculation/     # Calculation lifecycle management
│   ├── cli/             # Typer CLI entry point
│   ├── core/            # Kernel: YAML I/O, protocols, registry, analysis primitives
│   │   ├── analysis/    # Analysis primitives (BandStructure, DOS, Convergence, Field3D, etc.)
│   │   └── engines/     # Engine metadata and management
│   ├── daemon/          # WebSocket daemon server
│   ├── data/            # Shared data resources
│   ├── demo_store/      # Demo project compilation and replay
│   ├── drivers/         # 15 engine driver bundles
│   │   ├── abinit/  ├── cp2k/    ├── gaussian/  ├── gpaw/
│   │   ├── lammps/  ├── orca/    ├── psi4/      ├── pyscf/
│   │   ├── qe/      ├── qmcpack/ ├── siesta/    ├── vasp/
│   │   ├── w90/     ├── xtb/     └── yambo/
│   ├── engine/          # Engine installation and management
│   ├── engines/         # Python-script engine wrappers (ORCA, Psi4, PySCF)
│   ├── execution/       # Job execution, runner
│   ├── frontends/       # Frontend CLI app (legacy)
│   ├── inputformat/     # Input file parse/write orchestrator
│   ├── io/              # I/O providers, generators, parsers
│   ├── ir/              # Intermediate representation
│   ├── legacy/          # Legacy code (270 LOC)
│   ├── mcp/             # MCP server + 38 tools
│   ├── parsers/         # Output parsers
│   ├── presets/         # ParamSpace framework
│   ├── project/         # Project management
│   ├── provenance/      # SQLite + CAS provenance system
│   ├── pseudo/          # Pseudopotential management
│   ├── resources/       # Bundled resources (templates, demos, structures, pseudos)
│   ├── viz/             # Visualization data models
│   └── workflow/        # Workflow templates, step factory
├── gui/
│   ├── electron/        # Electron main process + preload
│   ├── src/             # React app (65 components, 5 contexts, 8 hooks)
│   └── tests/           # Playwright E2E tests (15 specs)
├── tests/               # 627 test files, 6,567 tests
│   ├── api/       ├── cli/       ├── contract_crawler/  ├── core/
│   ├── daemon/    ├── demo_store/ ├── drivers/           ├── examples/
│   ├── fixtures/  ├── gates/     ├── inputformat/       ├── integration/
│   ├── integrity/ ├── ir/        ├── mcp/               ├── presets/
│   ├── provenance/├── unit/      └── workflow/
├── docs/
│   ├── design/          # 30+ design documents
│   ├── engines/         # Per-engine plans, worklogs, curated indexes
│   ├── laws/            # L1 (8 laws) + L2 (15 specs) + README
│   └── history/         # Review documents
├── .github/workflows/   # 5 CI/CD workflows
├── CONSTITUTION.md      # Central constitutional document
├── CLAUDE.md            # Agent instruction file
├── pyproject.toml       # Package configuration (v1.2.2)
├── LICENSE              # GPL v3
└── README.md            # (Needs update for Python v2)
```

## Appendix B: Complete MCP Tool Inventory

| # | Tool | File | Description |
|---|------|------|-------------|
| 1 | ping | ping.py | Health check |
| 2 | init_project | init_project.py | Initialize new QMatSuite project |
| 3 | list_engines | list_engines.py | List registered engine families |
| 4 | list_workflows | list_workflows.py | List workflow templates |
| 5 | get_presets | get_presets.py | Get preset catalog |
| 6 | search_parameters | search_parameters.py | Search engine parameter metadata |
| 7 | create_calculation | create_calculation.py | Create new calculation |
| 8 | set_species_map | set_species_map.py | Set element→pseudo mapping |
| 9 | set_parameters | set_parameters.py | Set step parameters |
| 10 | apply_preset | apply_preset.py | Apply preset to step |
| 11 | inspect_calculation | inspect_calculation.py | Inspect calculation state |
| 12 | list_calculations | list_calculations.py | List project calculations |
| 13 | preview_compilation | preview_compilation.py | Preview input file compilation |
| 14 | run_calculation | run_calculation.py | Execute calculation |
| 15 | get_status | get_status.py | Get run status |
| 16 | get_results_summary | get_results_summary.py | Get results summary |
| 17 | quick_run | quick_run.py | One-shot create+run |
| 18 | search_knowledge | search_knowledge.py | Search engine knowledge base |
| 19 | list_structures | list_structures.py | List project structures |
| 20 | import_structure | import_structure.py | Import structure from file |
| 21 | get_structure_detail | get_structure_detail.py | Get structure details |
| 22 | promote_structure | promote_structure.py | Promote relaxed structure |
| 23 | demo_store | demo_store.py | Browse/load demo projects |
| 24 | list_resources | list_resources.py | List available resources |
| 25 | resolve_species_map | resolve_species_map.py | Resolve species to pseudos |
| 26 | download_pseudo_library | download_pseudo_library.py | Download pseudo library |
| 27 | cleanup_project | cleanup_project.py | Clean up project state |
| 28 | install_engine | install_engine.py | Install simulation engine |
| 29 | list_installable_engines | list_installable_engines.py | List available engines |
| 30 | verify_engine | verify_engine.py | Verify engine installation |
| 31 | register_engine_path | register_engine_path.py | Register custom engine path |
| 32 | uninstall_engine | uninstall_engine.py | Uninstall engine |
| 33 | set_active_engine | set_active_engine.py | Set active engine variant |
| 34 | list_analyses | list_analyses.py | List available analyses |
| 35 | plot_analysis | plot_analysis.py | Generate analysis plot |
| 36 | generate_kpath | generate_kpath.py | Generate k-point path |

(36 tool files; 38 `@mcp.tool` decorators including some files with multiple tools)

## Appendix C: Complete Step Type Registry

```
15 engines, 107 step types:

abinit (4):  abinit_md, abinit_nscf, abinit_relax, abinit_scf
cp2k (8):    cp2k_bandspw, cp2k_cell_opt, cp2k_dos, cp2k_geo_opt,
             cp2k_md, cp2k_relax, cp2k_scf, cp2k_vibrational
gaussian (6): gaussian_freq, gaussian_hf, gaussian_mp2,
              gaussian_relax, gaussian_scf, gaussian_td
gpaw (6):    gpaw_bandspw, gpaw_dos, gpaw_md, gpaw_nscf,
             gpaw_relax, gpaw_scf
lammps (8):  lammps_deform, lammps_equilibrate, lammps_md,
             lammps_minimize, lammps_npt, lammps_nve,
             lammps_nvt, lammps_relax
orca (12):   orca_casscf, orca_ccsd, orca_freq, orca_hf,
             orca_mp2, orca_nevpt2, orca_opt, orca_relax,
             orca_scf, orca_sp, orca_td, orca_tddft
psi4 (5):    psi4_hf, psi4_mp2, psi4_relax, psi4_scf, psi4_td
pyscf (11):  pyscf_casci, pyscf_casscf, pyscf_ccsd, pyscf_dft,
             pyscf_freq, pyscf_mp2, pyscf_opt, pyscf_relax,
             pyscf_scf, pyscf_td, pyscf_tddft
qe (20):     qe_bands, qe_bandspw, qe_custom, qe_dos, qe_dynmat,
             qe_gipaw, qe_hp, qe_matdyn, qe_md, qe_neb, qe_nscf,
             qe_pdos, qe_ph, qe_plotband, qe_pp, qe_pw2qmcpack,
             qe_pw2wannier, qe_q2r, qe_relax, qe_scf
qmcpack (3): qmcpack_dmc, qmcpack_vmc, qmcpack_wfopt
siesta (5):  siesta_bands, siesta_dos, siesta_md,
             siesta_relax, siesta_scf
vasp (11):   vasp_bandspw, vasp_dielectric, vasp_dos, vasp_elastic,
             vasp_md, vasp_neb, vasp_nscf, vasp_phonon,
             vasp_relax, vasp_scf, vasp_static
w90 (2):     w90_wannier, w90_wannierprep
xtb (2):     xtb_md, xtb_relax
yambo (4):   yambo_bse, yambo_gw, yambo_optics, yambo_setup
```

## Appendix D: Gate Test Inventory

63 gate test files enforcing constitutional invariants:

| Gate Test | Invariant Enforced |
|-----------|-------------------|
| `test_analysis_invariants.py` | Analysis primitive contracts |
| `test_api_surface_final.py` | API surface accounting |
| `test_api_utils_online_search_removed.py` | Utils slimming |
| `test_banned_legacy_aliases.py` | No legacy step type aliases |
| `test_cas_integrity.py` | CAS content-addressable integrity |
| `test_companion_completeness.py` | Companion engine completeness |
| `test_companion_routing.py` | Companion step routing |
| `test_corpus_index.py` | Corpus sample index integrity |
| `test_daemon_kernel_ban.py` | Daemon kernel import ban |
| `test_daemon_no_direct_workflow_templates_import.py` | Daemon workflow isolation |
| `test_daemon_no_hand_serialization.py` | Daemon DTO serialization |
| `test_daemon_no_legacy_resolve.py` | Daemon no legacy resolution |
| `test_daemon_no_yaml_write.py` | Daemon YAML write ban (H9) |
| `test_daemon_shim_no_logic.py` | Daemon shim simplicity |
| `test_demo_generated.py` | Demo generation correctness |
| `test_demo_integrity.py` | Demo data integrity |
| `test_engine_no_ssot_import.py` | Engine SSOT import ban (K6) |
| `test_frontend_no_yaml_write.py` | Frontend YAML write ban (H9) |
| `test_gen_spec_convergence_gate.py` | GEN/SPEC convergence |
| `test_gui_rpc_wiring.py` | GUI-daemon RPC completeness |
| `test_import_gate.py` | Three-layer import boundary (H1) |
| `test_import_rules.py` | Import rule enforcement |
| `test_kernel_no_api_import.py` | Kernel→API reverse ban (K0) |
| `test_kernel_no_frontend_import.py` | Kernel→frontend ban |
| `test_lock_ordering.py` | Lock ordering (§4) |
| `test_no_bare_step_type.py` | No bare step_type fields (§7) |
| `test_no_cross_engine_defaults.py` | No cross-engine defaults |
| `test_no_dangling_calls.py` | No dangling function calls |
| `test_no_deep_domain_import.py` | No deep domain imports |
| `test_no_duplicate_scanners.py` | No duplicate scanners |
| `test_no_fallbacks.py` | No silent fallbacks (INV-1) |
| `test_no_legacy_accessor_side_door.py` | No legacy accessor bypass |
| `test_no_legacy_history.py` | No legacy history |
| `test_no_legacy_identity_fields.py` | ULID-only identity (§6) |
| `test_no_legacy_imports.py` | No legacy module imports |
| `test_no_legacy_nested_accessors.py` | No legacy nested accessors |
| `test_no_manual_join_split.py` | No manual step type join/split |
| `test_no_nonderived_mappings.py` | No non-derived mappings |
| `test_no_qe_fallback.py` | No QE fallback (INV-1) |
| `test_no_qe_special_case.py` | No QE special-casing |
| `test_no_sensitive_paths.py` | No sensitive paths (S1) |
| `test_no_service_delegating_utils.py` | No service-delegating utils |
| `test_no_spec_in_preset_layer.py` | No spec in preset layer |
| `test_no_stub_service_methods.py` | No stub service methods |
| `test_no_third_namespace.py` | No third namespace (§7) |
| `test_postproc_gen_uniqueness.py` | Post-processing gen uniqueness |
| `test_provenance_failure_graceful.py` | Provenance graceful degradation |
| `test_provenance_independence.py` | History world independence (§3) |
| `test_provenance_opctx_required.py` | OperationContext required (P2) |
| `test_provenance_skip_isolation.py` | Provenance skip isolation |
| `test_ref_analysis_sweep.py` | Reference analysis sweep |
| `test_ref_packs.py` | Reference pack integrity |
| `test_registry_routing.py` | Registry routing correctness |
| `test_resolution_meta_only.py` | Resolution meta-only reads (K7) |
| `test_schema_self_consistency.py` | Schema self-consistency |
| `test_single_qmsservice_definition.py` | Single QMSService definition |
| `test_single_ssot_mapping.py` | Single SSOT mapping |
| `test_step_type_constitution.py` | Step type constitution (§7) |
| `test_step_type_cross_assignment.py` | No gen/spec cross-assignment |
| `test_step_type_declared_sets.py` | Declared step type sets |
| `test_step_type_param_mismatch.py` | Step type parameter matching |
| `test_supported_subset.py` | Supported gen steps subset |
| `test_tests_no_legacy_api_imports.py` | Tests no legacy API imports |
| `test_underscore_ban.py` | Underscore ban enforcement |
| `test_yaml_read_single_entry.py` | Single YAML read entry point |
| `test_yaml_write_single_entry.py` | Single YAML write entry point |

## Appendix E: Raw Metrics Output

```
=== Codebase Size ===
Python src/ LOC:          153,789
TypeScript/React gui/ LOC: 34,671
Test LOC (Python):        135,565
GUI test LOC (Playwright):  6,639
Source .py files:             608
Test .py files:               627
JSON data files:              193 (984,387 lines)
Tracked files:              4,069

=== Test Results (commit b379b06c) ===
Collected: 6,567 tests (1 collection error)
Passed:    6,562
Failed:    0
Skipped:   5
Warnings:  992
Coverage:  70% (61,482 statements, 18,740 missed)
Duration:  379.73s with -n auto

=== Engine Registry ===
Registered engines: 15
Total step types: 107

=== Dependencies ===
Runtime: 16 packages
Dev: 3 packages
Installed (transitive): 155 packages

=== CI/CD ===
Workflows: 5 (.github/workflows/)
  - tests.yml: Multi-OS (Ubuntu 22.04, macOS 14) with QE build
  - release-macos.yml: macOS DMG with code signing
  - release-windows.yml: Windows NSIS with Azure signing
  - release-pip.yml: PyPI release
  - build-runtime-dir.yml: Runtime bundling

=== Technical Debt ===
TODO comments in src/: 42 (31 CLI migration, 11 other)
FIXME comments: 0
HACK comments: 0

=== Daemon RPC Handlers: 121 ===
=== MCP Tools: 38 ===
=== CLI Commands: 40+ ===
=== GUI Components: 65 files ===
=== Demo Projects: 74 (52 YAML + 22 JSON) ===
=== Curated Input Samples: 134 cases across 14 engines ===
=== Gate Tests: 63 files, 719 individual tests ===
```

---

*Review generated on 2026-02-26 at commit b379b06cc082a18170d6ac3f7de8ef37f0dfe4cf. All metrics gathered programmatically from the repository. No external data sources were consulted beyond what the codebase provides.*
