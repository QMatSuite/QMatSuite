# OPTIMADE Test Data

This directory contains saved OPTIMADE JSON responses for offline testing.

## Structure

Each file should be named: `{provider}_{material_id}_{date}.json`

Example: `materials_project_mp-149_2024-01-15.json`

## File Format

Each JSON file should contain a complete OPTIMADE structure response:

```json
{
  "data": {
    "type": "structures",
    "id": "...",
    "attributes": {
      "chemical_formula_reduced": "...",
      "nsites": 12,
      "lattice_vectors": [[...], [...], [...]],
      "cartesian_site_positions": [[...], ...],
      "species_at_sites": [...],
      ...
    }
  }
}
```

## Usage

These files are used by `test_optimade_offline.py` to test the online → shared pipeline
without requiring network access.

## Adding New Test Data

1. Fetch structure from OPTIMADE (using test_optimade_online.py or manual fetch)
2. Save raw JSON response to this directory
3. Update test_optimade_offline.py to use the new file
4. Commit the JSON file (it's deterministic test data)

