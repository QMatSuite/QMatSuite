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
7. Generates demo snapshots in `resources/demo_projects/` with naming `00_*` to `19_*`
8. Extracts reference artifacts from output files (`.scf.json`, `.dos.json`, `.bands.json`)
9. Verifies consistency of generated demos

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

### Options

- `--clean`: Clean mode - delete existing demos with the same names before generating new ones
  - In clean mode: Deletes existing `.yml` files and associated `.json` artifact files first
  - In normal mode (default): Overwrites existing files with the same names

- `--verify`: Verification mode - after generating demos, verify they can be loaded and check their structure
  - Loads each generated demo using `ProjectSnapshot.from_dict()`
  - Verifies required sections (version, project, structures, calculations, meta)
  - Checks metadata structure
  - Validates step specifications
  - Reports structure/calculation/step counts

Example:
```bash
# Normal mode (overwrites existing demos)
python tools/import_tutorial_datasets.py

# Clean mode (deletes existing demos first)
python tools/import_tutorial_datasets.py --clean

# With verification
python tools/import_tutorial_datasets.py --clean --verify
```

## Requirements

- Python 3.8+
- All dependencies from `requirements.txt` installed
- Pseudopotentials available in `pseudo/` directory (missing ones will be automatically downloaded to `repo/pseudo/`)

## Output

The tool creates:

1. **Demo snapshots** in `resources/demo_projects/`:
   - Each demo is a single `.yml` file (e.g., `00_Si_scf.yml`, `04_Si_DOS.yml`)
   - Matches the structure of existing demos (`si_dos_demo.yml`, `si_bands_demo.yml`)
   - Contains complete project snapshot with structures, calculations, steps
   - Includes reference artifacts (`.scf.json`, `.dos.json`, `.bands.json`) if available

2. **Reports**:
   - `resources/demo_projects/import_report.json` - Machine-readable summary
   - `resources/demo_projects/import_report.md` - Human-readable summary

## Demo Structure

Each demo is a single `.yml` file matching the format of existing demos:

```yaml
version: 1
project:
  meta: {id, name, slug, path, kind}
  settings: {}
structures:
  - meta: {id, name, slug, path, kind}
    data: <pymatgen structure>
calculations:
  - meta: {id, name, slug, path, kind}
    mode: normal
    working_dir: raw
    steps:
      - meta: {id, name, slug, path, kind}
        step_type: <type>
        parameters: {CONTROL: {...}, SYSTEM: {...}, ...}
        cards: {K_POINTS: {...}, ...}
        species_overrides: {...}
    structure_id: <ULID>
pseudo:
  directory: pseudo
  files: [<pseudo_names>]
meta:
  id: <demo_id>
  title: <title>
  subtitle: <step_sequence>
  tags: [...]
  recommended_analysis: <type>
  difficulty: beginner
  reference_artifacts:
    scf: <demo_id>.scf.json
    dos: <demo_id>.dos.json
    ...
```

Reference artifacts (if available) are saved as separate JSON files:
- `<demo_id>.scf.json` - SCF analysis data
- `<demo_id>.dos.json` - DOS analysis data
- `<demo_id>.bands.json` - Bands analysis data

## Validation

The tool performs round-trip validation:
1. Parses original QE input
2. Creates step spec from input
3. Generates QE input from step spec
4. Compares original and generated inputs semantically

Validation checks:
- Namelist parameters (excluding structure-related)
- Card data (K_POINTS only - structure cards are excluded)
- Module detection
- Pseudopotential names (extracted to `species_overrides`)

**Important:** Structure-related cards (`ATOMIC_POSITIONS`, `CELL_PARAMETERS`, `ATOMIC_SPECIES`) are **not** stored in steps. They are:
- `ATOMIC_POSITIONS` and `CELL_PARAMETERS`: Stored in the structure JSON file
- `ATOMIC_SPECIES`: Extracted to `species_overrides` in step specs (mass and pseudopotential)

## Error Handling

The tool handles:
- Missing pseudopotentials (reports which ones are missing)
- Parser errors (reports with error details)
- Validation failures (reports differences)
- Subcase datasets (e.g., `14_DFT_plus_U_NiO/1_noU`, `2_addU`)

## Consistency Verification

When using `--verify` flag, each generated demo is verified:
- Demo can be loaded using `ProjectSnapshot.from_dict()`
- Required sections present (version, project, structures, calculations, meta)
- Metadata structure correct
- Step specifications valid (steps have meta, step_type, parameters, cards)
- Pseudo section format correct (directory and files)
- Structure/calculation/step counts are reported

Issues are reported in the summary report and printed to console.

## Structure Separation

**Important Design Principle:** Geometry parameters are stored in the structure section, not in steps.

- **Structure cards** (`ATOMIC_POSITIONS`, `CELL_PARAMETERS`): Stored in structure JSON files
- **Species information** (`ATOMIC_SPECIES`): Extracted to `species_overrides` in step specs
  - Contains: `mass` and `pseudopot` for each species
  - NOT stored as a card in steps
- **Steps** only contain:
  - Calculation-specific parameters (CONTROL, SYSTEM, ELECTRONS, etc.)
  - Non-structure cards (K_POINTS, etc.)

This matches the reference demo format (`si_dos_demo.yml`) and ensures proper separation of concerns.

## Architecture

The importer uses the QVService API to create projects, following the same workflow as manual project creation:

1. **Project Initialization**: `QVService.init_project()` - Creates empty project
2. **Structure Import**: `QVService.import_structure()` - Imports structure from first `.in` file
3. **Calculation Creation**: `QVService.init_calculation()` - Creates calculation with structure
4. **Step Import**: `QVService.import_step_from_qe_input()` - Imports each step sequentially
5. **Snapshot Export**: `export_project_to_snapshot()` - Exports to demo format

This ensures generated demos match the structure of manually created projects.

## Pseudopotential Management

The importer handles pseudopotentials automatically:

1. **During Import**: 
   - Searches for pseudos in dataset folder, `tests/data/`, and `pseudo/` directory
   - If not found, attempts to download from QE repository to `repo/pseudo/`
   - Reports failures if download also fails (404 errors)

2. **During Demo Expansion** (when materializing from snapshot):
   - Copies pseudos from `repo/pseudo/` to `project/pseudo/`
   - Falls back to download if not in repo
   - QE execution always uses `project/pseudo/` as `pseudo_dir`

## Notes

- Demos are **snapshots**: fully materialized projects with explicit parameters
- Demos do **not** depend on workflow/preset implementations
- **Structure separation**: Geometry parameters (ATOMIC_POSITIONS, CELL_PARAMETERS, ATOMIC_SPECIES) are stored in structure section, not in steps
- Steps only contain calculation-specific parameters and cards (K_POINTS, etc.)
- Species information (mass, pseudopotential) is stored in `species_overrides`, not as ATOMIC_SPECIES card
- Pseudopotentials are automatically downloaded if missing
- Round-trip validation ensures parameter preservation
- Naming uses zero-padded numbers (`00_*` through `19_*`) matching source folders
- Reference artifacts are extracted from `reference_out/` directories when available
- Improved step type recognition uses multiple heuristics for better accuracy

