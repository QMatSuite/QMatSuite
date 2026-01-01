# Journal System Design

## Overview

The Journal system provides **append-only change tracking** for all YAML document mutations in QMatSuite. It enables traceability by recording before/after snapshots at the Doc boundary.

**Design Principle:** YamlDoc guarantees correctness. Journal guarantees traceability. UI guarantees visibility.

## What Journal Records

Every save of a YAML document through `save_yaml_doc()` produces one `JournalEntry`:

```yaml
JournalEntry:
  id: ULID                    # Unique identifier for this entry
  target_ulid: str            # ULID of the document (from meta.id)
  doc_type: str               # "step" | "calc" | "project" | "unknown"
  timestamp: str              # ISO 8601 UTC timestamp
  before: dict                # Deep copy of document before changes
  after: dict                 # Deep copy of document after changes
  summary: str                # Human-readable change summary
  path: str | null            # File path (for debugging)
```

### Document Types Tracked

| Doc Type | Source | When Recorded |
|----------|--------|---------------|
| `step` | StepDoc.save() | Preset application, parameter edits |
| `calc` | CalcDoc.save() | Calculation metadata changes |
| `project` | ProjectDoc.save() | Project settings changes |

## Where Journal Hooks

**Single Hook Point:** `src/quantumvitas/core/yaml_io.py::save_yaml_doc()`

```python
# yaml_io.py
def save_yaml_doc(doc: YamlDoc, path: Path, *, skip_journal: bool = False) -> None:
    before = doc.get_snapshot()  # Initial state
    after = doc.to_dict()        # Current state
    
    _save_yaml_raw(after, path)
    doc.commit_changes()
    
    # === JOURNAL HOOK POINT ===
    if not skip_journal and before is not None:
        journal = get_journal()
        if journal.enabled:
            entry = JournalEntry.create(...)
            journal.record_change(entry)
```

All `YamlDoc.save()` methods delegate to `save_yaml_doc()`:
- `StepDoc.save()` → `save_yaml_doc()`
- `CalcDoc.save()` → `save_yaml_doc()`
- `ProjectDoc.save()` → `save_yaml_doc()`

**No other code paths record journal entries.** Business logic does not compute diffs.

## What Journal Does NOT Do (Yet)

| Feature | Status | Notes |
|---------|--------|-------|
| Undo/Redo | Not implemented | Would require applying patches |
| Diff computation | Not implemented | UI shows raw before/after |
| Compression | Not implemented | JSONL is human-readable |
| Rotation/Archiving | Not implemented | Add when files grow large |
| Real-time sync | Not implemented | Append-only is file-based |

## Storage

### Location

```
~/.quantumvitas/journal/journal.jsonl
```

### Format

Append-only JSONL (one JSON object per line):

```json
{"id":"01ABC...","target_ulid":"01STEP...","doc_type":"step","timestamp":"2026-01-01T12:00:00Z","before":{...},"after":{...},"summary":"Saved step (+1, ~2 keys)","path":"/path/to/step.yaml"}
```

### Why JSONL?

- **Simple:** No database schema, no migrations
- **Append-only:** Safe for concurrent writes
- **Human-readable:** Easy to debug with `cat`, `jq`
- **Portable:** No external dependencies

## API

### Journal Class

```python
from quantumvitas.core.journal import Journal, get_journal

# Get global journal
journal = get_journal()

# Record a change (typically done by save_yaml_doc)
journal.record_change(entry)

# List entries (most recent first)
entries = journal.list_entries()
entries = journal.list_entries(target_ulid="01STEP...")
entries = journal.list_entries(doc_type="step")
entries = journal.list_entries(limit=100)

# Get specific entry
entry = journal.get_entry("01ENTRY...")

# Enable/disable
journal.disable()  # Stop recording
journal.enable()   # Resume recording
```

### JournalEntry

```python
from quantumvitas.core.journal import JournalEntry

entry = JournalEntry.create(
    target_ulid="01STEP123",
    doc_type="step",
    before={"a": 1},
    after={"a": 2},
    summary="Changed parameter a",
    path=Path("/path/to/file.yaml"),
)

# Serialize
data = entry.to_dict()
json_str = json.dumps(data)

# Deserialize
entry = JournalEntry.from_dict(data)
```

## Reference Leakage Prevention

Journal entries use deep copies at all boundaries:

1. **At creation:** `JournalEntry.create()` deep copies `before` and `after`
2. **At hook point:** `save_yaml_doc()` gets `doc.get_snapshot()` (deep copy) and `doc.to_dict()` (deep copy)
3. **At retrieval:** Reading from disk naturally creates new objects

This ensures:
- Mutating a doc after save doesn't affect recorded entry
- Mutating retrieved entry doesn't affect stored data

## Testing

### Running Journal Tests

```bash
pytest tests/unit/test_journal.py -v
```

### Key Test Cases

- `test_save_doc_produces_journal_entry`: Saving a Doc produces exactly one JournalEntry
- `test_before_after_differ`: before/after correctly capture mutations
- `test_journal_entry_no_reference_leakage`: No reference leakage into journal

### Testing with Disabled Journal

```python
from quantumvitas.core.journal import get_journal, set_journal, Journal

# In tests, use a temp directory
test_journal = Journal(journal_dir=tmp_path / "journal")
set_journal(test_journal)

# ... run test ...

test_journal.clear()
reset_journal()
```

## UI Access

A minimal debug view is available at:

**Settings → Advanced → Journal History**

Features:
- Scrollable list of recent entries
- Columns: timestamp, target ULID, doc type, summary
- Click to view raw JSON diff (before vs after)
- Read-only, for debugging only

## Future Extensions

### Undo/Redo

Hook point is ready. Implementation would:
1. Retrieve entry by ID
2. Apply `entry.before` as a patch to revert
3. Or apply `entry.after` to redo

### Compression

When journal file grows large:
1. Rotate old entries to `journal.YYYYMMDD.jsonl.gz`
2. Keep recent entries in active file

### Filtering/Search

Add methods like:
```python
journal.list_entries(
    since=datetime(...),
    until=datetime(...),
    search="ecutwfc",
)
```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic                           │
│  (presets, detector, compiler, API handlers)                │
└────────────────────────────┬────────────────────────────────┘
                             │ doc.set() / doc.apply_patch()
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      YamlDoc                                │
│  - Mutation containment                                     │
│  - No reference leakage                                     │
│  - Snapshot management                                      │
└────────────────────────────┬────────────────────────────────┘
                             │ doc.save() → save_yaml_doc()
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    yaml_io.py                               │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  save_yaml_doc()                                     │  │
│  │    1. Capture before/after                           │  │
│  │    2. Write to disk                                  │  │
│  │    3. ═══ JOURNAL HOOK ═══                          │  │
│  │    4. Commit changes                                 │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                      Journal                                │
│  - Append-only JSONL storage                               │
│  - ULID-based identification                               │
│  - No business logic                                        │
└─────────────────────────────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                   Debug UI (Optional)                       │
│  - Read-only history view                                   │
│  - JSON diff display                                        │
└─────────────────────────────────────────────────────────────┘
```

## Migration Notes

### From Pre-Journal Codebase

No migration needed. Journal is opt-in and doesn't affect existing data.

### Disabling Journal

```python
from quantumvitas.core.journal import get_journal

# Disable globally
get_journal().disable()

# Or skip for specific saves
save_yaml_doc(doc, path, skip_journal=True)
```

