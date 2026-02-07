# Siesta Sources

Updated: 2026-02-07
Engine: `siesta`

## Official Documentation and Upstream Corpus

1. Siesta project homepage
- URL: `https://siesta-project.org/`
- Retrieved: 2026-02-06 and 2026-02-07
- Local evidence: `.tmp/engine_research/siesta/raw_web/siesta_org_main.html`

2. Siesta manual landing pages (legacy mirror; quality mixed)
- URL family: `https://siesta-project.org/manual*`
- Retrieved: 2026-02-06
- Local evidence: `.tmp/engine_research/siesta/raw_web/`
- Audit note: many mirrored pages are HTTP 404 placeholders; see corpus audit in `docs/engines/siesta/CORPUS_INDEX.md`.

3. Official Siesta source repository (authoritative examples/tests/docs)
- URL: `https://gitlab.com/siesta-project/siesta`
- Retrieved: 2026-02-07
- Local evidence: `.tmp/engine_research/siesta/extracted/siesta_repo/`
- Snapshot commit: `e486d12067b96ff688179f0496d0ec21b6fae0ab`

4. Siesta manual PDF (upstream bundle)
- URL: `https://gitlab.com/siesta-project/siesta/-/raw/master/Docs/manual_tex/SIESTA_manual.pdf`
- Retrieved: 2026-02-06
- Local evidence: `.tmp/engine_research/siesta/raw_pdfs/SIESTA_manual.pdf`

## Upstream Test/Example Provenance Used for Curated Cases

1. H2O molecular example
- `.tmp/engine_research/siesta/extracted/siesta_repo/Examples/H2O/h2o.fdf:1`

2. Si bulk SCF-style baseline
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/01.PseudoPotentials/base_si2.fdf:1`

3. Bands workflow provenance
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/05.Bands/ge_bands.fdf:2`
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/05.Bands/script.sh:12`

4. DOS/PDOS workflow provenance
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/06.DensityOfStates/pdos_kp.fdf:7`
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/06.DensityOfStates/script.sh:12`

5. Spin workflow provenance
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/02.SpinPolarization/fe_spin.fdf:4`
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/02.SpinPolarization/script.sh:12`

6. MD workflow provenance
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/09.MolecularDynamics/verlet.fdf:6`
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/09.MolecularDynamics/script.sh:13`

7. Variable-cell relaxation provenance
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/08.GeometryOptimization/cg_vc.fdf:4`
- `.tmp/engine_research/siesta/extracted/siesta_repo/Tests/08.GeometryOptimization/cg_vc.fdf:5`

## Reference Output Anchors (Numeric Comparisons)

1. `docs/engines/siesta/artifacts/h2o_scf/h2o.out:521`
2. `docs/engines/siesta/artifacts/si_scf/si_scf.out:494`
3. `docs/engines/siesta/artifacts/si_relax/si_relax.out:1228`
