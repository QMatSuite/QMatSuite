# GUI History+Resources + CLI History — Worklog

## Overview

Three gaps closed in a single pass:
1. **History timeline** only showed runs/pins; operation events (edits, presets, structure imports) now merged.
2. **Resources UI** was hardcoded to `engineFamily="qe"`; now self-initializing with engine dropdown.
3. **CLI has no `qms history`**; four commands added (`list`, `show`, `storage`, `clear`).

**Non-negotiable rule**: CLI and daemon call only `QMSService` / `qmatsuite.api.*`. No direct provenance/kernel imports.

## Phase 1 — Quick Wins

### 1.1 Fix `.history` -> `.provenance/` in delete modal
- **File**: `gui/src/components/panels/HistoryPanel.tsx` line 418
- Changed `<code>.history</code>` -> `<code>.provenance</code>`

### 1.2 Wire missing engine metadata modules
- **File**: `src/qmatsuite/api/utils.py` — `_get_engine_metadata_module()`
- Added `elif` branches for `yambo`, `w90`, `xtb`

### 1.3 Remove QE hardcode — panel owns its engine state
- **File**: `gui/src/components/panels/EngineParameterBrowserPanel.tsx`
  - `engineFamily` prop made optional
  - Added internal state: `selectedEngine`, `engineList`
  - On mount: fetch engine list via `listEngineFamilies()`
  - Engine selector: `<select>` dropdown in header, persists to localStorage
  - All RPC calls use internal `selectedEngine` state
- **File**: `gui/src/App.tsx`
  - Removed `engineFamily="qe"` — `<EngineParameterBrowserPanel />` with no props
- **File**: `gui/src/components/panels/EngineParameterBrowserPanel.css`
  - Added `.qe-parameter-browser__engine-select` styles

### 1.4 Update sidebar tooltip
- **File**: `gui/src/components/layout/Sidebar.tsx`
- Changed to "Browse engine parameter reference"

## Phase 2 — Operation Events in Timeline

### 2.1 Fix `build_timeline_entry()` — canonical formatter
- **File**: `src/qmatsuite/provenance/query.py`
- Fixed all comparisons to lowercase enum values
- Removed dead `RUN_START`/`RUN_COMPLETE` branches
- Added catch-all for unmapped op types -> `event_type: "operation"`
- Added `op_type` and `kind` fields to all entries

### 2.2 Drive-by fix: pins.py case-sensitivity
- **File**: `src/qmatsuite/provenance/pins.py` lines 273, 354
- `'PIN_CREATE'` -> `'pin_create'` (SQLite = is case-sensitive)

### 2.3 Merge operations into `get_timeline()`
- **File**: `src/qmatsuite/api/service.py`
- Fetches `limit` runs + `limit` operations, merges, sorts DESC, truncates to `limit`
- Tags run entries with `kind: "run"`, op entries with `kind` from builder

### 2.4 Frontend: render operation events
- **File**: `gui/src/types/qms.ts` — Added `op_type`, `kind`, `scope` to `HistoryTimelineEntry`
- **File**: `gui/src/components/panels/HistoryPanel.tsx`
  - Added `renderOperationEvent()` with icon map
  - Added `case 'operation'` in switch
- **File**: `gui/src/components/panels/HistoryPanel.css`
  - Added `.history-entry--operation` styles

### 2.5 Tests
- **New file**: `tests/api/test_history_timeline.py`
  - 9 tests covering empty, operations, merged ordering, limit, field presence, kind

## Phase 3 — Run Detail Drawer + Storage Summary

### 3.1 Backend: `get_storage_summary()`
- **File**: `src/qmatsuite/api/service.py`
- Queries `cas_objects`, `runs`, `operations` tables
- Returns `{tiers, total_objects, total_bytes, run_count, operation_count}`
- Graceful: returns zeros if `.provenance/` doesn't exist

### 3.2 Daemon handler
- **File**: `src/qmatsuite/daemon/server.py`
- Added `get_storage_summary` to dispatch table + handler
- Fixed `.history` -> `.provenance` in docstrings

### 3.3 Frontend types
- **File**: `gui/src/types/qms.ts`
- Added `get_run_revision` and `get_storage_summary` to `QMSCommandMap`

### 3.4 RunDetailDrawer component
- **New file**: `gui/src/components/panels/RunDetailDrawer.tsx`
- Overlay drawer with run metadata, steps table, collapsible snapshot
- Uses `get_run_revision` RPC (same endpoint CLI uses)

### 3.5 RunDetailDrawer styles
- **New file**: `gui/src/components/panels/RunDetailDrawer.css`

### 3.6 Wire drawer into HistoryPanel
- **File**: `gui/src/components/panels/HistoryPanel.tsx`
- Added `selectedRunUlid` state
- Run card click opens drawer
- Renders `<RunDetailDrawer>` when ULID selected

### 3.7 Tests
- Tests included in `tests/api/test_history_timeline.py`:
  - `test_storage_summary_empty`, `test_storage_summary_with_data`
  - `test_get_run_revision_includes_snapshot`

## Phase 4 — CLI `qms history` Commands

### 4.1 History subcommand group
- **File**: `src/qmatsuite/cli/main.py`
- Added `history_app = typer.Typer(...)` with `no_args_is_help=True`
- Registered via `app.add_typer(history_app, name="history")`

### 4.2 Commands (all use `svc.history.*` only)
- `qms history list` — timeline with icons, timestamps, summaries
- `qms history show <run_ulid>` — run metadata, steps, snapshot SHA
- `qms history storage` — tier breakdown, counts, sizes
- `qms history clear` — with `--force` flag, uses `typer.confirm()`

### 4.3 Tests
- **New file**: `tests/cli/test_history_commands.py`
- 6 tests: list empty, list help, show not found, storage fresh, clear without force, help output

## Files Changed Summary

| File | Change |
|------|--------|
| `gui/src/components/panels/HistoryPanel.tsx` | Fix text, add operation renderer, wire drawer |
| `gui/src/components/panels/HistoryPanel.css` | Operation entry styles |
| `gui/src/components/panels/EngineParameterBrowserPanel.tsx` | Self-initializing engine selector |
| `gui/src/components/panels/EngineParameterBrowserPanel.css` | Engine select styles |
| `gui/src/components/panels/RunDetailDrawer.tsx` | **New** |
| `gui/src/components/panels/RunDetailDrawer.css` | **New** |
| `gui/src/App.tsx` | Remove QE hardcode |
| `gui/src/components/layout/Sidebar.tsx` | Update tooltip |
| `gui/src/types/qms.ts` | Add fields + command types |
| `src/qmatsuite/api/utils.py` | Wire yambo/w90/xtb metadata |
| `src/qmatsuite/api/service.py` | Merge timeline + storage summary |
| `src/qmatsuite/provenance/query.py` | Fix build_timeline_entry |
| `src/qmatsuite/provenance/pins.py` | Fix case-sensitivity |
| `src/qmatsuite/daemon/server.py` | Storage summary handler + docstring fix |
| `src/qmatsuite/cli/main.py` | History subcommands |
| `tests/api/test_history_timeline.py` | **New** |
| `tests/cli/test_history_commands.py` | **New** |
