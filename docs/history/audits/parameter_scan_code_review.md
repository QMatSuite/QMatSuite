# Parameter Scan Code Review / Reconnaissance Report

**Date**: 2026-01-17  
**Reviewer**: Cursor Auto  
**Target Spec**: `docs/specs/parameter_scan.md`

---

## 2.1 Locate and Summarize

### A) StepDoc / YAML Parsing & Serialization

**File**: `src/qmatsuite/core/yamldoc.py`

- **StepDoc class** (lines 454-616): Wrapper around `YamlDoc` with QE-specific normalization
  - Normalizes section names to uppercase (CONTROL, SYSTEM, etc.)
  - Parameter aliases (gauss → gaussian)
  - Access control for compiler/detector/user roles
  - Known sections: `parameters`, `cards`, `species_overrides`, `meta`, `step_type`
  - **No validation of top-level keys** - accepts any dict structure

- **YamlDoc base class** (lines 75-443): Generic YAML document wrapper
  - `get()`: Returns leaf values (deep copy for containers)
  - `export_copy()`: Returns deep copy of branch (dict) subtrees
  - `set()` / `delete()` / `apply_patch()`: Mutation methods
  - `to_dict()`: Exports full document as dict
  - **No schema validation** - accepts any structure

- **Loading**: `StepDoc.load(path)` → calls `_load_yaml_raw()` → `yaml.safe_load()` → `StepDoc(data)`
  - **Location**: `src/qmatsuite/core/yaml_io.py:81-114`
  - No validation of unknown top-level keys

- **Saving**: `StepDoc.save(path)` → `save_yaml_doc()` → `_save_yaml_raw()` → `yaml.safe_dump()`
  - **Location**: `src/qmatsuite/core/yaml_io.py:117-175`
  - Writes entire `to_dict()` output - any top-level keys are preserved

- **Step Factory**: `src/qmatsuite/workflow/step_factory.py`
  - `create_step_doc()`: Creates StepDoc with known sections (meta, step_type, parameters, cards, species_overrides)
  - `save_step_doc()`: Saves via `save_yaml_doc()` (journaled)
  - **No validation** that only known keys exist

**Engine params location**: 
- `parameters` dict: `{section_name: {param: value}}` (e.g., `{"SYSTEM": {"ecutwfc": 50}}`)
- `cards` dict: `{card_name: {key: value}}`
- Both are top-level keys in step.yaml

### B) Manifest Digests / Incremental Skip

**File**: `src/qmatsuite/calculation/hash_utils.py`

- **`compute_step_sha()`** (lines 161-192):
  - Input: `step_doc` (dict or Path)
  - Strips meta fields via `strip_resource_meta()` (removes: meta, __qms_meta__, id, name, slug, path, kind, created_at, updated_at)
  - **Does NOT exclude runtime-managed keys** (prefix, outdir, pseudo_dir) - these are included in hash
  - **Does NOT handle `parameter_scan` section** - if present, it's included in hash
  - Uses `stable_serialize()` → SHA256

- **`strip_resource_meta()`** (lines 26-52): Recursively removes meta keys

- **`stable_serialize()`** (lines 103-118): Canonicalizes → JSON → bytes

**File**: `src/qmatsuite/calculation/manifest.py`

- **`ManifestStepEntry`** (lines 25-59): Stores per-step state
  - Fields: `kind`, `step_ulid`, `pseudo_set_sha`, `structure_sha`, `step_sha`, `run_id`, `done`, `started_at`, `done_at`
  - `step_sha` is the fingerprint used for skip logic

- **`should_skip_step()`** (lines 272-315): Skip decision logic
  - Requires: kind match + all 3 SHAs match + done==True
  - Uses `step_sha` from manifest entry vs current `step_sha`

**File**: `src/qmatsuite/execution/executor.py`

- **`_should_skip_job()`** (lines 156-195): Job-level skip logic
  - Checks all steps in job have matching fingerprints
  - Uses `step_shas` dict (step_ulid → SHA256)

**Manifest location**: `calculations/<calc_id>/.run_tmp_info/manifest.json`
- Overwritten each run (latest-only)

### C) Runtime-Managed Key Injection

**File**: `src/qmatsuite/calculation/structure_steps.py`

- **`_inject_calculation_prefix_outdir()`** (lines 341-447):
  - **When**: Called during `materialize_step_spec()` (line 1214)
  - **Where**: Injects into `QEInput` object (in-memory, NOT step.yaml)
  - **What**: Overrides `CONTROL.prefix` and `CONTROL.outdir` in the QE input file
  - **Step-level values**: Detected but ignored (logged as warning)
  - **NOT written to step.yaml** - only affects materialized `.in` file

- **`detect_runtime_control_keys()`** (lines 285-312):
  - Detects `prefix`, `outdir`, `pseudo_dir` in `parameters["CONTROL"]`
  - Pure keyword matching (no engine detection)
  - Used by `save_step_doc()` to emit warnings (line 125)

- **`set_pseudo_dir_in_input()`**: Called separately to inject `pseudo_dir` into QE input
  - **Location**: `src/qmatsuite/calculation/input_runner.py:113`

**Key finding**: Runtime-managed keys are **NOT excluded from step_sha fingerprint** currently. They are injected at materialize time but still present in step.yaml parameters dict when computing hash.

### D) Job Formation Semantics

**File**: `src/qmatsuite/execution/recipes.py`

- **QE Recipe** (lines 82-159):
  - **Job = 1 step**: Each step becomes one job
  - Job ID: `step_{idx:02d}`
  - Working dir: `calc/raw/` (shared across all jobs)
  - Steps list: Passed directly from `calculation.steps` (ordered list)

- **ORCA Recipe** (lines 162-268):
  - **Job = subchain**: SCF root → target step
  - Job ID: Stable token basename (e.g., "s", "s_t", "s_m2")
  - Working dir: `calc/raw/scf_<suffix>/` (per-chain namespace)
  - Steps list: First step must be SCF; builds subchains `steps[:target_idx+1]`

- **PySCF Recipe** (lines 271-376):
  - **Job = subchain session**: Similar to ORCA
  - Job ID: Stable token basename
  - Working dir: `calc/raw/scf_<suffix>/`
  - Steps list: Same subchain pattern as ORCA

**File**: `src/qmatsuite/calculation/runner.py`

- **`CalculationRunner.run()`** (lines 102-549):
  - **Run Calculation mode**: `target_step_id=None` → `SelectionMode.ALL` → all steps
  - **Run Step mode**: `target_step_id=<ulid>` → `SelectionMode.TARGET` → steps up to target
  - Steps list: `calculation.steps` (ordered list from calculation.yaml)

**File**: `src/qmatsuite/api.py`

- **`run_calculation()`** (lines 1151-1302): Calls `CalculationRunner.run()` with `target_step_id=None`
- **`run_step()`** (lines 1304-1400): Calls `CalculationRunner.run()` with `target_step_id=<resolved_ulid>`

**Key finding**: Job formation is deterministic - steps list is ordered from calculation.yaml, and recipes materialize jobs from that list.

### E) Raw Snapshot/Diff Archiving

**File**: `src/qmatsuite/history/run_revision.py`

- **`_create_snapshot()`** (lines 287-364):
  - **What**: Snapshots YAML files (project.qms.yml, calculation.yaml, step.yaml files)
  - **Does NOT snapshot raw/ directory** - only YAML config files
  - **Purpose**: History tracking, not output archiving
  - **Format**: tar.zst or tar.gz

- **`complete_run_revision()`** (lines 367-375): Completes revision after execution
  - No snapshot diff logic found

**Search results**: No existing snapshot/diff algorithm for `raw/` directory found.

**Outdir exclusion**: 
- `outdir` is a QE scratch directory at `raw/outdir/`
- No existing code excludes it from file operations
- **Not found**: Any existing archiving or snapshot logic that excludes `outdir`

**Key finding**: **No existing raw/ snapshot/diff archiving mechanism**. This is a new feature requirement.

---

## 2.2 Gap Analysis vs Spec

| Spec Requirement | Status | File/Symbol | Minimal Change Required |
|-----------------|--------|-------------|------------------------|
| **1.1-1.3: parameter_scan top-level section** | ❌ Missing | `StepDoc` class | Add `parameter_scan` as accepted top-level key (no validation needed - YamlDoc accepts any) |
| **1.2: ScanRef syntax `{scan_ref: X}`** | ❌ Missing | `StepDoc.load()` / validation | Add validation in `StepDoc.load()` or separate validator to detect ScanRef dicts |
| **1.4: ScanRef only at leaf positions** | ❌ Missing | Validation layer | Add validator to traverse parameters/cards and check ScanRef locations |
| **1.5: Dangling ScanRef error** | ❌ Missing | Validation layer | Add validator that checks all `{scan_ref: X}` reference existing `parameter_scan[X]` |
| **1.5: Orphan scan warning** | ❌ Missing | Validation layer | Add validator that checks `parameter_scan` entries are referenced |
| **2.1: Job formation unchanged** | ✅ Exists | `recipes.py` | No change - recipes already materialize jobs from step lists |
| **3.1-3.3: Variant expansion** | ❌ Missing | New module | Create variant expansion logic (collect dimensions, cartesian product, deterministic ordering) |
| **4: variant_key computation** | ❌ Missing | New module | Create `compute_variant_key()` function with assignment list + SHA256 |
| **5.2: Effective fingerprint (ScanRef resolution)** | 🟡 Partially | `hash_utils.py:compute_step_sha()` | Modify to: (1) resolve ScanRefs before hashing, (2) exclude runtime keys, (3) exclude `parameter_scan` section |
| **5.2: Exclude runtime keys from fingerprint** | ❌ Missing | `hash_utils.py:compute_step_sha()` | Add logic to remove `CONTROL.prefix`, `CONTROL.outdir`, `CONTROL.pseudo_dir` before hashing |
| **6.1-6.2: PostJobAction interface** | ❌ Missing | New module | Create `PostJobAction` ABC and `ArchiveToSlotAction` class |
| **6.3: Snapshot/diff algorithm** | ❌ Missing | New module | Create `snapshot_raw_dir()` and `compute_snapshot_diff()` functions |
| **6.3: Exclude outdir from snapshot** | ❌ Missing | New snapshot code | Add `exclude=["outdir", "scan"]` to snapshot logic |
| **6.4-6.5: Archive to raw/scan/<variant_key>/** | ❌ Missing | New module | Implement archive copy logic with overwrite semantics |
| **7: UI requirements** | ❌ Missing | GUI codebase | Out of scope for this review (backend only) |

---

## 2.3 Questions (Must Ask, Do Not Guess)

1. **Canonical param_path format**: What is the exact format for `param_path` in variant_key assignments?
   - Spec says: `"parameters.SYSTEM.ecutwfc"` or `"cards.K_POINTS.kpoints"`
   - Question: Should it use dot notation or tuple/list? Should section names be normalized (uppercase)?
   - **Recommendation needed**: Define canonical format (e.g., always uppercase sections, dot-separated strings)

2. **Effective fingerprint scope**: Exactly which subtree of step.yaml is used for `step_sha` today?
   - Current: `strip_resource_meta()` removes meta, then hashes entire remaining dict
   - Question: Does it include `cards`? `species_overrides`? `step_type`?
   - **Answer needed**: Confirm what `compute_step_sha()` currently includes (appears to be everything except meta)

3. **Runtime key exclusion timing**: When should runtime keys be excluded from fingerprint?
   - Current: Runtime keys are in step.yaml `parameters` dict, so they're included in hash
   - Question: Should we exclude them from step.yaml before hashing, or strip them during hash computation?
   - **Recommendation needed**: Strip during hash computation (preserve step.yaml as-is, exclude only in fingerprint)

4. **ScanRef resolution for fingerprint**: How to resolve ScanRefs when computing effective fingerprint?
   - Spec says: Replace `{scan_ref: X}` with variant's concrete value
   - Question: Should we deep-copy step.yaml first, then mutate? Or create new dict?
   - **Recommendation needed**: Deep copy → resolve → strip meta → strip runtime keys → hash

5. **Preset inference compatibility**: Will preset inference break if it encounters ScanRef dicts?
   - Current: `match_profile()` in `paramspace.py` calls `get_yaml_value()` which reads raw values
   - Question: What happens if `get_yaml_value()` returns `{scan_ref: "scan001"}` instead of a scalar?
   - **Risk**: Preset inference may fail or return CUSTOM if it sees dict values
   - **Answer needed**: Confirm preset inference should ignore parameters with ScanRefs (spec says "Parameter Scan must not participate in preset inference")

6. **StepDoc validation**: Does StepDoc currently validate parameter value types?
   - Current: No validation found - `StepDoc` accepts any dict structure
   - Question: Will ScanRef dicts be rejected by any existing validation?
   - **Answer**: No - no validation exists, so ScanRefs will be accepted as-is

7. **Job execution order**: How is step order determined within a job for variant ordering?
   - QE: One step per job → step_index = 0 always
   - ORCA/PySCF: Multiple steps per job → step_index = position in `subchain_steps` list
   - Question: Is `step_index` available in job metadata, or must we compute it?
   - **Answer needed**: Confirm how to get step_index for each step within a job

8. **Manifest per-variant**: Spec says "each variant run updates the same manifest" - is this correct?
   - Current: Manifest is per-calculation, overwritten each run
   - Question: If we run 12 variants, do we update manifest 12 times (last wins), or once per variant?
   - **Spec clarification needed**: How should manifest entries be keyed? By step_ulid only, or step_ulid + variant_key?

9. **Snapshot timing**: When should pre-job snapshot be captured?
   - Spec says: "Capture file listing of raw/ before job execution"
   - Question: For scan variants, is snapshot per-variant (before each variant job) or per-job (before first variant)?
   - **Recommendation needed**: Per-variant snapshot (each variant job gets its own before/after snapshot)

10. **Archive atomicity**: Spec says "atomicity NOT required" - what about partial failures?
    - Question: If variant job fails, should we still archive partial outputs?
    - **Recommendation needed**: Archive only on successful job completion (check `JobResult.success`)

11. **Variant key collision**: What if two different parameter combinations hash to same 16-char prefix?
    - Spec: `variant_key = "scan_" + sha256_hex[:16]`
    - Question: Should we check for collisions and extend hash if needed?
    - **Recommendation**: 16 hex chars = 64 bits, collision probability is negligible for practical scan sizes

12. **Cards with ScanRefs**: Spec allows ScanRefs in `cards` for "simple list leaves" - what qualifies?
    - Example given: `cards.K_POINTS.kpoints: {scan_ref: ...}` where values are `[4,4,4]`
    - Question: Are there other card types that qualify? How to validate "simple list"?
    - **Answer needed**: Define which cards support ScanRefs (likely only K_POINTS.kpoints for MVP)

---

## 2.4 Non-Goals (Confirmed)

- ✅ No code changes made
- ✅ No implementation started
- ✅ No refactoring performed
- ✅ Report only

---

## Summary

**Key Findings**:
1. **StepDoc/YAML**: No validation exists - `parameter_scan` section will be accepted as-is. No changes needed to parsing/serialization.

2. **Fingerprint**: Current `compute_step_sha()` includes runtime-managed keys and would include `parameter_scan` section. **Must modify** to exclude both.

3. **Job formation**: Already supports ordered step lists. No changes needed.

4. **Archiving**: **Completely missing** - must implement from scratch (snapshot/diff + archive logic).

5. **Preset inference**: **Risk** - may break if it encounters ScanRef dicts. Need to ensure preset inference ignores scanned parameters.

**Critical Gaps**:
- Variant expansion logic (entirely new)
- Effective fingerprint with ScanRef resolution (modify existing)
- Runtime key exclusion from fingerprint (modify existing)
- Post-job archiving (entirely new)
- Validation layer for ScanRef syntax and references (entirely new)

**Low-Risk Areas**:
- StepDoc parsing/serialization (accepts any structure)
- Job formation (already supports ordered steps)
- Manifest structure (can accommodate variant fingerprints)

