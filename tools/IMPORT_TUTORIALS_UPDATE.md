# Tutorial Dataset Importer - Updated for resources/demo_projects

## Changes Made

The importer has been updated to generate demos in `resources/demo_projects/` with the same structure as existing demos.

### Key Updates

1. **Output Location**: Changed from `demos/qe_tutorials/` to `resources/demo_projects/`
2. **Naming Convention**: Uses zero-padded numbers `00_*` through `19_*` matching source folder names
3. **Structure Matching**: Generates `.yml` files matching the exact format of existing demos (`si_dos_demo.yml`, `si_bands_demo.yml`)
4. **Reference Artifacts**: Extracts reference JSON files from output directories (`.scf.json`, `.dos.json`, `.bands.json`)
5. **Improved Recognition**: Enhanced step type inference with multiple heuristics
6. **Consistency Verification**: Added verification function to check demo structure consistency

### Demo File Structure

Each demo is a single `.yml` file in `resources/demo_projects/` with:

```yaml
version: 1
project:
  meta:
    id: <ULID>
    name: <demo_name>
    ...
structures:
  - meta: ...
    data: <pymatgen structure>
calculations:
  - meta: ...
    steps:
      - meta: ...
        step_type: <type>
        parameters: ...
        cards: ...
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

### Naming Convention

- `00_Si_scf.yml` - from `tests/data/0_Si_scf/`
- `04_Si_DOS.yml` - from `tests/data/4_Si_DOS/`
- `14_DFT_plus_U_NiO__1_noU.yml` - from `tests/data/14_DFT_plus_U_NiO/1_noU/`
- `14_DFT_plus_U_NiO__2_addU.yml` - from `tests/data/14_DFT_plus_U_NiO/2_addU/`

### Improved Recognition

The `infer_step_type_improved()` function uses multiple heuristics:

1. **Module Detection**: Uses QE module (PW, DOS, BANDS, etc.)
2. **CONTROL.calculation**: Reads explicit calculation type
3. **K_POINTS Analysis**: Detects k-path formats (crystal_b, tpiba) for bands
4. **Filename Patterns**: Checks filename for keywords (bands, relax, etc.)
5. **Card Presence**: Analyzes card types and options

### Reference Artifacts

The importer extracts reference artifacts from `reference_out/` directories:

- **SCF artifacts**: Parses `.out` files using `parse_scf_output()`
- **DOS artifacts**: Looks for `.dos.dat` files
- **Bands artifacts**: Looks for `.bands.dat` files

Artifacts are saved as JSON files alongside the demo `.yml` file.

### Consistency Verification

The `verify_demo_consistency()` function checks:

- Required sections (version, project, structures, calculations, meta)
- Project metadata structure
- Structure data format
- Calculation and step structure
- Meta section completeness
- Pseudo section format

### Usage

```bash
# From repository root
python tools/import_tutorial_datasets.py
```

The script will:
1. Discover all datasets in `tests/data/`
2. Generate demo `.yml` files in `resources/demo_projects/`
3. Extract reference artifacts (if available)
4. Verify consistency of generated demos
5. Generate reports (`import_report.json` and `import_report.md`)

### Reports

- **import_report.json**: Machine-readable summary with:
  - Total datasets discovered
  - Success/failure counts
  - Per-demo details (validation, verification, artifacts)
  
- **import_report.md**: Human-readable summary with:
  - Overview statistics
  - Successful imports with details
  - Failed imports with reasons

### Verification Results

Each successful demo is verified for consistency. The report includes:
- Consistency status (✓ or ✗)
- List of issues (if any)
- Validation results (round-trip)
- Reference artifacts extracted

