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

---

# Engine/Execution/Runner Generalization Review

**Review Date**: 2025-01-XX  
**Purpose**: Deep code review focused on engine/execution/runner layer to propose minimal generalization supporting both file-based engines (QE/VASP/ABINIT/Wannier90) and python-library engines (PySCF) while keeping current QE behavior unchanged  
**Status**: Review Complete - Minimal Plan Ready

---

## Executive Summary

This section provides a comprehensive review of the engine/execution/runner layer in QMatSuite to support generalization for both file-based engines (QE, VASP, ABINIT, Wannier90) and python-library engines (PySCF). The review focuses on **minimalism**: avoiding duplication, maintaining single source of truth, and preserving backward compatibility.

**Key Findings**:
- **Current QE execution**: Subprocess-based via `QECalculationRunner` in `core/engines/qe_calculation.py`
- **Workdir structure**: `calculations/<calc_id>/raw/` contains all inputs/outputs, QE `outdir/` subdirectory for scratch
- **Incremental runs**: Use manifest system with three SHA256 hashes (step_sha, structure_sha, pseudo_set_sha) to detect changes
- **Step completion**: Detected via "JOB DONE" marker in `.out` files (QE-specific) or file existence (Wannier90)
- **Concurrency**: `JobManager` with `ThreadPoolExecutor(max_workers=1)` for sequential QE execution; per-calc locking via `calc_run_lock()`
- **PySCF support**: Already exists as subprocess-based engine (`engine/pyscf_engine.py`), but uses `job.json`/`results.json` file exchange

**Minimal Strategy**: Introduce thin `EnginePlan` abstraction around existing step YAML/materialization, add runner interface with two implementations (SubprocessRunner, PythonWorkerRunner), keep existing QE code paths unchanged.

---

## A) Repo Map: Engine/Execution

### A.1 Engine Representation

**Engine Classes**:
- `src/quantumvitas/engine/base.py`: Abstract `Engine` interface (`run_step(step, working_dir) -> StepResult`)
- `src/quantumvitas/engine/qe_engine.py`: `QeEngine` adapter wrapping legacy `QuantumEspressoEngine`
- `src/quantumvitas/engine/pyscf_engine.py`: `PySCFEngine` subprocess-based engine
- `src/quantumvitas/core/engines/qe.py`: Legacy `QuantumEspressoEngine` (full QE implementation)
- `src/quantumvitas/core/engines/qe_calculation.py`: `QECalculationRunner` (actual execution logic)

**Engine Registry**:
- `src/quantumvitas/engine/registry.py`: `EngineRegistry` mapping names to engine instances
- `src/quantumvitas/core/engines/qe_registry.py`: `QEEngineRegistry` for QE-specific resolution

**Engine Configuration**:
- `src/quantumvitas/core/engines/base.py`: `EngineConfig` dataclass (executable_path, mpi_command, omp_threads, etc.)

### A.2 Runner/Executor Implementation

**Subprocess Execution**:
- `src/quantumvitas/core/engines/qe_calculation.py::QECalculationRunner.run_step()`: Main QE execution entry point
  - Builds command via `engine.build_command()`
  - Invokes subprocess with stdin/stdout/stderr capture
  - Writes stdout/stderr to `{step_type}.out` / `{step_type}.err`
  - Returns `StepResult` with execution metadata

**Command Building**:
- `src/quantumvitas/core/engines/qe.py::QuantumEspressoEngine.build_command()`: Builds QE command
  - Resolves executable path (`pw.x`, `bands.x`, etc.)
  - Handles stdin redirection (most QE steps) vs command-line args (Wannier90)
  - Adds MPI wrapper if configured (`mpirun -np N`)

**PySCF Execution**:
- `src/quantumvitas/engine/pyscf_engine.py::PySCFEngine.run_step()`: Subprocess-based PySCF execution
  - Writes `job.json` to workdir
  - Invokes `python -m quantumvitas.engines.pyscf.runner <job.json>`
  - Reads `results.json` from workdir

**Calculation Runner**:
- `src/quantumvitas/calculation/runner.py::CalculationRunner.run()`: Orchestrates multi-step execution
  - Manages incremental run logic (manifest reconciliation)
  - Calls `step.run(engine, raw_dir, project_root, species_map)`
  - Updates manifest entries (started_at, done flag, done_at)

### A.3 Workdir Creation & Materialization

**Workdir Structure**:
- **Location**: `calculations/<calc_id>/raw/` (per calculation)
- **Function**: `src/quantumvitas/calculation/runner.py::compute_io_dir_from_calculation_model()` (SSOT for I/O directory path)
- **Default**: `calculation_dir / "raw"` (configurable via `calculation.working_dir` in `calculation.yaml`)

**Input Materialization**:
- `src/quantumvitas/calculation/structure_steps.py::materialize_step_spec()`: Generates QE input files from step YAML
  - Reads step YAML (`*.step.yaml`)
  - Generates QE input file (e.g., `scf.in`) in `raw/` directory
  - Handles Wannier90 steps (`.win`, `.pw2wan` files) separately
- `src/quantumvitas/calculation/input_runner.py::prepare_input_step()`: Prepares input for execution
  - Sets `outdir='./outdir'` (relative to workdir)
  - Sets `pseudo_dir` (project mode: `project/pseudo`, standalone: `workdir/pseudo`)
  - Materializes pseudos if needed (calls `ensure_qe_pseudos()`)

**Output Collection**:
- QE outputs: `raw/{step_type}.out` (stdout capture), `raw/{step_type}.err` (stderr capture)
- QE artifacts: `raw/outdir/` (QE scratch directory, contains `.save/`, `.wfc` files, etc.)
- Wannier90 artifacts: `raw/{seedname}.wout` (primary output), `raw/{seedname}.mmn`, etc.

### A.4 Engine Version/Command Storage

**QE Engine Resolution**:
- `src/quantumvitas/core/engines/qe_resolver.py`: Two-state resolver (external vs managed)
- Priority: Project override → Settings → Managed engine → PATH fallback
- **Storage**: Not persisted (resolved at runtime)

**Engine Config**:
- `EngineConfig` (in-memory only): `executable_path`, `mpi_command`, `omp_threads`, `environment`
- **Source**: Passed to `Engine` constructor, not stored on disk

**QE Installation**:
- `src/quantumvitas/core/engines/qe_installation.py::QEInstallation`: Detects QE installation
  - Tracks `qe_home`, `bin_dir`, `test_suite_dir`
  - Resolves executable paths

### A.5 History/Job Manager Integration

**Job Manager**:
- `src/quantumvitas/daemon/jobs.py::JobManager`: Background job execution
  - Uses `ThreadPoolExecutor(max_workers=1)` for sequential QE execution (default)
  - Configurable via `settings.max_concurrent_calcs`
  - Tracks job status (pending/running/completed/failed/cancelled)
  - Stores `io_dir` (workdir path) for UI display

**History Integration**:
- `src/quantumvitas/calculation/runner.py::CalculationRunner._start_history_recording()`: Creates run revision
- `src/quantumvitas/history/run_revision.py::create_run_revision()`: Records run metadata (step_ids, engine, etc.)
- `src/quantumvitas/history/events.py`: `RunStartedEvent`, `RunFinishedEvent` for timeline

**Manifest System**:
- `src/quantumvitas/calculation/manifest.py`: Tracks step completion state
  - Stores three SHAs: `step_sha`, `structure_sha`, `pseudo_set_sha`
  - Stores `done` flag, `started_at`, `done_at` timestamps
  - Location: `calculations/<calc_id>/.run_tmp_info/manifest.json`

---

## B) Current QE Execution Pipeline (End-to-End)

### B.1 Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ UI/CLI TRIGGER                                                       │
│ - GUI: RPC call to "run_calculation"                                │
│ - CLI: `qv run calculation <calc>`                                  │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ DAEMON RPC (GUI path only)                                          │
│ - QVDaemon.handle_request() → QVService.run_calculation()           │
│ - JobManager.submit() → creates Job (pending)                       │
│ Location: src/quantumvitas/daemon/server.py                         │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PARAMETER RESOLUTION (QE-specific today)                            │
│ - Load calculation.yaml → Calculation model                         │
│ - Load step YAMLs → Step specs                                      │
│ - Materialize inputs: materialize_step_spec() → scf.in, etc.       │
│ Location: src/quantumvitas/calculation/structure_steps.py           │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ INPUT MATERIALIZATION (QE-specific)                                 │
│ - prepare_input_step() → sets outdir, pseudo_dir                    │
│ - QEInputGenerator.write_file() → writes .in file                   │
│ - Materialize pseudos: ensure_qe_pseudos() → project/pseudo/       │
│ Location: src/quantumvitas/calculation/input_runner.py              │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ COMMAND INVOCATION (QE-specific)                                    │
│ - QECalculationRunner.run_step()                                    │
│ - engine.build_command() → ["mpirun", "-np", "4", "pw.x"]          │
│ - subprocess.run() with stdin redirection (pw.x < scf.in)          │
│ - Capture stdout/stderr → scf.out / scf.err                         │
│ Location: src/quantumvitas/core/engines/qe_calculation.py           │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ OUTPUT ARTIFACTS (QE-specific)                                      │
│ - stdout: raw/scf.out (always overwritten, never versioned)        │
│ - stderr: raw/scf.err (always overwritten, never versioned)        │
│ - QE scratch: raw/outdir/ (contains .save/, .wfc, etc.)            │
│ - Primary artifact: raw/scf.out (used for parsing)                  │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PARSER (QE-specific)                                                │
│ - parse_scf_output_text() → extracts energy, forces, etc.           │
│ - Assumes QE file layout: regex for "JOB DONE", "total energy="    │
│ - Returns SCFResult (units: Ry/eV, but structure is QE-specific)   │
│ Location: src/quantumvitas/analysis/parsers.py                      │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ ANALYSIS ARTIFACTS (engine-agnostic today)                          │
│ - SCFResult, DOSResult, BandsResult dataclasses                     │
│ - Stored in results/ directory as JSON                              │
│ - Units normalized (Ry/eV) but structure is physics-driven          │
│ Location: src/quantumvitas/analysis/{energy,dos,bands}.py           │
└──────────────────┬──────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────────────────┐
│ HISTORY/STORAGE                                                     │
│ - Manifest update: set done=true, done_at timestamp                 │
│ - History: RunFinishedEvent → timeline                              │
│ - Journal: YAML change tracking (separate from execution)           │
│ Location: src/quantumvitas/{calculation/manifest,history/}.py       │
└─────────────────────────────────────────────────────────────────────┘
```

### B.2 QE-Specific Assumptions

**Hardcoded QE Assumptions** (need abstraction):
1. **Input format**: QE `.in` file format (namelists + cards)
2. **Command syntax**: `pw.x < input.in` (stdin redirection) or `wannier90.x seedname` (args)
3. **Output format**: `.out` file with "JOB DONE" marker (regex-based parsing)
4. **Artifact layout**: `outdir/` subdirectory for scratch, `{step_type}.out` for stdout
5. **Executable naming**: `pw.x`, `bands.x`, etc. (platform-specific: `.exe` on Windows)
6. **Restart files**: QE-specific `.save/` directory structure

**Potentially Engine-Agnostic**:
1. **Workdir structure**: `raw/` directory convention (could be engine-specific subdirectory)
2. **Manifest system**: Three SHA256 hashes (engine-agnostic, but artifact paths are QE-specific)
3. **Step completion**: File existence + marker detection (generalizable to any engine)

---

## C) Step Artifact Contract

### C.1 Artifact Files Per Step (QE Today)

**Inputs** (expected before execution):
- `raw/{step_type}.in`: QE input file (generated by `materialize_step_spec()`)
- `raw/outdir/`: QE scratch directory (may contain restart files from previous steps)
- `project/pseudo/`: Pseudopotential files (materialized by Step0, shared across steps)

**Outputs** (produced during execution):
- `raw/{step_type}.out`: Primary stdout capture (always overwritten)
- `raw/{step_type}.err`: Stderr capture (always overwritten)
- `raw/outdir/{prefix}.save/`: QE restart directory (contains charge density, wavefunctions)

**Artifacts** (primary output file):
- QE steps: `raw/{step_type}.out` (contains "JOB DONE" marker)
- Wannier90 steps: `raw/{seedname}.wout` (primary output), `raw/{seedname}.mmn`, etc.

### C.2 Artifacts Used for Incremental Run

**Incremental Run Logic** (`calculation/runner.py::CalculationRunner.run()`):
1. **Manifest reconciliation**: Compare three SHAs (step_sha, structure_sha, pseudo_set_sha)
2. **Skip decision**: If `kind` matches + all SHAs match + `done==true` → skip step
3. **Step completion**: Set `done=true` after successful execution

**SHA Computation** (`calculation/hash_utils.py`):
- `step_sha`: Hash of step YAML (meta stripped) → detects parameter changes
- `structure_sha`: Hash of structure JSON (meta stripped) → detects geometry changes
- `pseudo_set_sha`: Hash of pseudopotential set (file SHA256 per element) → detects pseudo changes

**Step Completion Detection** (`calculation/step_done.py::is_step_done()`):
- QE steps: Check `{step_type}.out` exists + contains "JOB DONE"
- Wannier90 steps: Check `{seedname}.wout` exists (minimal check)

### C.3 Code That Decides "Step Done / Can Reuse"

**Manifest Skip Logic** (`calculation/runner.py:270-336`):
```python
if manifest and step_idx < len(manifest.steps):
    entry = manifest.steps[step_idx]
    if entry.done and entry.kind == step_kind:
        if entry.step_sha == current_step_sha and \
           entry.structure_sha == current_structure_sha and \
           entry.pseudo_set_sha == current_pseudo_set_sha:
            # Skip step
```

**Step Completion Update** (`calculation/runner.py:570-592`):
```python
if step_status == StepStatus.SUCCESS:
    update_manifest_step(
        calc_dir=calculation.dir,
        step_index=step_idx,
        done=True,
        done_at=now_iso8601(),
    )
```

---

## D) Minimal EnginePlan Proposal (Engine-Specific SSOT)

### D.1 EnginePlan Schema

**Design Principles**:
1. **Minimal**: Only fields needed for execution + restartability
2. **Engine-specific**: Each engine has its own plan schema (no shared fields beyond core)
3. **On-disk SSOT**: Plan is stored per step, not derived from YAML

**Proposed Schema** (`src/quantumvitas/execution/plan.py`):

```python
@dataclass
class EnginePlan:
    """Engine-specific execution plan (SSOT for step execution)."""
    engine_id: str  # "qe", "pyscf", etc.
    step_kind: str  # "scf", "nscf", "pyscf_scf", etc. (engine-specific)
    workdir: Path  # Absolute path to workdir
    inputs: InputSpec  # Engine-specific input specification
    command: CommandSpec  # Command to execute (or runner entrypoint for PySCF)
    expected_artifacts: List[ArtifactSpec]  # Files/dirs expected after execution
    provenance: ProvenanceMetadata  # Minimal: step_id, materialized_at, input_sha
```

**Engine-Specific Input Specs**:
- **QE**: `QEInputSpec(input_file: Path, outdir: Path, pseudo_dir: Path, ...)`
- **PySCF**: `PySCFInputSpec(job_file: Path, ...)` (already uses `job.json`)

**Engine-Specific Command Specs**:
- **QE**: `SubprocessCommandSpec(executable: str, args: List[str], stdin_file: Optional[Path], env: Dict[str, str])`
- **PySCF**: `PythonCommandSpec(module: str, entrypoint: str, job_file: Path, env: Dict[str, str])`

**Artifact Specs**:
```python
@dataclass
class ArtifactSpec:
    path: Path  # Relative to workdir
    type: str  # "stdout", "stderr", "restart", "primary_output", etc.
    required: bool  # Whether absence indicates failure
```

### D.2 Storage Location

**Per-Step Plan File**: `calculations/<calc_id>/.run_tmp_info/plans/<step_id>.plan.yaml`

**Rationale**:
- Separate from step YAML (step YAML = user intent, plan = execution SSOT)
- Stored in `.run_tmp_info/` (same location as manifest, runtime-only)
- JSON or YAML format (TBD: prefer JSON for simplicity)

**Relation to Existing Files**:
- **Step YAML** (`steps/*.step.yaml`): User intent, editable, engine-agnostic (after IR migration)
- **Manifest** (`.run_tmp_info/manifest.json`): Completion tracking (references plan provenance)
- **EnginePlan**: Execution SSOT (derived from step YAML, but authoritative for execution)

**Migration Strategy**:
- Phase 0: Generate plan on-the-fly (no persistence)
- Phase 1: Store plan alongside manifest (for restartability)

---

## E) Runner Generalization (Two Implementations, One Interface)

### E.1 Runner Interface

**Proposed Interface** (`src/quantumvitas/execution/runner.py`):

```python
class Runner(ABC):
    """Abstract runner interface for engine execution."""
    
    @abstractmethod
    def run(self, plan: EnginePlan, context: ExecutionContext) -> ExecutionResult:
        """
        Execute an engine plan.
        
        Args:
            plan: Engine-specific execution plan
            context: Execution context (timeout, env vars, etc.)
            
        Returns:
            ExecutionResult with success flag, artifacts, stdout/stderr
        """
        pass
    
    @abstractmethod
    def can_restart(self, plan: EnginePlan, workdir: Path) -> bool:
        """
        Check if step can be restarted from existing artifacts.
        
        Args:
            plan: Engine plan
            workdir: Workdir to check
            
        Returns:
            True if restart artifacts exist and are valid
        """
        pass
```

**ExecutionContext**:
```python
@dataclass
class ExecutionContext:
    timeout: Optional[float] = None
    environment: Dict[str, str] = field(default_factory=dict)
    resource_limits: Optional[ResourceLimits] = None  # CPU, memory, etc.
```

**ExecutionResult**:
```python
@dataclass
class ExecutionResult:
    success: bool
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    artifacts: Dict[str, Path] = field(default_factory=dict)  # type -> path
    execution_time: float = 0.0
    error: Optional[str] = None
```

### E.2 SubprocessRunner Implementation

**File-Based Engines** (QE, VASP, ABINIT, Wannier90):

```python
class SubprocessRunner(Runner):
    """Runner for file-based engines (QE, VASP, etc.)."""
    
    def run(self, plan: EnginePlan, context: ExecutionContext) -> ExecutionResult:
        # 1. Validate inputs exist
        # 2. Build command from plan.command
        # 3. Invoke subprocess with stdin/stdout/stderr capture
        # 4. Write stdout/stderr to capture files
        # 5. Check expected artifacts exist
        # 6. Return ExecutionResult
        pass
```

**QE-Specific Logic** (wraps existing code):
- Calls `QECalculationRunner.run_step()` internally (backward compatibility)
- Maps `EnginePlan` → existing `StepResult` format

### E.3 PythonWorkerRunner Implementation

**Python-Library Engines** (PySCF):

**Design Constraints**:
1. **Long-lived process allowed**: Worker can persist across steps for speed (avoid repeated imports)
2. **Restartability required**: After each step, MUST flush on-disk artifacts (checkpoint + summary + logs)
3. **In-memory is cache only**: Correctness depends on disk artifacts, not in-memory state

**Proposed Implementation** (`src/quantumvitas/execution/python_runner.py`):

```python
class PythonWorkerRunner(Runner):
    """Runner for Python-library engines (PySCF)."""
    
    def __init__(self, worker_pool_size: int = 1):
        self._workers: Dict[str, WorkerProcess] = {}  # calc_id -> worker
        self._lock = Lock()
    
    def run(self, plan: EnginePlan, context: ExecutionContext) -> ExecutionResult:
        # 1. Get or create worker for this calc_id (from plan.provenance)
        # 2. Write plan to workdir/plan.json
        # 3. Send execute request to worker (via pipe/socket)
        # 4. Wait for completion
        # 5. Read results from workdir/results.json
        # 6. Validate artifacts exist (checkpoint, summary, logs)
        # 7. Return ExecutionResult
        pass
    
    def can_restart(self, plan: EnginePlan, workdir: Path) -> bool:
        # Check for checkpoint file + summary file
        pass
```

**Worker Process Lifecycle**:
- **Pool size**: 1 worker per calculation (per `calc_id` binding)
- **Lifetime**: Created on first step, destroyed on calc completion or timeout
- **Isolation**: Separate process per calculation (no shared state)

**Artifact Flush Requirements** (per step):
- **Checkpoint**: `workdir/checkpoint_{step_id}.pkl` (or engine-specific format)
- **Summary**: `workdir/results_{step_id}.json` (parsed results)
- **Logs**: `workdir/log_{step_id}.txt` (stdout/stderr capture)

### E.4 Daemon Worker Lifecycle Management

**Minimal Management** (`src/quantumvitas/execution/worker_manager.py`):

```python
class WorkerManager:
    """Manages Python worker lifecycle."""
    
    def __init__(self, max_workers_per_calc: int = 1, idle_timeout: float = 300.0):
        self._workers: Dict[str, WorkerProcess] = {}  # calc_id -> worker
        self._lock = Lock()
        self.idle_timeout = idle_timeout
    
    def get_worker(self, calc_id: str) -> WorkerProcess:
        """Get or create worker for calculation."""
        with self._lock:
            if calc_id not in self._workers:
                self._workers[calc_id] = self._create_worker(calc_id)
            return self._workers[calc_id]
    
    def cleanup_idle(self):
        """Kill workers that have been idle > timeout."""
        # Check last activity timestamp
        # Kill idle workers
        pass
```

**Integration with JobManager**:
- `JobManager` tracks running calcs → can call `WorkerManager.cleanup_idle()` periodically
- On calc completion: explicitly kill worker (don't wait for timeout)

---

## F) Parser Boundary & Canonical Artifacts

### F.1 Current Parser Location

**Parsers**: `src/quantumvitas/analysis/parsers.py`

**QE-Specific Parsers**:
- `parse_scf_output_text()`: Parses QE `.out` files (regex for "JOB DONE", "total energy=", etc.)
- `parse_dos_output()`: Parses `dos.x` output
- `parse_bands_output()`: Parses `bands.x` output

**Assumptions**:
- QE file layout (specific text patterns)
- QE units (Ry for energies, eV for Fermi/HOMO/LUMO)
- QE-specific artifact paths (`{step_type}.out`)

### F.2 Proposed Parser Abstraction

**Engine-Specific Parsers** (internal):
- `src/quantumvitas/execution/parsers/qe_parser.py`: `parse_qe_scf_output()`
- `src/quantumvitas/execution/parsers/pyscf_parser.py`: `parse_pyscf_scf_output()`

**Canonical Artifacts** (engine-agnostic):
- `src/quantumvitas/execution/artifacts.py`:
  - `EnergyResult`: `{energy: float, unit: str, converged: bool}`
  - `ForcesResult`: `{forces: array, unit: str}`
  - `BandsResult`: `{bands: array, kpath: array, unit: str}`

**Parser Interface**:
```python
class Parser(ABC):
    @abstractmethod
    def parse_energy(self, output_text: str, workdir: Path) -> EnergyResult:
        """Extract energy from engine output."""
        pass
    
    @abstractmethod
    def parse_forces(self, output_text: str, workdir: Path) -> Optional[ForcesResult]:
        """Extract forces from engine output."""
        pass
```

**Parser Registration**:
- `src/quantumvitas/execution/parser_registry.py`: Maps `(engine_id, step_kind)` → parser class

### F.3 Artifact Storage Location

**Stable Location**: `calculations/<calc_id>/results/<step_id>/`

**Artifact Files**:
- `results/<step_id>/energy.json`: `EnergyResult` (canonical)
- `results/<step_id>/forces.json`: `ForcesResult` (if available)
- `results/<step_id>/bands.json`: `BandsResult` (if available)

**Relation to Raw Artifacts**:
- Raw artifacts (`raw/{step_type}.out`) remain for debugging/restart
- Canonical artifacts are **derived** from raw artifacts (never edited directly)

---

## G) Concurrency / Scheduling Review

### G.1 Current Job Execution

**JobManager** (`daemon/jobs.py`):
- `ThreadPoolExecutor(max_workers=1)` by default (sequential QE execution)
- Configurable via `settings.max_concurrent_calcs` (default: 2)
- Jobs execute in background threads (daemon remains responsive)

**Concurrency Model**:
- **Intra-calc**: Sequential (steps run one at a time within a calculation)
- **Inter-calc**: Configurable (can run multiple calculations concurrently if `max_workers > 1`)

### G.2 Locking / Reentrancy

**Per-Calc Locks** (`core/locking.py`):
- `calc_run_lock(calc_dir)`: Long-held during entire run (materialization + execution)
- `calc_edit_lock(calc_dir)`: Short-held during YAML writes
- **Implementation**: `portalocker` (cross-platform file locking)
- **Reentrancy**: NOT re-entrant (enforced with thread-local guard)

**Lock Acquisition**:
- `CalculationRunner.run()`: Acquires `calc_run_lock()` before execution
- `save_yaml_doc()`: Acquires `calc_edit_lock()` internally

**Concurrency Guarantees**:
- **Per-calc isolation**: Only one run per calculation at a time
- **Cross-calc**: Multiple calculations can run concurrently (if `max_workers > 1`)

### G.3 Resource Hints (OMP/MPI)

**OMP Threads**:
- `EngineConfig.omp_threads` (default: 1)
- Set via `OMP_NUM_THREADS` environment variable in `QECalculationRunner.run_step()`

**MPI Cores**:
- `EngineConfig.mpi_cores` (default: 1)
- `EngineConfig.mpi_command` (e.g., `"mpirun"`)
- Used in `QuantumEspressoEngine.build_command()` → `["mpirun", "-np", "4", "pw.x"]`

**Storage**:
- **Runtime**: `EngineConfig` (in-memory, not persisted)
- **Future**: Could store in `EnginePlan` for per-step resource hints

---

## H) Migration Plan (Phased, Minimal)

### Phase 0: Document Current QE Execution as "EngineBackend=QE"

**Goal**: Document existing QE execution without changing behavior.

**Changes**:
1. **Documentation**: Add docstrings to `QECalculationRunner`, `QuantumEspressoEngine` identifying them as QE-specific
2. **Type Hints**: Add `EngineBackend` enum (`QE`, `PYSCF`) for clarity

**Files to Touch**:
- `src/quantumvitas/core/engines/qe_calculation.py`: Add "QE-specific" docstring
- `src/quantumvitas/core/engines/qe.py`: Add "QE-specific" docstring

**Tests**: None (documentation only)

**Risk**: None

---

### Phase 1: Introduce EnginePlan Abstraction (Thin Wrapper)

**Goal**: Add `EnginePlan` as thin wrapper around existing step YAML/materialization (no behavior change).

**Changes**:
1. **New Module**: `src/quantumvitas/execution/plan.py`
   - Define `EnginePlan` dataclass (QE-specific fields for now)
   - Define `generate_qe_plan(step_spec, workdir) -> EnginePlan` (wraps existing materialization)
2. **Integration**: `CalculationRunner` generates plan on-the-fly, passes to runner (stub)

**Files to Create**:
- `src/quantumvitas/execution/__init__.py`
- `src/quantumvitas/execution/plan.py`

**Files to Modify**:
- `src/quantumvitas/calculation/runner.py`: Generate plan before execution (no-op for now)

**Tests**:
- Unit: `generate_qe_plan()` roundtrip (plan → existing execution path)
- Integration: Existing QE execution still works (no regressions)

**Risk**: Low (thin wrapper, no behavior change)

---

### Phase 2: Add Runner Interface (Subprocess Runner Uses Current Code Paths)

**Goal**: Add runner interface, implement `SubprocessRunner` wrapping existing QE code.

**Changes**:
1. **New Module**: `src/quantumvitas/execution/runner.py`
   - Define `Runner` abstract interface
   - Implement `SubprocessRunner` (wraps `QECalculationRunner.run_step()`)
2. **Integration**: `CalculationRunner` uses `SubprocessRunner` for QE steps

**Files to Create**:
- `src/quantumvitas/execution/runner.py`

**Files to Modify**:
- `src/quantumvitas/calculation/runner.py`: Replace direct `step.run()` with `runner.run(plan)`

**Tests**:
- Unit: `SubprocessRunner.run()` for QE step
- Integration: Existing QE execution still works (no regressions)

**Risk**: Low-Medium (changes execution path, but wraps existing code)

---

### Phase 3: Add Python Runner Skeleton (PySCF)

**Goal**: Add `PythonWorkerRunner` skeleton for PySCF (no need to support full PySCF now).

**Changes**:
1. **New Module**: `src/quantumvitas/execution/python_runner.py`
   - Implement `PythonWorkerRunner` (stub implementation)
   - Worker process: reads `plan.json`, executes via subprocess (same as current PySCFEngine)
2. **Integration**: `CalculationRunner` selects runner based on `plan.engine_id`

**Files to Create**:
- `src/quantumvitas/execution/python_runner.py`
- `src/quantumvitas/execution/worker_manager.py` (skeleton)

**Files to Modify**:
- `src/quantumvitas/calculation/runner.py`: Route to `PythonWorkerRunner` for PySCF steps

**Tests**:
- Unit: `PythonWorkerRunner.run()` stub (returns success with mock artifacts)
- Integration: PySCF execution still works (via subprocess, no long-lived worker yet)

**Risk**: Medium (adds new execution path, but minimal for now)

---

## Critical Questions

### Q1: What is the current on-disk SSOT for a step?

**Answer**: **Step YAML** (`steps/*.step.yaml`) is the on-disk SSOT for user intent, but **generated input file** (`raw/{step_type}.in`) is the SSOT for execution.

**Current State**:
- **Step YAML**: User-editable, contains parameters/cards
- **Input file**: Generated from step YAML, used by QE execution
- **Problem**: If step YAML changes but input isn't regenerated, execution uses stale input

**Solution**: **EnginePlan** becomes the execution SSOT (derived from step YAML, but authoritative for execution). Plan is regenerated before each run if step YAML changed.

---

### Q2: Where can "two sources of truth" drift happen today?

**Answer**: **Step YAML vs generated input file** can drift if:
1. User edits step YAML manually
2. Step is executed without materialization (rare, but possible)
3. Materialization fails silently (input file not updated)

**Current Mitigation**: `materialize_step_spec()` is always called before execution (in `CalculationRunner.run()`).

**Solution**: Store `EnginePlan` with `input_sha` → detect drift, regenerate plan if needed.

---

### Q3: How is "step done" defined today?

**Answer**: **Manifest `done` flag + file existence + marker detection**.

**Current Logic** (`calculation/step_done.py::is_step_done()`):
- QE steps: `{step_type}.out` exists + contains "JOB DONE"
- Wannier90 steps: `{seedname}.wout` exists

**Manifest Integration**: `done==true` only set if `is_step_done()` returns `True` AND execution returned `success=True`.

**Solution**: Keep manifest `done` flag, but add `artifact_sha` to plan → detect artifact corruption.

---

### Q4: How does incremental run decide what to reuse?

**Answer**: **Three SHA256 hashes: `step_sha`, `structure_sha`, `pseudo_set_sha`**.

**Current Logic** (`calculation/runner.py:270-336`):
- If `kind` matches + all three SHAs match + `done==true` → skip step
- If any SHA mismatches → rerun step

**Rationale**: Three SHAs capture all inputs (parameters, geometry, pseudos). If inputs unchanged, output should be identical.

**Solution**: Keep three SHA system, but add `plan_sha` to manifest (hash of `EnginePlan`) → detect plan changes even if step YAML unchanged.

---

### Q5: Where is workdir naming/structure defined? Is it stable across sessions?

**Answer**: **Workdir is stable across sessions** (path: `calculations/<calc_id>/raw/`).

**Definition**: `calculation/runner.py::compute_io_dir_from_calculation_model()` (SSOT for I/O directory path)

**Stability**: Workdir path is based on `calculation_dir` (stable) + `working_dir` name from `calculation.yaml` (default: `"raw"`). Path persists across daemon restarts.

**Restartability**: QE restart files (`outdir/{prefix}.save/`) persist in workdir → subsequent steps can read them.

**Solution**: Keep workdir structure, but document engine-specific subdirectory conventions (e.g., `raw/qe_scratch/` for QE, `raw/pyscf_checkpoints/` for PySCF).

---

### Q6: How are stdout/stderr/logs stored and surfaced?

**Answer**: **Per-step capture files: `raw/{step_type}.out` / `raw/{step_type}.err`**.

**Storage**:
- Stdout: `raw/{step_type}.out` (always overwritten, never versioned)
- Stderr: `raw/{step_type}.err` (always overwritten, never versioned)

**Surfacing**:
- **GUI**: `JobManager.get_job_logs(job_id)` reads `output_file` (points to `{step_type}.out`)
- **CLI**: Direct file access (not abstracted)

**Solution**: Keep per-step capture files, but add `log_type` to `ArtifactSpec` (`"stdout"`, `"stderr"`, `"combined"`) → support different log formats per engine.

---

### Q7: How are engine commands configured (pw.x path, mpi, env vars)?

**Answer**: **`EngineConfig` (in-memory only, not persisted)**.

**Current Storage**:
- **Runtime**: `EngineConfig` passed to `Engine` constructor
- **Source**: Settings (`settings.qe.bin_dir`), environment, or explicit override

**QE-Specific**:
- Executable path: Resolved via `QEEngineRegistry` (managed engine or PATH)
- MPI: `EngineConfig.mpi_command`, `mpi_cores` (default: 1)
- OMP: `EngineConfig.omp_threads` (default: 1)

**Solution**: Store engine config in `EnginePlan.provenance` → per-step resource hints, but keep global defaults in `EngineConfig`.

---

### Q8: What is the minimal artifact set required to restart a calc at step N+1 for QE today?

**Answer**: **QE restart files in `raw/outdir/{prefix}.save/`**.

**QE Restart Requirements**:
- Charge density: `outdir/{prefix}.save/charge-density.dat`
- Wavefunctions: `outdir/{prefix}.save/{K*.wfc}` (if k-points changed, may need all K files)
- Metadata: `outdir/{prefix}.save/data-file.xml` (QE internal state)

**Step Dependencies**:
- **SCF → NSCF**: Requires SCF charge density
- **NSCF → DOS**: Requires NSCF wavefunctions
- **SCF → PH**: Requires SCF charge density

**Solution**: Document restart artifact requirements per step type in `EnginePlan.expected_artifacts` → enable engine-agnostic restart detection.

---

### Q9: If we add a long-lived python worker, how do we guarantee it doesn't silently use stale in-memory state after user edits upstream?

**Answer**: **Fingerprint-based invalidation + mandatory artifact flush**.

**Proposed Solution**:
1. **Plan fingerprint**: Hash of `EnginePlan` (includes all inputs: structure, parameters, pseudos)
2. **Worker cache**: Worker stores `last_plan_fingerprint` in memory
3. **Invalidation**: If `plan.fingerprint != worker.last_plan_fingerprint` → flush cache, reload state from disk artifacts
4. **Mandatory flush**: After each step, worker MUST write checkpoint + summary to disk (even if in-memory state exists)

**Artifact Flush Requirements**:
- **Checkpoint**: `workdir/checkpoint_{step_id}.pkl` (or engine-specific format)
- **Summary**: `workdir/results_{step_id}.json` (parsed results)
- **Logs**: `workdir/log_{step_id}.txt` (stdout/stderr)

**Restart Guarantee**: Worker can be killed at any time → next step loads from disk artifacts, not in-memory cache.

---

### Q10: What are the 10 most likely failure modes during engine generalization?

**Answer**: Top 10 failure modes:

1. **Path issues**: Relative vs absolute paths in `EnginePlan.workdir` → QE assumes relative `outdir`, PySCF may need absolute
2. **Race conditions**: Multiple steps writing to same workdir simultaneously → per-calc locking mitigates, but need to verify
3. **Partial outputs**: Step fails mid-execution → artifacts incomplete, but manifest may mark `done=false` correctly
4. **Restart file corruption**: QE restart files corrupted → next step fails silently (need artifact validation)
5. **Environment variable leaks**: `OMP_NUM_THREADS` set for QE but not cleared for PySCF → thread contention
6. **Worker process zombie**: Python worker crashes but process not cleaned up → `WorkerManager` needs timeout/kill logic
7. **Plan drift**: `EnginePlan` stored but step YAML changes → plan becomes stale (need regeneration on materialization)
8. **Artifact path conflicts**: QE expects `{step_type}.out`, PySCF expects `results.json` → need engine-specific artifact paths
9. **Manifest desync**: Manifest `done=true` but artifacts missing → reconciliation should detect and reset
10. **Unit mismatch**: QE uses Ry, PySCF uses eV → canonical artifacts must normalize units

**Mitigation**:
- Comprehensive roundtrip tests (step YAML → plan → execution → artifacts)
- Artifact validation before marking `done=true`
- Worker health checks (ping worker, kill if unresponsive)
- Unit normalization in canonical artifacts (always use eV for energies)

---

## Recommended Next PR (Phase 0 Only)

### Scope: Document Current QE Execution as "EngineBackend=QE"

**Goal**: Add minimal documentation identifying QE-specific components without changing behavior.

**Changes**:
1. Add docstrings to `QECalculationRunner`, `QuantumEspressoEngine` identifying them as QE-specific
2. Add type hint: `EngineBackend = Literal["qe", "pyscf"]` for clarity

**Files to Modify**:
- `src/quantumvitas/core/engines/qe_calculation.py`: Add "QE-specific" docstring to `QECalculationRunner`
- `src/quantumvitas/core/engines/qe.py`: Add "QE-specific" docstring to `QuantumEspressoEngine`
- `src/quantumvitas/execution/__init__.py`: Create new module (empty for now, prepare for Phase 1)

**No Changes To**:
- Execution logic (no behavior change)
- Tests (documentation only)

**Validation**:
- Code review: Verify docstrings are accurate
- Existing tests: Still pass (no regressions)

**Estimated Effort**: 1 hour (documentation only)

---

**End of Report**
