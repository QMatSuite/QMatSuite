<!-- Source: Claude Opus spec pasted verbatim from chat on 2026-01-17 -->

# Engine-Specific Parameter Scan — Engineering Specification

## Document Metadata
- **Version**: 1.0.0
- **Status**: Draft
- **Target Audience**: Implementers (Cursor Auto), Reviewers
- **Scope**: QE, ORCA, PySCF engines

---

## 1. Parameter Scan YAML & StepDoc Schema (Persisted in `step.yaml`)

### 1.1 Core Goal

Eliminate double-truth and stale-value conflicts. A parameter MUST be **either** a concrete value **or** a scan pointer—never both simultaneously in the YAML.

**Rationale**: Storing both a concrete value and a scan reference invites silent divergence (user edits concrete value, forgets scan reference, or vice versa). Single-representation enforces clarity.

### 1.2 ScanRef Pointer Syntax

**MUST**: A scanned parameter value is represented ONLY as a dictionary with the key `scan_ref`:

```yaml
parameters:
  SYSTEM:
    ecutwfc: {scan_ref: scan001}   # Pointer, no concrete value
    ecutrho: 400                   # Concrete value, no scan
```

**MUST NOT**:
- No string shorthand (e.g., `"@scan:scan001"` is forbidden)
- No embedded concrete value alongside `scan_ref`

**Type Definition** (runtime-only, for validation):
```python
ScanRef = TypedDict("ScanRef", {"scan_ref": str})  # Exactly one key
```

A leaf value is a ScanRef if and only if:
1. It is a `dict` with exactly one key: `"scan_ref"`
2. The value of `"scan_ref"` is a non-empty string matching `^[a-z0-9_]+$`

### 1.3 Top-Level `parameter_scan` Section

**MUST**: `step.yaml` contains a **top-level** section (NOT nested under `meta` or `parameters`):

```yaml
meta:
  id: "01HXYZ..."
  name: "SCF"
step_type: qe_scf
parameters:
  SYSTEM:
    ecutwfc: {scan_ref: scan001}
    degauss: {scan_ref: scan002}
cards: {}

parameter_scan:
  scan001:
    values: [30, 40, 50, 60]
  scan002:
    values: [0.01, 0.02, 0.03]
```

**MUST**:
- `parameter_scan` is a mapping of `scan_id → ScanDefinition`
- `ScanDefinition` is a mapping with exactly one key: `values`
- `values` is a list of concrete values (all same type: int, float, string, or simple list)

**MUST NOT**:
- No `dtype`, `linspace`, `logspace` in persisted YAML (these are UI conveniences that generate explicit `values` lists before saving)
- No `min/max/step` ranges—only explicit enumeration

**Schema (Python dataclass, runtime-only)**:
```python
@dataclass
class ScanDefinition:
    values: List[Union[int, float, str, List[Union[int, float]]]]

@dataclass  
class ParameterScanSection:
    __root__: Dict[str, ScanDefinition]  # scan_id → definition
```

### 1.4 Allowed ScanRef Locations

**MUST**: ScanRef may appear ONLY at **leaf positions** within `parameters` or `cards`:
- **Scalar leaves**: `ecutwfc: {scan_ref: ...}`
- **Simple list leaves**: `K_POINTS.kpoints: {scan_ref: ...}` where values are lists like `[4,4,4]`

**MUST NOT**:
- ScanRef as value for an entire dict/section (no `SYSTEM: {scan_ref: ...}`)
- ScanRef as value for a card with complex structure (no `ATOMIC_POSITIONS: {scan_ref: ...}`)
- ScanRef within nested dicts beyond leaf level

**Path Validation**: A valid ScanRef path has the form:
- `parameters.<SECTION>.<param_name>` (e.g., `parameters.SYSTEM.ecutwfc`)
- `cards.<card_name>.<leaf_key>` for simple-leaf cards (e.g., `cards.K_POINTS.kpoints`)

### 1.5 Validation Rules

**On Load/Validate**:
1. **Dangling ScanRef → Hard Error**: If any `{scan_ref: X}` references a `scan_id` not present in `parameter_scan`, raise `ScanRefNotFoundError` with message:
   ```
   ScanRef 'scan_ref: {X}' references undefined scan_id '{X}' at path '{path}'.
   Defined scan_ids: [{list}]
   ```

2. **Orphan Scan Definition → Non-blocking Warning**: If `parameter_scan` contains entries not referenced by any ScanRef in `parameters`/`cards`, emit warning:
   ```
   [WARN] Orphan scan definition(s) not referenced: {list of scan_ids}. Consider removing.
   ```
   Do NOT fail; allow save/run.

3. **Type Consistency**: All values in a `ScanDefinition.values` list SHOULD be same type. Implementer MAY emit warning on mixed types but MUST NOT error (runtime resolves by coercion).

### 1.6 Edit Semantics: Un-scan Operation

When converting a parameter from ScanRef back to a concrete scalar:

**Procedure** (atomic within a single save):
1. Identify the target `scan_id` from the ScanRef
2. Replace the ScanRef at the parameter path with the chosen concrete value
3. Check if any other ScanRefs reference the same `scan_id`
4. If NO other references exist, delete the scan definition from `parameter_scan`
5. Save step.yaml

**Note**: Scan IDs are never reused within a step. Once a scan_id is removed, a new scan MAY use the same ID string in the future (no collision risk because the old reference no longer exists).

---

## 2. Conceptual Model: Scan = Normal Jobs + Generic Post-Job Archiving

Parameter Scan is NOT a special execution mode. It expands a single "Run Calc" or "Run Step" into multiple job invocations, each with different parameter values.

### 2.1 Job Formation is Unchanged

Existing job formation semantics remain EXACTLY as-is:

| Engine | Job = | Steps per Job |
|--------|-------|---------------|
| QE | One executable invocation | 1 step |
| ORCA | One subchain execution | SCF → target (1..N steps) |
| PySCF | One session execution | SCF → target (1..N steps) |

**Invariant**: *"Scan only expands within the steps included in a single job. All ScanRefs inside those steps are fully resolved to a single variant before that job runs."*

**Consequence for ORCA/PySCF**: A subchain job covering [SCF, TD] where SCF has `nprocs` scanned and TD has `nroots` scanned will expand to `|nprocs_values| × |nroots_values|` variant executions of that subchain job.

### 2.2 Workdir/Outdir/Prefix Unchanged

- Execution still runs in the existing flat `raw/` workdir layout
- Do NOT introduce nested per-variant workdirs
- Runtime-managed keys (`prefix`, `outdir`, `pseudo_dir`) continue to be injected at materialize time
- Variant separation is achieved via post-job archiving (Section 6), not workdir isolation

### 2.3 Variant Labels

- **MVP**: Variant label (human-readable) is NOT required
- **Required**: Robust `variant_key` (Section 4) for archival and identification

---

## 3. Variant Expansion + Deterministic Ordering

### 3.1 Collect Scan Dimensions

For a given job (which covers an ordered list of step ULIDs):

1. For each step in job order, traverse `parameters` and `cards` to find all ScanRef occurrences
2. For each ScanRef, record a **ScanDimension**:
   ```python
   @dataclass
   class ScanDimension:
       step_ulid: str           # Which step contains this ScanRef
       step_index: int          # Position of step within job (0-based)
       param_path: str          # Canonical path, e.g., "parameters.SYSTEM.ecutwfc"
       scan_id: str             # Reference to parameter_scan entry
       values: List[Any]        # Resolved values list
   ```
3. Lookup `parameter_scan[scan_id].values` for each dimension

### 3.2 Cartesian Product Expansion

Given N scan dimensions with cardinalities `|V1|, |V2|, ..., |VN|`:
- Total variants = `|V1| × |V2| × ... × |VN|`
- Each variant is a full assignment of one value per dimension

### 3.3 Deterministic Ordering with Maximum Prefix Reuse

**Goal**: Maximize reuse of earlier steps across adjacent variants.

**Invariant**: *"Scan dimensions belonging to later steps in the job's execution order vary faster (are inner loops)."*

**Algorithm**:
1. Sort dimensions primarily by `step_index` ascending
2. Within same `step_index`, sort by `param_path` lexicographically (deterministic but implementation-defined)
3. Generate variants via nested iteration:
   ```python
   # dimensions sorted: [dim0, dim1, dim2, ...]
   # dim0.step_index <= dim1.step_index <= ...
   for v0 in dimensions[0].values:     # Outermost (earliest step)
       for v1 in dimensions[1].values:
           for v2 in dimensions[2].values:  # Innermost (latest step)
               yield {dim0.param_path: v0, dim1.param_path: v1, dim2.param_path: v2}
   ```

**Example**: Job covers steps [SCF, DOS]. SCF has ecutwfc scanned [30, 40]. DOS has Emin scanned [−10, −5].

| Variant | ecutwfc | Emin |
|---------|---------|------|
| 0 | 30 | −10 |
| 1 | 30 | −5 |
| 2 | 40 | −10 |
| 3 | 40 | −5 |

Adjacent variants (0,1) and (2,3) share SCF results (same ecutwfc).

---

## 4. Robust `variant_key` (Runtime-Only)

`variant_key` identifies ONLY the scan parameter combination. It does NOT encode engine version, mapper version, run mode, or any execution context.

### 4.1 Assignment List

For each variant, construct an ordered list of `VariantAssignment` tuples:

```python
@dataclass
class VariantAssignment:
    step_ulid: str      # Step containing the parameter
    param_path: str     # Canonical path within step (e.g., "parameters.SYSTEM.ecutwfc")
    value: Any          # Resolved value for this variant
```

### 4.2 Canonical Value Serialization

- **Floats**: Use Python `repr()` for maximum precision (e.g., `repr(0.01)` → `"0.01"`)
- **Integers**: String representation (e.g., `"30"`)
- **Strings**: As-is
- **Lists**: JSON array with elements following above rules

### 4.3 Deterministic Ordering

Sort assignments by:
1. Step order within job (by step_index)
2. `param_path` lexicographically within same step

### 4.4 Hashing

```python
def compute_variant_key(assignments: List[VariantAssignment]) -> str:
    # Build canonical structure
    data = [
        {
            "step_ulid": a.step_ulid,
            "param_path": a.param_path,
            "value": canonicalize_value(a.value),
        }
        for a in sorted(assignments, key=lambda a: (a.step_index, a.param_path))
    ]
    
    # Serialize to canonical JSON
    json_bytes = json.dumps(data, sort_keys=True, separators=(',', ':')).encode('utf-8')
    
    # Hash
    sha = hashlib.sha256(json_bytes).hexdigest()
    
    return f"scan_{sha[:16]}"

def canonicalize_value(v: Any) -> str:
    if isinstance(v, float):
        return repr(v)
    elif isinstance(v, list):
        return json.dumps([canonicalize_value(x) for x in v], separators=(',', ':'))
    else:
        return str(v)
```

**Result**: `variant_key` like `"scan_a1b2c3d4e5f6g7h8"` (16 hex chars = 64 bits)

---

## 5. Incremental Semantics: Effective Fingerprint Ignores Scan Existence

### 5.1 No Scan Barrier

Incremental skip is purely fingerprint-based. The manifest does NOT know scans exist—it only sees effective resolved parameters.

### 5.2 Effective Engine Params Fingerprint

For a step within a variant:

1. **Start with step YAML** (as-is from disk, including ScanRefs)
2. **Resolve all ScanRefs** by replacing each `{scan_ref: X}` with the variant's concrete value for that dimension
3. **Strip meta fields** (per existing `strip_resource_meta`)
4. **Exclude runtime-managed keys**: Remove `CONTROL.prefix`, `CONTROL.outdir`, `CONTROL.pseudo_dir` from the dict before hashing (these are injected at materialize and must NOT influence fingerprint)
5. **Compute SHA256** using existing `stable_serialize` + hash

```python
def compute_effective_step_sha(
    step_doc: Dict[str, Any],
    variant_assignments: Dict[str, Any],  # param_path → value for this variant
) -> str:
    # Deep copy to avoid mutation
    effective = copy.deepcopy(step_doc)
    
    # Resolve ScanRefs
    for param_path, value in variant_assignments.items():
        set_nested(effective, param_path, value)
    
    # Strip meta
    effective = strip_resource_meta(effective)
    
    # Remove runtime-managed keys
    if "parameters" in effective:
        control = effective["parameters"].get("CONTROL", {})
        for key in ["prefix", "outdir", "pseudo_dir"]:
            control.pop(key, None)
    
    # Hash
    return hashlib.sha256(stable_serialize(effective)).hexdigest()
```

### 5.3 Manifest Scope

- Manifest remains per-calculation (`calculations/<calc_id>/.run_tmp_info/manifest.json`)
- Manifest is overwritten each run (keeps only latest run state)
- **Implication**: Incremental reuse is only guaranteed for immediately subsequent runs matching latest fingerprints
- Scan variants do NOT have per-variant manifests; each variant run updates the same manifest (this is consistent with current single-variant behavior)

### 5.4 What the Fingerprint Includes / Excludes

| Includes | Excludes |
|----------|----------|
| Effective engine params (ScanRefs resolved) | `meta` fields (id, name, slug, path, kind, timestamps) |
| `cards` (with ScanRefs resolved) | Runtime-managed keys (prefix, outdir, pseudo_dir) |
| `species_overrides` | `parameter_scan` section itself |
| `step_type` | Scan IDs (only values matter) |

---

## 6. Generic PostJobActions + ArchiveToSlot

Introduce a generic post-job lifecycle stage. Scan variants attach an archive action, but the mechanism is generic (future uses: checkpointing, artifact extraction).

### 6.1 PostJobAction Interface (Runtime-Only)

```python
@dataclass
class PostJobAction(ABC):
    @abstractmethod
    def execute(self, job_result: JobResult, context: PostJobContext) -> None:
        pass

@dataclass
class PostJobContext:
    calc_raw_dir: Path
    variant_key: Optional[str]
    run_id: str
```

### 6.2 ArchiveToSlot Action

**Destination**: `raw/scan/<variant_key>/`

```python
@dataclass
class ArchiveToSlotAction(PostJobAction):
    variant_key: str
    
    def execute(self, job_result: JobResult, context: PostJobContext) -> None:
        dest = context.calc_raw_dir / "scan" / self.variant_key
        dest.mkdir(parents=True, exist_ok=True)
        
        # Use before/after snapshot diff to identify new/modified files
        new_modified = compute_snapshot_diff(
            before=job_result.pre_snapshot,
            after=snapshot_raw_dir(context.calc_raw_dir),
            exclude=["outdir", "scan"],  # Exclude scratch and archive dirs
        )
        
        # Copy/overwrite to slot
        for rel_path in new_modified:
            src = context.calc_raw_dir / rel_path
            dst = dest / rel_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
```

### 6.3 Snapshot/Diff Algorithm

**Pre-job**: Capture file listing of `raw/` before job execution
```python
def snapshot_raw_dir(raw_dir: Path, exclude: List[str]) -> Dict[str, float]:
    """Return {relative_path: mtime} for all files, excluding specified dirs."""
    result = {}
    for path in raw_dir.rglob("*"):
        if path.is_file():
            rel = path.relative_to(raw_dir)
            # Skip excluded directories
            if any(rel.parts[0] == ex for ex in exclude):
                continue
            result[str(rel)] = path.stat().st_mtime
    return result
```

**Post-job diff**:
```python
def compute_snapshot_diff(before: Dict, after: Dict, exclude: List[str]) -> List[str]:
    """Return list of new or modified file paths."""
    changed = []
    for path, mtime in after.items():
        if any(path.startswith(f"{ex}/") or path == ex for ex in exclude):
            continue
        if path not in before or before[path] < mtime:
            changed.append(path)
    return changed
```

**MUST exclude**:
- `outdir/` (QE scratch directory—large, transient)
- `scan/` (archive directory itself—avoid recursive archiving)

### 6.4 What to Archive

Archive all new/modified files in `raw/` EXCEPT:
- `outdir/` contents
- `scan/` contents
- Any engine-declared transient files (future extension)

**No engine-backend declaration required**: The snapshot diff approach is engine-agnostic.

### 6.5 Overwrite Semantics

- **Latest-only overwrite**: Each archive run for a variant_key overwrites the previous contents
- **Atomicity NOT required**: Partial writes are acceptable (interrupted run = partial archive)
- **No history within slot**: `raw/scan/<variant_key>/` contains only the latest run outputs

### 6.6 Optional Bookkeeping

**MAY** implement an append-only bookkeeping file:

**Path**: `raw/scan/slots.json`

**Format**:
```json
{
  "events": [
    {
      "variant_key": "scan_a1b2c3d4e5f6g7h8",
      "run_id": "01HXY...",
      "timestamp": "2026-01-17T10:30:00Z",
      "status": "ok",
      "files_archived": 5
    }
  ]
}
```

**Semantics**:
- Append-only (new events added to end of `events` list)
- NOT treated as SSOT—purely diagnostic
- MAY migrate to `.history` in future versions

---

## 7. MVP UI Requirements

### 7.1 Step Detail View

**Per-parameter row**:
- **Scan Toggle**: Checkbox or icon to enable/disable scan for this parameter
- **Value Display**:
  - When scan disabled: Normal scalar input field
  - When scan enabled: "Scanning N values" indicator + expand button
- **Scan Editor** (on expand):
  - Explicit list editor for scan values
  - Add/remove value buttons
  - Type validation (warn on mixed types)
  - NO linspace/logspace UI in MVP (manual entry only)

### 7.2 Calculation Overview

**Display**:
- Steps with active scans: Visual indicator (e.g., icon, badge)
- Parameters being scanned: List or summary (e.g., "ecutwfc, degauss")
- Total combinations: Computed Cartesian product count

**Warning**:
- If total combinations > 10: Display warning banner
  ```
  ⚠️ This scan will run 24 combinations. Large scans may take significant time.
  ```
- Warning is advisory only; does NOT block run
- Threshold (10) may be configurable in future

### 7.3 No UI for Variant Results in MVP

- MVP does NOT include a variant results browser
- Users access results via file system: `raw/scan/<variant_key>/`
- Future versions may add comparison UI

---

## Invariants Summary

1. **Single-Representation Invariant**: A parameter is either `{scan_ref: X}` or a concrete value, never both.
2. **Explicit-Only Invariant**: `parameter_scan[X].values` contains only explicit value lists, no generators.
3. **Job-Scope Expansion Invariant**: All ScanRefs within a job's steps are fully expanded into variants for that job.
4. **Deterministic Ordering Invariant**: Earlier-step dimensions vary slower (outer loops); later-step dimensions vary faster (inner loops).
5. **Fingerprint-Only Skip Invariant**: Incremental skip uses effective resolved params; manifest does not know scans exist.
6. **Runtime-Key Exclusion Invariant**: prefix/outdir/pseudo_dir are excluded from fingerprints.
7. **Latest-Only Archive Invariant**: `raw/scan/<variant_key>/` contains only the most recent run outputs.

---

# Acceptance Criteria

1. **AC-1**: `step.yaml` with `parameter_scan` section and ScanRef values loads without error and round-trips (save then load produces identical structure).

2. **AC-2**: Loading a step.yaml where a ScanRef references undefined scan_id raises `ScanRefNotFoundError` with clear message.

3. **AC-3**: Loading a step.yaml with orphan scan definitions (not referenced) emits warning but does NOT fail.

4. **AC-4**: Variant expansion produces correct Cartesian product count (e.g., 2 dims with 3 and 4 values → 12 variants).

5. **AC-5**: Variant ordering respects step-order invariant: dimensions from earlier steps vary slower than dimensions from later steps.

6. **AC-6**: `variant_key` is deterministic: same parameter assignments always produce identical key.

7. **AC-7**: Effective fingerprint excludes runtime-managed keys (prefix, outdir, pseudo_dir) and resolves ScanRefs to concrete values.

8. **AC-8**: Incremental skip works correctly: re-running same variant with unchanged params skips; changed param re-runs.

9. **AC-9**: Post-job archive writes to `raw/scan/<variant_key>/` with correct snapshot diff (excludes outdir).

10. **AC-10**: Archive overwrites previous contents for same variant_key (latest-only semantics).

11. **AC-11**: UI step detail shows scan toggle and explicit value list editor for scanned parameters.

12. **AC-12**: UI calculation overview displays total combinations with warning if > 10.

---

# Review Checklist (Pre-Implementation Code Review)

Before implementing this spec, Cursor Auto MUST locate and summarize the following in the existing codebase:

### Fingerprint & Manifest

- [ ] **Search for** `compute_step_sha` in `src/qmatsuite/calculation/hash_utils.py` and summarize:
  - What fields are stripped (meta)?
  - Is `parameter_scan` section currently present/handled?
  - Are runtime-managed keys (prefix, outdir, pseudo_dir) excluded?

- [ ] **Search for** `ManifestStepEntry` in `src/qmatsuite/calculation/manifest.py` and summarize:
  - What fields are stored per step?
  - How is `step_sha` used for skip logic?

- [ ] **Search for** `should_skip_step` and summarize the skip decision logic.

### Runtime-Managed Key Injection

- [ ] **Search for** `_inject_calculation_prefix_outdir` in `src/qmatsuite/calculation/structure_steps.py` and summarize:
  - When/where are prefix, outdir, pseudo_dir injected?
  - Are they added to step.yaml or only to the materialized input file?

- [ ] **Search for** `detect_runtime_control_keys` and confirm it identifies the correct runtime keys.

### StepDoc YAML Parsing/Serialization

- [ ] **Search for** `class StepDoc` in `src/qmatsuite/core/yamldoc.py` and summarize:
  - Current known sections (parameters, cards, species_overrides, meta, step_type)
  - Where top-level keys are validated/normalized

- [ ] **Search for** `step.yaml` file writing code paths (likely in `step_factory.py`, `yaml_io.py`) and summarize how new top-level keys would be persisted.

### Job Formation Differences

- [ ] **Search for** `class QERecipe`, `class ORCARecipe`, `class PySCFRecipe` in `src/qmatsuite/execution/recipes.py` and summarize:
  - How steps map to jobs for each engine
  - Where step lists are determined for a job

- [ ] **Search for** `JobGraph` and confirm job execution model for each engine family.

### Snapshot/Diff Archiving

- [ ] **Search for** `_create_snapshot` in `src/qmatsuite/history/run_revision.py` and summarize:
  - What files are currently snapshotted?
  - Is raw/ snapshotted?

- [ ] **Search for** any existing snapshot-diff logic in `src/qmatsuite/` and summarize if present.

- [ ] **Search for** how `outdir` is currently excluded from any file operations (grep for `outdir` patterns in calculation code).

### Risks & Ambiguities vs This Spec

- [ ] **Identify** any existing top-level keys in step.yaml that might conflict with `parameter_scan`.

- [ ] **Identify** any code that iterates over step.yaml top-level keys and might break with new key.

- [ ] **Identify** any preset inference code that reads step parameters—confirm it won't be confused by ScanRef values.

- [ ] **Identify** if any validation code currently rejects unknown types (like ScanRef dicts) in parameter values.

---

*End of Specification*

