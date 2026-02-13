# QMatSuite Constitution

**Version**: 2.1
**Last Updated**: 2026-02-03
**Scope**: QMatSuite / QuantumVITAS v2 codebase

---

## Preamble

This document is the QMatSuite project "Constitution". It defines the project's highest-level rules and invariants.
Detailed mechanics/specs are maintained as standalone documents in `docs/laws/`; this constitution records only high-level invariants and references those specs.

**Document Hierarchy**:
1. **This constitution** (highest authority)
2. **Laws** (standalone specs under `docs/laws/`, referenced by this constitution)
3. **Implementation docs** (design/implementation docs under `docs/`, non-binding)

**One-line instruction for AI**
> Obey the root-level `CONSTITUTION.md`; detailed specs at `docs/laws/`; improvements go through small PRs.

---

## Terminology & Truth Layers

### Truth vs Info
- **Truth (truth layer)**: Facts and keys used for computation, reproducibility, and stability (ULID, SHA256, canonical structure form, unit conventions).
- **Info (info layer)**: Mutable information for display, understanding, hints, and search (filenames, paths, slugs, source descriptions, UI copy).

### Identity
- Resource identity uses **ULID** as the sole identifier.
- Pseudopotential identity uses **SHA256 (strict)** / **SHA_FAMILY (physical)** as core comparison keys (see §9).

---

## 1. Language Policy

1) All code, comments, and documentation in this repository default to **English**.
2) Unless the author explicitly requests otherwise, no non-English documents or comments shall be added.

---

## 2. SSOT & Persistence (Single Source of Truth)

### 2.1 Sole Executable Truth

SSOT consists of only: **calculation.yaml** + **step.yaml**.

- `step.yaml` is the sole executable truth; reproducibility of any computation result can only be guaranteed by step parameters.
- `step.yaml` must remain pure input — it MUST NOT contain workflow / preset / provenance metadata.
- `calculation.yaml` is responsible for: structure, species_map (pseudo triple), step topology.

### 2.2 Input Files Are Intermediates

Input files (e.g., QE `.in` files) are intermediates:
- Written into `raw/` via clean rewrite during materialization.
- The run only reads from `raw/`.
- Modifying YAML during a run does not affect the current run (only the next run).

### 2.3 Scanning outdir/.save Is Banned

Scanning/cleaning `outdir/.save` (wavefunctions, etc.) is forbidden. It MUST NOT be used for incremental skip decisions.

### 2.4 YAML I/O Must Go Through Doc + yaml_io

All project/calc/step YAML reads and writes must use the Doc layer and centralized yaml_io. Direct use of `yaml.safe_load`/`yaml.safe_dump` is forbidden.

> Detailed spec: [KERNEL_DEPENDENCY_SPEC.md](docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md) §2.1 (Domain: ssot)

---

## 3. Present vs Past (History World Separation)

### 3.1 Present = Working Directory Truth

Current calculation state exists only in SSOT files (calculation.yaml + step.yaml) within the working directory.

### 3.2 Past = .history/ (Sole Location)

- `.history/` is the only allowed location for persisting derived narrative artifacts (digests / thumbnails / snapshots).
- `.history/` is append-only, immutable.
- Deleting `.history/` means the history UI goes blank — it MUST NOT be "rebuilt" from other locations.

### 3.3 Job == Run

- Each engine invocation = one Job = one Run; job_id == run_id (same ULID).
- Each run produces one immutable **RunRevision** (inputs snapshot + run digest + step digests).
- Digests are best-effort; digest failures MUST NOT cause crashes.

---

## 4. Concurrency & Locks

Each calculation has two cross-process file locks:

| Lock | Duration | Purpose |
|------|----------|---------|
| `edit.lock` | Short | YAML writes only (via `save_yaml_doc()`) |
| `run.lock` | Long | From materialization through execution completion |

**Locks are non-reentrant**: Calling `save_yaml_doc()` while holding `edit.lock` → deadlock (portalocker non-reentrant).

---

## 5. Incremental Run Manifest

### 5.1 Manifest = Runtime Bookkeeping (Non-SSOT)

Each calc's manifest is runtime bookkeeping — deletable, not a UI cache, not SSOT.

### 5.2 Skip Decisions

Skip determination uses only: `(kind/step_type, pseudo_set_sha, structure_sha, step_sha, done==true)`. Output hashes are never used.

### 5.3 Run Modes

- **Run Calculation**: Incremental run is default; full run first reconciles and clears done marks, then starts from step0.
- **Run Single Step**: The target step must always execute (no skip). After success, conservatively marks downstream steps as `done=false`.

### 5.4 Centralized StepDonePolicy

"Step done" logic must be centralized in `StepDonePolicy` (single entry point for runner + skip).

---

## 6. Identity: ULID-Only

### 6.1 ULID Reference Rules

- Resources may only reference each other via **ULID**.
- Paths, filenames, slugs may only serve as Info — never as cross-resource reference keys.
- DTOs/meta MUST NOT contain legacy identity fields (`id`, `calc_id`, `step_id`, `run_id`, etc.).
- Canonical fields: `project_ulid`, `calc_ulid`, `step_ulid`, `run_ulid`.
- Slugs are only for the resource's own `meta.slug` — never persisted in cross-resource references; internal references use ULID only.

### 6.2 Project Root

- Project root marker is fixed at: `project.qv.yml`.
- Discovery logic: traverse directory tree upward to find the directory containing the marker.

### 6.3 Identity Immutability

- Rename / move / directory reorganization must not change resource identity (ULID is immutable).

### 6.4 Immutability Scope

**Immutable truth keys** (must not change after initialization): ULID, step_type_spec, engine.

**Mutable info keys**: name, slug, path, description.

> Gate: `tests/gates/test_no_legacy_identity_fields.py`

---

## 7. Step Type Constitution (GEN/SPEC Only)

### 7.1 Two and Only Two Namespaces

| Field | Layer | Purpose | Examples |
|-------|-------|---------|----------|
| `step_type_gen` | Intent/UI/workflow/preset/ParamSpace/file naming | Engine-agnostic | `scf`, `relax`, `bandspw` |
| `step_type_spec` | SSOT execution/step.yaml/runner/dispatch/handler | Engine-specific | `qe_scf`, `vasp_relax`, `w90_wannier` |

### 7.2 Derivation Rule (Core Law)

```
step_type_spec = f"{engine_prefix}_{step_type_gen}"
```

- `engine_prefix` and `step_type_gen` MUST NOT contain underscores `_` (underscore ban → reliable splitting).
- Reverse derivation uses `split(spec)` at the first underscore.
- Conversion utility functions must be centralized in `workflow/step_type_convert.py`.

### 7.3 Bans

- **Legacy step type aliases are fully banned**: DTOs/YAML/tests/tools MUST NOT contain `vc-relax`, `opt`, `w90_preproc`, `w90_run`, etc.
- **Bare `step_type` field is banned**: Must explicitly use `step_type_gen` or `step_type_spec`.
- **Manual split/join is banned**: Code MUST NOT manually split/join underscores; must use canonical conversion functions.
- **Daemon/CLI must not convert**: Upper layers MUST NOT import/call conversion functions; DTOs carry both fields.

### 7.4 Wannier Workflow

- GEN: `wannierprep` → `pw2wannier` → `wannier`
- SPEC: `w90_wannierprep` → `qe_pw2wannier` → `w90_wannier`

### 7.5 Bands Semantics

- `bandspw` is a computation step (implementable by qe/vasp).
- `bands` is a post-processing step (implementable by qe; vasp may not have it — gen→spec=0 mapping is allowed).

> Detailed spec: [STEP_TYPE_GEN_SPEC_CONSTITUTION.md](docs/laws/L1/STEP_TYPE_GEN_SPEC_CONSTITUTION.md)
> Gates: `tests/gates/test_step_type_constitution.py`, `test_no_bare_step_type.py`, `test_underscore_ban.py`, `test_no_manual_join_split.py`, `test_banned_legacy_aliases.py`

---

## 8. Preset / ParamSpace / IR (Non-Persistent Intent Layer)

### 8.1 Non-Entity Principle

Preset / Workflow / IR **are not persisted**. They are only runtime interpretation of the current step DAG and forward generation / reverse interpretation of step parameter sets.

### 8.2 ParamSpace Compilation Flow

ParamSpace compiles preset profiles into IR patches, written to step.yaml (SSOT).

### 8.3 Reverse Detection

Preset is inferred only through "exact persistent pattern matching"; no match → `custom`.

### 8.4 Core ParamSpace Constraints

- **Single-writer principle**: Each YAML key can only be written/deleted by one ParamSpace.
- **Three-state Cell**: Each profile for each key must be `VALUE(v)` / `NOT_APPLICABLE` (must-absent) / `WILDCARD` (not participating in matching).
- **Compiler/Detector equivalence**: `detect(compile_one(step_type, options))` must equal the original options value.
- **No guessing**: When key parameters are missing with no reliable default semantics, Detector must return `CUSTOM`.

### 8.5 Apply Rules

- Apply is a **local precise modification**: only modifies keys declared by that dimension's Variant.
- NOT_APPLICABLE → must delete that key.
- Other dimensions / user-written parameters must remain unchanged.
- Execution order: Prerequisite ParamSpaces first (those that change applicability), then Dependent ParamSpaces (those depending on Oracle).

> Detailed definition: [PARAMSPACE_SPEC.md](docs/laws/L1/PARAMSPACE_SPEC.md)

---

## 9. Species / Pseudopotential SSOT

### 9.1 Project-Run Pseudo SSOT

- SSOT is in `calculation.yaml`: `species_map` (element / mass / pseudo filename + hash, extensible).
- Step-level `species_overrides` is warning+ignored (only for legacy/standalone).

### 9.2 Runtime pseudo_dir Management

- `pseudo_dir` is runtime-managed, forced to point at `project/pseudo`.
- Runner stages only required pseudopotentials.

### 9.3 Three Pseudo Sources

Only three sources are allowed:
- **internal**: `repo/resources/pseudo`
- **lib**: User-installed at `~/.qmatsuite/libraries/pseudo/`
- **project runtime**: `project/pseudo`

A fourth source is forbidden.

### 9.4 SHA256 vs SHA_FAMILY

- **SHA256**: Bitwise identical (strict).
- **SHA_FAMILY**: Physically equivalent (SHA256 after stripping all whitespace).
- UI dropdown selection primary key is SHA256. SHA_FAMILY is used only for conflict handling / warnings / cross-calc reference updates.

---

## 10. Scan Rules (Hard Law)

### 10.1 YamlDoc Invariant

`dict` is always a subtree patch; dict-leaf is forbidden (scan is no exception).

### 10.2 ScanRef

ScanRef leaf is a scalar token string only: `"@scan:<scan_id>"`. The old `{scan_ref: ...}` format is forbidden.

### 10.3 parameter_scan Structure

`step.yaml` top-level `parameter_scan.<scan_id>.values:[...]`.

- Values are explicit enumerations only; `linspace/logspace` are UI-only tools, never persisted.
- Fingerprint/manifest hash includes only resolved effective engine parameters; the `parameter_scan` section itself does not participate in hashing.

### 10.4 Scan Scope & Ordering

- Scan expansion occurs within a single job; scans do not span jobs.
- Variant ordering is deterministic: later-step / faster-changing dimensions go in the inner loop (maximize reuse).

### 10.5 Orphan Scan Deletion

Full replacement semantics required; when UI removes all scans it must send `parameter_scan:{}`. UI must flush scan values on Apply (commit-on-apply).

---

## 11. Managed / Injected Parameters UI Policy

Runtime-managed keys (e.g., QE CONTROL: `prefix`/`outdir`/`pseudo_dir`) and step-type-owned keys (e.g., `CONTROL.calculation`) are **read-only in UI**: not editable / scannable / unsettable / removable.

Engine metadata `is_managed` + `managed_reason` drives UI display (QE as MVP).

---

## 12. UI Input → YAML → Writer Type Contract

### 12.1 Two Key Classes

| Class | Definition | Type Rules |
|-------|-----------|------------|
| **A-class** | Keys owned/mapped by Preset/IR/ParamSpace | Strict typing + canonicalization; invalid parse blocks persistence |
| **B-class** | Free engine keys | No type enforcement; any string allowed |

### 12.2 A-class Key Set SSOT

Sourced from ParamSpace/IR registry export, **NOT** from `qeparameters.json`.

### 12.3 Writer Contract

- typed bool → QE outputs `.true.`/`.false.`
- string `".true."` preserves literal value, no reinterpretation.

---

## 13. RELAX Audit Law

### 13.1 Relax Is a Structure Transformer

Input structure → output structure; no electronic state / no SCF reference.

### 13.2 Single GEN Step

Only one public GEN step: `relax`. Engine-internal specs: `qe_relax`, `orca_relax`, `pyscf_relax`.

### 13.3 Output Structure

Output structure is a calc-private artifact; it is NOT a project structure resource unless explicitly promoted.

### 13.4 QC Strong-Chain Boundary (ORCA/PySCF)

- SCF chains must not cross a relax step.
- `run_step(non-relax)` must find the SCF before the relax; otherwise → hard error.
- `run_calc` validates topology and fails fast.

### 13.5 Missing Structure = Hard Error

Missing generated structure artifact → hard error; do not auto-rerun relax.

---

## 14. LAMMPS Integration Constitution

### 14.1 Structure Transformation Engine

LAMMPS is a structure transformation engine. GEN steps: `relax`, `md`; SPEC: `lammps_relax`, `lammps_md` (explicit mapping).

### 14.2 restart_from

`restart_from` references upstream artifacts, not structure resources. No cross-calculation references; cross-calc reuse requires structure promotion.

### 14.3 potential_map SSOT

`calculation.yaml`: `potential_map` is SSOT; assets live in `project/potentials/`.

### 14.4 Fingerprint Must Include Potentials

Inline dict → `step_sha`; external files → `potential_assets_sha` (to be unified as `engine_assets_sha` in future).

### 14.5 Real Execution Smoke Tests

Required: LJ relax, EAM MD external, relax→md chain, md restart_from — four categories of real execution tests.

---

## 15. Geometry Constitution

### 15.1 Single Canonicalization

Structure canonicalization may only occur once (at the geometry entry/preparation layer). No subsequent snap / wrap / fold is allowed.

### 15.2 Canonicalization Interval

Fractional coordinates map to `[-wrap_tol, 1 - wrap_tol)`, `wrap_tol = 1e-4` (default).

### 15.3 Boundary Atoms

Dual-side detection (`0 ± boundary_tol`, `1 ± boundary_tol`), `boundary_tol = 0.01` (default).

---

## 16. QE Structure Schema

### 16.1 Internal Storage

- Store only cell parameters (absolute units, angstrom).
- Atom positions always stored as fractional coordinates.
- Never store QE-specific representations (ibrav / alat / celldm, etc.) in JSON.

### 16.2 Output Filename Invariant

Input files may be versioned (`scf.in`, `scf-1.in`); output is fixed at `{step_type}.out/.err` and overwrites. Deriving output filenames from input filenames is forbidden.

---

## 17. Engine Execution Semantics

### 17.1 Two Engine Models

| Model | Engines | State Transfer |
|-------|---------|---------------|
| Session-chain | PySCF/ORCA | In-memory state chain, linearly ordered |
| Artifact-bridged | QE/W90/LAMMPS | Disk file bridging, steps can be independent |

### 17.2 Session-Chain Engine Strict Linear Dependency

- Each step must consume the most recent legal predecessor state; missing state → hard failure.
- DAG execution, skipped dependencies, and implicit completion are forbidden.
- SCF is the only step that consumes structure and produces mf.
- SCF checkpoint serves only as initial guess; SCF must be rerun.
- No reliable serialization/reuse/recovery of intermediate state exists except for SCF.

### 17.3 Engine Integration Invariants

- All routing must be explicit registry lookup; unknown step type → hard error.
- Adding a new engine MUST NOT modify kernel code (only add `drivers/<engine>/` + tests).
- Driver self-containment: all engine-specific logic lives within the driver bundle.

### 17.4 Engine Recipe & Runner Architecture

- Runner is engine-agnostic; dispatches exclusively through DriverRegistry.
- One engine → one driver → one recipe.
- Recipes produce runtime-only JobGraphs (not persisted).
- Three recipe archetypes: Directory-state (QE), Strong-chain (ORCA/PySCF/CP2K), Cleanup (VASP).

> Detailed specs:
> - [ENGINE_INTEGRATION_CONSTITUTION.md](docs/laws/L1/ENGINE_INTEGRATION_CONSTITUTION.md)
> - [ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md](docs/laws/L1/ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md)

---

## 18. API Layering & Facade

### 18.1 Three-Layer Model

| Layer | Package | Import Rules |
|-------|---------|-------------|
| **Frontend** | daemon, CLI, GUI | May only import from `quantumvitas.api` |
| **API Facade** | `quantumvitas.api` | DTOs + Errors + Utils + Service |
| **Core/Runtime** | All other packages | Frontend MUST NOT import directly |

### 18.2 Utils Policy

Utils reexport is disallowed by default. Exceptions only for:
- Genuine frontend boundary helpers
- Functions that cannot reasonably be a QVService capability method
- With docstring justification

### 18.3 DTO Boundary

All data crossing the API boundary must be DTOs or primitive types.

### 18.4 Filesystem Access Control (Law H9)

Only kernel is allowed to modify SSOT filesystem. Frontend MUST NOT directly write YAML / create project structures / modify calculation/step/structure files.

> Detailed spec: [API_CONSTITUTION.md](docs/laws/L1/API_CONSTITUTION.md)
> Gates: `tests/gates/test_import_gate.py`, `test_frontend_no_yaml_write.py`, `test_daemon_kernel_ban.py`

---

## 19. Kernel Internal Dependencies

### 19.1 Kernel → API Ban

Kernel MUST NOT reverse-import the API facade.

### 19.2 Seven-Domain Model

Kernel is organized into 7 domains (ssot, resources, models, runtime, engines, analysis, workflow), each with explicit responsibility boundaries and import bans.

### 19.3 YAML Reading

Resolution may only read the `meta.*` subtree (metadata); reading non-meta fields is forbidden.

> Detailed spec: [KERNEL_DEPENDENCY_SPEC.md](docs/laws/L1/KERNEL_DEPENDENCY_SPEC.md)
> Exceptions: [KERNEL_EXCEPTIONS.md](docs/laws/L1/KERNEL_EXCEPTIONS.md)
> Gates: `tests/gates/test_kernel_no_api_import.py`, `test_engine_no_ssot_import.py`, `test_resolution_meta_only.py`

---

## 20. Data Root Directories & Temporary Directories

### 20.1 Two Root Directory Types

| Directory | Semantics | Deletable |
|-----------|-----------|-----------|
| `.qmatsuite/` | Persistent assets (engines, libraries, seeds, config, logs) | No |
| `.tmp/` | Temporary files (runs, downloads, locks) | Yes |

### 20.2 Deprecated temp/

Code MUST NOT use `repo_root/temp/`. Any new code referencing `temp/` is unconstitutional.

### 20.3 settings.json

Sole global config (minimal). QE engine two-state model: `qe.bin_dir` is null → Internal QE; non-null → External QE. Implicit fallback (PATH / QE_HOME / shell discover / disk scan) is forbidden.

---

## Final Clauses

### Amendment Principle
- Constitutional amendments require project author review.
- Implementation details, evidence, TODOs, and improvement suggestions are maintained in English documentation.

### Interpretation
- Constitution takes precedence.
- Simplicity takes precedence.
- Mathematical provability takes precedence over UX convenience.

### Summary Principle

**Execution is concrete; intention is inferred.**

All computations trust only step parameters; workflow and preset are merely interpretations of the current state, not facts.

---

## Revision Summary v2.1 (2026-02-03)

### From v2.0 to v2.1

**Language change**:
- Constitution converted from Chinese (CONSTITUTION_ZH.md) to English (this document).
- CONSTITUTION_ZH.md is now deprecated / non-authoritative.
- Added §17.4 to reference ENGINE_RECIPE_AND_RUNNER_CONSTITUTION.md.

### From v1.2 to v2.0

**Structural overhaul**:
- Constitution rewritten from ~1400-line "full detail" to ~380-line "thin constitution".
- Detailed mechanics specs migrated to standalone documents under `docs/laws/`.
- Document hierarchy system introduced (constitution > governance specs > implementation docs).

**New laws** (aligned with 13 finalized laws):
1. **§3 History world separation**: Present vs Past, `.history/` append-only, Job == Run, RunRevision.
2. **§4 Concurrency & locks**: edit.lock / run.lock two-lock model, non-reentrant.
3. **§5 Incremental run manifest**: Non-SSOT bookkeeping, skip decision rules, StepDonePolicy centralization.
4. **§10 Scan rules**: ScanRef `@scan:<id>` scalar token, dict-leaf ban, scans don't span jobs.
5. **§11 Managed parameters**: UI read-only policy.
6. **§12 Type contract**: A-class / B-class key classification, writer contract.
7. **§13 RELAX audit**: Structure transformer semantics, QC strong-chain boundary, missing structure = hard error.
8. **§14 LAMMPS integration**: potential_map SSOT, fingerprint includes potentials.
9. **§18 API layering**: Three-layer model, Utils policy, H9 filesystem access control.
10. **§19 Kernel dependencies**: Seven-domain model, reverse import ban, meta-only reading.

**Semantic updates**:
- Step type section (§7) aligned with GEN_SPEC_CONSTITUTION; old "StepTypeRegistry centralization" narrative removed.
- SSOT (§2) explicitly names `calculation.yaml` + `step.yaml` (not `step.yml` / `calc.yml`).
- Identity (§6) aligned with ULID-only law: `id`, `calc_id`, `step_id` banned.
- Species/pseudo (§9) aligned with project-run species_map SSOT.

**Deleted/folded old sections**:
- Old §10 (full ParamSpace ~400 lines) → thinned to §8 (core constraints); details moved to `PARAMSPACE_SPEC.md`.
- Old §11-14 → folded into corresponding new sections or migrated to governance specs.
- Old revision history list (~200 lines) → deleted; only v2.0+ summaries retained.
