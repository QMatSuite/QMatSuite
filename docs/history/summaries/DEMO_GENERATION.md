# Demo Project Generation Guide

This document describes how to generate demo project snapshots in QuantumVITAS.

## Overview

Demo projects are pre-configured QuantumVITAS projects that serve as examples and tutorials. They are stored as snapshot YAML files in `resources/demo_projects/` and can be materialized by users via the GUI or CLI.

## Demo Generation Scripts

There are three scripts for generating demo projects:

### 1. `tools/generate_demo_snapshots.py`

Generates demo snapshots from test example projects in `tests/data/project_examples/`.

**Usage:**
```bash
python tools/generate_demo_snapshots.py
```

**What it does:**
- Exports `tests/data/project_examples/project2_bands` → `resources/demo_projects/si_bands_demo.yml`
- Exports `tests/data/project_examples/project1` → `resources/demo_projects/si_dos_demo.yml`
- Extracts reference artifacts (SCF, DOS, bands JSON files) from calculation results
- Adds demo metadata (title, subtitle, tags, recommended_analysis, difficulty)

**When to run:**
- When test example projects are updated
- To regenerate demo snapshots after changes to snapshot format

### 2. `tools/regenerate_si_bands_demo.py`

A minimal script that only regenerates `si_bands_demo.yml`.

**Usage:**
```bash
python tools/regenerate_si_bands_demo.py
```

**What it does:**
- Exports `tests/data/project_examples/project2_bands` → `resources/demo_projects/si_bands_demo.yml`
- Preserves existing meta section if present

**When to run:**
- Quick regeneration of `si_bands_demo.yml` when `project2_bands` is updated

### 3. `tools/import_tutorial_datasets.py`

Generates demo snapshots from tutorial datasets in `tests/data/` (folders `0_*` through `19_*`).

**Usage:**
```bash
# Normal mode (overwrites existing demos)
python tools/import_tutorial_datasets.py

# Clean mode (deletes existing demos first)
python tools/import_tutorial_datasets.py --clean

# With verification
python tools/import_tutorial_datasets.py --clean --verify
```

**What it does:**
- Scans `tests/data/` for folders matching pattern `0_*` through `19_*`
- For each dataset, finds `.in` files in execution order
- Extracts structure and parameters from inputs
- Maps pseudopotentials from `resources/pseudo/` directory
- Creates calculation structure using QMatSuite APIs
- Validates by round-tripping (parse → export → compare)
- Generates demo snapshots in `resources/demo_projects/` with naming `00_*` to `19_*`
- Extracts reference artifacts from output files (`.scf.json`, `.dos.json`, `.bands.json`)

**Options:**
- `--clean`: Delete existing demos with the same names before generating new ones
- `--verify`: After generation, verify each demo can be loaded and check structure

**When to run:**
- When tutorial datasets in `tests/data/` are updated
- To regenerate all tutorial demos after changes to snapshot format

## Pseudopotential Field Requirements

**Important:** All demo generation scripts must ensure that generated `species_map` entries include the complete triplet:

- `pseudo_basename`: Filename of the pseudopotential
- `pseudo_sha256`: SHA256 hash of the file (strict bytes identity)
- `pseudo_sha_family`: SHA256 hash of whitespace-stripped content (physical equivalence)

**Migration Note:** The old `pseudo_sha_token` field is **not supported** and must **never** appear in generated demos.

The `export_project_to_snapshot()` function (in `src/quantumvitas/project/snapshot.py`) automatically:
- Computes `pseudo_sha256` and `pseudo_sha_family` from files in `project/pseudo/` or `resources/pseudo/`
- Ensures the complete triplet is present before exporting
- Removes any legacy `pseudo_sha_token` fields during materialization

## Demo Snapshot Format

Each demo is a single `.yml` file with the following structure:

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
    structure_id: <ULID>
    species_map:
      <element>:
        mass: <float>
        pseudopot: <filename>
        pseudo_basename: <filename>
        pseudo_sha256: <sha256_hash>
        pseudo_sha_family: <sha_family_hash>
    steps:
      - meta: {id, name, slug, path, kind}
        step_type: <type>
        parameters: {CONTROL: {...}, SYSTEM: {...}, ...}
        cards: {K_POINTS: {...}, ...}
pseudo:
  directory: pseudo
  files: [<pseudo_names>]
meta:
  id: <demo_id>
  title: <title>
  subtitle: <subtitle>
  tags: [...]
  recommended_analysis: <type>
  difficulty: beginner|intermediate|advanced
  reference_artifacts:
    scf: <demo_id>.scf.json
    dos: <demo_id>.dos.json
    bands: <demo_id>.bands.json
```

## Verification

After generating demos, verify they are correct:

```bash
# Check for pseudo_sha_family (should be present)
grep -r "pseudo_sha_family" resources/demo_projects/*.yml

# Check for pseudo_sha_token (should be absent)
grep -r "pseudo_sha_token" resources/demo_projects/*.yml

# Run regression tests
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v
```

## Troubleshooting

### Missing pseudopotentials

If a demo generation fails due to missing pseudopotentials:
1. Check if the pseudo file exists in `resources/pseudo/`
2. If not, the script will attempt to download it (if network access is available)
3. For offline generation, ensure all required pseudos are in `resources/pseudo/` before running

### Incomplete species_map

If generated demos are missing `pseudo_sha256` or `pseudo_sha_family`:
1. Ensure the pseudo file exists in `project/pseudo/` or `resources/pseudo/`
2. Check that `export_project_to_snapshot()` is being called (it handles the computation)
3. Verify the pseudo file is readable and not corrupted

### Legacy pseudo_sha_token in demos

If you find `pseudo_sha_token` in generated demos:
1. This indicates a bug - the field should never be written
2. Check the source project's `calculation.yaml` - it may contain legacy fields
3. The `materialize_project_from_snapshot()` function should remove it, but check `export_project_to_snapshot()` as well

## Related Documentation

- `tools/README_import_tutorials.md` - Detailed documentation for `import_tutorial_datasets.py`
- `docs/SNAPSHOTS.md` - General snapshot format documentation
- `DEMO_SNAPSHOT_PSEUDO_FAMILY_FIX_REPORT.md` - Migration report for pseudo field changes

