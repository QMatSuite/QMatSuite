# Snapshots: Template with Fresh IDs (Option B)

## Overview

Snapshots in QuantumVITAS are **templates**, not bit-for-bit backups. When a snapshot is materialized (imported), all ULIDs are regenerated, preserving the graph structure but creating a new independent project with distinct identifiers.

## Behavior

### Export (`export_project_to_snapshot`)

- Preserves all `id` and `*_id` fields as recorded in the original project
- Exports complete resource graph with all cross-references (`structure_id` in calculations, `step_id` in calculation steps)
- Snapshot contains the full graph structure with original ULIDs

### Materialize (`materialize_project_from_snapshot`)

- **Always regenerates new ULIDs** for all resources (project, calculations, structures, steps)
- Builds an internal mapping (`old_id → new_id`) during materialization
- Rewrites all `*_id` cross-references using the mapping to maintain graph structure
- Snapshot IDs are used **only as a template graph** - they do not survive materialization
- Names, slugs, and logical relationships (which calculation uses which structure/steps) are preserved

## Key Implications

✅ **Multiple projects from same snapshot are independent** - Each materialization creates a new project with unique ULIDs  
✅ **Graph structure is preserved** - Relationships between resources are maintained  
❌ **Snapshots are NOT bit-for-bit backups** - Original ULIDs are not preserved  
❌ **Original ULIDs are NOT preserved** - Cannot use snapshot ULIDs for identification after materialization

## Demo/Reference Features

Demo and reference analysis features do **NOT** depend on preserving snapshot ULIDs:

- **Demo recognition**: Uses `origin.kind == "demo"` and `origin.demo_id` (stable string identifier)
- **Reference analysis**: Uses `origin.reference_artifacts` or `snapshot.meta.reference_artifacts` (stable filenames)
- All lookups use stable identifiers that survive materialization

## Verification

The snapshot ID regeneration behavior is verified by:
- `tests/unit/test_snapshot_id_regeneration.py` - Explicitly tests that all IDs are regenerated and graph structure is preserved

## Historical Note

An earlier design document (`SNAPSHOT_OPTION_A_AUDIT.md`) describes "Option A" (preserve ULIDs) as a desired feature, but this was never implemented. The current implementation uses **Option B** (regenerate ULIDs) as described in this document.
