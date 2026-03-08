# Knowledge Review System Implementation Worklog

**Date**: 2026-03-08
**Spec**: `docs/design/SPEC_KNOWLEDGE_REVIEW_SYSTEM.md`
**Review**: `docs/history/reviews/REVIEW_KNOWLEDGE_STATUS_MECHANISM.md`

---

## Plan

### Summary

Implement the knowledge status & review system per spec. Three status values (`confirmed`, `under_review`, `deprecated`) replace the old `active`/`under_review` pair. New `review_insight` tool provides the only explicit status-change mechanism. Grade-based auto-status on creation. No schema changes — all columns already exist.

### File Changes

#### 1. `src/qmatsuite/mcp/knowledge/schema.py`
- Change DDL default: `status TEXT DEFAULT 'under_review'` (was `'active'`)
- Add migration `_migrate_active_to_confirmed(conn)`:
  - `UPDATE insights SET status = 'confirmed' WHERE status = 'active'`
- Call migration in `init_db()` after existing migrations

#### 2. `src/qmatsuite/mcp/knowledge/store.py`
- **`count()`**: `status = 'active'` → `status = 'confirmed'`
- **`add()`**: Grade-based auto status:
  - `finding` → `'under_review'`
  - `pattern`, `principle` → `'confirmed'`
  - Change INSERT from hardcoded `'active'` to parameterized status
- **`list_by_grade()`**:
  - `status IN ('active', 'under_review')` → `status IN ('confirmed', 'under_review')`
  - Add optional `statuses: list[str] | None` parameter
- **`list_pending()`**:
  - Add status filter: default `['confirmed', 'under_review']` (exclude deprecated)
  - Add optional `statuses: list[str] | None` parameter
- **`_fts_search()`**: `('active', 'under_review')` → `('confirmed', 'under_review', 'deprecated')`
- **`_scope_search()`**: same
- **`_apply_trust_ranking()`**: Add status-based weight multiplier:
  - confirmed: 1.0, under_review: 0.8, deprecated: 0.3
- **`_detect_contradictions()`**:
  - `status = 'active'` → `status IN ('confirmed', 'under_review')`
  - Remove auto-status-change line (keep count increment only)
- **New method `update_status()`**: For review_insight to call
  - Accepts insight_id, verdict, reasoning, superseded_by
  - Writes status, deprecated_reason, superseded_by, last_validated, metadata.review, updated_at

#### 3. `src/qmatsuite/mcp/knowledge/build_builtin.py`
- `'active'` → `'confirmed'` in INSERT

#### 4. `src/qmatsuite/mcp/tools/record_insight.py`
- No changes needed — status is set in `store.add()` based on grade

#### 5. `src/qmatsuite/mcp/tools/list_insights.py`
- Add `status: str = ""` parameter (comma-separated filter)
- Return `"status"` and `"contradiction_count"` in both item dicts (recent + pending modes)
- Pass parsed statuses to store methods

#### 6. `src/qmatsuite/mcp/tools/search_knowledge.py`
- Return `"status"` in every result item
- contradiction_count always returned (not just when > 0)

#### 7. `src/qmatsuite/mcp/tools/review_insight.py` (NEW)
- ~100 lines
- Signature: `review_insight(insight_id, verdict, reasoning, superseded_by="")`
- Validations: exists in local.db, not builtin, valid verdict, non-empty reasoning, superseded_by exists if given, not already deprecated
- Calls `store.update_status()`
- Register in app.py imports

#### 8. `src/qmatsuite/mcp/app.py`
- Three-mode preamble: CALCULATION, KNOWLEDGE REVIEW, KNOWLEDGE SYNTHESIS

#### 9. `tests/mcp/test_knowledge_review.py` (NEW)
- ~20 tests covering review_insight operations, auto-status, validation, search/list integration, contradiction changes, migration

#### 10. `tests/mcp/test_knowledge_write.py` (MODIFY)
- `_insert_entry()` default: `status="active"` → `status="confirmed"`
- `test_contradiction_threshold_flags_review`: assertion changes (no longer auto-flags status)
- `test_all_grades_valid`: `status = 'active'` → different statuses per grade
- `test_search_does_not_prefix_under_review`: `status="active"` → `status="confirmed"`
- `TestMCPInstructions`: update assertions for three-mode preamble

### Status Rename Occurrences

| File | Old | New |
|------|-----|-----|
| schema.py:29 DDL default | `'active'` | `'under_review'` |
| store.py:168 count() | `= 'active'` | `= 'confirmed'` |
| store.py:253 add() INSERT | `'active'` | computed from grade |
| store.py:291 list_by_grade | `IN ('active', 'under_review')` | `IN ('confirmed', 'under_review')` |
| store.py:484 contradiction | `= 'active'` | `IN ('confirmed', 'under_review')` |
| store.py:502-503 contradiction auto-status | `, status = 'under_review'` | **removed** |
| store.py:552 fts_search | `IN ('active', 'under_review')` | `IN ('confirmed', 'under_review', 'deprecated')` |
| store.py:586 scope_search | `IN ('active', 'under_review')` | `IN ('confirmed', 'under_review', 'deprecated')` |
| build_builtin.py:75 | `'active'` | `'confirmed'` |

### Migration Strategy

1. `_migrate_active_to_confirmed(conn)`: `UPDATE insights SET status = 'confirmed' WHERE status = 'active'`
2. Called in `init_db()` after `_migrate_downvotes_column()`
3. Idempotent — no-op if no `active` rows exist
4. Builtin.db: rebuilt from scratch with `'confirmed'`
5. Local.db: migration runs on next `init_db()` call

### Risk Assessment

- **Existing experiments**: Old local.db files will get `active` → `confirmed` on next access via migration. This is correct — they were "active" which means "trusted", which maps to "confirmed".
- **Builtin.db**: Rebuilt from scratch, always clean.
- **count()**: Used in `__init__.py` to detect empty builtin.db. Changing filter to `confirmed` means after migration, the count will be correct. On a fresh DB before rebuild, count=0 triggers rebuild — correct.
- **Tests**: ~5 tests need assertion updates for new status values.

---

## Implementation Log

### Phase 1: Status rename + grade-based auto status + contradiction simplification

**Files changed:**

1. **schema.py**: DDL default `'active'` → `'under_review'`, added `_migrate_active_to_confirmed()`, called in `init_db()`
2. **store.py**:
   - `count()`: `'active'` → `'confirmed'`
   - `add()`: Grade-based status (`finding` → `under_review`, `pattern/principle` → `confirmed`), parameterized INSERT
   - `list_by_grade()`: accepts `statuses` param, default `['confirmed', 'under_review']`
   - `list_pending()`: accepts `statuses` param, default `['confirmed', 'under_review']` (bug fix: was no filter)
   - `_fts_search()` / `_scope_search()`: include deprecated in search
   - `_apply_trust_ranking()`: status weight multiplier (confirmed=1.0, under_review=0.8, deprecated=0.3)
   - `_detect_contradictions()`: match `IN ('confirmed', 'under_review')`, removed auto-status-change
   - New `update_status()` method: writes status, deprecated_reason, superseded_by, last_validated, metadata.review
3. **build_builtin.py**: `'active'` → `'confirmed'`
4. **search_knowledge.py**: returns `status` and `contradiction_count` in every item
5. **list_insights.py**: new `status` param, returns `status` + `contradiction_count` in items
6. **app.py**: three-mode preamble (CALCULATION, REVIEW, SYNTHESIS)

### Phase 2: review_insight tool

7. **review_insight.py** (NEW): ~110 lines, full validation, calls `store.update_status()`
8. **server.py**: registered `review_insight` import

### Phase 3: Tests

9. **test_knowledge_review.py** (NEW): 22 tests covering auto-status, review operations, validation, search/list integration, contradiction simplification, migration, metadata
10. **test_knowledge_write.py**: updated 5 assertions (status rename, contradiction no-auto-flag, grade-specific status, preamble assertions)
11. **test_behavioral_hints.py**: `'active'` → `'confirmed'` in test fixture
12. **test_stage11.py**, **test_stage_p1.py**, **test_stage_p2.py**: tool count 41 → 42

### Test Results

- `tests/mcp/test_knowledge_review.py`: 22 passed
- `tests/mcp/test_knowledge_write.py`: 100 passed
- `tests/mcp/` (full): 781 passed, 0 failed
- `tests/` (full): 6892 passed, 4 skipped, 1 pre-existing error (QMCPACK integration)

### Phase 4: `verified` status with mandatory citation

- **review_insight.py**: Added `verified` verdict + `citation` parameter. Citation required (>10 chars) for `verified`, optional for others.
- **store.py**:
  - `_STATUS_WEIGHT`: verified=1.0, confirmed=0.85, under_review=0.65, deprecated=0.3
  - `update_status()`: handles `verified` verdict, stores citation in `metadata.review.citation`
  - All SQL status filters include `'verified'` alongside `'confirmed'`
  - `list_by_grade`/`list_pending` defaults: `['verified', 'confirmed', 'under_review']`
  - `_detect_contradictions`: matches `IN ('verified', 'confirmed', 'under_review')`
- **app.py**: KNOWLEDGE REVIEW MODE updated with verify-first guidance
- **spec**: Updated with 4-status model, citation field, new ranking weights
- **test_knowledge_review.py**: +6 tests (28 total) — verified status, citation validation, ranking

Asymmetry audit (confirmed without verified):
- `count()`: builtin-only, always `confirmed` — correct
- `add()` auto-status: new entries can't be `verified` without citation — correct
- `superseded_by` replacement: auto-confirms, doesn't auto-verify — correct (per spec)

### Phase 4 Test Results

- `tests/mcp/test_knowledge_review.py`: 28 passed
- `tests/mcp/` (full): 787 passed, 0 failed

### Phase 5: superseded_by inherits citation → auto-verify

- **store.py** `update_status()`: When `superseded_by` is given with a citation, the replacement insight gets `verified` (not `confirmed`) with the citation propagated to its `metadata.review.citation`. Without citation, stays `confirmed`.
- **spec**: Updated behavior matrix (§3.2) with citation-conditional rows, added citation propagation note to §3.3, updated revise workflow (§3.5).
- **test_knowledge_review.py**: +2 tests (30 total) — `test_superseded_by_with_citation_auto_verifies`, `test_superseded_by_without_citation_stays_confirmed`

### Phase 5 Test Results

- `tests/mcp/test_knowledge_review.py`: 30 passed
- `tests/` (full): 6900 passed, 4 skipped, 1 pre-existing error (QMCPACK integration)

### Phase 6: Split citation into url+excerpt — prevent hallucinated citations

Run_06 revealed the review agent "verified" findings by citing papers from memory without actually searching or reading them. Fix: require a real URL + verbatim 50+ char excerpt from the source.

- **review_insight.py**: Replaced `citation: str` with `citation_url: str` + `citation_excerpt: str`. Validation for `verdict='verified'`: URL must start with `http://`/`https://`, excerpt must be ≥50 chars. Both optional for `confirmed`/`deprecated`.
- **store.py** `update_status()`: `citation` parameter split into `citation_url` + `citation_excerpt`. Both stored in `metadata.review`. superseded_by inheritance passes both fields.
- **app.py**: Rewrote KNOWLEDGE REVIEW MODE preamble — "Do NOT cite from memory", web_search+web_fetch required, verify-first with fallback to confirm.
- **spec**: Updated §3.1 (signature), §3.2 (behavior matrix), §3.3 (metadata format), §3.4 (validation), §7 (preamble).
- **test_knowledge_review.py**: Replaced 6 old citation tests with 10 new url+excerpt tests (33 total): url format, url nonempty, excerpt nonempty, excerpt min length, confirmed empty/given, superseded inherits both, ranking.

### Phase 6 Test Results

- `tests/mcp/test_knowledge_review.py`: 33 passed
- `tests/mcp/` (full): 792 passed, 0 failed
- `tests/` (full): 6903 passed, 4 skipped, 1 pre-existing error (QMCPACK integration)
