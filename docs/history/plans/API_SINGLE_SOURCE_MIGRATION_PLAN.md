# QVService Single-Source API Migration Plan

**Status:** Design Document (No Code Changes)
**Date:** 2026-01-28
**Problem:** Repo governance failure - multiple QVService classes, hidden legacy layers, 500+ dangling calls

---

## Executive Summary

The API slimming effort failed to achieve its stated goal. Despite claims of a "single public QVService," the repository currently has:

- **3 QVService definitions** in production code
- **2 hidden legacy layers** still being imported across the repo
- **500+ dangling calls** - code calling methods that don't exist on the imported class
- **Internal self-referential breakage** - the "new" QVService calls non-existent methods on the legacy class

This document provides a concrete migration plan to achieve actual single-source API compliance.

---

## A. Diagnosis

### A.1 Why Dangling Calls Happen

The root cause is a **semantic split** between import path and method resolution:

1. **Import Path:** Code correctly imports `from quantumvitas.api import QVService`
2. **Method Resolution:** Code then calls `QVService.create_project_from_snapshot()`
3. **Failure:** The `api.service.QVService` class only has **26 methods**
4. **The called method only exists on legacy classes** with 100-215 methods

**Concrete example from cli/main.py:703:**
```python
from quantumvitas.api import QVService  # Imports api.service.QVService (26 methods)
...
QVService.create_project_from_snapshot(...)  # Method doesn't exist! (only on _api_legacy)
```

### A.2 The Three QVService Classes

| Module | File | Method Count | Purpose |
|--------|------|--------------|---------|
| `quantumvitas.api.service.QVService` | `src/quantumvitas/api/service.py:27` | 26 + 7 nested | **Intended** new public API |
| `quantumvitas._api_legacy.QVService` | `src/quantumvitas/_api_legacy.py:229` | 215 | **Hidden** full legacy monolith |
| `quantumvitas.api_legacy.QVService` | `src/quantumvitas/api_legacy.py:148` | 101 | **Hidden** partial legacy subset |

### A.3 How the Two Legacy Layers Differ

**`quantumvitas._api_legacy` (215 methods):**
- Underscore-prefixed module (appears "private")
- Contains the FULL legacy implementation
- Has internal methods like `_build_structure_vis_payload`, `_detect_calculation_results_dir`
- Has advanced features: pseudo library management, preset system, blob stores, workflow service

**`quantumvitas.api_legacy` (101 methods):**
- No underscore (appears "public legacy")
- Subset of `_api_legacy` methods
- Has CLI-specific methods like `get_calculation_for_cli`, `get_step_for_cli`
- Missing many internal methods

**Key observation:** `api_legacy` appears to be a **facade** over `_api_legacy`, exposing a subset.

### A.4 Top Hot Spot Files

**Files with highest legacy usage (static + instance calls):**

| File | Legacy Calls | Dangling | Category |
|------|-------------|----------|----------|
| `src/quantumvitas/daemon/server.py` | 150+ | 80+ | Daemon |
| `src/quantumvitas/cli/main.py` | 50+ | 30+ | CLI |
| `src/quantumvitas/frontends/daemon/server.py` | 80+ | 40+ | Daemon |
| `tests/integration/*` | 200+ | 100+ | Tests |
| `tests/daemon/*` | 100+ | 50+ | Tests |
| `tests/unit/*` | 80+ | 30+ | Tests |

### A.5 Most Dangerous Pattern

**The new QVService internally calls non-existent methods on legacy!**

From `api/service.py:1155`:
```python
def analysis(self) -> QVService.Analysis:
    return QVService.Analysis(self)  # This is calling _api_legacy.QVService.Analysis() - DOESN'T EXIST
```

The nested class factory pattern in the new service attempts to instantiate classes that were **never migrated** from the legacy monolith. This causes:
- Runtime `AttributeError` when the nested accessor is used
- Silent breakage if code paths aren't exercised in tests

### A.6 Dangling Call Categories (from audit)

**By target class:**
- `quantumvitas.api.QVService` (resolves to api.service): 200+ dangling
- `quantumvitas.api_legacy.QVService`: 50+ dangling (private methods)
- `quantumvitas._api_legacy.QVService`: 20+ dangling (nested class constructors)

**By method type:**
- Nested class constructors (`Analysis()`, `Calculation()`, etc.): 7 calls
- Internal private methods (`_build_structure_vis_payload`, etc.): 30+ calls
- Missing public methods (not migrated to new API): 150+ calls

---

## B. Vault Design

### B.1 Vault Structure

Move legacy code to a **quarantined "vault"** area that is:
- Preserved for reference
- Import-protected from production code
- Clearly marked as deprecated

**Proposed structure:**
```
src/quantumvitas/_vault/
    __init__.py           # Empty - no exports, import protection
    _legacy_service.py    # Renamed from _api_legacy.py
    _legacy_facade.py     # Renamed from api_legacy.py
    README.md             # Explains vault purpose and rules
```

### B.2 Vault `__init__.py` (Import Protection)

```python
"""
VAULT: Legacy code preserved for reference only.

DO NOT IMPORT FROM THIS MODULE.

This code exists solely for:
1. Historical reference during migration
2. Documentation of legacy patterns
3. Emergency debugging if needed

Production code must NEVER import from _vault.
"""

import warnings

def _vault_import_guard():
    """Raise warning on any vault import."""
    warnings.warn(
        "Importing from _vault is prohibited. "
        "This module contains deprecated legacy code for reference only. "
        "Use quantumvitas.api.QVService for all production code.",
        DeprecationWarning,
        stacklevel=3
    )

_vault_import_guard()

# Explicitly export nothing
__all__ = []
```

### B.3 Vault Access Rules

| Consumer | Can Import Vault? | Reason |
|----------|------------------|--------|
| `quantumvitas.api.*` | **NO** | API must be self-contained |
| `quantumvitas.cli.*` | **NO** | CLI uses public API only |
| `quantumvitas.daemon.*` | **NO** | Daemon uses public API only |
| `quantumvitas.frontends.*` | **NO** | Frontends use public API only |
| `tests/*` | **NO** | Tests should test public API |
| `tools/migration_*.py` | YES (temporary) | Migration tooling only |
| `docs/examples/*` | NO | Examples use public API |

### B.4 Keeping Vault Code Accessible but Uncallable

1. **Module exists but exports nothing** via `__all__ = []`
2. **Import guard emits DeprecationWarning** on any import attempt
3. **CI gate fails build** if any production import from `_vault` is detected
4. **Code preserved verbatim** for git-blame and historical reference
5. **README.md in vault** explains purpose and migration path

---

## C. Migration Strategy

### Phase 0: Add Gates (Pre-Migration)

**Goal:** Prevent regression during migration. All gates should FAIL initially to prove they detect the problem.

#### Gate 0.1: Multiple QVService Definition Detector

**Scan command:**
```bash
grep -rn "^class QVService" src/quantumvitas/ --include="*.py" | grep -v "_vault" | grep -v "test_"
```

**Expected error format:**
```
ERROR: Multiple QVService definitions found:
  - src/quantumvitas/api/service.py:27 (ALLOWED - canonical)
  - src/quantumvitas/_api_legacy.py:229 (VIOLATION)
  - src/quantumvitas/api_legacy.py:148 (VIOLATION)

Only src/quantumvitas/api/service.py may define class QVService.
```

**CI integration:** `tests/gates/test_single_qvservice_definition.py`

#### Gate 0.2: Legacy Import Detector

**Scan patterns:**
```
from quantumvitas._api_legacy import
from quantumvitas.api_legacy import
from quantumvitas._vault import
import quantumvitas._api_legacy
import quantumvitas.api_legacy
import quantumvitas._vault
```

**Expected error format:**
```
ERROR: Legacy import detected in production code:
  - src/quantumvitas/daemon/server.py:15: from quantumvitas.api_legacy import QVService

Production code must only import from quantumvitas.api
```

**CI integration:** `tests/gates/test_no_legacy_imports.py`

#### Gate 0.3: Dangling Call Detector

**Detection approach:**
1. Parse all Python files using AST
2. For each file, resolve `from quantumvitas.api import QVService`
3. Collect all `QVService.method_name()` calls (static and instance)
4. Check if `method_name` exists on `quantumvitas.api.service.QVService`
5. Report mismatches as dangling

**Expected error format:**
```
ERROR: Dangling API call detected:
  - src/quantumvitas/cli/main.py:703: QVService.create_project_from_snapshot()
    Method 'create_project_from_snapshot' not found on quantumvitas.api.service.QVService
    Suggestion: Method exists on quantumvitas._api_legacy.QVService - needs migration
```

**CI integration:** `tests/gates/test_no_dangling_calls.py`

**Tooling:** Extend existing `tools/api_dangling_calls_scanner.py`

---

### Phase 1: Mechanical 1:1 Migrations (Easy Wins)

Methods that already exist on both old and new API with identical signatures.

**Migration table (1:1 mappings - no code change in callsite):**

| Legacy Method | New Method | Callsites | Notes |
|--------------|------------|-----------|-------|
| `QVService.get_project_summary()` | `QVService.get_project_summary()` | 8 | Already exists |
| `QVService.list_structures_data()` | `QVService.list_structures_data()` | 9 | Already exists |
| `QVService.list_calculations_data()` | `QVService.list_calculations_data()` | 11 | Already exists |
| `QVService.init_project()` | `QVService.init_project()` | 97 | Already exists |
| `QVService.init_calculation()` | `QVService.init_calculation()` | 78 | Already exists |
| `QVService.init_step()` | `QVService.init_step()` | 43 | Already exists |
| `QVService.run_calculation()` | `QVService.run_calculation()` | 12 | Already exists |
| `QVService.run_step()` | `QVService.run_step()` | 20 | Already exists |
| `QVService.import_structure()` | `QVService.import_structure()` | 67 | Already exists |
| `QVService.promote_relax_structure()` | `QVService.promote_relax_structure()` | 12 | Already exists |
| `QVService.save_relax_final_structure()` | `QVService.save_relax_final_structure()` | 4 | Already exists |
| `QVService.configure_species_map()` | `QVService.configure_species_map()` | 4 | Already exists |
| `QVService.create_demo_project()` | `QVService.create_demo_project()` | 7 | Already exists |
| `QVService.list_demo_projects()` | `QVService.list_demo_projects()` | 2 | Already exists |

**Total Phase 1:** ~375 callsites that should "just work" once nested accessors are fixed

---

### Phase 2: Complex Cases by Classification

For each dangling method, decide its fate:

#### Category A: Add as Official QVService Capability

Methods that belong on the public API surface.

| Legacy Method | Proposed Home | Callsites | Difficulty | Notes |
|--------------|---------------|-----------|------------|-------|
| `create_project_from_snapshot()` | `QVService.project.restore()` | 1 | Medium | Snapshot restore |
| `save_project_snapshot()` | `QVService.project.snapshot()` | 1 | Medium | Snapshot create |
| `export_project_snapshot()` | `QVService.project.export()` | 2 | Medium | Archive export |
| `get_calculation_detail()` | `QVService.calculation.get_detail()` | 3 | Low | Already pattern |
| `get_step_detail()` | `QVService.calculation.get_step_detail()` | 1 | Low | Already pattern |
| `rename_structure()` | `QVService.structure.rename()` | 2 | Low | CRUD operation |
| `rename_calculation()` | `QVService.calculation.rename()` | 2 | Low | CRUD operation |
| `delete_structure()` | `QVService.structure.delete()` | 2 | Low | Already exists! |
| `delete_calculation()` | `QVService.calculation.delete()` | 1 | Low | Already exists! |
| `can_delete_structure()` | `QVService.structure.can_delete()` | 4 | Low | Pre-flight check |
| `can_delete_calculation()` | `QVService.calculation.can_delete()` | 2 | Low | Already exists! |
| `get_common_cards()` | `QVService.calculation.get_common_cards()` | 1 | Low | Already exists! |
| `reorder_calculation_steps()` | `QVService.calculation.reorder_steps()` | 2 | Medium | Step management |
| `get_workflow_service()` | `QVService.get_workflow_service()` | 5 | Low | Already exists! |
| `get_settings()` | `QVService.get_settings()` | 4 | Low | Already exists! |
| `generate_kpath()` | `QVService.generate_kpath()` | 1 | Low | Already exists! |
| `get_default_step_params()` | `QVService.get_default_step_params()` | 3 | Low | Already exists! |
| `get_band_structure_data()` | `QVService.analysis.get_band_structure_data()` | 1 | Low | Analysis |
| `get_dos_data()` | `QVService.analysis.get_dos_data()` | 2 | Low | Analysis |
| `get_scf_convergence_data()` | `QVService.analysis.get_scf_convergence_data()` | 1 | Low | Already exists! |
| `list_step_artifacts()` | `QVService.analysis.list_step_artifacts()` | 2 | Low | Already exists! |
| `read_step_artifact_text()` | `QVService.analysis.read_step_artifact_text()` | 2 | Low | Already exists! |
| `get_reference_analysis()` | `QVService.analysis.get_reference()` | 2 | Medium | Reference data |
| `ensure_calculation_analysis()` | `QVService.analysis.ensure()` | 2 | Medium | Compute trigger |
| `analyze_band()` | `QVService.analysis.analyze_band()` | 2 | Low | Already exists! |
| `analyze_dos()` | `QVService.analysis.analyze_dos()` | 1 | Low | Already exists! |
| `list_qe_engines()` | `QVService.engine.list()` | 2 | Low | Already exists! |
| `discover_qe_engines()` | `QVService.engine.discover()` | 2 | Low | Engine discovery |
| `set_qe_engine()` | `QVService.engine.set()` | 2 | Low | Engine config |
| `detect_qe()` | `QVService.engine.detect()` | 2 | Low | Engine detection |
| `get_environment_info()` | `QVService.engine.get_environment()` | 2 | Low | Env info |
| `preflight_check()` | `QVService.run.preflight()` | 1 | Low | Already exists! |

#### Category B: Convert to Pure Utils Functions

Methods that are stateless and belong in `quantumvitas.api.utils`.

| Legacy Method | Proposed Utils Location | Callsites | Notes |
|--------------|------------------------|-----------|-------|
| `is_ulid_like()` | `utils.is_ulid_like()` | 22 | Pure string validation |
| `validate_ulid()` | `utils.validate_ulid()` | 7 | Pure validation |
| `slugify()` | `utils.slugify()` | 0 | Pure string transform |
| `meta_from_name()` | `utils.meta_from_name()` | 1 | Pure metadata extraction |
| `reduce_formula()` | `utils.reduce_formula()` | 1 | Pure chemistry |
| `generate_unique_name_and_slug()` | `utils.generate_unique_name_and_slug()` | 1 | Pure naming |
| `score_candidate()` | `utils.score_candidate()` | 1 | Pure scoring |

#### Category C: Delete/Replace (Obsolete or Internal)

Methods that should not be exposed and should be removed from call sites.

| Legacy Method | Action | Callsites | Rationale |
|--------------|--------|-----------|-----------|
| `_build_structure_vis_payload()` | **DELETE** - internal | 14 | Move to kernel, not API |
| `_detect_calculation_results_dir()` | **DELETE** - internal | 6 | Move to kernel, not API |
| `_detect_prefix_outdir_injection()` | **DELETE** - internal | 2 | Move to kernel, not API |
| `_preflight_check_and_seed_pseudos()` | **DELETE** - internal | 2 | Move to kernel, not API |
| `_update_calculation_steps()` | **DELETE** - internal | 4 | Move to kernel, not API |
| `get_calculation_for_cli()` | **REPLACE** with `calculation.get()` | 0 | CLI-specific removed |
| `get_step_for_cli()` | **REPLACE** with `calculation.get_step()` | 0 | CLI-specific removed |
| `visualize_structure_direct()` | **DELETE** - superseded | 1 | Use `structure.visualize()` |

#### Category D: Pseudo/Library Management (Special Domain)

Methods for pseudopotential library management - decide if this belongs in API or as separate tooling.

| Legacy Method | Decision | Callsites | Notes |
|--------------|----------|-----------|-------|
| `get_pseudo_config()` | Add to `QVService.pseudo.get_config()` | 15 | Core functionality |
| `set_pseudo_config()` | Add to `QVService.pseudo.set_config()` | 2 | Core functionality |
| `validate_pseudo_config()` | Add to `QVService.pseudo.validate()` | 1 | Validation |
| `init_pseudo_dirs()` | Add to `QVService.pseudo.init()` | 1 | Setup |
| `list_pseudo_libraries()` | Add to `QVService.pseudo.list_libraries()` | 1 | Discovery |
| `install_pseudo_library()` | Add to `QVService.pseudo.install()` | 1 | Install |
| `remove_pseudo_library()` | Add to `QVService.pseudo.remove()` | 1 | Uninstall |
| `repair_pseudo_library()` | Add to `QVService.pseudo.repair()` | 1 | Maintenance |
| `get_library_status()` | Add to `QVService.pseudo.get_status()` | 1 | Status |
| `get_pseudo_mapping()` | Add to `QVService.pseudo.get_mapping()` | 2 | Mapping |
| `set_pseudo_mapping()` | Add to `QVService.pseudo.set_mapping()` | 2 | Mapping |
| `import_pseudo_files()` | Add to `QVService.pseudo.import_files()` | 2 | Import |
| `download_pseudo_by_filename()` | Add to `QVService.pseudo.download()` | 4 | Download |
| `download_pseudo_from_url()` | Add to `QVService.pseudo.download_url()` | 2 | Download |
| `search_legacy_pseudos()` | Add to `QVService.pseudo.search()` | 2 | Search |
| `resolve_pseudo_provenance()` | Add to `QVService.pseudo.resolve()` | 2 | Resolution |
| `get_pseudo_options_for_elements()` | Add to `QVService.pseudo.options_for_elements()` | 1 | Options |
| `list_installed_sssp()` | Add to `QVService.pseudo.list_sssp()` | 3 | SSSP specific |
| `install_sssp_from_seed()` | Add to `QVService.pseudo.install_sssp()` | 1 | SSSP install |
| `install_all_sssp_from_seed()` | Add to `QVService.pseudo.install_all_sssp()` | 1 | SSSP install |
| `download_sssp_library()` | Add to `QVService.pseudo.download_sssp()` | 1 | SSSP download |
| `download_all_sssp()` | Add to `QVService.pseudo.download_all_sssp()` | 1 | SSSP download |
| `list_seed_archives()` | Add to `QVService.pseudo.list_seeds()` | 1 | Seeds |
| `import_seed_archives()` | Add to `QVService.pseudo.import_seeds()` | 1 | Seeds |
| `check_archives_status()` | Add to `QVService.pseudo.archives_status()` | 3 | Status |
| `load_manifest_archives()` | **DELETE** - internal | 2 | Internal |
| `is_pseudo_archive_installed()` | Add to `QVService.pseudo.is_installed()` | 1 | Check |
| `install_pseudo_archive()` | Add to `QVService.pseudo.install_archive()` | 1 | Install |
| `load_pseudo_config()` | **DELETE** - use get_pseudo_config | 4 | Redundant |
| `compute_store_size()` | Add to `QVService.pseudo.store_size()` | 1 | Metrics |
| `materialize_pseudo_file()` | Add to `QVService.pseudo.materialize()` | 1 | File ops |

**Recommendation:** Add `QVService.Pseudo` nested class for pseudopotential management.

#### Category E: Advanced/Preset System

| Legacy Method | Decision | Callsites | Notes |
|--------------|----------|-----------|-------|
| `get_preset_catalog()` | Add to `QVService.preset.catalog()` | 1 | Preset system |
| `apply_presets_to_step()` | Add to `QVService.preset.apply_to_step()` | 2 | Apply presets |
| `detect_presets_from_calculation()` | Add to `QVService.preset.detect()` | 3 | Detection |
| `detect_engine_for_calculation()` | Add to `QVService.preset.detect_engine()` | 3 | Engine detection |
| `detect_workflow_type()` | Add to `QVService.preset.detect_workflow()` | 1 | Workflow detection |
| `create_precision_advisor()` | Add to `QVService.preset.create_advisor()` | 1 | Precision |
| `resolve_precision_context()` | Add to `QVService.preset.resolve_precision()` | 1 | Precision |
| `get_step_preset_footprints()` | Add to `QVService.preset.get_footprints()` | 1 | Footprints |

**Recommendation:** Add `QVService.Preset` nested class or merge into Engine.

#### Category F: Online Structure Search

| Legacy Method | Decision | Callsites | Notes |
|--------------|----------|-----------|-------|
| `search_online_structures()` | Add to `QVService.structure.search_online()` | 1 | Search |
| `fetch_structure_from_optimade()` | Add to `QVService.structure.fetch_optimade()` | 1 | OPTIMADE |
| `canonicalize_structure()` | Add to `QVService.structure.canonicalize()` | 1 | Normalization |
| `extract_provenance()` | Add to `QVService.structure.extract_provenance()` | 1 | Provenance |

#### Category G: Miscellaneous/Rare

| Legacy Method | Decision | Callsites | Notes |
|--------------|----------|-----------|-------|
| `create_default_registry()` | **DELETE** - internal | 2 | Internal setup |
| `create_blob_store()` | **DELETE** - internal | 3 | Internal |
| `compute_io_dir_from_calculation_model()` | **DELETE** - internal | 2 | Internal |
| `load_calculation()` | **DELETE** - internal | 3 | Use get() |
| `find_calculation_raw_dir()` | **DELETE** - internal | 1 | Internal |
| `find_calculation_results_dir()` | **DELETE** - internal | 1 | Internal |
| `find_band_analysis_files()` | **DELETE** - internal | 1 | Internal |
| `find_path_context_from_pwd()` | **DELETE** - internal | 1 | Internal |
| `get_journal()` | Add to `QVService.history.journal()` | 2 | Journal |
| `list_calculation_templates()` | Add to `QVService.calculation.list_templates()` | 1 | Templates |
| `run_input_step()` | **REPLACE** with `run.run_step()` | 3 | Consolidate |
| `apply_card_overrides_to_qe_input()` | Move to `quantumvitas.core.qe_utils` | 1 | QE specific |
| `apply_species_overrides_to_qe_input()` | Move to `quantumvitas.core.qe_utils` | 1 | QE specific |
| `analyze_scf()` | Add to `QVService.analysis.analyze_scf()` | 1 | Analysis |
| `parse_volume_artifact()` | **DELETE** - internal | 2 | Internal |
| `read_structure()` | Use `structure.get_atoms()` | 1 | Consolidate |
| `set_settings()` | Add to `QVService.set_settings()` | 1 | Settings |
| `get_qe_home()` | Add to `QVService.engine.qe_home()` | 1 | QE paths |
| `analyze_project_pseudo_effects()` | Add to `QVService.pseudo.analyze_effects()` | 1 | Analysis |
| `get_relax_final_structure_preview()` | Add to `QVService.analysis.relax_preview()` | 2 | Preview |
| `configure_step()` | **REPLACE** with `calculation.update_step_params()` | 7 | Consolidate |
| `delete_step_from_calculation()` | Use `calculation.remove_step()` | 1 | Consolidate |
| `add_step_to_calculation()` | Use `calculation.add_step()` | 1 | Consolidate |
| `change_calculation_structure()` | Use `calculation.set_structure()` | 1 | Consolidate |
| `get_calculation_pseudo_mapping()` | Add to `QVService.calculation.get_pseudo_mapping()` | 3 | Pseudo |
| `update_calculation_species_map()` | Add to `QVService.calculation.update_species_map()` | 2 | Species |
| `reset_step_params()` | Add to `QVService.calculation.reset_step_params()` | 2 | Reset |
| `import_step_from_qe_input()` | Add to `QVService.calculation.import_step()` | 3 | Import |
| `get_structure_vis_data()` | Use `structure.get_vis_data()` | 1 | Consolidate |

---

### Phase 3: Vault Enforcement

After migration is complete, enforce that vault is unreachable:

#### Step 3.1: Move Legacy Files

```bash
# Create vault directory
mkdir -p src/quantumvitas/_vault

# Move legacy files
mv src/quantumvitas/_api_legacy.py src/quantumvitas/_vault/_legacy_service.py
mv src/quantumvitas/api_legacy.py src/quantumvitas/_vault/_legacy_facade.py

# Create vault __init__.py (import guard)
# Create vault README.md (documentation)
```

#### Step 3.2: Update CI Gates

Gates from Phase 0 should now PASS:
- No `class QVService` outside `api/service.py`
- No imports from `_api_legacy` or `api_legacy` (now `_vault`)
- Zero dangling calls

#### Step 3.3: Exit Criteria Verification

Run repo-wide scan to verify:

```bash
# Should output: "PASS: Only 1 QVService definition found"
python tools/check_single_qvservice.py

# Should output: "PASS: Zero legacy imports found"
python tools/check_no_legacy_imports.py

# Should output: "PASS: Zero dangling calls found"
python tools/api_dangling_calls_scanner.py --strict
```

---

## D. API Layer Architecture Proposal

### D.1 Proposed QVService Public Surface

**Pattern: Nested capability classes (current approach, but complete)**

```python
class QVService:
    """Single public API entrypoint."""

    def __init__(self, project_root: Path): ...

    # Direct methods (flat, frequently used)
    def init_project(self, ...) -> ...: ...
    def get_project_summary(self) -> ...: ...
    def get_settings(self) -> ...: ...
    def set_settings(self, ...) -> ...: ...
    def get_workflow_service(self) -> WorkflowService: ...
    def get_default_step_params(self, ...) -> ...: ...
    def generate_kpath(self, ...) -> ...: ...
    def create_demo_project(self, ...) -> ...: ...
    def list_demo_projects(self) -> ...: ...

    # Capability accessors
    def analysis(self) -> QVService.Analysis: ...
    def structure(self) -> QVService.Structure: ...
    def calculation(self) -> QVService.Calculation: ...
    def run(self) -> QVService.Run: ...
    def project(self) -> QVService.Project: ...
    def engine(self) -> QVService.Engine: ...
    def history(self) -> QVService.History: ...
    def pseudo(self) -> QVService.Pseudo: ...       # NEW
    def preset(self) -> QVService.Preset: ...       # NEW (optional)

    # Nested capability classes
    class Analysis:
        def get_summary(self, ...) -> AnalysisSummaryDTO: ...
        def list_properties(self, ...) -> List[AnalysisRefDTO]: ...
        def get_property_ref(self, ...) -> AnalysisRefDTO: ...
        def load_artifact(self, ...) -> Any: ...
        def analyze_band(self, ...) -> ...: ...
        def analyze_dos(self, ...) -> ...: ...
        def analyze_scf(self, ...) -> ...: ...
        def get_band_structure_data(self, ...) -> ...: ...
        def get_scf_convergence_data(self, ...) -> ...: ...
        def get_dos_data(self, ...) -> ...: ...
        def list_step_artifacts(self, ...) -> ...: ...
        def read_step_artifact_text(self, ...) -> ...: ...
        def get_reference(self, ...) -> ...: ...
        def ensure(self, ...) -> ...: ...
        def relax_preview(self, ...) -> ...: ...

    class Structure:
        def get(self, ...) -> StructureDTO: ...
        def list(self) -> List[StructureDTO]: ...
        def get_atoms(self, ...) -> ...: ...
        def require_ref(self, ...) -> ...: ...
        def visualize(self, ...) -> ...: ...
        def import_file(self, ...) -> ...: ...
        def get_vis_data(self, ...) -> ...: ...
        def update_meta(self, ...) -> ...: ...
        def delete(self, ...) -> ...: ...
        def rename(self, ...) -> ...: ...
        def can_delete(self, ...) -> bool: ...
        def search_online(self, ...) -> ...: ...       # NEW
        def fetch_optimade(self, ...) -> ...: ...      # NEW
        def canonicalize(self, ...) -> ...: ...        # NEW
        def extract_provenance(self, ...) -> ...: ...  # NEW

    class Calculation:
        def get(self, ...) -> CalculationDTO: ...
        def list(self) -> List[CalculationDTO]: ...
        def require_ref(self, ...) -> ...: ...
        def require_step_ref(self, ...) -> ...: ...
        def resolve_enclosing_path(self, ...) -> ...: ...
        def require_enclosing(self, ...) -> ...: ...
        def get_step(self, ...) -> StepDTO: ...
        def list_steps(self, ...) -> ...: ...
        def get_effective_params(self, ...) -> ...: ...
        def create(self, ...) -> ...: ...
        def update_meta(self, ...) -> ...: ...
        def update_step_params(self, ...) -> ...: ...
        def duplicate(self, ...) -> ...: ...
        def can_delete(self, ...) -> bool: ...
        def delete(self, ...) -> ...: ...
        def get_detail(self, ...) -> ...: ...
        def set_structure(self, ...) -> ...: ...
        def get_common_cards(self, ...) -> ...: ...
        def add_step(self, ...) -> ...: ...
        def remove_step(self, ...) -> ...: ...
        def rename(self, ...) -> ...: ...               # NEW
        def reorder_steps(self, ...) -> ...: ...        # NEW
        def list_templates(self) -> ...: ...            # NEW
        def get_pseudo_mapping(self, ...) -> ...: ...   # NEW
        def update_species_map(self, ...) -> ...: ...   # NEW
        def reset_step_params(self, ...) -> ...: ...    # NEW
        def import_step(self, ...) -> ...: ...          # NEW

    class Run:
        def run_calculation(self, ...) -> RunResultDTO: ...
        def run_step(self, ...) -> RunResultDTO: ...
        def get_status(self, ...) -> ...: ...
        def cancel(self, ...) -> ...: ...
        def list_runs(self, ...) -> ...: ...
        def preflight(self, ...) -> ...: ...

    class Project:
        def get_config(self) -> ...: ...
        def update_config(self, ...) -> ...: ...
        def get_species_map(self) -> ...: ...
        def get_potential_map(self) -> ...: ...
        def build_resource_index(self) -> ...: ...
        def list_calculations(self) -> ...: ...
        def collect_slugs(self) -> ...: ...
        def apply_structure_rename(self, ...) -> ...: ...
        def apply_calculation_rename(self, ...) -> ...: ...
        def snapshot(self, ...) -> ...: ...             # NEW
        def restore(self, ...) -> ...: ...              # NEW
        def export(self, ...) -> ...: ...               # NEW

    class Engine:
        def list(self) -> ...: ...
        def get_info(self, ...) -> ...: ...
        def list_step_types(self) -> ...: ...
        def validate_installation(self, ...) -> ...: ...
        def discover(self) -> ...: ...                  # NEW
        def set(self, ...) -> ...: ...                  # NEW
        def detect(self) -> ...: ...                    # NEW
        def get_environment(self) -> ...: ...           # NEW
        def qe_home(self) -> ...: ...                   # NEW

    class History:
        def get_timeline(self, ...) -> ...: ...
        def get_run_revision(self, ...) -> ...: ...
        def list_runs(self, ...) -> ...: ...
        def pin_analysis(self, ...) -> ...: ...
        def can_pin(self, ...) -> bool: ...
        def get_pin_data(self, ...) -> ...: ...
        def get_latest_run_for_step(self, ...) -> ...: ...
        def delete(self, ...) -> ...: ...
        def journal(self, ...) -> ...: ...              # NEW

    class Pseudo:  # NEW capability class
        def get_config(self) -> ...: ...
        def set_config(self, ...) -> ...: ...
        def validate(self, ...) -> ...: ...
        def init(self) -> ...: ...
        def list_libraries(self) -> ...: ...
        def install(self, ...) -> ...: ...
        def remove(self, ...) -> ...: ...
        def repair(self, ...) -> ...: ...
        def get_status(self, ...) -> ...: ...
        def get_mapping(self, ...) -> ...: ...
        def set_mapping(self, ...) -> ...: ...
        def import_files(self, ...) -> ...: ...
        def download(self, ...) -> ...: ...
        def download_url(self, ...) -> ...: ...
        def search(self, ...) -> ...: ...
        def resolve(self, ...) -> ...: ...
        def options_for_elements(self, ...) -> ...: ...
        def list_sssp(self) -> ...: ...
        def install_sssp(self, ...) -> ...: ...
        def install_all_sssp(self) -> ...: ...
        def download_sssp(self, ...) -> ...: ...
        def download_all_sssp(self) -> ...: ...
        def list_seeds(self) -> ...: ...
        def import_seeds(self, ...) -> ...: ...
        def archives_status(self) -> ...: ...
        def is_installed(self, ...) -> bool: ...
        def install_archive(self, ...) -> ...: ...
        def store_size(self) -> ...: ...
        def materialize(self, ...) -> ...: ...
        def analyze_effects(self, ...) -> ...: ...
```

### D.2 Add Capability vs Re-export Utils Decision Framework

**Rule: "Does it need QVService state?"**

| Question | YES (Add to QVService) | NO (Put in utils) |
|----------|----------------------|-------------------|
| Needs `project_root`? | Add to capability | Utils |
| Reads/writes project files? | Add to capability | Utils |
| Needs kernel/analysis modules? | Add to capability | Utils |
| Pure string/data transform? | Utils | Utils |
| Stateless validation? | Utils | Utils |
| Context-free computation? | Utils | Utils |

**Examples:**
- `is_ulid_like("01ARZ3NDEKTSV4RRFFQ69G5FAV")` -> **Utils** (pure validation)
- `get_calculation(selector)` -> **Capability** (needs project_root)
- `slugify("My Name")` -> **Utils** (pure transform)
- `list_calculations()` -> **Capability** (reads project files)

---

## E. Migration Difficulty Assessment

### E.1 Callsite Breakdown

| Category | Callsites | Files | Risk |
|----------|-----------|-------|------|
| CLI (`src/quantumvitas/cli/`) | ~80 | 1 | **High** - user-facing |
| Daemon (`src/quantumvitas/daemon/`) | ~150 | 1 | **High** - IPC boundary |
| Frontend Daemon (`src/quantumvitas/frontends/daemon/`) | ~80 | 1 | **High** - IPC boundary |
| Frontend CLI (`src/quantumvitas/frontends/cli/`) | ~10 | 1 | **Medium** |
| Integration tests | ~200 | 30+ | **Medium** - may need fixture updates |
| Unit tests | ~80 | 20+ | **Low** - can update incrementally |
| Daemon tests | ~100 | 10+ | **Medium** |
| Tools | ~20 | 5 | **Low** - internal |

**Total estimated callsites to update: 700+**

### E.2 Highest Risk API Areas

1. **Demo Projects** (`create_demo_project`, `list_demo_projects`)
   - User-facing feature
   - Used in tutorials
   - Risk: Breaking onboarding experience

2. **Analysis Export** (`get_band_structure_data`, `get_scf_convergence_data`, `analyze_band`)
   - Core scientific output
   - Used by plotting/visualization
   - Risk: Breaking data pipelines

3. **Artifact Listing** (`list_step_artifacts`, `read_step_artifact_text`)
   - Used by GUI viewers
   - Risk: Breaking interactive analysis

4. **Pseudo Management** (20+ methods)
   - Complex subsystem
   - Many external dependencies (downloads, archives)
   - Risk: Breaking first-run setup

5. **Snapshot/Restore** (`save_project_snapshot`, `create_project_from_snapshot`)
   - Data integrity critical
   - Used for project portability
   - Risk: Data loss if broken

### E.3 Suggested Migration Order

1. **Phase 1 (1:1 mappings)** - Low risk, high impact, quick wins
2. **Category A methods** - Official API additions, well-understood
3. **Category B methods** - Utils extraction, isolated changes
4. **Pseudo subsystem** - Self-contained, can be done as unit
5. **Category C methods** - Deletions/replacements, may break tests
6. **Daemon updates** - High churn but isolated
7. **CLI updates** - High visibility, do last with full testing

---

## F. Appendix: Scan Rules Reference

### F.1 Single QVService Definition Check

```python
# tests/gates/test_single_qvservice_definition.py
import ast
from pathlib import Path

def test_single_qvservice_definition():
    """Ensure only one QVService class exists in production code."""
    src = Path("src/quantumvitas")
    definitions = []

    for py_file in src.rglob("*.py"):
        if "_vault" in str(py_file) or "test_" in py_file.name:
            continue

        tree = ast.parse(py_file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "QVService":
                definitions.append(f"{py_file}:{node.lineno}")

    # Only api/service.py should define QVService
    assert len(definitions) == 1, f"Multiple QVService definitions: {definitions}"
    assert "api/service.py" in definitions[0]
```

### F.2 No Legacy Imports Check

```python
# tests/gates/test_no_legacy_imports.py
import re
from pathlib import Path

LEGACY_PATTERNS = [
    r"from quantumvitas\._api_legacy",
    r"from quantumvitas\.api_legacy",
    r"from quantumvitas\._vault",
    r"import quantumvitas\._api_legacy",
    r"import quantumvitas\.api_legacy",
    r"import quantumvitas\._vault",
]

def test_no_legacy_imports():
    """Ensure no production code imports from legacy modules."""
    src = Path("src/quantumvitas")
    violations = []

    for py_file in src.rglob("*.py"):
        if "_vault" in str(py_file):
            continue

        content = py_file.read_text()
        for pattern in LEGACY_PATTERNS:
            if re.search(pattern, content):
                for i, line in enumerate(content.split("\n"), 1):
                    if re.search(pattern, line):
                        violations.append(f"{py_file}:{i}: {line.strip()}")

    assert not violations, f"Legacy imports found:\n" + "\n".join(violations)
```

### F.3 No Dangling Calls Check

```python
# tests/gates/test_no_dangling_calls.py
# Uses the existing api_dangling_calls_scanner.py tool
import subprocess
import json

def test_no_dangling_calls():
    """Ensure all QVService calls resolve to existing methods."""
    result = subprocess.run(
        ["python", "tools/api_dangling_calls_scanner.py", "--json"],
        capture_output=True,
        text=True
    )

    data = json.loads(result.stdout)
    dangling = data.get("dangling_calls", [])

    assert len(dangling) == 0, (
        f"Found {len(dangling)} dangling calls:\n" +
        "\n".join(f"  {d['file']}:{d['line']}: {d['method']}" for d in dangling[:10])
    )
```

---

## G. Implementation Notes (For Future Executor)

1. **Do NOT attempt to implement this plan manually.** Use Cursor Auto or similar tooling.

2. **Preserve git history.** When moving files to vault, use `git mv` to maintain blame.

3. **Run gates after EVERY change.** The gates are the source of truth.

4. **Tests may fail during migration.** Expected - update tests to use new API.

5. **Pseudo subsystem is self-contained.** Can be migrated as atomic unit.

6. **Daemon and CLI are high-traffic.** Schedule changes during low-usage periods.

7. **Document breaking changes.** If method signatures change, document in CHANGELOG.

---

**End of Document**
