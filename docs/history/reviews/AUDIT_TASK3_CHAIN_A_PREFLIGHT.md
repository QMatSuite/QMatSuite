# Audit: Task 3 Chain A Pre-flight

**Date**: 2026-03-03
**Auditor**: Claude Opus 4.6
**Chain status**: 4 of 38 sessions completed (01_relax_C through 04_relax_alpha-Sn)

---

## Issue 1: Grade Numbering

- **Verdict**: Doc-only error — does NOT affect execution
- **Evidence**:
  - Plan document (`PLAN_TASK3_CHAIN_A.md` line 36): "L2 (pattern) and L3 (principle)"
  - Runner script comments (line 6-7): same "L2 (pattern)", "L3 (principle)" from plan
  - Code (`store.py` line 43): `_GRADE_ORDER = {"principle": 5, "pattern": 4, "finding": 3, "observation": 2, "bookkeeping": 1}`
  - Store nudge comments (`store.py` lines 498, 517): "L4→L5" (pattern→principle) and "L3→L4" (finding→pattern)
  - MCP preamble (`app.py` lines 26-31): uses grade NAMES ("finding", "pattern", "principle") — no L-numbers exposed to agents
  - Sub-agent prompts in `run_chain_a.sh` (lines 148-159): no grade numbers or L-levels mentioned at all
- **Risk to running experiment**: **None**. Grade strings ("finding", "pattern", "principle") are used everywhere in code and agent interaction. The L-number labels are only in documentation/comments for human readers. The plan's numbering convention (L2=pattern, L3=principle) is inconsistent with the code's internal convention (L4=pattern, L5=principle), but this is purely cosmetic.

---

## Issue 2: local.db Path Resolution

- **Verdict**: Working correctly
- **Evidence**:
  - **Code path**: `_local_db_path()` (store.py:103) → `get_qmatsuite_home_root()` (paths.py:147) → `get_app_data_dir()` (paths.py:94-115)
  - **Resolution logic**: Priority 1: `QMATSUITE_HOME` env var. Priority 2: Dev mode (walks up from `Path(__file__).resolve().parent` looking for `pyproject.toml` + `src/qmatsuite`). Priority 3: Electron mode. Priority 4: `~/.qmatsuite`
- **Critical detail**: `_try_find_repo_root()` (paths.py:30-51) walks up from the **installed code location** (`src/qmatsuite/core/paths.py`), NOT from `cwd`. Since the venv Python runs from `<repo_root>/.venv/bin/python` with the package installed in editable mode, `Path(__file__)` resolves to `<repo_root>/src/qmatsuite/core/paths.py`. Walking up finds `pyproject.toml` at `<repo_root>/`.
- **Result**: `local.db` resolves to `<repo_root>/.qmatsuite/knowledge/local.db` — same as the script's `$REPO_ROOT/.qmatsuite/knowledge/local.db`
  - **The `cd "$PROJECT_DIR"` in the script (line 349) does NOT affect path resolution** — the MCP server uses code location, not cwd.
- **.mcp.json verification** (project/.mcp.json): `command` points to `<repo_root>/.venv/bin/python`, `QMS_KNOWLEDGE_BUILTIN: "0"` is set.
  - **Empirical confirmation**: CHAIN_LOG shows insight counts incrementing correctly:
    - Session 01: insight_count = 1 (finding|1)
    - Session 02: insight_count = 2 (finding|2)
    - Session 03: insight_count = 3 (finding|3)
    - Session 04: insight_count = 4 (finding|4)
  - Each session adds exactly 1 finding to the accumulating DB. Path resolution is definitively working.
- **Risk to running experiment**: **None**

---

## Issue 3: Model Pinning

- **Verdict**: Unpinned (but empirically consistent so far)
- **Evidence**:
  - **Runner script** (line 353): `claude -p --dangerously-skip-permissions --output-format stream-json --verbose --no-session-persistence "$prompt"` — **no `--model` flag**
  - **Trace evidence**: Session 01 trace.jsonl first line contains `"model":"claude-opus-4-6"`. All three sampled model fields in the trace show `claude-opus-4-6`.
  - **No config pinning found**: The `.mcp.json` has no model configuration. No `--model` in the script. The model comes from the Claude CLI's default.
  - **Current default**: Claude CLI appears to default to `claude-opus-4-6`, which is consistent across all 4 completed sessions.
- **Risk to running experiment**: **Low**. For a single continuous run that takes ~6-19 hours, the CLI default is unlikely to change mid-execution. However, if the experiment is resumed after a CLI update, model consistency could break. For rigorous reproducibility, `--model claude-opus-4-6` should have been specified.

---

## Issue 4: Path Anchoring

- **Verdict**: Correct
- **Evidence**:
  - **REPO_ROOT** (line 16): `REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` — Script is at `.tmp/task3_chain_a/run_chain_a.sh`, so `dirname -> .tmp/task3_chain_a/`, `../.. -> repo root`. Correct.
  - **All paths** are `$REPO_ROOT`-prefixed:
    - `CHAIN_DIR="$REPO_ROOT/.tmp/task3_chain_a"` (line 19)
    - `PROJECT_DIR="$CHAIN_DIR/project"` (line 20)
    - `SESSIONS_DIR="$CHAIN_DIR/sessions"` (line 21)
    - `KNOWLEDGE_DIR="$REPO_ROOT/.qmatsuite/knowledge"` (line 24)
    - `VENV_PYTHON="$REPO_ROOT/.venv/bin/python"` (line 23)
  - **Post-session sqlite3** (lines 379, 382): uses `$REPO_ROOT/.qmatsuite/knowledge/local.db` — correct.
  - **cd management**: `cd "$REPO_ROOT"` at script start (line 17), `cd "$PROJECT_DIR"` in subshell for claude (lines 348-358), then `cd "$REPO_ROOT"` for post-session (line 373). Clean separation.
  - **Subshell isolation** (lines 348-358): The `( cd "$PROJECT_DIR"; ... claude -p ... )` runs in a subshell, so the `cd` doesn't affect the parent shell's cwd. Good practice.

---

## Issue 5: MPI Check

- **Verdict**: Fine (minor cosmetic bug in builtin leak logging)
- **Evidence**:
  - **MPI verification** (lines 393-398): Uses `find "$PROJECT_DIR" -name "*.out" -newer "$session_dir/.start_marker"` — the `.start_marker` is touched RIGHT BEFORE the session runs (line 345), so it correctly filters to only output files created during this session.
  - **Note**: The plan document (line 198) mentioned `-newer "$SESSION_DIR/timing.txt"` but the actual script uses `.start_marker`. The script's approach is slightly better because `.start_marker` is created before the session, while `timing.txt` is written both before (start time) and after (end time), creating a potential race.
  - **CHAIN_LOG results**: All 4 sessions show `MPI: Parallel (running on    12)` — correct.
  - **Cosmetic bug**: The `builtin_leak` variable (line 401) uses `grep -c ... || echo "0"`. When grep finds 0 matches, it outputs "0" to stdout but exits with code 1. The `|| echo "0"` then also outputs "0". Result: variable contains `"0\n0"`. This causes the CHAIN_LOG entry to show:
    ```
    - Builtin leak check: 0
    0 occurrences
    ```
    instead of the intended `- Builtin leak check: 0 occurrences`. Same bug affects all `grep -c ... || echo` patterns (lines 385-389), but those happen to produce correct values when count > 0 because grep exits 0 and the `|| echo` doesn't fire. Only the builtin leak check consistently hits this because `grep -c` returns 0 count with exit code 1.
  - **Impact**: Purely cosmetic in CHAIN_LOG formatting. Does not affect experiment validity.

---

## Additional Observations

### A. grep -c Overcounting (Known Issue)

The trace stat collection (lines 385-389) uses `grep -c 'search_knowledge'` etc. on `trace.jsonl`. This is the **same naive `grep -c` pattern** that was documented in the Task 2.2d metrics audit as producing overcounted values (the string appears in tool definitions, system messages, and result objects — not just in actual tool calls). For example, `run_calc` counts `grep -c 'run_calculation'` which counts every mention of the string, not just actual `tool_use` blocks.

**Impact**: CHAIN_LOG tool call counts are directionally useful but not precise. Session 02 shows `run_calc: 13` which is almost certainly overcounted (a relax session typically makes 1-3 run_calculation calls). This is the same systemic issue documented in `AUDIT_AWARENESS_TAX.md`.

**Recommendation**: Use trace-aware parsing (count `"type":"tool_use"` blocks where the `name` field matches) for the post-experiment analysis. The CHAIN_LOG values are fine for monitoring but should not be used in the final report as exact counts.

### B. Insight Accumulation Pattern

Sessions 01-04 each produced exactly 1 finding (total: 1→2→3→4). The `record_i` counts are 3, 4, 3, 3 — meaning agents are recording bookkeeping/observation entries too (which are journal-only, not promoted to the DB). This is healthy behavior.

### C. Builtin Knowledge Isolation

All 4 sessions show `Builtin leak check: 0` (despite the formatting bug). With `QMS_KNOWLEDGE_BUILTIN=0` in `.mcp.json` and `_builtin_enabled()` checking `os.environ.get("QMS_KNOWLEDGE_BUILTIN", "1") != "0"`, builtin knowledge is correctly disabled. The `search()` method (store.py:393-396) skips `_fts_search` on builtin when `_builtin_enabled()` is False.

### D. Reserved Slots Fix Applied

The code now uses `_merge_with_reserved_slots()` (store.py:79-93) with `LOCAL_RESERVED_SLOTS = 3`. This addresses the BM25 cross-collection ranking bug identified in the Task 2.2d awareness tax audit. In this experiment (builtin disabled), the fix is moot since only local results exist, but it's good to note the fix is in place for future experiments.

### E. Wall Times

| Session | Wall time | Notes |
|---------|-----------|-------|
| 01_relax_C | 3m 16s | Carbon — fast |
| 02_relax_Si | 4m 29s | Silicon |
| 03_relax_Ge | 4m 38s | Germanium |
| 04_relax_alpha-Sn | 6m 30s | alpha-Sn — heaviest Group IV, expected slower |

Wall times are increasing slightly with atomic number, which is physically sensible (heavier elements → more electrons → slower SCF).

---

## Overall Assessment

**The running experiment is valid. No issues require aborting.**

| Issue | Severity | Action Needed |
|-------|----------|---------------|
| 1. Grade numbering | Cosmetic | Fix plan doc post-experiment |
| 2. local.db path | ✅ Working | None |
| 3. Model pinning | Low risk | Note in final report; add `--model` flag if re-running |
| 4. Path anchoring | ✅ Correct | None |
| 5. MPI check | ✅ Working | Fix grep -c double-zero cosmetic bug if re-running |

**Known limitation**: Tool call counts in CHAIN_LOG are overcounted due to naive `grep -c`. Use canonical trace parsing for the final report. This does NOT affect experiment execution — only post-hoc analysis accuracy.
