# RPC Contract Recovery Fix Plan

**Generated:** 2026-01-27
**Baseline Commit:** 0873ebf
**Symptom:** `AttributeError: type object 'QMSService' has no attribute 'list_demo_projects'`

---

## Executive Summary

PR10's API slimming refactoring broke the daemon→QMSService RPC contract. The baseline `api.py` file contained ~95+ static methods; the refactored `api/service.py` contains only ~16 static methods plus domain accessor patterns. The daemon calls QMSService static methods directly, but most of them no longer exist.

**Root Cause:** Methods moved to `_api_legacy.py` (LegacyService) but daemon imports from `qmatsuite.api.QMSService` only.

---

## Part A: Baseline RPC Golden Contract

### A.1 RPC Handler Inventory (0873ebf baseline)

The daemon at baseline defines **112 RPC handlers** grouped into 16 categories:

| Category | Handlers | QMSService Calls |
|----------|----------|-----------------|
| Core/System | 6 | 0 (direct module calls) |
| Environment/QE | 5 | 5 |
| Pseudo Config | 18 | ~15 |
| QE Metadata | 4 | 0 (direct module calls) |
| Project Mgmt | 3 | 2 |
| Structure Mgmt | 8 | 6 |
| Calculation Mgmt | 9 | 7 |
| Step Mgmt | 13 | 12 |
| Step Pseudos | 7 | 6 |
| Relax Promotion | 3 | 3 |
| Presets/Workflows | 9 | 7 |
| Demo Projects | 2 | 2 |
| Analysis/Viz | 8 | 8 |
| Wannier/3D | 4 | 0 |
| Job Mgmt | 8 | 3 |
| History/Journal | 11 | 0 (direct module calls) |

### A.2 QMSService Methods Called by Daemon

The daemon makes **90+ unique QMSService static method calls**. Current `service.py` has only **16 static methods**.

**Missing methods (called by daemon but not in service.py):**

```
# Environment/QE Detection (5 methods)
detect_qe
get_environment_info
list_qe_engines
discover_qe_engines
set_qe_engine

# Pseudo Configuration (20+ methods)
get_pseudo_config
set_pseudo_config
validate_pseudo_config
init_pseudo_dirs
load_pseudo_config
install_sssp_from_seed
install_all_sssp_from_seed
list_installed_sssp
list_seed_archives
download_sssp_library
download_all_sssp
import_seed_archives
list_pseudo_libraries
get_library_status
install_pseudo_library
remove_pseudo_library
repair_pseudo_library
compute_store_size
load_manifest_archives
check_archives_status
is_pseudo_archive_installed
install_pseudo_archive

# Structure Operations (8 methods)
rename_structure
can_delete_structure
delete_structure
canonicalize_structure
generate_unique_name_and_slug
meta_from_name
find_path_context_from_pwd
read_structure

# Online Structure Search (6 methods)
search_online_structures
fetch_structure_from_optimade
reduce_formula
score_candidate
extract_provenance
create_online_structure_cache

# Calculation Operations (5 methods)
list_calculation_templates
rename_calculation
validate_ulid
load_calculation
compute_io_dir_from_calculation_model

# Step Operations (10 methods)
set_common_card
get_pseudo_mapping
set_pseudo_mapping
import_pseudo_files
search_legacy_pseudos
download_pseudo_by_filename
download_pseudo_from_url
reset_step_params
reorder_calculation_steps
import_step_from_qe_input

# Pseudo Mapping (5 methods)
get_calculation_pseudo_mapping
update_calculation_species_map
analyze_project_pseudo_effects
materialize_pseudo_file
get_pseudo_options_for_elements
resolve_pseudo_provenance

# Relax Operations (2 methods)
get_relax_final_structure_preview
save_relax_final_structure

# Presets & Workflows (7 methods)
get_preset_catalog
detect_engine_for_calculation
detect_presets_from_calculation
detect_workflow_type
apply_presets_to_step
get_step_preset_footprints
resolve_precision_context
create_precision_advisor

# Demo Projects (2 methods)
create_demo_project
list_demo_projects

# Analysis (7 methods)
ensure_calculation_analysis
get_dos_data
get_reference_analysis
parse_volume_artifact
list_step_artifacts
read_step_artifact_text
create_blob_store

# History (1 method)
get_journal
```

### A.3 Critical GUI E2E Endpoints

The following handlers are critical for GUI E2E tests:

| Handler | Response Shape | Status |
|---------|---------------|--------|
| `_handle_list_demo_projects` | `{demos: [{id, name, description, ...}], count: int}` | **BROKEN** |
| `_handle_get_env_info` | `{python_version, qms_version, qe_home, ...}` | **BROKEN** |
| `_handle_create_demo_project` | `{project_root, demo_id}` | **BROKEN** |
| `_handle_get_project_summary` | Project summary dict | OK |
| `_handle_list_structures` | `{structures: [...]}` | OK |
| `_handle_list_calculations` | `{calculations: [...]}` | OK |
| `_handle_get_step_detail` | Step detail dict | Needs verification |
| `_handle_run_calculation` | `{job_id, status, target_name}` | OK |

---

## Part B: Contract Test Design

### B.1 Proposed Test Structure

```
tests/
  contracts/
    __init__.py
    test_daemon_rpc_contract.py      # Core RPC contract tests
    test_qmsservice_static_methods.py # Static method existence tests
    conftest.py                      # Shared fixtures
```

### B.2 Contract Test: Static Method Existence

```python
# tests/contracts/test_qmsservice_static_methods.py
"""
Contract Test: Ensure QMSService exposes all static methods the daemon requires.

This test prevents API drift by asserting that QMSService has all methods
that daemon handlers call via QMSService.method_name().
"""

import pytest
from qmatsuite.api import QMSService


# Methods daemon calls as QMSService.method_name(...)
DAEMON_REQUIRED_STATIC_METHODS = [
    # Environment/QE
    "detect_qe",
    "get_environment_info",
    "list_qe_engines",
    "discover_qe_engines",
    "set_qe_engine",

    # Pseudo config
    "get_pseudo_config",
    "set_pseudo_config",
    "validate_pseudo_config",
    "init_pseudo_dirs",
    "load_pseudo_config",
    "list_installed_sssp",
    "list_seed_archives",
    "download_sssp_library",
    "download_all_sssp",
    "import_seed_archives",
    "install_sssp_from_seed",
    "install_all_sssp_from_seed",
    "list_pseudo_libraries",
    "get_library_status",
    "install_pseudo_library",
    "remove_pseudo_library",
    "repair_pseudo_library",
    "compute_store_size",
    "load_manifest_archives",
    "check_archives_status",
    "is_pseudo_archive_installed",
    "install_pseudo_archive",

    # Project/Structure
    "init_project",
    "get_project_summary",
    "list_structures_data",
    "list_calculations_data",
    "find_path_context_from_pwd",
    "rename_structure",
    "can_delete_structure",
    "delete_structure",
    "canonicalize_structure",
    "generate_unique_name_and_slug",
    "meta_from_name",

    # Online search
    "search_online_structures",
    "fetch_structure_from_optimade",
    "reduce_formula",
    "score_candidate",
    "extract_provenance",

    # Calculations
    "init_calculation",
    "list_calculation_templates",
    "rename_calculation",
    "validate_ulid",
    "load_calculation",
    "compute_io_dir_from_calculation_model",

    # Steps
    "init_step",
    "set_common_card",
    "get_pseudo_mapping",
    "set_pseudo_mapping",
    "import_pseudo_files",
    "search_legacy_pseudos",
    "download_pseudo_by_filename",
    "download_pseudo_from_url",
    "reset_step_params",
    "reorder_calculation_steps",
    "import_step_from_qe_input",

    # Pseudo mapping
    "get_calculation_pseudo_mapping",
    "update_calculation_species_map",
    "analyze_project_pseudo_effects",
    "materialize_pseudo_file",
    "get_pseudo_options_for_elements",
    "resolve_pseudo_provenance",

    # Relax
    "promote_relax_structure",
    "get_relax_final_structure_preview",
    "save_relax_final_structure",

    # Presets
    "get_preset_catalog",
    "detect_engine_for_calculation",
    "detect_presets_from_calculation",
    "detect_workflow_type",
    "apply_presets_to_step",
    "get_step_preset_footprints",
    "resolve_precision_context",
    "create_precision_advisor",

    # Demo
    "create_demo_project",
    "list_demo_projects",

    # Analysis
    "ensure_calculation_analysis",
    "get_dos_data",
    "get_reference_analysis",
    "parse_volume_artifact",
    "list_step_artifacts",
    "read_step_artifact_text",
    "create_blob_store",

    # Run
    "run_calculation",
    "run_step",

    # Other
    "get_settings",
    "set_settings",
    "get_workflow_service",
    "import_structure",
    "get_journal",
    "read_structure",
    "configure_species_map",
    "get_default_step_params",
    "generate_kpath",
]


@pytest.mark.parametrize("method_name", DAEMON_REQUIRED_STATIC_METHODS)
def test_qmsservice_has_static_method(method_name):
    """Verify QMSService exposes each method the daemon requires."""
    assert hasattr(QMSService, method_name), (
        f"QMSService missing required static method: {method_name}\n"
        f"The daemon calls QMSService.{method_name}() but it doesn't exist.\n"
        f"Either add it to QMSService or update the daemon to use domain accessors."
    )
    attr = getattr(QMSService, method_name)
    assert callable(attr), f"QMSService.{method_name} must be callable"
```

### B.3 Contract Test: RPC Response Shape

```python
# tests/contracts/test_daemon_rpc_contract.py
"""
Contract Test: Verify daemon RPC handlers return expected shapes.
"""

import pytest


class TestDemoProjectsContract:
    """Contract for list_demo_projects handler."""

    def test_response_has_demos_list(self, daemon_client):
        """Response must have 'demos' key with a list."""
        response = daemon_client.call("list_demo_projects", {})
        assert "demos" in response
        assert isinstance(response["demos"], list)

    def test_demo_entry_shape(self, daemon_client):
        """Each demo must have id, name, description."""
        response = daemon_client.call("list_demo_projects", {})
        for demo in response["demos"]:
            assert "id" in demo
            assert "name" in demo
            assert "description" in demo


class TestEnvironmentInfoContract:
    """Contract for get_env_info handler."""

    def test_response_has_version_info(self, daemon_client):
        """Response must have version information."""
        response = daemon_client.call("get_env_info", {})
        assert "python_version" in response
        assert "qms_version" in response
```

---

## Part C: Root Cause Analysis

### C.1 Architectural Drift

| Aspect | Baseline (0873ebf) | Current HEAD |
|--------|-------------------|--------------|
| API Location | `qmatsuite/api.py` (single file) | `qmatsuite/api/service.py` (package) |
| Static Methods | ~95+ methods on QMSService | ~16 methods on QMSService |
| Domain Accessors | None | `svc.calculation.*`, `svc.structure.*`, etc. |
| Legacy Methods | N/A | Moved to `_api_legacy.py` (LegacyService) |

### C.2 What Happened

1. **Refactoring Goal:** Introduce domain accessor pattern (`svc.calculation.get()` instead of `QMSService.get_calculation()`)
2. **Implementation:** Split `api.py` into `api/service.py` with accessors + utilities
3. **Migration Gap:** ~75 static methods moved to `_api_legacy.py` but daemon still imports from `qmatsuite.api.QMSService`
4. **Contract Break:** Daemon calls `QMSService.list_demo_projects()` → method doesn't exist → `AttributeError`

### C.3 Capability Surface Decisions

**Option A: Re-export from LegacyService (Quick Fix)**
- Add all missing methods as re-exports in `api/service.py`
- Pros: Minimal code change, fast fix
- Cons: Defeats purpose of refactoring, LegacyService persists

**Option B: Migrate Daemon to Domain Accessors (Proper Fix)**
- Update daemon to instantiate `QMSService(project_root)` and use accessors
- Requires daemon architecture changes (project context management)
- Pros: Clean API, matches refactoring goals
- Cons: Larger change, more risk

**Option C: Hybrid Approach (Recommended)**
- Re-export **project-agnostic** methods directly (list_demo_projects, detect_qe, etc.)
- Keep **project-specific** methods on domain accessors
- Daemon uses static methods for global ops, instantiates QMSService for project ops

### C.4 Classification of Missing Methods

**Project-Agnostic (should be static):**
```
detect_qe, get_environment_info, list_qe_engines, discover_qe_engines, set_qe_engine
get_pseudo_config, set_pseudo_config, validate_pseudo_config, init_pseudo_dirs
list_installed_sssp, list_pseudo_libraries, download_sssp_library, download_all_sssp
list_demo_projects, create_demo_project
get_settings, set_settings, get_workflow_service
get_default_step_params, generate_kpath
validate_ulid, list_calculation_templates, get_preset_catalog
```

**Project-Specific (should use accessors or accept project_root):**
```
rename_structure, can_delete_structure, delete_structure
rename_calculation, get_calculation_pseudo_mapping, update_calculation_species_map
get_step_detail, update_step_params, reset_step_params
promote_relax_structure, get_relax_final_structure_preview, save_relax_final_structure
ensure_calculation_analysis, get_dos_data, list_step_artifacts
```

---

## Part D: Fix Implementation Plan

### Phase 1: Re-export Missing Static Methods (Critical)

**File:** `src/qmatsuite/api/service.py`

Add imports from `_api_legacy.py` for all project-agnostic methods:

```python
# At the bottom of service.py, after QMSService class definition

# Re-export project-agnostic methods from LegacyService for daemon compatibility
from qmatsuite._api_legacy import LegacyService as _Legacy

# Environment/QE
QMSService.detect_qe = staticmethod(_Legacy.detect_qe)
QMSService.get_environment_info = staticmethod(_Legacy.get_environment_info)
QMSService.list_qe_engines = staticmethod(_Legacy.list_qe_engines)
QMSService.discover_qe_engines = staticmethod(_Legacy.discover_qe_engines)
QMSService.set_qe_engine = staticmethod(_Legacy.set_qe_engine)

# Pseudo configuration
QMSService.get_pseudo_config = staticmethod(_Legacy.get_pseudo_config)
QMSService.set_pseudo_config = staticmethod(_Legacy.set_pseudo_config)
QMSService.validate_pseudo_config = staticmethod(_Legacy.validate_pseudo_config)
QMSService.init_pseudo_dirs = staticmethod(_Legacy.init_pseudo_dirs)
QMSService.load_pseudo_config = staticmethod(_Legacy.load_pseudo_config)
QMSService.list_installed_sssp = staticmethod(_Legacy.list_installed_sssp)
QMSService.list_seed_archives = staticmethod(_Legacy.list_seed_archives)
QMSService.download_sssp_library = staticmethod(_Legacy.download_sssp_library)
QMSService.download_all_sssp = staticmethod(_Legacy.download_all_sssp)
QMSService.import_seed_archives = staticmethod(_Legacy.import_seed_archives)
QMSService.install_sssp_from_seed = staticmethod(_Legacy.install_sssp_from_seed)
QMSService.install_all_sssp_from_seed = staticmethod(_Legacy.install_all_sssp_from_seed)
QMSService.list_pseudo_libraries = staticmethod(_Legacy.list_pseudo_libraries)
QMSService.get_library_status = staticmethod(_Legacy.get_library_status)
QMSService.install_pseudo_library = staticmethod(_Legacy.install_pseudo_library)
QMSService.remove_pseudo_library = staticmethod(_Legacy.remove_pseudo_library)
QMSService.repair_pseudo_library = staticmethod(_Legacy.repair_pseudo_library)
QMSService.compute_store_size = staticmethod(_Legacy.compute_store_size)
QMSService.load_manifest_archives = staticmethod(_Legacy.load_manifest_archives)
QMSService.check_archives_status = staticmethod(_Legacy.check_archives_status)
QMSService.is_pseudo_archive_installed = staticmethod(_Legacy.is_pseudo_archive_installed)
QMSService.install_pseudo_archive = staticmethod(_Legacy.install_pseudo_archive)

# Demo projects
QMSService.create_demo_project = staticmethod(_Legacy.create_demo_project)
QMSService.list_demo_projects = staticmethod(_Legacy.list_demo_projects)

# Settings
QMSService.set_settings = staticmethod(_Legacy.set_settings)

# Online search
QMSService.search_online_structures = staticmethod(_Legacy.search_online_structures)
QMSService.fetch_structure_from_optimade = staticmethod(_Legacy.fetch_structure_from_optimade)
QMSService.reduce_formula = staticmethod(_Legacy.reduce_formula)
QMSService.score_candidate = staticmethod(_Legacy.score_candidate)
QMSService.extract_provenance = staticmethod(_Legacy.extract_provenance)

# Structure utilities
QMSService.canonicalize_structure = staticmethod(_Legacy.canonicalize_structure)
QMSService.generate_unique_name_and_slug = staticmethod(_Legacy.generate_unique_name_and_slug)
QMSService.meta_from_name = staticmethod(_Legacy.meta_from_name)
QMSService.read_structure = staticmethod(_Legacy.read_structure)

# Calculation utilities
QMSService.list_calculation_templates = staticmethod(_Legacy.list_calculation_templates)
QMSService.validate_ulid = staticmethod(_Legacy.validate_ulid)
QMSService.load_calculation = staticmethod(_Legacy.load_calculation)
QMSService.compute_io_dir_from_calculation_model = staticmethod(_Legacy.compute_io_dir_from_calculation_model)

# Step utilities
QMSService.set_common_card = staticmethod(_Legacy.set_common_card)
QMSService.get_pseudo_mapping = staticmethod(_Legacy.get_pseudo_mapping)
QMSService.set_pseudo_mapping = staticmethod(_Legacy.set_pseudo_mapping)
QMSService.import_pseudo_files = staticmethod(_Legacy.import_pseudo_files)
QMSService.search_legacy_pseudos = staticmethod(_Legacy.search_legacy_pseudos)
QMSService.download_pseudo_by_filename = staticmethod(_Legacy.download_pseudo_by_filename)
QMSService.download_pseudo_from_url = staticmethod(_Legacy.download_pseudo_from_url)
QMSService.reset_step_params = staticmethod(_Legacy.reset_step_params)
QMSService.reorder_calculation_steps = staticmethod(_Legacy.reorder_calculation_steps)
QMSService.import_step_from_qe_input = staticmethod(_Legacy.import_step_from_qe_input)

# Pseudo mapping
QMSService.get_calculation_pseudo_mapping = staticmethod(_Legacy.get_calculation_pseudo_mapping)
QMSService.update_calculation_species_map = staticmethod(_Legacy.update_calculation_species_map)
QMSService.analyze_project_pseudo_effects = staticmethod(_Legacy.analyze_project_pseudo_effects)
QMSService.materialize_pseudo_file = staticmethod(_Legacy.materialize_pseudo_file)
QMSService.get_pseudo_options_for_elements = staticmethod(_Legacy.get_pseudo_options_for_elements)
QMSService.resolve_pseudo_provenance = staticmethod(_Legacy.resolve_pseudo_provenance)

# Relax
QMSService.get_relax_final_structure_preview = staticmethod(_Legacy.get_relax_final_structure_preview)
QMSService.save_relax_final_structure = staticmethod(_Legacy.save_relax_final_structure)

# Presets
QMSService.get_preset_catalog = staticmethod(_Legacy.get_preset_catalog)
QMSService.detect_engine_for_calculation = staticmethod(_Legacy.detect_engine_for_calculation)
QMSService.detect_presets_from_calculation = staticmethod(_Legacy.detect_presets_from_calculation)
QMSService.detect_workflow_type = staticmethod(_Legacy.detect_workflow_type)
QMSService.apply_presets_to_step = staticmethod(_Legacy.apply_presets_to_step)
QMSService.get_step_preset_footprints = staticmethod(_Legacy.get_step_preset_footprints)
QMSService.resolve_precision_context = staticmethod(_Legacy.resolve_precision_context)
QMSService.create_precision_advisor = staticmethod(_Legacy.create_precision_advisor)

# Analysis
QMSService.ensure_calculation_analysis = staticmethod(_Legacy.ensure_calculation_analysis)
QMSService.get_dos_data = staticmethod(_Legacy.get_dos_data)
QMSService.get_reference_analysis = staticmethod(_Legacy.get_reference_analysis)
QMSService.parse_volume_artifact = staticmethod(_Legacy.parse_volume_artifact)
QMSService.list_step_artifacts = staticmethod(_Legacy.list_step_artifacts)
QMSService.read_step_artifact_text = staticmethod(_Legacy.read_step_artifact_text)
QMSService.create_blob_store = staticmethod(_Legacy.create_blob_store)

# Other
QMSService.find_path_context_from_pwd = staticmethod(_Legacy.find_path_context_from_pwd)
QMSService.get_journal = staticmethod(_Legacy.get_journal)
QMSService.rename_structure = staticmethod(_Legacy.rename_structure)
QMSService.can_delete_structure = staticmethod(_Legacy.can_delete_structure)
QMSService.delete_structure = staticmethod(_Legacy.delete_structure)
QMSService.rename_calculation = staticmethod(_Legacy.rename_calculation)
```

### Phase 2: Add Contract Test

**File:** `tests/contracts/test_qmsservice_static_methods.py`

Create the contract test from Part B.2 above.

### Phase 3: Verify All Tests Pass

```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Phase 4: Verify Import Gate Still Passes

```bash
python -m pytest tests/gates/test_import_gate.py -v
```

---

## Verification Checklist

- [ ] `QMSService.list_demo_projects()` is callable
- [ ] `QMSService.get_environment_info()` is callable
- [ ] `QMSService.create_demo_project(demo_id)` is callable
- [ ] All 90+ daemon-called methods exist on QMSService
- [ ] Contract test passes
- [ ] Import gate test passes
- [ ] All 2500+ existing tests pass

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Circular import | Medium | High | Import LegacyService at module level, not inside class |
| Method signature mismatch | Low | Medium | LegacyService has same signatures as baseline |
| Test failures | Medium | Medium | Run full test suite after each change |
| Import gate violation | Low | Low | LegacyService is internal, not exposed to daemon |

---

## Notes for Cursor Auto

1. **Do NOT modify daemon code** - fix is in `api/service.py` only
2. **Use dynamic attribute assignment** - cleaner than defining all methods inline
3. **Keep LegacyService import internal** - daemon continues importing `QMSService` from `qmatsuite.api`
4. **Test incrementally** - run contract test after adding each batch of methods
5. **Import gate exemption not needed** - we're re-exporting TO QMSService, not FROM LegacyService in daemon
