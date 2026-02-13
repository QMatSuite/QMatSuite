# Independent Audit Report: Precision Apply Breaking bands_pw K_POINTS

**Date**: 2025-01-XX  
**Auditor**: Independent Code Review  
**Scope**: Why applying precision preset overwrites/clears bands_pw K_POINTS (kpath)

---

## Executive Summary

**Root Cause**: The deletion logic in `apply_presets_to_step()` unconditionally removes `cards.K_POINTS` when precision is applied, because `DIMENSION_OWNED_KEYS` declares precision owns `K_POINTS`. For `bands_pw` steps, the receiver spec correctly rejects kmesh (`accepts_kmesh=False`), so no replacement is provided. The result: `K_POINTS` is deleted but never restored → **CLEARED**.

**Two Observed Phenomena**:
1. **CLEAR**: When `compiled_kpoints_card = None` (bands_pw case) → K_POINTS deleted, not restored
2. **OVERWRITE**: If `compiled_kpoints_card` was set (hypothetical bug) → K_POINTS replaced with automatic mesh

---

## Phase 1: Data Model & Ownership Rules (with Citations)

### 1.1 Precision Owned Keys Definition

**Location**: `src/quantumvitas/presets/integration.py:293-305`

```python
DIMENSION_OWNED_KEYS: dict[str, dict[str, set[str]]] = {
    DIMENSION_MAGNETISM: {
        "SYSTEM": {"nspin", "noncolin", "lspinorb"},
    },
    DIMENSION_OCCUPATIONS_SCHEME: {
        "SYSTEM": {"occupations", "smearing", "degauss"},
    },
    DIMENSION_PRECISION: {
        "SYSTEM": {"ecutwfc", "ecutrho"},
        "ELECTRONS": {"conv_thr"},
        "cards": {"K_POINTS"},  # Special: handled separately
    },
}
```

**Evidence**: 
- **File**: `src/quantumvitas/presets/integration.py:303`
- **Line**: 303
- **Data Shape**: `{"cards": {"K_POINTS"}}` - precision owns `cards.K_POINTS`

**Conclusion**: ✅ **Precision owns `cards.K_POINTS`** according to `DIMENSION_OWNED_KEYS`.

---

### 1.2 Other Dimensions' Ownership of K_POINTS

**Search Results**:
- `DIMENSION_MAGNETISM`: Does NOT own K_POINTS (only SYSTEM keys)
- `DIMENSION_OCCUPATIONS_SCHEME`: Does NOT own K_POINTS (only SYSTEM keys)

**Evidence**: `src/quantumvitas/presets/integration.py:293-305` - Only precision has `"cards": {"K_POINTS"}`

**Conclusion**: ✅ **Only precision dimension owns K_POINTS**. No other dimension touches it.

---

### 1.3 bands_pw Receiver Specification

**Location**: `src/quantumvitas/presets/receivers.py:158-163`

```python
# pw.x: bands_pw - accept cutoffs/conv_thr, but NOT kmesh (uses k-path)
"bands_pw": PrecisionReceiverSpec(
    accepts_kmesh=False,
    accepts_cutoffs=True,
    accepts_conv_thr=True,
    kmesh_strategy="none",
),
```

**Evidence**:
- **File**: `src/quantumvitas/presets/receivers.py:158-163`
- **Lines**: 158-163
- **Data Shape**: `PrecisionReceiverSpec(accepts_kmesh=False, kmesh_strategy="none")`

**Conclusion**: ✅ **bands_pw receiver explicitly rejects kmesh** (`accepts_kmesh=False`), indicating it uses k-path, not automatic mesh.

---

### 1.4 Receiver Filter Logic in Apply Path

**Location**: `src/quantumvitas/presets/integration.py:438-442`

```python
# Apply kmesh if accepted (receiver decides strategy)
if precision_spec.accepts_kmesh and precision_spec.kmesh_strategy != "none":
    compiled_kpoints_card = precision_compiled.get("K_POINTS_CARD")
    if compiled_kpoints_card:
        compiled_patches["cards"]["K_POINTS"] = compiled_kpoints_card
```

**Evidence**:
- **File**: `src/quantumvitas/presets/integration.py:438-442`
- **Lines**: 438-442
- **Logic**: Only sets `compiled_kpoints_card` if `accepts_kmesh=True AND kmesh_strategy != "none"`

**For bands_pw**: 
- `accepts_kmesh=False` → condition fails
- `compiled_kpoints_card` remains `None`
- `compiled_patches["cards"]["K_POINTS"]` is **NOT set**

**Conclusion**: ✅ **Receiver correctly filters out kmesh for bands_pw**, so no replacement K_POINTS is prepared.

---

### 1.5 K_POINTS Expected Shape in step_yaml

**Location**: Multiple references

**Canonical Format** (from `src/quantumvitas/presets/spaces_registry.py:293-296`):
```python
"K_POINTS_CARD": {
    "option": "automatic",  # or "crystal_b", "tpiba_b", etc.
    "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],  # for automatic
    # OR
    "data": [[kx1, ky1, kz1, weight1], ...],  # for explicit paths
}
```

**Evidence**:
- **Automatic mesh**: `{"option": "automatic", "data": [[6, 6, 6, 0, 0, 0]]}`
- **K-path (bands_pw)**: `{"option": "crystal_b", "data": [[0.0, 0.0, 0.0, 1.0], [0.5, 0.5, 0.5, 1.0]]}`

**Conclusion**: ✅ **K_POINTS is a dict with `option` and `data` keys**, stored in `cards.K_POINTS`.

---

## Phase 2: Integration Merge Semantics

### 2.1 Deletion Logic

**Location**: `src/quantumvitas/presets/integration.py:444-458`

```python
# Remove only keys owned by applied dimensions
keys_to_remove: dict[str, set[str]] = {"SYSTEM": set(), "ELECTRONS": set(), "cards": set()}
for dimension in applied_dimensions:
    if dimension in DIMENSION_OWNED_KEYS:
        for section, keys in DIMENSION_OWNED_KEYS[dimension].items():
            if section != "cards" or dimension == DIMENSION_PRECISION:
                keys_to_remove[section].update(keys)

# Remove owned keys from existing params
for key in keys_to_remove["SYSTEM"]:
    existing_system.pop(key, None)
for key in keys_to_remove["ELECTRONS"]:
    existing_electrons.pop(key, None)
if "K_POINTS" in keys_to_remove["cards"]:
    existing_cards.pop("K_POINTS", None)
```

**Evidence**:
- **File**: `src/quantumvitas/presets/integration.py:444-458`
- **Lines**: 444-458
- **Critical Line**: 449 - `if section != "cards" or dimension == DIMENSION_PRECISION:`

**Logic Analysis**:
- Condition: `section != "cards" OR dimension == DIMENSION_PRECISION`
- For precision + cards: `False OR True = True` → **K_POINTS added to removal list**
- Line 457: `existing_cards.pop("K_POINTS", None)` → **K_POINTS DELETED**

**Conclusion**: ✅ **Deletion logic unconditionally removes K_POINTS when precision is applied**, regardless of receiver acceptance.

---

### 2.2 Merge/Restore Logic

**Location**: `src/quantumvitas/presets/integration.py:460-464`

```python
# Add compiled params (only owned keys)
existing_system.update(compiled_patches["SYSTEM"])
existing_electrons.update(compiled_patches["ELECTRONS"])
if compiled_kpoints_card is not None:
    existing_cards["K_POINTS"] = compiled_kpoints_card
```

**Evidence**:
- **File**: `src/quantumvitas/presets/integration.py:460-464`
- **Lines**: 460-464
- **Critical Line**: 463 - `if compiled_kpoints_card is not None:`

**Logic Analysis**:
- For bands_pw: `compiled_kpoints_card = None` (from line 439 condition failure)
- Condition: `if None is not None` → **False**
- Result: **K_POINTS is NOT restored**

**Conclusion**: ✅ **Merge logic only restores K_POINTS if `compiled_kpoints_card is not None`**. For bands_pw, this is `None`, so K_POINTS remains deleted.

---

### 2.3 Merge Algorithm Summary

**One-Sentence Description**: 
> "Remove all owned keys from existing params, then add compiled patches (shallow dict update). For cards.K_POINTS, delete if owned by applied dimension, restore only if compiled replacement exists."

**Code Proof**:
- **Deletion**: `src/quantumvitas/presets/integration.py:444-458`
- **Restore**: `src/quantumvitas/presets/integration.py:460-464`
- **Merge Type**: **Shallow dict update** (not deep merge) - `existing_cards["K_POINTS"] = compiled_kpoints_card` replaces entire dict

**Conclusion**: ✅ **Merge is replacement-based, not field-level merge**. Entire `K_POINTS` dict is replaced or deleted.

---

## Phase 3: Root Cause Chain

### 3.1 Causal Chain

```
1. DIMENSION_OWNED_KEYS declares precision owns cards.K_POINTS
   ↓
2. When precision is applied, deletion logic (line 449) adds K_POINTS to keys_to_remove["cards"]
   ↓
3. Line 457 removes K_POINTS from existing_cards (unconditionally)
   ↓
4. For bands_pw, receiver spec has accepts_kmesh=False
   ↓
5. Line 439 condition fails: accepts_kmesh && kmesh_strategy != "none" → False
   ↓
6. compiled_kpoints_card remains None
   ↓
7. Line 463 condition fails: if compiled_kpoints_card is not None → False
   ↓
8. K_POINTS is NOT restored
   ↓
9. RESULT: K_POINTS is CLEARED (deleted but never restored)
```

**Evidence Chain**:
- **Step 1**: `integration.py:303` - `DIMENSION_OWNED_KEYS[DIMENSION_PRECISION]["cards"] = {"K_POINTS"}`
- **Step 2**: `integration.py:449` - `if section != "cards" or dimension == DIMENSION_PRECISION:` → True
- **Step 3**: `integration.py:457` - `existing_cards.pop("K_POINTS", None)`
- **Step 4**: `receivers.py:159` - `accepts_kmesh=False`
- **Step 5**: `integration.py:439` - Condition evaluates to False
- **Step 6**: `integration.py:440` - `compiled_kpoints_card` remains `None`
- **Step 7**: `integration.py:463` - Condition evaluates to False
- **Step 8**: Line 464 not executed
- **Step 9**: `existing_cards` no longer contains `K_POINTS`

---

### 3.2 Two Observed Phenomena Explained

#### Phenomenon A: CLEAR (Current Bug)

**Scenario**: `bands_pw` step with kpath K_POINTS, apply precision

**Flow**:
1. `compiled_kpoints_card = None` (receiver rejects kmesh)
2. Deletion removes `K_POINTS` from `existing_cards`
3. Restore condition fails → `K_POINTS` not restored
4. **Result**: `cards.K_POINTS` is **MISSING** (cleared)

**Evidence**: 
- `integration.py:457` - Deletion happens
- `integration.py:463` - Restore condition fails
- Final state: `existing_cards` has no `K_POINTS` key

---

#### Phenomenon B: OVERWRITE (Hypothetical, if receiver bug)

**Scenario**: If `accepts_kmesh=True` for bands_pw (hypothetical bug)

**Flow**:
1. `compiled_kpoints_card = {"option": "automatic", "data": [[6,6,6,0,0,0]]}`
2. Deletion removes original kpath `K_POINTS`
3. Restore condition succeeds → `K_POINTS` replaced with automatic mesh
4. **Result**: `cards.K_POINTS` is **OVERWRITTEN** with mesh (kpath lost)

**Evidence**:
- `integration.py:464` - `existing_cards["K_POINTS"] = compiled_kpoints_card` replaces entire dict
- Original kpath data is lost

---

### 3.3 Semantic Mismatch

**Problem**: 
- **Precision's K_POINTS semantic**: Automatic k-mesh (for SCF/NSCF)
- **bands_pw's K_POINTS semantic**: K-path (for band structure)
- **Architecture assumption**: Precision "owns" K_POINTS, but this conflates two different use cases

**Conclusion**: ✅ **Root cause is architectural**: `DIMENSION_OWNED_KEYS` treats all `K_POINTS` as precision-owned, but bands_pw uses K_POINTS for a different purpose (kpath, not kmesh).

---

## Phase 4: Fix Options (Not Implemented)

### Option 1: Remove K_POINTS from Precision Owned Keys

**Change**: Remove `"cards": {"K_POINTS"}` from `DIMENSION_OWNED_KEYS[DIMENSION_PRECISION]`

**Files**:
- `src/quantumvitas/presets/integration.py:300-304`

**Logic**:
- Precision only owns `ecutwfc`, `ecutrho`, `conv_thr`
- K_POINTS handled separately (maybe new dimension: `kmesh`?)

**Pros**:
- ✅ Clean separation: precision = cutoffs/threshold, kmesh = separate concern
- ✅ No impact on existing precision detection (kmesh is wildcard anyway)
- ✅ Minimal code change

**Cons**:
- ⚠️ Breaking change: precision no longer "owns" kmesh semantically
- ⚠️ Need new dimension or mechanism for kmesh presets
- ⚠️ May affect detection logic (if precision detection relies on K_POINTS ownership)

**Impact**:
- **Steps affected**: All steps that currently get kmesh from precision
- **Detection**: May need to update precision detection to not require K_POINTS

**Priority**: ⭐⭐⭐ (High - cleanest solution, but requires architectural decision)

---

### Option 2: Step-Type-Aware Ownership

**Change**: Make ownership conditional on step_type

**Files**:
- `src/quantumvitas/presets/integration.py:293-305` - Make `DIMENSION_OWNED_KEYS` step-type-aware
- `src/quantumvitas/presets/integration.py:444-450` - Check step_type before adding to removal list

**Logic**:
- For `scf/nscf/relax/md/vc-*`: precision owns `K_POINTS` (kmesh)
- For `bands_pw`: precision does NOT own `K_POINTS` (kpath)

**Implementation**:
```python
# Pseudo-code
if dimension == DIMENSION_PRECISION and section == "cards":
    if step_type == "bands_pw":
        # Don't add K_POINTS to removal list
        continue
keys_to_remove[section].update(keys)
```

**Pros**:
- ✅ Preserves existing behavior for SCF/NSCF steps
- ✅ Fixes bands_pw without breaking other steps
- ✅ Semantic: precision owns kmesh, not kpath

**Cons**:
- ⚠️ Adds step_type dependency to ownership logic (coupling)
- ⚠️ More complex: ownership becomes conditional
- ⚠️ May need similar logic for other step types in future

**Impact**:
- **Steps affected**: Only bands_pw (preserves others)
- **Detection**: No change needed

**Priority**: ⭐⭐⭐⭐ (Very High - targeted fix, minimal side effects)

---

### Option 3: Conditional Deletion Based on Receiver Acceptance

**Change**: Only delete K_POINTS if receiver accepts kmesh

**Files**:
- `src/quantumvitas/presets/integration.py:444-458` - Check receiver spec before deletion

**Logic**:
```python
# Pseudo-code
if "K_POINTS" in keys_to_remove["cards"]:
    # Only delete if precision receiver accepts kmesh
    if dimension == DIMENSION_PRECISION:
        precision_spec = get_precision_receiver_spec(step_type)
        if precision_spec and precision_spec.accepts_kmesh:
            existing_cards.pop("K_POINTS", None)
    else:
        existing_cards.pop("K_POINTS", None)
```

**Pros**:
- ✅ Minimal change: only affects deletion logic
- ✅ Preserves existing behavior
- ✅ Uses receiver spec (already exists)

**Cons**:
- ⚠️ Couples deletion logic to receiver spec (two layers interacting)
- ⚠️ Special case for precision (other dimensions don't need this)
- ⚠️ May be confusing: ownership vs. acceptance

**Impact**:
- **Steps affected**: Only bands_pw (preserves others)
- **Detection**: No change needed

**Priority**: ⭐⭐⭐⭐ (Very High - minimal change, uses existing receiver logic)

---

### Recommendation

**Recommended**: **Option 2 (Step-Type-Aware Ownership)** or **Option 3 (Conditional Deletion)**

**Rationale**:
- Both preserve existing behavior for SCF/NSCF steps
- Both fix bands_pw without breaking other functionality
- Option 2 is more architecturally clean (ownership is step-aware)
- Option 3 is simpler to implement (only deletion logic changes)

**Not Recommended**: Option 1 (Remove from owned keys)
- Requires new dimension/mechanism for kmesh
- Breaking change for existing precision detection
- More architectural work needed

---

## Deliverable Summary

### Key Code Locations

1. **Ownership Definition**: `src/quantumvitas/presets/integration.py:303`
2. **Receiver Spec**: `src/quantumvitas/presets/receivers.py:158-163`
3. **Deletion Logic**: `src/quantumvitas/presets/integration.py:444-458`
4. **Restore Logic**: `src/quantumvitas/presets/integration.py:460-464`
5. **Receiver Filter**: `src/quantumvitas/presets/integration.py:438-442`

### Minimal Reproduction

**Script**: `audit_precision_bands_kpoints.py` (run to see before/after)

**Before**:
```yaml
cards:
  K_POINTS:
    option: crystal_b
    data:
      - [0.0, 0.0, 0.0, 1.0]
      - [0.5, 0.5, 0.5, 1.0]
```

**After (CLEAR scenario)**:
```yaml
cards: {}  # K_POINTS missing
```

**After (OVERWRITE scenario, if receiver bug)**:
```yaml
cards:
  K_POINTS:
    option: automatic
    data: [[6, 6, 6, 0, 0, 0]]  # kpath lost
```

### Root Cause Chain

**One Sentence**: 
> "Precision owns K_POINTS in DIMENSION_OWNED_KEYS, so deletion logic removes it unconditionally, but bands_pw receiver rejects kmesh so no replacement is provided, resulting in K_POINTS being cleared."

**Full Chain**: See Section 3.1

### Fix Options

1. **Option 1**: Remove K_POINTS from precision owned keys (requires new kmesh dimension)
2. **Option 2**: Step-type-aware ownership (precision owns kmesh for SCF, not for bands_pw)
3. **Option 3**: Conditional deletion based on receiver acceptance (only delete if accepts_kmesh=True)

**Recommendation**: Option 2 or Option 3 (both preserve existing behavior, fix bands_pw)

---

## End of Audit Report

