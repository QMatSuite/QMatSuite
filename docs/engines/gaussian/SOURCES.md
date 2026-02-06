# Gaussian Phase B1 — Sources

## Crawl Timestamp
2026-02-06

## Source 1: Official Gaussian Documentation (gaussian.com)

### Pages Crawled
| URL | Topic | Status |
|-----|-------|--------|
| gaussian.com/input/ | Input file format | OK |
| gaussian.com/route/ | Route section syntax | OK |
| gaussian.com/keywords/ | Complete keyword list | Partial (JS-rendered) |
| gaussian.com/link0/ | Link 0 commands | OK |
| gaussian.com/basissets/ | Basis set specification | OK |
| gaussian.com/opt/ | Geometry optimization | OK |
| gaussian.com/scf/ | SCF convergence | OK |
| gaussian.com/td/ | TDDFT excited states | OK |
| gaussian.com/freq/ | Frequency calculations | OK |
| gaussian.com/scrf/ | Solvation models | OK |
| gaussian.com/dft/ | DFT methods | OK |
| gaussian.com/mp/ | Moller-Plesset methods | OK |
| gaussian.com/irc/ | Intrinsic reaction coordinate | OK |
| gaussian.com/scan/ | PES scan | OK |
| gaussian.com/nmr/ | NMR properties | OK |
| gaussian.com/polar/ | Polarizability | OK |
| gaussian.com/stable/ | Wavefunction stability | OK |
| gaussian.com/geom/ | Geometry options | OK |
| gaussian.com/guess/ | Initial guess control | OK |
| gaussian.com/oniom/ | Multi-layer calculations | OK |
| gaussian.com/gen/ | Custom basis set input | OK |
| gaussian.com/pbc/ | Periodic boundary conditions | OK |
| gaussian.com/capabilities/ | Feature overview | OK |
| gaussian.com/integral/ | Integration grid control | OK |
| gaussian.com/smdtip/ | SMD solvation tips | JS-blocked |
| gaussian.com/pop/ | Population analysis | JS-blocked |
| gaussian.com/qst2/ | QST2 transition states | JS-blocked |
| gaussian.com/counterpoise/ | BSSE counterpoise | (search only) |

### Stored at
`.tmp/engine_research/gaussian/raw_web/`
- 17 markdown files covering all successfully crawled pages

## Source 2: G09 Keyword Reference Mirror (thiele.ruc.dk)

### URL
https://thiele.ruc.dk/~spanget/help/g09/l_keywords09.htm

### Contents
- Complete alphabetical keyword list for Gaussian 09
- 90+ keywords enumerated with links

### Stored at
`.tmp/engine_research/gaussian/raw_web/gaussian_keywords_complete.md`

## Source 3: Gaussian Test Examples (GitHub Gist)

### URL
https://gist.github.com/platinhom/c9a6baee3c611d4b22b84f61368c79e6

### Contents
- 17 representative test examples extracted from G09 test suite
- Covers: SP, Opt, Freq, SCRF, IRC, CIS, CCSD, CASSCF, ONIOM, Counterpoise, Scan, Force, Polarizability, NMR, PBC, composite methods (G1)
- Route lines and feature tags preserved

### Stored at
`.tmp/engine_research/gaussian/raw_web/gaussian_test_examples.md`

## Source 4: Community Tutorials

### URLs Consulted
- emleddin.github.io/comp-chem-website/Otherguide-gaussian-input.html (water opt+freq example)
- www.cup.uni-muenchen.de/ch/compchem/basic/g03input.html (Link1 examples, Z-matrix)
- joaquinbarroso.com/2013/11/27/qst2-qst3/ (QST2/QST3 TS search)

### Contents
- Input file format explanations and examples
- Link1 multi-job syntax with Z-matrix
- Transition state search examples

## Source 5: Pre-existing QMatSuite Exploration

### Location
`docs/engines/gaussian/`

### Contents
- GAUSSIAN_EXPLORATION.md — 347 lines of comprehensive exploration notes
- GAUSSIAN_INTEGRATION_PLAN.md — 436 lines of integration plan (completed)
- gaussian_parser.py — 435 lines (output log parser)
- gaussian_writer.py — 102 lines (input file writer)
- smoke_tests/ — 5 validated cases with .gjf + .log files

## Source 6: Local Gaussian 09 Binary

### Location
`.qmatsuite/engines/gaussian/gaussian09/g09/g09`

### Details
- Gaussian 09 Revision D.01
- Mach-O 64-bit executable (x86_64)
- Used for validation runs (9 cases executed successfully)
