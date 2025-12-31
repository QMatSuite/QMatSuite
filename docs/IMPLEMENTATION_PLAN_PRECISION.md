# Implementation Plan: Precision Preset (v1)

## Overview

Add a "Precision" preset dimension (low/med/high) covering:
- K_POINTS automatic (nk1 nk2 nk3 + shifts)
- ecutwfc, ecutrho (plane-wave cutoffs)
- conv_thr (SCF convergence threshold)

## Governing Documents

- Constitution Chapter 10: step.yml is sole executable truth
- WORKFLOW_PRESET_DESIGN_V0.md: preset is runtime-only interpretation

## Research Summary

### K-Point Spacing

Standard practice uses k-point density defined as `nk_i = ceil(k_density / a_i)` where:
- `k_density` is in units of "k-points × Å" (or equivalently, points per Å of lattice)
- `a_i` is the lattice constant in direction i (in Å)

Common values from literature (VASP, Materials Project, QE tutorials):
- **Low precision**: Δk ≈ 0.15 Å⁻¹ → k_density ≈ 40-45
- **Med precision**: Δk ≈ 0.08-0.10 Å⁻¹ → k_density ≈ 60-70
- **High precision**: Δk ≈ 0.04-0.06 Å⁻¹ → k_density ≈ 100-120

**Slab/vacuum detection**: If one lattice axis is >15 Å AND significantly larger (>2x) than the minimum axis, treat as vacuum direction and set nk=1.

**Sanity check for Si (a ≈ 5.43 Å)**:
- Low (k_density=42): nk = ceil(42/5.43) = 8 → 8×8×8 ✓
- Med (k_density=63): nk = ceil(63/5.43) = 12 → 12×12×12 ✓
- High (k_density=100): nk = ceil(100/5.43) = 19 → 19×19×19 ✓

These align with common practice (6-8 for screening, 10-12 for production, 16-20 for high accuracy).

### Convergence Threshold

QE default is 1e-6. Common practices:
- **Low**: 1e-6 (quick screening, forces acceptable for coarse relaxation)
- **Med**: 1e-8 (production, good for most properties)
- **High**: 1e-10 (high-accuracy forces, phonons, fine energy differences)

### Cutoffs

Using SSSP/PseudoDojo recommended values from PSEUDO_FILE_INDEX.json:
- Base values: max(cutoff_wfc_normal) and max(cutoff_rho_normal) over all species
- For NC pseudos: if ecutrho not specified, use 4*ecutwfc
- For USPP/PAW: use recommended ecutrho (typically 8-12x ecutwfc)

Precision multipliers:
- **Low**: 0.85× (acceptable for quick tests)
- **Med**: 1.0× (recommended values)
- **High**: 1.15× (extra convergence margin)

Rounding: Round ecutwfc to nearest 5 Ry, ecutrho to nearest 10 Ry for cleaner inputs.

## Final Parameter Defaults

| Level | k_density | conv_thr | cutoff_mult |
|-------|-----------|----------|-------------|
| Low   | 42        | 1e-6     | 0.85        |
| Med   | 63        | 1e-8     | 1.0         |
| High  | 100       | 1e-10    | 1.15        |

---

## Implementation Milestones

### Milestone 1: Core PrecisionOption Dimension + Detector
**Status**: [x] COMPLETED

**Goal**: Add PrecisionOption enum, extend detector to recognize precision from step params.

**Files modified**:
- `src/quantumvitas/presets/dimensions.py` - Added PrecisionOption enum

**Files created**:
- `src/quantumvitas/presets/precision.py` - PrecisionAdvisor and related logic

**Tasks**:
- [x] Add `PrecisionOption` enum (LOW, MED, HIGH) to dimensions.py
- [x] Add `DIMENSION_PRECISION = "precision"` constant
- [x] Added `V1_DIMENSIONS` (V0 kept for backward compat)
- [x] Created `precision.py` with `PrecisionAdvisor` class

**Verification**:
```bash
python -c "from quantumvitas.presets.dimensions import PrecisionOption; print(PrecisionOption.LOW.value)"
# Output: low
```

---

### Milestone 2: PrecisionAdvisor - Cutoff Calculation
**Status**: [x] COMPLETED

**Goal**: Implement cutoff calculation from PSEUDO_FILE_INDEX.json.

**Files modified**:
- `src/quantumvitas/presets/precision.py`

**Tasks**:
- [x] Implemented `_load_index()` helper in PrecisionAdvisor (uses `load_pseudo_libinfo_bundle`)
- [x] Implemented `get_cutoffs_from_index(sha256) -> (ecutwfc, ecutrho)` lookup
- [x] Implemented `aggregate_cutoffs(species_map) -> (ecutwfc, ecutrho)` aggregation
- [x] Handle "na" values gracefully (fallback to defaults: 50/400 Ry)
- [x] Apply precision multipliers and rounding (round_cutoff)
- [x] Added unit tests for cutoff lookup and aggregation

**Verification**: All cutoff tests pass (8 tests)

---

### Milestone 3: PrecisionAdvisor - K-Mesh Calculation
**Status**: [x] COMPLETED

**Goal**: Implement k-point mesh calculation from lattice vectors.

**Files modified**:
- `src/quantumvitas/presets/precision.py`

**Tasks**:
- [x] Implemented `compute_kmesh(lattice_matrix, k_density) -> (nk1, nk2, nk3, sk1, sk2, sk3)`
- [x] Implemented vacuum/slab detection (axis >15 Å and >2x min axis → nk=1)
- [x] Shift logic: 0 0 0 for Gamma-centered mesh
- [x] Added unit tests for kmesh including slab case (8 tests)
- [x] Sanity check: Si at 5.43 Å returns 8×8×8 (low), 12×12×12 (med), 19×19×19 (high)

**Verification**: All kmesh tests pass

---

### Milestone 4: Precision Compiler + Detector
**Status**: [x] COMPLETED

**Goal**: Implement forward compilation and reverse detection for precision.

**Files modified**:
- `src/quantumvitas/presets/compiler.py` - Added `compile_precision()`
- `src/quantumvitas/presets/detector.py` - Added `detect_precision()`

**Tasks**:
- [x] Added `compile_precision(option, ecutwfc, ecutrho, conv_thr, nk1, nk2, nk3)` → returns SYSTEM + ELECTRONS + K_POINTS
- [x] Added `detect_precision(params)` → infers precision from conv_thr
- [x] Detection strategy: conv_thr >= 5e-7 → LOW, >= 5e-9 → MED, < 5e-9 → HIGH
- [x] Updated `detect_all_presets()` to include precision dimension
- [x] Added equivalence tests: detect(compile(x)) == x for all precision levels

**Verification**: All compiler/detector tests pass

---

### Milestone 5: Integration + Step Receivers
**Status**: [x] COMPLETED

**Goal**: Wire precision into BROADCAST apply and step receivers.

**Files modified**:
- `src/quantumvitas/presets/receivers.py` - Added `DIMENSION_PRECISION` to V1_DIMENSIONS
- `src/quantumvitas/presets/integration.py` - Updated apply_presets_to_step for precision

**Tasks**:
- [x] Added `DIMENSION_PRECISION` to V1_DIMENSIONS in receivers.py
- [x] Updated PW_STEP_TYPES to accept V1_DIMENSIONS (including precision)
- [x] Updated `apply_presets_to_step()` to handle precision params (K_POINTS + SYSTEM + ELECTRONS)
- [x] Updated `get_step_preset_params()` to include precision-related params
- [x] Updated `get_step_preset_footprints()` to include precision params

**Verification**: All integration tests pass (782 total)

---

### Milestone 6: Daemon Handler
**Status**: [ ] Not Started

**Goal**: Update daemon RPC handlers for precision preset.

**Files to modify**:
- `src/quantumvitas/daemon/server.py` - Update preset handlers

**Tasks**:
- [ ] Update `_handle_detect_presets()` to include precision
- [ ] Update `_handle_apply_presets_to_calculation()` to accept precision
- [ ] Add `_handle_get_precision_advice()` for UI to get recommended values
- [ ] Return computed values (ecutwfc, ecutrho, kmesh) for UI display

**Verification**:
```bash
python -m pytest tests/integration/test_daemon_presets.py -v -k "precision"
```

---

### Milestone 7: TypeScript Types + UI Hook
**Status**: [ ] Not Started

**Goal**: Update frontend types and hooks for precision.

**Files to modify**:
- `gui/src/types/qv.ts` - Add precision types
- `gui/src/hooks/usePresets.ts` - Update hook to handle precision

**Tasks**:
- [ ] Add `PrecisionValue = 'low' | 'med' | 'high'`
- [ ] Update `PresetDimension` type to include 'precision'
- [ ] Update `DetectedPresets` to include precision
- [ ] Add `PrecisionAdviceResult` type for UI hints
- [ ] Update `usePresets` to handle precision dimension

**Verification**:
```bash
cd gui && npm run typecheck
```

---

### Milestone 8: UI Components
**Status**: [ ] Not Started

**Goal**: Add precision to PresetSection UI with dropdown and footprint chips.

**Files to modify**:
- `gui/src/components/presets/PresetSection.tsx` - Add precision row
- `gui/src/components/panels/CalculationListPanel.tsx` - Add precision footprint chips

**Tasks**:
- [ ] Add precision row to PresetSection with dropdown
- [ ] Show computed values (ecutwfc, ecutrho, kmesh) as hints
- [ ] Add precision-related params to footprint chips (ecutwfc, conv_thr)
- [ ] Update chip layout to include new params compactly

**Verification**:
- Manual: Open GUI, navigate to calculation, verify precision dropdown appears
- Manual: Apply precision preset, verify step.yml updates

---

### Milestone 9: Unit Tests for Precision
**Status**: [x] COMPLETED

**Goal**: Comprehensive unit tests for precision preset.

**Files created**:
- `tests/unit/test_precision_advisor.py` - 29 unit tests

**Tests cover**:
- [x] K-mesh computation for various lattice types (8 tests)
- [x] Cutoff resolution from index (6 tests)
- [x] Cutoff rounding (2 tests)
- [x] PrecisionAdvisor end-to-end (2 tests)
- [x] Precision configs ordering and values (2 tests)
- [x] Precision detection from conv_thr (6 tests)
- [x] Compiler/detector equivalence for LOW/MED/HIGH (3 tests)

**Verification**: All 29 precision tests pass

---

### Milestone 10: Full Test Suite + Documentation
**Status**: [x] COMPLETED

**Goal**: Ensure all tests pass and update documentation.

**Results**:
- [x] Full test suite: 782 tests pass
- [x] Updated existing tests to accommodate new precision dimension
- [x] Implementation plan updated with progress

**Verification**:
```bash
source .venv/bin/activate
python -m pytest tests/ -q
# Output: 782 passed
```

---

### Milestone 6: Daemon Handler (PENDING)
**Status**: [ ] Not Started

**Goal**: Update daemon RPC handlers for precision preset.

---

### Milestone 7: TypeScript Types + UI (PENDING)
**Status**: [ ] Not Started

**Goal**: Update frontend types and hooks for precision.

---

### Milestone 8: UI Components (PENDING)
**Status**: [ ] Not Started

**Goal**: Add precision to PresetSection UI with dropdown.

---

## Handoff Notes

**Current state**: Backend complete, UI pending.

**Completed work**:
1. `PrecisionOption` enum (LOW, MED, HIGH) in dimensions.py
2. `PrecisionAdvisor` class with cutoff/kmesh computation in precision.py
3. `compile_precision()` in compiler.py
4. `detect_precision()` in detector.py
5. V1_DIMENSIONS includes precision in receivers.py
6. `apply_presets_to_step()` handles precision params in integration.py
7. 29 unit tests for precision module

**Key design decisions**:
1. Precision detection based on conv_thr ranges (simpler than cutoff analysis)
2. K-mesh uses k_density formula with slab detection
3. Cutoffs come from PSEUDO_FILE_INDEX.json via sha256 lookup
4. Precision is a receiver dimension like spin/soc/material

**Dependencies**:
- PSEUDO_FILE_INDEX.json must be installed via `tools/build_pseudo_libinfo_bundle.py`
- Structure must be resolved for kmesh calculation

**Edge cases handled**:
- Missing cutoff data in index → use sensible defaults (50/400 Ry)
- Molecule (large cell) → small mesh (Gamma-like)
- Slab (one large vacuum axis) → nk=1 for that direction

---

## Phase: Revision (2025-12-31)

Revising the precision backend to align with updated product/physics decisions.

### Revised Parameter Defaults

| Level | Δk (Å⁻¹) | conv_thr | cutoff_mult |
|-------|----------|----------|-------------|
| Low   | 0.30     | 1e-6     | 0.8         |
| Med   | 0.20     | 1e-8     | 1.0         |
| High  | 0.15     | 1e-10    | 1.2         |

### Key Changes

1. **K-mesh**: Use reciprocal-space correct formulation: `nk_i = max(1, ceil(|b_i| / Δk))`
   - Remove slab/vacuum heuristics
   - Si (a≈5.43 Å) expected: ~5×5×5 (low), ~6×6×6 (med), ~8×8×8 (high)

2. **Cutoffs**: Symmetric multipliers (0.8/1.0/1.2), integer Ry rounding only

3. **Detection**: Strict 3-way match (conv_thr + kmesh + cutoffs) for level detection

4. **Caching**: PSEUDO_FILE_INDEX.json loaded once per process via lru_cache

### Revision Tasks

- [x] **A) Update compute_kmesh() to reciprocal formulation**
  - Removed slab detection heuristics
  - Added `compute_reciprocal_lengths()` for |b_i| calculation
  - Formula: `nk_i = max(1, ceil(|b_i| / Δk))`
  - Proper reciprocal lattice via cross products

- [x] **B) Update cutoff multipliers and rounding**
  - Changed multipliers to 0.8/1.0/1.2 (symmetric)
  - Added `round_cutoff_integer()` for integer Ry rounding
  - `PrecisionAdvice.ecutwfc/ecutrho` now typed as `int`

- [x] **C) Add caching for PSEUDO_FILE_INDEX.json**
  - Added `@lru_cache(maxsize=1)` on `_load_pseudo_index_cached()`
  - Added `get_pseudo_index()` and `clear_pseudo_index_cache()`
  - Advisor uses cached index via `get_pseudo_index()`

- [x] **D) Update detect_precision() for strict 3-way match**
  - Added `detect_precision_strict(params, lattice, base_wfc, base_rho)`
  - Matches conv_thr within abs_tol (`CONV_THR_ABS_TOL = 1e-11`)
  - Matches K_POINTS automatic mesh exactly
  - Matches ecutwfc AND ecutrho exactly (integer values)
  - Returns None if no level matches (aggregation interprets as CUSTOM)

- [x] **E) Update compile_precision for deterministic encoding**
  - Compiler outputs integer cutoffs from PrecisionAdvice
  - Canonical encoding: K_POINTS automatic, ecutwfc, ecutrho, conv_thr

- [x] **F) Update/extend tests** (35 tests, all passing)
  - [x] Updated Si kmesh expectations: 4×4×4 (low), 6×6×6 (med), 8×8×8 (high)
  - [x] Added `TestIntegerCutoffRounding` (3 tests)
  - [x] Added `TestPrecisionDetectorStrict` (4 tests: match, mismatch cutoff/kmesh/conv_thr)
  - [x] Added `TestPseudoIndexCaching` (2 tests: cache hits, clear cache)
  - [x] Added `TestCompilerDetectorEquivalence` with strict detection

---

## Changelog

- 2025-12-30: Initial plan created
- 2025-12-30: Milestones 1-5, 9-10 completed (backend + tests)
  - Added PrecisionOption enum and V1_DIMENSIONS
  - Created precision.py with PrecisionAdvisor
  - Added compile_precision and detect_precision
  - Updated integration for precision params
  - 29 unit tests passing, 782 total tests passing
- 2025-12-31: Revision phase COMPLETED
  - A) Updated K-mesh to reciprocal formulation with proper |b_i| calculation
  - B) Changed cutoff multipliers to symmetric 0.8/1.0/1.2, integer rounding
  - C) Added PSEUDO_FILE_INDEX caching via lru_cache
  - D) Added strict 3-way detection (conv_thr, kmesh, cutoffs)
  - E) Compiler outputs deterministic integer cutoffs
  - F) 35 precision tests passing, 788 total tests passing

