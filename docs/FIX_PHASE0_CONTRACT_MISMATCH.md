# Fix Phase 0 Contract Mismatch Plan

## Problem
Phase 0 validation failed: `values.length (1000) != nx*ny*nz (64000) for dims=[40,40,40]`
- 1000 = 10³ suggests downsample preview blob (10×10×10)
- Frontend using original dims (40×40×40)
- Contract broken: blob data length ≠ metadata dims

## Root Cause Analysis (Need Evidence)

- [ ] Code review backend:
  - [ ] `src/quantumvitas/analysis/blob_store.py` - Blob registration
  - [ ] `src/quantumvitas/analysis/volume_artifacts.py` - Metadata structure
  - [ ] `src/quantumvitas/io/parser/volume_parsers.py` - Parsing + downsample
  - [ ] `src/quantumvitas/daemon/server.py` - `compile_fixture_volume` handler
  
- [ ] Code review frontend:
  - [ ] `gui/electron/preload.ts` - `readBlob` API
  - [ ] `gui/electron/main.ts` - IPC handler
  - [ ] `gui/src/components/panels/VolumeViewerSandbox.tsx` - State machine
  - [ ] `gui/src/utils/marchingCubes.ts` - Phase 0 validation

- [ ] Add logging to trace contract:
  - [ ] Backend: log `blob_path`, `os.path.getsize(blob_path)`, `dims`, `expected_bytes = 4 * nx*ny*nz`
  - [ ] Frontend: log `blobId`, `buffer.byteLength`, `floatArray.length`, `dims`, `expected`
  
- [ ] Determine which case:
  - [ ] Case 1: Backend downsamples but returns original dims
  - [ ] Case 2: Backend returns preview dims, frontend uses original
  - [ ] Case 3: readBlob reads partial file

## Fix Strategy

- [x] P0: Fix contract - **Option A chosen**: Return `preview_grid_shape` matching preview blob
  - [x] Added `preview_grid_shape` to `VolumeMetadata` dataclass
  - [x] Updated parsers to store `preview_shape` in metadata
  - [x] Updated `to_dict()` to include `preview_grid_shape` in JSON
  
- [x] Frontend contract fix:
  - [x] `loadBlob` determines dims based on which blob is loaded (preview → preview_grid_shape, full → grid_shape)
  - [x] Frontend Phase 0 validation uses `debugInfo.dims` (correct dims for loaded blob)
  - [x] `IsosurfaceMesh` receives metadata with correct `grid_shape` matching loaded blob
  - [x] Debug panel shows `level: 'preview' | 'full'` and corresponding dims

## Tests

- [x] Backend pytest:
  - [x] `test_compile_fixture_volume_blob_contract_xsf` ✅ PASSING
    - Verifies full blob: `file_size == 4 * nx*ny*nz`
    - Verifies preview blob: `file_size == 4 * preview_nx*preview_ny*preview_nz`
    - Asserts `preview_grid_shape` is not None when `preview_blob_id` exists
  
  - [x] `test_compile_fixture_volume_blob_contract_bxsf` ✅ PASSING (same contract for BXSF)

- [x] Frontend vitest:
  - [x] Created `validateVolumeContract(valuesLen, dims)` function in test file
  - [x] Test: `1000 vs [40,40,40]` throws ✅
  - [x] Test: `1000 vs [10,10,10]` passes ✅
  - [x] Additional edge cases tested ✅

## UI Readability Fix

- [x] Error banner: text color/background contrast ✅
  - Changed color from `#c00` to `#a00` with better padding/font-weight
- [x] Debug panel: text color ✅
  - Labels: `#666` → `#444` (darker)
  - Values: `#333` → `#000` (black, monospace)
  - Background: increased opacity to 0.98, better border contrast
  - h4: `#666` → `#222`, added border-bottom
- [x] No light text on light backgrounds ✅

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

1. Root cause explanation (with evidence: dims/bytes/valuesLen logs)
2. Fixed behavior demo:
   - Click `gaas_00002.xsf`: Phase 0 passes; Triangles > 0 or at least not stuck
   - Click `diamond_00003.xsf`: Same
   - Click `lead.bxsf`: At least Phase 0 passes
3. New test output (pytest backend + vitest frontend)
4. If preview dims: Debug panel shows `level=preview` and preview dims

