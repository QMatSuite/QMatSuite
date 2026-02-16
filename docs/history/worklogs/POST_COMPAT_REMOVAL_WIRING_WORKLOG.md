# Worklog: Post-Compat-Removal Wiring Fixes

**Date**: 2026-02-16
**Plan**: `docs/history/plans/POST_COMPAT_REMOVAL_WIRING_PLAN.md`

## Progress

### Step 1: Update TS types in qv.ts
- [ ] StepInfo
- [ ] CalculationInfo
- [ ] CalculationDetailResult
- [ ] DemoProjectInfo
- [ ] DemoProjectResult

### Step 2: Fix CalculationListPanel.tsx
- [ ] Remove structure/mode/steps references in list view
- [ ] Fix stepFootprints lookup in detail view
- [ ] Fix absolute_path in detail view
- [ ] Fix handleStartReorder

### Step 3: Fix CalculationOverviewTab.tsx
- [ ] Update CompactStepList step interface
- [ ] Fix step_file references
- [ ] Fix absolute_path reference

### Step 4: Fix App.tsx + DemoGalleryPanel.tsx
- [ ] App.tsx: calculation.steps?.length
- [ ] DemoGalleryPanel.tsx: recommended_use guard

### Step 5: TypeScript build check
- [ ] npx tsc --noEmit passes

### Step 6: Write backend test
- [ ] tests/api/test_structure_import_pipeline.py

### Step 7: Run Python tests
- [ ] All tests pass

---

## Detailed Log

(entries added as work proceeds)
