# M5: GUI Step Palette

## Scope

Replace hard-coded QE step dropdowns with backend-driven step palette from `list_step_palette` RPC. Add engine_family selector to CreateCalculationDialog.

## Prerequisites

M0-M4 must be complete. The `list_engine_families`, `list_step_palette`, and `set_engine_family` RPCs must be working.

## Exact File List

### Modify

1. `gui/src/components/panels/CalculationOverviewTab.tsx` — Replace hard-coded QE step dropdown (lines 453-461) with dynamic list from `list_step_palette` RPC
2. `gui/src/components/panels/CalculationListPanel.tsx` — Replace hard-coded QE step dropdown (lines 1345-1354) with dynamic list from `list_step_palette` RPC
3. `gui/src/components/dialogs/CreateCalculationDialog.tsx` — Add engine_family selector, pass engine_family in `create_calculation` payload
4. `gui/src/hooks/useQMSClient.ts` — Add `listEngineFamilies()` and `listStepPalette()` convenience methods
5. `gui/src/types/qms.ts` — Add `EngineFamilyInfo`, `StepPaletteResult`, and new RPC type entries

## Do NOT Touch

- `gui/src/components/panels/StepDetailPanel.tsx` (that's M6)
- `gui/src/components/panels/QEParameterBrowserPanel.tsx` (that's M7)
- `gui/src/hooks/useQEParameterMetadata.ts` (that's M7)
- `gui/src/components/panels/SettingsPanel.tsx` (that's M7)
- Any Python backend files (already done in M4)

## Exact Instructions

### Step 1: Add types to qms.ts

Add these interfaces after the existing `QEDetectionResult` interface (around line 405):

```typescript
// ─────────────────────────────────────────────────────────────────────
// Generic Engine Types (replaces QE-specific types)
// ─────────────────────────────────────────────────────────────────────

export interface EngineFamilyInfo {
  engine_family: string;
  display_name: string;
  engine_role: 'base' | 'postprocessing';
  companion_engines: string[];
  supported_gen_steps: string[];
}

export interface StepPaletteEntry {
  gen: string;
  spec: string;
  description: string;
}

export interface StepPaletteResult {
  base_steps: StepPaletteEntry[];
  companion_steps: Record<string, StepPaletteEntry[]>;
}
```

Add the RPC type entries to the `QMSCommandMap` interface (around line 490, after existing entries):

```typescript
  // Generic engine RPCs
  list_engine_families: {
    payload: Record<string, never>;
    result: { engines: EngineFamilyInfo[] };
  };
  list_step_palette: {
    payload: { engine_family: string | null };
    result: StepPaletteResult;
  };
  set_engine_family: {
    payload: { project_root: string; calculation: string; engine_family: string };
    result: { success: boolean; engine_family: string };
  };
```

### Step 2: Add convenience methods to useQMSClient.ts

Add these after the existing `listQeParameterMetadata` method (around line 58):

```typescript
  listEngineFamilies: () => Promise<QMSResponse<QMSResult<'list_engine_families'>>>;
  listStepPalette: (engineFamily: string | null) => Promise<QMSResponse<QMSResult<'list_step_palette'>>>;
  setEngineFamily: (projectRoot: string, calculation: string, engineFamily: string) => Promise<QMSResponse<QMSResult<'set_engine_family'>>>;
```

And implement them in the hook body:

```typescript
  listEngineFamilies: () => call('list_engine_families', {}),
  listStepPalette: (engineFamily) => call('list_step_palette', { engine_family: engineFamily }),
  setEngineFamily: (projectRoot, calculation, engineFamily) =>
    call('set_engine_family', { project_root: projectRoot, calculation, engine_family: engineFamily }),
```

### Step 3: Replace CalculationOverviewTab.tsx dropdown

Find the hard-coded step dropdown (lines 448-461):

```tsx
<select value={newStepType} onChange={(e) => setNewStepType(e.target.value)} ...>
  <option value="">Select step type...</option>
  <option value="scf">SCF</option>
  <option value="nscf">NSCF</option>
  <option value="relax">Relax</option>
  <option value="vc-relax">VC-Relax</option>
  <option value="bands_pw">Bands (PW)</option>
  <option value="bands">Bands</option>
  <option value="dos">DOS</option>
</select>
```

Replace with a dynamic dropdown that fetches from `list_step_palette`:

1. Add state for palette data:
```typescript
const [stepPalette, setStepPalette] = useState<StepPaletteResult | null>(null);
```

2. Add effect to fetch palette when the calculation's engine_family is known:
```typescript
useEffect(() => {
  // engine_family comes from the calculation data (loaded from calculation.yaml)
  const engineFamily = calculationDetail?.engine_family ?? null;
  qms.listStepPalette(engineFamily).then((res) => {
    if (res.ok && res.data) {
      setStepPalette(res.data);
    }
  });
}, [calculationDetail?.engine_family]);
```

3. Replace the static `<option>` elements:
```tsx
<select value={newStepType} onChange={(e) => setNewStepType(e.target.value)} ...>
  <option value="">Select step type...</option>
  {stepPalette?.base_steps.map((step) => (
    <option key={step.gen} value={step.gen}>
      {step.description || step.gen.toUpperCase()}
    </option>
  ))}
  {stepPalette && Object.entries(stepPalette.companion_steps).map(([engine, steps]) => (
    <optgroup key={engine} label={engine.toUpperCase()}>
      {steps.map((step) => (
        <option key={step.gen} value={step.gen}>
          {step.description || step.gen}
        </option>
      ))}
    </optgroup>
  ))}
</select>
```

### Step 4: Replace CalculationListPanel.tsx dropdown

Find the hard-coded dropdown (lines 1338-1355):

```tsx
<select id="step-type" value={newStepType} ...>
  <option value="">-- Select Type --</option>
  <option value="scf">SCF (pw.x)</option>
  <option value="nscf">NSCF (pw.x)</option>
  ...
</select>
```

Apply the exact same pattern as Step 3: fetch from `list_step_palette`, render dynamically.

### Step 5: Update CreateCalculationDialog.tsx

Add an engine_family selector to the dialog:

1. Add state:
```typescript
const [engineFamilies, setEngineFamilies] = useState<EngineFamilyInfo[]>([]);
const [selectedEngine, setSelectedEngine] = useState<string>('');
```

2. Fetch engine families on mount:
```typescript
useEffect(() => {
  qms.listEngineFamilies().then((res) => {
    if (res.ok && res.data) {
      // Filter to base engines only (postprocessing engines can't be selected as engine_family)
      const baseEngines = res.data.engines.filter(e => e.engine_role === 'base');
      setEngineFamilies(baseEngines);
    }
  });
}, []);
```

3. Add the selector UI (before the template/workflow selectors):
```tsx
<div className="form-group">
  <label htmlFor="engine-family">Engine</label>
  <select
    id="engine-family"
    value={selectedEngine}
    onChange={(e) => setSelectedEngine(e.target.value)}
  >
    <option value="">Decide later</option>
    {engineFamilies.map((eng) => (
      <option key={eng.engine_family} value={eng.engine_family}>
        {eng.display_name}
      </option>
    ))}
  </select>
</div>
```

4. Pass engine_family in the create_calculation payload (around line 96):
```typescript
const response = await qms.call('create_calculation', {
  project_root: projectRoot,
  name: calculationName,
  structure: selectedStructure || undefined,
  template: selectedWorkflow ? undefined : (selectedTemplate || undefined),
  engine_family: selectedEngine || undefined,  // null = UNDECIDED
});
```

## Invariants to Preserve

- Existing QE types (`QEDetectionResult`, etc.) still exist in qms.ts (deleted in M8)
- Existing QE RPC methods (`listQeUiParameters`, etc.) still exist in useQMSClient.ts (deleted in M8)
- The `step_type_gen` value sent to `add_step_to_calculation` RPC remains the same format (lowercase gen step name, e.g., "scf")
- The `create_calculation` RPC accepts `engine_family: null` for UNDECIDED state
- The dropdown shows step labels, not raw spec types
- Companion steps are visually separated from base steps (using `<optgroup>`)

## Verifiers

```bash
# 1. No hard-coded QE step lists in the two panels
grep -c "qe_scf\|qe_nscf\|qe_relax\|qe_bands\|SCF (pw.x)\|NSCF (pw.x)\|Relax (pw.x)" gui/src/components/panels/CalculationOverviewTab.tsx
# Expected: 0

grep -c "qe_scf\|qe_nscf\|qe_relax\|qe_bands\|SCF (pw.x)\|NSCF (pw.x)\|Relax (pw.x)" gui/src/components/panels/CalculationListPanel.tsx
# Expected: 0

# 2. Engine selector exists in CreateCalculationDialog
grep -c "engine_family\|engine-family\|selectedEngine\|listEngineFamilies" gui/src/components/dialogs/CreateCalculationDialog.tsx
# Expected: > 0

# 3. New types exist
grep -c "EngineFamilyInfo\|StepPaletteResult\|StepPaletteEntry" gui/src/types/qms.ts
# Expected: > 0

# 4. New convenience methods exist
grep -c "listEngineFamilies\|listStepPalette\|setEngineFamily" gui/src/hooks/useQMSClient.ts
# Expected: > 0

# 5. Backend tests still pass
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT remove QE-specific types from qms.ts (that's M8)
- Do NOT remove QE RPC methods from useQMSClient.ts (that's M8)
- Do NOT modify StepDetailPanel.tsx (that's M6)
- Do NOT modify QEParameterBrowserPanel.tsx (that's M7)
- Do NOT modify SettingsPanel.tsx (that's M7)
- Do NOT modify Python backend files
- Do NOT hard-code new engine lists in the dropdown (use the RPC)
- Do NOT default selectedEngine to "qe" (use empty string for UNDECIDED)
- Do NOT remove the "Decide later" option from the engine selector

## Expected Failure Modes

1. **Forgetting to import new types**: `EngineFamilyInfo`, `StepPaletteResult`, `StepPaletteEntry` must be imported in files that use them.
2. **Engine dropdown defaulting to "qe"**: The initial state must be `''` (empty) representing UNDECIDED, not `'qe'`.
3. **Step palette not refreshing on engine change**: The useEffect dependency must include `engine_family` so the palette updates when the user changes the engine.
4. **Breaking the add-step flow**: The `handleAddStep` function sends `newStepType` (a gen step name) to `add_step_to_calculation`. This gen name must still be the same format.
5. **TypeScript compilation errors**: New types must be exported and imported correctly. Check `tsc --noEmit` after changes.
6. **Calculation data not including engine_family**: The calculation detail object from the backend must include `engine_family` in its response. Verify that `_handle_get_calculation_detail` returns this field.
