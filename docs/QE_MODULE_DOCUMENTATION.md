# Quantum ESPRESSO Module Documentation Links

This document lists all QE modules and their official documentation links following the pattern:
`https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html`

## Currently Supported Modules (with Documentation)

### Core Modules

1. **PW (pw.x)** - Main DFT code
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PW.html
   - Namelists: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`

2. **PH (ph.x)** - Phonon calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PH.html
   - Namelist: `&inputph`

3. **Q2R (q2r.x)** - q-point to real space conversion
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
   - Namelist: `&input`

4. **MATDYN (matdyn.x)** - Phonon frequency calculation
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
   - Namelist: `&input`

### Post-Processing Modules

5. **PP (pp.x)** - Post-processing
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PP.html
   - Namelist: `&inputpp`

6. **BANDS (bands.x)** - Band structure calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_BANDS.html
   - Namelist: `&BANDS`

7. **DOS (dos.x)** - Density of states calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_DOS.html
   - Namelist: `&DOS`

8. **PROJWFC (projwfc.x)** - Projected wavefunction calculations
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PROJWFC.html
   - Namelist: `&PROJWFC`

### Advanced Modules

9. **NEB (neb.x)** - Nudged Elastic Band method
   - Documentation: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
   - Namelist: `&PATH` (plus embedded pw.x input)

10. **CP (cp.x)** - Car-Parrinello molecular dynamics
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_CP.html
    - Namelists: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`

11. **LD1 (ld1.x)** - Atomic calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
    - Namelist: `&input`

12. **HP (hp.x)** - Hubbard U parameter calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_HP.html
    - Namelist: `&inputhp`

13. **PWCOND (pwcond.x)** - Conductance calculations
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
    - Namelist: `&cond`

## Documentation URL Pattern

All QE module documentation follows a consistent pattern:
```
https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html
```

Where `{MODULE_NAME}` is the uppercase version of the executable name (with `.x` removed), with special characters converted:
- Hyphens (`-`) → Underscores (`_`)
- Example: `pwcond.x` → `INPUT_PWCOND.html`
- Example: `band-interpolation.x` → `INPUT_BAND_INTERPOLATION.html`

## Adding New Modules

To add support for a new QE module:

1. **Check if documentation exists**:
   - Convert executable name to uppercase
   - Replace hyphens with underscores
   - Check: `https://www.quantum-espresso.org/Doc/INPUT_{MODULE_NAME}.html`

2. **Add to QEModule enum** in `src/quantumvitas/core/engines/qe_input.py`:
   ```python
   MODULE_NAME = "module"  # module.x - description
   ```

3. **Update detect_module()** method with detection logic

4. **Add to MODULE_NAMELISTS** in `src/quantumvitas/core/engines/qe.py`

5. **Add documentation link** to enum docstring and comments

## Additional Supported Modules (with Documentation)

14. **POSTAHC (postahc.x)** - Post-processing for AHC
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_POSTAHC.html
    - Namelist: `&input`

15. **DYNMAT (dynmat.x)** - Dynamical matrix diagonalization
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_DYNMAT.html
    - Namelist: `&input`

16. **OSCDFT_ET (oscdft_et.x)** - OSCDFT eigenvalue tracking
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_ET.html
    - Namelist: `&oscdft_et_namelist`

17. **OSCDFT_PP (oscdft_pp.x)** - OSCDFT post-processing
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_OSCDFT_PP.html
    - Namelist: `&oscdft_pp_namelist`

18. **BAND_INTERPOLATION (band_interpolation.x)** - Band interpolation
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_BAND_INTERPOLATION.html
    - Namelist: `&interpolation`

19. **CPPP (cppp.x)** - CP post-processing
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_CPPP.html
    - Namelist: `&inputpp`

20. **D3HESS (d3hess.x)** - Third-order force constants
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_D3HESS.html
    - Namelist: `&input`

21. **PPACF (ppacf.x)** - Post-processing ACF
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PPACF.html
    - Namelist: `&plot`

22. **PPRISM (pprism.x)** - Post-processing RISM
    - Documentation: https://www.quantum-espresso.org/Doc/INPUT_PPRISM.html
    - Namelists: `&inputpp`, `&plot`

## Other QE Modules (No Input Documentation)

The following modules exist in QE but do not have input file documentation or are utility programs without structured input files:

**Note**: These modules either:
- Are utility programs that don't use structured input files
- Have documentation but without input file format specifications
- Are external tools (e.g., Wannier90)

Examples include:
- Utility tools: `alpha2f.x`, `average.x`, `cell2ibrav.x`, `ibrav2cell.x`, `kpoints.x`, `dist.x`
- Plotting tools: `plotband.x`, `plotproj.x`, `plotrho.x`
- Conversion tools: `pw2gw.x`, `pw2bgw.x`, `pw2wannier90.x`, `pwi2xsf.x`
- External interfaces: `wannier90.x` (external tool)
- And many others...

For a complete list of all QE executables, check the `bin` directory of your QE installation.

## Notes

- Not all modules have input files (some are utilities)
- Some modules may use the same input format as other modules
- Documentation availability should be verified before adding support
- When adding new modules, follow the detection logic in `detect_module()` method

