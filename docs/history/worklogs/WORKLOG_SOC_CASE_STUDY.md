# SOC Knowledge Distillation Case Study Worklog

**Date**: 2026-02-27
**Status**: PAUSED — blocked on serial QE compute time
**Purpose**: Measure knowledge transfer across agent sessions via QMatSuite's distillation system

## Experiment Design
- 4 sessions: Bi (learn), Pb (transfer), GaAs (consolidate), Pb-control (baseline)
- Sessions 1-3 share repo-level `.qmatsuite/` (shared local.db + pseudo libraries + provenance)
- Control uses isolated `QMATSUITE_HOME` (no prior knowledge, SSSP only via symlink)
- Each session is an isolated Claude process (no conversation context carry-over)
- Knowledge channel: only `local.db` (record_insight -> search_knowledge)

---

## Pre-flight

### QE Status
- QE installed: `pw.x` at `$HOME/src/q-e-qe-7.5/bin/pw.x`
- `qms engine verify qe`: OK
- **Single-core only** — no MPI parallelization configured

### Pseudo Libraries Status (before experiment)
- SSSP: installed (precision/1.3.0 + efficiency)
- PseudoDojo: ONLY `nc-sr_pbe_standard` (scalar-relativistic)
- PseudoDojo `nc-fr_pbe_standard` (full-relativistic): **NOT installed** (agent must download)
- GIPAW, GBRV, SG15, HGH, SCAN_TM: present (mostly empty or sr-only)

### Pseudo Libraries Status (after Session 1 partial)
- PseudoDojo `nc-fr_pbe_standard` v0.4: **NOW INSTALLED** (70 UPFs, downloaded by Session 1 agent)
- Location: `.qmatsuite/libraries/pseudo/PseudoDojo/nc-fr_pbe_standard/0.4/`

### Knowledge Store Baseline
- builtin.db: 45 entries (rebuilt with current schema on 2026-02-27 — old one had schema mismatch, `last_validated` column missing)
- local.db: 14 entries (prior findings from agent matrix runs — QE SCF/relax/magnetic, xTB, all irrelevant to SOC)
- SOC builtin entry exists: "Spin-orbit coupling (SOC) is essential for heavy elements..." — mentions lspinorb, noncolin parameters but **does NOT mention FR pseudopotential requirement**
- FTS search confirmed working: `search_knowledge("spin orbit")` returns the SOC entry

### Infrastructure Fix Needed: builtin.db Rebuild
- builtin.db had 20 entries (old schema), BUILTIN_ENTRIES has 45
- `build_builtin_db()` failed with `sqlite3.OperationalError: table insights has no column named last_validated`
- **Fix**: deleted old builtin.db, re-ran `build_builtin_db()` → now 45 entries, FTS working
- This must be done before any fresh experiment runs

### Directory Structure
```
.tmp/soc_case_study/
  shared_project/             # Sessions 1-3 run here
    .mcp.json                 # Points to repo .venv/bin/python (absolute path)
    project.qms.yml           # Created by Session 1 agent
    calculations/             # Created by Session 1 agent
      bi_soc_bands/raw/       # Partial Session 1 run artifacts
    structures/               # Bi rhombohedral structure
    pseudo/                   # FR Bi.upf copied here by agent
  control_project/            # Control runs here
    .mcp.json                 # Same + QMATSUITE_HOME env override
  session_1_bi/               # Trace output for Session 1 (181 lines, 324K)
    trace.jsonl               # stream-json trace (INCOMPLETE — session killed)
    timing.txt                # Start time only (session killed before completion)
  session_2_pb/               # (empty — not started)
  session_3_gaas/             # (empty — not started)
  control_pb/                 # (empty — not started)
  control_qms_home/           # Isolated .qmatsuite for control
    libraries/pseudo/SSSP -> (symlink to repo SSSP)
    knowledge/                # Empty (no local.db)
  analyze_traces.py           # Trace analysis script (ready to use)
```

### .mcp.json Setup
- shared_project: absolute python path (`$HOME/QMatSuite/.venv/bin/python`), standard MCP instructions ✓
- control_project: same + `"env": {"QMATSUITE_HOME": ".../control_qms_home"}` ✓
- No `.claude/` or `CLAUDE.md` in either project directory ✓

### Knowledge Isolation Design
- Path resolution: `_try_find_repo_root()` in `core/paths.py` uses `Path(__file__)` (installed module location), NOT cwd
- This means the MCP server **always** resolves to repo-root `.qmatsuite/` regardless of agent's working directory
- Sessions 1-3: use repo-level `.qmatsuite/knowledge/local.db` (shared knowledge channel) — this works because they share the same MCP server binary
- Control: `QMATSUITE_HOME` env var in `.mcp.json` → `control_qms_home/` → isolated local.db
- SSSP shared via symlink so control agent doesn't waste time downloading

### Agent Spawn Pattern (from agent_test_matrix.sh)
```bash
cd "$task_dir"
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT 2>/dev/null || true
claude -p \
    --dangerously-skip-permissions \
    --output-format stream-json --verbose \
    --no-session-persistence \
    "$task_prompt"
```
Key flags:
- `-p`: print/non-interactive mode
- `--dangerously-skip-permissions`: bypass all permission checks
- `--output-format stream-json`: full trace capture
- `--verbose`: enhanced logging
- `--no-session-persistence`: prevent session resume contamination
- No `--no-memory` flag exists in Claude CLI; memory isolation via prompt instruction only
- No `--max-turns` flag; using `timeout 7200` for 2-hour hard limit

---

## Session 1: Bismuth SOC (First Encounter) — INCOMPLETE

### Timing
- **Start**: 2026-02-27T16:04:44
- **End**: killed at ~17:45 (approx 100 min wall time)
- **Exit code**: N/A (killed)
- **Trace**: 181 lines, 324K, 68 tool calls

### What the Agent Did (Chronological)

#### Phase A: Discovery & Planning (tool calls 1-16)
1. Created TODO list for tracking
2. `init_project("Bi SOC Band Structure")` ✓
3. `verify_engine("qe")` ✓
4. `list_workflows("qe")` → found `bands` workflow (scf → bandspw → bands)
5. **`search_knowledge("spin-orbit coupling SOC band structure", engine="qe")`** → found builtin SOC entry (lspinorb, noncolin parameters)
6. `search_parameters("spin-orbit coupling", engine="qe")` → found `lspinorb`, `noncolin` tags
7. `list_available_resources(engine="qe", elements=["Bi"])` → saw installed libraries
8. `get_presets(engine="qe", workflow="bands")` → found `SOC_CANONICAL` magnetism preset
9. Additional parameter searches for noncolin details, ecutwfc
10. `preview_compilation(engine="qe", workflow="bands", presets={"magnetism":"SOC_CANONICAL"})` → saw compiled params
11. `import_structure(file_content=<Bi CIF>, format="cif", name="Bi_rhombohedral")` → Bi6, R-3m, 6 atoms

**Key observation**: Agent immediately found and recognized `SOC_CANONICAL` preset. It also called `search_knowledge` proactively — the builtin entry told it about lspinorb/noncolin but NOT about FR pseudo requirements.

#### Phase B: Pseudo Investigation (tool calls 17-46)
After `create_calculation` and inspecting the auto-resolved species map (SSSP `Bi_pbe_v1.uspp.F.UPF`), the agent said:

> "The current pseudo is Bi.UPF from SSSP. For SOC I need a **fully relativistic** pseudopotential."

Then spent ~30 tool calls systematically searching for FR pseudos:
- Glob patterns for `*Bi*.UPF`, `*Bi*.upf` across repo and `~/.qmatsuite`
- `find` commands across all library directories
- Read UPF headers of SSSP, SG15, PseudoDojo-SR, HGH, GIPAW Bi pseudos
- Checked `relativistic_type` markers in all Bi pseudos
- Concluded: **all installed Bi pseudos are scalar-relativistic**

**Key observation**: The agent's LLM knowledge about SOC requirements (FR pseudos needed) was correct and prevented a crash. The experiment hypothesis assumed the agent would crash first and learn, but this agent preemptively checked. This is important data — the "first encounter" was NOT a blind crash.

#### Phase C: FR Pseudo Download & Resolution (tool calls 47-54)
47. `download_pseudo_library(library="pseudodojo", variant="nc-fr_pbe_standard", version="0.4")` → **success, 70 UPFs**
48. `auto_resolve_species_map(calc_ulid=..., library="pseudodojo", variant="nc-fr_pbe_standard")` → **BUG: returned SSSP `Bi_pbe_v1.uspp.F.UPF` instead of PseudoDojo FR `Bi.upf`**
49. Checked PseudoDojo FR directory → found `Bi.upf`
50. `set_species_map(calc_ulid=..., species_map={"Bi": {"pseudopot": "Bi.upf", "library": "PseudoDojo", "variant": "nc-fr_pbe_standard"}})` → manual workaround ✓
51-54. Verified FR pseudo is truly FR by reading header, copied to project `pseudo/` directory

**Soft gap confirmed**: `auto_resolve_species_map` with `library="pseudodojo"` returned the SSSP pseudo. The agent had to manually use `set_species_map`. This matches the soft gap SOC-S2 from the review.

#### Phase D: Parameter Setup & First Run (tool calls 55-61)
55. `set_parameters` for SCF step (lspinorb=true, noncolin=true, ecutwfc=50)
56. `generate_kpath(structure_selector="Bi_rhombohedral", points_per_segment=20)` → Γ-L-B₁-B-Z-Γ-X-Q-F-P₁-Z-L-P
57. `set_parameters` for bands step
58. `inspect_calculation(dry_run=True)` → confirmed lspinorb/noncolin in input ✓
59. Verified pseudo file in project directory
60. `record_intent` (not `record_insight`) — logged intent to run
61. **`run_calculation(run_mode="full")`** → SCF converged (11 iterations, E=-982.72 Ry, ~65 min wall) BUT **bandspw CRASHED**: "too many bands are not converged"

#### Phase E: Error Recovery (tool calls 62-68)
The agent diagnosed the crash:

> "Bi pseudo has Zval=15, so 6 atoms × 15 = 90 electrons. In SOC/noncollinear mode, each spinor band holds 1 electron, so nbnd=48 is way too small."

62-65. Read bandspw output, found `nbnd=48` (default) insufficient for 90-electron SOC
66. `set_parameters(params={"SYSTEM": {"nbnd": 120}})` for step 1
67. Updated TODO list
68. **`run_calculation(run_mode="incremental")`** → skipped SCF (already done), started new bandspw run

**Session killed here** — the second bandspw run was in progress when we stopped.

### Performance Bottleneck: Why We Stopped

The Bi SOC calculation is extremely compute-intensive on a single core:
- **6 Bi atoms**, 90 electrons, full-relativistic SOC, noncollinear spin
- Dense grid: 68,483 G-vectors, FFT dimensions (40, 40, 108)
- Estimated max dynamical RAM: **2.08 GB** (for single-core SCF)
- SCF: 11 iterations, ~65 minutes wall time (single-core)
- Bands step: 260+ k-points along the path, ~5 min per k-point → **estimated 20+ hours single-core**
- Second bands attempt with nbnd=120 was also running single-core

**Root cause**: No MPI parallelization. QE is running `pw.x` as a serial process. Each agent session with 6+ heavy atoms and SOC will take hours.

**The experiment requires parallel QE** — either MPI (`mpirun -np N pw.x`) or OpenMP (`export OMP_NUM_THREADS=N`), or both. Without this, each session could take 2-8 hours of wall time, making the 4-session experiment impractical in a single day.

### Artifacts Preserved
- `session_1_bi/trace.jsonl`: 181 lines, 324K — full tool call log up to kill point
- `shared_project/calculations/bi_soc_bands/raw/scf.out`: completed SCF output (first run)
- `shared_project/calculations/bi_soc_bands/raw/bandspw.out`: first failed bandspw output
- `shared_project/calculations/bi_soc_bands/raw/scf.out`: second SCF restarted (from incremental run)
- `shared_project/pseudo/Bi.upf`: FR pseudopotential copied by agent
- PseudoDojo FR library: installed at `.qmatsuite/libraries/pseudo/PseudoDojo/nc-fr_pbe_standard/0.4/` (70 UPFs)

---

## Experiment Observations So Far

### 1. Agent Did NOT Crash on SSSP (Hypothesis Partially Invalidated)
The experiment assumed Session 1 would blindly use SSSP, crash, then learn. Instead, the agent:
- Called `search_knowledge` proactively and found the SOC builtin entry
- Used its LLM knowledge about SOC requiring FR pseudos
- Checked pseudo headers BEFORE running
- This is **valuable positive data**: the agent's existing knowledge + builtin KB entry were sufficient to avoid the SSSP crash

### 2. `auto_resolve_species_map` Bug Confirmed
When called with `library="pseudodojo", variant="nc-fr_pbe_standard"`, the tool returned the SSSP pseudo instead. The agent worked around this by using `set_species_map` manually. This confirms soft gap SOC-S2 from the review.

### 3. nbnd Default Is Wrong for SOC
QE's default nbnd is calculated assuming collinear spin (2 electrons per band). In SOC/noncollinear mode, it should be at least n_electrons. This is a gap in the preset system — the `SOC_CANONICAL` preset should set an appropriate nbnd.

### 4. Bi Is Too Heavy for Single-Core Demo
6 atoms × 15 electrons × SOC × noncollinear = extremely expensive. For the case study, consider:
- Using 2-atom primitive cell instead of 6-atom hexagonal cell
- Using lighter elements (GaAs: 2 atoms, Z=31/33 vs Bi: Z=83)
- Or implementing MPI parallelization

---

## What Needs to Happen Before Resuming

### P0: Parallel QE Computation
- **Option A**: Configure MPI runner — `mpirun -np N pw.x < input > output`
  - Need to check if QE was compiled with MPI support
  - Need to update the QE engine runner to use mpirun
  - Typical: 4-8 cores reduces SCF time from 65 min → 10-15 min
- **Option B**: OpenMP threading — `export OMP_NUM_THREADS=N`
  - Simpler but less efficient for plane-wave DFT
  - Check if QE was compiled with OpenMP
- **Option C**: Use smaller systems
  - Bi primitive cell (2 atoms, rhombohedral) instead of hexagonal (6 atoms)
  - GaAs (2 atoms) as primary test case
  - But Bi was specifically chosen for being a strong SOC material
- **Recommended**: Option A + C — enable MPI and also use smaller cells

### P1: Decide Whether to Restart Session 1
Options:
- **Resume**: The shared_project already has the structure, calculation, and FR pseudos set up. Could re-run from where we left off (incremental bands step). But the trace is incomplete and the agent didn't call `record_insight` yet.
- **Clean restart**: Wipe shared_project and start fresh. Loses ~100 min of agent work but gives a clean trace. With parallel QE, the full session would complete in ~30 min.
- **Recommended**: Clean restart with parallel QE and possibly smaller Bi cell

### P2: Consider Experiment Design Adjustments
Given that the agent did NOT crash on SSSP (used LLM knowledge to avoid it):
- The "knowledge distillation" story shifts from "learn from crash" to "learn efficient workflow"
- Session 1's insight would be about the `auto_resolve_species_map` bug workaround and nbnd fix
- Session 2's benefit would be skipping the long pseudo investigation phase
- This is actually a MORE interesting story: the agent learns QMatSuite-specific procedural knowledge that no LLM has

---

## Knowledge Snapshots

### Before Experiment (Baseline)
- Builtin entries: 45
- Local entries: 14
- SOC-related local entries: 0
- Local entry topics: Al vc-relax, Si vc-relax, xTB H2O, Mo vc-relax, Ag vc-relax, Li vc-relax, NaCl vc-relax, diamond bands, Ni magnetic, Fe magnetic, xTB NH3, Co magnetic, BN bands, MgO vc-relax

### After Session 1 (Partial — agent killed before record_insight)
- Local entries: still 14 (agent used `record_intent`, not `record_insight`)
- PseudoDojo FR installed (side effect preserved)

### Sessions 2-3, Control
(not started)

---

## Files Reference

| File | Purpose |
|------|---------|
| `.tmp/soc_case_study/shared_project/.mcp.json` | MCP config for Sessions 1-3 |
| `.tmp/soc_case_study/control_project/.mcp.json` | MCP config for Control (with QMATSUITE_HOME isolation) |
| `.tmp/soc_case_study/session_1_bi/trace.jsonl` | Session 1 stream-json trace (181 lines, incomplete) |
| `.tmp/soc_case_study/session_1_bi/timing.txt` | Session 1 start time |
| `.tmp/soc_case_study/analyze_traces.py` | Trace analysis script (ready for Phase 5) |
| `docs/history/reviews/SPECIAL_CALC_PSEUDO_REVIEW.md` | Pre-experiment infrastructure review |
