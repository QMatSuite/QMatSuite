# Authorship Path (Path B) — Deep Review

**Date:** 2025-02-11
**Scope:** Assess feasibility of implementing Path B (Authoring from scratch)
as defined in DEMO_STORE_SPEC.md Draft v6 §MP.2.

---

## 1. Current Capability Map

### 1.1 API Service Layer (`src/qmatsuite/api/service.py`)

The QMSService class exposes 35+ authoring methods organised in nested domain
classes.  These are the operations needed to build a project from scratch
without loading a snapshot:

| Operation | Method | Line | Granularity |
|-----------|--------|------|-------------|
| Init project | `QMSService.init_project()` | 7416 | Static, creates dirs + project.qms.yml |
| Import structure | `svc.structure.import_file()` | 1527 | Single file, returns StructureDTO |
| Create calculation | `svc.calculation.create()` | 3073 | One calc, binds engine + structure |
| Add step | `svc.calculation.add_step()` | 3955 | One step, accepts gen/spec + params |
| Update step params | `svc.calculation.update_step_params()` | 3271 | Patch semantics via `apply_patch()` |
| Configure species | `svc.calculation.configure_species_map()` | 5234 | Per-calculation pseudo mapping |
| Set structure | `svc.calculation.set_structure()` | — | Change structure reference |
| Run calculation | `svc.run.run_calculation()` | 5294 | Full or incremental run |
| Get analysis | `svc.analysis.get_analysis()` | 1022 | Per-run, per-object-type |

**Core mutation primitive:** `YamlDoc.apply_patch(patch, base_path)` (line 358
in `core/yamldoc.py`).  Delete Semantics A: `None` = delete.  All
`update_step_params` calls funnel through this.

**Snapshot machinery:** `export_project_to_snapshot()` (line 189) and
`materialize_project_from_snapshot()` (line 521) in
`src/qmatsuite/project/snapshot.py`.  The `ProjectSnapshot` dataclass
(line 42) carries `version, project, structures, calculations, pseudo, extra,
meta`.

**Verdict:** The API service layer has **sufficient coverage** to implement
a complete authoring sequence:
`init_project → import_structure → create_calculation → add_step(×N) →
update_step_params(×N) → configure_species → run → analyse`.

### 1.2 Daemon RPC Layer (`src/qmatsuite/daemon/server.py`)

86 `_handle_*` methods routed via `self._handlers` dict (lines 236–401).
The authoring-relevant subset:

| RPC method | Handler | Delegation |
|------------|---------|------------|
| `create_project` | `_handle_create_project` (2071) | `QMSService.init_project()` |
| `import_structure` | `_handle_import_structure` (2109) | `svc.structure.import_file()` |
| `create_calculation` | `_handle_create_calculation` (2824) | `svc.calculation.create()` |
| `add_step_to_calculation` | `_handle_add_step_to_calculation` (4171) | `svc.calculation.add_step()` |
| `update_step_params` | `_handle_update_step_params` (3175) | `svc.calculation.update_step_params()` |
| `set_engine_family` | `_handle_set_engine_family` (1945) | **DIRECT YAML** (see §3.1) |
| `apply_presets_to_calculation` | `_handle_apply_presets_to_calculation` (3879) | **EMBEDDED LOGIC** (see §3.2) |
| `create_demo_project` | `_handle_create_demo_project` (4620) | `QMSService.create_demo_project()` |
| `run_calculation` | `_handle_run_calculation` (5247) | `svc.run.run_calculation()` |

Most handlers are thin wrappers around QMSService.  Two exceptions are
flagged as architectural issues in §3.

### 1.3 CLI Layer (`src/qmatsuite/cli/main.py`)

~40 subcommands covering the full CRUD lifecycle:

| Group | Commands |
|-------|----------|
| **init** | `project`, `calculation`, `step` |
| **import** | `import-structure` |
| **configure** | `step`, `calculation`, `species`, `structure` |
| **rename** | `structure`, `calculation`, `project`, `step` |
| **delete** | `structure`, `calculation`, `step`, `project`, `trash` |
| **run** | `step`, `calculation`, `structure` |
| **save** | `save-project` (export snapshot) |

All CLI commands call QMSService methods.  No direct YAML manipulation.

---

## 2. What Can We Reuse Today?

### 2.1 Test Patterns Already Demonstrating Authorship

Several existing test suites already exercise the exact authoring sequence
that Path B requires:

**`tests/unit/test_api_service.py`** — Most comprehensive:
- `TestQMSServiceProject`: `init_project`, `configure_project`
- `TestQMSServiceStructure`: `import_file`, `list`, `get`, `update_meta`, `delete`
- `TestQMSServiceCalculation`: `init_calculation`, `list`, `get`, `set_structure`, `delete`
- `TestQMSServiceStep`: `add_step`, `list`, `remove_step`

**`tests/unit/test_api_service_steps.py`** — Step configuration:
- `test_add_step_to_calculation_creates_valid_spec`
- `test_add_step_to_calculation_with_defaults`
- `test_configure_step_species_overrides` — uses `update_step_params()`

**`tests/unit/test_api_parameter_scan_persistence.py`** — Scan authoring:
- Demonstrates `update_step_params()` with merge semantics for parameter scans

**`tests/daemon/test_gui_job_and_step_flows.py`** — Full daemon authoring:
- Fixture builds project via API: init → import → create calc → add step
- Tests job submission and step detail retrieval through daemon RPC

**`tests/daemon/test_gui_calculation_detail.py`** — Multi-step authoring:
- Creates project with two structures, calculation, SCF + NSCF steps
- Tests calculation detail retrieval and structure change via daemon

**`tests/daemon/test_promote_relax_structure.py`** — Post-run authoring:
- Promote relaxed structure to new resource

**`tests/utils/calculation_projects.py`** — Helper:
- `create_calculation_project()` — programmatic scaffolding (lower-level
  than QMSService, writes YAML directly for test speed)

### 2.2 Reuse Assessment

| Component | Reusable for Path B? | Notes |
|-----------|---------------------|-------|
| `QMSService.*` methods | **YES — directly** | All authoring ops exist |
| `YamlDoc.apply_patch()` | **YES** | Core mutation primitive |
| `ProjectSnapshot` export | **YES** | Roundtrip B needs re-snapshot |
| Test patterns in `test_api_service.py` | **YES — as templates** | Copy-adapt for demo-specific sequences |
| `create_calculation_project()` helper | **PARTIAL** | Bypasses QMSService; useful for reference only |
| Daemon RPC handlers | **YES — mostly** | Two exceptions (§3.1, §3.2) |
| `generate_ref_packs_realrun.py` | **YES** | Analysis probe logic reusable as-is |

---

## 3. Gap Analysis — What Breaks if We Force Authorship?

### 3.1 CRITICAL: `set_engine_family` — Second Truth Violation

**Location:** `daemon/server.py:1945–1986`

```python
def _handle_set_engine_family(self, payload):
    from qmatsuite.api.utils import load_calculation, save_calculation
    calc_yaml = calc_dir / "calculation.yaml"
    calc_model = load_calculation(calc_yaml, project_root)
    calc_model.engine_family = engine_family
    save_calculation(calc_model, calc_dir)
```

This handler bypasses QMSService entirely and performs **direct YAML
load/save** via `api.utils` proxies.  This is a "second truth" because:

1. It does not call `svc.calculation.create()` or any service method.
2. It does not flow through `YamlDoc.apply_patch()`.
3. It does not emit provenance/journal entries.
4. If Path B replays an authoring sequence through the daemon, this handler
   is the only way to set `engine_family` on an existing calculation —
   and it operates outside the service contract.

**Impact on Path B:** The `create_calculation` RPC already accepts
`engine_family` as a parameter (delegating to `svc.calculation.create()`).
So for **new** calculations, the violation is avoidable.  But the
standalone `set_engine_family` RPC — used by the GUI when the user switches
engines on an existing calculation — has no QMSService equivalent.

**Fix required:** Add `svc.calculation.set_engine_family(calc_selector,
engine_family)` to QMSService, then refactor the daemon handler to delegate.

### 3.2 MODERATE: `apply_presets_to_calculation` — Embedded Broadcast Logic

**Location:** `daemon/server.py:3879–4040`

This handler contains ~160 lines of embedded logic for:
- Iterating all steps in a calculation directory
- Loading each step's YAML
- Compiling presets per step via `compile_step_preset()`
- Broadcasting parameter patches to each step
- Collecting per-step results

While it does call `svc.calculation.update_step_params()` for each step,
the **orchestration logic** (iteration, compilation, broadcast) lives in
the daemon, not in QMSService.

**Impact on Path B:** If Path B replays preset application, it must either:
(a) call the daemon RPC (coupling to daemon), or (b) duplicate the
broadcast logic.  Neither is clean.

**Fix required:** Extract a `svc.calculation.apply_presets(calc_selector,
presets)` method that encapsulates the broadcast.  The daemon handler
becomes a thin wrapper.

### 3.3 MODERATE: Missing `init_calculation` on QMSService.Calculation

The existing test fixture pattern uses `svc.project.init_calculation()` —
a method on the `Project` nested class that creates a calculation and
returns a CalculationDTO.  The `Calculation` nested class has `create()`
which does the same thing.  These are two entry points for the same
operation, which is fine, but the naming inconsistency may confuse
authoring script authors.

**Impact on Path B:** Minor.  Pick one canonical entry point and document
it.  `svc.calculation.create()` is preferred (domain-correct).

### 3.4 MINOR: No Standalone `set_structure` on Calculation Steps

Steps inherit their structure from the calculation (DAG model).
`svc.calculation.set_structure()` exists for changing the calculation-level
binding.  However, for multi-structure workflows (e.g., NEB with
start/end images), there is no step-level structure override API.

**Impact on Path B:** None for current demos (all single-structure).
Future concern only.

### 3.5 GAP: No Authoring Compiler Exists

Path B requires an "authoring compiler" — a component that takes a Level-2
demo YAML snapshot and emits an ordered sequence of authoring operations
(init project, import structure, create calc, add step, update params, ...).

**This component does not exist.**

The reverse is available: `export_project_to_snapshot()` serializes a
project to a snapshot.  But no `compile_snapshot_to_ops(snapshot) →
list[AuthoringOp]` function exists.

**Impact on Path B:** This is the **primary implementation gap**.
Without it, Path B has no automated replay capability.

### 3.6 GAP: No Roundtrip B Test Harness

The DEMO_STORE_SPEC defines Roundtrip B as:
> Level-2 → compile to authoring ops → replay → re-snapshot →
> semantic diff ≈ original

No test harness exists for this.  The closest is the integrity suite
(`tests/integrity/backend/test_demo_lifecycle.py`), which tests
Roundtrip A (snapshot load → re-snapshot → diff).

**Impact on Path B:** A new test harness is needed.

---

## 4. Route Comparison: API vs Daemon vs CLI

### 4.1 Feature Matrix

| Capability | API Service | Daemon RPC | CLI |
|------------|------------|------------|-----|
| Init project | `init_project()` | `create_project` | `init project` |
| Import structure | `import_file()` | `import_structure` | `import-structure` |
| Create calculation | `create()` | `create_calculation` | `init calculation` |
| Set engine family | `create(engine=...)` | `set_engine_family` ⚠ | `init calculation --engine` |
| Add step | `add_step()` | `add_step_to_calculation` | `init step` |
| Update step params | `update_step_params()` | `update_step_params` | `configure step` |
| Apply presets | — ⚠ | `apply_presets_to_calculation` ⚠ | — |
| Configure species | `configure_species_map()` | `update_calculation_species_map` | `configure species` |
| Run calculation | `run_calculation()` | `run_calculation` | `run calculation` |
| Export snapshot | `export_project_to_snapshot()` | — | `save-project` |

⚠ = architectural concern (see §3)

### 4.2 Route Suitability for Path B

| Criterion | API Service | Daemon RPC | CLI |
|-----------|------------|------------|-----|
| **Completeness** | ★★★★☆ | ★★★★★ | ★★★★☆ |
| **Architectural cleanliness** | ★★★★★ | ★★★☆☆ | ★★★★★ |
| **Testability** | ★★★★★ | ★★★☆☆ | ★★☆☆☆ |
| **Provenance tracking** | ★★★★☆ | ★★★☆☆ | ★★★★☆ |
| **Preset support** | ★★☆☆☆ | ★★★★★ | ★☆☆☆☆ |
| **GUI fidelity** | ★★☆☆☆ | ★★★★★ | ★☆☆☆☆ |

**Recommended route:** API Service (QMSService).

Rationale:
1. All authoring ops exist and are architecturally clean.
2. No daemon process needed → faster tests, no IPC overhead.
3. DTO-based returns are easy to assert on.
4. Two missing capabilities (set engine family, apply presets) should be
   fixed by promoting daemon-embedded logic into QMSService (§3.1, §3.2).
5. CLI adds subprocess overhead and string parsing with no benefit.
6. Daemon adds IPC overhead and inherits the two architectural issues.

---

## 5. Implementation Roadmap

### Phase 0: Prerequisites (fix architectural debt)

| Task | Effort | Blocking? |
|------|--------|-----------|
| Add `svc.calculation.set_engine_family()` | Small | Yes |
| Extract `svc.calculation.apply_presets()` from daemon | Medium | Yes (if demos use presets) |
| Verify `init_calculation` vs `create` naming | Trivial | No |

### Phase 1: Authoring Compiler

Build `compile_snapshot_to_authoring_ops(snapshot: ProjectSnapshot) →
list[AuthoringOp]` that decomposes a Level-2 YAML into an ordered
sequence of QMSService calls.

**AuthoringOp** vocabulary (minimum viable set):

```
InitProject(name)
ImportStructure(file_content, name, format)
CreateCalculation(engine, name, structure_ref)
AddStep(calc_ref, step_type_gen, name, params, cards, species_overrides)
UpdateStepParams(calc_ref, step_ref, patch)
ConfigureSpecies(calc_ref, species_map)
ApplyPresets(calc_ref, presets)       # if applicable
```

Estimated scope: ~200–300 lines.  The snapshot already contains all
information needed; the compiler just needs to emit ops in dependency
order (structures before calculations, calculations before steps).

### Phase 2: Authoring Replay Engine

Build `replay_authoring_ops(ops: list[AuthoringOp], target_dir: Path) →
Path` that executes the op sequence against QMSService.

This is straightforward — each op maps 1:1 to a QMSService call.
~100–150 lines.

### Phase 3: Roundtrip B Test Harness

Build a test harness analogous to the integrity suite:

```python
def test_roundtrip_b(demo_slug):
    # 1. Load Level-2 YAML
    snapshot = load_snapshot(demo_slug)
    # 2. Compile to authoring ops
    ops = compile_snapshot_to_authoring_ops(snapshot)
    # 3. Replay into fresh project
    project_root = replay_authoring_ops(ops, tmp_dir)
    # 4. Re-export snapshot
    new_snapshot = export_project_to_snapshot(project_root)
    # 5. Semantic diff
    diff = canonical_semantic_diff(snapshot, new_snapshot)
    assert diff.is_equivalent()
```

### Phase 4: Real-Run Validation (Path B)

Extend `generate_ref_packs_realrun.py` (or add a parallel tool) that:
1. Compiles each demo to authoring ops
2. Replays into a fresh project
3. Runs the calculation
4. Compares analysis bundles against Path A ref packs

---

## 6. Conclusions

### What works today

- **API Service** has all core authoring operations needed for Path B.
- **Existing tests** already demonstrate the full authoring sequence
  (init → import → create → add step → update params → run).
- **Snapshot export** provides the re-snapshot capability for Roundtrip B.
- **Ref pack generator** provides the real-run validation harness.

### What must be built

1. **Fix two daemon handlers** that bypass QMSService (small, well-scoped).
2. **Authoring compiler** — the primary gap (~300 lines).
3. **Replay engine** — mechanical mapping of ops to API calls (~150 lines).
4. **Roundtrip B test harness** — analogous to existing integrity suite.

### Risk assessment

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Snapshot → ops lossy (info lost in compilation) | Medium | Semantic diff tolerances; iterate on compiler |
| Preset broadcast needs daemon-only logic | High | Extract to QMSService first (Phase 0) |
| ULID non-determinism breaks naive diff | Certain | Already handled: semantic diff ignores ULIDs |
| Multi-step dependency ordering fragile | Low | Snapshot already encodes order via step lists |

### Recommendation

**Implement Path B incrementally:**

1. Start with Phase 0 (fix debt) — can be done independently, improves
   architecture regardless of Path B.
2. Phase 1 (compiler) is the critical new component.  Prototype with
   3–5 simple demos (e.g., `qe_si_scf`, `vasp_si_scf`, `orca_water_sp`)
   before scaling to all 45+ demos.
3. Phases 2–4 are mechanical once the compiler works.

Total estimated effort: **~800 lines of new code**, spread across 4 files.
No changes to kernel, runner, or engine drivers required.
