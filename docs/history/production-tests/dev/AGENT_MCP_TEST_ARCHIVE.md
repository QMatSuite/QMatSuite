# Agent MCP Test Archive — Development History

**Date**: 2026-02-21 (all tests run on this date)
**Branch**: v2-python
**Model**: claude-sonnet-4-6 (all agents)
**Runner script**: `tools/agent_test_matrix.sh` (committed to repo)

## What This Is

This archive preserves the agent MCP integration test artifacts from the
development phase of the QMatSuite MCP server. During development, the
`tools/agent_test_matrix.sh` script spawned real Claude Code CLI agents
(`claude -p`) against the QMatSuite MCP server, each performing a different
materials science calculation. The agents received ONLY a simple task prompt
and `.mcp.json` — no preconditioning about resources, paths, or tool usage.

The raw artifacts lived under `.tmp/agent_mcp_test/` (gitignored, ephemeral).
This archive preserves the valuable summary documents, review analyses, and
agent-generated worklogs in a permanent, sanitized form.

**Sanitization**: All files have been processed to replace:
- `/Users/<username>/QMatSuite` with `<REPO_ROOT>`
- `/Users/<username>` with `<HOME>`
- Usernames with `<USER>`

## Chronological Run History

All 10 runs occurred on 2026-02-21, spanning ~7 hours of iterative development.

### Phase 1: Early Iteration (10:11 - 11:31)

These runs debugged the test harness itself (env vars, project isolation,
MCP config discovery). The script evolved through several iterations.

| Run Timestamp | Tasks | Outcome | Notes |
|---------------|-------|---------|-------|
| 10:11:07 | 9 (Si SCF through water xTB) | 5/9 created projects | **First real run.** Agents wrote WORKLOG.md files. Project-root-equals-repo-root bug discovered. |
| 10:22:42 | 1 (si_scf_cold) | Debug run | 1-line trace — script abort |
| 10:23:57 | 1 (si_scf_cold) | Debug run | 42-line trace — testing fixes |
| 10:26:00 | 1 (si_scf_cold) | Debug run | 32-line trace — more fixes |
| 11:06:35 | 1 (gaas_bands) | Debug run | Single-task validation |
| 11:29:18 | 10 (expanded task set) | No SUMMARY | Pre-Round 1 dry run with revised tasks |

### Phase 2: Round 1 (12:13)

First clean full run after harness fixes. All 9 tasks pass (create projects).
Discovered 5 bugs and 8 information gaps. Detailed code review in REVIEW.md.

| Run Timestamp | Tasks | Pass Rate | Key Finding |
|---------------|-------|-----------|-------------|
| 12:13:01 | 9 | 9/9 PASS | 5 bugs, 8 MCP gaps identified |

### Phase 3: Round 2 (14:59)

After Round 1 bug fixes. Verified BUG-1 through BUG-5 fixes. Dramatic
behavioral improvement from instruction updates.

| Run Timestamp | Tasks | Pass Rate | Key Finding |
|---------------|-------|-----------|-------------|
| 14:59:01 | 9 | 9/9 PASS | 4/5 bugs verified fixed, agent behavior significantly improved |

### Phase 4: Round 3 (16:54)

Expanded to 17 tasks. New tasks verify targeted fixes (magnetization, xTB
promote, ORCA error handling, convergence study, etc.).

| Run Timestamp | Tasks | Pass Rate | Key Finding |
|---------------|-------|-----------|-------------|
| 16:54:10 | 17 | 17/17 PASS | Parallel run (no REVIEW) |
| 16:54:14 | 17 | 17/17 PASS | Canonical run with REVIEW |

## File Index

### `orchestration/`

| File | Source | Description |
|------|--------|-------------|
| `WORKLOG_test_matrix_design.md` | `.tmp/WORKLOG.md` | Design worklog for the test matrix script. Documents Claude Code CLI research (flags, MCP discovery, session isolation), `QMATSUITE_PROJECT` env var behavior, pseudo library paths, script design decisions, and iteration log for early debugging (Iterations 1-2). |

### `round0-early/`

Artifacts from the first real run (run_20260221_101107) — the only run where
agents wrote WORKLOG.md files. These are valuable because they show the raw
agent decision-making process: tool call sequences, error recovery, and the
project-root-equals-repo-root bug discovery.

| File | Source | Description |
|------|--------|-------------|
| `SUMMARY_run_101107.txt` | `run_20260221_101107/SUMMARY.txt` | Pass/fail summary. 9/9 worklogs, but only 5/9 created projects (bug). |
| `WORKLOG_task_00_si_scf_cold.md` | `task_00_si_scf_cold/WORKLOG.md` | **Si SCF cold start.** 14-step detailed log. Cold SSSP download, LDA vs PBE pseudo mismatch discussion. Result: -310.686 eV. Most detailed worklog in the set. |
| `WORKLOG_task_01_si_bands_demo.md` | `task_01_si_bands_demo/WORKLOG.md` | **Si band structure via demo.** Truncated at step 4 (agent timed out during run). Shows demo discovery and load path. |
| `WORKLOG_task_02_si_dos_demo.md` | `task_02_si_dos_demo/WORKLOG.md` | **Si DOS via demo.** Complete 13-step log with ASCII DOS plot. Shows project-root bug workaround (manual project.qms.yml creation). Result: -310.748 eV, DOS plotted. |
| `WORKLOG_task_03_si_relax_bands.md` | `task_03_si_relax_bands/WORKLOG.md` | **Si relax + bands pipeline.** Truncated at step 5. Documents project isolation tension and structure import. |
| `WORKLOG_task_04_al_scf_scratch.md` | `task_04_al_scf_scratch/WORKLOG.md` | **Al FCC SCF from scratch.** Documents preset selection rationale (HIGH precision, ROBUST convergence, SMEARING_GAUSSIAN for metal). CIF import failure, POSCAR recovery. Truncated before results. |
| `WORKLOG_task_05_gaas_bands.md` | `task_05_gaas_bands/WORKLOG.md` | **GaAs band structure from scratch.** Manual structure construction (zincblende, F-43m). K-path generation. Failed on project-root bug (truncated). |
| `WORKLOG_task_06_fe_magnetic.md` | `task_06_fe_magnetic/WORKLOG.md` | **Fe BCC magnetic SCF.** Shows collinear magnetism preset, starting_magnetization setup, SSSP PAW pseudo selection. Truncated before results. |
| `WORKLOG_task_07_bad_config.md` | `task_07_bad_config/WORKLOG.md` | **Intentionally bad config (ecutwfc=5 Ry).** Complete log. Preflight correctly flagged `LOW_ECUTWFC` advisory. Failed to run due to project-root bug. Documents both physics and system-level "bad configs". |
| `WORKLOG_task_08_water_xtb.md` | `task_08_water_xtb/WORKLOG.md` | **Water xTB geometry optimization.** Complete 10-step log. Demo discovery + load + run. Detailed final results including bond lengths, angles, HOMO-LUMO gap, Wiberg bond orders. Result: -5.071 Eh, O-H=0.959 A. |

### `round1/`

First clean full matrix run. The REVIEW.md is a comprehensive code review
that identified 5 bugs and 8 information gaps, with proposed fixes for each.

| File | Source | Description |
|------|--------|-------------|
| `SUMMARY.txt` | `run_20260221_121301/SUMMARY.txt` | 9/9 PASS, all tasks created projects. No worklogs (not requested in Round 1 prompts). |
| `REVIEW.md` | `run_20260221_121301/REVIEW.md` | **Round 1 code review.** Per-task results table, agent decision pipeline analysis (demo vs scratch, tool call sequences, best practices), 5 bugs found (BUG-1 through BUG-5), 8 information gaps (GAP-1 through GAP-8), physics quality assessment, proposed improvements (3 priority tiers), 8 proposed additional test cases, 5 systemic issues. ~280 lines. |

### `round2/`

After Round 1 fixes. Verified bug fixes and measured behavioral improvement
from instruction updates.

| File | Source | Description |
|------|--------|-------------|
| `SUMMARY.txt` | `run_20260221_145901/SUMMARY.txt` | 9/9 PASS. |
| `REVIEW.md` | `run_20260221_145901/REVIEW.md` | **Round 2 review.** Bug fix verification (5/5 code-verified, 4/5 runtime-verified). GAP verification (6/7 fixed). Quantitative R1 vs R2 comparison table. Behavioral metrics: `inspect(dry_run)` 2/9 -> 6/9, `plot_analysis` 5/9 -> 9/9, `search_knowledge` 0/9 -> 2/9. 5 remaining issues identified. ~220 lines. |

### `round3/`

Expanded to 17 tasks. Verified targeted fixes (magnetization, xTB promote,
error enrichment). Regression analysis on behavioral metrics.

| File | Source | Description |
|------|--------|-------------|
| `SUMMARY.txt` | `run_20260221_165414/SUMMARY.txt` | 17/17 PASS (canonical run). |
| `SUMMARY_parallel_run.txt` | `run_20260221_165410/SUMMARY.txt` | 17/17 PASS (parallel run, same prompts, no REVIEW). |
| `REVIEW.md` | `run_20260221_165414/REVIEW.md` | **Round 3 review.** 17-task results (9 core + 8 new). Fix verification: magnetization pipeline VERIFIED, xTB energy VERIFIED, xTB promote VERIFIED, BUG-4/5 runtime VERIFIED. R1->R2->R3 behavioral comparison. Regression analysis (real vs statistical). 6 remaining issues. 6 notable successes highlighted. ~260 lines. |

## Related Documents (Committed Elsewhere)

These documents are already committed in the repo and provide context for the
test matrix work:

| File | Description |
|------|-------------|
| `tools/agent_test_matrix.sh` | The runner script (336 lines). Phases: walk-up guard, cold SSSP test, parallel agents, summary with pass/fail gates. |
| `docs/history/worklogs/AGENT_TEST_MATRIX_ROUND1_FIXES_WORKLOG.md` | Implementation worklog for Round 1 bug fixes (BUG-1 through BUG-5, GAP-1 through GAP-8). |
| `docs/history/worklogs/AGENT_TEST_MATRIX_ROUND2_FIXES_WORKLOG.md` | Implementation worklog for Round 2 fixes (magnetization pipeline, xTB promote, xTB energy). |
| `docs/history/reviews/MCP_E2E_READINESS_REVIEW.md` | Full MCP E2E readiness review (references this test matrix in section 2.2). |
| `docs/design/AGENT_INTEGRATION_DESIGN.md` | Master MCP/agent integration design doc. |

## What Was NOT Preserved

The following ephemeral artifacts from `.tmp/agent_mcp_test/` are NOT archived:

1. **NDJSON trace files** (`traces/task_XX.log`): 10-500 lines of streaming JSON per task. Contains full Claude Code session transcripts including tool call arguments and results. Too large and too noisy for permanent archival, and heavily embedded with absolute paths. The REVIEW.md documents summarize the important findings.

2. **Calculation output files** (QE `.out`, xTB `.xyz`, etc.): Raw engine output in `task_XX_*/calculations/*/raw/`. Reproducible by re-running the matrix.

3. **Intermediate debug runs** (run_102242, run_102357, run_102600, run_110635, run_112918): Single-task or incomplete harness debugging runs. The orchestration worklog documents the iteration history.

4. **`.mcp.json` files**: Generated per-task by the runner script. Template is `.mcp.json.example` in repo root.

## Replication Guide

To reproduce these results:

```bash
# 1. Activate venv
source .venv/bin/activate

# 2. Run the matrix (takes ~10 minutes, costs ~$5-10 in Claude API credits)
bash tools/agent_test_matrix.sh

# 3. Results in .tmp/agent_mcp_test/run_<timestamp>/
#    - SUMMARY.txt: pass/fail per task
#    - traces/task_XX.log: NDJSON session transcripts
#    - task_XX_*/: per-task project directories with calculation output
```

**Prerequisites**: Claude Code CLI (`claude`) in PATH, `.venv` with qmatsuite installed, QE engine installed (for QE tasks), xTB engine installed (for xTB tasks).

**Cost**: ~$3-5 per 9-task run, ~$5-10 per 17-task run (claude-sonnet-4-6).

## Key Findings Across All Rounds

### Bugs Found and Fixed

| Bug | Round Found | Round Fixed | Description |
|-----|-----------|------------|-------------|
| BUG-1 | R1 | R2 | `apply_preset` returned success when `steps_updated=0` |
| BUG-2 | R1 | R2 | `promote_structure` missing "minimize" in relax type set |
| BUG-3 | R1 | R2 | `get_results_summary` only had QE parser (engine-agnostic fix) |
| BUG-4 | R1 | R3 (verified) | `quick_run` missing error enrichment |
| BUG-5 | R1 | R3 (verified) | `get_status` never detected failures |
| xTB energy | R2 | R3 | `get_results_summary` returned null energy for xTB |
| xTB promote | R2 | R3 | `promote_structure` failed for xTB (file path mismatch) |
| Magnetization | R1 | R3 | `get_results_summary` missing magnetization fields |

### Behavioral Metrics Across Rounds

| Metric | R1 (9 tasks) | R2 (9 tasks) | R3 (17 tasks) |
|--------|:------------:|:------------:|:--------------:|
| Tasks PASS | 9/9 | 9/9 | 17/17 |
| `inspect(dry_run)` | 22% | 67% | 29% |
| `plot_analysis` | 56% | 100% | 35% |
| `search_knowledge` | 0% | 22% | 0% |
| Bash violations | 2 | 1 | 1 |

The R2->R3 behavioral regression is partly a statistical artifact (denominator effect from adding 8 new tasks) and partly real stochastic model variation. See Round 3 REVIEW.md section 4 for detailed analysis.
