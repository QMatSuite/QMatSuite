# Tutorial Dataset Importer

This tool imports tutorial datasets from `tests/data/` into demo project snapshots.

## Overview

The importer:
1. Scans `tests/data/` for folders matching pattern `0_*` through `19_*`
2. For each dataset, finds `.in` files in execution order
3. Extracts structure and parameters from inputs
4. Maps pseudopotentials from `pseudo/` directory
5. Creates calculation structure using QMatSuite APIs
6. Validates by round-tripping (parse -> export -> compare)
7. Generates demo snapshots in `demos/qe_tutorials/`

## Usage

```bash
# From the repository root
python tools/import_tutorial_datasets.py
```

Or make it executable and run directly:

```bash
chmod +x tools/import_tutorial_datasets.py
./tools/import_tutorial_datasets.py
```

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt` installed
- Pseudopotentials available in `pseudo/` directory

## Output

The tool creates:

1. **Demo snapshots** in `demos/qe_tutorials/`:
   - Each demo is a complete project snapshot
   - Contains `demo.qv.yml` (project snapshot)
   - Contains `demo.json` (demo manifest)
   - Contains `reference_inputs/` (original `.in` files)
   - Contains `reference_outputs/` (if available)

2. **Reports**:
   - `demos/qe_tutorials/import_report.json` - Machine-readable summary
   - `demos/qe_tutorials/import_report.md` - Human-readable summary

## Demo Structure

Each demo snapshot contains:

- **demo.qv.yml**: Complete project snapshot with:
  - Project metadata
  - Structures (as JSON)
  - Calculations with step specs
  - All materialized parameters

- **demo.json**: Demo manifest with:
  - Demo ID and title
  - Description
  - Step list
  - Validation status
  - Pseudopotential list

- **reference_inputs/**: Original QE input files (for reference)

- **reference_outputs/**: Original output files (if available)

## Validation

The tool performs round-trip validation:
1. Parses original QE input
2. Creates step spec from input
3. Generates QE input from step spec
4. Compares original and generated inputs semantically

Validation checks:
- Namelist parameters (excluding structure-related)
- Card data (K_POINTS, ATOMIC_SPECIES, etc.)
- Module detection
- Pseudopotential names

## Error Handling

The tool handles:
- Missing pseudopotentials (reports which ones are missing)
- Parser errors (reports with error details)
- Validation failures (reports differences)
- Subcase datasets (e.g., `14_DFT_plus_U_NiO/1_noU`, `2_addU`)

## Notes

- Demos are **snapshots**: fully materialized projects with explicit parameters
- Demos do **not** depend on workflow/preset implementations
- Pseudopotentials are copied from `pseudo/` into each demo snapshot
- Round-trip validation ensures parameter preservation

