# IR, Step, and Engine Generalization v0 Charter

**Version**: 0.0  
**Status**: Design Freeze Document  
**Date**: 2025-01-XX  
**Purpose**: Freeze v0 targets for parameter generalization (Preset → IR → step.yaml), step generalization (physical step taxonomy), and engine generalization (execution contract).

---

## Overview

This document establishes the v0 design targets for three interconnected generalization efforts organized around **two parallel intent → materialization pipelines**:

### Architecture: Two Parallel Pipelines

**1. Parameter Pipeline**:
- Preset (physical intent, subjective) → IR parameters (physical quantities, objective, unitful, engine-agnostic) → Engine-specific parameters (step.yaml, SSOT)

**2. Workflow Pipeline**:
- Workflow (physical intent) → Generalized Steps (physical operations, engine-agnostic) → Engine-specific Steps (step.yaml, executable, SSOT)

**Critical Rule**: Only the engine-specific layer is written to disk and executed.

### v0 Scope

1. **Parameter Generalization**: Introduce an Intermediate Representation (IR) layer as a minimal rename/indirection layer that mediates between ParamSpace and QE parameter keys. IR is QE-equivalent in v0 (mostly same names) and exists ONLY to mediate ParamSpace ↔ QE parameter keys. IR is NOT directly exposed to users in v0 (no Jupyter/API migration); it is an internal mediation layer.

2. **Step Generalization**: Define minimal physical step taxonomy separating Generalized Steps (engine-agnostic, not written to disk) from Engine-specific Steps (written to step.yaml, executed). Workflow materialization produces engine-specific steps from generalized steps.

3. **Engine Generalization**: Establish minimal execution contract where engines translate IR → engine-specific parameters and execute engine-specific steps. v0 MUST NOT refactor QE/Wannier execution paths.

**Non-Goals for v0**: Full multi-engine support, generalized artifact contracts, unit-system UI, universal DFT language, user-facing IR editing, IR API exposure, Ry↔eV conversion, semantic refactoring of ParamSpace (e.g., spin_mode/soc normalization), central engine registry refactoring, engine_id introduction (deferred unless strictly necessary).

---

## Non-Negotiable Principles

These principles must be respected in all v0 implementations and future evolution:

### 1. step.yaml is the ONLY on-disk SSOT ("machine code") for execution.

- Execution consumes step.yaml only.
- For QE, step.yaml ⇄ *.in is a unique, deterministic round-trip mapping:
  - step.yaml is the structured truth; *.in is the QE-consumed text.
- Preset/IR are NOT SSOT and are NOT persisted as execution truth.
- Preset/IR must NOT be written into step.yaml.
- Any provenance about preset/IR belongs to history/journal only (not step files).

### 2. There are EXACTLY three user-facing tiers:

**A) Preset** = fuzzy intent (subjective, strategy-like bundles, e.g. precision).  
**B) IR** = textbook physical knobs (deterministic, named, independent as physics).  
**C) Engine-specific params** = full machine code (expert mode; user assumes responsibility).

### 3. ParamSpace logic MUST NOT be rewritten.

- ParamSpace is matrix-based and mathematically reversible today.
- It contains static/dynamic/oracle entries, wildcard, not-applicable, step applicability, etc.
- In v0, the ONLY allowed change is: replace dimension-2 keys from QE-parameter keys to IR-parameter keys (through an explicit mapping table).
- You must NOT assume ir_key == qe_key even if they look identical; v0 still requires an explicit mapping table.
- v0 does NOT introduce spin_mode ("none/collinear/noncollinear") or soc normalization.
- Keep current QE-equivalent keys (nspin/noncolin/lspinorb etc.) as IR keys.
- Any future semantic refactor (spin_mode + soc) must be explicitly deferred to a separate PR.

### 4. IR is a physics layer. It must NOT include engine-specific implementation details.

- IR parameter definitions must NOT embed qe_key.
- qe_key belongs to an IR↔QE adapter layer, not to IR itself.
- IR keys fully reuse QE key semantics in v0 (mostly the same names), to minimize changes and guarantee round-trip.
- IR is NOT directly exposed to users in v0 (no Jupyter/API migration); it is an internal mediation layer for ParamSpace and QE.

---

## Definitions

**Preset**: A high-level, fuzzy intent that bundles multiple IR parameters into a strategy-like selection (e.g., `MagnetismOption.COLLINEAR_LSDA`, `PrecisionOption.MED`). Presets are runtime-only concepts that are never persisted. Presets are detected from step.yaml or set by users, then compiled into IR parameters via ParamSpace.

**IR (Intermediate Representation)**: A minimal rename/indirection layer that mediates between ParamSpace and engine-specific parameter keys. In v0, IR is QE-equivalent (mostly same names as QE keys) and exists ONLY to mediate ParamSpace ↔ QE parameter keys. IR parameters are physics-driven with stable names, units, and physical meaning. IR is NOT directly exposed to users in v0 (no user-facing editing or API); it is an internal mediation layer. IR is NOT persisted as SSOT for execution.

**step.yaml**: The on-disk Single Source of Truth (SSOT) for execution. Contains engine-specific parameters (e.g., QE namelist parameters) in a structured YAML format. Execution consumes step.yaml directly; presets and IR are derived from step.yaml (detection) or compiled into step.yaml (application).

**ParamSpace**: A mathematically reversible matrix-based system for mapping preset intents (dimension 1: rows/profiles) to IR parameters (dimension 2: columns/keys) with cell types (VALUE, NOT_APPLICABLE, WILDCARD). Defined in `src/quantumvitas/presets/paramspace.py`. **ParamSpace operates ONLY on IR keys**; it does NOT perform engine translation.

**IR↔QE Adapter**: A mechanical mapping layer that converts IR parameter names to QE parameter names (module/section/key). In v0, IR base units align with QE (Ry, Bohr), so no unit conversion is performed. This layer is explicitly engine-specific and separate from the IR definition itself. **IR→QE mapping MUST live in a QE-specific adapter/compiler layer, NOT inside ParamSpace**.

**Engine Backend**: The engine-specific implementation (QE, PySCF, Wannier90) that materializes inputs from step.yaml, executes steps, and produces artifacts.

**Generalized Step**: A physical operation (e.g., SCF, NSCF, Wannierization) that is engine-agnostic. Used ONLY by workflow definitions. Not written to disk.

**Engine-Specific Step**: The existing step types (qe_scf, qe_nscf, w90_run, pyscf_xxx, etc.). Each maps to a unique executable and engine. These are the ONLY steps written to step.yaml and executed.

**Workflow**: An ordered list of generalized steps. Workflow declares one or more valid materialization mappings (e.g., generalized workflow → qe + wannier90). Materialization produces an ordered list of engine-specific steps.

**Session-Fast**: Optimization where a Python-library engine (e.g., PySCF) can maintain a long-lived worker process within a single calculation to avoid repeated import/initialization overhead.

**Session-Restartable**: Guarantee that correctness depends on on-disk artifacts (logs, checkpoints, summary files) rather than in-memory state. A user can close the app and resume a calculation later using previous step outputs.

---

## Section A: Parameter Pipeline (Preset → IR → Engine-Specific Parameters)

**Architecture**: Two parallel intent → materialization pipelines

1. **Parameter Pipeline**: Preset (physical intent, subjective) → IR parameters (physical quantities, objective, unitful, engine-agnostic) → Engine-specific parameters (step.yaml, SSOT)
2. **Workflow Pipeline**: Workflow (physical intent) → Generalized Steps (physical operations, engine-agnostic) → Engine-specific Steps (step.yaml, executable, SSOT)

Only the engine-specific layer is written to disk and executed.

### A.1 Three Tier Definitions (Parameter Pipeline)

#### Preset Tier

**What it is**:
- High-level, subjective intent bundles (e.g., "high precision", "collinear magnetism")
- Strategy-like selections that group multiple IR parameters
- Defined in `src/quantumvitas/presets/dimensions.py` as enums (`MagnetismOption`, `PrecisionOption`, `OccupationsSchemeOption`, `ConvergenceOption`)

**What it can contain**:
- Named enum values that map to ParamSpace profiles (e.g., `MagnetismOption.COLLINEAR_LSDA` → "COL" profile)
- Multiple preset dimensions per calculation (magnetism, precision, occupations_scheme, convergence)

**What it cannot contain**:
- Engine-specific parameter names (e.g., `nspin`, `ecutwfc`)
- Low-level implementation details
- Persistent state (presets are runtime-only, never persisted)

**Storage**: Presets are NOT persisted in step.yaml. They are:
- Computed from step.yaml via detection (`src/quantumvitas/presets/detector.py`)
- Recorded in history/provenance metadata only
- Compiled into step.yaml when applied by users

---

#### IR Tier

**What it is**:
- Deterministic physical knobs with stable names, units, and physical meaning
- In v0, IR is QE-equivalent (mostly same names as QE keys, e.g., `ecutwfc`, `nspin`)
- Minimal rename/indirection layer that mediates ParamSpace ↔ QE parameter keys

**What it can contain**:
- Named IR parameters with physical dimensions (Energy, Length, Dimensionless, Bool, Enum, Integer)
- IR base units (Energy=Ry, Length=Bohr for v0)
- Physical meaning descriptions derived from QE metadata but IR-owned

**What it cannot contain**:
- Engine-specific parameter names (e.g., `ecutwfc`, `nspin`)
- Engine identifiers (`qe_key`, `qe_section`)
- Implementation details (mixing algorithms, diagonalization methods are engine-specific)

**Storage**: IR parameters are NOT persisted in step.yaml. Any provenance about IR belongs to history/journal only (not step files).

**User Channel**: In v0, IR is NOT directly exposed to users. There is no user-facing IR editing or IR API in v0. IR is an internal mediation layer for ParamSpace and QE only.

---

#### step.yaml Tier (Engine-Specific Parameters)

**What it is**:
- Engine-specific "machine code" in structured YAML format
- Single Source of Truth (SSOT) for execution
- Contains engine-specific parameters (e.g., QE namelist parameters: `SYSTEM.nspin`, `SYSTEM.ecutwfc`)

**What it can contain**:
- Engine-specific parameter names and values (QE namelists, cards)
- `engine_id` field specifying which engine to use (e.g., "qe", "pyscf")
- Structure references, pseudopotential mappings, input/output paths

**What it cannot contain**:
- IR parameter names (IR is not persisted in step.yaml)
- Preset enum values (presets are not persisted in step.yaml)

**Storage**: Persisted in `steps/{step_id}.step.yaml`. Authoritative for execution.

**Location**: Defined in `src/quantumvitas/calculation/structure_steps.py` as `StructureStepSpec`.

**Round-Trip Uniqueness (QE)**: For QE, step.yaml ⇄ `*.in` is a unique, deterministic round-trip mapping:
- `step.yaml` → `*.in`: `src/quantumvitas/io/generator/qe_generator.py` (`QEInputGenerator`)
- `*.in` → `step.yaml`: `src/quantumvitas/io/parser/qe_parser.py` (import functionality)
- This uniqueness must be documented and tested in v0 Phase 2.

---

### A.2 IR v0 Scope

#### IR Parameters Required by Existing Presets

IR v0 MUST include all IR parameters required by the four existing preset dimensions:

**Magnetism** (`src/quantumvitas/presets/paramspace.py:545-634`):
- `nspin` (QE-equivalent; maps to QE `SYSTEM.nspin`)
- `noncolin` (QE-equivalent; maps to QE `SYSTEM.noncolin`)
- `lspinorb` (QE-equivalent; maps to QE `SYSTEM.lspinorb`)

**OccupationsScheme** (`src/quantumvitas/presets/paramspace.py:460-526`):
- `occupations` (QE-equivalent; maps to QE `SYSTEM.occupations`)
- `smearing` (QE-equivalent; maps to QE `SYSTEM.smearing`)
- `degauss` (QE-equivalent; maps to QE `SYSTEM.degauss`)

**Precision** (`src/quantumvitas/presets/paramspace.py:652-727`):
- `ecutwfc` (QE-equivalent; maps to QE `SYSTEM.ecutwfc`)
- `ecutrho` (QE-equivalent; maps to QE `SYSTEM.ecutrho`)
- `conv_thr` (QE-equivalent; maps to QE `ELECTRONS.conv_thr`)
- `K_POINTS` (QE-equivalent card; maps to QE `cards.K_POINTS`)

**Convergence** (`src/quantumvitas/presets/paramspace.py:829-936`):
- `mixing_beta` (QE-equivalent; maps to QE `ELECTRONS.mixing_beta`)
- `electron_maxstep` (QE-equivalent; maps to QE `ELECTRONS.electron_maxstep`)
- `mixing_mode` (QE-equivalent; maps to QE `ELECTRONS.mixing_mode`)
- `mixing_ndim` (QE-equivalent; maps to QE `ELECTRONS.mixing_ndim`)
- `diagonalization` (QE-equivalent; maps to QE `ELECTRONS.diagonalization`)

**Total from presets**: 15 IR parameters.

#### Low-Hanging IR Additions (v0)

Additionally, include ONLY the following low-hanging IR additions:

- `nbnd` (Number of electronic bands)
- `nosym` (Disable symmetry)
- `noinv` (Disable time-reversal symmetry)

**Rationale**: These are commonly user-edited physical knobs that are not currently controlled by presets but are straightforward physics concepts.

#### Explicitly Excluded from IR v0

The following are explicitly excluded and must NOT appear in IR v0:

- `restart_mode` (execution policy, not physics)
- `tstress` / `tprnfor` (output verbosity, not physics)
- `outdir` / `prefix` (I/O paths, execution mechanics)
- `pseudo_dir` (resource paths, execution mechanics)
- `startingpot` / `startingwfc` (initialization strategy, execution mechanics)

**Rationale**: IR is a physics layer. Execution policies, verbosity flags, I/O paths, and initialization strategies belong to engine-specific parameters, not IR.

---

### A.3 IR Parameter Definition Format (IR Layer Only)

For each IR parameter in v0, define:

**ir_key** (canonical stable name):
- In v0, IR keys fully reuse QE key semantics (mostly the same names) to minimize changes and guarantee round-trip
- QE-equivalent names (e.g., `ecutwfc`, `nspin`, `conv_thr`, `mixing_beta`)
- Examples: `ecutwfc`, `nspin`, `conv_thr`, `mixing_beta`, `occupations`

**physical meaning** (1–2 sentences):
- Clear physical description independent of engine
- Example: "Kinetic energy cutoff for plane-wave expansion of wavefunctions (basis set quality)"

**dimension** (physical dimension):
- Energy (e.g., `ecutwfc`, `conv_thr`)
- Length (e.g., lattice parameters; not in v0 scope)
- Dimensionless (e.g., `nspin`, `mixing_beta`)
- Bool (e.g., `noncolin`, `nosym`)
- Enum (e.g., `occupations`, `diagonalization`)
- Integer (e.g., `nbnd`, `electron_maxstep`)
- Struct (e.g., `K_POINTS` is a structured card)

**IR base unit** (for v0):
- Energy: Ry (Rydberg) - aligns with QE for v0 (no conversion)
- Length: Bohr - aligns with QE for v0 (no conversion)
- Do NOT introduce Ry↔eV conversion or any unit system in v0
- NOTE: Structure uses Angstrom elsewhere (`src/quantumvitas/io/structure_io.py`); out of scope for IR v0

**type** (Python type):
- `float` (energy parameters, dimensionless ratios)
- `int` (counts, mesh divisions)
- `bool` (flags)
- `str` (enums, string options)
- `dict` (structured cards like `kpoint_mesh`)

**comment/docs text**:
- Can be copied from QE metadata initially (`src/quantumvitas/data/qe_module_parameters.json`)
- Is IR-owned (may diverge from QE descriptions as IR evolves)
- Must NOT reference QE-specific terminology (e.g., "namelist", "Fortran")

**IMPORTANT**: IR definitions MUST NOT contain:
- `qe_key` (belongs to IR↔QE adapter)
- Engine identifiers (e.g., "QE", "pw.x")
- QE-specific terminology (e.g., "namelist", "SYSTEM section")

**Example IR Parameter Definition**:
```
ir_key: ecutwfc
physical_meaning: "Kinetic energy cutoff for plane-wave expansion of wavefunctions. Determines basis set quality and computational cost."
dimension: Energy
ir_base_unit: Ry
type: float
comment: "Higher values improve accuracy but increase computational cost. Typical range: 20-100 Ry for norm-conserving pseudopotentials."
```

---

### A.4 IR↔QE Adapter Layer (Separate from IR and ParamSpace)

**Location**: `src/quantumvitas/ir/backends/qe/mapping.py` or QE engine adapter/compiler (conceptual; implementation in v0 Phase 1)

**Purpose**: Mechanical mapping between IR parameter names and QE parameter names.

**Critical Architecture**: IR→QE mapping MUST live in a QE-specific adapter/compiler layer, NOT inside ParamSpace. ParamSpace operates ONLY on IR keys and does NOT perform engine translation.

**Structure** (concept only; no implementation details):

**IR → QE Mapping** (for compilation):
- `ir_key` → `(qe_module, qe_section, qe_key)`
- Example: `ecutwfc` → `("pw", "SYSTEM", "ecutwfc")`
- In v0, IR base units align with QE (Ry, Bohr), so no unit conversion is performed

**QE → IR Mapping** (for detection):
- `(qe_module, qe_section, qe_key)` → `ir_key`
- Example: `("pw", "SYSTEM", "ecutwfc")` → `ecutwfc`
- In v0, IR base units align with QE (Ry, Bohr), so no unit conversion is performed

**Unit Alignment (v0)**:
- IR base units align with QE in v0 (Energy=Ry, Length=Bohr)
- Do NOT introduce Ry↔eV conversion or any unit system in v0
- Units are recorded explicitly in the mapping table to keep the boundary clear

**Special Cases**:
- `K_POINTS` (IR) ↔ `cards.K_POINTS` (QE card, not namelist parameter)
  - v0 canonicalization: Represent K_POINTS in 4 modes: `gamma` / `automatic` / `crystal(list)` / `crystal_b(path endpoints + interpolation count)`
  - Other QE modes (tpiba, etc.) are converted to crystal form (equivalent)
  - This is a statement of representation/normalization, not an implementation plan
- `nbnd` (IR) ↔ `SYSTEM.nbnd` (QE integer)
- `nosym` (IR) ↔ `SYSTEM.nosym` (QE boolean)
- `noinv` (IR) ↔ `SYSTEM.noinv` (QE boolean)

**This layer is explicitly engine-specific** and must be separated from IR definitions. Multiple engines (QE, PySCF, etc.) will have separate IR↔Engine adapters in the future.

---

### A.5 Round-Trip and "No Double Truth"

#### Intended Behavior

**Execution Truth**: `step.yaml` `parameters:` section is the only SSOT for execution.

**Parameter Pipeline Flow**:
1. **Preset → IR**: ParamSpace compiles preset options to IR parameters (operates on IR keys only)
2. **IR → Engine-Specific**: IR↔QE adapter (in QE engine layer) translates IR parameters to QE parameters
3. **Engine-Specific → step.yaml**: QE parameters written to `step.yaml["parameters"]` as SSOT

**Preset/IR Derivation** (Detection - Reverse Flow):
- Presets and IR parameters may be derived from `step.yaml` via detector (`src/quantumvitas/presets/detector.py`)
- Detection flow: QE parameters (step.yaml) → IR↔QE adapter → IR parameters → ParamSpace matching → preset enum
- Derived values are recorded in history/journal only (NOT in step.yaml)
- Detection uses ParamSpace matching with IR keys (after v0 Phase 1 migration)

**Preset Compilation** (Application - Forward Flow):
- If the user edits presets, the system compiles them into `step.yaml` immediately
- Compilation flow: Preset enum → ParamSpace (IR keys) → IR parameters → IR↔QE adapter → QE parameters → step.yaml
- **ParamSpace does NOT perform engine translation**; that happens in the IR↔QE adapter layer
- `step.yaml` is updated atomically; presets/IR are not persisted separately
- In v0, IR is NOT directly exposed to users; preset editing compiles through IR internally

**Expert Edits** (Direct step.yaml editing):
- If the user edits engine-specific parameters directly in `step.yaml` (expert mode), detector may fail to match any preset profile
- In that case, preset/IR derivation returns `CUSTOM` (defined in `src/quantumvitas/presets/dimensions.py`)
- Do NOT guess or infer presets/IR from non-matching parameters

**No Double Truth Guarantee**:
- `step.yaml` `parameters:` is the ONLY authoritative source for execution
- Presets are never persisted; they are computed on-demand from `step.yaml`
- IR is never persisted; it is an internal mediation layer only
- Any provenance about preset/IR belongs to history/journal only (not step files)

---

## Section B: Workflow Pipeline (Workflow → Generalized Steps → Engine-Specific Steps)

### B.0 Architecture: Two Distinct Step Layers

There are TWO distinct step layers:

**Generalized Step**:
- Represents a physical operation (SCF, NSCF, Wannierization, etc.)
- Engine-agnostic
- Used ONLY by workflow definitions
- Not written to disk

**Engine-Specific Step**:
- The existing step types (qe_scf, qe_nscf, w90_run, pyscf_xxx, etc.)
- Each maps to a unique executable and engine
- These are the ONLY steps written to step.yaml and executed

**Workflow**:
- Workflow is an ordered list of generalized steps
- Workflow declares one or more valid materialization mappings (e.g., generalized workflow → qe + wannier90)
- Materialization produces an ordered list of engine-specific steps

### B.1 Step Generalization (Physical Step Taxonomy)

### B.1 Minimal Generalized Physical Step Taxonomy

**Current Step Types** (from `src/quantumvitas/calculation/types.py:StepType`):

Existing step types that v0 must support:
- `SCF` (Self-Consistent Field)
- `NSCF` (Non-Self-Consistent Field)
- `DOS` (Density of States)
- `BANDS_PW` (Band structure via pw.x)
- `BANDS` (Band structure via bands.x)
- `PH` (Phonon calculation)
- `RELAX` (Ionic relaxation)
- `VC_RELAX` (Variable-cell relaxation)
- `W90_PREPROC` (Wannier90 preprocessing)
- `PW2WANNIER90` (pw2wannier90)
- `W90_RUN` (Wannier90 main run)
- `PYSCF_SCF` (PySCF single-point)

**v0 Minimal Taxonomy** (physical step categories):

For v0, do NOT merge step categories. Separate step types remain distinct:

1. **SCF** (Self-Consistent Field):
   - Physical meaning: Ground-state electronic structure calculation
   - Includes: `SCF` only
   - Common across engines: QE (`pw.x`), PySCF (`SCF`), future VASP, ABINIT

2. **RELAX** (Ionic Relaxation):
   - Physical meaning: Structural relaxation with fixed cell
   - Includes: `RELAX` only
   - Common across engines: QE (`pw.x calculation='relax'`), future VASP, ABINIT

3. **VC_RELAX** (Variable-Cell Relaxation):
   - Physical meaning: Structural relaxation with variable cell
   - Includes: `VC_RELAX` only
   - Common across engines: QE (`pw.x calculation='vc-relax'`), future VASP, ABINIT

4. **NSCF** (Non-Self-Consistent Field):
   - Physical meaning: Fixed-potential calculation on converged charge density
   - Includes: `NSCF` only
   - Common across engines: QE (`pw.x calculation='nscf'`)

5. **BANDS** (Band Structure):
   - Physical meaning: Electronic band structure along k-path
   - Includes: `BANDS_PW`, `BANDS`
   - Engine-specific: QE uses `pw.x` or `bands.x`; other engines may use different executables

6. **DOS** (Density of States):
   - Physical meaning: Density of electronic states
   - Includes: `DOS` only
   - Engine-specific: QE uses `dos.x`; other engines may compute DOS differently

7. **WANNIER** (Wannier Functions):
   - Physical meaning: Maximally localized Wannier functions (MLWF)
   - Includes: `W90_PREPROC`, `PW2WANNIER90`, `W90_RUN`
   - Engine-specific: Wannier90 workflow (may be used with QE, VASP, ABINIT)

**v0 Scope**: Support the above step types as distinct categories. Engine-specific step types (e.g., `PYSCF_SCF`) map to the closest physical category (`SCF`).

**Future Work**: Full generalization where step definitions are engine-agnostic and engine binding happens at runtime.

---

### B.2 Engine Binding

**Generalized Step Definitions Must Be Engine-Free**:
- Step type definitions (SCF, NSCF, BANDS, etc.) must not reference specific engines
- Physical step taxonomy is engine-agnostic

**Engine Implementation Selection**:
- Engine is chosen via a registry/capabilities mapping at runtime
- `step.yaml` must contain `engine_id` field (e.g., "qe", "pyscf") as part of machine code
- Engine registry maps `(engine_id, step_type)` → executable/runner entrypoint

**Current Implementation**:
- Engine selection: `src/quantumvitas/core/engines/qe.py` (`QuantumEspressoEngine`)
- Executable mapping: `QuantumEspressoEngine.EXECUTABLE_MAP` (maps step types to QE executables)
- Step type → executable binding: `src/quantumvitas/core/engines/qe.py:build_command()`

**v0 Requirement**:
- Document that `engine_id` in `step.yaml` selects the engine backend
- Generalized step types (SCF, NSCF, etc.) are engine-agnostic
- Engine-specific executable/runner mapping is encapsulated in engine backend

**Future Work**: Full engine capability registry where engines declare which step types they support.

---

### B.3 Requires/Produces (Minimal, Acknowledge Limitations)

#### Current Reality (QE File-Based Engine)

For file-based engines like QE, many steps read/write within a shared `outdir`:
- Multiple steps (SCF → NSCF → DOS) share the same `outdir` (e.g., `calculations/{calc_id}/raw/`)
- SCF produces `*.wfc`, `*.charge-density` in `outdir`
- NSCF reads from `outdir` (restart from SCF)
- DOS reads from `outdir` (requires NSCF outputs)
- **Granularity**: "requires/produces" may not be perfectly granular in v0

**Current Step Completion Detection** (`src/quantumvitas/calculation/step_done.py`):
- Determines if a step is "done" based on output file existence and content markers
- For QE: checks for "JOB DONE" in primary output file
- For Wannier90: checks for `.wout` file existence
- **Location**: `src/quantumvitas/calculation/step_done.py:is_step_done()`

#### v0 Approach

**Optional Generalized Requires/Produces**:
- Step generalized requires/produces is OPTIONAL metadata only and is NOT authoritative for "done" in v0
- You MAY define a generalized requires/produces concept as optional metadata in step definitions
- Example: `SCF` produces `charge_density`, `wavefunctions`; `NSCF` requires `charge_density`
- **But**: This must NOT be used as the authoritative "done" condition across engines in v0

**Engine-Specific Success Criteria Remain Engine-Specific**:
- In v0, success/done remains engine-specific
- QE: File existence + "JOB DONE" marker (`src/quantumvitas/calculation/step_done.py`)
- PySCF: `results.json` + checkpoint files (if implemented)
- Wannier90: `.wout` file existence
- **v0**: Engine-specific success criteria remain engine-specific

**What v0 Will Use**:
- Current implementation in `src/quantumvitas/calculation/step_done.py` determines step completion
- For QE: Primary output file existence + "JOB DONE" marker
- For PySCF: `results.json` existence (current implementation in `src/quantumvitas/engine/pyscf.py`)
- For Wannier90: `.wout` file existence

**What Remains Future Work**:
- Generalized artifact contracts across all engines
- Perfect granularity of requires/produces (file-based engines share `outdir`)
- Cross-engine artifact dependency tracking

---

## Section C: Engine Layer (IR → Engine-Specific Parameters, Execution)

**Architecture**: Engines are responsible for:
1. Translating IR parameters → engine-specific parameters
2. Executing engine-specific steps

**v0 Constraint**: v0 MUST NOT refactor QE or Wannier execution paths. PySCF may be redesigned first as an experimental engine adapter. Engine registry / engine_id introduction must be deferred or isolated and MUST NOT break existing QE/Wannier behavior.

### C.1 Engine Generalization (Execution Contract)

### C.1 Two Engine Execution Families

#### File-Based Executable Engines (QE/Wannier90-like)

**Characteristics**:
- Materialize input files (e.g., `*.in`) in a working directory
- Run executable via subprocess (possibly with MPI)
- Produce output files/directories in working directory
- Restart artifacts exist on disk (e.g., `*.wfc`, `*.charge-density`)

**Examples**:
- QE: `pw.x`, `bands.x`, `dos.x`, `ph.x` (via `src/quantumvitas/core/engines/qe.py`)
- Wannier90: `wannier90.x` (via `src/quantumvitas/core/engines/wannier90.py`)

**Current Implementation**:
- Input materialization: `src/quantumvitas/io/generator/qe_generator.py` (`QEInputGenerator`)
- Command building: `src/quantumvitas/core/engines/qe.py:build_command()`
- Subprocess execution: `src/quantumvitas/core/engines/qe_calculation.py:run_step()`
- Working directory: `calculations/{calc_id}/raw/` (via `src/quantumvitas/calculation/runner.py:compute_io_dir_from_calculation_model()`)

#### Python-Library Engines (PySCF-like)

**Characteristics**:
- Executed by a stable Python runner (no code generation; structured plan data)
- Can be long-lived per-calc for speed (session-fast)
- MUST flush on-disk artifacts after each step for restartability (session-restartable)
- In-memory state is cache only; correctness depends on disk artifacts

**Examples**:
- PySCF: `src/quantumvitas/engine/pyscf.py` (`PySCFEngine`)

**Current Implementation**:
- Runner: `src/quantumvitas/engines/pyscf/runner.py` (executes PySCF via subprocess)
- Communication: `job.json` → runner → `results.json` (file-based, restartable)
- Artifacts: `results.json` + `pyscf_input.py` (if generated) stored in working directory

**v0 Requirement**: Per-calc worker is minimal plan; pooling/LRU is out of scope.

---

### C.2 Minimal Shared Execution Contract

All engines must provide the following minimal set of concepts (interfaces to be defined in Phase 3):

#### materialize

**Purpose**: Prepare engine-consumable input from `step.yaml`.

**File-Based Engines** (QE):
- Input: `step.yaml` `parameters:` section
- Output: Engine input files (e.g., `*.in` for QE) written to working directory
- Implementation: `src/quantumvitas/io/generator/qe_generator.py` (`QEInputGenerator.generate()`)

**Python-Library Engines** (PySCF):
- Input: `step.yaml` `parameters:` section
- Output: Structured plan data (`job.json` for PySCF) written to working directory
- Implementation: `src/quantumvitas/engine/pyscf.py:run_step()` writes `job.json`

**v0 Requirement**: Document that materialize prepares inputs from `step.yaml`; engine-specific format.

---

#### run

**Purpose**: Execute the step.

**File-Based Engines** (QE):
- Command: Subprocess invocation (e.g., `mpirun -np 4 pw.x < input.in`)
- Outputs: stdout/stderr captured, files written to working directory
- Implementation: `src/quantumvitas/core/engines/qe_calculation.py:run_step()`

**Python-Library Engines** (PySCF):
- Command: Python runner subprocess (e.g., `python -m quantumvitas.engines.pyscf.runner`)
- Outputs: `results.json` written to working directory, stdout/stderr captured
- Implementation: `src/quantumvitas/engine/pyscf.py:run_step()` invokes runner subprocess

**v0 Requirement**: Document that run executes the step; engine-specific mechanism (subprocess vs. Python worker).

---

#### artifacts

**Purpose**: Persist per-step logs/results/checkpoints needed for session-external restart.

**File-Based Engines** (QE):
- Artifacts: Primary output file (e.g., `*.out`), restart files (e.g., `*.wfc`), logs
- Location: Working directory (e.g., `calculations/{calc_id}/raw/`)
- Detection: `src/quantumvitas/calculation/step_done.py:is_step_done()` checks for "JOB DONE"

**Python-Library Engines** (PySCF):
- Artifacts: `results.json` (summary), `pyscf_input.py` (if generated), logs
- Location: Working directory
- Detection: `results.json` existence indicates completion

**v0 Requirement**: Document that artifacts must persist for restart; engine-specific format.

---

#### parse (Optional)

**Purpose**: Engine-specific parsing to canonical analysis outputs.

**File-Based Engines** (QE):
- Parser: `src/quantumvitas/analysis/parsers.py` (`parse_scf_output_text()`)
- Output: `SCFResult` dataclass (energies, convergence, timing)

**Python-Library Engines** (PySCF):
- Parser: `results.json` → canonical analysis outputs (if implemented)

**v0 Requirement**: Parsing is optional; document that engines may provide parsers for canonical outputs.

---

### C.3 Session-Fast vs Session-Restartable

#### Session-Fast

**Definition**: Python worker can persist within a calc to avoid repeated import/init.

**Mechanism**:
- Long-lived Python worker process per calculation
- Worker reads structured plan data (`job.json`) and executes steps
- In-memory state (PySCF objects) persists across steps within the same calculation

**Benefit**: Avoids repeated `import pyscf`, initialization overhead.

**Scope**: Per-calc worker is minimal v0 plan; pooling/LRU is out of scope.

---

#### Session-Restartable

**Definition**: Correctness depends on disk artifacts; worker memory is cache only.

**Requirement**:
- After each step, MUST flush on-disk artifacts required for restart:
  - Checkpoint files (if engine supports checkpoints)
  - Summary files (e.g., `results.json` for PySCF)
  - Logs (stdout/stderr)
- In-memory state (worker cache) is NOT authoritative

**Guarantee**:
- User can close the app and resume calculation later using previous step outputs
- Worker restart reads artifacts from disk, not from memory

**Current Implementation** (PySCF):
- `src/quantumvitas/engine/pyscf.py:run_step()` writes `results.json` after each step
- Runner subprocess is invoked per step (no long-lived worker yet in v0)
- **v0**: Document session-restartable requirement; full long-lived worker implementation is future work

**Invalidation**:
- If user edits upstream `step.yaml`, worker must detect stale state
- Fingerprint/invalidation mechanism required (out of scope for v0 Phase 3 skeleton)

---

## Section D: Migration Plan (v0 Only, No Code Details)

### D.1 Phase Plan (Conceptual)

#### Phase 0: Document Current Truth Sources and Behavior (QE-Only)

**Goal**: Establish baseline without changing behavior.

**Tasks**:
- Document current QE execution pipeline (UI/CLI → daemon → parameter resolution → input materialization → command invocation → logs → output artifacts → parser → analysis → history)
- Document current step.yaml SSOT role (authoritative for execution)
- Document current QE step.yaml ⇄ `*.in` round-trip mapping (via `QEInputGenerator` and parser)
- Document current ParamSpace structure and reversibility (matrix-based, `match_profile()` / `compile_profile_patch()`)
- Document current preset detection/compilation paths (`src/quantumvitas/presets/detector.py`, `src/quantumvitas/presets/compiler.py`)

**Deliverables**: Documentation only; no code changes.

**Location**: `IR_Landing_Review.md` (existing), this charter document.

---

#### Phase 1: Introduce IR Parameter Registry + IR↔QE Adapter Layer

**Goal**: Introduce IR layer conceptually; switch ParamSpace dimension-2 keys to IR keys (mapping-driven).

**Tasks**:
- Create IR parameter registry (IR definitions only; no `qe_key` references)
  - Location: `src/quantumvitas/ir/parameters.py` (conceptual)
  - Define all 18 IR parameters (15 from presets + 3 low-hanging: `nbnd`, `nosym`, `noinv`)
- Create IR↔QE adapter layer (mechanical mapping)
  - Location: `src/quantumvitas/ir/backends/qe/mapping.py` (conceptual)
  - `IR_TO_QE_MAPPING`: `ir_key` → `(qe_module, qe_section, qe_key)`
  - `QE_TO_IR_MAPPING`: `(qe_module, qe_section, qe_key)` → `ir_key`
  - No unit conversion in v0 (IR base units align with QE)
- Switch ParamSpace dimension-2 keys from QE keys to IR keys
  - Location: `src/quantumvitas/presets/paramspace.py`
  - Replace `ParamKey.key` (QE parameter name) with IR parameter name
  - All other ParamSpace logic unchanged (matrices, cells, reversibility preserved)
- Update preset compilation/detection to use IR keys
  - Location: `src/quantumvitas/presets/compiler.py`, `src/quantumvitas/presets/detector.py`
  - YAML access layer converts IR YAML ↔ QE YAML at boundary

**Deliverables**: IR registry, IR↔QE adapter, ParamSpace uses IR keys, compilation/detection work with IR keys.

**Testing**: Round-trip tests (preset → IR → QE → IR → preset), ParamSpace reversibility tests.

---

#### Phase 2: Ensure step.yaml SSOT and QE step.yaml ⇄ *.in Uniqueness

**Goal**: Document and test that step.yaml is SSOT and QE round-trip is unique.

**Tasks**:
- Document QE step.yaml ⇄ `*.in` round-trip uniqueness
  - Location: `docs/design/qe_roundtrip_uniqueness.md` (conceptual)
  - Test: Generate `*.in` from `step.yaml`, parse back, verify equality
- Verify step.yaml SSOT enforcement
  - Ensure execution reads from `step.yaml` only (not from IR/preset)
  - Ensure IR/preset are derived from `step.yaml` (detection) or compiled into `step.yaml` (application)
- Test expert edits (direct `step.yaml` editing)
  - Verify detection returns `CUSTOM` for non-matching parameters
  - Verify no guessing or inference

**Deliverables**: Documentation, tests, SSOT enforcement verified.

**Testing**: Round-trip tests (step.yaml → *.in → step.yaml), SSOT enforcement tests, expert edit tests.

---

#### Phase 3: (Optional Skeleton) Python Runner Contract for PySCF

**Goal**: Establish Python runner contract skeleton (still step.yaml SSOT).

**Tasks**:
- Define minimal Python runner interface (conceptual)
  - `materialize`: Write `job.json` from `step.yaml`
  - `run`: Execute Python runner subprocess
  - `artifacts`: Persist `results.json` + logs
- Document session-restartable requirement
  - Artifacts must persist after each step
  - Worker memory is cache only
- Skeleton implementation (no full long-lived worker yet)
  - Current: `src/quantumvitas/engine/pyscf.py` already implements subprocess runner
  - Document that long-lived worker is future work

**Deliverables**: Runner contract documentation, skeleton implementation (if not already present).

**Testing**: Basic PySCF execution tests, artifact persistence tests.

---

### D.2 Non-Goals (Explicit)

The following are explicitly out of scope for v0:

1. **No unit-system UI**: No user-facing unit conversion UI, no unit preference settings. No Ry↔eV conversion in v0.

2. **No new "DFT universal language"**: IR is a minimal rename/indirection layer in v0, not a universal DFT language. Engine-specific details remain engine-specific.

3. **No user-facing IR editing or IR API**: IR is NOT directly exposed to users in v0 (no Jupyter/API migration); it is an internal mediation layer for ParamSpace and QE.

4. **No semantic refactoring of ParamSpace**: v0 does NOT introduce spin_mode ("none/collinear/noncollinear") or soc normalization. Keep current QE-equivalent keys (nspin/noncolin/lspinorb etc.) as IR keys. Any future semantic refactor (spin_mode + soc) must be explicitly deferred to a separate PR.

3. **No rewriting ParamSpace logic**: ParamSpace matrices, cell types, reversibility logic remain unchanged. Only dimension-2 key substitution is allowed.

5. **No attempting full conflict detection for expert engine-param edits**: If user edits `step.yaml` directly with non-matching parameters, detection returns `CUSTOM`; no guessing.

6. **No perfect generalized requires/produces semantics across all engines**: File-based engines share `outdir`; granularity is limited. Engine-specific success criteria remain engine-specific. Step generalized requires/produces is OPTIONAL metadata only and is NOT authoritative for "done" in v0.

7. **No full long-lived Python worker in v0**: Session-fast optimization (long-lived worker) is documented but not fully implemented in v0 Phase 3 (skeleton only).

8. **No engine pooling/LRU**: Per-calc worker is minimal plan; pooling/LRU is out of scope.

9. **No full multi-engine support**: v0 focuses on QE primarily; PySCF skeleton is optional. Full VASP/ABINIT support is future work.

---

## IR v0 Parameter List

Complete list of IR parameters for v0, with dimension and base unit. IR keys fully reuse QE key semantics (mostly the same names) to minimize changes and guarantee round-trip:

| IR Parameter | Dimension | IR Base Unit | Type | Physical Meaning |
|--------------|-----------|--------------|------|------------------|
| `nspin` | Dimensionless | N/A | int | Number of spin components: 1=none, 2=collinear, 4=noncollinear |
| `noncolin` | Bool | N/A | bool | Enable noncollinear magnetism (vector magnetization) |
| `lspinorb` | Bool | N/A | bool | Enable spin-orbit coupling (requires noncollinear) |
| `occupations` | Enum | N/A | str | Occupation scheme: fixed/smearing/tetrahedra |
| `smearing` | Enum | N/A | str | Smearing type: gaussian/fermi/marzari-vanderbilt |
| `degauss` | Energy | Ry | float | Smearing width for metals |
| `ecutwfc` | Energy | Ry | float | Kinetic energy cutoff for wavefunctions |
| `ecutrho` | Energy | Ry | float | Kinetic energy cutoff for charge density |
| `conv_thr` | Energy | Ry | float | SCF convergence threshold |
| `K_POINTS` | Struct | N/A | dict | K-point mesh (card: gamma/automatic/crystal/crystal_b) |
| `mixing_beta` | Dimensionless | N/A | float | SCF mixing factor (0-1) |
| `electron_maxstep` | Dimensionless | N/A | int | Maximum SCF iterations |
| `mixing_mode` | Enum | N/A | str | SCF mixing mode: plain/TF/local-TF |
| `mixing_ndim` | Dimensionless | N/A | int | SCF mixing history length |
| `diagonalization` | Enum | N/A | str | SCF diagonalization method: david/cg/rmm-davidson |
| `nbnd` | Dimensionless | N/A | int | Number of electronic bands |
| `nosym` | Bool | N/A | bool | Disable symmetry |
| `noinv` | Bool | N/A | bool | Disable time-reversal symmetry |

**Total**: 18 IR parameters (15 from presets + 3 low-hanging additions).

**Note**: In v0, IR keys are QE-equivalent (mostly same names). You must NOT assume ir_key == qe_key even if they look identical; v0 still requires an explicit mapping table (see Appendix).

---

## Repo References

Key modules and paths referenced in this charter:

**Presets**:
- `src/quantumvitas/presets/paramspace.py`: ParamSpace matrix-based system
- `src/quantumvitas/presets/spaces_registry.py`: ParamSpace registry
- `src/quantumvitas/presets/variants_registry.py`: Step-specific variants
- `src/quantumvitas/presets/dimensions.py`: Preset enum definitions
- `src/quantumvitas/presets/detector.py`: Preset detection from step.yaml
- `src/quantumvitas/presets/compiler.py`: Preset compilation to step.yaml

**QE Metadata**:
- `src/quantumvitas/data/qe_module_parameters.json`: QE parameter metadata (types, defaults, descriptions)

**Steps**:
- `src/quantumvitas/calculation/types.py`: `StepType` enum
- `src/quantumvitas/calculation/structure_steps.py`: `StructureStepSpec` (step.yaml structure)
- `src/quantumvitas/calculation/step_done.py`: Step completion detection

**Engines**:
- `src/quantumvitas/core/engines/qe.py`: Quantum ESPRESSO engine
- `src/quantumvitas/core/engines/qe_calculation.py`: QE execution runner
- `src/quantumvitas/engine/pyscf.py`: PySCF engine adapter
- `src/quantumvitas/engines/pyscf/runner.py`: PySCF runner subprocess

**I/O**:
- `src/quantumvitas/io/generator/qe_generator.py`: QE input file generation (step.yaml → *.in)
- `src/quantumvitas/io/parser/qe_parser.py`: QE input parsing (*.in → step.yaml)

**Analysis**:
- `src/quantumvitas/analysis/parsers.py`: QE output parsing

**Execution**:
- `src/quantumvitas/calculation/runner.py`: Calculation execution orchestration
- `src/quantumvitas/calculation/manifest.py`: Incremental run tracking

---

## Appendix: IR↔QE Adapter Mapping (v0)

Explicit mapping table between IR parameter keys and QE parameter keys. Even if ir_key == qe_key, they are listed explicitly.

| ir_key | qe_key | qe_section/card | qe_unit | Notes |
|--------|--------|-----------------|---------|-------|
| `nspin` | `nspin` | `SYSTEM` | N/A | Integer: 1=none, 2=collinear, 4=noncollinear |
| `noncolin` | `noncolin` | `SYSTEM` | N/A | Boolean flag |
| `lspinorb` | `lspinorb` | `SYSTEM` | N/A | Boolean flag, requires noncolin=true |
| `occupations` | `occupations` | `SYSTEM` | N/A | Enum: fixed/smearing/tetrahedra |
| `smearing` | `smearing` | `SYSTEM` | N/A | Enum: gaussian/fermi/marzari-vanderbilt |
| `degauss` | `degauss` | `SYSTEM` | Ry | Energy parameter |
| `ecutwfc` | `ecutwfc` | `SYSTEM` | Ry | Energy parameter |
| `ecutrho` | `ecutrho` | `SYSTEM` | Ry | Energy parameter |
| `conv_thr` | `conv_thr` | `ELECTRONS` | Ry | Energy parameter |
| `K_POINTS` | `K_POINTS` | `cards` | N/A | Card (not namelist). v0 canonicalization: gamma/automatic/crystal(list)/crystal_b(path) |
| `mixing_beta` | `mixing_beta` | `ELECTRONS` | N/A | Dimensionless (0-1) |
| `electron_maxstep` | `electron_maxstep` | `ELECTRONS` | N/A | Integer |
| `mixing_mode` | `mixing_mode` | `ELECTRONS` | N/A | Enum: plain/TF/local-TF |
| `mixing_ndim` | `mixing_ndim` | `ELECTRONS` | N/A | Integer |
| `diagonalization` | `diagonalization` | `ELECTRONS` | N/A | Enum: david/cg/rmm-davidson/etc |
| `nbnd` | `nbnd` | `SYSTEM` | N/A | Integer (low-hanging addition) |
| `nosym` | `nosym` | `SYSTEM` | N/A | Boolean flag (low-hanging addition) |
| `noinv` | `noinv` | `SYSTEM` | N/A | Boolean flag (low-hanging addition) |

**Mapping Notes**:
- All IR base units align with QE in v0 (Energy=Ry, Length=Bohr). No unit conversion is performed.
- `K_POINTS` is a card (not a namelist parameter), handled separately in YAML access layer.
- Even when ir_key == qe_key (which is common in v0), the mapping table is explicit to maintain the boundary.

---

## Conclusion

This charter freezes v0 targets for parameter, step, and engine generalization organized around **two parallel intent → materialization pipelines**.

### Architecture Summary

**Two Parallel Pipelines**:
1. **Parameter Pipeline**: Preset → IR parameters → Engine-specific parameters (step.yaml, SSOT)
2. **Workflow Pipeline**: Workflow → Generalized Steps → Engine-specific Steps (step.yaml, executable, SSOT)

**Critical Rule**: Only engine-specific layer is written to disk and executed.

### v0 Deliverables

1. **IR as a minimal rename/indirection layer** with 18 QE-equivalent parameters, mediating ParamSpace ↔ QE parameter keys
2. **ParamSpace operates ONLY on IR keys**; IR→QE translation happens in QE engine adapter (NOT in ParamSpace)
3. **Three-tier parameter model** (Preset → IR → Engine-specific) with step.yaml as SSOT
4. **ParamSpace preservation** (only dimension-2 key substitution allowed; no semantic changes like spin_mode/soc normalization)
5. **Step layer separation** (Generalized Steps vs Engine-specific Steps) - design-level scaffolding in v0
6. **Engine layer** (IR → engine-specific params translation, execution) - v0 MUST NOT refactor QE/Wannier paths

**v0 Scope Restrictions**:
- IR is NOT directly exposed to users (no Jupyter/API migration)
- No Ry↔eV conversion or unit system in v0
- No persistence of IR/preset in step.yaml (history/journal only)
- No semantic refactoring of ParamSpace (keep nspin/noncolin/lspinorb as-is)
- No central engine registry refactoring (QE/Wannier paths untouched)
- No engine_id introduction (deferred unless strictly necessary for PySCF experimental adapter)
- Step/Engine parts are design-level scaffolding unless strictly necessary (IR landing is primary deliverable)

v0 focuses on QE primarily, with PySCF as an optional skeleton. Full multi-engine support, generalized artifact contracts, session-fast optimizations, user-facing IR editing, and semantic refactoring (spin_mode/soc) are explicitly deferred to future work.

---

## Doc Patch Summary

**What Changed**:
- Clarified that IR is a minimal rename/indirection layer (QE-equivalent) that exists ONLY to mediate ParamSpace ↔ QE parameter keys
- Removed all references to IR persistence in step.yaml (IR belongs to history/journal only)
- Removed Ry↔eV conversion mentions (IR base units align with QE in v0, no conversion)
- Removed IR as user-editable public API (IR is internal mediation layer in v0)
- Renamed IR keys to be QE-equivalent (ecutwfc, nspin, conv_thr, etc. instead of wavefunction_cutoff, spin_polarization, scf_threshold)
- Added explicit "no user channel" statement (IR NOT exposed to users in v0)
- Updated K_POINTS section to specify v0 canonicalization (4 modes: gamma/automatic/crystal/crystal_b)
- Updated step taxonomy to NOT merge categories (separate SCF, RELAX, VC_RELAX, NSCF, DOS, BANDS, WANNIER)
- Added Appendix with explicit IR↔QE adapter mapping table (even when ir_key == qe_key)

**What Was Explicitly Deferred to Later PRs**:
- Semantic refactoring of ParamSpace (spin_mode "none/collinear/noncollinear" + soc normalization)
- User-facing IR editing or IR API exposure
- Ry↔eV conversion or unit system UI
- Full long-lived Python worker implementation (skeleton only in v0 Phase 3)

---

**End of Charter**

