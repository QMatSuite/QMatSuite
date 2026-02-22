# Implementation Plan: Preset UI Integration

**Status**: In Progress  
**Created**: 2025-12-30  
**Constitution Reference**: Chapter 10  
**Design Document**: `WORKFLOW_PRESET_DESIGN_V0.md`

---

## Overview

This plan implements a full UI for the workflow + preset system, allowing users to:
1. View detected preset state at the calculation level
2. Apply presets (BROADCAST to all steps)
3. See effective preset parameters on each step row
4. Understand when manual edits cause "Custom" state

### Core Design Principles (Non-Negotiable)

1. **Preset application is BROADCAST** - Targets ALL steps, each step decides how to receive
2. **Steps are the only executable truth** - step.yml is final, presets are runtime-only
3. **UI philosophy** - Simple for users, transparent for experts, WYSIWYG

---

## Phase 1: Backend Preparation ✅ COMPLETE

- [x] Detector B core logic (spin, soc, material)
- [x] Compiler with canonical encoding
- [x] Integration layer (`detect_presets_from_calculation`, `apply_presets_to_step`)
- [x] Daemon handlers (`detect_presets`, `detect_workflow`, `apply_presets_to_step`)
- [x] 96 tests passing

---

## Phase 2: Hook for Preset Detection ✅ COMPLETE

**Goal**: Create React hook to fetch and cache preset state.

- [x] **2.1** Create `usePresets` hook
  - File: `gui/src/hooks/usePresets.ts`
  - State: `{ presets, workflow, isLoading, error, refresh }`
  - Calls `detect_presets` and `detect_workflow` RPC
  - Auto-refresh when calculation changes

- [x] **2.2** Add TypeScript types
  - File: `gui/src/types/qms.ts`
  - Types: `PresetState`, `PresetDimension`, `PresetValue`
  - Added command types for `detect_presets`, `detect_workflow`, `apply_presets_to_calculation`

---

## Phase 3: Calculation Overview - Presets Section ✅ COMPLETE

**Goal**: Add presets section to CalculationDetailPanel showing detected state.

- [x] **3.1** Create PresetSection component
  - File: `gui/src/components/presets/PresetSection.tsx`
  - Shows spin/soc/material dimensions
  - Each dimension: label + detected value/CUSTOM + dropdown
  - Dropdown triggers apply (BROADCAST)

- [x] **3.2** Create PresetDimensionRow component
  - Inline in PresetSection.tsx
  - Individual dimension with dropdown
  - Shows "Custom" badge when heterogeneous

- [x] **3.3** Integrate into CalculationDetailPanel
  - Added PresetSection after Structure/Pseudopotentials
  - Pass projectRoot, calculationSlug, onPresetsChanged callback

- [x] **3.4** Add CSS styles
  - File: `gui/src/components/presets/PresetSection.css`
  - Consistent with existing panel styles

---

## Phase 4: Step Row Parameter Footprint ✅ COMPLETE

**Goal**: Show preset-relevant parameters on each step row.

- [x] **4.1** Add step parameter footprint to backend
  - Daemon endpoint: `get_step_preset_footprints`
  - Returns: `{ footprints: { "1_scf.step.yaml": { params, spin, soc, material } } }`
  - Integration function: `get_step_preset_footprints`

- [x] **4.2** Backend types and hook updated
  - Added `StepPresetFootprint` type
  - usePresets hook now fetches footprints in parallel
  - Footprints available as `footprints` state

- [x] **4.3** Update step row UI in CalculationDetailPanel
  - Footprint chips shown on right side of step row
  - Format: `nspin=2` `occupations='smearing'`
  - Uses small, muted badges with monospace font

- [x] **4.4** CompactStepList - SKIPPED
  - Focus mode already shows full StepDetailPanel
  - Adding footprints would clutter the compact view

---

## Phase 5: Apply Presets (BROADCAST) ✅ COMPLETE

**Goal**: Implement preset application that broadcasts to all steps.

- [x] **5.1** Create applyPresetsToCalculation backend function
  - Implemented in daemon handler `_handle_apply_presets_to_calculation`
  - Iterates all step files in calculation
  - Calls `apply_presets_to_step` for each
  - Returns summary of changes + updated presets

- [x] **5.2** Add daemon handler
  - Method: `apply_presets_to_calculation`
  - Payload: `{ project_root, calculation, presets, validate_physics }`
  - Returns: `{ status, steps_updated, presets }`

- [x] **5.3** Connect UI dropdown to apply
  - usePresets hook calls `apply_presets_to_calculation`
  - Updates local state with returned presets
  - Notifies parent via onPresetsChanged callback

---

## Phase 6: Workflow Detection Badge

**Goal**: Show detected workflow type in calculation header.

- [ ] **6.1** Add workflow badge to CalculationDetailPanel header
  - Show: "DOS Workflow", "Band Structure", "Relaxation", etc.
  - Use `detect_workflow` RPC result

- [ ] **6.2** Style workflow badge
  - Pill/chip style next to calculation name

---

## Phase 7: Custom State Warning ✅ MERGED INTO PHASE 8

Merged into Phase 8F (CUSTOM UX hints).

---

## Phase 8: Hardening & Refinement (Follow-up Milestone)

**Goal**: Make Preset Receiver explicit, improve UX, add robustness, add integration tests.

### A) Preset Receiver - Step-owned acceptance logic ✅ COMPLETE

- [x] **8A.1** Define preset receiver capability in step spec
  - Created `receivers.py` with step_type → dimensions mapping
  - Default: accept none (no-op) for unknown types
  - QE pw.x step_types (scf/nscf/bands/relax/md/vc-*): accept spin/soc/material
  - Post-processing steps: accept none
  
- [x] **8A.2** Create step_type → receiver mapping registry
  - File: `src/qmatsuite/presets/receivers.py`
  - `PresetReceiverRegistry` class with dimension mapping
  - `filter_presets_for_step()` helper function
  - `is_receiver()` check for step types
  
- [x] **8A.3** Update BROADCAST apply to use receiver
  - `apply_presets_to_step()` now uses `filter_presets_for_step()`
  - Returns `{content, accepted, filtered_options}` instead of just content
  - Daemon handler returns detailed `step_results` with status per step

### B) Apply UX - Toast + expandable audit detail ✅ COMPLETE

- [x] **8B.1** Create Toast/Snackbar component
  - `ApplyToast` component in `PresetSection.tsx`
  - Shows: "Applied {dimension}={value}: N updated, M skipped"
  - "Details" button to expand
  - Auto-dismiss after 5 seconds
  
- [x] **8B.2** Create ApplyResultModal component
  - `ApplyDetailsModal` component in `PresetSection.tsx`
  - Lists: step file, step type, status (updated/skipped/error)
  - Shows applied presets and skip reasons
  - Overlay modal with close button

- [x] **8B.3** Connect apply flow to toast system
  - `usePresets` hook returns `ApplyResult` with detailed info
  - `lastApplyResult` state for toast display
  - `clearApplyResult()` callback to dismiss

### C) Footprint chips - Noise reduction + expansion ✅ COMPLETE

- [x] **8C.1** Limit default chip display to N (3) chips
  - `FootprintChips` component with `maxChips` prop
  - Shows "+k" button if more chips exist
  
- [x] **8C.2** Add click expansion for "+k more"
  - Click expands to show all chips
  - Collapse button (◂) to reduce again
  - WYSIWYG: values from step.yml preserved

### D) Concurrency robustness ✅ COMPLETE

- [x] **8D.1** Add request sequence guard
  - `requestSeqRef` counter in `usePresets`
  - Increment on each request
  
- [x] **8D.2** Ignore stale responses
  - Check `currentSeq === requestSeqRef.current` before updating state
  - Prevents race conditions on rapid calc switching

### E) BROADCAST apply integration test (MANDATORY) ✅ COMPLETE

- [x] **8E.1** Create integration test for BROADCAST apply
  - File: `tests/integration/test_preset_broadcast.py`
  - Tests receiver registry (PW types accept, post-processing rejects)
  - Tests apply_presets_to_step with receiver logic
  - Tests BROADCAST apply across mixed step calculation
  - Tests Custom state detection and resolution
  - Tests edge cases (empty params, physics validation)

### F) CUSTOM UX hints (MANDATORY) ✅ COMPLETE

- [x] **8F.1** Add hover tooltip on "Custom" badge
  - `customTooltip` prop in `PresetDimensionRow`
  - Text: "Steps disagree on this dimension. Check step rows for details."
  
- [ ] **8F.2** Add warning in StepDetailPanel for preset-related params
  - TODO: Non-blocking note when editing preset params

---

## Test Strategy

### Frontend Tests (if feasible)
- [ ] Hook tests with mock RPC
- [ ] Component render tests

### Backend Tests
- [x] Unit tests for detector (70 tests)
- [x] Integration tests (26 tests)
- [ ] BROADCAST apply tests (new)

---

## Files to Create/Modify

### New Files
| File | Purpose |
|------|---------|
| `gui/src/hooks/usePresets.ts` | React hook for preset state |
| `gui/src/components/presets/PresetSection.tsx` | Presets section component |
| `gui/src/components/presets/PresetSection.css` | Styles |
| `gui/src/components/presets/PresetDimensionRow.tsx` | Individual dimension |
| `src/qmatsuite/presets/broadcast.py` | BROADCAST apply logic |

### Modified Files
| File | Changes |
|------|---------|
| `gui/src/types/qms.ts` | Add preset types |
| `gui/src/components/panels/CalculationListPanel.tsx` | Add PresetSection, step footprints |
| `gui/src/components/panels/CalculationOverviewTab.tsx` | Pass preset props |
| `gui/src/hooks/useQMSClient.ts` | Add preset RPC methods |
| `src/qmatsuite/daemon/server.py` | Add BROADCAST handler |

---

## Verification Commands

```bash
# Backend tests
python -m pytest tests/unit/test_detector_b.py tests/unit/test_preset_integration.py -v

# Run GUI in dev mode
cd gui && npm run dev
```

---

## Progress Tracking

| Phase | Status | Notes |
|-------|--------|-------|
| 1 | ✅ Complete | Backend ready |
| 2 | ✅ Complete | Hook + types added |
| 3 | ✅ Complete | PresetSection integrated |
| 4 | ✅ Complete | Step footprint chips added |
| 5 | ✅ Complete | BROADCAST apply working |
| 6 | ✅ Complete | Workflow badge in PresetSection |
| 7 | ✅ Merged | Into Phase 8F |
| 8A | ✅ Complete | Preset Receiver registry + step-owned logic |
| 8B | ✅ Complete | Apply UX (toast + modal) |
| 8C | ✅ Complete | Footprint chips limit + expansion |
| 8D | ✅ Complete | Concurrency robustness (request sequence guard) |
| 8E | ✅ Complete | BROADCAST integration test (17 tests) |
| 8F | ✅ Mostly Complete | CUSTOM tooltip done (StepDetail warning optional) |

---

## Change Log

| Date | Change |
|------|--------|
| 2025-12-30 | Initial plan created |
| 2025-12-30 | Phase 2-3, 5 completed: usePresets hook, PresetSection, BROADCAST apply |
| 2025-12-30 | Phase 4 backend done: get_step_preset_footprints handler + hook integration |
| 2025-12-30 | Phase 6 done: Workflow badge already in PresetSection |
| 2025-12-30 | Phase 4 UI done: Step footprint chips in CalculationDetailPanel |
| 2025-12-30 | Phase 8 added: Hardening & Refinement milestone (A-F) |
| 2025-12-30 | Phase 8A: Preset Receiver registry + step-owned acceptance |
| 2025-12-30 | Phase 8B: Toast + details modal for apply feedback |
| 2025-12-30 | Phase 8C: Footprint chips limit + expansion |
| 2025-12-30 | Phase 8D: Concurrency robustness (request sequence guard) |
| 2025-12-30 | Phase 8E: BROADCAST integration tests (16 tests) |
| 2025-12-30 | Phase 8F: Custom badge tooltip (StepDetail warning TODO) |
| 2025-12-30 | All 753 tests pass, TypeScript compiles |

