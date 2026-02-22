# RELAX System Milestone Reference

**Date**: 2026-01-18  
**Status**: RATIFIED

---

## Purpose

This document establishes the authoritative reference points for RELAX system compliance and fingerprint/canonicalization contracts. All future changes to these areas must reference and maintain compliance with the documents listed below.

---

## Milestone Documents

### 1. RELAX System "Up to Spec" Sign-off

**Document**: [RELAX_UP_TO_SPEC_SIGNOFF.md](./RELAX_UP_TO_SPEC_SIGNOFF.md)  
**Date**: 2026-01-18  
**Reviewer**: Opus  
**Verdict**: ✅ **UP TO SPEC: YES**

This document provides the definitive compliance checklist for the RELAX system, verifying:
- Single public GEN step: `relax`
- Structure-only artifacts (no electronic-state dependency)
- Correct artifact paths and cleanup semantics
- Missing artifact hard error behavior
- Two-phase canonicalization/fingerprint architecture
- Deterministic quantization rules
- SSOT tolerance constant usage
- QC topology rules
- Integration test coverage

**All PRs touching RELAX must maintain compliance with the 10 pillars verified in this sign-off.**

---

### 2. Fingerprint Tolerance SSOT Review

**Document**: [PR_FINGERPRINT_TOL_SSOT_REVIEW.md](./PR_FINGERPRINT_TOL_SSOT_REVIEW.md)  
**Date**: 2026-01-18  
**Reviewer**: Opus  
**Verdict**: ✅ **PASS**

This document verifies:
- `DEFAULT_FINGERPRINT_TOL_ANG = 1e-3` as the single source of truth
- All fingerprint call paths use the SSOT constant
- No second default tolerance remains
- Idempotency tests correctly verify the contract
- No unintended changes to PBC canonicalization, quantization, or relax execution

**All PRs touching fingerprint tolerance must use `DEFAULT_FINGERPRINT_TOL_ANG` from `src/qmatsuite/core/structure_fingerprint.py`.**

---

## Contract Requirements

### Two-Phase Architecture (MANDATORY)

1. **Canonicalization Phase**:
   - Happens ONLY at import/read/parse time
   - Performs geometry transforms (COG shift for Molecule, wrap for Structure)
   - Entry point: `canonicalize_structure_like_in_place()`

2. **Fingerprint Phase**:
   - Pure quantize+hash function
   - NO geometry transforms (no mod, no wrap, no COG shift)
   - Entry point: `structure_like_fingerprint()`
   - Uses deterministic quantization: `floor(x/tol + 0.5 + eps)`

**Violation of this contract is a breaking change and must be explicitly justified.**

---

## Usage

When creating a PR that touches RELAX or fingerprint code:

1. Check the PR template checklist
2. Reference both milestone documents
3. Verify your changes maintain the two-phase contract
4. Update tests to verify compliance

---

**This milestone represents the completion of the RELAX implementation and fingerprint unification work. Future changes must preserve these contracts.**

