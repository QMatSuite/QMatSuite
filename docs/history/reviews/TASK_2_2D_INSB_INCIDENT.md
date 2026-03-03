# Incident Report: B06_dos_InSb — Knowledge-Induced Compute Runaway

**Date:** 2026-03-02 / 2026-03-03
**Experiment:** Task 2.2d Controlled Knowledge Transfer Efficiency Study
**Session:** B06_dos_InSb (Condition B, Informed)
**Outcome:** Session skipped after two failed launches; agent escalated to an impractical 868 k-point NSCF calculation estimated at 3.5 days

## Context

Task 2.2d is a controlled A/B experiment. For each material, two pipelines
(relax → bands → DOS) run with identical prompts. The only difference:

- **Condition A (Naive):** empty `local.db` — agent has only 45 builtin seeds
- **Condition B (Informed):** `local.db` pre-loaded with A's 3 pipeline findings

InSb (indium antimonide) is a narrow-gap III-V semiconductor with strong
spin-orbit coupling. PBE-DFT fundamentally fails to open the InSb band gap
due to systematic GGA underestimation — the gap inverts, making InSb appear
as a zero-gap semimetal. Correcting this requires hybrid functionals (HSE06)
or GW, neither available in the experiment's QE/PBE setup.

## What A06 (Naive) Did

The naive agent completed the InSb DOS in **18 minutes** with **24 `run_calculation` calls** across 3 attempts:

| Attempt | k-points | Method | NSCF done | Outcome |
|---------|----------|--------|-----------|---------|
| `insb_dos_attempt1` | 145 | Gaussian smearing (σ=0.01 Ry) | Yes | Got zero-gap DOS |
| `insb_dos_attempt2_fine` | 256 | Gaussian smearing (σ=0.005 Ry) | Yes | Same zero-gap result, finer mesh |
| `insb_dos_attempt3_soc` | 145 | Gaussian smearing (σ=0.005 Ry) + SOC | Yes | Still zero-gap, reported result |

The naive agent tried reasonable mesh sizes, observed the zero gap, tried SOC
as an obvious fix, confirmed it didn't help, and reported the result with appropriate
caveats. All three NSCF steps completed in seconds to minutes. Total wall time: 18 minutes.

**A06's recorded insight:**
> "PBE (with and without SOC) predicts InSb as a zero-gap semimetal due to band
> inversion at Gamma. [...] This is a fundamental GGA limitation requiring hybrid
> functionals or GW for correct InSb band gap."

## What B05_bands_InSb (Informed) Did Before B06

Before B06 even started, the B agent already struggled on InSb bands:

- **B05 wall time:** 98 minutes (vs A05's 18 minutes — **5.4x slower**)
- **B05 run_calc:** 31 (vs A05's 19 — **63% more**)

The B agent entered B06 with 5 accumulated insights, including two that explicitly
stated InSb has an inverted gap and "requires hybrid functionals or GW."

### Full knowledge DB at B06 entry (5 insights)

1. **InSb lattice constant:** a = 6.637 Å, +2.4% vs experiment (from A relax)
2. **InSb band inversion (A bands):** PBE without SOC: -2.1 eV gap. PBE+SOC: -3.0 eV gap. "Accurate InSb band gap requires HSE06, GW, or mBJ functional."
3. **InSb zero-gap details (A bands):** Gamma_6 sits 0.75 eV below Gamma_8. "This is a fundamental GGA limitation requiring hybrid functionals or GW."
4. **InSb lattice constant (B relax):** a = 6.628 Å, +2.3% vs experiment (from B relax)
5. **InSb PBE gap = zero (B bands):** "PBE fundamentally fails for this narrow-gap semiconductor due to systematic gap underestimation."

Three out of five insights explicitly state that PBE cannot produce the correct
InSb gap and that higher-level methods are required.

## What B06 (Informed) Did — Launch 1

**Start:** 2026-03-02 ~12:02 UTC
**Duration:** ~1h50m before manual kill

The agent created `insb_dos_attempt1` with 165 k-points (tetrahedron method).
The QE SCF and NSCF both completed successfully. However, the MCP `run_calculation`
tool call never returned the result to the agent — the trace file stopped growing at
90 KB (17 tool calls, 1 `run_calculation`).

**Root cause of hang:** MCP stdio transport issue (unrelated to knowledge transfer).
The QE output files all showed "JOB DONE" but the MCP server lost the response.

**Action:** Manually killed. Cleaned session directory, calculation artifacts,
project.qms.yml ULID pointers, and restored local.db from B05 snapshot.

## What B06 (Informed) Did — Launch 2

**Start:** 2026-03-02 16:09:59 UTC
**Duration:** ~1h35m before manual kill

The agent made two attempts:

### Attempt 1: `insb_dos_soc_attempt1`

- **k-points:** 165 (tetrahedron method, SOC)
- **SCF:** 62 KB output, completed normally
- **NSCF:** 6 KB output, completed normally
- **Outcome:** Got zero-gap DOS (as expected). Agent was unsatisfied.

### Attempt 2: `insb_dos_soc_attempt2`

- **k-points:** 868 (Gaussian smearing, σ=0.005 Ry, SOC)
- **SCF:** 62 KB output, completed normally
- **NSCF:** Running... and running... and running

The NSCF step was processing k-points at approximately **10 per hour** with
persistent convergence warnings:

```
c_bands:  6 eigenvalues not converged
c_bands:  3 eigenvalues not converged
c_bands:  2 eigenvalues not converged
c_bands:  8 eigenvalues not converged
```

After 58 minutes of NSCF computation (12 MPI processes at 100% CPU each),
only ~10 of 868 k-points had been processed. Extrapolated completion time:
**~87 hours (~3.6 days).**

For comparison:
- A06's largest NSCF: 256 k-points, completed in under a minute
- B06 attempt 2: 868 k-points with SOC = **3.4x more k-points**, each taking
  **orders of magnitude longer** due to SOC doubling the Hamiltonian size
  (134 Kohn-Sham states vs ~30 without SOC)

**Action:** Manually killed. Session permanently skipped. B_InSb pipeline
snapshot preserved from B05 (5 insights).

## k-mesh Comparison Across All InSb DOS Attempts

| Attempt | Condition | k-points | SOC | Method | Completed | Wall |
|---------|-----------|----------|-----|--------|-----------|------|
| A06 attempt1 | Naive | 145 | No | Gaussian (σ=0.01) | Yes | ~mins |
| A06 attempt2 | Naive | 256 | No | Gaussian (σ=0.005) | Yes | ~mins |
| A06 attempt3 | Naive | 145 | Yes | Gaussian (σ=0.005) | Yes | ~mins |
| B06 launch1 | Informed | 165 | Yes | Tetrahedra | Yes* | ~mins |
| B06 launch2 att1 | Informed | 165 | Yes | Tetrahedra | Yes | ~mins |
| B06 launch2 att2 | Informed | **868** | Yes | Gaussian (σ=0.005) | **No** | est. 87h |

*MCP hung before result returned

## Root Cause Analysis

### Why did the B agent choose 868 k-points?

The agent had three insights explicitly stating that InSb has a zero/inverted gap
with PBE and that "hybrid functionals or GW" are needed. When attempt 1 confirmed
the zero-gap result, the agent could not apply the correct fix (switch to HSE06/GW)
because the experiment constrains it to QE/PBE.

Instead, the agent reasoned that a denser k-mesh might resolve fine gap structure
or a small gap hidden by insufficient sampling. This is physically wrong — the
zero gap is a systematic DFT-PBE error, not a sampling artifact — but the agent
doesn't have the physics intuition to distinguish between "need more k-points"
and "need a different functional."

The 868 k-points likely came from a very dense mesh specification (possibly 16x16x16
or higher on the primitive cell), which is a reasonable choice for well-behaved
semiconductors but catastrophic for SOC calculations on heavy-element compounds.

### Why didn't A06 escalate?

The naive agent had no prior knowledge that the result was wrong. When it got zero
gap on attempt 1, it tried a finer mesh (256 points), confirmed the result, tried
SOC, confirmed again, and reported: "PBE gives zero gap, this is a known DFT
limitation." Total: 3 attempts, all reasonable, 18 minutes.

The naive agent treated "zero gap" as a result to report. The informed agent treated
"zero gap" as a problem to solve.

## The "Awareness Tax" — Generalized Lesson

This incident demonstrates a failure mode of knowledge transfer systems:

**When knowledge describes a problem that cannot be solved within the available
method constraints, the informed agent may spend more effort trying to fix the
unfixable than a naive agent would spend simply observing and reporting it.**

The tax manifests across the entire InSb B pipeline:

| Step | A (Naive) | B (Informed) | Ratio |
|------|-----------|-------------|-------|
| Relax | 5m / 17rc | 11m / 8rc | 2.2x wall, 0.47x run_calc |
| Bands | 18m / 19rc | 98m / 31rc | **5.4x wall**, 1.6x run_calc |
| DOS | 18m / 24rc | **SKIP** (est. 87h) | **>290x wall** (projected) |

The escalation is monotonic: each successive step is worse because the agent
accumulates more evidence that the result is wrong without gaining the ability
to fix it. By the DOS step, the agent is desperate enough to attempt a
brute-force resolution that would take days.

### Conditions for the awareness tax

The tax appears when ALL of these hold:
1. Knowledge correctly identifies a problem (InSb gap is wrong with PBE)
2. Knowledge correctly identifies the solution (need HSE06/GW)
3. The solution is unavailable in the current context (experiment uses PBE only)
4. The agent cannot distinguish "unsolvable within constraints" from "needs more effort"

### Mitigation strategies

For future knowledge DB design:
- Insights about method limitations should include explicit **stop conditions**: "If
  constrained to PBE, accept the zero-gap result and report the known limitation"
- The knowledge system could tag insights with **actionability scores** — an insight
  that identifies a problem but offers no in-scope fix should have a different
  retrieval priority than one that provides a directly applicable solution
- Prompts could include explicit instructions: "If the knowledge DB indicates a
  fundamental method limitation, do not attempt to work around it with parameter
  tuning"

## Impact on Experiment

- B06_dos_InSb is marked as SKIP in the chain log with this explanation
- B_InSb pipeline has 2/3 complete sessions (relax + bands) + 1 skip
- The InSb A/B comparison remains informative for relax and bands steps
- The DOS comparison is lost for InSb but preserved for PbTe, CdTe, and MgO
- This incident itself is a key experimental finding — arguably more valuable
  than a clean B06 completion would have been

## Files and Evidence

- Chain log: `.tmp/task_2_2d/CHAIN_LOG_2_2D.md` (B06 marked as SKIP with note)
- A06 calculations: `.tmp/task_2_2d/A_InSb/project/calculations/insb_dos_attempt{1,2_fine,3_soc}/`
- B05 snapshot: `.tmp/task_2_2d/B_InSb/sessions/B05_bands_InSb/local_db_after_B05_bands_InSb.db`
- B06 skip marker: `.tmp/task_2_2d/B_InSb/sessions/B06_dos_InSb/timing.txt` (exit=-1)
- B_InSb pipeline snapshot: `.tmp/task_2_2d/B_InSb/local_db_after_pipeline.db` (from B05, 5 insights)
- Runner log: `.tmp/task_2_2d/runner_2_2d.log`
- Interim report: `docs/history/reviews/TASK_2_2D_INTERIM_REPORT.md`
