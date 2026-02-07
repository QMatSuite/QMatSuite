# VASP Curated Sample Index

**Engine**: VASP 6.5.0
**Location**: `tests/inputformat/samples/vasp/`
**Total cases**: 13

---

## Case Inventory

### 1. si_scf

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond SCF |
| **Species** | Si |
| **Workflow tags** | scf, electronic |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki standard Si diamond example |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Baseline PBE SCF — minimal reference for parser/writer validation |
| **Real run slug** | `si_scf` |

### 2. si_relax

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond ionic relaxation |
| **Species** | Si |
| **Workflow tags** | relax, ionic |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki IBRION=2 example |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Ionic relaxation (IBRION=2, ISIF=2) — geometry optimization |
| **Real run slug** | `si_relax` |

### 3. si_vc_relax

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond variable-cell relaxation |
| **Species** | Si |
| **Workflow tags** | vc-relax, ionic, cell |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki ISIF=3 example |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Variable-cell relaxation (ISIF=3) — cell shape + volume optimization |
| **Real run slug** | `si_vc_relax` |

### 4. si_bands

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond band structure |
| **Species** | Si |
| **Workflow tags** | bands, nscf |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki band structure tutorial |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Band structure (ICHARG=11, line-mode KPOINTS) — non-SCF dependent workflow |
| **Real run slug** | `si_bands` |

### 5. si_dos

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond density of states |
| **Species** | Si |
| **Workflow tags** | dos, nscf |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki DOS tutorial |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Density of states (ISMEAR=-5, NEDOS) — tetrahedron method, ICHARG=11 dependency |
| **Real run slug** | `si_dos` |

### 6. fe_magnetic

| Field | Value |
|-------|-------|
| **Title** | Iron BCC spin-polarised SCF |
| **Species** | Fe |
| **Workflow tags** | scf, magnetic, spin |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki magnetism example |
| **Diversity category** | B (physics) |
| **Diversity rationale** | Spin-polarized magnetism (ISPIN=2, MAGMOM) — collinear spin, transition metal |
| **Real run slug** | `fe_magnetic` |

### 7. tio2_hubbard

| Field | Value |
|-------|-------|
| **Title** | TiO2 rutile DFT+U |
| **Species** | Ti, O |
| **Workflow tags** | scf, hubbard, dft_plus_u |
| **Functional** | PBE+U |
| **Provenance** | Authored from VASP Wiki DFT+U tutorial |
| **Diversity category** | B (physics) |
| **Diversity rationale** | DFT+U (LDAU arrays) — strong correlation, multi-species, array-valued INCAR tags |
| **Real run slug** | `tio2_hubbard` |

### 8. graphene_vdw

| Field | Value |
|-------|-------|
| **Title** | Graphene with DFT-D3(BJ) vdW correction |
| **Species** | C |
| **Workflow tags** | scf, vdw |
| **Functional** | PBE-D3 |
| **Provenance** | Authored from VASP Wiki van der Waals tutorial |
| **Diversity category** | B (physics) |
| **Diversity rationale** | van der Waals (IVDW=12) — dispersion, 2D material with vacuum |
| **Real run slug** | `graphene_vdw` |

### 9. al_md

| Field | Value |
|-------|-------|
| **Title** | Aluminium FCC molecular dynamics |
| **Species** | Al |
| **Workflow tags** | md, ionic |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki MD tutorial |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Molecular dynamics (IBRION=0, NVT) — ensemble, metallic smearing |
| **Real run slug** | `al_md` |

### 10. mgo_slab

| Field | Value |
|-------|-------|
| **Title** | MgO(001) slab with dipole correction |
| **Species** | Mg, O |
| **Workflow tags** | scf, slab, dipole |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki slab tutorial |
| **Diversity category** | B (physics) |
| **Diversity rationale** | Slab + dipole correction (IDIPOL=3) — surface science, asymmetric cell |
| **Real run slug** | `mgo_slab` |

### 11. si_hybrid

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond HSE06 hybrid functional |
| **Species** | Si |
| **Workflow tags** | scf, hybrid, hse |
| **Functional** | HSE06 |
| **Provenance** | Authored from VASP Wiki hybrid functional tutorial |
| **Diversity category** | B (physics) |
| **Diversity rationale** | HSE06 hybrid (LHFCALC, HFSCREEN) — exact exchange, specialized algorithm |
| **Real run slug** | `si_hybrid` |

### 12. gaas_soc

| Field | Value |
|-------|-------|
| **Title** | GaAs zinc-blende spin-orbit coupling |
| **Species** | Ga, As |
| **Workflow tags** | scf, soc, noncollinear |
| **Functional** | PBE |
| **Provenance** | Authored from VASP Wiki SOC example |
| **Diversity category** | B (physics) |
| **Diversity rationale** | Spin-orbit coupling (LSORBIT, LNONCOLLINEAR) — requires vasp_ncl, relativistic |
| **Real run slug** | `gaas_soc` |

### 13. si_w90_pipeline

| Field | Value |
|-------|-------|
| **Title** | Silicon diamond VASP+Wannier90 composite pipeline |
| **Species** | Si |
| **Workflow tags** | scf, wannier, composite_pipeline |
| **Functional** | PBE |
| **Provenance** | Adapted from VASP 6.5.0 testsuite `mlwf_mos2_wannier90/` for Si diamond |
| **Diversity category** | A (workflow) |
| **Diversity rationale** | Composite VASP->W90 pipeline (LWANNIER90_RUN) — multi-engine workflow |
| **Real run slug** | `si_w90_pipeline` (partial: step 1 OK, step 2 needs W90-linked binary) |

---

## Diversity Coverage Summary

| Category | Count | Cases |
|----------|-------|-------|
| A (workflow) | 7 | si_scf, si_relax, si_vc_relax, si_bands, si_dos, al_md, si_w90_pipeline |
| B (physics) | 6 | fe_magnetic, tio2_hubbard, graphene_vdw, mgo_slab, si_hybrid, gaas_soc |

**Species coverage**: Si, Fe, Ti, O, C, Al, Mg, Ga, As (9 elements)
**Functional coverage**: PBE, PBE+U, PBE-D3, HSE06 (4 functionals)
**Binary coverage**: vasp_std (12 cases), vasp_ncl (1 case: gaas_soc)
