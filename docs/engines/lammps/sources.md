# LAMMPS Research Sources

**Version**: 1.0.0  
**Date**: 2026-01-19  
**Status**: Research & Design Phase

---

## 1. Official LAMMPS Documentation

### 1.1 Core Manual Pages

| Topic | URL | Notes |
|-------|-----|-------|
| **Commands Structure** | https://docs.lammps.org/Commands_structure.html | Input script organization |
| **Input Commands List** | https://docs.lammps.org/Commands_all.html | Complete command reference |
| **Units** | https://docs.lammps.org/units.html | Unit systems (metal, real, lj, etc.) |
| **Atom Style** | https://docs.lammps.org/atom_style.html | Per-atom properties |
| **Boundary** | https://docs.lammps.org/boundary.html | Periodic/fixed/shrink-wrap |

### 1.2 Structure & Data

| Topic | URL | Notes |
|-------|-----|-------|
| **read_data** | https://docs.lammps.org/read_data.html | Data file format specification |
| **read_restart** | https://docs.lammps.org/read_restart.html | Restart file usage |
| **write_data** | https://docs.lammps.org/write_data.html | Output structure files |
| **restart** | https://docs.lammps.org/restart.html | Checkpoint file writing |

### 1.3 Force Fields

| Topic | URL | Notes |
|-------|-----|-------|
| **pair_style** | https://docs.lammps.org/pair_style.html | Force field types overview |
| **pair_style eam** | https://docs.lammps.org/pair_eam.html | EAM metal potentials |
| **pair_style tersoff** | https://docs.lammps.org/pair_tersoff.html | Tersoff potentials |
| **pair_style reaxff** | https://docs.lammps.org/pair_reaxff.html | Reactive force fields |
| **pair_style lj/cut** | https://docs.lammps.org/pair_lj.html | Lennard-Jones potentials |
| **kspace_style** | https://docs.lammps.org/kspace_style.html | Long-range electrostatics |

### 1.4 Dynamics & Thermostats

| Topic | URL | Notes |
|-------|-----|-------|
| **fix nve** | https://docs.lammps.org/fix_nve.html | Microcanonical dynamics |
| **fix nvt/npt/nph** | https://docs.lammps.org/fix_nh.html | Nose-Hoover thermostats |
| **fix langevin** | https://docs.lammps.org/fix_langevin.html | Langevin thermostat |
| **minimize** | https://docs.lammps.org/minimize.html | Energy minimization |

### 1.5 Output

| Topic | URL | Notes |
|-------|-----|-------|
| **thermo** | https://docs.lammps.org/thermo.html | Thermo output frequency |
| **thermo_style** | https://docs.lammps.org/thermo_style.html | Thermo output format |
| **dump** | https://docs.lammps.org/dump.html | Trajectory output |
| **dump_modify** | https://docs.lammps.org/dump_modify.html | Dump file options |

### 1.6 Build & Installation

| Topic | URL | Notes |
|-------|-----|-------|
| **Install Overview** | https://docs.lammps.org/Install.html | Installation options |
| **Install macOS** | https://docs.lammps.org/Install_mac.html | Homebrew/MacPorts |
| **Install Conda** | https://docs.lammps.org/Install_conda.html | Conda packages |
| **Build Extras** | https://docs.lammps.org/Build_extras.html | Optional packages |
| **Speed Packages** | https://docs.lammps.org/Speed_packages.html | Acceleration options |
| **Kokkos** | https://docs.lammps.org/Speed_kokkos.html | Kokkos portability layer |

---

## 2. Tutorials & Examples

### 2.1 Official Tutorials

| Tutorial | URL | Coverage |
|----------|-----|----------|
| **LAMMPS Tutorials** | https://lammpstutorials.github.io/ | Comprehensive tutorial series |
| **Level 1: LJ Fluid** | https://lammpstutorials.github.io/sphinx/build/html/tutorial1/lennard-jones-fluid.html | Basic MD |
| **Level 2: Carbon Nanotube** | https://lammpstutorials.github.io/sphinx/build/html/tutorial2/carbon-nanotube.html | Tersoff potentials |
| **Level 3: Water** | https://lammpstutorials.github.io/sphinx/build/html/tutorial3/spc-e-water.html | Charged systems |

### 2.2 Official Examples

| Example Set | Location | Notes |
|-------------|----------|-------|
| **Benchmark Inputs** | `share/lammps/bench/` | Performance testing |
| **in.lj** | `share/lammps/bench/in.lj` | LJ fluid benchmark |
| **Examples Directory** | `share/lammps/examples/` | Varied examples |
| **Potentials Library** | `share/lammps/potentials/` | Built-in potential files |

---

## 3. Potential Repositories

### 3.1 NIST Interatomic Potentials Repository

| Resource | URL | Content |
|----------|-----|---------|
| **Main Site** | https://www.ctcms.nist.gov/potentials/ | Potential database |
| **EAM Potentials** | https://www.ctcms.nist.gov/potentials/eam.html | Metal potentials |
| **Search Interface** | https://www.ctcms.nist.gov/potentials/Search/ | Find potentials by element |

### 3.2 OpenKIM

| Resource | URL | Notes |
|----------|-----|-------|
| **Main Site** | https://openkim.org/ | Standardized potential testing |
| **KIM Models** | https://openkim.org/browse/models | Downloadable models |
| **KIM API** | https://docs.lammps.org/kim_commands.html | LAMMPS KIM integration |

---

## 4. File Format References

### 4.1 LAMMPS Data File Format

**Source**: https://docs.lammps.org/read_data.html

Key sections:
- Header (counts, box bounds)
- Masses
- Atoms (position, type, optional: charge, molecule-id)
- Bonds, Angles, Dihedrals, Impropers (for molecular systems)
- Coefficients (optional)

### 4.2 Dump File Format

**Source**: https://docs.lammps.org/dump.html

Format:
```
ITEM: TIMESTEP
<timestep>
ITEM: NUMBER OF ATOMS
<N>
ITEM: BOX BOUNDS <boundary flags>
<xlo> <xhi>
<ylo> <yhi>
<zlo> <zhi>
ITEM: ATOMS <column names>
<atom data rows>
```

### 4.3 Restart File Format

**Source**: https://docs.lammps.org/restart.html

- Binary format (platform-dependent)
- Contains: box, positions, velocities, atom types
- Does NOT contain: pair_style, fix definitions, compute definitions

---

## 5. Related Tools

### 5.1 Visualization

| Tool | URL | Notes |
|------|-----|-------|
| **OVITO** | https://www.ovito.org/ | Dump file visualization |
| **VMD** | https://www.ks.uiuc.edu/Research/vmd/ | Molecular visualization |
| **ASE** | https://wiki.fysik.dtu.dk/ase/ | Python structure manipulation |

### 5.2 Python Interfaces

| Package | URL | Purpose |
|---------|-----|---------|
| **lammps Python** | https://docs.lammps.org/Python_module.html | Direct LAMMPS binding |
| **MDAnalysis** | https://www.mdanalysis.org/ | Trajectory analysis |
| **ASE LAMMPS** | https://wiki.fysik.dtu.dk/ase/ase/calculators/lammps.html | ASE calculator |
| **atomman** | https://www.ctcms.nist.gov/potentials/atomman/ | Atomistic manipulation |

---

## 6. Academic References

### 6.1 LAMMPS Citations

**Primary LAMMPS Paper:**
> A. P. Thompson, H. M. Aktulga, R. Berger, et al., "LAMMPS - a flexible simulation tool for particle-based materials modeling at the atomic, meso, and continuum scales," Comp. Phys. Comm. 271, 108171 (2022). https://doi.org/10.1016/j.cpc.2021.108171

**Original LAMMPS Paper:**
> S. Plimpton, "Fast Parallel Algorithms for Short-Range Molecular Dynamics," J. Comp. Phys. 117, 1-19 (1995). https://doi.org/10.1006/jcph.1995.1039

### 6.2 Potential Method References

**EAM:**
> M. S. Daw and M. I. Baskes, "Embedded-atom method: Derivation and application to impurities, surfaces, and other defects in metals," Phys. Rev. B 29, 6443 (1984).

**Tersoff:**
> J. Tersoff, "New empirical approach for the structure and energy of covalent systems," Phys. Rev. B 37, 6991 (1988).

**ReaxFF:**
> A. C. T. van Duin, et al., "ReaxFF: A Reactive Force Field for Hydrocarbons," J. Phys. Chem. A 105, 9396-9409 (2001).

---

## 7. QMatSuite Internal References

### 7.1 Constitution & Specs

| Document | Location | Relevance |
|----------|----------|-----------|
| **Constitution** | `CONSTITUTION_ZH.md` | Core invariants |
| **Trajectory Spec** | `docs/specs/TRAJECTORY_CORE.md` | Output data model |
| **Analysis Framework** | `docs/specs/ANALYSIS_OBJECTS_FRAMEWORK.md` | Analysis object design |

### 7.2 Existing Engine Docs

| Document | Location | Relevance |
|----------|----------|-----------|
| **VASP Goals** | `docs/engines/vasp/02_vasp_goals_and_required_behaviors.md` | GEN→SPEC pattern |
| **VASP Design** | `docs/engines/vasp/03_minimal_generalization_plan.md` | Integration approach |
| **QE Backend Review** | `docs/engines/vasp/01_qe_backend_code_review.md` | Existing patterns |

---

## 8. Version Information

This research was conducted with:
- LAMMPS documentation version: 2 Aug 2023 (stable)
- Web searches performed: January 2026
- QMatSuite codebase: Current main branch

All URLs verified accessible as of 2026-01-19.

