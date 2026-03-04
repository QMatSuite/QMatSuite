# Worklog: Task 3 Part 1 — MCP Text Changes

**Date**: 2026-03-03
**Commit**: `fix(knowledge): refine nudge text and preamble for Task 3 experiments`

---

## Purpose

Refine MCP preamble and nudge text to encourage synthesis behavior (pattern/principle recording) based on findings from Task 2.2 experiments where zero L2/L3 insights emerged from 85+ sessions.

## Changes Made

### Change 1: Preamble KNOWLEDGE GRADES — finding line

**File**: `src/qmatsuite/mcp/app.py:26-28`

Changed the `finding` grade description to emphasize numerical values:

```
  finding -> verified result from one calculation (promoted to knowledge DB)
            Include specific numerical values so future sessions can
            compare across compounds.
```

Previously a single line with `—` dash; now uses `->` arrow and adds two-line elaboration about numerical values and cross-compound comparison.

### Change 2: Preamble — search-before-calculate guidance

**File**: `src/qmatsuite/mcp/app.py:40-43`

Appended to end of `_MCP_INSTRUCTIONS`:

```
Before starting new calculations:
- Search the knowledge base for relevant prior findings
- Check if similar compounds or workflows have been studied before
```

### Change 3: New helper — `_pending_compounds()`

**File**: `src/qmatsuite/mcp/knowledge/store.py:451-482`

Added `_pending_compounds(grade)` method to `KnowledgeStore`. Queries the local DB for distinct tags from pending insights (those created since the last higher-grade synthesis). Returns a comma-separated string of tag values, or "multiple compounds" if none found. Used by the L3->L4 nudge text to show which compounds the pending findings cover.

### Change 4: L4->L5 Nudge Text (strong tone)

**File**: `src/qmatsuite/mcp/knowledge/store.py:508-514`

Replaced the pattern->principle nudge with text that asks the agent to consider unifying physical/chemical mechanisms or computational guidelines, rather than generic "synthesizing principles is part of your research program".

### Change 5: L3->L4 Nudge Text (strong tone)

**File**: `src/qmatsuite/mcp/knowledge/store.py:523-534`

Replaced the finding->pattern nudge with text that:
- Shows which compounds the pending findings cover (via `_pending_compounds()`)
- Asks about systematic trends across related compounds
- Asks about physical/chemical factors explaining variation
- Removes generic "synthesizing patterns is part of your research program"

### Change 6: `get_results_summary` context_hint

**File**: `src/qmatsuite/mcp/tools/get_results_summary.py:95-107`

Replaced old hint (which led with `inspect_calculation` and appended generic `record_insight`) with workflow-specific hints:

- **relax/minimize**: Leads with `promote_structure()` for relaxed geometry extraction, then asks for numerical findings (lattice constants, errors vs experiment)
- **other**: Asks for numerical findings (band gaps, k-point locations, direct/indirect) for cross-compound comparison

## Files Changed

| File | Lines | Nature |
|------|-------|--------|
| `src/qmatsuite/mcp/app.py` | 14-44 | Text-only (preamble string) |
| `src/qmatsuite/mcp/knowledge/store.py` | 451-535 | New helper method + text changes in nudge |
| `src/qmatsuite/mcp/tools/get_results_summary.py` | 95-108 | Text-only (context_hint string) |

## Verification

All existing tests pass. Changes are text-only except for the `_pending_compounds()` helper, which queries existing DB tables with no schema changes.
