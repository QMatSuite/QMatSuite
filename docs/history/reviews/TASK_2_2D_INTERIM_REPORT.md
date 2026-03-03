# Task 2.2d Interim Report: Controlled Knowledge Transfer Efficiency

**Date:** 2026-03-02 (updated 2026-03-03)
**Status:** Phase A complete (12/12), Phase B in progress (5/12 complete, B06 skipped, B07+ running)

## Experiment Design

A clean A/B causal test measuring whether pre-loaded knowledge DB entries improve agent efficiency on DFT workflows. The **only** variable between conditions is the `local.db` content.

- **Condition A (Naive):** Empty `local.db` — agent has only the 45 builtin seeds
- **Condition B (Informed):** `local.db` pre-loaded with A's 3 pipeline findings per material
- **Materials:** PbTe (strong SOC), InSb (moderate SOC), CdTe (moderate), MgO (control)
- **Workflows per material:** relax → bands → DOS (sequential, same project)
- **Total:** 24 sessions (4 materials x 2 conditions x 3 workflows)
- **Infrastructure:** QE 7.5, MPI 12-core, SSSP pseudopotentials, Claude Opus 4.6

## Raw Data (17/24 sessions complete)

### Phase A (Naive) — Complete

| Material | Relax | Bands | DOS | Pipeline Total |
|----------|-------|-------|-----|----------------|
| PbTe | 8m / 8rc | 108m / 22rc | 62m / 16rc | **178m / 46rc** |
| InSb | 5m / 17rc | 18m / 19rc | 18m / 24rc | **41m / 60rc** |
| CdTe | 27m / 7rc | 18m / 11rc | 14m / 15rc | **59m / 33rc** |
| MgO | 6m / 7rc | 6m / 12rc | 4m / 11rc | **16m / 30rc** |

*Format: wall time / run_calculation calls. All sessions exit 0.*

### Phase B (Informed) — PbTe + InSb partial

| Material | Relax | Bands | DOS | Pipeline Total |
|----------|-------|-------|-----|----------------|
| PbTe | 26m / 10rc | 85m / 18rc | 66m / 19rc | **177m / 47rc** |
| InSb | 11m / 8rc | 98m / 31rc | **SKIP** | — |
| CdTe | — | — | — | — |
| MgO | — | — | — | — |

### Head-to-Head: PbTe (complete pipeline)

| Step | A (Naive) | B (Informed) | Wall Delta | run_calc Delta |
|------|-----------|-------------|------------|----------------|
| relax | 8m / 8rc | 26m / 10rc | **+225%** | +25% |
| bands | 108m / 22rc | 85m / 18rc | **-21%** | **-18%** |
| dos | 62m / 16rc | 66m / 19rc | +6% | +19% |
| **Total** | **178m / 46rc** | **177m / 47rc** | **-0.6%** | +2% |

### Head-to-Head: InSb (partial — relax + bands only)

| Step | A (Naive) | B (Informed) | Wall Delta | run_calc Delta |
|------|-----------|-------------|------------|----------------|
| relax | 5m / 17rc | 11m / 8rc | +120% | **-53%** |
| bands | 18m / 19rc | 98m / 31rc | **+444%** | +63% |

## Key Observations

### 1. PbTe bands: knowledge helped, but pipeline total washed out

The PbTe bands step is the experiment's flagship test case. The A pipeline spent 108 minutes struggling with SOC — the naive agent had to discover that PbTe requires fully relativistic pseudopotentials and SOC treatment. The B agent, armed with A's finding ("PBE without SOC gives wrong band ordering"), reached the correct SOC calculation faster (85m, -21%).

However, the B agent's relax step took 3x longer (26m vs 8m). Trace inspection suggests the informed agent pursued a more thorough setup (heavier pseudopotentials, more careful convergence), likely guided by the knowledge that PbTe requires special treatment. The net pipeline time is virtually identical (177m vs 178m).

**Interpretation:** Knowledge transferred *quality awareness* rather than *speed*. The B agent front-loaded effort into getting the physics right from the start, while the A agent stumbled into the correct approach through trial and error on the bands step.

### 2. InSb: B agent performed worse on bands despite knowledge

This is the most surprising result so far. The B agent's InSb bands calculation took 98 minutes and 31 `run_calculation` calls — dramatically worse than A's 18m/19rc. The A pipeline's 3 transferred insights explicitly state that "PBE predicts InSb as a zero-gap semimetal due to band inversion" and that SOC doesn't fix this.

The B agent appears to have struggled *more* with this known-difficult system, possibly because the knowledge raised awareness of the problem without providing a solution (the correct fix requires hybrid functionals or GW, not available in the experiment's QE/PBE setup). The agent may have spent more attempts trying to resolve the known zero-gap issue.

**Interpretation:** Knowledge about an *unsolvable* problem (within the method constraints) can increase effort rather than reduce it. The naive agent accepted the zero-gap result and moved on; the informed agent knew the result was wrong and kept trying.

### 3. Relax steps consistently slower in B

Both materials show B-condition relax taking longer (PbTe: 8→26m, InSb: 5→11m). However, InSb relax `run_calc` dropped dramatically (17→8, -53%). The B agent set up calculations more carefully with fewer wasted runs, but the per-run compute time was higher (heavier pseudos, tighter convergence).

### 4. Knowledge system engagement is identical across conditions

Both conditions show remarkably consistent `search_knowledge` (2-3 per session) and `record_insight` (2 per session) patterns. The knowledge system's *usage frequency* is not affected by DB content — only the *content retrieved* differs.

### 5. All A pipeline insights are domain-appropriate findings

Every material produced exactly 3 insights (one per workflow step), all graded `finding`. The content is scientifically specific: lattice constants with error bars, band gap values with method caveats, DOS features. These are high-quality knowledge entries that faithfully capture the computational results.

### 6. B06_dos_InSb: the "awareness tax" made concrete

B06 was skipped after the informed agent launched an NSCF calculation with **868 k-points** (SOC, InSb DOS attempt 2), versus A06's 145-256. At ~10 k-points/hour, this single QE step would have taken ~3.5 days. Two separate attempts both escalated to impractical meshes.

The A agent (naive) used modest k-meshes, got a zero-gap DOS, reported it, and moved on in 18 minutes. The B agent, armed with knowledge that "PBE predicts InSb as a zero-gap semimetal due to band inversion," tried to compensate with brute-force k-point density — seeking fine structure that cannot exist within the PBE approximation for this material.

This is the clearest evidence of the awareness tax: **knowledge about an unsolvable problem (within method constraints) can make the agent work harder, not smarter.** The naive agent's ignorance was operationally superior — it completed quickly and reported the correct (if limited) result.

## Operational Issues

### MCP `run_calculation` hang (1 confirmed occurrence)

B06_dos_InSb's first run attempt (from the earlier restart) experienced a stuck `run_calculation` where QE completed but the MCP server never returned the result. The second run attempt was not a hang — it was genuinely computing an impractically large NSCF (868 k-points with SOC).

**Corrective action:** Removed the 2-hour timeout from the runner script. The `run_calculation` hang is a separate MCP infrastructure issue.

## Preliminary Conclusions (subject to CdTe + MgO completion)

1. **Knowledge transfer is real but nuanced.** The B agent demonstrably changes behavior based on transferred insights — it uses SOC from the start for PbTe, uses heavier pseudopotentials, and shows awareness of known problems. But this doesn't always translate to faster completion.

2. **The "awareness tax" hypothesis.** When knowledge describes a problem that *can* be solved within method constraints (PbTe SOC), it accelerates the solution. When knowledge describes an *inherent limitation* (InSb zero-gap with PBE), it may increase effort as the agent tries harder to fix an unfixable problem.

3. **Quality vs speed tradeoff.** B-condition relax steps consistently take longer but use fewer `run_calc` calls (InSb: -53%). The agent is doing fewer but more expensive calculations — a sign of better planning but not necessarily faster completion.

4. **Pipeline-level effects are small for PbTe.** Despite a 21% improvement on the hardest step (bands), the total pipeline time is within 1%. Gains on one step are offset by more thorough work on others.

5. **MgO (negative control) will be critical.** MgO is a simple wide-gap insulator with no SOC complications. If the B agent shows no significant difference on MgO, it confirms that knowledge effects are material-specific rather than systematic overhead.

## What Remains

- **B06_dos_InSb:** Skipped (runaway k-mesh, see observation 6 above)
- **B07-B09 (CdTe):** CdTe is a moderate-difficulty semiconductor; expect moderate knowledge effects
- **B10-B12 (MgO):** Negative control — expect minimal A/B differences
- **Final analysis:** `metrics_2_2d.json` + `REPORT_2_2D.md` with full statistical comparison
