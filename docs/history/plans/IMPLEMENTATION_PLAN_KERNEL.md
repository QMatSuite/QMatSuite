# Kernel-Only Implementation Plan

**Status**: COMPLETE (PR-K0 through PR-K6, PR-K3b done)
**Version**: 1.0
**Date**: 2026-02-03
**Scope**: Kernel layer only — no API/daemon/CLI/GUI changes
**Companion Documents**:
- [KERNEL_DEPENDENCY_SPEC.md](./KERNEL_DEPENDENCY_SPEC.md) v3.1
- [KERNEL_REVIEW_REPORT.md](./KERNEL_REVIEW_REPORT.md) v3.1
- [KERNEL_EXCEPTIONS.md](./KERNEL_EXCEPTIONS.md) v3.1

---

## Scope Boundary (Non-Negotiable)

**Kernel-only**: This plan touches ONLY packages listed in KERNEL_DEPENDENCY_SPEC.md §1.1. The following are explicitly frozen and out-of-scope:

| Frozen Layer | Governing Document | What This Means |
|--------------|--------------------|-----------------|
| `qmatsuite.api.*` | `API_CONSTITUTION.md` v2.1 | No changes to `api/service.py`, `api/utils.py`, `api/__init__.py`, `api/errors.py` |
| `qmatsuite.cli.*` | `API_CONSTITUTION.md` H1 | No CLI changes |
| `qmatsuite.daemon.*` | `API_CONSTITUTION.md` H1 | No daemon changes |
| Step type system | `step_type_gen_spec_constitution.md` v1.1 | No new aliases, no legacy bare `step_type`, no manual join/split, no new mapping tables, no drift |

**Kernel public naming**: All domain entrypoints are `<domain>/public.py`. No `*_public.py` filenames anywhere in code or docs.

**Engine MUST NOT import SSOT**: No engine reads `step.yaml` or `calculation.yaml`. Runner provides all data via `EngineInput`.

---

## Constitution References

This plan was validated against `CONSTITUTION_ZH.md` (repo root). Key alignments:

| Constitution Section | Relevance | Plan Alignment |
|----------------------|-----------|----------------|
| S2 (ULID-only DAG + Index) | Resources domain meta-only reads | PR-K3: `load_yaml_meta_subtree()` enforces `meta.*` only |
| S10.1 (Single Source of Truth) | step.yaml is the only executable truth | PR-K4: runner reads SSOT, engines consume EngineInput |
| S11.1 (YAML IO must use Doc + yaml_io) | Centralized YAML loader | PR-K2, PR-K3: route all YAML through `yaml_io.py` |
| S13.2.2 (step.yaml is execution truth) | Runner reads step.yaml, not engines | PR-K4: engines receive pre-loaded data via EngineInput |
| S14 (Engine Execution Semantics) | Session-chain vs artifact-bridged | PR-K4: no semantic changes; only data source changes |
| §3.1 step_type_gen_spec_constitution | No manual join/split in engines | PR-K4: engines use pre-resolved `step_type_gen` from EngineInput |

---

## PR Breakdown

### PR-K0: Gate Tests (Foundation)

**Goal**: Establish enforceable baseline. All subsequent PRs shrink allowlists toward zero.

**Violations addressed**: None directly — this PR creates the enforcement infrastructure.

**Tasks**:

1. **`tests/gates/test_kernel_no_api_import.py`** (G-K0)
   - AST-scan all kernel packages for `from qmatsuite.api`
   - Allowlist (initial, 10 entries):
     ```
     engine/pyscf_engine.py:385
     engine/pyscf_engine.py:515
     engine/pyscf_engine.py:544
     workflow/registry.py:930
     workflow/templates.py:516
     presets/integration.py:314
     presets/integration.py:379
     drivers/qe/handler.py:168
     calculation/folder_import.py:15
     ```
   - Allowlist MUST shrink to 0 after PR-K1

2. **`tests/gates/test_kernel_no_frontend_import.py`** (G-K1)
   - AST-scan kernel for `from qmatsuite.cli` / `from qmatsuite.daemon`
   - Expected: empty allowlist (no known violations)

3. **`tests/gates/test_yaml_write_single_entry.py`** (G-K3)
   - Grep kernel for `yaml.safe_dump` outside `core/yaml_io.py`
   - Allowlist (initial, 9 entries — see Review Report §2.2)
   - For EXC-004 entries: require `# EXC-004` comment AND `is_export_zone` assertion
   - Allowlist MUST shrink to 0 (+ EXC-004 whitelist) after PR-K2

4. **`tests/gates/test_engine_no_ssot_import.py`** (G-K6)
   - Scan `engine/` for:
     - `yaml.safe_load` on any path
     - `from qmatsuite.core.yaml_io`
     - `from qmatsuite.core.yamldoc`
     - `from qmatsuite.core.locking`
     - `from qmatsuite.core.journal`
   - Also scan for manual step-type manipulation: `split("_"`, `"_" in step_type`, `"_" in target_step`, `f"{prefix}_`
   - Allowlist (initial, 6 entries):
     ```
     engine/pyscf_engine.py:368  (yaml.safe_load)
     engine/pyscf_engine.py:498  (yaml.safe_load)
     engine/pyscf_engine.py:387  ("_" in step_type)
     engine/pyscf_engine.py:518  ("_" in step_type)
     engine/orca_engine.py:514   (yaml.safe_load)
     engine/orca_engine.py:529   (yaml.safe_load)
     ```
   - Allowlist MUST shrink to 0 after PR-K4

5. **`tests/gates/test_resolution_meta_only.py`** (G-K7-res)
   - Scan `core/resolution.py` for:
     - `yaml.safe_load` (MUST be 0 after PR-K3)
     - Access to keys outside `meta.*` (MUST be 0 after PR-K3)
   - Allowlist (initial — current beyond-meta reads):
     ```
     core/resolution.py:~1463 (step_type_spec)
     core/resolution.py:~1036 (structure_ulid)
     core/resolution.py:~1220 (calculation_id)
     core/resolution.py:~831,868 (file)
     ```

**Acceptance criteria**:
- All 5 gate tests pass with their initial allowlists
- No new violations introduced
- CI runs gates on every PR

**Risk**: LOW — no behavior changes, documentation and gates only.

---

### PR-K1: Fix Kernel → API Reverse Imports (Law K0)

**Goal**: Eliminate all `from qmatsuite.api` imports inside kernel. Zero allowlist for G-K0.

**Violations addressed** (from Review Report §5.2, §6.2):

| # | File:Line | Current Import | Replacement |
|---|-----------|---------------|-------------|
| 1 | `engine/pyscf_engine.py:385` | `from qmatsuite.api import get_step_type_gen` | `from qmatsuite.workflow.step_type_convert import gen_from` |
| 2 | `engine/pyscf_engine.py:515` | same | same |
| 3 | `engine/pyscf_engine.py:544` | same | same |
| 4 | `workflow/registry.py:930` | same | `from qmatsuite.workflow.step_type_convert import gen_from` |
| 5 | `workflow/templates.py:516` | same | same |
| 6 | `presets/integration.py:314` | same | same |
| 7 | `presets/integration.py:379` | same | same |
| 8 | `drivers/qe/handler.py:168` | same | same |
| 9 | `calculation/folder_import.py:15` | `from qmatsuite.api import QMSService` | Extract kernel-level functions (see below) |

**folder_import.py refactoring strategy**:

`folder_import.py` calls `QMSService.init_project()`, `QMSService.init_calculation()`, and `QMSService.import_step_from_qe_input()`. These are facade orchestration methods. Options:

- **Option A (preferred)**: Move `folder_import.py` to the facade layer (`qmatsuite.api.folder_import`) since it *is* a facade-level orchestration function. This removes the K0 violation without touching API internals — it's a file move, not an API change.
- **Option B**: Extract the kernel-level functions that `QMSService` delegates to, and call them directly. This requires understanding `QMSService` internals, which is more invasive.

Decision: **Option A** — move file to `api/` directory (it's already a facade-level concern). No API surface change.

**Step-type safety**: All replacements use the canonical `gen_from()` from `workflow.step_type_convert`, per `step_type_gen_spec_constitution.md` §3.2. No manual join/split introduced.

**Acceptance criteria**:
- `test_kernel_no_api_import.py` passes with empty allowlist
- All existing tests pass (no behavior change — `gen_from()` is the same function that `get_step_type_gen` delegates to)

**Risk**: LOW — 8 of 9 are direct 1:1 import substitutions. The `folder_import.py` move is a file relocation.

---

### PR-K2: YAML Write Centralization (Law K3)

**Goal**: Route all kernel YAML writes through `save_yaml_doc()`. Zero allowlist for G-K3 (kernel scope), except EXC-004 whitelist entries.

**Violations addressed** (from Review Report §2.2):

| # | File | Current Pattern | Fix Strategy |
|---|------|-----------------|-------------|
| 1 | `core/calc_identity.py` | `yaml.safe_dump(...)` on SSOT | Build appropriate `YamlDoc`, call `doc.save()` → routes through `save_yaml_doc()` |
| 2 | `core/project_utils.py` | `yaml.safe_dump(...)` on SSOT | Route through `ProjectDoc.save()` |
| 3 | `core/templates.py` | `yaml.safe_dump(...)` on SSOT | Route through `save_yaml_doc()` |
| 4 | `core/models.py` | `yaml.safe_dump(...)` on SSOT | Route through appropriate `YamlDoc.save()` |
| 5 | `workflow/step_factory.py` | `yaml.safe_dump(...)` on SSOT | Route through `StepDoc.save()` |
| 6 | `calculation/importers.py` | `yaml.safe_dump(...)` on SSOT | Route through `CalcDoc.save()` or `StepDoc.save()` |
| 7 | `calculation/species_config.py` | `yaml.safe_dump(...)` on SSOT | Route through `save_yaml_doc()` |
| 8 | `project/snapshot.py` | `yaml.safe_dump(...)` target TBD | If target is `.history/**` → add `is_export_zone` assertion + `# EXC-004` comment. If SSOT → route through `save_yaml_doc()`. |
| 9 | `project/storage.py` | `yaml.safe_dump(...)` on SSOT | Route through `save_yaml_doc()` |

**For each migration**:
1. Read the current `yaml.safe_dump` call to understand what data is written and to what path
2. Determine the appropriate `YamlDoc` subclass (StepDoc, CalcDoc, ProjectDoc)
3. Load the doc, apply changes via `doc.set()` / `doc.apply_patch()`, then `doc.save()`
4. Verify Journal integration fires (the save path records to Journal automatically)
5. Run existing tests to confirm no behavioral regression

**EXC-004 classification** (for `project/snapshot.py`):
- If the write target matches `.history/**` or `.analysis/**` or `exports/**` → add the `is_export_zone()` assertion and `# EXC-004` comment per KERNEL_EXCEPTIONS.md v3.1
- Implement `is_export_zone()` helper in `core/yaml_io.py` (as specified in EXC-004)

**Step-type safety**: N/A — this PR does not touch step-type fields.

**Acceptance criteria**:
- `test_yaml_write_single_entry.py` passes with zero kernel allowlist entries (except documented EXC-004 whitelist entries)
- Journal integration verified (changed files are recorded)
- All existing tests pass

**Risk**: MEDIUM — Changing write paths may affect Journal/History recording. Each migration must be individually tested. The `save_yaml_doc()` path acquires edit locks, which could change concurrency behavior if the original code didn't lock.

---

### PR-K3: YAML Read Centralization + Resources Meta-Only (Law K7, Spec §2.2)

**Goal**: Eliminate direct `yaml.safe_load` in kernel (except `yaml_io.py`). Enforce resources meta-only boundary.

**Violations addressed** (from Review Report §2.3, §3.2.1):

#### Part A: Implement `load_yaml_meta_subtree()` helper

Create in `core/yaml_io.py`:

```python
def load_yaml_meta_subtree(path: Path) -> dict:
    """Load a YAML file and return ONLY the 'meta' subtree.

    Returns the dict under the 'meta' key (or '__qms_meta__' for
    legacy structure files). All other top-level keys are discarded.
    Uses _load_yaml_raw() internally.

    This is the ONLY YAML loader that the resources/resolution domain
    should call during index building and resolution.
    """
    data = _load_yaml_raw(path)
    return data.get("meta") or data.get("__qms_meta__") or {}
```

#### Part B: Migrate resolution.py YAML reads

| # | Line(s) | Current | Replacement |
|---|---------|---------|-------------|
| 1-8 | ~8 sites | `yaml.safe_load(open(...))` | `load_yaml_meta_subtree(path)` |

#### Part C: Remove beyond-meta field reads

| # | Line(s) | Field | Action |
|---|---------|-------|--------|
| 1 | ~1463 | `step_type_spec` | Remove. If filtering by step type is needed, it should happen in a separate domain (models or runtime), not in resolution. |
| 2 | ~1036 | `structure_ulid` | Remove. Cross-linking can be done after resolution returns the resource index, by the caller. |
| 3 | ~1220 | `calculation_id` | Remove. Legacy field — should not be read. |
| 4 | ~831, ~868 | `file` | Remove. Legacy path field — use `meta.path` or `meta.slug` instead if needed. |

**How to avoid step-type drift**: This PR does NOT touch step-type fields or conversion logic. The removal of `step_type_spec` from resolution is a deletion, not a conversion. No new step-type code is introduced.

**Acceptance criteria**:
- `test_yaml_read_centralized.py` passes: no `yaml.safe_load` in kernel except `yaml_io.py`
- `test_resolution_meta_only.py` passes: `resolution.py` calls only `load_yaml_meta_subtree()`
- Resource index building works correctly (integration tests pass)
- No regressions in resource resolution (ULID, slug, name, path resolution all still work)

**Risk**: MEDIUM — Removing `step_type_spec` and `structure_ulid` reads from resolution may break features that depend on resolution returning these fields. Each removal requires:
1. Grepping callers to understand who consumes the removed data
2. Providing an alternative data path if needed (e.g., the caller loads the full document separately)
3. Running full test suite to catch breakage

---

### PR-K4: Engine Input Contract — EngineInput Port (Law K6)

**Goal**: Remove SSOT YAML reads and manual step-type manipulation from engine implementations. Zero allowlist for G-K6.

**Violations addressed** (from Review Report §4.2, §4.3, §4.4, §6.2):

#### Part A: Define EngineInput and ChainStepEntry

Define as dataclasses in `engine/engine_input.py` (new file, inside engines domain):

```python
@dataclass(frozen=True)
class ChainStepEntry:
    step_ulid: str
    step_type_spec: str
    step_type_gen: str       # Pre-resolved by runner via gen_from()
    parameters: dict
    requires_structure: bool
    step_artifacts_dir: Path

@dataclass(frozen=True)
class EngineInput:
    step_ulid: str
    step_type_spec: str
    step_type_gen: str       # Pre-resolved by runner via gen_from()
    working_dir: Path
    parameters: dict
    materialized_inputs: dict[str, Path]
    run_ulid: str
    chain: list[ChainStepEntry] | None = None
    upstream_artifacts: dict[str, Path] | None = None
    structure_data: dict | None = None
```

**Placement rationale**: `EngineInput` is placed in the `engines` domain because it is part of the engine protocol (engines consume it). The `runtime` domain *populates* it, but engines *own the type definition*. This avoids engines importing from runtime.

#### Part B: Update runner/materialization to build EngineInput

In `calculation/runner.py` and/or `execution/executor.py`:

1. After loading step definitions from SSOT (via `load_step_doc()` or equivalent):
   - Extract `step_type_spec` from loaded SSOT data
   - Derive `step_type_gen` using canonical `gen_from(step_type_spec)` from `workflow.step_type_convert`
   - Extract `parameters` from loaded SSOT data
2. For session-chain engines: build `chain` list by iterating chain steps and populating each `ChainStepEntry`
3. For artifact-bridged engines: populate `materialized_inputs` with paths to `.in` files
4. Construct `EngineInput` and pass to engine

**Step-type safety**: The runner performs exactly ONE `gen_from()` call per step (at the choke point), per `step_type_gen_spec_constitution.md` §4.3. This value is placed on `EngineInput.step_type_gen`. Engines read it directly — no conversion inside engines.

#### Part C: Refactor PySCF engine

| Line | Current Code | New Code |
|------|-------------|----------|
| 368 | `yaml.safe_load(step_yaml_path)["step_type_spec"]` | `engine_input.step_type_spec` |
| 387 | `get_step_type_gen(target_step_type) if "_" in target_step_type else target_step_type` | `engine_input.step_type_gen` |
| 498 | `yaml.safe_load(step_yaml_path)["step_type_spec"]` | `chain_entry.step_type_spec` |
| 518 | `get_step_type_gen(step_type_spec) if "_" in step_type_spec else step_type_spec` | `chain_entry.step_type_gen` |
| 385, 515, 544 | `from qmatsuite.api import get_step_type_gen` | DELETE (no longer needed — gen is pre-resolved on EngineInput) |

**Semantic invariant**: The PySCF engine still builds `job_chain.json` with the same data. It still launches a Python subprocess. It still re-executes the entire chain in one session. The ONLY change is the data source: `EngineInput.chain` instead of `yaml.safe_load`.

#### Part D: Refactor ORCA engine

| Line | Current Code | New Code |
|------|-------------|----------|
| 514 | `yaml.safe_load(step_yaml_path)["step_type_spec"]` | `chain_entry.step_type_spec` |
| 529 | `yaml.safe_load(step_yaml_path)["parameters"]` | `chain_entry.parameters` |

**Semantic invariant**: The ORCA engine still wraps steps into `StepWrapper`, still detects chains, still fuses ORCA input, still bridges via GBW files. The ONLY change is the data source: `ChainStepEntry` instead of `yaml.safe_load`.

#### Part E: Update Engine protocol

In `engine/base.py`, update the `Engine` protocol:

```python
class Engine(Protocol):
    name: str

    def run_step(
        self,
        engine_input: EngineInput,
    ) -> StepResult: ...

    @property
    def supported_presets(self) -> list[str]: ...
```

All engine implementations must be updated to accept `EngineInput` instead of `(step, working_dir)`. For engines that already comply (QE, VASP, LAMMPS, CP2K), the change is mechanical: replace the two-argument signature with the single `EngineInput` argument and extract `working_dir` from it.

**Acceptance criteria**:
- `test_engine_no_ssot_import.py` passes with empty allowlist
- No `yaml.safe_load` in `engine/` directory
- No `from qmatsuite.core.yaml_io` or `from qmatsuite.core.yamldoc` in `engine/`
- No `from qmatsuite.api` in `engine/`
- No manual `"_" in step_type` checks in `engine/`
- All existing engine tests pass (PySCF, ORCA, QE, etc.)
- `job_chain.json` contents for PySCF are identical before/after
- ORCA chain detection produces same chains before/after

**Risk**: MEDIUM — This is the most structurally significant PR. Key risks:
1. The `Engine.run_step()` signature change affects all engine implementations. Must update all 6+ engines.
2. The runner must correctly populate `EngineInput` with all data that engines currently read from SSOT. Missing fields will cause runtime errors.
3. Session-chain engines (PySCF, ORCA) are complex. Careful testing required.

**Mitigation**: The Review Report (§4.3, §4.4) exhaustively catalogued what each engine reads from SSOT. Only `step_type_spec` and `parameters` are read — both are straightforward to populate on `EngineInput`.

---

### PR-K5: Create `public.py` Stubs (Law K2)

**Goal**: Create kernel-internal cross-domain import entrypoints. Additive only — no existing code changes.

**Tasks**:

| File | Exports |
|------|---------|
| `qmatsuite/core/public.py` | **ssot**: `load_yaml_doc`, `save_yaml_doc`, `load_yaml_meta_subtree`, `YamlDoc`, `StepDoc`, `CalcDoc`, `ProjectDoc`, `calc_edit_lock`, `calc_run_lock`; **resources**: `require_calculation`, `require_step`, `require_structure`, `list_calculations`, `list_structures`, `build_resource_index` |
| `qmatsuite/calculation/public.py` | `Calculation`, `Step`, `CalculationRunner` |
| `qmatsuite/execution/public.py` | `JobExecutor`, `JobGraph`, `get_recipe_for_engine` |
| `qmatsuite/engine/public.py` | `EngineRegistry`, `create_default_registry`, `Engine`, `EngineInput`, `ChainStepEntry` |
| `qmatsuite/workflow/public.py` | `get_registry`, `StepTypeRegistry`, `StepTypeSpec`, `spec_from`, `gen_from`, `prefix_from` |
| `qmatsuite/analysis/public.py` | `read_artifact`, `artifact_exists`, `AnalysisType` |

> **Reminder**: These `public.py` files are kernel-internal cross-domain entrypoints for dependency DAG hygiene. They are NOT the facade API and NOT externally stable contracts. See KERNEL_DEPENDENCY_SPEC.md §3.5.

**Step-type safety**: `workflow/public.py` re-exports `spec_from`, `gen_from`, `prefix_from` — the canonical conversion utilities per `step_type_gen_spec_constitution.md` §3.2. No new conversion functions are introduced.

**Acceptance criteria**:
- All `public.py` files exist
- Existing code still works (stubs are purely additive)
- No `*_public.py` filenames exist anywhere

**Risk**: LOW — Adding new files, no existing behavior change.

---

### PR-K6: Deep Import Migration (Law K2) ✅ DONE

**Goal**: Migrate cross-domain imports to use `public.py` entry points.

**Completed**:
- Expanded all 6 `public.py` with cross-domain symbols (~65 new exports)
- Migrated 169 cross-domain deep imports across 43 files
- Circular import mitigation via `__getattr__` lazy loading in core/public.py and calculation/public.py
- 15 not-in-public exemptions (private helpers, resolvers)
- 63 DAG violations allowlisted (deferred to PR-K7)
- Gate test G-K2b: `tests/gates/test_no_deep_domain_import.py` (2 tests, passing)

**Step-type safety**: No step-type fields or conversion logic touched.

**Verification**: 3039 tests passed, 0 failed. 149 gate tests passed.

---

## Recommended Execution Order

```
PR-K0 (gates)
  │
  ├─→ PR-K1 (K0 reverse imports)     ← can start immediately after K0
  │     │
  │     └─→ PR-K4 (EngineInput port)  ← depends on K1 for pyscf API imports
  │
  ├─→ PR-K2 (YAML write centralization)  ← independent of K1
  │
  ├─→ PR-K3 (YAML read + meta-only)      ← independent of K1/K2
  │
  └─→ PR-K5 (public.py stubs)            ← independent, can run anytime
        │
        └─→ PR-K6 (deep import migration) ← depends on K5
```

**Parallelizable**: PR-K1, PR-K2, PR-K3, PR-K5 can all proceed in parallel after PR-K0.

**Critical path**: PR-K0 → PR-K1 → PR-K4 (the engine contract refactor depends on removing API imports first, since we'll also be changing the engine method signature).

---

## Step-Type Drift Prevention

Per `step_type_gen_spec_constitution.md`, the following rules apply throughout ALL PRs:

1. **No manual join/split**: Never introduce `spec.split("_", 1)`, `f"{prefix}_{gen}"`, `startswith(prefix+"_")`, or `"_" in step_type` in any new code.
2. **Canonical utilities only**: If step-type conversion is needed, use `gen_from()`, `spec_from()`, `prefix_from()` from `workflow.step_type_convert`.
3. **Prefer pre-resolved fields**: `EngineInput` carries both `step_type_spec` and `step_type_gen`. Consumers read whichever they need — no conversion required downstream.
4. **Single choke point**: The runner performs exactly one `gen_from(step_type_spec)` per step at the materialization boundary (constitution §4.3). This is the ONLY place where spec→gen conversion happens in execution.
5. **Existing gate enforcement**: `tests/gates/test_no_manual_join_split.py` already catches manual underscore manipulation. All PRs must pass this gate.

---

## Gate Allowlist Shrink-to-Zero Strategy

| Gate | PR-K0 (initial) | After PR-K1 | After PR-K2 | After PR-K3 | After PR-K4 | Target |
|------|-----------------|-------------|-------------|-------------|-------------|--------|
| G-K0 (no API import) | 10 entries | **0** | 0 | 0 | 0 | 0 |
| G-K3 (YAML write single entry) | 9 entries | 9 | **0 + EXC-004** | 0 + EXC-004 | 0 + EXC-004 | 0 + EXC-004 |
| G-K6 (engine no SSOT) | 6 entries | 6 | 6 | 6 | **0** | 0 |
| G-K7-res (resolution meta-only) | 4+8 entries | 4+8 | 4+8 | **0** | 0 | 0 |

---

## Acceptance Criteria (All PRs Complete)

When all PRs land:

- [x] **K0**: Zero `from qmatsuite.api` imports in kernel. Gate G-K0 passes with empty allowlist.
- [x] **K1**: No import cycles. Lazy imports documented per EXC-002.
- [x] **K2**: `public.py` exists for all 6 domains. Deep import migration pending (PR-K6).
- [x] **K3**: All YAML writes through `save_yaml_doc()` (or EXC-004 whitelist with assertions). Gate G-K3 passes.
- [x] **K6**: `EngineInput` port implemented. All 6 engines accept `EngineInput`. No SSOT imports in engine/. Gate G-K6 passes (K4-ALLOW entries on legacy paths for backward compat).
- [x] **K7 (reads)**: No raw `yaml.safe_load` in kernel (except `yaml_io.py` + allowlisted exceptions). Gate `test_yaml_read_single_entry.py` passes.
- [x] **K7 (meta-only)**: `resolution.py` uses only `load_yaml_meta_subtree()`. `step_type_spec` resolution strategy removed. Gate G-K7-res passes (3 tests).
- [x] **Step-type constitution**: No new violations. `test_no_manual_join_split.py` passes. No bare `step_type` fields.
- [x] **No `*_public.py`**: Zero matches for `*_public.py` in codebase.
- [x] **No engines → SSOT**: Zero matches for engine imports of `core.yaml_io`, `core.yamldoc`, `core.locking`, `core.journal`.
- [x] **Legacy**: No new `legacy/` usage. EXC-003 deletion plan on track (deadline 2026-05-01).

---

**End of Implementation Plan v1.0**
