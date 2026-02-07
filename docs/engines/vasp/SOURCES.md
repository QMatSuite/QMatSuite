# VASP Documentation Sources

## Phase B1 Research Sources

- **Date**: 2026-02-05
- **Phase**: B1 (VASP End-to-End "QE-Depth")

## Primary References

| Source | URL / Location | Used For |
|--------|---------------|----------|
| VASP Wiki (INCAR tags) | https://www.vasp.at/wiki/index.php/Category:INCAR_tag | INCAR metadata catalog (232 tags) |
| VASP Wiki (input files) | https://www.vasp.at/wiki/index.php/The_VASP_Manual | POSCAR/KPOINTS format specs |
| VASP Wiki (vasprun.xml) | https://www.vasp.at/wiki/index.php/Vasprun.xml | Output parser XPath design |
| VASP Wiki (OUTCAR) | https://www.vasp.at/wiki/index.php/OUTCAR | OUTCAR regex fallback patterns |
| VASP 6.5.0 installation | `.qmatsuite/engines/vasp/vasp.6.5.0/` | Binary verification, testsuite reference data |
| VASP POTCAR library | `.qmatsuite/engines/vasp/potpaw_PBE.64/` | POTCAR staging validation |
| QE metadata pattern | `drivers/qe/data/qe_metadata.py` | Architecture reference for metadata access layer |
| QE output parser | `drivers/qe/parsers/trajectory.py` | Architecture reference for output parser |

## INCAR Tag Categories Researched

- electronic (~50 tags): ENCUT, PREC, EDIFF, NELM, ISMEAR, SIGMA, ALGO, etc.
- ionic (~25 tags): NSW, IBRION, ISIF, EDIFFG, POTIM, TEBEG, etc.
- output (~15 tags): NWRITE, LELF, LVTOT, LVHAR, LAECHG, etc.
- xc (~15 tags): GGA, METAGGA, LDAU, LDATYPE, LDAUL, LDAUU, LDAUJ, etc.
- magnetism (~10 tags): MAGMOM, SAXIS, LNONCOLLINEAR, LSORBIT, etc.
- parallelization (~8 tags): KPAR, NPAR, NCORE, NSIM, etc.
- hybrid (~10 tags): LHFCALC, HFSCREEN, AEXX, PRECFOCK, etc.
- vdw (~10 tags): IVDW, VDW_S6, VDW_S8, LUSE_VDW, etc.
- response (~10 tags): LEPSILON, LOPTICS, CSHIFT, etc.
- gw (~15 tags): NOMEGA, ENCUTGW, NBANDSGW, etc.
- wannier (~7 tags): LUSEW, LWANNIER90_RUN, LWRITE_MMN_AMN, NUM_WANN, etc.
- symmetry, ml: remaining tags

## 13 Curated Input Cases

Each case was authored by referencing VASP Wiki examples and standard
computational materials science workflows:

| Case | Workflow | Species | Reference |
|------|----------|---------|-----------|
| si_scf | SCF | Si | Standard PBE Si diamond |
| si_relax | Relaxation | Si | IBRION=2 CG |
| si_vc_relax | VC-relax | Si | ISIF=3 |
| si_bands | Band structure | Si | ICHARG=11, line-mode KPOINTS |
| si_dos | DOS | Si | ISMEAR=-5, NEDOS=2001 |
| fe_magnetic | Spin-polarised | Fe | ISPIN=2, MAGMOM |
| tio2_hubbard | DFT+U | Ti, O | LDAU, LDATYPE=2 |
| graphene_vdw | DFT-D3 | C | IVDW=12 |
| al_md | MD | Al | IBRION=0, TEBEG=300 |
| mgo_slab | Slab+dipole | Mg, O | IDIPOL=3, LDIPOL |
| si_hybrid | HSE06 | Si | LHFCALC, HFSCREEN=0.2 |
| gaas_soc | SOC | Ga, As | LSORBIT, LNONCOLLINEAR |
| si_w90_pipeline | VASP+W90 | Si | LWANNIER90_RUN, composite pipeline |
