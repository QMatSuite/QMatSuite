# API Facade Slimming Design

**Date**: 2026-01-22  
**Status**: DESIGN DOCUMENT (No Implementation)  
**Reference**: `docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`, `docs/history/plans/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md`

---

## SECTION 0: Executive Summary

### What Is Wrong Today

**Symptoms**:

1. **"Shadow Kernel" Pattern**: `api.py` has become a dumping ground for re-exports. Evidence:
   - **642 re-exports** detected (many duplicates)
   - **26 modules** re-exporting from kernel (top: `core.resolution` 115 symbols, `core.project_utils` 63 symbols)
   - API effectively re-exports half the kernel, violating the spirit of the architecture

2. **Wrapper Sprawl**: One wrapper per internal function creates maintenance burden:
   - **210 static methods** (many are pure pass-throughs)
   - **~82 pass-through wrappers** (estimated: simple `from X import Y as _Y; return _Y(...)` pattern)
   - **11,887 lines** in a single file (unmaintainable)

3. **No "One Capability, One Entrypoint"**: Frontends must know which of 5-10 wrappers to call for a single logical operation:
   - To analyze output: `parse_scf_output()` + `plot_scf_convergence()` + `save_figure()` + re-export `DOSData`
   - To visualize structure: `visualize_structure()` + `get_structure_vis_data()` + `build_display_atoms()` + re-export `DisplayModeParams`
   - To run calculation: `run_calculation()` + `build_resource_index()` + `load_project_config()` + re-export `Calculation`

4. **Frontend Confusion**: CLI, daemon, and future Jupyter must navigate 200+ methods to find the right one. No clear capability grouping.

**Why It Becomes Unmaintainable**:

- **Import coupling**: Every kernel change risks breaking API re-exports
- **Testing burden**: 200+ wrappers need tests, but many are trivial pass-throughs
- **Documentation sprawl**: Hard to document 200+ methods meaningfully
- **Breaking changes**: Moving/renaming kernel symbols breaks API surface
- **No clear contract**: What is the "stable API"? Everything? Nothing?

### What "Good" Looks Like

**North Star Principles**:

1. **"One Capability, One Entrypoint"**: Each logical capability (e.g., "analyze calculation output", "run calculation", "visualize structure") has ONE primary entrypoint. Frontends call the same endpoint regardless of whether they're CLI, GUI, or Jupyter.

2. **Minimal Stable Surface**: Public API is small (~20-30 capability endpoints), well-documented, and stable. Internal implementation can change without breaking frontends.

3. **No Mass Re-exporting**: API does NOT re-export internal kernel types. Frontends operate on API-owned DTOs (simple dataclasses/dicts) returned by capability endpoints.

4. **Capability-Based Organization**: API organized by capabilities (project, structure, calculation, step, run, analysis, presets, workflow), not by kernel module structure.

### North Star Public Surface

**Core Service**:
- `QVService` (class) - Primary service interface

**Capability Groups** (instance methods on `QVService`):
- `svc.project.*` - Project management (init, config, snapshot)
- `svc.structure.*` - Structure operations (import, export, list, get)
- `svc.calculation.*` - Calculation CRUD (create, configure, list, get, delete)
- `svc.step.*` - Step operations (create, configure, get, delete)
- `svc.run.*` - Execution (run calculation, run step)
- `svc.analysis.*` - Analysis (analyze output, extract artifacts)
- `svc.presets.*` - Preset operations (detect, apply, catalog)
- `svc.workflow.*` - Workflow operations (detect, validate, instantiate)

**Core Types** (API-owned, not re-exported):
- `QVServiceError` (exception) - Base exception
- `ResourceNotFoundError`, `AmbiguousSelectorError`, `SelectorNotFoundError` (exceptions)
- `ResourceMeta` (dataclass) - Resource metadata DTO
- `StepMode`, `StepStatus` (Enum) - Execution state enums

**Total**: ~1 class + ~8 capability groups (~20-30 methods) + ~5-10 types = **~35-40 public symbols**

**Current**: 1 class + 210 static methods + 642 re-exports = **~850+ symbols**

**Reduction Target**: ~95% reduction in public surface.

---

## SECTION 1: Spec Compliance Audit

### Evidence-Based Compliance Check

**Command**: `rg -n "^from quantumvitas\.api import|^import quantumvitas\.api" src/quantumvitas/cli`
**Result**: 8 matches ✅
**Evidence**: CLI imports only from `quantumvitas.api`

**Command**: `rg -n "^from quantumvitas\.api import|^import quantumvitas\.api" src/quantumvitas/daemon`
**Result**: 1 match ✅
**Evidence**: Daemon imports only from `quantumvitas.api`

**Command**: `rg -n "^from quantumvitas\.(core|calculation|drivers|analysis|io|engine|workflow|presets)\b" src/quantumvitas/cli`
**Result**: 0 matches ✅
**Evidence**: CLI has no direct kernel imports

**Command**: `rg -n "^from quantumvitas\.(core|calculation|drivers|analysis|io|engine|workflow|presets)\b" src/quantumvitas/daemon`
**Result**: 0 matches ✅
**Evidence**: Daemon has no direct kernel imports

**Command**: `rg -n "^from quantumvitas\.(core|calculation|drivers|analysis|io|engine|workflow|presets) import" src/quantumvitas/api.py`
**Result**: 26 matches ⚠️
**Evidence**: API imports from kernel (allowed by spec), but see "Backdoors" below

### Backdoors: API Re-exporting Half the Kernel

**Problem**: While gates pass (frontends don't import kernel directly), `api.py` has become a "shadow kernel" by re-exporting 642 symbols from kernel modules.

**Evidence**:
```bash
# Top 10 modules by re-export count (from audit script):
quantumvitas.core.resolution: 115 symbols
quantumvitas.core.project_utils: 63 symbols
quantumvitas.core.pseudo_config: 51 symbols
quantumvitas.core.models: 45 symbols
quantumvitas.core.resources: 25 symbols
quantumvitas.analysis.structure_viz: 23 symbols
quantumvitas.calculation.structure_steps: 19 symbols
quantumvitas.calculation.naming: 18 symbols
quantumvitas.core.yamldoc: 15 symbols
quantumvitas.io: 13 symbols
```

**Why This Violates the Spirit**:

1. **Coupling**: Frontends are still tightly coupled to kernel internals, just through a different import path
2. **Breaking Changes**: Any kernel refactor breaks API surface
3. **No Abstraction**: API provides no abstraction layer - it's just a pass-through
4. **Spec Intent**: The spec says "api/ is the single entry point" - it should be a **capability** entry point, not a **symbol** entry point

**Spec Mismatch**:

The spec (`docs/laws/L2/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`) says:
> "api/ is the PUBLIC API LAYER (single entry point to kernel)"

But the current implementation treats "entry point" as "re-export everything", not "provide capability endpoints".

**Intended Behavior** (from spec):
- Frontends call `svc.run_calculation(selector)` → API orchestrates kernel calls → Returns simple DTO
- Frontends do NOT import `Calculation`, `Step`, `ResourceMeta` types directly

**Current Behavior**:
- Frontends call `svc.run_calculation(selector)` → But also import `Calculation`, `Step`, `ResourceMeta` from `api`
- API re-exports internal types, creating tight coupling

---

## SECTION 2: API Surface Inventory

### Hard Numbers

**File Size**: 11,887 lines (single file)

**Method Counts**:
- **Instance methods**: 24
- **Static methods**: 210
- **Total methods**: 234

**Re-export Counts**:
- **Total re-exports detected**: 642 (from AST analysis)
- **Unique re-exports** (estimated): ~150-200 (many duplicates)
- **Re-exports in `__all__`**: 26

**`__all__` Exports**:
```python
__all__ = [
    "QVService", "QVServiceError",
    "ResourceNotFoundError", "RegistryOutOfSyncError", "AmbiguousSelectorError",
    "SelectorNotFoundError", "ContextNotFoundError", "VolumeParserError",
    "DisplayModeParams", "ResourceContext", "ProjectConfigError", "ResourceMeta",
    "StepMode", "StepStatus", "ParameterOverride", "BandAnalysisFiles",
    "Step", "Calculation", "EngineConfig", "CalculationStepEntry", "QeEngine",
    "ProjectContext", "PresetCompilationError", "PrecisionContextError",
    "DIMENSION_PRECISION", "PrecisionOption",
]
```

### Classification Table

| Category | Type | Count | Examples | Should Remain? |
|----------|------|-------|----------|----------------|
| **A) Capability Endpoints** | Instance/Static | ~30 | `run_calculation()`, `configure_step()`, `init_project()`, `analyze_output()` | ✅ Yes (but consolidate) |
| **B) Pass-Through Wrappers** | Static | ~82 | `slugify()`, `generate_resource_id()`, `read_structure()`, `parse_scf_output()` | ❌ No (absorb into capabilities) |
| **C) Re-Exports (Types)** | Module-level | ~150-200 | `Calculation`, `Step`, `ResourceMeta`, `StepMode`, `StepStatus` | ⚠️ Replace with API-owned DTOs |
| **D) Re-Exports (Functions)** | Module-level | ~100+ | `resolve_calculation()`, `load_project_config()`, `build_resource_index()` | ❌ No (internalize, use via capabilities) |
| **E) Re-Exports (Exceptions)** | Module-level | ~10 | `ResourceNotFoundError`, `AmbiguousSelectorError` | ✅ Yes (but minimize) |
| **F) Internal Helpers** | Static (prefixed `_`) | ~20 | `_build_structure_vis_payload()`, `_detect_calculation_results_dir()` | ✅ Yes (internal only) |

### Top N Largest Re-Export Clusters

**By Source Module** (from AST analysis):

| Module | Re-Export Count | Top Symbols | Rationale for Removal |
|--------|----------------|-------------|----------------------|
| `quantumvitas.core.resolution` | 115 | `resolve_calculation`, `build_resource_index`, `ResourceIndex`, `ResolvedResource` | Functions should be internal; types should be DTOs |
| `quantumvitas.core.project_utils` | 63 | `load_project_config`, `save_project_config`, `find_structure_entry` | Functions should be internal; use via capabilities |
| `quantumvitas.core.pseudo_config` | 51 | `PseudoConfig`, `load_pseudo_config`, `get_ssl_context` | Types should be DTOs; functions internal |
| `quantumvitas.core.models` | 45 | `CalculationModel`, `load_calculation`, `save_calculation` | Heavy dataclasses - replace with DTOs |
| `quantumvitas.core.resources` | 25 | `ResourceMeta`, `generate_resource_id`, `slugify` | `ResourceMeta` → DTO; utilities → internal |
| `quantumvitas.analysis.structure_viz` | 23 | `visualize_structure`, `DisplayModeParams`, `build_display_atoms` | Capability endpoint; types → DTOs |
| `quantumvitas.calculation.structure_steps` | 19 | `StructureStepSpec`, `STEP_TYPE_MODULE_MAP` | Types → DTOs; constants → internal |
| `quantumvitas.calculation.naming` | 18 | `find_calculation_raw_dir`, `BandAnalysisFiles` | Functions → internal; types → DTOs |
| `quantumvitas.core.yamldoc` | 15 | `StepDoc`, `PathNotFoundError` | Types → DTOs; exceptions → minimal set |
| `quantumvitas.io` | 13 | `read_structure`, `write_structure` | Functions → capability endpoints |

**Total from top 10**: ~387 re-exports (60% of total)

**Strategy**: Eliminate these clusters first - they represent the bulk of the "shadow kernel" problem.

---

## SECTION 3: Capability Map

### Design Philosophy

**"One Capability, One Entrypoint"**: Each logical capability has ONE primary method. Frontends (CLI, GUI, Jupyter) call the same endpoint. The endpoint orchestrates multiple kernel calls internally.

**Return Types**: Capability endpoints return API-owned DTOs (simple dataclasses or dicts), NOT re-exported kernel types.

### Proposed Capability Groups

#### 1. `svc.project.*` - Project Management

**Entrypoints**:
```python
# Project lifecycle
svc.project.init(path: Path, name: str) -> ProjectInfo
svc.project.get_config() -> ProjectConfig
svc.project.update_config(updates: dict) -> ProjectConfig
svc.project.snapshot.export(path: Path) -> SnapshotInfo
svc.project.snapshot.import_from(path: Path) -> ProjectInfo

# Context detection
svc.project.detect_context(cwd: Path) -> ProjectContext
```

**Absorbs**:
- `init_project()` → `svc.project.init()`
- `load_project_config()` → `svc.project.get_config()`
- `save_project_config()` → `svc.project.update_config()`
- `export_project_snapshot()` → `svc.project.snapshot.export()`
- `create_project_from_snapshot()` → `svc.project.snapshot.import_from()`
- `detect_project_root()` → `svc.project.detect_context()`
- `require_project_root()` → internal (used by capabilities)

**Return Types**:
- `ProjectInfo`: `{id: str, name: str, path: Path, created: datetime}`
- `ProjectConfig`: `{name: str, structures: List[StructureRef], calculations: List[CalculationRef]}`
- `ProjectContext`: `{project_root: Path, is_project: bool, is_calculation: bool, is_step: bool}`

**Re-exports Eliminated**: `ProjectContext` (replace with DTO), `ProjectConfigError` (keep as exception)

---

#### 2. `svc.structure.*` - Structure Operations

**Entrypoints**:
```python
# Structure CRUD
svc.structure.list() -> List[StructureInfo]
svc.structure.get(selector: str) -> StructureInfo
svc.structure.import_from(path: Path, name: str) -> StructureInfo
svc.structure.import_from_template(template_id: str, name: str) -> StructureInfo
svc.structure.export(selector: str, path: Path, format: str) -> ExportInfo
svc.structure.delete(selector: str) -> DeleteResult
svc.structure.rename(selector: str, new_name: str) -> StructureInfo

# Structure search (if needed by Jupyter)
svc.structure.search_online(query: str) -> List[StructureCandidate]
svc.structure.fetch_from_optimade(id: str) -> StructureInfo
```

**Absorbs**:
- `list_structures()` → `svc.structure.list()`
- `get_structure()` → `svc.structure.get()`
- `import_structure()` → `svc.structure.import_from()`
- `import_structure_from_template()` → `svc.structure.import_from_template()`
- `write_structure()` → `svc.structure.export()`
- `delete_structure()` → `svc.structure.delete()`
- `rename_structure()` → `svc.structure.rename()`
- `search_online_structures()` → `svc.structure.search_online()`
- `fetch_structure_from_optimade()` → `svc.structure.fetch_from_optimade()`
- `read_structure()` → internal (used by capabilities)

**Return Types**:
- `StructureInfo`: `{id: str, name: str, path: Path, formula: str, n_atoms: int}`
- `StructureCandidate`: `{id: str, formula: str, source: str, score: float}`
- `ExportInfo`: `{path: Path, format: str, size: int}`

**Re-exports Eliminated**: `PMGStructure` (internal only), `StructureStepSpec` (internal only)

---

#### 3. `svc.calculation.*` - Calculation CRUD

**Entrypoints**:
```python
# Calculation CRUD
svc.calculation.list() -> List[CalculationInfo]
svc.calculation.get(selector: str) -> CalculationDetail
svc.calculation.create(structure_selector: str, name: str) -> CalculationInfo
svc.calculation.create_from_template(template_id: str, structure_selector: str) -> CalculationInfo
svc.calculation.configure(selector: str, updates: dict) -> CalculationDetail
svc.calculation.delete(selector: str) -> DeleteResult
svc.calculation.rename(selector: str, new_name: str) -> CalculationInfo

# Calculation metadata
svc.calculation.get_steps(selector: str) -> List[StepInfo]
svc.calculation.get_structure(selector: str) -> StructureInfo
```

**Absorbs**:
- `list_calculations()` → `svc.calculation.list()`
- `get_calculation()` → `svc.calculation.get()`
- `init_calculation()` → `svc.calculation.create()`
- `copy_calculation_template()` → `svc.calculation.create_from_template()`
- `configure_calculation()` → `svc.calculation.configure()`
- `delete_calculation()` → `svc.calculation.delete()`
- `rename_calculation()` → `svc.calculation.rename()`
- `list_steps()` → `svc.calculation.get_steps()`
- `change_calculation_structure()` → `svc.calculation.configure()` (with structure update)

**Return Types**:
- `CalculationInfo`: `{id: str, name: str, structure_id: str, n_steps: int, status: str}`
- `CalculationDetail`: `{id: str, name: str, structure: StructureInfo, steps: List[StepInfo], mode: str}`
- `StepInfo`: `{id: str, type: str, status: str, done: bool}`

**Re-exports Eliminated**: `Calculation` (replace with DTOs), `CalculationModel` (internal only), `CalculationStepEntry` (replace with `StepInfo` DTO)

---

#### 4. `svc.step.*` - Step Operations

**Entrypoints**:
```python
# Step CRUD
svc.step.get(calculation_selector: str, step_selector: str) -> StepDetail
svc.step.create(calculation_selector: str, step_type: str, after: Optional[str]) -> StepInfo
svc.step.configure(calculation_selector: str, step_selector: str, params: dict) -> StepDetail
svc.step.delete(calculation_selector: str, step_selector: str) -> DeleteResult
svc.step.reorder(calculation_selector: str, step_ids: List[str]) -> List[StepInfo]

# Step configuration
svc.step.get_default_params(step_type: str) -> dict
svc.step.validate_params(step_type: str, params: dict) -> ValidationResult
```

**Absorbs**:
- `get_step()` → `svc.step.get()`
- `init_step()` → `svc.step.create()`
- `configure_step()` → `svc.step.configure()`
- `delete_step()` → `svc.step.delete()`
- `reorder_calculation_steps()` → `svc.step.reorder()`
- `get_default_step_params()` → `svc.step.get_default_params()`
- `update_step_params()` → `svc.step.configure()` (partial update)

**Return Types**:
- `StepDetail`: `{id: str, type: str, status: str, params: dict, artifacts: List[ArtifactInfo]}`
- `ValidationResult`: `{valid: bool, errors: List[str], warnings: List[str]}`

**Re-exports Eliminated**: `Step` (replace with DTOs), `StepMode`, `StepStatus` (keep as Enums, but API-owned), `ParameterOverride` (replace with dict)

---

#### 5. `svc.run.*` - Execution

**Entrypoints**:
```python
# Execution
svc.run.calculation(selector: str, mode: str = "incremental") -> RunResult
svc.run.step(calculation_selector: str, step_selector: str, force: bool = False) -> RunResult
svc.run.input_file(path: Path, engine: str) -> RunResult

# Execution status
svc.run.get_status(calculation_selector: str) -> RunStatus
```

**Absorbs**:
- `run_calculation()` → `svc.run.calculation()`
- `run_step()` → `svc.run.step()`
- `run_single_step()` → `svc.run.step()` (with single step)
- `run_input_step()` → `svc.run.input_file()`

**Return Types**:
- `RunResult`: `{status: str, steps: List[StepRunInfo], duration: float, errors: List[str]}`
- `RunStatus`: `{calculation_id: str, current_step: Optional[str], progress: float, is_running: bool}`
- `StepRunInfo`: `{step_id: str, status: str, output_file: Path, duration: float}`

**Re-exports Eliminated**: `CalculationRunner` (internal only), `StepStatus` (keep as Enum, but API-owned)

---

#### 6. `svc.analysis.*` - Analysis Operations

**Entrypoints**:
```python
# Analysis (unified endpoint)
svc.analysis.analyze_output(
    calculation_selector: str,
    step_selector: str,
    analysis_type: str,  # "scf", "dos", "bands", "all"
    options: dict = {}
) -> AnalysisResult

# Artifact extraction
svc.analysis.get_artifacts(
    calculation_selector: str,
    step_selector: str,
    artifact_type: Optional[str] = None
) -> List[ArtifactInfo]
```

**Absorbs**:
- `analyze_scf()` → `svc.analysis.analyze_output(..., analysis_type="scf")`
- `analyze_dos()` → `svc.analysis.analyze_output(..., analysis_type="dos")`
- `analyze_band()` → `svc.analysis.analyze_output(..., analysis_type="bands")`
- `parse_scf_output()` → internal (used by `analyze_output`)
- `parse_dos_data()` → internal (used by `analyze_output`)
- `parse_bands_gnu()` → internal (used by `analyze_output`)
- `plot_scf_convergence()` → internal (used by `analyze_output` if `options.plot=True`)
- `plot_dos()` → internal (used by `analyze_output` if `options.plot=True`)
- `plot_bands()` → internal (used by `analyze_output` if `options.plot=True`)
- `save_figure()` → internal (used by `analyze_output`)
- `get_band_structure_data()` → `svc.analysis.get_artifacts(..., artifact_type="bands")`
- `get_dos_data()` → `svc.analysis.get_artifacts(..., artifact_type="dos")`
- `get_scf_convergence_data()` → `svc.analysis.get_artifacts(..., artifact_type="scf")`

**Return Types**:
- `AnalysisResult`: `{type: str, data: dict, artifacts: List[ArtifactInfo], plots: List[PlotInfo]}`
- `ArtifactInfo`: `{type: str, path: Path, size: int, format: str}`
- `PlotInfo`: `{type: str, path: Path, format: str}`

**Re-exports Eliminated**: `DOSData` (replace with dict in `AnalysisResult.data`), `BandAnalysisFiles` (replace with `ArtifactInfo`)

**Note**: Plotting is NOT removed - it's just internal to the capability endpoint. Frontends can request plots via `options.plot=True`, and the endpoint handles it.

---

#### 7. `svc.presets.*` - Preset Operations

**Entrypoints**:
```python
# Preset operations
svc.presets.get_catalog() -> PresetCatalog
svc.presets.detect(calculation_selector: str) -> PresetDetectionResult
svc.presets.apply(calculation_selector: str, step_selector: str) -> ApplyResult
svc.presets.get_footprints(calculation_selector: str, step_selector: str) -> List[PresetFootprint]
```

**Absorbs**:
- `get_preset_catalog()` → `svc.presets.get_catalog()`
- `detect_presets_from_calculation()` → `svc.presets.detect()`
- `apply_presets_to_step()` → `svc.presets.apply()`
- `get_step_preset_footprints()` → `svc.presets.get_footprints()`
- `resolve_precision_context()` → internal (used by `apply`)
- `create_precision_advisor()` → internal (used by `apply`)

**Return Types**:
- `PresetCatalog`: `{presets: List[PresetInfo]}`
- `PresetDetectionResult`: `{detected: List[str], confidence: dict}`
- `ApplyResult`: `{applied: List[str], warnings: List[str]}`

**Re-exports Eliminated**: `PresetCompilationError` (keep as exception), `PrecisionContextError` (keep as exception), `PrecisionOption` (replace with string), `DIMENSION_PRECISION` (internal constant)

---

#### 8. `svc.workflow.*` - Workflow Operations

**Entrypoints**:
```python
# Workflow operations
svc.workflow.list_templates() -> List[WorkflowTemplateInfo]
svc.workflow.detect(calculation_path: Path) -> WorkflowMatch
svc.workflow.validate(calculation_path: Path, workflow_id: str) -> ValidationResult
svc.workflow.instantiate(
    workflow_id: str,
    calculation_path: Path,
    structure_id: str,
    options: dict = {}
) -> InstantiationResult
```

**Absorbs**:
- `get_workflow_service().list_templates()` → `svc.workflow.list_templates()`
- `get_workflow_service().detect_workflow()` → `svc.workflow.detect()`
- `get_workflow_service().validate_workflow()` → `svc.workflow.validate()`
- `get_workflow_service().instantiate_workflow()` → `svc.workflow.instantiate()`
- `detect_workflow_type()` → `svc.workflow.detect()`

**Return Types**:
- `WorkflowTemplateInfo`: `{id: str, name: str, description: str, steps: List[str]}`
- `WorkflowMatch`: `{workflow_id: str, confidence: float, matched_steps: List[str]}`
- `InstantiationResult`: `{calculation_id: str, steps_created: List[str]}`

**Re-exports Eliminated**: `WorkflowTemplate` (replace with DTO), `WorkflowMatch` (replace with DTO), `WorkflowIssue` (replace with `ValidationResult.errors`)

---

### Capability Group Summary

| Group | Entrypoints | Absorbs | Re-exports Eliminated |
|-------|-------------|---------|----------------------|
| `project.*` | 6 | 6 methods | `ProjectContext` (→ DTO) |
| `structure.*` | 9 | 9 methods | `PMGStructure`, `StructureStepSpec` |
| `calculation.*` | 8 | 9 methods | `Calculation`, `CalculationModel`, `CalculationStepEntry` |
| `step.*` | 7 | 7 methods | `Step`, `ParameterOverride` |
| `run.*` | 4 | 4 methods | `CalculationRunner` |
| `analysis.*` | 2 | 13 methods | `DOSData`, `BandAnalysisFiles` |
| `presets.*` | 4 | 6 methods | `PrecisionOption`, `DIMENSION_PRECISION` |
| `workflow.*` | 4 | 5 methods | `WorkflowTemplate`, `WorkflowMatch`, `WorkflowIssue` |
| **Total** | **42** | **59 methods** | **~15 types** |

**Reduction**: 59 current methods → 42 capability endpoints (29% reduction in method count, but much clearer organization)

---

## SECTION 4: Re-export Elimination Strategy

### Principle: Frontends Operate on DTOs, Not Kernel Types

**Current Problem**: Frontends import kernel types from API:
```python
from quantumvitas.api import Calculation, Step, ResourceMeta
calc = Calculation.from_yaml(...)  # Direct kernel type usage
```

**Target State**: Frontends call capabilities, get DTOs:
```python
from quantumvitas.api import QVService
svc = QVService(project_root)
calc_info = svc.calculation.get(selector)  # Returns CalculationInfo DTO
```

### Gradual Elimination Strategy

**Phase 1: Identify Re-export Categories** (Easiest to Hardest)

| Category | Examples | Difficulty | Strategy |
|----------|----------|------------|----------|
| **Constants/Enums** | `DIMENSION_PRECISION`, `STEP_TYPE_MODULE_MAP` | EASY | Move to internal constants; expose via capability endpoints if needed |
| **Exceptions** | `ResourceNotFoundError`, `AmbiguousSelectorError` | MEDIUM | Keep minimal set (5-7 core exceptions); others become internal |
| **Lightweight Types** | `StepMode`, `StepStatus`, `ResourceMeta` | MEDIUM | Replace with API-owned Enums/DTOs; maintain compatibility shim |
| **Heavy Dataclasses** | `Calculation`, `Step`, `CalculationModel` | HARD | Replace with DTOs; provide migration path (deprecation warnings) |

**Phase 2: Replace with API-Owned DTOs**

**Create**: `quantumvitas.api.types` module:
```python
# api/types.py
@dataclass
class CalculationInfo:
    id: str
    name: str
    structure_id: str
    n_steps: int
    status: str

@dataclass
class StepInfo:
    id: str
    type: str
    status: str
    done: bool

# Enums (API-owned)
class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
```

**Migration Path**:
1. Add DTOs to `api/types.py`
2. Update capability endpoints to return DTOs
3. Add deprecation warnings to re-exported kernel types
4. Update frontends to use DTOs
5. Remove re-exports after 1-2 releases

**Phase 3: Internalize Function Re-exports**

**Current**: `from quantumvitas.api import resolve_calculation, load_project_config`
**Target**: These become internal; frontends use capabilities:
- `resolve_calculation()` → `svc.calculation.get()` (internal resolution)
- `load_project_config()` → `svc.project.get_config()` (returns DTO)

**Hard Rule**: `api` public surface is ONLY what's in `__all__` (or equivalent explicit export list). Everything else is internal.

---

## SECTION 5: Wrapper Elimination Strategy

### Principle: Collapse Multiple Wrappers into Single Capability

**Pattern**: Instead of `parse_X()` + `plot_X()` + `save_figure()` + re-export `XData`, provide `analyze_output()` that does all three.

### Concrete Examples

#### Example 1: Analysis Operations

**Current** (5 wrappers + 1 re-export):
```python
# Current API surface
QVService.parse_scf_output(scf_file: Path) -> dict
QVService.plot_scf_convergence(data: dict, output_path: Path) -> None
QVService.save_figure(fig, path: Path) -> None
QVService.parse_dos_data(dos_file: Path) -> DOSData  # re-exported
QVService.plot_dos(data: DOSData, output_path: Path) -> None
QVService.analyze_scf(...) -> dict  # High-level but still uses above

# Frontend code
dos_data = QVService.parse_dos_data(dos_file)
QVService.plot_dos(dos_data, output_path)
QVService.save_figure(fig, output_path)
```

**Proposed** (1 capability endpoint):
```python
# New API surface
svc.analysis.analyze_output(
    calculation_selector: str,
    step_selector: str,
    analysis_type: str,  # "scf", "dos", "bands", "all"
    options: AnalysisOptions = AnalysisOptions()
) -> AnalysisResult

@dataclass
class AnalysisOptions:
    plot: bool = False
    plot_format: str = "png"
    output_dir: Optional[Path] = None
    energy_range: Optional[Tuple[float, float]] = None

@dataclass
class AnalysisResult:
    type: str
    data: dict  # Type-specific data (scf: convergence, dos: energies/densities, bands: kpoints/energies)
    artifacts: List[ArtifactInfo]
    plots: List[PlotInfo]  # If options.plot=True
```

**Frontend code**:
```python
result = svc.analysis.analyze_output(
    calculation_selector="si_dos",
    step_selector="scf",
    analysis_type="dos",
    options=AnalysisOptions(plot=True, plot_format="png")
)
# result.plots contains plot file paths
# result.data contains DOS data as dict
```

**Eliminated**: 5 wrappers → 1 capability endpoint. Frontend code simpler, API surface smaller.

---

#### Example 2: Structure Visualization

**Current** (4 wrappers + 1 re-export):
```python
# Current API surface
QVService.visualize_structure(project_root, structure_selector, ...) -> dict
QVService.visualize_structure_direct(structure, ...) -> StructureVisualizationResult  # re-exported
QVService.get_structure_vis_data(structure, ...) -> dict
QVService.build_display_atoms(structure) -> List[AtomInfo]
QVService.build_bonds(structure) -> List[BondInfo]

# Frontend code
vis_data = QVService.get_structure_vis_data(structure)
atoms = QVService.build_display_atoms(structure)
bonds = QVService.build_bonds(structure)
result = QVService.visualize_structure_direct(structure, ...)
```

**Proposed** (1 capability endpoint):
```python
# New API surface
svc.structure.visualize(
    selector: str,
    options: VisualizationOptions = VisualizationOptions()
) -> VisualizationResult

@dataclass
class VisualizationOptions:
    supercell: Tuple[int, int, int] = (1, 1, 1)
    repeat_boundary: bool = False
    output_path: Optional[Path] = None
    format: str = "png"
    show: bool = False

@dataclass
class VisualizationResult:
    structure_id: str
    plot_path: Optional[Path]
    data: StructureVisualizationData  # DTO with atoms, bonds, etc.
```

**Frontend code**:
```python
result = svc.structure.visualize(
    selector="si",
    options=VisualizationOptions(supercell=(2, 2, 2), output_path=Path("si.png"))
)
# result.plot_path contains saved plot
# result.data contains atoms/bonds for custom rendering
```

**Eliminated**: 4 wrappers → 1 capability endpoint. Visualization logic internal to API.

---

#### Example 3: Calculation Management

**Current** (8 wrappers + 2 re-exports):
```python
# Current API surface
QVService.init_calculation(project_root, structure_selector, name) -> Calculation  # re-exported
QVService.configure_calculation(project_root, selector, updates) -> Calculation
QVService.get_calculation(project_root, selector) -> Calculation
QVService.list_calculations(project_root) -> List[Calculation]
QVService.delete_calculation(project_root, selector) -> None
QVService.rename_calculation(project_root, selector, new_name) -> Calculation
QVService.change_calculation_structure(project_root, selector, structure_selector) -> Calculation
QVService.copy_calculation_template(project_root, template_id, ...) -> Calculation

# Frontend code
calc = QVService.init_calculation(project_root, "si", "si_dos")
calc = QVService.configure_calculation(project_root, "si_dos", {"mode": "strict"})
calc = QVService.get_calculation(project_root, "si_dos")
```

**Proposed** (8 capability endpoints, but organized):
```python
# New API surface
svc.calculation.create(structure_selector: str, name: str) -> CalculationInfo
svc.calculation.get(selector: str) -> CalculationDetail
svc.calculation.list() -> List[CalculationInfo]
svc.calculation.configure(selector: str, updates: dict) -> CalculationDetail
svc.calculation.delete(selector: str) -> DeleteResult
svc.calculation.rename(selector: str, new_name: str) -> CalculationInfo
svc.calculation.create_from_template(template_id: str, structure_selector: str) -> CalculationInfo

# Frontend code
calc_info = svc.calculation.create("si", "si_dos")
calc_detail = svc.calculation.configure("si_dos", {"mode": "strict"})
calc_detail = svc.calculation.get("si_dos")
```

**Eliminated**: 8 wrappers → 7 capability endpoints (slight reduction, but better organization). Re-exports eliminated: `Calculation` → `CalculationInfo`/`CalculationDetail` DTOs.

**Note**: This example shows that not all wrappers collapse into fewer endpoints - some capabilities need multiple endpoints (CRUD operations). The key is **organization by capability**, not reduction at all costs.

---

### Wrapper Elimination Summary

| Current Pattern | Proposed Pattern | Reduction |
|----------------|------------------|-----------|
| `parse_X()` + `plot_X()` + `save_figure()` + re-export | `svc.analysis.analyze_output()` | 3 wrappers → 1 endpoint |
| `visualize_structure()` + `get_structure_vis_data()` + `build_*()` | `svc.structure.visualize()` | 4 wrappers → 1 endpoint |
| `init_calculation()` + `configure_calculation()` + ... | `svc.calculation.*` (organized) | 8 wrappers → 7 endpoints (better org) |
| `read_structure()` + `write_structure()` (re-exported) | `svc.structure.import_from()` + `svc.structure.export()` | 2 re-exports → 2 endpoints |
| `slugify()` + `generate_resource_id()` + `meta_from_name()` | Internal utilities (not public) | 3 wrappers → 0 (internalized) |

**Total Estimated Reduction**: ~100 wrappers → ~40-50 capability endpoints (~50-60% reduction)

---

## SECTION 6: Non-Goals / Guardrails

### What We Will NOT Do

1. **Avoid Creating Lots of Pure-Function Utils**
   - Do NOT create `api/utils.py` with 50+ helper functions
   - Prefer capability endpoints that encapsulate utilities internally
   - Exception: Minimal utilities (2-3) that are truly shared and don't fit a capability

2. **No Moving Logic "Out of Python"**
   - Jupyter is a frontend too - it should have the same capabilities as CLI
   - Do NOT create "CLI-only" APIs - assume Jupyter needs CLI capabilities
   - If CLI can do it, Jupyter should be able to do it via the same endpoint

3. **No Engine-Specific Branching in Frontends**
   - Frontends should NOT check `if engine == "qe": ...`
   - API handles engine-specific logic internally
   - Frontends call capability endpoints, API routes to correct engine

4. **Keep Architecture Gates Meaningful**
   - Gates should enforce the **spirit** of the architecture, not just letter
   - If `api.py` becomes a "shadow kernel" (re-exporting everything), gates pass but architecture fails
   - Consider adding a gate that limits `__all__` size or re-export count

5. **No "Shadow Kernel" Pattern**
   - API must NOT be a dumping ground for re-exports
   - Re-export count must be aggressively reduced over time
   - Target: < 20 re-exports (exceptions + minimal core types only)

6. **No Breaking Changes Without Migration Path**
   - Deprecation warnings for removed re-exports
   - Compatibility shims for 1-2 releases
   - Clear migration guide for frontends

---

## SECTION 7: Open Questions for Opus

**These require a smarter planner to resolve**:

1. **API-Owned DTOs Module**: Should we create `quantumvitas.api.types` for DTOs, or keep them in `api/__init__.py`? Trade-off: separate module is cleaner, but adds import path.

2. **API Versioning**: How do we version the API surface? Semantic versioning for capability endpoints? Breaking change policy?

3. **Exception Strategy**: One base `QVServiceError` with error codes, or typed exceptions (`ResourceNotFoundError`, `ValidationError`, etc.)? Current mix of both is inconsistent.

4. **Capability Group Implementation**: Should capability groups be:
   - Sub-objects (`svc.calculation.get()`)
   - Namespaced methods (`svc.calculation_get()`)
   - Separate classes (`CalculationService(project_root).get()`)

5. **Return Type Consistency**: Should all capability endpoints return:
   - DTOs (dataclasses)
   - Dicts (JSON-serializable)
   - `Result[T]` wrapper (success/error pattern)

6. **Internal vs Public**: How to clearly mark internal methods? Prefix with `_`? Separate `_internal` module? Documentation-only?

7. **Re-export Elimination Timeline**: How aggressive should we be? All at once (breaking) or gradual (maintain shims for N releases)?

8. **Testing Strategy**: How to test capability endpoints without running real engines? Current monkeypatching approach works, but needs scaling to 40+ endpoints.

9. **Documentation**: How to document capability endpoints? Per-group docs? Single API reference? Examples for each frontend type?

10. **Migration Tooling**: Should we provide automated migration tools to update frontend code from old wrappers to new capability endpoints?

---

## Appendix: Evidence Collection

### Commands Used

```bash
# Count API surface
python scripts/audit_api_surface.py

# Count re-exports by module
python -c "import ast; ..."  # (see design doc for full script)

# Verify frontend imports
rg -n "^from quantumvitas\.api import" src/quantumvitas/cli
rg -n "^from quantumvitas\.api import" src/quantumvitas/daemon

# Verify no kernel imports in frontends
rg -n "^from quantumvitas\.(core|calculation|...)\b" src/quantumvitas/cli
rg -n "^from quantumvitas\.(core|calculation|...)\b" src/quantumvitas/daemon

# Count methods
rg -n "@staticmethod|@classmethod" src/quantumvitas/api.py | wc -l
rg -n "^    def " src/quantumvitas/api.py | wc -l

# File size
wc -l src/quantumvitas/api.py
```

### Audit Artifacts

- `.audit/api_surface.json` - Full API surface inventory
- `.audit/cli_kernel_deps.json` - CLI import audit (0 violations)
- `.audit/daemon_kernel_deps.json` - Daemon import audit (0 violations)

---

*End of design document.*

