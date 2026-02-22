# QMatSuite Architecture Code Review & Audit

**Version**: 1.0  
**Date**: 2026-01-02  
**Scope**: Full codebase audit against `CONSTITUTION_ZH.md` and `WORKFLOW_PRESET_DESIGN_V0.md`

---

## 1. Executive Summary

This document provides a comprehensive inventory of the current codebase implementation status, identifying what exists, what's missing, and what needs alignment with the constitution. The audit confirms that QMatSuite has a **solid foundation** for the preset/workflow system but requires targeted extensions for:

1. **Role-based applicability** (new concept to implement)
2. **Project export bundles** (snapshot.py exists but needs enhancement)
3. **Calc type / system_kind** (not yet implemented)
4. **Wannier90 integration** (step types declared in docs but not implemented)
5. **PySCF integration** (not yet started)

---

## 2. Module Inventory

### 2.1 Preset System (`src/qmatsuite/presets/`)

| File | Purpose | Constitution Alignment | Status |
|------|---------|----------------------|--------|
| `paramspace.py` | ParamSpace framework with Cell types (VALUE, NOT_APPLICABLE, WILDCARD) | ✅ §10.7 | Complete |
| `space_variant.py` | ParamSpaceVariant with `applies_to_step_types` | ✅ §10.7.9 | Complete |
| `variants_registry.py` | Single source of truth for variant definitions | ✅ §10.7.8 | Complete |
| `compiler.py` | Forward generation (options → params) | ✅ §10.3 | Complete |
| `detector.py` | Reverse detection (params → options) | ✅ §10.4-10.5 | Complete |
| `dimensions.py` | Enum definitions for preset options | ✅ | Complete |
| `precision.py` | Precision computation utilities | ✅ §10.9 | Complete |
| `precision_variants.py` | Precision ParamSpace variants (default/nscf/bands_pw) | ✅ §10.9.2 | Complete |
| `precision_context.py` | Context resolution for precision | ✅ §10.9.1 | Complete |
| `receivers.py` | Precision receiver specifications | ✅ | Complete |
| `integration.py` | Step document integration | ✅ | Complete |
| `catalog.py` | UI catalog presets | ✅ | Complete |

**Assessment**: The preset system is well-implemented and aligned with the constitution.

### 2.2 Workflow System (`src/qmatsuite/workflow/`)

| File | Purpose | Constitution Alignment | Status |
|------|---------|----------------------|--------|
| `registry.py` | StepTypeRegistry with specs | ✅ §13.2 | Complete |
| `templates.py` | WorkflowTemplate definitions (runtime-only) | ✅ §10.2, §13.1 | Complete |
| `step_factory.py` | Step creation via factory | ✅ §13.3 | Complete |

**Assessment**: Workflow system correctly implements runtime-only interpretation. Templates are not persisted.

### 2.3 Pseudo Management (`src/qmatsuite/core/pseudo*.py`)

| File | Purpose | Constitution Alignment | Status |
|------|---------|----------------------|--------|
| `pseudo.py` | Core pseudo utilities | ✅ §6-7 | Complete |
| `pseudo_config.py` | Pseudo configuration | ✅ §7.1 | Complete |
| `pseudo_options.py` | UI options building | ✅ §7.5 | Complete |
| `pseudo_provenance.py` | SHA256/SHA_FAMILY computation | ✅ §6.1-6.2 | Complete |
| `pseudo_materialization.py` | Step0 materialization | ✅ §7.7 | Complete |
| `pseudo_libinfo.py` | Library info bundle | ✅ | Complete |
| `pseudo_runtime.py` | Runtime pseudo resolution | ✅ §7.2 | Complete |
| `pseudo_installs.py` | Archive installation | ✅ | Complete |

**Assessment**: Pseudo system implements the identity triple (filename, sha256, sha_family) correctly.

### 2.4 Engine Management (`src/qmatsuite/core/engines/`, `src/qmatsuite/engine/`)

| File | Purpose | Constitution Alignment | Status |
|------|---------|----------------------|--------|
| `core/engines/base.py` | Abstract Engine interface | ✅ | Partial |
| `core/engines/qe.py` | QE engine implementation | ✅ | Complete |
| `core/engines/qe_resolver.py` | Two-state QE resolution | ✅ §9.4 | Complete |
| `core/settings.py` | Settings with `qe.bin_dir` | ✅ §9.5 | Complete |

**Assessment**: Two-state engine model is implemented. No PATH fallback. Wannier90/PySCF engines not yet implemented.

### 2.5 Project Export (`src/qmatsuite/project/snapshot.py`)

| Feature | Status | Notes |
|---------|--------|-------|
| Export project metadata | ✅ | Complete |
| Export structures | ✅ | Complete |
| Export calculations + steps | ✅ | Complete |
| Export pseudo identity triple | ✅ | sha256 + sha_family included |
| Bundle levels (inputs-only/analyzed/full) | ❌ | Not implemented |
| Manifest with hashes | ❌ | Not implemented |
| Analysis staleness tracking | ❌ | Not implemented |

**Assessment**: Snapshot.py provides basic export but needs enhancement for bundle levels.

---

## 3. step.yml Truth Layer Audit

### 3.1 Where step.yml is Written

| Location | Operation | Constitution Check |
|----------|-----------|-------------------|
| `workflow/step_factory.py:create_step_doc()` | Creates new step | ✅ Pure inputs only |
| `presets/integration.py:apply_preset_to_step()` | Applies preset dimension | ✅ Only modifies declared keys |
| `core/yaml_io.py:save_yaml_doc()` | Generic YAML save | ✅ Uses Doc abstraction |

### 3.2 What step.yml Contains

Per Constitution §10.1.2, step.yml must be "pure inputs". Current implementation:

```yaml
# step.yaml structure
meta:
  id: <ULID>
  name: <string>
  slug: <string>
  path: <relative>
  kind: "step"
step_type: <string>
parameters:
  CONTROL: {...}
  SYSTEM: {...}
  ELECTRONS: {...}
cards:
  K_POINTS: {...}
  ATOMIC_SPECIES: {...}
```

**Violation Check**: 
- ✅ No workflow identifiers stored
- ✅ No preset states/options stored
- ✅ No provenance metadata in step.yml
- ✅ structure_id removed from step.yml (per Constitution)

### 3.3 Preset Apply - Parameter Locality

Per Constitution §10.3.3, preset apply must only modify keys in its ParamSpace Variant.

**Audit of `variants_registry.py:compile_dimension_patch_for_step()`**:
- ✅ Uses `compile_profile_patch()` which only touches declared keys
- ✅ Returns explicit `deletions` set for NOT_APPLICABLE cells
- ✅ Other parameters are preserved (not reset)

---

## 4. Pseudo Identity Triple Audit

### 4.1 Where Triple is Recorded

| Location | Field | Present |
|----------|-------|---------|
| `calculation.yaml` → `species_map` | `pseudo_basename` | ✅ |
| `calculation.yaml` → `species_map` | `pseudo_sha256` | ✅ |
| `calculation.yaml` → `species_map` | `pseudo_sha_family` | ✅ |

### 4.2 Step0 Refresh Rules

Per Constitution §7.6, Step0 must refresh the triple after materialization.

**Location**: `core/pseudo_materialization.py:materialize_calc_pseudos()`
- ✅ Computes SHA256 after copy
- ✅ Verifies SHA256 matches expected
- ⚠️ Does NOT currently write back to calc.yaml (deferred to runner)

**Gap**: Step0 refresh write-back should be explicit in materialization flow.

---

## 5. Engine Selection Audit

### 5.1 Two-State Model Implementation

Per Constitution §9.4.2:

| State | settings.qe.bin_dir | Behavior | Implemented |
|-------|---------------------|----------|-------------|
| External QE | `!= null` | Use specified bin_dir | ✅ |
| Internal QE | `== null` | Auto-select from .qmatsuite/engines/qe | ✅ |

### 5.2 No PATH Fallback

Per Constitution §9.4.3:

**Checked in** `core/engines/qe_resolver.py`:
- ✅ No `which`/`shutil.which` calls
- ✅ No PATH environment variable scanning
- ✅ No QE_HOME fallback
- ✅ Error raised if internal QE not found

---

## 6. Gaps vs Constitution

### 6.1 Missing: Role-Based Applicability

**Constitution Decision A**: Introduce StepRole for topology-based preset applicability.

**Current State**: 
- `applies_to_step_types` exists in ParamSpaceVariant
- No role inference from step topology
- No `applies_to: List[(StepType, Role)]` representation

**Required Changes**:
1. Add `StepRole` enum (e.g., `default`, `nscf_dos`, `nscf_bands`)
2. Add role inference algorithm (pure function from step graph)
3. Extend ParamSpaceVariant.applies_to to include roles

### 6.2 Missing: Project Export Bundle Levels

**Constitution Decision B**: Three export bundle levels.

**Current State**:
- `snapshot.py` exports all data in one format
- No manifest with hashes
- No analysis versioning/staleness

**Required Changes**:
1. Add `BundleLevel` enum (INPUTS_ONLY, INPUTS_ANALYZED, INPUTS_OUTPUTS)
2. Add `manifest.json` schema with file hashes
3. Add analysis staleness markers

### 6.3 Missing: Calc Type / System Kind

**Constitution Decision C**: Immutable calc types with engine compatibility.

**Current State**:
- Calculations have no explicit `system_kind` field
- No engine compatibility enforcement
- Calc conversion not blocked

**Required Changes**:
1. Add `system_kind` field to CalculationModel (`periodic`, `molecular`)
2. Add engine compatibility rules
3. Block in-place calc type conversion

### 6.4 Missing: Wannier90 Integration

**Current State**:
- Step types declared in `WORKFLOW_PRESET_DESIGN_V0.md` but not in code
- No Wannier90 engine adapter
- No `.win` file generator/parser

**Required Changes**:
1. Add step types: `w90_preproc`, `pw2wannier90`, `w90_main`, `postw90`
2. Add Wannier90 engine adapter
3. Add data dependency definitions
4. Add at least one demo workflow

### 6.5 Missing: PySCF Integration

**Current State**:
- Not started

**Required Changes**:
1. Add PySCF engine adapter (python-native)
2. Add step types for RHF/DFT single point
3. Add molecular system_kind enforcement
4. Add demo project

---

## 7. Concrete Refactor Suggestions

### 7.1 Role Inference (Minimal Breakage)

1. **Add new file**: `src/qmatsuite/workflow/role_inference.py`
   - Pure function: `infer_step_roles(step_graph) -> Dict[str, StepRole]`
   - Uses topology only (no step.yml reading)

2. **Extend ParamSpaceVariant** in `space_variant.py`:
   ```python
   @dataclass
   class ParamSpaceVariant:
       applies_to_step_types: FrozenSet[str]
       applies_to_roles: Optional[FrozenSet[StepRole]] = None  # If None, matches all roles
   ```

3. **Update matching logic** in `variants_registry.py`:
   - Add role parameter to `get_variant()`
   - Check role compatibility if `applies_to_roles` is set

### 7.2 Export Bundle Enhancement (Minimal Breakage)

1. **Add new file**: `src/qmatsuite/project/bundle.py`
   - Separate from snapshot.py to avoid breaking changes
   - Implements `create_bundle(project_root, level, output_path)`

2. **Add manifest schema**:
   ```python
   @dataclass
   class BundleManifest:
       version: int = 1
       bundle_level: str  # "inputs_only" | "inputs_analyzed" | "inputs_outputs"
       files: List[BundleFile]  # path, sha256, optional
       pseudo_identities: Dict[str, PseudoIdentity]  # element -> triplet
       created_at: str
       qmatsuite_version: str
   ```

### 7.3 Calc Type System (Minimal Breakage)

1. **Extend CalculationModel** in `core/models.py`:
   ```python
   @dataclass
   class CalculationModel:
       # ... existing fields ...
       system_kind: Optional[str] = None  # "periodic" | "molecular"
   ```

2. **Add validation hook** in calculation creation:
   - Enforce system_kind is immutable after creation
   - Validate engine compatibility

### 7.4 Wannier90 Integration (New Module)

1. **Add step types** to `workflow/registry.py`:
   ```python
   "w90_preproc": StepTypeSpec(
       id="w90_preproc",
       engine="wannier90",
       executable="wannier90.x -pp",
       ...
   ),
   ```

2. **Add engine adapter**: `src/qmatsuite/engine/wannier90_engine.py`

3. **Add input generator**: `src/qmatsuite/io/generator/wannier90_generator.py`

---

## 8. Test Coverage Assessment

### 8.1 Existing Contract Tests

| Module | Test File | Coverage |
|--------|-----------|----------|
| ParamSpace | `tests/unit/test_paramspace.py` | Roundtrip tests |
| Variants | `tests/unit/test_variants_registry.py` | Detection/compilation |
| Workflow | `tests/unit/test_workflow.py` | Registry, templates, factory |
| Presets | `tests/unit/test_presets.py` | Compiler/detector |

### 8.2 Missing Tests

1. **Role inference tests** (not implemented yet)
2. **Bundle export tests** (snapshot tests exist, bundle levels don't)
3. **Calc type immutability tests**
4. **Cross-engine workflow tests** (Wannier90 + QE)
5. **E2E UI tests** (only basic Playwright tests)

---

## 9. Recommendations

### Priority 1: Foundation (Before Features)
1. Add role inference spec and implementation
2. Enhance export bundles with manifest
3. Add calc type/system_kind enforcement

### Priority 2: Integration Proof
1. Implement Wannier90 step types and engine
2. Create one working Wannier90 demo
3. Validate cross-engine data dependencies work

### Priority 3: Ecosystem Expansion
1. Implement PySCF engine (molecular system_kind)
2. Add packaging/update strategy
3. Complete UI bug-bash

---

## 10. Appendix: File-by-File Status

### A. Core Files Touching Presets/Workflows

| File | Lines | Status | Notes |
|------|-------|--------|-------|
| `presets/paramspace.py` | 937 | ✅ | ParamSpace framework complete |
| `presets/variants_registry.py` | 642 | ✅ | Variant definitions complete |
| `presets/compiler.py` | 335 | ✅ | Thin wrappers work |
| `presets/detector.py` | 697 | ✅ | Variants-based detection |
| `workflow/registry.py` | 375 | ✅ | StepTypeRegistry complete |
| `workflow/templates.py` | 557 | ✅ | WorkflowService complete |
| `project/snapshot.py` | 837 | ⚠️ | Needs bundle levels |
| `core/models.py` | ~800 | ⚠️ | Needs system_kind |

### B. Step Default Parameters

Current defaults in `calculation/step_defaults.py`:
- scf, nscf, dos, bands, bands_pw, relax, vc-relax, md

Missing:
- ph, q2r, matdyn, dynmat (phonon)
- w90_preproc, pw2wannier90, w90_main, postw90 (Wannier90)

---

## 11. Demo Generator & Pseudo Library

### 11.1 Demo Generator Files

| File | Purpose | Entry Point |
|------|---------|-------------|
| `tools/generate_demo_snapshots.py` | Generate si_bands_demo.yml and si_dos_demo.yml | `main()` |
| `tools/regenerate_si_bands_demo.py` | Regenerate only si_bands_demo.yml | `main()` |
| `tools/import_tutorial_datasets.py` | Generate demos from tests/data/ folders (0_* to 19_*) | `main()` |

### 11.2 Pseudo Library Path

- **Internal pseudo library**: `resources/pseudo/` (repo root)
- **Demo generation requirement**: All pseudos must exist in `resources/pseudo/` before generation
- **No manifest lookup**: Demo generators use direct file system access only

### 11.3 Demo Generation Invocation

**CLI commands**:
```bash
# Generate main demos (si_bands, si_dos)
python tools/generate_demo_snapshots.py

# Regenerate si_bands only
python tools/regenerate_si_bands_demo.py

# Generate all tutorial demos (0_* to 19_*)
python tools/import_tutorial_datasets.py
```

**Where species_map is written**:
- `extract_species_map_from_qe_input()` in `calculation/folder_import.py` extracts `{mass, pseudopot}` from QE inputs
- `export_project_to_snapshot()` in `project/snapshot.py` enhances species_map with sha256/sha_family (fallback mechanism)
- **Gap**: Demo generators should compute triple upfront from `resources/pseudo/` before export

**Demo enumeration**:
- `generate_demo_snapshots.py`: Hardcoded list of 2 demos
- `import_tutorial_datasets.py`: Scans `tests/data/` for folders matching `0_*` through `19_*`

---

*This audit was conducted against the codebase as of 2026-01-02.*

