# Dedup Fingerprint-Only Implementation Plan

**Date**: 2026-01-18  
**Author**: Opus (Code Auditor)  
**Target**: Cursor Auto (single PR)  
**Depends on**: `docs/reviews/DEDUP_LEGACY_REMOVAL_REVIEW.md`

---

## Goal

Remove all production usage of `canonicalize_structure_for_identity()` and `structures_semantically_equal()`, then delete both functions from the codebase entirely.

After this PR:
- Dedup == fingerprint identity (sole criterion)
- No geometry transforms in dedup verification
- No `np.mod()` in any fingerprint/dedup path

---

## Step A: Replace Production Dedup Logic

### A.1 Update `import_structure()` in `api.py` (Lines 417-436)

**Current code** (lines 413-436):
```python
if existing_fingerprint == fingerprint:
    existing_fingerprint_id = struct_meta.get("id")
    if existing_fingerprint_id:
        # Verify with semantic equality as belt-and-suspenders
        from qmatsuite.core.structure_fingerprint import structures_semantically_equal
        from pymatgen.core import Structure as PMGStructure
        
        existing_structure = read_structure(struct_file)
        
        is_semantic_match = True
        if isinstance(structure, PMGStructure) and isinstance(existing_structure, PMGStructure):
            is_semantic_match = structures_semantically_equal(structure, existing_structure)
        
        if is_semantic_match:
            # Reuse existing structure
            from qmatsuite.core.resolution import require_structure
            resolved = require_structure(...)
            return resolved
```

**Replace with** (fingerprint-only):
```python
if existing_fingerprint == fingerprint:
    existing_fingerprint_id = struct_meta.get("id")
    if existing_fingerprint_id:
        # Fingerprint match is sufficient for dedup (no secondary check)
        from qmatsuite.core.resolution import require_structure
        resolved = require_structure(
            project_root, existing_fingerprint_id, config=config, index=index
        )
        return resolved
```

**Changes**:
- Remove import of `structures_semantically_equal`
- Remove import of `PMGStructure` (if no longer needed)
- Remove `existing_structure = read_structure(struct_file)` (no longer needed for comparison)
- Remove `is_semantic_match` variable and conditional
- Simplify to: if fingerprint matches → return existing resource

### A.2 Update `import_from_qe_directory()` in `api.py` (Lines 5868-5892)

**Current code** (lines 5868-5892):
```python
from qmatsuite.core.structure_fingerprint import structure_fingerprint, structures_semantically_equal
fingerprint = structure_fingerprint(structure)

# ... loop ...
if existing_fingerprint == fingerprint:
    existing_id = struct_meta.get("id")
    if existing_id:
        # Verify with semantic equality as belt-and-suspenders
        existing_structure = read_structure(struct_file)
        if structures_semantically_equal(structure, existing_structure):
            structure_id_value = existing_id
            break
```

**Replace with** (fingerprint-only):
```python
from qmatsuite.core.structure_fingerprint import structure_fingerprint
fingerprint = structure_fingerprint(structure)

# ... loop ...
if existing_fingerprint == fingerprint:
    existing_id = struct_meta.get("id")
    if existing_id:
        # Fingerprint match is sufficient for dedup
        structure_id_value = existing_id
        break
```

**Changes**:
- Remove `structures_semantically_equal` from import
- Remove `existing_structure = read_structure(struct_file)` call
- Remove the semantic equality check conditional
- Simplify to: if fingerprint matches → use existing id

---

## Step B: Verify No Other Production Usage

Run grep to confirm no other production call sites:

```bash
rg "structures_semantically_equal|canonicalize_structure_for_identity" src/ --type py
```

Expected remaining matches after Step A: **only the function definitions** in `structure_fingerprint.py` (which we delete in Step D).

If any other call sites are found, update them following the same pattern: remove the semantic equality check and use fingerprint only.

---

## Step C: Update Tests

### C.1 Delete Legacy Function Tests

**File**: `tests/unit/test_structure_fingerprint.py`

Delete these tests/sections:

1. **Lines 86-101**: Delete `test_canonicalize_structure_for_identity` and `test_canonicalize_preserves_structure`

2. **Lines 104-131**: Delete entire `TestStructuresSemanticallyEqual` class:
   - `test_semantically_equal_identical`
   - `test_semantically_equal_tiny_perturbations`
   - `test_semantically_equal_different`
   - `test_semantically_equal_different_composition`

3. **Lines 13-17**: Update imports to remove:
   ```python
   canonicalize_structure_for_identity,
   structures_semantically_equal,
   ```

### C.2 Add/Verify Fingerprint-Only Dedup Tests

Verify these tests exist (or add if missing). They should be in `tests/unit/test_structure_fingerprint.py` or `tests/integration/test_api.py`:

#### Test 1: Same structure imports return same resource ID

```python
def test_import_same_structure_twice_returns_same_id(tmp_path):
    """Importing the same structure twice should return the same resource."""
    project_root = QMSService.init_project(tmp_path / "proj")
    
    # Create a simple structure
    lattice = Lattice.cubic(5.43)
    species = ["Si", "Si"]
    coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
    structure = Structure(lattice, species, coords)
    
    # Import twice
    result1 = QMSService.import_structure(project_root, structure)
    result2 = QMSService.import_structure(project_root, structure, dedup_by_fingerprint=True)
    
    # Should return same resource ID
    assert result1.id == result2.id
```

#### Test 2: Small noise below tolerance returns same resource

```python
def test_import_structure_small_noise_dedup(tmp_path):
    """Small noise within tolerance should return same resource (dedup works)."""
    project_root = QMSService.init_project(tmp_path / "proj")
    
    # Create base structure
    lattice = Lattice.cubic(5.43)
    species = ["Si", "Si"]
    coords = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
    structure1 = Structure(lattice, species, coords)
    
    # Add tiny noise (well within tol_ang=1e-3, away from boundaries)
    # Use 0.25 + 0.0001 (not near 0.5 boundary)
    coords_noisy = [[0.0001, 0.0001, 0.0001], [0.2501, 0.2501, 0.2501]]
    structure2 = Structure(lattice, species, coords_noisy)
    
    result1 = QMSService.import_structure(project_root, structure1)
    result2 = QMSService.import_structure(project_root, structure2, dedup_by_fingerprint=True)
    
    # Should return same resource (noise absorbed by quantization)
    assert result1.id == result2.id
```

#### Test 3: Structural difference above tolerance creates new resource

```python
def test_import_different_structure_creates_new(tmp_path):
    """Significantly different structure should create new resource."""
    project_root = QMSService.init_project(tmp_path / "proj")
    
    # Create two different structures
    lattice = Lattice.cubic(5.43)
    species = ["Si", "Si"]
    coords1 = [[0.0, 0.0, 0.0], [0.25, 0.25, 0.25]]
    coords2 = [[0.0, 0.0, 0.0], [0.5, 0.5, 0.5]]  # Different structure
    
    structure1 = Structure(lattice, species, coords1)
    structure2 = Structure(lattice, species, coords2)
    
    result1 = QMSService.import_structure(project_root, structure1)
    result2 = QMSService.import_structure(project_root, structure2, dedup_by_fingerprint=True)
    
    # Should create different resources
    assert result1.id != result2.id
```

If these tests already exist (check `TestQMSServiceDedup` or `TestImportStructureUnifiedFingerprint` classes), verify they pass without the legacy functions.

---

## Step D: Delete Legacy Functions

### D.1 Delete from `structure_fingerprint.py`

**File**: `src/qmatsuite/core/structure_fingerprint.py`

1. **Delete `canonicalize_structure_for_identity()`** (lines 33-82)
2. **Delete `structures_semantically_equal()`** (lines 318-384)

After deletion, verify no dangling references or imports within the file.

### D.2 Update `__all__` if Present

If `structure_fingerprint.py` has an `__all__` list, remove these function names from it.

---

## Step E: Update Documentation

### E.1 Update `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md`

Find lines 346-347:
```
├── structures_semantically_equal()   # LEGACY: belt-and-suspenders verification only (uses np.mod)
└── canonicalize_structure_for_identity()  # LEGACY: only used by structures_semantically_equal (uses np.mod)
```

**Replace with**:
```
# DELETED (2026-01-18): structures_semantically_equal() and canonicalize_structure_for_identity()
# were removed as they used np.mod() and violated the two-phase contract.
# Dedup uses fingerprint identity only. No secondary verification exists.
```

### E.2 Update `docs/reviews/PR_FINGERPRINT_TOL_SSOT_REVIEW.md`

Find line 115 (the "Low risk" item about `canonicalize_structure_for_identity()`).

**Replace with**:
```
1. **RESOLVED**: `canonicalize_structure_for_identity()` and `structures_semantically_equal()` have been 
   deleted from the codebase. Dedup uses fingerprint identity only.
```

### E.3 Update `docs/reviews/IMPORT_STRUCTURE_AUDIT.md`

Find lines 46-47 and 170. Add a note:
```
**NOTE (2026-01-18)**: `canonicalize_structure_for_identity()` and `structures_semantically_equal()` 
have been DELETED. They are no longer part of the codebase.
```

---

## Step F: Final Verification

### F.1 Run grep to confirm deletion

```bash
rg "canonicalize_structure_for_identity|structures_semantically_equal" src/ tests/
```

**Expected output**: No matches (0 results)

### F.2 Run full test suite

```bash
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

**Expected**: All tests pass.

### F.3 Confirm no new identity logic

Review the changes to ensure:
- No new comparison functions were introduced
- Fingerprint matching is the sole dedup criterion
- No `np.mod()` usage in any fingerprint-related code path

---

## Summary Checklist

| Step | Task | File(s) |
|------|------|---------|
| A.1 | Remove semantic check from `import_structure()` | `src/qmatsuite/api.py` |
| A.2 | Remove semantic check from `import_from_qe_directory()` | `src/qmatsuite/api.py` |
| B | Verify no other production usage | grep confirmation |
| C.1 | Delete legacy function tests | `tests/unit/test_structure_fingerprint.py` |
| C.2 | Verify fingerprint-only dedup tests exist | `tests/unit/test_structure_fingerprint.py` |
| D.1 | Delete `canonicalize_structure_for_identity()` | `src/qmatsuite/core/structure_fingerprint.py` |
| D.2 | Delete `structures_semantically_equal()` | `src/qmatsuite/core/structure_fingerprint.py` |
| E.1 | Update SPEC doc | `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md` |
| E.2 | Update SSOT review | `docs/reviews/PR_FINGERPRINT_TOL_SSOT_REVIEW.md` |
| E.3 | Update audit doc | `docs/reviews/IMPORT_STRUCTURE_AUDIT.md` |
| F.1 | Grep confirms 0 matches | - |
| F.2 | All tests pass | - |
| F.3 | No new identity logic | code review |

---

## Acceptance Criteria (copy from review)

1. ✅ `rg "canonicalize_structure_for_identity|structures_semantically_equal" src/` returns 0 matches
2. ✅ `rg "canonicalize_structure_for_identity|structures_semantically_equal" tests/` returns 0 matches
3. ✅ Dedup in `import_structure()` uses fingerprint comparison only
4. ✅ Dedup in `import_from_qe_directory()` uses fingerprint comparison only
5. ✅ All tests pass
6. ✅ No new identity/comparison logic is introduced

