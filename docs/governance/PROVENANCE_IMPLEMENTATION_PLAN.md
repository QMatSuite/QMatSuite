# Provenance System: Code Review & Implementation Plan

**Date:** 2026-02-05
**Companion to:** `PROVENANCE_VERSIONED_HISTORY_SPEC.md` v1.1
**Purpose:** Deep code review and phased implementation plan for Auto

---

## Part 1: Deep Code Review

### 1.1 Existing SSOT Write Choke Points

#### Primary Entry Point: `save_yaml_doc()`

**Location:** `/src/quantumvitas/core/yaml_io.py:141-244`

```python
def save_yaml_doc(
    doc: YamlDoc,
    path: Path,
    *,
    skip_journal: bool = False,
    skip_history: bool = False,
    actor: Optional[str] = None,
) -> None:
```

**Current Behavior:**
1. Captures before/after snapshots for Journal integration
2. Acquires `calc_edit_lock()` for calculation/step YAML files
3. Writes YAML via `_save_yaml_raw()` (atomic temp+rename)
4. Records in Journal (if enabled)
5. Records in Project History (if enabled)

**MUST BE MODIFIED:**
- Add required `opctx: OperationContext` parameter
- Compute diff summary before edit.lock
- Append to provenance SQLite AFTER releasing edit.lock (sequential locking)

#### Raw YAML Write

**Location:** `/src/quantumvitas/core/yaml_io.py:89-102`

```python
def _save_yaml_raw(data: dict, path: Path) -> None:
    """Save raw dict to YAML file - ONLY place using yaml.safe_dump"""
```

**Status:** Private function, only called by `save_yaml_doc()`. No changes needed.

#### Document Classes Delegating to `save_yaml_doc()`

| Class | File | Method | Status |
|-------|------|--------|--------|
| `StepDoc` | `yamldoc.py:597` | `save()` | Must pass opctx |
| `CalcDoc` | `yamldoc.py:626` | `save()` | Must pass opctx |
| `ProjectDoc` | `yamldoc.py:655` | `save()` | Must pass opctx |

**MUST BE MODIFIED:** All `save()` methods need opctx parameter propagation.

#### apply_patch() Pattern

**Location:** `/src/quantumvitas/core/yamldoc.py:358-396`

```python
def apply_patch(self, patch: dict) -> None:
    """Apply patch dict to document. MUTATES internal state."""
```

**Status:** Pure mutation, no YAML write. Callers must call `save()` afterward. No changes needed to `apply_patch()` itself.

### 1.2 Existing Locking Mechanisms

#### Edit Lock

**Location:** `/src/quantumvitas/core/locking.py:111-194`

```python
@contextlib.contextmanager
def calc_edit_lock(calc_dir: Path, fail_fast: bool = False):
```

**Characteristics:**
- Per-calculation scope: `{calc_dir}/.locks/edit.lock`
- Non-reentrant (thread-local tracking)
- Uses portalocker (cross-platform)
- Typical duration: ~100ms

**Integration Point:** Already called inside `save_yaml_doc()`. No direct changes needed to locking.py.

#### Run Lock

**Location:** `/src/quantumvitas/core/locking.py:53-109`

```python
@contextlib.contextmanager
def calc_run_lock(calc_dir: Path, fail_fast: bool = True):
```

**Status:** Long-held during run. Not involved in provenance recording.

#### No Existing Project-Level Lock

**Finding:** Only per-calculation locks exist. Need to add:
- `provenance_lock()` in new file `src/quantumvitas/provenance/locks.py`
- Lock file at `.provenance/provenance.lock`

### 1.3 Existing History/Provenance Infrastructure

#### Project History Module

**Location:** `/src/quantumvitas/history/`

| File | Purpose | Reuse Potential |
|------|---------|-----------------|
| `storage.py` | JSONL append-only events | Replace with SQLite |
| `events.py` | Event type definitions | Adapt types to OperationType |
| `run_revision.py` | Run metadata | Move to runs table |
| `digests.py` | Content hashing | Reuse for CAS |

**Key Finding:** Existing `.history/events.jsonl` should be replaced by `.provenance/provenance.db`. The history module becomes a thin wrapper over provenance.

#### Journal Module

**Location:** `/src/quantumvitas/core/journal.py`

**Purpose:** Document-level change tracking (before/after snapshots)

**Integration Point:** Journal hook in `save_yaml_doc()` (lines 201-230). This is independent of provenance. Can keep both systems:
- Journal: Per-document change tracking (optional, for debugging)
- Provenance: Project-level operation timeline (required)

#### Current Artifact Tracking

**Location:** `/src/quantumvitas/core/provenance.py`

**Purpose:** Current-only artifact provenance (which run/step produced each file)

**Status:** This is "present-world" provenance, not historical. Keep it separate. The new provenance system is "history-world" versioned.

### 1.4 Manifest and Skip Logic

**Location:** `/src/quantumvitas/calculation/manifest.py`

**Key Pattern:**
```python
@dataclass
class ManifestStepEntry:
    kind: str
    step_ulid: str
    pseudo_set_sha: str
    structure_sha: str
    step_sha: str
    done: bool = False
```

**Law P3 Enforcement:** This file MUST NOT import from `quantumvitas.provenance`. Skip logic uses only: kind, pseudo_set_sha, structure_sha, step_sha, done flag.

### 1.5 Preset Handling

#### Preset Apply Flow

**Location:** `/src/quantumvitas/presets/integration.py`

```python
# Line ~832
doc.apply_patch(qe_patch)
doc.save(step_path)  # ← Currently no opctx
```

**MUST BE MODIFIED:**
1. Caller creates `OperationContext(op=PRESET_APPLY, payload={preset_name: ...})`
2. Pass opctx to `doc.save(step_path, opctx)`

#### Select vs Apply Distinction

| Operation | YAML Write? | Provenance Event? |
|-----------|-------------|-------------------|
| `detect_presets_from_calculation()` | No | No |
| `apply_preset_options_to_step()` | Yes | Yes (PRESET_APPLY) |

**Law P8:** Only APPLY operations are recorded. Detection/selection is UI-only.

### 1.6 Runner Integration Points

**Location:** `/src/quantumvitas/calculation/runner.py`

#### Pre-Run Hook (for snapshot creation)

**Current:** `_start_history_recording()` at line 688-796

**Integration Point:** Before materialization, call:
```python
snapshot_sha = create_run_snapshot(project_root, calc_ulid, run_ulid)
record_run_start(project_root, run_ulid, calc_ulid, snapshot_sha)
```

#### Post-Step Hook (for artifact scanning)

**Current:** `update_provenance_after_step()` at line 642-655

**Integration Point:** After each step execution:
```python
scanner = ArtifactScanner(calc_raw_dir, policy)
scanner.capture_baseline()  # PRE-STEP
# ... execute step ...
changes = scanner.scan_changes()  # POST-STEP
artifact_sha = ingest_artifacts(project_root, changes)
record_run_step(project_root, run_ulid, step_ulid, index, artifact_sha=artifact_sha)
```

#### Post-Run Hook (for run completion)

**Current:** `_complete_history_recording()` at line 798-871

**Integration Point:**
```python
record_run_complete(project_root, run_ulid, status, finished_at)
```

---

## Part 2: Integration Risk Analysis

### 2.1 Risk: Creating "Two Systems"

**Symptom:** Duplicate event recording in both `.history/` and `.provenance/`

**Avoidance:**
1. Phase 1 removes or disables existing history recording in `save_yaml_doc()`
2. All event recording goes through new provenance module
3. Gate test: No writes to `.history/events.jsonl` after migration

### 2.2 Risk: Duplicate Artifact Scanners

**Symptom:** Handlers or engines implementing their own artifact scanning

**Avoidance:**
1. Gate test: No scanner imports in `drivers/*/handler.py`
2. Single scanner class in `src/quantumvitas/provenance/scanner.py`
3. Runner is the ONLY caller of scanner methods

### 2.3 Risk: Direct YAML Writes Bypassing Choke Point

**Symptom:** Code using `yaml.safe_dump()` directly instead of `save_yaml_doc()`

**Avoidance:**
1. Gate test: Search for `yaml.safe_dump` outside `yaml_io.py`
2. Gate test: Search for `path.write_text` with `.yaml` extensions
3. KERNEL_EXCEPTIONS.md EXC-004 already whitelists acceptable exceptions

### 2.4 Risk: Nested Lock Acquisition

**Symptom:** Deadlock when `edit.lock` held while acquiring `provenance.lock`

**Avoidance:**
1. Sequential locking: release edit.lock BEFORE acquiring provenance.lock
2. Gate test: Code inspection of `save_yaml_doc()` structure
3. Concurrency test: Multi-threaded writers

### 2.5 Risk: Facade/Daemon Bypassing Kernel Public Methods

**Symptom:** Daemon calling `save_yaml_doc()` directly instead of through kernel methods

**Avoidance:**
1. Existing API_CONSTITUTION.md H9: Frontend no YAML write
2. Existing gate test: `test_frontend_no_yaml_write.py`
3. Facade creates opctx and passes to kernel; kernel calls `save_yaml_doc()`

---

## Part 3: Where to Integrate (File Map)

### 3.1 New Files to Create

```
src/quantumvitas/provenance/
├── __init__.py           # Package exports
├── opctx.py              # OperationContext, OperationType, ActorType, ScopeType
├── schema.py             # SQLite schema DDL, schema version management
├── db.py                 # ProvenanceDB class, connection management
├── locks.py              # provenance_lock(), gc_lock()
├── cas.py                # CAS class, store/retrieve/exists
├── scanner.py            # ArtifactScanner, ArtifactPolicy, ScannedFile
├── recording.py          # record_operation_event(), record_run_*()
├── snapshots.py          # create_run_snapshot(), restore_from_snapshot()
└── query.py              # query_operations(), query_runs(), get_run_steps()
```

### 3.2 Files to Modify

| File | Changes |
|------|---------|
| `src/quantumvitas/core/yaml_io.py` | Add opctx parameter, sequential lock pattern, provenance recording |
| `src/quantumvitas/core/yamldoc.py` | Add opctx to `StepDoc.save()`, `CalcDoc.save()`, `ProjectDoc.save()` |
| `src/quantumvitas/presets/integration.py` | Create opctx for preset apply, pass to save |
| `src/quantumvitas/calculation/runner.py` | Add pre-run snapshot, post-step scanning, run recording |
| `src/quantumvitas/drivers/*/recipe.py` | Add `ARTIFACT_POLICY` constant |

### 3.3 Files to NOT Modify

| File | Reason |
|------|--------|
| `src/quantumvitas/core/locking.py` | Keep existing edit.lock/run.lock unchanged |
| `src/quantumvitas/calculation/manifest.py` | Must not import provenance (Law P3) |
| `src/quantumvitas/drivers/*/handler.py` | Must not import scanner (Law P9) |
| `runner.py` executor logic | Only add hooks, don't change execution flow |

---

## Part 4: Phased Implementation Plan

### Phase 0: Scaffolding + Gate Tests

**Scope:** Create package structure and blocking gate tests BEFORE any implementation.

**New Files:**
```
src/quantumvitas/provenance/__init__.py
src/quantumvitas/provenance/opctx.py
src/quantumvitas/provenance/errors.py
tests/gates/test_provenance_opctx_required.py
tests/gates/test_provenance_independence.py
tests/gates/test_provenance_skip_isolation.py
tests/gates/test_no_duplicate_scanners.py
```

**Implementation:**

1. Create `OperationContext` dataclass with all fields
2. Create `OperationType`, `ActorType`, `ScopeType` enums
3. Create `OperationContextRequiredError` exception
4. Create gate tests (they will FAIL until Phase 1)

**Gate Tests (Phase 0):**
```python
# test_provenance_opctx_required.py
def test_save_yaml_doc_without_opctx_raises():
    # This test will FAIL until Phase 1 modifies save_yaml_doc()
    pass  # Placeholder

# test_provenance_skip_isolation.py
def test_manifest_no_provenance_imports():
    # AST scan of manifest.py for provenance imports
    # This test should PASS immediately (no provenance imports yet)
    pass

# test_no_duplicate_scanners.py
def test_handler_no_scanner_import():
    # AST scan of all handler.py for scanner imports
    # This test should PASS immediately (no scanner yet)
    pass
```

**Acceptance Criteria:**
- [ ] `src/quantumvitas/provenance/` package exists
- [ ] `OperationContext` dataclass is importable
- [ ] Gate test files exist (may fail or be skipped)
- [ ] All existing tests still pass

---

### Phase 1: SQLite Provenance Store + OpCtx Enforcement

**Scope:** Modify `save_yaml_doc()` to require opctx and record operations.

**New Files:**
```
src/quantumvitas/provenance/schema.py
src/quantumvitas/provenance/db.py
src/quantumvitas/provenance/locks.py
src/quantumvitas/provenance/recording.py
```

**Modifications:**

1. **yaml_io.py:**
   ```python
   def save_yaml_doc(
       doc: YamlDoc,
       path: Path,
       opctx: OperationContext,  # NEW: Required
       *,
       skip_journal: bool = False,
       skip_history: bool = False,  # Deprecated, remove later
   ) -> None:
       if opctx is None:
           raise OperationContextRequiredError(...)

       before = doc.get_snapshot()
       after = doc.to_dict()
       diff_summary = compute_diff_summary(before, after)

       # YAML write with edit.lock
       calc_dir = find_calc_dir_from_path(path)
       if calc_dir:
           with calc_edit_lock(calc_dir):
               _save_yaml_raw(after, path)
       else:
           _save_yaml_raw(after, path)

       # ─── edit.lock released ───

       # Provenance recording (sequential, not nested)
       try:
           project_root = find_project_root(path)
           if project_root:
               record_operation_event(project_root, opctx, diff_summary)
       except ProvenanceError as e:
           logger.warning(f"Provenance recording failed: {e}")
   ```

2. **yamldoc.py:**
   ```python
   class StepDoc(YamlDoc):
       def save(self, path: Path, opctx: OperationContext) -> None:
           from quantumvitas.core.yaml_io import save_yaml_doc
           save_yaml_doc(self, path, opctx)
   ```

3. **All callers of save():** Must be updated to pass opctx. This is a LARGE change affecting:
   - `presets/integration.py`
   - `calculation/calculation.py`
   - `calculation/step.py`
   - Test fixtures

**Migration Strategy for Callers:**
- Add `opctx` parameter with a temporary default:
  ```python
  def save(self, path: Path, opctx: Optional[OperationContext] = None) -> None:
      if opctx is None:
          opctx = OperationContext(
              op=OperationType.CUSTOM,
              actor=ActorType.SYSTEM,
              scope=ScopeType.STEP,
              source="legacy_save_without_opctx",
              payload={},
          )
      ...
  ```
- Once all callers updated, remove default and make required

**Tests:**
```python
# tests/gates/test_provenance_opctx_required.py
def test_save_yaml_doc_without_opctx_raises():
    with pytest.raises(OperationContextRequiredError):
        save_yaml_doc(doc, path)  # No opctx

def test_save_yaml_doc_with_opctx_succeeds():
    opctx = OperationContext(...)
    save_yaml_doc(doc, path, opctx)
    assert path.exists()

# tests/integration/test_provenance_operations.py
def test_step_update_creates_operation(tmp_project):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")

    db = open_provenance_db(tmp_project.root)
    ops = db.execute("SELECT * FROM operations").fetchall()
    assert len(ops) >= 1
```

**Acceptance Criteria:**
- [ ] `save_yaml_doc()` requires opctx (gate test passes)
- [ ] Operations table populated on YAML writes
- [ ] Sequential locking implemented (provenance.lock after edit.lock release)
- [ ] All existing tests pass (with opctx added to fixtures)

---

### Phase 2: Run Recording + Normalized run_steps

**Scope:** Integrate with Runner to record runs and per-step execution.

**New Files:**
```
src/quantumvitas/provenance/snapshots.py
```

**Modifications:**

1. **runner.py:**
   ```python
   def run(self, ...):
       run_ulid = generate_ulid()

       # PRE-RUN: Create snapshot and record run_start
       try:
           snapshot_sha = create_run_snapshot(project_root, calc_ulid, run_ulid)
           record_run_start(project_root, run_ulid, calc_ulid, snapshot_sha)
       except ProvenanceError:
           logger.warning("Failed to record run start")

       # ... existing materialization and execution ...

       for job in job_graph:
           # Execute step
           result = execute(job)

           # POST-STEP: Record step result
           try:
               record_run_step(
                   project_root, run_ulid, step_ulid, step_index,
                   status=result.status,
                   started_at=result.started_at,
                   finished_at=result.finished_at,
               )
           except ProvenanceError:
               logger.warning("Failed to record run step")

       # POST-RUN: Record completion
       try:
           record_run_complete(project_root, run_ulid, final_status, finished_at)
       except ProvenanceError:
           logger.warning("Failed to record run complete")
   ```

2. **snapshots.py:**
   ```python
   def create_run_snapshot(project_root: Path, calc_ulid: str, run_ulid: str) -> str:
       """Collect YAML files and store in CAS as Tier-0 snapshot."""
       calc_dir = project_root / "calculations" / calc_ulid

       snapshot = {
           "version": 1,
           "type": "run_snapshot",
           "run_ulid": run_ulid,
           "calc_ulid": calc_ulid,
           "timestamp": now_iso8601(),
           "files": {},
       }

       # Collect calculation.yaml
       calc_yaml = calc_dir / "calculation.yaml"
       if calc_yaml.exists():
           snapshot["files"]["calculation.yaml"] = calc_yaml.read_text()

       # Collect step_*.yaml
       for step_file in calc_dir.glob("step_*.yaml"):
           snapshot["files"][step_file.name] = step_file.read_text()

       # Store in CAS
       content = json.dumps(snapshot).encode()
       return cas_store(project_root, content, tier=0)
   ```

**Tests:**
```python
# tests/integration/test_provenance_run.py
def test_run_creates_runs_row(tmp_project, mock_engine):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")

    runner = Runner(calc)
    run_ulid = runner.run()

    db = open_provenance_db(tmp_project.root)
    run_row = db.execute(
        "SELECT * FROM runs WHERE run_ulid = ?", (run_ulid,)
    ).fetchone()

    assert run_row is not None
    assert run_row["status"] == "success"
    assert run_row["snapshot_sha"] is not None

def test_run_steps_normalized(tmp_project, mock_engine):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")
    calc.add_step("bands", step_type_spec="qe_bands")

    runner = Runner(calc)
    run_ulid = runner.run()

    db = open_provenance_db(tmp_project.root)
    steps = db.execute(
        "SELECT * FROM run_steps WHERE run_ulid = ? ORDER BY step_index",
        (run_ulid,)
    ).fetchall()

    assert len(steps) == 2
    assert steps[0]["step_index"] == 0
    assert steps[1]["step_index"] == 1
```

**Acceptance Criteria:**
- [ ] `runs` table populated on run start/complete
- [ ] `run_steps` table populated per step (normalized, not JSON blob)
- [ ] Snapshot stored in CAS with tier=0
- [ ] All existing tests pass

---

### Phase 3: Artifact Scanning + Blacklist Policy

**Scope:** Implement artifact scanner and integrate with engine recipes.

**New Files:**
```
src/quantumvitas/provenance/scanner.py
src/quantumvitas/provenance/policy.py
```

**Modifications:**

1. **scanner.py:** (Full implementation from spec)

2. **policy.py:**
   ```python
   @dataclass(frozen=True, slots=True)
   class ArtifactPolicy:
       mode: Literal["blacklist", "whitelist"] = "blacklist"
       blacklist_dirs: List[str] = field(default_factory=list)
       blacklist_patterns: List[str] = field(default_factory=list)
       force_capture_patterns: List[str] = field(default_factory=list)
       tier3_patterns: List[str] = field(default_factory=list)

       def should_capture(self, rel_path: str, size_bytes: int) -> Tuple[bool, int, Optional[str]]:
           ...
   ```

3. **Each engine recipe (e.g., `drivers/qe/recipe.py`):**
   ```python
   class QERecipe(BaseRecipe):
       ARTIFACT_POLICY = ArtifactPolicy(
           mode="blacklist",
           blacklist_dirs=["outdir/"],
           blacklist_patterns=["*.wfc*"],
           tier3_patterns=["*.save/"],
           force_capture_patterns=["*.out", "*.xml"],
       )

       def get_artifact_policy(self) -> ArtifactPolicy:
           return self.ARTIFACT_POLICY
   ```

4. **runner.py:** Add pre-step/post-step scanning:
   ```python
   for job in job_graph:
       policy = recipe.get_artifact_policy()
       scanner = ArtifactScanner(calc_raw_dir, policy)

       # PRE-STEP
       scanner.capture_baseline()

       # Execute
       result = execute(job)

       # POST-STEP
       changes = scanner.scan_changes()
       if changes:
           artifact_sha = ingest_artifacts(project_root, changes)
           record_run_step(..., artifact_collection_sha=artifact_sha)
   ```

**Tests:**
```python
# tests/integration/test_provenance_artifacts.py
def test_artifact_scan_captures_outputs(tmp_project, mock_engine):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Create mock output
    raw_dir = calc.dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "scf.out").write_text("output")

    runner = Runner(calc)
    run_ulid = runner.run()

    db = open_provenance_db(tmp_project.root)
    step = db.execute(
        "SELECT * FROM run_steps WHERE run_ulid = ?", (run_ulid,)
    ).fetchone()

    assert step["artifact_collection_sha"] is not None

    # Verify artifact in CAS
    collection = cas_retrieve_json(tmp_project.root, step["artifact_collection_sha"])
    paths = [a["relative_path"] for a in collection["artifacts"]]
    assert "scf.out" in paths

def test_blacklist_excludes_outdir(tmp_project, mock_engine):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")

    raw_dir = calc.dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / "scf.out").write_text("output")
    (raw_dir / "outdir").mkdir()
    (raw_dir / "outdir" / "huge_file").write_text("x" * 10000000)

    runner = Runner(calc)
    run_ulid = runner.run()

    # Verify outdir excluded
    db = open_provenance_db(tmp_project.root)
    step = db.execute(
        "SELECT * FROM run_steps WHERE run_ulid = ?", (run_ulid,)
    ).fetchone()

    collection = cas_retrieve_json(tmp_project.root, step["artifact_collection_sha"])
    paths = [a["relative_path"] for a in collection["artifacts"]]
    assert "scf.out" in paths
    assert not any("outdir" in p for p in paths if collection["artifacts"][paths.index(p)]["captured"])
```

**Acceptance Criteria:**
- [ ] ArtifactScanner captures baseline and detects changes
- [ ] Blacklist policy excludes QE outdir by default
- [ ] Artifact collections stored in CAS with tier=2/3
- [ ] `run_steps.artifact_collection_sha` populated
- [ ] Gate test: handlers don't import scanner

---

### Phase 4: CAS + Snapshot Restore

**Scope:** Complete CAS implementation and rollback functionality.

**New Files:**
```
src/quantumvitas/provenance/cas.py
src/quantumvitas/provenance/restore.py
```

**Implementation:**

1. **cas.py:**
   ```python
   class CAS:
       def __init__(self, project_root: Path):
           self.root = project_root / ".provenance" / ".cas"

       def store(self, content: bytes, tier: int) -> str:
           sha = hashlib.sha256(content).hexdigest()
           obj_path = self.root / "objects" / sha[:2] / sha[2:]

           if obj_path.exists():
               return sha  # Dedup

           # Atomic write via temp
           tmp_path = self.root / "tmp" / f"{sha}.tmp"
           tmp_path.parent.mkdir(parents=True, exist_ok=True)
           tmp_path.write_bytes(content)
           obj_path.parent.mkdir(parents=True, exist_ok=True)
           tmp_path.rename(obj_path)

           # Record in DB
           db = open_provenance_db(self.project_root)
           db.execute(
               "INSERT INTO cas_objects (sha256, tier, size_bytes) VALUES (?, ?, ?)",
               (sha, tier, len(content))
           )

           return sha

       def retrieve(self, sha: str) -> bytes:
           obj_path = self.root / "objects" / sha[:2] / sha[2:]
           if not obj_path.exists():
               raise SnapshotNotFoundError(sha)
           return obj_path.read_bytes()

       def exists(self, sha: str) -> bool:
           return (self.root / "objects" / sha[:2] / sha[2:]).exists()
   ```

2. **restore.py:**
   ```python
   def restore_from_snapshot(project_root: Path, snapshot_sha: str, opctx: OperationContext):
       """Restore SSOT files from a run snapshot."""
       cas = CAS(project_root)
       snapshot = json.loads(cas.retrieve(snapshot_sha))

       calc_ulid = snapshot["calc_ulid"]
       calc_dir = project_root / "calculations" / calc_ulid

       for filename, content in snapshot["files"].items():
           file_path = calc_dir / filename
           doc = YamlDoc(yaml.safe_load(content))
           save_yaml_doc(doc, file_path, opctx)
   ```

**Tests:**
```python
# tests/gates/test_cas_integrity.py
def test_cas_content_addressed(tmp_project):
    cas = CAS(tmp_project.root)
    content = b"test content"

    sha1 = cas.store(content, tier=0)
    sha2 = cas.store(content, tier=0)

    assert sha1 == sha2
    assert cas.exists(sha1)

def test_cas_immutable(tmp_project):
    cas = CAS(tmp_project.root)
    content = b"original"
    sha = cas.store(content, tier=0)

    # Verify content unchanged
    assert cas.retrieve(sha) == content

# tests/integration/test_provenance_rollback.py
def test_restore_from_run_snapshot(tmp_project, mock_engine):
    calc = tmp_project.create_calculation("test")
    calc.add_step("scf", step_type_spec="qe_scf")

    # Run and get snapshot
    runner = Runner(calc)
    run_ulid = runner.run()

    db = open_provenance_db(tmp_project.root)
    run = db.execute("SELECT * FROM runs WHERE run_ulid = ?", (run_ulid,)).fetchone()
    snapshot_sha = run["snapshot_sha"]

    # Modify the step
    calc.steps[0].update({"parameters": {"ecutwfc": 100}}, opctx)

    # Restore
    restore_opctx = OperationContext(op=OperationType.RESTORE, ...)
    restore_from_snapshot(tmp_project.root, snapshot_sha, restore_opctx)

    # Verify restored
    calc2 = tmp_project.load_calculation(calc.ulid)
    # Original value restored
```

**Acceptance Criteria:**
- [ ] CAS store/retrieve/exists working
- [ ] Content-addressed deduplication working
- [ ] Restore from snapshot writes files via save_yaml_doc with RESTORE opctx
- [ ] Gate tests for CAS integrity pass

---

### Phase 5: Cleanup + Migration

**Scope:** Remove legacy history, finalize migration path.

**Changes:**

1. Remove or deprecate:
   - `skip_history` parameter in `save_yaml_doc()`
   - Legacy `.history/events.jsonl` recording

2. Add migration:
   ```python
   def migrate_legacy_history(project_root: Path):
       """One-time migration from .history to .provenance."""
       legacy_dir = project_root / ".history"
       if not legacy_dir.exists():
           return

       # Read legacy events
       events_file = legacy_dir / "events.jsonl"
       if events_file.exists():
           # Convert to new format and insert
           ...

       # Rename legacy dir
       legacy_dir.rename(legacy_dir.with_suffix(".legacy"))
   ```

3. Update governance README gate inventory

**Tests:**
```python
def test_legacy_history_migration(tmp_project):
    # Create legacy .history
    legacy = tmp_project.root / ".history"
    legacy.mkdir()
    (legacy / "events.jsonl").write_text('{"type": "baseline"}\n')

    # Trigger migration
    ensure_provenance_initialized(tmp_project.root)

    # Verify migrated
    assert (tmp_project.root / ".provenance").exists()
    assert (tmp_project.root / ".history.legacy").exists()
```

**Acceptance Criteria:**
- [ ] Legacy history code removed or deprecated
- [ ] Migration path for existing projects
- [ ] All gate tests pass
- [ ] Governance README updated with final gate list

---

## Part 5: Test Summary

### Gate Tests (CI-blocking)

| Test File | Law | Status After Phase |
|-----------|-----|-------------------|
| `test_provenance_opctx_required.py` | P2 | Phase 1 |
| `test_provenance_independence.py` | P1 | Phase 1 |
| `test_provenance_skip_isolation.py` | P3 | Phase 0 (immediate) |
| `test_lock_ordering.py` | P6 | Phase 1 |
| `test_cas_integrity.py` | P5 | Phase 4 |
| `test_no_duplicate_scanners.py` | P9 | Phase 0 (immediate) |

### Integration Tests

| Test File | Feature | Status After Phase |
|-----------|---------|-------------------|
| `test_provenance_operations.py` | Operation recording | Phase 1 |
| `test_provenance_preset.py` | Preset apply events | Phase 1 |
| `test_provenance_run.py` | Run/step recording | Phase 2 |
| `test_provenance_artifacts.py` | Artifact scanning | Phase 3 |
| `test_provenance_rollback.py` | Snapshot restore | Phase 4 |
| `test_provenance_concurrent.py` | Concurrency | Phase 1 |
| `test_provenance_failure_graceful.py` | Graceful degradation | Phase 1 |

---

*End of Implementation Plan*
