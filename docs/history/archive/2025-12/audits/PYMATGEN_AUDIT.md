# PyMatGen Usage Audit Report

**Date**: Generated from codebase analysis  
**Scope**: Complete enumeration of all pymatgen usage across the repository  
**Goal**: Identify platform-dependent defaults/behaviors affecting structure/bond results

---

## Executive Summary

### Top 10 Highest-Risk Calls

1. **`structure.make_supercell(scaling)` - structure_viz.py:1076**
   - **Risk**: HIGH - Missing `to_unit_cell` parameter (default likely `True` in some pymatgen versions)
   - **Impact**: May fold coordinates back to [0,1) after supercell expansion, breaking canonicalization contract
   - **Recommendation**: Explicitly pass `to_unit_cell=False` to preserve coordinates

2. **`SpacegroupAnalyzer(structure)` - structure_viz.py:1101, kpath.py:169**
   - **Risk**: HIGH - Missing `symprec` and `angle_tolerance` parameters
   - **Impact**: Platform-dependent tolerance defaults may affect symmetry detection and primitive/conventional cell selection
   - **Recommendation**: Pin `symprec=0.01` and `angle_tolerance=5.0` explicitly

3. **`analyzer.get_conventional_standard_structure()` - structure_viz.py:1102**
   - **Risk**: HIGH - May reorder sites, change lattice representation, fold coordinates
   - **Impact**: Different conventional cell choices across platforms could affect bond detection
   - **Recommendation**: Document that this changes representation; consider caching results

4. **`structure.get_primitive_structure()` - daemon/server.py:1544, test files**
   - **Risk**: HIGH - Missing tolerance parameters, may reorder sites, change lattice
   - **Impact**: Different primitive representations across platforms
   - **Recommendation**: Pass explicit `tolerance` parameter; document site reordering

5. **`Structure.from_file(str(filepath))` - structure_io.py:63**
   - **Risk**: MED - Auto-detects format, may set `coords_are_cartesian` based on file format
   - **Impact**: Coordinate system assumptions may differ by file format
   - **Recommendation**: Explicitly specify format and coordinate system when known

6. **`PMGStructure.from_dict(structure_payload)` - structure_io.py:57, online_cache.py:157**
   - **Risk**: MED - Relies on pymatgen's dict format interpretation
   - **Impact**: Coordinate system and lattice interpretation may vary
   - **Recommendation**: Verify dict format matches expected pymatgen version

7. **`Structure(lattice, species, coords, coords_are_cartesian=...)` - structure_io.py:253, online_search.py:449**
   - **Risk**: MED - `coords_are_cartesian` parameter controls coordinate interpretation
   - **Impact**: Fractional vs Cartesian conversion may differ slightly
   - **Recommendation**: Always explicitly set `coords_are_cartesian` parameter

8. **`HighSymmKpath(structure, path_type=ptype)` - kpath.py:180**
   - **Risk**: MED - Missing tolerance parameters, may use different path algorithms
   - **Impact**: K-path generation may differ across pymatgen versions
   - **Recommendation**: Pin `path_type` explicitly; document fallback behavior

9. **`structure.replace(i, site.specie, frac_canon, coords_are_cartesian=False)` - structure_viz.py:253**
   - **Risk**: LOW-MED - Explicit parameter, but coordinate update may trigger internal conversions
   - **Impact**: Minor float precision differences in coordinate updates
   - **Recommendation**: Verify behavior is consistent

10. **`structure.to(fmt=fmt, filename=str(filepath))` - structure_io.py:104**
    - **Risk**: LOW - Output operation, but format-specific coordinate handling
    - **Impact**: Output coordinates may be formatted differently
    - **Recommendation**: Document format-specific behavior

---

## Full Inventory Table

| File:Line | Import(s) | Call Expression | Params Passed (Explicit) | Defaults Relied Upon | Effect | Risk | Pipeline Usage |
|-----------|-----------|-----------------|--------------------------|----------------------|--------|------|----------------|
| **structure_viz.py:60-62** | `from pymatgen.core import Structure as PMGStructure`<br>`from pymatgen.core.periodic_table import Element`<br>`from pymatgen.symmetry.analyzer import SpacegroupAnalyzer` | Import only | N/A | N/A | N/A | LOW | All visualization |
| **structure_viz.py:253** | (uses PMGStructure) | `structure.replace(i, site.specie, frac_canon, coords_are_cartesian=False)` | `coords_are_cartesian=False` | None | Updates fractional coords in place | LOW | Canonicalization |
| **structure_viz.py:372** | (uses PMGStructure) | `lattice.get_fractional_coords(c)` | None | None | Converts cart→frac | LOW | Coordinate conversion |
| **structure_viz.py:378** | (uses PMGStructure) | `lattice.get_cartesian_coords(f)` | None | None | Converts frac→cart | LOW | Coordinate conversion |
| **structure_viz.py:1076** | (uses PMGStructure) | `supercell.make_supercell(scaling)` | `scaling` only | **`to_unit_cell` (default likely `True` in some versions)** | **FOLDS COORDS to [0,1)** | **HIGH** | Supercell expansion |
| **structure_viz.py:1101-1102** | (uses SpacegroupAnalyzer) | `analyzer = SpacegroupAnalyzer(structure)`<br>`conventional = analyzer.get_conventional_standard_structure()` | None | **`symprec` (default ~0.01)**<br>**`angle_tolerance` (default ~5.0)**<br>**`tolerance` in get_conventional** | **Reorders sites, changes lattice, may fold coords** | **HIGH** | Conventional cell |
| **structure_viz.py:1364** | (uses PMGStructure) | `display_structure.lattice.get_cartesian_coords(site.frac_coords)` | None | None | Converts frac→cart | LOW | Display atom building |
| **structure_io.py:15-17** | `from pymatgen.core import Element`<br>`from pymatgen.core import Lattice`<br>`from pymatgen.core import Structure as PMGStructure` | Import only | N/A | N/A | N/A | LOW | Structure I/O |
| **structure_io.py:57** | (uses PMGStructure) | `PMGStructure.from_dict(structure_payload)` | `structure_payload` | **Dict format interpretation** | **May interpret coords as cart/frac based on dict** | MED | JSON structure loading |
| **structure_io.py:63** | (uses PMGStructure) | `PMGStructure.from_file(str(filepath))` | `filepath` only | **Format auto-detection**<br>**`coords_are_cartesian` inferred from format** | **Coordinate system may vary by format** | MED | File structure loading |
| **structure_io.py:91** | (uses PMGStructure) | `structure.as_dict()` | None | None | Serializes to dict | LOW | Structure serialization |
| **structure_io.py:104** | (uses PMGStructure) | `structure.to(fmt=fmt, filename=str(filepath))` | `fmt`, `filename` | **Format-specific coordinate handling** | Output formatting | LOW | Structure writing |
| **structure_io.py:143** | (uses Element) | `structure.composition.elements` | None | None | Gets unique elements | LOW | QE input generation |
| **structure_io.py:160** | (uses Element) | `float(el.atomic_mass)` | None | None | Gets atomic mass | LOW | QE input generation |
| **structure_io.py:174** | (uses PMGStructure) | `site.coords` (property) | None | None | Gets Cartesian coords | LOW | QE input generation |
| **structure_io.py:184** | (uses PMGStructure) | `structure.lattice.matrix` | None | None | Gets lattice matrix | LOW | QE input generation |
| **structure_io.py:253-258** | (uses PMGStructure) | `PMGStructure(lattice, species, coords, coords_are_cartesian=not coords_are_frac)` | `coords_are_cartesian` explicitly set | None | Constructs structure | MED | QE input parsing |
| **structure_io.py:327** | (uses Lattice) | `Lattice(data)` | `data` (3x3 matrix) | None | Constructs lattice | LOW | Lattice construction |
| **structure_steps.py:10** | `from pymatgen.core import Structure as PMGStructure` | Import only | N/A | N/A | N/A | LOW | Step generation |
| **kpath.py:15-17** | `from pymatgen.core import Structure as PMGStructure, Lattice`<br>`from pymatgen.symmetry.analyzer import SpacegroupAnalyzer`<br>`from pymatgen.symmetry.bandstructure import HighSymmKpath` | Import only | N/A | N/A | N/A | LOW | K-path generation |
| **kpath.py:169** | (uses SpacegroupAnalyzer) | `sga = SpacegroupAnalyzer(structure)` | None | **`symprec` (default ~0.01)**<br>**`angle_tolerance` (default ~5.0)** | **Symmetry analysis with platform-dependent tolerances** | **HIGH** | K-path generation |
| **kpath.py:170-172** | (uses SpacegroupAnalyzer) | `sga.get_space_group_symbol()`<br>`sga.get_space_group_number()`<br>`sga.get_lattice_type()` | None | None | Gets symmetry info | LOW | K-path generation |
| **kpath.py:180** | (uses HighSymmKpath) | `kpath = HighSymmKpath(structure, path_type=ptype)` | `path_type` (with fallback) | **Tolerance parameters (if any)** | **K-path generation algorithm** | MED | K-path generation |
| **kpath.py:182-187** | (uses HighSymmKpath) | `kpath.kpath` or `kpath._kpath` | None | None | Accesses k-path data | LOW | K-path generation |
| **online_search.py:21-22** | `from pymatgen.core import Composition, Structure as PMGStructure`<br>`from pymatgen.core.periodic_table import Element` | Import only | N/A | N/A | N/A | LOW | Online structure search |
| **online_search.py:25-28** | `from pymatgen.ext.cod import COD` | Import only | N/A | N/A | N/A | LOW | COD search |
| **online_search.py:97** | (uses Composition) | `comp = Composition(normalized)` | `normalized` | None | Creates composition | LOW | Formula reduction |
| **online_search.py:98** | (uses Composition) | `comp.reduced_formula` | None | None | Gets reduced formula | LOW | Formula reduction |
| **online_search.py:192** | (uses COD) | `cod = COD()` | None | **Database path defaults** | Initializes COD | LOW | COD search |
| **online_search.py:196** | (uses COD) | `cod.get_structure_by_formula(reduced)` | `reduced` | None | Gets structure from COD | MED | COD search |
| **online_search.py:220** | (uses COD) | `cod.query(reduced)` | `reduced` | None | Queries COD | MED | COD search |
| **online_search.py:234** | (uses PMGStructure) | `structure.composition.reduced_formula` | None | None | Gets formula | LOW | COD result processing |
| **online_search.py:274** | (uses PMGStructure) | `comp = structure.composition` | None | None | Gets composition | LOW | Candidate scoring |
| **online_search.py:275** | (uses PMGStructure) | `comp.reduced_formula` | None | None | Gets formula | LOW | Candidate scoring |
| **online_search.py:287** | (uses PMGStructure) | `site.species.as_dict()` | None | None | Gets species dict | LOW | Partial occupancy check |
| **online_search.py:433** | (uses Lattice) | `from pymatgen.core import Lattice`<br>`lattice = Lattice(lattice_vectors)` | `lattice_vectors` | None | Constructs lattice | LOW | OPTIMADE parsing |
| **online_search.py:449** | (uses PMGStructure) | `PMGStructure(lattice, site_species, cartesian_positions, coords_are_cartesian=True)` | `coords_are_cartesian=True` | None | Constructs structure | MED | OPTIMADE parsing |
| **online_search.py:453** | (uses PMGStructure) | `structure.frac_coords` (property) | None | None | Gets fractional coords | LOW | OPTIMADE validation |
| **online_search.py:532** | (uses PMGStructure) | `structure.composition.reduced_formula` | None | None | Gets formula | LOW | Overview resolution |
| **online_search.py:556** | (uses PMGStructure) | `site.specie` (property) | None | None | Gets species | LOW | Overview resolution |
| **online_cache.py:24** | `from pymatgen.core import Structure as PMGStructure` | Import only | N/A | N/A | N/A | LOW | Structure caching |
| **online_cache.py:145** | (uses PMGStructure) | `structure.as_dict()` | None | None | Serializes to dict | LOW | Structure serialization |
| **online_cache.py:157** | (uses PMGStructure) | `PMGStructure.from_dict(structure_dict)` | `structure_dict` | **Dict format interpretation** | **Deserializes from dict** | MED | Structure deserialization |
| **parsers.py:741-742** | `from pymatgen.core import Structure`<br>`from pymatgen.symmetry.bandstructure import HighSymmKpath` | Import only | N/A | N/A | N/A | LOW | Band structure parsing |
| **parsers.py:746** | (uses Structure) | `struct = Structure.from_file(str(structure_file))` | `structure_file` | **Format auto-detection** | **Loads structure from file** | MED | High-symmetry point labeling |
| **parsers.py:747** | (uses HighSymmKpath) | `kpath = HighSymmKpath(struct)` | None | **Tolerance parameters (if any)** | **K-path generation** | MED | High-symmetry point labeling |
| **parsers.py:753** | (uses HighSymmKpath) | `kpath.kpath['kpoints']` | None | None | Accesses k-points | LOW | High-symmetry point labeling |
| **daemon/server.py:1544** | (uses PMGStructure) | `structure.get_primitive_structure()` | None | **`tolerance` (default likely ~0.01)** | **Reorders sites, changes lattice** | **HIGH** | Online structure processing |
| **Test files** | Various imports | `Structure(Lattice.cubic(...), [...], [[...]])` | Various | **`coords_are_cartesian` default `False`** | Constructs test structures | LOW | Unit tests |
| **Test files** | Various imports | `structure.get_primitive_structure()` | None | **`tolerance` default** | Gets primitive | HIGH | Unit tests |

---

## Deep Dive: Supercell Folding

### All Uses of `make_supercell`

#### 1. `structure_viz.py:1076` - CRITICAL
```python
supercell = structure.copy()
supercell.make_supercell(scaling)
```

**Current State**:
- **Missing `to_unit_cell` parameter** - relies on pymatgen default
- **Default behavior**: In pymatgen, `make_supercell()` typically has `to_unit_cell=True` by default
- **Impact**: After supercell expansion, coordinates are folded back to [0,1), breaking the canonicalization contract

**Contract Violation**:
- The codebase has a strict contract: canonicalize once at entry point, never again
- `make_supercell()` is called AFTER canonicalization
- If `to_unit_cell=True` (default), it folds coordinates again, potentially moving boundary atoms back into the main cell

**Recommendation**:
```python
supercell.make_supercell(scaling, to_unit_cell=False)
```

**Verification Needed**:
- Check pymatgen version in environment
- Confirm default value of `to_unit_cell` in `make_supercell()`
- Test that `to_unit_cell=False` preserves coordinates outside [0,1)

#### 2. No Other Direct Calls Found
- All other supercell operations go through `make_supercell()` wrapper in `structure_viz.py`
- The wrapper does NOT pass `to_unit_cell` parameter

### Coordinate Wrapping After Supercell

**Current Flow**:
1. `canonicalize_structure_in_place()` - wraps to [-1e-4, 0.9999)
2. `make_supercell()` - expands, but may fold back to [0,1) if `to_unit_cell=True`
3. `generate_boundary_atoms()` - expects coordinates in canonical interval

**Risk**: If step 2 folds coordinates, boundary atom generation may miss atoms that should generate images.

---

## Deep Dive: Primitive/Conventional Cell Transformations

### `get_primitive_structure()` Calls

#### 1. `daemon/server.py:1544`
```python
structure = structure.get_primitive_structure()
```

**Missing Parameters**:
- `tolerance` - default likely ~0.01
- May have other parameters depending on pymatgen version

**Effects**:
- **Reorders sites** - site indices may change
- **Changes lattice** - primitive lattice may differ from input
- **May fold coordinates** - coordinates may be wrapped to [0,1)
- **Platform-dependent** - tolerance differences may select different primitive cells

**Recommendation**:
```python
structure = structure.get_primitive_structure(tolerance=0.01)
```

#### 2. Test Files (multiple locations)
- `tests/unit/test_optimade_offline.py:90, 147`
- `tests/unit/test_online_structure_supercell.py:594`
- `tests/integration/test_pipeline_alignment.py:79`
- `tests/integration/test_optimade_live.py:226`

**All missing `tolerance` parameter** - same risks as above.

### `get_conventional_standard_structure()` Calls

#### 1. `structure_viz.py:1102`
```python
analyzer = SpacegroupAnalyzer(structure)
conventional = analyzer.get_conventional_standard_structure()
```

**Missing Parameters**:
- `SpacegroupAnalyzer`: `symprec` (default ~0.01), `angle_tolerance` (default ~5.0)
- `get_conventional_standard_structure()`: may have `tolerance` parameter

**Effects**:
- **Reorders sites** - conventional cell has different site ordering
- **Changes lattice** - conventional lattice differs from primitive
- **May fold coordinates** - coordinates wrapped to [0,1)
- **Platform-dependent** - tolerance differences affect conventional cell choice

**Recommendation**:
```python
analyzer = SpacegroupAnalyzer(structure, symprec=0.01, angle_tolerance=5.0)
conventional = analyzer.get_conventional_standard_structure()
```

---

## Recommendations

### Critical Fixes (High Priority)

1. **Fix `make_supercell()` call** - `structure_viz.py:1076`
   ```python
   # BEFORE:
   supercell.make_supercell(scaling)
   
   # AFTER:
   supercell.make_supercell(scaling, to_unit_cell=False)
   ```
   **Rationale**: Preserves canonicalization contract, prevents double-wrapping

2. **Pin `SpacegroupAnalyzer` tolerances** - `structure_viz.py:1101`, `kpath.py:169`
   ```python
   # BEFORE:
   analyzer = SpacegroupAnalyzer(structure)
   
   # AFTER:
   analyzer = SpacegroupAnalyzer(structure, symprec=0.01, angle_tolerance=5.0)
   ```
   **Rationale**: Ensures consistent symmetry detection across platforms

3. **Pin `get_primitive_structure()` tolerance** - `daemon/server.py:1544` and test files
   ```python
   # BEFORE:
   structure = structure.get_primitive_structure()
   
   # AFTER:
   structure = structure.get_primitive_structure(tolerance=0.01)
   ```
   **Rationale**: Ensures consistent primitive cell selection

### Medium Priority

4. **Document coordinate system assumptions** - `structure_io.py:57, 63`
   - Add comments clarifying when `coords_are_cartesian` is inferred vs explicit
   - Consider validating coordinate system after `from_file()` / `from_dict()`

5. **Pin `HighSymmKpath` parameters** - `kpath.py:180`
   - Document fallback behavior when `path_type` fails
   - Consider pinning tolerance parameters if available

6. **Validate structure after transformations** - All primitive/conventional calls
   - Add assertions that site counts match expectations
   - Log warnings if coordinate ranges change unexpectedly

### Low Priority

7. **Add type hints for pymatgen objects** - All files
   - Improves code clarity and IDE support

8. **Create wrapper functions for common operations** - Consider refactoring
   - Centralize parameter defaults
   - Example: `get_primitive_structure_safe(structure, tolerance=0.01)`

---

## Appendices

### Appendix A: Code Excerpts

#### A.1: Supercell Expansion (structure_viz.py:1049-1078)
```python
def make_supercell(
    structure: PMGStructure,
    scaling: Union[int, Tuple[int, int, int]],
) -> PMGStructure:
    """
    Create a supercell of the structure.
    
    IMPORTANT: This function assumes the input structure has already been canonicalized
    at the primitive stage via canonicalize_structure_in_place(). It does NOT perform
    any canonicalization itself - it only applies integer lattice translations / supercell
    matrices to build the supercell.
    """
    scaling = _normalize_supercell(scaling)
    if scaling == (1, 1, 1):
        return structure.copy()
    
    # Simply create the supercell - no canonicalization here
    # The input structure should already be canonicalized at the primitive stage
    supercell = structure.copy()
    supercell.make_supercell(scaling)  # ⚠️ MISSING to_unit_cell=False
    
    return supercell
```

#### A.2: Conventional Cell (structure_viz.py:1085-1106)
```python
def get_conventional_cell(
    structure: PMGStructure,
) -> PMGStructure:
    """
    Get the conventional/standard cell using pymatgen's SpacegroupAnalyzer.
    """
    try:
        analyzer = SpacegroupAnalyzer(structure)  # ⚠️ MISSING symprec, angle_tolerance
        conventional = analyzer.get_conventional_standard_structure()  # ⚠️ MISSING tolerance
        return conventional
    except Exception as e:
        logger.warning(f"Failed to get conventional cell: {e}. Using original structure.")
        return structure.copy()
```

#### A.3: Primitive Structure (daemon/server.py:1541-1547)
```python
# Get primitive structure (project structures are typically already primitive)
# This ensures online structures match the representation of project structures
try:
    structure = structure.get_primitive_structure()  # ⚠️ MISSING tolerance
    logger_local.debug(f"[ONLINE] Converted to primitive: n_sites={len(structure)}")
except Exception as e:
    logger_local.warning(f"Failed to get primitive structure, using as-is: {e}")
```

#### A.4: K-Path Generation (kpath.py:169-180)
```python
# Get spacegroup info
sga = SpacegroupAnalyzer(structure)  # ⚠️ MISSING symprec, angle_tolerance
spg_symbol = sga.get_space_group_symbol()
spg_number = sga.get_space_group_number()
lattice_type = sga.get_lattice_type()

# Generate k-path based on type - try different methods
kpath = None
kpath_data = None

for ptype in [path_type, "hinuma", "setyawan_curtarolo"]:
    try:
        kpath = HighSymmKpath(structure, path_type=ptype)  # ⚠️ MISSING tolerance params
        # ...
```

### Appendix B: File:Line Reference Summary

**Source Files (Production)**:
- `src/qmatsuite/analysis/structure_viz.py`: 60, 62, 253, 372, 378, 1076, 1101-1102, 1364
- `src/qmatsuite/io/structure_io.py`: 15-17, 57, 63, 91, 104, 143, 160, 174, 184, 253-258, 327
- `src/qmatsuite/calculation/structure_steps.py`: 10
- `src/qmatsuite/analysis/kpath.py`: 15-17, 169-172, 180, 182-187
- `src/qmatsuite/io/online_search.py`: 21-22, 25-28, 97-98, 192, 196, 220, 234, 274-275, 287, 433, 449, 453, 532, 556
- `src/qmatsuite/io/online_cache.py`: 24, 145, 157
- `src/qmatsuite/analysis/parsers.py`: 741-742, 746-747, 753
- `src/qmatsuite/daemon/server.py`: 1544

**Test Files**:
- `tests/unit/test_structure_viz.py`: Multiple Structure() constructors
- `tests/unit/test_optimade_offline.py`: 90, 147
- `tests/unit/test_online_structure_supercell.py`: 594
- `tests/integration/test_pipeline_alignment.py`: 79
- `tests/integration/test_optimade_live.py`: 226

### Appendix C: Default Parameter Values (To Be Verified)

**Note**: These defaults should be verified in the actual pymatgen installation:

1. **`Structure.make_supercell(to_unit_cell=?)`**
   - Likely default: `True` (folds coordinates to [0,1))
   - **Action Required**: Verify and document

2. **`Structure.get_primitive_structure(tolerance=?)`**
   - Likely default: `0.01` (Angstrom)
   - **Action Required**: Verify and pin explicitly

3. **`SpacegroupAnalyzer(symprec=?, angle_tolerance=?)`**
   - Likely defaults: `symprec=0.01`, `angle_tolerance=5.0`
   - **Action Required**: Verify and pin explicitly

4. **`SpacegroupAnalyzer.get_conventional_standard_structure(tolerance=?)`**
   - Likely default: Uses analyzer's `symprec`
   - **Action Required**: Verify behavior

5. **`HighSymmKpath(path_type=?, ...)`**
   - Default `path_type`: Likely `"hinuma"`
   - **Action Required**: Verify tolerance parameters if any

6. **`Structure.from_file(..., coords_are_cartesian=?)`**
   - Default: Inferred from file format
   - **Action Required**: Document format-specific behavior

7. **`Structure(coords_are_cartesian=?)`**
   - Default: `False` (fractional coordinates)
   - **Status**: Usually explicit in code

---

## Verification Checklist

- [ ] Verify `make_supercell()` default `to_unit_cell` value
- [ ] Verify `get_primitive_structure()` default `tolerance` value
- [ ] Verify `SpacegroupAnalyzer` default `symprec` and `angle_tolerance` values
- [ ] Test `to_unit_cell=False` preserves coordinates outside [0,1)
- [ ] Test primitive/conventional transformations with pinned tolerances
- [ ] Verify coordinate system assumptions in `from_file()` / `from_dict()`
- [ ] Test platform consistency (Ubuntu vs macOS) with pinned parameters
- [ ] Document any pymatgen version-specific behavior

---

## Conclusion

The audit identified **4 HIGH-risk calls** that rely on platform-dependent defaults:
1. `make_supercell()` missing `to_unit_cell=False`
2. `SpacegroupAnalyzer()` missing tolerance parameters (2 locations)
3. `get_primitive_structure()` missing `tolerance` parameter (5+ locations)
4. `get_conventional_standard_structure()` missing tolerance parameter

These should be fixed immediately to ensure consistent behavior across platforms. The remaining MED/LOW-risk calls should be addressed as part of ongoing code quality improvements.

**Next Steps**:
1. Verify default parameter values in actual pymatgen installation
2. Apply critical fixes (HIGH priority)
3. Test platform consistency
4. Apply medium-priority fixes
5. Update documentation

