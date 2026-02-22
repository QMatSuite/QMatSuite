# IMPORT_STRUCTURE Fix Plan

**Date**: 2026-01-18  
**Status**: ✅ COMPLETED (v2.2 - Deterministic Quantization Fix)  
**PR Title**: `fix: unify fingerprint for Structure and Molecule (single entrypoint, no re-wrap)`

---

## CHANGELOG

| Version | Date | Summary |
|---------|------|---------|
| 2.2 | 2026-01-XX | **FIX**: Deterministic quantization rule; forbid np.round(); add knife-edge regression tests. |
| 2.1 | 2026-01-18 | **BREAKING**: Removed `np.mod()` from fingerprint. Moved COG shift to canonicalization phase. Fingerprint is now pure (no geometry transforms). |
| 2.0 | 2026-01-18 | Initial plan with fingerprint doing wrap + COG shift |

---

## 1. Overview

This PR:
1. Removes the Molecule hash fork from `import_structure()`
2. Establishes a single fingerprint entrypoint that is **pure** (no geometry transforms)
3. Moves all geometry normalization to the **canonicalization phase** (import/read time)

**Key Insight**: The original plan (v2.0) had fingerprint re-wrapping PBC coords via `np.mod(frac, 1.0)`. This reintroduced the knife-edge instability that the existing PBC canonicalization deliberately avoids. The fix is to make fingerprint a pure hash function that trusts input is already canonicalized.

**Scope**:
- Add unified fingerprint function (pure, no transforms)
- Add molecule canonicalization (COG shift)
- Add unified canonicalization dispatch
- Remove the `json.dumps()` hash fork from `api.py`
- Update all call sites

**Non-scope**:
- No changes to existing PBC canonicalization logic
- No rotational invariance
- No symmetry handling

---

## 2. Architecture: Two Phases

| Phase | Function | Responsibility | Geometry Transforms |
|-------|----------|----------------|---------------------|
| Canonicalization | `canonicalize_structure_like_in_place()` | Normalize coords to stable representation | YES |
| Fingerprint | `structure_like_fingerprint()` | Quantize + hash | **NO** |

**Call Order** (at import/read time):
```
1. Load object from file/source
2. canonicalize_structure_like_in_place(obj)  # Geometry transforms here
3. fingerprint = structure_like_fingerprint(obj)  # Pure hash
4. Store obj + fingerprint
```

---

## 3. File Changes Summary

| File | Action | Description | Status |
|------|--------|-------------|--------|
| `src/qmatsuite/core/structure_fingerprint.py` | MODIFY | Add pure fingerprint functions (NO transforms) | ✅ DONE |
| `src/qmatsuite/core/structure_canonicalize.py` | CREATE | New module for unified canonicalization | ✅ DONE |
| `src/qmatsuite/api.py` | MODIFY | Call canonicalize before fingerprint; remove hash fork | ✅ DONE |
| `src/qmatsuite/execution/executor.py` | MODIFY | Use unified fingerprint | ✅ DONE |
| `src/qmatsuite/execution/orca_relax_parser.py` | MODIFY | Canonicalize before writing current.json | ✅ DONE |
| `src/qmatsuite/execution/pyscf_relax_handler.py` | MODIFY | Canonicalize before writing current.json | ✅ DONE |
| `src/qmatsuite/execution/handlers.py` | MODIFY | Canonicalize QE relax output before writing | ✅ DONE |
| `src/qmatsuite/io/structure_io.py` | MODIFY | Remove duplicate or wrap | ✅ DONE |
| `tests/unit/test_structure_fingerprint.py` | MODIFY | Update tests per matrix | ✅ DONE |

---

## 4. Implementation Steps

### ✅ Step 1: Create Unified Canonicalization Module

**File**: `src/qmatsuite/core/structure_canonicalize.py` (NEW)

```python
"""
Unified canonicalization for Structure and Molecule.

This module provides the ONLY place where geometry transforms happen.
Called at import/read/parse time.
"""

from __future__ import annotations

import numpy as np
from pymatgen.core import Structure as PMGStructure
from pymatgen.core import Molecule as PMGMolecule
from typing import Union

from qmatsuite.analysis.structure_viz import canonicalize_structure_in_place


def canonicalize_structure_like_in_place(obj: Union[PMGStructure, PMGMolecule]) -> None:
    """
    Canonicalize a structure-like object in place.
    
    For Structure: wraps frac coords to [-WRAP_TOL, 1-WRAP_TOL)
    For Molecule: centers at origin (COG shift)
    
    This is the ONLY place geometry transforms happen.
    Must be called at import/read/parse time BEFORE fingerprinting.
    
    Args:
        obj: pymatgen Structure or Molecule (modified in place)
    """
    if isinstance(obj, PMGMolecule):
        _canonicalize_molecule_in_place(obj)
    elif isinstance(obj, PMGStructure):
        canonicalize_structure_in_place(obj)  # existing function
    # else: pass silently for other types (or raise TypeError if strict)


def _canonicalize_molecule_in_place(molecule: PMGMolecule) -> None:
    """
    Canonicalize a Molecule by centering at origin (COG shift).
    
    Computes center-of-geometry and subtracts from all positions.
    This ensures translation invariance for fingerprinting.
    
    Args:
        molecule: pymatgen Molecule (modified in place)
    """
    if len(molecule) == 0:
        return
    
    # Compute center-of-geometry
    coords = np.array([site.coords for site in molecule])
    cog = coords.mean(axis=0)
    
    # Shift all sites by -COG
    for i, site in enumerate(molecule):
        new_coords = site.coords - cog
        molecule.replace(i, site.specie, new_coords, coords_are_cartesian=True)
```

---

### ✅ Step 1.5: Add Quantization Helper (Single Entrypoint)

**File**: `src/qmatsuite/core/structure_fingerprint.py`

**Add quantization helper function** (before `structure_like_fingerprint`):

```python
import math

def quantize_scalar(x: float, tol: float) -> int:
    """
    Deterministic quantization: q = floor(x / tol + 0.5 + eps).
    
    This replaces np.round() to avoid banker's rounding instability.
    Banker's rounding (ties-to-even) causes half-integers to flip with tiny noise.
    
    Args:
        x: Value to quantize
        tol: Tolerance (same units as x)
        
    Returns:
        Quantized integer value
    """
    eps = 1e-12  # Dimensionless, ensures ties round up
    return int(math.floor(x / tol + 0.5 + eps))


def quantize_array(arr: np.ndarray, tol: float) -> np.ndarray:
    """
    Vectorized deterministic quantization.
    
    Args:
        arr: Array of values to quantize
        tol: Tolerance (same units as arr)
        
    Returns:
        Array of quantized integers (int64)
    """
    eps = 1e-12
    return np.floor(arr / tol + 0.5 + eps).astype(np.int64)
```

**Unit conventions**:
- Molecule: Use `tol_ang` on cartesian coordinates and lattice vectors (both in Angstrom)
- PBC: Use `tol_ang` for lattice matrix (Angstrom) and `frac_tol = tol_ang / min(|a|,|b|,|c|)` for fractional coordinates

**CRITICAL**: Replace ALL uses of `round()` / `np.round()` inside fingerprint implementations with this helper. DO NOT change canonicalization logic. Do not add wrapping/mod.

---

### ✅ Step 2: Update Fingerprint Functions (Remove Transforms)

**File**: `src/qmatsuite/core/structure_fingerprint.py`

**Update imports** (after line 27):

```python
from pymatgen.core import Molecule as PMGMolecule
from typing import Union
```

**Replace `_fingerprint_pbc_structure()`** with (NO mod/wrap):

```python
def _fingerprint_pbc_structure(structure: PMGStructure, tol_ang: float) -> str:
    """
    Fingerprint for PBC Structure.
    
    CRITICAL: This function does NO geometry transforms.
    It assumes the structure is already canonicalized.
    
    Algorithm:
    1. Compute fractional tolerance
    2. Quantize lattice matrix (NO transforms)
    3. Quantize fractional coords AS-IS (NO mod, NO wrap)
    4. Sort sites deterministically
    5. Build payload and hash
    """
    # 1. Compute fractional tolerance
    a, b, c = structure.lattice.abc
    min_length = min(a, b, c)
    if min_length < 1e-10:
        raise ValueError(f"Lattice vector too small: min={min_length}")
    frac_tol = tol_ang / min_length
    
    # 2. Quantize lattice matrix (in Angstrom) - NO transforms
    # Use deterministic quantization (NOT np.round)
    lattice_matrix = structure.lattice.matrix
    lattice_q = quantize_array(lattice_matrix / tol_ang, tol=1.0)
    
    # 3. Quantize fractional coordinates AS-IS - NO mod, NO wrap
    # Structure is assumed to be already canonicalized
    # Use deterministic quantization (NOT np.round)
    frac_coords = structure.frac_coords  # Use directly
    frac_q = quantize_array(frac_coords / frac_tol, tol=1.0)
    
    # 4. Get species symbols
    species = [site.specie.symbol for site in structure]
    
    # 5. Sort sites deterministically: (element, fx_q, fy_q, fz_q)
    site_data = [
        (elem, int(fx), int(fy), int(fz))
        for elem, (fx, fy, fz) in zip(species, frac_q)
    ]
    site_data_sorted = sorted(site_data, key=lambda x: (x[0], x[1], x[2], x[3]))
    
    # 6. Build payload
    payload_parts = ["PBC"]
    payload_parts.append("lat")
    for row in lattice_q:
        for val in row:
            payload_parts.append(str(int(val)))
    payload_parts.append("sites")
    for elem, fx, fy, fz in site_data_sorted:
        payload_parts.append(f"{elem}:{fx}:{fy}:{fz}")
    
    # Hash
    payload = "|".join(payload_parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

**Replace `_fingerprint_molecule()`** with (NO COG shift):

```python
def _fingerprint_molecule(molecule: PMGMolecule, tol_ang: float) -> str:
    """
    Fingerprint for Molecule.
    
    CRITICAL: This function does NO geometry transforms.
    It assumes the molecule is already canonicalized (centered at origin).
    
    Algorithm:
    1. Get Cartesian coordinates AS-IS (already centered)
    2. Quantize coordinates (NO COG shift here)
    3. Sort sites deterministically
    4. Build payload and hash
    """
    # 1. Get Cartesian coordinates AS-IS - already canonicalized
    coords = np.array([site.coords for site in molecule])
    
    # 2. Quantize coordinates - NO COG shift, NO transform
    # Use deterministic quantization (NOT np.round)
    if len(coords) > 0:
        coords_q = quantize_array(coords / tol_ang, tol=1.0)
    else:
        coords_q = np.array([], dtype=np.int64).reshape(0, 3)
    
    # 3. Get species symbols
    species = [site.specie.symbol for site in molecule]
    
    # 4. Sort sites deterministically: (element, x_q, y_q, z_q)
    site_data = [
        (elem, int(x), int(y), int(z))
        for elem, (x, y, z) in zip(species, coords_q)
    ]
    site_data_sorted = sorted(site_data, key=lambda x: (x[0], x[1], x[2], x[3]))
    
    # 5. Build payload
    payload_parts = ["MOL", "sites"]
    for elem, x, y, z in site_data_sorted:
        payload_parts.append(f"{elem}:{x}:{y}:{z}")
    
    # Hash
    payload = "|".join(payload_parts)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()
```

---

### ✅ Step 3: Update api.py

**File**: `src/qmatsuite/api.py`

**Update dedup section** (around lines 397-410):

```python
if dedup_by_fingerprint:
    from qmatsuite.core.structure_fingerprint import structure_like_fingerprint
    from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place
    
    # Canonicalize first, then fingerprint
    canonicalize_structure_like_in_place(structure)
    fingerprint = structure_like_fingerprint(structure, tol_ang=1e-3)
```

**Update fingerprint storage section** (around lines 431-447):

```python
# Compute fingerprint for storage (even if not using for dedup)
from qmatsuite.core.structure_fingerprint import structure_like_fingerprint
from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place

# Canonicalize if not already done in dedup path
if not dedup_by_fingerprint:
    canonicalize_structure_like_in_place(structure)

# Unified fingerprint for both Structure and Molecule
fingerprint = structure_like_fingerprint(structure, tol_ang=1e-3)
```

---

### ✅ Step 4: Update Relax Handlers to Canonicalize Before Writing

**File**: `src/qmatsuite/execution/orca_relax_parser.py`

In `handle_orca_relax_output()`, after parsing the molecule:

```python
from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place

# After parsing molecule from output...
canonicalize_structure_like_in_place(molecule)
write_generated_structure(molecule, calc_dir, step_ulid)
```

**File**: `src/qmatsuite/execution/pyscf_relax_handler.py`

In `handle_pyscf_relax_output()`, after creating the molecule:

```python
from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place

# After creating molecule from results...
canonicalize_structure_like_in_place(molecule)
write_generated_structure(molecule, calc_dir, step_ulid)
```

**File**: `src/qmatsuite/execution/handlers.py`

In `handle_qe_relax_output()`, after parsing the structure:

```python
from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place

# After parsing structure from QE output...
canonicalize_structure_like_in_place(structure)
write_generated_structure(structure, calc_dir, step_ulid)
```

---

### ✅ Step 5: Update executor.py

**File**: `src/qmatsuite/execution/executor.py`

**Update import**:

```python
from qmatsuite.core.structure_fingerprint import structure_like_fingerprint
```

**Update usage** (line ~751):

```python
# Structure read from current.json is already canonicalized (was canonicalized before writing)
effective_structure_sha = structure_like_fingerprint(structure, tol_ang=1e-3)
```

---

### ✅ Step 6: Handle Duplicate in structure_io.py

**File**: `src/qmatsuite/io/structure_io.py`

Make it a wrapper that delegates to the canonical implementation:

```python
def structure_fingerprint(structure: PMGStructure, tol: float = 1e-5) -> str:
    """
    Generate a deterministic fingerprint for a structure.
    
    Deprecated: Use qmatsuite.core.structure_fingerprint.structure_like_fingerprint()
    """
    from qmatsuite.core.structure_fingerprint import structure_like_fingerprint
    return structure_like_fingerprint(structure, tol_ang=tol)
```

---

## 5. Pseudocode Summary

### 5.1 Canonicalization Phase

```
FUNCTION canonicalize_structure_like_in_place(obj):
    IF obj is Molecule:
        coords = GET all cartesian coords
        cog = MEAN(coords)
        FOR each site:
            site.coords = site.coords - cog
    ELIF obj is Structure:
        CALL existing canonicalize_structure_in_place(obj)
        # Wraps to [-WRAP_TOL, 1-WRAP_TOL)
```

### 5.2 Fingerprint Phase (PURE)

```
FUNCTION structure_like_fingerprint(obj, tol_ang):
    # NO geometry transforms - obj is already canonicalized
    IF obj is Molecule:
        RETURN _fingerprint_molecule(obj, tol_ang)
    ELIF obj is Structure:
        RETURN _fingerprint_pbc_structure(obj, tol_ang)
    ELSE:
        RAISE TypeError

FUNCTION _fingerprint_pbc_structure(structure, tol_ang):
    # NO mod, NO wrap
    frac_tol = tol_ang / MIN(lattice.abc)
    lattice_q = ROUND(lattice.matrix / tol_ang)
    frac_q = ROUND(frac_coords / frac_tol)  # AS-IS, no mod
    site_data = SORT(species, frac_q)
    payload = "PBC|lat|..." + site_data
    RETURN SHA256(payload)

FUNCTION _fingerprint_molecule(molecule, tol_ang):
    # NO COG shift - already centered
    coords_q = ROUND(coords / tol_ang)  # AS-IS
    site_data = SORT(species, coords_q)
    payload = "MOL|sites|..." + site_data
    RETURN SHA256(payload)
```

---

## 6. Call Flow Diagram

```
import_structure(file_or_obj)
    │
    ├─> Load/parse object
    │
    ├─> canonicalize_structure_like_in_place(obj)
    │       │
    │       ├─> Structure: canonicalize_structure_in_place()
    │       │       └─> Wrap to [-WRAP_TOL, 1-WRAP_TOL)
    │       │
    │       └─> Molecule: _canonicalize_molecule_in_place()
    │               └─> COG shift to center at origin
    │
    ├─> fingerprint = structure_like_fingerprint(obj)
    │       │
    │       └─> Pure: quantize + sort + hash (NO transforms)
    │
    └─> Store obj + fingerprint
```

---

## 7. Backward Compatibility

### 7.1 Fingerprint Value Changes

**PBC Structures**: Fingerprint values will change for structures where:
- Coordinates were not already in the canonical interval

This is acceptable because:
1. Fingerprints are not persisted as primary identifiers (ULIDs are)
2. Fingerprints are used for stale detection, not identity
3. The new fingerprints are more stable (no knife-edge)

### 7.2 Molecule Fingerprint

**Before**: No fingerprint or `json.dumps()` hash or fingerprint-time COG shift  
**After**: Fingerprint with canonicalization-time COG shift

This is a fix, not a regression.

---

## 8. Implications for Implementation

Cursor Auto must:

1. **Create** `src/qmatsuite/core/structure_canonicalize.py` with:
   - `canonicalize_structure_like_in_place()`
   - `_canonicalize_molecule_in_place()`

2. **Modify** `src/qmatsuite/core/structure_fingerprint.py`:
   - Remove `np.mod(frac, 1.0)` from `_fingerprint_pbc_structure()`
   - Remove COG shift from `_fingerprint_molecule()`

3. **Modify** `src/qmatsuite/api.py`:
   - Call `canonicalize_structure_like_in_place()` before fingerprint
   - Remove the `json.dumps()` hash fork

4. **Modify** relax handlers to canonicalize before writing `current.json`:
   - `orca_relax_parser.py`
   - `pyscf_relax_handler.py`
   - `handlers.py` (QE)

5. **Update tests** per the test matrix

---

## 9. Review Checklist

- [x] `structure_canonicalize.py` created with dispatch function
- [x] `_canonicalize_molecule_in_place()` implements COG shift
- [x] `_fingerprint_pbc_structure()` has NO `mod` or wrap
- [x] `_fingerprint_molecule()` has NO COG shift
- [x] `import_structure()` calls canonicalize before fingerprint
- [x] Relax handlers canonicalize before writing `current.json`
- [x] No `json.dumps()` hashing anywhere
- [x] Knife-edge regression test passes
- [x] All existing tests pass
