# TODO: ADR Alignment & Lightweight Improvements

This document lists lightweight improvements needed to align the codebase with the Constitution (`CONSTITUTION_ZH.md`). These are **not urgent** and should be done incrementally via small PRs.

**Related Documents**:
- Constitution: [`CONSTITUTION_ZH.md`](../CONSTITUTION_ZH.md) - Rules and definitions (Chinese)
- Implementation Notes: [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md) - Implementation details, evidence, locations

---

## [A] Resource Index & Cache

### A1: Persistent Cache Missing
**Status**: Current implementation only has in-memory cache in daemon (`DaemonState._caches`).

**Location**: See [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md#a-resource-index--cache-implementation) for details:
- Cache implementation: `src/quantumvitas/daemon/server.py:82-156`
- Index building: `src/quantumvitas/core/resolution.py:368-523`

**Issue**: 
- `build_resource_index()` does full filesystem scan every time (no persistent cache).
- Large projects (100+ calculations/structures) will be slow.

**Suggested Fix**:
- Add persistent cache (JSON/SQLite) with mtime-based invalidation.
- Cache file: `.qv_index_cache.json` in project root (or `.qv/` subdirectory).
- Invalidate when any resource file mtime changes.

**Files to Modify**:
- `src/quantumvitas/core/cache.py` (new) - Cache management
- `src/quantumvitas/core/resolution.py` - Integrate cache into `build_resource_index()`

**Test**:
- `tests/unit/test_resource_index_cache.py` (new) - Test cache creation, mtime invalidation

---

### A2: Cache Invalidation Strategy Not Documented
**Status**: Cache invalidation is manual (`invalidate_cache()`), no automatic mtime/hash-based invalidation.

**Location**: `src/quantumvitas/daemon/server.py:148-156`

**Issue**: 
- No clear documentation on when cache should be invalidated.
- No automatic invalidation based on file mtime changes.

**Suggested Fix**:
- Document cache invalidation strategy in code comments.
- Consider adding mtime-based automatic invalidation (check mtime on cache load).

**Files to Modify**:
- `src/quantumvitas/daemon/server.py` - Add invalidation strategy comments
- `docs/CACHE_STRATEGY.md` (new) - Document cache strategy

---

### A3: Consistency Validation Missing
**Status**: No validation for duplicate ULIDs, dangling references, missing entities.

**Location**: `build_resource_index()` only scans, doesn't validate.

**Issue**: 
- Corrupted projects (duplicate ULIDs, missing files) won't be detected early.

**Suggested Fix**:
- Add `validate_resource_index()` function to check:
  - Duplicate ULIDs
  - Dangling references (calculation.yaml references non-existent structure_id)
  - Missing files (ULID in index but file doesn't exist)

**Files to Modify**:
- `src/quantumvitas/core/resolution.py` - Add validation function
- `tests/unit/test_resource_index_validation.py` (new)

---

## [B] Geometry & Canonicalization

### B1: BOUNDARY_FRAC_TOL Value Inconsistency
**Status**: Code has `BOUNDARY_FRAC_TOL = 1e-6`, but some docs mention `1e-8`.

**Location**: See [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md#b-geometry--canonicalization-implementation) for constant definitions:
- Code: `src/quantumvitas/analysis/structure_viz.py:160`
- Docs: `docs/BOND_DETECTION_NOTES.md:72` mentions `1e-8`

**Issue**: 
- Value inconsistency between code and docs.
- Note: Code comment says it's "legacy, only for debug checks", so this may be intentional.

**Suggested Fix**:
- Verify if `BOUNDARY_FRAC_TOL` is actually used for geometry modifications (it shouldn't be).
- Update docs to match code (or vice versa if code is wrong).
- If it's truly legacy, mark it clearly in docs.

**Files to Modify**:
- `docs/BOND_DETECTION_NOTES.md` - Update to match code
- `src/quantumvitas/analysis/structure_viz.py` - Add comment if legacy

---

### B2: Cross-Platform Bond Count Test Missing
**Status**: No dedicated test to verify bond counts are consistent across platforms.

**Location**: `tests/unit/test_structure_viz.py` has tests but no cross-platform markers.

**Issue**: 
- Constitution requires cross-platform consistency, but no test enforces it.

**Suggested Fix**:
- Add `@pytest.mark.platform` test for Si 2×2×2 supercell bond count = 18.
- Run in CI on Linux/macOS (Windows when available).

**Files to Modify**:
- `tests/integration/test_cross_platform_bonds.py` (new)

---

## [C] QE Schema Storage

### C1: Schema Documentation Missing
**Status**: No explicit documentation that JSON only stores lattice matrix (Å) + frac coords, never ibrav/alat.

**Location**: 
- Documentation: `docs/SCHEMA.md` doesn't explicitly state this rule.
- Implementation evidence: See [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md#c-qe-schema-storage-implementation) for unit verification.

**Issue**: 
- Constitution requires this, but it's not documented clearly.
- Risk: Someone might think JSON can store ibrav.

**Suggested Fix**:
- Add section to `docs/SCHEMA.md` explicitly stating:
  - JSON stores: `lattice.matrix` (Å) + `sites[].abc` (frac coords)
  - JSON never stores: ibrav, alat, celldm, etc.

**Files to Modify**:
- `docs/SCHEMA.md` - Add Structure JSON Schema section
- `docs/QE_SCHEMA_STORAGE.md` (new) - Detailed QE → JSON conversion rules

---

### C2: Unit Verification in Tests
**Status**: No test explicitly verifies lattice matrix is in Å.

**Issue**: 
- Constitution states unit is Å, but no test enforces it.

**Suggested Fix**:
- Add test that reads/writes structure and verifies lattice values match expected Å values.

**Files to Modify**:
- `tests/unit/test_structure_io_units.py` (new)

---

## [D] Pseudopotential SHA/SHATOKEN

### D1: ADR Documentation Missing
**Status**: Code implements SHA/SHATOKEN, but no ADR documents explain the design decision.

**Location**: See [`IMPLEMENTATION_NOTES.md`](IMPLEMENTATION_NOTES.md#d-pseudopotential-shashatoken-implementation) for function locations:
- SHA256: `src/quantumvitas/core/pseudo_provenance.py:56`
- SHATOKEN: `src/quantumvitas/core/pseudo_libinfo.py:95`

**Issue**: 
- Constitution requires this distinction, but it's not documented as an ADR.
- Risk: Future contributors/AI might not understand the difference.

**Suggested Fix**:
- Create `docs/adr/ADR-004.md` - SHA256 identity design
- Create `docs/adr/ADR-005.md` - SHATOKEN semantic equivalence design
- Document algorithm boundaries and known limitations (e.g., comment differences, field order).

**Files to Modify**:
- `docs/adr/ADR-004.md` (new)
- `docs/adr/ADR-005.md` (new)

---

### D2: SHATOKEN Algorithm Risk Assessment
**Status**: Current algorithm (whitespace normalization) may not handle all "physically same" cases.

**Location**: `src/quantumvitas/core/pseudo_libinfo.py:71-92`

**Issue**: 
- Algorithm doesn't handle:
  - Comment differences (e.g., `# comment` will change sha_token)
  - Field order differences (e.g., XML attribute order)
- Constitution acknowledges this but doesn't document the risk.

**Suggested Fix**:
- Document known limitations in ADR-005.
- Consider adding test cases for edge cases (comment differences, etc.).

**Files to Modify**:
- `docs/adr/ADR-005.md` (new) - Document limitations
- `tests/unit/test_pseudo_provenance.py` - Add edge case tests

---

## [E] Windows Toolchain

### E1: ADR Documentation Missing
**Status**: No ADR document explains why oneAPI+MKL is chosen over MinGW.

**Location**: No `docs/adr/ADR-007.md`

**Issue**: 
- Constitution requires this, but it's not documented.
- Risk: Future contributors/AI might suggest MinGW route.

**Suggested Fix**:
- Create `docs/adr/ADR-007.md` - Windows Toolchain decision
- Document reasons: performance, stability, HPC compatibility

**Files to Modify**:
- `docs/adr/ADR-007.md` (new)

---

### E2: Windows Build Guide Missing
**Status**: No guide for building on Windows with oneAPI+MKL.

**Issue**: 
- Constitution states the direction, but no practical guide exists.

**Suggested Fix**:
- Create `docs/WINDOWS_TOOLCHAIN.md` - Build guide for Windows
- Document: oneAPI installation, MKL setup, MPI configuration

**Files to Modify**:
- `docs/WINDOWS_TOOLCHAIN.md` (new)

---

### E3: Windows CI Missing
**Status**: `.github/workflows/tests.yml` only has ubuntu-22.04 and macos-14.

**Issue**: 
- Constitution acknowledges this is "not yet done", but should be tracked.

**Suggested Fix**:
- Windows CI is not yet integrated in this repo (not a technical limitation, just not done yet). Track as low priority.

**Files to Modify**:
- `.github/workflows/tests.yml` - Add Windows matrix when ready

---

## Summary

### High Priority (Should Do Soon)
- **A1**: Persistent cache for resource index
- **D1**: ADR documentation for SHA/SHATOKEN
- **E1**: ADR documentation for Windows toolchain

### Medium Priority (Nice to Have)
- **A2**: Cache invalidation strategy documentation
- **A3**: Consistency validation
- **C1**: Schema documentation
- **E2**: Windows build guide

### Low Priority (Can Wait)
- **B1**: BOUNDARY_FRAC_TOL value consistency (may be intentional)
- **B2**: Cross-platform bond count test
- **C2**: Unit verification in tests
- **D2**: SHATOKEN algorithm risk assessment (document limitations)
- **E3**: Windows CI (track but not urgent)

---

## Notes

- All improvements should be done via **small, focused PRs**.
- No large refactoring.
- Each PR should be independently testable and reviewable.
- Tests should be added for any new functionality.

