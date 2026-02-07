# LAMMPS Curated Sample Index

**Location**: `tests/inputformat/samples/lammps/`
**Total samples**: 8
**Engine**: LAMMPS (command-stream syntax, F5)

---

## Sample Inventory

| # | Slug | Title | Workflow Tags | Potential | Units | Diversity Rationale |
|---|------|-------|---------------|-----------|-------|---------------------|
| 1 | `melt_lj_nve` | 3D LJ melt NVE | md, nve | LJ pair | lj | Baseline MD: simplest possible LAMMPS run (LJ units, lattice-create, no data file) |
| 2 | `minimize_2d_lj` | 2D LJ melt + minimize | md, minimize, 2d | LJ pair | lj | Multi-phase workflow (run then minimize) + 2D dimensionality |
| 3 | `peptide_nvt` | Peptide NVT with CHARMM | md, nvt, biomolecular | CHARMM bonded | real | Full atom_style with kspace, SHAKE, 4 bonded styles, read_data — biomolecular regime |
| 4 | `reaxff_rdx` | ReaxFF RDX | md, reactive, reaxff | ReaxFF | real | Reactive potential with charge equilibration (qeq/reaxff) — unique chemistry |
| 5 | `eam_hyper` | EAM hyperdynamics | accelerated_dynamics, eam, hyper | EAM/alloy | metal | Accelerated dynamics (hyper/local fix) — unique time-scale method |
| 6 | `coreshell` | Core-shell NaCl | md, coreshell, ionic | Born-Mayer + core-shell | metal | Polarizable model with unfix/multi-run — unique physics (ionic polarization) |
| 7 | `meam_sic` | MEAM SiC NVE | md, nve, meam | MEAM | metal | Many-body angular potential (MEAM library) — unique potential class |
| 8 | `elastic_sw` | Elastic constants SW Si | minimize, elastic, sw | Stillinger-Weber | metal | Property calculation via variables + minimize + unfix cycle — unique analysis workflow |

---

## Diversity Assessment (§1.11)

### Category A Coverage (Workflow Types)
- **Standard MD**: NVE (melt_lj_nve, meam_sic), NVT (peptide_nvt)
- **Minimization**: 2-phase (minimize_2d_lj), property extraction (elastic_sw)
- **Reactive MD**: ReaxFF (reaxff_rdx)
- **Accelerated dynamics**: Hyperdynamics (eam_hyper)
- **Multi-phase**: Run + minimize (minimize_2d_lj), unfix cycle (coreshell, elastic_sw)

### Category B Coverage (Force Field Families)
- **Simple pair**: LJ (2 samples — intentionally: one basic, one multi-phase)
- **Embedded atom**: EAM/alloy (eam_hyper)
- **Many-body**: MEAM (meam_sic), Stillinger-Weber (elastic_sw)
- **Reactive**: ReaxFF (reaxff_rdx)
- **Biomolecular**: CHARMM bonded + kspace (peptide_nvt)
- **Ionic/polarizable**: Born-Mayer + core-shell (coreshell)

### Category C Coverage (Syntax Features)
- **Lattice-create** (no data file): melt_lj_nve, minimize_2d_lj
- **read_data**: peptide_nvt, meam_sic
- **Variables**: reaxff_rdx, eam_hyper, elastic_sw
- **Line continuation (&)**: reaxff_rdx, eam_hyper
- **unfix/multi-run**: coreshell, elastic_sw
- **kspace_style**: peptide_nvt, coreshell
- **fix_modify**: coreshell
- **2D dimension**: minimize_2d_lj

### Near-Duplicate Check (§1.11 D1)
- Two LJ samples exist but serve different purposes: `melt_lj_nve` (baseline NVE) vs `minimize_2d_lj` (multi-phase + 2D). No near-duplicates.

### Composite Pipeline (§1.12)
LAMMPS is typically a downstream consumer of DFT force fields. No standard composite pipeline in the §1.12 W4 list. No composite sample required.

---

## Provenance

All samples are simplified and anonymized from LAMMPS bundled examples (v22 Jul 2025 Update 3). Each `in.lammps` was manually curated to demonstrate specific features while remaining parseable and fast-running.

Source: `$(brew --prefix)/Cellar/lammps/20250722-update3/share/lammps/examples/`
