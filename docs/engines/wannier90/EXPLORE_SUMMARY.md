# Wannier90 Exploration Summary

## Raw Corpus Location
`.tmp/engine_research/wannier90/`

## Contents

| Directory | Contents | Size |
|-----------|----------|------|
| `raw_web/` | 15 files: ReadTheDocs pages, QE interface docs, fetch logs | ~96 KB |
| `raw_pdfs/` | user_guide.pdf, tutorial.pdf, solution_booklet.pdf | 16 MB |
| `extracted/doc_full/user_guide/` | 26 LaTeX source files (complete W90 user guide) | ~33 MB |
| `extracted/examples_src/` | 33 original example directories | ~18 MB |
| `extracted/INPUT_pw2wannier90.txt` | pw2wannier90 input specification | 16 KB |
| `extracted/EXAMPLES_MANIFEST.md` | Catalog of all 83 .win files found | 11 KB |
| `metadata/wannier90_params.yaml` | 171 parameter entries (1723 lines) | 59 KB |
| `normalized/` | 20 case directories with case.yaml + input files | ~14 MB |
| `normalized/SKIPPED.md` | 13 skipped examples with reasons | 4 KB |

## Metadata Seed Coverage
- 120 .win parameters across 8 categories (system, projection, job_control, disentanglement, wannierise, plot, transport, postw90)
- 9 block definitions (unit_cell_cart, atoms_cart, atoms_frac, projections, kpoints, kpoint_path, nnkpts, dis_spheres, slwf_centres)
- 30 pw2wannier90 interface parameters

## Normalized Case Library
20 cases covering 13 materials (GaAs, Pb, Si, Cu, C, Fe, BaTiO3, graphite, SiH4, CNT, Pt, W) and 11 feature categories (disentanglement, band_interpolation, fermi_surface, wannier_plot, spinors, spin_polarized, berry_phase, guiding_centres, auto_projections, gamma_only, transport).

5 pure Wannier90 cases (standalone with pre-computed .amn/.mmn/.eig) and 15 QE pipeline cases (require scf/nscf/pw2wannier90).
