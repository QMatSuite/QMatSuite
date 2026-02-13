# Project History Feature - Code Review Report & Implementation Plan

**Date:** January 6, 2026  
**Phase:** 0 (Code Review Only - No Implementation)

---

## Table of Contents

1. [Architecture Map](#1-architecture-map)
2. [YAML/JSON I/O Abstraction](#2-yamljson-io-abstraction)
3. [Project/Calc/Step Model Boundary](#3-projectcalcstep-model-boundary)
4. [Run Initiation Points](#4-run-initiation-points)
5. [Preset Compilation Flow](#5-preset-compilation-flow)
6. [Proposed History Persistence Design](#6-proposed-history-persistence-design)
7. [UI/Frontend Integration Points](#7-uifrontend-integration-points)
8. [Implementation Plan (Phased TODOs)](#8-implementation-plan-phased-todos)
9. [Risk Assessment & Mitigations](#9-risk-assessment--mitigations)

---

## 1. Architecture Map

### High-Level Module Structure

```
QMatSuite
├── src/quantumvitas/
│   ├── core/               # Core infrastructure
│   │   ├── yaml_io.py      # **CRITICAL**: Single YAML commit point with Journal hook
│   │   ├── yamldoc.py      # YamlDoc/StepDoc/CalcDoc/ProjectDoc wrappers
│   │   ├── journal.py      # **EXISTING**: Append-only change tracking (JSONL)
│   │   ├── models.py       # Project/Calc/Step dataclass models
│   │   ├── resolution.py   # Resource registry & ULID resolution
│   │   └── resources.py    # ResourceMeta, ULID generation
│   │
│   ├── calculation/        # Calculation runtime
│   │   ├── calculation.py  # Calculation class loading from YAML
│   │   ├── runner.py       # **HOOK POINT**: CalculationRunner.run() orchestration
│   │   └── step.py         # Step execution
│   │
│   ├── daemon/             # JSON-RPC daemon for GUI
│   │   ├── server.py       # **HOOK POINT**: run_calculation/run_step RPC handlers
│   │   └── jobs.py         # JobManager for background execution
│   │
│   ├── presets/            # Preset detection & compilation
│   │   ├── compiler.py     # **HOOK POINT**: compile_* functions
│   │   ├── integration.py  # apply_presets_to_step() - modifies step YAML
│   │   └── detector.py     # detect_* functions (read-only)
│   │
│   ├── workflow/           # Step creation
│   │   └── step_factory.py # **HOOK POINT**: save_step_doc() → yaml_io
│   │
│   ├── project/            # Project model
│   │   ├── model.py        # Project dataclass, open/save
│   │   └── storage.py      # ProjectStorage utility
│   │
│   └── api.py              # QVService: high-level API (CLI + daemon use)
│
└── gui/src/                # Electron GUI
    ├── App.tsx             # Main app with view routing
    ├── components/
    │   ├── layout/
    │   │   └── Sidebar.tsx # **UI HOOK**: Navigation tabs
    │   └── settings/
    │       └── JournalHistoryPanel.tsx # **EXISTING**: Debug history view
    └── hooks/
        └── useQVClient.ts  # Daemon RPC client
```

### Data Flow Boundaries

```
                        ┌─────────────────────────────────────────────────┐
                        │                  GUI (Electron)                  │
                        │  App.tsx → Sidebar → {Home,Structures,Calcs,..} │
                        └───────────────────────┬─────────────────────────┘
                                                │ JSON-RPC (stdio)
                        ┌───────────────────────▼─────────────────────────┐
                        │             daemon/server.py (QVDaemon)          │
                        │  ├─ RPC handlers (_handle_run_calculation, etc.) │
                        │  └─ JobManager (ThreadPoolExecutor)              │
                        └───────────────────────┬─────────────────────────┘
                                                │ QVService API calls
                        ┌───────────────────────▼─────────────────────────┐
                        │              api.py (QVService)                  │
                        │  Static methods: run_calculation, apply_presets  │
                        └───────────────────────┬─────────────────────────┘
                                                │
          ┌─────────────────────────────────────┼─────────────────────────────────────┐
          │                                     │                                     │
          ▼                                     ▼                                     ▼
  ┌───────────────────┐               ┌───────────────────┐               ┌───────────────────┐
  │ calculation/      │               │ presets/          │               │ workflow/         │
  │ runner.py         │               │ integration.py    │               │ step_factory.py   │
  │ (CalculationRunner)│              │ compiler.py       │               │ (save_step_doc)   │
  └─────────┬─────────┘               └─────────┬─────────┘               └─────────┬─────────┘
            │                                   │                                   │
            │                                   │                                   │
            └───────────────────────────────────┼───────────────────────────────────┘
                                                │
                        ┌───────────────────────▼─────────────────────────┐
                        │           core/yaml_io.py                        │
                        │  save_yaml_doc() ─── SINGLE COMMIT POINT ───     │
                        │       │                                          │
                        │       ▼                                          │
                        │  core/journal.py                                 │
                        │  Journal.record_change() → ~/.quantumvitas/...   │
                        └─────────────────────────────────────────────────┘
```

---

## 2. YAML/JSON I/O Abstraction

### Key Classes and Files

| File | Class/Function | Role |
|------|----------------|------|
| `core/yaml_io.py` | `save_yaml_doc()` | **SINGLE COMMIT POINT** - All YAML saves go through here. Journal hook integrated. |
| `core/yaml_io.py` | `load_yaml_doc()` | Load YAML into Doc instances |
| `core/yaml_io.py` | `_save_yaml_raw()` | Internal: only place `yaml.safe_dump` should be used |
| `core/yamldoc.py` | `YamlDoc` | Base class with mutation containment, snapshot support |
| `core/yamldoc.py` | `StepDoc` | Step-specific wrapper (QE normalization, access control) |
| `core/yamldoc.py` | `CalcDoc` | Calculation document wrapper |
| `core/yamldoc.py` | `ProjectDoc` | Project document wrapper |

### Hook Points for History

```python
# core/yaml_io.py:117-182
def save_yaml_doc(doc: YamlDoc, path: Path, *, skip_journal: bool = False) -> None:
    """
    This is the SINGLE COMMIT POINT for all YAML changes.
    Journal is hooked here - no other place records changes.
    """
    # Capture before/after for Journal
    before = doc.get_snapshot()
    after = doc.to_dict()
    
    # ... write to disk ...
    
    # Record in Journal
    if not skip_journal and before is not None:
        # Current Journal records JournalEntry with before/after snapshots
        # HISTORY EXTENSION: Add structured diff events here
```

### Remaining Direct `yaml.safe_dump` Usage (Migration Needed)

Found **17+ files** still using direct `yaml.safe_dump`:

| File | Context | Migration Priority |
|------|---------|-------------------|
| `api.py:289` | `export_project_snapshot()` | Medium - snapshot export |
| `api.py:984` | Calculation YAML write | **HIGH** - should use CalcDoc |
| `cli/main.py` (7 locations) | Project/calc/step writes | **HIGH** - should use yaml_io |
| `project/snapshot.py:825` | Step file write | **HIGH** |
| `core/project_utils.py:60` | `write_project_config()` | **HIGH** |
| `core/models.py:783` | `save_project()` | **HIGH** |
| `calculation/importers.py` | Step spec writes | Medium |
| `legacy/migrate.py` | Migration scripts | Low |
| `core/templates.py` | Template instantiation | Medium |

**Recommendation:** Before Phase 1, create a tech debt ticket to migrate all direct `yaml.safe_dump` to `save_yaml_doc()` flow.

### Existing Journal System

```python
# core/journal.py - EXISTING implementation

@dataclass
class JournalEntry:
    id: str           # ULID for this entry
    target_ulid: str  # ULID of target document (from meta.id)
    doc_type: str     # "step", "calc", "project", "unknown"
    timestamp: str    # ISO 8601
    before: dict      # Full snapshot before
    after: dict       # Full snapshot after
    summary: str      # Human-readable summary
    path: str         # File path (optional)

class Journal:
    # Storage: ~/.quantumvitas/journal/journal.jsonl
    # Append-only JSONL format
```

**Finding:** The Journal system already provides before/after snapshots per save. However:
1. It stores **full documents**, not structured diffs
2. It's global (not per-project)
3. No run/execution event tracking
4. No intention/preset metadata

---

## 3. Project/Calc/Step Model Boundary

### Project Root Layout Convention

```
<project_root>/
├── project.qv.yml          # Project manifest (structure/calc registry)
├── structures/
│   └── <slug>.json         # Structure files with __qv_meta__
├── calculations/
│   └── <slug>/             # Calculation directory (= workdir)
│       ├── calculation.yaml    # Calculation manifest
│       ├── steps/
│       │   └── <slug>.step.yaml
│       └── raw/            # Working directory (QE I/O)
│           ├── scf.in
│           ├── scf.out
│           └── ...
├── pseudo/                 # Project-local pseudopotentials
│   └── *.UPF
└── settings.yaml           # Optional project settings
```

### Entity Definitions

| Entity | Definition File | Key Fields |
|--------|----------------|------------|
| Project | `project/model.py:Project` | root, meta, structures, calculations |
| Project (model) | `core/models.py:ProjectModel` | meta, structures[], calculations[] |
| Calculation | `calculation/calculation.py:Calculation` | id, project, dir, mode, steps[], structure |
| Calculation (model) | `core/models.py:CalculationModel` | meta, structure_id, mode, steps[], species_map |
| Step | `calculation/step.py:Step` | meta, input_file, engine, step_type |

### ULID Registry System

- All resources have `meta.id` (26-char ULID, starts with "01")
- `core/resolution.py:build_resource_index()` scans project for all resources
- Cross-references use ULIDs only (DAG + ID-only model)
- Example: `calculation.yaml` references structure via `structure_id: 01HXXXXXX...`

### Family Enforcement (PBC vs QuantumChem)

Currently implicit based on engine selection:
- `engine: "qe"` → Periodic Boundary Conditions (QE-based)
- `engine: "pyscf"` → Quantum Chemistry (PySCF-based)

No explicit family field in calculation.yaml yet.

---

## 4. Run Initiation Points

### Entry Points Summary

| Layer | File | Function/Method | Description |
|-------|------|-----------------|-------------|
| CLI | `cli/main.py` | Various commands | `qv run`, `qv step run`, etc. |
| Daemon RPC | `daemon/server.py:5039` | `_handle_run_calculation()` | GUI → daemon |
| Daemon RPC | `daemon/server.py:5063` | `_handle_run_step()` | Single step run |
| API | `api.py` | `QVService.run_calculation()` | Core execution logic |
| Runner | `calculation/runner.py:62` | `CalculationRunner.run()` | Step orchestration |

### Daemon Run Flow (GUI Path)

```python
# daemon/server.py:5039-5060
def _handle_run_calculation(self, payload):
    """
    1. Parse payload (project_root, calculation selector)
    2. Build initial_steps metadata for job display
    3. Submit to JobManager:
       job_id = self.job_manager.submit(
           job_type="run_calculation",
           func=QVService.run_calculation,  # <-- actual execution
           ...
       )
    4. Return job_id to GUI
    """

# daemon/jobs.py:146-230
class JobManager:
    def submit(self, job_type, func, params, ...):
        # Creates Job record
        # Executes in ThreadPoolExecutor
        # Updates job status on completion
```

### Suggested Run Snapshot Hook Points

**Best location for "Run Revision Snapshot":**

```python
# Option A: In daemon before job submission (daemon/server.py ~5040)
# PRO: Captures state before any execution
# CON: Would need to pass snapshot ref to JobManager

# Option B: In CalculationRunner.run() start (calculation/runner.py ~64)
# PRO: Single place for all run paths (CLI, daemon)
# CON: Slightly after job creation

# RECOMMENDED: Option B - Runner entry point
```

**Implementation sketch:**

```python
# calculation/runner.py
class CalculationRunner:
    def run(self, calculation: Calculation) -> CalculationResult:
        # === HISTORY HOOK: Create Run Revision Snapshot ===
        from quantumvitas.core.history import create_run_snapshot
        run_id = create_run_snapshot(
            calculation=calculation,
            intention_record=self._build_intention_record(calculation),
        )
        
        # ... existing execution logic ...
        
        # === HISTORY HOOK: Record Run Completion ===
        record_run_completion(run_id, result)
        
        return result
```

---

## 5. Preset Compilation Flow

### Preset Application Path

```
GUI/CLI
    │
    ▼
daemon/server.py:_handle_apply_presets_to_calculation()
    │
    ▼
presets/integration.py:apply_presets_to_step()
    │
    ├─► variants_registry.py:compile_dimension_patch_for_step()
    │       │
    │       ▼
    │   compiler.py:compile_magnetism(), compile_occupations_scheme(), etc.
    │
    ▼
StepDoc.apply_patch(unified_patch)
    │
    ▼
StepDoc.save(step_path)  →  yaml_io.save_yaml_doc()  →  Journal
```

### Key File: `presets/integration.py`

```python
# presets/integration.py:327-568
def apply_presets_to_step(
    step_path: Path,
    options: Dict[str, Any],
    *,
    validate_physics: bool = True,
    precision_advice: Optional[Any] = None,
    precision_lattice_matrix: Optional[List[List[float]]] = None,
) -> Dict[str, Any]:
    """
    Apply preset options to an existing step.
    
    OVERWRITES preset-related parameters (does NOT merge).
    Uses StepDoc abstraction for mutation containment.
    """
    # Load via StepDoc (compiler has write access)
    doc = StepDoc.load(step_path, access_control=True, owner="compiler")
    
    # ... compile patches for each dimension ...
    
    # Apply unified patch via StepDoc
    doc.apply_patch(unified_patch)
    
    # Save via StepDoc (single commit point → Journal)
    doc.save(step_path)  # <-- Goes through yaml_io.save_yaml_doc()
```

### Intention Record for History

Currently, preset compilation does NOT store intention metadata. The Journal captures before/after snapshots, but not:
- Which preset options were selected
- Decision summaries from detector
- Precision advice context

**Recommendation:** Add intention record to Journal entry:

```python
# Proposed extension to JournalEntry
@dataclass
class JournalEntry:
    # ... existing fields ...
    
    # NEW: Intention metadata (optional)
    intention: Optional[Dict[str, Any]] = None
    # Example: {
    #   "preset_options": {"magnetism": "collinear_lsda", "precision": "med"},
    #   "precision_advice": {"ecutwfc": 60.0, "nk": [6,6,6]},
    #   "actor": "gui",
    # }
```

---

## 6. Proposed History Persistence Design

### On-Disk Layout (Per-Project)

```
<project_root>/
├── .history/
│   ├── events.jsonl            # Append-only structured events
│   ├── baseline/               # Optional: initial project state snapshot
│   │   ├── project.qv.yml
│   │   ├── structures/
│   │   └── calculations/
│   │
│   └── runs/
│       └── run_<ULID>/
│           ├── run_revision.json   # Run metadata
│           └── snapshot/           # OR snapshot.tar.zst
│               ├── project.qv.yml
│               ├── structures/
│               │   └── *.json
│               └── calculations/
│                   └── <calc_slug>/
│                       ├── calculation.yaml
│                       └── steps/*.step.yaml
```

### Event Schema (events.jsonl)

```jsonc
// Each line is a JSON object
{
  "id": "01HQXYZ...",           // Event ULID
  "timestamp": "2026-01-06T12:34:56.789Z",
  "event_type": "edit",         // "init" | "edit" | "preset_apply" | "run_start" | "run_complete" | "run_failed"
  "actor": "gui",               // "gui" | "cli" | "daemon" | "system"
  
  // Target context
  "project_id": "01HQABC...",
  "calc_id": "01HQDEF...",      // Optional
  "step_id": "01HQGHI...",      // Optional
  
  // For "edit" events: structured diff
  "diff": {
    "doc_type": "step",
    "path": "calculations/si-scf/steps/scf.step.yaml",
    "changes": [
      {"op": "set", "path": "/parameters/SYSTEM/ecutwfc", "old": 40.0, "new": 60.0},
      {"op": "delete", "path": "/parameters/SYSTEM/nspin"}
    ]
  },
  
  // For "preset_apply" events: intention record
  "intention": {
    "preset_options": {"magnetism": "nonmagnetic", "precision": "med"},
    "precision_advice": {"ecutwfc": 60.0, "ecutrho": 480.0, "nk": [6,6,6]},
    "affected_steps": ["scf", "nscf"]
  },
  
  // For "run_*" events
  "run_id": "01HQRUN...",       // Links to runs/<run_id>/
  "run_result": {               // Only for run_complete/run_failed
    "status": "success",
    "duration_seconds": 123.4,
    "step_summaries": [...]
  }
}
```

### Run Revision Metadata Schema (run_revision.json)

```jsonc
{
  "id": "01HQRUN...",
  "timestamp": "2026-01-06T12:34:56.789Z",
  "project_id": "01HQABC...",
  "calc_id": "01HQDEF...",
  "calc_name": "Silicon SCF",
  
  // Engine info (for reproducibility)
  "engine": {
    "name": "qe",
    "version": "7.2",
    "path": "/opt/qe-7.2/bin/pw.x"
  },
  
  // Intention record
  "intention": {
    "preset_options": {"magnetism": "nonmagnetic", "precision": "med"},
    "step_types": ["scf"],
    "structure_id": "01HQSTR...",
    "structure_name": "Silicon (conventional)"
  },
  
  // Pseudo references (for reproducibility)
  "pseudo_refs": {
    "Si": {
      "filename": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
      "sha256": "abc123...",
      "sha_family": "def456..."  // Physical equivalence hash
    }
  },
  
  // Execution metadata
  "started_at": "2026-01-06T12:34:56.789Z",
  "finished_at": "2026-01-06T12:35:23.456Z",
  "status": "success",  // "success" | "failed" | "cancelled"
  "working_dir": "calculations/si-scf/raw",
  
  // Step summaries (from CalculationResult)
  "step_results": [
    {
      "step_id": "01HQSTP...",
      "step_type": "scf",
      "status": "success",
      "metrics": {"total_energy": -15.854, "scf_iterations": 8}
    }
  ]
}
```

### Project-Wide vs Global History

| Aspect | Per-Project History | Global Journal (existing) |
|--------|---------------------|---------------------------|
| Location | `<project>/.history/` | `~/.quantumvitas/journal/` |
| Scope | Single project | All projects |
| Includes | Edits, runs, intentions | YAML saves only |
| Snapshots | Full run snapshots | Before/after diffs |
| Use case | Project narrative | Debug/audit |

**Recommendation:** Keep both:
- Global Journal for system-wide audit
- Per-Project History for user-facing notebook view

---

## 7. UI/Frontend Integration Points

### Current Navigation Structure (Sidebar.tsx)

```typescript
// gui/src/components/layout/Sidebar.tsx:18
export type ViewType = 'home' | 'structures' | 'calculations' | 'jobs' | 'resources' | 'settings';
```

**To add History:**

```typescript
export type ViewType = 'home' | 'structures' | 'calculations' | 'jobs' | 'history' | 'resources' | 'settings';
```

### Sidebar Tab Addition

```tsx
// Sidebar.tsx ~line 260 (after Jobs tab)
<button
  className={`sidebar__tab ${currentView === 'history' ? 'active' : ''}`}
  onClick={() => onViewChange('history')}
  disabled={!projectLoaded}
  title={projectLoaded ? 'View project history timeline' : 'Load a project first'}
  data-testid="qv-nav-history"
>
  <span className="sidebar__tab-icon">📜</span>
  {!isCollapsed && 'History'}
</button>
```

### App.tsx View Routing

The App.tsx uses a switch-like pattern based on `currentView`:

```tsx
// App.tsx ~line 800+
{currentView === 'history' && projectLoaded && (
  <HistoryPanel
    projectRoot={projectRoot}
    qv={qv}
  />
)}
```

### Existing JournalHistoryPanel

There's already a `JournalHistoryPanel` in `components/settings/` that shows global journal entries. This could be:
1. **Extended** to show per-project history
2. **Replaced** with a new `HistoryPanel` component for notebook-style view

**Recommendation:** Create new `HistoryPanel` component:

```
gui/src/components/panels/
├── HistoryPanel.tsx       # NEW: Main history view
├── HistoryPanel.css
├── HistoryTimeline.tsx    # Timeline rendering
├── HistoryEventCard.tsx   # Individual event cards
└── HistoryFilters.tsx     # Search/filter controls
```

### Daemon RPC Endpoints Needed

```typescript
// New RPC endpoints in daemon/server.py

// List history events with filtering
"list_project_history": {
  project_root: string,
  filters?: {
    calc_id?: string,
    event_types?: string[],
    since?: string,  // ISO timestamp
    until?: string,
  },
  limit?: number,
  offset?: number,
}

// Get run revision details
"get_run_revision": {
  project_root: string,
  run_id: string,
}

// Get event details
"get_history_event": {
  project_root: string,
  event_id: string,
}
```

---

## 8. Implementation Plan (Phased TODOs)

### Phase 1: History Recording Backend (Events + Run Snapshots)

**Goal:** Record history events without UI changes.

#### Phase 1.1: History Module Setup
- [ ] Create `src/quantumvitas/core/history.py` module
- [ ] Define `HistoryEvent` dataclass
- [ ] Define `RunRevision` dataclass
- [ ] Implement `ProjectHistory` class with:
  - `record_event(event: HistoryEvent)` → append to events.jsonl
  - `create_run_snapshot(calc, intention)` → create runs/<id>/
  - `record_run_completion(run_id, result)`
  - `list_events(filters)` → read events.jsonl
  - `get_run_revision(run_id)` → read run_revision.json

#### Phase 1.2: Integrate with yaml_io
- [ ] Extend `save_yaml_doc()` to call `ProjectHistory.record_event()`
- [ ] Pass project context through save chain (may need CalcDoc/StepDoc extension)
- [ ] Add `intention` parameter to `save_yaml_doc()` for preset applications

#### Phase 1.3: Integrate with Runner
- [ ] Add `create_run_snapshot()` call at start of `CalculationRunner.run()`
- [ ] Add `record_run_completion()` call at end
- [ ] Extract intention record from calculation's detected presets

#### Phase 1.4: Daemon RPC Endpoints
- [ ] Add `_handle_list_project_history()` handler
- [ ] Add `_handle_get_run_revision()` handler
- [ ] Add `_handle_get_history_event()` handler

#### Phase 1.5: Migration of Direct YAML Writes
- [ ] Audit all `yaml.safe_dump` calls in api.py, cli/main.py
- [ ] Migrate to `save_yaml_doc()` flow (tech debt)

**Deliverables:**
- `.history/events.jsonl` populated on YAML saves
- `.history/runs/<id>/` created on calculation runs
- RPC endpoints returning history data

---

### Phase 2: History View Rendering (Notebook Timeline)

**Goal:** Display history in GUI as notebook-style timeline.

#### Phase 2.1: History Panel Component
- [ ] Create `gui/src/components/panels/HistoryPanel.tsx`
- [ ] Create `gui/src/components/panels/HistoryPanel.css`
- [ ] Add to component index exports

#### Phase 2.2: Timeline Rendering
- [ ] Create `HistoryTimeline.tsx` - vertical timeline layout
- [ ] Create `HistoryEventCard.tsx` - event cards with:
  - Icon per event type (edit, run, preset)
  - Timestamp + relative time
  - Summary text
  - Expandable details

#### Phase 2.3: Navigation Integration
- [ ] Add 'history' to `ViewType` in Sidebar.tsx
- [ ] Add History tab button to Sidebar
- [ ] Add History view routing in App.tsx

#### Phase 2.4: Data Fetching
- [ ] Create `useProjectHistory` hook for RPC calls
- [ ] Implement polling/refresh on tab focus
- [ ] Handle loading/error states

**Deliverables:**
- History tab in sidebar (📜 icon)
- Timeline view showing events chronologically
- Click event to see details

---

### Phase 3: Result Previews + Diff Summaries + Search/Filter

**Goal:** Rich history browsing experience.

#### Phase 3.1: Run Result Previews
- [ ] Show step outcomes in run event cards
- [ ] Mini energy/convergence plots (if data available)
- [ ] Link to full result view (jump to Calculations → Analysis)

#### Phase 3.2: Structured Diff Display
- [ ] Compute human-readable diffs from before/after
- [ ] Syntax highlight parameter changes
- [ ] Collapse large diffs with "show more"

#### Phase 3.3: Search & Filter
- [ ] Filter by event type (checkbox pills)
- [ ] Filter by calculation (dropdown)
- [ ] Filter by date range
- [ ] Text search in summaries

#### Phase 3.4: Jump Links
- [ ] "View Calculation" → navigate to calc detail
- [ ] "View Step" → navigate to step detail
- [ ] "Open Workdir" → reveal in file manager

#### Phase 3.5: Performance Optimization
- [ ] Virtualized list for long histories
- [ ] Pagination in RPC responses
- [ ] Lazy load run snapshots

**Deliverables:**
- Rich event cards with previews
- Working filters and search
- Jump links to related views

---

## 9. Risk Assessment & Mitigations

### Risk 1: Schema Migration
**Risk:** History schema changes breaking existing history files.  
**Mitigation:**
- Version field in event schema (`"schema_version": 1`)
- Migration function on load if version < current
- Keep schema additive (new optional fields only)

### Risk 2: Performance with Large Histories
**Risk:** Thousands of events slowing UI.  
**Mitigation:**
- Pagination in RPC (limit/offset)
- Virtualized list rendering in React
- Index file for binary search by timestamp (future)

### Risk 3: Large Diffs
**Risk:** Full before/after snapshots bloat storage.  
**Mitigation:**
- Store structured diffs in events.jsonl (not full docs)
- Full snapshots only for run revisions
- Optional compression for run snapshots (.tar.zst)

### Risk 4: Pseudo Storage Growth
**Risk:** Run snapshots duplicating pseudopotentials.  
**Mitigation:**
- Run snapshots reference pseudos by sha, don't copy them
- Pseudo files live in project/pseudo (single copy)
- run_revision.json stores sha references only

### Risk 5: Concurrent Access
**Risk:** Multiple processes writing to events.jsonl.  
**Mitigation:**
- Append-only writes are generally safe
- Consider file locking for critical sections
- SQLite backend as future option

### Risk 6: Direct YAML Writes Bypassing History
**Risk:** Code paths not using yaml_io miss history recording.  
**Mitigation:**
- Phase 1.5 migrates all direct writes
- grep audit for `yaml.safe_dump` in CI
- Lint rule or pre-commit hook

---

## Summary

The QMatSuite codebase has a solid foundation for Project History:

1. **YAML I/O abstraction exists** (`yaml_io.py` + `YamlDoc` classes) with Journal hook
2. **Runner has clear entry point** (`CalculationRunner.run()`)
3. **Preset system has intention data** available during compilation
4. **GUI has extensible navigation** (Sidebar + view routing)
5. **Existing JournalHistoryPanel** proves pattern works

Key work needed:
1. Create per-project history module (events.jsonl + run snapshots)
2. Extend yaml_io hook for project-scoped events
3. Add run snapshot creation to runner
4. Build History panel UI with timeline rendering
5. Migrate remaining direct YAML writes

The phased approach allows incremental delivery with backend recording first (testable without UI), then progressive UI enhancement.

