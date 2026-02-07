# B1 Engine Corpus Index (Repo-Level Rollup)

**Purpose**: Central index of all engine corpus, curated samples, and real-run validation evidence.
**Playbook ref**: B1 Engine Playbook v2.2, §1.10 I5

---

## VASP — COMPLIANT

| Item | Status | Location |
|------|--------|----------|
| **Tier** | A | — |
| **SOURCES.md** | Done | `docs/engines/vasp/SOURCES.md` |
| **CURATED_INDEX.md** | Done | `docs/engines/vasp/CURATED_INDEX.md` |
| **CORPUS_INDEX.json** | Done (28 entries) | `.tmp/engine_research/vasp/CORPUS_INDEX.json` |
| **Plan** | Done | `docs/engines/vasp/PHASE_B1_PLAN.md` |
| **Worklog** | Done | `docs/engines/vasp/PHASE_B1_WORKLOG.md` |
| **Binary** | vasp.6.5.0 (std/gam/ncl) | `.qmatsuite/engines/vasp/vasp.6.5.0/bin/` |
| **POTCAR library** | potpaw_PBE.64 | `.qmatsuite/engines/vasp/potpaw_PBE.64/` |
| **Curated samples** | 13 cases | `tests/inputformat/samples/vasp/` |
| **Real-run validation** | 13 cases (V3 layout) | `.tmp/engine_research/vasp/real_run/` |
| **Corpus (.tmp)** | 15 extracted + 15 normalized | `.tmp/engine_research/vasp/` |
| **Metadata catalog** | 238 INCAR tags | `src/quantumvitas/drivers/vasp/data/vasp_incar_tags.json` |
| **Composite pipeline** | si_w90_pipeline (partial) | Step 1 OK; Step 2 needs W90-linked binary |
| **Diversity** | 7 workflow + 6 physics, 9 elements | See CURATED_INDEX.md |

### Curated Samples Summary

| Case | Workflow | Species | Real Run |
|------|----------|---------|----------|
| si_scf | SCF | Si | si_scf |
| si_relax | Relaxation | Si | si_relax |
| si_vc_relax | VC-relax | Si | si_vc_relax |
| si_bands | Band structure | Si | si_bands |
| si_dos | DOS | Si | si_dos |
| fe_magnetic | Spin-polarised | Fe | fe_magnetic |
| tio2_hubbard | DFT+U | Ti, O | tio2_hubbard |
| graphene_vdw | DFT-D3 | C | graphene_vdw |
| al_md | MD | Al | al_md |
| mgo_slab | Slab+dipole | Mg, O | mgo_slab |
| si_hybrid | HSE06 | Si | si_hybrid |
| gaas_soc | SOC | Ga, As | gaas_soc |
| si_w90_pipeline | VASP+W90 | Si | si_w90_pipeline |

---

## ORCA — Pending Remediation

| Item | Status |
|------|--------|
| **Tier** | B1 |
| **Gaps** | CURATED_INDEX.md, CORPUS_INDEX.json format, real-run validation, rollup entry, diversity rationale, composite pipeline |

---

## LAMMPS — Pending Remediation

| Item | Status |
|------|--------|
| **Tier** | B1 |
| **Gaps** | CURATED_INDEX.md, CORPUS_INDEX.json, real-run validation (V3 layout), rollup entry, diversity rationale |

---

## Gaussian — Pending Remediation

| Item | Status |
|------|--------|
| **Tier** | B1 |
| **Gaps** | CURATED_INDEX.md, CORPUS_INDEX.json, real-run validation (V3 layout), rollup entry, diversity rationale, composite pipeline |

---

## Wannier90 — Pending Remediation

| Item | Status |
|------|--------|
| **Tier** | B1 |
| **Gaps** | CURATED_INDEX.md, CORPUS_INDEX.json, real-run validation (V3 layout), rollup entry, diversity rationale |

---

## QMCPACK — Pending Remediation

| Item | Status |
|------|--------|
| **Tier** | B1 |
| **Gaps** | CURATED_INDEX.md, CORPUS_INDEX.json, real-run validation (V3 layout), rollup entry, diversity rationale |

---

## QE — Gold Standard (No B1 Required)

| Item | Status |
|------|--------|
| **Tier** | A |
| **Notes** | Reference implementation. All other engines aspire to QE-level maturity. |

---

## Remaining Engines — Full B1 Required

| Engine | Tier | Status |
|--------|------|--------|
| ABINIT | B0 | Full B1 required |
| CP2K | C | Full B1 required |
| Siesta | B0 | Full B1 required |
| xTB | C | Full B1 required |
| GPAW | B0 | Full B1 required |
| Psi4 | C | Full B1 required |
| PySCF | C | Full B1 required |
| Yambo | B0 | Full B1 required |
