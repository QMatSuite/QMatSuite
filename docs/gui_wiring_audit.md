# GUI Wiring Audit

**Created**: 2026-02-02
**Purpose**: Comprehensive audit of backend RPC contracts and frontend wiring for GEN/SPEC compliance

---

## Executive Summary

This audit identifies legacy field usage across the RPC boundary between the daemon backend and the GUI frontend. The goal is to ensure compliance with the naming conventions:

| Category | Allowed Fields | Forbidden Fields |
|----------|----------------|------------------|
| Step Type | `step_type_gen`, `step_type_spec` | `type`, `step_type` |
| Identity | `ulid`, `step_ulid`, `calc_ulid`, `run_ulid` | `id`, `step_id`, `calc_id`, `run_id` |

---

## Part A: Backend RPC Contract Audit

### Summary Matrix

| Compliance Status | Count | Description |
|-------------------|-------|-------------|
| **Fully Compliant** | 12 | Remove all legacy fields, use new schema |
| **Partially Compliant** | 5 | Still emit `type` field for v0 compat layer |
| **Non-Compliant** | 0 | All have documented compat reasons |

### Fully Compliant Endpoints

These endpoints correctly emit only the new field names:

| Endpoint | Handler Location | Fields Returned |
|----------|------------------|-----------------|
| `get_step_detail` | server.py:3046 | `step_type_spec`, `step_type_gen` (via compat.py:924-945) |
| `add_step_to_calculation` | server.py:4125 | `step_ulid`, `step_type_spec`, `step_type_gen`, `status` |
| `get_calculation_detail` | server.py:4049 | `step_ulid`, `step_type_spec`, `step_type_gen` (removes `id`, `type`) |
| `update_step_params` | server.py:3127 | Delegates to `_shape_step_detail()` |
| `reorder_calculation_steps` | server.py:4092 | Delegates to `_shape_calculation_detail()` |
| `import_step_from_qe_input` | server.py:4181 | Delegates to `_shape_calculation_detail()` |
| `delete_step` | server.py:3605 | Status response only (no step data) |
| `run_calculation` | server.py:5239 | `step_ulid`, `step_type_spec`, `status` |
| `run_step` | server.py:5345 | Job response only (no step data) |
| `run_single_step` | server.py:5420 | Job response only |
| `apply_presets_to_step` | server.py:3772 | `step_type_gen` (read from file per Constitution v1.1) |
| `apply_presets_to_calculation` | server.py:3832 | Per-step results with `step_type_gen` |

### Partially Compliant Endpoints (v0 Compat Layer)

These endpoints emit legacy `type` field for v0 client compatibility:

| Endpoint | Handler Location | Compat Shaper | Legacy Field Conversion |
|----------|------------------|---------------|-------------------------|
| `list_calculations` | server.py:2034 | compat.py:462-528 | Line 521: `step["type"] = step["step_type_gen"]` |
| `change_calculation_structure` | server.py:4222 | compat.py:406-437 | Line 426: `step["type"] = step["step_type_gen"]` |
| `update_calculation_species_map` | server.py:4405 | compat.py:771-811 | Line 791: `type` field populated |
| `list_journal_entries` | (via compat) | compat.py:203-216 | Line 215: `step["type"] = step["step_type_gen"]` |

### Field Normalization in Compat Layer

**Location**: `src/quantumvitas/daemon/compat.py`

| Function | Lines | What It Does |
|----------|-------|--------------|
| `_shape_calculation_detail()` | 707-747 | Normalizes `id` → `step_ulid`, removes `type`, `id` |
| `_shape_step_detail()` | 924-945 | Removes `meta`, `status`, keeps `step_type_spec`/`step_type_gen` |
| `_shape_add_step_to_calculation()` | 298-339 | Converts `type` via `_derive_step_name_from_type()`, removes `id` |

### Constitution v1.1 Compliance Check

**Requirement (§4.7)**: Daemon MUST NOT convert between GEN/SPEC. All `step_type_gen` values MUST be read from DTO fields.

**Status**:
- **COMPLIANT**: `add_step_to_calculation` (server.py:4167-4170) reads both fields from DTO
- **COMPLIANT**: `apply_presets_to_step` (server.py:3922) reads from YAML without conversion
- **PARTIAL**: Compat shapers still CONVERT `step_type_gen` → `type` for v0 clients

---

## Part B: Frontend Wiring Audit

### Type Definition Violations

**File**: `gui/src/types/qv.ts`

| Line | Type | Field | Violation | Should Be |
|------|------|-------|-----------|-----------|
| 40 | `QVError.details` | `step_id?: string` | Legacy identity | `step_ulid?: string` |
| 327-328 | `JobStepInfo` | `step_id?: string`, `step_type: string` | Legacy fields | `step_ulid`, `step_type_gen` |
| 335 | `JobInfo` | `id: string` | Legacy identity | `run_ulid: string` |
| 698 | RPC payload | `step_type: string` | Legacy step type | `step_type_gen: string` |
| 1362 | RPC payload | `step_type: string` | Legacy step type | `step_type_gen: string` |
| 1576-1580 | Preset scope | `type`, `step_types` | Legacy type field | `step_type_gen`, `step_type_gens` |
| 1669, 1673 | History | `calc_id?: string`, `latest_run_id` | Legacy identity | `calc_ulid`, `latest_run_ulid` |
| 1681, 1684 | History | `step_id: string`, `run_id: string` | Legacy identity | `step_ulid`, `run_ulid` |
| 1693-1706 | Pin RPC | `run_id`, `step_id` | Legacy identity | `run_ulid`, `step_ulid` |
| 1788 | Structure change | `step_id: string` | Legacy identity | `step_ulid: string` |
| 1826-1830 | Timeline entry | `calc_id?`, `step_id?`, `run_id?`, `step_ids?`, `step_types?` | Legacy fields | ULID variants |
| 1844-1845 | Step digests | `step_id`, `step_type` | Legacy fields | `step_ulid`, `step_type_gen` |

### Correct Type Definitions (Reference)

These types already use the correct field names:

| Line | Type | Fields | Status |
|------|------|--------|--------|
| 194-199 | `StepInfo` | `ulid`, `step_type_spec`, `step_type_gen` | COMPLIANT |
| 424-425 | `StepDetail` | `step_type_spec`, `step_type_gen` | COMPLIANT |

---

### Runtime Code Violations by File

#### 1. `App.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 1300-1301 | `s.id`, `s.type` | Uses `id` and `type` from `detail.steps` |
| 2410-2411, 2423 | `s.id`, `s.type` | Logging uses legacy names |

#### 2. `StepDetailPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 234 | `stepDetail.step_type` | Should be `step_type_gen` or `step_type_spec` |
| 365 | `step_type: response.data.step_type` | Legacy field name |
| 528-529 | `stepDetail.step_type` | Legacy field name |
| 1362 | `{stepDetail.step_type}` | Display uses legacy |
| 1590 | `stepDetail.step_type?.toLowerCase()` | Comparison uses legacy |

#### 3. `CalculationRunTab.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 245 | `step.step_type \|\| step.type` | Dual fallback pattern (handles both) |

#### 4. `HistoryPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 154-165 | `entry.run_id` | Should be `run_ulid` |
| 221, 224 | `step.step_id`, `step.step_type` | Legacy fields |
| 254-256 | `entry.step_types` | Should be `step_type_gens` |

#### 5. `JobsPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 77 | `step.step_type` | Legacy field |
| 94-95 | `step.step_type` | Legacy field |
| 109 | `currentStep?.step_type` | Legacy field |

#### 6. `AnalysisPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 831 | `step.type?.toLowerCase()` | Uses `type` (legacy in some contexts) |

#### 7. `ScanSummary.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 31 | `step.id` | Legacy identity |
| 35-36 | `step.id`, `step.type` | Legacy fields |

#### 8. `CalculationAnalysisPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 318 | `step_id: selectedStepId` | RPC payload uses legacy |
| 322 | `run_id: response.data.run_id` | Response uses legacy |
| 378-379 | `run_id`, `step_id` | Pin RPC payload uses legacy |
| 81-82 | `s.id`, `selectedStep?.type` | Legacy fields |
| 443-445 | `s.id`, `s.type` | Display uses legacy |

#### 9. `CalculationOverviewTab.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 296 | `step_type: newStepType` | RPC payload uses legacy |

#### 10. `CalculationListPanel.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 287-289 | `step.id`, `step.type` | Display uses legacy |
| 593, 597, 603, 845 | `step.id` | Step selection uses legacy |
| 1444-1445 | `step.id`, `step.type` | Logging uses legacy |
| 1458 | `step.id` | Display uses legacy |

#### 11. `hooks/useQVClient.ts`

| Line | Usage | Issue |
|------|-------|-------|
| 382 | `step_type: stepType` | RPC payload uses legacy |

#### 12. `PresetSection.tsx`

| Line | Usage | Issue |
|------|-------|-------|
| 54-55 | `dimension.scope.type`, `dimension.scope.step_types` | Legacy scope fields |
| 72 | `v.step_types` | Legacy field |
| 207 | `step.step_type` | Legacy field |

---

## Summary Tables

### Backend Endpoints Emitting Legacy Fields

| Endpoint | Legacy Fields Emitted | Reason |
|----------|----------------------|--------|
| `list_calculations` | `type` | v0 compat |
| `change_calculation_structure` | `type` | v0 compat |
| `update_calculation_species_map` | `type` | v0 compat |
| `list_journal_entries` | `type` | v0 compat |

### Frontend Files Needing Updates

| File | Issue Count | Categories |
|------|-------------|------------|
| `types/qv.ts` | 18 | Type definitions |
| `StepDetailPanel.tsx` | 5 | Runtime accesses |
| `HistoryPanel.tsx` | 4 | Runtime accesses |
| `CalculationAnalysisPanel.tsx` | 6 | Runtime accesses |
| `CalculationListPanel.tsx` | 6 | Runtime accesses |
| `JobsPanel.tsx` | 3 | Runtime accesses |
| `App.tsx` | 3 | Logging |
| `CalculationOverviewTab.tsx` | 1 | RPC payload |
| `CalculationRunTab.tsx` | 1 | Fallback pattern |
| `ScanSummary.tsx` | 2 | Runtime accesses |
| `AnalysisPanel.tsx` | 1 | Runtime accesses |
| `useQVClient.ts` | 1 | RPC payload |
| `PresetSection.tsx` | 3 | Runtime accesses |

---

## Appendix: Field Mapping Reference

### Step Type Fields

| Legacy | New | Description |
|--------|-----|-------------|
| `type` | `step_type_gen` | Generic step type (e.g., "scf", "relax") |
| `step_type` | `step_type_spec` | Engine-specific step type (e.g., "qe_scf") |

### Identity Fields

| Legacy | New | Description |
|--------|-----|-------------|
| `id` | `ulid` | Generic ULID (context-dependent) |
| `step_id` | `step_ulid` | Step ULID |
| `calc_id` | `calc_ulid` | Calculation ULID |
| `run_id` | `run_ulid` | Run ULID |

### Conversion Utilities (SSOT)

All conversions MUST use functions from `src/quantumvitas/workflow/step_type_convert.py`:

| Function | Purpose |
|----------|---------|
| `spec_from(prefix, gen)` | Create SPEC from engine prefix + GEN |
| `gen_from(spec)` | Extract GEN from SPEC |
| `prefix_from(spec)` | Extract engine prefix from SPEC |
| `is_spec(step_type)` | Check if step type is SPEC format |
| `is_gen(step_type)` | Check if step type is GEN format |
