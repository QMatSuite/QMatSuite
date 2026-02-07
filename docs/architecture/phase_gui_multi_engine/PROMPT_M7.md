# M7: GUI Parameter Browser + Settings

## Scope

Rename `QEParameterBrowserPanel` to `EngineParameterBrowserPanel` (engine-agnostic). Rename `useQEParameterMetadata` hook. Generalize the Settings panel to show all engines, not just QE.

## Prerequisites

M0-M6 must be complete. The `list_engine_parameter_metadata` and `list_engine_families` RPCs must be working.

## Exact File List

### Rename

1. `gui/src/components/panels/QEParameterBrowserPanel.tsx` → `gui/src/components/panels/EngineParameterBrowserPanel.tsx`
2. `gui/src/hooks/useQEParameterMetadata.ts` → `gui/src/hooks/useEngineParameterMetadata.ts`

### Modify

3. `gui/src/components/panels/EngineParameterBrowserPanel.tsx` (the renamed file) — Accept `engineFamily` prop, replace QE-specific RPC calls
4. `gui/src/hooks/useEngineParameterMetadata.ts` (the renamed file) — Accept `engineFamily` parameter, replace QE-specific RPC calls
5. `gui/src/components/panels/SettingsPanel.tsx` — Generalize QE section (lines 300-349) to show all engines
6. `gui/src/hooks/useQVClient.ts` — Add `listEngineParameterMetadata()` convenience method
7. `gui/src/types/qv.ts` — Add `list_engine_parameter_metadata` RPC entry
8. Any files that import `QEParameterBrowserPanel` or `useQEParameterMetadata` — Update imports

## Do NOT Touch

- Any Python backend files (already done in M4)
- `gui/src/components/panels/StepDetailPanel.tsx` (already done in M6)
- `gui/src/components/panels/CalculationOverviewTab.tsx` (already done in M5)
- `gui/src/components/panels/CalculationListPanel.tsx` (already done in M5)
- `gui/src/components/dialogs/CreateCalculationDialog.tsx` (already done in M5)

## Exact Instructions

### Step 1: Find all imports of the old names

Before renaming, find every file that imports the old names:

```bash
grep -rn "QEParameterBrowserPanel\|useQEParameterMetadata" gui/src/ --include="*.tsx" --include="*.ts"
```

Record all files that need import updates.

### Step 2: Rename QEParameterBrowserPanel.tsx

Rename the file:
```bash
mv gui/src/components/panels/QEParameterBrowserPanel.tsx gui/src/components/panels/EngineParameterBrowserPanel.tsx
```

In the renamed file:

**2a. Rename the component**

Find: `export function QEParameterBrowserPanel(` or `export default function QEParameterBrowserPanel(`
Replace with: `export function EngineParameterBrowserPanel(`

**2b. Add `engineFamily` prop**

Add to the component's props interface:

```typescript
interface EngineParameterBrowserPanelProps {
  engineFamily: string;  // NEW: which engine to browse
  projectRoot?: string;
  // ... existing props
}
```

**2c. Replace QE-specific RPC calls**

Find all calls to `listQeParameterMetadata` and replace with `listEngineParameterMetadata`:

```typescript
// OLD:
// const res = await qv.listQeParameterMetadata('list_modules');
// const res = await qv.listQeParameterMetadata('list_sections', { module: selectedModule });
// const res = await qv.listQeParameterMetadata('list_parameters', { module, section });
// const res = await qv.listQeParameterMetadata('search', { query: searchQuery });

// NEW:
const res = await qv.listEngineParameterMetadata(engineFamily, 'list_categories');
const res = await qv.listEngineParameterMetadata(engineFamily, 'list_tags', { category: selectedCategory });
const res = await qv.listEngineParameterMetadata(engineFamily, 'search', { query: searchQuery });
```

Note the operation name changes:
- `list_modules` → `list_categories` (generic term)
- `list_sections` → also use `list_tags` with category filter
- `list_parameters` → `list_tags`
- `search` → `search` (unchanged)

**2d. Update UI labels**

Replace any hard-coded "QE" or "Quantum ESPRESSO" labels:

```typescript
// OLD: "QE Parameter Browser"
// NEW: use display_name from the engine info, or generic "Parameter Browser"

// OLD: "QE Module"
// NEW: "Category"

// OLD: "Namelist"
// NEW: "Section"
```

**2e. Handle the response shape difference**

The generic RPC returns `categories` instead of `modules`, `tags` instead of `parameters`. Update the state variable names and rendering logic accordingly.

### Step 3: Rename useQEParameterMetadata.ts

Rename the file:
```bash
mv gui/src/hooks/useQEParameterMetadata.ts gui/src/hooks/useEngineParameterMetadata.ts
```

In the renamed file:

**3a. Rename the hook**

```typescript
// OLD: export function useQEParameterMetadata(...)
// NEW: export function useEngineParameterMetadata(engineFamily: string, ...)
```

**3b. Thread `engineFamily` through all RPC calls**

Every call to `listQeParameterMetadata` becomes `listEngineParameterMetadata(engineFamily, ...)`.

**3c. Update return type names if needed**

Rename any internal types that have "QE" in the name to generic equivalents.

### Step 4: Add RPC type and convenience method

In `gui/src/types/qv.ts`, add:

```typescript
  list_engine_parameter_metadata: {
    payload: {
      engine_family: string;
      operation: 'list_categories' | 'list_tags' | 'search';
      category?: string;
      section?: string;
      query?: string;
    };
    result: {
      categories?: Array<{ id: string; label: string }>;
      tags?: Array<{ name: string; type: string; default: any; description: string; category: string }>;
      results?: Array<{ name: string; type: string; default: any; description: string; category: string }>;
    };
  };
```

In `gui/src/hooks/useQVClient.ts`, add:

```typescript
  listEngineParameterMetadata: (
    engineFamily: string,
    operation: 'list_categories' | 'list_tags' | 'search',
    params?: { category?: string; section?: string; query?: string }
  ) => Promise<QVResponse<QVResult<'list_engine_parameter_metadata'>>>;
```

Implementation:

```typescript
  listEngineParameterMetadata: (engineFamily, operation, params) =>
    call('list_engine_parameter_metadata', { engine_family: engineFamily, operation, ...params }),
```

### Step 5: Update all import sites

For every file found in Step 1, update imports:

```typescript
// OLD:
// import { QEParameterBrowserPanel } from './panels/QEParameterBrowserPanel';
// import { useQEParameterMetadata } from '../hooks/useQEParameterMetadata';

// NEW:
import { EngineParameterBrowserPanel } from './panels/EngineParameterBrowserPanel';
import { useEngineParameterMetadata } from '../hooks/useEngineParameterMetadata';
```

Update component usage:

```tsx
// OLD: <QEParameterBrowserPanel ... />
// NEW: <EngineParameterBrowserPanel engineFamily={engineFamily} ... />
```

The `engineFamily` must come from the current calculation's data or from user selection in the UI.

### Step 6: Generalize SettingsPanel.tsx

Find the hard-coded "Quantum ESPRESSO" section (lines 300-349).

**6a. Add engine list state**

```typescript
const [engineFamilies, setEngineFamilies] = useState<EngineFamilyInfo[]>([]);

useEffect(() => {
  qv.listEngineFamilies().then((res) => {
    if (res.ok && res.data) {
      setEngineFamilies(res.data.engines.filter(e => e.engine_role === 'base'));
    }
  });
}, []);
```

**6b. Replace single QE section with engine loop**

```tsx
{/* Engine Detection Sections */}
{engineFamilies.map((engine) => (
  <div key={engine.engine_family} className="settings-section">
    <div className="settings-section__header">
      <h3 className="settings-section__title">
        <span className="settings-icon">⚛️</span>
        {engine.display_name}
      </h3>
      {/* For QE, keep the existing re-detect button */}
      {engine.engine_family === 'qe' && (
        <button
          className="settings-btn settings-btn--sm"
          onClick={handleRedetectQE}
          disabled={isDetecting}
        >
          {isDetecting ? 'Detecting...' : 'Re-detect'}
        </button>
      )}
    </div>
    <div className="settings-section__content">
      {engine.engine_family === 'qe' ? (
        /* Keep existing QE detection display */
        <QEDetectionDisplay qeInfo={qeInfo} />
      ) : (
        /* Generic engine status */
        <div className="engine-status">
          <p>Supported gen steps: {engine.supported_gen_steps.join(', ')}</p>
          {engine.companion_engines.length > 0 && (
            <p>Companion engines: {engine.companion_engines.join(', ')}</p>
          )}
        </div>
      )}
    </div>
  </div>
))}
```

**NOTE**: The QE-specific detection UI can remain functional for now (detect_qe RPC still exists). For other engines, show a simple status display. Full engine detection for all engines is a future task beyond this plan.

## Invariants to Preserve

- The old file paths (`QEParameterBrowserPanel.tsx`, `useQEParameterMetadata.ts`) must NOT exist after rename
- No file should import the old names
- QE parameter browsing still works (the generic RPC delegates to QE metadata for engine_family="qe")
- The Settings panel still shows QE detection status (detect_qe RPC still exists until M8)
- Old QE convenience methods still exist in useQVClient.ts (deleted in M8)

## Verifiers

```bash
# 1. Old files are gone
ls gui/src/components/panels/QEParameterBrowserPanel.tsx 2>&1 | grep "No such file"
# Expected: file not found

ls gui/src/hooks/useQEParameterMetadata.ts 2>&1 | grep "No such file"
# Expected: file not found

# 2. New files exist
ls gui/src/components/panels/EngineParameterBrowserPanel.tsx
ls gui/src/hooks/useEngineParameterMetadata.ts

# 3. No references to old names
grep -rn "QEParameterBrowserPanel\|QEParameterBrowser" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: 0 matches

grep -rn "useQEParameterMetadata" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: 0 matches

# 4. New names are used
grep -rn "EngineParameterBrowserPanel" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: > 0

grep -rn "useEngineParameterMetadata" gui/src/ --include="*.tsx" --include="*.ts"
# Expected: > 0

# 5. Backend tests still pass
source .venv/bin/activate && python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

## Do NOT Do

- Do NOT delete the old QE RPC handlers from server.py (that's M8)
- Do NOT delete `listQeUiParameters` or `listQeParameterMetadata` from useQVClient.ts (that's M8)
- Do NOT delete `QEDetectionResult` from qv.ts (that's M8)
- Do NOT modify Python backend files
- Do NOT create engine-specific parameter browser panels (one generic panel handles all engines)
- Do NOT break the QE parameter browser (it must still work via the generic abstraction)
- Do NOT add engine detection RPCs for non-QE engines (that's a future task)

## Expected Failure Modes

1. **Missing import updates**: A file that imports `QEParameterBrowserPanel` or `useQEParameterMetadata` was not updated. Use grep to find ALL references before and after.
2. **Response shape mismatch**: The generic RPC returns `categories` but the component expects `modules`. All variable names and rendering logic must be updated.
3. **Missing `engineFamily` prop**: The renamed component requires `engineFamily` but a parent doesn't pass it. Thread it through from the calculation data.
4. **TypeScript compilation errors**: Renamed types, interfaces, and functions must be consistently updated across all files.
5. **Settings panel breaking**: If the engine loop doesn't properly handle the QE case (which has special detection UI), the QE section may regress.
