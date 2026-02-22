# CLI Migration Map

**Status**: Batch 3 (Preparation) - Migration map created, Chunk 1 wrappers identified

**Date**: 2025-01-27

**Audit Summary**:
- Total violations: 142
- Bare resolve_* calls: 3
- Single file: `src/qmatsuite/cli/main.py`

## Top 10 Kernel Modules by Import Count

1. **qmatsuite.core.resolution** (30 imports)
   - `build_resource_index`: 10 uses
   - `require_calculation`: 5 uses
   - `require_structure`: 4 uses
   - `resolve_step`: 2 uses
   - `require_step`: 1 use
   - `ResourceNotFoundError`: 2 uses
   - `make_structure_selector_resolver`: 2 uses
   - `resolve_structure`: 1 use
   - Other symbols: 3 uses

2. **qmatsuite.core.project_utils** (30 imports)
   - Many utility functions used across CLI commands
   - Functions: `load_project_config`, `save_project_config`, `find_project_root`, `collect_slugs`, `entry_matches`, `entry_display_name`, `ensure_structure_entry_defaults`, `ensure_calculation_entry_defaults`, `find_structure_entry`, `find_calculation_entry`, `calculation_directory`, `structure_reference_tokens`, `spec_uses_structure`, `calculations_using_structure`, `calculation_identifiers`, `calculations_depending_on`, `move_to_trash`, `apply_structure_rename`, `apply_calculation_rename`, `delete_calculation_entry`, `require_project_root`, `find_enclosing_calculation`, `find_step_in_calculation`, `find_resource_auto`, `resolve_resource`

3. **qmatsuite.core.context** (11 imports)
   - `find_path_context_from_pwd`: 6 uses
   - `ContextNotFoundError`: 5 uses

4. **qmatsuite.core.selectors** (7 imports)
   - `extract_calculation_selector_from_entry`: 1 use
   - `extract_structure_selector_from_entry`: 1 use
   - `extract_step_selector_from_entry`: 1 use
   - `match_step_selector`: 1 use
   - `get_calculation_selector_from_entry_or_raise`: 1 use
   - `get_structure_selector_from_entry_or_raise`: 1 use
   - `get_step_selector_from_entry_or_raise`: 1 use

5. **qmatsuite.core.resources** (6 imports)
   - `ResourceMeta`: 1 use
   - `ensure_relative_path`: 1 use
   - `generate_resource_id`: 1 use
   - `generate_unique_name_and_slug`: 1 use
   - `meta_from_name`: 1 use
   - `slugify`: 1 use

6. **qmatsuite.calculation.structure_steps** (6 imports)
   - `StructureStepSpec`: 2 uses
   - `generate_qe_input_from_spec`: 1 use
   - `generate_qe_input_from_structure`: 1 use
   - `materialize_step_spec`: 1 use
   - `detect_runtime_control_keys`: 1 use

7. **qmatsuite.calculation.input_runner** (5 imports)
   - `ParameterOverride`: 1 use
   - `apply_card_overrides_to_qe_input`: 1 use
   - `apply_species_overrides_to_qe_input`: 1 use
   - `detect_project_root`: 1 use
   - `run_input_step`: 1 use

8. **qmatsuite.io** (5 imports)
   - `QEInputGenerator`: 1 use
   - `read_structure`: 3 uses
   - `write_structure`: 1 use

9. **qmatsuite.analysis.parsers** (4 imports)
   - `parse_scf_output`: 1 use
   - `parse_dos_data`: 1 use
   - `parse_bands_gnu`: 1 use
   - `DOSData`: 1 use

10. **qmatsuite.analysis.plotting** (4 imports)
    - `plot_dos`: 1 use
    - `plot_bands`: 1 use
    - `plot_scf_convergence`: 1 use
    - `save_figure`: 1 use

## Migration Chunks

### Chunk 1: Resolution & Context (10-15 call sites)
**Target**: Core resolution functions and context detection

**CLI Functions Affected**:
- `analyze_band_command` (uses `build_resource_index`, `require_calculation`, `find_path_context_from_pwd`)
- `analyze_output_command` (uses `build_resource_index`, `require_calculation`, `find_path_context_from_pwd`)
- `analyze_dos_command` (uses `find_path_context_from_pwd`)
- `analyze_energy_command` (uses `find_path_context_from_pwd`)
- `configure_calculation_command` (uses `build_resource_index`, `resolve_step`, `resolve_structure`, `make_structure_selector_resolver`)
- `configure_step_command` (uses `load_project_config`, `find_project_root`, `make_structure_selector_resolver`)
- `delete_structure_command` (uses `build_resource_index`, `require_structure`)
- `init_calculation_command` (uses `require_structure`)
- `run_calculation_command` (uses `build_resource_index`, `require_calculation`)
- `run_step_command` (uses `build_resource_index`)

**Kernel Modules**:
- `qmatsuite.core.resolution` (primary)
- `qmatsuite.core.context` (secondary)

**QMSService Wrappers Needed** (Chunk 1):
1. ✅ `build_resource_index()` - **EXISTS** (already in QMSService)
2. ✅ `resolve_calculation_ref()` - **EXISTS** (already in QMSService)
3. ✅ `resolve_step_ref()` - **EXISTS** (already in QMSService)
4. ✅ `resolve_structure_ref()` - **EXISTS** (already in QMSService)
5. ✅ `find_path_context_from_pwd()` - **EXISTS** (static method in QMSService, line 9585)
6. ❌ `require_calculation_ref()` - **NEEDED** (wrapper for `require_calculation`)
7. ❌ `require_structure_ref()` - **NEEDED** (wrapper for `require_structure`)
8. ❌ `require_step_ref()` - **NEEDED** (wrapper for `require_step`)
9. ❌ `make_structure_selector_resolver()` - **NEEDED** (used in configure commands)

**Migration Pattern**:
```python
# BEFORE:
from qmatsuite.core.resolution import build_resource_index, require_calculation
index = build_resource_index(project_root)
calc = require_calculation(project_root, selector, config=config, index=index)

# AFTER:
svc = QMSService(project_root)
index = svc.build_resource_index()
calc_ref = svc.require_calculation_ref(selector, index=index)
```

### Chunk 2: Project Utilities - Entry Lookup (10-15 call sites)
**Target**: Entry finding and matching functions

**CLI Functions Affected**:
- `init_calculation_command`
- `configure_calculation_command`
- `configure_step_command`
- `delete_structure_command`
- `delete_calculation_command`
- Various helper functions

**Kernel Modules**:
- `qmatsuite.core.project_utils` (entry lookup subset)

**QMSService Wrappers Needed**:
1. `find_structure_entry_ref()` - wrapper for `find_structure_entry`
2. `find_calculation_entry_ref()` - wrapper for `find_calculation_entry`
3. `entry_matches_ref()` - wrapper for `entry_matches`
4. `entry_display_name_ref()` - wrapper for `entry_display_name`

### Chunk 3: Project Utilities - Resource Management (10-15 call sites)
**Target**: Resource operations (rename, delete, move)

**CLI Functions Affected**:
- `delete_structure_command`
- `delete_calculation_command`
- `configure_structure_command`
- `configure_calculation_command`

**Kernel Modules**:
- `qmatsuite.core.project_utils` (resource management subset)

**QMSService Wrappers Needed**:
1. `move_to_trash_ref()` - wrapper for `move_to_trash`
2. `apply_structure_rename_ref()` - wrapper for `apply_structure_rename`
3. `apply_calculation_rename_ref()` - wrapper for `apply_calculation_rename`
4. `delete_calculation_entry_ref()` - wrapper for `delete_calculation_entry`
5. `calculations_using_structure_ref()` - wrapper for `calculations_using_structure`

### Chunk 4: Selectors & Resources (10-15 call sites)
**Target**: Selector extraction and resource metadata

**CLI Functions Affected**:
- Various helper functions
- Multiple commands using selectors

**Kernel Modules**:
- `qmatsuite.core.selectors`
- `qmatsuite.core.resources`

**QMSService Wrappers Needed**:
1. `extract_calculation_selector_ref()` - wrapper for `extract_calculation_selector_from_entry`
2. `extract_structure_selector_ref()` - wrapper for `extract_structure_selector_from_entry`
3. `extract_step_selector_ref()` - wrapper for `extract_step_selector_from_entry`
4. `generate_unique_name_and_slug_ref()` - wrapper for `generate_unique_name_and_slug`
5. `meta_from_name_ref()` - wrapper for `meta_from_name`
6. `ensure_relative_path_ref()` - wrapper for `ensure_relative_path`

### Chunk 5: Calculation & Step Operations (10-15 call sites)
**Target**: Calculation runner, step specs, input generation

**CLI Functions Affected**:
- `run_step_command`
- `run_calculation_command`
- `init_step_command`
- `_run_standalone_step`

**Kernel Modules**:
- `qmatsuite.calculation.runner`
- `qmatsuite.calculation.structure_steps`
- `qmatsuite.calculation.input_runner`
- `qmatsuite.calculation.types`

**QMSService Wrappers Needed**:
1. `run_calculation_ref()` - **EXISTS** (already in QMSService)
2. `run_step_ref()` - **EXISTS** (already in QMSService)
3. `generate_qe_input_from_spec_ref()` - wrapper for `generate_qe_input_from_spec`
4. `generate_qe_input_from_structure_ref()` - wrapper for `generate_qe_input_from_structure`
5. `apply_card_overrides_ref()` - wrapper for `apply_card_overrides_to_qe_input`
6. `apply_species_overrides_ref()` - wrapper for `apply_species_overrides_to_qe_input`

### Chunk 6: Analysis & I/O (10-15 call sites)
**Target**: Analysis parsers, plotting, structure I/O

**CLI Functions Affected**:
- `analyze_output_command`
- `analyze_band_command`
- `analyze_dos_command`
- `analyze_structure_command`
- `init_calculation_command`

**Kernel Modules**:
- `qmatsuite.analysis.parsers`
- `qmatsuite.analysis.plotting`
- `qmatsuite.io`
- `qmatsuite.analysis.structure_viz`

**QMSService Wrappers Needed**:
1. `read_structure_ref()` - wrapper for `read_structure`
2. `write_structure_ref()` - wrapper for `write_structure`
3. `parse_scf_output_ref()` - wrapper for `parse_scf_output`
4. `parse_dos_data_ref()` - wrapper for `parse_dos_data`
5. `parse_bands_gnu_ref()` - wrapper for `parse_bands_gnu`
6. `visualize_structure_ref()` - **EXISTS** (already in QMSService)

### Chunk 7: Templates & Initialization (10-15 call sites)
**Target**: Template copying, step defaults, kpath generation

**CLI Functions Affected**:
- `init_calculation_command`
- `init_step_command`

**Kernel Modules**:
- `qmatsuite.core.templates`
- `qmatsuite.calculation.step_defaults`
- `qmatsuite.analysis.kpath`

**QMSService Wrappers Needed**:
1. `copy_calculation_template_ref()` - wrapper for `copy_calculation_template`
2. `copy_structure_template_ref()` - wrapper for `copy_structure_template`
3. `list_calculation_templates_ref()` - wrapper for `list_calculation_templates`
4. `get_default_step_params_ref()` - wrapper for `get_default_step_params`
5. `generate_kpath_ref()` - wrapper for `generate_kpath`

### Chunk 8: Remaining Utilities (10-15 call sites)
**Target**: Remaining project utilities, calculation naming, species config

**CLI Functions Affected**:
- `configure_species_command`
- `show_command`
- Various helper functions

**Kernel Modules**:
- `qmatsuite.calculation.species_config`
- `qmatsuite.calculation.naming`
- `qmatsuite.io.model`
- `qmatsuite.calculation.importers`

**QMSService Wrappers Needed**:
1. `configure_species_map_ref()` - wrapper for `configure_species_map`
2. `find_band_analysis_files_ref()` - wrapper for `find_band_analysis_files`
3. `find_calculation_raw_dir_ref()` - wrapper for `find_calculation_raw_dir`
4. `find_calculation_results_dir_ref()` - wrapper for `find_calculation_results_dir`

## Migration Strategy

1. **Wrapper-first approach**: Never remove an import until a QMSService wrapper exists
2. **Small chunks**: 10-20 call sites per chunk to keep changes manageable
3. **Test after each chunk**: Run full test suite after each chunk migration
4. **Incremental commits**: Commit after each successful chunk

## Chunk 1 Implementation Plan

### Step 1: Add Missing QMSService Wrappers
Add these methods to `QMSService` class in `src/qmatsuite/api.py`:

1. `require_calculation_ref(selector, *, index=None, config=None) -> ResolvedResource`
2. `require_structure_ref(selector, *, index=None, config=None) -> ResolvedResource`
3. `require_step_ref(calc_selector, step_selector, *, index=None, config=None) -> ResolvedResource`
4. `make_structure_selector_resolver(*, index=None, config=None) -> Callable`

### Step 2: Add Unit Tests
Create/extend tests in `tests/unit/test_api_*.py` to verify:
- Wrappers correctly call underlying kernel functions
- Error handling works correctly
- Return types match expected ResolvedResource

### Step 3: Verify Importability
- `python -m py_compile src/qmatsuite/cli/main.py`
- `python -c "import qmatsuite.cli.main; print('CLI import ok')"`
- `python -m pytest tests/gates/test_import_rules.py -v -rs`
- `python -m pytest tests/ -v --tb=short -n auto --dist=loadfile`

## Notes

- All wrappers should be instance methods (use `self.project_root`)
- Keep wrapper names generic (no `*_for_cli` suffix)
- Prefer returning dicts/strings over re-exporting kernel types
- Exception handling: wrap kernel exceptions in `QMSServiceError` where appropriate

