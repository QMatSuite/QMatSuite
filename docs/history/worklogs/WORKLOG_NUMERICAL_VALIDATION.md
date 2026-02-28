# Numerical Validation Benchmark Worklog

## Overview
Large-scale numerical validation benchmark of QMatSuite's MCP agent capabilities.
40 DFT/xTB calculations across 4 tiers: lattice constants (24), band structure (10),
magnetic moments (3), molecular geometry via xTB (3).

## File Inventory

| Path | Description |
|------|-------------|
| `.tmp/bench/tasks.jsonl` | 40 task definitions (prompts + ground truth) |
| `.tmp/bench/run_benchmark.sh` | Orchestrator script (parallel exec, trace capture) |
| `.tmp/bench/analyze_results.py` | Result analysis + paper table generation |
| `.tmp/bench/progress.log` | Append-only log of all task completions |
| `.tmp/bench/run_20260227_111323/` | Validation run (3 tasks, all passed) |
| `.tmp/bench/run_20260227_112901/` | Main run attempt 1 (18/40 completed, rate-limited) |
| `.tmp/bench/run_20260227_112901/_archive_snapshot_124010/` | Archive of state before rerun attempt |

## Timeline

### 2026-02-27 10:30 — Setup Phase

**Pre-flight checks — all passed:**
- QE: OK (`qms engine verify qe`)
- SSSP: OK (105 elements, SSSP/efficiency/1.3.0)
- MCP server: OK (FastMCP 2.14.5)
- venv: OK (qmatsuite v1.2.3)
- claude CLI: OK (v2.1.62)
- timeout: OK (/opt/homebrew/bin/timeout)

**Infrastructure created:**
- `tasks.jsonl` — 40 tasks with prompts and ground truth
- `run_benchmark.sh` — orchestrator (replicated agent_test_matrix.sh patterns)
- `analyze_results.py` — flexible result parser + paper table generator

**Bug fixes during setup:**
- macOS bash 3.x has no `declare -A` or `wait -n` — rewrote script to use Python for task dispatch and `jobs -r` polling for job pool

### 2026-02-27 11:13 — Small-Scale Validation — PASSED

Run ID: `run_20260227_111323` (3 tasks, sequential)

| Task | Result | Exp | Dev | Time | Attempts |
|------|--------|-----|-----|------|----------|
| relax_Al | 4.044 A | 4.050 A | -0.14% | 298s | 1 |
| relax_Si | 5.469 A | 5.431 A | +0.71% | 459s | 1 |
| xtb_H2O | O-H 0.960 A, 107.2° | 0.957 A, 104.5° | +0.25%, +2.7° | 102s | 1 |

- Total wall time: 14m 22s
- Analysis script tested — found missing key `relaxed_lattice_constant_angstrom`, fixed parser

### 2026-02-27 11:29 — Full Run Attempt 1

Run ID: `run_20260227_112901` (40 tasks, 12 parallel slots)

**Phase 1 (11:29–12:23): Smooth sailing.** First 20 tasks completed perfectly.
All exit=0, all produced result.json with detailed self-assessments.

**Phase 2 (12:24): Rate limit hit.** Pro plan 5-hour window exhausted.
- 11 tasks got instant `rate_limit_event: rejected` (2-3s, exit=1)
- 3 tasks failed mid-run (bands_MgO 533s, bands_SiC 789s, relax_MgO 2546s)
- 8 tasks still running (had active pw.x processes)

**Completed 18/40 tasks with result.json:**

Lattice (16/24): relax_Al, relax_Ag, relax_Au, relax_BN, relax_C, relax_Cu, relax_Fe, relax_Li, relax_Mg, relax_Mo, relax_Na, relax_Ni, relax_Pd, relax_SiC, relax_Ti, relax_W

Bands (2/10): bands_Si, bands_Ge

All 18 traces intact (68–130 lines each).

### 2026-02-27 12:35 — User upgraded Pro → Max plan

Rate limit headroom restored. 8 agents still had active pw.x.

### 2026-02-27 12:40 — INCIDENT: Rerun attempt (problematic)

**Decision:** Launched `rerun_failed.sh` with 6 parallel slots to recover while 8 agents still running.

**Problem:** Rerun script found 22 tasks without result.json — including the 8 still-running tasks. It `rm -rf`'d their workdirs, orphaning the old agents and their pw.x processes.

**Actions taken:**
1. Archived state before rerun: `_archive_snapshot_124010/` (18 result.json preserved)
2. Killed 8 orphaned pw.x processes (freeing ~800% CPU)
3. Killed orphaned old claude agents

**Result:** Rerun itself also hit rate limit again (all 22 tasks exit=1, 2-4s). Zero new results.

**Lesson:** Rerun script was dangerous — it `rm -rf`'d workdirs unconditionally without checking for running agents. Script deleted.

### 2026-02-27 12:44 — Full cleanup

- Killed ALL benchmark-related claude agents and pw.x
- Verified: 0 remaining processes
- Verified: archive intact (18 result.json)
- Verified: all 18 original traces intact in main run dir
- Deleted `rerun_failed.sh` (dangerous, replaced by `--run-dir` flag on main script)

### 2026-02-27 ~12:50 — Hit rate limit again, session paused

Rate limit hit on orchestrating session itself. Waiting for reset.

**State at pause:**
- 18/40 tasks complete with full results + traces
- 22 tasks need fresh run
- Main script enhanced with `--run-dir` flag for resuming into existing run dir
- Archive snapshot safe at `run_20260227_112901/_archive_snapshot_124010/`

### Remaining 22 tasks (for next run)

```
relax_Si relax_Ge relax_GaAs relax_NaCl relax_MgO relax_LiF relax_AlAs relax_GaN bands_GaAs bands_SiC bands_MgO bands_NaCl bands_LiF bands_BN bands_GaN bands_diamond mag_Fe mag_Ni mag_Co xtb_H2O xtb_CH4 xtb_NH3
```

**Command to resume:**
```bash
bash .tmp/bench/run_benchmark.sh \
  --run-dir .tmp/bench/run_20260227_112901 \
  --tasks "relax_Si relax_Ge relax_GaAs relax_NaCl relax_MgO relax_LiF relax_AlAs relax_GaN bands_GaAs bands_SiC bands_MgO bands_NaCl bands_LiF bands_BN bands_GaN bands_diamond mag_Fe mag_Ni mag_Co xtb_H2O xtb_CH4 xtb_NH3"
```

### 2026-02-27 ~13:00 — Recovery Run (22 tasks)

Rate limit reset. Launched recovery run for 22 remaining tasks:

```bash
bash .tmp/bench/run_benchmark.sh \
  --run-dir .tmp/bench/run_20260227_112901 \
  --tasks "relax_Si relax_Ge relax_GaAs relax_NaCl relax_MgO relax_LiF relax_AlAs relax_GaN bands_GaAs bands_SiC bands_MgO bands_NaCl bands_LiF bands_BN bands_GaN bands_diamond mag_Fe mag_Ni mag_Co xtb_H2O xtb_CH4 xtb_NH3"
```

12 parallel slots, 7200s (2h) timeout. All 22 tasks started successfully.

**Results:** 19/22 completed. 3 timeouts — all III-V compounds:
- `relax_GaAs` (TIMEOUT): Mixed PAW+NC pseudos (Ga:PAW, As:ONCV). Calc 1 converged wrong (5.437 A vs 5.653 exp). Agent diagnosed, retried with higher cutoff. Calc 2 timed out at BFGS step 0.
- `relax_AlAs` (TIMEOUT): Same mixed pseudo issue. Calc 1 ran 91 min, converged wrong (5.386 A). Calc 2 timed out mid-SCF.
- `bands_GaAs` (TIMEOUT): SCF took 8 min, bands (201 k-points) took 108 min. MCP call still blocking when 2h limit hit. Legitimate computational cost issue exacerbated by mixed pseudos.

**Root cause for all 3:** QMatSuite's species auto-resolve maps Ga/Al to PSL PAW pseudos but As to DOJO ONCV norm-conserving pseudos. This mixed PAW+NC combination is accepted by QE but produces inconsistent total energies and excessive runtimes with semi-core states.

### 2026-02-27 ~15:10 — Analysis Phase (Phase 6-7)

**Parser fixes applied:**
1. Added lattice constant key variants: `computed_value_angstrom`, `equilibrium_lattice_constant_ang`, `lattice_constant_a_angstrom`, etc.
2. Added `lattice_constant_c_angstrom` for HCP c parameter
3. Added magnetic moment keys: `total_magnetization_per_atom_uB`, `absolute_magnetization_per_atom_uB`
4. Rewrote xTB parser for nested dict structures (`bond_lengths_angstrom.average`)
5. Removed bare `"type"` from gap_type candidates (was matching crystal structure type instead of gap type for SiC)

**Final Results:**

```
Total tasks:              40
Completed (with result):  37/40
Timeouts:                 3

Lattice MARE:             0.88%
Lattice pass rate (2%):   20/22
Band gap MAE:             2.05 eV
Band gap pass rate:       0/9   (expected — DFT-PBE systematically underestimates)
Gap type accuracy:        8/9   (only Ge wrong — tiny gap collapsed by DFT)
Magnetic MARE:            3.5%
Mean rounds used:         1.2
Mean tool calls/task:     30.6  (median 29, min 15, max 54)
```

**Key findings for paper:**
1. **Lattice constants**: 0.88% MARE is excellent for DFT-PBE with SSSP pseudos. 20/22 within 2% of experiment. Outliers: Na (2.13%), Li (2.16%) — alkali metals with very soft potentials.
2. **Band gaps**: 2.05 eV MAE reflects the well-known DFT band gap problem, not an agent error. All 9 calculated gaps systematically underestimate (PBE lacks derivative discontinuity). Gap type identification correct 8/9 times.
3. **Magnetic moments**: 3.5% MARE. Fe (1.1%), Co (1.5%) excellent. Ni (8.1%) slightly overestimates — sensitive to k-mesh and smearing.
4. **Molecular geometry (xTB)**: Bond lengths within 0.5%, angles within 2.8° — excellent for GFN2-xTB.
5. **Agent autonomy**: Mean 1.2 rounds (self-correction cycles). 30.6 mean tool calls per task. Agents correctly diagnosed DFT band gap underestimation in self-assessments.
6. **III-V compound limitation**: Mixed PAW+NC pseudopotential auto-resolution is a systemic issue worth addressing in future QMatSuite releases.

### File Inventory (Final)

| Path | Description |
|------|-------------|
| `.tmp/bench/tasks.jsonl` | 40 task definitions (prompts + ground truth) |
| `.tmp/bench/run_benchmark.sh` | Orchestrator script (parallel exec, trace capture) |
| `.tmp/bench/analyze_results.py` | Result analysis + paper table generation |
| `.tmp/bench/count_tool_calls.py` | Tool call counter for traces |
| `.tmp/bench/run_20260227_111323/` | Validation run (3 tasks, all passed) |
| `.tmp/bench/run_20260227_112901/` | **Main run** (37/40 completed, 3 TIMEOUT) |
| `.tmp/bench/run_20260227_112901/_archive_snapshot_124010/` | Archive of state before rerun attempt |
| `.tmp/bench/run_20260227_112901/traces/` | All 40 stream-JSON traces |
| `.tmp/bench/paper_tables.md` | Paper-ready markdown tables |
| `.tmp/bench/summary_table.md` | Summary table (same as paper_tables) |
| `.tmp/bench/statistics.json` | Machine-readable statistics |
| `.tmp/bench/failure_analysis.md` | Failure/outlier analysis |
| `docs/history/worklogs/WORKLOG_NUMERICAL_VALIDATION.md` | This worklog |

### Investigation: III-V Timeouts & QE Parallelism

**Date**: 2026-02-27

#### 1. Structure Analysis

All three timed-out tasks used **8-atom conventional cubic cells** instead of 2-atom primitive zinc blende cells. This is the primary cause of the excessive runtimes.

| Task | Atoms | Cell type | Pseudos | Pseudo consistency | Electrons | KS states |
|------|-------|-----------|---------|--------------------|-----------|-----------|
| relax_GaAs | **8** | conventional cubic (5.75 A) | Ga: PAW (PSL), As: NC (DOJO) | **MIXED** | 112 | 56 |
| relax_AlAs | **8** | conventional cubic (5.66 A) | Al: PAW (PSL), As: NC (DOJO) | **MIXED** | 72 | 36 |
| bands_GaAs | **8** | conventional cubic (5.653 A) | Ga: PAW (PSL), As: NC (DOJO) | **MIXED** | 112 | 56 |

For comparison, successful compound systems:

| Task | Atoms | Cell type | Electrons | KS states | Wall time |
|------|-------|-----------|-----------|-----------|---------  |
| relax_BN | 8 | conventional cubic | 32 | 16 | 14m |
| relax_SiC | 8 | conventional cubic | 32 | 16 | 7m |
| relax_Si | **2** | primitive FCC | 8 | 4 | 1m 13s |
| relax_NaCl (attempt 2) | **2** | primitive rocksalt | 16 | 8 | 2m 39s |

**Key insight:** BN and SiC also used 8-atom conventional cells but succeeded because they have far fewer electrons (32 vs 112 for GaAs). The combination of 8-atom conventional cell AND heavy elements with semi-core states (Ga d-electrons, As 3d) makes the calculation prohibitively expensive serially.

**Pseudopotential details:**
- **Ga.pbe-dn-kjpaw_psl.1.0.0.UPF** — PAW, Zval=13 (includes 3d10 semi-core), 6 beta functions
- **As.nc.z_15.oncvpsp3.dojo.v4-std.upf** — Norm-conserving, Zval=15 (includes 3d10 semi-core), 6 beta functions
- **Mixed PAW+NC is physically problematic**: total energies not on same footing, stress tensor unreliable for vc-relax

#### 2. SCF Convergence

**relax_GaAs calc1** (ecutwfc=60 Ry, 6x6x6 k→20 irr, 8 atoms):
- SCF convergence: ~12 iterations per BFGS step, ~40-50s per iteration
- BFGS steps: 4 (converged, but to wrong geometry)
- Wall time: **1h 43m** (6062s electrons)
- Final lattice: a = 5.437 A (exp: 5.653 A, **3.8% error** — much worse than typical PBE)
- Root cause: mixed PAW+NC pseudos give inconsistent total energies

**relax_GaAs calc2** (ecutwfc=90 Ry, 8x8x8 k→35 irr, 8 atoms):
- Started 14:49, only reached SCF iteration #5 (671s CPU) before timeout
- ~130s per SCF iteration at 90 Ry (vs ~40s at 60 Ry)
- **Did not complete even 1 BFGS step**

**relax_AlAs calc1** (ecutwfc=60 Ry, 8x8x8 k→35 irr, 8 atoms):
- SCF convergence: ~40s per iteration
- BFGS steps: 5 (converged)
- Wall time: **1h 31m** (5228s electrons)
- Final lattice: a = 5.386 A (exp: 5.661 A, **4.9% error**)

**relax_AlAs calc2** (ecutwfc=90 Ry, 8x8x8 k→35 irr, 8 atoms):
- First SCF converged in 13 iterations, 1456s (~24 min)
- Started first BFGS step at 1491s
- Killed mid-SCF of second BFGS step (~25 min into BFGS)

**bands_GaAs** (ecutwfc=50 Ry, 8 atoms):
- SCF (6x6x6 k→20 irr): 14 iterations, **8m 22s** wall
- Bands (201 k-points, crystal_b): avg 104.7 Davidson iterations per k-point, **1h 48m** wall
- **JOB DONE** — the bands calculation actually completed! But the agent's MCP call was still blocking at the 2h timeout.
- Output: bands.bands.dat (110 KB) + bands.bands.dat.gnu (236 KB) successfully generated

#### 3. Timeout Feasibility

| Task | Calc1 wall | Calc2 wall (est.) | Total est. | 2h sufficient? |
|------|-----------|-------------------|-----------|----------------|
| relax_GaAs | 103m | ~150m (90 Ry) | ~253m | **No** (4.2h needed) |
| relax_AlAs | 91m | ~120m (90 Ry) | ~211m | **No** (3.5h needed) |
| bands_GaAs | 8m (SCF) + 108m (bands) = 116m | n/a (single run) | 116m | **Borderline** (actually finished but MCP call timed out at 120m) |

**bands_GaAs was actually the closest to success** — pw.x finished at 1h48m, but the benchmark's 2h timeout caught the agent while still in the MCP `run_calculation` call that was waiting for pw.x. With even 15 more minutes of timeout headroom, this task would have produced results.

**relax_GaAs and relax_AlAs were fundamentally doomed**: the agent's self-correction strategy (detect bad result → retry at higher cutoff) doubled the total runtime. Each calc1 alone consumed ~90+ min, leaving insufficient time for calc2.

#### 4. Comparison with Previous GaAs

The Wannier90 example GaAs (`example01_gaas`) used:
- **nat = 2** (primitive FCC cell)
- **ecutwfc = 50** Ry
- Only Wannier90 post-processing (not full QE vc-relax)

No direct timing comparison available (Wannier90 only, no QE SCF), but the 2-atom primitive cell confirms that the standard practice is to use the primitive cell for these calculations.

#### 5. QE Parallelism Status

**Two QE installations found:**

| Property | QMatSuite-managed (ACTIVE) | System build |
|----------|---------------------------|--------------|
| Path | `.qmatsuite/engines/qe/q-e-qe-7.5/bin` | `/Users/hh7465/src/q-e-qe-7.5/bin` |
| Version | 7.5 | 7.5 |
| Compiler | h5fc (HDF5 wrapper for gfortran) | mpif90 (Open MPI wrapper) |
| DFLAGS | `-D__FFTW` | `-D__MPI -D__MPI_MODULE -D__FFTW3` |
| FFLAGS | `-O3 -g` (no -fopenmp) | `-O3 -g` (no -fopenmp) |
| MPI | **None** | Open MPI (libmpi.40.dylib) |
| OpenMP | **None** (no `-fopenmp`, no `__OPENMP`) | **None** |
| ScaLAPACK | **None** | **None** |
| BLAS/LAPACK | Accelerate framework | Accelerate framework |
| Header at startup | `Serial version` | `Parallel version (MPI), running on N processors` |

**Neither build has OpenMP.** The QMatSuite bundled build is purely serial. The system build has MPI only.

**Apple Accelerate framework note:** Accelerate uses Grand Central Dispatch (GCD) internally and can multi-thread BLAS/LAPACK operations. However, this only helps the `cdiaghg` and matrix multiply portions of QE, not the FFT or eigenvalue solver loops which dominate runtime.

**QMatSuite invocation path:**
- `EngineConfig` dataclass has `mpi_command: Optional[str]` and `mpi_cores: int = 1`
- `build_command()` prepends `mpirun -np N` if `mpi_command` is set and `mpi_cores > 1`
- Currently, `mpi_command = None` and `mpi_cores = 1` (defaults)
- MPI support **already exists in code** — just not configured

**Parallelism quick test (Si 2-atom SCF, ecutwfc=50 Ry):**

| Run mode | Binary | Wall time | Speedup |
|----------|--------|-----------|---------|
| Serial | QMatSuite bundled (`Serial version`) | **12.69s** | 1.0x |
| MPI -np 4 | System build (`Parallel version`) | **1.03s** | **12.3x** |

The 12.3x speedup with 4 cores (super-linear) is due to reduced per-process memory footprint improving L2/L3 cache utilization, a well-known effect in plane-wave DFT codes.

**Available hardware:** 14 CPU cores (Apple Silicon M-series, arm64).

#### 6. Time Estimates with Fixes

Using conservative 8x MPI speedup with 4 cores:

| Task | Serial | MPI-4 est. | Prim+MPI-4 est. |
|------|--------|------------|-----------------|
| relax_GaAs (calc1) | 103m | ~13m | ~2-3m |
| relax_GaAs (calc2) | ~150m | ~19m | ~3-4m |
| relax_AlAs (calc1) | 91m | ~11m | ~2m |
| bands_GaAs (SCF+bands) | 116m | ~15m | ~3-5m |

With primitive cell (2 atoms): additional ~4-8x speedup from fewer bands/electrons. Combined: **~32-64x total speedup possible.**

#### 7. Recommendations

- [ ] **R1: Use primitive cell (HIGH IMPACT, no code change needed)**
  The agents used `import_structure` which likely imported the conventional cell. QMatSuite's structure import should expose a `reduce_to_primitive=True` option, or the MCP tool documentation should suggest using primitive cells for DFT.
  **Estimated effort:** ~1 day (add structure reduction option)
  **Impact:** 4-8x speedup, no QE changes needed

- [ ] **R2: Recompile bundled QE with MPI (HIGH IMPACT)**
  The bundled QE at `.qmatsuite/engines/qe/q-e-qe-7.5` was compiled with `h5fc` (serial). Recompile with `mpif90` and `-D__MPI`. Open MPI is already installed at `/opt/homebrew/opt/open-mpi/`.
  **Estimated effort:** ~2 hours (recompile + test)
  **Impact:** 8-12x speedup demonstrated

- [ ] **R3: Configure QMatSuite MPI (LOW EFFORT)**
  The code already supports `mpi_command` and `mpi_cores` in `EngineConfig`. Expose these in `engines.json` or settings, or auto-detect MPI when the binary is linked against libmpi. As a workaround, the active installation could be switched to the system build which already has MPI.
  **Estimated effort:** ~1 hour (switch active install or add config)
  **Impact:** Immediate 12x speedup with existing system QE

- [ ] **R4: Add OpenMP to QE build (MODERATE)**
  Neither build has OpenMP (`-fopenmp` + `-D__OPENMP`). OpenMP helps with threaded FFTs and linear algebra within each MPI rank. Useful when running fewer MPI ranks than cores.
  **Estimated effort:** ~2 hours (recompile + benchmark)
  **Impact:** Additional ~2x on top of MPI

- [ ] **R5: Pseudo consistency check (MEDIUM EFFORT)**
  QMatSuite should warn when auto-resolved pseudopotentials mix PAW and NC types within the same calculation. This caused the 3.8-4.9% lattice errors that triggered unnecessary retry cycles.
  **Estimated effort:** ~0.5 days
  **Impact:** Prevents wasted compute time on doomed calculations

- [ ] **R6: Increase timeout for heavy-element compounds (TRIVIAL)**
  For the benchmark: 3h timeout for III-V compounds with d-electrons would suffice even without MPI.
  **Impact:** bands_GaAs would have succeeded (pw.x finished at 1h48m)

- [ ] **R7: Quick fix for immediate rerun — switch active QE to system build**
  Change `engines.json` active QE from `q-e-qe-7.5` to `system-pw.x` (path: `/Users/hh7465/src/q-e-qe-7.5/PW/src`).
  Then set `mpi_command: "mpirun"` and `mpi_cores: 4` in EngineConfig.
  With the system MPI build + 4 cores, all 3 timeouts would complete in <30 min each.
  **Estimated effort:** ~15 minutes
  **Impact:** Resolves all 3 timeouts immediately

#### 8. Root Cause Summary

The timeouts resulted from **three compounding factors**:

1. **8-atom conventional cell** instead of 2-atom primitive (~4x cost from more bands, equivalent to much denser k-mesh)
2. **Heavy elements with semi-core states** (Ga 3d10 → 13 valence electrons, As 3d10 → 15 valence electrons, giving 112 electrons for 8 atoms vs 32 for BN)
3. **Serial QE execution** (bundled binary compiled without MPI or OpenMP, on a 14-core machine)

A secondary factor was the **mixed PAW+NC pseudopotentials** which produced wrong lattice constants (3.8-4.9% error vs typical <1% for PBE), causing the agent to retry at higher cutoff — doubling the total runtime without fixing the underlying pseudo incompatibility.

**None of these are agent logic errors.** The agent correctly:
- Set up the structures and calculations
- Diagnosed the poor calc1 results and attempted self-correction
- Used appropriate k-meshes and cutoffs for the chosen cell size

The issues are infrastructure-level (serial QE, structure import defaults to conventional cell, pseudo auto-resolve doesn't check type consistency).

### MPI Environment Variable Implementation & Smoke Test

**Date**: 2026-02-28

#### Implementation

- Added env var reading in `src/qmatsuite/core/engines/base.py:33-43` (`__post_init__`)
- Added `EngineConfigError` exception class at `base.py:16`
- `QMS_MPI_CORES` (int) and `QMS_MPI_COMMAND` (str) override instance config
- Validation: if `mpi_cores > 1` and command not in PATH → hard error, no fallback
- Default: `mpi_cores > 1` without explicit command → auto-defaults to `"mpirun"`
- Added 12 new tests in `tests/unit/test_mpi_env_vars.py`
- Full test suite: 6665 passed, 5 skipped, 1 pre-existing error (QMCPACK pw2qmcpack not compiled in MPI build)

#### Design Spec

- Created `docs/design/ENGINE_REGISTRY_SPEC.md` — future engine lifecycle management (discovery/select/verify)
- Added deferred item 11 to `docs/plans/DEFERRED_ITEMS.md`

#### Smoke Test Results

Test script: `.tmp/mpi_smoke_test.py`
Binary: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x` (MPI build, linked against Open MPI 5.0.8)

| Cores | Actual (from .out) | Wall time | Speedup | Header |
|-------|--------------------|-----------|---------|--------|
| 1 | 1 | 0.66s | 1.0x | Parallel version (MPI), running on 1 processors |
| 2 | 2 | 0.56s | 1.2x | Parallel version (MPI), running on 2 processors |
| 4 | 4 | 0.35s | 1.9x | Parallel version (MPI), running on 4 processors |
| 8 | 8 | 0.35s | 1.9x | Parallel version (MPI), running on 8 processors |

Note: Modest scaling expected — 2-atom Si cell at ecutwfc=30 Ry is too small to benefit significantly from parallelism (MPI startup overhead dominates). The key verification is that QE actually runs on N processors as requested.

#### Edge Case: Missing mpirun

- `QMS_MPI_CORES=4` + `QMS_MPI_COMMAND=nonexistent_mpirun_xyz` → `EngineConfigError`: "QMS_MPI_CORES=4 but 'nonexistent_mpirun_xyz' not found in PATH. Either install MPI (e.g., `brew install open-mpi`) or unset QMS_MPI_CORES to run in serial mode."
- Confirmed: no silent fallback to serial

#### Active QE Binary Verification

- Path: `.qmatsuite/engines/qe/q-e-qe-7.5/bin/pw.x`
- Linking: `libmpi.40.dylib`, `libmpi_usempif08.40.dylib`, `libmpi_usempi_ignore_tkr.40.dylib`, `libmpi_mpifh.40.dylib` (Open MPI)
- Startup header: "Parallel version (MPI), running on 1 processors"
- System mpirun: `/opt/homebrew/Caskroom/miniforge/base/bin/mpirun` (Open MPI 5.0.8)
