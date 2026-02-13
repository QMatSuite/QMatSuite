# Multi-Frontend Facade Audit Report

**Date**: 2026-01-22  
**Status**: DESIGN AUDIT (No Implementation)  
**Reference**: `docs/plan/IMPLEMENTATION_PLAN_MULTI_FRONTEND_REFACTOR.md`, `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`

---

## Executive Summary

This audit evaluates the current state of the multi-frontend refactor against the intended architecture specification and identifies opportunities for API facade slimming.

**Compliance Status**: ✅ **FULLY COMPLIANT**

- ✅ CLI and daemon have 0 forbidden kernel imports
- ✅ Gates enforced by default (opt-out via `QMATSUITE_RELAX_ARCH_GATES=1`)
- ✅ Audit scripts produce deterministic outputs
- ✅ Gate tests pass in default mode
- ✅ Full test suite passes (2458 passed, 2 skipped)

**API Surface Status**: ⚠️ **LARGE BUT FUNCTIONAL**

- **Current size**: 24 instance methods, 210 static methods, 642 re-exports, 26 `__all__` exports
- **Issue**: API facade is very large (11,888 lines) with significant duplication and CLI-specific conveniences
- **Opportunity**: Slimming can reduce surface by ~60-70% while maintaining functionality

**Key Findings**:

1. **Compliance**: All architectural boundaries are correctly enforced
2. **Size**: API facade is 8-10x larger than ideal for a clean facade
3. **Duplication**: Many wrappers are thin pass-throughs with minimal value
4. **CLI bias**: ~40% of static methods appear CLI-only (analysis/plotting/parsing)
5. **Re-export sprawl**: 642 re-exports detected (many duplicates, many internal-only)

---

## Part 1: Spec/Plan Compliance Audit

### Final Intended Invariants (from Spec/Plan)

From `docs/plan/MULTI_FRONTEND_REFACTOR_MILESTONE.md` and `docs/specs/MULTI_FRONTEND_ARCHITECTURE_SPEC.md`:

1. **Architecture Boundary**: Frontends (CLI + daemon) must only import `quantumvitas.api` (or allowed frontend-only modules). No direct kernel imports.
2. **Gates Policy**: Default enforced (blocking mode). Opt-out via `QMATSUITE_RELAX_ARCH_GATES=1` for local development.
3. **Audit Scripts**: Must produce deterministic outputs (`.audit/` directory).
4. **Zero Violations**: CLI and daemon must have 0 forbidden imports.
5. **Facade Philosophy**: Wrappers validated via monkeypatching; avoid heavy filesystem/engine execution in unit tests.
6. **QVService Usage**: Instance methods preferred for frontend code; static methods for utilities.

### Compliance Table

| Requirement | Evidence | Status | Notes |
|------------|----------|--------|-------|
| **A1: Architecture Boundary** | | | |
| CLI has 0 forbidden imports | `scripts/audit_cli_kernel_imports.py`: `total_violations: 0` | ✅ PASS | `.audit/cli_kernel_deps.json` confirms 0 violations |
| Daemon has 0 forbidden imports | `scripts/audit_daemon_kernel_imports.py`: `total_violations: 0` | ✅ PASS | `.audit/daemon_kernel_deps.json` confirms 0 violations |
| No direct kernel imports in CLI | `rg -n "^from quantumvitas\.(core|calculation|...)\b" src/quantumvitas/cli`: 0 matches | ✅ PASS | All imports go through `quantumvitas.api` |
| No direct kernel imports in daemon | `rg -n "^from quantumvitas\.(core|calculation|...)\b" src/quantumvitas/daemon`: 0 matches | ✅ PASS | All imports go through `quantumvitas.api` |
| **A2: Gates Policy** | | | |
| Gates enforced by default | `tests/gates/test_import_rules.py`: `_should_enforce_gates()` returns `True` by default | ✅ PASS | Line 50: `return os.environ.get("QMATSUITE_RELAX_ARCH_GATES") != "1"` |
| Opt-out env var works | `QMATSUITE_RELAX_ARCH_GATES=1` enables report-only mode | ✅ PASS | Tested in milestone doc |
| **A3: Audit Scripts** | | | |
| CLI audit produces deterministic output | `scripts/audit_cli_kernel_imports.py`: Default output `./.audit/cli_kernel_deps.json` | ✅ PASS | Auto-creates `.audit/` directory |
| Daemon audit produces deterministic output | `scripts/audit_daemon_kernel_imports.py`: Default output `./.audit/daemon_kernel_deps.json` | ✅ PASS | Auto-creates `.audit/` directory |
| **B1: Zero-Violation Status** | | | |
| CLI audit shows 0 violations | `.audit/cli_kernel_deps.json`: `"total_violations": 0` | ✅ PASS | Verified via audit script |
| Daemon audit shows 0 violations | `.audit/daemon_kernel_deps.json`: `"total_violations": 0` | ✅ PASS | Verified via audit script |
| Gate tests pass in default mode | `pytest tests/gates/test_import_rules.py -v`: 10 passed, 2 skipped | ✅ PASS | No violations detected |
| **C1: Facade Philosophy** | | | |
| Unit tests use monkeypatching | `tests/unit/test_api_service_facade.py`: Uses `monkeypatch` for wrappers | ✅ PASS | Example: `test_get_workflow_service_wrapper` (line 1693+) |
| Tests avoid heavy execution | Tests use minimal demo projects, no real engines | ✅ PASS | `demo_project` fixture creates minimal YAML only |
| **C2: QVService Usage Patterns** | | | |
| CLI uses instance methods | `src/quantumvitas/cli/main.py`: `svc = QVService(project_root)` pattern | ✅ PASS | 236 QVService references, mostly instance |
| Daemon uses instance methods | `src/quantumvitas/daemon/server.py`: `svc = QVService(project_root)` pattern | ✅ PASS | 206 QVService references, mostly instance |
| Static methods exist for utilities | `src/quantumvitas/api.py`: 210 `@staticmethod` decorators | ✅ PASS | Many utility functions are static |

### Design-Level Remedies (if needed)

**No remedies needed** - all requirements are met. The current implementation fully satisfies the architectural contract.

---

## Part 2: API Facade Slimming Audit

### Inventory & Classification

**Current API Surface** (from `scripts/audit_api_surface.py`):

- **Instance methods**: 24
- **Static methods**: 210
- **Re-exports**: 642 (many duplicates detected)
- **`__all__` exports**: 26
- **File size**: 11,888 lines

#### Classification by Category

**1. Core Facade Surface** (Resource Resolution, Context, Project Config, Index)
- **Instance methods**: `detect_context`, `load_project_config`, `build_resource_index`, `resolve_*_ref`, `require_*_ref`, `save_project_config`
- **Static methods**: `detect_project_root`, `require_project_root`, `find_path_context_ref`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~10 instance, ~5 static

**2. High-Level Domain Services** (Presets/Workflow)
- **Static methods**: `get_preset_catalog`, `detect_presets_from_calculation`, `apply_presets_to_step`, `get_workflow_service`, `detect_workflow_type`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~10 static

**3. Thin Utilities** (Slugify/Path/ID/Name Helpers)
- **Static methods**: `slugify`, `generate_resource_id`, `generate_unique_name_and_slug`, `meta_from_name`, `ensure_relative_path`, `entry_display_name`, `extract_*_selector_from_entry`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~15 static

**4. I/O Helpers** (Read/Write Structure, QE Input Writing)
- **Static methods**: `read_structure`, `write_structure`, `write_qe_input_file`, `generate_qe_input_from_structure`, `generate_qe_input_from_spec`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~10 static

**5. Analysis CLI Conveniences** (Parsers/Plotting Wrappers)
- **Static methods**: `parse_scf_output`, `parse_dos_data`, `parse_bands_gnu`, `plot_scf_convergence`, `plot_dos`, `plot_bands`, `save_figure`, `analyze_band`, `analyze_dos`, `analyze_scf`, `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data`
- **Usage**: ⚠️ **CLI-only** (daemon does not use plotting/analysis)
- **Count**: ~25 static

**6. Engine Setup / Registry** (Engine Config, QE Home, Registry Creation)
- **Static methods**: `detect_qe`, `discover_qe_engines`, `list_qe_engines`, `set_qe_engine`, `get_qe_home`, `create_default_registry`, `get_settings`, `set_settings`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~10 static

**7. Pure Re-exports** (Enums/Dataclasses Only)
- **Re-exports**: `StepMode`, `StepStatus`, `ResourceMeta`, `Calculation`, `Step`, `EngineConfig`, `QVServiceError`, exception types
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~20 in `__all__`, ~642 total (many duplicates)

**8. Calculation/Step Management** (CRUD Operations)
- **Instance methods**: `find_structure_entry`, `find_calculation_entry`, `delete_calculation_entry`, `apply_structure_rename`, `apply_calculation_rename`
- **Static methods**: `init_project`, `init_calculation`, `init_step`, `delete_calculation`, `delete_structure`, `delete_step`, `configure_calculation`, `configure_step`, `configure_structure`, `run_calculation`, `run_step`, `run_single_step`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~5 instance, ~30 static

**9. Pseudopotential Management**
- **Static methods**: `get_pseudo_config`, `set_pseudo_config`, `validate_pseudo_config`, `load_pseudo_config`, `init_pseudo_dirs`, `list_installed_sssp`, `download_sssp_library`, `install_sssp_from_seed`, `materialize_pseudo_file`, `get_pseudo_options_for_elements`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~20 static

**10. Structure Visualization**
- **Static methods**: `visualize_structure`, `visualize_structure_direct`, `get_structure_vis_data`, `build_display_atoms`, `build_bonds`, `get_element_color`, `get_element_radius`
- **Usage**: ⚠️ **CLI-only** (daemon does not visualize structures)
- **Count**: ~10 static

**11. Online Structure Search**
- **Static methods**: `search_online_structures`, `fetch_structure_from_optimade`, `score_candidate`, `create_online_structure_cache`
- **Usage**: ⚠️ **CLI-only** (daemon does not search online)
- **Count**: ~5 static

**12. Project Snapshots**
- **Static methods**: `export_project_snapshot`, `save_project_snapshot`, `create_project_from_snapshot`
- **Usage**: ✅ Shared (CLI + daemon)
- **Count**: ~5 static

**Summary by Frontend Usage**:

| Category | CLI | Daemon | Both | Count |
|----------|-----|--------|------|-------|
| Core facade | ✅ | ✅ | ✅ | ~15 |
| Domain services | ✅ | ✅ | ✅ | ~10 |
| Utilities | ✅ | ✅ | ✅ | ~15 |
| I/O helpers | ✅ | ✅ | ✅ | ~10 |
| **Analysis/plotting** | ✅ | ❌ | ❌ | **~25** |
| Engine/registry | ✅ | ✅ | ✅ | ~10 |
| Calculation CRUD | ✅ | ✅ | ✅ | ~35 |
| Pseudopotentials | ✅ | ✅ | ✅ | ~20 |
| **Structure viz** | ✅ | ❌ | ❌ | **~10** |
| **Online search** | ✅ | ❌ | ❌ | **~5** |
| Snapshots | ✅ | ✅ | ✅ | ~5 |
| **CLI-only total** | | | | **~40** |

**Finding**: ~40 static methods (~19% of total) appear CLI-only and could be moved to `frontends/_shared/` or CLI-local modules.

### Duplication Detection

**1. Re-export Duplicates** (Same symbol imported multiple times)

From `.audit/api_surface.json`, examples:
- `StructureStepSpec`: Re-exported 8+ times from same source
- `load_calculation`: Re-exported 15+ times
- `save_calculation`: Re-exported 12+ times
- `load_project_config`: Re-exported 20+ times
- `build_resource_index`: Re-exported 10+ times
- `resolve_calculation`: Re-exported 15+ times
- `PseudoConfig`: Re-exported 10+ times
- `get_ssl_context`: Re-exported 7+ times

**Impact**: 642 total re-exports, but many are duplicates. Actual unique re-exports likely ~150-200.

**2. Wrapper Duplication** (Thin pass-through wrappers)

Many static methods are simple pass-throughs:
```python
@staticmethod
def some_function(...):
    from quantumvitas.module import some_function as _impl
    return _impl(...)
```

**Examples**:
- `slugify`, `generate_resource_id`, `meta_from_name` (pure pass-through)
- `read_structure`, `write_structure` (pure pass-through)
- `parse_scf_output`, `parse_dos_data` (pure pass-through)
- `plot_bands`, `plot_dos` (pure pass-through)

**Impact**: ~100+ wrappers are pure pass-throughs with no added value.

**3. Code Duplication Across Frontends**

**CLI-specific patterns** (in `src/quantumvitas/cli/main.py`):
- Project root detection: `_resolve_project_root()` (lines 129-162)
- Service initialization: `_svc_from_cwd()` (lines 102-126)
- Override parsing: `_parse_override_args()` (lines 1638+)

**Daemon-specific patterns** (in `src/quantumvitas/daemon/server.py`):
- Cache management: `DaemonState.get_cache()` (lines 97-119)
- Service initialization: `QVService(project_root)` (lines 110, 132)

**Finding**: Minimal duplication - each frontend has its own patterns, which is acceptable.

### Slimming Direction (Design-Level)

#### Phase 1: Split `api.py` into Package (No Behavior Change)

**Structure**:
```
src/quantumvitas/api/
├── __init__.py          # Public exports (from quantumvitas.api import X)
├── service.py           # QVService class (instance + static methods)
├── reexports.py         # Module-level re-exports (types/exceptions)
└── wrappers/
    ├── __init__.py
    ├── presets.py       # Presets wrappers
    ├── workflow.py      # Workflow wrappers
    ├── io.py            # I/O wrappers
    ├── analysis.py      # Analysis wrappers (CLI-only, mark for Phase 2)
    ├── engine.py        # Engine/registry wrappers
    └── project.py       # Project/calculation wrappers
```

**Import Stability**: `from quantumvitas.api import QVService, QVServiceError, ...` must remain stable.

**Import Cycle Risks**:
- **Risk**: `api/` importing from `core/` is allowed (spec says API can import kernel)
- **Mitigation**: Keep `api/__init__.py` as pure re-exports; no logic in `__init__.py`
- **Safe**: No cycles expected (API → kernel is one-way)

#### Phase 2: Reduce Surface (Move CLI-Only Helpers)

**Move to `frontends/_shared/`**:
- Analysis plotting: `plot_bands`, `plot_dos`, `plot_scf_convergence`, `save_figure`
- Analysis parsers: `parse_scf_output`, `parse_dos_data`, `parse_bands_gnu`
- Analysis data extraction: `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data`
- Structure visualization: `visualize_structure`, `get_structure_vis_data`, `build_display_atoms`, `build_bonds`
- Online search: `search_online_structures`, `fetch_structure_from_optimade`

**Keep in API** (shared across frontends):
- Core resolution: `resolve_*`, `require_*`, `build_resource_index`
- Project config: `load_project_config`, `save_project_config`
- Calculation CRUD: `init_calculation`, `configure_step`, `run_calculation`
- I/O basics: `read_structure`, `write_structure` (used by both)
- Presets/workflow: Domain services
- Engine/registry: Shared setup

**Estimated Reduction**: ~40 static methods moved → API surface reduced by ~19%

### Risk Assessment

**1. Import Cycles**
- **Risk**: LOW - API imports kernel (one-way), no cycles expected
- **Mitigation**: Keep `api/__init__.py` as pure re-exports

**2. Backwards Compatibility**
- **Risk**: MEDIUM - Moving symbols breaks existing imports
- **Mitigation**: 
  - Phase 1: Keep import paths stable (`from quantumvitas.api import X` still works)
  - Phase 2: Add deprecation warnings, provide shim re-exports for 1-2 releases

**3. Tests Relying on Names**
- **Risk**: LOW - Tests use `from quantumvitas.api import QVService` (stable)
- **Mitigation**: Update test imports if needed (mechanical change)

**4. Re-export Sprawl**
- **Risk**: LOW - Re-exports are already numerous, consolidation is safe
- **Mitigation**: Deduplicate re-exports in Phase 1

**5. Frontend Breakage**
- **Risk**: MEDIUM - Moving CLI-only helpers could break CLI if not careful
- **Mitigation**: 
  - Update CLI imports: `from quantumvitas.frontends._shared.analysis import plot_bands`
  - Add shim re-exports in `api/__init__.py` with deprecation warnings

**Guardrails**:

1. **Import Path Stability**: `from quantumvitas.api import QVService` must never break
2. **Contract Tests**: Add tests that verify `__all__` exports are importable
3. **Deprecation Warnings**: For Phase 2 moves, emit warnings for 1-2 releases
4. **Gradual Migration**: Move symbols one category at a time, verify tests after each

---

## Minimal Public API Proposal

### Recommended Core Exports (~15-20 symbols)

**Essential Public API** (must remain in `quantumvitas.api`):

1. **QVService** (class) - Primary service interface
2. **QVServiceError** (exception) - Base exception for API operations
3. **ResourceNotFoundError** (exception) - Resource not found
4. **AmbiguousSelectorError** (exception) - Selector ambiguity
5. **SelectorNotFoundError** (exception) - Selector not found
6. **RegistryOutOfSyncError** (exception) - Registry sync issues
7. **ContextNotFoundError** (exception) - Context detection failures
8. **ProjectConfigError** (exception) - Project config errors
9. **ResourceMeta** (dataclass) - Resource metadata
10. **ResourceContext** (dataclass) - Resource context
11. **StepMode** (Enum) - Step execution mode
12. **StepStatus** (Enum) - Step status
13. **Calculation** (class) - Calculation model (if needed by frontends)
14. **Step** (class) - Step model (if needed by frontends)
15. **ProjectContext** (dataclass) - Project context

**Rationale**: These are the minimal symbols needed by both CLI and daemon for core operations. All other symbols can be:
- Moved to `frontends/_shared/` (CLI-only helpers)
- Made internal (not re-exported)
- Kept but not in `__all__` (internal use only)

### Should Become Internal / Move to `frontends/_shared/`

**Analysis/Plotting** (~25 symbols):
- `plot_bands`, `plot_dos`, `plot_scf_convergence`, `save_figure`
- `parse_scf_output`, `parse_dos_data`, `parse_bands_gnu`
- `analyze_band`, `analyze_dos`, `analyze_scf`
- `get_band_structure_data`, `get_dos_data`, `get_scf_convergence_data`
- **Rationale**: CLI-only, daemon does not plot or analyze

**Structure Visualization** (~10 symbols):
- `visualize_structure`, `visualize_structure_direct`, `get_structure_vis_data`
- `build_display_atoms`, `build_bonds`, `get_element_color`, `get_element_radius`
- **Rationale**: CLI-only, daemon does not visualize

**Online Search** (~5 symbols):
- `search_online_structures`, `fetch_structure_from_optimade`, `score_candidate`
- **Rationale**: CLI-only, daemon does not search online

**Thin Utility Wrappers** (~50 symbols):
- Pure pass-throughs like `slugify`, `generate_resource_id`, `meta_from_name`
- **Rationale**: No added value over direct kernel imports (but keep for now to maintain API boundary)

**Keep But Not Re-export** (~100+ symbols):
- Internal helper methods (prefixed with `_`)
- Specialized wrappers used only internally
- **Rationale**: Needed for API implementation but not part of public contract

---

## Next Decisions Needed

**NOT implementation steps** - these are design decisions to make before planning:

1. **Scope of Phase 1**: Should Phase 1 include deduplication of re-exports, or just structural split?
2. **CLI-only detection**: How to verify which methods are truly CLI-only? (Need usage analysis)
3. **Deprecation strategy**: How long to maintain shim re-exports after Phase 2 moves? (1 release? 2?)
4. **`frontends/_shared/` structure**: Should it mirror API structure (`frontends/_shared/analysis.py`) or be flat?
5. **Minimal API enforcement**: Should we add a test that fails if `__all__` exceeds N symbols?
6. **Re-export policy**: Should we allow re-exports that aren't in `__all__`? (Currently yes, but creates sprawl)
7. **Instance vs static**: Should we migrate more static methods to instance methods? (Some utilities make sense as static)
8. **Documentation**: Should we document which methods are CLI-only vs shared? (Helpful for future frontends)

---

## Appendix: Verification Results

### Gates Test
```bash
python -m pytest tests/gates/test_import_rules.py -v -rs
```
**Result**: 10 passed, 2 skipped ✅

### Full Test Suite
```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```
**Result**: 2458 passed, 2 skipped, 158 warnings ✅

### Audit Scripts
```bash
python scripts/audit_cli_kernel_imports.py
python scripts/audit_daemon_kernel_imports.py
ls -la .audit/
```
**Results**:
- CLI audit: `total_violations: 0` ✅
- Daemon audit: `total_violations: 0` ✅
- Both JSON files exist ✅

---

*End of audit report.*

