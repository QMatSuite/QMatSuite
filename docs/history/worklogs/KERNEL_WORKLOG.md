# Kernel Cleanup Worklog

**Governing Documents**:
- [KERNEL_DEPENDENCY_SPEC.md](./KERNEL_DEPENDENCY_SPEC.md) v3.1
- [KERNEL_REVIEW_REPORT.md](./KERNEL_REVIEW_REPORT.md) v3.1
- [KERNEL_EXCEPTIONS.md](./KERNEL_EXCEPTIONS.md) v3.1
- [IMPLEMENTATION_PLAN_KERNEL.md](./IMPLEMENTATION_PLAN_KERNEL.md) v1.0

**Test Commands**:
```bash
# Full suite
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile

# Quick gate tests only
python -m pytest tests/gates/ -v --tb=short
```

---

## PR Checklist

- [x] **PR-K0** — Gate Tests (3 new gate test files)
- [x] **PR-K1** — Fix Kernel→API Reverse Imports (zero allowlist for G-K0)
- [x] **PR-K2** — YAML Write Centralization (Law K3)
- [x] **PR-K3** — YAML Read Centralization (Law K7, read side)
- [x] **PR-K4** — Engine Input Contract — EngineInput Port (Law K6)
- [x] **PR-K5** — Create `public.py` Stubs (Law K2)
- [x] **PR-K3b** — Resources Meta-Only Enforcement (Law K7, Spec §2.2)
- [x] **PR-K6** — Deep Import Migration (Law K2)

---

## Completed Work

### PR-K0: Gate Tests
- `tests/gates/test_kernel_no_api_import.py` (G-K0) — AST scan kernel for `from quantumvitas.api`
- `tests/gates/test_kernel_no_frontend_import.py` (G-K1) — AST scan kernel for CLI/daemon imports
- `tests/gates/test_engine_no_ssot_import.py` (G-K6) — Scan engine/ for SSOT imports and yaml.safe_load

### PR-K1: Fix Kernel→API Reverse Imports
- Replaced 8 `get_step_type_gen` → `gen_from()` call sites
- Moved facade function `materialize_project_from_qe_input_folder` from `calculation/folder_import.py` to `api/folder_import.py`
- G-K0 allowlist reduced to 0

### PR-K2: YAML Write Centralization (Law K3)
- Migrated 9 `yaml.safe_dump` call sites to use `save_yaml_doc()` or EXC-004 annotation
- `tests/gates/test_yaml_write_single_entry.py` (G-K3) — 3 tests, all passing
- Gate test enforces: no `yaml.safe_dump` outside `yaml_io.py` except allowlisted EXC-004 sites

### PR-K5: Create `public.py` Stubs (Law K2)
- Created 6 `public.py` entry points: `core`, `calculation`, `execution`, `engine`, `workflow`, `analysis`
- All re-export domain public surfaces per KERNEL_DEPENDENCY_SPEC.md §3.5
- Additive only, no existing imports broken

### PR-K3: YAML Read Centralization (Law K7, read side)
- **Date**: 2026-02-03
- Migrated ~45 `yaml.safe_load` call sites across 22 files to centralized YamlDoc API
- Migration pattern: `yaml.safe_load(path.read_text())` → `CalcDoc.load(path).to_dict()` / `StepDoc.load(path).to_dict()` / `ProjectDoc.load(path).to_dict()` / `load_yaml_doc(path).to_dict()`
- Imports added at function scope to avoid circular dependencies
- Exception annotations added:
  - `project/storage.py:28` — EXC-004 (settings file)
  - `project/snapshot.py:135,162,169` — EXC-004 (in-memory strings from archive)
  - `legacy/migrate.py:139` — EXC-003 (deletion scheduled 2026-05-01)
  - `engine/pyscf_engine.py`, `engine/orca_engine.py` — K4-ALLOW (removed by PR-K4)
- `tests/gates/test_yaml_read_single_entry.py` — NEW gate test, 3 tests
- **Bug fix**: `StepDoc._normalize_sections()` in `yamldoc.py:509` crashed on non-string dict keys (e.g., `{1: 1.0}` for LAMMPS mass params). Added `isinstance(key, str)` guard. Latent bug exposed by migration.
- Files modified (22): `core/resolution.py` (7), `core/templates.py` (3), `core/models.py` (5), `core/project_utils.py` (3), `core/context.py` (3), `core/project_context.py` (1), `core/calc_identity.py` (1), `core/yaml_io.py` (1 internal), `calculation/calculation.py` (3), `calculation/structure_steps.py` (1), `calculation/hash_utils.py` (2), `calculation/wannier90_kpoints.py` (1), `execution/handlers.py` (1), `drivers/qe/handler.py` (1), `project/model.py` (4), `project/snapshot.py` (3 annotations), `project/storage.py` (1 annotation), `workflow/registry.py` (1), `workflow/templates.py` (1), `analysis/artifacts.py` (1), `history/run_revision.py` (1), `presets/capability.py` (1)

### PR-K4: EngineInput Port (Law K6)
- **Date**: 2026-02-03
- Created `engine/engine_input.py` — `EngineInput` and `ChainStepEntry` frozen dataclasses
- Updated all 6 engines with dual-signature `run_step(step_or_input, working_dir=None)`:
  - QE, VASP, CP2K, LAMMPS — simple extraction from EngineInput fields
  - PySCF — new `_run_with_engine_input()` method (~150 lines), uses `chain` for multi-step
  - ORCA — new `_run_with_engine_input()` method (~140 lines), `_EIStepWrapper` bridge class
- Updated `engine/base.py` signature and `engine/public.py` exports
- Updated `test_engine_no_ssot_import.py` allowlist line numbers
- G-K6 yaml.safe_load allowlist: 4 remaining entries (K4-ALLOW on pyscf/orca legacy paths, kept for backward compat during transition)
- Verification: 3030 tests passed, 0 failed

### PR-K3b: Resources Meta-Only Enforcement (Law K7, Spec §2.2)
- **Date**: 2026-02-03
- Created `load_yaml_meta_subtree()` and `load_json_meta_subtree()` in `core/yaml_io.py`
  - Returns ONLY the `meta` (or `__qv_meta__`) subtree from YAML/JSON files
  - Exported from `core/public.py`
- Migrated `build_resource_index()` — 3 sites:
  - `CalcDoc.load(calculation_yaml).to_dict()` → `load_yaml_meta_subtree(calculation_yaml)`
  - `StepDoc.load(step_file).to_dict()` → `load_yaml_meta_subtree(step_file)`
  - `json.loads(struct_file.read_text())` → `load_json_meta_subtree(struct_file)`
- Migrated `resolve_step()` fallback scanning — strategies 4-6 now read from meta subtree only
- **Removed Strategy 7**: `step_type_spec` resolution (beyond-meta semantic field)
- Migrated `_step_path_to_resolved()` — meta-only for identity, full doc only for POST-resolution entry
- Migrated `_calculation_to_resolved()` and `_structure_to_resolved()` — meta-only YAML reads
- `tests/gates/test_resolution_meta_only.py` — NEW gate test (G-K7-res), 3 tests:
  - No full-doc loaders in index building
  - No `step_type_spec` in resolution strategies
  - `build_resource_index()` uses meta-only loaders
- **Bug fix**: `ast.Str` removed in Python 3.12+ — fixed gate tests `test_yaml_read_single_entry.py` and `test_yaml_write_single_entry.py` to use `hasattr(ast, "Str")` guard
- Files modified: `core/yaml_io.py`, `core/public.py`, `core/resolution.py`, `tests/gates/test_resolution_meta_only.py` (new), `tests/gates/test_yaml_read_single_entry.py`, `tests/gates/test_yaml_write_single_entry.py`, `tests/unit/test_resolution.py`
- Verification: 3039 tests passed, 0 failed; 150 gate tests passed

### PR-K6: Deep Import Migration (Law K2)
- **Date**: 2026-02-03
- Expanded all 6 `public.py` entry points with cross-domain symbols:
  - `core/public.py`: ~40 new symbols (resources, models, project_utils, exceptions, driver protocol, structure utils, pseudo). Legacy engine symbols via `__getattr__` lazy loading.
  - `calculation/public.py`: ~7 new symbols (StructureStepSpec, manifest, hash, scan, results). CalculationRunner via lazy loading (breaks analysis cycle).
  - `execution/public.py`: ~9 new symbols (JobResult, Job, SelectionMode, recipes, relax_artifacts, handlers, latest_selector, reference_resolver, preflight)
  - `engine/public.py`: ~3 new symbols (EngineConfig, StepResult, SCF_ROOT_TYPES, RELAX_STEP_TYPES, detect_chains, QeEngine, extract_final_structure)
  - `workflow/public.py`: ~4 new symbols (normalize_step_type_to_gen, generate_subchain_basename, normalize_step_type, get_chain_namespace_folder, is_spec, is_gen)
  - `analysis/public.py`: ~1 new symbol (extract_energy_metrics_from_text)
- Migrated 169 cross-domain deep imports across 43 files to use `public.py`
- Consolidated duplicate `from quantumvitas.<domain>.public import` in 15 files
- Circular import fixes: `core/public.py` lazy-loads structure_canonicalize/structure_fingerprint/legacy engines; `calculation/public.py` lazy-loads CalculationRunner
- Remaining deep imports (15): private symbols not exported via public.py (_find_quantumvitas_root, resolvers, RunManifest, geometry helpers)
- DAG violations (63): deferred to PR-K7 (need code movement)
- `tests/gates/test_no_deep_domain_import.py` — NEW gate test (G-K2b), 2 tests:
  - No cross-domain deep imports bypassing public.py (with DAG + not-in-public allowlists)
  - Staleness check for allowlist entries
- Files modified: 6 public.py files, 43 kernel files (import migration), 1 new gate test
- Verification: 3039 tests passed, 0 failed; 149 gate tests passed (all green)
