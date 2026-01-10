# IR Landing Review: Physical Intent IR Layer Design

**Review Date**: 2025-01-XX  
**Purpose**: Deep code review and migration plan for introducing engine-agnostic Physical Intent IR layer  
**Status**: Review Complete - Plan Ready

---

## Executive Summary

This document provides a comprehensive review of the QMatSuite codebase to support introduction of a Physical Intent IR (Intermediate Representation) layer. The IR will serve as an engine-agnostic abstraction between user intent (presets) and engine-specific parameter compilation (currently QE-only, future PySCF, etc.).

**Key Findings**:
- Current system: Presets directly compile to QE parameters via `presets/compiler.py`
- QE parameter JSON: Located at `src/quantumvitas/data/qe_module_parameters.json` (schema v3, 954 parameters)
- Presets: 4 dimensions (magnetism, occupations_scheme, precision, convergence) mapping to ~15 QE parameters
- Steps: QE-specific, stored in `*.step.yaml` with parameters/cards structure
- Incremental runs: Use `step_sha` (hash of step YAML with meta stripped) to detect changes

**Migration Strategy**: Phased approach preserving backward compatibility, starting with read-only IR derivation (Phase 0).

---

## A) Repository Map

### A.1 Presets Location

**Primary Location**: `src/quantumvitas/presets/`

**Key Files**:
- `dimensions.py`: Dimension enums (MagnetismOption, OccupationsSchemeOption, PrecisionOption, ConvergenceOption)
- `compiler.py`: Forward compilation (preset options → QE parameters)
- `detector.py`: Reverse detection (QE parameters → preset options)
- `integration.py`: Preset application to steps (uses StepDoc for mutation)
- `catalog.py`: UI catalog generation from variants registry
- `spaces_registry.py`: ParamSpace registry (single source of truth for dimension definitions)
- `variants_registry.py`: Variant registry (which presets apply to which step types)

**How Presets Work**:
1. User selects preset options (e.g., `{"magnetism": "collinear_lsda"}`)
2. `compiler.py::compile_presets()` → compiles to QE SYSTEM params (e.g., `{"SYSTEM": {"nspin": 2}}`)
3. `integration.py::apply_presets_to_step()` → patches step YAML via StepDoc
4. Detector B (`detector.py`) can reverse-detect preset from step params

### A.2 Steps/Workflow Location

**Steps**: `src/quantumvitas/calculation/`
- `step.py`: Step dataclass (meta, input_file, step_type, options)
- `step_defaults.py`: Default parameters per step type (hardcoded dicts)
- `types.py`: StepType enum (SCF, NSCF, DOS, BANDS_PW, BANDS, etc.)
- `structure_steps.py`: StructureStepSpec (step YAML representation)

**Workflows**: `src/quantumvitas/workflow/`
- `templates.py`: WorkflowTemplate definitions (scf, dos, bands, etc.) with step sequences
- `step_factory.py`: Step creation with Journal integration
- `registry.py`: StepTypeRegistry (centralized step type semantics)

**Step Storage**: `calculations/{calc_id}/steps/*.step.yaml`
- Structure: `{meta, step_type, parameters: {SYSTEM: {...}, ...}, cards: {K_POINTS: {...}}, ...}`
- YAML I/O: Via `StepDoc` (`src/quantumvitas/core/yamldoc.py`) with mutation containment

### A.3 QE Parameter JSON Location

**File**: `src/quantumvitas/data/qe_module_parameters.json`

**Access API**: `src/quantumvitas/data/qe_metadata.py`
- `safe_load_metadata()`: Loads JSON with caching
- `get_module_param_sections(module)`: Returns section → parameter list mapping
- `_iter_params(module)`: Iterator over parameter metadata

**Schema v3 Structure**:
```json
{
  "schema_version": 3,
  "generated_at": "2025-12-12T04:41:30.679615+00:00",
  "modules": {
    "pw": {
      "doc_url": "...",
      "sections": [...],  // Hierarchical section tree
      "parameters": {
        "&SYSTEM.ecutwfc": {
          "namelist": "&SYSTEM",
          "name": "ecutwfc",
          "type": "REAL",
          "default": "required",
          "enum": null,
          "description": "..."
        },
        ...
      }
    }
  }
}
```

**Coverage**: 954 parameters across 22 modules (pw, ph, dos, bands, etc.)
- Types: 83% coverage (791/954)
- Defaults: 65% coverage (623/954)
- Descriptions: 81% coverage (774/954)

**Usage**: 
- GUI parameter browser (`gui/src/components/panels/StepDetailPanel.tsx`)
- Preset compilation (validates parameter existence)
- Input generation (validates parameters against schema)

---

## B) Current Compilation Pipeline

### B.1 Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ USER INTENT                                                          │
│ - Preset selection (GUI/CLI)                                        │
│ - Direct parameter edits (expert mode)                              │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PRESET DETECTION/APPLICATION (engine-specific today: QE only)      │
│ - Detector B: params → preset options                               │
│ - Compiler: preset options → QE params                              │
│ Location: src/quantumvitas/presets/{detector,compiler}.py          │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PARAMETER COMPILATION (QE-specific)                                 │
│ - compile_presets(options) → {"SYSTEM": {...}, "ELECTRONS": {...}} │
│ - compile_precision(advice) → adds K_POINTS card                    │
│ Location: src/quantumvitas/presets/compiler.py                     │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ STEP YAML MATERIALIZATION                                           │
│ - apply_presets_to_step() patches step YAML via StepDoc            │
│ - Step YAML stored: calculations/{calc}/steps/*.step.yaml          │
│ Location: src/quantumvitas/presets/integration.py                  │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ INPUT FILE GENERATION (QE-specific)                                 │
│ - StructureStepSpec → QEInput → QEInputGenerator                    │
│ - Generates .in file from parameters/cards                          │
│ Location: src/quantumvitas/io/generator/qe_generator.py            │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ EXECUTION (engine-specific)                                         │
│ - QECalculationRunner.run_step()                                    │
│ - Executes pw.x/bands.x/etc. with .in file                         │
│ Location: src/quantumvitas/core/engines/qe_calculation.py          │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT PARSING (QE-specific)                                        │
│ - parse_scf_output_text() extracts energy, forces, etc.            │
│ - Assumes QE file layout (regex patterns for "JOB DONE", etc.)     │
│ Location: src/quantumvitas/analysis/parsers.py                     │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ANALYSIS ARTIFACTS (engine-agnostic today)                          │
│ - SCFResult, DOSResult, BandsResult dataclasses                     │
│ - Stored in results/ directory as JSON                              │
│ Location: src/quantumvitas/analysis/{energy,dos,bands}.py          │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HISTORY/STORAGE                                                      │
│ - Journal: tracks YAML changes (before/after snapshots)            │
│ - Manifest: tracks step completion (done flag + step_sha)          │
│ - Incremental run: compares step_sha to skip unchanged steps        │
│ Location: src/quantumvitas/{core/journal,calculation/manifest}.py  │
└─────────────────────────────────────────────────────────────────────┘
```

### B.2 Engine-Specific Components (Today)

**QE-Specific**:
1. Preset compilation (`presets/compiler.py`) - maps preset options to QE parameter names
2. Input generation (`io/generator/qe_generator.py`) - generates QE .in file format
3. Execution (`core/engines/qe_calculation.py`) - runs pw.x/bands.x executables
4. Output parsing (`analysis/parsers.py`) - regex patterns for QE output files
5. Parameter metadata (`data/qe_module_parameters.json`) - QE-specific schema

**Potentially Engine-Agnostic** (needs abstraction):
1. Analysis artifacts (SCFResult, etc.) - already use physical units
2. Workflow templates - step sequences are physics-driven (SCF → NSCF → DOS)

---

## C) QE Parameter Inventory

### C.1 JSON Structure

**File**: `src/quantumvitas/data/qe_module_parameters.json`

**Schema v3 Format**:
- Top-level: `{schema_version, generated_at, doc_pattern, modules: {...}}`
- Module entry: `{doc_url, sections: [...], parameters: {...}, card_metadata: {...}}`
- Parameter entry: `{namelist, name, type, default, enum, description, status, see_also}`

**Key Fields**:
- `namelist`: Section name (e.g., "&SYSTEM")
- `name`: Parameter name (e.g., "ecutwfc")
- `type`: QE type (CHARACTER, INTEGER, REAL, LOGICAL)
- `default`: Default value or "REQUIRED" or null
- `enum`: List of allowed values (or null)
- `description`: Free-text description from QE docs

### C.2 Parameter Extraction Table

**Subset Used by Presets** (from `presets/integration.py::DIMENSION_OWNED_KEYS`):

| Parameter Key | Namelist | Type | Default | Description | Used By |
|---------------|----------|------|---------|-------------|---------|
| `nspin` | SYSTEM | INTEGER | 1 | Spin polarization (1=nonmagnetic, 2=collinear, 4=noncollinear) | magnetism |
| `noncolin` | SYSTEM | LOGICAL | .false. | Noncollinear magnetism | magnetism |
| `lspinorb` | SYSTEM | LOGICAL | .false. | Spin-orbit coupling | magnetism |
| `occupations` | SYSTEM | CHARACTER | 'fixed' | Occupations scheme | occupations_scheme |
| `smearing` | SYSTEM | CHARACTER | null | Smearing type | occupations_scheme |
| `degauss` | SYSTEM | REAL | 0.D0 | Gaussian smearing width (Ry) | occupations_scheme |
| `ecutwfc` | SYSTEM | REAL | REQUIRED | Wavefunction cutoff (Ry) | precision |
| `ecutrho` | SYSTEM | REAL | 4*ecutwfc | Charge density cutoff (Ry) | precision |
| `conv_thr` | ELECTRONS | REAL | 1.D-6 | SCF convergence threshold (Ry) | precision |
| `mixing_beta` | ELECTRONS | REAL | 0.7D0 | Mixing parameter | convergence |
| `electron_maxstep` | ELECTRONS | INTEGER | 100 | Max SCF iterations | convergence |
| `mixing_mode` | ELECTRONS | CHARACTER | 'plain' | Mixing algorithm | convergence |
| `mixing_ndim` | ELECTRONS | INTEGER | 8 | Mixing history length | convergence |
| `diagonalization` | ELECTRONS | CHARACTER | 'david' | Diagonalization method | convergence |
| `K_POINTS` (card) | cards | - | - | K-point mesh or k-path | precision |

**Total Parameters in JSON**: 954 across 22 modules  
**Parameters Touched by Presets**: ~15 (listed above)  
**Common User-Edited Parameters** (from `data/qe_ui_parameters.json` and `step_defaults.py`):
- `calculation` (CONTROL): Step type selector
- `outdir` (CONTROL): Output directory
- `prefix` (CONTROL): File prefix
- `restart_mode` (CONTROL): Restart flag
- `ibrav` (SYSTEM): Bravais lattice index
- `nat` (SYSTEM): Number of atoms
- `ntyp` (SYSTEM): Number of species
- `ATOMIC_SPECIES` (card): Pseudopotential mappings
- `ATOMIC_POSITIONS` (card): Atomic coordinates

---

## D) Preset Inventory

### D.1 All Presets

**Preset Dimensions** (from `presets/dimensions.py`):

1. **magnetism** (4 options):
   - `nonmagnetic`: `{nspin: 1, noncolin: .false., lspinorb: .false.}`
   - `collinear_lsda`: `{nspin: 2, noncolin: .false., lspinorb: .false.}`
   - `noncollinear`: `{noncolin: .true., lspinorb: .false.}` (nspin omitted/4)
   - `noncollinear_soc`: `{noncolin: .true., lspinorb: .true.}` (nspin omitted/4)

2. **occupations_scheme** (3 options):
   - `fixed`: `{occupations: 'fixed'}` (smearing/degauss omitted)
   - `smearing_gaussian`: `{occupations: 'smearing', smearing: 'gaussian', degauss: 0.02}`
   - `tetrahedra`: `{occupations: 'tetrahedra'}`

3. **precision** (3 options, context-dependent):
   - `low`: Lower cutoffs/kmesh, higher conv_thr
   - `med`: Balanced (default)
   - `high`: Higher cutoffs/kmesh, lower conv_thr
   - **Context required**: `{base_ecutwfc, base_ecutrho, lattice_matrix}` → computes actual values

4. **convergence** (4 options):
   - `fast`: `{mixing_beta: 0.7, electron_maxstep: 100}`
   - `normal`: `{mixing_beta: 0.4, electron_maxstep: 150}`
   - `robust`: `{mixing_beta: 0.2, electron_maxstep: 200}`
   - `very_robust`: `{mixing_beta: 0.1, electron_maxstep: 250}`

### D.2 Code Paths

**Compilation** (`presets/compiler.py`):
- `compile_presets(options)` → calls `compile_magnetism()`, `compile_occupations_scheme()`, etc.
- Each dimension compiler → calls `spaces_registry::compile_dimension_patch()` → uses ParamSpace to generate QE params
- Precision: Special case - requires `PrecisionAdvisor` to compute actual cutoffs from structure/pseudos

**Detection** (`presets/detector.py`):
- `detect_all_presets(step_params_list)` → calls dimension-specific detectors
- Each detector → uses ParamSpace matching to infer preset option from QE params
- Precision: Requires context (lattice, pseudo cutoffs) for strict matching

**Application** (`presets/integration.py`):
- `apply_presets_to_step(step_path, options)` → uses `StepDoc` to patch step YAML
- Deletes old preset params (via `None` in patch) before writing new ones
- Physics validation: Ensures SOC → noncollinear, etc.

### D.3 Physical vs Implementation Knobs

**Physically Meaningful** (should map to IR):
- Magnetism treatment (spin/SOC) → physics model choice
- Occupations scheme → electronic structure type (metal vs insulator)
- Precision level → accuracy vs cost tradeoff
- Convergence strategy → robustness vs speed tradeoff

**QE Implementation Knobs** (should stay in engine layer):
- `nspin`, `noncolin`, `lspinorb` → QE-specific encoding of magnetism
- `occupations`, `smearing`, `degauss` → QE-specific occupations syntax
- `ecutwfc`, `ecutrho` → QE plane-wave cutoffs (units: Ry)
- `conv_thr` → QE convergence threshold (units: Ry)
- `mixing_beta`, `electron_maxstep` → QE SCF algorithm parameters

**Boundary**: Presets are already "physical intent" - they just need to be abstracted into IR rather than directly compiled to QE.

---

## E) Proposed IR v0

### E.1 IR Schema (20-40 Fields)

**Design Principles**:
1. **Physical meaning**: Names reflect physics, not QE syntax
2. **Stable**: Names don't change when adding engines
3. **Minimal**: Only covers current presets + common non-preset controls
4. **Extensible**: Can add fields without breaking existing code

**IR Fields** (25 total):

#### Magnetism (4 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `spin_treatment` | enum | `none` | Spin model: none/collinear/noncollinear | `nspin`, `noncolin` |
| `spin_orbit_coupling` | bool | `false` | Enable SOC | `lspinorb`, requires `spin_treatment=noncollinear` |
| `magnetization_direction` | optional[vec3] | null | Fixed magnetization (collinear only) | QE doesn't support fixed direction easily |
| `initial_magnetization` | optional[list[float]] | null | Per-atom initial magnetization | `starting_magnetization` (advanced) |

#### Electronic Structure (3 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `electronic_type` | enum | `insulator` | Material type: insulator/metal | Determines `occupations` scheme |
| `smearing_type` | optional[enum] | null | Smearing: gaussian/fermi/tetrahedra | `smearing`, `occupations` |
| `smearing_width` | optional[float] | null | Smearing width (eV) | `degauss` (Ry) |

#### Basis Set / Cutoffs (5 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `wavefunction_cutoff` | float | REQUIRED | Wavefunction cutoff (eV) | `ecutwfc` (Ry) |
| `charge_density_cutoff` | optional[float] | 4x wavefunction | Charge density cutoff (eV) | `ecutrho` (Ry) |
| `precision_level` | enum | `medium` | Quality level: low/medium/high | Multiplier on base cutoffs (precision preset) |
| `base_cutoffs_source` | enum | `pseudopotential` | Source of base cutoffs | Used by precision advisor |
| `cutoff_unit` | enum | `eV` | Unit for cutoffs | IR uses eV, QE uses Ry |

#### K-Point Mesh (5 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `kpoint_mesh` | optional[vec3i] | null | Uniform mesh divisions | `K_POINTS` automatic |
| `kpoint_shifts` | optional[vec3] | null | Mesh shifts (0-1) | In `K_POINTS` data |
| `kpoint_mode` | enum | `automatic` | automatic/manual/path | `K_POINTS` option |
| `kpoint_path` | optional[list[path_segment]] | null | High-symmetry k-path | `K_POINTS` crystal_b/tpiba_b |
| `kpoint_density` | optional[float] | null | Target density (1/Å) | Used by precision preset |

#### SCF Convergence (4 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `scf_threshold` | float | 1e-8 | Energy convergence (eV) | `conv_thr` (Ry) |
| `scf_max_iterations` | int | 100 | Max SCF steps | `electron_maxstep` |
| `scf_mixing` | optional[dict] | null | Mixing parameters | `mixing_beta`, `mixing_mode`, etc. |
| `scf_convergence_strategy` | enum | `normal` | fast/normal/robust | Convergence preset |

#### Geometric (2 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `calculation_type` | enum | `scf` | scf/nscf/relax/vc-relax/md | `CONTROL.calculation` |
| `optimization_target` | optional[enum] | null | energy/forces/stress | Implied by calculation_type |

#### Advanced (2 fields)
| IR Field | Type | Default | Physical Meaning | QE Mapping |
|----------|------|---------|------------------|------------|
| `exchange_correlation` | optional[str] | `PBE` | XC functional name | Not directly in QE input (via pseudos) |
| `vdw_correction` | optional[enum] | null | vdW correction: dft-d/dft-d3 | `vdw_corr` (if supported) |

### E.2 IR Validation Rules

**Physics Constraints**:
1. `spin_orbit_coupling=true` → requires `spin_treatment=noncollinear`
2. `electronic_type=metal` → requires `smearing_type` or `smearing_width`
3. `precision_level` → overrides `wavefunction_cutoff` if preset used (conflict resolution)
4. `kpoint_path` → requires `kpoint_mode=path` (or auto-detected)

**Unit Conversions**:
- IR uses eV for energies, QE uses Ry (1 Ry = 13.6057 eV)
- IR uses Å for lengths, QE uses Bohr (1 Bohr = 0.529177 Å)

**Default Policies**:
- If `precision_level` set → compute cutoffs from base + multiplier
- If `wavefunction_cutoff` explicitly set → use it (override precision_level)
- If `kpoint_density` set → compute mesh from lattice (precision preset logic)

---

## F) Mapping & Backend Design

### F.1 Interface Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ IR Schema (engine-agnostic)                                 │
│ Location: src/quantumvitas/ir/schema.py                     │
│ - IRField definitions (dataclasses with types)              │
│ - IRDocument (step-level IR)                                │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Backend Capability Declaration (per engine)                 │
│ Location: src/quantumvitas/ir/backends/{engine}/cap.py     │
│ - Declares: which IR fields are supported                   │
│ - Declares: default mappings (IR field → engine param)      │
│ - Declares: step type → executable mapping                  │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ IR → Engine Lowering (compiler backend)                     │
│ Location: src/quantumvitas/ir/backends/{engine}/lower.py   │
│ - lower_ir_to_engine(ir_doc, step_type) → engine_params    │
│ - Handles: unit conversion, syntax translation              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Engine Params → Input Materialization                       │
│ Location: src/quantumvitas/io/generator/{engine}_gen.py    │
│ - Existing: qe_generator.py (refactor to use engine_params) │
│ - Generates: .in file (QE) or input dict (PySCF)            │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────┐
│ Parser → Engine-Agnostic Artifacts                          │
│ Location: src/quantumvitas/analysis/parsers.py              │
│ - Abstract: parse_energy(), parse_forces(), etc.            │
│ - Backend-specific: qe_parse_scf_output() (internal)        │
│ - Returns: SCFResult (units: Ry/eV, engine-agnostic)        │
└─────────────────────────────────────────────────────────────┘
```

### F.2 Interface Definitions

**IR Schema** (`ir/schema.py`):
```python
@dataclass
class IRDocument:
    """Step-level IR (engine-agnostic physical intent)."""
    step_type: str  # Generalized: "scf", "nscf", "bands", etc.
    magnetism: MagnetismIR
    electronic: ElectronicIR
    basis: BasisIR
    kpoints: KPointsIR
    scf: SCFIR
    geometry: GeometryIR
    # Optional advanced fields
```

**Backend Capability** (`ir/backends/qe/cap.py`):
```python
class QEBackendCapability:
    """QE backend capability declaration."""
    supported_ir_fields: set[str]
    ir_to_qe_mapping: dict[str, QEParamMapping]
    step_type_to_executable: dict[str, str]  # {"scf": "pw.x", ...}
    required_context: set[str]  # {"structure", "pseudos", ...}
```

**IR Lowering** (`ir/backends/qe/lower.py`):
```python
def lower_ir_to_qe(ir_doc: IRDocument, step_type: str, context: dict) -> QEParams:
    """Lower IR to QE parameters."""
    # Convert units (eV → Ry, etc.)
    # Map IR fields to QE param names
    # Validate QE-specific constraints
    return qe_params  # {parameters: {...}, cards: {...}}
```

### F.3 Boundary Enforcement

**UI Boundaries**:
- **IR Mode**: Show IR fields (physically meaningful names)
- **Expert Mode**: Show engine params (read-only, with IR→engine mapping displayed)
- **Toggle**: Allow switching between modes, but never mix edits

**Code Boundaries**:
- Presets → IR (via `ir/presets.py`)
- IR → Engine params (via `ir/backends/{engine}/lower.py`)
- Engine params → Input file (via `io/generator/{engine}_gen.py`)
- **No direct**: Presets → Engine params (remove `presets/compiler.py` direct QE compilation)

---

## G) Workflow/Step Generalization

### G.1 Current Step Representation

**Step Types** (`calculation/types.py`):
- QE-specific: `SCF`, `NSCF`, `BANDS_PW`, `BANDS`, `DOS`, `PH`, etc.
- Wannier90: `W90_PREPROC`, `PW2WANNIER90`, `W90_RUN`
- PySCF: `PYSCF_SCF` (molecular chemistry)

**Step Storage** (`*.step.yaml`):
- Contains: `{meta, step_type, parameters: {SYSTEM: {...}}, cards: {K_POINTS: {...}}}`
- **Problem**: `step_type` is engine-specific (e.g., "scf" implies pw.x)

### G.2 Generalized Step Contract

**Proposed**: Separate **physical step type** from **engine implementation**

**Generalized Step Types** (physics-driven):
- `self_consistent`: SCF calculation (any engine)
- `non_self_consistent`: Fixed density calculation
- `band_structure`: Band energies along k-path
- `density_of_states`: DOS calculation
- `relaxation`: Atomic position optimization
- `cell_relaxation`: Variable-cell optimization
- `molecular_dynamics`: MD simulation

**Step Contract** (engine-agnostic):
```python
@dataclass
class GeneralizedStep:
    physical_type: str  # "self_consistent", "band_structure", etc.
    ir: IRDocument  # Physical intent
    engine: str  # "qe", "pyscf", etc.
    engine_step_type: str  # Engine-specific: "scf", "pyscf_scf", etc.
    executable: str  # "pw.x", "pyscf", etc.
```

**Engine Binding** (per engine):
```python
# ir/backends/qe/steps.py
QE_STEP_MAPPING = {
    "self_consistent": {
        "engine_step_type": "scf",
        "executable": "pw.x",
        "calculation": "scf",
        "required_artifacts": ["energy", "forces"],
    },
    "band_structure": {
        "engine_step_type": "bands_pw",
        "executable": "pw.x",
        "calculation": "bands",
        "required_artifacts": ["bands", "kpath"],
    },
    # ...
}
```

### G.3 Artifact Contract

**Required Artifacts** (per physical step type):
- `self_consistent`: `{energy: float, forces: Optional[array], ...}`
- `band_structure`: `{bands: array, kpath: array, ...}`
- `density_of_states`: `{dos: array, energy: array, ...}`

**Parser Abstraction**:
- Each engine implements `parse_{artifact}()` (e.g., `qe_parse_energy()`)
- Returns engine-agnostic dataclass (e.g., `EnergyResult`)

---

## H) Migration Strategy

### Phase 0: Read-Only IR (Derive IR from Existing State)

**Goal**: Add IR derivation without changing UI or storage.

**Changes**:
1. **New Module**: `src/quantumvitas/ir/` with:
   - `schema.py`: IR field definitions
   - `derivation.py`: `derive_ir_from_step(step_doc) → IRDocument`
   - `backends/qe/derive.py`: `derive_ir_from_qe_params(qe_params) → IRDocument`

2. **Integration**:
   - Add `ir` field to `StepDetail` RPC response (read-only)
   - GUI can display IR alongside QE params (for debugging)

3. **Validation**:
   - `lower_ir_to_qe(derive_ir_from_qe_params(qe_params)) == qe_params` (roundtrip test)

**Files to Create**:
- `src/quantumvitas/ir/__init__.py`
- `src/quantumvitas/ir/schema.py`
- `src/quantumvitas/ir/derivation.py`
- `src/quantumvitas/ir/backends/__init__.py`
- `src/quantumvitas/ir/backends/qe/__init__.py`
- `src/quantumvitas/ir/backends/qe/derive.py`
- `src/quantumvitas/ir/backends/qe/lower.py` (stub for Phase 1)

**Tests**:
- Unit: IR derivation from QE params
- Unit: IR → QE lowering (stub returns original params)
- Integration: Roundtrip QE params → IR → QE params

**Risk**: Low (read-only, no UI changes)

---

### Phase 1: IR as Control Surface for Presets

**Goal**: Presets produce IR; QE backend compiles IR to QE params.

**Changes**:
1. **Refactor Presets**:
   - `presets/compiler.py` → compiles to IR (not QE params)
   - `ir/backends/qe/lower.py` → implements IR → QE lowering
   - `presets/integration.py` → calls IR → QE lowering

2. **IR Storage**:
   - Add `ir` field to `*.step.yaml` (alongside `parameters`)
   - Migration: Derive IR from existing `parameters` on first load

3. **UI**:
   - Preset UI unchanged (still shows preset dimensions)
   - Step detail panel: Show IR field values (read-only initially)

**Files to Modify**:
- `presets/compiler.py`: Return `IRDocument` instead of QE params
- `presets/integration.py`: Call `lower_ir_to_qe()` before patching step YAML
- `ir/backends/qe/lower.py`: Implement full IR → QE lowering
- `calculation/structure_steps.py`: Add `ir` field to StepSpec

**Tests**:
- Unit: Preset → IR compilation
- Unit: IR → QE lowering (full implementation)
- Integration: Preset application end-to-end (preset → IR → QE → input file)

**Risk**: Medium (changes preset application path)

---

### Phase 2: General Step Contract

**Goal**: Steps become engine-agnostic; QE implements backend hooks.

**Changes**:
1. **Step Type Generalization**:
   - Add `physical_type` to step YAML (alongside `step_type`)
   - `step_type` becomes engine-specific ("scf" for QE, "pyscf_scf" for PySCF)
   - `physical_type` is engine-agnostic ("self_consistent")

2. **Backend Registry**:
   - `ir/backends/registry.py`: Maps `(physical_type, engine)` → backend
   - Each backend declares: executable, required artifacts, step type

3. **Workflow Updates**:
   - `workflow/templates.py`: Use `physical_type` instead of `step_type`
   - Workflow detection: Match by `physical_type`

**Files to Modify**:
- `calculation/types.py`: Add `PhysicalStepType` enum
- `workflow/templates.py`: Use `physical_type`
- `ir/backends/registry.py`: New backend registry
- `ir/backends/qe/steps.py`: QE step mappings

**Tests**:
- Unit: Physical type → engine step type mapping
- Integration: Workflow with physical types

**Risk**: Medium-High (changes step type semantics)

---

### Phase 3: Optional IR Exposure in CLI/Jupyter

**Goal**: Allow users to edit IR directly (expert mode).

**Changes**:
1. **IR Editor**:
   - GUI: IR editing mode (toggles with QE expert mode)
   - CLI: `qv step set-ir --field spin_treatment=collinear`

2. **Validation**:
   - IR → QE lowering validates IR constraints
   - Presets remain recommended (simpler UX)

**Files to Create**:
- `gui/src/components/ir/IREditor.tsx`
- `cli/main.py`: IR editing commands

**Risk**: Low (optional feature)

---

## I) Critical Questions

### I.1 What is the current single source of truth for parameters?

**Answer**: `*.step.yaml` files (via `StepDoc`) are the **single source of truth** for parameters.

- Presets are **never persisted** (Constitution §10.2.1)
- Presets compile to QE params → patch step YAML
- Detector B reads step YAML → infers preset values (reverse)

**Where drift can happen**:
- User edits QE params directly (expert mode) → preset detection may return "Custom"
- Preset compilation uses explicit defaults → if QE defaults change, compilation may diverge
- **Solution**: IR becomes intermediate truth; presets → IR → engine params (single compilation path)

---

### I.2 What is the current boundary between "preset intent" and "engine parameter"?

**Answer**: The boundary is **implicit** in the preset compiler.

- **Preset intent**: `{"magnetism": "collinear_lsda"}` (physics)
- **Engine parameter**: `{"SYSTEM": {"nspin": 2}}` (QE syntax)

**Current boundary**:
- `presets/compiler.py` → hardcoded QE param mappings
- `presets/detector.py` → reverse mapping (tolerant, handles QE defaults)

**Problem**: No explicit IR layer → can't abstract to PySCF without duplicating logic.

**Solution**: Insert IR layer:
- Preset → IR (physics)
- IR → Engine params (engine-specific)

---

### I.3 How are params stored (per calc? per step? global)? What is the current inheritance behavior?

**Answer**: Parameters are stored **per step** in `*.step.yaml`.

**Storage Hierarchy**:
1. **Project-level**: `project.qv.yml` (settings, not params)
2. **Calculation-level**: `calculation.yaml` (structure_id, species_map, step list)
3. **Step-level**: `steps/*.step.yaml` (parameters, cards, step_type)

**Inheritance**:
- Steps **inherit** structure from calculation (`calculation.structure_id`)
- Steps **inherit** pseudos from calculation (`calculation.species_map`)
- Steps **do NOT inherit** parameters from each other (each step has own params)

**Preset Application**:
- Presets apply to **individual steps** (via `apply_presets_to_step()`)
- Each step can have different preset values (detection returns "Custom" if steps differ)

---

### I.4 Where does job/history record "what changed"? Is it QE-key-based today? How to evolve to IR diff?

**Answer**: History uses **Journal** (YAML snapshot diffs) and **Manifest** (step completion tracking).

**Journal** (`core/journal.py`):
- Records: `{before: {...}, after: {...}}` (full YAML snapshots)
- **Problem**: Diff is QE-key-based (e.g., `parameters.SYSTEM.ecutwfc` changed)

**Manifest** (`calculation/manifest.py`):
- Records: `{step_id, done: bool, step_sha: str}` (step completion)
- `step_sha`: Hash of step YAML (meta stripped) → detects any param change

**Evolution to IR diff**:
- Add `ir_sha` to manifest (hash of IR document)
- Journal: Record IR diff alongside QE diff (for readability)
- **Challenge**: IR is derived (not stored initially) → need to store IR in step YAML (Phase 1)

---

### I.5 How does run/incremental/invalidations currently work? Which assumptions will IR break?

**Answer**: Incremental runs use **step_sha** (hash of step YAML) to skip unchanged steps.

**Current Flow** (`calculation/runner.py`):
1. Load manifest (previous run state)
2. For each step:
   - Compute `step_sha` (hash of step YAML, meta stripped)
   - Compare with manifest `entry.step_sha`
   - If match → skip step (already done)
   - If mismatch → rerun step

**Assumptions**:
- Step YAML changes → `step_sha` changes → step needs rerun
- **Problem**: If we derive IR from QE params, changing QE params → IR changes, but reverse may not hold (multiple QE param sets → same IR)

**IR Impact**:
- **Option A**: Store IR in step YAML → `step_sha` includes IR → IR changes trigger rerun
- **Option B**: Compute `ir_sha` separately → compare both `step_sha` and `ir_sha` → rerun if either changes
- **Recommendation**: Option A (store IR) → simpler, preserves current behavior

---

### I.6 Where do parsers assume QE file layout/output format? How to abstract into engine-agnostic artifacts?

**Answer**: Parsers use **regex patterns** on QE output text.

**Current Parsers** (`analysis/parsers.py`):
- `parse_scf_output_text()`: Regex for "JOB DONE", "total energy = X Ry", etc.
- Assumes: QE-specific text format
- Returns: `SCFResult` (already engine-agnostic: units Ry/eV, not QE-specific)

**Abstraction Strategy**:
1. **Keep parsers engine-specific** (internal):
   - `qe_parse_scf_output()` (private)
   - `pyscf_parse_scf_output()` (future)

2. **Abstract API** (public):
   - `parse_energy(output_text, engine="qe") → EnergyResult`
   - `parse_forces(output_text, engine="qe") → ForcesResult`

3. **Artifact Contract**:
   - Each engine implements `parse_{artifact}()` → returns engine-agnostic dataclass
   - Artifacts already engine-agnostic (units normalized)

**Files to Refactor**:
- `analysis/parsers.py`: Split into `qe_parsers.py` (internal) + `parse_energy()` (public)
- Add `ir/backends/{engine}/parse.py`: Engine-specific parsing

---

### I.7 What is the minimal IR that can support current presets WITHOUT hiding expert QE editing?

**Answer**: IR should be **minimal** (20-30 fields) covering:
1. All preset dimensions (magnetism, occupations, precision, convergence) → 15 fields
2. Common non-preset controls (calculation_type, kpoint_mode) → 5 fields
3. **Advanced QE params remain in expert mode** (not in IR):
   - `ibrav`, `celldm` (lattice encoding)
   - `starting_magnetization` (advanced magnetism)
   - `mixing_ndim`, `diagonalization` (advanced SCF)

**UI Separation**:
- **IR Mode**: Show IR fields (physically meaningful, ~25 fields)
- **Expert Mode**: Show all QE params (read-only IR mapping shown, ~200+ params)
- **Never mix**: User edits either IR OR QE params, not both

**IR Completeness**:
- IR covers **all preset-touched params** (required for preset → IR → QE roundtrip)
- IR does **NOT** cover all QE params (expert mode still needed for advanced features)

---

### I.8 What is the best place to put QE parameter JSON and how to reference it without leaking QE concepts into IR?

**Answer**: Keep QE parameter JSON in `data/`; reference via **backend capability** declarations.

**Current Location**: `src/quantumvitas/data/qe_module_parameters.json`

**IR Abstraction**:
- IR schema (`ir/schema.py`) → **no QE concepts** (uses eV, not Ry; uses physics names)
- QE backend (`ir/backends/qe/`) → references QE JSON for validation
- **Boundary**: IR layer never imports QE metadata directly; only QE backend does

**Reference Pattern**:
```python
# ir/schema.py (no QE imports)
@dataclass
class BasisIR:
    wavefunction_cutoff: float  # eV, not Ry

# ir/backends/qe/lower.py (QE imports OK)
from quantumvitas.data.qe_metadata import safe_load_metadata

def lower_ir_to_qe(ir: BasisIR) -> dict:
    ecutwfc_ry = ir.wavefunction_cutoff / 13.6057  # eV → Ry
    # Validate against QE JSON
    metadata = safe_load_metadata()
    # ...
```

**Prevent Leakage**:
- IR schema uses physical units (eV, Å) → engine backends convert
- IR field names are physics-driven ("spin_treatment") → engine backends map to engine syntax

---

### I.9 How to prevent "IR + QE params mixed editing" confusion in UI? Where should UI boundaries be enforced?

**Answer**: **Enforce boundaries at UI layer** with mode toggles and validation.

**UI Design**:
1. **Mode Toggle**:
   - "Physical Intent" mode (IR fields, human-friendly)
   - "Expert QE" mode (all QE params, read-only IR mapping shown)

2. **Boundary Rules**:
   - User edits **either** IR **or** QE params (never both in same session)
   - Switching modes: Warn if unsaved changes, convert IR → QE (or reverse)

3. **Enforcement**:
   - Step detail panel: Disable one mode when other is active
   - Validation: If IR edited → clear QE param edits (and vice versa)
   - Backend: `apply_presets()` always uses IR (even if user edited QE directly, convert to IR first)

**Code Enforcement**:
- `presets/integration.py::apply_presets_to_step()`:
  - If step has IR → use IR
  - If step has only QE params → derive IR first, then apply preset to IR
- **Never**: Apply preset to QE params directly (always via IR)

---

### I.10 What are the top 10 edge cases that will cause semantic bugs during migration?

**Answer**: Top edge cases:

1. **Precision preset requires context** (lattice, pseudo cutoffs) → IR derivation may return "Custom" if context missing
2. **Multiple QE param sets → same IR** (e.g., `nspin=2` vs `nspin=4` with `noncolin=true` both → `spin_treatment=noncollinear`) → reverse derivation ambiguous
3. **IR units (eV) vs QE units (Ry)** → conversion errors if not normalized
4. **Step_sha includes meta** (currently stripped) → if IR stored, need to ensure IR changes trigger rerun
5. **Preset "Custom" state** → how to represent in IR? (store raw QE params as fallback?)
6. **Workflow detection** → currently uses `step_type` (QE-specific) → need to use `physical_type`
7. **Post-processing steps** (DOS, bands.x) → don't have IR (no SYSTEM params) → need special handling
8. **Wannier90 steps** → engine-agnostic but different IR model → need separate IR schema?
9. **Legacy calculations** → no IR field → need migration path (derive on first load)
10. **Incremental run** → compares step_sha → if IR derivation changes logic, same QE params → different IR → false invalidation

**Mitigation**:
- Comprehensive roundtrip tests (QE → IR → QE)
- Migration script for legacy calculations
- IR derivation caching (avoid recomputation)

---

## Recommended Next PR (Phase 0 Only)

### Scope: Read-Only IR Derivation

**Goal**: Add IR derivation without changing UI or storage.

**Changes**:
1. Create `src/quantumvitas/ir/` module structure
2. Implement `IRDocument` schema (25 fields)
3. Implement `derive_ir_from_qe_params()` (QE → IR)
4. Implement `lower_ir_to_qe()` stub (IR → QE, returns original params for now)
5. Add unit tests (roundtrip QE → IR → QE)

**Files to Create**:
- `src/quantumvitas/ir/__init__.py`
- `src/quantumvitas/ir/schema.py` (IRDocument, IR field dataclasses)
- `src/quantumvitas/ir/derivation.py` (derive_ir_from_qe_params)
- `src/quantumvitas/ir/backends/qe/__init__.py`
- `src/quantumvitas/ir/backends/qe/derive.py` (QE-specific derivation)
- `src/quantumvitas/ir/backends/qe/lower.py` (stub)
- `tests/unit/test_ir_derivation.py` (roundtrip tests)

**No Changes To**:
- UI (no IR display yet)
- Storage (no IR in step YAML yet)
- Presets (still compile to QE directly)

**Validation**:
- Roundtrip test: `lower_ir_to_qe(derive_ir_from_qe_params(qe_params)) == qe_params` (exact match)
- Coverage: All preset-touched QE params → IR → QE params

**Estimated Effort**: 2-3 days (schema design + derivation logic + tests)

---

## Appendix: Key File Reference

**Presets**:
- `src/quantumvitas/presets/compiler.py`: Preset → QE params compilation
- `src/quantumvitas/presets/detector.py`: QE params → preset detection
- `src/quantumvitas/presets/integration.py`: Preset application to steps

**Steps**:
- `src/quantumvitas/calculation/structure_steps.py`: Step YAML representation
- `src/quantumvitas/calculation/step_defaults.py`: Default parameters per step type
- `src/quantumvitas/core/yamldoc.py`: StepDoc (YAML mutation containment)

**Workflows**:
- `src/quantumvitas/workflow/templates.py`: Workflow definitions
- `src/quantumvitas/workflow/step_factory.py`: Step creation

**QE Parameters**:
- `src/quantumvitas/data/qe_module_parameters.json`: QE parameter JSON (954 params)
- `src/quantumvitas/data/qe_metadata.py`: QE metadata access API

**Execution**:
- `src/quantumvitas/core/engines/qe_calculation.py`: QE execution
- `src/quantumvitas/io/generator/qe_generator.py`: Input file generation

**Parsing**:
- `src/quantumvitas/analysis/parsers.py`: QE output parsing

**History**:
- `src/quantumvitas/core/journal.py`: YAML change tracking
- `src/quantumvitas/calculation/manifest.py`: Step completion tracking
- `src/quantumvitas/calculation/hash_utils.py`: Step hashing for incremental runs

---

**End of Report**
