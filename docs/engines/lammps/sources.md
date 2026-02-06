# LAMMPS Corpus Sources

## Crawl Timestamp
2026-02-05

## Source 1: Homebrew LAMMPS Installation (bundled examples + potentials)
- **LAMMPS Version**: 22 Jul 2025 - Update 3
- **Location**: `/opt/homebrew/Cellar/lammps/20250722-update3/share/lammps/`
- **Copied to**: `.tmp/engine_research/lammps/extracted/`
- **Contents**:
  - `bundled_examples/` — 90 example directories, 843 input files (in.*), 3629 total files
  - `bundled_potentials/` — 257 potential files (EAM, MEAM, Tersoff, SW, ReaxFF, etc.)
  - `bundled_benchmarks/` — Standard LAMMPS benchmarks (LJ, EAM, chain, chute, rhodo), 202 files including reference logs
- **Installed Packages**: ASPHERE, BODY, BPM, CLASS2, COLLOID, COLVARS, COMPRESS, CORESHELL, DIELECTRIC, DIFFRACTION, DIPOLE, DPD-BASIC, DPD-MESO, DPD-REACT, DPD-SMOOTH, DRUDE, EFF, ELECTRODE, EXTRA-COMMAND, EXTRA-COMPUTE, EXTRA-DUMP, EXTRA-FIX, EXTRA-MOLECULE, EXTRA-PAIR, FEP, GRANULAR, INTERLAYER, KIM, KSPACE, LEPTON, MACHDYN, MANYBODY, MC, MDI, MEAM, MISC, ML-IAP, ML-POD, ML-SNAP, MOFFF, MOLECULE, OPENMP, OPT, ORIENT, PERI, PHONON, PLUGIN, POEMS, PTM, QEQ, REACTION, REAXFF, REPLICA, RHEO, RIGID, SHOCK, SMTBQ, SPH, SPIN, SRD, TALLY, UEF, VORONOI, YAFF
- **FFT**: FFTW3 with threads
- **Compiler**: Clang C++ Apple LLVM 17.0.0

## Source 2: LAMMPS Official Documentation (docs.lammps.org)
- **URL**: https://docs.lammps.org/
- **Crawled pages**: ~70+ command/concept pages
- **Stored in**: `.tmp/engine_research/lammps/raw_web/`
- **Key areas covered**:
  - All major command docs (pair_style, fix, compute, dump, etc.)
  - How-to guides (thermostat, barostat, restart)
  - Input script structure and processing
  - Pair styles: lj, eam, meam, tersoff, sw, reaxff, buck, morse, born, coul, table, hybrid
  - Fix styles: nve, nvt, npt, langevin, shake, rigid, deform, wall, spring, indent, deposit
  - Compute styles: pe, ke, temp, pressure, rdf, msd
  - Bond/angle/dihedral styles
  - Commands: read_data, read_restart, write_data, write_restart, minimize, run, etc.

## Source 3: LAMMPS Documentation (embedded in Homebrew install)
- **Location**: `/opt/homebrew/Cellar/lammps/20250722-update3/share/lammps/doc/`
- **Not separately copied** (available via Homebrew install)

## Example Categories (from bundled examples)
- **Potentials/force fields**: airebo, amoeba, atm, comb, dreiding, eim, meam, mliap, nb3b, reaxff, snap, streitz, tersoff, threebody, vashishta
- **Physical systems**: ASPHERE, body, bpm, charmmfsw, cmap, colloid, coreshell, crack, dipole, ellipse, granregion, granular, mesh, micelle, peptide, peri, rheo, rigid, srd, voronoi
- **Workflow types**: ELASTIC, ELASTIC_T, DIFFUSE, fire, flow, friction, HEAT, hugoniostat, hyper, indent, KAPPA, min, msst, neb, nemd, prd, shear, tad, VISCOSITY
- **Special features**: balance, controller, deposit, grid, kim, LEPTON, mc, MC-LOOP, mdi, multi, numdiff, obstacle, PACKAGES, pour, python, qeq, QUANTUM, rdf-adf, relres, replicate, rerun, SPIN, steinhardt, stress_vcm, template, tracker, triclinic, ttm, UNITS, wall, yaml
- **Coupling**: COUPLE (LAMMPS-SPPARKS, multiple, plugin, python, simple)
