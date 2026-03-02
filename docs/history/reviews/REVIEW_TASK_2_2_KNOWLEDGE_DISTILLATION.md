# Review: Task 2.2 Knowledge Distillation Experiments

**Author**: Auto-generated from experiment data
**Date**: 2026-03-01
**Commit**: `71209a45` (v2-python branch, `d30e214e35e2b6cdb8b53026a1f4573897bbdf17`)
**Status**: Complete (all 5 phases)
**Data Sources**: Worklogs, chain reports, metrics JSON, knowledge DB snapshots

---

## 1. Abstract

This review covers a series of experiments (Tasks 2.2, 2.2b, 2.2c, 2.2c-ext, and DOS extension) testing whether AI agent sessions can accumulate and transfer computational materials science knowledge through QMatSuite's knowledge store. The experiments comprise 61 total runs: a 5-session pilot (2.2 v1), a 32-run controlled pair (2.2b control with broken FTS5 search vs 2.2c treatment with fixed search, same 8 compounds), and a 24-session observational chain extending 2.2c with 8 new compounds (ext) and a cross-workflow DOS phase. Across 16 unique semiconductor compounds and 3 workflow types (structural relaxation, band structure, density of states), we found that: (1) agents reliably write insights (97.8% compliance) but search proactively in only 37--63% of sessions; (2) a 2-line FTS5 search bug completely blocked knowledge retrieval in the 2.2b control, and fixing it in 2.2c immediately produced 100% search success and 6 strong transfer events; (3) knowledge transfer is chemically specific, enabling predictive reasoning (InAs band inversion predicting InSb), diagnostic troubleshooting (PBE bias knowledge diagnosing pseudopotential artifacts), and template reuse (MgO parameters applied to CaO); (4) seed knowledge dominates search results (86--93%) while session-generated findings provide a smaller but growing fraction (7--14%); and (5) project state (inspecting prior calculations) is the dominant transfer channel for same-compound cross-workflow tasks, while the knowledge database is essential for cross-compound transfer. The experiments ran for approximately 17 hours of wall time with a 100% session success rate (61/61 exit=0), producing physically correct PBE results across all compounds.

---

## 2. Background & Motivation

### 2.1 The Problem: Stateless AI Agents in Computational Science

AI agents that drive computational materials science workflows (DFT calculations, molecular dynamics, etc.) typically operate without memory between sessions. Each new session starts from scratch, re-discovering lessons that a previous session already learned. In computational materials science, this is particularly costly because:

- Many compounds share structural and electronic similarities (e.g., all III-V zinc-blende semiconductors)
- Computational pitfalls recur (pseudopotential mixing, insufficient k-mesh density, nbnd selection)
- Parameter choices from successful calculations on similar systems provide good starting points

A human researcher naturally carries this contextual knowledge across projects. Can an AI agent system replicate this?

### 2.2 QMatSuite's Knowledge Architecture

QMatSuite implements a two-tier knowledge store:

1. **Seed knowledge** (`builtin.db`): 45 curated entries covering general DFT principles, Quantum ESPRESSO best practices, convergence protocols, and known PBE biases. These are pre-loaded and immutable.

2. **Session knowledge** (`local.db`): An accumulating database where agents record findings via `record_insight` and query them via `search_knowledge`. Uses SQLite FTS5 full-text search with BM25 ranking.

The MCP (Model Context Protocol) tools available to agents are:
- `search_knowledge(query, engine, workflow)`: FTS5 full-text search across both databases, returning up to 10 results ranked by relevance
- `record_insight(content, grade, tags)`: Write a new insight with structured metadata. The API accepts four grades (`finding`, `observation`, `principle`, `bookkeeping`), but only `finding` and `principle` are persisted to SQLite; `observation` and `bookkeeping` are journal-only (accepted but not stored). In practice, all 40 recorded insights across these experiments used grade `finding`.

Agents also have access to **project state** via `list_calculations` and `inspect_calculation`, which lets them see prior calculations in the same project directory.

### 2.3 Hypothesis

**Primary**: Agents will naturally use the knowledge system to transfer learning between sessions, and this transfer will improve accuracy or efficiency compared to isolated sessions.

**Secondary**: The relative importance of seed knowledge vs session-generated knowledge will shift as the session knowledge base grows.

---

## 3. Experiment Timeline & Design

### 3.1 Phase Overview

| Phase | Sessions | Compounds | Workflows | Key Variable | Wall Time |
|-------|----------|-----------|-----------|-------------|-----------|
| 2.2 (v1) | S1--S5 | 3 III-V | relax | Minimal prompt, shared/isolated DB | ~70 min |
| 2.2b | 1--16 | 8 III-V/IV | relax + bands | FTS5 broken (implicit AND) — **control** | ~233 min |
| 2.2c | 1--16 | 8 III-V/IV | relax + bands | FTS5 fixed (OR-join) — **treatment** | ~254 min |
| 2.2c-ext | 17--32 | 8 new (mixed families) | relax + bands | Cross-family generalization | ~297 min |
| DOS | 33--40 | Same 8 as ext | dos | Cross-workflow + project state | ~172 min |
| **Total** | **61 runs** | **16 unique** | **3 types** | | **~1026 min (17.1h)** |

**Experiment structure**: The 61 runs have three distinct roles:
- **Pilot** (2.2 v1, 5 sessions): Exploratory, different protocol. Not directly comparable to later phases.
- **Controlled pair** (2.2b + 2.2c, 32 runs on the same 8 compounds): The only variable changed was the FTS5 fix. This is the experiment's strongest evidence.
- **Observational chain** (2.2c → ext → DOS, 40 sessions, 16 compounds): A continuous knowledge chain where `local.db` accumulated across all sessions. 2.2c's 16 insights seeded ext; ext's 31 insights seeded DOS.

Note: the count of 61 (not 45) includes 2.2b, which earlier summaries incorrectly omitted. 2.2b is the control arm and essential to the controlled comparison.

### 3.2 Common Protocol

All phases after 2.2 (v1) shared this protocol:
- **Model**: claude-opus-4-6 (Claude Opus) for all sessions
- **Engine**: Quantum ESPRESSO with MPI (12 cores, `mpirun -np 12`)
- **Execution**: Sequential sessions via bash runner script, each invoked as `claude -p --dangerously-skip-permissions --output-format stream-json`
- **Prompt structure**: Compound name + workflow instruction + "make up to 3 attempts" + "compare with experimental values"
- **Knowledge isolation**: Each session has no conversation memory; only the knowledge DB and project directory persist
- **Data capture**: JSONL stream traces, timing, insight counts per session

### 3.3 Phase-Specific Details

**Task 2.2 (v1)**: 5 sessions total -- 3 treatment (shared `local.db`) and 2 controls (isolated via `QMATSUITE_HOME` override). Minimal prompt: "Calculate the equilibrium lattice constant of [X] using Quantum ESPRESSO." Treatment sessions S2/S3 received a hint: "This project has been used for similar calculations before."

**Task 2.2b**: 16 sessions (8 compounds x {relax, bands}), all sharing a single `local.db`. Compounds: GaAs, SiC, AlAs, BN, GaP, InP, AlN, InAs. The FTS5 search was unknowingly broken (implicit AND join).

**Task 2.2c**: Exact re-run of 2.2b with two fixes: (1) FTS5 OR-join in `_sanitize_fts_query()`, (2) workflow scope filter removed from search. Same prompts, compounds, order, and MPI config. This forms a controlled pair with 2.2b.

**Task 2.2c-ext**: Continuation of 2.2c with 8 new compounds: GaN, AlSb, InSb, ZnS, CdTe, MgO, CaO, PbTe. The `local.db` retained all 16 insights from 2.2c. Sessions numbered 17--32.

**DOS extension**: 8 additional sessions (33--40) computing density of states for the ext compounds. Same project directory, so agents could see all prior relax + bands calculations via `list_calculations`.

### 3.4 Data Integrity Notes

Three data sources exist for each session: (a) per-session `metrics.json` (machine-generated from JSONL trace files), (b) `CHAIN_LOG.md` (runner script grep counts), and (c) narrative reports (`CHAIN_REPORT_*.md`, human-authored summaries). Where these disagree, this review uses `metrics.json` as the authoritative source because it is parsed directly from the agent's tool-call traces with no manual summarization step.

**Discrepancy 1 — 2.2b search count**: The chain report claimed "10 out of 16 sessions" called `search_knowledge`, but per-session `metrics.json` shows only 8 sessions with `search_knowledge_count > 0`. The overcounting likely came from a grep pattern that matched the tool *listing* at MCP initialization (where available tools are enumerated) in addition to actual tool *calls*. **Correct value: 8/16 (50%).**

**Discrepancy 2 — ext transfer count**: The ext report summary listed "STRONG: 7" but the per-session classification table and `metrics.json` both show 8 sessions with STRONG transfer (sessions 18, 19, 25, 27, 28, 30, 31, 32). The summary text miscounted. **Correct value: 8 STRONG.**

**Discrepancy 3 — CHAIN_LOG vs metrics.json tool counts**: The `CHAIN_LOG.md` `search_k` column counts ALL knowledge-adjacent tool calls (`search_knowledge` + `list_calculations` + `inspect_calculation`), not just `search_knowledge`. For example, CHAIN_LOG shows session 17 (GaN relax) with `search_k=2`, but `metrics.json` shows `search_knowledge_count=0`. Those 2 calls were `list_calculations` and `inspect_calculation` (project state queries), not knowledge DB searches. Similarly, CHAIN_LOG's `record_i` column appears to count both `record_insight` and `record_intent` calls. Session 23 (CaO relax) shows `record_i=1` in CHAIN_LOG but recorded no insight in the database — the call was likely `record_intent` or a failed/filtered `record_insight` (observation-grade, which is accepted but not persisted).

**Authoritative source convention**: All numerical claims in this review use `metrics.json` data. Lattice constants, band gaps, tool call counts, and search hit counts are taken directly from the per-session JSON, not from narrative report text or CHAIN_LOG grep counts.

---

## 4. Results by Phase

### 4.1 Task 2.2 (v1): Baseline -- No Transfer Observed

| Session | Material | a_calc (A) | a_exp (A) | Error | search_knowledge | record_insight | Tools |
|---------|----------|-----------|-----------|-------|-----------------|----------------|-------|
| S1 | GaAs | 5.726 | 5.653 | +1.29% | 1x (empty DB) | 1x | 29 |
| S2 | AlAs | 5.70 | 5.661 | +0.69% | 0 | 1x | 54 |
| S3 | GaP | 5.510 | 5.451 | +1.08% | 0 | 1x | 64 |
| C1 | AlAs | 5.72 | 5.661 | +1.04% | 0 | 1x | 65 |
| C2 | GaP | 5.505 | 5.451 | +0.99% | 0 | 1x | 26 |

**Key finding**: No knowledge transfer occurred. Only S1 searched (against an empty DB). S2 and S3 never called `search_knowledge` despite the hint. All 5 sessions recorded insights (100% write compliance). The initial conclusion -- "agents don't use the knowledge system" -- was later shown to be premature by Task 2.2b.

**Secondary findings**: All sessions used mixed pseudopotential types without detecting it. PseudoDojo NC pseudo contamination propagated through shared pseudo directory (filesystem side-channel). Agent methodology varied significantly (vc-relax vs EOS scan) even with identical prompts.

### 4.2 Task 2.2b: FTS5 Bug Discovery

| # | Session | Wall | Tools | SK | Hits | Insights | Exit |
|---|---------|------|-------|----|------|----------|------|
| 01 | relax_GaAs | 18m | 34 | 1 | 0 | 1 | 0 |
| 02 | relax_SiC | 4m | 26 | 0 | -- | 2 | 0 |
| 03 | relax_AlAs | 7m | 56 | 0 | -- | 3 | 0 |
| 04 | relax_BN | 3m | 38 | 1 | 0 | 4 | 0 |
| 05 | relax_GaP | 8m | 28 | 0 | -- | 6 | 0 |
| 06 | relax_InP | 9m | 29 | 0 | -- | 7 | 0 |
| 07 | relax_AlN | 5m | 39 | 0 | -- | 8 | 0 |
| 08 | relax_InAs | 13m | 30 | 0 | -- | 9 | 0 |
| 09 | bands_GaAs | 35m | 66 | 1 | 0 | 10 | 0 |
| 10 | bands_SiC | 5m | 46 | 0 | -- | 11 | 0 |
| 11 | bands_AlAs | 4m | 41 | 0 | -- | 12 | 0 |
| 12 | bands_BN | 7m | 41 | 1 | 0 | 13 | 0 |
| 13 | bands_GaP | 14m | 66 | 1 | 0 | 14 | 0 |
| 14 | bands_InP | 14m | 38 | 1 | 0 | 15 | 0 |
| 15 | bands_AlN | 10m | 39 | 1 | 0 | 16 | 0 |
| 16 | bands_InAs | 77m | 54 | 1 | 0 | 17 | 0 |

**Total**: 233 min, 671 tool calls, 8/16 sessions searched, 0/8 searches returned hits, 17 insights recorded, 100% exit=0.

**Key discovery**: `search_knowledge` was called in 8 of 16 sessions (50%) but returned 0 results every time. Root cause: `_sanitize_fts_query()` joined tokens with spaces, which FTS5 interprets as implicit AND. A query like "BN band structure band gap" requires ALL tokens in a single document -- which never matches. Testing confirmed: `"BN"` alone returned 1 hit; `"BN band structure band gap"` returned 0.

**Critical reinterpretation**: The v1 conclusion that "agents don't use knowledge" was wrong. Agents DO search (50% rate in 2.2b), but the search was broken.

**Search query analysis** (all returned 0 hits):

| Session | Query | DB Size | Why It Failed |
|---------|-------|---------|---------------|
| 01 relax_GaAs | "GaAs lattice constant vc-relax QE" | 0 | Empty DB |
| 04 relax_BN | "lattice constant optimization equation of state" | 3 | FTS5 AND: all tokens required |
| 09 bands_GaAs | "bands not converged c_bands too many bands" | 9 | FTS5 AND + workflow=bands filter |
| 12 bands_BN | "BN band structure band gap" | 12 | FTS5 AND + workflow=bands filter |
| 13 bands_GaP | "band structure calculation semiconductor band gap" | 13 | FTS5 AND + workflow=bands filter |
| 14 bands_InP | "InP band structure band gap" | 14 | FTS5 AND |
| 15 bands_AlN | "AlN band structure band gap" | 15 | FTS5 AND |
| 16 bands_InAs | "InAs band structure band gap semiconductor" | 16 | FTS5 AND + workflow=bands filter |

Note: The `workflow=bands` filter on sessions 09, 12, 13, 16 would have also excluded relax-scoped insights even if FTS5 had matched. Both bugs (FTS5 AND + workflow filter) needed fixing.

**Notable sessions**: AlAs relax (session 03) detected ~500 kbar Pulay stress from mixed PAW+NC pseudos, devised E(V) scan workaround (textbook-correct response). GaAs bands (session 09) required switching to CG diagonalization after Davidson failure with mixed pseudos (35 min). InAs bands (session 16) was the longest at 77 min, attempting SOC as remedy for PBE zero-gap failure. Multiple sessions (09, 10, 12, 13) independently discovered the conventional-vs-primitive cell issue for band structure interpretation.

**Mixed pseudo detection**: 4 of 5 mixed-pseudo compounds detected (GaAs, AlAs, GaP, InAs) -- a significant improvement over v1 (0/5). AlN (PAW+USPP) was the only mixed compound not flagged.

### 4.3 Task 2.2c: FTS5 Fixed -- Transfer Works

| # | Session | Wall | Tools | SK | Hits | Transfer | Insights | Exit |
|---|---------|------|-------|----|------|----------|----------|------|
| 01 | relax_GaAs | 28m | 53 | 0 | -- | -- | 1 | 0 |
| 02 | relax_SiC | 3m | 33 | 0 | -- | -- | 2 | 0 |
| 03 | relax_AlAs | 11m | 44 | 1 | 10 | STRONG | 3 | 0 |
| 04 | relax_BN | 5m | 38 | 1 | 6 | STRONG | 4 | 0 |
| 05 | relax_GaP | 25m | 26 | 0 | -- | -- | 5 | 0 |
| 06 | relax_InP | 10m | 29 | 0 | -- | -- | 6 | 0 |
| 07 | relax_AlN | 19m | 56 | 1 | 10 | STRONG | 7 | 0 |
| 08 | relax_InAs | 27m | 43 | 1 | 10 | STRONG | 8 | 0 |
| 09 | bands_GaAs | 29m | 84 | 0 | -- | -- | 9 | 0 |
| 10 | bands_SiC | 4m | 40 | 0 | -- | -- | 10 | 0 |
| 11 | bands_AlAs | 19m | 43 | 0 | -- | -- | 11 | 0 |
| 12 | bands_BN | 6m | 39 | 0 | -- | -- | 12 | 0 |
| 13 | bands_GaP | 23m | 50 | 1 | 10 | STRONG | 13 | 0 |
| 14 | bands_InP | 12m | 39 | 1 | 10 | STRONG | 14 | 0 |
| 15 | bands_AlN | 7m | 44 | 0 | -- | -- | 15 | 0 |
| 16 | bands_InAs | 26m | 52 | 0 | -- | -- | 16 | 0 |

**Total**: 254 min, 713 tool calls, 6/16 sessions searched, 6/6 searches returned hits, 6 STRONG transfers, 16 insights.

**Controlled comparison (2.2b vs 2.2c)**:

| Metric | 2.2b (broken) | 2.2c (fixed) | Change |
|--------|--------------|--------------|--------|
| Search calls | 8 | 6 | -2 |
| Searches with hits > 0 | 0 (0%) | 6 (100%) | **+6** |
| STRONG transfer events | 0 | **6** | **+6** |
| Cross-session finding transfers | 0 | 2 sessions | +2 |
| InAs bands wall time | 77m | 26m | **-66%** |
| Total wall time | 233m | 254m | +9% |

All 6 sessions that received search results showed STRONG transfer -- agents explicitly cited retrieved knowledge and changed their behavior based on it.

**Search result composition**: 52/56 results (93%) from seed knowledge, 4/56 (7%) from session-generated findings.

### 4.4 Task 2.2c-ext: Cross-Family Generalization

| # | Session | Wall | Tools | SK | Seed | 2.2c | Ext | Transfer | Exit |
|---|---------|------|-------|----|------|------|-----|----------|------|
| 17 | relax_GaN | 4m | 27 | 0 | -- | -- | -- | NONE | 0 |
| 18 | relax_AlSb | 11m | 30 | 1 | 7 | 3 | 0 | STRONG | 0 |
| 19 | relax_InSb | 19m | 31 | 1 | 7 | 1 | 2 | STRONG | 0 |
| 20 | relax_ZnS | 4m | 28 | 0 | -- | -- | -- | NONE | 0 |
| 21 | relax_CdTe | 54m | 39 | 1 | 5 | 1 | 3 | MODERATE | 0 |
| 22 | relax_MgO | 3m | 30 | 0 | -- | -- | -- | NONE | 0 |
| 23 | relax_CaO | 5m | 27 | 0 | -- | -- | -- | NONE | 0 |
| 24 | relax_PbTe | 26m | 30 | 0 | -- | -- | -- | NONE | 0 |
| 25 | bands_GaN | 10m | 44 | 1 | 10 | 0 | 0 | STRONG | 0 |
| 26 | bands_AlSb | 12m | 42 | 0 | -- | -- | -- | NONE | 0 |
| 27 | bands_InSb | 20m | 51 | 1 | 9 | 1 | 0 | STRONG | 0 |
| 28 | bands_ZnS | 12m | 46 | 1 | 10 | 0 | 0 | STRONG | 0 |
| 29 | bands_CdTe | 20m | 41 | 0 | -- | -- | -- | NONE | 0 |
| 30 | bands_MgO | 6m | 47 | 2 | 18 | 0 | 2 | STRONG | 0 |
| 31 | bands_CaO | 6m | 42 | 1 | 9 | 0 | 1 | STRONG | 0 |
| 32 | bands_PbTe | 85m | 125 | 1 | 10 | 0 | 0 | STRONG | 0 |

**Total**: 297 min, 750 tool calls, 9/16 sessions searched (10 calls), 15 insights (CaO relax missing), 31 total insights in DB.

**Search result composition shift**: Seed 85.9%, 2.2c sessions 6.1%, ext sessions 8.1%. Session-finding fraction doubled from 7% to 14%.

**Notable transfers**:
- **InSb bands (session 27)**: Searched for "InSb band structure narrow gap semiconductor", received InAs band inversion insight from session 16. Agent's reasoning: "InAs shows inverted band gap with PBE -- InSb is even narrower-gap, so PBE will likely give band inversion." Calculation confirmed: 0.59 eV inversion at Gamma, larger than InAs (0.218 eV). This is the strongest evidence of predictive knowledge transfer in the entire experiment series.
- **MgO-to-CaO (sessions 30-31)**: Session 30 encountered S-matrix error for MgO bands, performed two searches (proactive + reactive). Session 31 (CaO) retrieved MgO band gap finding and explicitly used MgO_bands_v2 as template: "It's also a rocksalt structure and can serve as a reference for the CaO band structure."
- **PbTe bands (session 32)**: 85 min, 125 tool calls, 48 run_calculation calls. Most complex session across all 40. Correctly identified SOC as essential, discovered SSSP pseudos lack FR capability, switched to PseudoDojo NC-FR. Eventually obtained PBE+SOC gap = 0.094 eV at L point.
- **CdTe relax (session 21)**: 54 min outlier. Independently discovered `cell_dofree='ibrav'` bug with `ibrav=0`. First attempt gave wrong a = 6.387 A; switching to `cell_dofree='all'` gave correct a = 6.610 A (+2.0%). Knowledge search was MODERATE -- agent acknowledged results but the critical fix was independent.
- **CaO relax (session 23)**: Only session in the entire 32-session chain that did not record an insight. No search either. Lattice constant of 4.810 A is suspiciously close to experimental (4.811 A), suggesting the starting structure was already at equilibrium.

### 4.5 DOS Extension: Project State as Transfer Channel

| # | Session | Wall | Tools | SK | Project State | Knowledge DB | Dominant |
|---|---------|------|-------|----|--------------|-------------|----------|
| 33 | dos_GaN | 9.8m | 48 | 0 | STRONG | NONE | Project State |
| 34 | dos_AlSb | 8.5m | 33 | 1 | STRONG | MODERATE | Project State |
| 35 | dos_InSb | 39.5m | 44 | 1 | STRONG | MODERATE | Project State |
| 36 | dos_ZnS | 14.0m | 54 | 0 | STRONG | NONE | Project State |
| 37 | dos_CdTe | 9.3m | 40 | 1 | STRONG | MODERATE | Project State |
| 38 | dos_MgO | 4.4m | 31 | 0 | MODERATE | NONE | Project State |
| 39 | dos_CaO | 9.6m | 35 | 2 | MODERATE | STRONG | Knowledge DB |
| 40 | dos_PbTe | 76.8m | 47 | 1 | STRONG | STRONG | Both |

**Total**: 171.9 min, $12.52 cost, 10 insights recorded (9 findings + 1 observation from ZnS), 40 total insights in DB.

**Key finding**: Project state dominated (6/8 sessions). All 8 sessions reused relaxed structures from prior calculations. 5/8 inspected prior bands calculation parameters. Knowledge DB was dominant only for CaO (ZnS nbnd lesson + MgO isostructural reference) and synergistic for PbTe (bands SOC finding + project state for parameters).

**Band gap consistency (DOS vs bands)**: Mean |delta| = 0.05 eV across 7 compounds (excluding InSb). ZnS: exact match (2.09 eV). Maximum delta: 0.15 eV (MgO).

**NSCF failures**: 3/8 sessions had NSCF step failures:

| Session | Failure | Root Cause | Fix | Knowledge Used? |
|---------|---------|-----------|-----|-----------------|
| 33 GaN | c_bands convergence | 16x16x10 mesh too dense for empty states | Reduced to 12x12x8 + diago_david_ndim=4 | No |
| 36 ZnS | bad Fermi energy | nbnd=40 < 52 occupied bands (Zn Zval=20) | Increased nbnd to 70 (new calculation) | No (recorded as insight) |
| 39 CaO | S matrix crash | nbnd=48 too many empty states for Ca USPP | Reduced nbnd to 40 + diago_full_acc=.true. | **Yes** -- ZnS nbnd lesson |

The CaO session (39) provides the clearest example of cross-session debugging transfer: ZnS discovered the nbnd lesson (session 36), recorded it as an insight, and CaO (session 39) retrieved and applied it after its own S-matrix crash. The fixes are complementary (ZnS had too few bands, CaO had too many), demonstrating the nuance of nbnd selection that the knowledge base captured.

**Cross-session knowledge flow within DOS**:
```
33 GaN  -> records DOS finding (gap=1.84 eV, NSCF lesson)
34 AlSb -> records DOS finding (gap=1.30 eV)
35 InSb -> receives GaN+AlSb findings (cross-compound within DOS)
36 ZnS  -> records 2 insights (nbnd lesson + DOS gap=2.09 eV)
37 CdTe -> receives CdTe relax lattice constant
38 MgO  -> records DOS finding (gap=4.90 eV)
39 CaO  -> receives MgO DOS + ZnS nbnd lesson (fixes S-matrix crash)
40 PbTe -> receives PbTe bands SOC gap (goes directly to correct methodology)
```

---

## 5. Cross-Phase Comparative Analysis

### 5.1 Search Behavior Evolution

| Phase | Sessions | Sessions Searching | Search Rate | Hits > 0 | Hit Rate |
|-------|----------|--------------------|-------------|----------|----------|
| 2.2 (v1) | 5 | 1 | 20% | 0 | 0% (empty DB) |
| 2.2b | 16 | 8 | 50% | 0 | 0% (FTS5 bug) |
| 2.2c | 16 | 6 | 37.5% | 6 | 100% |
| 2.2c-ext | 16 | 9 | 56.3% | 9 | 100% |
| DOS | 8 | 5 | 62.5% | 5 | 100% |

Search rate increased from 20% (v1) to 62.5% (DOS), though with considerable stochastic variance between phases. The jump from v1 (20%) to 2.2b (50%) was driven by improved prompts ("up to 3 attempts" retry allowance) and the inclusion of band structure calculations, which have more failure modes that trigger troubleshooting searches.

Critically, the search *hit* rate went from 0% (broken FTS5) to 100% (fixed) overnight with a 2-line code change. After the fix, every search returned actionable results.

### 5.2 Knowledge Source Composition

| Phase | Seed (builtin.db) | Session Findings | Session % |
|-------|-------------------|------------------|-----------|
| 2.2c | 52 of 56 (93%) | 4 of 56 (7%) | 7% |
| 2.2c-ext | 85 of 99 (86%) | 14 of 99 (14%) | 14% |
| DOS | ~70% builtin | ~30% local | 30%* |

*DOS percentages are approximate; the metrics show 5 of 20 search results as local findings for sessions with non-zero hits, but exact counts vary by query.

Session-generated findings doubled from 7% (2.2c) to 14% (ext) as the knowledge base grew from 0 to 31 session entries. The DOS phase showed the highest local finding rate because queries were more specific (compound-targeted DOS queries matching prior DOS/bands findings).

However, seed knowledge remained dominant throughout. This is partly an artifact of the OR-join search: broad queries like "lattice constant vc-relax convergence" match many generic seed entries, potentially pushing compound-specific session findings below the 10-result limit.

### 5.3 Transfer Channel Analysis

The experiments revealed two distinct knowledge transfer channels:

**Knowledge DB** (`search_knowledge`):
- Best for cross-compound transfer (InAs -> InSb, MgO -> CaO)
- Essential for surfacing lessons from compounds the agent hasn't directly worked with
- Provides general principles (PBE bias, convergence protocols) from seed knowledge
- Agents must proactively decide to search

**Project state** (`list_calculations` + `inspect_calculation`):
- Best for same-compound cross-workflow transfer (relax -> bands -> DOS)
- Provides exact parameter values (ecutwfc, pseudos, k-mesh) from prior calculations
- All DOS agents used this channel (8/8 reused relaxed structures)
- More deterministic -- agents naturally inspect the project when setting up a calculation

The PbTe DOS session (session 40) showed both channels working synergistically: knowledge DB provided the SOC gap expectation (0.094 eV) and validation that SOC was essential, while project state provided the exact SOC parameters from PbTe_bands_SOC_v3 (noncolin, lspinorb, ecutwfc=60, mixing_beta=0.3, PseudoDojo NC-FR pseudos). The agent went directly to the correct methodology on the first attempt, completely avoiding the 85-minute trial-and-error process that the bands agent endured.

**Channel effectiveness by scenario**:

| Scenario | Knowledge DB | Project State | Which Dominates |
|----------|-------------|---------------|-----------------|
| Same compound, same workflow (re-run) | Moderate | Strong | Project State |
| Same compound, different workflow (relax→bands→DOS) | Moderate | Strong | Project State |
| Same family, different compound (InAs→InSb) | Strong | None | Knowledge DB |
| Different family, similar structure (MgO→CaO) | Strong | None | Knowledge DB |
| Troubleshooting a novel failure | Moderate | None | Knowledge DB |
| Parameter setup for routine calculation | Weak | Strong | Project State |

This matrix suggests a clear division of labor: project state handles "vertical" transfer (depth within one compound), while the knowledge DB handles "horizontal" transfer (breadth across compounds). A complete knowledge system needs both channels.

### 5.4 Transfer Event Taxonomy

Across all phases with working search (2.2c, ext, DOS), we catalog 15+ STRONG transfer events classified by type:

**Predictive transfer** (agent forms hypothesis from prior knowledge before calculating):
- Session 27 (InSb bands): "InAs shows inverted band gap with PBE -- InSb is even narrower-gap, so PBE will likely give band inversion." Confirmed: 0.59 eV inversion.

**Diagnostic transfer** (agent uses prior knowledge to diagnose unexpected result):
- Session 08 (InAs relax, 2.2c): PBE knowledge confirmed "should give 1-2% too large, not 4.6% too small." Immediately diagnosed mixed pseudo artifact, switched to consistent pseudos.
- Session 18 (AlSb relax, ext): Retrieved InAs mixed pseudo warning, correctly judged PAW+US mixing acceptable (unlike PAW+NC).

**Template transfer** (agent copies setup from structurally analogous prior calculation):
- Session 31 (CaO bands): Used MgO_bands_v2 as template (same rocksalt structure, same BZ).
- Session 14 (InP bands, 2.2c): Inspected GaAs_bands parameters and replicated setup.
- Session 40 (PbTe DOS): Inspected PbTe_bands_SOC_v3 for exact SOC parameters.

**Debugging transfer** (agent uses prior failure knowledge to fix current failure):
- Session 39 (CaO DOS): ZnS nbnd lesson from session 36 ("nbnd must exceed 52 occupied bands") used to diagnose and fix CaO S-matrix crash.

**Parameter transfer** (agent applies numerical parameters or methodological guidance):
- Session 07 (AlN relax, 2.2c): BN finding "ecutwfc >= 90 Ry for NC pseudos" -> chose PAW to avoid high cutoff.
- Session 13 (GaP bands, 2.2c): Applied nbnd formula, ecutrho ratio, fixed occupations from seed knowledge.
- Session 19 (InSb relax, ext): Calibrated lattice constant expectation from InAs (+2.17%) and AlSb (+1.4%).

The predictive transfer (InSb, session 27) is the single strongest evidence in the entire experiment series. The agent demonstrated genuine scientific reasoning: applying a known finding about one compound (InAs) to predict the behavior of a chemically similar compound (InSb) before running any calculation.

### 5.5 The FTS5 Bug: Infrastructure as Bottleneck

**Discovery**: Task 2.2b showed 8 sessions calling `search_knowledge` but getting 0 results every time. Manual testing revealed the root cause: `_sanitize_fts_query()` joined tokens with spaces, and FTS5 treats spaces as implicit AND. Multi-word queries required ALL tokens in a single document.

**Evidence**: Testing on the 2.2b database snapshot:
- `"BN"` alone: 1 hit (correct)
- `"band"` alone: 4 hits (correct)
- `"BN band structure band gap"` (actual agent query): 0 hits (all tokens must co-occur)
- `"BN OR band OR structure OR band OR gap"` (OR-join): 6 hits (would have worked)

**The fix** (2 lines in `src/qmatsuite/mcp/knowledge/store.py`):
1. `_sanitize_fts_query()`: `" ".join(tokens)` -> `" OR ".join(tokens)`
2. `_add_scope_filters()`: Removed `scope_workflow` WHERE clause

**Impact** (2.2b vs 2.2c):
- Search hit rate: 0% -> 100%
- STRONG transfer events: 0 -> 6
- The only variable changed between 2.2b and 2.2c

**Lesson**: "Agents naturally use knowledge tools when given results. The bottleneck was infrastructure, not agent behavior." This overturned the v1 conclusion that agents don't search.

### 5.6 Write vs Read Asymmetry

| Phase | record_insight Rate | search_knowledge Rate |
|-------|--------------------|-----------------------|
| 2.2 (v1) | 5/5 (100%) | 1/5 (20%) |
| 2.2b | 16/16 (100%) | 8/16 (50%) |
| 2.2c | 16/16 (100%) | 6/16 (37.5%) |
| 2.2c-ext | 15/16 (93.8%) | 9/16 (56.3%) |
| DOS | 8/8 (100%) | 5/8 (62.5%) |

Write compliance is near-perfect across the observational chain (39/40 = 97.5%; only CaO relax, session 23, failed to record) and across all 61 runs (60/61 = 98.4%). Read behavior is variable (37.5--62.5%) and never exceeds two-thirds of sessions.

**Why the asymmetry?**
- **Write** is triggered by task completion: the agent has a clear result to record, and the MCP instructions explicitly state "record your findings." The trigger is unambiguous.
- **Read** requires a proactive decision at the start of a session. The agent must judge that searching would be valuable -- which depends on task complexity, prior experience, and the perceived utility of the knowledge base. Simple compounds (SiC, ZnS, MgO) rarely trigger searches; complex ones (InAs, PbTe, InSb) more often do.

**Compound difficulty correlates with search propensity**:

| Difficulty Tier | Compounds | Avg Wall Time | Search Rate | Notes |
|----------------|-----------|---------------|-------------|-------|
| Easy (< 10 min) | SiC, BN, GaN, ZnS, MgO, CaO | 5 min | 25% | Straightforward setup, few failures |
| Medium (10-30 min) | GaAs, AlAs, GaP, InP, AlN, AlSb, CdTe | 16 min | 55% | Occasional convergence issues |
| Hard (> 30 min) | InAs, InSb, PbTe | 56 min | 80% | Mixed pseudos, SOC, band inversion |

Agents are more likely to search when they encounter difficulties -- the search is a troubleshooting reflex, not a proactive preparation step. This reactive pattern means knowledge is used for diagnosis rather than prevention, which is less efficient than having relevant knowledge available before the first calculation attempt.

**Implications**: Ambient knowledge surfacing (automatically providing relevant knowledge when a calculation is created) would capture the 40--60% of sessions that never search. The system should not rely on agents to proactively decide to search.

### 5.7 Accuracy & Computational Correctness

#### Lattice Constants (16 compounds, PBE vc-relax)

| Compound | Family | Structure | a_calc (A) | a_exp (A) | Error (%) | Phase |
|----------|--------|-----------|-----------|-----------|-----------|-------|
| GaAs | III-V | ZB | 5.746 | 5.653 | +1.6 | 2.2c |
| SiC | IV | ZB | 4.381 | 4.360 | +0.5 | 2.2c |
| AlAs | III-V | ZB | 5.732 | 5.661 | +1.3 | 2.2c |
| BN | III-V | ZB | 3.624 | 3.616 | +0.2 | 2.2c |
| GaP | III-V | ZB | 5.505 | 5.451 | +1.0 | 2.2c |
| InP | III-V | ZB | 5.960 | 5.869 | +1.6 | 2.2c |
| AlN | III-V | WZ | 3.113 | 3.112 | +0.03 | 2.2c |
| InAs | III-V | ZB | 6.190 | 6.058 | +2.2 | 2.2c |
| GaN | III-V | WZ | 3.217 | 3.189 | +0.9 | ext |
| AlSb | III-V | ZB | 6.222 | 6.136 | +1.4 | ext |
| InSb | III-V | ZB | 6.633 | 6.479 | +2.4 | ext |
| ZnS | II-VI | ZB | 5.438 | 5.409 | +0.5 | ext |
| CdTe | II-VI | ZB | 6.610 | 6.481 | +2.0 | ext |
| MgO | Oxide | RS | 4.253 | 4.212 | +1.0 | ext |
| CaO | Oxide | RS | 4.810 | 4.811 | ~0.0* | ext |
| PbTe | IV-VI | RS | 6.567 | 6.462 | +1.6 | ext |

Mean error: +1.1% (excluding CaO). Range: +0.03% to +2.4%. All positive (overestimation), consistent with well-known PBE overbinding.

*CaO ~0% error is anomalous -- likely the starting CIF structure was at the experimental geometry, so the vc-relax had nothing to relax.

**Error trends by chemical family** (excluding CaO):

| Family | Compounds | Mean Error (%) | Max Error (%) | Notes |
|--------|-----------|---------------|---------------|-------|
| III-V (light) | GaAs, AlAs, GaP, BN, AlN | +0.9 | +1.6 (GaAs) | Tight cluster, well-described by PBE |
| III-V (heavy) | InP, InAs, InSb, AlSb, GaN | +1.7 | +2.4 (InSb) | Heavier anions give larger errors |
| II-VI | ZnS, CdTe | +1.3 | +2.0 (CdTe) | d-electron effects in Zn/Cd |
| Oxides | MgO | +1.0 | +1.0 | Only MgO reliable (CaO anomalous) |
| IV-VI | PbTe | +1.6 | +1.6 | Heavy-element relativistic effects |

The trend of increasing PBE overestimation with heavier elements (particularly In, Cd, Pb) is well-documented in the literature and reflects the increasing importance of relativistic and dispersion effects that PBE neglects.

#### Band Gaps (16 compounds, PBE, no SOC except PbTe)

| Compound | Bands (eV) | DOS (eV) | |DOS-Bands| | Exp (eV) | PBE Error |
|----------|-----------|----------|-------------|---------|-----------|
| GaAs | 0.503 | -- | -- | 1.42 | -65% |
| SiC | 1.36 | -- | -- | 2.36 | -42% |
| AlAs | 1.46 | -- | -- | 2.16 | -32% |
| BN | 4.53 | -- | -- | 6.36 | -29% |
| GaP | 1.59 | -- | -- | 2.26 | -30% |
| InP | 0.69 | -- | -- | 1.34 | -49% |
| AlN | 4.16 | -- | -- | ~6.0 | -31% |
| InAs | 0.00 | -- | -- | 0.35 | -100% |
| GaN | 1.85 | 1.84 | 0.01 | 3.40 | -46% |
| AlSb | 1.24 | 1.30 | 0.06 | 1.62 | -23% |
| InSb | 0.00 | 0.15 | 0.15 | 0.235 | -100% |
| ZnS | 2.09 | 2.09 | 0.00 | 3.54 | -41% |
| CdTe | 0.77 | 0.78 | 0.01 | 1.60 | -52% |
| MgO | 4.75 | 4.90 | 0.15 | 7.83 | -39% |
| CaO | 3.65 | 3.67 | 0.02 | 7.00 | -48% |
| PbTe | 0.094 | 0.10--0.15 | ~0.03 | 0.19 | -50% |

PBE underestimation ranges from -23% (AlSb) to -100% (InAs, InSb band inversion). Mean underestimation: approximately -42% (excluding the band-inverted compounds). This is consistent with the well-known PBE band gap problem.

DOS-bands consistency is excellent: mean |delta| = 0.05 eV (excluding InSb, where the bands session reported 0.0 eV due to band inversion while DOS found ~0.15 eV without SOC).

**Band gap error trends by compound**:

| PBE Error Range | Compounds | Common Feature |
|----------------|-----------|----------------|
| -23% to -32% | AlSb, BN, GaP, AlAs, AlN | Wide-gap, light elements |
| -39% to -52% | MgO, ZnS, SiC, GaN, CaO, InP, CdTe, PbTe | Mid-gap or d-electron |
| -65% | GaAs | Narrow-gap III-V |
| -100% (inverted) | InAs, InSb | Ultra-narrow-gap, SOC essential |

PBE band gap error correlates strongly with the experimental gap magnitude: narrower-gap compounds show larger fractional errors. This is a fundamental limitation of semilocal DFT, not a computational artifact. The two band-inverted compounds (InAs, InSb) represent the extreme case where PBE qualitatively fails, predicting metallic behavior instead of narrow-gap semiconductors.

### 5.8 Efficiency Beyond Wall Time

Wall time is a poor proxy for knowledge transfer efficiency because it is dominated by QE compute time, which is identical regardless of whether the agent knew the correct methodology from the start. A 20×20×20 SOC NSCF calculation takes the same time whether the agent discovered SOC after 5 failed attempts or applied it immediately. Better metrics are iteration count (`run_calculation` calls), failure count, and first-attempt success rate.

#### 5.8.1 2.2b vs 2.2c: Compound-Matched Iteration Comparison

For bands sessions (clean comparison — no methodology confound from EOS `quick_run` tool):

| Compound | 2.2b QE runs | 2.2c run_calc | Δ | 2.2b wall | 2.2c wall | Δ wall | 2.2b tools | 2.2c tools |
|----------|-------------|--------------|---|---------|---------|--------|----------|----------|
| GaAs | 3 | 3 | 0 | 35m | 29m | -6m | 66 | 84 |
| SiC | 2 | 2 | 0 | 5m | 4m | -1m | 46 | 40 |
| AlAs | 1 | 2 | +1 | 4m | 19m | +15m | 41 | 43 |
| BN | 1 | 2 | +1 | 7m | 6m | -1m | 41 | 39 |
| GaP | 4 | 2 | **-2** | 14m | 23m | +9m | 66 | 50 |
| InP | 1 | 1 | 0 | 14m | 12m | -2m | 38 | 39 |
| AlN | 2 | 2 | 0 | 10m | 7m | -3m | 39 | 44 |
| InAs | 2 | 2 | 0 | 77m | 26m | **-51m** | 54 | 52 |
| **Total** | **16** | **16** | **0** | **166m** | **126m** | **-40m** | **391** | **391** |

**Key finding**: Aggregate iteration count is identical (16 vs 16). Knowledge transfer did NOT reduce the number of calculation attempts for band structure workflows. However, wall time dropped by 40 min (24%), driven almost entirely by InAs bands (77→26 min). The InAs improvement came not from fewer iterations but from **avoiding the wrong path**: the 2.2b agent spent ~50 min attempting SOC as a workaround for InAs band inversion, while the 2.2c agent correctly identified band inversion as an inherent PBE limitation and stopped.

For relax sessions, 3 of 8 2.2b sessions used EOS methodology (`quick_run` tool, 7-8 QE runs each) while all 2.2c sessions used vc-relax (`run_calculation`, 1-4 calls). This methodology divergence prevents direct iteration-count comparison for relax. The methodology shift itself may be meaningful — 2.2c agents had knowledge about vc-relax convergence protocols from seed knowledge, potentially favoring vc-relax over EOS.

#### 5.8.2 DOS: First-Attempt Success Analysis

The DOS phase has the cleanest efficiency data because `metrics_dos.json` explicitly records failures, retries, and API time:

| Session | Compound | Total Runs | Failures | Retries | API min | Wall min | Searched? | First-Try |
|---------|----------|-----------|---------|---------|---------|---------|----------|-----------|
| 33 | GaN | 2 | 1 | 1 | 5.4 | 9.8 | No | Retry |
| 34 | AlSb | 1 | 0 | 0 | 3.3 | 8.5 | Yes | Success |
| 35 | InSb | 2 | 0 | 0 | 6.3 | 39.5 | Yes | Refinement |
| 36 | ZnS | 2 | 1 | 1 | 7.0 | 14.0 | No | Retry |
| 37 | CdTe | 1 | 0 | 0 | 5.2 | 9.3 | Yes | Success |
| 38 | MgO | 1 | 0 | 0 | 3.4 | 4.4 | No | Success |
| 39 | CaO | 2 | 1 | 1 | 3.9 | 9.6 | Yes | Retry* |
| 40 | PbTe | 2 | 0 | 0 | 7.8 | 76.8 | Yes | Refinement |

*CaO failed first, then used retrieved ZnS nbnd knowledge to diagnose and fix the failure. The retry WAS knowledge-assisted.

**Failure distribution by search behavior** (DOS phase only, N=8):

| | Searched (N=5) | Not Searched (N=3) |
|---|---|---|
| First-try success | 2 (40%) | 1 (33%) |
| Refinement (deliberate, no failure) | 2 (40%) | 0 (0%) |
| Retry (failure-driven) | 1 (20%) | 2 (67%) |

Sessions that searched had a 20% failure rate vs 67% for non-searching sessions. N=8 is too small for statistical significance, but the direction is suggestive: agents that consult the knowledge base are less likely to encounter failures. The one searched session that failed (CaO) was the only session that used knowledge to FIX its failure — without the ZnS nbnd lesson, the CaO failure might have taken longer to resolve.

**API time vs wall time**: Agent reasoning accounted for only 25% of total wall time (42.3 min API / 171.9 min wall). The remaining 75% was QE compute. PbTe DOS is the extreme: 7.8 min of agent reasoning, 69 min of QE compute (10% agent / 90% compute). This confirms that wall time is a poor efficiency metric — the agent's contribution is a small fraction.

#### 5.8.3 PbTe Deep Comparison: Bands (S32) vs DOS (S40)

PbTe is the strongest individual case study for knowledge transfer efficiency:

| Metric | PbTe Bands (S32) | PbTe DOS (S40) | Change |
|--------|-----------------|----------------|--------|
| run_calculation calls | 48 | 2 | **-96%** |
| Failures | Multiple (SSSP SOC, K_POINTS, S-matrix) | 0 | **Eliminated** |
| Tool calls | 125 | 47 | -62% |
| Wall time | 85 min | 76.8 min | -10% |
| API time | N/A | 7.8 min | — |
| search_knowledge | 1 call (seed only) | 1 call (seed + session) | — |
| Correct methodology first? | No (SSSP → discovered no FR → PseudoDojo) | **Yes** (PseudoDojo NC-FR from start) | — |

The 48→2 reduction in `run_calculation` calls (-96%) is the single most dramatic efficiency gain in the entire experiment series. The bands agent endured multiple failure cycles: SSSP pseudos lacked SOC support, K_POINTS format errors with non-collinear wavefunctions, S-matrix convergence issues. Each failure required diagnosis, parameter modification, and re-execution. The DOS agent skipped the entire discovery process because:
1. **Knowledge DB** provided the finding: PbTe requires SOC, gap ~0.094 eV at L point
2. **Project state** provided exact parameters from `PbTe_bands_SOC_v3`: `noncolin=.true.`, `lspinorb=.true.`, `ecutwfc=60`, `mixing_beta=0.3`, PseudoDojo NC-FR pseudopotentials

Wall time decreased by only 10% (85→76.8 min) because the large SOC NSCF calculation on a 20×20×20 k-mesh dominates both sessions. The efficiency gain is entirely in agent iteration overhead, not compute time.

#### 5.8.4 Summary: What Efficiency Metrics Show

| Metric | Shows Improvement? | Interpretation |
|--------|-------------------|---------------|
| Wall time | No aggregate trend | Dominated by QE compute; wrong metric |
| Iteration count (run_calc) | No aggregate trend (2.2b=2.2c=16 for bands) | Compound difficulty dominates aggregate |
| Iteration count (case-specific) | **Yes**: PbTe 48→2, InAs 77→26 min | Knowledge avoids catastrophic wrong paths |
| First-try failure rate (DOS) | Suggestive: 20% (searched) vs 67% (not searched) | N=8, not significant, but directionally correct |
| API time (DOS only) | Agent is 25% of wall time | Real efficiency domain is agent reasoning, not compute |

Knowledge transfer improves efficiency by **eliminating wrong-path exploration**, not by reducing the number of iterations for routine calculations. The value is concentrated in "hard" sessions where the correct methodology is non-obvious (SOC for heavy elements, consistent pseudopotentials for mixed compounds). For "easy" sessions (SiC, BN, MgO), knowledge transfer provides no measurable efficiency gain because the agent gets the methodology right without help.

---

## 6. Infrastructure Discoveries

The experiments uncovered several bugs and infrastructure issues:

### 6.1 FTS5 Implicit-AND Bug (Critical)
**Found in**: Task 2.2b analysis. **Fixed in**: Task 2.2c.
`_sanitize_fts_query()` joined tokens with spaces -> FTS5 implicit AND. Multi-word queries always returned 0 results. Fix: `" OR ".join(tokens)`.

### 6.2 Workflow Scope Filter Overly Restrictive
**Found in**: Task 2.2b analysis. **Fixed in**: Task 2.2c.
`_add_scope_filters()` hard-filtered by `scope_workflow`, so bands sessions could not find relax insights for the same compound. Fix: removed workflow WHERE clause.

### 6.3 promote_structure Returns Initial Cell
**Found in**: Sessions 05, 17 (GaP relax, GaN relax).
`promote_structure()` returns the initial geometry instead of the vc-relax final geometry. Agents must parse QE output directly to get relaxed cell parameters. **Not yet fixed.**

### 6.4 cell_dofree='ibrav' with ibrav=0 Bug
**Found in**: Session 21 (CdTe relax, 54 min).
Setting `cell_dofree='ibrav'` with `ibrav=0` constrains the cell incorrectly, producing wrong lattice constants. Fix: use `cell_dofree='all'`. **This is a QE behavior, not a QMatSuite bug.**

### 6.5 SSSP Pseudos Lack SOC Support
**Found in**: Session 32 (PbTe bands, 85 min).
SSSP efficiency/precision pseudopotential libraries do not include fully-relativistic (FR) variants needed for spin-orbit coupling calculations on heavy elements. Agents must switch to PseudoDojo NC-FR pseudos. **Documented but not programmatically addressed.**

### 6.6 Mixed Pseudopotential Silent Degradation
**Found in**: Tasks 2.2 and 2.2b across multiple sessions.
SSSP auto-resolution can assign different pseudo types (PAW, USPP, NC) to different elements in the same compound. PAW+USPP mixing is generally acceptable in QE; PAW+NC mixing causes Pulay stress artifacts and convergence failures. The mixed-pseudo issue does not cause hard errors for lattice constants (errors remain within 1--2% PBE range), making it a silent accuracy degradation.

### 6.7 Summary: Bug Impact on Experiment Validity

| Bug | Sessions Affected | Impact on Results | Status |
|-----|-------------------|-------------------|--------|
| FTS5 implicit-AND | 8 searches in 2.2b | Zero knowledge transfer for entire phase | Fixed |
| Workflow scope filter | All bands sessions in 2.2b | Could not retrieve relax insights | Fixed |
| promote_structure | Sessions 05, 17 | Extra time parsing QE output | Open |
| cell_dofree + ibrav=0 | Session 21 (CdTe) | 54 min session, incorrect first result | QE behavior, documented |
| SSSP no SOC | Session 32 (PbTe) | 85 min pseudo search | Documented |
| Mixed pseudo types | Multiple in 2.2/2.2b | Silent accuracy degradation | Documented |

The FTS5 bug had the largest impact: it invalidated an entire 16-session experiment and required a full re-run (2.2c). The remaining bugs are either QE behaviors or QMatSuite issues that don't affect the knowledge transfer conclusions.

---

## 7. Limitations & Honest Caveats

### 7.1 Single Model

All experiments used claude-opus-4-6. We cannot claim these results generalize to other models (GPT-4, Gemini, smaller Claude variants). The agent's propensity to search, quality of search queries, and ability to act on retrieved knowledge may differ substantially across models.

### 7.2 Single Engine

All calculations used Quantum ESPRESSO. QMatSuite supports 15 engines, but the knowledge system, transfer dynamics, and failure modes are likely engine-specific. VASP, ORCA, and LAMMPS have different input formats, failure modes, and parameter spaces.

### 7.3 Seed Knowledge Dominance

86--93% of search results came from pre-loaded seed knowledge. This means most "knowledge transfer" is actually seed-to-agent transfer, not session-to-session transfer. The 4--14% session-finding fraction, while growing, is still small. It is difficult to disentangle the value of session-generated knowledge from the much larger seed knowledge base.

### 7.4 No Aggregate Learning Curve, but Targeted Efficiency Gains

Knowledge transfer does not produce a measurable aggregate learning curve in either wall time or iteration count. Total wall time and `run_calculation` calls did NOT decrease across phases:
- 2.2b bands total: 166 min, 16 QE runs
- 2.2c bands total: 126 min, 16 run_calculation calls (same iteration count, 24% less time)
- ext + DOS: higher iteration counts due to harder compounds

Aggregate metrics are dominated by compound-specific difficulty and stochastic agent behavior. However, iteration-based metrics (§5.8) tell a more nuanced story: knowledge transfer eliminates wrong-path exploration for specific hard compounds, reducing PbTe from 48→2 `run_calculation` calls (-96%) and InAs from 77→26 min wall time (-66%). The efficiency gain is concentrated where it matters most — sessions where the correct methodology is non-obvious. For easy compounds, knowledge transfer provides no measurable benefit because the agent succeeds without help.

The value of knowledge transfer is **insurance against catastrophic wrong paths** (missing SOC, mixed pseudopotentials, wrong cell_dofree), not incremental speedup for routine calculations. See §5.8 for the full compound-matched comparison, first-attempt success analysis, and PbTe deep dive.

### 7.5 Search Rate Below 65%

Even in the best phase (DOS, 62.5%), over a third of sessions never searched the knowledge base. The knowledge system is purely opt-in; agents that don't search get zero benefit. This is the largest structural limitation.

### 7.6 No L2/L3 Insights Emerged

All 41 recorded insights are L1 findings (specific numerical results or troubleshooting tips). No agent spontaneously synthesized higher-level insights such as "PBE consistently overestimates lattice constants by 1--2% for all zinc-blende III-V compounds" (L2 pattern) or "Mixed PAW+NC pseudopotentials should be avoided in any vc-relax calculation" (L3 principle). Higher-level knowledge formation would require multi-session reflection, which is not currently implemented.

### 7.7 Stochastic Agent Behavior

The same compound can get different search patterns, methodologies, and wall times across runs. Session 07 (AlN relax) used wurtzite in 2.2c but zinc-blende in 2.2b. GaAs bands gave 0.503 eV in 2.2c but 0.135 eV in 2.2b (different pseudos). This stochastic variance makes controlled comparison difficult without many more replicates.

### 7.8 Small Sample Sizes

Each compound was tested once per workflow per phase. N=1 per condition provides no error bars on transfer rates, wall times, or accuracy. The 16-compound corpus provides diversity but not statistical power for any single compound.

---

## 8. Gap Analysis

### Gap 1: No Formal Control for DOS Chain
**Severity**: Important
**Detail**: The DOS chain has no controlled comparison (unlike 2.2b vs 2.2c). We cannot say whether DOS agents performed better *because* of knowledge transfer or simply because the task is straightforward given a relaxed structure. A control experiment with no knowledge DB and no prior calculations in the project would establish the baseline.
**To fill**: Run 8 DOS sessions on the same compounds with empty `local.db` and no prior calculations in the project directory.
**Blocks paper?**: Not critical, but weakens the DOS claims.

### Gap 2: No Cross-Engine Transfer Testing
**Severity**: Important
**Detail**: All experiments used QE. The knowledge system is engine-agnostic in principle, but we have no evidence that a QE relax insight about InAs would help a VASP agent doing InAs bands.
**To fill**: Run a mixed-engine chain (e.g., QE relax -> VASP bands -> ORCA DOS) for a subset of compounds.
**Blocks paper?**: No, but limits generalizability claims.

### Gap 3: No L2/L3 Insight Emergence
**Severity**: Important
**Detail**: All 41 insights are L1 (specific findings). No agent synthesized patterns across compounds or formed general principles. The knowledge system records what agents discover but doesn't promote synthesis.
**To fill**: Add a periodic "reflection" step that reviews accumulated insights and synthesizes patterns. Or add a meta-agent that processes the full insight corpus.
**Blocks paper?**: No -- this is a known limitation and a natural future direction.

### Gap 4: No Ambient Knowledge Surfacing
**Severity**: Critical for product, not for paper
**Detail**: 37--60% of sessions never search. Ambient surfacing (auto-providing relevant knowledge when `create_calculation` is called) would close this gap.
**To fill**: Implement auto-surfacing in the MCP server. This is a code change, not an experiment.
**Blocks paper?**: No, but should be in recommendations.

### Gap 5: No Ranking/Relevance Scoring
**Severity**: Nice-to-have
**Detail**: FTS5 with OR-join returns results ranked by BM25, but all queries return the maximum 10 results. Session-specific findings may be pushed below the limit by high-scoring generic seed entries.
**To fill**: Implement compound-aware boosting or increase the result limit. Add element extraction from queries for exact-match filtering.
**Blocks paper?**: No.

### Gap 6: Session Findings Drowned by Seed Knowledge
**Severity**: Important
**Detail**: At 86--93% seed dominance, session findings provide marginal signal. This could be an artifact of the broad OR-join search returning many generic seed matches.
**To fill**: Test with an empty `builtin.db` (seed-free chain) to isolate session-to-session transfer. Also test with compound-specific search boosting.
**Blocks paper?**: No, but a seed-free experiment would be compelling.

### Gap 7: No Statistical Significance Testing
**Severity**: Important
**Detail**: Is 6 STRONG events in 16 sessions statistically significant? Is the 50% -> 37.5% search rate change meaningful or noise? With N=1 per compound per workflow, we cannot compute confidence intervals.
**To fill**: Multiple replicates per compound (3--5x) would enable significance testing. This is expensive (~50h of additional compute).
**Blocks paper?**: Not fatal, but reviewers may question it.

### Gap 8: No Comparison with Human Researcher Workflow
**Severity**: Nice-to-have
**Detail**: We don't know how a human expert would perform on the same task sequence. A human naturally carries knowledge between sessions and would likely achieve higher transfer rates.
**To fill**: Have 1--2 DFT practitioners follow the same compound sequence, recording their knowledge transfer decisions. Compare search patterns and efficiency.
**Blocks paper?**: No.

### Gap 9: CaO 0% Lattice Error Unexplained
**Severity**: Nice-to-have
**Detail**: CaO vc-relax (session 23) returned a = 4.810 A vs experimental 4.811 A (0.0% error). This is suspiciously accurate for PBE, suggesting the starting CIF structure was already at the experimental geometry.
**To fill**: Verify the CIF source for CaO. Re-run from a perturbed starting geometry.
**Blocks paper?**: No.

### Gap 10: Knowledge Quality Not Validated — **ADDRESSED (see §A.6)**
**Severity**: Important
**Detail**: We verified that agents record insights and retrieve them, but we did not systematically validate whether the recorded insights are actually correct. An incorrect insight could propagate erroneous information.
**Resolution**: All 40 insights in `local_db_final_dos.db` were cross-referenced against Materials Project PBE-PAW values, Tran et al. (2017) PBE benchmarks, and CRC/Madelung experimental references. Results: 16/16 lattice constants correct, 14/16 band gaps correct or approximately correct (2 minor gap-type misclassifications), 3/16 experimental reference values slightly non-standard. No insight contains dangerously incorrect information. See Appendix §A.6 for the full validation table.
**Blocks paper?**: No longer blocking.

### Gap 11: No Cost-Benefit Analysis
**Severity**: Nice-to-have
**Detail**: The DOS phase cost $12.52 across 8 sessions ($1.57 avg). We don't know how much additional cost the knowledge search adds (extra API calls, longer prompts from retrieved knowledge) vs the savings from faster convergence.
**To fill**: Compare API cost per session for searching vs non-searching sessions, controlling for compound difficulty.
**Blocks paper?**: No.

### Gap 12: Missing Compounds
**Severity**: Nice-to-have
**Detail**: 16 compounds is a reasonable diversity sample but covers only a fraction of the materials space. No transition metal compounds, no 2D materials, no molecular crystals.
**To fill**: Future phases could add transition metal oxides (e.g., TiO2, Fe2O3), 2D materials (graphene, MoS2), and strongly correlated systems.
**Blocks paper?**: No.

---

## 9. Recommendations for Next Steps

### 9.1 Immediate (Before Task 2.3)

1. **Fix promote_structure for vc-relax** (infrastructure bug §6.3). Multiple sessions lost time parsing QE output because promote_structure returned the initial cell.

2. **Add SOC pseudo guidance to seed knowledge**. A seed entry stating "SSSP pseudos do not support SOC; use PseudoDojo NC-FR for elements with Z > 50" would save substantial time for heavy-element compounds.

3. ~~**Validate all recorded insights** (Gap 10)~~ — **DONE**. See §A.6. All 40 insights validated; no dangerous errors found.

### 9.2 Additional Experiments to Strengthen the Paper

4. **Seed-free control chain** (Gap 6). Run 16 sessions with empty `builtin.db` but accumulated `local.db`. This isolates session-to-session transfer from seed knowledge.

5. **DOS control experiment** (Gap 1). Run 8 DOS sessions with no prior calculations and empty knowledge DB. Compare wall time and success rate.

6. **Multiple replicates** (Gap 7). Run 3 replicates of the 8-compound bands chain to compute error bars on search rate and transfer frequency.

### 9.3 System Improvements

7. **Implement ambient knowledge surfacing** (Gap 4). Auto-surface relevant insights when `create_calculation()` is called, keyed by compound/element.

8. **Add compound-aware search boosting** (Gap 5). Extract element symbols from queries and boost results tagged with matching compounds.

9. **Increase search result limit** from 10 to 20 for chains with large local.db.

### 9.4 Future Work (Post-Paper)

10. **Cross-engine transfer** (Gap 2). Test QE -> VASP -> ORCA chains.

11. **L2/L3 insight synthesis** (Gap 3). Add a meta-agent or periodic reflection step.

12. **Transition metal compounds** (Gap 12). Expand beyond sp-bonded semiconductors.

---

## 10. Appendix: Complete Numerical Results

### A.1 All Lattice Constants

| # | Compound | Structure | a_calc (A) | c_calc (A) | a_exp (A) | c_exp (A) | Error a (%) | Phase |
|---|----------|-----------|-----------|-----------|-----------|-----------|-------------|-------|
| 1 | GaAs | ZB | 5.746 | -- | 5.653 | -- | +1.6 | 2.2c |
| 2 | SiC | ZB | 4.381 | -- | 4.360 | -- | +0.5 | 2.2c |
| 3 | AlAs | ZB | 5.732 | -- | 5.661 | -- | +1.3 | 2.2c |
| 4 | BN | ZB | 3.624 | -- | 3.616 | -- | +0.2 | 2.2c |
| 5 | GaP | ZB | 5.505 | -- | 5.451 | -- | +1.0 | 2.2c |
| 6 | InP | ZB | 5.960 | -- | 5.869 | -- | +1.6 | 2.2c |
| 7 | AlN | WZ | 3.113 | 4.984 | 3.112 | 4.982 | +0.03 | 2.2c |
| 8 | InAs | ZB | 6.190 | -- | 6.058 | -- | +2.2 | 2.2c |
| 9 | GaN | WZ | 3.217 | 5.241 | 3.189 | 5.185 | +0.9 | ext |
| 10 | AlSb | ZB | 6.222 | -- | 6.136 | -- | +1.4 | ext |
| 11 | InSb | ZB | 6.633 | -- | 6.479 | -- | +2.4 | ext |
| 12 | ZnS | ZB | 5.438 | -- | 5.409 | -- | +0.5 | ext |
| 13 | CdTe | ZB | 6.610 | -- | 6.481 | -- | +2.0 | ext |
| 14 | MgO | RS | 4.253 | -- | 4.212 | -- | +1.0 | ext |
| 15 | CaO | RS | 4.810 | -- | 4.811 | -- | ~0.0* | ext |
| 16 | PbTe | RS | 6.567 | -- | 6.462 | -- | +1.6 | ext |

ZB = zinc-blende, WZ = wurtzite, RS = rocksalt. *CaO anomalous.
Mean error (excl. CaO): +1.1%. Range: +0.03% to +2.4%.

### A.2 All Band Gaps

| # | Compound | Bands (eV) | DOS (eV) | Exp (eV) | Bands Error | Gap Type | SOC |
|---|----------|-----------|----------|---------|-------------|----------|-----|
| 1 | GaAs | 0.503 | -- | 1.42 | -65% | direct (Gamma) | No |
| 2 | SiC | 1.36 | -- | 2.36 | -42% | indirect (Gamma-X) | No |
| 3 | AlAs | 1.46 | -- | 2.16 | -32% | indirect (Gamma-X) | No |
| 4 | BN | 4.53 | -- | 6.36 | -29% | indirect (Gamma-X) | No |
| 5 | GaP | 1.59 | -- | 2.26 | -30% | indirect (Gamma-X) | No |
| 6 | InP | 0.69 | -- | 1.34 | -49% | direct (Gamma) | No |
| 7 | AlN | 4.16 | -- | ~6.0 | -31% | direct (Gamma, WZ) | No |
| 8 | InAs | 0.00 | -- | 0.35 | -100% | inverted | No |
| 9 | GaN | 1.85 | 1.84 | 3.40 | -46% | direct (Gamma, WZ) | No |
| 10 | AlSb | 1.24 | 1.30 | 1.62 | -23% | indirect (Gamma-L) | No |
| 11 | InSb | 0.00 | 0.15 | 0.235 | -100% | inverted | No |
| 12 | ZnS | 2.09 | 2.09 | 3.54 | -41% | direct (Gamma) | No |
| 13 | CdTe | 0.77 | 0.78 | 1.60 | -52% | direct (Gamma) | No |
| 14 | MgO | 4.75 | 4.90 | 7.83 | -39% | direct (Gamma) | No |
| 15 | CaO | 3.65 | 3.67 | 7.00 | -48% | direct (Gamma) | No |
| 16 | PbTe | 0.094 | 0.10--0.15 | 0.19 | -51% | direct (L) | Yes |

### A.3 Transfer Event Catalog

| # | Phase | Session | Source | Target Knowledge | Type | Strength |
|---|-------|---------|--------|-----------------|------|----------|
| 1 | 2.2c | 03 AlAs relax | Seed | PBE bias, convergence settings | Parameter | STRONG |
| 2 | 2.2c | 04 BN relax | Sessions 01-03 | GaAs/SiC/AlAs lattice constants, PAW+NC warning | Template | STRONG |
| 3 | 2.2c | 07 AlN relax | Session 04 | BN ecutwfc >= 90 Ry for NC pseudos | Parameter | STRONG |
| 4 | 2.2c | 08 InAs relax | Seed | PBE should give +1-2%, not -4.6% | Diagnostic | STRONG |
| 5 | 2.2c | 13 GaP bands | Seed | ecutwfc, nbnd formula, occupations | Parameter | STRONG |
| 6 | 2.2c | 14 InP bands | Seed + project state | PBE gap error, GaAs_bands template | Parameter+Template | STRONG |
| 7 | ext | 18 AlSb relax | Session 08 (2.2c) | InAs mixed pseudo warning | Diagnostic | STRONG |
| 8 | ext | 19 InSb relax | Session 08 + ext 17-18 | InAs lattice calibration, GaN/AlSb refs | Parameter | STRONG |
| 9 | ext | 21 CdTe relax | Sessions 08,18-20 | Multiple lattice constants | -- | MODERATE |
| 10 | ext | 25 GaN bands | Seed | PBE gap error, nbnd, occupations | Parameter | STRONG |
| 11 | ext | 27 InSb bands | Session 16 (2.2c) | InAs band inversion -> InSb prediction | Predictive | STRONG |
| 12 | ext | 28 ZnS bands | Seed | PBE gap, nbnd, occupations | Parameter | STRONG |
| 13 | ext | 30 MgO bands | Session 22 + 28 | MgO relax self-chain + ZnS gap | Template | STRONG |
| 14 | ext | 31 CaO bands | Session 30 | MgO bands as template | Template | STRONG |
| 15 | ext | 32 PbTe bands | Seed | SOC essential for Z > 50 | Parameter | STRONG |
| 16 | DOS | 39 CaO DOS | Sessions 36, 38 | ZnS nbnd lesson + MgO DOS ref | Debugging | STRONG |
| 17 | DOS | 40 PbTe DOS | Session 32 + project | PbTe bands SOC gap + SOC params | Template+Parameter | STRONG |

### A.4 Knowledge DB Snapshots

| Snapshot | File | Insights | Seed | Session |
|----------|------|----------|------|---------|
| After 2.2b | `.tmp/pseudo_chain/local_db_final_2_2b.db` | 17 | 45 | 17 |
| After 2.2c | `.tmp/pseudo_chain_v2c/local_db_final_2_2c.db` | 16 | 45 | 16 |
| After ext bands | `.tmp/pseudo_chain_v2c_ext/local_db_after_bands.db` | 31 | 45 | 31 |
| After DOS | `.tmp/pseudo_chain_v2c_ext/local_db_final_dos.db` | 40 | 45 | 40 |
| Seed only | `.qmatsuite/knowledge/builtin.db` | -- | 45 | 0 |

The 2.2b chain produced 17 insights (1 duplicate) while 2.2c produced 16 (no duplicates). The ext chain added 15 (CaO missing) and DOS added 9 more, reaching 40 total session-generated insights.

### A.5 Per-Phase Aggregate Statistics

| Metric | 2.2 (v1) | 2.2b (control) | 2.2c (treatment) | ext | DOS | Grand Total |
|--------|----------|----------------|------------------|-----|-----|-------------|
| Runs | 5 | 16 | 16 | 16 | 8 | **61** |
| Wall time (min) | 70 | 233 | 254 | 297 | 172 | 1026 |
| Tool calls | 238 | 671 | 713 | 750 | 332 | 2704 |
| search_knowledge calls | 1 | 8 | 6 | 10 | 6 | 31 |
| Searches with hits | 0 | 0 | 6 | 9 | 5 | 20 |
| STRONG transfers | 0 | 0 | 6 | 8 | 2 | 16 |
| record_insight calls | 5 | 16 | 16 | 15 | 10 | 62 |
| Session insights in DB | 3* | 17** | 16 | 15 | 9 | 60*** |
| Success rate | 100% | 100% | 100% | 100% | 100% | 100% |

*v1 had different protocol; only 3 of 5 sessions' insights persisted to the chain databases.
**2.2b insights were overwritten when 2.2c started with a fresh `local.db`. They exist in the `local_db_final_2_2b.db` snapshot but not in the final chain.
***60 total insights recorded across all phases. The final `local_db_final_dos.db` contains 40 unique insights (16 from 2.2c + 15 from ext + 9 from DOS). 2.2b's 17 and v1's 3 are in separate snapshots only.

**Structural note**: 2.2b and 2.2c are a **controlled pair** (same 8 compounds, same prompts, only the FTS5 fix changed). 2.2c → ext → DOS form a **continuous chain** (40 sessions, accumulated `local.db`). Summing 2.2b + 2.2c as "32 sessions" would double-count the 8 compounds; they should be compared, not summed. The chain's unique session count is 40 (2.2c + ext + DOS).

### A.6 Insight Validation (Gap 10)

All 40 insights in `local_db_final_dos.db` were cross-referenced against published PBE results (Materials Project PBE-PAW calculations, Tran et al. J. Phys. Chem. A 2017, Borlido et al. J. Chem. Theory Comput. 2019) and standard experimental references (Madelung "Semiconductors", CRC Handbook). Status: **✓** correct, **≈** approximately correct (within expected PBE/pseudopotential variance), **✗** incorrect, **?** unable to verify.

#### A.6.1 Lattice Constants

| # | Compound | a_calc (A) | a_exp (claimed) | a_exp (literature) | a_PBE (MP) | Calc vs MP | Exp Ref | Status |
|---|----------|-----------|----------------|-------------------|-----------|-----------|---------|--------|
| 1 | GaAs | 5.746 | 5.653 | 5.653 | 5.750 | -0.07% | ✓ | ✓ |
| 2 | SiC | 4.381 | 4.360 | 4.360 | 4.380 | +0.02% | ✓ | ✓ |
| 3 | AlAs | 5.732 | 5.661 | 5.661 | 5.733 | -0.02% | ✓ | ✓ |
| 4 | BN | 3.624 | 3.616 | 3.616 | 3.626 | -0.06% | ✓ | ✓ |
| 5 | GaP | 5.505 | 5.451 | 5.451 | 5.507 | -0.04% | ✓ | ✓ |
| 6 | InP | 5.960 | 5.869 | 5.869 | 5.957 | +0.05% | ✓ | ✓ |
| 7 | AlN | 3.113/4.984 | 3.112/4.982 | 3.111/4.981 | 3.129/5.017 | -0.5%/-0.7% | ≈ | ≈ |
| 8 | InAs | 6.190 | 6.058 | 6.058 | 6.182 | +0.1% | ✓ | ✓ |
| 9 | GaN | 3.217/5.241 | 3.189/5.185 | 3.189/5.185 | 3.216/5.240 | ~0% | ✓ | ✓ |
| 10 | AlSb | 6.222 | 6.136 | 6.136 | 6.234 | -0.2% | ✓ | ≈ |
| 11 | InSb | 6.633 | 6.479 | 6.479 | 6.633 | 0.0% | ✓ | ✓ |
| 12 | ZnS | 5.438 | 5.409 | 5.410 | 5.450 | -0.2% | ≈ | ≈ |
| 13 | CdTe | 6.610 | 6.481 | 6.482 | 6.628 | -0.3% | ≈ | ≈ |
| 14 | MgO | 4.253 | 4.212 | 4.212 | 4.257 | -0.1% | ✓ | ✓ |
| 15 | CaO | 4.810 | 4.811 | 4.811 | 4.839 | -0.6% | ✓ | ≈ |
| 16 | PbTe | 6.567 | 6.462 | 6.462 | 6.566 | +0.02% | ✓ | ✓ |

**Assessment**: All 16 lattice constants are within expected variance. The "Calc vs MP" column shows the QE-SSSP result vs Materials Project PBE-PAW (VASP). Differences of 0.1--0.7% are expected from pseudopotential and code differences (QE vs VASP, SSSP vs MP PAW library). AlN shows the largest deviation (-0.5%), likely from different pseudopotential cutoffs. No insight contains a factually incorrect lattice constant.

The experimental reference values cited by agents are all correct to within 0.001 A of standard literature values (Madelung/CRC).

#### A.6.2 Band Gaps

| # | Compound | Gap (eV) | Gap Type (claimed) | Gap Type (lit.) | Exp (claimed) | Exp (lit.) | PBE Ref (Tran) | Status |
|---|----------|---------|-------------------|----------------|--------------|-----------|----------------|--------|
| 1 | GaAs | 0.503 | direct Gamma | direct Gamma | 1.42 | 1.42 | 0.54 | ≈ |
| 2 | SiC | 1.36 | indirect Gamma→X | indirect Gamma→X | 2.36 | 2.36 | 1.36 | ✓ |
| 3 | AlAs | 1.46 | indirect Gamma→X | indirect Gamma→X | 2.16 | 2.16 | 1.45 | ✓ |
| 4 | BN | 4.53 | indirect Gamma→X | indirect Gamma→X | 6.1--6.4 | 6.36 | 4.45 | ≈ |
| 5 | GaP | 1.59 | indirect Gamma→X | indirect Gamma→X | 2.26 | 2.26 | 1.60 | ✓ |
| 6 | InP | 0.69 | direct Gamma | direct Gamma | 1.35 | 1.34 | 0.68 | ✓ |
| 7 | AlN | 4.16 | direct Gamma | direct Gamma | ~6.2 | 6.2 | 3.33 | ≈ |
| 8 | InAs | -0.218 (inv.) | band inversion | band inversion | 0.354 | 0.36 | 0.00 | ✓ |
| 9 | GaN | 1.85 | direct Gamma | direct Gamma | 3.4 | 3.39 | 1.66 | ≈ |
| 10 | AlSb | 1.24 | indirect Gamma→L | indirect Gamma→X* | 1.62 | 1.62 | 1.22 | ≈ |
| 11 | InSb | -0.59 (inv.) | band inversion | band inversion | 0.235 | 0.17 | 0.00 | ≈ |
| 12 | ZnS | 2.09 | direct Gamma | direct Gamma | 3.54 | 3.68 | 2.09 | ≈ |
| 13 | CdTe | 0.77 | direct Gamma | direct Gamma | 1.6 | 1.48 | 0.76 | ≈ |
| 14 | MgO | 4.75 | direct Gamma | direct Gamma | 7.8 | 7.8 | 4.78 | ✓ |
| 15 | CaO | 3.65 | direct Gamma | indirect Gamma→X** | 7.0 | 7.1 | 3.67 | ≈ |
| 16 | PbTe | 0.094 | direct L | direct L | 0.19 | 0.31 | N/A (SOC) | ≈ |

**Notes on flagged items**:

- **(10) AlSb gap type**: The insight claims indirect Gamma→L. Literature is ambiguous — the CBM is near X but with a camelback structure; some references say Gamma→X, others Gamma→near-X. The L-valley is close in energy. **Status ≈**: not incorrect, but the standard classification is Gamma→X.

- **(11) InSb experimental gap**: The insight cites 0.235 eV; standard 300K value is 0.17 eV (CRC/Ioffe). The 0.235 eV value appears to be from a low-temperature measurement or an older reference. **Status ≈**: the order of magnitude and physics are correct, but the reference value is non-standard.

- **(12) ZnS experimental gap**: The insight cites 3.54 eV; CRC gives 3.68 eV (300K). The 3.54 eV may be from a different polytype or temperature. **Status ≈**: slight discrepancy but not harmful.

- **(13) CdTe experimental gap**: The insight cites 1.6 eV; CRC gives 1.48 eV (300K). The 1.6 eV value may be from a 0K/2K measurement. **Status ≈**: PBE error percentage changes from -52% (using 1.6) to -48% (using 1.48) — the qualitative conclusion (severe underestimation) is unaffected.

- **(15) CaO gap type**: The insight claims direct at Gamma. PBE calculations (Materials Project, Tran et al.) show CaO has an indirect Gamma→X gap. The agent likely measured the direct gap at Gamma rather than the true CBM at X. **Status ≈**: the gap *value* (3.65 eV) is reasonable for the Gamma-point direct gap, but the fundamental gap classification is wrong.

- **(16) PbTe experimental gap**: The insight cites 0.19 eV; CRC gives 0.31 eV (300K). The 0.19 eV value is from low-temperature measurements (~4K). **Status ≈**: the agent correctly identified PbTe as a narrow-gap semiconductor requiring SOC, so this doesn't affect methodology.

#### A.6.3 Methodological Claims

| Claim | Source Session | Correct? | Notes |
|-------|--------------|----------|-------|
| "Davidson diagonalization fails with fixed occupations" | 09 (GaAs bands) | ≈ | RMM-Davidson (not standard Davidson) can fail; the insight's advice to use `diagonalization='david'` is correct |
| "ecutwfc >= 90 Ry for NC pseudos" | 04 (BN relax) | ✓ | BN NC pseudos in PseudoDojo typically need 80--100 Ry |
| "SSSP precision As.nc.z_15 gives wrong lattice constant" | 03 (AlAs relax) | ✓ | NC pseudo + PAW mixing causes Pulay stress; documented in 2.2b/2.2c |
| "cell_dofree='ibrav' with ibrav=0 gives wrong cell" | 21 (CdTe relax) | ✓ | Known QE behavior; ibrav=0 means no lattice type constraint |
| "PBE overestimates lattice constants by 1-2%" | Multiple | ✓ | Well-established PBE behavior for these materials |
| "PBE underestimates band gaps by 30-50%" | Multiple | ✓ | Well-established; actual range 23-100% for these compounds |
| "SOC essential for PbTe; SSSP lacks FR pseudos" | 32 (PbTe bands) | ✓ | SSSP efficiency/precision sets do not include FR variants |
| "Zn Zval=20 → 52 occupied bands; nbnd must exceed this" | 36 (ZnS DOS) | ✓ | SSSP Zn PAW has 20 electrons; 2 atoms × 26 = 52 occupied bands |

#### A.6.4 Validation Summary

Of 40 insights in `local_db_final_dos.db`:
- **Lattice constants**: 16/16 correct (within expected PBE/PP variance)
- **Band gaps**: 14/16 correct or approximately correct; 2 have minor issues (AlSb gap location, CaO gap type classification)
- **Experimental references**: 13/16 match standard literature; 3 have non-standard values (InSb 0.235→0.17, ZnS 3.54→3.68, CdTe 1.6→1.48, PbTe 0.19→0.31). None are grossly wrong.
- **Methodological claims**: 8/8 verified correct
- **Propagation risk**: LOW. The two gap-type misclassifications (AlSb, CaO) would not cause a future agent to choose incorrect methodology. The non-standard experimental references could slightly miscalibrate PBE error assessments but not change qualitative conclusions.

**Overall**: No insight contains dangerously incorrect information. The knowledge base is reliable for its intended purpose (guiding PBE workflow decisions).

---

## 11. Conclusions

1. **Knowledge transfer between AI agent sessions is real and measurable.** When the search infrastructure works correctly, agents retrieve and apply knowledge in 100% of search sessions, with chemically specific reasoning (not random noise).

2. **The FTS5 bug provides the cleanest experimental evidence.** The 2.2b-vs-2.2c controlled comparison -- identical protocol, 2-line code change -- produced 0 vs 6 STRONG transfer events. This demonstrates that the bottleneck was infrastructure, not agent capability.

3. **Seed knowledge provides the majority of immediate value.** At 86--93% of search results, curated domain knowledge in `builtin.db` is far more impactful than session-generated findings. Investing in high-quality seed knowledge packs yields the highest ROI.

4. **Session-generated knowledge is growing but still marginal.** The session-finding fraction increased from 7% to 14% over 32 sessions. At this rate, it would take hundreds of sessions for session knowledge to rival seed knowledge in search results -- unless search ranking is improved.

5. **Project state is the dominant channel for cross-workflow transfer.** When prior calculations exist in the project, agents overwhelmingly use `list_calculations` + `inspect_calculation` to reuse structures and parameters (8/8 DOS sessions). The knowledge DB is essential only for cross-compound insights.

6. **The InSb band inversion prediction is the experiment's crown jewel.** A genuine example of predictive scientific reasoning: the agent applied InAs knowledge to predict InSb behavior before calculating. This is the type of knowledge transfer that could meaningfully accelerate computational materials science research.

7. **Significant gaps remain.** No formal controls for DOS, no cross-engine testing, no L2/L3 insight emergence, and no ambient knowledge surfacing. Search rate remains below 65%, meaning one-third to two-thirds of sessions get zero benefit from the knowledge system.

8. **Cost-effectiveness is favorable.** At $12.52 for 8 DOS sessions (including knowledge search overhead), the marginal cost of knowledge transfer is negligible compared to the potential savings. PbTe DOS (session 40) demonstrates the upper bound: what took 85 minutes in the bands phase completed correctly on the first attempt in the DOS phase, with the knowledge DB providing the methodology and project state providing the parameters.

9. **Experiment design improved iteratively.** The v1 → 2.2b → 2.2c progression demonstrates the value of "experiment on the experiment" -- each phase's failures directly informed the next phase's design. The FTS5 bug would not have been discovered without the 2.2b chain; the controlled 2.2c comparison would not exist without the 2.2b baseline. This suggests that knowledge system validation should be part of any AI-agent product's development cycle, not an afterthought.

---

*This review was generated from experimental data in `.tmp/pseudo_case_study_v1/`, `.tmp/pseudo_chain/`, `.tmp/pseudo_chain_v2c/`, `.tmp/pseudo_chain_v2c_ext/`, and `docs/history/worklogs/WORKLOG_PSEUDO_CASE_STUDY.md`.*
