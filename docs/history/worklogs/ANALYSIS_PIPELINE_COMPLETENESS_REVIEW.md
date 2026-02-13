# Analysis Pipeline Completeness Review

**Date:** 2026-02-10
**Baseline:** 4875 passed, 19 skipped, 0 failures
**Branch:** v2-python

## Executive Summary

The QMatSuite analysis pipeline is production-ready with comprehensive multi-engine coverage. All planned phases from ANALYSIS_PIPELINE_NEXT_PLAN.md are complete. This review documents the full state and identifies remaining gaps.

## Registered Parsers (35 total)

### Solid-State Engines (6 engines)
| Engine | bands | dos | trajectory | convergence | field3d | scf_digest |
|--------|:-----:|:---:|:----------:|:-----------:|:-------:|:----------:|
| QE     | Y (fatbands) | Y (PDOS) | Y (relax+md) | - | - | Y |
| VASP   | Y (fatbands) | Y (PDOS) | Y (relax+md) | Y | Y | Y |
| ABINIT | Y | Y (PDOS) | Y (relax) | - | - | Y |
| Siesta | Y | Y (PDOS) | Y (relax+md) | - | - | Y |
| CP2K   | Y | Y (PDOS) | Y (relax+md) | - | - | Y |
| GPAW   | Y | Y | Y (relax+md) | - | - | - |

### Molecular/Classical Engines
| Engine   | trajectory | scf_digest |
|----------|:----------:|:----------:|
| LAMMPS   | Y (md+minimize) | Y |
| xTB      | Y (relax) | Y |
| ORCA     | Y (relax) | Y |
| Gaussian | Y (relax) | Y |

### Specialized Engines
| Engine  | scf_digest | Notes |
|---------|:----------:|-------|
| W90     | Y | Postprocessing engine |
| QMCPACK | Y | Fixed-nuclei QMC |
| Yambo   | Y | MBPT postprocessing |

### No Parsers (by design)
- Psi4: Python-script engine
- PySCF: Python-script engine

## ANALYSIS_CAPABILITIES Declarations (10 engines)

| Engine | Object Types | Gen Steps |
|--------|-------------|-----------|
| QE | bands, dos, trajectory | bandspw, dos, relax, md |
| VASP | bands, dos, convergence, trajectory, field3d | bandspw, dos, scf/relax/md, relax/md, scf |
| ABINIT | bands, dos, trajectory | nscf, nscf, relax |
| Siesta | bands, dos, trajectory | bands, dos, relax/md |
| CP2K | bands, dos, trajectory | bandspw, dos, relax/md |
| GPAW | bands, dos, trajectory | bandspw, dos, relax/md |
| LAMMPS | trajectory | md, minimize |
| xTB | trajectory | relax |
| ORCA | trajectory | relax |
| Gaussian | trajectory | relax |

## Gate Test Coverage (30 tests in test_analysis_invariants.py)

All 30 gate tests passing. Key enforced invariants:
- Inv-A2: All AnalysisObject classes have meta field
- Inv-A4: Canonical output is deterministic, to_primitives() parameterless
- Inv-A5: Derived never cached
- Inv-A7/A13: Transforms/orchestrator no engine imports or branching
- Inv-A9/A10: No lazy payloads, no disk cache in analysis core
- Inv-A11: CAS content-addressed
- Inv-A12: Frontend API-only
- bands/dos parser matrix: 6 engines x 2 types = 12 cells
- trajectory parser matrix: 10 engines
- ANALYSIS_CAPABILITIES enforcement for bands/dos (6) and trajectory (10)

## Identified Gaps

### Gap 1: Convergence Parsers (Medium Priority)
- **Current:** VASP-only (OSZICAR parser)
- **Missing:** QE, ABINIT, Siesta, CP2K (all have SCF convergence data in output files)
- **Effort:** ~200 lines per engine
- **Value:** High for QE (second-most-used engine), medium for others

### Gap 2: Transform Library (Medium Priority)
- **Current:** DerivedPrimitiveBundle framework exists, no transforms implemented
- **Missing:** MSD (mean square displacement), RDF (radial distribution function), VACF (velocity autocorrelation), diffusion coefficient, frame slicing
- **Effort:** ~100-200 lines per transform
- **Value:** Medium (critical for MD analysis users)

### Gap 3: Field3D for Other Engines (Low Priority)
- **Current:** VASP-only (CHGCAR, LOCPOT, ELFCAR, PARCHG)
- **Missing:** QE (.pp format), ABINIT (netCDF volumetric)
- **Effort:** High (~400 lines per engine + dependencies)
- **Value:** Low (VASP covers most use cases)

### Gap 4: NEB Trajectory Support (Low Priority)
- **Current:** Trajectory model has image_index field but no NEB parsers
- **Missing:** QE neb.x, VASP VTST plugin
- **Effort:** ~200-300 lines per engine
- **Value:** Low (specialist use case)

### Gap 5: Psi4/PySCF Trajectory (Low Priority)
- **Current:** No analysis parsers for Python-script engines
- **Missing:** Molecular optimization trajectory from Psi4/PySCF output
- **Effort:** ~150 lines per engine
- **Value:** Very low (minimal demand)

### Gap 6: Lazy Trajectory Loading (Low Priority)
- **Current:** All frames loaded into memory
- **Missing:** LazyTrajectory for 100k+ frame MD
- **Effort:** Medium (~300 lines)
- **Value:** Low (current approach handles 10k frames)

## Compliance Status

### Analysis Pipeline Playbook: COMPLIANT
- Real fixtures only (no synthesis)
- EvidenceBundle API for all parsers
- Registration chain via @register_parser
- 7-test template for all parsers
- Unit conversion at parse time (eV, Angstrom, GPa)

### Analysis Object Primitives Spec: COMPLIANT
- All 14+ invariants enforced by gate tests
- No TODO/FIXME markers in analysis code

### Trajectory Analysis Design: COMPLIANT
- All 4 phases (QE/ABINIT/CP2K, LAMMPS/Siesta, xTB/GPAW, ORCA/Gaussian) complete
- Frame model (16 fields) handles all engines
- Coordinate convention (Cartesian Angstrom) enforced

## Conclusion

The pipeline is production-ready. Gaps 1-2 (convergence + transforms) are the highest-value next steps. Gaps 3-6 are optional future work with diminishing returns.
