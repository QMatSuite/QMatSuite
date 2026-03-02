# MACE Curated Sample Index

## Diversity Rationale

MACE is the first ML interatomic potential engine in QMatSuite. The 5 curated cases
cover all 3 supported generalized step types (scf, relax, md) across diverse system
types (elemental crystals, molecules, ternary oxides, metals).

ML potentials have fundamentally different parameter spaces than DFT codes:
- No basis set, exchange-correlation, or convergence parameters
- Key parameters are model selection, optimizer/MD settings, and device configuration
- ~42 tags vs. 150-250 tags for DFT engines (documented justification)

## Coverage Matrix

| Case | System | Gen Step | Elements | Periodicity | demo_eligible |
|------|--------|----------|----------|-------------|---------------|
| si_scf | Si diamond (2 atoms) | scf | Si | periodic | yes |
| si_relax | Distorted Si (2 atoms) | relax | Si | periodic | yes |
| water_md | H2O in box (3 atoms) | md | O, H | periodic | yes |
| li_metal_scf | Li BCC (1 atom) | scf | Li | periodic | no |
| perovskite_relax | CaTiO3 (5 atoms) | relax | Ca, Ti, O | periodic | no |

## Feature Coverage

| Feature | Cases |
|---------|-------|
| Foundation model (mace_mp) | All 5 |
| Single-point energy | si_scf, li_metal_scf |
| Geometry optimization | si_relax, perovskite_relax |
| Molecular dynamics | water_md |
| Stress tensor | si_scf, li_metal_scf |
| Variable-cell relax | perovskite_relax |
| Multi-element system | water_md, perovskite_relax |
| Metallic system | li_metal_scf |
| Molecular system | water_md |

## Demo-Eligible Cases

3 of 5 cases are demo-eligible with slugs:
- `mace_si_scf` — beginner tutorial, simplest possible MACE calculation
- `mace_si_relax` — beginner tutorial, shows optimization workflow
- `mace_water_md` — beginner tutorial, shows MD with Langevin thermostat
