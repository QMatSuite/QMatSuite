# Parameter Scan Implementation Plan

**Date**: 2026-01-17  
**Status**: Draft  
**Target**: Cursor Auto (implementer)

---

## PR-by-PR Implementation Plan

### PR 1: StepDoc/YAML Schema — ScanRef + parameter_scan + Validations

**Scope**: Add scan-related schema support and validation to StepDoc layer.

**Files to modify**:
- `src/quantumvitas/core/yamldoc.py` — No changes needed (already accepts any top-level keys)
- `src/quantumvitas/calculation/scan_validation.py` — **NEW FILE**

**New module `scan_validation.py`**:
```python
# Functions to implement:
def is_scan_ref(value: Any) -> bool
def validate_scan_ref_format(value: dict) -> bool  # regex check on scan_id, and must have ONLY scan_ref key
def find_all_scan_refs(data: dict) -> List[Tuple[str, str]]  # (param_path, scan_id)
def validate_step_scan_refs(step_doc: dict) -> List[str]  # returns list of errors/warnings
    # - Hard error if scan_ref points to missing scan_id
    # - Hard error if ScanRef dict has extra fields beyond scan_ref
    # - Hard error if ScanRef at non-leaf position (dict/card/subtree)
    # - Warning if parameter_scan has orphan definitions
```

**Integration point**:
- `src/quantumvitas/workflow/step_factory.py:save_step_doc()` — call `validate_step_scan_refs()` before save, log warnings, raise on errors

**Tests to add**:
- `tests/unit/test_scan_validation.py`:
  - `test_is_scan_ref_valid()`
  - `test_is_scan_ref_invalid_format()`
  - `test_scan_ref_extra_fields_error()` — ScanRef dict must have ONLY scan_ref key
  - `test_dangling_scan_ref_error()`
  - `test_orphan_scan_definition_warning()`
  - `test_scan_ref_at_non_leaf_error()` — hard error for dict/card/subtree
  - `test_scan_ref_leaf_only_acceptance()` — scalar and simple list are OK
  - `test_round_trip_with_parameter_scan()`

**Careful about**:
- Keep validation separate from YamlDoc (YamlDoc remains schema-agnostic)
- Use logging for warnings, not print
- Validation is optional at load (for backwards compat), mandatory at save

---

### PR 2: Variant Expansion + variant_key Computation

**Scope**: Core variant expansion logic and deterministic variant_key.

**Files to create**:
- `src/quantumvitas/execution/scan_expansion.py` — **NEW FILE**

**New module contents**:
```python
@dataclass
class ScanDimension:
    step_ulid: str
    step_index: int
    param_path: str
    scan_id: str
    values: List[Any]

@dataclass
class VariantAssignment:
    step_ulid: str
    step_index: int
    param_path: str
    value: Any

def collect_scan_dimensions(
    steps: List[Step],  # Ordered list of steps in job
    step_docs: Dict[str, dict],  # step_ulid -> step.yaml dict
) -> List[ScanDimension]

def expand_variants(dimensions: List[ScanDimension]) -> List[List[VariantAssignment]]
    # Cartesian product with deterministic ordering

def compute_variant_key(assignments: List[VariantAssignment]) -> str
    # Canonical JSON -> SHA256 -> "scan_" + hex[:16]

def canonicalize_value(v: Any) -> str
    # repr for floats, str for int, JSON for lists
```

**Tests to add**:
- `tests/unit/test_scan_expansion.py`:
  - `test_collect_dimensions_single_step()`
  - `test_collect_dimensions_multi_step()`
  - `test_expand_variants_cartesian_product()`
  - `test_expand_variants_deterministic_ordering()`
  - `test_variant_key_deterministic()`
  - `test_variant_key_float_precision()` — verify `repr(0.01)` works correctly
  - `test_ordering_later_step_varies_faster()`

**Careful about**:
- `param_path` is runtime-only, derived deterministically from actual traversal of engine params; any canonical pointer format is OK as long as deterministic (e.g., dot-separated paths work, but format is implementation-defined)
- Floats use `repr()`, not `str()` — critical for precision
- Sort dimensions by (step_index, param_path) for deterministic ordering

---

### PR 3: Effective Fingerprint Integration (Reuse Existing System)

**Scope**: Resolve ScanRefs to produce effective engine params view, then feed into existing fingerprint/manifest logic.

**Files to modify**:
- `src/quantumvitas/calculation/hash_utils.py` — add helper to build effective params view

**New function**:
```python
def build_effective_engine_params_view(
    step_doc: Dict[str, Any],
    variant_assignments: Optional[Dict[str, Any]] = None,  # param_path -> value
) -> Dict[str, Any]:
    """
    Build effective engine params view by resolving ScanRefs to concrete values.
    
    Returns a dict suitable for feeding into existing compute_step_sha().
    - If variant_assignments provided: replaces {scan_ref: X} with concrete values
    - Always removes parameter_scan section (not an engine parameter)
    - Preserves all other fields (parameters, cards, species_overrides, step_type, etc.)
    """
```

**Helper function**:
```python
def set_nested(data: dict, path: str, value: Any) -> None:
    """Set value at runtime param_path (format determined by traversal)"""
```

**Integration points**:
- `src/quantumvitas/calculation/manifest_reconcile.py` — for variants: build effective view, then call existing `compute_step_sha(effective_view)`
- For non-scan runs: if `parameter_scan` section exists, remove it before calling `compute_step_sha()`
- **Key principle**: Reuse existing `compute_step_sha()` / manifest hashing pathway; do not create parallel fingerprint system

**Tests to add**:
- `tests/unit/test_hash_utils.py`:
  - `test_build_effective_view_resolves_scan_refs()`
  - `test_build_effective_view_removes_parameter_scan()`
  - `test_effective_sha_equivalence()` — **critical**: step with concrete value 50 and scan-variant resolved to 50 produce identical step_sha via existing compute_step_sha()
  - `test_effective_view_no_mutation()` — verify input dict not mutated

**Careful about**:
- Deep copy input before mutation
- PR1 enforces leaf-only ScanRefs, so PR3 assumes valid leaf-only input (no need to handle dict/card/subtree cases)
- Feed effective view into existing `compute_step_sha()`, not a new function
- Keep existing behavior about prefix/outdir/pseudo_dir (do NOT add stripping logic)

---

### PR 4: PostJobActions + ArchiveToSlot

**Scope**: Generic post-job action system and scan archive implementation.

**Files to create**:
- `src/quantumvitas/execution/post_job.py` — **NEW FILE**

**New module contents**:
```python
@dataclass
class PostJobContext:
    calc_raw_dir: Path
    variant_key: Optional[str]
    run_id: str

class PostJobAction(ABC):
    @abstractmethod
    def execute(self, job_result: Any, context: PostJobContext) -> None

def snapshot_raw_dir(raw_dir: Path, exclude: List[str] = None) -> Dict[str, float]

def compute_snapshot_diff(before: Dict, after: Dict, exclude: List[str]) -> List[str]

@dataclass
class ArchiveToSlotAction(PostJobAction):
    variant_key: str
    def execute(self, job_result, context) -> None
```

**Integration points**:
- `src/quantumvitas/execution/executor.py:_execute_job()` — capture pre-snapshot, execute job, run post-job actions
- `Job` dataclass may need optional `post_actions: List[PostJobAction]` field

**Tests to add**:
- `tests/unit/test_post_job.py`:
  - `test_snapshot_raw_dir_basic()`
  - `test_snapshot_raw_dir_excludes_outdir()`
  - `test_snapshot_raw_dir_excludes_scan()`
  - `test_compute_diff_new_files()`
  - `test_compute_diff_modified_files()`
  - `test_archive_to_slot_creates_directory()`
  - `test_archive_to_slot_copies_files()`
  - `test_archive_to_slot_overwrites()`
  - `test_archive_on_failure_still_archives()` — failure case archives + ok=false
  - `test_slots_json_appends_entry()` — bookkeeping entry appended

**Note on slots.json**:
- `raw/scan/slots.json` is runtime bookkeeping only; not SSOT; not used for skip logic; may migrate to `.history` later

**Careful about**:
- Exclude both `outdir/` and `scan/` from snapshot
- Handle empty raw/ directory gracefully
- Use `shutil.copy2()` to preserve metadata
- Archive on both success and failure (best-effort); record `ok=false` in slots.json when job fails

---

### PR 5: Scan Orchestration in Runner

**Scope**: Wire up scan expansion and variant execution in the calculation runner.

**Files to modify**:
- `src/quantumvitas/calculation/runner.py` — add scan variant loop
- `src/quantumvitas/execution/recipes.py` — may need variant-aware job generation

**Changes to `CalculationRunner.run()`**:
```python
# After building job graph:
for job in job_graph:
    step_docs = load_step_docs_for_job(job)
    dimensions = collect_scan_dimensions(job.steps, step_docs)
    
    if not dimensions:
        # No scans: execute job normally
        execute_job(job)
    else:
        # Has scans: expand and execute variants
        variants = expand_variants(dimensions)
        for assignments in variants:
            variant_key = compute_variant_key(assignments)
            # Compute effective fingerprints for skip logic
            # Execute job with resolved params
            # Run ArchiveToSlotAction
```

**Tests to add**:
- `tests/integration/test_scan_execution.py`:
  - `test_single_step_scan_runs_all_variants()`
  - `test_scan_archives_to_correct_slots()`
  - `test_scan_incremental_skip_works()`
  - `test_scan_variant_count_matches_cartesian_product()`
  - `test_scan_stops_on_first_failure()` — MVP failure policy verification

**Careful about**:
- Manifest updates per variant (each variant updates same manifest with its effective fingerprint)
- Pre-snapshot before each variant job, not once per job
- **MVP Failure Policy**: Stop job-group on first variant failure (safer given shared raw/outdir current-state). Future work may add continue-with-cleanup option.

---

### PR 6: Preset Inference Robustness

**Scope**: Ensure preset inference gracefully handles ScanRef dicts.

**Files to modify**:
- `src/quantumvitas/presets/paramspace.py` — possibly add type check
- `src/quantumvitas/presets/detector.py` — possibly add guard

**Changes**:
- Review `get_yaml_value()` and `match_profile()` to confirm dict values don't cause crashes
- Ensure preset inference does not crash when encountering ScanRef dict values
- Behavior: scanned params naturally mismatch profile => inferred "custom" (no special ignore logic needed)

**Tests to add**:
- `tests/unit/test_preset_inference_scan.py`:
  - `test_preset_inference_with_scan_ref_returns_custom()` — ScanRef dict naturally mismatches => custom
  - `test_preset_inference_no_crash_on_scan_ref()` — no exceptions thrown

**Careful about**:
- Don't over-engineer: existing comparison logic should naturally return CUSTOM when dict value doesn't match expected scalar
- Verify with actual test data before adding special handling
- No changes to preset semantics—just ensure robustness (no crash)

---

### PR 7: Minimal UI (Optional, Last PR)

**Scope**: Basic UI for scan configuration and overview.

**Files to modify** (in `gui/` directory):
- Step detail component — add scan toggle per parameter row
- Calculation overview component — show scan summary + warning

**UI requirements**:
- Scan toggle (checkbox/icon) per scalar parameter
- When enabled: explicit list editor for values
- Calculation overview: total combinations count
- Warning banner if combinations > 10

**Tests to add**:
- Playwright/Vitest tests for UI components

**Careful about**:
- UI edits must use existing StepDoc mutation API
- Scan toggle must create/delete `parameter_scan` entries atomically
- Don't implement linspace/logspace UI in MVP

---

## Execution Order & Dependencies

```
PR 1 (Schema/Validation)
    ↓
PR 2 (Variant Expansion) ← depends on PR 1 for ScanRef detection
    ↓
PR 3 (Fingerprinting) ← depends on PR 2 for VariantAssignment type
    ↓
PR 4 (PostJobActions) ← independent, can parallel with PR 2-3
    ↓
PR 5 (Orchestration) ← depends on PR 2, 3, 4
    ↓
PR 6 (Preset Robustness) ← can parallel with PR 5
    ↓
PR 7 (UI) ← depends on PR 1-5 backend being complete
```

**Recommended merge order**: PR 1 → PR 2 → PR 3 → PR 4 → PR 5 → PR 6 → PR 7

---

*End of Implementation Plan*

