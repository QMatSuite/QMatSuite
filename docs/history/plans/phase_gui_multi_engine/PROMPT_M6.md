# M6: GUI Parameter Editor

## Scope

Replace QE-specific parameter editing in StepDetailPanel with generic `list_engine_ui_parameters` RPC. Delete `stepTypeToModule()` and `LEGACY_EDITABLE_PARAMS`.

## Prerequisites

M0-M5 must be complete. The `list_engine_ui_parameters` RPC must be working (from M4).

## Exact File List

### Modify

1. `gui/src/components/panels/StepDetailPanel.tsx` — Remove `stepTypeToModule()` (lines 52-73), remove `LEGACY_EDITABLE_PARAMS` (lines 76-121), replace with generic RPC call
2. `gui/src/hooks/useQMSClient.ts` — Add `listEngineUiParameters()` convenience method
3. `gui/src/types/qms.ts` — Add `EngineUIParameter` type and `list_engine_ui_parameters` RPC entry

## Do NOT Touch

- `gui/src/components/panels/QEParameterBrowserPanel.tsx` (that's M7)
- `gui/src/hooks/useQEParameterMetadata.ts` (that's M7)
- `gui/src/components/panels/SettingsPanel.tsx` (that's M7)
- Any Python backend files (already done in M4)
- `gui/src/components/panels/CalculationOverviewTab.tsx` (already done in M5)
- `gui/src/components/panels/CalculationListPanel.tsx` (already done in M5)
- `gui/src/components/dialogs/CreateCalculationDialog.tsx` (already done in M5)

## Exact Instructions

### Step 1: Add types to qms.ts

Add the `EngineUIParameter` interface (near the other engine types added in M5):

```typescript
export interface EngineUIParameter {
  key: string;
  label: string;
  type: string;        // "number", "select", "bool", "text"
  section?: string;     // e.g., "SYSTEM", "ELECTRONS" for QE; "general" for others
  unit?: string;
  description?: string;
  options?: string[];
  importance?: string;
  default?: any;
}
```

Add the RPC entry to `QMSCommandMap`:

```typescript
  list_engine_ui_parameters: {
    payload: { engine_family: string; step_type_gen: string };
    result: { parameters: EngineUIParameter[] };
  };
```

### Step 2: Add convenience method to useQMSClient.ts

Add after the M5 convenience methods:

```typescript
  listEngineUiParameters: (
    engineFamily: string,
    stepTypeGen: string
  ) => Promise<QMSResponse<QMSResult<'list_engine_ui_parameters'>>>;
```

Implementation:

```typescript
  listEngineUiParameters: (engineFamily, stepTypeGen) =>
    call('list_engine_ui_parameters', { engine_family: engineFamily, step_type_gen: stepTypeGen }),
```

### Step 3: Modify StepDetailPanel.tsx

**3a. Delete `stepTypeToModule()` function (lines 52-73)**

Remove the entire function. It mapped QE step types to QE modules — this is now done server-side by the `list_engine_ui_parameters` RPC handler.

**3b. Delete `LEGACY_EDITABLE_PARAMS` constant (lines 76-121)**

Remove the entire constant. This was a QE-specific fallback — the generic RPC provides parameters for all engines.

**3c. Update parameter loading logic**

Find the place where the component calls `listQeUiParameters(module, stepType)` to get parameters. This is likely in a useEffect or data-fetching block. Replace it with:

```typescript
// OLD:
// const module = stepTypeToModule(stepTypeGen);
// if (module) {
//   const res = await qms.listQeUiParameters(module, stepTypeGen);
//   ...
// } else {
//   // Use LEGACY_EDITABLE_PARAMS fallback
// }

// NEW:
const engineFamily = calculationDetail?.engine_family;
if (engineFamily && stepTypeGen) {
  const res = await qms.listEngineUiParameters(engineFamily, stepTypeGen);
  if (res.ok && res.data) {
    setUiParameters(res.data.parameters);
  } else {
    setUiParameters([]);  // No metadata available for this engine/step
  }
}
```

The `engine_family` must come from the calculation data (loaded from calculation.yaml), which should be available in the component's props or parent state.

**3d. Update parameter rendering**

If the component currently renders parameters using QE-specific field names (like `param.namelist`), update to use the generic field names from `EngineUIParameter`:

- `param.namelist` → `param.section`
- `param.name` → `param.key`
- Other fields (`label`, `type`, `unit`, `description`, `options`) have the same names

**3e. Handle managed keys generically**

Find any code that checks for QE-specific managed keys (like `CONTROL.prefix`, `CONTROL.outdir`, `CONTROL.pseudo_dir`). Replace with a generic check:

```typescript
// OLD:
// const isManagedKey = (namelist === 'CONTROL' && ['prefix', 'outdir', 'pseudo_dir'].includes(key));

// NEW:
// Managed keys are now indicated by the backend response
// The list_engine_ui_parameters RPC filters them out or marks them
// OR: Keep a minimal check if the backend doesn't handle this yet
```

**3f. Handle empty parameters gracefully**

If `list_engine_ui_parameters` returns empty `parameters` for an engine, show a fallback message:

```tsx
{uiParameters.length === 0 && (
  <div className="step-detail__no-params">
    <p>No guided parameters available for this engine/step type.</p>
    <p>Use the raw parameter editor below to edit parameters directly.</p>
  </div>
)}
```

The raw parameter editor (JSON/YAML direct edit) should always be available regardless of whether guided parameters exist.

### Step 4: Ensure engine_family is available in StepDetailPanel

Check if `StepDetailPanel` receives `engine_family` through its props or can access it from the calculation data. If not, you may need to:

1. Add `engineFamily?: string` to the component's props interface
2. Pass it from the parent component (CalculationOverviewTab or wherever StepDetailPanel is rendered)

Look at the existing prop interface (around line 40-46):
```typescript
interface StepDetailPanelProps {
  projectRoot: string;
  selectedCalculation: string;
  selectedStepId: string;
  calculationName?: string;
  // ... other props
}
```

If `engine_family` is not there, add it and thread it through from the parent.

## Invariants to Preserve

- The raw parameter editor (direct JSON/YAML editing) still works for ALL engines
- QE parameter editing still works (the generic RPC returns QE parameters when engine_family="qe")
- The K_POINTS card rendering is NOT changed in this milestone (it's a separate concern)
- Existing QE RPC methods (`listQeUiParameters`) still exist in useQMSClient.ts (deleted in M8)
- The component gracefully handles engines with no UI parameter metadata

## Verifiers

```bash
# 1. stepTypeToModule is gone
grep -c "stepTypeToModule" gui/src/components/panels/StepDetailPanel.tsx
# Expected: 0

# 2. LEGACY_EDITABLE_PARAMS is gone
grep -c "LEGACY_EDITABLE_PARAMS" gui/src/components/panels/StepDetailPanel.tsx
# Expected: 0

# 3. Generic RPC is used
grep -c "listEngineUiParameters\|list_engine_ui_parameters" gui/src/components/panels/StepDetailPanel.tsx
# Expected: > 0

# 4. No direct QE module references
grep -c "listQeUiParameters" gui/src/components/panels/StepDetailPanel.tsx
# Expected: 0

# 5. Backend tests still pass
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT remove `listQeUiParameters` from useQMSClient.ts (that's M8)
- Do NOT modify QEParameterBrowserPanel.tsx (that's M7)
- Do NOT modify Python backend files
- Do NOT change the raw parameter editor (it should remain engine-agnostic)
- Do NOT remove K_POINTS card handling (it's a separate UI element)
- Do NOT hard-code parameter lists for non-QE engines in the TypeScript code
- Do NOT add engine-specific rendering logic (if VASP, show X; if ORCA, show Y) — use the generic `EngineUIParameter` type for all

## Expected Failure Modes

1. **Missing `engine_family` prop**: StepDetailPanel may not have access to the calculation's engine_family. It needs to be threaded through props from the parent component.
2. **Breaking QE parameter display**: If the generic RPC returns a different response shape than the QE-specific one, parameter rendering may break. Verify the response shape matches `EngineUIParameter`.
3. **Empty parameters for non-QE engines**: If the user selects a VASP step, the RPC may return an empty list. The UI must gracefully show a "no guided parameters" message.
4. **Section/namelist mismatch**: QE uses `namelist` (e.g., "&SYSTEM"), while other engines use `section` or `category`. The generic type uses `section` — ensure the RPC normalizes this.
5. **TypeScript compilation**: Removing `stepTypeToModule` and `LEGACY_EDITABLE_PARAMS` may break references. Search for all usages before deleting.
