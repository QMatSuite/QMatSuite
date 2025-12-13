# Schema Refactor Plan: DAG + ID-only References

## Current Schema Analysis

### 1. project.qv.yml (CURRENT - has duplication)
```yaml
project:
  meta: { id, name, slug, path, kind }
  settings: {}
calculations:
  - name: "Si dos"           # ❌ Duplicated from calculation.yaml
    path: "calculations/si-dos" # ❌ Duplicated from calculation.yaml
    meta: { id, name, slug, path, kind }  # ❌ Full meta duplication
structures:
  - name: "Si"               # ❌ Duplicated from structure.json
    file: "structures/si.json"  # ❌ Path duplication
    format: json
    meta: { id, name, slug, path, kind }  # ❌ Full meta duplication
```

### 2. calculation.yaml (CURRENT - mostly good)
```yaml
meta: { id, name, slug, path, kind }
structure_id: <ULID>  # ✅ ID-only (good)
steps:
  - step_id: <ULID>   # ✅ ID-only (good)
    type: scf         # ✅ Relationship metadata (good)
```

### 3. step YAML (CURRENT - has parent references)
```yaml
meta: { id, name, slug, path, kind }
structure_id: <ULID>        # ❌ Should NOT be in step (comes from calculation)
parent_calculation_id: <ULID>  # ❌ Should NOT be in step (parent is implicit)
step_type: scf
parameters: {}
```

## Target Schema (DAG + ID-only)

### 1. project.qv.yml (TARGET)
```yaml
project:
  meta: { id, name, slug, path, kind }
  settings: {}
calculations:
  - calculation_id: <ULID>  # ✅ Only ID, no meta duplication
structures:
  - structure_id: <ULID>  # ✅ Only ID, no meta duplication
```

### 2. calculation.yaml (TARGET - already mostly correct)
```yaml
meta: { id, name, slug, path, kind }
structure_id: <ULID>  # ✅ ID-only
steps:
  - step_id: <ULID>   # ✅ ID-only
    type: scf         # ✅ Relationship metadata
```

### 3. step YAML (TARGET)
```yaml
meta: { id, name, slug, path, kind }
step_type: scf
parameters: {}
cards: {}
# ✅ NO structure_id (inherits from calculation)
# ✅ NO parent_calculation_id (parent is implicit)
```

## Implementation Tasks

1. Update `StructureEntry.to_dict()` - write only `structure_id`
2. Update `CalculationEntry.to_dict()` - write only `calculation_id`
3. Update `ProjectModel.to_dict()` - use new entry format
4. Remove `structure_id` and `parent_calculation_id` from `StructureStepSpec.to_dict()`
5. Update init commands to produce new schema
6. Remove standalone step execution paths
7. Update tests to match new schema

