# API Slimming Opportunity Report

**Generated**: 2026-02-02
**Revised**: 2026-02-02 (Deep review with case-by-case analysis)
**Baseline**: 243 entrypoints → **Current**: 213 entrypoints (-30, -12.3%)

---

## Executive Summary

### Highest-Confidence Slimming Opportunities (5)

| Priority | Opportunity | Expected Delta | Evidence |
|----------|-------------|----------------|----------|
| 1 | Delete `Analysis.find_band_files` | **-1** | Zero usage (d=0, c=0, t=0); duplicate of utils `find_band_analysis_files` |
| 2 | Delete `Project.get_species_map` | **-1** | Tests-only (d=0, c=0, t=3); redundant with `get_config().get("species_map")` |
| 3 | Delete `Project.get_potential_map` | **-1** | Tests-only (d=0, c=0, t=3); redundant with `get_config().get("potential_map")` |
| 4 | Merge `visualize_structure` + `build_structure_vis_payload` | **-1** | Same purpose, different interfaces |
| 5 | Delete internal model leak functions (`load_calculation`, `save_calculation`) | **-2** | Expose internal `CalculationModel`; callers should use service methods |

**Total high-confidence slimming: -6 entrypoints**

### Clarity-Only Refactors (No Count Reduction)

| Refactor | Rationale |
|----------|-----------|
| Group pseudo-related static methods under a `pseudo` nested accessor | Clarity: 14 methods logically belong together, but no entrypoint reduction |
| Rename `run_single_step` to clarify it uses ULID | Reduces confusion with `run.run_step` |

### Tests-Only Entrypoints Summary

| Classification | Count | Recommendation |
|----------------|-------|----------------|
| A) Future capability (keep, monitor) | 7 | Keep - tested API contracts for future daemon/CLI integration |
| B) Legacy/outdated test | 0 | None found |
| C) Kernel behavior (relocate test) | 0 | None found |
| D) Test-only helper (move to tests/) | 2 | `get_species_map`, `get_potential_map` - thin wrappers with no daemon/CLI use |
| E) Tooling concern | 0 | None found |

---

## CORRECTION: Static Methods ARE Used by Daemon/CLI

**Critical correction from initial report**: The original claim that "23 static methods are ALL unused by daemon/CLI" was **incorrect**.

Re-audit with correct grep patterns shows:

| Static Method | Daemon Refs | CLI Refs | Status |
|---------------|-------------|----------|--------|
| `init_project` | 1 | 1 | **PRODUCTION** |
| `get_settings` | 6 | 0 | **PRODUCTION** |
| `get_workflow_service` | 4 | 0 | **PRODUCTION** |
| `run_single_step` | 5 | 0 | **PRODUCTION** |
| `get_default_step_params` | 0 | 1 | **PRODUCTION** |
| `resolve_step_type_spec` | 0 | 1 | **PRODUCTION** |
| `generate_kpath` | 0 | 1 | **PRODUCTION** |
| `create_demo_project` | 10 | 1 | **PRODUCTION** |
| `list_demo_projects` | 5 | 0 | **PRODUCTION** |
| `init_pseudo_dirs` | 3 | 0 | **PRODUCTION** |
| `list_pseudo_libraries` | 1 | 0 | **PRODUCTION** |
| `get_library_status` | 3 | 0 | **PRODUCTION** |
| `install_pseudo_library` | 1 | 0 | **PRODUCTION** |
| `remove_pseudo_library` | 1 | 0 | **PRODUCTION** |
| `repair_pseudo_library` | 1 | 0 | **PRODUCTION** |
| `compute_store_size` | 3 | 0 | **PRODUCTION** |
| `is_pseudo_archive_installed` | 1 | 0 | **PRODUCTION** |
| `install_pseudo_archive` | 3 | 0 | **PRODUCTION** |
| `install_sssp_from_seed` | 1 | 0 | **PRODUCTION** |
| `install_all_sssp_from_seed` | 1 | 0 | **PRODUCTION** |
| `download_sssp_library` | 3 | 0 | **PRODUCTION** |
| `download_all_sssp` | 3 | 0 | **PRODUCTION** |
| `import_seed_archives` | 3 | 0 | **PRODUCTION** |

**All 23 static methods are legitimate production code used by daemon or CLI.**

### Why Static?

These methods are static because they operate without a project context:
- **Project initialization**: `init_project`, `create_demo_project` - Cannot have a project instance before creating one
- **Global settings**: `get_settings` - User-level settings, not project-level
- **Pseudo management**: 14 methods - Pseudopotential library is machine-wide, not per-project
- **Workflow registry**: `get_workflow_service`, `get_default_step_params`, etc. - Global workflow definitions

**Conclusion**: Static methods are correctly designed; no slimming opportunity here.

---

## Tests-Only Entrypoints Audit

### Methodology

Searched for methods where:
- `daemon_refs == 0`
- `cli_refs == 0`
- `test_refs > 0`

Using accessor-qualified patterns (e.g., `svc.engine.list`) to avoid false positives.

### Detailed Audit Table

| Entrypoint | Location | Tests Calling It | Behavior | Classification | Action | Risk |
|------------|----------|------------------|----------|----------------|--------|------|
| `Analysis.list_properties` | service.py:104 | `test_analysis_capabilities.py` | Returns list of available artifact types for a calc/step | **A) Future capability** | KEEP | LOW - tested contract |
| `Analysis.get_property_ref` | service.py:152 | `test_analysis_capabilities.py` | Returns reference to analysis artifact (for lazy loading) | **A) Future capability** | KEEP | LOW - tested contract |
| `Analysis.load_artifact` | service.py:249 | `test_analysis_capabilities.py` (8 calls) | Load analysis artifact from reference | **A) Future capability** | KEEP | LOW - tested contract |
| `Analysis.get_summary` | service.py:53 | `test_analysis_capabilities.py` | Get analysis summary DTO | **A) Future capability** | KEEP | LOW - tested contract |
| `Analysis.find_band_files` | service.py:1447 | **NONE** | Thin wrapper around utils `find_band_analysis_files` | **UNUSED** | DELETE | NONE - no callers |
| `Engine.list` | service.py:6144 | `test_engine_capabilities.py` | List available engines | **A) Future capability** | KEEP | LOW - tested contract |
| `Engine.get_info` | service.py:6170 | `test_engine_capabilities.py` | Get engine info | **A) Future capability** | KEEP | LOW - tested contract |
| `Engine.list_step_types` | service.py:6219 | `test_engine_capabilities.py` | List supported step types | **A) Future capability** | KEEP | LOW - tested contract |
| `Engine.validate_installation` | service.py:6255 | `test_engine_capabilities.py` (4 calls) | Validate engine installation | **A) Future capability** | KEEP | LOW - tested contract |
| `Project.get_species_map` | service.py:5592 | `test_project_capabilities.py` | Return `config.get("species_map", {})` | **D) Test-only helper** | DELETE | LOW - trivial wrapper |
| `Project.get_potential_map` | service.py:5616 | `test_project_capabilities.py` | Return `config.get("potential_map", {})` | **D) Test-only helper** | DELETE | LOW - trivial wrapper |

### Classification Justification

#### A) Future Capability (7 methods)

**Evidence for "future use"**:
1. These methods are in `tests/api/test_*_capabilities.py` - explicit capability contract tests
2. The tests verify return types/schema, not just that methods exist
3. The Analysis/Engine domains are documented as PR3/PR9 features in service.py
4. Comment in service.py line 46: "Analysis domain (PR3)"
5. Comment in service.py line 6137: "Engine domain (PR9)"

**When should these become production-used?**
- `Engine.*` methods: When GUI adds engine management panel (currently uses utils functions)
- `Analysis.list_properties`, `get_property_ref`, `load_artifact`: When GUI adds lazy-loading artifact browser

**Recommendation**: Keep these. They represent planned future API surface with tested contracts.

#### D) Test-Only Helper (2 methods)

**`Project.get_species_map()`** - service.py:5592
```python
def get_species_map(self) -> dict:
    config = load_project_config(self._service.project_root)
    return config.get("species_map", {})
```
- **What it does**: Returns species_map from project config
- **Inputs**: None (uses project_root from service)
- **Outputs**: dict (may be empty)
- **Why it exists**: Convenience method for tests
- **Who should own it**: Not API - callers can use `svc.project.get_config().get("species_map", {})`
- **Action**: DELETE - redundant with `get_config()`
- **Migration**: Update test to use `get_config()` pattern

**`Project.get_potential_map()`** - service.py:5616
```python
def get_potential_map(self) -> dict:
    config = load_project_config(self._service.project_root)
    return config.get("potential_map", {})
```
- Same analysis as `get_species_map` - DELETE

#### UNUSED (1 method)

**`Analysis.find_band_files()`** - service.py:1447
```python
def find_band_files(self, directory: Path, prefix: str | None = None) -> Any:
    from quantumvitas.calculation.naming import find_band_analysis_files
    return find_band_analysis_files(Path(directory), prefix=prefix)
```
- **What it does**: Finds band analysis files in a directory
- **Inputs**: directory (Path), prefix (str|None)
- **Outputs**: BandAnalysisFiles (kernel type)
- **Why it exists**: Unclear - thin wrapper with no callers
- **Who should own it**: Already exists in utils as `find_band_analysis_files`
- **Action**: DELETE - zero usage, duplicate functionality
- **Risk**: NONE - no code uses this

---

## Static Methods: Ownership Analysis

Since all 23 static methods ARE used by daemon/CLI, we analyze why they're static rather than nested:

### Group 1: Project Initialization (Cannot Have Instance)

| Method | Daemon | CLI | Justification |
|--------|--------|-----|---------------|
| `init_project` | 1 | 1 | Creates project - no QVService instance possible before creation |
| `create_demo_project` | 10 | 1 | Creates project from template |
| `list_demo_projects` | 5 | 0 | Lists available demos (no project needed) |

**Conclusion**: Correctly static - cannot be nested accessor methods.

### Group 2: Global Settings (User-Level, Not Project-Level)

| Method | Daemon | CLI | Justification |
|--------|--------|-----|---------------|
| `get_settings` | 6 | 0 | Reads ~/.qmatsuite/settings.json (user-level) |

**Conclusion**: Correctly static.

### Group 3: Workflow Registry (Global Definitions)

| Method | Daemon | CLI | Justification |
|--------|--------|-----|---------------|
| `get_workflow_service` | 4 | 0 | Returns global workflow service singleton |
| `get_default_step_params` | 0 | 1 | Returns step defaults from global registry |
| `resolve_step_type_spec` | 0 | 1 | Converts GEN→SPEC using global registry |
| `generate_kpath` | 0 | 1 | Pure function on structure (no project context) |
| `run_single_step` | 5 | 0 | Legacy wrapper - delegates to `run.run_step` |

**Potential issue**: `run_single_step` takes `project_root` as parameter, so it COULD be a nested method. However, daemon calls it with explicit project_root for job scheduling reasons. **Keep as-is** - no slimming benefit.

### Group 4: Pseudo Library Management (Machine-Wide)

| Method | Daemon | CLI | Justification |
|--------|--------|-----|---------------|
| `init_pseudo_dirs` | 3 | 0 | Creates ~/.qmatsuite/pseudo/ directories |
| `list_pseudo_libraries` | 1 | 0 | Lists globally available libraries |
| `get_library_status` | 3 | 0 | Checks library installation status |
| `install_pseudo_library` | 1 | 0 | Installs to global store |
| `remove_pseudo_library` | 1 | 0 | Removes from global store |
| `repair_pseudo_library` | 1 | 0 | Repairs global store |
| `compute_store_size` | 3 | 0 | Computes global store size |
| `is_pseudo_archive_installed` | 1 | 0 | Checks global archive |
| `install_pseudo_archive` | 3 | 0 | Installs to global store |
| `install_sssp_from_seed` | 1 | 0 | Installs from seed directory |
| `install_all_sssp_from_seed` | 1 | 0 | Installs all from seed |
| `download_sssp_library` | 3 | 0 | Downloads to global store |
| `download_all_sssp` | 3 | 0 | Downloads all to global store |
| `import_seed_archives` | 3 | 0 | Imports archives to global store |

**Conclusion**: These are correctly static - pseudopotential library is machine-wide, not per-project.

### Clarity Refactor Opportunity (Not Slimming)

The 14 pseudo methods could be grouped under a `pseudo_library` static accessor for clarity:

```python
# Current (14 static methods on QVService)
QVService.init_pseudo_dirs()
QVService.list_pseudo_libraries()
# ... 12 more

# Proposed (1 static accessor returning object)
QVService.pseudo_library().init_dirs()
QVService.pseudo_library().list()
```

**This is NOT slimming** - it's a clarity refactor. The entrypoint count stays at 14 (the accessor itself is 1 entrypoint, plus 14 methods = 15, which is WORSE).

**Decision**: Keep current design. Adding a nested layer does not reduce surface area and violates the "no multi-layer facade" constraint.

---

## Consolidation Opportunities

### Cluster 1: Structure Visualization (SLIMMING: -1)

**Current entrypoints (2 utils)**:
- `visualize_structure(structure, ...)` - Returns visualization dict (CLI usage: 2)
- `build_structure_vis_payload(structure, params)` - Returns visualization dict (daemon usage: 3)

**Analysis**:
- Both functions produce similar output (visualization primitives)
- `visualize_structure` is higher-level (creates DisplayModeParams internally)
- `build_structure_vis_payload` takes explicit DisplayModeParams

**Proposed**: Keep `build_structure_vis_payload` as the canonical, delete `visualize_structure`

**Expected delta**: **-1**

**Migration**: 2 CLI call sites migrate to `build_structure_vis_payload`

**Risks**: Low - both functions tested

### Cluster 2: Internal Model Leaks (SLIMMING: -2)

**Current entrypoints**:
- `load_calculation(path, project_root)` → returns `CalculationModel` (internal type)
- `save_calculation(model, path)` → accepts `CalculationModel` (internal type)

**Analysis**:
- These expose internal kernel types (`CalculationModel`) through the API
- Violates API isolation - callers become coupled to kernel internals
- Tests use these heavily (t=121, t=21) but could use service methods instead

**Proposed**: DELETE both

**Expected delta**: **-2**

**Migration**:
- Tests calling `load_calculation` should use `svc.calculation.get()` returning `CalculationDTO`
- Tests calling `save_calculation` should use `svc.calculation.update_*()` methods

**Risks**: Medium - requires test migration (121 + 21 = 142 test refs)

### Cluster 3: More Internal Model Leaks (SLIMMING: -4)

**Current entrypoints**:
- `create_default_registry(config_dict)` → returns `EngineRegistry`
- `get_journal()` → returns `Journal`
- `create_blob_store(calc_dir)` → returns `BlobStore`
- `create_precision_advisor(calculation_dir)` → returns `PrecisionAdvisor`

**Analysis**: All return internal kernel types, violating API isolation.

**Proposed**: DELETE all (or move to internal-only module not in api/)

**Expected delta**: **-4**

**Migration**: Tests can import from kernel directly if needed

**Risks**: Medium - test migration required

### Cluster 4: Unused Service Methods (SLIMMING: -3)

**Current entrypoints**:
- `Analysis.find_band_files` - UNUSED (d=0, c=0, t=0)
- `Project.get_species_map` - TESTS-ONLY (d=0, c=0, t=3)
- `Project.get_potential_map` - TESTS-ONLY (d=0, c=0, t=3)

**Analysis**: Zero production value; tests can use alternatives

**Proposed**: DELETE all three

**Expected delta**: **-3**

**Migration**:
- `find_band_files`: None needed (no callers)
- `get_species_map`/`get_potential_map`: Tests use `svc.project.get_config().get("species_map", {})`

**Risks**: Low - trivial test migration

---

## Summary: Remaining Opportunities

Based on audited clusters:

| Cluster | Type | Delta | Priority |
|---------|------|-------|----------|
| Unused service methods | Slimming | -3 | HIGH |
| Internal model leaks (load/save_calculation) | Slimming | -2 | MEDIUM |
| Internal model leaks (other) | Slimming | -4 | MEDIUM |
| Structure visualization | Slimming | -1 | LOW |
| **Total** | | **-10** | |

### What's NOT an Opportunity

1. **Static methods** - All 23 are production-used, correctly designed
2. **Engine accessor** - Tests-only but represents planned future capability
3. **Analysis accessor methods** - Tests-only but represents planned future capability
4. **Pseudo library grouping** - Would add facade layer, not reduce count

---

## Appendix: Audit Methodology

### Pattern Matching

Initial report used:
```bash
grep -r "\.method\(" daemon/
```

This MISSED static method calls like `QVService.init_project(...)` because they don't have a leading dot.

Corrected approach:
```bash
grep -r "QVService\." daemon/  # For static methods
grep -r "svc\.accessor\.method" daemon/  # For nested methods
```

### Verified Counts

All counts re-verified using:
```python
def count_refs(pattern, search_dir):
    result = subprocess.run(['grep', '-r', '-c', pattern, str(search_dir)], ...)
```

With explicit patterns for each entrypoint category.

---

**End of Report**
