# Plan: Fix All Post-Compat-Removal Wirings + Backend Structure Test

**Date**: 2026-02-16
**Status**: In Progress

## Context

After deleting `compat.py` (~1000 lines of response shapers + payload adapters), the GUI TypeScript types and field accesses still expect fields that the compat layer used to inject. This plan covers ALL remaining broken wirings — primarily `CalculationInfo`, `DemoProjectInfo`, `DemoProjectResult`, `CalculationDetailResult`, and `StepInfo` — plus a backend unit test for the Si/Al structure import pipeline.

**Guiding principle**: Wire the GUI to the **new world** (native handler responses). We do NOT add old-world fields to backend responses. Instead, update TS types + GUI code to match what the daemon actually returns.

## Task 1: Fix All Remaining GUI Wirings

### 1A. StepInfo + CalculationInfo types
- Remove `step_file` from StepInfo, add `name?`, `status?`, `missing?`, `step_ulid?`
- Remove `absolute_path`, `mode`, `steps`, `structure` from CalculationInfo (not in list_calculations response)
- Add `engine?`, `status?`, `structure_ulid?`, `step_ulids?`, `step_count?`, `ulid?`

### 1B. CalculationListPanel — remove step chips from list view
- Replace step chips with step count text
- Remove mode badge (not in list response)
- Remove `calculation.structure` references (not in list response)

### 1C. CalculationListPanel — detail panel fixes
- `calculation.absolute_path` → `calculationDetail?.absolute_path`
- `calculation.steps` for reorder → `calculationDetail?.steps`
- `stepFootprints[step.step_file]` → `stepFootprints[step.name + '.step.yaml']`

### 1D. CalculationOverviewTab — step_file references
- Update step interface to remove `slug`, `step_file`
- `selectedStep.step_file` → derive from `step.name`
- `step.step_file` in tooltip → `step.name`

### 1E. CalculationDetailResult type
- Remove `step_file`/`slug` from steps
- Add `name?`, `status?`, `missing?`, `step_ulid?`, `structure_name?`, `calculation_id?`

### 1F-1H. Demo types
- Make `recommended_use`, `recommended_analysis`, `difficulty`, `estimated_runtime_scf` optional in DemoProjectInfo
- Fix DemoProjectResult to match native `{project_root, demo_id}`
- Guard `recommended_use` fallback in DemoGalleryPanel

### 1I-1K. Miscellaneous
- App.tsx: `calculation.steps?.length` → `calculation.n_steps ?? 0`
- Footprint lookup: key by `step.name + '.step.yaml'`

## Task 2: Backend Unit Test
- `tests/api/test_structure_import_pipeline.py`
- Si diamond and Al FCC CIF import → JSON → QE materialization
