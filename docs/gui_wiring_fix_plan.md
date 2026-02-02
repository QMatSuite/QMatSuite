# GUI Wiring Fix Plan

**Created**: 2026-02-02
**Amended**: 2026-02-02 (Hard constraints added)
**Prerequisite**: `docs/gui_wiring_audit.md` (audit findings)
**Purpose**: Step-by-step implementation plan to fix frontend legacy field usage

---

## HARD CONSTRAINTS (MANDATORY - NON-NEGOTIABLE)

### 1. Backend is FROZEN

- Backend code may ONLY be touched if audit evidence proves an RPC endpoint does NOT emit new fields (`ulid`, `step_type_gen`, `step_type_spec`) or does NOT accept new fields where required.
- If backend changes are required: keep backend fully green (tests pass), make changes minimal and directly tied to missing RPC fields.

### 2. ABSOLUTELY FORBIDDEN - No Legacy Mapping in Backend

Do NOT create or use any legacy mapping in backend/daemon compat, especially:
- `step_type_gen` → `step_type` (FORBIDDEN)
- `step_ulid` → `step_id` (FORBIDDEN)
- `ulid` → `id` (FORBIDDEN)

No "adapter/shim/compat for GUI" is allowed anywhere in the backend.

### 3. GUI Must Live in New World ONLY

- GUI code must read/write ONLY the new fields: `ulid`, `step_ulid`, `calc_ulid`, `run_ulid`, `step_type_gen`, `step_type_spec`
- Old fields (`id`, `type`, `step_type`, `step_id`, `calc_id`, `run_id`) are deprecated
- GUI usage of legacy fields is a VIOLATION even if backend still emits them for golden contract reasons

### 4. No Optional Legacy Fallbacks in TypeScript Types

- Do NOT model legacy fields in TS types, not even as optional
- If unavoidable, mark as `unknown` and do not access
- No fallback patterns like `step.step_type || step.type` - use ONLY new fields

---

## Non-Negotiable Field Rules

| Category | Allowed Fields | FORBIDDEN Fields |
|----------|----------------|------------------|
| Step Type | `step_type_gen`, `step_type_spec` | `type`, `step_type` |
| Identity | `ulid`, `step_ulid`, `calc_ulid`, `run_ulid` | `id`, `step_id`, `calc_id`, `run_id` |

---

## Phase 1: Update Type Definitions

**File**: `gui/src/types/qv.ts`

### Step 1.1: Fix QVError

```diff
- step_id?: string;
+ step_ulid?: string;
```
**Line**: 40

### Step 1.2: Fix JobStepInfo

```diff
- step_id?: string;
- step_type: string;
+ step_ulid?: string;
+ step_type_gen: string;
+ step_type_spec?: string;
```
**Lines**: 327-328

### Step 1.3: Fix JobInfo

```diff
- id: string; // equals run_id
+ run_ulid: string;
```
**Line**: 335

### Step 1.4: Fix RPC Payloads (list_qe_ui_parameters)

```diff
- step_type: string;
+ step_type_gen: string;
```
**Line**: 698

### Step 1.5: Fix RPC Payloads (add_step_to_calculation)

```diff
- step_type: string;
+ step_type_gen: string;
```
**Line**: 1362

### Step 1.6: Fix Preset Scope Types

```diff
- type: 'variant_step_types';
- step_types: string[];
+ type: 'variant_step_type_gens';
+ step_type_gens: string[];
```
**Lines**: 1576-1580

### Step 1.7: Fix get_project_history Response

```diff
- calc_id?: string;
- latest_run_id: string | null;
+ calc_ulid?: string;
+ latest_run_ulid: string | null;
```
**Lines**: 1669, 1673

### Step 1.8: Fix get_latest_run_for_step

```diff
- step_id: string;
- run_id: string | null;
+ step_ulid: string;
+ run_ulid: string | null;
```
**Lines**: 1681, 1684

### Step 1.9: Fix Pin RPC Types

```diff
- run_id: string;
- step_id: string;
+ run_ulid: string;
+ step_ulid: string;
```
**Lines**: 1693-1706

### Step 1.10: Fix CalculationStructureChangeResult

```diff
- step_id: string;
+ step_ulid: string;
```
**Line**: 1788

### Step 1.11: Fix HistoryTimelineEntry

```diff
- calc_id?: string;
- step_id?: string;
- run_id?: string;
- step_ids?: string[];
- step_types?: string[];
+ calc_ulid?: string;
+ step_ulid?: string;
+ run_ulid?: string;
+ step_ulids?: string[];
+ step_type_gens?: string[];
```
**Lines**: 1826-1830

### Step 1.12: Fix Step Digests

```diff
- step_id: string;
- step_type: string;
+ step_ulid: string;
+ step_type_gen: string;
```
**Lines**: 1844-1845

---

## Phase 2: Update Runtime Code

### Step 2.1: App.tsx (Logging)

**Lines**: 1300-1301, 2410-2411, 2423

Update logging to use new field names:
```diff
- stepIds: detail.steps?.map(s => s.id) ?? [],
- stepOrder: detail.steps?.map((s, i) => ({ index: i, id: s.id, type: s.type })) ?? [],
+ stepUlids: detail.steps?.map(s => s.ulid) ?? [],
+ stepOrder: detail.steps?.map((s, i) => ({ index: i, ulid: s.ulid, step_type_gen: s.step_type_gen })) ?? [],
```

### Step 2.2: StepDetailPanel.tsx

**Line 234**:
```diff
- const module = stepDetail ? stepTypeToModule(stepDetail.step_type) : null;
+ const module = stepDetail ? stepTypeToModule(stepDetail.step_type_gen) : null;
```

**Line 365**:
```diff
- step_type: response.data.step_type,
+ step_type_gen: response.data.step_type_gen,
```

**Line 528-529**:
```diff
- const module = stepTypeToModule(stepDetail.step_type);
- const stepType = stepDetail.step_type;
+ const module = stepTypeToModule(stepDetail.step_type_gen);
+ const stepType = stepDetail.step_type_gen;
```

**Line 1362**:
```diff
- {stepDetail.step_type}
+ {stepDetail.step_type_gen}
```

**Line 1590**:
```diff
- stepDetail.step_type?.toLowerCase() === 'relax'
+ stepDetail.step_type_gen?.toLowerCase() === 'relax'
```

### Step 2.3: CalculationRunTab.tsx

**Line 245** (REMOVE FALLBACK PATTERN):
```diff
- {step.step_type || step.type || 'Unknown'}
+ {step.step_type_gen || 'Unknown'}
```

### Step 2.4: HistoryPanel.tsx

**Line 154-165**:
```diff
- const isExpanded = entry.run_id ? expandedRuns.has(entry.run_id) : false;
- const isLatest = entry.run_id === latestRunId;
- onClick={() => entry.run_id && toggleRunExpanded(entry.run_id)}
+ const isExpanded = entry.run_ulid ? expandedRuns.has(entry.run_ulid) : false;
+ const isLatest = entry.run_ulid === latestRunUlid;
+ onClick={() => entry.run_ulid && toggleRunExpanded(entry.run_ulid)}
```

**Line 221, 224**:
```diff
- key={step.step_id || idx}
- {step.step_type}
+ key={step.step_ulid || idx}
+ {step.step_type_gen}
```

**Line 254-256**:
```diff
- {entry.step_types.join(' → ')}
+ {entry.step_type_gens.join(' → ')}
```

### Step 2.5: JobsPanel.tsx

**Lines 77, 94-95, 109**:
```diff
- title={`${step.step_type}: ${step.status}`}
- {step.step_type}
- ${currentStep?.step_type || '...'}
+ title={`${step.step_type_gen}: ${step.status}`}
+ {step.step_type_gen}
+ ${currentStep?.step_type_gen || '...'}
```

### Step 2.6: AnalysisPanel.tsx

**Line 831**:
```diff
- const t = step.type?.toLowerCase() || '';
+ const t = step.step_type_gen?.toLowerCase() || '';
```

### Step 2.7: ScanSummary.tsx

**Line 31, 35-36**:
```diff
- const stepDetail = stepDetails.get(step.id);
- stepId: step.id,
- stepType: step.type || 'unknown',
+ const stepDetail = stepDetails.get(step.ulid);
+ stepUlid: step.ulid,
+ stepType: step.step_type_gen || 'unknown',
```

### Step 2.8: CalculationAnalysisPanel.tsx

**Line 318**:
```diff
- step_id: selectedStepId,
+ step_ulid: selectedStepUlid,
```

**Line 322**:
```diff
- run_id: response.data.run_id,
+ run_ulid: response.data.run_ulid,
```

**Line 378-379**:
```diff
- run_id: pinInfo.run_id,
- step_id: selectedStepId,
+ run_ulid: pinInfo.run_ulid,
+ step_ulid: selectedStepUlid,
```

**Lines 81-82**:
```diff
- steps.find(s => s.id === selectedStepId) || null;
- selectedStep?.type?.toLowerCase() || '';
+ steps.find(s => s.ulid === selectedStepUlid) || null;
+ selectedStep?.step_type_gen?.toLowerCase() || '';
```

**Lines 443-445**:
```diff
- s.id
- s.type
+ s.ulid
+ s.step_type_gen
```

### Step 2.9: CalculationOverviewTab.tsx

**Line 296**:
```diff
- step_type: newStepType,
+ step_type_gen: newStepType,
```

### Step 2.10: CalculationListPanel.tsx

**Lines 287-289**:
```diff
- key={step.id}
- {step.type}
+ key={step.ulid}
+ {step.step_type_gen}
```

**Lines 593, 597, 603, 845**:
```diff
- step.id
+ step.ulid
```

**Lines 1444-1445**:
```diff
- stepId: step.id,
- stepType: step.type,
+ stepUlid: step.ulid,
+ stepType: step.step_type_gen,
```

**Line 1458**:
```diff
- <span className="step-id">{step.id}</span>
+ <span className="step-ulid">{step.ulid}</span>
```

### Step 2.11: hooks/useQVClient.ts

**Line 382**:
```diff
- call('list_qe_ui_parameters', { module, step_type: stepType })
+ call('list_qe_ui_parameters', { module, step_type_gen: stepType })
```

### Step 2.12: PresetSection.tsx

**Lines 54-55**:
```diff
- dimension.scope.type === 'variant_step_types'
- dimension.scope.step_types
+ dimension.scope.type === 'variant_step_type_gens'
+ dimension.scope.step_type_gens
```

**Line 72**:
```diff
- v.step_types.forEach(st => stepTypesSet.add(st))
+ v.step_type_gens.forEach(st => stepTypesSet.add(st))
```

**Line 207**:
```diff
- {step.step_type}
+ {step.step_type_gen}
```

---

## Phase 3: Update Variable Names

Rename local variables that use legacy naming for clarity:

| Old Name | New Name | Files |
|----------|----------|-------|
| `stepId` | `stepUlid` | CalculationAnalysisPanel.tsx, ScanSummary.tsx |
| `selectedStepId` | `selectedStepUlid` | CalculationAnalysisPanel.tsx |
| `runId` | `runUlid` | CalculationAnalysisPanel.tsx, HistoryPanel.tsx |
| `latestRunId` | `latestRunUlid` | HistoryPanel.tsx |

---

## ~~Phase 4: Verify Backend Payload Compatibility~~ STRUCK

~~This phase previously suggested creating backend compat adapters.~~

**FORBIDDEN**: No backend adapters mapping new→old field names.

If backend RPC does not accept new field names in payloads, this is a backend bug requiring minimal fix to accept new fields - NOT a compat adapter.

---

## Phase 4: Testing Checklist

### Compile/Typecheck

- [ ] `npm run build` passes (TypeScript compilation)
- [ ] No type errors in IDE
- [ ] All imports resolve correctly

### Manual Verification

- [ ] Calculation list displays correctly
- [ ] Step detail panel loads and displays step type
- [ ] History panel shows run information
- [ ] Jobs panel shows job step types
- [ ] Analysis panel functions work
- [ ] Preset section renders step types
- [ ] Add step to calculation works
- [ ] Pin to history works

### E2E Tests (if available)

```bash
cd gui
npm run build:e2e
npm run test:e2e
```

---

## Phase 5: Documentation Updates

Update any user-facing or developer documentation that references the old field names:

- [ ] API documentation
- [ ] Type definition comments
- [ ] Component prop documentation
- [ ] README files

---

## Rollback Plan

If issues are discovered after deployment:

1. **Revert frontend changes** (git revert)
2. **Backend unchanged** (frozen per hard constraints)
3. **Investigate and fix** the specific issue
4. **Re-deploy** with fix

---

## Estimated Impact

### Files to Modify

| Category | Count |
|----------|-------|
| Type definitions | 1 file (qv.ts) |
| React components | 10 files |
| Hooks | 1 file |
| **Total** | 12 files |

### Field Renames

| From | To | Count |
|------|-----|-------|
| `step_type` | `step_type_gen` | ~15 |
| `type` | `step_type_gen` | ~8 |
| `step_id` | `step_ulid` | ~12 |
| `id` | `ulid` | ~8 |
| `run_id` | `run_ulid` | ~6 |
| `calc_id` | `calc_ulid` | ~3 |

---

## Implementation Order

1. **Phase 1** first (type definitions) - ensures type safety during refactor
2. **Phase 2** component by component - start with leaf components
3. **Phase 3** variable naming cleanup
4. **Phase 4** thorough testing
5. **Phase 5** documentation cleanup
