# Logging Fix Summary

## Problem Diagnosis

### Why GUI Couldn't See [viewer] Logs

**Root Cause**: Python's `logging.getLogger(...).info(...)` calls were not configured to output to stderr.

**Evidence**:
1. Daemon has a `log()` method (`server.py:278`) that writes to `stderr` with format `[qv-daemon] [LEVEL] message`
2. Electron main process (`electron/main.ts:284`) listens to daemon's `stderr` and forwards to renderer via IPC
3. GUI `DebugPanel` uses `useQVLogs()` hook to receive all logs
4. **BUT**: Code using `logging.getLogger(__name__).info(...)` (e.g., `api.py:1892`) doesn't automatically output to stderr because Python's logging module wasn't configured

**Specific Code Locations**:
- `src/quantumvitas/api.py:1892`: `logger = logging.getLogger(__name__)`
- `src/quantumvitas/analysis/structure_viz.py:62`: `logger = logging.getLogger(__name__)`
- Many other modules use `logging.getLogger(__name__)` but logs were lost

## Solution Implemented

### 1. Configure Python Logging in Daemon (`server.py`)

**File**: `src/quantumvitas/daemon/server.py`

**Added**: `_configure_logging()` method in `QVDaemon.__init__()`

```python
def _configure_logging(self):
    """
    Configure Python logging to output all logs to stderr.
    
    This ensures that all logging.getLogger(...).info(...) calls throughout
    the codebase are visible in the GUI Daemon Logs panel.
    """
    # Create a handler that writes to stderr
    handler = logging.StreamHandler(self.stderr)
    
    # Use a formatter that matches the daemon log format
    formatter = logging.Formatter(
        '[qv-daemon] [%(levelname)s] [%(name)s] %(message)s',
        datefmt=None
    )
    handler.setFormatter(formatter)
    
    # Configure root logger to output to stderr at INFO level
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Prevent duplicate logs (don't propagate to parent if already handled)
    root_logger.propagate = False
```

**Result**: All `logging.getLogger(...).info(...)` calls now output to stderr with format:
```
[qv-daemon] [INFO] [quantumvitas.api] [viewer] kind=online mode=supercell ...
```

### 2. Backend Viewer Summary Log (`api.py`)

**File**: `src/quantumvitas/api.py`

**Added**: One-line summary log in `_build_structure_vis_payload()`

**Format**: `[viewer] kind=online mode=supercell sc=2x2x2 repeat=1 atoms=3->24 bonds=84 prep=8ms bonds=120ms total=135ms payload=420KB`

**Fields**:
- `kind`: `online` or `project`
- `mode`: `primitive`, `supercell`, `conventional`, `box`
- `sc`: Supercell dimensions (e.g., `2x2x2`)
- `repeat`: `1` if boundary repeat enabled, `0` otherwise
- `atoms`: `atoms_in->atoms_out` (original structure atoms -> display atoms)
- `bonds`: Number of bonds detected
- `prep`: Time to prepare display atoms (ms, integer)
- `bonds`: Time to build bonds (ms, integer)
- `total`: Total payload build time (ms, integer)
- `payload`: Serialized payload size (KB, integer)

**Location**: Line 2162-2190 in `api.py`

### 3. Frontend Timing Logs (`App.tsx`)

**File**: `gui/src/App.tsx`

**Added**: Two timing measurements in `loadStructureModel()`:

1. **RPC Timing**: Measured from RPC call start to response received
2. **Render Timing**: Measured from `setState` (committing data to viewer) to first frame rendered

**Format**: `[ui] kind=project rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell`

**Fields**:
- `kind`: `project` or `online`
- `rpc`: RPC round-trip time (ms, integer)
- `render`: Viewer render time (ms, integer)
- `atoms`: Number of display atoms
- `bonds`: Number of bonds
- `mode`: Display mode

**Implementation**:
- RPC timing: Measured in `loadStructureModel()` (lines 650, 684, 717)
- Render timing: Measured using `viewerStartTimeRef` and `handleViewerFirstFrame` callback (lines 698, 929-970)
- Logged in `handleViewerFirstFrame` when viewer completes first frame

### 4. Integration Test Skip Fix

**Files**: 
- `tests/integration/test_pipeline_alignment.py`
- `tests/integration/test_optimade_live.py`

**Status**: ✅ Already using `pytest.fail()` instead of `pytest.skip()`

**Verification**: All integration tests pass without skipping:
- `test_online_vs_project_pipeline_bit_aligned` ✅
- `test_optimade_live_search_si` ✅
- `test_optimade_live_fetch_si_structure_and_parse_pymatgen` ✅
- `test_optimade_live_viewer_payload_builder` ✅
- `test_optimade_live_fetch_mos2_with_rich_metadata` ✅

## Verification

### How to Verify Logs Are Visible

1. **Start GUI** and open Structures page
2. **Click a project structure** → Should see in Daemon Logs:
   ```
   [qv-daemon] [INFO] [quantumvitas.api] [viewer] kind=project mode=primitive sc=1x1x1 repeat=0 atoms=2->2 bonds=4 prep=2ms bonds=1ms total=5ms payload=2KB
   ```
3. **Click an online candidate** → Should see:
   ```
   [qv-daemon] [INFO] [quantumvitas.api] [viewer] kind=online mode=primitive sc=1x1x1 repeat=0 atoms=3->3 bonds=6 prep=3ms bonds=2ms total=8ms payload=3KB
   ```
4. **Check browser console** → Should see:
   ```
   [ui] kind=project rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell
   ```

### Expected Log Format

**Backend** (visible in Daemon Logs panel):
```
[qv-daemon] [INFO] [quantumvitas.api] [viewer] kind=online mode=supercell sc=2x2x2 repeat=1 atoms=3->24 bonds=84 prep=8ms bonds=120ms total=135ms payload=420KB
```

**Frontend** (visible in browser console):
```
[ui] kind=online rpc=42ms render=180ms atoms=24 bonds=84 mode=supercell
```

## Files Changed

1. `src/quantumvitas/daemon/server.py`: Added `_configure_logging()` method
2. `src/quantumvitas/api.py`: Added `[viewer]` summary log in `_build_structure_vis_payload()`
3. `gui/src/App.tsx`: Added frontend timing logs in `loadStructureModel()` and `handleViewerFirstFrame()`

## Testing

All integration tests pass:
```bash
pytest tests/integration/test_pipeline_alignment.py tests/integration/test_optimade_live.py -v -m integration
```

Result: ✅ 5 passed
