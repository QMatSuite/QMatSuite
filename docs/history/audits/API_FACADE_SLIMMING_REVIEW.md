# API Facade Slimming Review

**Date**: 2026-01-22  
**Status**: DESIGN REVIEW (No Implementation)  
**Reference**: `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`, `docs/plan/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md`, `docs/plan/MULTI_FRONTEND_FACADE_AUDIT_REPORT.md`, `docs/specs/API_FACADE_SLIMMING_DESIGN.md`

---

## 1) Spec Compliance: Letter vs Spirit

### Letter Compliance ✅

**Evidence** (from gate tests and audit scripts):

| Requirement | Evidence | Status |
|------------|----------|--------|
| Frontends only import `qmatsuite.api` | `rg -n "^from qmatsuite\.api import" src/qmatsuite/cli`: 8 matches<br>`rg -n "^from qmatsuite\.api import" src/qmatsuite/daemon`: 1 match | ✅ PASS |
| No direct kernel imports in frontends | `rg -n "^from qmatsuite\.(core|calculation|...)\b" src/qmatsuite/cli`: 0 matches<br>`rg -n "^from qmatsuite\.(core|calculation|...)\b" src/qmatsuite/daemon`: 0 matches | ✅ PASS |
| Gates enforced by default | `tests/gates/test_import_rules.py`: Default mode blocks violations | ✅ PASS |
| Audit scripts deterministic | `.audit/cli_kernel_deps.json`, `.audit/daemon_kernel_deps.json` exist | ✅ PASS |

**Verdict**: ✅ **COMPLIANT** - All architectural gates pass.

### Spirit Mismatch ⚠️

**Problem**: The facade is a "single import path" but NOT a "capability abstraction."

**Evidence of Spirit Violation**:

1. **Massive Re-export Volume**:
   - **642 re-exports** detected (AST analysis)
   - **76 unique modules** re-exporting from kernel
   - Top clusters: `core.resolution` (28 symbols), `core.project_utils` (23 symbols), `core.pseudo_config` (15 symbols)
   - **132 types**, **485 functions**, **25 exceptions** re-exported

2. **Frontends Import Kernel Types from API**:
   ```python
   # CLI (src/qmatsuite/cli/main.py:25, 56)
   from qmatsuite.api import ResourceMeta, Calculation, StepMode, StepStatus
   from qmatsuite.api import StructureStepSpec, Step, EngineConfig, QeEngine
   
   # CLI usage (line 1735, 2798)
   step = Step(meta=spec.meta, input_file=generated_input, ...)
   spec.meta = ResourceMeta(...)
   ```
   
   **Impact**: Frontends are tightly coupled to kernel dataclasses, not API DTOs.

3. **Wrapper Sprawl**:
   - **210 static methods** (many pure pass-throughs)
   - **25 instance methods**
   - **11,887 lines** in single file
   - Pattern: `from qmatsuite.X import Y as _Y; return _Y(...)`

4. **No Capability Abstraction**:
   - Frontends must know which of 5-10 wrappers to call for one logical operation
   - Example: To analyze output, CLI calls `parse_scf_output()` + `plot_scf_convergence()` + `save_figure()` + imports `DOSData`
   - No single "analyze output" capability endpoint

**Why This Violates Spirit**:

The spec (`docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`) says:
> "api/ is the PUBLIC API LAYER (single entry point to kernel)"

**Intended**: API provides capability endpoints that abstract kernel complexity.  
**Current**: API is a symbol pass-through - frontends still import kernel types and call kernel functions (just through a different import path).

**Verdict**: ⚠️ **NOT ALIGNED IN SPIRIT** - Gates pass, but API is a "shadow kernel" not a capability layer.

---

## 2) Inventory & Taxonomy of Facade Surface

### Measurement Methodology

**Commands Used**:
```bash
python scripts/audit_api_surface.py  # Generated .audit/api_surface.json
# AST analysis of api.py for re-export classification
# grep/ripgrep for usage patterns
```

**Current Surface**:
- **Instance methods**: 25
- **Static methods**: 210
- **Total methods**: 235
- **Re-exports**: 642 (132 types, 485 functions, 25 exceptions)
- **`__all__` exports**: 26
- **File size**: 11,887 lines

### Complete Inventory Table

| Name | Kind | Underlying Dependency | Frontend Usage | Should Remain? |
|------|------|----------------------|----------------|----------------|
| **`__all__` Exports** | | | | |
| `QMSService` | Class | N/A (API-owned) | CLI, daemon, Jupyter | ✅ YES |
| `QMSServiceError` | Exception | N/A (API-owned) | CLI, daemon | ✅ YES |
| `ResourceNotFoundError` | Re-export exception | `core.resolution` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `RegistryOutOfSyncError` | Re-export exception | `core.resolution` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `AmbiguousSelectorError` | Re-export exception | `core.resolution` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `SelectorNotFoundError` | Re-export exception | `core.resolution` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `ContextNotFoundError` | Re-export exception | `core.context` | CLI | ⚠️ DEPENDS (keep minimal set) |
| `VolumeParserError` | Re-export exception | `analysis.parsers` | Daemon | ❌ NO (internalize) |
| `DisplayModeParams` | Re-export type | `analysis.structure_viz` | CLI only | ❌ NO (replace with DTO) |
| `ResourceContext` | Re-export type | `core.project_utils` | CLI, daemon | ❌ NO (replace with DTO) |
| `ProjectConfigError` | Re-export exception | `core.project_utils` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `ResourceMeta` | Re-export type | `core.resources` | CLI, daemon | ❌ NO (replace with API-owned DTO) |
| `StepMode` | Re-export enum | `core.models` | CLI, daemon | ⚠️ DEPENDS (keep but API-owned) |
| `StepStatus` | Re-export enum | `core.models` | CLI, daemon | ⚠️ DEPENDS (keep but API-owned) |
| `ParameterOverride` | Re-export type | `core.models` | CLI | ❌ NO (replace with dict) |
| `BandAnalysisFiles` | Re-export type | `calculation.naming` | CLI only | ❌ NO (replace with DTO) |
| `Step` | Re-export type | `core.models` | CLI | ❌ NO (replace with DTO) |
| `Calculation` | Re-export type | `core.models` | CLI | ❌ NO (replace with DTO) |
| `EngineConfig` | Re-export type | `engine.config` | CLI, daemon | ❌ NO (replace with DTO) |
| `CalculationStepEntry` | Re-export type | `core.models` | CLI, daemon | ❌ NO (replace with DTO) |
| `QeEngine` | Re-export type | `drivers.qe` | CLI | ❌ NO (internalize) |
| `ProjectContext` | Re-export type | `core.context` | CLI | ❌ NO (replace with DTO) |
| `PresetCompilationError` | Re-export exception | `presets.compiler` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `PrecisionContextError` | Re-export exception | `presets.precision_context` | CLI, daemon | ⚠️ DEPENDS (keep minimal set) |
| `DIMENSION_PRECISION` | Re-export constant | `presets.precision` | CLI, daemon | ❌ NO (internalize) |
| `PrecisionOption` | Re-export type | `presets.precision` | CLI, daemon | ❌ NO (replace with string) |
| **Instance Methods (Sample)** | | | | |
| `detect_context` | Capability endpoint | `core.context` | CLI, daemon | ✅ YES |
| `load_project_config` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| `build_resource_index` | Capability endpoint | `core.resolution` | CLI, daemon | ✅ YES |
| `resolve_calculation_ref` | Capability endpoint | `core.resolution` | CLI, daemon | ✅ YES |
| `resolve_step_ref` | Capability endpoint | `core.resolution` | CLI, daemon | ✅ YES |
| `resolve_structure_ref` | Capability endpoint | `core.resolution` | CLI, daemon | ✅ YES |
| `find_calculation_entry` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| `find_structure_entry` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| `delete_calculation_entry` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| `apply_calculation_rename` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| `apply_structure_rename` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES |
| **Static Methods (Sample - Top Categories)** | | | | |
| **Analysis Wrappers (CLI-only)** | | | | |
| `parse_scf_output` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `parse_dos_data` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `parse_bands_gnu` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `plot_scf_convergence` | Pass-through wrapper | `analysis.plotters` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `plot_dos` | Pass-through wrapper | `analysis.plotters` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `plot_bands` | Pass-through wrapper | `analysis.plotters` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `save_figure` | Pass-through wrapper | `analysis.plotters` | CLI only | ❌ NO (absorb into `svc.analysis.analyze_output`) |
| `analyze_scf` | High-level wrapper | `analysis.*` | CLI only | ⚠️ DEPENDS (consolidate into capability) |
| `analyze_dos` | High-level wrapper | `analysis.*` | CLI only | ⚠️ DEPENDS (consolidate into capability) |
| `analyze_band` | High-level wrapper | `analysis.*` | CLI only | ⚠️ DEPENDS (consolidate into capability) |
| `get_band_structure_data` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.get_artifacts`) |
| `get_dos_data` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.get_artifacts`) |
| `get_scf_convergence_data` | Pass-through wrapper | `analysis.parsers` | CLI only | ❌ NO (absorb into `svc.analysis.get_artifacts`) |
| **Visualization Wrappers (CLI-only)** | | | | |
| `visualize_structure` | Capability endpoint | `analysis.structure_viz` | CLI only | ⚠️ DEPENDS (keep but consolidate) |
| `visualize_structure_direct` | Pass-through wrapper | `analysis.structure_viz` | CLI only | ❌ NO (absorb into `svc.structure.visualize`) |
| `get_structure_vis_data` | Pass-through wrapper | `analysis.structure_viz` | CLI only | ❌ NO (absorb into `svc.structure.visualize`) |
| `build_display_atoms` | Pass-through wrapper | `analysis.structure_viz` | CLI only | ❌ NO (absorb into `svc.structure.visualize`) |
| `build_bonds` | Pass-through wrapper | `analysis.structure_viz` | CLI only | ❌ NO (absorb into `svc.structure.visualize`) |
| **Calculation CRUD (Shared)** | | | | |
| `init_calculation` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `configure_calculation` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `get_calculation` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `list_calculations` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES (but reorganize) |
| `delete_calculation` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `rename_calculation` | Capability endpoint | `core.project_utils` | CLI, daemon | ✅ YES (but reorganize) |
| **Step CRUD (Shared)** | | | | |
| `init_step` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `configure_step` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| `get_step` | Capability endpoint | `core.resolution` | CLI, daemon | ✅ YES (but reorganize) |
| `delete_step` | Capability endpoint | `calculation.*` | CLI, daemon | ✅ YES (but reorganize) |
| **Run Operations (Shared)** | | | | |
| `run_calculation` | Capability endpoint | `calculation.runner` | CLI, daemon | ✅ YES |
| `run_step` | Capability endpoint | `calculation.runner` | CLI, daemon | ✅ YES |
| `run_single_step` | Capability endpoint | `calculation.runner` | CLI, daemon | ✅ YES |
| **I/O Helpers (Shared)** | | | | |
| `read_structure` | Pass-through wrapper | `io` | CLI, daemon | ⚠️ DEPENDS (absorb into `svc.structure.import_from`) |
| `write_structure` | Pass-through wrapper | `io` | CLI, daemon | ⚠️ DEPENDS (absorb into `svc.structure.export`) |
| `write_qe_input_file` | Pass-through wrapper | `io` | CLI, daemon | ❌ NO (internalize) |
| **Utility Wrappers (Shared)** | | | | |
| `slugify` | Pass-through wrapper | `core.resources` | CLI, daemon | ❌ NO (internalize) |
| `generate_resource_id` | Pass-through wrapper | `core.resources` | CLI, daemon | ❌ NO (internalize) |
| `meta_from_name` | Pass-through wrapper | `core.resources` | CLI, daemon | ❌ NO (internalize) |
| `ensure_relative_path` | Pass-through wrapper | `core.resources` | CLI, daemon | ❌ NO (internalize) |
| **Presets (Shared)** | | | | |
| `get_preset_catalog` | Capability endpoint | `presets.*` | CLI, daemon | ✅ YES (but reorganize) |
| `detect_presets_from_calculation` | Capability endpoint | `presets.*` | CLI, daemon | ✅ YES (but reorganize) |
| `apply_presets_to_step` | Capability endpoint | `presets.*` | CLI, daemon | ✅ YES (but reorganize) |
| **Workflow (Shared)** | | | | |
| `get_workflow_service` | Capability endpoint | `workflow.*` | CLI, daemon | ⚠️ DEPENDS (replace with direct methods) |
| `detect_workflow_type` | Capability endpoint | `workflow.*` | CLI, daemon | ✅ YES (but reorganize) |
| **Engine Setup (Shared)** | | | | |
| `detect_qe` | Capability endpoint | `engine.registry` | CLI, daemon | ✅ YES |
| `discover_qe_engines` | Capability endpoint | `engine.registry` | CLI, daemon | ✅ YES |
| `list_qe_engines` | Capability endpoint | `engine.registry` | CLI, daemon | ✅ YES |
| `set_qe_engine` | Capability endpoint | `engine.registry` | CLI, daemon | ✅ YES |
| **Online Search (CLI-only)** | | | | |
| `search_online_structures` | Capability endpoint | `io.online` | CLI only | ⚠️ DEPENDS (keep if Jupyter needs it) |
| `fetch_structure_from_optimade` | Capability endpoint | `io.online` | CLI only | ⚠️ DEPENDS (keep if Jupyter needs it) |

### Top Re-export Clusters by Source Module

| Module | Count | Example Symbols | Rationale for Removal |
|--------|-------|-----------------|----------------------|
| `qmatsuite.core.resolution` | 28 | `resolve_calculation`, `build_resource_index`, `ResourceIndex`, `ResolvedResource` | Functions → internal; types → DTOs |
| `qmatsuite.core.project_utils` | 23 | `load_project_config`, `save_project_config`, `find_structure_entry` | Functions → internal; use via capabilities |
| `qmatsuite.core.pseudo_config` | 15 | `PseudoConfig`, `load_pseudo_config`, `get_ssl_context` | Types → DTOs; functions → internal |
| `qmatsuite.analysis.structure_viz` | 9 | `visualize_structure`, `DisplayModeParams`, `build_display_atoms` | Capability endpoint; types → DTOs |
| `qmatsuite.core.resources` | 7 | `ResourceMeta`, `generate_resource_id`, `slugify` | `ResourceMeta` → DTO; utilities → internal |

**Total from top 5**: ~82 re-exports (13% of total, but high-value targets)

### Top Wrapper Clusters

| Pattern | Count | Examples | Consolidation Target |
|---------|-------|-----------|---------------------|
| `parse_*` + `plot_*` + `save_figure` | ~13 | `parse_scf_output`, `plot_scf_convergence`, `save_figure` | `svc.analysis.analyze_output()` |
| `visualize_*` + `build_*` + `get_*_data` | ~6 | `visualize_structure`, `build_display_atoms`, `get_structure_vis_data` | `svc.structure.visualize()` |
| `init_*` + `configure_*` + `get_*` + `list_*` | ~20 | `init_calculation`, `configure_calculation`, `get_calculation`, `list_calculations` | `svc.calculation.*` (organized) |
| `slugify` + `generate_*` + `meta_from_*` | ~8 | `slugify`, `generate_resource_id`, `meta_from_name` | Internal utilities (not public) |
| `read_*` + `write_*` | ~5 | `read_structure`, `write_structure` | `svc.structure.import_from()` + `export()` |

---

## 3) Capability Map Proposal

### Design Philosophy

**"One Capability, One Entrypoint"**: Each logical capability has ONE primary method (or a tiny coherent group for CRUD). Frontends (CLI, GUI, Jupyter) call the same endpoint. The endpoint orchestrates multiple kernel calls internally and returns API-owned DTOs.

### Proposed Capability Groups

#### Group 1: `svc.project.*` - Project Management

**Entrypoints**:
```python
svc.project.init(path: Path, name: str) -> ProjectInfo
svc.project.get_config() -> ProjectConfig
svc.project.update_config(updates: dict) -> ProjectConfig
svc.project.detect_context(cwd: Path) -> ProjectContext
svc.project.snapshot.export(path: Path) -> SnapshotInfo
svc.project.snapshot.import_from(path: Path) -> ProjectInfo
```

**Collapses**:
- `init_project()` → `svc.project.init()`
- `load_project_config()` → `svc.project.get_config()`
- `save_project_config()` → `svc.project.update_config()`
- `detect_project_root()` → `svc.project.detect_context()`
- `require_project_root()` → internal
- `export_project_snapshot()` → `svc.project.snapshot.export()`
- `create_project_from_snapshot()` → `svc.project.snapshot.import_from()`

**Return Types** (API-owned DTOs):
```python
@dataclass
class ProjectInfo:
    id: str
    name: str
    path: Path
    created: datetime

@dataclass
class ProjectConfig:
    name: str
    structures: List[StructureRef]
    calculations: List[CalculationRef]

@dataclass
class ProjectContext:
    project_root: Path
    is_project: bool
    is_calculation: bool
    is_step: bool
```

---

#### Group 2: `svc.structure.*` - Structure Operations

**Entrypoints**:
```python
svc.structure.list() -> List[StructureInfo]
svc.structure.get(selector: str) -> StructureInfo
svc.structure.import_from(path: Path, name: str) -> StructureInfo
svc.structure.import_from_template(template_id: str, name: str) -> StructureInfo
svc.structure.export(selector: str, path: Path, format: str) -> ExportInfo
svc.structure.delete(selector: str) -> DeleteResult
svc.structure.rename(selector: str, new_name: str) -> StructureInfo
svc.structure.visualize(selector: str, options: VisualizationOptions) -> VisualizationResult
svc.structure.search_online(query: str) -> List[StructureCandidate]
svc.structure.fetch_from_optimade(id: str) -> StructureInfo
```

**Collapses**:
- `list_structures()` → `svc.structure.list()`
- `get_structure()` → `svc.structure.get()`
- `import_structure()` → `svc.structure.import_from()`
- `import_structure_from_template()` → `svc.structure.import_from_template()`
- `write_structure()` → `svc.structure.export()`
- `read_structure()` → internal (used by `import_from`)
- `delete_structure()` → `svc.structure.delete()`
- `rename_structure()` → `svc.structure.rename()`
- `visualize_structure()` + `visualize_structure_direct()` + `get_structure_vis_data()` + `build_display_atoms()` + `build_bonds()` → `svc.structure.visualize()`
- `search_online_structures()` → `svc.structure.search_online()`
- `fetch_structure_from_optimade()` → `svc.structure.fetch_from_optimade()`

**Return Types**:
```python
@dataclass
class StructureInfo:
    id: str
    name: str
    path: Path
    formula: str
    n_atoms: int

@dataclass
class VisualizationResult:
    structure_id: str
    plot_path: Optional[Path]
    data: StructureVisualizationData  # DTO with atoms, bonds, etc.
```

---

#### Group 3: `svc.calculation.*` - Calculation CRUD

**Entrypoints**:
```python
svc.calculation.list() -> List[CalculationInfo]
svc.calculation.get(selector: str) -> CalculationDetail
svc.calculation.create(structure_selector: str, name: str) -> CalculationInfo
svc.calculation.create_from_template(template_id: str, structure_selector: str) -> CalculationInfo
svc.calculation.configure(selector: str, updates: dict) -> CalculationDetail
svc.calculation.delete(selector: str) -> DeleteResult
svc.calculation.rename(selector: str, new_name: str) -> CalculationInfo
svc.calculation.get_steps(selector: str) -> List[StepInfo]
svc.calculation.get_structure(selector: str) -> StructureInfo
```

**Collapses**:
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
```python
@dataclass
class CalculationInfo:
    id: str
    name: str
    structure_id: str
    n_steps: int
    status: str

@dataclass
class CalculationDetail:
    id: str
    name: str
    structure: StructureInfo
    steps: List[StepInfo]
    mode: str
```

---

#### Group 4: `svc.step.*` - Step Operations

**Entrypoints**:
```python
svc.step.get(calculation_selector: str, step_selector: str) -> StepDetail
svc.step.create(calculation_selector: str, step_type: str, after: Optional[str]) -> StepInfo
svc.step.configure(calculation_selector: str, step_selector: str, params: dict) -> StepDetail
svc.step.delete(calculation_selector: str, step_selector: str) -> DeleteResult
svc.step.reorder(calculation_selector: str, step_ids: List[str]) -> List[StepInfo]
svc.step.get_default_params(step_type: str) -> dict
svc.step.validate_params(step_type: str, params: dict) -> ValidationResult
```

**Collapses**:
- `get_step()` → `svc.step.get()`
- `init_step()` → `svc.step.create()`
- `configure_step()` → `svc.step.configure()`
- `delete_step()` → `svc.step.delete()`
- `reorder_calculation_steps()` → `svc.step.reorder()`
- `get_default_step_params()` → `svc.step.get_default_params()`
- `update_step_params()` → `svc.step.configure()` (partial update)

**Return Types**:
```python
@dataclass
class StepDetail:
    id: str
    type: str
    status: str
    params: dict
    artifacts: List[ArtifactInfo]

@dataclass
class ValidationResult:
    valid: bool
    errors: List[str]
    warnings: List[str]
```

---

#### Group 5: `svc.run.*` - Execution

**Entrypoints**:
```python
svc.run.calculation(selector: str, mode: str = "incremental") -> RunResult
svc.run.step(calculation_selector: str, step_selector: str, force: bool = False) -> RunResult
svc.run.input_file(path: Path, engine: str) -> RunResult
svc.run.get_status(calculation_selector: str) -> RunStatus
```

**Collapses**:
- `run_calculation()` → `svc.run.calculation()`
- `run_step()` → `svc.run.step()`
- `run_single_step()` → `svc.run.step()` (with single step)
- `run_input_step()` → `svc.run.input_file()`

**Return Types**:
```python
@dataclass
class RunResult:
    status: str
    steps: List[StepRunInfo]
    duration: float
    errors: List[str]

@dataclass
class RunStatus:
    calculation_id: str
    current_step: Optional[str]
    progress: float
    is_running: bool
```

---

#### Group 6: `svc.analysis.*` - Analysis Operations

**Entrypoints**:
```python
svc.analysis.analyze_output(
    calculation_selector: str,
    step_selector: str,
    analysis_type: str,  # "scf", "dos", "bands", "all"
    options: AnalysisOptions = AnalysisOptions()
) -> AnalysisResult

svc.analysis.get_artifacts(
    calculation_selector: str,
    step_selector: str,
    artifact_type: Optional[str] = None
) -> List[ArtifactInfo]
```

**Collapses** (13 wrappers → 2 endpoints):
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
```python
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

@dataclass
class ArtifactInfo:
    type: str
    path: Path
    size: int
    format: str
```

---

#### Group 7: `svc.presets.*` - Preset Operations

**Entrypoints**:
```python
svc.presets.get_catalog() -> PresetCatalog
svc.presets.detect(calculation_selector: str) -> PresetDetectionResult
svc.presets.apply(calculation_selector: str, step_selector: str) -> ApplyResult
svc.presets.get_footprints(calculation_selector: str, step_selector: str) -> List[PresetFootprint]
```

**Collapses**:
- `get_preset_catalog()` → `svc.presets.get_catalog()`
- `detect_presets_from_calculation()` → `svc.presets.detect()`
- `apply_presets_to_step()` → `svc.presets.apply()`
- `get_step_preset_footprints()` → `svc.presets.get_footprints()`

**Return Types**:
```python
@dataclass
class PresetCatalog:
    presets: List[PresetInfo]

@dataclass
class PresetDetectionResult:
    detected: List[str]
    confidence: dict
```

---

#### Group 8: `svc.workflow.*` - Workflow Operations

**Entrypoints**:
```python
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

**Collapses**:
- `get_workflow_service().list_templates()` → `svc.workflow.list_templates()`
- `get_workflow_service().detect_workflow()` → `svc.workflow.detect()`
- `get_workflow_service().validate_workflow()` → `svc.workflow.validate()`
- `get_workflow_service().instantiate_workflow()` → `svc.workflow.instantiate()`
- `detect_workflow_type()` → `svc.workflow.detect()`

**Return Types**:
```python
@dataclass
class WorkflowTemplateInfo:
    id: str
    name: str
    description: str
    steps: List[str]

@dataclass
class WorkflowMatch:
    workflow_id: str
    confidence: float
    matched_steps: List[str]
```

---

#### Group 9: `svc.engine.*` - Engine Setup

**Entrypoints**:
```python
svc.engine.detect() -> List[EngineInfo]
svc.engine.list() -> List[EngineInfo]
svc.engine.set(name: str, config: dict) -> EngineInfo
svc.engine.get_config(name: str) -> EngineConfig
```

**Collapses**:
- `detect_qe()` → `svc.engine.detect()`
- `discover_qe_engines()` → `svc.engine.detect()`
- `list_qe_engines()` → `svc.engine.list()`
- `set_qe_engine()` → `svc.engine.set()`
- `get_qe_home()` → `svc.engine.get_config()` (property)

**Return Types**:
```python
@dataclass
class EngineInfo:
    name: str
    version: Optional[str]
    path: Optional[Path]
    config: EngineConfig
```

---

### Capability Map Summary

| Group | Entrypoints | Collapses | Reduction |
|-------|-------------|-----------|-----------|
| `project.*` | 6 | 7 methods | 14% |
| `structure.*` | 10 | 12 methods | 17% |
| `calculation.*` | 9 | 9 methods | 0% (better org) |
| `step.*` | 7 | 7 methods | 0% (better org) |
| `run.*` | 4 | 4 methods | 0% (better org) |
| `analysis.*` | 2 | 13 methods | **85%** |
| `presets.*` | 4 | 4 methods | 0% (better org) |
| `workflow.*` | 4 | 5 methods | 20% |
| `engine.*` | 4 | 5 methods | 20% |
| **Total** | **50** | **66 methods** | **24% reduction** |

**Note**: Reduction is conservative because CRUD operations need multiple endpoints. The real win is **organization by capability** and **elimination of pass-through wrappers**.

---

## 4) Re-export Elimination Strategy

### Ranked Elimination Order

| Rank | Category | Count | Examples | Difficulty | Strategy |
|------|----------|-------|----------|------------|----------|
| 1 | **Functions** | 485 | `resolve_calculation`, `load_project_config`, `build_resource_index` | EASY | Internalize; use via capability endpoints |
| 2 | **Constants/Enums** | ~10 | `DIMENSION_PRECISION`, `STEP_TYPE_MODULE_MAP` | EASY | Move to internal constants; expose via capability if needed |
| 3 | **Lightweight Types** | ~20 | `StepMode`, `StepStatus`, `ResourceMeta` | MEDIUM | Replace with API-owned Enums/DTOs; compatibility shim |
| 4 | **Heavy Dataclasses** | ~10 | `Calculation`, `Step`, `CalculationModel` | HARD | Replace with DTOs; deprecation warnings; migration path |
| 5 | **Exceptions** | 25 | `ResourceNotFoundError`, `AmbiguousSelectorError` | MEDIUM | Keep minimal set (5-7); others internalize |

### Detailed Elimination Plan

#### Category 1: Functions (485 re-exports)

**Strategy**: Internalize all function re-exports. Frontends call capability endpoints, not kernel functions.

**Examples**:
- `resolve_calculation()` → internal; frontends use `svc.calculation.get(selector)`
- `load_project_config()` → internal; frontends use `svc.project.get_config()`
- `build_resource_index()` → internal; used by capabilities internally

**Migration**:
1. Mark re-exported functions as deprecated (emit warnings)
2. Update frontends to use capability endpoints
3. Remove re-exports after 1-2 releases

**Timeline**: 2-3 months (gradual, per-frontend)

---

#### Category 2: Constants/Enums (Easy)

**Strategy**: Move to internal constants. If frontends need enum values, provide via capability endpoints or API-owned enums.

**Examples**:
- `DIMENSION_PRECISION` → internal constant
- `STEP_TYPE_MODULE_MAP` → internal constant
- `StepMode`, `StepStatus` → API-owned Enums (not re-exported)

**Migration**:
1. Create API-owned `StepMode`, `StepStatus` enums (copy values, not re-export)
2. Update capability endpoints to return API-owned enums
3. Remove kernel enum re-exports

**Timeline**: 1 month

---

#### Category 3: Lightweight Types (Medium)

**Strategy**: Replace with API-owned DTOs. Maintain compatibility shims for 1-2 releases.

**Examples**:
- `ResourceMeta` → `ResourceInfo` DTO (API-owned)
- `ResourceContext` → `ProjectContext` DTO (API-owned)
- `ParameterOverride` → `dict` (no type needed)

**Migration**:
1. Create `api/types.py` with DTOs
2. Update capability endpoints to return DTOs
3. Add compatibility shims (re-export DTOs as old names with deprecation warnings)
4. Update frontends to use DTOs
5. Remove shims after 1-2 releases

**Timeline**: 2-3 months

---

#### Category 4: Heavy Dataclasses (Hard)

**Strategy**: Replace with DTOs. Provide migration path with deprecation warnings.

**Examples**:
- `Calculation` → `CalculationInfo` / `CalculationDetail` DTOs
- `Step` → `StepInfo` / `StepDetail` DTOs
- `CalculationModel` → internal only

**Why Problematic**:
- Frontends currently construct `Calculation`/`Step` objects directly (see CLI line 1735, 3501)
- Tight coupling: kernel dataclass changes break frontends
- No abstraction: frontends know kernel internals

**Migration Path**:
1. Create DTOs: `CalculationInfo`, `CalculationDetail`, `StepInfo`, `StepDetail`
2. Update capability endpoints to return DTOs
3. Add deprecation warnings to `Calculation`/`Step` re-exports
4. Update CLI to use DTOs (remove `Step(...)` construction, use `svc.step.get()`)
5. Remove re-exports after 2 releases

**Timeline**: 3-4 months (requires frontend refactoring)

---

#### Category 5: Exceptions (Keep Minimal Set)

**Strategy**: Keep 5-7 core exceptions; internalize the rest.

**Keep** (minimal set):
- `QMSServiceError` (base, API-owned)
- `ResourceNotFoundError`
- `AmbiguousSelectorError`
- `SelectorNotFoundError`
- `ProjectConfigError`
- `PresetCompilationError` (if presets are public capability)

**Remove** (internalize):
- `VolumeParserError` → internal (daemon can catch `QMSServiceError`)
- `ContextNotFoundError` → internal (capability returns `None` or raises `ResourceNotFoundError`)
- `PrecisionContextError` → internal (preset capability handles internally)

**Migration**:
1. Define minimal exception set in `api/errors.py`
2. Update capability endpoints to raise only minimal set
3. Remove other exception re-exports
4. Update frontends to catch minimal set

**Timeline**: 1 month

---

### Compatibility Strategy

**Deprecation Warnings**:
```python
# api/__init__.py
import warnings
from qmatsuite.core.models import Calculation as _Calculation

def Calculation(*args, **kwargs):
    warnings.warn(
        "Calculation is deprecated. Use svc.calculation.get() to get CalculationInfo DTO.",
        DeprecationWarning,
        stacklevel=2
    )
    return _Calculation(*args, **kwargs)
```

**Internal Shims**:
- Keep re-exports for 1-2 releases with warnings
- Provide migration guide
- Update frontends gradually

**Minimal "Keep" List**:
- `QMSService` (class)
- `QMSServiceError` (exception)
- 5-7 core exceptions (see above)
- **Total**: ~8-10 symbols in `__all__`

---

## 5) Wrapper Elimination Strategy

### Principle: Collapse to Capabilities

**Rule**: Do NOT solve by moving wrappers into other random modules. Solve by consolidating call graphs so frontends call one operation function.

### Wrapper Families to Eliminate

#### Family 1: Analysis Operations (13 wrappers → 1 endpoint)

**Current**:
```python
# Frontend must know which 5-10 wrappers to call
dos_data = QMSService.parse_dos_data(dos_file)
QMSService.plot_dos(dos_data, output_path)
QMSService.save_figure(fig, output_path)
```

**Proposed**:
```python
# Single capability endpoint
result = svc.analysis.analyze_output(
    calculation_selector="si_dos",
    step_selector="scf",
    analysis_type="dos",
    options=AnalysisOptions(plot=True, plot_format="png")
)
# result.plots contains plot file paths
# result.data contains DOS data as dict
```

**Eliminated**: `parse_scf_output`, `parse_dos_data`, `parse_bands_gnu`, `plot_scf_convergence`, `plot_dos`, `plot_bands`, `save_figure`, `analyze_scf`, `analyze_dos`, `analyze_band`, `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data` → `svc.analysis.analyze_output()` + `svc.analysis.get_artifacts()`

---

#### Family 2: Structure Visualization (5 wrappers → 1 endpoint)

**Current**:
```python
vis_data = QMSService.get_structure_vis_data(structure)
atoms = QMSService.build_display_atoms(structure)
bonds = QMSService.build_bonds(structure)
result = QMSService.visualize_structure_direct(structure, ...)
```

**Proposed**:
```python
result = svc.structure.visualize(
    selector="si",
    options=VisualizationOptions(supercell=(2, 2, 2), output_path=Path("si.png"))
)
# result.plot_path contains saved plot
# result.data contains atoms/bonds for custom rendering
```

**Eliminated**: `visualize_structure`, `visualize_structure_direct`, `get_structure_vis_data`, `build_display_atoms`, `build_bonds` → `svc.structure.visualize()`

---

#### Family 3: Utility Helpers (8 wrappers → 0 public)

**Current**:
```python
slug = QMSService.slugify(name)
id = QMSService.generate_resource_id()
meta = QMSService.meta_from_name(name)
```

**Proposed**: Internalize - these are implementation details, not capabilities.

**Eliminated**: `slugify`, `generate_resource_id`, `meta_from_name`, `ensure_relative_path`, `entry_display_name`, `extract_calculation_selector_from_entry`, `extract_step_selector_from_entry`, `entry_matches` → internal utilities (not public)

---

#### Family 4: I/O Helpers (2 wrappers → capability endpoints)

**Current**:
```python
structure = QMSService.read_structure(path)
QMSService.write_structure(structure, path)
```

**Proposed**:
```python
structure_info = svc.structure.import_from(path, name="si")
svc.structure.export("si", path, format="cif")
```

**Eliminated**: `read_structure`, `write_structure` → `svc.structure.import_from()` + `svc.structure.export()`

---

### Wrapper Elimination Summary

| Family | Current | Proposed | Reduction |
|--------|---------|----------|-----------|
| Analysis | 13 wrappers | 2 endpoints | 85% |
| Visualization | 5 wrappers | 1 endpoint | 80% |
| Utilities | 8 wrappers | 0 (internal) | 100% |
| I/O | 2 wrappers | 2 endpoints | 0% (better org) |
| **Total** | **28 wrappers** | **5 endpoints** | **82%** |

---

## 6) "Where UI Re-implemented Logic" Audit

### Duplication Detection

**Methodology**: Compare CLI (`src/qmatsuite/cli/main.py`) and daemon (`src/qmatsuite/daemon/server.py`) for duplicated logic patterns.

### Duplicated Logic Patterns

#### Pattern 1: Project Root Detection

**CLI** (lines 129-162):
```python
def _resolve_project_root(project: Optional[Path]) -> Path:
    if project:
        return Path(project).expanduser().resolve()
    else:
        try:
            return QMSService.require_project_root()
        except Exception as exc:
            raise typer.BadParameter(str(exc)) from exc
```

**Daemon** (lines 5282-5288):
```python
project_root = self._require_path(payload, "project_root")
# Uses QMSService internally but has its own validation
```

**Recommendation**: ✅ **Already unified** - Both use `QMSService.require_project_root()` or `QMSService(project_root)`. No action needed.

---

#### Pattern 2: Calculation Resolution with Fallback

**CLI** (lines 3463-3500):
```python
# Resolve calculation via registry
registry = svc.build_resource_index()
calc_ref = svc.resolve_calculation_ref(calc_selector, index=registry)
calc_dir = calc_ref.absolute_path
```

**Daemon** (lines 5288-5290):
```python
calculation_resolved = self._resolve_calculation_with_fallback(project_root, calculation)
# Has fallback logic to ensure cache is up-to-date
```

**Recommendation**: ⚠️ **Partially unified** - Both use `QMSService.resolve_calculation_ref()`, but daemon has extra fallback logic. Consider adding `svc.calculation.resolve_with_fallback()` capability endpoint.

---

#### Pattern 3: Step Resolution

**CLI** (lines 1430-1458):
```python
# Resolve step via registry
calc_ref = svc.resolve_calculation_ref(calc_selector, index=registry)
step_ref = svc.resolve_step_ref(calc_selector, step_selector, index=registry)
```

**Daemon** (lines 5289):
```python
self._resolve_step_with_fallback(project_root, calculation, step)
```

**Recommendation**: ⚠️ **Partially unified** - Both use `QMSService.resolve_step_ref()`, but daemon has fallback. Consider unified `svc.step.resolve()` capability.

---

#### Pattern 4: Calculation Model Loading

**CLI** (lines 3509-3518):
```python
calc_model = QMSService.load_calculation(calc_dir, project_root)
calc_model.mode = "strict"
QMSService.save_calculation(calc_model, calc_dir)
```

**Daemon** (lines 5299-5301):
```python
wf_model = QMSService.load_calculation(calculation_path, project_root=project_root)
calculation_dir = calculation_resolved.absolute_path
planned_io_dir = QMSService.compute_io_dir_from_calculation_model(calculation_dir, wf_model.working_dir)
```

**Recommendation**: ⚠️ **Partially unified** - Both use `QMSService.load_calculation()`, but this is a re-exported function. Should use `svc.calculation.get()` which returns DTO, not kernel model.

---

#### Pattern 5: Standalone Step Execution (CLI-only)

**CLI** (lines 1638-1750):
```python
def _run_standalone_step(input_file, workdir, engine_name):
    # Step 1: Import .in to YAML
    import_result = QMSService.build_step_spec_from_qe_input(...)
    # Step 2: Materialize step from YAML
    svc = QMSService(workdir_path)
    generated_input, materialized_spec = svc.materialize_step_spec(...)
    # Step 3: Run step
    step = Step(...)  # Constructs kernel Step object
    qe_engine = QeEngine(engine_config)
    result = step.run(engine=qe_engine, ...)
```

**Daemon**: ❌ **Not present** - Daemon doesn't support standalone mode.

**Recommendation**: ⚠️ **CLI-specific logic** - This is legitimate CLI-only functionality (standalone mode). However, it constructs `Step` and `QeEngine` directly (kernel types). Should use `svc.run.input_file()` capability endpoint instead.

---

### Duplication Summary

| Pattern | Location | Status | Recommendation |
|---------|----------|--------|----------------|
| Project root detection | CLI, daemon | ✅ Unified | No action |
| Calculation resolution | CLI, daemon | ⚠️ Partial | Add `svc.calculation.resolve_with_fallback()` |
| Step resolution | CLI, daemon | ⚠️ Partial | Add `svc.step.resolve()` |
| Calculation model loading | CLI, daemon | ⚠️ Partial | Use `svc.calculation.get()` (DTO) instead |
| Standalone execution | CLI only | ⚠️ Uses kernel types | Use `svc.run.input_file()` capability |

**Key Finding**: Most duplication is already unified via `QMSService`, but both CLI and daemon still use re-exported kernel functions (`load_calculation`, `resolve_calculation_ref`) instead of capability endpoints. Migration to capability endpoints will eliminate remaining duplication.

---

## 7) Decision Points for Opus

### Hard Design Decisions Required

1. **DTO Schema Design**
   - Should DTOs be in `api/types.py` or `api/__init__.py`?
   - Should DTOs be dataclasses or dicts (JSON-serializable)?
   - How to handle nested DTOs (e.g., `CalculationDetail.steps: List[StepInfo]`)?

2. **Capability Group Organization**
   - Sub-objects: `svc.calculation.get()` (preferred)
   - Namespaced methods: `svc.calculation_get()` (alternative)
   - Separate classes: `CalculationService(project_root).get()` (not preferred)

3. **Exception Policy**
   - One base `QMSServiceError` with error codes?
   - Typed exceptions (`ResourceNotFoundError`, `ValidationError`)?
   - Current mix is inconsistent.

4. **Deprecation Timeline**
   - How long to maintain shim re-exports? (Recommendation: 1-2 releases)
   - How aggressive should warnings be?
   - Migration guide format?

5. **API Versioning**
   - Semantic versioning for capability endpoints?
   - Breaking change policy?
   - How to communicate API stability to frontends?

6. **Return Type Consistency**
   - All endpoints return DTOs?
   - All endpoints return `Result[T]` wrapper (success/error pattern)?
   - Mix of both?

7. **Internal vs Public Marking**
   - Prefix with `_` for internal?
   - Separate `_internal` module?
   - Documentation-only?

8. **Re-export Elimination Aggressiveness**
   - All at once (breaking)?
   - Gradual (maintain shims for N releases)?
   - Recommendation: Gradual, 2-3 months.

9. **Testing Strategy**
   - How to test 50+ capability endpoints without running real engines?
   - Current monkeypatching approach - scale it?
   - Contract tests for DTOs?

10. **Documentation**
    - Per-group docs (`svc.calculation.*`)?
    - Single API reference?
    - Examples for each frontend type (CLI, daemon, Jupyter)?

11. **Migration Tooling**
    - Automated migration tools to update frontend code?
    - Codemods for common patterns?
    - Manual migration guide only?

---

## Appendix: Evidence Collection

### Commands Used

```bash
# API surface inventory
python scripts/audit_api_surface.py > .audit/api_surface.json

# Re-export classification
python -c "import ast; ..."  # AST analysis (see report)

# Frontend import verification
rg -n "^from qmatsuite\.api import" src/qmatsuite/cli
rg -n "^from qmatsuite\.api import" src/qmatsuite/daemon
rg -n "^from qmatsuite\.(core|calculation|...)\b" src/qmatsuite/cli
rg -n "^from qmatsuite\.(core|calculation|...)\b" src/qmatsuite/daemon

# Kernel type usage in frontends
rg -n "Calculation\(|Step\(|ResourceMeta\(" src/qmatsuite/cli/main.py
rg -n "Calculation\(|Step\(|ResourceMeta\(" src/qmatsuite/daemon/server.py

# Method counts
rg -n "@staticmethod|@classmethod" src/qmatsuite/api.py | wc -l
rg -n "^    def " src/qmatsuite/api.py | wc -l

# File size
wc -l src/qmatsuite/api.py
```

### Audit Artifacts

- `.audit/api_surface.json` - Full API surface inventory (instance methods, static methods)
- `.audit/cli_kernel_deps.json` - CLI import audit (0 violations)
- `.audit/daemon_kernel_deps.json` - Daemon import audit (0 violations)

---

*End of design review report.*

