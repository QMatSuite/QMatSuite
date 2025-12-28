# Common Cards Contract

## Architecture Rule: UI Never Parses QE Raw Text

This document defines the contract for implementing Common Card editors (K_POINTS, PSEUDO, etc.) in the QuantumVITAS GUI.

## Core Principles

### 1. YAML Storage is Raw QE Text Only

- **Cards are stored as raw QE text** (string or list-of-lines) in `step.yaml`
- **No type tagging** in YAML (e.g., no `{type: "automatic", data: {...}}`)
- **String-only storage rule** applies: all card data is stored as strings

### 2. Python Service Owns Parsing/Formatting

The Python `qvservice/daemon` is responsible for:

- **Parsing**: Raw card text → structured view model
- **Validating**: Soft warnings (non-blocking), not hard errors
- **Formatting**: Structured view model → raw text (round-trip stable)

### 3. UI is Presentation-Only

The UI is **dumb**:

- **Renders** view model from backend
- **Sends** view model edits back to backend
- **Never parses** raw QE text in TypeScript/React
- **Never formats** structured data to raw text in UI

## Implementation Pattern

### Backend RPCs

```typescript
// Get view model for common cards
get_common_cards(step_id: string) -> {
  k_points?: {
    raw: string;              // Original raw QE text
    mode: string;             // "gamma" | "automatic" | "tpiba" | "crystal" | ...
    automatic?: {              // Present if mode === "automatic"
      nk1: number;
      nk2: number;
      nk3: number;
      sk1: number;
      sk2: number;
      sk3: number;
    };
    points?: Array<{          // Present if mode is list-based (tpiba, crystal, etc.)
      x: number;
      y: number;
      z: number;
      w: number;
    }>;
    warnings?: string[];      // Non-blocking validation warnings
  };
  // ... other cards
}

// Set common card from view model
set_common_card(
  step_id: string,
  card_name: "K_POINTS" | "PSEUDO" | ...,
  payload: ViewModel
) -> {
  // Backend:
  // 1. Validates view model (soft warnings)
  // 2. Formats view model → canonical raw QE text
  // 3. Writes YAML as string (no type tagging)
  // 4. Returns updated step detail
}
```

### UI Component Pattern

```typescript
// Component receives view model from backend
function CommonCardKPoints({ viewModel, onUpdate }) {
  // Render view model (never parse raw)
  const [localViewModel, setLocalViewModel] = useState(viewModel);
  
  // User edits update local view model
  const handleModeChange = (mode: string) => {
    setLocalViewModel({ ...localViewModel, mode });
  };
  
  // On Apply, send view model back
  const handleApply = () => {
    onUpdate(localViewModel); // Calls set_common_card RPC
  };
  
  // Show warnings inline (non-blocking)
  return (
    <div>
      {viewModel.warnings?.map(w => <Warning key={w}>{w}</Warning>)}
      {/* Render form based on mode */}
    </div>
  );
}
```

## Round-Trip Rules

### Preservation of Original Formatting

- **If user never touches card**: Keep original raw formatting exactly as imported
- **Once user edits in structured UI**: Write canonical formatting (stable, deterministic)

### Canonical Formatting

Backend must produce **stable, deterministic** formatting:

- Same view model → same raw text (always)
- No random whitespace or formatting variations
- Consistent with QE conventions (e.g., automatic mode: `K_POINTS automatic\n8 8 8 0 0 0`)

## Validation Strategy

### Soft Warnings (Non-Blocking)

- **Display inline** in UI (e.g., "sk* must be 0/1", "nks mismatch")
- **Never block** Apply button
- **Backend may return warnings** but still write YAML

### Hard Errors (Rare)

- Only for **completely invalid** data (e.g., missing required fields)
- Should be **rare** - most issues are warnings

## Examples

### K_POINTS Automatic Mode

**YAML (raw)**:
```yaml
cards:
  K_POINTS: "automatic\n8 8 8 0 0 0"
```

**View Model**:
```json
{
  "raw": "automatic\n8 8 8 0 0 0",
  "mode": "automatic",
  "automatic": {
    "nk1": 8,
    "nk2": 8,
    "nk3": 8,
    "sk1": 0,
    "sk2": 0,
    "sk3": 0
  }
}
```

**User edits nk1 to 10** → View model updates → Backend formats → YAML becomes:
```yaml
cards:
  K_POINTS: "automatic\n10 8 8 0 0 0"
```

### PSEUDO Card (Pseudopotentials)

**Note**: Pseudopotentials are stored in `calculation.species_map` (calculation-level), not in step YAML. The UI provides a structured editor for per-element mapping at the calculation level.

**YAML (calculation.yaml)**:
```yaml
species_map:
  Si:
    pseudopot: "Si.pbe-n-rrkjus_psl.1.0.0.UPF"
    mass: 28.0855
  Mo:
    pseudopot: "Mo.pbe-spn-rrkjus_psl.1.0.0.UPF"
    mass: 95.95
```

**Legacy Note**: Old projects may have `species_overrides` in step YAML files. These are migrated to `calculation.species_map` on load, and step-level `species_overrides` is considered legacy.

**View Model** (from `get_calculation_pseudo_mapping`):
```json
{
  "species": ["Si", "Mo"],
  "mapping": {
    "Si": "Si.pbe-n-rrkjus_psl.1.0.0.UPF",
    "Mo": "Mo.pbe-spn-rrkjus_psl.1.0.0.UPF"
  },
  "pseudo_dir": "../pseudo",
  "available_pseudos": ["Si.pbe-n-rrkjus_psl.1.0.0.UPF", "Mo.pbe-spn-rrkjus_psl.1.0.0.UPF"],
  "warnings": [],
  "library_preference": "precision",
  "sssp_defaults": {
    "Si": {"precision": "Si.pbe-n-kjpaw_psl.1.0.0.UPF", "efficiency": "Si.pbe-n-kjpaw_psl.1.0.0.UPF"},
    "Mo": {"precision": "Mo.pbe-spn-rrkjus_psl.1.0.0.UPF", "efficiency": "Mo.pbe-spn-rrkjus_psl.1.0.0.UPF"}
  },
  "sssp_installed": {"precision": true, "efficiency": true}
}
```

**Key Design Decisions**:
- `pseudo_dir` is **NOT editable** in UI (runtime always uses `../pseudo` relative to calculation's raw/)
- **Pseudo directory location**:
  - **Project mode**: `project_root/pseudo/` (shared across all calculations in the project)
  - **Standalone mode**: `working_dir/pseudo/` (isolated per execution, used in tests)
- Per-element mapping is the canonical source of truth (`calculation.species_map`)
- Pseudopotentials are stored at **calculation level**, not step level (all steps in a calculation share the same pseudo mapping)
- Element list comes from the calculation's structure (`structure_id` → structure composition)
- SSSP defaults are auto-preselected but only committed on Apply (no silent side effects)
- Online resolve downloads individual UPF files into `project/pseudo/` for self-containment
- SHA256 deduplication prevents duplicate files
- Deterministic renaming (`_1`, `_2`) resolves filename conflicts
- `ESPRESSO_PSEUDO` environment variable is set to the absolute path of the pseudo directory during execution

**Online Resolve Features**:
- **Download by filename**: Direct download from QE repository
- **Search by element**: Browse QE legacy tables for available pseudopotentials
- Both modes download to `project/pseudo/` and update available options

### K_POINTS Crystal Mode

**YAML (raw)**:
```yaml
cards:
  K_POINTS: "crystal\n4\n0.0 0.0 0.0 0.25\n0.5 0.0 0.0 0.25\n0.0 0.5 0.0 0.25\n0.5 0.5 0.0 0.25"
```

**View Model**:
```json
{
  "raw": "crystal\n4\n...",
  "mode": "crystal",
  "points": [
    {"x": 0.0, "y": 0.0, "z": 0.0, "w": 0.25},
    {"x": 0.5, "y": 0.0, "z": 0.0, "w": 0.25},
    {"x": 0.0, "y": 0.5, "z": 0.0, "w": 0.25},
    {"x": 0.5, "y": 0.5, "z": 0.0, "w": 0.25}
  ]
}
```

## Preventing UI Parsing Creep

### ❌ BAD: UI Parses Raw Text

```typescript
// DON'T DO THIS
const parseKPoints = (raw: string) => {
  const lines = raw.split('\n');
  const mode = lines[0];
  // ... parsing logic in UI
};
```

### ✅ GOOD: UI Uses View Model

```typescript
// DO THIS
const viewModel = await getCommonCards(stepId);
// Use viewModel.k_points.mode, viewModel.k_points.automatic, etc.
```

## Testing Requirements

### Round-Trip Tests

For each card type, test:

1. **Import QE input** → View model is correct
2. **Edit view model** → YAML raw text updates correctly
3. **Switch modes** → Raw text rewrites appropriately
4. **Canonical formatting** → Same view model always produces same raw text

### Edge Cases

- Unsupported modes (e.g., `crystal_b`) → View model has `mode: "custom"` with `raw` passthrough
- Parse errors → View model has `mode: "custom"` with warnings
- Empty/invalid → View model has appropriate defaults or errors

