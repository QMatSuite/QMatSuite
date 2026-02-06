# Wannier90 Corpus — SOURCES

All sources used for the Wannier90 exploration track.

## Official Sources
| Source | URL/Path | Type | Crawl Date |
|--------|----------|------|------------|
| Wannier90 website (main) | https://wannier.org/ | web | 2026-02-05 |
| Wannier90 support page | https://wannier.org/support/ | web | 2026-02-05 |
| Wannier90 tutorials page | https://wannier.org/tutorials/ | web | 2026-02-05 |
| GitHub docs directory listing | https://github.com/wannier-developers/wannier90/tree/develop/docs | web | 2026-02-05 |
| GitHub README | https://raw.githubusercontent.com/wannier-developers/wannier90/develop/README.md | web | 2026-02-05 |
| ReadTheDocs (online docs) | https://wannier90.readthedocs.io/ | web | 2026-02-05 |

## Local Source Trees (PRIMARY)
| Source | Path | Type | Notes |
|--------|------|------|-------|
| QE-bundled Wannier90 v3.1.0 (FULL, non-empty) | `.qmatsuite/engines/qe/q-e-qe-7.5/external/wannier90/` | local | Complete source with examples and docs. **Primary source for examples and LaTeX docs.** |
| QE pw2wannier90 docs | `.qmatsuite/engines/qe/q-e-qe-7.5/PP/Doc/INPUT_pw2wannier90.{txt,def}` | local | Complete pw2wannier90 input documentation |

## Documentation Files Extracted
| File | Lines | Content |
|------|-------|---------|
| `doc_full/user_guide/parameters.tex` | ~1800 | Complete parameter reference for .win files |
| `doc_full/user_guide/projections.tex` | ~200+ | Projection specification syntax |
| `doc_full/user_guide/wannier.tex` | 272 | Wannierisation procedure |
| `doc_full/user_guide/wannier-pp.tex` | 610 | Post-processing |
| `doc_full/user_guide/utilities.tex` | 304 | Utility programs |
| `INPUT_pw2wannier90.txt` | 352 | pw2wannier90 input reference |

## Examples Extracted
| Source | Count | Notes |
|--------|-------|-------|
| QE-bundled examples (example01-example32) | 34 dirs | Mix of pure W90 (01-04, 16-noqe) and QE->W90 pipeline (05-32). All .win files have content. |

## QE Interface Sources
| Source | URL/Path | Type | Crawl Date |
|--------|----------|------|------------|
| pw2wannier90 input docs (.txt) | local (QE PP/Doc/) | local | 2026-02-05 |
| pw2wannier90 input definition (.def) | local (QE PP/Doc/) | local | 2026-02-05 |
| pw2wannier90 source (multiple versions v3.2.3-v6.5) | local (QE external/wannier90/pwscf/) | local | 2026-02-05 |
| QE pw2wannier90 web docs | https://www.quantum-espresso.org/Doc/INPUT_pw2wannier90.html | web | 2026-02-05 |

## Citations (from wannier.org)
- v3.x: Pizzi et al., J. Phys. Cond. Matt. 32, 165902 (2020)
- v2.x: Mostofi et al., Comput. Phys. Commun. 185, 2309 (2014)
- v1.x: Mostofi et al., Comput. Phys. Commun. 178, 685 (2008)
