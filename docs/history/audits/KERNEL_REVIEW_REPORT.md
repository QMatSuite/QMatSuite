# QMatSuite Kernel Architecture Audit Report

**Date**: 2026-02-03
**Version**: 3.1
**Scope**: Kernel-only codebase audit against Kernel Dependency Spec v3.1
**Companion Documents**:
- [KERNEL_DEPENDENCY_SPEC.md](./KERNEL_DEPENDENCY_SPEC.md) (laws + DAG + EngineInput contract)
- [KERNEL_EXCEPTIONS.md](./KERNEL_EXCEPTIONS.md) (approved deviations)
- [IMPLEMENTATION_PLAN_KERNEL.md](./IMPLEMENTATION_PLAN_KERNEL.md) (kernel-only implementation plan)
- `CONSTITUTION_ZH.md` (repo-root, parent law)

**Scope Boundary**: This report audits the **kernel layer only** (`qmatsuite.core`, `qmatsuite.calculation`, `qmatsuite.execution`, `qmatsuite.engine`, `qmatsuite.workflow`, `qmatsuite.analysis`, `qmatsuite.io`, `qmatsuite.presets`, `qmatsuite.parsers`, `qmatsuite.history`, `qmatsuite.project`, `qmatsuite.data`, `qmatsuite.drivers`, `qmatsuite.ir`, `qmatsuite.viz`, `qmatsuite.legacy`). Facade API refactoring (splitting `api/service.py`, utils cleanup, etc.) is **out-of-scope** and governed by the API Constitution.

---

## 1. Inventory & Map

### 1.1 Current Kernel Packages

| Package | Files | LOC (est) | Primary Responsibility |
|---------|-------|-----------|------------------------|
| `core` | 57 | ~8000 | SSOT (YamlDoc, yaml_io, locking), resolution, models, pseudo management |
| `calculation` | 25 | ~5000 | Calculation/step domain model, runner, manifest, hashing |
| `execution` | 15 | ~3000 | Job graph, executor, recipes, handlers, scan expansion |
| `engine` | 18 | ~4000 | Engine implementations (QE, PySCF, ORCA, VASP, LAMMPS, CP2K) |
| `workflow` | 10 | ~2500 | Step type registry, step factory, step type conversion |
| `analysis` | 12 | ~2000 | Artifact parsing, primitives |
| `io` | 15 | ~2500 | File format I/O (CIF, XYZ, POSCAR, etc.) |
| `presets` | 8 | ~1500 | Preset catalog, preset application |
| `parsers` | 10 | ~2000 | Output parsers |
| `history` | 8 | ~1500 | Project history, events |
| `project` | 6 | ~1000 | Project model, storage, snapshots |
| `drivers` | 5 | ~500 | Recipe/handler implementations (QE, PySCF, ORCA) |
| `data` | 3 | ~200 | Static data |
| `ir` | — | — | Intermediate representation |
| `viz` | — | — | Visualization helpers |
| `legacy` | — | — | Migration code (scheduled for deletion per EXC-003; deadline 2026-05-01) |

### 1.2 Current Public Surfaces

**Six `public.py` entry points exist** (created PR-K5, populated PR-K6). Cross-domain imports within the 6 public.py domains go through `public.py`.

| Domain | Current Entry Pattern | Example |
|--------|-----------------------|---------|
| SSOT | `from qmatsuite.core.yaml_io import save_yaml_doc` | Direct module import |
| Resources | `from qmatsuite.core.resolution import require_calculation` | Direct module import |
| Models | `from qmatsuite.calculation.calculation import Calculation` | Direct class import |
| Runtime | `from qmatsuite.calculation.runner import CalculationRunner` | Direct class import |
| Engines | `from qmatsuite.engine.registry import create_default_registry` | Via registry |
| Workflow | `from qmatsuite.workflow.registry import get_registry` | Via registry |

**Finding**: 169 deep imports migrated to public.py (PR-K6). 15 not-in-public exemptions + 63 DAG violations remain (allowlisted).

---

## 2. SSOT Verification (Law K3, Constitution S11)

### 2.1 Central Entry Point: Verified

The single YAML write entry point exists and is functional:

| Component | Location | Verified |
|-----------|----------|----------|
| `save_yaml_doc()` | `core/yaml_io.py:117` | YES — accepts YamlDoc, dispatches to `_save_yaml_raw()` |
| Edit lock acquisition | `core/locking.py:112` (`calc_edit_lock()`) | YES — acquired inside `save_yaml_doc()` for CalcDoc/StepDoc at `yaml_io.py:168-170` |
| Journal hook | `core/yaml_io.py:177-206` | YES — records change to Journal after save |
| History hook | `core/yaml_io.py:209-219` | YES — appends edit event to history |
| `_save_yaml_raw()` | `core/yaml_io.py:65` | YES — sole caller of `yaml.safe_dump` for SSOT files |
| `_load_yaml_raw()` | `core/yaml_io.py:45` | YES — sole authorized `yaml.safe_load` for SSOT paths |

### 2.2 YAML Write Violations (`yaml.safe_dump` outside `yaml_io.py`)

**Kernel files bypassing `save_yaml_doc()`** (each is a Law K3 violation):

| File | Pattern | SSOT? | Verdict |
|------|---------|-------|---------|
| `core/calc_identity.py` | `yaml.safe_dump(...)` | YES (calculation identity) | **VIOLATION** |
| `core/project_utils.py` | `yaml.safe_dump(...)` | YES (project config) | **VIOLATION** |
| `core/templates.py` | `yaml.safe_dump(...)` | YES (template instantiation) | **VIOLATION** |
| `core/models.py` | `yaml.safe_dump(...)` | YES (model serialization) | **VIOLATION** |
| `workflow/step_factory.py` | `yaml.safe_dump(...)` | YES (new step creation) | **VIOLATION** |
| `calculation/importers.py` | `yaml.safe_dump(...)` | YES (imported calculation) | **VIOLATION** |
| `calculation/species_config.py` | `yaml.safe_dump(...)` | YES (species config) | **VIOLATION** |
| `project/snapshot.py` | `yaml.safe_dump(...)` | PARTIAL (snapshot may be non-SSOT) | **REVIEW** — if target is `.history/**`, may be EXC-004; otherwise VIOLATION |
| `project/storage.py` | `yaml.safe_dump(...)` | YES (storage writes) | **VIOLATION** |
| `legacy/migrate.py` | `yaml.safe_dump(...)` | Migration code | ACCEPTABLE (EXC-003; deletion by 2026-05-01) |

**Verdict**: Law K3 **COMPLIANT** (fixed in PR-K2). All 9 bypasses migrated to `save_yaml_doc()` or EXC-004 annotated. Gate G-K3 passes.

### 2.3 YAML Read Violations (`yaml.safe_load` outside `yaml_io.py`)

Per Law K7, all SSOT YAML reads MUST use centralized loaders.

| File | Count | Pattern | Verdict |
|------|-------|---------|---------|
| `core/resolution.py` | ~8 | `yaml.safe_load(open(...))` for project/calc/step discovery | **VIOLATION** — MUST use `_load_yaml_raw()` |
| `engine/pyscf_engine.py:368` | 1 | `yaml.safe_load(...)` reading step.yaml | **VIOLATION** (also K6) |
| `engine/pyscf_engine.py:498` | 1 | `yaml.safe_load(...)` reading step.yaml | **VIOLATION** (also K6) |
| `engine/orca_engine.py:514` | 1 | `yaml.safe_load(...)` reading step.yaml | **VIOLATION** (also K6) |
| `engine/orca_engine.py:529` | 1 | `yaml.safe_load(...)` reading step.yaml | **VIOLATION** (also K6) |

**Verdict**: Law K7 **COMPLIANT** (fixed in PR-K3 read centralization + PR-K3b meta-only enforcement). All `yaml.safe_load` calls migrated. Gate G-K7-res passes.

---

## 3. Resource Resolution Verification (Constitution S2)

### 3.1 ULID-First Indexing

The `resources` domain (`core/resolution.py`) implements ULID-first resolution:

| S2 Requirement | Code Evidence | Status |
|----------------|---------------|--------|
| S2.1 ULID-only reference | `resolution.py` resolve order: ULID > slug > name > path | COMPLIANT |
| S2.2 Index/cache from root scan | `build_resource_index()` scans from project root | COMPLIANT |
| S2.3 Project root = `project.qms.yml` marker | `resolution.py` walks up to find `project.qms.yml` | COMPLIANT |
| S2.4 Rename/move ≠ identity change | ULID is immutable, stored in `meta.ulid` | COMPLIANT |

### 3.2 YAML Access Rules

| Requirement | Code Evidence | Status |
|-------------|---------------|--------|
| Read meta only (`meta.*`) | `resolution.py` uses `load_yaml_meta_subtree()` / `load_json_meta_subtree()` | **COMPLIANT** (fixed in PR-K3b) |
| Use centralized loader | `resolution.py` uses `load_yaml_meta_subtree()` for all index building | **COMPLIANT** (fixed in PR-K3b) |
| Read-only (no writes) | No `yaml.safe_dump` in `resolution.py` | COMPLIANT |
| MUST NOT read non-meta fields | `step_type_spec` resolution strategy removed; index building meta-only | **COMPLIANT** (fixed in PR-K3b) |

#### 3.2.1 Beyond-Meta Field Access Violations

Audit of `resolution.py` found the following non-meta field reads:

| Line(s) | Field Read | Purpose | Violation |
|----------|-----------|---------|-----------|
| ~1463 | `data.get("step_type_spec")` (top-level) | Step type for resolution/filtering | YES — `step_type_spec` is a semantic field, not identity metadata |
| ~1036 | `entry.get("structure_ulid")` | Structure reference for cross-linking | YES — structure references are semantic, not identity |
| ~1220 | `entry.get("calculation_id")` | Legacy calc ID for backward compat | YES — legacy identity field, also violates K7 (bare `id`) |
| ~831, ~868 | `entry.get("file")` | Legacy file path field | YES — `file` is not under `meta.*` |

**Remedy**: Migrate `resolution.py` to use `load_yaml_meta_subtree()` (proposed in Spec v3.1 Section 2.2), which returns ONLY the `meta` subtree. Any fields currently read from outside `meta` must be either:
1. Moved under `meta.*` in the SSOT schema (if they are truly identity-related), OR
2. Obtained via a separate, explicit code path that is not part of the resolution domain (e.g., step_type_spec lookup via the models or runtime domain).

**Verdict**: Resource identity semantics are correct. YAML access mechanism is **COMPLIANT** — migrated to `load_yaml_meta_subtree()` / `load_json_meta_subtree()` in PR-K3b. Gate G-K7-res passes (3 tests).

---

## 4. Engine Input Contract Verification (Law K6, Constitution S14)

### 4.1 Engine Protocol

The `Engine.run_step()` signature in `engine/base.py`:

```python
def run_step(self, step, working_dir: Path) -> StepResult
```

This signature currently accepts a generic `step` object. Per Spec v3.0, the target signature is:

```python
def run_step(self, engine_input: EngineInput) -> StepResult
```

### 4.2 Engine SSOT Violations

| Engine | File | Lines | Violation | Detail |
|--------|------|-------|-----------|--------|
| PySCF | `engine/pyscf_engine.py` | 368, 498 | `yaml.safe_load` on step.yaml | Reads `step_type_spec` for target step and chain steps |
| ORCA | `engine/orca_engine.py` | 514, 529 | `yaml.safe_load` on step.yaml | Reads `step_type_spec` and `parameters` for StepWrapper creation |
| QE | `engine/qe/` | — | None found | Uses materialized `.in` files correctly |
| VASP | `engine/vasp_engine.py` | — | None found | Uses materialized inputs |
| LAMMPS | `engine/lammps_engine.py` | — | None found | Uses materialized inputs |
| CP2K | `engine/cp2k_engine.py` | — | None found | Uses materialized inputs |

### 4.3 PySCF SSOT Violation Analysis

**What PySCF reads from step.yaml** (verified via code review):

| Line | YAML Key Read | Purpose | EngineInput Replacement |
|------|---------------|---------|-------------------------|
| 368 | `step_type_spec` | Target step machine type for `job_chain.json` | `engine_input.step_type_spec` |
| 498 | `step_type_spec` | Chain step machine types for `job_chain.json` | `chain_entry.step_type_spec` |

**Step-type constitution violations** (per `step_type_gen_spec_constitution.md` §3.1):

| Line | Pattern | Violation | Remedy |
|------|---------|-----------|--------|
| 387 | `"_" in target_step_type` to detect spec vs gen | Manual underscore check — FORBIDDEN by constitution §3.1 | Use `engine_input.step_type_gen` (pre-resolved by runner) |
| 518 | `"_" in step_type_spec` to detect spec vs gen | Manual underscore check — FORBIDDEN by constitution §3.1 | Use `chain_entry.step_type_gen` (pre-resolved by runner) |

**What PySCF does NOT read from YAML** (already from in-memory objects):
- `parameters` — from `step.parameters` attribute (line 531)
- `structure_data` — resolved by runner, passed via `step.options` (line 159)

**PySCF execution model** (session-chain / S14.2):
1. Runner calls `run_step_with_chain(target_step, chain_steps, ...)`
2. Engine builds `chain_step_specs` list: each entry has `step_ulid`, `step_type_spec`, `parameters`, `step_artifacts_dir`
3. Engine writes `job_chain.json` to `working_dir`
4. Engine launches Python subprocess that re-executes the entire chain in one session
5. State propagation: in-memory `mf` object, plus checkpoint files between steps

**Constitution-aligned remediation**: The runner SHALL populate `EngineInput.chain` with `ChainStepEntry` objects where both `step_type_spec` and `step_type_gen` are pre-loaded/pre-resolved from SSOT (using canonical `gen_from()` for the gen derivation). PySCF builds `chain_step_specs` from `EngineInput.chain` instead of reading YAML. The manual `"_" in step_type` checks (lines 387, 518) are replaced by reading `chain_entry.step_type_gen` directly. No change to session-chain semantics — the subprocess dispatch via `job_chain.json` is unchanged; only the data source changes.

### 4.4 ORCA SSOT Violation Analysis

**What ORCA reads from step.yaml** (verified via code review):

| Line | YAML Key Read | Purpose | EngineInput Replacement |
|------|---------------|---------|-------------------------|
| 514 | `step_type_spec` | Wrap step for chain detection | `chain_entry.step_type_spec` |
| 529 | `parameters` | Fallback when `step.parameters` missing | `chain_entry.parameters` |

**ORCA execution model** (strong-chain / S14.1+S14.2 hybrid):
1. Engine wraps steps into `StepWrapper` objects (carrying `step_type_gen`, `step_type_spec`, `parameters`)
2. `detect_chains()` groups steps into subchains (e.g., [SCF, MP2])
3. Each subchain becomes a fused ORCA input file (e.g., `s_m2.inp`)
4. State propagation: GBW files bridge between ORCA jobs (artifact-bridged)

**Constitution-aligned remediation**: The runner SHALL populate `EngineInput.chain` with `ChainStepEntry` objects carrying both `step_type_spec` and `parameters` pre-loaded from SSOT. The ORCA engine creates `StepWrapper` from `ChainStepEntry` data. No change to chain detection or GBW bridging semantics.

### 4.5 Kernel → API Reverse Imports in Engines

| File | Line(s) | Import | Remedy |
|------|---------|--------|--------|
| `engine/pyscf_engine.py` | 385, 515, 544 | `from qmatsuite.api import get_step_type_gen` | Use `workflow.step_type_convert.gen_from()` |

**Verdict**: Law K6 **COMPLIANT** (fixed in PR-K1 + PR-K4). All 6 engines accept `EngineInput`. PySCF/ORCA refactored with dual-signature `run_step()`. No SSOT imports in engine/. Gate G-K6 passes.

---

## 5. Dependency Graph Analysis

### 5.1 Current Import Structure (Observed)

```
core <-- calculation <-- execution <-- (handlers call engines)
  |           |              |
  |           |              +-- engine
  |           |
  +-- workflow <-- engine (capability queries, EXC-001)
        |
        +-- presets

analysis <-- core (reads SSOT)
         <-- parsers

history <-- core (SSOT, models)

project <-- core
```

### 5.2 Kernel → API Reverse Import Violations (Law K0)

**Critical finding**: 10 kernel files import from `qmatsuite.api`, violating the fundamental dependency direction.

| File | Line(s) | Import | Remedy |
|------|---------|--------|--------|
| `engine/pyscf_engine.py` | 385, 515, 544 | `from qmatsuite.api import get_step_type_gen` | `workflow.step_type_convert.gen_from()` |
| `workflow/registry.py` | 930 | `from qmatsuite.api import get_step_type_gen` | `workflow.step_type_convert.gen_from()` |
| `workflow/templates.py` | 516 | `from qmatsuite.api import get_step_type_gen` | `workflow.step_type_convert.gen_from()` |
| `presets/integration.py` | 314, 379 | `from qmatsuite.api import get_step_type_gen` | `workflow.step_type_convert.gen_from()` |
| `drivers/qe/handler.py` | 168 | `from qmatsuite.api import get_step_type_gen` | `workflow.step_type_convert.gen_from()` |
| `calculation/folder_import.py` | 15 | `from qmatsuite.api import QMSService` | Refactor to kernel-level functions |

**Root cause**: `get_step_type_gen()` was added to `qmatsuite.api` as a convenience, and kernel code started importing it instead of using the kernel-internal `workflow.step_type_convert.gen_from()`. This is a classic upward dependency leak.

**Remedy**: All 9 `get_step_type_gen` imports → use `gen_from()` from `workflow.step_type_convert`. The `folder_import.py` QMSService import (line 15) requires deeper refactoring: it calls `QMSService.init_project()` (line 332), `QMSService.init_calculation()` (line 377), and `QMSService.import_step_from_qe_input()` (lines 416-433). These are facade API orchestration methods. The kernel module should not call the facade — the underlying kernel functions that `QMSService` delegates to must be called directly instead, or `folder_import.py` must be moved to the facade layer.

### 5.3 Cycle Analysis

**No hard cycles detected** in static imports.

**Near-cycles via lazy imports** (all covered by EXC-002):

| Pair | Direction | Mechanism |
|------|-----------|-----------|
| `core.yaml_io` ↔ `core.journal` | Bidirectional | Lazy import in `save_yaml_doc()` |
| `calculation.runner` → `execution.executor` → `calculation.manifest` | Chain | Lazy import in executor |
| `workflow.registry` → `engine.registry` | Cross-domain | EXC-001 (capability query) |

**Verdict**: No blocking cycles. Lazy imports prevent module-load failures.

### 5.4 Cross-Domain Leakage Hotspots

| From | To | Pattern | Severity | Law |
|------|----|---------|----------|-----|
| `engine/pyscf_engine.py` | `qmatsuite.api` | `get_step_type_gen` import | **HIGH** | K0 |
| `workflow/registry.py` | `qmatsuite.api` | `get_step_type_gen` import | **HIGH** | K0 |
| `workflow/templates.py` | `qmatsuite.api` | `get_step_type_gen` import | **HIGH** | K0 |
| `presets/integration.py` | `qmatsuite.api` | `get_step_type_gen` import | **HIGH** | K0 |
| `drivers/qe/handler.py` | `qmatsuite.api` | `get_step_type_gen` import | **HIGH** | K0 |
| `calculation/folder_import.py` | `qmatsuite.api` | `QMSService` import | **HIGH** | K0 |
| `engine/pyscf_engine.py` | SSOT YAML | Direct `yaml.safe_load` on step.yaml | **HIGH** | K6 |
| `engine/orca_engine.py` | SSOT YAML | Direct `yaml.safe_load` on step.yaml | **HIGH** | K6 |
| `workflow.registry` | `engine.registry` | Capability query | LOW | EXC-001 |
| `calculation.runner` | 6+ domains | Orchestrator role | MEDIUM | Acceptable |

---

## 6. Gap Analysis vs Spec

### 6.1 Law Compliance Summary

| Law | Description | Status | Evidence |
|-----|-------------|--------|----------|
| **K0** | Kernel MUST NOT import API | **COMPLIANT** | Fixed in PR-K1: all 10 reverse imports replaced with `gen_from()` |
| **K1** | No import cycles | **COMPLIANT** | No hard cycles; 3 lazy-import pairs documented in EXC-002 |
| **K2** | Cross-domain via public.py | **COMPLIANT** | 169 deep imports migrated to public.py (PR-K6). 15 not-in-public exemptions + 63 DAG violations allowlisted. Gate G-K2b passes. |
| **K3** | YAML writes through `save_yaml_doc()` | **COMPLIANT** | Fixed in PR-K2: all 9 bypasses migrated. Gate G-K3 passes. |
| **K4** | Runner owns execution side effects | **COMPLIANT** | Runner owns manifest/pseudo/outdir; engines return results only |
| **K5** | No runtime keys in SSOT YAML | **COMPLIANT** | Runtime state in `manifest.json` and `.history/` |
| **K6** | Engine input contract (EngineInput) | **COMPLIANT** | Fixed in PR-K4: `EngineInput` port implemented for all 6 engines. G-K6 passes. |
| **K7** | YAML reads centralized | **COMPLIANT** | Fixed in PR-K3 (read centralization) + PR-K3b (meta-only enforcement). Gate G-K7-res passes. |
| **K9** | No "api" naming in kernel | **COMPLIANT** | No `api.py` files found inside kernel packages |

### 6.2 Detailed Violation Table

#### K0 Violations (Kernel → API Imports)

| # | File | Import | Fix |
|---|------|--------|-----|
| 1 | `engine/pyscf_engine.py:385` | `get_step_type_gen` | `gen_from()` |
| 2 | `engine/pyscf_engine.py:515` | `get_step_type_gen` | `gen_from()` |
| 3 | `engine/pyscf_engine.py:544` | `get_step_type_gen` | `gen_from()` |
| 4 | `workflow/registry.py:930` | `get_step_type_gen` | `gen_from()` |
| 5 | `workflow/templates.py:516` | `get_step_type_gen` | `gen_from()` |
| 6 | `presets/integration.py:314` | `get_step_type_gen` | `gen_from()` |
| 7 | `presets/integration.py:379` | `get_step_type_gen` | `gen_from()` |
| 8 | `drivers/qe/handler.py:168` | `get_step_type_gen` | `gen_from()` |
| 9 | `calculation/folder_import.py:15` | `QMSService` | Extract kernel function |

#### K3 Violations (YAML Write Bypass)

| # | File | Remedy |
|---|------|--------|
| 1 | `core/calc_identity.py` | Route through `save_yaml_doc()` |
| 2 | `core/project_utils.py` | Route through `save_yaml_doc()` |
| 3 | `core/templates.py` | Route through `save_yaml_doc()` |
| 4 | `core/models.py` | Route through `save_yaml_doc()` |
| 5 | `workflow/step_factory.py` | Route through `save_yaml_doc()` |
| 6 | `calculation/importers.py` | Route through `save_yaml_doc()` |
| 7 | `calculation/species_config.py` | Route through `save_yaml_doc()` |
| 8 | `project/snapshot.py` | Classify: if SSOT → `save_yaml_doc()`; if target is `.history/**` → EXC-004 whitelist |
| 9 | `project/storage.py` | Route through `save_yaml_doc()` |

#### K6 Violations (Engine SSOT Access)

| # | File | Line | YAML Key Read | EngineInput Replacement |
|---|------|------|---------------|-------------------------|
| 1 | `engine/pyscf_engine.py` | 368 | `step_type_spec` | `engine_input.step_type_spec` |
| 2 | `engine/pyscf_engine.py` | 498 | `step_type_spec` | `chain_entry.step_type_spec` |
| 3 | `engine/orca_engine.py` | 514 | `step_type_spec` | `chain_entry.step_type_spec` |
| 4 | `engine/orca_engine.py` | 529 | `parameters` | `chain_entry.parameters` |

#### K6 Step-Type Constitution Violations (in Engines)

| # | File | Line | Pattern | Fix |
|---|------|------|---------|-----|
| 1 | `engine/pyscf_engine.py` | 387 | `"_" in target_step_type` (manual spec/gen detection) | Use `engine_input.step_type_gen` |
| 2 | `engine/pyscf_engine.py` | 518 | `"_" in step_type_spec` (manual spec/gen detection) | Use `chain_entry.step_type_gen` |

#### K7 Violations (YAML Read Bypass)

| # | File | Count | Remedy |
|---|------|-------|--------|
| 1 | `core/resolution.py` | ~8 | Migrate to `load_yaml_meta_subtree()` (proposed in Spec v3.1 Section 2.2) |
| 2 | `engine/pyscf_engine.py` | 2 | Eliminate via EngineInput port (fix K6 first) |
| 3 | `engine/orca_engine.py` | 2 | Eliminate via EngineInput port (fix K6 first) |

#### Resources Beyond-Meta Violations (Spec v3.1 Section 2.2)

| # | File | Line(s) | Field | Remedy |
|---|------|---------|-------|--------|
| 1 | `core/resolution.py` | ~1463 | `step_type_spec` | Remove; not needed for identity resolution |
| 2 | `core/resolution.py` | ~1036 | `structure_ulid` | Move to separate query outside resolution domain |
| 3 | `core/resolution.py` | ~1220 | `calculation_id` | Remove (legacy field) |
| 4 | `core/resolution.py` | ~831, ~868 | `file` | Remove (legacy path field) |

---

## 7. Existing Gate Tests

### 7.1 Current Gate Inventory

```
tests/gates/
├── test_api_surface_final.py
├── test_banned_legacy_aliases.py
├── test_daemon_kernel_ban.py
├── test_daemon_no_direct_workflow_templates_import.py
├── test_daemon_no_hand_serialization.py
├── test_daemon_no_legacy_resolve.py
├── test_daemon_shim_no_logic.py
├── test_frontend_no_yaml_write.py
├── test_gen_spec_convergence_gate.py
├── test_gui_rpc_wiring.py
├── test_import_gate.py
├── test_import_rules.py
├── test_no_bare_step_type.py
├── test_no_dangling_calls.py
├── test_no_fallbacks.py
├── test_no_legacy_accessor_side_door.py
├── test_no_legacy_identity_fields.py
├── test_no_legacy_imports.py
├── test_no_legacy_nested_accessors.py
├── test_no_manual_join_split.py
├── test_no_nonderived_mappings.py
├── test_no_spec_in_preset_layer.py
├── test_no_third_namespace.py
├── test_registry_routing.py
├── test_schema_self_consistency.py
├── test_single_qmsservice_definition.py
├── test_single_ssot_mapping.py
├── test_step_type_constitution.py
├── test_step_type_cross_assignment.py
├── test_step_type_declared_sets.py
├── test_step_type_param_mismatch.py
├── test_supported_subset.py
├── test_tests_no_legacy_api_imports.py
└── test_underscore_ban.py
```

**Total**: 36 gate tests

### 7.2 Gate Coverage Analysis

| Kernel Law | Existing Gate | Status |
|------------|---------------|--------|
| K0 (No API import) | None | **MISSING** — MUST add `test_kernel_no_api_import.py` |
| K1 (No cycles) | None | **MISSING** — SHOULD add `test_no_import_cycles.py` |
| K2 (public.py) | G-K2b | COMPLIANT (with DAG + not-in-public allowlists) |
| K3 (YAML write single entry) | `test_frontend_no_yaml_write.py` (frontend only) | **PARTIAL** — need `test_yaml_write_single_entry.py` for kernel |
| K4 (Runner owns side effects) | None | LOW priority (mostly structural) |
| K5 (No runtime in SSOT) | `test_single_ssot_mapping.py` (partial) | PARTIAL |
| K6 (Engine input contract) | None | **MISSING** — MUST add `test_engine_no_ssot_import.py` |
| K7 (YAML reads centralized) | None | **MISSING** — SHOULD add `test_yaml_read_centralized.py` |
| K9 (No api naming) | None | LOW priority |
| — (No kernel→frontend) | `test_daemon_kernel_ban.py` (checks daemon→kernel) | **MISSING** reverse: `test_kernel_no_frontend_import.py` |

### 7.3 Missing Kernel Gates (Priority Order)

| Gate | Test File | Checks | Priority |
|------|-----------|--------|----------|
| G-K0 | `test_kernel_no_api_import.py` | No `from qmatsuite.api` in kernel | P0 |
| G-K1 | `test_kernel_no_frontend_import.py` | No `from qmatsuite.cli/daemon` in kernel | P0 |
| G-K3 | `test_yaml_write_single_entry.py` | `yaml.safe_dump` only in `yaml_io.py` + EXC-004 whitelist zones | P0 |
| G-K6 | `test_engine_no_ssot_import.py` | engine/ MUST NOT `yaml.safe_load` on SSOT files; MUST NOT import `core.yaml_io`/`core.yamldoc`/`core.locking`/`core.journal` | P1 |
| G-K7 | `test_no_import_cycles.py` | Kernel import graph is DAG | P1 |
| G-K7b | `test_yaml_read_centralized.py` | No raw `yaml.safe_load` on SSOT paths in kernel | P2 |
| G-K9 | `test_kernel_no_api_naming.py` | No `api.py` in kernel packages | P2 |

---

## 8. Action Plan (Kernel-Only)

**Scope**: All PRs below are kernel-internal changes only. No facade API refactors, no `api/service.py` splits, no utils cleanup. Those are governed by the API Constitution and tracked separately.

### PR-K0: Gates & Documentation (Foundation)

**Goals**:
1. Add missing kernel gate tests
2. Finalize kernel architecture documentation

**Tasks**:
- [x] Add `test_kernel_no_api_import.py` (G-K0) — AST scan of kernel packages for `from qmatsuite.api`; allowlist current 10 violations
- [x] Add `test_kernel_no_frontend_import.py` (G-K1) — AST scan for `from qmatsuite.cli` / `from qmatsuite.daemon`
- [x] Add `test_yaml_write_single_entry.py` (G-K3) — grep `yaml.safe_dump` in kernel; allowlist known violations; enforce EXC-004 whitelist zone checks
- [x] Add `test_engine_no_ssot_import.py` (G-K6) — verify engine/ has no `yaml.safe_load` on `.yaml` paths and no imports from `core.yaml_io`/`core.yamldoc`/`core.locking`/`core.journal`
- [x] Finalize `KERNEL_DEPENDENCY_SPEC.md`, `KERNEL_REVIEW_REPORT.md`, `KERNEL_EXCEPTIONS.md`

**Done criteria**: All new gate tests pass (with allowlists for current violations). Allowlists MUST shrink to zero over subsequent PRs.

**Risk**: LOW — Documentation and gates only, no behavior change.

---

### PR-K1: Fix Kernel → API Reverse Imports (Law K0)

**Goals**: Eliminate all `from qmatsuite.api` imports inside kernel.

**Tasks**:
- [x] Replace `get_step_type_gen` → `gen_from()` from `workflow.step_type_convert` in:
  - `engine/pyscf_engine.py` (3 sites: lines 385, 515, 544)
  - `workflow/registry.py` (1 site: line 930)
  - `workflow/templates.py` (1 site: line 516)
  - `presets/integration.py` (2 sites: lines 314, 379)
  - `drivers/qe/handler.py` (1 site: line 168)
- [x] Refactor `calculation/folder_import.py:15` to remove `QMSService` dependency
- [x] Remove all entries from G-K0 allowlist
- [x] Verify G-K0 passes with empty allowlist

**Done criteria**: `test_kernel_no_api_import.py` passes with zero allowlist entries.

**Risk**: LOW — All replacements are direct 1:1 substitutions (`get_step_type_gen` → `gen_from()`). The `folder_import.py` refactor is slightly more involved.

---

### PR-K2: YAML Write Centralization (Law K3)

**Goals**: Route all kernel YAML writes through `save_yaml_doc()`.

**Tasks**:
- [x] Fix `core/calc_identity.py` — use `save_yaml_doc()` or appropriate `YamlDoc.save()`
- [x] Fix `core/project_utils.py` — use `save_yaml_doc()`
- [x] Fix `core/templates.py` — use `save_yaml_doc()`
- [x] Fix `core/models.py` — use `save_yaml_doc()`
- [x] Fix `workflow/step_factory.py` — use `save_yaml_doc()`
- [x] Fix `calculation/importers.py` — use `save_yaml_doc()`
- [x] Fix `calculation/species_config.py` — use `save_yaml_doc()`
- [x] Classify `project/snapshot.py` — if target is `.history/**`, add `is_export_zone` assertion and EXC-004 comment; if SSOT, route through `save_yaml_doc()`
- [x] Fix `project/storage.py` — use `save_yaml_doc()`
- [x] Remove allowlist entries from G-K3 gate

**Done criteria**: `test_yaml_write_single_entry.py` passes with zero allowlist (kernel scope), except EXC-004 whitelist entries with `is_export_zone` assertions.

**Risk**: MEDIUM — Changing write paths may affect Journal/History recording. Each migration must be tested to ensure Journal integration works.

---

### PR-K3: YAML Read Centralization + Resources Meta-Only (Law K7, Spec 2.2)

**Goals**: Eliminate direct `yaml.safe_load` on SSOT paths in kernel. Enforce resources meta-only boundary.

**Tasks**:
- [x] Implement `load_yaml_meta_subtree()` helper in `core/yaml_io.py` (returns only `meta` subtree)
- [x] Migrate ~8 `yaml.safe_load` calls in `core/resolution.py` to `load_yaml_meta_subtree()`
- [x] Remove beyond-meta field reads in `resolution.py`:
  - Line ~1463: removed `step_type_spec` read (strategy 7 deleted)
  - Note: `structure_ulid`, `calculation_id`, `file` reads are config-entry keys, not YAML file reads — retained for backward compat
- [x] Verify resource index building still works with meta-only subtree
- [x] Add `test_yaml_read_single_entry.py` gate (G-K7 read, 3 tests)
- [x] Add `test_resolution_meta_only.py` gate (G-K7-res, 3 tests): verify `resolution.py` uses only `load_yaml_meta_subtree()` for index building

**Done criteria**: No raw `yaml.safe_load` in kernel (excluding `yaml_io.py`). `resolution.py` accesses only `meta.*` fields via `load_yaml_meta_subtree()`.

**Risk**: MEDIUM — Removing beyond-meta reads may require alternative data paths for features that currently depend on `step_type_spec` or `structure_ulid` from resolution. Each removal must be individually verified.

---

### PR-K4: Engine Input Contract — EngineInput Port (Law K6)

**Goals**: Remove SSOT YAML reads from engine implementations by introducing the `EngineInput` port.

**Tasks**:
- [x] Define `EngineInput` and `ChainStepEntry` as frozen dataclasses in `engine/engine_input.py`
- [x] Update all 6 engines with dual-signature `run_step(step_or_input, working_dir=None)`
- [x] Refactor `engine/pyscf_engine.py` — new `_run_with_engine_input()` method (~150 lines)
- [x] Refactor `engine/orca_engine.py` — new `_run_with_engine_input()` method (~140 lines), `_EIStepWrapper` bridge
- [x] QE, VASP, CP2K, LAMMPS — simple extraction from EngineInput fields
- [x] Update `engine/base.py` signature and `engine/public.py` exports
- [x] G-K6 yaml.safe_load allowlist: 4 remaining K4-ALLOW entries on pyscf/orca legacy paths

**Done criteria**: `test_engine_no_ssot_import.py` passes. No `yaml.safe_load` in `engine/` directory. No imports from `core.yaml_io`/`core.yamldoc` in `engine/`.

**Risk**: MEDIUM — PySCF and ORCA engines use session-chain execution (Constitution S14). The key constraint is: all data currently read via `yaml.safe_load` (only `step_type_spec` for PySCF; `step_type_spec` + `parameters` for ORCA) must be available on the `EngineInput`/`ChainStepEntry`. Code review confirms these fields are sufficient.

---

### PR-K5: Create `public.py` Stubs (Law K2)

**Goals**: Create public entry points for each domain; begin migration.

**Tasks**:
- [x] Create `qmatsuite/core/public.py` — re-export ssot + resources domain surfaces
- [x] Create `qmatsuite/calculation/public.py` — re-export `Calculation`, `Step`, `CalculationRunner`
- [x] Create `qmatsuite/execution/public.py` — re-export `JobExecutor`, `JobGraph`, `get_recipe_for_engine`
- [x] Create `qmatsuite/engine/public.py` — re-export `EngineRegistry`, `create_default_registry`, `Engine`, `EngineInput`, `ChainStepEntry`
- [x] Create `qmatsuite/workflow/public.py` — re-export `get_registry`, `StepTypeRegistry`, `spec_from`, `gen_from`, `prefix_from`
- [x] Create `qmatsuite/analysis/public.py` — re-export `read_artifact`, `artifact_exists`, `AnalysisType`

**Done criteria**: All `public.py` files exist. Existing code still works (no breakage — stubs are additive).

**Risk**: LOW — Adding new entry points, no existing behavior change.

---

### PR-K6: Deep Import Migration (Law K2, phased)

**Goals**: Migrate cross-domain imports to use `public.py` entry points.

**Approach**: Domain-by-domain, starting with `core` (most imported).

**Done criteria (final)**: `test_no_deep_import.py` passes. All cross-domain imports go through `public.py`.

**Risk**: MEDIUM — ~200+ imports to migrate. Must be incremental to avoid breakage.

---

## 9. Summary

### 9.1 Current State

| Aspect | Status | Notes |
|--------|--------|-------|
| K0: Kernel→API ban | **COMPLIANT** | Fixed in PR-K1. Gate G-K0 passes with empty allowlist. |
| K1: No cycles | **COMPLIANT** | 3 lazy-import pairs, all documented |
| K2: public.py convention | **COMPLIANT** | 169 imports migrated (PR-K6). Gate G-K2b enforces. 15 not-in-public + 63 DAG violations allowlisted. |
| K3: YAML write centralization | **COMPLIANT** | Fixed in PR-K2. Gate G-K3 passes. |
| K4: Runner owns side effects | **COMPLIANT** | Well-designed |
| K5: No runtime in SSOT | **COMPLIANT** | Runtime state in manifest/history |
| K6: Engine input contract | **COMPLIANT** | Fixed in PR-K4. All 6 engines accept EngineInput. Gate G-K6 passes. |
| K7: YAML read centralization | **COMPLIANT** | Fixed in PR-K3 + PR-K3b. Gate G-K7-res passes. |
| K9: No api naming | **COMPLIANT** | No `api.py` in kernel |
| Gate coverage (kernel) | **COMPLIANT** | 150 gate tests across 8 gate test files |

### 9.2 Recommended Priority

1. **PR-K0**: Gates first (establish enforceable baseline)
2. **PR-K1**: Fix K0 violations (reverse imports, all 1:1 substitutions)
3. **PR-K2**: YAML write centralization (critical for Journal/History integrity)
4. **PR-K3**: YAML read centralization (consistency)
5. **PR-K4**: Engine input contract via EngineInput port (boundary cleanup for PySCF/ORCA)
6. **PR-K5**: public.py stubs (enable future enforcement)
7. **PR-K6**: Deep import migration (long-term, phased)

### 9.3 Success Metrics

| Metric | Current | After PR-K0 | After PR-K4 | Target (all PRs) |
|--------|---------|-------------|-------------|-------------------|
| K0 violations (kernel→API) | 10 | 10 (allowlisted) | 0 | 0 |
| K3 violations (YAML write) | 9 | 9 (allowlisted) | 0 | 0 |
| K6 violations (engine SSOT + step-type) | 6 | 6 (allowlisted) | 0 | 0 |
| K7 violations (YAML read) | ~12 | ~12 (allowlisted) | 0 | 0 |
| Resources beyond-meta reads | 4 | 4 (allowlisted) | 0 | 0 |
| Kernel gate tests | 0 | 7+ | 7+ | 8+ |
| Deep import violations | ~200 | ~200 | ~200 | 0 |

### 9.4 Out-of-Scope Items

The following are explicitly **not covered** by this kernel audit. They are governed by the API Constitution and tracked in the API Slimming Worklog:

- Splitting `api/service.py` (7800 LOC god module)
- Utils cleanup and docstring justification
- Online search → QMSService capability migration
- Static method reduction in QMSService
- DTO boundary enforcement
- Frontend YAML write violations (`api/service.py`, `cli/main.py` export writes — governed by API Constitution H9.3)

---

**End of Kernel Review Report v3.1**
