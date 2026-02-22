# Tutorial Dataset Importer - Implementation Summary

## Overview

This document summarizes the implementation of the tutorial dataset importer that converts legacy QE tutorial/test datasets into QMatSuite demo project snapshots.

## Implementation

### Script Location
- **Main script**: `tools/import_tutorial_datasets.py`
- **Documentation**: `tools/README_import_tutorials.md`

### Key Features

1. **Dataset Discovery**
   - Automatically scans `tests/data/` for folders `0_*` through `19_*`
   - Handles subcases (e.g., `14_DFT_plus_U_NiO/1_noU`, `2_addU`)
   - Sorts input files by execution order (extracts numeric prefixes from filenames)

2. **Pseudopotential Mapping**
   - Extracts pseudopotential filenames from `ATOMIC_SPECIES` cards
   - Searches in dataset folder, `tests/data/`, and `pseudo/` directory
   - Automatically downloads missing pseudos to `repo/pseudo/` using `QMSService.download_pseudo_by_filename()`
   - Reports failures if download also fails (404 errors)
   - During demo expansion, pseudos are copied from `repo/pseudo/` to `project/pseudo/`

3. **Project Structure Creation**
   - Uses QMSService API (matching manual workflow):
     - `QMSService.init_project()` - Creates empty project
     - `QMSService.import_structure()` - Imports structure from first `.in` file
     - `QMSService.init_calculation()` - Creates calculation with structure
     - `QMSService.import_step_from_qe_input()` - Imports each step sequentially
   - Creates complete project structure with:
     - `project.qms.yml` (project config)
     - `calculations/main/calculation.yaml` (calculation config)
     - `calculations/main/steps/*.step.yaml` (step specs)
     - `structures/*.json` (structure files)
   - **Core function**: `materialize_project_from_input_folder()` - Reusable function to materialize a project from a folder of `.in` files

4. **Round-Trip Validation**
   - Parses original QE input
   - Creates step spec from input
   - Generates QE input from step spec
   - Compares semantically (not strict textual)
   - Reports differences in:
     - Namelist parameters (excluding structure-related)
     - Card data (K_POINTS only - structure cards excluded)
     - Module detection
   - **Note**: Structure cards (ATOMIC_POSITIONS, CELL_PARAMETERS, ATOMIC_SPECIES) are not in steps - they're in the structure section or `species_overrides`

5. **Demo Snapshot Generation**
   - Uses `export_project_to_snapshot()` to create project snapshots
   - Adds demo metadata (title, description, tags, source)
   - Creates `demo.json` manifest with:
     - Demo ID and metadata
     - Step list
     - Validation status
     - Pseudopotential list
   - Copies original inputs to `reference_inputs/`
   - Copies reference outputs to `reference_outputs/` (if available)

6. **Reporting**
   - Generates JSON report (`import_report.json`) with:
     - Total datasets discovered
     - Success/failure counts
     - Per-demo details (errors, missing pseudos, validation status)
   - Generates Markdown report (`import_report.md`) with:
     - Human-readable summary
     - Successful imports list
     - Failed imports with reasons

## Architecture

### Key Components

1. **DatasetInfo**: Dataclass storing dataset metadata
   - Folder name and path
   - Input files list
   - Subcases (if any)
   - Reference output directory

2. **ValidationResult**: Dataclass for round-trip validation results
   - Success flag
   - Differences list
   - Error message (if any)

3. **DemoResult**: Dataclass for demo creation results
   - Demo name and path
   - Success flag
   - Validation result
   - Missing pseudos list
   - Error message
   - Step count

### Functions

- `discover_datasets()`: Scans `tests/data/` and finds all datasets
- `sort_input_files_by_execution_order()`: Sorts `.in` files by numeric prefix
- `materialize_project_from_input_folder()`: **Core function** - Materializes a project from a folder of `.in` files
  - Handles structure preprocessing (injects missing CELL_PARAMETERS, fixes ibrav issues)
  - Uses QMSService API to create project, import structure, create calculation, import steps
  - Rebuilds resource index after each major step
- `extract_pseudopotential_names()`: Extracts pseudo filenames from ATOMIC_SPECIES
- `find_pseudopotential_file()`: Searches for pseudo files in search directories
- `validate_roundtrip()`: Performs semantic comparison of original vs generated input
- `create_demo_from_dataset()`: Main function that creates a demo from a dataset
- `verify_demo_consistency()`: Verifies generated demo can be loaded and checks structure

## Usage

```bash
# From repository root
python tools/import_tutorial_datasets.py
```

The script will:
1. Discover all datasets in `tests/data/`
2. Process each dataset
3. Create demo snapshots in `demos/qe_tutorials/`
4. Generate reports

## Output Structure

```
demos/qe_tutorials/
├── 0_Si_scf/
│   ├── demo.qms.yml          # Project snapshot
│   ├── demo.json            # Demo manifest
│   ├── reference_inputs/    # Original .in files
│   └── reference_outputs/   # Original .out files (if available)
├── 4_Si_DOS/
│   └── ...
├── 14_DFT_plus_U_NiO__1_noU/
│   └── ...
├── 14_DFT_plus_U_NiO__2_addU/
│   └── ...
├── import_report.json        # Machine-readable report
└── import_report.md          # Human-readable report
```

## Design Principles

1. **Snapshot Truth**: Demos are fully materialized snapshots with explicit parameters
2. **No Workflow Dependencies**: Demos do not depend on workflow/preset implementations
3. **Artifact-Driven**: Analysis works with whatever outputs exist
4. **Robustness**: Handles irregularities without overfitting to specific cases
5. **Graceful Failure**: Reports clear errors instead of crashing

## Error Categories

The importer categorizes failures:

1. **Missing Pseudopotentials**: Lists which pseudos are missing
2. **Parser Errors**: Reports parsing failures with error details
3. **Validation Failures**: Reports semantic differences in round-trip
4. **Structure Errors**: Reports issues with structure extraction
5. **General Errors**: Catches and reports other exceptions

## Validation Strategy

Round-trip validation is **semantic**, not strict textual:
- Ignores whitespace differences
- Ignores parameter order differences
- Ignores structure-related parameters (stored in structure JSON)
- Compares:
  - Namelist parameters (excluding structure-related)
  - Card data (K_POINTS only - structure cards are excluded)
  - Module detection
  - Pseudopotential names (from `species_overrides`)

**Structure Separation:**
- `ATOMIC_POSITIONS` and `CELL_PARAMETERS`: Stored in structure JSON, not in steps
- `ATOMIC_SPECIES`: Extracted to `species_overrides` (mass, pseudopotential), not in cards
- Steps only contain calculation-specific cards (K_POINTS, etc.)

## Future Enhancements

Potential improvements:
1. Support for more complex dataset structures
2. Better handling of relax/vc-relax structure propagation
3. Support for NEB calculations with multiple images
4. Automatic pseudopotential download (if allowed)
5. Integration with CI/CD for automated demo updates

## Notes

- The script uses QMSService API (`init_project`, `import_structure`, `init_calculation`, `import_step_from_qe_input`)
- **Structure separation**: Geometry parameters are stored in structure section, not in steps
- **Species overrides**: ATOMIC_SPECIES information is extracted to `species_overrides`, not stored as a card
- Pseudopotentials are automatically downloaded if missing, then copied to demo snapshots
- Original input files are preserved as reference
- Validation is performed on the first step only (can be extended)
- Core function `materialize_project_from_input_folder()` is reusable for other import scenarios

