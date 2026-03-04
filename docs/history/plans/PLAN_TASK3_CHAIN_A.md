# Task 3 Chain A — Systematic Zincblende Survey with Nudge

**Date**: 2026-03-03
**Status**: Ready for execution
**Prerequisite**: Commit `fix(knowledge): refine nudge text and preamble for Task 3 experiments` must be present in `git log`

---

## Background

Previous experiments (Task 2.2 series) ran 85+ sessions across 16 compounds with 2 workflows (relax, bands). Key findings:

- Knowledge transfer is real and chemistry-aware (6+ STRONG transfer events)
- Write compliance ~97%, search rate ~45-62%
- **Zero L2/L3 insights emerged organically** — all 41+ insights are grade='finding'
- The nudge mechanism + preamble changes (Part 1 of Task 3) are designed to break this ceiling

### Reference Documents

The orchestrating agent should read these before execution:

| Document | Path | Purpose |
|----------|------|---------|
| Full experiment history | `docs/history/reviews/REVIEW_TASK_2_2_KNOWLEDGE_DISTILLATION.md` | Prior experiment results and lessons |
| Experiment summary | `docs/history/reviews/REVIEW_MCP_EXPERIMENTS_SUMMARY.md` | Condensed methodology and data |
| 2.2c runner script | `.tmp/pseudo_chain_v2c/run_chain.sh` | Reference runner implementation |
| 2.2d runner script | `.tmp/task_2_2d/run_2_2d.sh` | Reference runner with A/B conditions |
| MCP preamble | `src/qmatsuite/mcp/app.py` | Current instructions text (changed in Task 3 Part 1) |

---

## Experiment Design

**Name**: Task 3 Chain A — Systematic Zincblende Survey with Nudge

**Goal**: Test whether the refined nudge mechanism elicits L2 (pattern) and L3 (principle) insights from agents performing a systematic survey of zincblende semiconductors.

### Materials

19 zincblende compounds, organized by chemical family:

| Phase | Sessions | Workflow | Compounds |
|-------|----------|----------|-----------|
| Phase 1: Group IV relax | 01-04 | relax | C(diamond), Si, Ge, alpha-Sn |
| Phase 2: III-V relax | 05-13 | relax | GaP, GaAs, GaSb, InP, InAs, InSb, AlP, AlAs, AlSb |
| Phase 3: II-VI relax | 14-19 | relax | ZnS, ZnSe, ZnTe, CdS, CdSe, CdTe |
| Phase 4: Group IV bands | 20-23 | bands | C(diamond), Si, Ge, alpha-Sn |
| Phase 5: III-V bands | 24-32 | bands | GaP, GaAs, GaSb, InP, InAs, InSb, AlP, AlAs, AlSb |
| Phase 6: II-VI bands | 33-38 | bands | ZnS, ZnSe, ZnTe, CdS, CdSe, CdTe |

**Total**: 38 sessions (19 relax + 19 bands)

**Estimated wall time**: 6-19 hours total (10-30 min per session depending on compound complexity and number of attempts). The orchestrating agent should expect the full chain to complete within ~24 hours.

### Design Rationale

- All zincblende (F-43m) — eliminates structure variation as a variable
- Grouped by chemical family — maximizes transfer opportunity within group (Ga appears 3x, In 3x, Al 3x, Zn 3x, Cd 3x)
- All relax first, then all bands — first nudge fires around session 8 (8 L1 findings), giving the agent a synthesis opportunity mid-chain. By session 19 (start of bands), DB has ~19 findings covering all families
- Bands sessions use relaxed structures from same-compound relax via shared project state

### Knowledge DB Configuration

- **Fresh local.db** (0 entries). If local.db exists with entries, ABORT.
- **Builtin DB DISABLED**: Set `QMS_KNOWLEDGE_BUILTIN=0` in `.mcp.json` env. This ensures ALL knowledge comes from session-generated insights, with no seed knowledge contamination. Critical for measuring the nudge mechanism's effect in isolation.
- local.db is the core asset. NEVER delete, NEVER reset, NEVER modify directly. Only snapshot.

### Project Configuration

Single shared project directory. All 38 sessions run in the same project. Calculations accumulate — bands agents can `list_calculations()` and find relax results.

---

## Sub-agent Prompts

These are final. Do NOT modify mid-experiment.

### Relax Template

```
You are starting fresh with no prior experience with QMatSuite. Do not rely on any knowledge from previous conversations.

Calculate the equilibrium lattice constant of {COMPOUND} using Quantum ESPRESSO. Use the minimum-atom primitive cell. Compare your result with experimental values. You may make up to 3 attempts if the result seems unreasonable. Report your final lattice constant, the error versus experiment, and any issues you encountered.
```

### Bands Template

```
You are starting fresh with no prior experience with QMatSuite. Do not rely on any knowledge from previous conversations.

Calculate the electronic band structure and band gap of {COMPOUND} using Quantum ESPRESSO. Use the relaxed structure from a previous calculation in this project if available. Compare your result with experimental values. You may make up to 3 attempts if the result seems unreasonable. Report the band gap value, type (direct/indirect), locations of VBM and CBM in k-space, and any issues you encountered.
```

Replace `{COMPOUND}` with the compound name for each session. Prompts do NOT mention crystal structure, space group, pseudopotentials, knowledge system, or specific experimental values.

---

## Runner Script Specification

Create `run_chain_a.sh` at `.tmp/task3_chain_a/run_chain_a.sh`. Base it on the 2.2c runner (`.tmp/pseudo_chain_v2c/run_chain.sh`).

### Directory Structure

```
.tmp/task3_chain_a/
    run_chain_a.sh
    project/
        .mcp.json
    sessions/
        01_relax_C/
        02_relax_Si/
        ...
        38_bands_CdTe/
    CHAIN_LOG.md
```

### Pre-flight Checks

In script, ABORT on any failure:

1. Verify local.db is clean: `sqlite3 .qmatsuite/knowledge/local.db "SELECT COUNT(*) FROM insights;" 2>/dev/null` must be 0 or file must not exist
2. Verify `QMS_KNOWLEDGE_BUILTIN=0` is set in `.mcp.json` env section
3. Verify MPI pw.x works: run a quick test, output must say "Parallel version (MPI)" and "running on 12 processors"
4. Verify `mpirun` exists: `which mpirun`
5. Remove any `.claude/` or `CLAUDE.md` from project dir

### .mcp.json

Copy from a previous experiment (e.g., `.tmp/pseudo_chain_v2c/project/.mcp.json`) and add `QMS_KNOWLEDGE_BUILTIN=0` to env. Verify the `command` path resolves correctly when `claude` is invoked from the project dir.

### Session Execution

All relative paths in the script (`.tmp/task3_chain_a/...`, `.qmatsuite/knowledge/...`) are relative to REPO_ROOT. The script must anchor to the repo root before the session loop:

```bash
# Anchor all paths to repo root
REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO_ROOT"
```

For each session:

```bash
SESSION_NAME="{NN}_{workflow}_{compound}"
SESSION_DIR="$REPO_ROOT/.tmp/task3_chain_a/sessions/$SESSION_NAME"
PROJECT_DIR="$REPO_ROOT/.tmp/task3_chain_a/project"

mkdir -p "$SESSION_DIR"

# Clean agent artifacts from previous session
rm -rf "$PROJECT_DIR/.claude" "$PROJECT_DIR/CLAUDE.md"

cd "$PROJECT_DIR"
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null
export QMS_MPI_COMMAND=mpirun
export QMS_MPI_CORES=12

start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "start: $start_time" > "$SESSION_DIR/timing.txt"

timeout 7200 claude -p \
    --dangerously-skip-permissions \
    --output-format stream-json --verbose \
    --no-session-persistence \
    "$PROMPT" > "$SESSION_DIR/trace.jsonl" 2>&1

exit_code=$?
end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "end: $end_time" >> "$SESSION_DIR/timing.txt"
echo "exit: $exit_code" >> "$SESSION_DIR/timing.txt"
```

### Post-session Data Collection

After EACH session (automated in script):

```bash
# Return to repo root for absolute path resolution
cd "$REPO_ROOT"

# 1. Snapshot local.db
cp "$REPO_ROOT/.qmatsuite/knowledge/local.db" "$SESSION_DIR/local_db_snapshot.db" 2>/dev/null || echo "no local.db yet"

# 2. Count insights total
insight_count=$(sqlite3 "$REPO_ROOT/.qmatsuite/knowledge/local.db" "SELECT COUNT(*) FROM insights;" 2>/dev/null || echo "0")

# 3. Count by grade (critical: watch for pattern/principle emergence)
grade_counts=$(sqlite3 "$REPO_ROOT/.qmatsuite/knowledge/local.db" "SELECT grade, COUNT(*) FROM insights GROUP BY grade;" 2>/dev/null || echo "none")

# 4. Trace stats
tool_calls=$(grep -c '"tool_use"' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo 0)
search_k=$(grep -c 'search_knowledge' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo 0)
record_i=$(grep -c 'record_insight' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo 0)
list_i=$(grep -c 'list_insights' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo 0)
run_calc=$(grep -c 'run_calculation' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo 0)

# 5. Check MPI actually used
mpi_check=$(find "$PROJECT_DIR" -name "*.out" -newer "$SESSION_DIR/timing.txt" 2>/dev/null | head -1 | xargs grep -E "Parallel|Serial|running on" 2>/dev/null || echo "no output found")

# 6. Spot-check: verify no builtin knowledge leaked into search results
builtin_leak=$(grep -c '"source_type".*"builtin"' "$SESSION_DIR/trace.jsonl" 2>/dev/null || echo "0")

# 7. Append to CHAIN_LOG.md
cat >> "$REPO_ROOT/.tmp/task3_chain_a/CHAIN_LOG.md" << EOF

## Session $SESSION_NAME
- Wall time: $start_time -> $end_time
- Exit code: $exit_code
- Tool calls: $tool_calls (search_k: $search_k, record_i: $record_i, list_i: $list_i, run_calc: $run_calc)
- Insights total: $insight_count (by grade: $grade_counts)
- MPI: $mpi_check
- Builtin leak check: $builtin_leak occurrences
EOF

# 8. Remove .claude/ if created
rm -rf "$PROJECT_DIR/.claude" "$PROJECT_DIR/CLAUDE.md"
```

### Execution Rules

1. Strictly sequential. Session N completes before N+1 starts.
2. NEVER delete local.db. Only snapshot after each session.
3. NEVER clean the project directory between sessions. Calculations accumulate.
4. No `.claude/` or `CLAUDE.md` — remove after every session.
5. If session hangs (no progress 30 min), kill it. Record in CHAIN_LOG. Proceed.
6. If session fails (exit != 0), record it. Proceed.
7. 7200s (2h) timeout per session.
8. MPI = 12 cores for all sessions.

---

## Orchestrating Agent Instructions

The orchestrating agent receives this plan and does the following:

### Step 1: Read Reference Documents

Read the reference documents listed in the Background section to understand experiment history and methodology.

### Step 2: Verify Part 1 Text Changes

Check `git log --oneline -5` for the commit message `fix(knowledge): refine nudge text and preamble for Task 3 experiments`. If not committed, execute Part 1 first (see `docs/history/worklogs/WORKLOG_TASK3_TEXT_CHANGES.md` for what was changed).

### Step 3: Create Runner Script

Create `run_chain_a.sh` at `.tmp/task3_chain_a/run_chain_a.sh` based on the specification above.

### Step 4: Launch

```bash
cd <REPO_ROOT>
nohup bash .tmp/task3_chain_a/run_chain_a.sh > .tmp/task3_chain_a/runner.log 2>&1 &
echo $! > .tmp/task3_chain_a/runner.pid
```

### Step 5: Verify First 2 Sessions

Before stepping back:

- Check `runner.log` for errors
- Check session 01's `trace.jsonl` is non-empty and has tool calls
- Check session 01's QE `.out` files say "Parallel version (MPI), running on 12 processors"
- Check local.db has >=1 entry after session 01
- Check no builtin `source_type` in trace (builtin leak = 0)
- Wait for session 02 to start, confirm it also begins correctly

### Step 6: Monitor Every 30 Minutes

```bash
# Check if still running
ps -p $(cat .tmp/task3_chain_a/runner.pid 2>/dev/null) > /dev/null 2>&1 && echo "RUNNING" || echo "STOPPED"

# Latest progress
tail -25 .tmp/task3_chain_a/CHAIN_LOG.md

# Grade distribution (the key metric)
sqlite3 .qmatsuite/knowledge/local.db "SELECT grade, COUNT(*) FROM insights GROUP BY grade;"

# Any new patterns or principles?
sqlite3 .qmatsuite/knowledge/local.db "SELECT id, grade, substr(content,1,80) FROM insights WHERE grade IN ('pattern','principle') ORDER BY created_at;"
```

Brief report each check: which session is running/completed, total insights, any pattern/principle emergence, any failures, any builtin leaks.

### Step 7: After All 38 Sessions Complete

- Final local.db snapshot: `cp .qmatsuite/knowledge/local.db .tmp/task3_chain_a/local_db_final.db`
- Write detailed report at `docs/history/reports/REPORT_TASK3_CHAIN_A.md` covering:
  - Session-by-session summary table
  - Nudge firing analysis (when, which sessions, agent response)
  - Pattern/principle emergence analysis (content, quality, references)
  - Information density analysis (do findings have numbers?)
  - Cross-session knowledge flow (search -> use patterns)
  - Comparison with 2.2 series baseline (0% L2/L3)

---

## Key Observation Points

### Nudge Firing

Around session 8-9, the L3->L4 nudge should appear in `record_insight` responses. Check `trace.jsonl` for "Knowledge synthesis checkpoint" in tool responses.

### Pattern Emergence

Does any agent respond to the nudge by calling `list_insights(grade='finding')` and then `record_insight(grade='pattern', ...)`? This is the PRIMARY signal.

### Numerical Findings

Do findings include specific numbers (lattice constants in angstroms, band gaps in eV, VBM/CBM k-points)? Or vague statements ("result is reasonable")?

### Cross-family Transfer

When bands sessions start (session 20+), does the agent search knowledge and find relax findings? Especially within families (e.g., bands_GaAs finding relax_GaP insights).

### Builtin Contamination

If any search result shows `source_type: "builtin"`, that means `QMS_KNOWLEDGE_BUILTIN=0` is not working. Flag immediately.

---

## Success Criteria

| Level | Criterion |
|-------|-----------|
| Minimum | Nudge fires as designed; findings include numerical values |
| Good | At least 1 pattern-grade insight recorded |
| Strong | Pattern insight is scientifically valid AND references finding IDs |
| Excellent | Pattern insight is retrieved and used by a later session |
| Best case | Principle-grade insight emerges from patterns |

---

## What NOT to Do

- Do NOT modify sub-agent prompts mid-experiment
- Do NOT delete or reset local.db during experiment
- Do NOT clean project directory between sessions
- Do NOT add hints about crystal structure, pseudopotentials, or knowledge tools to prompts
- Do NOT enable builtin knowledge mid-experiment
- Do NOT run controls now — controls come after, targeting specific sessions that showed signal
