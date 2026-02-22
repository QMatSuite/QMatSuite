# Authorship Path (Path B) Implementation Plan — v4

## Plan Diff Summary (v4 vs v3)

| Area | v3 | v4 (this plan) |
|------|-----|----------------|
| **Terminology** | Used "machine_step_type" in places | Strict: only `step_type_gen` / `step_type_spec` per Step Type GEN/SPEC Constitution |
| **Companion steps** | Not addressed | Defaults spec-keyed: w90/yambo/qmcpack step_type_spec get empty defaults (no QE leak). Gate test added. |
| **add_step fallback** | `registry.get(step_type_gen)` as generic fallback | Hard-banned. Uses `DriverRegistry.resolve_companion_step()` only. No match → hard error. |
| **Fine-grain rule** | "leaf parameters = MUST per-op; lists/tables = one op" | Tightened: MUST = one op per independent scalar leaf; ALLOWED = lists/tables/scripts one op if matches one UI widget submit unit |

All v3 content preserved. Changes are additive/tightening only.

**Governing rule (verbatim):** "One UI widget / one text field / one table row edit = one op."

---

## Context

Path A (load demo snapshot) is working. Path B (authoring from scratch) is the missing
half: prove every Level-2 demo snapshot can be compiled to fine-grained user-like ops,
replayed through QMSService, and the resulting project re-snapshots to semantic equivalence
with the original. This plan covers Phase 0-2 (Phase 3 real-run is deferred).

Two daemon handlers bypass QMSService (second truth). The step default lookup uses
GEN-keyed defaults that leak QE namelists into non-QE engines. Both must be fixed
first (Phase 0) before the authoring IR and replay engine (Phase 1-2) can work.

---

## Phase 0 — Fix Second Truth + Fix Default Resolution

### 0A. Second-Truth Daemon Handlers

**Problem**:
1. `_handle_set_engine_family` (server.py:1945-1986): calls `load_calculation` / `save_calculation` directly.
2. `_handle_apply_presets_to_calculation` (server.py:3879-4040): ~120 lines embedded logic with `yaml.safe_load` at line 3968.

**Changes**:

**`src/qmatsuite/api/service.py`** — Add two methods to Calculation inner class:

1. `set_engine_family(calc_selector, engine_family) -> CalculationDTO`
   - Validate via `validate_engine_family()` (reuse from `api/utils.py:751`)
   - Resolve calc via `require_calculation()`
   - Load model, set `engine_family`, save, return DTO

2. `apply_presets(calc_selector, presets, *, validate_physics=True) -> dict`
   - Move ~120 lines from daemon handler into this method
   - Same return shape: `{status, steps_updated, steps_skipped, step_results, dimension_states}`
   - Reusable by both daemon and CLI (capability mouth per API_CONSTITUTION H1)

**`src/qmatsuite/daemon/server.py`** — Both handlers become 5-line thin wrappers.

**`tests/gates/test_daemon_no_yaml_write.py`** (NEW) — Scans `_handle_*` methods for:
- `yaml.safe_load` (outside dispatch parsing)
- `save_calculation` / `save_yaml_doc` (direct model saves)

### 0B. Fix Default Resolution — No Cross-Engine Fallback

**Problem**: `step_defaults.py:DEFAULT_STEP_PARAMS` keys are GEN types ("scf", "nscf", etc.) containing QE namelist structures (CONTROL, SYSTEM, ELECTRONS). When `create_step_doc("scf", engine_family="vasp")` is called, it looks up `registry.get_defaults("scf")` → returns QE defaults → VASP step gets QE namelists. **This is wrong.**

**Root cause trace** (audit of default resolution path):

```
create_step_doc(step_type_gen="scf", engine_family="vasp")
  → machine_step_type = "vasp_scf"             # line 55-65: spec materialization (correct)
  → defaults = registry.get_defaults("scf")     # line 68: ← BUG: uses GEN, ignores engine
    → get_default_step_params("scf")             # registry.py:1182-1184
      → DEFAULT_STEP_PARAMS.get("scf")           # step_defaults.py:207: returns QE defaults!
  → data["parameters"] = defaults["parameters"]  # line 92: QE namelists injected into VASP step
```

**Fix — spec-keyed defaults (no fallback)**:

1. **`src/qmatsuite/calculation/step_defaults.py`** — Rename all GEN keys to SPEC keys:
   - `"scf"` → `"qe_scf"`
   - `"nscf"` → `"qe_nscf"`
   - `"dos"` → `"qe_dos"`
   - `"bands"` → `"qe_bands"`
   - `"bandspw"` → `"qe_bandspw"`
   - `"relax"` → `"qe_relax"`
   - `"md"` → `"qe_md"`
   - `"pyscf_scf"` stays (already spec-keyed)
   - `"pyscf_mp2"` stays (already spec-keyed)
   - `"mp2"` legacy entry → remove
   - Rename function: `get_default_step_params(step_type_spec: str)` (docstring: accepts SPEC type, no GEN fallback)

2. **`src/qmatsuite/workflow/step_factory.py:68`** — Change:
   ```python
   # Before (line 68):
   defaults = registry.get_defaults(step_type_gen)
   # After: use the already-derived step_type_spec (variable at line 58: machine_step_type)
   defaults = registry.get_defaults(step_type_spec)
   ```
   Note: the local variable `machine_step_type` in `step_factory.py` is a `step_type_spec` value per GEN/SPEC Constitution §2. No rename of the variable is needed (it's local), but in this plan and all new code we use the constitutional name `step_type_spec`.

3. **`src/qmatsuite/workflow/registry.py:1170-1184`** — Rename `get_defaults(step_type_gen)` to `get_defaults(step_type_spec)`. Update docstring.

4. **Callers that pass GEN type — update to pass SPEC type**:
   - `cli/main.py:1227`: CLI has engine context → construct `step_type_spec` via `spec_from(engine, gen)` (canonical derivation per §3)
   - `importers.py:75`: Always QE → use `spec_from("qe", step_type_gen)`
   - `frontends/cli/app.py:1143`: Has engine context → construct `step_type_spec`
   - `service.py:7597-7611`: Static wrapper → accept `step_type_spec`, update docstring
   - `service.py:4819`: Already uses `spec.step_type_spec` ← currently broken for QE (returns empty). After fix, returns QE defaults correctly.

**Result**: `create_step_doc("scf", engine_family="vasp")` → `step_type_spec = "vasp_scf"` → `get_defaults("vasp_scf")` → not found → empty defaults. VASP step has no QE namelists. ✓

**Companion steps** (w90/yambo/qmcpack): When a QE calculation adds a w90 step (e.g., `step_type_gen="wannierprep"` resolved to `step_type_spec="w90_wannierprep"` via companion allowlist), `get_defaults("w90_wannierprep")` → not found → empty defaults. No QE namelist skeleton leaks into w90 steps. ✓

**`tests/gates/test_no_cross_engine_defaults.py`** (NEW) — Gate test:
- Create step via `create_step_doc("scf", engine_family="vasp")`: assert no CONTROL/SYSTEM/ELECTRONS keys
- Create step via `create_step_doc("scf", engine_family="orca")`: assert no QE namelist keys
- Create step via `create_step_doc("scf", engine_family="qe")`: assert HAS CONTROL/SYSTEM/ELECTRONS (QE defaults correct)
- Create step via `create_step_doc("scf", engine_family="lammps")`: assert empty parameters
- **Companion step**: Create step via `create_step_doc("wannierprep", engine_family="w90")`: assert no QE namelist keys (empty defaults)
- **Companion step**: Create step via `create_step_doc("vmc", engine_family="qmcpack")`: assert no QE namelist keys

### 0C. Hard-Ban add_step Fallback — Companion Allowlist Only

**Problem**: `service.py:add_step()` (lines 4028-4031) uses a two-tier fallback:
```python
spec = registry.get_for_engine(step_type_gen, engine_family)
if not spec:
    spec = registry.get(step_type_gen)  # ← generic first-match fallback
```
The `registry.get(step_type_gen)` fallback ignores `engine_family` entirely — it returns the first engine that registered that GEN type. This violates engine isolation: a VASP calc could silently resolve a step via QE's registry entry.

**Fix**: Replace the two-tier fallback with `DriverRegistry.resolve_companion_step()` (already exists at `driver_registry.py:330-367`), which respects the companion allowlist (COMPANION_ENGINES). This is the same resolution used by `materialize_public_step_key()` at `generalized_steps.py:161-191` — single SSOT for all step resolution.

**`src/qmatsuite/api/service.py`** — In `add_step()` (lines 4019-4043):
```python
# Before:
spec = registry.get_for_engine(step_type_gen, engine_family)
if not spec:
    spec = registry.get(step_type_gen)

# After:
spec = registry.get_for_engine(step_type_gen, engine_family)
if not spec:
    # Try companion allowlist (e.g., w90 step in QE calc)
    resolved_spec = DriverRegistry.resolve_companion_step(engine_family, step_type_gen)
    if resolved_spec is None:
        raise ValueError(
            f"No step type '{step_type_gen}' registered for engine '{engine_family}' "
            f"or its companion engines"
        )
    spec = registry.get(resolved_spec)  # lookup by resolved step_type_spec
```

**Result**: Unknown step types → hard error (no silent first-match). Companion steps (w90 in QE calc, yambo in QE calc, qmcpack in QE calc) → resolved via COMPANION_ENGINES allowlist. ✓

### Phase 0 Verification
```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
python -m pytest tests/gates/test_daemon_no_yaml_write.py tests/gates/test_no_cross_engine_defaults.py -v
```

---

## Patch Semantics — Verified In-Repo Behavior

All patch operations used by the replay engine go through `yamldoc.py` (read: `src/qmatsuite/core/yamldoc.py:299-396`). Verified behavior:

### `set(path, value)` (line 299)
- Creates intermediate dicts as needed
- **Rejects dict values** (line 322: raises `YamlDocError`)
- Accepts: scalars (str, int, float, bool, None) and lists
- Lists are deep-copied (line 330)
- **Replaces** any existing value at path (assignment at line 333)

### `delete(path)` (line 335)
- Removes leaf or branch at path (`del parent[key]`, line 352)
- Returns True if deleted, False if path didn't exist
- Safe on non-existent paths (catches `PathNotFoundError`, returns False)

### `apply_patch(patch)` (line 358)
- Recursive walk of patch dict (line 383-396):
  - `None` → `delete(path)` (**Delete Semantics A**, line 388-390)
  - `dict` → **recurse** (MERGE semantics, NOT replace — line 391-393)
  - Other → `set(path, value)` (REPLACE leaf, line 394-396)
- **Critical**: Dict merge does NOT delete keys that exist in target but not in patch. Existing keys persist.

### `update_step_params(calc, step, params)` (service.py:3271-3396)
- For `parameters`, `cards`, `species_overrides`, `parameter_scan`: routes through `apply_patch` (line 3324-3325)
- For other dict values: also routes through `apply_patch` (line 3327-3328)
- For scalars: routes through `set()` (line 3330)
- **Top-level None check** (line 3322): `if value is not None:` — skips top-level None values. So `update_step_params(C, S, {"parameters": None})` is a no-op.
- **Nested None works**: `update_step_params(C, S, {"parameters": {"CONTROL": None}})` → value is `{"CONTROL": None}` (not None) → apply_patch → recurse → delete CONTROL. ✓

### Implications for Authoring

| Operation | How replayed via `update_step_params` | Semantics | Verified? |
|-----------|--------------------------------------|-----------|-----------|
| SetField(ptr, val) | Build nested dict from pointer+value, call update_step_params | `set()` replaces leaf | ✓ |
| UnsetField(ptr) | Build nested dict with None at leaf, call update_step_params | `delete()` via Delete Semantics A | ✓ |
| ReplaceMap(ptr, map) | Build nested dict with map value, call update_step_params | `apply_patch` merges (recurses into dict) | ⚠️ merge, not replace |

**ReplaceMap merge residue risk**: If existing section has keys NOT in the replacement map, those keys persist. Mitigation: for sections where replacement is needed, the compiler emits `UnsetField` for the entire section first, then `ReplaceMap` to recreate from scratch. Alternatively: for steps with empty defaults (non-QE), no residue risk because section starts empty.

For QE steps (have defaults): compiler emits explicit UnsetField ops for default keys absent in the demo BEFORE SetField/ReplaceMap ops.

### Tests to Lock Semantics

**`tests/demo_store/test_patch_semantics.py`** (NEW ~60 lines):
- `test_set_replaces_leaf`: set → overwrite → verify new value
- `test_delete_removes_branch`: delete section → verify gone
- `test_apply_patch_none_deletes`: apply_patch with None → verify deletion
- `test_apply_patch_merge_preserves_existing`: apply_patch adds keys, existing untouched
- `test_apply_patch_merge_residue`: existing keys NOT in patch persist (document behavior)
- `test_update_step_params_nested_none_deletes`: full round-trip through service API
- `test_update_step_params_toplevel_none_noop`: top-level None is skipped

---

## Phase 1 — Fine-Grained AuthoringOps IR + Replay Engine

### Op Vocabulary (8 types)

| Op | Maps to | Fields | Granularity |
|----|---------|--------|-------------|
| `InitProject` | `QMSService.init_project()` | `name` | 1 per project |
| `ImportStructure` | `svc.structure.import_file()` | `name, structure_data` | 1 per structure |
| `CreateCalculation` | `svc.project.init_calculation()` | `name, engine_family, structure_selector` | 1 per calc |
| `AddStep` | `svc.calculation.add_step()` | `calc_selector, step_type_gen, name` | 1 per step |
| `SetField` | `svc.calculation.update_step_params()` | `target, pointer, value` | 1 per leaf value |
| `UnsetField` | `svc.calculation.update_step_params()` | `target, pointer` | 1 per deleted field |
| `ReplaceMap` | `svc.calculation.update_step_params()` | `target, pointer, value` | 1 per card/species section |
| `ConfigureSpeciesMap` | `svc.calculation.update_species_map()` | `calc_selector, species_map` | 1 per calc |

### Fine-Grain Rule (precise definition)

**MUST** (hard requirement):
- One op per independent **scalar** leaf parameter.
- `/parameters/SYSTEM/ecutwfc` = one op. `/parameters/ELECTRONS/conv_thr` = one op. `/parameters/ENCUT` = one op.
- **Hard ban**: No op may carry the entire `parameters` dict tree as value. An op whose `pointer` is `"/parameters"` and whose `value` is a dict = bulk patch = forbidden.

**ALLOWED** (one UI widget submit unit):
- Lists, tables, and scripts can be **one op** if that matches one UI widget submit unit.
- LAMMPS `_commands` (script editor widget) → one SetField with full list.
- K-mesh `[4, 4, 4]` → one SetField (one numeric input field).
- xTB `xcontrol` nested dict → each leaf field is its own SetField (each is a separate input field).
- Row-level splitting of lists (e.g., LAMMPS commands line-by-line, k-point rows individually) is **optional**, not required, unless a specific UI interaction justifies it.

### Leaf-Level Ops — Design

**SetField**: Sets exactly ONE scalar or list value at a JSON pointer path.
- `value` must be scalar (str, int, float, bool) or list. **Never a dict** (matches `yamldoc.set()` semantics).
- `target` format: `"step:<calc_slug>/<step_slug>"`
- `pointer` format: JSON pointer, e.g., `"/parameters/CONTROL/calculation"`, `"/parameters/ENCUT"`, `"/input_name"`

**UnsetField**: Removes exactly ONE field (leaf or branch). Used to clean up unwanted defaults or managed keys.
- Replayed via: `update_step_params(C, S, nested_dict_with_None_at_leaf)`
- Verified: nested None passes the `value is not None` check, apply_patch recurses, delete at leaf. ✓

**ReplaceMap**: Replaces a dict sub-tree. For sections authored as one UI panel:
- Cards: `ReplaceMap("step:C/S", "/cards/K_POINTS", {option: ..., data: ...})`
- Species overrides: `ReplaceMap("step:C/S", "/species_overrides/Si", {mass: 28.086})`
- For sections where defaults may have been injected: compiler emits `UnsetField` for the section first, then `ReplaceMap` to recreate from scratch (no merge residue).

### Replay Engine — No New QMSService Methods

All SetField/UnsetField/ReplaceMap route through existing `update_step_params`:

| Op | How replayed | Verified? |
|----|-------------|-----------|
| SetField(step:C/S, ptr, val) | `_pointer_to_nested_dict(ptr, val)` → `update_step_params(C, S, dict)` | ✓ (set at leaf) |
| UnsetField(step:C/S, ptr) | `_pointer_to_nested_dict(ptr, None)` → `update_step_params(C, S, dict)` | ✓ (delete at leaf) |
| ReplaceMap(step:C/S, ptr, map) | `_pointer_to_nested_dict(ptr, map)` → `update_step_params(C, S, dict)` | ✓ (apply_patch) |

Helper: `_pointer_to_nested_dict("/parameters/CONTROL/calculation", "scf")` → `{"parameters": {"CONTROL": {"calculation": "scf"}}}`

### `is_bulk_op(op)` — Gate Function

Returns True if an op carries a full params tree. Specifically:
- `SetField` where pointer is `"/parameters"` and value is a dict → bulk (but value can't be dict anyway per SetField rule)
- `ReplaceMap` where pointer is `"/parameters"` → bulk
- All others → not bulk

### Files

**`src/qmatsuite/demo_store/authoring_ops.py`** (NEW ~120 lines)
- 8 frozen `@dataclass` op types
- `AuthoringOp = Union[...]` type alias
- `ops_to_json(ops) -> str`, `ops_from_json(json_str) -> list[AuthoringOp]`
- `is_bulk_op(op) -> bool`

**`src/qmatsuite/demo_store/replay.py`** (NEW ~130 lines)
- `replay_ops(ops: list[AuthoringOp], target_dir: Path) -> Path`
- `_pointer_to_nested_dict(pointer: str, value: Any) -> dict`
- Dispatches to QMSService calls per table above
- ImportStructure: write temp `.json`, call `svc.structure.import_file()`, cleanup
- AddStep: calls `svc.calculation.add_step()` (no skip_defaults — defaults are now engine-correct)
- No direct YAML writes

**`tests/demo_store/test_authoring_ops.py`** (NEW ~60 lines)
- Serialization roundtrip, is_bulk_op, value type validation

**`tests/demo_store/test_replay.py`** (NEW ~70 lines)
- Empty ops raises, missing InitProject raises
- SetField replay creates expected leaf value
- UnsetField replay removes existing value
- Full QE SCF replay (manual fine-grained ops)

**`tests/demo_store/test_patch_semantics.py`** (NEW ~60 lines)
- Lock observed yamldoc behavior (see Patch Semantics section)

### Verification
```bash
python -m pytest tests/demo_store/ -v
```

---

## Phase 2 — Compiler + Roundtrip B Harness

### Compiler Algorithm

`compile_snapshot(snapshot_dict) -> list[AuthoringOp]`:

1. Emit `InitProject(name=project.meta.name)`

2. For each structure: emit `ImportStructure(name=meta.name, structure_data=data)`
   - Track `ulid → slug` mapping for calc structure references

3. For each calculation:
   a. Emit `CreateCalculation(name, engine_family, structure_selector=slug_from_ulid)`
   b. For each step:
      - `step_type_gen = gen_from(step_type_spec)` (from `workflow/step_type_convert.py:38`)
      - Emit `AddStep(calc_slug, step_type_gen, name=step_meta.name)`
      - **Reconcile defaults** (see below)
      - Walk demo parameters leaf-by-leaf: emit `SetField` per leaf (skip managed keys)
      - For each card: emit `ReplaceMap`
      - For each species_overrides entry: emit `ReplaceMap`
      - If `input_name` in step: emit `SetField`
   c. If `species_map` on calc: strip pseudo_sha*/pseudo_basename, emit `ConfigureSpeciesMap`

### Default Reconciliation (QE-specific)

After `AddStep`, QE steps have defaults injected (CONTROL, SYSTEM, ELECTRONS, K_POINTS). Non-QE steps have empty defaults (after Phase 0B fix). The compiler reconciles:

```python
defaults = get_default_step_params(step_type_spec)  # e.g., "qe_scf"
managed = MANAGED_KEYS_BY_ENGINE[engine]
demo_params = step.get("parameters", {})
default_params = defaults.get("parameters", {})

# 1. Unset default sections absent from demo (e.g., ELECTRONS not in demo)
for section_key in default_params:
    if section_key not in demo_params and section_key not in managed:
        emit UnsetField(step, f"/parameters/{section_key}")

# 2. Unset leaf keys within shared sections (e.g., CONTROL.outdir in defaults, not in demo)
for section_key in default_params:
    if section_key in demo_params and isinstance(default_params[section_key], dict):
        for leaf_key in default_params[section_key]:
            if leaf_key not in demo_params.get(section_key, {}) and leaf_key not in managed:
                emit UnsetField(step, f"/parameters/{section_key}/{leaf_key}")

# 3. Unset default cards absent from demo
for card_key in defaults.get("cards", {}):
    if card_key not in step.get("cards", {}):
        emit UnsetField(step, f"/cards/{card_key}")
```

For non-QE steps: `defaults` is empty → no UnsetField ops emitted → just SetField/ReplaceMap from scratch.

### `_walk_leaves(d, prefix="")` helper

Recursively yields `(pointer, value)` for each leaf:
- `dict` → recurse deeper (not a leaf)
- Everything else (scalar, list, None) → yield as leaf

```python
_walk_leaves({"CONTROL": {"calculation": "scf"}, "SYSTEM": {"ecutwfc": 20}})
→ [("/CONTROL/calculation", "scf"), ("/SYSTEM/ecutwfc", 20)]

_walk_leaves({"ENCUT": 240, "kpoints": {"mode": "automatic", "mesh": [4,4,4]}})
→ [("/ENCUT", 240), ("/kpoints/mode", "automatic"), ("/kpoints/mesh", [4,4,4])]

_walk_leaves({"_commands": [{cmd: "units", args: ["lj"]}, ...]})
→ [("/_commands", [{cmd: "units", args: ["lj"]}, ...])]
```

### Canonicalizer — Strict Allowlist

**`src/qmatsuite/demo_store/roundtrip.py`** — `_canonicalize_snapshot()` uses a strict, tiny allowlist. No field may be added without explicit rationale.

#### Allowed-to-ignore fields (exhaustive)

| # | Field | Location | Justification | Status |
|---|-------|----------|---------------|--------|
| 1 | `ulid` | All meta blocks | Identity regenerated each creation (SE.3 MUST IGNORE) | Already stripped |
| 2 | `path` | All meta blocks | Filesystem layout is derivative (SE.3 MUST IGNORE) | Already stripped |
| 3 | `meta` | Top-level snapshot | Demo gallery catalog metadata, not project content (SE.3 MUST IGNORE) | Already stripped |
| 4 | `structure_ulid` | `calculations[]` | Cross-reference uses fresh ULIDs per creation | Already stripped |
| 5 | `structure_name` | `calculations[]` | Derived from structure meta; may differ in format | Already stripped |
| 6 | `structure_kind` | `calculations[]` | Default "periodic"; not all creation paths set it | Already stripped |
| 7 | Managed param keys | `steps[].parameters` | Per `MANAGED_KEYS_BY_ENGINE`: runtime-injected by materialization (SE.3 MUST IGNORE) | Already stripped |
| 8 | `pseudo_sha256` | `species_map` entries | File-level hash from pseudo install; not authored | **NEW** |
| 9 | `pseudo_sha_family` | `species_map` entries | File-level hash from pseudo install; not authored | **NEW** |
| 10 | `pseudo_basename` | `species_map` entries | File-level basename from pseudo install; not authored | **NEW** |
| 11 | `pseudo` | Top-level snapshot | Pseudo directory config + file metadata; not project content | **NEW** |

#### NOT allowed to ignore (fixed in authoring instead)

| Field | Location | How fixed |
|-------|----------|-----------|
| `input_name` | `steps[]` | Compiler emits SetField — it IS authored content |
| `working_dir` | `calculations[]` | `init_calculation()` sets "raw" — matches demo |
| `mode` | `calculations[]` | `init_calculation()` sets "normal" — matches demo |
| `parameters` | `steps[]` | Every leaf via SetField; defaults reconciled via UnsetField |
| `cards` | `steps[]` | Each card via ReplaceMap |
| `species_overrides` | `steps[]` | Each species via ReplaceMap |
| `engine_family` | `calculations[]` | Set in CreateCalculation |
| `step_type_spec` | `steps[]` | Set by AddStep (registry materialization) |
| `species_map` (non-pseudo) | `calculations[]` | Set by ConfigureSpeciesMap |

#### Canonicalizer changes (minimal — 5 lines)

- Strip `pseudo_sha256`, `pseudo_sha_family`, `pseudo_basename` from species_map entries
- Strip top-level `pseudo` section

### Roundtrip B Diagnostics

The harness categorizes each mismatch and prints diagnostics:

```python
class MismatchCategory(Enum):
    ALLOWED_IGNORE = "allowed_ignore"     # Sanity check: should not appear (canonicalizer stripped)
    AUTHORSHIP = "authorship_mismatch"    # Compiler/op bug: field missing or extra
    SERVICE = "service_inconsistency"     # QMSService bug: value changed unexpectedly

def categorize_diff(diff_path: str, snap_a, snap_b) -> MismatchCategory:
    """Categorize a diff path for diagnostic reporting."""
    # Check if it's a field that should have been stripped
    if _is_allowed_ignore_field(diff_path):
        return MismatchCategory.ALLOWED_IGNORE
    # Check if it's a missing field (present in one, absent in other)
    if "missing in" in diff_path:
        return MismatchCategory.AUTHORSHIP
    # Value mismatch = service inconsistency
    return MismatchCategory.SERVICE
```

Harness output per failing demo:
```
FAIL: qe_si_scf (3 mismatches)
  [AUTHORSHIP] calculations[0].steps[0].parameters.ELECTRONS.conv_thr: missing in first snapshot
    expected: (absent)
    actual:   1e-08
  [AUTHORSHIP] calculations[0].steps[0].input_name: missing in second snapshot
    expected: "si.scf.in"
    actual:   (absent)
```

### Files

**`src/qmatsuite/demo_store/compiler.py`** (NEW ~170 lines)
- `compile_snapshot(snapshot: dict) -> list[AuthoringOp]`
- `_walk_leaves(d: dict, prefix: str = "") -> list[tuple[str, Any]]`
- `_reconcile_defaults(step_type_spec, engine, demo_step) -> list[AuthoringOp]`
- Uses `MANAGED_KEYS_BY_ENGINE` from `roundtrip.py`
- Uses `gen_from()` from `workflow/step_type_convert.py`
- Uses `get_default_step_params()` from `calculation/step_defaults.py`

**`src/qmatsuite/demo_store/roundtrip.py`** (MODIFY +15 lines)
- Strip pseudo-related keys from species_map entries (4 lines)
- Strip top-level `pseudo` section (1 line)
- Add `MismatchCategory` enum and `categorize_diff()` (10 lines)

**`tests/integrity/authoring/__init__.py`** (NEW, empty)

**`tests/integrity/authoring/conftest.py`** (NEW ~10 lines)
- Register `integrity` marker

**`tests/integrity/authoring/test_roundtrip_b.py`** (NEW ~120 lines)
- `@pytest.mark.integrity`
- Parametrized over all 52 demo `.yml` files
- `test_compile_produces_ops`: non-empty ops list starting with InitProject
- `test_no_bulk_ops`: `is_bulk_op(op)` is False for every op
- `test_roundtrip_b`: compile → replay → re-snapshot → `verify_roundtrip_equivalence()` → assert equivalent
- On failure: print first mismatch with category, path, expected/actual (truncated to 200 chars)
- Summary: per-demo ops count, SetField/UnsetField/ReplaceMap counts

### Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| QE defaults leak into non-QE steps | Phase 0B: spec-keyed lookup. Gate test enforces. |
| QE defaults persist after replay | Compiler emits UnsetField for default keys absent in demo |
| Merge residue in ReplaceMap | UnsetField clears section before ReplaceMap recreates it |
| Float precision in structure coords | `_deep_diff` uses 1e-10 tolerance |
| Slug collision | Use snapshot meta.slug as name |
| Cross-engine steps (w90, yambo) | Phase 0C: `add_step` uses `resolve_companion_step()` with hard error on no match. No generic `registry.get` fallback. |
| `input_name` mismatch | Compiler emits SetField for input_name |
| Diagnostics unclear | Categorized output: allowed-ignore / authorship / service |

### Verification
```bash
# Phase 2 authoring tests
python -m pytest tests/integrity/authoring/ -v --tb=short

# Full regression
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### Acceptance Criteria
1. All 52 demos compile to ops without errors
2. **Zero bulk ops** in any compiled ops list
3. All 52 demos complete Roundtrip B (semantic equivalence)
4. All existing tests remain green
5. Demo content unchanged (no modifications to `resources/demo_projects/*.yml`)
6. Canonicalizer allowlist: +5 lines only (pseudo-related)
7. No `skip_defaults` flag anywhere
8. Gate test: VASP/ORCA/LAMMPS steps have zero QE namelist keys
9. No `registry.get(step_type_gen)` fallback in `add_step` — companion resolution via `resolve_companion_step()` only

---

## Phase 3 — Optional Real-Run via Authorship (Deferred)

If easy, add pilot in `tests/integrity/authoring/test_authoring_realrun.py`:
1. Compile one demo (e.g., `qe_si_scf`)
2. Replay to fresh project
3. Run via `svc.run.run_calculation()`
4. Assert run completes

---

## Deliverable Files Summary

| File | Phase | Action | Lines (est.) |
|------|-------|--------|------|
| `src/qmatsuite/api/service.py` | 0A+0C | MODIFY | +140 (set_engine_family, apply_presets) + add_step fallback ban |
| `src/qmatsuite/daemon/server.py` | 0A | MODIFY | -130, +12 |
| `src/qmatsuite/calculation/step_defaults.py` | 0B | MODIFY | rename keys (same line count) |
| `src/qmatsuite/workflow/step_factory.py` | 0B | MODIFY | +1 (use step_type_spec for defaults lookup) |
| `src/qmatsuite/workflow/registry.py` | 0B | MODIFY | +2 (docstring) |
| `src/qmatsuite/cli/main.py` | 0B | MODIFY | +2 (construct spec type) |
| `src/qmatsuite/calculation/importers.py` | 0B | MODIFY | +1 (prefix with "qe_") |
| `src/qmatsuite/frontends/cli/app.py` | 0B | MODIFY | +2 (construct spec type) |
| `tests/gates/test_daemon_no_yaml_write.py` | 0A | NEW | ~40 |
| `tests/gates/test_no_cross_engine_defaults.py` | 0B | NEW | ~40 |
| `src/qmatsuite/demo_store/authoring_ops.py` | 1 | NEW | ~120 |
| `src/qmatsuite/demo_store/replay.py` | 1 | NEW | ~130 |
| `tests/demo_store/test_authoring_ops.py` | 1 | NEW | ~60 |
| `tests/demo_store/test_replay.py` | 1 | NEW | ~70 |
| `tests/demo_store/test_patch_semantics.py` | 1 | NEW | ~60 |
| `src/qmatsuite/demo_store/compiler.py` | 2 | NEW | ~170 |
| `src/qmatsuite/demo_store/roundtrip.py` | 2 | MODIFY | +15 |
| `tests/integrity/authoring/__init__.py` | 2 | NEW | 0 |
| `tests/integrity/authoring/conftest.py` | 2 | NEW | ~10 |
| `tests/integrity/authoring/test_roundtrip_b.py` | 2 | NEW | ~120 |
| `docs/demo_store/AUTHORSHIP_PATH_PLAN.md` | pre | NEW | copy of this |
| `docs/demo_store/AUTHORSHIP_PATH_CLOSEOUT.md` | post | NEW | results |

Total: ~820 lines new code, ~130 lines removed from daemon, ~10 lines modified
