# Worklog: Pre-Meta-Session Code Fixes

**Date:** 2026-03-04
**Branch:** v2-python
**Context:** Chain A experiment (38 sessions) showed zero patterns/principles despite 25+ findings. Traceability audit identified 4 code-level gaps blocking effective meta-session synthesis.

## Change 1: Return Full ULIDs (not truncated [:14])

Truncated IDs prevented cross-referencing between `list_insights` output and `record_insight(references=[...])`.

**Files changed:**
- `src/qmatsuite/mcp/tools/list_insights.py` — 2 locations: `r["id"][:14]` → `r["id"]`
- `src/qmatsuite/mcp/tools/search_knowledge.py` — 1 location: `r["id"][:14]` → `r["id"]`
- `src/qmatsuite/mcp/tools/record_insight.py` — 1 location: `insight_id[:14]` → `insight_id`

**Tests updated:**
- `test_short_id_length_is_14` → `test_full_ulid_length_is_26`
- `test_record_insight_with_short_references` → `test_record_insight_with_full_references`
- `test_full_synthesis_flow` — updated assertions from 14-char to 26-char ULIDs

## Change 2: Include `under_review` in Status Filters

Contradiction detection sets findings to `under_review` when 3+ same-scope entries exist. In survey experiments (all same scope), only the 3 most recent were ever `active`, hiding the rest.

**File:** `src/qmatsuite/mcp/knowledge/store.py` — 3 locations:
- `list_by_grade()`: `AND status = 'active'` → `AND status IN ('active', 'under_review')`
- `_fts_search()`: `AND i.status = 'active'` → `AND i.status IN ('active', 'under_review')`
- `_scope_search()`: `WHERE i.status = 'active'` → `WHERE i.status IN ('active', 'under_review')`

**Not changed:** `_detect_contradictions` logic, `count()` method, any status transitions.

## Change 3: Remove Nudge Mechanism

0% engagement across 16+ post-threshold sessions. Nudge text in `record_insight` and `search_knowledge` had zero effect on agent behavior.

**Deleted from `store.py`:**
- `_count_pending()` method
- `_pending_compounds()` method
- `_maybe_nudge()` method
- `import random` (only caller was `_maybe_nudge`)

**Deleted from tools:**
- `record_insight.py`: 10-line strong nudge injection block
- `search_knowledge.py`: 7-line soft nudge injection block

**Tests deleted (12 total):**
- `TestNudge` class (8 tests)
- `TestSearchContext` class (4 tests)

## Change 4: Expose `source_calculation` as Top-Level Field

Previously buried in `metadata` JSON blob. The meta-session needs it to cross-reference findings with calculation directories.

**Pattern:** Parse metadata JSON once into `meta` local var, reuse for both `metadata` key and `source_calculation` extraction.

**Files changed:**
- `list_insights.py` — both recent and pending mode item dicts
- `search_knowledge.py` — search results item dict

## Verification

```
746 passed, 0 failed, 486 warnings (57.31s)
```

12 nudge-related tests removed (was ~758 tests in MCP suite).
