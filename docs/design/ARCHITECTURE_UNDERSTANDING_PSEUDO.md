# Architecture Understanding: Pseudopotential Management

## Summary

This document explains the current pseudopotential architecture before refactoring the UI to move pseudopotentials from step-level to calculation-level.

## Where Pseudo State Lives

### 1. Calculation-Level (Authoritative Source)
- **Location**: `calculation.yaml` → `species_map` field
- **Format**: `{ element: { pseudopot: string, mass?: number } }`
- **RPC**: `get_calculation_pseudo_mapping`, `update_calculation_species_map`
- **Purpose**: Single source of truth for all steps in a calculation

### 2. Step-Level (Legacy/Override)
- **Location**: `step.yaml` → `species_overrides` field
- **Format**: `{ element: { pseudopot: string, mass?: number } }`
- **RPC**: `get_pseudo_mapping`, `set_pseudo_mapping` (legacy)
- **Purpose**: Can override calculation-level, but calculation-level takes precedence

### 3. Filesystem
- **Location**: `project/pseudo/` directory
- **Contents**: Actual `.UPF` files
- **Purpose**: Self-contained project (all pseudos must exist here for runs)

## How State is Shared Across Steps

1. **Calculation-level `species_map` is authoritative**: All steps in a calculation inherit from `calculation.yaml`'s `species_map`
2. **Step-level `species_overrides` can override**: Steps can have per-step overrides, but these are secondary
3. **Runtime resolution**: When generating QE input, the runtime:
   - First checks calculation-level `species_map`
   - Then checks step-level `species_overrides` (if present)
   - Falls back to structure defaults if neither is set

## RPCs Involved

### Calculation-Level (Preferred)
- `get_calculation_pseudo_mapping(project_root, calculation_selector)`
  - Returns: `{ species, mapping, species_map, available_pseudos, pseudo_dir, warnings, sssp_defaults, sssp_installed }`
  - Source: `calculation.yaml` → `species_map`
  
- `update_calculation_species_map(project_root, calculation_selector, species_map)`
  - Updates: `calculation.yaml` → `species_map`
  - Returns: Updated calculation detail

### Step-Level (Legacy - Should Not Use for New Code)
- `get_pseudo_mapping(project_root, calculation_selector, step_selector)`
  - Returns step-level mapping (includes step overrides)
  - **Note**: Currently used in `StepDetailPanel`, but should use calculation-level instead

- `set_pseudo_mapping(project_root, calculation_selector, step_selector, mapping)`
  - Updates step-level `species_overrides`
  - **Note**: Currently used in `StepDetailPanel`, but should use calculation-level instead

## Why `../pseudo` is Enforced

### Runtime Enforcement
1. **`ensure_qe_pseudos()`** (in `core/pseudo.py`):
   - Ensures all required pseudos exist in `project_pseudo_dir` (typically `project/pseudo/`)
   - Copies from system cache if needed
   - Downloads if allowed and not found
   - **Never allows user to override the directory**

2. **`set_pseudo_dir_in_input()`** (called during QE input generation):
   - Always sets `pseudo_dir = ../pseudo` in QE input
   - This is relative to the calculation directory (e.g., `calculations/si_scf/`)
   - So `../pseudo` resolves to `project/pseudo/`

### Project Self-Containment
- All pseudos used in a run must exist in `project/pseudo/`
- This ensures:
  - Projects are portable (all dependencies in one place)
  - No external dependencies during runs
  - Reproducibility (pseudos are versioned with project)

### UI Constraint
- **UI must NOT allow users to override `pseudo_dir`**
- The `CommonCardPseudo` component correctly shows `pseudo_dir` as read-only
- Runtime will always enforce `../pseudo` regardless of UI input

## Current UI Behavior

### StepDetailPanel (Current - Wrong)
- Shows `CommonCardPseudo` component inside step detail
- Uses `get_calculation_pseudo_mapping` (correct RPC)
- But updates via `update_calculation_species_map` (correct)
- **Problem**: Pseudos are hidden inside step panels, not visible at calculation level

### CalculationDetailPanel (Current - Missing)
- Shows structure, mode, steps list
- **Missing**: No pseudopotential section
- **Problem**: Users can't see pseudos before configuring steps

## Target Architecture (After Refactor)

### Calculation Overview (Expanded)
- Show pseudopotentials section:
  - Element → pseudo filename mapping
  - Source indicator (SSSP / Imported / Online)
  - Read-only summary
  - "Edit Pseudopotentials" button → opens editor

### Calculation Overview (Collapsed)
- Show compact inline summary:
  - `Structure: Si | Pseudo: Si.pbe-n-rrkjus_psl (SSSP)`

### Step Detail Panel
- Remove full pseudo editor
- Replace with:
  - Read-only reference to calculation-level pseudos
  - Link: "Edit in Calculation Overview"

## Key Invariants (Do Not Violate)

1. **`pseudo_dir` is always `../pseudo`** - Runtime enforces this, UI must not allow override
2. **Calculation-level `species_map` is authoritative** - All steps inherit from it
3. **Project self-containment** - All pseudos must exist in `project/pseudo/`
4. **No hidden side effects** - No auto-commit without Apply button
5. **UI reflects filesystem** - Show actual filenames, not ULIDs

