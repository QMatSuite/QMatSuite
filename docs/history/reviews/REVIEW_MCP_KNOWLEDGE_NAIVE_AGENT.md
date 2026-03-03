# MCP Knowledge System — Naive Agent Review

Date: 2026-03-03
Reviewer: Claude Code
Spec: docs/design/MCP_KNOWLEDGE_SYSTEM_SPEC.md
Code base: post-R11

## Methodology

Walked two complete scenarios against **actual code** (not the spec). Read every
file in the knowledge tool pipeline: `app.py`, `search_knowledge.py`,
`list_insights.py`, `record_insight.py`, `record_intent.py`, `store.py`,
`server.py`, `schema.py`, `insight_record.py`, `envelope.py`,
`get_results_summary.py`, and the full spec. Traced every dict construction,
every context_hint, every error path.

---

## Scenario 1: First-Time Agent, Empty Knowledge Base

**Start state**: local.db doesn't exist, builtin.db populated (QMS_KNOWLEDGE_BUILTIN=1).
**Task**: "Compute SCF convergence, lattice constant, and band structure of GaAs
using Quantum ESPRESSO."

### Step 0: Boot — What the Agent Sees

**Preamble** (exact text from `app.py:14-42`):

```
You are a computational materials science research assistant powered by QMatSuite.

You have a 5-level knowledge hierarchy for recording insights during a session:
  1. bookkeeping — mechanical notes (journal only, not searchable)
  2. observation — preliminary observations (journal only)
  3. finding — verified, reproducible conclusions (promoted to knowledge DB)
  4. pattern — synthesis of multiple findings into a recurring theme (promoted)
  5. principle — high-level rule distilled from patterns (promoted)

Key tools for knowledge management:
  - search_knowledge: BM25 full-text search over curated + session knowledge.
  - record_insight: Record insights at any grade. Findings, patterns, and
    principles are promoted into the searchable knowledge database.
  - list_insights: Review accumulated findings/patterns/principles by grade
    for synthesis.

Workflow: record observations → consolidate into findings → synthesize patterns
(with references to findings) → distill principles (with references to patterns).

Before starting new calculations:
  - Search the knowledge base for relevant prior findings
  - Check if similar compounds or workflows have been studied before

When recording insights, you can cite prior knowledge that influenced your
approach using the 'citations' field (format: "ID:up,ID:down"). Rate 'up' if
the knowledge was accurate and helpful, 'down' if it was misleading or
inapplicable.
```

**Findings**:

1. **Preamble does tell agent to search first.** Lines 34-36 ("Before starting
   new calculations...") are clear and well-placed (R10).

2. **Grade hierarchy is clear.** The 5-level list with one-line descriptions
   gives enough to start.

3. **Citations are explained** but `upvotes`/`downvotes` are never mentioned.
   Agent sees these fields in search results but has no context for what they
   mean. The preamble explains the *input* format ("ID:up,ID:down") but not
   that votes accumulate as `upvotes`/`downvotes` counters visible in search.

4. **`record_intent` is NOT mentioned in the preamble.** Not in the "Key tools"
   list, not in the "Workflow" line. The designed flow (spec §5) is SEARCH →
   PLAN → EXECUTE → RECORD, but the preamble only conveys SEARCH → RECORD.
   A naive agent will never discover `record_intent` unless it independently
   reads the tool description. See **G3**.

5. **`get_results_summary` does NOT suggest recording insights.** Its
   context_hint (`get_results_summary.py:95-101`) says:
   ```
   Use inspect_calculation(calc_ulid='...') for parameter details.
   ```
   For relax workflows it adds a `promote_structure` suggestion. No mention
   of knowledge recording. The SEARCH→EXECUTE→**???**→RECORD chain is broken
   at the EXECUTE→RECORD handoff. See **G4**.

**Tool descriptions** (from `@mcp.tool` docstrings — what MCP exposes via
`list_tools`):

| Tool | Description (first line of docstring) |
|------|---------------------------------------|
| `search_knowledge` | "Search the QMatSuite knowledge base for DFT best practices and error recovery." |
| `record_insight` | "Record an agent-authored insight into the QMatSuite knowledge base." |
| `record_intent` | "Record an agent's intent in the provenance journal." |
| `list_insights` | "List insights by grade for review or synthesis." |

The descriptions are adequate. `record_intent`'s description makes clear it's
journal-only, but nothing tells the agent *when* to use it.

### Step 1: Search

Reasonable first query: `search_knowledge(query="GaAs SCF convergence band structure", engine="qe")`

**What happens in code** (`search_knowledge.py` + `store.py`):

1. `_sanitize_fts_query("GaAs SCF convergence band structure")` → strips FTS5
   reserved words, joins with OR → `"GaAs OR SCF OR convergence OR band OR structure"`
2. local.db doesn't exist → `_has_local_db()` returns False → `local_results = []`
3. builtin.db searched via FTS5 → `builtin_results` populated
4. `_merge_with_reserved_slots([], builtin_results, 10)` → `local_take = []`,
   `remaining = 10`, result = `builtin_results[:10]`
5. Each result item built in `search_knowledge.py:57-76`:

```python
{
    "id": r["id"][:14],           # 14-char short ID
    "grade": r["grade"],
    "scope_engine": r["scope_engine"],
    "scope_workflow": r["scope_workflow"],
    "scope_system_type": r["scope_system_type"],
    "scope_method": r["scope_method"],
    "content": r["content"][:300] + ("..." if len(r["content"]) > 300 else ""),
    "confidence": r["confidence"],
    "tags": r["tags"],             # ← JSON string, NOT parsed list
    "source_type": r["source_type"],
    "upvotes": r.get("upvotes", 0),
    "downvotes": r.get("downvotes", 0),
    "metadata": json.loads(r["metadata"]) if r.get("metadata") else {},
}
```

6. Nudge check: `_maybe_nudge(tone="soft")` → `_count_pending("pattern")`:
   `_has_local_db()` is False → returns (0, None). Same for findings. No nudge.
   Correct.

7. Context hint: `"Found N insight(s). Use these insights to inform your parameter choices with set_parameters or apply_preset."`

**Issues found**:

- **`tags` is a JSON string, not a list.** Agent sees
  `"tags": "[\"convergence\", \"scf\"]"` — a doubly-encoded string — alongside
  `"metadata": {"agent_model": "..."}` which IS parsed. Inconsistent. An agent
  trying to programmatically filter by tag would need to know to JSON.parse the
  string. See **G7**.

- **`source_type` distinguishes builtin vs local.** Agent can see
  `"source_type": "builtin"`. Clear enough.

- Agent sees `upvotes: 0, downvotes: 0` on all builtin results (builtin
  entries have no vote history). No confusion here.

### Step 2: Plan — record_intent?

The preamble says:
```
Workflow: record observations → consolidate into findings → synthesize patterns
```

This does NOT mention recording intent. A reasonable agent would skip straight
from searching to creating the calculation. `record_intent` is effectively
invisible in the designed flow. See **G3**.

### Step 3: Execute

Agent creates calculation, runs it, calls `get_results_summary`. The
context_hint says `"Use inspect_calculation(calc_ulid='...') for parameter details."`

No mention of recording insights. No nudge toward the knowledge system.
See **G4**.

### Step 4: Record

Agent wants to record what it learned. It calls:
```
record_insight(
    content="GaAs SCF with ecutwfc=80 Ry converges to <0.1 meV...",
    grade="finding",
    scope_engine="qe",
    scope_workflow="scf",
    tags="GaAs,convergence,scf",
    citations="01HXYZ12345678:up"   # citing a useful builtin insight
)
```

**Citation of builtin insight — the broken path**:

1. `rsplit(":", 1)` on `"01HXYZ12345678:up"` → `["01HXYZ12345678", "up"]`. OK.
2. `resolve_short_id("01HXYZ12345678")` (`record_insight.py:139`) queries
   **local.db only** (`store.py:309-321`). Builtin IDs are NOT in local.db.
   → `ValueError: "No insight found matching prefix '01HXYZ12345678'"`
3. Caught by `except (ValueError, Exception): pass` → `cit_id` stays as the
   original 14-char string.
4. `apply_citations([{"id": "01HXYZ12345678", "vote": "up"}])` (`store.py:341-361`):
   `UPDATE insights SET upvotes = upvotes + 1 WHERE id = ?` on local.db.
   No row matches → `rowcount = 0` → skipped.
5. **Vote silently dropped.**
6. But `citation_summary` is built from `parsed_citations` (`record_insight.py:227-230`):
   ```python
   n_up = sum(1 for c in parsed_citations if c["vote"] == "up")
   citation_summary = f"Cited {len(parsed_citations)} insight(s) ({n_up} helpful, {n_down} not)"
   ```
   → Agent sees: **"Cited 1 insight(s) (1 helpful, 0 not)"** — implies success.
7. `apply_citations()` returns `{"applied_up": 0, "skipped": 1}` but this
   return value is **never checked** (`record_insight.py:214` and `:224`).

**Result**: Agent tries to upvote a builtin insight. Vote is silently dropped.
Agent is told it was successful. See **G1**.

**Nudge**: 1 finding. `_count_pending("finding")` = 1. 1 < 8. No nudge. Correct.

**Response data** (`record_insight.py:263-270`):
```python
{
    "insight_id": insight_id[:14],      # 14-char short ID
    "journal_entry_ulid": "...",        # full ULID
    "promoted": True,
    "journal_recorded": True,
    "grade": "finding",
    "contradictions": [],
    "citation_summary": "Cited 1 insight(s) (1 helpful, 0 not)"
}
```

Note: `journal_entry_ulid` is a full 26-char ULID while `insight_id` is 14-char.
Minor inconsistency but not confusing since they're different ID types.

### Step 5: Convergence Series (findings 2-8)

Agent runs 7 more SCF calculations at different ecutwfc values, recording a
finding after each. At finding #8:

- `_count_pending("finding")` (`store.py:428-449`): No patterns exist. Last
  higher = None. `COALESCE(NULL, '1970-01-01')` → counts all findings → 8.
  8 >= 8 → nudge fires.

**Strong nudge text** (exact, from `store.py:492-498`):
```
📊 Knowledge synthesis checkpoint: 8 new findings since last pattern synthesis.
Synthesizing patterns is part of your research program. Use
list_insights(grade='finding') to review, then record_insight(grade='pattern',
references=[...]). It's okay to skip if findings don't yet show a clear pattern.
```

- Nudge tells agent to call `list_insights(grade='finding')` — default mode is
  `"pending"`, which is correct.
- Nudge does NOT explicitly mention `mode="pending"` but the default is
  correct. Fine.
- Nudge format is clear and actionable. The "It's okay to skip" gives the agent
  permission to defer. Good design.

---

## Scenario 2: Session 12, Rich Knowledge Base

**Start state**: local.db has 10 findings, 1 pattern (referencing findings 1-8).
Findings 9 and 10 are "pending" (created after the pattern). Builtin enabled.
**Task**: "Compute lattice constant of InSb with spin-orbit coupling."

### Step 0: Search

Agent searches: `search_knowledge(query="InSb lattice constant spin-orbit")`

Assume finding #4 is about InSb (upvotes=2, downvotes=1 from prior sessions).

**What happens**:

1. local.db has 11 entries (10 findings + 1 pattern). FTS5 ranks them by BM25
   against "InSb OR lattice OR constant OR spin OR orbit".
2. The 11 local entries compete for 3 reserved slots. Top 3 by BM25 score
   appear as `local_take`.
3. If the InSb finding matches the query, it appears. If the pattern's content
   mentions InSb, it can also appear. Otherwise only findings with matching
   keywords appear.
4. `builtin_results` fill the remaining 7 slots.

**Agent sees for the InSb finding**:
```json
{
    "id": "01HXYZ12345678",
    "grade": "finding",
    "upvotes": 2,
    "downvotes": 1,
    "source_type": "local",
    "content": "InSb with SOC requires... (truncated to 300 chars)",
    ...
}
```

- The downvote signals that someone found this knowledge misleading before.
  Nothing in the system *explains* this to the agent — the preamble only
  explains the citation *input* format, not what accumulated votes mean.
  An agent can likely infer from field names. See **G6**.

**Nudge check**: `_count_pending("finding")` = 2 (findings 9 and 10). 2 < 8.
No nudge. Correct.

### Step 1: Execute + Record

Agent computes, records finding #11 about InSb SOC. Cites the prior InSb
finding: `citations="01HXYZ12345678:up"`.

1. `resolve_short_id("01HXYZ12345678")` → queries local.db → finds exactly
   1 match → returns full 26-char ULID. Works.
2. `apply_citations([{"id": "01FULL26CHARULID...", "vote": "up"}])` →
   `UPDATE insights SET upvotes = upvotes + 1 WHERE id = ?` → rowcount = 1 →
   upvotes goes from 2 to 3. Works correctly.
3. 3 pending findings now. Still < 8. No nudge. Correct.

### Step 2: Nudge Eventually Fires (session 15+)

After 8 pending findings (total ~18, pattern still only 1):

1. Strong nudge fires: `📊 Knowledge synthesis checkpoint: 8 new findings...`
2. Agent calls `list_insights(grade='finding')`. Default mode = "pending".
3. `list_pending("finding")` → finds last pattern's `created_at` → returns
   only findings after that timestamp → 8 pending findings.
4. Full content returned (R9). `upvotes`/`downvotes` visible (R11). `metadata`
   parsed from JSON. All good.
5. Context hint (`list_insights.py:96-105`):
   ```
   Showing 8 of 8 pending finding(s) (since last pattern synthesis at 2026-03-02T...)
   Synthesize recurring themes into a pattern with record_insight(grade='pattern', references=[...]).
   ```
   Clear and actionable.

6. Agent synthesizes pattern. Passes 8 finding IDs (14-char each) as references.
   `resolve_short_id()` resolves all to full ULIDs. Stored in
   `metadata.references` as full 26-char ULIDs. Works.

7. After recording new pattern:
   - `_count_pending("finding")` = 0 (new pattern's timestamp is after all 8).
   - `_count_pending("pattern")` = 2 (1 old + 1 new, no principles). 2 < 3.
   - No L5 nudge. Correct.

### Step 3: L5 Synthesis

After 3 total patterns, L5 nudge fires:
```
📊 Knowledge synthesis checkpoint: 3 new patterns since last principle
synthesis...
```

Agent calls `list_insights(grade='pattern', mode='pending')`.

**Pending mode for patterns**: `_count_pending("pattern")` looks for last
principle's `created_at`. No principles → `COALESCE(NULL, '1970-01-01')` →
all 3 patterns are "pending". Returns all 3. Correct.

**If agent forgets references for principle**:
`record_insight.py:102-110`:
```python
return make_error(
    error_type="VALIDATION_ERROR",
    message=f"grade 'principle' requires at least one reference ID",
    context_hint=(
        "Use list_insights(grade='finding') to review findings, "
        "then pass their IDs as references."
    ),
)
```

**BUG**: The `context_hint` says `grade='finding'` for ALL missing-reference
errors, including `grade='principle'`. For a principle, it should say
`grade='pattern'`. See **G2**.

---

## Code-Level Checks

### A. Builtin Citation Edge Case

**Traced above in Scenario 1, Step 4.**

- `resolve_short_id()` only queries local.db → ValueError for builtin IDs
- `apply_citations()` UPDATE on local.db → rowcount 0 → silently skipped
- `citation_summary` counts **attempted**, not applied → misleading message
- `apply_citations()` return value (`{"applied_up": 0, "skipped": 1}`) is
  never used in `record_insight.py`

**Impact**: Agent trusts a "1 helpful" confirmation that never happened. If
the agent builds reasoning chains based on citation feedback, this is
misleading. **FRICTION**.

### B. Short ID in Nudge Messages

Nudge messages in `_maybe_nudge()` (`store.py:468-498`) do NOT contain any
insight IDs. They reference tool calls (`list_insights(grade='finding')`) but
no IDs. **No issue.**

### C. Tags as JSON String

In `search_knowledge.py:67`:
```python
"tags": r["tags"],
```
In `list_insights.py:52` and `:84`:
```python
"tags": r["tags"],
```

Tags are stored in SQLite as a JSON string: `'["convergence", "scf"]'`.
They are returned verbatim — a JSON-encoded string inside a JSON response.

Meanwhile, `metadata` IS parsed:
```python
"metadata": json.loads(r["metadata"]) if r.get("metadata") else {},
```

**Result**: Agent sees:
```json
{
    "tags": "[\"convergence\", \"scf\"]",
    "metadata": {"agent_model": "claude-opus-4-6"}
}
```

`tags` is a string while `metadata` is an object. Inconsistent. An LLM agent
will likely handle this fine (it can read both), but a programmatic consumer
would be confused. See **G7**.

### D. Empty Search Results

Agent searches with no results (weird query, empty DBs):

- `search_knowledge.py:83-84`:
  ```python
  hint = "No matching knowledge found. Try broader search terms or remove filters."
  ```
- Nudge still runs (`store.py:_maybe_nudge(tone="soft")`). If pending counts
  are below thresholds, no nudge appended. If above thresholds, nudge is
  appended to the "no results" hint. Slightly odd (nudge about synthesis
  when search returned nothing) but not harmful.
- Response: `{"query": "...", "results": [], "total_results": 0}`. Clear.

**No issue.**

### E. Mode Validation in list_insights

`list_insights.py:44`:
```python
if mode == "recent":
    ...
else:
    # pending mode (default)
    ...
```

Passing `mode="all"`, `mode="everything"`, or a typo like `mode="recnt"`
silently falls into the `else` branch (pending mode). No validation.

**Impact**: Agent gets pending results when it wanted recent results, with no
error. See **G8**.

### F. Compound Filter in list_insights

`store.py:520-522` (in `list_pending`) and `:294-296` (in `list_by_grade`):
```python
if compound:
    sql += " AND tags LIKE ?"
    params.append(f"%{compound}%")
```

- `compound="GaAs"` → `LIKE '%GaAs%'` → matches `["GaAs", "ZB"]`. Correct.
- `compound="Ga"` → `LIKE '%Ga%'` → matches "GaAs", "InGaAs", "GaN", etc.
  Substring matching, not exact element matching.

**Inherent LIKE limitation.** Not a blocker — agent should use specific compound
names. **INFO.**

### G. `_count_by_grade()` — Dead Code?

Grep across all source files: `_count_by_grade` appears ONLY in documentation
files (worklog, spec). It was **fully removed** from `store.py` during R1-R3
implementation. Not dead code — properly cleaned up. **No issue.**

### H. Knowledge Usage Tracking (user's question)

The system has no structured mechanism for tracking whether searched knowledge
was actually used by an agent in its reasoning. Specifically:

1. **`record_intent`** has `intent` (free text), `calc_ulid`, `tags`.
   No `knowledge_consulted` or `search_result_ids` field.

2. **Citations** (on `record_insight`) are the closest feedback mechanism,
   but they record "was it helpful?" *after* the fact, not "I'm using it now."

3. **No link from search → intent → calculation → finding.** An agent that
   searches, uses knowledge to set parameters, and records a finding has no
   structured way to trace: "insight X → caused parameter ecutwfc=60 → produced
   result Y → confirmed as finding Z."

4. The preamble's "Search... before starting calculations" and "cite prior
   knowledge" are temporally disconnected — search happens at the start,
   citation happens at the end, and nothing connects them.

See **G5**.

### I. Reference Grade Validation

`record_insight.py:101-110` enforces that pattern/principle grades REQUIRE
references, but does NOT validate that references are of the correct grade.
A principle could reference findings (skipping patterns), and the system would
accept it. This is arguably flexible by design. **INFO.**

---

## Gap Summary

| # | Gap | Severity | Location | Fix Complexity |
|---|-----|----------|----------|---------------|
| G1 | Builtin citation votes silently dropped; citation_summary says success | FRICTION | `record_insight.py:213-230`, `store.py:309-321` | Medium — need to either (a) resolve against builtin.db too, or (b) report actual applied count |
| G2 | Reference-required error always says `grade='finding'` even for `grade='principle'` | FRICTION | `record_insight.py:106-109` | Trivial — conditional hint text |
| G3 | `record_intent` not mentioned in preamble; agents won't discover it | FRICTION | `app.py:14-42` | Trivial — add to preamble |
| G4 | `get_results_summary` doesn't suggest recording insights | FRICTION | `get_results_summary.py:95-101` | Trivial — add context_hint |
| G5 | No structured link from search results → intent → calculation → insight | FRICTION | `record_intent.py` (missing fields), `record_insight.py` (no `knowledge_used`) | Medium — needs schema addition |
| G6 | Preamble doesn't explain what `upvotes`/`downvotes` counters mean to consumers | COSMETIC | `app.py:14-42` | Trivial — add one sentence |
| G7 | `tags` returned as JSON string while `metadata` is parsed object | COSMETIC | `search_knowledge.py:67`, `list_insights.py:52,84` | Trivial — `json.loads(r["tags"])` |
| G8 | `list_insights` mode parameter not validated; typos silently fall to pending | COSMETIC | `list_insights.py:44` | Trivial — validate mode |
| G9 | `list_insights` response doesn't include `mode` field | COSMETIC | `list_insights.py:67-74,112-119` | Trivial — add `"mode": mode` |

---

## Recommendations

Ordered by impact on agent success:

### Priority 1: Fix G2 (reference hint says wrong grade)

One-line fix. Currently a principle missing references is told to review
*findings*, not patterns. This would send an agent on the wrong path.

```python
# record_insight.py:106-109
grade_to_review = {"pattern": "finding", "principle": "pattern"}[grade]
context_hint=(
    f"Use list_insights(grade='{grade_to_review}') to review {grade_to_review}s, "
    "then pass their IDs as references."
)
```

### Priority 2: Fix G1 (builtin citation feedback)

Two options:
- **Option A**: Make `resolve_short_id()` also search builtin.db. Then
  `apply_citations()` could update builtin entries. But builtin.db is meant
  to be read-only. Voting on curated knowledge is questionable.
- **Option B** (recommended): Keep votes local-only, but make `citation_summary`
  report actual applied counts from `apply_citations()` return value, and add
  a note like "1 citation skipped (builtin insights not votable)".

### Priority 3: Fix G4 (get_results_summary → record hint)

Add to `get_results_summary.py:95`:
```python
hint += " Record what you learned with record_insight(grade='finding')."
```

This closes the EXECUTE→RECORD handoff gap. The full flow becomes:
preamble says "search first" → search results say "use these insights" →
results summary says "record what you learned" → record nudges say "synthesize."

### Priority 4: Fix G3 (record_intent visibility)

Add `record_intent` to preamble's "Key tools" list and mention it in the
workflow line. Consider whether it should also have a `knowledge_used` field
(G5) before adding it to the workflow.

### Priority 5: Fix G7, G8, G9 (cosmetic consistency)

- Parse `tags` to a list in search/list tool layers
- Validate `mode` parameter in `list_insights`
- Include `mode` in response dict

### Priority 6: Address G5 (knowledge traceability)

Longer-term. Options:
- Add `search_result_ids: str` to `record_intent` for structured capture
- Add `knowledge_consulted: str` to `record_insight` linking back to search
- Or accept that citation votes are "good enough" for now and defer to the
  architecture migration (A1, currently deferred as D11)

---

## What Works Well

For completeness, things that are correctly implemented:

- **Sliding window nudge** (R1): Correctly counts only findings since last
  pattern, not all-time. Prevents "nudge fatigue" in long-running projects.
- **Dual nudge** (R2): Both L3→L4 and L4→L5 can fire simultaneously. Tested.
- **Soft/strong tone** (R3): Search gets gentle nudge, record gets directive.
  Good UX calibration.
- **Stochastic gate** (R4): `QMS_NUDGE_PROBABILITY` allows suppression. Clean.
- **Pending mode** (R5): `list_insights` default shows only unsynthesized
  items. Exactly what a nudge-responding agent needs.
- **Pending count header** (R6): "Showing 8 of 12 pending findings (since last
  pattern synthesis at ...)" — gives agent context for how much work remains.
- **Short IDs** (R7+R8): 14-char IDs with prefix resolution. Agent ergonomics
  are good. Collision risk negligible (verified empirically at 14 chars).
- **No content truncation in list** (R9): Full content for synthesis review.
- **Search-before-calculate preamble** (R10): Clear instruction.
- **Vote visibility** (R11): `upvotes`/`downvotes` in search and list results.
- **Reserved slots**: 3 local results guaranteed in search. Good for ensuring
  the agent's own knowledge surfaces alongside builtins.
- **FTS5 sanitization**: Robust. Handles dashes, quotes, reserved words.
- **Contradiction detection**: Scope-aware, with review flagging at threshold 3.
- **Error messages**: Generally clear with actionable `context_hint` values.
