# QE Code Inventory: Exhaustive Map of QE-Specific Code

> This document provides a complete inventory of all QE-specific code paths across the codebase.

## 1. Core Engine Files (Primary Migration Targets)

### 1.1 `src/qmatsuite/core/engines/qe.py` (622 lines)
**Role**: Main QuantumEspressoEngine class
**Key Components**:
- `QuantumEspressoEngine` class - Primary QE engine implementation
- `EXECUTABLE_MAP` (lines 30-65) - Maps step types to QE executables (pw.x, ph.x, dos.x, etc.)
- `MODULE_NAMELISTS` (lines 72-96) - Maps QE modules to their namelists
- `find_executable()` - QE binary discovery
- `build_command()` (lines 344-425) - Command building with W90 special handling
- `uses_stdin()` - Stdin vs command-line input detection

**Dependencies**:
- Uses `qe_installation.py` for installation detection
- Uses `qe_calculation.py` for step execution
- Uses `qe_resolver.py` for two-state bin resolution

### 1.2 `src/qmatsuite/core/engines/qe_calculation.py` (~705 lines)
**Role**: QE calculation runner for step/chain execution
**Key Components**:
- `QECalculationRunner` class
- `run_step()` - Single step execution
- `run_calculation()` - Multi-step sequential execution
- `detect_step_type()` - Step type auto-detection from input
- Extensive W90 step handling (w90_preproc, w90_run, pw2wannier90)
- `ESPRESSO_PSEUDO` environment variable setup
- Post-run verification for different step types

### 1.3 `src/qmatsuite/core/engines/qe_installation.py` (571 lines)
**Role**: QE installation detection and path management
**Key Components**:
- `QEInstallation` class - Represents QE installation
- `_detect_qe_home()` - Auto-detection heuristics
- `_extract_from_shell_config()` - Parses ~/.zshrc, ~/.bashrc for QE paths
- `qe_home_from_binary()` - Infers QE_HOME from executable path
- `_validate_qe_home()` - Validates QE installation (checks for bin/pw.x)

**Note**: DEPRECATED for runtime selection - use `qe_resolver.py` instead

### 1.4 `src/qmatsuite/core/engines/qe_resolver.py` (192 lines)
**Role**: Two-state QE bin directory resolution
**Key Components**:
- `resolve_qe_bin_dir()` - Main entry point for QE resolution
- `find_internal_qe_bin_dir()` - Auto-selects from `.qmatsuite/engines/qe/**/bin`
- `validate_qe_bin_dir()` - Validates bin directory has pw.x
- Two-state model: external (settings.qe.bin_dir) or internal (auto-select)

### 1.5 `src/qmatsuite/core/engines/qe_binary_locator.py` (69 lines)
**Role**: Helper for locating QE executables
**Key Components**:
- `locate_qe_executable()` - Finds QE executables via engine discovery
- `locate_pw2wannier90()` - Specific helper for pw2wannier90.x

### 1.6 `src/qmatsuite/core/engines/qe_diagnostics.py` (196 lines)
**Role**: Diagnostic tools for QE engine resolution
**Key Components**:
- `QEResolutionReport` dataclass - Diagnostic report
- `diagnose_qe_resolution()` - Full diagnostic for QE resolution
- `check_settings_for_external_engines()` - Settings validation
- `check_environment_variables()` - Env var inspection
- `check_managed_engines()` - Managed engine inspection

### 1.7 `src/qmatsuite/core/engines/qe_pseudopotentials.py` (226 lines)
**Role**: QE pseudopotential management
**Key Components**:
- `download_pseudopotential()` - Downloads from QE pseudo server
- `PseudoManager` dataclass - Centralized pseudo management
- Resolution order: project pseudo → global pseudo → test-suite → download

### 1.8 `src/qmatsuite/core/engines/qe_registry.py`
**Role**: QE-specific registry utilities

### 1.9 `src/qmatsuite/core/engines/qe_seed.py`
**Role**: QE seed/seedname handling

---

## 2. Driver Shim (To Be Replaced)

### 2.1 `src/qmatsuite/drivers/qe_shim/__init__.py` (194 lines)
**Role**: Minimal driver shim wrapping legacy QE code
**Key Components**:
- `QELegacyDriver` class extending `BaseEngineDriver`
- `get_step_type_specs()` - Returns 20+ QE step types
- `get_handler()` - Returns `qe_step_handler`
- `get_recipe_class()` - Returns `QERecipe`
- `get_materialization_map()` - GEN_* → qe_* mappings
- `WorkdirPolicy.SHARED` - QE uses shared outdir model

**Step Types Registered** (20):
- qe_scf, qe_relax, qe_vc_relax, qe_bands, qe_bands_pw
- qe_nscf, qe_dos, qe_pdos, qe_ph, qe_q2r
- qe_matdyn, qe_dynmat, qe_pp, qe_plotband, qe_hp
- qe_md, qe_vc_md, qe_pw2wannier90, qe_custom, w90_preproc

---

## 3. Engine Wrapper

### 3.1 `src/qmatsuite/engine/qe_engine.py` (79 lines)
**Role**: Thin adapter over legacy QuantumEspressoEngine
**Key Components**:
- `QeEngine` class extending `Engine`
- `supported_presets` property - Returns QE preset dimensions
- `run_step()` - Delegates to legacy engine

---

## 4. Execution Layer

### 4.1 `src/qmatsuite/execution/handlers.py` (436 lines)
**QE-Specific Content**:
- `qe_step_handler()` (lines 141-293) - Main QE step handler
- `handle_qe_relax_output()` (lines 303-362) - Relax artifact handling
- `_get_step_input_from_calculation_yaml()` - Compat input playback
- Fallback to `qe_step_handler` in `create_handler_map()` (lines 403-413)

### 4.2 `src/qmatsuite/execution/recipes.py` (280 lines)
**QE-Specific Content**:
- `QERecipe` class (lines 157-234) - Creates one job per QE step
- Uses shared outdir model: `scratch_dir: calc_raw_dir / "outdir"`
- Directory-state, step-run model

---

## 5. I/O Layer (QE Models, Parsers, Generators)

### 5.1 `src/qmatsuite/io/model.py` (218 lines)
**Role**: QE data structures
**Key Components**:
- `QEModule` enum - PW, PH, Q2R, MATDYN, PP, etc. (25 modules)
- `QECardType` enum - ATOMIC_SPECIES, ATOMIC_POSITIONS, K_POINTS, etc.
- `QENamelist` dataclass - Represents &control, &system, etc.
- `QECard` dataclass - Represents cards
- `QEInput` dataclass - Complete QE input with `detect_module()`

### 5.2 `src/qmatsuite/io/parser/qe_parser.py`
**Role**: QE input file parser
**Key Components**:
- `QEInputParser` class - Parses QE input files to `QEInput`
- `parse_file()` - Main entry point
- Namelist and card parsing logic

### 5.3 `src/qmatsuite/io/generator/qe_generator.py`
**Role**: QE input file generator
**Key Components**:
- `QEInputGenerator` class - Generates QE input from `QEInput`
- `write_file()` - Main entry point
- Namelist and card serialization

### 5.4 `src/qmatsuite/io/structure_io.py`
**QE-Specific Content**:
- `structure_from_qe_input()` - Extracts pymatgen Structure from QE input

### 5.5 `src/qmatsuite/io/__init__.py`
**Exports**:
- QEModule, QECardType, QENamelist, QECard, QEInput
- QEInputParser, QEInputGenerator
- structure_from_qe_input

---

## 6. IR Backend

### 6.1 `src/qmatsuite/ir/backends/qe/mapping.py` (463 lines)
**Role**: IR ↔ QE adapter mapping
**Key Components**:
- `CLASS_A_TYPES` dict - Strict-typed parameter registry
- `IR_TO_QE_MAPPING` dict - Maps IR keys to (module, section, key) tuples
- `QE_TO_IR_MAPPING` dict - Reverse mapping
- `ir_to_qe_param()` - Converts IR param to QE param
- `qe_to_ir_param()` - Converts QE param to IR param
- `ir_patch_to_qe_patch()` - Patch conversion
- `qe_yaml_to_ir_yaml()` - YAML conversion
- `is_class_a_key()`, `get_class_a_type()` - Type checking

**Note**: This is the ONLY engine with an IR backend

---

## 7. Parsers

### 7.1 `src/qmatsuite/parsers/qe/__init__.py`
**Role**: QE parser module init

### 7.2 `src/qmatsuite/parsers/qe/trajectory.py` (295 lines)
**Role**: QE trajectory parser
**Key Components**:
- `QETrajectoryParser` class - Parses QE MD/relax outputs
- `@register_parser("qe", "trajectory")` decorator
- `_parse_relax_output()` - Relax/vc-relax parsing
- `_parse_md_output()` - MD parsing (placeholder)
- Unit conversions: RY_TO_EV, Bohr to Angstrom

---

## 8. Workflow/Registry

### 8.1 `src/qmatsuite/workflow/registry.py` (947 lines)
**QE-Specific Content** (lines 166-626):
- QE step type specs (~25 entries with `engine="qe"`):
  - qe_scf, qe_nscf, qe_relax, qe_bands_pw, qe_md, qe_vc_md
  - qe_dos, qe_bands, qe_projwfc, qe_pp
  - qe_ph, qe_q2r, qe_matdyn, qe_dynmat
  - w90_preproc, qe_pw2wannier90, w90_run (with `engine="qe"` for compat)
  - qe_custom
- `STEP_TYPE_ALIASES` - Maps vc-relax → relax, etc.

**Note**: W90 steps have `engine="qe"` for backward compatibility

---

## 9. Calculation Layer

### 9.1 `src/qmatsuite/calculation/step.py` (137 lines)
**QE-Specific Content**:
- Line 28: `engine: str = "qe"` - **DEFAULT ENGINE**
- Lines 79-85: Special QE path checking in `run()` method

### 9.2 `src/qmatsuite/calculation/runner.py` (846 lines)
**QE-Specific Content**:
- Line 523: `engine_family = "qe"  # Default`
- Line 631: `engine_name = job.engine or "qe"`
- Line 735: `engine="qe"` in history recording
- Line 761: `engine="qe"` in event creation
- `_get_engine_family_from_step()` with QE/W90 family mapping

### 9.3 `src/qmatsuite/calculation/geometry.py`
**QE-Specific Content**:
- `read_final_geometry_from_output_text()` - Parses QE output
- `structure_from_qe_geometry_snapshot()` - Converts to pymatgen

### 9.4 `src/qmatsuite/calculation/compat_executor.py`
**QE-Specific Content**:
- `run_qe_step_from_existing_input_compat()` - Compat mode execution

### 9.5 `src/qmatsuite/calculation/wannier90_kpoints.py`
**QE-Specific Content**:
- K-point generation for QE+W90 workflows

---

## 10. Core Infrastructure

### 10.1 `src/qmatsuite/core/calc_identity.py` (242 lines)
**QE-Specific Content**:
- Lines 103-107: W90 → QE mapping:
  ```python
  if engine == "w90" or step_type in ("w90_run", "w90_preproc"):
      engine = "qe"
  ```
- Line 132: `return "periodic"  # Default for qe, w90, etc.`

### 10.2 `src/qmatsuite/core/pseudo.py` (492 lines)
**Role**: Pseudopotential handling (QE-centric)
**Key Components**:
- `ensure_qe_pseudos()` - Main pseudo resolution
- Uses `QEInputParser` for ATOMIC_SPECIES extraction
- `PseudoResolutionResult` dataclass
- Species map handling

### 10.3 `src/qmatsuite/core/settings.py`
**QE-Specific Content**:
- `QESettings` class with `bin_dir` field
- Settings section for QE configuration

### 10.4 `src/qmatsuite/core/paths.py`
**QE-Specific Content**:
- `home_qe_engines_dir()` - Returns `.qmatsuite/engines/qe/`

---

## 11. Presets

### 11.1 `src/qmatsuite/presets/capability.py`
**QE-Specific Content**:
- QE engine capability declarations

### 11.2 `src/qmatsuite/presets/integration.py`
**QE-Specific Content**:
- QE preset integration

---

## 12. Data/Metadata

### 12.1 `src/qmatsuite/data/qe_metadata.py`
**Role**: QE module documentation and parameter metadata

### 12.2 `src/qmatsuite/data/qe_module_parameters.json`
**Role**: QE parameter definitions

---

## 13. Other Files with QE References

### 13.1 Files with `"qe"` literals (grep results)
Total: 54 files

**API/CLI**:
- `src/qmatsuite/api.py`
- `src/qmatsuite/cli/main.py`

**Analysis**:
- `src/qmatsuite/analysis/__init__.py`
- `src/qmatsuite/analysis/kpath.py`

**Calculation**:
- `src/qmatsuite/calculation/__init__.py`
- `src/qmatsuite/calculation/calculation.py`
- `src/qmatsuite/calculation/folder_import.py`
- `src/qmatsuite/calculation/importers.py`
- `src/qmatsuite/calculation/input_runner.py`
- `src/qmatsuite/calculation/species_config.py`
- `src/qmatsuite/calculation/standalone.py`
- `src/qmatsuite/calculation/structure_steps.py`

**Core**:
- `src/qmatsuite/core/artifact_scanning.py`
- `src/qmatsuite/core/models.py`
- `src/qmatsuite/core/templates.py`

**Daemon**:
- `src/qmatsuite/daemon/server.py`

**Execution**:
- `src/qmatsuite/execution/job_graph.py`
- `src/qmatsuite/execution/relax_artifacts.py`

**History**:
- `src/qmatsuite/history/run_revision.py`

**IR**:
- `src/qmatsuite/ir/dialects/pw/__init__.py`

**Workflow**:
- `src/qmatsuite/workflow/generalized_steps.py`
- `src/qmatsuite/workflow/templates.py`

---

## Summary Statistics

| Category | File Count | Estimated Lines |
|----------|------------|-----------------|
| Core Engines (qe*.py) | 9 | ~3,200 |
| Driver Shim | 1 | 194 |
| Engine Wrapper | 1 | 79 |
| Execution Layer | 2 | ~400 |
| I/O Layer | 5 | ~1,000 |
| IR Backend | 1 | 463 |
| Parsers | 2 | ~350 |
| Workflow/Registry | 1 | ~300 (QE portion) |
| Calculation Layer | 5 | ~200 (QE portions) |
| Core Infrastructure | 4 | ~300 (QE portions) |
| Data/Metadata | 2 | ~200 |
| Other References | 20+ | ~100 (QE references) |
| **Total** | **54** | **~6,500+** |

---

## Migration Priority

### Must Move (Driver Bundle):
1. `core/engines/qe*.py` (9 files) → `drivers/qe/engine/`
2. `drivers/qe_shim/` → DELETE (replaced by proper driver)
3. `engine/qe_engine.py` → `drivers/qe/`
4. `execution/handlers.py` (QE handler) → `drivers/qe/handler.py`
5. `execution/recipes.py` (QERecipe) → `drivers/qe/recipe.py`
6. `io/model.py` (QE models) → `drivers/qe/io/model.py`
7. `io/parser/qe_parser.py` → `drivers/qe/io/parser.py`
8. `io/generator/qe_generator.py` → `drivers/qe/io/generator.py`
9. `ir/backends/qe/` → `drivers/qe/ir/`
10. `parsers/qe/` → `drivers/qe/parsers/`
11. `data/qe_metadata.py` → `drivers/qe/data/`

### Must Modify (Kernel Cleanup):
1. `calculation/step.py` - Remove `engine: str = "qe"` default
2. `calculation/runner.py` - Remove QE fallbacks
3. `core/calc_identity.py` - Remove W90→QE hardcoding
4. `workflow/registry.py` - Move QE step types to driver bundle
5. `core/pseudo.py` - Generalize or move to driver

### Maintain Backward Compatibility:
1. `io/__init__.py` - Re-export QE types for public API
2. Public API functions that use QE types
