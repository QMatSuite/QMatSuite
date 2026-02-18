# MCP Stage 10: Demo Store — Worklog

**Status**: DONE

## Summary

3 new MCP tools (search_demos, get_demo_results, load_demo) + 1 new QVService method (load_demo_as_calculation). 52 demo snapshots across 13 engines loadable into any project.

## Design Decisions

### Path B: Direct File Materialization (not API reconstruction)

**Decision**: `load_demo_as_calculation()` directly writes structure JSON, calculation.yaml, and step.yaml files — mirroring `materialize_project_from_snapshot()` from `project/snapshot.py`.

**Why NOT the API path (add_step + update_step_params)**:
- `add_step()` only accepts GEN types, requiring spec→gen conversion
- `update_step_params()` may not handle all engine-specific parameter nesting faithfully (QE namelists vs VASP flat dicts vs LAMMPS `_commands` lists vs CP2K nested sections)
- The snapshot materializer already handles all these variations by writing step YAMLs directly via `StructureStepSpec.from_dict()` + `save_yaml_doc()` — proven correct for all 52 demos

**What Path B does**:
1. Load demo YAML (same as `create_demo_project`)
2. Generate new ULIDs for structure, calculation, and each step
3. Write structure JSON with `__qv_meta__` wrapper to `structures/`
4. Create calculation directory with `calculation.yaml` via `CalculationModel` + `save_calculation()`
5. Write each step YAML via `StructureStepSpec.from_dict()` → `StepDoc` → `save_yaml_doc()`
6. Register both structure and calculation in `project.qv.yml` via `save_project()`
7. Create empty `pseudo/` dir if snapshot has pseudo data (resolved at run time)

### Slug Dedup

Both structure and calculation slugs are deduped against existing project resources before writing. Loading the same demo 3× produces `0-si-scf`, `0-si-scf-2`, `0-si-scf-3`.

### Engine Filter in search_demos

`_build_engine_map()` reads `meta.required_engine` from each demo YAML (falling back to `calculations[0].engine_family`). No prefix inference from demo IDs — handles legacy demos like `si_bands_demo` correctly.

## Implementation Log

### Files Created (2)

| File | Description |
|------|-------------|
| `src/quantumvitas/mcp/tools/demo_store.py` | 3 MCP tools: search_demos, get_demo_results, load_demo |
| `tests/mcp/test_stage10.py` | ~190 tests (7 search + 4 ref_pack + 156 all-engine parametrized + 12 basic + 7 meta/repeat + 2 integration) |

### Files Modified (2)

| File | Change |
|------|--------|
| `src/quantumvitas/api/service.py` | Added `load_demo_as_calculation()` instance method after `list_demo_projects()` |
| `src/quantumvitas/mcp/server.py` | Added Stage 10 import: `import quantumvitas.mcp.tools.demo_store` |

## Tool Inventory (Stage 10)

| Tool | Description |
|------|-------------|
| `search_demos(engine, tag, difficulty, query)` | Browse demo catalog with filters (AND logic) |
| `get_demo_results(demo_id, object_type)` | Preview pre-computed ref pack results |
| `load_demo(demo_id, name)` | Load demo into current project (no context switch) |

## Test Results

- Stage 10 tests: 188 passed
- All MCP tests: 325 passed
- Full suite: **5980 passed, 0 failed, 4 skipped**

### Parametrized Coverage (52 demos × 3 tests each)

Every demo snapshot tested for:
1. `test_load_demo_succeeds` — load returns success, has calc_ulid/engine/demo_id
2. `test_load_demo_steps_match_snapshot` — step count matches YAML
3. `test_load_demo_step_yaml_has_parameters` — parameter keys preserved on disk

### Meta Consistency Tests

- `test_meta_ulids_consistent` — calc_ulid in project.qv.yml matches calculation.yaml meta
- `test_structure_meta_consistent` — struct_ulid in project.qv.yml matches structure JSON file
- `test_step_ulids_in_calculation_yaml` — step ULIDs in calculation.yaml match returned ULIDs
- `test_step_yaml_files_exist_on_disk` — each step has a .step.yaml file
- `test_calc_structure_ulid_points_to_loaded_structure` — calculation's structure_ulid matches

### Repeated Load Tests

- `test_load_same_demo_three_times` — 3 loads → 3 unique calc_ulids, struct_ulids, step_ulids
- `test_repeated_load_slugs_unique_on_disk` — no slug collisions on disk

## Deferred Items

- Real QE run of loaded demo → Stage 11
- promote_structure happy path with real QE relax → Stage 11
