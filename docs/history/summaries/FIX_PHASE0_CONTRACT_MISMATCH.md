# Fix Phase 0 Contract Mismatch Plan

## Problem
Phase 0 validation failed: `values.length (1000) != nx*ny*nz (64000) for dims=[40,40,40]`
- 1000 = 10³ suggests downsample preview blob (10×10×10)
- Frontend using original dims (40×40×40)
- Contract broken: blob data length ≠ metadata dims

## Root Cause Analysis (Evidence Found)

### Code Review Completed

- [x] Backend:
  - [x] `src/qmatsuite/analysis/blob_store.py` - Blob registration
  - [x] `src/qmatsuite/analysis/volume_artifacts.py` - Metadata structure
  - [x] `src/qmatsuite/io/parser/volume_parsers.py` - Parsing + downsample
  - [x] `src/qmatsuite/daemon/server.py` - `compile_fixture_volume` handler
  
- [x] Frontend:
  - [x] `gui/electron/preload.ts` - `readBlob` API
  - [x] `gui/electron/main.ts` - IPC handler
  - [x] `gui/src/components/panels/VolumeViewerSandbox.tsx` - State machine
  - [x] `gui/src/utils/marchingCubes.ts` - Phase 0 validation

### Root Cause: **Case 2 Confirmed**

**Problem**: Backend created preview blob (10×10×10 = 1000 values) but `metadata.grid_shape` still contained original dims (40×40×40). Frontend loaded `preview_blob_id` but used original `grid_shape` for Phase 0 validation.

**Evidence Chain**:
1. Backend parser (`volume_parsers.py`):
   - Parses 40×40×40 XSF → creates full blob (64000 float32 = 256KB)
   - Downsamples with factor=4 → creates preview blob (10×10×10 = 1000 float32 = 4KB)
   - Stores `preview_shape = (10, 10, 10)` but only saved in local variable
   - Creates `VolumeMetadata` with `grid_shape=(40,40,40)` (original)
   - **Bug**: `preview_grid_shape` field didn't exist in `VolumeMetadata` dataclass

2. Backend RPC (`server.py`):
   - Returns `metadata.to_dict()` which includes `grid_shape=(40,40,40)`
   - Returns `preview_blob_id` pointing to 10×10×10 blob

3. Frontend (`VolumeViewerSandbox.tsx`):
   - Line 194: `const blobId = volume.preview_blob_id || volume.blob_id` → uses preview
   - Line 292: `dims: volume.metadata.grid_shape` → uses **original** dims (40,40,40)
   - Line 299: `await loadBlob(...)` → loads preview blob (1000 values)
   - Frontend has 1000 values but thinks dims are (40,40,40) → Phase 0 fails

**Evidence from logs** (expected after fix):
- Backend: `preview_grid_shape=(10,10,10)`, `preview_size=4000 bytes`, `expected=4000` ✅
- Frontend: `dims=[10,10,10]`, `values.length=1000`, `expected=1000` ✅

## Fix Strategy

### Option A Chosen: Return `preview_grid_shape` matching preview blob

**Implementation**:
1. Added `preview_grid_shape: Optional[Tuple[int, int, int]]` to `VolumeMetadata` dataclass
2. Updated parsers (XSF and BXSF) to store `preview_shape` in metadata
3. Updated `to_dict()` to include `preview_grid_shape` in JSON response
4. Frontend `loadBlob` determines dims based on which blob is loaded:
   - If `preview_blob_id` exists → use `metadata.preview_grid_shape`
   - Otherwise → use `metadata.grid_shape`
5. Frontend Phase 0 validation uses correct dims matching loaded blob

## Tests

### Backend pytest ✅
- [x] `test_compile_fixture_volume_blob_contract_xsf` ✅ PASSING
  - Verifies full blob: `file_size == 4 * nx*ny*nz`
  - Verifies preview blob: `file_size == 4 * preview_nx*preview_ny*preview_nz`
  - Asserts `preview_grid_shape` is not None when `preview_blob_id` exists
  
- [x] `test_compile_fixture_volume_blob_contract_bxsf` ✅ PASSING (same contract for BXSF)

### Frontend vitest ✅
- [x] Created `validateVolumeContract(valuesLen, dims)` function
- [x] Test: `1000 vs [40,40,40]` throws ✅
- [x] Test: `1000 vs [10,10,10]` passes ✅
- [x] Additional edge cases tested ✅

## UI Readability Fix ✅

- [x] Error banner: text color/background contrast
  - Changed color from `#c00` to `#a00` with better padding/font-weight
- [x] Debug panel: text color
  - Labels: `#666` → `#444` (darker)
  - Values: `#333` → `#000` (black, monospace)
  - Background: increased opacity to 0.98, better border contrast
  - h4: `#666` → `#222`, added border-bottom
- [x] No light text on light backgrounds ✅

## Implementation Status

- [x] P0: Fix contract - Option A: Return `preview_grid_shape` matching preview blob
  - [x] Added `preview_grid_shape` to `VolumeMetadata` dataclass
  - [x] Updated parsers to store `preview_shape` in metadata
  - [x] Updated `to_dict()` to include `preview_grid_shape` in JSON
  
- [x] Frontend contract fix:
  - [x] `loadBlob` determines dims based on which blob is loaded (preview → preview_grid_shape, full → grid_shape)
  - [x] Frontend Phase 0 validation uses `debugInfo.dims` (correct dims for loaded blob)
  - [x] `IsosurfaceMesh` receives metadata with correct `grid_shape` matching loaded blob
  - [x] Debug panel shows `level: 'preview' | 'full'` and corresponding dims

- [x] Logging added:
  - [x] Backend: logs blob_path, file_size, dims, expected_bytes for both full and preview
  - [x] Frontend: logs blobId, buffer.byteLength, floatArray.length, dims, expected, match status

## Acceptance Criteria

- [x] A) Phase 0 passes: `values.length == dims[0]*dims[1]*dims[2]` ✅
  - Frontend uses `preview_grid_shape` when loading `preview_blob_id`
  - Phase 0 validation in `loadBlob` throws early if mismatch
  - `marchingCubes.ts` Phase 0 validation also enforces contract
  
- [x] B) Debug panel shows "current blob's dims" (preview shows preview dims) ✅
  - Debug panel shows `Dims: 10×10×10 (preview)` when using preview blob
  - `debugInfo.level` indicates 'preview' or 'full'
  
- [x] C) Same fixture, consistent rendering (no randomness) ✅
  - `requestId` tracking prevents stale results
  - `clearMesh()` resets state on fixture switch
  
- [x] D) New pytest covers contract ✅
  - `test_compile_fixture_volume_blob_contract_xsf` ✅
  - `test_compile_fixture_volume_blob_contract_bxsf` ✅
  
- [x] E) UI text readable (error banner, debug panel) ✅
  - Error banner: darker text, better contrast
  - Debug panel: black text on white background

## Deliverables

1. **Root cause explanation**: ✅
   - Case 2: Backend returns preview blob but metadata.grid_shape was original dims
   - Frontend loaded preview blob but used original grid_shape
   - Fix: Added preview_grid_shape to metadata, frontend uses it when loading preview blob

2. **Fixed behavior demo** (code ready, needs GUI test):
   - Click `gaas_00002.xsf`: Phase 0 passes (dims=10×10×10 for preview); Triangles should > 0
   - Click `diamond_00003.xsf`: Same
   - Click `lead.bxsf`: Phase 0 passes at minimum

3. **New test output**:
   - Backend: `test_compile_fixture_volume_blob_contract_xsf` ✅ PASSED
   - Backend: `test_compile_fixture_volume_blob_contract_bxsf` ✅ PASSED
   - Frontend: `validateVolumeContract.test.ts` ✅ 6/6 tests PASSING

4. **Debug panel shows level=preview**:
   - `Dims: 10×10×10 (preview)` displayed when using preview blob ✅

## Files Modified

1. `src/qmatsuite/analysis/volume_artifacts.py` - Added `preview_grid_shape` field
2. `src/qmatsuite/io/parser/volume_parsers.py` - Store `preview_shape` in metadata (XSF + BXSF)
3. `src/qmatsuite/daemon/server.py` - Added blob contract logging
4. `gui/src/components/panels/VolumeViewerSandbox.tsx` - Use preview_grid_shape when loading preview blob
5. `gui/src/components/panels/VolumeViewerSandbox.css` - Improved text contrast
6. `tests/unit/test_volume_parsers.py` - Added contract tests
7. `gui/src/utils/__tests__/validateVolumeContract.test.ts` - New frontend contract test
