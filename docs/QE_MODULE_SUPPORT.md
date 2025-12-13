# Quantum ESPRESSO Module Support

This document lists all supported QE modules and their documentation links.

## Supported Modules

### Core Modules

#### PW (pw.x)
- **Purpose**: Main DFT code for self-consistent field calculations
- **Namelists**: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_PW.html
- **Detection**: Default for `&CONTROL`, `&SYSTEM`, `&ELECTRONS` namelists

#### PH (ph.x)
- **Purpose**: Phonon calculations
- **Namelist**: `&inputph`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_PH.html
- **Detection**: `&inputph` namelist

#### Q2R (q2r.x)
- **Purpose**: q-point to real space conversion
- **Namelist**: `&input`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_Q2R.html
- **Detection**: `&input` namelist with `fildyn` parameter

#### MATDYN (matdyn.x)
- **Purpose**: Phonon frequency calculation
- **Namelist**: `&input`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_MATDYN.html
- **Detection**: `&input` namelist with `dos` or `flfrq` parameters

### Post-Processing Modules

#### PP (pp.x)
- **Purpose**: Post-processing (charge density, wavefunctions, etc.)
- **Namelist**: `&inputpp`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_PP.html
- **Detection**: `&inputpp` namelist

#### BANDS (bands.x)
- **Purpose**: Band structure calculations
- **Namelists**: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&BANDS`
- **Documentation**: Similar to pw.x
- **Detection**: `calculation='bands'` in `&CONTROL`

#### DOS (dos.x)
- **Purpose**: Density of states calculations
- **Namelists**: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&DOS`
- **Documentation**: Similar to pw.x
- **Detection**: `calculation='dos'` in `&CONTROL`

#### PROJWFC (projwfc.x)
- **Purpose**: Projected wavefunction calculations
- **Namelists**: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&PROJWFC`
- **Documentation**: Similar to pw.x
- **Detection**: `&PROJWFC` namelist

### Advanced Modules

#### NEB (neb.x)
- **Purpose**: Nudged Elastic Band method for transition state search
- **Namelist**: `&PATH` (plus embedded pw.x input)
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_NEB.html
- **Detection**: `&PATH` namelist
- **Note**: NEB uses a special input format with supercards (BEGIN/END blocks)

#### CP (cp.x)
- **Purpose**: Car-Parrinello molecular dynamics
- **Namelists**: `&CONTROL`, `&SYSTEM`, `&ELECTRONS`, `&IONS`, `&CELL`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_CP.html
- **Detection**: `calculation='cp'` or `calculation='cp-wf'` in `&CONTROL`

#### HP (hp.x)
- **Purpose**: Hubbard U parameter calculations
- **Namelist**: `&inputhp`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_HP.html
- **Detection**: `&inputhp` namelist

#### LD1 (ld1.x)
- **Purpose**: Atomic calculations (pseudopotential generation, etc.)
- **Namelist**: `&input`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_LD1.html
- **Detection**: `&input` namelist with `atom` or `zed` parameters

#### PWCOND (pwcond.x)
- **Purpose**: Conductance calculations
- **Namelist**: `&cond`
- **Documentation**: https://www.quantum-espresso.org/Doc/INPUT_PWCOND.html
- **Detection**: `&cond` namelist

#### GIPAW (gipaw.x)
- **Purpose**: NMR/EPR calculations
- **Namelist**: `&inputgipaw`
- **Documentation**: (See QE documentation)
- **Detection**: `&inputgipaw` namelist

## Module Detection Logic

The `QEInput.detect_module()` method uses the following detection order:

1. **Module-specific namelists** (highest priority):
   - `&inputph` → PH
   - `&inputhp` → HP
   - `&inputpp` → PP
   - `&inputgipaw` → GIPAW
   - `&PATH` → NEB
   - `&cond` → PWCOND

2. **&input namelist** (requires parameter checking):
   - Check for `atom` or `zed` → LD1
   - Check for `dos` or `flfrq` → MATDYN
   - Check for `fildyn` → Q2R
   - Default → Q2R

3. **Standard namelists** (`&CONTROL`, `&SYSTEM`, `&ELECTRONS`):
   - Check `calculation` parameter:
     - `'cp'` or `'cp-wf'` → CP
     - `'bands'` → BANDS
     - `'dos'` → DOS
   - Default → PW

## Calculation Notes

Many QE calculations run modules sequentially where:
- Previous step's OUTPUT determines next step's INPUT filename
- Example: `pw.x` generates `.save` directory → `ph.x` reads from `.save`
- Example: `ph.x` generates `dyn` files → `q2r.x` reads `dyn` files → `matdyn.x` reads `.fc` file
- The `prefix`/`outdir` from previous step's input determines output filenames

## References

All official documentation links are embedded in the code comments for easy reference:
- `src/quantumvitas/core/engines/qe_input.py`
- `src/quantumvitas/core/engines/qe.py`

