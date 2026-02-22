# PR Review: Fingerprint Tolerance SSOT + Idempotency Tests

**Date**: 2026-01-18  
**Reviewer**: Opus  
**Status**: ✅ **PASS**

---

## Executive Summary

The PR introducing `DEFAULT_FINGERPRINT_TOL_ANG` SSOT constant and idempotency tests is **APPROVED**. All required changes are correctly implemented, no second default tolerance remains in fingerprint paths, and idempotency tests correctly verify the contract.

---

## 1. SSOT Constant Definition

### ✅ PASS — Single Canonical Location

**Evidence**:
- **File**: `src/qmatsuite/core/structure_fingerprint.py:147`
- **Definition**: `DEFAULT_FINGERPRINT_TOL_ANG = 1e-3  # Default tolerance in Angstrom`
- **Default in function signature**: `src/qmatsuite/core/structure_fingerprint.py:152`
  ```python
  def structure_like_fingerprint(
      obj: Union[PMGStructure, PMGMolecule],
      tol_ang: float = DEFAULT_FINGERPRINT_TOL_ANG,
  ) -> str:
  ```

No other `1e-3` constants exist in the fingerprint definition path.

---

## 2. Call Site Updates

### ✅ PASS — All fingerprint call paths use the constant

| Call Site | File:Line | Imports Constant | Uses Constant |
|-----------|-----------|------------------|---------------|
| `api.import_structure` (dedup path) | `api.py:399-404` | ✅ | ✅ |
| `api.import_structure` (storage path) | `api.py:441-449` | ✅ | ✅ |
| `executor.effective_structure_sha` | `executor.py:47,751` | ✅ | ✅ |
| `promote_relax_structure` | `api.py:4750` | N/A (delegates to `import_structure`) | ✅ |

**Evidence**:
```
src/qmatsuite/api.py:399:  from qmatsuite.core.structure_fingerprint import structure_like_fingerprint, DEFAULT_FINGERPRINT_TOL_ANG
src/qmatsuite/api.py:404:  fingerprint = structure_like_fingerprint(structure, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
src/qmatsuite/api.py:441:  from qmatsuite.core.structure_fingerprint import structure_like_fingerprint, DEFAULT_FINGERPRINT_TOL_ANG
src/qmatsuite/api.py:449:  fingerprint = structure_like_fingerprint(structure, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
src/qmatsuite/execution/executor.py:47:   from qmatsuite.core.structure_fingerprint import structure_like_fingerprint, DEFAULT_FINGERPRINT_TOL_ANG
src/qmatsuite/execution/executor.py:751:  effective_structure_sha = structure_like_fingerprint(structure, tol_ang=DEFAULT_FINGERPRINT_TOL_ANG)
```

### ✅ PASS — `relax_artifacts` does NOT compute fingerprint

**Evidence**: Grep of `src/qmatsuite/execution/relax_artifacts.py` for `fingerprint` returns no matches.

Fingerprint is computed only:
1. At import time (`api.import_structure`)
2. At manifest build time (`executor.py`)

---

## 3. No Second Default Tolerance Remains

### ✅ PASS — `1e-3` in src/ only appears in definition

**Evidence** (grep for `1e-3` in `src/`):
```
src/qmatsuite/core/structure_fingerprint.py:147:DEFAULT_FINGERPRINT_TOL_ANG = 1e-3  # Definition
src/qmatsuite/core/structure_fingerprint.py:173:... (default 1e-3)  # Docstring only
```

All other occurrences of `1e-3` are in documentation or the SSOT definition itself.

---

## 4. Idempotency Tests

### ✅ PASS — Tests correctly verify contract

**New Test Class**: `TestFingerprintSSOTAndIdempotency` at `tests/unit/test_structure_fingerprint.py:872`

| Test | Purpose | Verified |
|------|---------|----------|
| `test_fingerprint_uses_default_constant_when_not_specified` | Verifies default value equals constant | ✅ |
| `test_molecule_canonicalization_idempotency_with_fingerprint` | Verifies coords + fingerprint stable after 2nd canonicalization | ✅ |

**Enhanced Existing Test**: `test_molecule_canonicalization_idempotent` at `tests/unit/test_structure_fingerprint.py:622`
- Now includes fingerprint verification
- Asserts `fp_after_first == fp_after_second`

**Test semantics match contract**:
- Canonicalization is idempotent (coords unchanged after second call, tolerance 1e-12)
- Fingerprint remains identical (no drift)

---

## 5. No Unintended Changes

### ✅ PASS — Constrained scope verified

| Area | Changed? | Evidence |
|------|----------|----------|
| PBC canonicalization | ❌ NO | `structure_canonicalize.py` unchanged; still calls `canonicalize_structure_in_place` from `structure_viz.py` |
| Quantization rule | ❌ NO | `quantize_scalar/quantize_array` still uses `floor(x/tol + 0.5 + eps)` at lines 109-139 |
| Relax execution logic | ❌ NO | No changes to `recipes.py`, `executor.py` (except tol constant import) |
| SSOT/resource semantics | ❌ NO | No changes to resource model, ULID semantics, or SSOT rules |

---

## 6. Remaining Risks / Follow-ups

1. **RESOLVED**: `canonicalize_structure_for_identity()` and `structures_semantically_equal()` have been 
   deleted from the codebase. Dedup uses fingerprint identity only.

2. **Low**: Tests still use explicit `tol_ang=1e-3` in many places (44 occurrences in test file). These are test-specific and do not affect production code. **Cosmetic improvement only**.

3. **Info**: Documentation in `docs/specs/STRUCTURE_FINGERPRINT_SPEC.md` still references `tol_ang = 1e-3` directly instead of the constant. **Documentation-only; no functional impact**.

---

## Conclusion

**VERDICT**: ✅ **APPROVED**

All requirements met:
- SSOT constant defined in canonical location
- All production fingerprint call paths use the constant
- No second default tolerance in fingerprint code
- Idempotency tests correctly verify contract
- No unintended changes to PBC canonicalization, quantization, relax execution, or SSOT semantics

