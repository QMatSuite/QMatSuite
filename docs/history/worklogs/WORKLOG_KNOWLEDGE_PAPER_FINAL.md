# Worklog: Knowledge System Refinements (R1–R11)

## Session 1 — R1–R10 Implementation

**Date**: 2026-03-03

Implemented all 10 planned refinements from `docs/design/MCP_KNOWLEDGE_SYSTEM_SPEC.md`.

### Changes

| ID | Title | Files |
|----|-------|-------|
| R1 | Sliding window nudge | `store.py`: `_count_pending()` replaces `_count_by_grade()` |
| R2 | Simultaneous L3→L4 and L4→L5 nudge | `store.py`: `_maybe_nudge()` returns `list[str]` |
| R3 | Soft/strong nudge tone | `store.py`: `tone` param. `search_knowledge.py`: soft. `record_insight.py`: strong |
| R4 | Stochastic nudge probability | `store.py`: `QMS_NUDGE_PROBABILITY` env var |
| R5 | list_insights mode parameter | `list_insights.py`: `mode="pending"` (default) / `"recent"` |
| R6 | Pending count header | `list_insights.py`: header shows pending count and since-timestamp |
| R7 | Short IDs in output | 14-char prefix in `search_knowledge.py`, `list_insights.py`, `record_insight.py` |
| R8 | Short ID prefix resolution | `store.py`: `resolve_short_id()`. `record_insight.py`: resolve refs + citations |
| R9 | Remove content truncation | `list_insights.py`: full content returned |
| R10 | Search-before-calculate preamble | `app.py`: added guidance paragraph |

### Design deviation

R7 uses 14-char short IDs instead of the planned 10-char. ULID first 10 chars
are pure timestamp (ms precision); ULIDs generated in the same millisecond share
identical 10-char prefixes. 14 chars adds 4 random chars (20 bits), eliminating
collisions in practice.

### Tests

- 104 knowledge write tests (15 net new)
- 6844 total passed, 0 failed, 4 skipped

---

## Session 2 — R11: Close Vote Feedback Loop

**Date**: 2026-03-03

### Problem

Citation votes (`upvotes`/`downvotes`) were stored in local.db but never
returned to agents in search or list results. The feedback loop was broken.

### Fix

Added `upvotes` and `downvotes` fields to result items in:
- `search_knowledge.py` — search result dicts
- `list_insights.py` — both pending and recent mode item dicts

No changes to `store.py` (counters already stored and updated correctly).

### Tests

- `test_votes_visible_in_search_results` — record insight, upvote via citation, search, verify `upvotes == 1`
- `test_votes_visible_in_list_insights` — record insight, downvote via citation, list, verify `downvotes == 1`

### Spec

Updated `MCP_KNOWLEDGE_SYSTEM_SPEC.md` §4.1 and §4.2 response format examples
to include `upvotes`/`downvotes` fields.

---

## Session 3 — Final Polish (G1–G9 + Preamble Rewrite)

**Date**: 2026-03-03

Addressed all gaps from `docs/history/reviews/REVIEW_MCP_KNOWLEDGE_NAIVE_AGENT.md`.
This is the final MCP knowledge system change before experiments.

### Changes

| ID | Title | Files |
|----|-------|-------|
| G1 | Citation summary uses actual applied counts | `record_insight.py`: use `apply_citations()` return value |
| G2 | Reference error hint grade-aware | `record_insight.py`: pattern→'finding', principle→'pattern' |
| G3 | record_intent in preamble | `app.py`: preamble rewrite |
| G4 | get_results_summary hints record_insight | `get_results_summary.py`: append to context_hint |
| G5 | Structured knowledge tracking | Deferred to `DEFERRED_ITEMS.md` |
| G6 | Preamble explains upvotes/downvotes | `app.py`: preamble rewrite |
| G7 | Tags parsed to list | `search_knowledge.py`, `list_insights.py`: `json.loads(tags)` |
| G8 | Mode validation in list_insights | `list_insights.py`: validate 'pending'/'recent' |
| G9 | Mode field in list_insights response | `list_insights.py`: add `"mode": mode` to both branches |

### Tests

- 11 new tests in `TestGapFixes` + 3 updated preamble tests + 1 updated citation test
- Total: 6857 passed, 0 failed, 4 skipped
