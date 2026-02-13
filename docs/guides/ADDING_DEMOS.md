# Adding New Demo Projects

## Step-by-Step

### 1. Create or identify a corpus case

Each demo originates from a corpus case at `tests/inputformat/samples/<engine>/<case_name>/`.

If the case already exists, skip to step 2. Otherwise create:

```
tests/inputformat/samples/<engine>/<case_name>/
    case.yaml      # metadata (required)
    <input_file>   # engine input file(s)
```

### 2. Write case.yaml

Required fields:

```yaml
case_id: <engine>_<case_name>
title: Human-readable title
engine: <engine>
workflow_tags:
- scf          # or relax, bands, dos, md, etc.
species:
- Si           # chemical species involved
functional: PBE
description: Brief description

# Demo store fields
demo_eligible: true
step_type_gen: scf              # from workflow_tags
step_type_spec: <engine>_scf    # engine-prefixed
required_engine: <engine>
availability: open_source       # or requires_local_install
demo_slug: <engine>_<case_name> # globally unique
asset_policy: redistributable   # or proprietary, none
recommended_analysis: scf       # or bands, dos, energy, etc.
```

### 3. Regenerate corpus_index.yaml

```bash
python tools/demo_store/generate_corpus_index.py
```

### 4. Regenerate all demos

```bash
python tools/demo_store/generate_all.py
```

### 5. Run gate tests

```bash
python -m pytest tests/gates/test_corpus_index.py tests/gates/test_demo_generated.py -v
```

### 6. Run full test suite

```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## For Python-Script Engines (GPAW, Psi4, PySCF)

These engines don't have parseable input files. Use `parser_mode: direct_snapshot` in case.yaml with inline parameters and structure:

```yaml
parser_mode: direct_snapshot
inline_parameters:
  functional: B3LYP
  basis: cc-pVDZ
inline_structure:
  species: [O, H, H]
  cart_coords:
  - [0.0, 0.0, 0.1173]
  - [0.0, 0.75695, -0.4692]
  - [0.0, -0.75695, -0.4692]
  charge: 0
  spin_multiplicity: 1
```

## Naming Conventions

- `demo_slug` format: `<engine>_<descriptor>` (e.g., `vasp_si_scf`, `orca_water_sp`)
- Must be globally unique across all engines
- The slug becomes the `.yml` filename: `<slug>.yml`
