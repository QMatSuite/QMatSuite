# Legacy Dedup Functions Removal Review

**Date**: 2026-01-18  
**Author**: Opus (Code Auditor)  
**Status**: READY FOR IMPLEMENTATION

---

## 1. Executive Summary

This review documents two legacy functions that violate the two-phase fingerprint contract and must be completely removed from production code:

| Function | Location | Lines | Problem |
|----------|----------|-------|---------|
| `canonicalize_structure_for_identity()` | `src/quantumvitas/core/structure_fingerprint.py` | 33-82 | Uses `np.mod(frac, 1.0)` |
| `structures_semantically_equal()` | `src/quantumvitas/core/structure_fingerprint.py` | 318-384 | Calls `canonicalize_structure_for_identity()` |

**Contract Violation**: Both functions use `np.mod()` for coordinate wrapping, which can produce different results than the deterministic quantization rule (`floor(x/tol + 0.5 + eps)`) used by the canonical fingerprint path. This creates a potential for knife-edge instability and false negatives in deduplication.

**Decision**: Remove all production usage and delete both functions entirely.

---

## 2. Function Definitions

### 2.1 `canonicalize_structure_for_identity()`

**File**: `src/quantumvitas/core/structure_fingerprint.py`  
**Lines**: 33-82

```python
def canonicalize_structure_for_identity(structure: PMGStructure) -> PMGStructure:
    """
    LEGACY: Canonicalize a structure for identity comparison.
    
    ⚠️ WARNING: This function uses `np.mod()` which violates the two-phase contract.
    ...
    """
    canon = structure.copy()
    for i, site in enumerate(canon):
        frac = np.array(site.frac_coords)
        frac_fingerprint = np.mod(frac, 1.0)  # ← VIOLATION: uses np.mod()
        canon.replace(i, site.specie, frac_fingerprint, coords_are_cartesian=False)
    return canon
```

**What it does**:
1. Copies the structure
2. Applies `np.mod(frac_coords, 1.0)` to wrap to [0, 1)
3. Returns modified structure

**Why it violates contract**:
- Uses `np.mod()` instead of the canonical `canonicalize_structure_in_place()` from `structure_viz.py`
- The canonical path wraps to `[-WRAP_TOL, 1-WRAP_TOL)`, not `[0, 1)`
- Creates inconsistency with the two-phase architecture where canonicalization happens at import/read time via `canonicalize_structure_like_in_place()`

### 2.2 `structures_semantically_equal()`

**File**: `src/quantumvitas/core/structure_fingerprint.py`  
**Lines**: 318-384

```python
def structures_semantically_equal(
    a: PMGStructure,
    b: PMGStructure,
    tol: float = 1e-5,
) -> bool:
    """
    LEGACY: Check if two structures are semantically equal after canonicalization.
    
    ⚠️ WARNING: This function uses `canonicalize_structure_for_identity()` which uses `np.mod()`.
    ...
    """
    canon_a = canonicalize_structure_for_identity(a)  # ← VIOLATION: calls legacy function
    canon_b = canonicalize_structure_for_identity(b)
    # ... comparison logic
```

**What it does**:
1. Canonicalizes both structures using the legacy function
2. Compares compositions
3. Compares lattice matrices (with tolerance)
4. Compares sorted fractional coordinates (with tolerance)

**Why it violates contract**:
- Calls `canonicalize_structure_for_identity()` which uses `np.mod()`
- Uses different tolerance (`1e-5`) than the SSOT fingerprint tolerance (`1e-3`)
- Reintroduces geometry transforms in a verification step, violating "fingerprint is pure quantize+hash"

---

## 3. Production Call Sites

### 3.1 `api.py` — `import_structure()` (Lines 417-428)

**File**: `src/quantumvitas/api.py`  
**Lines**: 417-428

```python
# Verify with semantic equality as belt-and-suspenders
# Note: structures_semantically_equal only supports Structure (not Molecule)
from quantumvitas.core.structure_fingerprint import structures_semantically_equal
from pymatgen.core import Structure as PMGStructure

existing_structure = read_structure(struct_file)

# Only apply semantic check for Structure (not Molecule)
is_semantic_match = True
if isinstance(structure, PMGStructure) and isinstance(existing_structure, PMGStructure):
    is_semantic_match = structures_semantically_equal(structure, existing_structure)

if is_semantic_match:
    # Reuse existing structure
```

**Context**: Inside `import_structure()` deduplication logic. After finding a fingerprint match, it calls `structures_semantically_equal()` as a secondary verification. This is the "belt-and-suspenders" pattern that must be removed.

### 3.2 `api.py` — `import_from_qe_directory()` (Lines 5868-5890)

**File**: `src/quantumvitas/api.py`  
**Lines**: 5868-5890

```python
# Compute fingerprint for content-based deduplication
from quantumvitas.core.structure_fingerprint import structure_fingerprint, structures_semantically_equal
fingerprint = structure_fingerprint(structure)

# ... fingerprint matching loop ...

if existing_fingerprint == fingerprint:
    # Found matching structure by fingerprint
    existing_id = struct_meta.get("id")
    if existing_id:
        # Verify with semantic equality as belt-and-suspenders
        existing_structure = read_structure(struct_file)
        if structures_semantically_equal(structure, existing_structure):
            structure_id_value = existing_id
            break
```

**Context**: Inside `import_from_qe_directory()` (or similar QE import flow). Same "belt-and-suspenders" pattern.

---

## 4. Test References

### 4.1 Direct Tests in `test_structure_fingerprint.py`

**File**: `tests/unit/test_structure_fingerprint.py`

| Test | Lines | Description |
|------|-------|-------------|
| `test_canonicalize_structure_for_identity` | 86-92 | Tests legacy canonicalization produces coords in [0,1) |
| `test_canonicalize_preserves_structure` | 94-101 | Tests legacy canonicalization preserves composition/lattice |
| `TestStructuresSemanticallyEqual::test_semantically_equal_identical` | 107-110 | Tests identical structures |
| `TestStructuresSemanticallyEqual::test_semantically_equal_tiny_perturbations` | 112-115 | Tests small perturbations |
| `TestStructuresSemanticallyEqual::test_semantically_equal_different` | 117-120 | Tests different structures |
| `TestStructuresSemanticallyEqual::test_semantically_equal_different_composition` | 122-131 | Tests different compositions |

**Import at top of file** (lines 13-17):
```python
from quantumvitas.core.structure_fingerprint import (
    canonicalize_structure_for_identity,
    structure_fingerprint,
    structure_like_fingerprint,
    structures_semantically_equal,
    ...
)
```

### 4.2 Why These Tests Exist

These tests were written before the two-phase architecture was established. They test the legacy functions in isolation but do not validate the production fingerprint-only dedup path. They must be deleted.

---

## 5. Documentation References

### 5.1 `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md` (Lines 346-347)

```
├── structures_semantically_equal()   # LEGACY: belt-and-suspenders verification only (uses np.mod)
└── canonicalize_structure_for_identity()  # LEGACY: only used by structures_semantically_equal (uses np.mod)
```

Currently marked as LEGACY. After deletion, these lines must be removed entirely with a note that they were deleted.

### 5.2 `docs/reviews/PR_FINGERPRINT_TOL_SSOT_REVIEW.md` (Line 115)

```
1. **Low**: `canonicalize_structure_for_identity()` (legacy function at line 33-73) still uses `np.mod`. 
   This is only used in `structures_semantically_equal()` which is a secondary verification function, 
   not the main fingerprint path. **No action required** unless that function is called in production paths.
```

This risk is now being addressed. Update to note deletion.

### 5.3 `docs/reviews/IMPORT_STRUCTURE_AUDIT.md` (Lines 46-47, 170)

References these functions as existing. Update to note deletion.

### 5.4 `docs/archive/2025-12/import/STRUCTURE_FINGERPRINT_IMPLEMENTATION.md` (Lines 6-10)

References these functions. This is an archive, so no update needed, but note for completeness.

---

## 6. Risk Assessment

| Risk | Severity | Mitigation |
|------|----------|------------|
| Fingerprint collision leading to wrong dedup | Low | Fingerprint uses deterministic quantization; collision is mathematically rare |
| Removing "safety check" exposes bugs | None | If fingerprints match, structures are identical within tolerance by definition |
| Behavioral change in edge cases | Low | Current belt-and-suspenders uses different tolerance (1e-5 vs 1e-3); removing it makes behavior consistent |

**Conclusion**: The belt-and-suspenders check adds complexity without safety. Fingerprint identity is the correct and sufficient criterion.

---

## 7. Acceptance Criteria for Removal

1. `rg "canonicalize_structure_for_identity|structures_semantically_equal" src/` returns 0 matches
2. `rg "canonicalize_structure_for_identity|structures_semantically_equal" tests/` returns 0 matches
3. Dedup in `import_structure()` uses fingerprint comparison only (no secondary check)
4. Dedup in `import_from_qe_directory()` uses fingerprint comparison only (no secondary check)
5. All tests pass
6. No new identity/comparison logic is introduced

