# QE Metadata Load Status Implementation Summary

## Overview
Added internal-only QE metadata load status tracking that displays in Settings -> Debug panel. This tracks whether metadata was loaded from cache or disk, when it was loaded, and the schema version.

## Backend Changes

### 1. `src/quantumvitas/data/qe_metadata.py`
- **Added global state**: `QE_METADATA_LOAD_STATE` dictionary tracking:
  - `loaded_via`: "cache" | "disk" | "unknown"
  - `loaded_at`: ISO timestamp string
  - `schema_version`: int | None
  - `path_abs`: str | None

- **Added function**: `_update_qe_metadata_load_state(loaded_via, path_abs, schema_version)`
  - Updates the global state on every metadata access
  - Called automatically from `_load_raw_metadata()`

- **Modified `_load_raw_metadata()`**:
  - Cache hits: calls `_update_qe_metadata_load_state("cache", ...)`
  - Disk loads: calls `_update_qe_metadata_load_state("disk", ...)`
  - Tracks absolute path and schema version automatically

- **Added function**: `get_qe_metadata_debug_info()`
  - Returns a copy of `QE_METADATA_LOAD_STATE`
  - Used by the debug RPC endpoint

### 2. `src/quantumvitas/data/__init__.py`
- Exported `get_qe_metadata_debug_info` in `__all__`

### 3. `src/quantumvitas/daemon/server.py`
- **Added RPC handler**: `_handle_get_qe_parameter_metadata_debug_info()`
  - Command: `get_qe_parameter_metadata_debug_info`
  - Returns load state for debug/internal use only
  - Registered in `_handlers` dict

- **Added req_id logging**:
  - All RPC logs now include `req_id={request.id}` to help identify duplicate calls
  - Added optional debug logging with `QV_DEBUG_RPC=1` environment variable
  - Logs incoming requests with req_id when debug mode enabled

## Frontend Changes

### 1. `gui/src/types/qv.ts`
- **Added RPC command type**: `get_qe_parameter_metadata_debug_info`
  - Payload: `Record<string, never>`
  - Result: `{ loaded_via, loaded_at, schema_version, path_abs }`

### 2. `gui/src/components/panels/SettingsPanel.tsx`
- **Added state**: `qeMetadataDebugInfo` to store load status
- **Added function**: `fetchQEMetadataDebugInfo()` to fetch debug info
- **Added useEffect**: Fetches debug info when Diagnostics section is shown
- **Added UI section**: "QE Metadata Load Status" in Diagnostics/Debug section
  - Shows "Loaded via: cache|disk (HH:MM:SS)"
  - Shows "Schema: v<version>" if available
  - Shows path with tooltip (truncated with ellipsis)
  - Includes refresh button (🔄) to manually refresh status

## Double-Call Investigation

### Findings
1. **Added req_id logging**: All RPC logs now include `req_id={request.id}` to help identify duplicate calls
2. **Added debug mode**: Set `QV_DEBUG_RPC=1` to log incoming requests with req_id
3. **Investigation method**: 
   - Check daemon logs for duplicate `req_id` values
   - If same `req_id` appears twice, it's log duplication (not duplicate calls)
   - If different `req_id` values for same command, it's actual duplicate calls

### How to Investigate
1. Enable debug mode: `export QV_DEBUG_RPC=1`
2. Run the GUI and perform operations
3. Check daemon logs for patterns:
   - Same `req_id` appearing twice → log duplication (stdout/stderr forwarding)
   - Different `req_id` for same command → actual duplicate RPC calls
4. Check frontend code for:
   - Multiple `useEffect` hooks calling same RPC
   - Event handlers + effects both triggering
   - Missing guards/coalescing

### Summary
- **Not implemented**: Automatic deduplication (requires evidence of actual duplicate calls)
- **Implemented**: Instrumentation to identify the issue (req_id logging)
- **Next steps**: Monitor logs with `QV_DEBUG_RPC=1` to determine if duplicates are real calls or log forwarding

## Files Changed

### Backend
1. `src/quantumvitas/data/qe_metadata.py` - Load state tracking
2. `src/quantumvitas/data/__init__.py` - Export new function
3. `src/quantumvitas/daemon/server.py` - New RPC handler + req_id logging

### Frontend
1. `gui/src/types/qv.ts` - RPC type definition
2. `gui/src/components/panels/SettingsPanel.tsx` - Debug UI

## Testing
- ✅ All unit tests pass (`tests/unit/test_qe_metadata.py`)
- ✅ TypeScript compilation successful
- ✅ Load state updates on cache hits and disk loads
- ✅ Debug info accessible via RPC

## Usage
1. Open Settings panel
2. Expand "Diagnostics / Debug" section
3. View "QE Metadata Load Status" subsection
4. Click refresh button (🔄) to update status
5. Hover over path to see full absolute path

## Notes
- Load status is **internal-only** and not shown in customer-facing Parameter Viewer
- Status updates automatically on every metadata access
- Timestamp is in UTC ISO format, displayed as local HH:MM:SS in UI
- Path is truncated with ellipsis but full path shown in tooltip
