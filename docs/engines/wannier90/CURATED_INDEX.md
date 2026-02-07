# Wannier90 Curated Case Index

**Location**: `tests/inputformat/samples/w90/`
**Count**: 8 curated cases
**Last updated**: 2026-02-07

## Cases

| # | case_id | Species | Key Features | Provenance |
|---|---------|---------|-------------|------------|
| 1 | gaas_basic | Ga, As | Basic Wannierisation, sp3, bohr lattice | W90 Tutorial Example 1 |
| 2 | copper_disentangle | Cu | Disentanglement, kpoint_path, f-centred projections, Fortran d0 notation | W90 Tutorial Example 4 |
| 3 | diamond_pipeline | C | QE pipeline case, wannier_plot, f-centred projections | W90 Tutorial Example 5 |
| 4 | iron_spinor | Fe | Spinors, disentanglement, postw90 kpath, spin-coloured bands | W90 Tutorial Example 17 |
| 5 | pt_shc | Pt | Spin Hall conductivity, Berry phase, spinors, kslice, fermi scan | W90 Tutorial Example 29 |
| 6 | silicon_bandinterp | Si | Disentanglement, band interpolation, case-insensitive block delimiters | W90 Tutorial Example 3 |
| 7 | silane_molecular | Si, H | Molecular system, gamma-only, atoms_cart, bohr lattice | W90 Tutorial Example 7 |
| 8 | batio3_excludebands | Ba, Ti, O | exclude_bands, guiding_centres, perovskite oxide, kpoint_path | W90 Tutorial Example 9 |

## Diversity Rationale (per Playbook S1.11 D2)

### Crystal Structure Types
- Zincblende: GaAs (gaas_basic)
- FCC metal: Cu (copper_disentangle), Pt (pt_shc)
- Diamond cubic: C (diamond_pipeline), Si (silicon_bandinterp)
- BCC metal: Fe (iron_spinor)
- Perovskite: BaTiO3 (batio3_excludebands)
- Molecular: SiH4 (silane_molecular)

### Material Classes
- III-V semiconductor: GaAs
- Group-IV semiconductor: Si, C (diamond)
- Transition metal: Cu, Fe, Pt
- Oxide: BaTiO3
- Molecular: SiH4

### Feature Coverage
| Feature | Covered by |
|---------|-----------|
| Basic Wannierisation | gaas_basic |
| Disentanglement | copper_disentangle, silicon_bandinterp, iron_spinor, pt_shc |
| Band interpolation (kpoint_path) | copper_disentangle, silicon_bandinterp, batio3_excludebands, iron_spinor, pt_shc |
| Spinors | iron_spinor, pt_shc |
| Berry phase / transport | pt_shc |
| Spin Hall conductivity | pt_shc |
| Wannier function plotting | diamond_pipeline |
| exclude_bands | batio3_excludebands |
| guiding_centres | batio3_excludebands, pt_shc |
| atoms_cart (Cartesian coords) | silane_molecular |
| atoms_frac (fractional coords) | gaas_basic, copper_disentangle, diamond_pipeline, iron_spinor, pt_shc, silicon_bandinterp, batio3_excludebands |
| Gamma-only | silane_molecular |
| postw90 (kpath/kslice) | iron_spinor, pt_shc |
| f-centred projections | copper_disentangle, diamond_pipeline |
| Fortran d0 notation | copper_disentangle, iron_spinor, pt_shc |
| Bohr unit cell | gaas_basic, silane_molecular, iron_spinor, pt_shc, batio3_excludebands |
| Angstrom unit cell (default) | copper_disentangle (no units line = default Ang), diamond_pipeline, silicon_bandinterp |

### Parser Edge Cases Covered
- Case-insensitive block delimiters (`Begin`/`End`): silicon_bandinterp
- Both comment styles (`!` and `#`): gaas_basic (`!`), iron_spinor (`#`), pt_shc (`#`)
- Separator variants: `=` (most cases), `:` (batio3_excludebands, silane_molecular)
- Fortran scientific notation (`1.0d0`): copper_disentangle, iron_spinor, pt_shc
- Inline comments: gaas_basic, pt_shc

### Real Execution Verified
- `gaas_basic` — Standalone W90 smoke test (`.tmp/engine_research/wannier90/real_run/gaas_standalone_smoke/`)
- `diamond_pipeline` — Full QE pipeline smoke test (`.tmp/engine_research/wannier90/real_run/diamond_qe_pipeline_smoke/`)
