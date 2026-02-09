# Multi-Engine Bands/DOS Analysis Expansion — Acceptance

## Summary

Wired bands + DOS analysis providers for 6 engines (QE, VASP, ABINIT, Siesta, CP2K, GPAW). Before this work, only VASP had complete bands+DOS and QE had bands-only. Now all 6 periodic-capable engines have both.

## Final Test Results

```
4745 passed, 0 failed, 20 skipped (3:49)
```

Baseline was 4647 passed. Delta: **+98 tests** (81 provider tests + 18 gate tests - 1 skip delta).

## Engine×Object Matrix (CLOSED)

| Engine | bands | dos | PDOS | Source |
|--------|-------|-----|------|--------|
| **VASP** | done (prior) | done (prior) | done (prior) | EIGENVAL, DOSCAR, PROCAR |
| **QE** | done (prior) | **NEW** | **NEW** | *.dos.dat, *.pdos_atm* |
| **ABINIT** | **NEW** | **NEW** | defer | *_EIG, *_DOS |
| **Siesta** | **NEW** | **NEW** | **NEW** | *.EIG, *.DOS, *.PDOS.xml |
| **CP2K** | **NEW** | **NEW** | **NEW** | *.bs, *.pdos |
| **GPAW** | **NEW** | **NEW** | defer | bandstructure.json, dos.json |

Not applicable (molecular/classical/QMC): ORCA, Gaussian, Psi4, PySCF, xTB, LAMMPS, QMCPACK, Wannier90, Yambo.

## Files Created

### Providers (9 files)
| File | Engine | Type |
|------|--------|------|
| `src/quantumvitas/drivers/qe/parsers/dos.py` | QE | DOS+PDOS |
| `src/quantumvitas/drivers/abinit/parsers/bands.py` | ABINIT | Bands |
| `src/quantumvitas/drivers/abinit/parsers/dos.py` | ABINIT | DOS |
| `src/quantumvitas/drivers/siesta/parsers/bands.py` | Siesta | Bands |
| `src/quantumvitas/drivers/siesta/parsers/dos.py` | Siesta | DOS+PDOS |
| `src/quantumvitas/drivers/cp2k/parsers/bands.py` | CP2K | Bands |
| `src/quantumvitas/drivers/cp2k/parsers/dos.py` | CP2K | DOS+PDOS |
| `src/quantumvitas/drivers/gpaw/parsers/bands.py` | GPAW | Bands |
| `src/quantumvitas/drivers/gpaw/parsers/dos.py` | GPAW | DOS |

### Fixtures (9 directories, all from real engine runs)
| Directory | Engine | Files |
|-----------|--------|-------|
| `tests/data/analysis_qe_dos/` | QE | si.dos.dat |
| `tests/data/analysis_abinit_bands/` | ABINIT | si_bands_fixedo_DS2_EIG, si_bands.abo |
| `tests/data/analysis_abinit_dos/` | ABINIT | si_doso_DS2_DOS, si_dos.abo, si_dos.abi |
| `tests/data/analysis_siesta_bands/` | Siesta | si_bands.EIG, si_bands.out |
| `tests/data/analysis_siesta_dos/` | Siesta | si_dos.DOS, si_dos.PDOS.xml, si_dos.out |
| `tests/data/analysis_cp2k_bands/` | CP2K | si_bands.bs, si_bands.out |
| `tests/data/analysis_cp2k_dos/` | CP2K | si_dos-k1-1.pdos, si_dos.out |
| `tests/data/analysis_gpaw_bands/` | GPAW | bandstructure.json |
| `tests/data/analysis_gpaw_dos/` | GPAW | dos.json |

### Tests (9 files, 81 tests — by Cursor Auto)
| File | Tests |
|------|-------|
| `tests/drivers/qe/test_qe_dos_parser.py` | 8 |
| `tests/drivers/abinit/test_abinit_bands_parser.py` | 9 |
| `tests/drivers/abinit/test_abinit_dos_parser.py` | 8 |
| `tests/drivers/siesta/test_siesta_bands_parser.py` | 8 |
| `tests/drivers/siesta/test_siesta_dos_parser.py` | 10 |
| `tests/drivers/cp2k/test_cp2k_bands_parser.py` | 10 |
| `tests/drivers/cp2k/test_cp2k_dos_parser.py` | 9 |
| `tests/drivers/gpaw/test_gpaw_bands_parser.py` | 10 |
| `tests/drivers/gpaw/test_gpaw_dos_parser.py` | 9 |

### Gate Tests (18 parametrized tests)
| Test | Params |
|------|--------|
| `test_bands_dos_parser_matrix` | 12 (6 engines × 2 types) |
| `test_bands_dos_engine_has_analysis_capabilities` | 6 (one per engine) |

### Files Edited
| File | Change |
|------|--------|
| `drivers/qe/driver.py` | Added DOS AnalysisCapability |
| `drivers/qe/parsers/__init__.py` | Added QEDOSProvider import |
| `drivers/abinit/driver.py` | Added ANALYSIS_CAPABILITIES (bands+dos) |
| `drivers/abinit/parsers/__init__.py` | Added bands+dos imports |
| `drivers/siesta/driver.py` | Added ANALYSIS_CAPABILITIES (bands+dos) |
| `drivers/siesta/parsers/__init__.py` | Added bands+dos imports |
| `drivers/cp2k/driver.py` | Added ANALYSIS_CAPABILITIES (bands+dos) |
| `drivers/cp2k/parsers/__init__.py` | Added bands+dos imports |
| `drivers/gpaw/driver.py` | Added ANALYSIS_CAPABILITIES (bands+dos) |
| `drivers/gpaw/__init__.py` | Added `from . import parsers` for registration |
| `drivers/gpaw/parsers/__init__.py` | Created (bands+dos imports) |
| `tests/gates/test_analysis_invariants.py` | Added 18 matrix gate tests |

## Key Design Decisions

1. **All fixtures from real engine runs** — no synthetic data. ABINIT/Siesta/CP2K/GPAW all executed on this machine.
2. **Reused existing low-level parsers** where available: QE's `parse_dos_data()`, Siesta's `parse_eig_file()`/`parse_dos_file()`/`parse_pdos_xml()`.
3. **Unit conversions**: ABINIT (Ha→eV), CP2K PDOS (a.u.→eV). GPAW/Siesta/CP2K-bands already in eV.
4. **PDOS where format supports it**: QE (projwfc.x), Siesta (PDOS.xml), CP2K (per-kind PDOS files).
5. **High-symmetry points**: GPAW (from ASE labelseq), CP2K (from .bs set headers), Siesta (from BandLines in .out).
6. **CP2K PDOS limitation**: PDOS not implemented for k-points in CP2K — fixture uses Gamma-only, giving discrete eigenvalues (not smoothed DOS grid).

## Verification

```bash
# Parser registration matrix
python -c "
from quantumvitas.parsers.registry import _PARSERS
import quantumvitas.drivers
for e in ['qe','vasp','abinit','siesta','cp2k','gpaw']:
    for t in ['bands','dos']:
        p = _PARSERS.get((e,t))
        print(f'  {e}/{t}: {p.__name__ if p else \"MISSING\"}')"

# Capability declarations
python -c "
from quantumvitas.core.driver_registry import DriverRegistry
import quantumvitas.drivers
for e in ['qe','vasp','abinit','siesta','cp2k','gpaw']:
    d = DriverRegistry.get_driver(e)
    caps = [c.object_type for c in getattr(d,'ANALYSIS_CAPABILITIES',[])]
    print(f'  {e}: {caps}')"
```
