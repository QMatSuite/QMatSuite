# Volume Viewer Debug Log

## Current Symptoms (Before Fix)

1. **0 triangles** - Most fixtures produce no mesh
2. **Flying fragments** - Occasional fragments at wrong positions
3. **BBox shows "—"** - Bounding box not calculated/displayed
4. **toFixed crashes** - Fixed in P0
5. **Non-deterministic switching** - Old async results overwrite new ones

## Root Cause Analysis

### Phase 0: Strong Validation ✅

**Status**: Implemented entry-point validation.
- Values length check: throws if `values.length != nx*ny*nz`
- NaN/Inf check: throws if found (reports first bad index)
- getValue bounds check: throws with full context (i,j,k,flatIdx,data_order)

### Phase 1: Index Contract ✅

**Problem**: Flat index calculation was scattered and may not respect `data_order` correctly.

**Fix**: Created centralized `flatIndex()` and `getValue()` functions in `volumeIndexing.ts`.

**Tests**: ✅ 8 tests passing
- FORTRAN order: idx = i + nx*(j + ny*k)
- C order: idx = k + nz*(j + ny*i)
- Bounds checking
- Value retrieval consistency

### Phase 2: Coordinate Mapping ✅

**Problem**: Grid-to-world coordinate transformation was incorrect (used raw grid_vectors, not step vectors).

**Fix**: Implemented `gridToWorld()` with correct step vector calculation:
- Step vectors: a = v1/(nx-1), b = v2/(ny-1), c = v3/(nz-1)
- World = origin + i*a + j*b + k*c
- Bbox calculated from 8 grid corners (not mesh vertices)

**Tests**: ✅ 6 tests passing
- Grid endpoints map correctly (i=0 → origin, i=nx-1 → origin+v1)
- Bbox calculation from corners

### Phase 3: Marching Cubes Contract ✅

**Status**: Using standard 256-case triTable, corner/edge definitions documented.

**Synthetic Sphere Test**: ✅ PASSING
- Created 32³ synthetic sphere field (distance - radius)
- iso=0 produces sphere surface
- Generated 2252 triangles, all finite positions/normals
- Mesh bbox in expected range (sphere in [-5,5])

**Evidence from test output**:
```
[Step A] Grid bbox: min=[-10.00, -10.00, -10.00], max=[10.00, 10.00, 10.00]
[Step C] activeCells: 1130, Top 5 cubeIndexes: 0(27274), 255(1387), 64(27), 128(27), 32(27)
[P3 triTable Proof] Final counts: vertexCount=6756, triangleCount=2252
```

### Phase 4: Async Race Conditions ✅

**Fix**: Strengthened async guards:
- `requestId` checked in `onMeshGenerated` callback
- Stale results discarded with console log
- All async operations check `latestRequestIdRef.current`

### Phase 5: Real Fixture Acceptance ⏳

**Status**: Code ready, needs GUI testing.

**Iso Default Logic**:
- BXSF: iso = fermi_energy (if available)
- XSF: iso = 0.2 * maxAbs (avoids near-zero noise fragments)

## Implementation Status

- [x] Phase 0: Add strong validation at entry point ✅
- [x] Phase 1: Centralize index calculation + tests ✅ (8 tests passing)
- [x] Phase 2: Fix coordinate mapping + tests ✅ (6 tests passing)
- [x] Phase 3: MC contract verification + synthetic test ✅ (1 test passing, 2252 triangles)
- [x] Phase 4: Strengthen async guards ✅
- [ ] Phase 5: Real fixture acceptance (needs GUI run)

## Test Evidence

### Phase 1 Tests (volumeIndexing.test.ts)
- ✅ 8/8 tests passing
- FORTRAN/C order index calculations verified
- Bounds checking working

### Phase 2 Tests (volumeCoordinates.test.ts)
- ✅ 6/6 tests passing
- Grid-to-world mapping correct
- Bbox calculation correct

### Phase 3 Test (marchingCubes.test.ts)
- ✅ 1/1 test passing (synthetic sphere)
- Generated 2252 triangles
- All positions/normals finite
- Mesh bbox correct (sphere in [-5,5] range)

### All Tests Summary
```bash
✓ volumeIndexing.test.ts (8 tests)
✓ volumeCoordinates.test.ts (6 tests)
✓ marchingCubes.test.ts (1 test)
Total: 15/15 tests passing
```

## Files Modified

1. `gui/src/utils/volumeIndexing.ts` (NEW) - Centralized index functions
2. `gui/src/utils/volumeCoordinates.ts` (NEW) - Grid-to-world mapping
3. `gui/src/utils/marchingCubes.ts` (MODIFIED) - Phase 0 validation, uses new functions
4. `gui/src/utils/__tests__/volumeIndexing.test.ts` (NEW)
5. `gui/src/utils/__tests__/volumeCoordinates.test.ts` (NEW)
6. `gui/src/utils/__tests__/marchingCubes.test.ts` (NEW)
7. `gui/src/components/panels/VolumeViewerSandbox.tsx` (MODIFIED) - Phase 4 async guards, Phase 5 iso logic

## Next Steps

1. Run GUI and test with real fixtures (gaas_00001.xsf, diamond_00001.xsf, lead.bxsf)
2. Verify bbox shows real values (not "—")
3. Verify triangles > 0 for reasonable iso values
4. Verify no flying fragments
5. Verify deterministic switching (no async overwrites)

