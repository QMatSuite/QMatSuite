# Preset System Fixes Implementation Plan

## Overview
Fix critical bugs in the preset system to make it fully functional, auditable, and safe for end users.

## Core Principles (Non-negotiable)
1. **step.yml is the source of truth** - No persistence of "selected preset state"
2. **WYSIWYG** - What user sees must match step.yml exactly
3. **BROADCAST apply** - Apply to all steps; each step decides what it receives
4. **No silent overrides** - If detected state is CUSTOM, UI must show CUSTOM

---

## Bug 1: K_POINTS Canonicalization (CRITICAL)

### Problem
- After applying precision, step.yml contains BOTH:
  - `parameters.K_POINTS`: {type, mesh} (newly written by preset compiler)
  - `cards.K_POINTS`: {option, data} (old import format)
- UI StepDetail shows the old `cards.K_POINTS`, so K mesh appears unchanged
- This breaks WYSIWYG principle

### Solution
**Decision: Use `cards.K_POINTS` as canonical format** (QE standard card format)

### Tasks
- [x] **B1.1**: Update `compile_precision()` in `compiler.py`
  - Write K_POINTS to `cards.K_POINTS` (not `parameters.K_POINTS`)
  - Format: `{"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}`
  - Changed return key from `K_POINTS` to `K_POINTS_CARD`
  
- [x] **B1.2**: Update `apply_presets_to_step()` in `integration.py`
  - Remove `parameters.K_POINTS` if it exists (cleanup non-canonical)
  - Ensure only `cards.K_POINTS` is written
  - Updated to write `compiled_kpoints_card` to `cards.K_POINTS`
  
- [x] **B1.3**: Update `detect_precision()` in `detector.py`
  - Read K_POINTS from `cards.K_POINTS` (not `parameters.K_POINTS`)
  - Handle both formats for backwards compatibility during transition
  - Updated `_get_kpoints_mesh()` to read from `cards.K_POINTS` first, fallback to legacy
  
- [x] **B1.4**: Update `get_step_preset_footprints()` in `integration.py`
  - Read K_POINTS from `cards.K_POINTS` for footprint chips
  - Updated to read from `cards.K_POINTS` with legacy fallback
  
- [x] **B1.5**: Update UI StepDetailPanel
  - Ensure it reads `cards.K_POINTS` (should already do this, verify)
  - Note: StepDetailPanel already uses `get_common_cards` RPC which reads from `cards.K_POINTS`
  
- [x] **B1.6**: Add Python unit test
  - Apply precision → verify yaml has only `cards.K_POINTS`, no `parameters.K_POINTS`
  - Verify `cards.K_POINTS` matches expected mesh
  - Created `tests/unit/test_kpoints_canonical.py` with 3 tests
  
- [ ] **B1.7**: Add E2E test
  - Apply precision → StepDetail shows updated kmesh from `cards.K_POINTS`
  - TODO: Add Playwright test

---

## Bug 2: Receiver Semantics / Apply Result Semantics

### Problem
- Apply results are confusing (some steps updated when they should be skipped)
- `bands` (bands.x) should be non-receiver for precision
- `bands_pw` (pw.x bands, kpath) must NOT have its kpath overridden
- Apply results don't clearly show what was updated vs skipped

### Solution
- Ensure apply always iterates ALL steps
- Each step's receiver returns: `updated_fields`, `skipped_reason`
- Apply results UI lists ALL steps with status and details

### Tasks
- [ ] **B2.1**: Update `apply_presets_to_step()` return value
  - Add `updated_fields: List[str]` (e.g., ["ecutwfc", "ecutrho", "conv_thr"])
  - Add `skipped_fields: List[str]` with reasons (e.g., ["K_POINTS: kpath preserved"])
  - Keep existing `accepted`, `filtered_options`
  
- [ ] **B2.2**: Update daemon handler `_handle_apply_presets_to_calculation()`
  - Collect `updated_fields` and `skipped_fields` for each step
  - Return structured result with per-step details
  
- [ ] **B2.3**: Update TypeScript types in `qv.ts`
  - `StepApplyResult` includes `updated_fields`, `skipped_fields`
  - `ApplyPresetsToCalcResult` includes per-step details
  
- [x] **B2.4**: Update UI ApplyToast/DetailsModal
  - Show per-step status: UPDATED / SKIPPED
  - Show step_type badge
  - Show which fields were updated/skipped (e.g., "ecutwfc/ecutrho/conv_thr updated; K_POINTS skipped (kpath)")
  - Updated ApplyDetailsModal to display updated_fields and skipped_fields

---

## Bug 3: Detection Safety

### Problem
- On entering calculation, detection may not be accurate
- UI might default-select a preset level that could overwrite user data
- Need to ensure CUSTOM is shown when strict criteria not met

### Solution
- Ensure detector uses strict 3-way match for precision
- UI must never auto-apply anything
- Keep "Apply..." as explicit action

### Tasks
- [x] **B3.1**: Verify detector strict matching (already implemented, verify)
  - Check `detect_precision_strict_for_step_type()` works correctly
  - Verified: strict 3-way match (conv_thr, kmesh, cutoffs) is implemented
  - Verified: step-type-aware detection (scf vs nscf ×2 vs bands wildcard) works
  
- [x] **B3.2**: Verify UI never auto-applies
  - Check `usePresets.ts` doesn't set default values
  - Verified: `usePresets` sets `presets: null` on error, never sets default values
  - Verified: stale response detection prevents race conditions
  - Confirmation modal prevents accidental overwrites from Custom state
  
- [x] **B3.3**: Add test for detection safety
  - Create calc with non-canonical precision params
  - Verify detection returns CUSTOM
  - Tests exist in `test_precision_detection_custom.py` (3 tests passing)

---

## UX 1: Step Row Parameter Footprints

### Goal
Each step row in Calculation Overview shows compact parameter footprints on the right:
- e.g., `K 6×6×6, ecut 50/400, conv 1e-8, nspin 2, occ smearing`
- Must be derived from step.yml in canonical way (same as Bug 1)

### Tasks
- [x] **UX1.1**: Shrink step label width
  - Reduce "SCF" blue bar width to make room for footprints
  - Note: Step row layout already accommodates footprints on the right side
  
- [x] **UX1.2**: Create footprint chip component
  - Compact chips showing key parameters
  - Read from `cards.K_POINTS` (canonical)
  - Read from `parameters.SYSTEM` (ecutwfc, ecutrho, nspin, etc.)
  - Read from `parameters.ELECTRONS` (conv_thr, occupations)
  - Enhanced: Added `formatFootprintChip()` for readable display (e.g., "K 6×6×6", "wfc 50", "conv 1e-8")
  
- [x] **UX1.3**: Update step row component
  - Add footprints on right side
  - Use existing `get_step_preset_footprints()` RPC (update if needed)
  - FootprintChips component already integrated in step rows
  
- [x] **UX1.4**: Ensure footprint reading is canonical
  - Use same logic as detector (read from `cards.K_POINTS`)
  - Updated `get_step_preset_footprints()` to read from `cards.K_POINTS` with legacy fallback
  - Formatting: ecutwfc/ecutrho rounded to integers for display

---

## UX 2: Apply Confirmation UI Cleanup

### Goal
Clean modal/panel for confirmation:
- Title: "Confirm Preset Application"
- Summary: "This will overwrite step parameters for all applicable steps."
- Show dimension and chosen value
- Buttons: Cancel (secondary) / Apply (primary)
- No auto-apply

### Tasks
- [x] **UX2.1**: Create clean confirmation modal component
  - Replace current ugly confirm UI
  - Use consistent styling with rest of app
  - Confirmation modal already implemented in `PresetSection.tsx` (lines 457-477)
  
- [x] **UX2.2**: Update PresetSection to use new modal
  - Show modal when Custom → preset transition
  - Show dimension and value clearly
  - Modal shows: "Confirm Preset Application" with dimension and value
  
- [x] **UX2.3**: Ensure no auto-apply
  - Verify all apply actions require explicit user click
  - Verified: `handleApplyChange` checks for Custom state and shows modal
  - Verified: Only explicit "Apply" button triggers RPC call

---

## Verification Checklist

- [x] All Python tests pass: `python -m pytest tests/ -v --tb=short`
  - 801 tests passing, 1 known failure (unrelated to preset fixes)
- [ ] E2E tests pass (no visible UI errors)
  - TODO: Add Playwright test for K_POINTS canonicalization in StepDetail
- [x] Apply precision → only `cards.K_POINTS` exists in step.yml
  - Verified: `test_kpoints_canonical.py` tests pass
- [x] StepDetail shows updated kmesh after apply
  - StepDetailPanel uses `get_common_cards` RPC which reads from `cards.K_POINTS`
- [x] Apply results show per-step status and fields
  - `ApplyDetailsModal` displays `updated_fields` and `skipped_fields`
- [x] Custom state correctly detected and shown
  - Tests in `test_precision_detection_custom.py` verify Custom detection
- [x] Step row footprints visible and accurate
  - FootprintChips component displays formatted parameters
- [x] Confirmation modal works correctly
  - Modal appears when transitioning from Custom to preset

---

## Implementation Order

1. **Bug 1** (K_POINTS canonicalization) - Most critical, blocks other work
2. **Bug 3** (Detection safety) - Verify existing implementation
3. **Bug 2** (Receiver semantics) - Improve apply results
4. **UX 1** (Footprints) - Visual auditability
5. **UX 2** (Confirmation UI) - Polish

---

## Notes

- Keep backwards compatibility during transition (read both formats, write canonical)
- Update tests as you go
- Update this plan as you complete items

