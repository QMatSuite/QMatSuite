# GEN vs SPEC Step Type Semantics: Vocabulary Audit

**Date**: 2026-01-29 (Post-Rollback, Strict Convergence)
**Status**: AUDIT COMPLETE - Ready for Mechanical Implementation

---

## NON-NEGOTIABLE LAWS

### Law 1: NO Compatibility, NO Deprecation, NO Legacy Shims, NO Fallbacks

Project is not released. All old keys/aliases MUST become hard errors or be fully removed. Any loader that encounters an old key MUST raise an exception, not silently convert.

### Law 2: NO Aliases

After migration, repo MUST NOT contain alternative field names for the same concept. One name only. Gate tests MUST enforce this with zero-tolerance ripgrep patterns.

### Law 3: Two Step-Type Fields Only

| Canonical Name | Semantic | Where Used |
|----------------|----------|------------|
| `step_type_spec` | SPEC (engine-prefixed, e.g., `"qe_scf"`) | ALL persisted YAML, RPC, execution |
| `step_type_gen` | GEN (engine-agnostic, e.g., `"scf"`) | UI display, feature gating, workflow templates (input), RPC (display) |

**BANNED** (must not exist anywhere after migration):
- `step_type` (ambiguous)
- `type` (as step-type field)
- `public_type`
- `machine_type`
- `id` (as step-type concept)
- `step_type_public`
- Any other alias

### Law 4: YAML is SSOT and MUST be SPEC-Only

**ALL persisted YAML** must contain `step_type_spec` only:
- `calculation.yaml` steps array: `step_type_spec`
- `step.yaml` files: `step_type_spec`
- Demo snapshot YAML: `step_type_spec`

Workflow system may reason in GEN internally, but the moment it serializes to YAML, it MUST write SPEC.

### Law 5: RPC Contract Includes Both

Every step-bearing RPC response MUST include:
```json
{
  "step_type_spec": "qe_scf",
  "step_type_gen": "scf"
}
```

GUI displays `step_type_gen`. Execution uses `step_type_spec`.

### Law 6: Engine Registry is SSOT for Mapping

SPEC↔GEN mapping SSOT is in `src/quantumvitas/workflow/registry.py`. No second mapping table in API/daemon. Daemon calls API facade; API facade delegates to kernel registry.

### Law 7: ULID Identity Fields

All identity fields for resources (project, calculation, step, structure, job, run, event) MUST use `ulid` or `*_ulid` naming:
- `meta.id` → `meta.ulid`
- `step_id` → `step_ulid`
- `calc_id` → `calc_ulid`
- `job_id` → `job_ulid`
- `structure_id` → `structure_ulid`
- `project_id` → `project_ulid`
- `run_id` → `run_ulid`
- `event_id` → `event_ulid`

Protocol-level request IDs (JSON-RPC `"id"`) are NOT targeted.

---

## Part 1: Identity Field Audit (ULID Renames)

### 1.1 Fields That MUST Be Renamed to `*_ulid`

| Current Name | New Name | File | Line(s) | Context |
|--------------|----------|------|---------|---------|
| `meta.id` | `meta.ulid` | `workflow/step_factory.py` | 68 | Step YAML meta block |
| `meta.id` | `meta.ulid` | All YAML files | various | calculation.yaml, step.yaml, structure.yaml |
| `step_id` | `step_ulid` | `core/models.py` | 81 | CalculationStepEntry |
| `step_id` | `step_ulid` | `api/types/calculation.py` | 51,105 | API types |
| `step_id` | `step_ulid` | `api/types/run.py` | 29 | Run types |
| `step_id` | `step_ulid` | `history/storage.py` | 423,434,442,448,461 | Pin storage |
| `step_id` | `step_ulid` | `history/digests.py` | 95,142 | Digest dataclass |
| `step_id` | `step_ulid` | `engine/orca_engine.py` | 29,413,600 | OrcaResult |
| `calc_id` | `calc_ulid` | `history/storage.py` | 204,217,246,383,390,398 | Event filtering |
| `calc_id` | `calc_ulid` | `api/types/calculation.py` | various | DTO |
| `structure_id` | `structure_ulid` | `engine/vasp_engine.py` | 71-76 | Structure resolution |
| `structure_id` | `structure_ulid` | `engine/orca_engine.py` | 190,194,203,425,438,455,474 | Structure loading |
| `structure_id` | `structure_ulid` | `engine/pyscf_engine.py` | 175,179,198,314,395,400,421 | Structure loading |
| `structure_id` | `structure_ulid` | `engine/lammps_engine.py` | 146,238-243 | Structure loading |
| `structure_id` | `structure_ulid` | `engine/cp2k_engine.py` | 114,128-133 | Structure loading |
| `structure_id` | `structure_ulid` | `core/models.py` | various | Calculation model |
| `project_id` | `project_ulid` | `history/storage.py` | 150,155 | Project storage |
| `job_id` | `job_ulid` | `execution/job_graph.py` | various | Job identity |
| `run_id` | `run_ulid` | `history/storage.py` | 442 | Run identity |

### 1.2 Fields NOT Targeted (Protocol/Unrelated)

| Field | File | Reason |
|-------|------|--------|
| JSON-RPC `"id"` | `daemon/server.py` | Protocol request ID, not resource identity |
| `Job.id` (internal) | `execution/job_graph.py` | Internal job identifier (rename to `job_ulid` if exposed) |
| `StepTypeSpec.id` | `workflow/registry.py:42` | GEN step type, NOT identity (rename to eliminate) |

---

## Part 2: Step-Type Field Audit (Canonical Renames)

### 2.1 Fields That MUST Be Renamed

| Current Name | Location | Line(s) | Current Semantic | Rename To |
|--------------|----------|---------|------------------|-----------|
| `StepTypeSpec.id` | `workflow/registry.py` | 42 | GEN | DELETE (redundant with public_type) |
| `StepTypeSpec.machine_type` | `workflow/registry.py` | 43 | SPEC | `step_type_spec` (field name) |
| `StepTypeSpec.public_type` | `workflow/registry.py` | 44 | GEN | `step_type_gen` (field name) |
| `CalculationStepEntry.type` | `core/models.py` | 82 | GEN | `step_type_spec` (YAML must be SPEC) |
| `CalculationStepEntry.step_type` | `core/models.py` | 89-95 | Property → GEN | DELETE property |
| `Step.step_type` | `calculation/step.py` | ~29 | SPEC (from YAML) | `step_type_spec` |
| `"step_type"` key | `workflow/step_factory.py` | 73 | SPEC | `"step_type_spec"` |
| `"type"` key in calc.yaml | `core/models.py` | 108-109,174 | GEN | `"step_type_spec"` (YAML = SPEC) |
| `spec.public_type` usage | 32+ files | various | GEN | `spec.step_type_gen` |
| `spec.machine_type` usage | 15+ files | various | SPEC | `spec.step_type_spec` |

### 2.2 RPC/DTO Field Renames

| Current Name | File | Line(s) | Rename To |
|--------------|------|---------|-----------|
| `StepInfo.type` | `gui/src/types/qv.ts` | ~196 | DELETE, add `step_type_spec` + `step_type_gen` |
| `StepInfo.id` | `gui/src/types/qv.ts` | ~195 | `ulid` |
| `StepDetail.step_type` | `gui/src/types/qv.ts` | ~420 | `step_type_spec` + add `step_type_gen` |
| `StepDetail.id` | `gui/src/types/qv.ts` | ~418 | `ulid` |
| `step["type"]` | `daemon/compat.py` | 228,432,530,717,772 | `step["step_type_spec"]` + add `step_type_gen` |
| `response["step_type"]` | `daemon/compat.py` | 924 | `response["step_type_spec"]` + add `step_type_gen` |

### 2.3 Daemon Second-Truth Table (MUST DELETE)

| Item | File | Line(s) | Action |
|------|------|---------|--------|
| `_map_step_type_to_v0` function | `daemon/compat.py` | 199-214 | DELETE entirely |
| `TYPE_MAP` dict | `daemon/compat.py` | 202-213 | DELETE entirely |
| All calls to `_map_step_type_to_v0` | `daemon/compat.py` | 228,432,530,717,772,924 | Replace with API facade |

---

## Part 3: SPEC↔GEN Mapping SSOT

### 3.1 Canonical Location

**File**: `src/quantumvitas/workflow/registry.py`

| Component | Line | Purpose |
|-----------|------|---------|
| `_STEP_TYPES` dict | 166-626 | Maps SPEC → StepTypeSpec (66 step types) |
| `StepTypeRegistry.get()` | 662-686 | Lookup by SPEC or GEN |
| `normalize_step_type_to_public()` | 890-913 | SPEC → GEN conversion |
| `StepTypeRegistry._machine_to_spec` | 658 | SPEC → StepTypeSpec |
| `StepTypeRegistry._public_to_machine` | 655 | GEN → SPEC |

### 3.2 Functions to Use (Existing)

**SPEC → GEN**:
```python
from quantumvitas.workflow.registry import normalize_step_type_to_public
gen = normalize_step_type_to_public("qe_scf")  # Returns "scf"
```

**GEN → SPEC** (requires engine context):
```python
from quantumvitas.workflow.registry import get_registry
registry = get_registry()
spec = registry.get_for_engine("scf", "qe")
spec_type = spec.machine_type  # Returns "qe_scf"
```

### 3.3 API Facade (Required for Daemon)

Daemon MUST NOT import kernel. Add to `src/quantumvitas/api/__init__.py`:

```python
def get_step_type_gen(step_type_spec: str) -> str:
    """Convert SPEC to GEN. Thin facade over registry SSOT."""
    from quantumvitas.workflow.registry import normalize_step_type_to_public
    return normalize_step_type_to_public(step_type_spec)
```

---

## Part 4: Golden Fixtures & Demo Projects

### 4.1 Golden Fixture Keys to Rename

| File Pattern | Current Key | New Key |
|--------------|-------------|---------|
| `tests/fixtures/golden_*/daemon/*.json` | `"type"` | `"step_type_spec"` + add `"step_type_gen"` |
| `tests/fixtures/golden_*/daemon/*.json` | `"step_type"` | `"step_type_spec"` + add `"step_type_gen"` |
| `tests/fixtures/golden_*/daemon/*.json` | `"id"` (in steps/meta) | `"ulid"` |
| `tests/fixtures/golden_*/daemon/*.json` | `"step_id"` | `"step_ulid"` |

### 4.2 Demo Project Keys to Rename

| File Pattern | Current Key | New Key |
|--------------|-------------|---------|
| `resources/demo_projects/*.yml` | `step_type:` | `step_type_spec:` |
| `resources/demo_projects/*.yml` | `meta.id:` | `meta.ulid:` |

**Note**: Demo `step_type` values are currently GEN (`"scf"`). They MUST be converted to SPEC (`"qe_scf"`) since YAML must be SPEC-only.

---

## Part 5: Complete Canonical Mapping Table

| SPEC (`step_type_spec`) | GEN (`step_type_gen`) | Engine |
|-------------------------|----------------------|--------|
| `qe_scf` | `scf` | QE |
| `qe_nscf` | `nscf` | QE |
| `qe_relax` | `relax` | QE |
| `qe_bands_pw` | `bands_pw` | QE |
| `qe_bands` | `bands` | QE |
| `qe_dos` | `dos` | QE |
| `qe_projwfc` | `projwfc` | QE |
| `qe_md` | `md` | QE |
| `qe_vc_md` | `vcmd` | QE |
| `qe_ph` | `ph` | QE |
| `qe_q2r` | `q2r` | QE |
| `qe_matdyn` | `matdyn` | QE |
| `qe_dynmat` | `dynmat` | QE |
| `qe_pp` | `pp` | QE |
| `qe_pw2wannier90` | `pw2wan` | QE |
| `qe_custom` | `custom` | QE |
| `w90_preproc` | `w90pre` | W90 |
| `w90_run` | `w90` | W90 |
| `pyscf_scf` | `scf` | PySCF |
| `pyscf_mp2` | `mp2` | PySCF |
| `pyscf_td` | `td` | PySCF |
| `pyscf_relax` | `relax` | PySCF |
| `orca_scf` | `scf` | ORCA |
| `orca_hf` | `hf` | ORCA |
| `orca_td` | `td` | ORCA |
| `orca_relax` | `relax` | ORCA |
| `vasp_scf` | `scf` | VASP |
| `vasp_nscf` | `nscf` | VASP |
| `vasp_bands` | `bands` | VASP |
| `vasp_relax` | `relax` | VASP |
| `lammps_relax` | `relax` | LAMMPS |
| `lammps_md` | `md` | LAMMPS |
| `cp2k_scf` | `scf` | CP2K |
| `cp2k_relax` | `relax` | CP2K |
| `cp2k_md` | `md` | CP2K |

---

## Part 6: Files Summary by Rename Category

### Category A: StepTypeSpec Dataclass

| File | Change |
|------|--------|
| `workflow/registry.py:42` | DELETE `id` field |
| `workflow/registry.py:43` | RENAME `machine_type` → `step_type_spec` |
| `workflow/registry.py:44` | RENAME `public_type` → `step_type_gen` |
| All files using `spec.machine_type` | → `spec.step_type_spec` |
| All files using `spec.public_type` | → `spec.step_type_gen` |
| All files using `spec.id` | → DELETE or use `spec.step_type_gen` |

### Category B: YAML Persistence (Models + Factory)

| File | Change |
|------|--------|
| `workflow/step_factory.py:68` | `"id"` → `"ulid"` |
| `workflow/step_factory.py:73` | `"step_type"` → `"step_type_spec"` |
| `core/models.py:81` | `step_id` → `step_ulid` |
| `core/models.py:82` | `type` → `step_type_spec` |
| `core/models.py:88-95` | DELETE `step_type` property |
| `core/models.py:108-109` | `d["type"]` → `d["step_type_spec"]` |
| `core/models.py:162-174` | Update from_dict to use `step_type_spec` |
| `calculation/step.py:~29` | `step_type` → `step_type_spec` |

### Category C: Daemon Compat (RPC Shaping)

| File | Change |
|------|--------|
| `daemon/compat.py:199-214` | DELETE `_map_step_type_to_v0` function entirely |
| `daemon/compat.py:228,432,530,717,772` | Replace `_map_step_type_to_v0` calls with API facade |
| `daemon/compat.py` all shapers | Emit `step_type_spec` + `step_type_gen` |
| `daemon/compat.py` all shapers | Emit `step_ulid` instead of `step_id` |

### Category D: API Facade

| File | Change |
|------|--------|
| `api/__init__.py` | ADD `get_step_type_gen(step_type_spec: str) -> str` |

### Category E: GUI TypeScript

| File | Change |
|------|--------|
| `gui/src/types/qv.ts` StepInfo | `id` → `ulid`, `type` → `step_type_spec` + `step_type_gen` |
| `gui/src/types/qv.ts` StepDetail | `id` → `ulid`, `step_type` → `step_type_spec` + `step_type_gen` |
| All GUI components using `.type` | → `.step_type_gen` (display) |
| All GUI components using `.id` | → `.ulid` |

### Category F: Test Fixtures

| File | Change |
|------|--------|
| `tests/fixtures/golden_*/daemon/*.json` | Patch keys per Part 4.1 |

### Category G: Demo Projects

| File | Change |
|------|--------|
| `resources/demo_projects/*.yml` | `step_type:` → `step_type_spec:` with SPEC values |
| `resources/demo_projects/*.yml` | `meta.id:` → `meta.ulid:` |
