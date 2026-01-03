# Failed Demo Generation Report

**Last Updated**: After manual pseudo download and regeneration

## Summary
- **Total datasets attempted**: 28 (from tutorial datasets)
- **Successfully generated**: 19 (increased from 18 after ibrav=12 fix)
- **Failed**: 9 (only missing pseudos remain)
- **Main demos**: 2 (si_bands_demo, si_dos_demo) ✅
- **Wannier90 demos**: 3 (diamond, copper, silicon) ✅
- **Total valid demos**: 16 ✅

## Recent Fixes
- ✅ **13_graphene**: Fixed ibrav=12/-12 parsing bug (was incorrectly using cosbc instead of cosab)

## Recently Fixed Demos
After manual pseudo download, the following demos are now successfully generated:
- ✅ **12_NMR_gipaw** (previously missing GIPAW pseudos) - Now works with manual downloads

## Failed Demos by Category

### Category 1: Missing Pseudopotentials (404 from QE Repository)

These pseudopotentials cannot be downloaded from the official QE repository:

#### H_ONCV_PBE-1.0.oncvpsp.upf (5 demos)
- **01_H2** - Missing: `H_ONCV_PBE-1.0.oncvpsp.upf`
- **02_H2O** - Missing: `H_ONCV_PBE-1.0.oncvpsp.upf`
- **11_Si_100_surface_reconstruction** - Missing: `H_ONCV_PBE-1.0.oncvpsp.upf`
- **17_H2O_vibration** - Missing: `H_ONCV_PBE-1.0.oncvpsp.upf`
- **18_H2O_MD** - Missing: `H_ONCV_PBE-1.0.oncvpsp.upf`

**Status**: Cannot be automatically downloaded. These ONCV pseudopotentials need to be:
- Downloaded from Materials Project, ONCVPSP repository, or other sources
- Generated using ONCVPSP code
- Replaced with alternative pseudo types (e.g., `H.pbe-rrkjus.UPF` or `H.pz-vbc.UPF`)

**Note**: We have `H_ONCV_PBE-1.0.upf` in `resources/pseudo/`, but the demos require `H_ONCV_PBE-1.0.oncvpsp.upf` (different filename).

#### H.upf, C.upf (1 demo)
- **10_benzene_TDDFT** - Missing: `H.upf`, `C.upf`

**Status**: Generic filenames, likely need specific versions. Cannot be automatically downloaded.

**Note**: We have various C and H pseudos available:
- `C.pbe-n-kjpaw_psl.1.0.0.UPF`, `C.pbe-rrkjus.UPF`, `C.pz-rrkjus.UPF`, `C.pz-vbc.UPF`
- `H.pbe-rrkjus.UPF`, `H.pz-vbc.UPF`, `H_ONCV_PBE-1.0.upf`

But the demo requires exact filenames `C.upf` and `H.upf`.

#### Nickel Pseudopotentials (2 demos)
- **14_DFT_plus_U_NiO__1_noU** - Missing: `ni_pbe_v1.4.uspp.F.UPF`
- **14_DFT_plus_U_NiO__2_addU** - Missing: `ni_pbe_v1.4.uspp.F.UPF`

**Status**: Specific USPP pseudopotential version, not available in standard repository.

#### Nitrogen ONCV Pseudopotentials (1 demo)
- **05_NH3_inversion** - Missing: `N.oncvpsp.upf`, `H_ONCV_PBE-1.0.oncvpsp.upf`

**Status**: ONCV pseudopotentials, not available in standard repository.

**Note**: We have `N-PBE.upf` in `resources/pseudo/`, but the demo requires `N.oncvpsp.upf`.

### Category 2: Structure Parsing Errors

#### ✅ FIXED: ibrav=12/-12 Parameter Recognition (1 demo)
- **13_graphene** - ~~Error: `ibrav=12/-12 requires b, c, and cos(angle).`~~

**Status**: ✅ **FIXED** - This was a parser bug, not a data issue. The parser was incorrectly looking for `cosbc` instead of `cosab` for ibrav=12. Fixed in commit [ref].

**Fix details**:
- ibrav=12 (monoclinic, unique axis c) uses `cosab` (cos of angle between a and b), not `cosbc`
- The parser now correctly uses `cosab` for ibrav=12 and `cosac` for ibrav=-12
- Case-insensitive parameter matching was already in place and working correctly

## Successfully Generated Demos (18 from tutorials + 5 main/wannier90 = 23 total files, but some merge into same files)

### Tutorial Demos (19)
1. ✅ 00_Si_scf
2. ✅ 03_Si_vc_relax
3. ✅ 04_Si_DOS
4. ✅ 06_Al_DOS
5. ✅ 07_Si_bandStructure
6. ✅ 08_Fe_DOS (collinear)
7. ✅ 08_Fe_DOS (noncollinear)
8. ✅ 09_Si_phonon (gamma point)
9. ✅ 09_Si_phonon (DOS)
10. ✅ 09_Si_phonon (phonon dispersion)
11. ✅ 12_NMR_gipaw (TMS reference) - **Now working after manual pseudo download**
12. ✅ 12_NMR_gipaw (benzene) - **Now working after manual pseudo download**
13. ✅ 13_graphene - **Now working after ibrav=12 parser fix** ✅
14. ✅ 15_bulk_modulus_Si
15. ✅ 19_Si_CPMD (cell relax)
16. ✅ 19_Si_CPMD (CPMD NVE)
17. ✅ 19_Si_CPMD (CPMD NVT)
18. ✅ 19_Si_CPMD (BOMD NVE)
19. ✅ 19_Si_CPMD (BOMD NVT)

### Main Demos (2)
1. ✅ si_bands_demo.yml
2. ✅ si_dos_demo.yml

### Wannier90 Demos (3)
1. ✅ diamond_wannier90_demo.yml
2. ✅ copper_wannier90_demo.yml
3. ✅ silicon_wannier90_demo.yml

## Verification Status

All 16 generated demo files pass validation:
```bash
python tools/verify_demos.py
# Result: ✓ All demos are valid
```

## Available Pseudopotentials in resources/pseudo/

Current count: 21 files

- Al.pbe-n-kjpaw_psl.1.0.0.UPF
- Al.pz-vbc.UPF
- B-PBE.upf
- C.pbe-n-kjpaw_psl.1.0.0.UPF
- C.pbe-rrkjus.UPF
- C.pbe-tm-gipaw.UPF
- C.pz-rrkjus.UPF
- C.pz-vbc.UPF
- Cu.pz-n-van_ak.UPF
- Fe.pbe-spn-kjpaw_psl.0.2.1.UPF
- H.pbe-rrkjus.UPF
- H.pbe-tm-gipaw.UPF
- H.pz-vbc.UPF
- H_ONCV_PBE-1.0.upf
- N-PBE.upf
- O.pbe-n-kjpaw_psl.0.1.UPF
- O.pz-rrkjus.UPF
- Si.pbe-n-rrkjus_psl.1.0.0.UPF
- Si.pbe-n-van.UPF
- Si.pbe-tm-gipaw.UPF

## Recommendations

### For Remaining Missing Pseudopotentials

1. **H_ONCV_PBE-1.0.oncvpsp.upf**:
   - Download from ONCVPSP repository or Materials Project
   - Or rename/symlink from `H_ONCV_PBE-1.0.upf` if they are the same file
   - Or modify demo inputs to use `H.pbe-rrkjus.UPF` or `H.pz-vbc.UPF`

2. **C.upf, H.upf** (generic filenames):
   - Determine which specific pseudo versions are needed
   - Either rename existing pseudos or download the exact versions
   - Or modify demo inputs to use specific filenames like `C.pbe-rrkjus.UPF`

3. **ni_pbe_v1.4.uspp.F.UPF**:
   - Download from QE pseudopotential database or Materials Project
   - May require manual search as it's a specific version

4. **N.oncvpsp.upf**:
   - Download from ONCVPSP repository
   - Or rename/symlink from `N-PBE.upf` if compatible

### For Graphene Structure Issue

- Check if the tutorial input file needs manual correction
- Or document this demo as requiring manual structure setup

## Progress Summary

- **Before fixes**: 8/28 successful
- **After API fixes**: 16/28 successful
- **After manual pseudo download**: 18/28 successful
- **After ibrav=12 parser fix**: 19/28 successful ✅
- **Overall improvement**: +11 demos (from 8 to 19)

## Next Steps

To reach 100% success rate, need to:
1. Download or resolve the remaining 4 unique missing pseudo filenames:
   - `H_ONCV_PBE-1.0.oncvpsp.upf` (or modify demos to use available H pseudos)
   - `C.upf`, `H.upf` (or determine exact versions needed)
   - `ni_pbe_v1.4.uspp.F.UPF`
   - `N.oncvpsp.upf` (or modify demo to use `N-PBE.upf`)
2. ~~Fix graphene structure input file~~ ✅ **FIXED** - Was a parser bug, not a data issue
