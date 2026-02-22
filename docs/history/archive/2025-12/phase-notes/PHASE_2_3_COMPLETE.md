# Phase 2 & 3 Implementation Complete

## Summary

All quick adds, Phase 2 (K_POINTS Common Card), and Phase 3 (PSEUDO Common Card) have been implemented following the Common Cards Contract.

## Quick Adds (Completed)

### 1. Metadata Load Policy
- **File**: `gui/src/hooks/useQEParameterMetadata.ts`
- Added `refresh()` method that clears `loadedSectionsRef` and `inFlightRef`
- Allows fresh loads without backend reload
- Available for StepDetailPanel to use when needed

### 2. One Source of Truth for Display vs Storage
- **File**: `gui/src/utils/qeStringUtils.ts`
- Added `displayScalar(value: string)`: Strip quotes, trim for UI display
- Added `storeEnumSelection(value: string, meta)`: Quote only when CHARACTER type
- Added `canonicalLogicalSelection(bool)`: Returns ".true." or ".false."
- These are the canonical functions for ParameterValueEditor

### 3. Common Cards Contract
- **File**: `docs/COMMON_CARDS_CONTRACT.md`
- Defines architecture: UI never parses QE raw text
- Python service owns parsing/formatting
- UI is presentation-only (renders view model, sends edits back)
- Prevents "UI parsing creep" in future implementations

## Phase 2: K_POINTS Common Card (Completed)

### Backend (Python)

1. **K_POINTS View Model Module** (`src/qmatsuite/calculation/k_points_view.py`)
   - `KPointsViewModel` dataclass with mode, automatic, points, warnings
   - `parse_k_points(raw: str)` - Parses raw QE text to view model
   - `format_k_points(view_model)` - Formats view model to canonical QE text
   - `k_points_from_card_data()` - Converts YAML card data to raw text
   - `k_points_to_card_data()` - Converts raw text to YAML card data
   - Supports: gamma, automatic, tpiba, crystal, tpiba_b, crystal_b, tpiba_c, crystal_c, custom

2. **QMSService Methods** (`src/qmatsuite/api.py`)
   - `get_common_cards()` - Returns view models for all common cards
   - `set_common_card()` - Updates card from view model, writes YAML as string

3. **RPC Handlers** (`src/qmatsuite/daemon/server.py`)
   - `get_common_cards` RPC handler
   - `set_common_card` RPC handler
   - Registered in `_handlers` dict

### Frontend (TypeScript/React)

1. **TypeScript Types** (`gui/src/types/qms.ts`)
   - Added `get_common_cards` and `set_common_card` to QMSCommandMap
   - Type-safe view model types

2. **RPC Client** (`gui/src/hooks/useQMSClient.ts`)
   - Added `getCommonCards()` method
   - Added `setCommonCard()` method
   - Added to QMSClient interface

3. **CommonCardKPoints Component** (`gui/src/components/common_cards/CommonCardKPoints.tsx`)
   - Mode dropdown (gamma, automatic, tpiba, crystal, etc.)
   - Automatic mode: nk1, nk2, nk3, sk1, sk2, sk3 inputs
   - List modes: Editable table for k-points (x, y, z, w)
   - Raw fallback: Collapsible raw textarea
   - Warnings display: Inline non-blocking warnings
   - Apply button: Calls `set_common_card` RPC

4. **StepDetailPanel Integration** (`gui/src/components/panels/StepDetailPanel.tsx`)
   - Added "Common Cards" section after "Active Parameters"
   - Shows K_POINTS card editor (only for pw module steps)
   - Loads common cards on step detail fetch
   - Handles Apply with step detail refresh

## Phase 3: PSEUDO Common Card (Completed)

### Backend (Python)

1. **QMSService Methods** (`src/qmatsuite/api.py`)
   - `get_pseudo_mapping()` - Returns species list, current mapping, pseudo_dir, available pseudos, warnings
   - `set_pseudo_mapping()` - Updates species_overrides and CONTROL.pseudo_dir, writes YAML as string

2. **RPC Handlers** (`src/qmatsuite/daemon/server.py`)
   - `get_pseudo_mapping` RPC handler
   - `set_pseudo_mapping` RPC handler
   - Registered in `_handlers` dict

### Frontend (TypeScript/React)

1. **TypeScript Types** (`gui/src/types/qms.ts`)
   - Added `get_pseudo_mapping` and `set_pseudo_mapping` to QMSCommandMap
   - Type-safe mapping types

2. **RPC Client** (`gui/src/hooks/useQMSClient.ts`)
   - Added `getPseudoMapping()` method
   - Added `setPseudoMapping()` method
   - Added to QMSClient interface

3. **CommonCardPseudo Component** (`gui/src/components/common_cards/CommonCardPseudo.tsx`)
   - Species → pseudopotential file mapping table
   - Pseudo directory input (CONTROL.pseudo_dir)
   - Dropdown to select from available UPF files in project
   - Warnings display: Missing pseudos, files not found
   - Available pseudos list (collapsible)
   - Apply button: Calls `set_pseudo_mapping` RPC

4. **StepDetailPanel Integration** (`gui/src/components/panels/StepDetailPanel.tsx`)
   - Added PSEUDO card editor to "Common Cards" section
   - Loads pseudo mapping on step detail fetch
   - Handles Apply with step detail refresh

## Files Created/Modified

### Backend
- `src/qmatsuite/calculation/k_points_view.py` (NEW)
- `src/qmatsuite/api.py` (MODIFIED - added get_common_cards, set_common_card, get_pseudo_mapping, set_pseudo_mapping)
- `src/qmatsuite/daemon/server.py` (MODIFIED - added RPC handlers)

### Frontend
- `gui/src/types/qms.ts` (MODIFIED - added command types)
- `gui/src/hooks/useQMSClient.ts` (MODIFIED - added RPC methods)
- `gui/src/utils/qeStringUtils.ts` (MODIFIED - added displayScalar, storeEnumSelection, canonicalLogicalSelection)
- `gui/src/hooks/useQEParameterMetadata.ts` (MODIFIED - added refresh method)
- `gui/src/components/common_cards/CommonCardKPoints.tsx` (NEW)
- `gui/src/components/common_cards/CommonCardKPoints.css` (NEW)
- `gui/src/components/common_cards/CommonCardPseudo.tsx` (NEW)
- `gui/src/components/common_cards/CommonCardPseudo.css` (NEW)
- `gui/src/components/panels/StepDetailPanel.tsx` (MODIFIED - integrated common cards)

### Documentation
- `docs/COMMON_CARDS_CONTRACT.md` (NEW)
- `PHASE_2_PROGRESS.md` (NEW)
- `PHASE_2_3_COMPLETE.md` (NEW - this file)

## Architecture Compliance

✅ **UI Never Parses QE Raw Text**: All parsing/formatting done in Python backend  
✅ **YAML Storage is String-Only**: All values stored as strings, no type coercion  
✅ **View Model Pattern**: UI receives structured view models, sends back structured edits  
✅ **Round-Trip Stable**: Original formatting preserved until user edits, then canonical formatting  
✅ **Non-Blocking Warnings**: Validation warnings displayed inline, never block Apply

## Testing Notes

### K_POINTS
- Import QE input with any K_POINTS flavor → UI shows correct mode and values
- Changing values updates YAML raw string only
- Switching modes rewrites card appropriately
- Raw text fallback works for custom/unsupported modes

### PSEUDO
- Species list populated from structure
- Current mapping displayed from species_overrides
- Available pseudos listed from project/pseudo directory
- Warnings shown for missing pseudos
- Apply updates species_overrides and CONTROL.pseudo_dir

## Next Steps (Optional)

1. Add unit tests for K_POINTS parse/format round-trip
2. Add integration tests for common cards RPCs
3. Consider adding more common cards (ATOMIC_POSITIONS, CELL_PARAMETERS, etc.)
4. Add "Download SSSP" feature for pseudopotentials (future enhancement)

