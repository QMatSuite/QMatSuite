# Structure / Visualization / Boundary / Bond Pipeline Audit Report

**Date**: Generated from codebase analysis  
**Task**: Read-only audit of structure lifecycle, canonicalization, boundary repeat, supercell, visualization, and bond computation

---

## 1️⃣ Entry Points & Structure Lifecycle

### A. Project Structure Loading

**Entry Point**: `QMSService.get_structure_vis_data()`  
**File**: `src/qmatsuite/api.py:2243`

**Flow**:
1. **Structure Resolution**: `resolve_structure(project_root, selector)` → `ResolvedResource`
   - File: `src/qmatsuite/api.py` (via import)
   - Returns path to structure file

2. **Structure Loading**: `read_structure(resolved.absolute_path)` → `PMGStructure`
   - File: `src/qmatsuite/io/structure_io.py:30`
   - Supports formats: QE input (`.in`), JSON, CIF, POSCAR, etc.
   - **Fractional coordinates**: NOT assumed canonical at this stage
   - **Canonicalization**: NOT called here

3. **QE Input Parsing** (if format is QE):
   - Function: `structure_from_qe_input(qe_input)`
   - File: `src/qmatsuite/io/structure_io.py:211`
   - Handles `ibrav` rules and coordinate system conversion
   - Creates `PMGStructure` with fractional or Cartesian coords based on `ATOMIC_POSITIONS` option
   - **No canonicalization** at this stage

### B. Online Structure Fetching (OPTIMADE)

**Entry Point**: `_handle_get_structure_vis()` (online path)  
**File**: `src/qmatsuite/daemon/server.py:2548`

**Flow**:
1. **Structure Fetch**: `fetch_structure_from_optimade(base_url, entry_id)`
   - File: `src/qmatsuite/io/online_search.py:331`
   - Fetches from OPTIMADE API
   - Receives Cartesian coordinates from API
   - Creates `PMGStructure` with `coords_are_cartesian=True`
   - **Fractional coordinates**: Computed by pymatgen during Structure construction
   - **No canonicalization** at fetch stage

2. **Primitive Conversion**: `structure.get_primitive_structure()`
   - File: `src/qmatsuite/daemon/server.py:1544`
   - Uses pymatgen's `SpacegroupAnalyzer` to get primitive cell
   - **Fractional coordinates**: May be outside [0,1) after primitive conversion
   - **No canonicalization** at this stage

### C. GUI Import

**Entry Point**: `ImportStructureDialog` component  
**File**: `gui/src/components/dialogs/ImportStructureDialog.tsx:16`

**Flow**:
1. **RPC Call**: `qms.call('import_structure', {project_root, source_file, name})`
   - File: `src/qmatsuite/daemon/server.py` (handler)
   - Calls `QMSService.import_structure()`

2. **Structure Loading**: Uses `read_structure()` (same as project path)
   - **Fractional coordinates**: NOT assumed canonical
   - **Canonicalization**: NOT called during import

### D. CLI Structure Loading

**Entry Point**: `_resolve_structure_input()`  
**File**: `src/qmatsuite/cli/main.py:579`

**Flow**:
- Uses `read_structure()` for file-based structures
- **No canonicalization** at CLI level

---

## 2️⃣ Canonicalization / Wrap / Snap Functions

### A. Core Canonicalization Functions

#### 1. `canonicalize_structure_in_place()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:194`
- **When Called**: 
  - `build_display_atoms()` (line 1314) - main entry point
  - `visualize_structure()` (line 1727) - high-level API
  - `plot_structure_3d()` (line 1517) - matplotlib entry
- **Modifies**: Structure in place (replaces fractional coordinates)
- **Thresholds**: Uses `BOUNDARY_FRAC_TOL = 1e-6` (default eps parameter)
- **Algorithm**: Calls `canonicalize_frac_coords()` for each site

#### 2. `canonicalize_frac_coords()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:237`
- **When Called**: 
  - Only from `canonicalize_structure_in_place()` (line 232)
  - Also from `wrap_fractional_coords()` wrapper (line 328)
- **Modifies**: Returns new array (does not modify input)
- **Thresholds**: 
  - `eps` (default `BOUNDARY_FRAC_TOL = 1e-6`) for integer snapping
  - Integer snapping tolerance: `max(eps * 10.0, 1e-5)` (line 296)
  - Boundary threshold: `0.0101` (hardcoded, line 310)
- **Algorithm**:
  1. Integer snapping: `abs(f - round(f)) < max(eps * 10.0, 1e-5)` → snap to integer
  2. Modulo wrap: `np.mod(result, 1.0)` → wrap into [0, 1)
  3. Boundary snapping near 1.0: `result >= (1.0 - 0.0101)` OR `result > (1.0 - 1e-12)` → snap to 0.0
  4. Boundary snapping near 0.0: `result < 0.0101` OR `result < 1e-12` → snap to 0.0

#### 3. `wrap_fractional_coords()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:337`
- **When Called**: 
  - Wrapper for backward compatibility
  - Calls `canonicalize_frac_coords()` internally
- **Modifies**: Returns new array
- **Thresholds**: Uses `BOUNDARY_FRAC_TOL` (default)

#### 4. `wrap_cartesian_coords()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:353`
- **When Called**: Not found in active code paths (legacy/unused?)
- **Modifies**: Returns new array
- **Algorithm**: Converts to fractional → wraps → converts back to Cartesian

### B. Constants

- **`BOUNDARY_FRAC_TOL`**: `1e-6` (line 146)
  - Used for: integer snapping in `canonicalize_frac_coords()`
  - Used for: boundary detection in `generate_boundary_atoms()`
  - Previously `1e-8`, increased to `1e-6` for Ubuntu compatibility

---

## 3️⃣ Boundary Repeat / Supercell Logic

### A. Boundary Atom Generation

#### `generate_boundary_atoms()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:952`
- **Input Assumption**: Structure is already canonicalized (fractional coords in [0,1))
- **When Called**: 
  - `build_display_atoms()` (lines 1348, 1396, 1446) - when `repeat_boundary=True`
- **Output**: List of `BoundaryAtom` objects (appends to display list)
- **Threshold Logic**: 
  - Uses `tolerance` parameter (default `BOUNDARY_FRAC_TOL = 1e-6`)
  - Boundary detection: `abs(frac[dim]) < tolerance` OR `abs(frac[dim] - 1.0) < tolerance` (line 989)
- **Coordinate Handling**:
  - **Does NOT canonicalize** image atoms (line 1011 comment)
  - Image atoms have fractional coords **outside [0,1)** (line 1020)
  - Uses integer shifts: `+1` for atoms near 0, `-1` for atoms near 1 (lines 998, 1001)
- **Purpose**: Visualization only (adds periodic images for display)

### B. Supercell Expansion

#### `make_supercell()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:1031`
- **Input Assumption**: Structure is already canonicalized (line 1038 comment)
- **When Called**: 
  - `build_display_atoms()` (line 1371) - when mode is "supercell"
- **Output**: New `PMGStructure` object (replaces structure)
- **Coordinate Handling**:
  - **Does NOT canonicalize** (line 1038, 1055)
  - Uses pymatgen's `make_supercell()` internally (line 1058)
  - Supercell atoms may have fractional coords **outside [0,1)** (line 1048)
  - Uses integer lattice translations only
- **Algorithm**: Applies supercell scaling matrix via pymatgen

### C. Display Mode: Box

#### `enumerate_atoms_in_aabb()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:1150` (referenced, not shown in detail)
- **When Called**: `build_display_atoms()` (line 1471) - when mode is "box"
- **Input**: Canonicalized structure + box bounds
- **Output**: List of `DisplayAtom` objects
- **Coordinate Handling**: Enumerates atoms in axis-aligned bounding box
- **Boundary Repeat**: Always disabled for box mode (line 1467)

### D. Display Mode: Conventional

#### `get_conventional_cell()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:1045` (referenced)
- **When Called**: `build_display_atoms()` (line 1418) - when mode is "conventional"
- **Input**: Canonicalized structure
- **Output**: New `PMGStructure` with conventional cell
- **Coordinate Handling**: Uses pymatgen's `SpacegroupAnalyzer.get_conventional_standard_structure()`

---

## 4️⃣ Visualization (structure_viz) Data Flow

### A. Main Entry Point: `build_display_atoms()`

**File**: `src/qmatsuite/analysis/structure_viz.py:1288`

**Call Chain**:
```
QMSService.get_structure_vis_data()
  → QMSService._build_structure_vis_payload()
    → build_display_atoms(structure, params)
```

**Input**:
- `structure`: `PMGStructure` (NOT canonicalized at entry)
- `params`: `DisplayModeParams` (mode, supercell, repeat_boundary, box_bounds)

**Step-by-Step Flow**:

1. **Canonicalization (ONCE, at entry)**:
   - Line 1313: `structure_canon = structure.copy()`
   - Line 1314: `canonicalize_structure_in_place(structure_canon, eps=BOUNDARY_FRAC_TOL)`
   - **This is the ONLY canonicalization point**

2. **Mode-Specific Processing**:

   **Primitive Mode** (line 1319):
   - Uses `structure_canon` directly
   - Creates `DisplayAtom` objects from canonicalized sites
   - If `repeat_boundary=True`: calls `generate_boundary_atoms()` (line 1348)

   **Supercell Mode** (line 1367):
   - Calls `make_supercell(structure_canon, params.supercell)` (line 1371)
   - Creates `DisplayAtom` objects from supercell sites
   - If `repeat_boundary=True`: calls `generate_boundary_atoms()` on supercell (line 1396)

   **Conventional Mode** (line 1415):
   - Calls `get_conventional_cell(structure_canon)` (line 1418)
   - Creates `DisplayAtom` objects from conventional cell
   - If `repeat_boundary=True`: calls `generate_boundary_atoms()` on conventional cell (line 1446)

   **Box Mode** (line 1465):
   - Calls `enumerate_atoms_in_aabb(structure_canon, params.box_bounds)` (line 1471)
   - Creates minimal structure for lattice info only

3. **Output**:
   - `display_atoms`: List of `DisplayAtom` objects (base + boundary images if enabled)
   - `display_structure`: `PMGStructure` object (for lattice info)

### B. Coordinate Consistency Checks

Throughout `build_display_atoms()`, there are verification checks:
- Lines 1328-1334: Verifies `site.coords` matches `lattice.get_cartesian_coords(site.frac_coords)`
- Lines 1351-1356: Verifies boundary atom coords match lattice
- Similar checks for supercell (1378-1383) and conventional (1428-1433) modes

### C. High-Level API: `visualize_structure()`

**File**: `src/qmatsuite/analysis/structure_viz.py:1727`

**Flow**:
1. Calls `canonicalize_structure_in_place()` (line 1747)
2. Calls `build_display_atoms()` internally
3. Creates matplotlib visualization

### D. Matplotlib API: `plot_structure_3d()`

**File**: `src/qmatsuite/analysis/structure_viz.py:1517`

**Flow**:
1. Calls `canonicalize_structure_in_place()` (line 1292)
2. Calls `build_display_atoms()` internally
3. Creates 3D plot

---

## 5️⃣ Bond Computation Interface

### A. Public API: `build_bonds()`

**File**: `src/qmatsuite/analysis/structure_viz.py:754`

**When Called**:
- `QMSService._build_structure_vis_payload()` (line 1982)
- `detect_bonds()` (line 909) - legacy wrapper

**Input**:
- `display_atoms`: List of `DisplayAtom` objects OR numpy array of coordinates
- Optional: `species` (if array input)
- Optional: `lattice` (ignored, kept for compatibility)

**Assumptions**:
- **Coordinates are already prepared** (canonicalized, supercell expanded, boundary images added)
- **Does NOT canonicalize** (pure geometric function)
- **Does NOT wrap coordinates**

**Algorithm**:
1. Extracts Cartesian coordinates from `DisplayAtom` objects
2. Extracts species/element symbols
3. Resolves radii map (covalent radii)
4. Calls `_build_bonds()` internally

### B. Internal Implementation: `_build_bonds()`

**File**: `src/qmatsuite/analysis/structure_viz.py:660`

**Algorithm Selection**:
- Default: `build_bonds_cell_list()` (cell-list neighbor search)
- Fallback: `build_bonds_bruteforce()` (if `use_bruteforce=True` or debug flag)

**Precondition** (line 676):
- Input atoms are **already prepared** (canonicalized, supercell, boundary images)
- **Does NOT canonicalize, wrap, or modify coordinates**

### C. Bond Detection Algorithms

#### 1. `build_bonds_bruteforce()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:455`
- **Algorithm**: O(N²) pairwise distance check
- **Bond Criterion**: `distance <= min(max_cutoff, (r_i + r_j) * max_factor + tolerance)`
- **Default Parameters**:
  - `max_factor = 1.2`
  - `tolerance = 0.3` Å
  - `max_cutoff = 3.5` Å
- **No coordinate modification**: Pure Euclidean distance on provided coordinates

#### 2. `build_bonds_cell_list()`
- **File**: `src/qmatsuite/analysis/structure_viz.py:530`
- **Algorithm**: Cell-list (neighbor-grid) acceleration
- **Same bond criterion** as brute-force
- **Guaranteed to match brute-force results** (validated in tests)
- **No coordinate modification**: Pure geometric function

#### 3. `detect_bonds()` (Legacy Wrapper)
- **File**: `src/qmatsuite/analysis/structure_viz.py:888`
- **Input**: `PMGStructure` object
- **Assumption**: Structure is already canonicalized (line 879)
- **Does NOT canonicalize** (line 884)
- **Calls**: `build_bonds()` internally

### D. Bond Computation in Visualization Pipeline

**Call Site**: `QMSService._build_structure_vis_payload()` (line 1982)

**Flow**:
```
build_display_atoms() → returns (display_atoms_list, display_structure)
  ↓
build_bonds(display_atoms_list) → returns List[Bond]
  ↓
Bonds serialized to JSON payload
```

**Key Point**: Bonds are computed on the **exact same atom list** that is rendered (display_atoms_list), which includes:
- Base atoms (from primitive/supercell/conventional/box)
- Boundary image atoms (if `repeat_boundary=True`)

---

## 6️⃣ Invariants & Potential Risk Points

### A. Single-Point Canonicalization Contract

**Design Rule** (documented in code, line 149-191):
- Canonicalization happens **exactly once** at entry point (`build_display_atoms()`)
- **Forbidden**: Internal helpers must NOT canonicalize

**Risk Points**:

1. **Double Canonicalization Risk**:
   - If `canonicalize_structure_in_place()` is called before `build_display_atoms()`, coordinates will be canonicalized twice
   - **Location**: Any code path that calls canonicalization before passing to `build_display_atoms()`
   - **Current Status**: No evidence of this in active code paths

2. **Boundary Atom Canonicalization Risk**:
   - `generate_boundary_atoms()` explicitly does NOT canonicalize image atoms (line 1011)
   - **Risk**: If boundary atoms are accidentally canonicalized, they would fold back into [0,1) and overlap with base atoms
   - **Current Status**: Protected by design (no canonicalization in `generate_boundary_atoms()`)

3. **Supercell Canonicalization Risk**:
   - `make_supercell()` assumes input is canonicalized but does NOT canonicalize output
   - **Risk**: If supercell is canonicalized after creation, atoms at boundaries would be incorrectly wrapped
   - **Current Status**: Protected by design (no canonicalization in `make_supercell()`)

### B. Threshold Logic Risks

1. **Integer Snapping Tolerance**:
   - Current: `max(eps * 10.0, 1e-5)` (line 296)
   - **Risk**: Platform-specific floating point differences (Ubuntu vs Mac) may cause values near integers to not be snapped
   - **Mitigation**: Tolerance increased from `1e-6` to `1e-5` for Ubuntu compatibility

2. **Boundary Detection Tolerance**:
   - Current: `BOUNDARY_FRAC_TOL = 1e-6` (line 146)
   - **Risk**: Atoms very close to boundaries (but not within tolerance) may not generate boundary images
   - **Location**: `generate_boundary_atoms()` line 989

3. **Boundary Snapping Threshold**:
   - Current: `0.0101` (hardcoded, line 310)
   - **Risk**: Values between `0.0101` and `0.01` may not be snapped to 0.0, causing inconsistent supercell construction
   - **Location**: `canonicalize_frac_coords()` lines 318, 324

### C. Coordinate System Consistency Risks

1. **Lattice Changes**:
   - Supercell expansion changes lattice (line 1371)
   - Conventional cell transformation changes lattice (line 1418)
   - **Risk**: Cartesian coordinates computed from old lattice may not match new lattice
   - **Mitigation**: Code verifies consistency (lines 1328-1334, 1378-1383, 1428-1433)

2. **Fractional vs Cartesian Mismatch**:
   - `DisplayAtom` stores both `cart_coords` and `frac_coords`
   - **Risk**: If one is modified without updating the other, inconsistency occurs
   - **Current Status**: Both computed from same source (site.frac_coords via lattice)

### D. Boundary Repeat Application Risks

1. **Multiple Boundary Repeat Calls**:
   - `generate_boundary_atoms()` can be called multiple times (once per display mode)
   - **Risk**: If called on already-expanded structure (supercell), boundary images may be duplicated
   - **Current Status**: Each call is on the appropriate structure (primitive, supercell, or conventional)

2. **Boundary Repeat in Box Mode**:
   - Box mode explicitly disables `repeat_boundary` (line 1467)
   - **Risk**: If boundary repeat is enabled for box mode, it would be ignored (not an error, but may confuse users)

### E. Implicit Assumptions

1. **Structure is Primitive**:
   - Online structures: Explicitly converted to primitive (line 1544)
   - Project structures: Assumed to be primitive (no conversion)
   - **Risk**: If project structure is not primitive, canonicalization may behave differently

2. **Fractional Coordinates in [0,1)**:
   - After canonicalization, fractional coords are in [0,1)
   - **Assumption**: All downstream code assumes this
   - **Risk**: Supercell atoms have coords outside [0,1) - this is intentional and correct

3. **Bond Computation on Display Atoms**:
   - Bonds are computed on `display_atoms_list` (includes boundary images if enabled)
   - **Assumption**: Display atoms are the source of truth for bond computation
   - **Risk**: If display atoms are modified after bond computation, bonds become stale

### F. Platform-Specific Risks

1. **Floating Point Precision**:
   - Ubuntu vs Mac may produce different results for `np.mod()` and `np.round()`
   - **Location**: `canonicalize_frac_coords()` (lines 290, 293)
   - **Mitigation**: Increased integer snapping tolerance and added checks for values very close to 1.0/0.0

2. **Coordinate Transformation Precision**:
   - Fractional ↔ Cartesian conversions may accumulate errors
   - **Location**: Throughout `build_display_atoms()` when computing `cart_from_lattice`
   - **Mitigation**: Consistency checks with `atol=1e-6` tolerance

---

## 7️⃣ Summary of Data Flow

### Complete Pipeline (Project Structure)

```
1. File Load
   read_structure(filepath) → PMGStructure
   [Fractional coords: NOT canonicalized]

2. Service Entry
   QMSService.get_structure_vis_data()
   → read_structure() → PMGStructure
   [Still NOT canonicalized]

3. Shared Builder
   QMSService._build_structure_vis_payload()
   → build_display_atoms(structure, params)
   [CANONICALIZATION HAPPENS HERE - ONCE]
   → canonicalize_structure_in_place(structure_canon)
   → canonicalize_frac_coords() for each site
   [Fractional coords: NOW canonicalized to [0,1)]

4. Display Atom Building
   build_display_atoms():
   - Mode-specific processing (primitive/supercell/conventional/box)
   - make_supercell() [NO canonicalization]
   - generate_boundary_atoms() [NO canonicalization of images]
   → display_atoms_list (DisplayAtom objects)

5. Bond Computation
   build_bonds(display_atoms_list)
   → _build_bonds() → build_bonds_cell_list()
   [Pure geometric function, NO coordinate modification]
   → List[Bond]

6. Serialization
   → JSON payload with atoms, bonds, lattice info
```

### Complete Pipeline (Online Structure)

```
1. OPTIMADE Fetch
   fetch_structure_from_optimade() → PMGStructure (Cartesian)
   [Fractional coords: Computed by pymatgen, NOT canonicalized]

2. Primitive Conversion
   structure.get_primitive_structure()
   [Fractional coords: May be outside [0,1), NOT canonicalized]

3. Service Entry
   _handle_get_structure_vis() (online path)
   → QMSService._build_structure_vis_payload()
   [Same as project path from here]
```

---

## 8️⃣ Key Design Contracts

### Canonicalization Contract

- **Single Point**: Canonicalization happens exactly once at `build_display_atoms()` entry
- **Forbidden**: `detect_bonds()`, `make_supercell()`, `generate_boundary_atoms()`, bond functions must NOT canonicalize
- **Purpose**: Ensures stable bond counts and correct visualization

### Bond Detection Contract

- **Pure Geometric Functions**: Bond functions consume prepared geometry, never modify it
- **Precondition**: Input atoms are already canonicalized, supercell expanded, boundary images added
- **No Coordinate Modification**: Bond functions only compute distances, never wrap or snap

### Boundary Repeat Contract

- **Visualization Only**: Boundary repeat adds image atoms for display
- **Image Atoms**: Have fractional coords outside [0,1) and are NOT canonicalized
- **Bond Computation**: Bonds are computed on display atoms (base + images if enabled)

### Supercell Contract

- **Input Assumption**: Supercell input structure is already canonicalized
- **Output**: Supercell atoms may have fractional coords outside [0,1) (intentional)
- **No Canonicalization**: Supercell expansion does NOT canonicalize

---

**End of Audit Report**

