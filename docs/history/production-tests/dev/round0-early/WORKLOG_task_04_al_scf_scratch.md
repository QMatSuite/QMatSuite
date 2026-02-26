# Task 04: Aluminum FCC SCF Calculation — WORKLOG

## Task
Calculate the total energy of aluminum (FCC structure) using Quantum ESPRESSO with a high-quality preset if available.

## Date
2026-02-21

---

## Step 1: Initialize
- Pinged MCP server: OK (version 0.1.0)
- Working directory: task_04_al_scf_scratch (empty)
- Project loaded: <REPO_ROOT> ("Al SCF Scratch")
- Existing structures: only Si2 (not Al)
- Demo search for "aluminum FCC SCF" in QE: no results
- Available QE SCF preset dimensions:
  - precision: LOW / MED / HIGH(chosen)
  - convergence: FAST / NORMAL / ROBUST(chosen)
  - magnetism: NM(chosen) / COL / NC / SOC
  - occupations_scheme: FIXED / TETRAHEDRA / SMEARING_GAUSSIAN(chosen — Al is a metal)
- Decision: use HIGH precision + ROBUST convergence + NM + SMEARING_GAUSSIAN

## Step 2: Import FCC Al structure
- CIF format failed ("Invalid CIF file with no structures!") — switched to POSCAR
- POSCAR import succeeded: Al4, Fm-3m, a=4.046 Å, volume=66.23 Å³
- Structure ULID: 01KJ0C9J55BXKXS6X7MGHXQ3Q9

## Step 3: Create QE SCF calculation
- create_calculation(engine='qe', workflow='scf', structure='Al_fcc', name='Al_fcc_scf_high')
- Calc ULID: 01KJ0C9RNNXHD0H27J5R7Z2HBF
- Species map auto-resolved (Al.UPF from installed library)
- Available pseudo libraries for Al: GBRV, GIPAW, HGH, PseudoDojo, SCAN_TM, SG15, SSSP-efficiency

## Step 4: Apply presets
- Applied: precision=HIGH, convergence=ROBUST, magnetism=NM, occupations_scheme=SMEARING_GAUSSIAN
- Updated fields: ecutwfc=60 Ry, ecutrho=480 Ry, K_POINTS=11×11×11, conv_thr=1e-10,
  mixing_beta=0.2, electron_maxstep=200, mixing_mode=TF, degauss=0.03, smearing=gaussian

## Step 5: Dry-run inspection (preflight)
- Input file preview: scf.in
  - SYSTEM: ecutwfc=60, ecutrho=480, occupations='smearing', smearing='gaussian', degauss=0.03
  - ELECTRONS: conv_thr=1e-10, diagonalization='rmm-davidson'
  - ATOMIC_POSITIONS: 4 Al atoms at FCC conventional positions
  - K_POINTS: 11 11 11  0 0 0
- All pseudopotentials resolved. Ready to run.

## Step 6: Run calculation
- Calling run_calculation(calc_ulid='01KJ0C9RNNXHD0H27J5R7Z2HBF')
- (Running...)


