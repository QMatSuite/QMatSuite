# Task 2.2: Mixed Pseudo Knowledge Distillation Case Study — Worklog

**Date**: 2026-02-28
**Status**: COMPLETE
**Full report**: `.tmp/pseudo_case_study/CASE_STUDY_REPORT.md`

## Summary

Ran 5 agent sessions (3 shared knowledge + 2 control) testing whether agents transfer knowledge about mixed pseudopotential types through QMatSuite's knowledge store. Each session calculated equilibrium lattice constants for III-V semiconductors (GaAs, AlAs, GaP) using Quantum ESPRESSO with MPI (12 cores).

## Key Results

| Session | Material | a_calc (A) | a_exp (A) | Error | search_knowledge | record_insight | Tool calls |
|---------|----------|-----------|-----------|-------|-----------------|----------------|------------|
| S1 | GaAs | 5.726 | 5.653 | +1.29% | Yes (1x) | Yes (1x) | 29 |
| S2 | AlAs | 5.70 | 5.661 | +0.69% | **No** | Yes (1x) | 54 |
| S3 | GaP | 5.510 | 5.451 | +1.08% | **No** | Yes (1x) | 64 |
| C1 | AlAs | 5.72 | 5.661 | +1.04% | No | Yes (1x) | 65 |
| C2 | GaP | 5.505 | 5.451 | +0.99% | No | Yes (1x) | 26 |

## Primary Finding

**No knowledge transfer occurred.** S2 and S3 never called `search_knowledge`, so the insights recorded by S1 were never accessed. The knowledge system's "write" side works (all agents record insights), but the "read" side is never triggered. The hint "This project has been used for similar calculations before" was insufficient to prompt knowledge retrieval.

## Secondary Findings

1. All 5 sessions used mixed pseudo types (PAW+NC or PAW+USPP) without detecting it
2. Mixed pseudos produced results within normal PBE error (0.7-1.3%), making the issue invisible
3. PseudoDojo contamination: S1 downloaded NC pseudos that propagated to S2/C1 via shared pseudo directory
4. Agent methodology varied significantly (vc-relax vs EOS scan) even with identical prompts
5. MPI confirmed working: all QE runs used "Parallel version (MPI), running on 12 processors"

## Infrastructure

- QE: MPI build at `.qmatsuite/engines/parallel_q_e/q-e-qe-7.5/bin/pw.x`
- MPI: `mpirun -np 12`, env vars `QMS_MPI_COMMAND=mpirun`, `QMS_MPI_CORES=12`
- Knowledge isolation: `QMATSUITE_HOME` env var in control `.mcp.json`
- Total experiment time: ~70 minutes (5 sessions sequential)

## SSSP Pseudo Type Scan (for reference)

III-V elements in SSSP efficiency 1.3.0:
- Ga: PAW (`Ga.pbe-dn-kjpaw_psl.1.0.0.UPF`)
- Al: PAW (`Al.pbe-n-kjpaw_psl.1.0.0.UPF`)
- As: USPP (`As.pbe-n-rrkjus_psl.0.2.UPF`)
- P: USPP (`P.pbe-n-rrkjus_psl.1.0.0.UPF`)
- N: USPP (`N.pbe-n-radius_5.UPF`)
- In: USPP (`In.pbe-dn-rrkjus_psl.0.2.2.UPF`)

All III-V compounds with Ga or Al have mixed PAW+USPP pseudos in SSSP.

---

# Task 2.2b: Long-Chain Knowledge Distillation — Worklog

**Date**: 2026-02-28 / 2026-03-01
**Status**: COMPLETE
**Full report**: `.tmp/pseudo_chain/CHAIN_REPORT.md`
**Data**: `.tmp/pseudo_chain/sessions/` (16 sessions), `.tmp/pseudo_chain/metrics.json`

## Summary

Ran 16 sequential agent sessions (8 compounds x 2 workflows: relax + bands) through a shared project directory with accumulating knowledge. Total wall time ~4h 53m. All sessions used MPI with 12 cores (confirmed via QE output headers).

## Key Discovery: FTS5 Implicit-AND Bug

**search_knowledge was called 10 times across 10 sessions (62.5%), but returned 0 results every time.** The root cause: `_sanitize_fts_query()` in `store.py` joins tokens with spaces, which FTS5 interprets as implicit AND. Multi-word queries like "BN band structure band gap" require ALL tokens in a single document — which never matches.

**Fix**: Change `" ".join(tokens)` to `" OR ".join(tokens)` in `_sanitize_fts_query()`.

## Contrast with Task 2.2 (v1)

| Metric | v1 (5 sessions) | v2b (16 sessions) |
|--------|-----------------|-------------------|
| search_knowledge call rate | 1/5 (20%) | 10/16 (62.5%) |
| search_knowledge hits > 0 | 0 | 0 |
| record_insight call rate | 5/5 (100%) | 16/16 (100%) |
| Root cause of no transfer | Agent didn't call search | FTS5 AND bug |

**v1 conclusion "agents don't use knowledge" was premature.** v2b proves agents DO search (62.5% rate), but the search is broken.

## Results Summary

| # | Session | Wall | Tools | search_k | Insights | Exit |
|---|---------|------|-------|----------|----------|------|
| 01 | relax_GaAs | 18m | 34 | 1 | 1 | 0 |
| 02 | relax_SiC | 4m | 26 | 0 | 2 | 0 |
| 03 | relax_AlAs | 7m | 56 | 0 | 3 | 0 |
| 04 | relax_BN | 3m | 38 | 1 | 4 | 0 |
| 05 | relax_GaP | 8m | 28 | 0 | 6 | 0 |
| 06 | relax_InP | 9m | 29 | 0 | 7 | 0 |
| 07 | relax_AlN | 5m | 39 | 0 | 8 | 0 |
| 08 | relax_InAs | 13m | 30 | 0 | 9 | 0 |
| 09 | bands_GaAs | 35m | 66 | 1 | 10 | 0 |
| 10 | bands_SiC | 5m | 46 | 0 | 11 | 0 |
| 11 | bands_AlAs | 4m | 41 | 0 | 12 | 0 |
| 12 | bands_BN | 7m | 41 | 1 | 13 | 0 |
| 13 | bands_GaP | 14m | 66 | 1 | 14 | 0 |
| 14 | bands_InP | 14m | 38 | 1 | 15 | 0 |
| 15 | bands_AlN | 10m | 39 | 1 | 16 | 0 |
| 16 | bands_InAs | 77m | 54 | 1 | 17 | 0 |

All 16 sessions: exit=0, MPI=12 cores, 17 insights accumulated.

## Notable Observations

1. **AlAs Pulay stress** (session 03): Agent detected ~500 kbar Pulay stress from mixed PAW+NC pseudos, switched to E(V) scan
2. **GaAs bands Davidson failure** (session 09): Mixed pseudos caused Davidson convergence failure, agent switched to CG + consistent NC pseudos (35 min)
3. **InAs zero band gap** (session 16): Agent correctly identified PBE failure, tried SOC as remedy (77 min, longest session)
4. **Mixed pseudo detection**: 4 of 5 mixed compounds detected (80%) — significant improvement over v1 (0%)
5. **Conventional vs primitive cell confusion**: Multiple bands sessions struggled with band folding in 8-atom cells

## Recommendations

1. **R1 (Critical)**: Fix FTS5 query to use OR-join instead of AND-join
2. **R2**: Remove workflow scope filter from search (bands sessions should find relax insights)
3. **R3**: Add ambient knowledge surfacing at create_calculation/run_calculation time
4. **R4**: Re-run experiment after fixing R1 to measure actual knowledge transfer
5. **R5**: Add structured fields (compound, lattice, band_gap) to insight schema
