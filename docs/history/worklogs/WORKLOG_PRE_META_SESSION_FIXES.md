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

## Change 5: Dual-Mode Preamble

Replaced the single-workflow preamble in `src/qmatsuite/mcp/app.py` with a dual-mode structure:

- **CALCULATION MODE** — explicit step sequence for computing properties
- **KNOWLEDGE SYNTHESIS MODE** — explicit step sequence for reviewing/synthesizing findings into patterns/principles
- **WHEN TO RECORD vs REPORT** — guidance on synthesis threshold (chemical family/structural class vs premature 3-point patterns)
- Removed: citations section, bookkeeping/observation from grades list, nudge response instruction

**Tests updated** (`TestMCPInstructions`):
- `test_instructions_mention_all_grades` → `test_instructions_mention_core_grades` (only finding/pattern/principle required)
- `test_instructions_workflow` → checks CALCULATION MODE and KNOWLEDGE SYNTHESIS MODE headers
- `test_instructions_citation_semantics` → checks WHEN TO RECORD guidance
- `test_instructions_upvotes_downvotes` → checks "vote entries up or down" phrase

## Verification

```
746 passed (pre-meta session changes 1-4)
104 passed (test_knowledge_write.py, all changes including preamble)
```

12 nudge-related tests removed (was ~758 tests in MCP suite).

---

## Round 2: Pre-Experiment Behavioral Hints (M1-M6)

**Date:** 2026-03-06
**Ref:** `docs/history/reviews/REVIEW_MCP_PRE_EXPERIMENT_READINESS.md`

Pre-experiment review identified 6 behavioral gaps that would cause
experiments to produce thin, purely numerical knowledge. All gaps were in
context_hint text and preamble wording.

### Change M1: Record-Failure Prompt in Error Enrichment

**File:** `src/qmatsuite/mcp/error_enrichment.py`
Error hint now says "Consider recording this error...record_insight(grade='finding',...tags='error-recovery')" before suggesting fix+retry. Previously only said "fix and retry" — failures were never recorded.

### Change M2: Encourage Additional Insights After Recording

**File:** `src/qmatsuite/mcp/tools/record_insight.py`
Promoted-insight hint changed from "Insight recorded in knowledge base. Use search_knowledge() to verify it's findable." (dead-end termination signal) to "Insight recorded. If this session produced additional findings (methodology lessons, error workarounds, parameter guidance), record each as a separate insight."

### Change M3: Methodology in Finding Definition

**File:** `src/qmatsuite/mcp/app.py`
Finding grade definition expanded: "verified result from one calculation, OR a methodology lesson learned from a failure or workaround."

### Change M4b: Remove [UNDER REVIEW] Prefix from Search Results

**File:** `src/qmatsuite/mcp/knowledge/store.py`
Removed the code that prepended `[UNDER REVIEW]` to content for entries with high contradiction_count. The contradiction_count field is already exposed in each result dict.

### Change M5: Multiple-Insights Guidance in Preamble

**File:** `src/qmatsuite/mcp/app.py`
Added: "Record each distinct finding as a separate insight — a session may produce one or several (numerical result, methodology lesson, error workaround). Include specific numbers and context."

### Change M6: Search-Knowledge Hint in create_calculation

**File:** `src/qmatsuite/mcp/tools/create_calculation.py`
context_hint now starts with "Tip: use search_knowledge(query='<workflow>') to check for known issues before configuring."

### Tests

- Updated `test_search_annotates_under_review` → `test_search_does_not_prefix_under_review`
- Added `tests/mcp/test_behavioral_hints.py` (8 tests covering M1-M6)

### Verification

| Suite | Before | After | Delta |
|-------|--------|-------|-------|
| Gates | 733 passed, 2 skipped | 733 passed, 2 skipped | 0 |
| MCP | 746 passed | 754 passed | +8 new |
| Full | — | 6864 passed, 4 skipped | 0 failures |

---

## Round 3: Resolution-Moment Insight Hint

**Date:** 2026-03-06
**Ref:** Chain A (38 sessions) — agents record 0 findings on the failure path despite 6+ error-enrichment hints per session. Error hints fire during "fix mode" and are 100% ignored.

### Problem

The resolution moment — when a previously-failed calculation succeeds — is the ideal time to prompt insight recording because:
- The fix is verified (success response confirms it)
- Success response has the agent's attention (not in panicked fix-mode)
- Error details are still in context

### Change R1: Prior-Failure Detection in `run_calculation`

**File:** `src/qmatsuite/mcp/tools/run_calculation.py`

After existing hint construction and before `return make_response(...)` on the success path, queries provenance for the 2 most recent runs of this calc. If the prior run (not the current one) had `status == "failed"`, appends resolution-moment hint prompting `record_insight(grade='finding', tags='error-recovery')`.

Graceful degradation: outer try/except catches import errors, missing `.provenance/`, or DB issues — never crashes the success path.

### Change R2: Preamble Workflow Update

**File:** `src/qmatsuite/mcp/app.py`

- Both Fast and Normal track workflows now show explicit failure-recovery loop: `run_calculation → check result: on failure → fix → run again; on success → record findings + error-recovery insights`
- Multiple-insights text reworded: "a session may produce several: the numerical result, each error encountered and its resolution, and any methodology lessons"

### Tests

**File:** `tests/mcp/test_resolution_hint.py` (5 tests, real QE execution)

| Test | Scenario | Expected |
|------|----------|----------|
| `test_first_success_no_resolution_hint` | First run succeeds | No resolution hint |
| `test_success_after_failure_has_resolution_hint` | Bad ecutwfc → QE crash → fix → succeed | Hint fires |
| `test_no_hint_when_previous_success` | QE crash → fix → succeed → succeed again | Hint on 2nd, not 3rd |
| `test_consecutive_successes_no_hint` | Two consecutive successes | No hint on 2nd |
| `test_no_provenance_no_crash` | Remove `.provenance/` dir | Succeeds, no hint, no crash |

### Design note: failure mechanism

Bad pseudo filenames (e.g., `NONEXISTENT.UPF`) cause failures in the pseudo pipeline
BEFORE the runner starts, so provenance never records the failed run. Tests use
`ecutwfc=-1.0` instead, which makes QE crash during execution — this failure IS
recorded in provenance via `_complete_provenance_recording(status=FAILED)`.

### Round 3b: Two-tone hint + fix pre-existing failures

**Date:** 2026-03-06

Changed resolution hint from "only fire on failure→success" to "always fire on every
success, with different tone based on prior failure."

- **Hard tone** (after recovery): "⚠️ You just recovered from a failed run. MUST record..."
- **Soft tone** (all other successes): "Run succeeded. If you learned something new..."

Also fixed 3 pre-existing test failures:
- **Gate S1**: sanitized `/Users/<user>/` paths in `REVIEW_MCP_PRE_EXPERIMENT_READINESS.md`
- **scope_engine (9 tests)**: added `_migrate_stale_schema()` in `schema.py` — detects
  old 7-column prototype `insights` table, drops and recreates with current schema
- **test_stage6 singleton leak**: added `reset_knowledge_store()` before/after
  `_patch_knowledge` fixture so the `_store` singleton doesn't leak between tests

### Verification

| Suite | Result |
|-------|--------|
| Success hint tests | 5 passed |
| MCP suite | 759 passed |
| Gate tests | 733 passed, 2 skipped |
| Full suite | 6868 passed, 4 skipped, 1 error (pre-existing QMCPACK) |

---

## Round 4: num_iter Overwrite Bug + Exp2 CLAUDE.md

**Date:** 2026-03-06

### Change N1: Prevent postwannier from overwriting num_iter

**Problem:** In `wannier_properties_calc` workflows, wannier (step 4) and postwannier
(step 5) share the same `.win` file in `raw/`. If the agent sets `num_iter=0` on
postwannier (postw90.x doesn't need iterations), the materialiser overwrites the
wannier step's `num_iter=200` → zero spread minimisation → AHC=0.

**File:** `src/qmatsuite/calculation/structure_steps.py` — 1 location (line ~987)

Added guard: `if step_type_gen != "postwannier":` around the `num_iter` override.
Postwannier inherits num_iter from the existing .win file written by the wannier step.

**Tests added** (2 new + 1 strengthened in `tests/unit/test_wannier90_step_materialization.py`):
- `test_postwannier_preserves_num_iter_from_wannier` — postwannier with explicit num_iter=0 → .win still has 200
- `test_postwannier_preserves_num_iter_when_not_set` — postwannier without num_iter → .win still has 200
- `test_postwannier_reuses_existing_seed_win` — added `assert "num_iter = 200"` assertion

### Change N2: Exp2 CLAUDE_TEMPLATE.md

**File:** `.tmp/paper_experiments/exp2_ab_control/CLAUDE_TEMPLATE.md` (new, gitignored)

Agent-facing rules copied as CLAUDE.md into every project directory:
- MCP-only engine execution (no direct Bash)
- Mandatory insight recording for every error recovery
- K_POINTS guidance (automatic mesh + explicit crystal list)
- Run mode guidance (full vs incremental)

### Change N3: run_exp2.sh CLAUDE.md lifecycle

**File:** `.tmp/paper_experiments/exp2_ab_control/run_exp2.sh` (gitignored)

- Added CLAUDE_TEMPLATE.md verification and initial copy to all project dirs
- Pre-session: `rm -rf .claude/` + fresh copy of CLAUDE_TEMPLATE.md → CLAUDE.md
- Post-session: `rm -rf .claude/` only (CLAUDE.md preserved on disk, refreshed next session)
- Removed CLAUDE.md deletion from both pre-session and post-session cleanup

### Verification

| Suite | Result |
|-------|--------|
| W90 materialization | 8 passed |
| Full suite | 6870 passed, 4 skipped, 1 error (pre-existing QMCPACK) |
