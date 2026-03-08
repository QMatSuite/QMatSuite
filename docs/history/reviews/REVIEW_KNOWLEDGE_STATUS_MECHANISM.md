# Knowledge System Status & Review Mechanism Review

**Date**: 2026-03-08
**Reviewer**: Claude Opus 4.6
**Scope**: Read-only analysis of the `status` field lifecycle, contradiction detection, vote system, and gap analysis for a future `review_insight` tool.

---

## 1. Current Status Lifecycle

### 1.1 Schema Definition

**File**: `src/qmatsuite/mcp/knowledge/schema.py:13-41`

The `insights` table defines `status` as free-form TEXT with a default:

```sql
status TEXT DEFAULT 'active',
```

There is **no CHECK constraint or enum enforcement** — any string value can be stored. The schema also defines three related columns that are **never used by any code**:

```sql
superseded_by TEXT,       -- FK to insights(id), never populated
deprecated_reason TEXT,   -- never populated
merged_into TEXT,         -- never populated
```

Additional status-adjacent columns:

```sql
contradiction_count INTEGER DEFAULT 0,
upvotes INTEGER DEFAULT 0,
downvotes INTEGER DEFAULT 0,
```

An index exists on the status column:

```sql
CREATE INDEX IF NOT EXISTS idx_insights_status ON insights(status);
```

**Known status values in practice**: `'active'` and `'under_review'`. No other values exist in any database (see §2).

### 1.2 Creation (record_insight → store.add)

**File**: `src/qmatsuite/mcp/knowledge/store.py:243-253`

Every new insight is **always** inserted with:

```sql
INSERT INTO insights (..., status, contradiction_count, upvotes, ...)
VALUES (..., 'active', 0, 0, ...)
```

The `InsightRecord` dataclass (`insight_record.py:19-43`) has **no status field** — status is set exclusively by `store.add()` at INSERT time. There is no mechanism for a caller to specify initial status.

**Builtin insights** (`build_builtin.py:73-75`) are also inserted with `'active'`, `contradiction_count=0`, `upvotes=0`.

### 1.3 Contradiction Detection

**File**: `src/qmatsuite/mcp/knowledge/store.py:454-519`

#### When does it fire?

On every `add()` call, immediately after INSERT. Called at `store.py:277-279`:

```python
contradictions = self._detect_contradictions(
    insight_id, scope_engine, scope_workflow, scope_system_type, scope_method,
)
```

It fires **only** on `add()` — not on search, not on list, not on any other operation.

#### Matching logic (store.py:467-491)

The algorithm:

1. Collect all non-wildcard scope fields from the **new** entry (lines 474-476):
   ```python
   non_wildcard = {k: v for k, v in new_scopes.items() if v != "*"}
   if not non_wildcard:
       return []  # All wildcards — nothing to contradict
   ```

2. For each database (builtin + local), find entries where (line 484-489):
   - `status = 'active'` — only active entries are matched
   - `id != ?` — skip the newly inserted entry itself
   - For each non-wildcard scope field: `(field = ? AND field != '*')` — the existing entry must also be non-wildcard AND have the same value

3. **Tags, compound, content** are NOT part of matching.

4. Searches **both** databases (builtin + local) via `_active_dbs()` (line 481, 521-526).

#### What does it change? (store.py:494-509)

On each matching existing entry:

```python
new_count = old_count + 1  # Always increments by 1
update_sql = "UPDATE insights SET contradiction_count = ?"
if new_count >= _CONTRADICTION_THRESHOLD:  # Threshold = 3
    update_sql += ", status = 'under_review'"
update_sql += " WHERE id = ?"
```

- **Increments** `contradiction_count` on the **existing** (older) entry, not the new one.
- When count reaches `_CONTRADICTION_THRESHOLD` (3), sets `status = 'under_review'`.
- The **new** entry's `contradiction_count` stays at 0 (as inserted).

#### One-way status change

There is **no mechanism to clear `under_review` back to `active`**. Once status is set to `under_review`, it stays there permanently. No code in the entire `mcp/` directory writes `status = 'active'` to an existing row.

#### No mechanism to decrease contradiction_count

No code ever decrements `contradiction_count`. It is monotonically increasing.

#### The Chain A false-positive problem

Because matching uses only scope fields (engine, workflow, system_type, method) and ignores tags/content, entries for **different compounds with the same scope** trigger false contradictions. For example, all `scope_engine='qe', scope_workflow='scf'` findings (regardless of whether they're about Si, Fe, GaAs, etc.) match each other.

**This was NOT fixed.** The matching logic at lines 467-489 is unchanged. The database evidence (§2) confirms: 6 out of 15 local insights hit `contradiction_count >= 3` and were flagged `under_review`, despite likely being about different compounds.

### 1.4 Up/Down Votes (Citations)

**File**: `src/qmatsuite/mcp/tools/record_insight.py:126-146` (parsing), `store.py:322-360` (application)

#### How an agent casts a vote

Votes are cast **only** through the `citations` parameter on `record_insight`:

```python
citations: str = ""  # "ULID:up,ULID:down" format
```

There is **no standalone vote tool**. You must create a new insight and include citation votes with it. Votes can also be applied for non-promoted grades (observation/bookkeeping) — see `record_insight.py:222-228`.

#### What columns are updated (store.py:346-350)

```python
col = "upvotes" if vote == "up" else "downvotes"
cur = self.local_conn.execute(
    f"UPDATE insights SET {col} = {col} + 1 WHERE id = ?",
    (cit_id,),
)
```

- Simple `+1` increment on `upvotes` or `downvotes` column.
- **Only operates on local.db** — `apply_citations` checks `_has_local_db()` (line 338) and only updates `self.local_conn`. Builtin insights cannot receive votes.

#### No duplicate prevention

There is **no deduplication**. The same agent can vote on the same insight multiple times, inflating counts.

#### Votes do NOT affect status

Vote counts never trigger a status change. There is no threshold where accumulated downvotes change status to `under_review` or `deprecated`. Votes are purely informational.

### 1.5 Status in Search & List

#### search_knowledge (search_knowledge.py + store.py:528-571)

**Visibility**: Both `_fts_search` and `_scope_search` filter:
```sql
i.status IN ('active', 'under_review')
```

This means:
- `active` — **visible**
- `under_review` — **visible** (same ranking as active)
- `deprecated` (if it existed) — **invisible**
- Any other status value — **invisible**

**Fields returned** (search_knowledge.py:59-78):
- `id`, `grade`, `scope_*` (4 fields), `content` (truncated 300 chars), `confidence`, `tags`, `source_type`, `upvotes`, `downvotes`, `metadata`, `source_calculation`
- `contradiction_count` — included **only if > 0** (line 75-77)
- **`status` is NOT returned** — agents cannot see whether an insight is active or under_review
- **No status filter parameter** — agents cannot filter by status

**Ranking**: `under_review` insights receive **identical ranking** to active insights. There is no penalty in the trust-weighted BM25 formula for being under review.

#### list_insights (list_insights.py)

**Mode 'recent'** → calls `store.list_by_grade()` (store.py:291):
```sql
WHERE grade = ? AND status IN ('active', 'under_review')
```
- `active` and `under_review` visible; deprecated invisible.

**Mode 'pending'** → calls `store.list_pending()` (store.py:437):
```sql
WHERE grade = ?
```
- **NO status filter** — would return deprecated insights if they existed.

**Fields returned** (list_insights.py:57-68, 91-102):
- `id`, `grade`, `content` (full), `tags`, `created_at`, `upvotes`, `downvotes`, `metadata`, `source_calculation`
- **`status` is NOT returned**
- **`contradiction_count` is NOT returned**
- **No `status` filter parameter**

### 1.6 Other Status Consumers

#### Exhaustive grep of status-related code in `src/qmatsuite/mcp/`

| File | Line(s) | Access | Detail |
|------|---------|--------|--------|
| `schema.py` | 29 | DDL | `status TEXT DEFAULT 'active'` |
| `schema.py` | 69 | DDL | `CREATE INDEX ... ON insights(status)` |
| `store.py` | 168 | READ | `WHERE status = 'active'` (count) |
| `store.py` | 253 | WRITE | `'active'` (INSERT new insight) |
| `store.py` | 291 | READ | `status IN ('active', 'under_review')` (list_by_grade) |
| `store.py` | 437 | READ | no filter (list_pending) |
| `store.py` | 484 | READ | `status = 'active'` (contradiction matching) |
| `store.py` | 503 | WRITE | `status = 'under_review'` (contradiction threshold) |
| `store.py` | 552 | READ | `status IN ('active', 'under_review')` (fts_search) |
| `store.py` | 586 | READ | `status IN ('active', 'under_review')` (scope_search) |
| `build_builtin.py` | 75 | WRITE | `'active'` (INSERT builtin entries) |

**No other code reads or writes `status`.** The `superseded_by`, `deprecated_reason`, and `merged_into` columns appear **only** in `schema.py` DDL (lines 30-32) and are referenced by zero other files.

---

## 2. Current Database State

### 2.1 Live Databases

Four knowledge databases exist at runtime:

| Path | Type | Insights | Status |
|------|------|----------|--------|
| `.qmatsuite/knowledge/builtin.db` (project) | builtin | 45 | all `active` |
| `~/.qmatsuite/knowledge/builtin.db` (user) | builtin | 45 | all `active` |
| `.qmatsuite/knowledge/local.db` (project) | local | 15 | 9 active, 6 under_review |
| `~/.qmatsuite/knowledge/local.db` (user) | local | 0 | empty |

**Path resolution**: `get_qmatsuite_home_root()` checks `QMATSUITE_HOME` env → dev-mode `<repo>/.qmatsuite` → Electron app-data → fallback `~/.qmatsuite`.

### 2.2 Project local.db Detail

```
id                          status         contradiction_count  upvotes  downvotes
01KK2AV4YG...               active         0                   0        0
01KK2Y9S50...               active         0                   0        0
01KK2YA5TT...               under_review   3                   0        0
01KK2YAGYG...               under_review   3                   0        0
01KK2YAXW7...               under_review   3                   0        0
01KK2YB449...               under_review   3                   0        0
01KK3PGAMW...               under_review   3                   0        0
01KK3PGF32...               active         2                   0        0
01KK3PGP2Y...               under_review   3                   0        0
01KK4FEV9A...               active         1                   0        0
01KK4FEYAB...               active         0                   0        0
01KK4FF34X...               active         0                   0        0
01KK6DH9GQ...               active         2                   0        0
01KK6DHDZ4...               active         1                   0        0
01KK6DHJHR...               active         0                   0        0
```

**Observations**:
- 6 of 15 (40%) insights are `under_review` — all with `contradiction_count=3` (exactly at threshold)
- 0 upvotes, 0 downvotes on every row — citation system has never been used
- `superseded_by`, `deprecated_reason`, `merged_into` = NULL on every row
- No insights with `status='deprecated'` or any other status value

### 2.3 Experiment Snapshot Databases

Experiment databases in `.tmp/` (gitignored) show the pattern at scale:

| Experiment | Total | Active | Under Review | % Flagged |
|-----------|-------|--------|-------------|-----------|
| Chain A (task3) | 28 | 8 | 20 | 71% |
| exp2 run_01 output | 10 | 6 | 4 | 40% |
| exp2 run_02 output | 9 | 7 | 2 | 22% |
| exp2 run_03 input | 9 | 7 | 2 | 22% |

Chain A's 71% flagging rate confirms the false-positive problem: scope-only matching without compound/tag discrimination causes cascading contradictions.

### 2.4 Builtin DB

All 45 builtin insights are `active` with `contradiction_count=0`, `upvotes=0`, `downvotes=0`. None have ever been flagged. This is because builtin entries use wildcard scopes (e.g., `scope_engine='qe'`) and builtin.db is rebuilt from scratch by `build_builtin_db()`.

---

## 3. Design Analysis

### 3.1 Contradiction Detection: Keep, Modify, or Remove?

#### What it does well
- **Automatic**: fires on every `add()` without agent action
- **Zero-config**: no setup needed, works out of the box
- **Surfaces potential conflicts**: the `under_review` flag prevents agents from blindly trusting stale insights

#### What it does poorly
- **High false-positive rate**: 40-71% of insights get flagged (§2.3), mostly false
- **No semantic understanding**: scope-only matching treats "QE SCF converges faster with mixing_beta=0.3 for Fe" and "QE SCF requires ecutwfc=60 for Si" as contradictory because both share `scope_engine='qe', scope_workflow='scf'`
- **One-way ratchet**: once flagged, never returns to active — no code path clears `under_review`
- **Monotonic contradiction_count**: only increases, never decreases, never resets
- **Flags old entries, not new**: the existing insight gets flagged, not the one that may actually be wrong
- **Operates on builtin.db**: can flag curated builtin insights, which makes no sense (they're rebuilt from source)
- **No agent visibility**: `status` is not returned by search or list tools, so the agent can't even see the flag

#### Recommendation: **(b) Simplify — count only, never auto-change status**

Rationale:
1. With `review_insight`, status changes become **agent-driven with reasoning** rather than heuristic-driven with false positives
2. The `contradiction_count` metric is still useful as a **signal** for the review agent to investigate — it just shouldn't auto-change status
3. Removing the auto-status-change line (store.py:503) is a 1-line change
4. The review agent can use contradiction_count as one input among many (votes, age, content analysis) when deciding whether to deprecate

The alternative (d) "add compound/tags to matching" would reduce false positives but adds complexity and doesn't solve the fundamental problem: syntactic matching can't assess semantic contradiction.

### 3.2 Status Values and State Machine

#### Can we use new values without schema migration?

**Yes.** The `status` column is `TEXT DEFAULT 'active'` with **no CHECK constraint**. Any string value can be stored. No migration needed — just INSERT/UPDATE with the new value.

#### Proposed status values

| Status | Meaning | Set by |
|--------|---------|--------|
| `active` | Live, searchable, trustworthy | `add()` (initial), `review_insight` (re-confirm) |
| `under_review` | Flagged for review, still searchable | `_detect_contradictions` (automatic, if kept) |
| `deprecated` | Rejected/outdated, invisible to search | `review_insight` (explicit deprecation) |

**Removed from consideration**:
- `confirmed` — not needed as a distinct status. A review that confirms just keeps `active` and optionally bumps `upvotes` or sets `last_validated`.
- `superseded` — use `deprecated` + populate `superseded_by` with the replacement ID.
- `revised` — use `deprecated` + `superseded_by` pointing to the new version.

#### State Machine

```
                    add()
                      │
                      ▼
                   active ──────────────────────────────────────┐
                      │                                         │
        _detect_contradictions()                    review_insight(action='deprecate')
        (count >= threshold)                                    │
                      │                                         ▼
                      ▼                                    deprecated
                 under_review ──────────────────────────────────┤
                      │                                         │
        review_insight(action='confirm')            review_insight(action='deprecate')
                      │
                      ▼
                   active
```

Key transitions:
- `active → under_review` — automatic (contradiction detection, if kept)
- `active → deprecated` — explicit (review_insight)
- `under_review → active` — explicit (review_insight confirms the insight is valid)
- `under_review → deprecated` — explicit (review_insight deprecates after review)
- `deprecated → ???` — terminal state, no transitions back (require creating a new insight instead)

### 3.3 Who Changes Status (Authority Model)

**Current reality**: Only `_detect_contradictions` changes status (store.py:503). `record_insight` never directly changes another insight's status — it only triggers contradiction detection as a side effect of `add()`.

**Proposed authority model**:

| Actor | Can change status? | Mechanism |
|-------|-------------------|-----------|
| `record_insight` | No (except via contradiction side-effect) | Unchanged |
| `_detect_contradictions` | Yes: `active → under_review` | Automatic, threshold-based |
| `review_insight` (new) | Yes: any → any (except deprecated → active) | Explicit, with reasoning |
| `build_builtin_db` | No (always inserts fresh with `active`) | Unchanged |

### 3.4 Votes vs Reviews

#### Current vote system limitations
- Never been used (0 upvotes, 0 downvotes across all databases)
- Requires creating a new insight to vote — no standalone vote mechanism
- No duplicate prevention — same agent can vote unlimited times
- No impact on status or ranking

#### Should votes influence status?

**No.** Keep votes as lightweight informational signals. Reasons:
1. Without duplicate prevention, vote counts are unreliable
2. Downvotes reflect "this wasn't helpful for my specific case" not "this is incorrect"
3. The review agent can consider vote counts as one input in its judgment
4. Status changes should require explicit reasoning (from review_insight)

#### Should search ranking use votes?

**Yes, optionally.** A simple boost/penalty in the trust-weighted ranking:
```python
vote_factor = 1.0 + 0.1 * (upvotes - downvotes)  # Mild adjustment
score = cw * raw_rank * tw * max(vote_factor, 0.1)
```

This is a small enhancement that gives votes practical effect without making them authoritative.

### 3.5 Review Agent Discoverability

#### What the review agent needs

1. **List ALL insights regardless of status** — including `deprecated`, `under_review`
2. **Filter by status** — "show me all under_review insights"
3. **See full metadata** — status, contradiction_count, upvotes, downvotes, tags, references
4. **See the underlying calculations** — source_calculation links
5. **Take action** — confirm, deprecate, revise

#### What's currently missing

| Need | Available? | Gap |
|------|-----------|-----|
| See `status` field | No | Not returned by search or list |
| Filter by status | No | No status parameter on list_insights or search_knowledge |
| See `contradiction_count` | Partially | search_knowledge returns it (if >0), list_insights does not |
| See deprecated insights | No | Filtered out by `status IN ('active', 'under_review')` |
| Change status | No | No tool exists |
| Provide deprecation reasoning | No | `deprecated_reason` column exists but no tool writes it |

#### Minimal changes needed for review agent discoverability

1. **`list_insights`**: Add optional `status` parameter (default: `'active,under_review'`), return `status` and `contradiction_count` in response items
2. **`search_knowledge`**: Return `status` in response items, optionally allow `status` filter
3. **New `review_insight` tool**: Confirm/deprecate/revise with reasoning

---

## 4. Gap Analysis

### 4.1 Mechanism Summary Table

| Mechanism | Exists? | Changes status? | Changes what columns? | Visible in search? | Visible in list? |
|-----------|---------|----------------|-----------------------|--------------------|--------------------|
| Initial creation (`add()`) | Yes | Sets initial `active` | status, contradiction_count, upvotes | N/A (new entry) | N/A (new entry) |
| Contradiction detection | Yes | `active → under_review` | contradiction_count (+1), status (at threshold) | No — status not returned | No — status not returned |
| Up/down votes (citations) | Yes | No | upvotes (+1) or downvotes (+1) | Yes — upvotes, downvotes returned | Yes — upvotes, downvotes returned |
| `review_insight` | **NOT YET** | Would change status | status, deprecated_reason, superseded_by, last_validated | N/A | N/A |
| `superseded_by` column | Schema only | Never written | — | N/A | N/A |
| `deprecated_reason` column | Schema only | Never written | — | N/A | N/A |
| `merged_into` column | Schema only | Never written | — | N/A | N/A |

### 4.2 Prerequisites for review_insight

Before implementing `review_insight`, these changes must be made:

#### Must-have

1. **`list_insights` must expose `status` and `contradiction_count`** in response items
   - File: `src/qmatsuite/mcp/tools/list_insights.py:57-68` and `:91-102`
   - Add `"status": r["status"]` and `"contradiction_count": r.get("contradiction_count", 0)` to both item dicts

2. **`list_insights` must accept a `status` filter parameter**
   - File: `src/qmatsuite/mcp/tools/list_insights.py:12` (signature)
   - New parameter: `status: str = ""` (comma-separated, e.g., `"under_review"` or `"active,under_review,deprecated"`)
   - Both modes (recent/pending) must respect this filter

3. **`store.list_by_grade` must support status filtering including `deprecated`**
   - File: `src/qmatsuite/mcp/knowledge/store.py:287-301`
   - Change the hardcoded `status IN ('active', 'under_review')` to accept a parameter

4. **`store.list_pending` must add a status filter**
   - File: `src/qmatsuite/mcp/knowledge/store.py:423-450`
   - Currently has NO status filter — must add one (default: exclude deprecated)

5. **`search_knowledge` must expose `status` in response items**
   - File: `src/qmatsuite/mcp/tools/search_knowledge.py:59-78`
   - Add `"status": r["status"]` to the item dict

6. **`store` needs an `update_status()` method** for review_insight to call
   - File: `src/qmatsuite/mcp/knowledge/store.py` (new method)
   - Must validate target exists, enforce allowed transitions, write `deprecated_reason`, `superseded_by`, `last_validated`, and `updated_at`

#### Nice-to-have

7. **Contradiction detection simplification** — remove auto-status-change
   - File: `src/qmatsuite/mcp/knowledge/store.py:502-503`
   - Remove or comment out the `, status = 'under_review'` portion

8. **Search ranking penalty for `under_review`**
   - File: `src/qmatsuite/mcp/knowledge/store.py:601-618`
   - Add a small ranking penalty (e.g., 0.8× multiplier) for under_review insights

9. **Vote-based ranking adjustment**
   - File: `src/qmatsuite/mcp/knowledge/store.py:601-618`
   - Add mild upvote/downvote factor to trust-weighted scoring

### 4.3 Minimal Implementation Proposal

#### 1. review_insight tool

**New file**: `src/qmatsuite/mcp/tools/review_insight.py`

```python
@mcp.tool
def review_insight(
    insight_id: str,        # Full ULID or short prefix
    action: str,            # "confirm" | "deprecate" | "revise"
    reasoning: str = "",    # Required for deprecate/revise, optional for confirm
    replacement_id: str = "",  # For revise: the new insight that supersedes this one
) -> dict:
```

**Actions**:
- `confirm`: Set `status='active'`, update `last_validated`, reset `contradiction_count` to 0. Used to clear `under_review` flag after review.
- `deprecate`: Set `status='deprecated'`, write `deprecated_reason`, update `updated_at`. Reasoning required.
- `revise`: Set `status='deprecated'`, write `deprecated_reason`, set `superseded_by=replacement_id`, update `updated_at`. The agent should first `record_insight` with the corrected version, then `review_insight(action='revise')` on the old one pointing to the new.

**Columns used** (all existing, no schema change):
- `status` — set to `'active'` or `'deprecated'`
- `deprecated_reason` — written on deprecate/revise
- `superseded_by` — written on revise
- `last_validated` — updated on confirm
- `updated_at` — always updated
- `contradiction_count` — reset to 0 on confirm

#### 2. Status values

Final set: `active`, `under_review`, `deprecated`. Three values, no schema change needed.

#### 3. Contradiction detection

**Simplify**: Remove the auto-status-change (store.py:503). Keep counting contradictions as a signal.

**Change** (store.py:499-503):
```python
# Before:
update_sql = "UPDATE insights SET contradiction_count = ?"
if new_count >= _CONTRADICTION_THRESHOLD:
    update_sql += ", status = 'under_review'"

# After:
update_sql = "UPDATE insights SET contradiction_count = ?"
# Status changes are handled by review_insight, not automatic detection
```

#### 4. Search ranking

Add status-based ranking factor in `_apply_trust_ranking` (store.py:601-618):
```python
status_factor = 0.8 if r.get("status") == "under_review" else 1.0
r["_score"] = cw * raw_rank * tw * status_factor
```

#### 5. List filtering

Modify `list_insights` to accept `status` parameter:
- Default: `"active,under_review"` (backward compatible)
- Review agent uses: `"under_review"` or `"active,under_review,deprecated"`

Modify `list_by_grade` and `list_pending` in store.py to accept a `statuses` list parameter.

#### 6. Vote interaction

No change to vote mechanism. Votes remain informational. The review agent sees vote counts when reviewing insights and may factor them into its judgment, but votes never trigger automatic status changes.

---

## Appendix: All Code Locations

### status — reads and writes

| File | Line | R/W | Code |
|------|------|-----|------|
| `knowledge/schema.py` | 29 | DDL | `status TEXT DEFAULT 'active'` |
| `knowledge/schema.py` | 69 | DDL | `CREATE INDEX ... ON insights(status)` |
| `knowledge/store.py` | 168 | R | `WHERE status = 'active'` |
| `knowledge/store.py` | 253 | W | `VALUES (..., 'active', ...)` |
| `knowledge/store.py` | 291 | R | `status IN ('active', 'under_review')` |
| `knowledge/store.py` | 437 | R | (no status filter — bug) |
| `knowledge/store.py` | 484 | R | `status = 'active'` |
| `knowledge/store.py` | 503 | W | `status = 'under_review'` |
| `knowledge/store.py` | 552 | R | `status IN ('active', 'under_review')` |
| `knowledge/store.py` | 586 | R | `status IN ('active', 'under_review')` |
| `knowledge/build_builtin.py` | 75 | W | `'active'` |

### contradiction_count — reads and writes

| File | Line | R/W | Code |
|------|------|-----|------|
| `knowledge/schema.py` | 34 | DDL | `contradiction_count INTEGER DEFAULT 0` |
| `knowledge/store.py` | 253 | W | `0` (INSERT initial) |
| `knowledge/store.py` | 496-497 | R | `old_count = row[1]; new_count = old_count + 1` |
| `knowledge/store.py` | 499 | W | `SET contradiction_count = ?` |
| `knowledge/build_builtin.py` | 75 | W | `0` |
| `tools/search_knowledge.py` | 75-77 | R | `r.get("contradiction_count", 0)` (returned if >0) |

### upvotes / downvotes — reads and writes

| File | Line | R/W | Code |
|------|------|-----|------|
| `knowledge/schema.py` | 35-36 | DDL | `upvotes INTEGER DEFAULT 0`, `downvotes INTEGER DEFAULT 0` |
| `knowledge/store.py` | 253 | W | `0` (INSERT initial, upvotes only — downvotes gets DEFAULT) |
| `knowledge/store.py` | 348 | W | `SET {col} = {col} + 1` |
| `tools/search_knowledge.py` | 71-72 | R | `r.get("upvotes", 0)`, `r.get("downvotes", 0)` |
| `tools/list_insights.py` | 63-64, 97-98 | R | `r.get("upvotes", 0)`, `r.get("downvotes", 0)` |

### superseded_by / deprecated_reason / merged_into — DEAD COLUMNS

| File | Line | R/W | Code |
|------|------|-----|------|
| `knowledge/schema.py` | 30 | DDL | `superseded_by TEXT` |
| `knowledge/schema.py` | 31 | DDL | `deprecated_reason TEXT` |
| `knowledge/schema.py` | 32 | DDL | `merged_into TEXT` |
| `knowledge/schema.py` | 40 | DDL | `FOREIGN KEY (superseded_by) REFERENCES insights(id)` |

**Zero other references in the entire codebase.** These columns exist in the schema but are never read, written, or queried by any code. They were designed for `review_insight` but never implemented.

### Files that will need changes for review_insight

| File | Change Type | Scope |
|------|------------|-------|
| `tools/review_insight.py` | **NEW FILE** | ~80 lines — tool definition |
| `knowledge/store.py` | **MODIFY** | New `update_status()` method (~40 lines), modify `_detect_contradictions` (1 line), modify `list_by_grade` (status param), modify `list_pending` (add status filter) |
| `tools/list_insights.py` | **MODIFY** | Add `status` parameter, return `status` and `contradiction_count` |
| `tools/search_knowledge.py` | **MODIFY** | Return `status` in items |
