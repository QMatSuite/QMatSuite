# Phase 2 Progress - K_POINTS Common Card

## Completed

### Backend (Python)

1. **K_POINTS View Model Module** (`src/quantumvitas/calculation/k_points_view.py`)
   - `KPointsViewModel` dataclass with mode, automatic, points, warnings
   - `parse_k_points(raw: str)` - Parses raw QE text to view model
   - `format_k_points(view_model)` - Formats view model to canonical QE text
   - `k_points_from_card_data()` - Converts YAML card data to raw text
   - `k_points_to_card_data()` - Converts raw text to YAML card data
   - Supports: gamma, automatic, tpiba, crystal, tpiba_b, crystal_b, tpiba_c, crystal_c, custom

2. **QVService Methods** (`src/quantumvitas/api.py`)
   - `get_common_cards()` - Returns view models for all common cards
   - `set_common_card()` - Updates card from view model, writes YAML as string

3. **RPC Handlers** (`src/quantumvitas/daemon/server.py`)
   - `get_common_cards` RPC handler
   - `set_common_card` RPC handler
   - Registered in `_handlers` dict

## Remaining

### Frontend (TypeScript/React)

1. **CommonCardKPoints Component** (`gui/src/components/common_cards/CommonCardKPoints.tsx`)
   - Mode dropdown (gamma, automatic, tpiba, crystal, etc.)
   - Automatic mode: nk1, nk2, nk3, sk1, sk2, sk3 inputs
   - List modes: Editable table for k-points (x, y, z, w)
   - Raw fallback: Collapsible raw textarea
   - Warnings display: Inline non-blocking warnings
   - Integration: Call `get_common_cards` on load, `set_common_card` on Apply

2. **StepDetailPanel Integration**
   - Add "Common" section after "Active Parameters"
   - Show K_POINTS card editor (only for pw module steps)
   - Handle Apply/Cancel with step detail refresh

3. **TypeScript Types** (`gui/src/types/qv.ts`)
   - Add `CommonCardsResponse` type
   - Add `KPointsViewModel` type

4. **RPC Client** (`gui/src/hooks/useQVClient.ts`)
   - Add `getCommonCards()` method
   - Add `setCommonCard()` method

## Next Steps

1. Add TypeScript types for view models
2. Add RPC client methods
3. Create CommonCardKPoints component
4. Integrate into StepDetailPanel
5. Test round-trip: import → edit → save → verify YAML

## Notes

- Backend follows Common Cards Contract: UI never parses raw text
- YAML storage is string-only (card data dict, not typed)
- Round-trip: Original formatting preserved until user edits, then canonical formatting

