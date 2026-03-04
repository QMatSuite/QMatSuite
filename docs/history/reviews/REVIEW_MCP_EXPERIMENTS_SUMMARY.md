# MCP Knowledge System — Experiment Summary for New Experiment Design

**Date**: 2026-03-03
**Purpose**: Reference document for designing post-R1-R11/G1-G9 experiments
**Scope**: All MCP experiments (Task 2.1 agent test matrix, Task 1 benchmark, SOC case study, Tasks 2.2 through 2.2d), scripts, prompts, corrected findings

---

## 1. Experiment Methodology

### 1.1 Isolation Protocol

Every experiment session is a single `claude -p` invocation (Claude Code in pipe mode). Between sessions, the only persistent state is:

| Channel | Persists? | How |
|---------|-----------|-----|
| Knowledge DB (`local.db`) | Yes | Accumulates insights across sessions |
| Seed knowledge (`builtin.db`) | Yes | 45 immutable curated entries |
| Project directory | Yes (within chain) | Calculations, structures, QE output files |
| Conversation context | **No** | `--no-session-persistence` flag |
| Claude memory | **No** | `rm -rf $PROJECT_DIR/.claude $PROJECT_DIR/CLAUDE.md` before each session |
| MCP server state | **No** | Fresh server per session (stdio transport) |

Critical isolation steps in every runner script:
```bash
rm -rf "$PROJECT_DIR/.claude" "$PROJECT_DIR/CLAUDE.md"    # kill Claude memory
claude -p --dangerously-skip-permissions --output-format stream-json \
    --verbose --no-session-persistence "$prompt"           # no session persistence
```

The `--no-session-persistence` flag ensures no conversation state carries over. Deleting `.claude/` and `CLAUDE.md` prevents Claude Code from auto-creating memory files that could leak context.

### 1.2 Subagent Prompt Template

All prompts (2.2b onward) share this structure:
```
You are starting fresh with no prior experience with QMatSuite.
Do not rely on any knowledge from previous conversations.

Calculate the [property] of [compound] using Quantum ESPRESSO.
[Use the relaxed structure from a previous calculation in this
project if available.]
Compare your result with experimental values.
You may make up to 3 attempts if the result seems unreasonable.
Report your [result], [comparison], and any issues you encountered.
```

Key prompt features:
- "Starting fresh" + "no prior experience" = anti-context-leak preamble
- "Up to 3 attempts" = retry allowance that triggers troubleshooting searches
- No mention of knowledge system, pseudopotentials, or structure type
- Identical across A/B conditions in 2.2d

**Known gap for next experiment**: The prompt does not specify cell type (primitive vs conventional). This caused a confound in 2.2d (see section 4.5).

### 1.3 Infrastructure Stack

| Component | Version/Config |
|-----------|---------------|
| Model | claude-opus-4-6 (Claude Opus) |
| Engine | Quantum ESPRESSO 7.5 |
| MPI | `mpirun -np 12` |
| Pseudopotentials | SSSP efficiency 1.3.0 |
| Knowledge seeds | 45 entries in `builtin.db` |
| MCP server | `python -m qmatsuite.mcp.server` (stdio) |

### 1.4 Data Capture

Each session produces:
- `trace.jsonl` — full Claude Code stream-json trace (tool calls, reasoning, results)
- `timing.txt` — start/end timestamps, exit code, wall time
- `local_db_snapshot.db` — knowledge DB state after session

Runner scripts extract per-session metrics via `grep -c` on trace files. **Caution**: naive grep overcounts (see section 4.4). Authoritative tool counts come from `audit_metrics_2_2d.py` (parses JSONL properly).

---

## 2. Scripts and Their Locations

| Script | Path (relative to repo root) | What It Does |
|--------|-----|--------------|
| 2.1 agent test matrix | `.tmp/agent_mcp_test/` | 10 runs of 9-17 MCP tool integration tasks (Sonnet model) |
| SOC case study | `.tmp/soc_case_study/` | 3 SOC compound sessions + control, with `analyze_traces.py` |
| Task 1 benchmark | `.tmp/bench/run_benchmark.sh` | 40 parallel isolated tasks, each in own project dir |
| Task 1 task defs | `.tmp/bench/tasks.jsonl` | JSON-lines with task id, prompt, expected values |
| Task 1 analysis | `.tmp/bench/analyze_results.py` | Parses result.json files, produces summary tables |
| Task 1 tool counter | `.tmp/bench/count_tool_calls.py` | Counts tool calls across traces |
| 2.2b runner | `.tmp/pseudo_chain/run_chain.sh` | 16 sequential sessions, shared project, empty→accumulating local.db |
| 2.2c runner | `.tmp/pseudo_chain_v2c/run_chain.sh` | Same as 2.2b but with FTS5 fix. Clean local.db start. |
| 2.2c-ext runner | `.tmp/pseudo_chain_v2c_ext/run_chain.sh` | 16 sessions (17-32), inherits 2.2c local.db (>=16 entries), fresh project |
| DOS runner | `.tmp/pseudo_chain_v2c_ext/run_chain_dos.sh` | 8 sessions (33-40), same project as ext, inherits local.db (>=31 entries) |
| 2.2d runner | `.tmp/task_2_2d/run_2_2d.sh` | 24 sessions (4 materials x 2 conditions x 3 workflows), per-material pipelines |
| FTS5 verification | `.tmp/pseudo_chain/verify_fts_fix.py` | Confirms FTS5 OR-join fix by querying 2.2b DB |
| Metrics audit | `.tmp/task_2_2d/audit_metrics_2_2d.py` | Parses trace.jsonl properly (not grep) for accurate tool counts |
| v1 trace analyzer | `.tmp/pseudo_case_study_v1/analyze_traces.py` | Extracts per-session metrics from v1 pilot |

### 2.1 Script Architecture (Common Pattern)

All runner scripts follow this pattern:
1. **Pre-flight checks**: venv, qmatsuite import, claude CLI, SSSP library, builtin.db (45 entries), MPI pw.x (12 cores), local.db state
2. **Session loop**: for each session → generate prompt → clean `.claude/` → run `claude -p` → save timing → snapshot local.db → grep trace stats → append to chain log
3. **Post-run**: final insight count, summary

The 2.2d script adds per-material pipeline management:
- Phase A: install empty local.db → run 3 workflows → snapshot pipeline DB
- Phase B: install A's pipeline DB → run 3 workflows → compare

---

## 3. Experiment Timeline

### 3.0a Task 2.1 — MCP Agent Test Matrix (Feb 21)

| | |
|---|---|
| **Runs** | 10 (evolving from 9 to 17 tasks per run) |
| **Model** | `claude-sonnet-4-6` (NOT Opus — only experiment to use Sonnet) |
| **Tasks (9-task variant)** | Na SCF, Si SCF, Si bands, Si DOS, Si relax+bands, Al SCF, Fe magnetic, bad config (5 Ry), water xTB |
| **Tasks (17-task variant, later runs)** | Above + Fe magnetization check, xTB promote, Si vc-relax, ORCA water, failing SCF, Al DOS, Mg HCP SCF, Si convergence |
| **Script** | `.tmp/agent_mcp_test/` (10 run directories, each with per-task subdirs + `traces/`) |
| **Isolation** | Per-task project directory; some tasks use demo projects, others build from scratch |
| **Knowledge system** | NOT tested — 0/9 tasks called `search_knowledge` in analyzed runs |

**Purpose**: MCP tool integration matrix — tests that agents can use the full tool set (`init_project`, `search_demos`, `load_demo`, `import_structure`, `create_calculation`, `apply_preset`, `run_calculation`, `get_results_summary`, `plot_analysis`, etc.) for diverse QE and xTB workflows. Not a knowledge system experiment.

**Key findings from REVIEW.md** (run `run_20260221_121301`):
- 9/9 PASS (all tasks created projects and ran calculations)
- Demo vs scratch decision: 4 tasks used demos, 5 built from scratch. 2 agents skipped `search_demos` entirely (protocol violation)
- `inspect_calculation(dry_run=true)` before run: only 2/9 agents used it
- `search_knowledge`: 0/9 — agents never used knowledge tools. This was before the preamble explicitly mentioned knowledge workflow
- BUG-1 found: `apply_preset` returns `status: "applied"` when `steps_updated: 0` (misleading success)
- BUG-2 found: `promote_structure` fails after xTB relax (missing step types in `_RELAX_GEN_TYPES`)
- Cost: ~$3.28 per run (Sonnet model)

**Later runs** (17 tasks): Added ORCA, convergence testing, failing-SCF error handling, HCP lattice. These test broader engine and workflow coverage.

**Relationship to 2.2 series**: Task 2.1 is the "does the tool pipeline work?" precursor. The 2.2 series is "does the knowledge system enable cross-session transfer?" built on top of the working pipeline confirmed here.

---

### 3.0b SOC Knowledge Distillation Case Study (Feb 27)

| | |
|---|---|
| **Sessions** | 3 treatment (Bi, Pb, GaAs) + 1 control |
| **Compounds** | Bi (strong SOC), Pb (strong SOC), GaAs (weak SOC) |
| **Script** | `.tmp/soc_case_study/` (per-session dirs + `analyze_traces.py`) |
| **Shared project** | `.tmp/soc_case_study/shared_project/` (calculations, structures, pseudo) |
| **Control isolation** | Separate `QMATSUITE_HOME` (`.tmp/soc_case_study/control_qms_home/`) + separate project (`.tmp/soc_case_study/control_project/`) |
| **Analysis** | `.tmp/soc_case_study/analyze_traces.py` — parses stream-json traces for tool call sequences, search results, pseudopotential choices, crash counts |

**Purpose**: Test SOC-specific knowledge transfer. Treatment sessions share a project and knowledge DB; control sessions get isolated `QMATSUITE_HOME` (separate knowledge DB) and separate project directory. Designed to measure whether SOC-related insights (e.g., "use fully-relativistic pseudopotentials for heavy elements") transfer across compounds.

**Data**: `trace.jsonl` + `timing.txt` per session. Analysis script extracts: `search_knowledge_called`, `search_knowledge_results`, `record_insight_count`, `used_fr_pseudo_first`, `band_structure_produced`, `tool_sequence`.

**Note**: This is a smaller, more focused study than the 2.2 series. It preceded Task 1 chronologically but has a narrower scope (SOC compounds only, 3+1 sessions vs 40+ sessions).

---

### 3.0c Archived Partial 2.2b Run (Feb 28)

`.tmp/pseudo_chain_partial_archived/` — an earlier partial run of the 2.2b chain that was archived before the final run completed. Contains the same compound/workflow plan as 2.2b (GaAs, SiC, AlAs, BN, GaP, InP, AlN, InAs — relax then bands). Kept as reference but superseded by the full `.tmp/pseudo_chain/` run.

---

### 3.0d Task 1 — Isolated Numerical Validation Benchmark (40 tasks)

| | |
|---|---|
| **Tasks** | 40 (24 relax + 10 bands + 3 magnetic + 3 xTB) |
| **Design** | Parallel isolated sessions — each task gets its own project directory, NO shared state |
| **Script** | `.tmp/bench/run_benchmark.sh` (supports `--max-parallel 12`, `--validate`, `--tasks`) |
| **Task definitions** | `.tmp/bench/tasks.jsonl` (JSON-lines, one task per line with id, prompt, expected values) |
| **Run directory** | `.tmp/bench/run_20260227_112901/` (each task gets `$RUN_DIR/$task_id/`) |
| **Analysis scripts** | `.tmp/bench/analyze_results.py`, `.tmp/bench/count_tool_calls.py` |
| **Knowledge audit** | `.tmp/bench/knowledge_audit_20260228_112646.md` |
| **Results** | `.tmp/bench/summary_table.md`, `.tmp/bench/paper_tables.md`, `.tmp/bench/statistics.json` |

**Key difference from 2.2 series**: Task 1 is NOT a chain. Each task runs in complete isolation (separate project directory, no shared `local.db` accumulation). The purpose is numerical accuracy validation, not knowledge transfer. However, all tasks share the same dev-mode `local.db` and `builtin.db`, so knowledge written by one parallel task CAN be read by another concurrent task (race condition, not controlled).

**Prompt template** (Task 1 style):
```
Relax the crystal structure of [X] ([structure]) using Quantum ESPRESSO and
report the equilibrium lattice constant. After obtaining results, assess your
accuracy — compare with known experimental or literature values. If your result
seems unreasonable, analyze why and try to improve. You have up to 3 total
attempts. Save your final assessment to result.json.
```

Note: Task 1 prompts include "Save your final assessment to result.json" — the 2.2 series does NOT have this. Task 1 prompts do NOT include "starting fresh" anti-context-leak preamble — the 2.2 series does.

**Materials (24 relax)**: Si, C, Ge, Al, Cu, Ag, Au, Pd, Ni, Fe, W, Mo, Na, Li, Mg, Ti, GaAs, SiC, NaCl, MgO, LiF, BN, AlAs, GaN

**Materials (10 bands)**: Si, Ge, GaAs, SiC, MgO, NaCl, LiF, BN, GaN, C (diamond)

**Materials (3 magnetic)**: Fe, Ni, Co

**Materials (3 xTB molecular)**: H2O, CH4, NH3

**Results summary**:
- 40/40 completed (0 timeouts)
- Lattice MARE: 0.93%, pass rate (within 2%): 22/24
- Band gap MAE: 1.94 eV, gap type accuracy: 9/10
- Magnetic MARE: 3.5%
- Mean rounds used: 1.2

**Knowledge system usage (key finding)**:
- 100% of agents (43/43 traces) referenced all 3 knowledge tools (`search_knowledge`, `record_insight`, `record_intent`)
- 60 `search_knowledge` calls, 57 `record_insight` calls, 54 `record_intent` calls across all traces
- 17 findings promoted to `local.db` (the rest were observation/bookkeeping grade, journal-only)
- **This was the first evidence that agents organically use the knowledge system** — before the 2.2 series was even conceived

**Self-correction examples** (from Task 1):
- GaAs: detected mixed PAW+NC Pulay stress, recorded as finding
- AlAs: detected ecutwfc too low → Pulay stress, recorded as finding
- GaAs bands: PBE gap 0.43 eV (correctly identified as PBE underestimate)

**Limitation**: Task 1 used dev-mode `.qmatsuite/knowledge/` (not isolated per-task), so the 17 findings accumulated in a shared `local.db`. This is fine for benchmarking accuracy but means knowledge cross-contamination between parallel tasks was possible (though unlikely to matter given the parallel execution model where most tasks run simultaneously).

### 3.1 Task 2.2 v1 — Pilot (5 sessions)

| | |
|---|---|
| **Sessions** | 5 (3 treatment + 2 control) |
| **Compounds** | GaAs, AlAs, GaP |
| **Script** | `.tmp/pseudo_case_study_v1/` (manual invocations, not a single runner) |
| **DB isolation** | Treatment: shared local.db. Control: isolated via `QMATSUITE_HOME` override |
| **Prompt** | Minimal: "Calculate the equilibrium lattice constant of [X]..." (no retry allowance) |
| **Bug state** | FTS5 implicit-AND active, workflow scope filter active |

**Finding**: 100% write compliance (5/5 sessions recorded insights), 20% search rate (1/5). The 1 search was against an empty DB. No transfer observed. Initial (wrong) conclusion: "agents don't use the knowledge system."

### 3.2 Task 2.2b — Long Chain, FTS5 Broken (16 sessions) — CONTROL

| | |
|---|---|
| **Sessions** | 16 (sessions 01-16) |
| **Compounds** | GaAs, SiC, AlAs, BN, GaP, InP, AlN, InAs (in this order) |
| **Workflows** | Sessions 01-08: relax, Sessions 09-16: bands |
| **Script** | `.tmp/pseudo_chain/run_chain.sh` |
| **DB state** | Empty local.db at start, accumulates to 17 insights |
| **Bug state** | FTS5 implicit-AND active (queries return 0 hits), workflow scope filter active |
| **Wall time** | ~233 min |

**Finding**: 8/16 sessions called `search_knowledge`, but 0/8 searches returned any results. FTS5 implicit-AND made multi-word queries impossible. This retroactively proved agents DO search — the v1 conclusion was wrong. Value as natural control: 0 transfer events.

### 3.3 Task 2.2c — Long Chain, FTS5 Fixed (16 sessions) — TREATMENT

| | |
|---|---|
| **Sessions** | 16 (sessions 01-16) |
| **Compounds** | GaAs, SiC, AlAs, BN, GaP, InP, AlN, InAs (same order as 2.2b) |
| **Workflows** | Sessions 01-08: relax, Sessions 09-16: bands |
| **Script** | `.tmp/pseudo_chain_v2c/run_chain.sh` |
| **Bugs fixed before run** | (1) `_sanitize_fts_query()`: `" ".join()` → `" OR ".join()`, (2) workflow scope filter removed |
| **Wall time** | ~254 min |

**Finding**: 6/16 sessions searched, 6/6 searches returned hits (100% hit rate), 6 STRONG transfer events. The 2.2b→2.2c pair is the cleanest infrastructure-controlled comparison: same compounds, same prompts, same order, only the FTS5 fix changed.

Search result composition: 93% seed (builtin.db), 7% session findings (local.db).

### 3.4 Task 2.2c-ext — Extended Chain, New Compounds (16 sessions)

| | |
|---|---|
| **Sessions** | 16 (sessions 17-32) |
| **Compounds** | GaN, AlSb, InSb, ZnS, CdTe, MgO, CaO, PbTe (in this order) |
| **Workflows** | Sessions 17-24: relax, Sessions 25-32: bands |
| **Script** | `.tmp/pseudo_chain_v2c_ext/run_chain.sh` |
| **DB state** | Inherits 2.2c local.db (>=16 entries). Verifies `local_count >= 16`. |
| **Project** | Fresh project directory (no 2.2c calculations visible) |
| **Wall time** | ~297 min |

**Finding**: 9/16 sessions searched, 15 insights recorded (CaO relax = only session in entire series with 0 insights). Search composition shifted: 86% seed, 14% session findings (doubled from 7%).

**Notable**: InSb bands (session 27) = strongest evidence of predictive knowledge transfer. Agent retrieved InAs band inversion insight, predicted InSb would show same behavior, confirmed by calculation.

**Metrics overcounting bug discovered later**: The `grep -c 'run_calculation'` in `run_chain.sh` overcounted by 3-18x. Only ext phase was affected. Corrected via `.tmp/task_2_2d/audit_metrics_2_2d.py`.

### 3.5 DOS Extension (8 sessions)

| | |
|---|---|
| **Sessions** | 8 (sessions 33-40) |
| **Compounds** | GaN, AlSb, InSb, ZnS, CdTe, MgO, CaO, PbTe (same order as ext) |
| **Workflows** | DOS only |
| **Script** | `.tmp/pseudo_chain_v2c_ext/run_chain_dos.sh` |
| **DB state** | Inherits ext local.db (>=31 entries) |
| **Project** | Same project as ext (agents can see relax + bands calculations) |
| **Wall time** | ~172 min |

**Key finding**: Project state (inspecting prior calculations) was the dominant transfer channel in 6/8 sessions. Knowledge DB dominant only for CaO (used ZnS nbnd lesson) and synergistic for PbTe (SOC knowledge + project state parameters). Established the **dual-channel model**: knowledge DB for cross-compound methodology, project state for same-compound parameter reuse.

### 3.6 Task 2.2d — Controlled A/B (24 sessions)

| | |
|---|---|
| **Sessions** | 24 (4 materials x 2 conditions x 3 workflows) |
| **Materials** | PbTe (strong SOC), InSb (moderate SOC), CdTe (standard), MgO (negative control) |
| **Workflows** | relax → bands → DOS (sequential pipeline per material) |
| **Script** | `.tmp/task_2_2d/run_2_2d.sh` |
| **Design** | A (Naive) = empty local.db. B (Informed) = A's 3 pipeline findings pre-loaded. |
| **Key difference from chain experiments** | Fresh project per material. Only variable = local.db content. |
| **Wall time** | ~661 min |

**CRITICAL CORRECTION**: The initial "awareness tax" narrative for InSb was **substantially wrong**. See section 4.

---

## 4. Corrected Findings (Final Understanding)

### 4.1 FTS5 Bug (2.2b → 2.2c)

The 2-line FTS5 fix (`" OR ".join()` + remove workflow scope filter) is the single most impactful infrastructure change. It transformed search from 0% hit rate to 100%. The 2.2b/2.2c pair is clean causal evidence that infrastructure, not agent behavior, was the bottleneck.

### 4.2 Builtin Overwhelm / BM25 Cross-Collection Bug (2.2d)

**Discovered during**: 2.2d audit (`.tmp/task_2_2d/AUDIT_AWARENESS_TAX.md`)

The `search()` method searches `builtin.db` (45 entries) and `local.db` (few entries) independently, then merges by BM25 score. BM25 scores from different-sized collections are not comparable — the 45-document builtin DB produces systematically higher absolute scores than a 4-document local DB.

**Impact**: Queries with 5+ generic terms (e.g., "InSb band structure narrow gap semiconductor QE") return 10/10 builtin results, 0 local results. The pre-loaded InSb-specific insights were **never retrieved** in 2.2d B05.

Across all 2.2d B-condition sessions: only 3/8 searches retrieved any local results (37.5%). Strong local retrieval (>=2 results): 2/8 (25%). This means the experiment's core assumption — that B agents had access to pre-loaded knowledge — was only partially true.

**Fix applied post-experiments (R-series)**: Reserved 3 slots for local results in search output, regardless of BM25 score. This is part of the R1-R11 refinements.

### 4.3 "Awareness Tax" Is Wrong — Cell Size Confound (2.2d InSb)

The REVIEW document's "awareness tax" narrative claimed:
> Knowledge about PBE's failure to open the InSb gap drove the B agent to escalate effort (+162% pipeline, B06 skipped).

**Actual cause** (from `.tmp/task_2_2d/AUDIT_AWARENESS_TAX.md`):

1. **B05 never received InSb-specific knowledge** (see 4.2 above — 0 local search results)
2. **Cell size confound**: A04 used EOS (7 single-point calcs on 2-atom primitive cells via `quick_run`), B04 used vc-relax (1 calc on 8-atom conventional cell). B05 inherited the 8-atom cell (112 electrons), A05 inherited the 2-atom cell (28 electrons). O(N^3) scaling → ~64x theoretical cost ratio for SCF, fully explaining the 5.4x wall time difference.
3. Both A05 and B05 independently discovered PBE zero-gap failure from their own training knowledge, not from retrieved insights.

**Corrected interpretation by material**:

| Material | Initial Claim | Corrected Claim |
|----------|--------------|-----------------|
| InSb (+162%) | "Awareness tax" — knowledge of unsolvable problem | Cell-size confound + stochastic variation. Knowledge never retrieved. |
| CdTe (-9.1%) | "Cleanest positive transfer" | Not attributable — 0 local search results in B sessions. |
| PbTe (-0.1%) | "Effort redistribution" | Partially correct — B01 retrieved 4 local results (short query). B02/B03 got 0 local. |
| MgO (-5.9%) | "Negative control, no effect" | Correct. |

### 4.4 Grep-Based Metrics Overcounting

All runner scripts extract tool counts via `grep -c 'run_calculation' trace.jsonl`. This matches tool results echoing the name, reasoning text referencing the tool, and MCP initialization listings — not just actual invocations. Overcounting factor: 3-18x. Only the ext phase `metrics.json` was affected (others were independently verified).

**Lesson**: Future experiments must use proper JSONL parsing (e.g., `audit_metrics_2_2d.py` pattern: parse only `type=assistant` messages with `type=tool_use` content blocks).

### 4.5 Cell Size as Confound

The prompts do not specify primitive vs conventional cell. Different relaxation methodologies (EOS via `quick_run` vs vc-relax via `run_calculation`) produce different cell types, which propagate to bands/DOS via project state. This is a confound for any A/B comparison where A and B use different relaxation strategies.

**Mitigation for next experiment**: Add to prompt: "Use a primitive cell containing the minimum number of atoms."

---

## 5. Claims That Survive Audit

| Claim | Evidence |
|-------|---------|
| FTS5 fix enabled knowledge transfer (0 → 6 STRONG events) | 2.2b vs 2.2c controlled pair |
| Agents reliably write insights (98.8% compliance) | 83/84 completed sessions recorded |
| Search rate is 37-75%, reactive not proactive | Consistent across all phases |
| Session-generated findings grow as DB accumulates (7% → 14% → 30%) | 2.2c → ext → DOS composition |
| Project state dominates same-compound cross-workflow transfer | DOS phase (6/8 sessions) |
| Knowledge DB enables cross-compound transfer | InSb prediction (session 27), MgO→CaO template (31) |
| PbTe bands→DOS shows strongest per-compound efficiency gain (-75% run_calc) | Session 32→40 |
| Agents never spontaneously synthesize L4/L5 insights | 0 patterns/principles in 41 insights |

---

## 6. What Changed in MCP (Post-Experiments, Pre-Next-Run)

### R-Series Refinements (R1-R11)

| ID | Change | Impact on Experiments |
|----|--------|----------------------|
| R1 | Sliding window nudge (count since last synthesis) | Nudges fire based on pending findings, not global count |
| R2 | Simultaneous L3→L4 and L4→L5 nudge | Both findings→patterns and patterns→principles can fire |
| R3 | Soft/strong nudge tone | Search gets soft hint; record_insight gets directive nudge |
| R4 | Stochastic nudge probability (`QMS_NUDGE_PROBABILITY` env) | Can control nudge frequency for experiments |
| R5 | `list_insights(mode="pending")` | Agents can review unsynthesized findings |
| R6 | Pending count header in list_insights | Shows "N findings since last pattern synthesis" |
| R7 | 14-char short IDs in output | Less noise in agent responses |
| R8 | Short ID prefix resolution | Agents can reference insights by short prefix |
| R9 | Remove content truncation in list_insights | Full insight text visible for synthesis |
| R10 | Search-before-calculate in preamble | Preamble now says "1. search_knowledge — check what's known" |
| R11 | Upvotes/downvotes visible in search/list results | Agents see citation confidence |

### G-Series Gap Fixes (G1-G9)

| ID | Change | Impact on Experiments |
|----|--------|----------------------|
| G1 | Citation summary uses actual applied counts | Accurate feedback on citation success |
| G2 | Reference error hint is grade-aware | Better guidance for pattern/principle creation |
| G3 | `record_intent` in preamble workflow | Agents should now state plans before calculating |
| G4 | `get_results_summary` hints `record_insight` | Post-calculation nudge to record findings |
| G6 | Preamble explains upvotes/downvotes semantics | Agents understand citation voting |
| G7 | Tags parsed to list (not JSON string) | Cleaner search/list output |
| G8 | Mode validation in `list_insights` | Error on invalid mode |
| G9 | Mode field in `list_insights` response | Response includes which mode was used |

### New Preamble (Critical for Behavior Change)

```
WORKFLOW FOR EVERY TASK:
1. search_knowledge — check what's known before calculating
2. record_intent — state your plan, referencing knowledge entries you'll use
3. Execute calculations (create_calculation, run_calculation, etc.)
4. record_insight — record verified results as grade='finding'
5. Respond to synthesis nudges when they appear

CITATIONS — when recording insights:
  Format: citations="ID:up,ID:down"
  up = your calculation CONFIRMS this knowledge was correct
  down = your calculation CONTRADICTS this knowledge
```

### Reserved Slots Fix (Addresses Builtin Overwhelm)

Search now reserves 3 slots for local results regardless of BM25 score, preventing seed knowledge from completely drowning out session-generated findings.

---

## 7. Key Metrics Across All Experiments

| Experiment | Sessions | Search Rate | Hit Rate | STRONG Transfers | Insights Recorded | Write Compliance |
|------------|----------|-------------|----------|-----------------|-------------------|-----------------|
| 2.1 agent test matrix | 9-17/run (10 runs) | 0% | N/A | N/A (tool integration test) | N/A | N/A |
| SOC case study | 3+1 control | TBD | TBD | TBD | TBD | TBD |
| Task 1 benchmark | 40 (parallel) | ~100%* | N/A | N/A (isolated) | 17 (promoted) | ~100% |
| 2.2 v1 | 5 | 20% | 0% (empty DB) | 0 | 5 | 100% |
| 2.2b (control) | 16 | 50% | 0% (FTS5 bug) | 0 | 17 | 100% |
| 2.2c (treatment) | 16 | 37.5% | 100% | 6 | 16 | 100% |
| 2.2c-ext | 16 | 56.3% | 100% | 8 | 15 | 93.8% |
| DOS | 8 | 62.5% | 100% | see note | 10 | 100% |
| 2.2d Phase A | 12 | 75% | 100% | N/A (baseline) | 12 | 100% |
| 2.2d Phase B | 11* | 63.6% | 100%** | see 4.2 | 11 | 100% |
| **Total (knowledge expts)** | **124** | | | | | **~99%** |

*Task 1 grep counts are approximate (60 search references across 43 traces ≈ 100% of agents used search at least once). **Excluding B06 (skipped). ***100% hit rate but only 37.5% of hits included local results (builtin overwhelm).

---

## 8. Experiment Data Locations

| Artifact | Path |
|----------|------|
| 2.1 agent test runs (10 runs) | `.tmp/agent_mcp_test/run_*/` |
| 2.1 REVIEW (analysis) | `.tmp/agent_mcp_test/run_20260221_121301/REVIEW.md` |
| SOC case study sessions | `.tmp/soc_case_study/session_{1_bi,2_pb,3_gaas}/` |
| SOC case study control | `.tmp/soc_case_study/control_qms_home/`, `.tmp/soc_case_study/control_project/` |
| SOC case study shared project | `.tmp/soc_case_study/shared_project/` |
| SOC trace analyzer | `.tmp/soc_case_study/analyze_traces.py` |
| Archived partial 2.2b | `.tmp/pseudo_chain_partial_archived/` |
| Knowledge system inventory | `.tmp/knowledge_review/KNOWLEDGE_REVIEW.md` |
| Task 1 benchmark script | `.tmp/bench/run_benchmark.sh` |
| Task 1 task definitions | `.tmp/bench/tasks.jsonl` |
| Task 1 run data | `.tmp/bench/run_20260227_112901/` (per-task dirs + `traces/`) |
| Task 1 results | `.tmp/bench/summary_table.md`, `.tmp/bench/paper_tables.md`, `.tmp/bench/statistics.json` |
| Task 1 knowledge audit | `.tmp/bench/knowledge_audit_20260228_112646.md` |
| Task 1 failure analysis | `.tmp/bench/failure_analysis.md` |
| 2.2 v1 pilot | `.tmp/pseudo_case_study_v1/` |
| 2.2b sessions + DB | `.tmp/pseudo_chain/sessions/`, `.tmp/pseudo_chain/local_db_final_2_2b.db` |
| 2.2c sessions + DB | `.tmp/pseudo_chain_v2c/sessions/`, `.tmp/pseudo_chain_v2c/local_db_final_2_2c.db` |
| 2.2c-ext sessions + DB | `.tmp/pseudo_chain_v2c_ext/sessions/` (17-32), `.tmp/pseudo_chain_v2c_ext/local_db_after_bands.db` |
| DOS sessions + DB | `.tmp/pseudo_chain_v2c_ext/sessions/` (33-40), `.tmp/pseudo_chain_v2c_ext/local_db_final_dos.db` |
| 2.2d all sessions | `.tmp/task_2_2d/{A,B}_{PbTe,InSb,CdTe,MgO}/sessions/` |
| 2.2d audited metrics | `.tmp/task_2_2d/metrics_2_2d_audited.json` |
| 2.2d awareness tax audit | `.tmp/task_2_2d/AUDIT_AWARENESS_TAX.md` |
| Chain reports | `.tmp/pseudo_chain/CHAIN_REPORT.md`, `.tmp/pseudo_chain_v2c/CHAIN_REPORT_V2C.md`, etc. |
| Main review | `docs/history/reviews/REVIEW_TASK_2_2_KNOWLEDGE_DISTILLATION.md` |
| 2.2d interim report | `docs/history/reviews/TASK_2_2D_INTERIM_REPORT.md` |
| InSb incident report | `docs/history/reviews/TASK_2_2D_INSB_INCIDENT.md` |

---

## 9. Lessons for Next Experiment Design

### 9.1 Must-Do Isolation

1. `--no-session-persistence` on every `claude -p` call
2. `rm -rf $PROJECT_DIR/.claude $PROJECT_DIR/CLAUDE.md` before each session
3. `env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT` to prevent nesting detection

### 9.2 Must-Do Confound Controls

1. **Cell type**: Add "Use a primitive cell containing the minimum number of atoms" to prompts. The 2.2d InSb confound (2-atom vs 8-atom) invalidated the A/B comparison.
2. **Proper metrics extraction**: Use JSONL parsing (not `grep -c`). Template: `.tmp/task_2_2d/audit_metrics_2_2d.py`
3. **Reserved slots for local search**: Already fixed in R-series. Verify by checking that B-condition sessions actually retrieve pre-loaded insights.

### 9.3 What the New MCP Should Change

| Behavior | Old (pre-R) | New (post-R/G) | Expected Delta |
|----------|-------------|-----------------|----------------|
| Search rate | 37-75% (reactive) | Higher (preamble says "search first") | Expect >60% |
| `record_intent` usage | ~0% | >0% (preamble step 2) | First data point |
| Citation voting | 0 (not available) | >0 (format explained in preamble) | First data point |
| L4 pattern synthesis | 0 (no nudge system) | >=1 (nudge fires at 8 findings) | Key paper evidence |
| Nudge response rate | N/A | Measurable | First data point |
| Local search retrieval in B sessions | 37.5% (builtin overwhelm) | Higher (reserved slots) | Must verify |

### 9.4 Recommended Next Experiment

**Task 2.3: Improved MCP Chain (16 sessions)**

Re-run the 2.2c chain with the new MCP:
- Same 8 compounds: GaAs, SiC, AlAs, BN, GaP, InP, AlN, InAs
- Same order: sessions 01-08 relax, sessions 09-16 bands
- Same prompts **plus** cell-type control: "Use a primitive cell containing the minimum number of atoms"
- Clean local.db, shared project, accumulating knowledge
- 2.2c IS the control (same compounds, old MCP)

**New metrics to collect**:
- `record_intent` call count per session
- Citation counts (up/down) per insight
- Nudge fire events (check if agent records L4 pattern after session 08)
- Local vs builtin retrieval ratio per search call (verify reserved slots work)

**Key hypotheses**:
1. Search rate increases from 37.5% to >60% (preamble "search first")
2. `record_intent` usage >50% (preamble step 2)
3. At least 1 L4 pattern emerges (nudge fires after 8 findings)
4. Citation data exists (first time ever)
5. Local retrieval rate >80% when searching (reserved slots)

**If successful**, the narrative is: "Same chain, improved guidance → qualitatively different knowledge behavior (flat L3 accumulation → hierarchical distillation with L4 emergence)."

### 9.5 Optional Follow-Up Experiments

1. **Re-run 2.2d A/B with cell-type control + reserved slots**: The original 2.2d was confounded. A clean re-run with fixed BM25 + cell-type prompting would provide actual causal evidence for knowledge content effects.
2. **Seed-free chain**: Run with empty `builtin.db` to isolate session-to-session transfer from seed knowledge (currently 86-93% of results are seeds).
3. **Awareness tax isolation**: Repeat InSb with (a) descriptive-only knowledge ("PBE gives zero gap"), (b) prescriptive with available fix ("use SOC"), (c) prescriptive with unavailable fix ("use HSE06"). Requires fixed BM25 so knowledge is actually retrieved.
