# Knowledge Status & Review System Spec

**Date**: 2026-03-08
**Status**: Implemented
**Constraint**: Zero schema migration. All changes use existing columns.

---

## 1. Status Values

Four values. Replace `active` everywhere in code.

| Status | Meaning | Set by |
|---|---|---|
| `under_review` | New finding, not yet reviewed | `record_insight` (auto for grade=finding) |
| `confirmed` | Reviewed and validated by expertise | `review_insight`, `record_insight` (auto for grade≥pattern) |
| `verified` | Reviewed with external citation (URL + verbatim excerpt) | `review_insight` only (requires `citation_url` + `citation_excerpt` ≥50 chars) |
| `deprecated` | Rejected or superseded | `review_insight` only |

**No other code path may change status.** `review_insight` is the sole authority for status transitions.

---

## 2. record_insight — Auto Status by Grade

```
grade = bookkeeping  → provenance only (not promoted to local.db)
grade = observation   → provenance only (not promoted to local.db)
grade = finding       → status = 'under_review'
grade = pattern       → status = 'confirmed'
grade = principle     → status = 'confirmed'
```

Rationale: findings come from calculation sessions (unreviewed). Patterns and principles come from dedicated synthesis/review sessions where the agent has already assessed the evidence — the synthesis IS the review. No auto-status produces `verified` — that requires an explicit citation via `review_insight`.

---

## 3. review_insight — The Only Status Changer

### 3.1 Signature

```python
review_insight(
    insight_id: str,            # Full ULID of insight to review
    verdict: str,               # "confirmed" | "verified" | "deprecated"
    reasoning: str,             # Required. Why this verdict.
    citation_url: str = "",     # Must start with http:// or https://
    citation_excerpt: str = "", # 50+ chars verbatim from the source
    superseded_by: str = "",    # Optional: ULID of replacement insight
)
```

### 3.2 Behavior Matrix

| verdict | superseded_by | Effect on insight_id | Effect on superseded_by |
|---|---|---|---|
| confirmed | empty | → `confirmed`, update `last_validated` | — |
| confirmed | has ULID | → `confirmed`, update `last_validated` | → `confirmed` |
| verified | empty | → `verified`, update `last_validated`, store url+excerpt | — |
| verified | has ULID | → `verified`, update `last_validated`, store url+excerpt | → `confirmed` |
| deprecated | empty | → `deprecated`, write `deprecated_reason` | — |
| deprecated | has ULID, no citation | → `deprecated`, write `deprecated_reason` + `superseded_by` | → `confirmed` |
| deprecated | has ULID, citation given | → `deprecated`, write `deprecated_reason` + `superseded_by` | → `verified` (citation inherited) |

Note: When `superseded_by` is given with a citation (url+excerpt), the citation proves both that the old insight is wrong and that the replacement is correct — so the replacement is auto-verified with the same citation. Without a citation, the replacement gets `confirmed`. **Never downgrade**: if the replacement already has a higher status (e.g., `verified`), it keeps that status.

### 3.3 Columns Written

All existing columns, no schema change:

- `status` — set to `confirmed`, `verified`, or `deprecated`
- `deprecated_reason` — reasoning text (on deprecate)
- `superseded_by` — ULID of replacement (on deprecate with superseded_by)
- `last_validated` — ISO timestamp (on confirm/verify)
- `updated_at` — always updated
- `metadata.review` — `{"verdict": "...", "reasoning": "...", "reviewed_at": "...", "citation_url": "...", "citation_excerpt": "..."}`

When `superseded_by` is given with a citation, both `citation_url` and `citation_excerpt` propagate to the replacement insight's `metadata.review`.

### 3.4 Validation

- `insight_id` must exist in local.db (not builtin.db)
- `verdict` must be `"confirmed"`, `"verified"`, or `"deprecated"`
- `reasoning` must be non-empty
- If `verdict='verified'`: `citation_url` must be non-empty and start with `http://` or `https://`, `citation_excerpt` must be non-empty and ≥50 characters — **hard error** otherwise
- If `verdict='confirmed'` or `'deprecated'`: `citation_url` and `citation_excerpt` are optional (stored if given)
- If `superseded_by` is given, it must exist in local.db — **hard error** if not found, no changes made
- If insight is already `deprecated`, return error "insight already deprecated"

### 3.5 Revise Workflow (Two Steps)

```
Step 1: record_insight(content='corrected version', grade='finding', ...)
        → new insight, status = under_review

Step 2: review_insight(insight_id=old_id, verdict='deprecated',
                       superseded_by=new_id, reasoning='...',
                       citation='https://...')           # optional
        → old: deprecated + superseded_by=new_id
        → new: verified (if citation given) or confirmed (if no citation)
```

---

## 4. Contradiction Detection — Simplified

### 4.1 What Changes

Remove auto-status-change. Keep counting as informational signal.

```python
update_sql = "UPDATE insights SET contradiction_count = ?"
# Status changes handled exclusively by review_insight
```

### 4.2 Contradiction Matching Scope

Match all non-deprecated entries:
```sql
WHERE status IN ('verified', 'confirmed', 'under_review')
```

### 4.3 Contradiction Count

Remains monotonically increasing. Never reset by contradiction detection.
`review_insight(verdict='confirmed')` does NOT reset contradiction_count — it's a historical signal.

---

## 5. Search & List — Status Visibility

### 5.1 search_knowledge

- Return **all statuses** by default (verified + confirmed + under_review + deprecated)
- Ranking: `verified` (1.0) > `confirmed` (0.85) > `under_review` (0.65) > `deprecated` (0.3)
- `status` field returned in every result item
- Status-based multiplier added to trust-weighted BM25 score

### 5.2 list_insights

- Default: return `verified`, `confirmed`, `under_review` (exclude deprecated)
- Add optional `status` parameter: e.g., `status='under_review'` or `status='under_review,confirmed'`
- `status` and `contradiction_count` returned in every item

### 5.3 list_pending (synthesis mode)

Finds findings since last pattern — temporal window, not status-based.
Include `verified`, `confirmed`, and `under_review` findings in the window.
Exclude `deprecated`.

---

## 6. Vote System — Unchanged

- `upvotes`/`downvotes` via citations: keep as-is
- Votes never change status
- Votes are informational for review agent

---

## 7. Preamble — Three Modes

```
CALCULATION MODE — when asked to compute properties:
  search_knowledge → create_calculation → configure →
  run_calculation → check result:
    on failure → fix parameters → run_calculation again
    on success → get_results_summary →
      record_insight(grade='finding') for the result          [auto: under_review]
      record_insight(grade='finding', tags='error-recovery')  [auto: under_review]
        for EACH error you encountered and resolved this session

KNOWLEDGE REVIEW MODE — when asked to audit or validate knowledge:

  Your primary task is ensuring correctness. Incorrect knowledge that
  persists will mislead future sessions, waste compute, and produce
  wrong results. Take the time to verify thoroughly.

  1. list_insights(status='under_review') — see unreviewed findings
  2. For each finding:

     VERIFY (preferred): Search the web for relevant documentation,
     tutorials, or papers. Read the actual source with web_fetch.
     If the source supports the finding, use verdict='verified' with
     the URL and a verbatim excerpt (50+ chars). If the source
     contradicts the finding, deprecate or revise it.
     Do NOT cite from memory — citations must come from sources you
     read in this session.

     REASON (for every finding — disentangle its parts):
     A finding may contain data, conclusions, and recommendations that
     are independently correct or wrong. Separate them. For numerical
     data: ignore the literature value and ask where results converge —
     an outlier that matches a reference is not convergence. For each
     conclusion: does it follow from the data? Does it hold up against
     literature? Each part may need its own search.

     CONFIRM (fallback): Only if the finding is tool-specific (e.g.,
     YAML serialization quirks) where no external literature applies,
     or if you genuinely cannot find relevant sources after searching.

     DEPRECATE: If the finding is incorrect, outdated, or superseded.
     To revise: record_insight(corrected content) then
     review_insight(old_id, verdict='deprecated', superseded_by=new_id)

  3. Record any patterns that emerge from verified/confirmed findings

KNOWLEDGE SYNTHESIS MODE — when asked to review or summarize findings:
  list_insights(grade='finding', status='confirmed') → identify trends →
    record_insight(grade='pattern', references=[...finding IDs])  [auto: confirmed]
  list_insights(grade='pattern') → identify unifying mechanisms →
    record_insight(grade='principle', references=[...pattern IDs]) [auto: confirmed]
```

---

## 8. Migration

### 8.1 Status Rename in Code

Every occurrence of `'active'` in store.py, schema.py, build_builtin.py, search_knowledge.py, list_insights.py:

- `'active'` → `'confirmed'` for builtin entries and code defaults where "active" meant "trusted"
- BUT: `record_insight` for findings now writes `'under_review'` instead of `'active'`

### 8.2 Data Migration

**Builtin.db**: Rebuild with `confirmed` status (build_builtin.py already recreates from scratch).

**local.db**: `_migrate_active_to_confirmed()` runs on `init_db()`:
```sql
UPDATE insights SET status = 'confirmed' WHERE status = 'active';
```

### 8.3 Schema Migration Helper

In `schema.py`:
```python
def _migrate_active_to_confirmed(conn):
    """One-time: rename 'active' to 'confirmed' for existing entries."""
    conn.execute("UPDATE insights SET status = 'confirmed' WHERE status = 'active'")
    conn.commit()
```

Called in `init_db()` after other column migrations.

---

## 9. Files Changed

| File | Change |
|---|---|
| `src/qmatsuite/mcp/tools/review_insight.py` | **NEW** — review tool with confirmed/verified/deprecated verdicts |
| `src/qmatsuite/mcp/tools/record_insight.py` | Grade-based auto status |
| `src/qmatsuite/mcp/tools/list_insights.py` | Return status, add status filter |
| `src/qmatsuite/mcp/tools/search_knowledge.py` | Return status, ranking by status |
| `src/qmatsuite/mcp/knowledge/store.py` | `update_status()` method, contradiction simplification, status rename, list_pending fix |
| `src/qmatsuite/mcp/knowledge/schema.py` | Migration helper |
| `src/qmatsuite/mcp/knowledge/build_builtin.py` | Write `confirmed` not `active` |
| `src/qmatsuite/mcp/app.py` | Three-mode preamble with review guidance |
| `tests/mcp/test_knowledge_review.py` | **NEW** — 28 tests |
| `tests/mcp/test_knowledge_write.py` | Update status assertions |
