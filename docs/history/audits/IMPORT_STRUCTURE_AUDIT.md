# IMPORT_STRUCTURE Fingerprint Audit

**Date**: 2026-01-18  
**Auditor**: Opus (Code Review Mode)  
**Scope**: Fingerprint logic in `import_structure()` and related functions

---

## 1. Executive Summary

### Critical Finding

**VIOLATION**: `import_structure()` contains a Molecule hash fork that bypasses the canonical fingerprint entrypoint.

**Location**: `src/quantumvitas/api.py:437-446`

**Current Code**:
```python
if isinstance(structure, Molecule):
    # For molecules, use a simple hash of the structure dict
    import hashlib
    structure_dict = structure.as_dict()
    # Remove metadata if present
    structure_dict.pop("__qv_meta__", None)
    structure_str = json.dumps(structure_dict, sort_keys=True)
    fingerprint = hashlib.sha256(structure_str.encode('utf-8')).hexdigest()
else:
    fingerprint = structure_fingerprint(structure)
```

**Problems**:
1. Violates "single entrypoint" invariant
2. `json.dumps()` includes charge, spin_multiplicity, and other fields that should be excluded
3. No translation normalization (two identical molecules at different origins get different fingerprints)
4. Different tolerance semantics than PBC path

---

## 2. Current Code Locations

### 2.1 Fingerprint Functions

| File | Function | Line Range | Purpose |
|------|----------|------------|---------|
| `src/quantumvitas/core/structure_fingerprint.py` | `structure_fingerprint()` | 73-137 | Canonical PBC fingerprint |
| `src/quantumvitas/core/structure_fingerprint.py` | `canonicalize_structure_for_identity()` | **DELETED (2026-01-18)** | Was: PBC canonicalization for fingerprint |
| `src/quantumvitas/core/structure_fingerprint.py` | `structures_semantically_equal()` | **DELETED (2026-01-18)** | Was: Semantic equality check |
| `src/quantumvitas/io/structure_io.py` | `structure_fingerprint()` | 433-498 | **DUPLICATE** - demo fingerprint (should be removed) |

### 2.2 Molecule Hash Fork

| File | Function | Line Range | Issue |
|------|----------|------------|-------|
| `src/quantumvitas/api.py` | `import_structure()` | 437-446 | **VIOLATION**: Separate Molecule hashing |

**Full Context** (`api.py:431-447`):
```python
# Compute fingerprint for storage (even if not using for dedup)
from quantumvitas.core.structure_fingerprint import structure_fingerprint
from pymatgen.core import Molecule
# structure_fingerprint only works for Structure, not Molecule
# For Molecule, we use a simple hash of the structure dict
if isinstance(structure, Molecule):
    # For molecules, use a simple hash of the structure dict
    import hashlib
    structure_dict = structure.as_dict()
    # Remove metadata if present
    structure_dict.pop("__qv_meta__", None)
    structure_str = json.dumps(structure_dict, sort_keys=True)
    fingerprint = hashlib.sha256(structure_str.encode('utf-8')).hexdigest()
else:
    fingerprint = structure_fingerprint(structure)
```

---

## 3. All Call Sites

### 3.1 import_structure() Call Sites

| File | Function/Line | Context |
|------|---------------|---------|
| `src/quantumvitas/daemon/server.py:2204` | `_handle_import_structure()` | Daemon RPC for GUI |
| `src/quantumvitas/cli/main.py:1316-1393` | `import_structure_command()` | CLI command |
| `src/quantumvitas/api.py:4747` | `promote_relax_structure()` | Promote relax output |
| `tests/unit/test_structure_fingerprint.py` | Multiple test methods | Unit tests |
| `tests/unit/test_api_service.py` | Multiple test methods | API tests |
| `tests/daemon/test_*` | Multiple daemon tests | Integration tests |

### 3.2 structure_fingerprint() Call Sites

| File | Line | Context |
|------|------|---------|
| `src/quantumvitas/api.py:399` | Dedup check in `import_structure()` | `dedup_by_fingerprint=True` path |
| `src/quantumvitas/api.py:406` | Dedup check in `import_structure()` | Structure fingerprint comparison |
| `src/quantumvitas/api.py:446` | Fingerprint for storage | **After Molecule fork** |
| `src/quantumvitas/api.py:5866` | `create_structure()` | Structure creation |
| `src/quantumvitas/execution/executor.py:47` | Import at module level | For effective_structure_sha |
| `src/quantumvitas/execution/executor.py:751` | `_load_effective_structure_for_step()` | Compute effective_structure_sha |
| `tests/unit/test_structure_fingerprint.py:256` | Test assertion | Fingerprint verification |

### 3.3 Critical Path: promote_relax_structure()

The promote flow calls `import_structure()`:

```
promote_relax_structure()  (api.py:4747)
    └── import_structure()  (api.py:338-477)
        └── [Molecule hash fork]  (api.py:437-446) ❌ VIOLATION
```

When promoting a Molecule (from ORCA/PySCF relax), the fork path is taken, producing a fingerprint that:
- Is not translation-invariant
- Includes charge/spin in the hash
- Uses different tolerance semantics

---

## 4. Duplicate Fingerprint Function

### 4.1 Location

**File**: `src/quantumvitas/io/structure_io.py`  
**Function**: `structure_fingerprint()`  
**Lines**: 433-498

This is a **DUPLICATE** of the function in `core/structure_fingerprint.py`.

### 4.2 Differences

| Aspect | `core/structure_fingerprint.py` | `io/structure_io.py` |
|--------|--------------------------------|---------------------|
| Import path | `from quantumvitas.core.structure_fingerprint` | `from quantumvitas.io.structure_io` |
| Quantization | `round(x / tol)` → int64 | `round(x / tol) * tol` → float |
| Payload format | `"lattice:" + ints + "sites:" + ints` | Float strings with 10 decimal places |
| Used by | All production code | Appears unused |

### 4.3 Recommendation

The `structure_io.py` version should be **REMOVED** or made to call the canonical `core/structure_fingerprint.py` version.

---

## 5. Confirm No Other Forks

### 5.1 Search Results

**Query**: `hashlib.sha256.*json.dumps|json.dumps.*sha256`  
**Result**: No other occurrences found outside `api.py:437-446`

**Query**: `structure.as_dict().*sha256|sha256.*as_dict`  
**Result**: Only `api.py:437-446`

### 5.2 Confirmation

**The only Molecule hash fork is in `api.py:437-446`.**

No other locations bypass the canonical fingerprint entrypoint.

---

## 6. Canonicalization Functions Audit

### 6.1 PBC Canonicalization

| Function | Location | Purpose |
|----------|----------|---------|
| `canonicalize_structure_in_place()` | `structure_viz.py:208-253` | Entry point for visualization |
| `canonicalize_frac_coords()` | `structure_viz.py:256-280` | Core wrap logic |
| `canonicalize_structure_for_identity()` | **DELETED (2026-01-18)** | Was: For fingerprint (uses mod 1.0) |

**Observation**: Two different canonicalization approaches:
1. `structure_viz.py`: Wraps to `[-WRAP_TOL, 1-WRAP_TOL)`
2. `structure_fingerprint.py`: Wraps to `[0, 1)` via `mod 1.0`

This is intentional: visualization needs knife-edge handling, fingerprint needs simpler wrap.

### 6.2 Molecule Canonicalization

**NONE EXISTS**.

Molecules are not canonicalized anywhere in the codebase. The new spec requires:
- Translation normalization (COG centering)
- Applied in `_fingerprint_molecule()` before quantization

---

## 7. ORCA/PySCF Relax Handlers

### 7.1 ORCA Handler

**File**: `src/quantumvitas/execution/orca_relax_parser.py:118-222`

**Function**: `handle_orca_relax_output()`

**Behavior**:
1. Parse `.xyz` or `.out` file → `Molecule`
2. Call `write_generated_structure(molecule, ...)` → writes `current.json`

**Does NOT compute fingerprint**. Fingerprint is computed later when:
- `import_structure()` is called during promote
- `effective_structure_sha` is computed in executor

### 7.2 PySCF Handler

**File**: `src/quantumvitas/execution/pyscf_relax_handler.py:19-76`

**Function**: `handle_pyscf_relax_output()`

**Behavior**:
1. Read `optimized_atoms` from results dict
2. Create `Molecule(species, coords, charge, spin_multiplicity)`
3. Call `write_generated_structure(molecule, ...)` → writes `current.json`

**Does NOT compute fingerprint**. Same pattern as ORCA.

### 7.3 Canonicalization Issue

**Neither handler calls canonicalize** on the Molecule before writing.

This is acceptable IF fingerprinting applies canonicalization (COG centering) during computation. The spec requires translation normalization in `_fingerprint_molecule()`, which handles this.

---

## 8. Impact Analysis

### 8.1 What Breaks Without Fix

| Scenario | Current Behavior | Correct Behavior |
|----------|------------------|------------------|
| Import same Molecule twice at different origins | Different fingerprints | Same fingerprint |
| Promote ORCA relax output, compare to input | Fingerprint may differ due to origin shift | Should match if geometry unchanged |
| Dedup Molecule by fingerprint | May fail to dedup identical molecules | Should dedup correctly |

### 8.2 Affected Flows

1. **promote_relax_structure()**: Uses Molecule hash fork
2. **Incremental run skip logic**: `effective_structure_sha` for Molecule may be unstable
3. **Dedup on import**: `dedup_by_fingerprint=True` skips Molecules entirely

---

## 9. Files to Modify

| File | Changes Required |
|------|------------------|
| `src/quantumvitas/core/structure_fingerprint.py` | Add `structure_like_fingerprint()`, `_fingerprint_molecule()` |
| `src/quantumvitas/api.py:437-446` | Remove Molecule hash fork, call unified function |
| `src/quantumvitas/execution/executor.py:751` | Use `structure_like_fingerprint()` for Molecules |
| `src/quantumvitas/io/structure_io.py:433-498` | Remove duplicate or make wrapper |
| `tests/unit/test_structure_fingerprint.py` | Add Molecule tests |

---

## 10. Recommended Fix Order

1. **Add unified fingerprint function** to `structure_fingerprint.py`
2. **Add Molecule fingerprint with COG** to `structure_fingerprint.py`
3. **Update `api.py`** to remove fork and use unified function
4. **Update `executor.py`** to use unified function for both types
5. **Remove/wrap duplicate** in `structure_io.py`
6. **Add tests** for Molecule translation invariance
7. **Add regression test** to lock existing PBC fingerprint behavior

