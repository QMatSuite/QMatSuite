# VASP DOS Test Fixtures

Generated from real VASP calculations.

## Files

- `DOSCAR`: Si non-spin total DOS (NEDOS=301)
- `DOSCAR_spin`: Fe spin-polarized DOS (ISPIN=2, NEDOS=301)
- `DOSCAR_pdos`: TiO2 with LORBIT=11 for full lm PDOS (NEDOS=301)
- `vasprun.xml`: Minimal vasprun.xml from Si calculation (for efermi)

## INCAR Key Settings

### Si (DOSCAR)
- ISMEAR = -5 (tetrahedron)
- NEDOS = 301
- Non-spin (default)

### Fe (DOSCAR_spin)
- ISMEAR = 0 (Gaussian)
- ISPIN = 2
- MAGMOM = 2.0
- NEDOS = 301

### TiO2 (DOSCAR_pdos)
- ISMEAR = -5
- LORBIT = 11 (full lm decomposition)
- NEDOS = 301
