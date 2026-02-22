# Pipeline Dataflow Analysis: p4vasp & XCrySDen Deep Dive

**Purpose:** Extract implementable engineering specifications from source code analysis of p4vasp and XCrySDen, focusing on data pipelines, coordinate systems, units, ordering, and performance strategies.

**Compliance:** No third-party code snippets; only file paths, function/class names, conceptual behavior descriptions (1-2 sentences), and evidence pointers.

---

## 1. Pipeline Answers (User Physical Workflows)

### A1) Bands / DOS / PDOS / Fatband Visualization

**What We Need to Implement:**
- Parse VASP EIGENVAL/DOSCAR or vasprun.xml for bands/DOS data
- Compute k-path distances from k-point list and reciprocal basis
- Handle Fermi energy alignment (shift to 0) with spin channel awareness
- Extract orbital/atom projections for PDOS and fatband weights
- Organize data by spin channels and orbital indices

**Data Source → Internal Representation → Selection → Output:**

**Evidence from p4vasp (ElectronicApplet.py, SystemPM.py):**

1. **Bands Data Source:**
   - Primary: `vasprun.xml` → `EIGENVALUES_L` (lazy Array) from `<eigenvalues>` XML node
   - Fallback: Direct parsing of `EIGENVAL` file (not implemented in XMLSystemPM, only referenced in error handling)
   - Structure: `Array[spin][kpoint][band][energy]` where energy is `(value, occupancy)`
   - Projected eigenvalues: `PROJECTED_EIGENVALUES_L` → `Array[spin][kpoint][band][ion][orbital]`

2. **Fermi Energy (`E_FERMI`):**
   - From XML: `<dos>/<i name="efermi">` → float value
   - Fallback: Line 6 of `DOSCAR` file → `float(split(line)[3])`
   - Default: 0.0 if not found (see `ElectronicApplet.updateDataGen` line 494-498)
   - **Behavior:** Always subtracted from eigenvalues (`ev[i][k][j][0]-e`) before plotting

3. **k-Path Distance Calculation:**
   - Source: `KPOINT_LIST` (reciprocal fractional coordinates)
   - Uses `struct.rbasis` (reciprocal basis vectors) from `struct.updateRecipBasis()`
   - Distance: Cartesian distance between consecutive k-points in reciprocal space
   - Formula: `kk[i-1] * rbasis → k0, kk[i] * rbasis → k1, dist = |k1 - k0|`
   - Evidence: `ElectronicApplet.updateKpointsGen` lines 433-441

4. **High-Symmetry Points:**
   - Detected from `kdiv = KPOINT_DIVISIONS` (e.g., 4×4×4 mesh)
   - Vertical lines drawn at k-division boundaries (where `k % kdiv == 0`)
   - Evidence: `ElectronicApplet.updateKpointsGen` lines 432, 443

5. **PDOS / Fatband Projection:**
   - Data: `PROJECTED_EIGENVALUES_L` → `[spin][k][band][ion][orbital]`
   - Selection: User selects atoms (`selection`) and orbitals (`orbital` list)
   - Weight calculation: Sum over selected ions and orbital indices
   - For phases (LORBIT=12): `w += sdata[ion][o]**2` (squared projection)
   - For magnitudes: `w += abs(sdata[ion][o])` (absolute projection)
   - Evidence: `ElectronicApplet.updateEigenvaluesGen` lines 222-232

6. **DOS Pipeline:**
   - Data: `TOTAL_DOS` → `Array[gridpoints, spin]` with fields `[energy, total, integrated]`
   - From XML: `<dos>/<total>/<array>` → fastflag=1 parsing
   - Fallback: `readDOSCAR()` function (line 151-183 in SystemPM.py)
   - Energy axis: `data[0][i][0]` (first field)
   - DOS values: `data[0][i][1]` (second field)
   - **Fermi shift:** All DOS energies shifted: `map(lambda x,e=e:(x[0]-e, x[1]), tdos[0])`
   - Spin channels: Separate arrays for spin-up (`tdos[0]`) and spin-down (`tdos[1]`, if present)
   - Evidence: `ElectronicApplet.updateDataGen` lines 512-522

7. **Partial DOS:**
   - Data: `PARTIAL_DOS_L` → `Array[ion][spin][energy][orbital]`
   - Orbital indexing: Field names map to indices via `data.fieldIndex(orbital_name)`
   - Aggregation: Sum over selected ions, spins, and orbital indices
   - Energy shift: Same as total DOS (`data[0][0][i][0]-e`)
   - Evidence: `ElectronicApplet.updateDosGen` lines 296-307

**QMatSuite LineArtifact Contract v1:**

```python
@dataclass
class LineArtifact(BaseArtifact):
    """1D line data: bands, DOS, SCF convergence, etc."""
    kind: ArtifactKind = ArtifactKind.LINE
    
    # For bands:
    k_distances: Optional[np.ndarray] = None  # [n_kpoints] float64, cumulative distance
    energies: Optional[np.ndarray] = None     # [n_spins, n_kpoints, n_bands] or [n_kpoints, n_bands]
    high_symmetry_points: Optional[List[Tuple[float, str]]] = None  # [(distance, label)]
    
    # For DOS/PDOS:
    energy_axis: Optional[np.ndarray] = None  # [n_points] float64, already shifted by E_Fermi
    dos_values: Optional[np.ndarray] = None   # [n_spins, n_points] or [n_points] float64
    
    # Projection weights (fatband):
    projection_weights: Optional[np.ndarray] = None  # [n_spins, n_kpoints, n_bands] float64
    
    # Metadata:
    fermi_energy: float = 0.0  # Original Ef from source (before shift)
    fermi_shift_applied: bool = True  # Whether energies are relative to Ef
    spin_channels: List[str] = field(default_factory=lambda: ["total"])  # ["total"] or ["up", "down"]
    orbital_indices: Optional[List[int]] = None  # Selected orbital field indices
    atom_indices: Optional[List[int]] = None     # Selected atom indices
    
    # Units:
    energy_units: str = "eV"  # Must be explicit
    distance_units: str = "Å⁻¹"  # For k-path (reciprocal space distance)
```

**Missing Information & Validation:**
- How to detect spin-polarized vs non-spin-polarized from EIGENVAL header? (Check ISPIN or data dimensions)
- How to handle LORBIT=12 (complex projections) vs LORBIT=11 (real)? (Check PARAMETERS dict)
- Validation: Verify `len(energies) == len(k_distances)` and `high_symmetry_points` within range

---

### A2) Charge Density / Spin Density / Partial Charge / ELF / Local Potential

**What We Need to Implement:**
- Parse VASP volumetric files (CHGCAR, ELFCAR, LOCPOT, PARCHG) with embedded structure
- Extract grid metadata: dimensions, origin (implicit from structure), lattice vectors, data ordering
- Handle multi-channel data: spin up/down (separate files or single file with structure)
- Support derived quantities: up-down difference, orbital summation, energy window selection
- Track units and coordinate system (real-space vs reciprocal-space)

**Evidence from p4vasp (Chgcar.cpp, SystemPM.py):**

1. **Grid Metadata:**
   - Structure embedded: POSCAR format header in CHGCAR/ELFCAR/LOCPOT
   - Grid dimensions: Line after structure header → `nx ny nz` (three integers)
   - Data layout: `data[i + (j + k*ny)*nx]` (C-style row-major, k-fastest)
   - Lattice vectors: From `structure.basis1/2/3` (3×3 float64 in Ångström)
   - **Origin:** Implicit at (0,0,0) in fractional coordinates (grid covers unit cell)
   - Evidence: `Chgcar.read()` lines 191-238

2. **Units:**
   - Length: Ångström (from Structure.basis vectors)
   - **No explicit unit conversion:** p4vasp assumes Å for display
   - Charge density: Electrons per voxel (not normalized by voxel volume)
   - Evidence: `Chgcar.sumElectrons()` returns `N/(nx*ny*nz)` (average per voxel)

3. **Multi-Channel Handling:**
   - CHGCAR: Single channel (total charge)
   - CHGCAR_spin / PARCHG: Separate files for spin channels or partial charges
   - No internal multi-component array: p4vasp loads separate Chgcar objects
   - Evidence: `SystemPM.getChargeFile()` loads single file → single Chgcar object

4. **Derived Quantities:**
   - `Chgcar.subtractChgcar()`: Element-wise subtraction (e.g., up - down)
   - No built-in orbital summation: Must load multiple PARCHG files and sum manually
   - Evidence: `Chgcar.subtractChgcar()` lines 90-118

5. **Plane Extraction:**
   - `Chgcar.getPlaneX/Y/Z(n)`: Extracts 2D slice as FArray2D
   - Statistics per plane: `calculatePlaneStatisticsX/Y/Z()` → min/max/avg/variance
   - Evidence: `ChgcarStatisticsLateList` in SystemPM.py lines 248-273

6. **Periodic Boundary Conditions:**
   - `Chgcar.get(i,j,k)`: Automatic wrapping via modulo (`i %= nx`, `j %= ny`, `k %= nz`)
   - `Chgcar.getRaw(i,j,k)`: No wrapping (throws if out of bounds)
   - Critical for supercell tiling and gradient calculations
   - Evidence: `Chgcar.get()` lines 358-372

7. **Downsampling:**
   - `Chgcar.downSampleByFactors(x,y,z)`: Blocks average over x×y×z voxel blocks
   - Uses `getRaw()` for source data (no wrapping during block extraction)
   - Stores sum (not average) in downsampled array
   - Evidence: `Chgcar.downSampleByFactors()` lines 303-356

**QMatSuite VolumeMetadata Contract v1:**

```python
@dataclass
class VolumeMetadata:
    """Metadata for volumetric data (charge density, potential, etc.)"""
    # Grid shape:
    grid_shape: Tuple[int, int, int]  # (nx, ny, nz) - MUST match binary data
    
    # Coordinate system:
    coordinate_system: str  # "real-space" or "reciprocal-space" (k-space)
    origin: np.ndarray  # [3] float64, Cartesian coordinates in Å
    grid_vectors: np.ndarray  # [3, 3] float64, defines grid cell in Cartesian Å
    # Note: grid_vectors[i] = (vector for i-th grid direction)
    # For real-space: typically aligned with lattice vectors but may differ
    # For k-space: reciprocal lattice vectors
    
    # Lattice (for structure overlay):
    lattice_vectors: Optional[np.ndarray] = None  # [3, 3] float64, unit cell in Å
    # Note: If None, use grid_vectors as lattice (typical for CHGCAR)
    
    # Data ordering:
    data_order: str  # "k-fastest" (C-style, k varies fastest) or "i-fastest" (Fortran-style)
    # MUST be explicit to avoid silent wrong rendering
    
    # Units:
    length_units: str = "Å"  # Must be explicit
    value_units: str = "e/voxel"  # "e/voxel", "eV", "dimensionless" (for ELF), etc.
    value_normalized: bool = False  # Whether values are normalized by voxel volume
    
    # Multi-channel:
    n_channels: int = 1  # Number of data channels (spin, orbital, etc.)
    channel_names: List[str] = field(default_factory=lambda: ["total"])  # ["total"], ["up", "down"], etc.
    channel_indices: Optional[Dict[str, int]] = None  # {"up": 0, "down": 1} if multi-component
    
    # Binary cache:
    binary_path: Path  # Path to .npy file with shape (nx, ny, nz) or (n_channels, nx, ny, nz)
    binary_format: str = "numpy"  # "numpy" or "zarr" (future)
    preview_path: Optional[Path] = None  # Downsampled preview binary
    
    # Value range (lazy computed, cached):
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_mean: Optional[float] = None
    
    # Structure (optional, for overlay):
    structure_path: Optional[Path] = None  # Path to structure file if separate
    structure_embedded: bool = True  # True if structure in same file (CHGCAR/XSF)
```

**From p4vasp to QMatSuite Mapping:**
- `Chgcar.nx/ny/nz` → `grid_shape`
- `Chgcar.structure.basis1/2/3` → `lattice_vectors` (also used as `grid_vectors` for CHGCAR)
- `Chgcar.data[i+(j+k*ny)*nx]` → `data_order="k-fastest"` (C-style)
- `Chgcar.get()` wrapping → Implement `get(i,j,k, wrap=True)` in VolumeArtifact
- `Chgcar.downSampleByFactors()` → Generate preview with 4× downsampling

**Missing Information & Validation:**
- How to detect spin-polarized CHGCAR? (Check if CHGCAR_spin exists or parse ISPIN from OUTCAR)
- How to handle PARCHG with band/energy window labels? (Filename convention: `PARCHG.nnn.band`)
- Validation: Verify `grid_shape` matches binary file size; check `grid_vectors` orthogonality sanity

---

### A3) MLWF (±iso) / Wannier Centers / Fermi Surface (BXSF)

**What We Need to Implement:**
- Parse XSF files for MLWF isosurfaces with multiple DATAGRID blocks (positive/negative iso)
- Parse BXSF files for Fermi surface with multi-band support and lazy band loading
- Extract Wannier centers/spreads from Wannier90 .wout output
- Handle reciprocal cell geometry and optional Brillouin Zone clipping
- Support energy shift (Fermi level alignment) and band selection UI

**Evidence from XCrySDen (readstrf.c, datagrid.c, fs.c, xcReadXSF.c):**

1. **XSF Format Variants:**
   - Structure block: `CRYSTAL` (periodic) or `ATOMS` (molecular)
   - Lattice vectors: `PRIMVEC` (3×3) or `CONVCOORD` (conventional cell)
   - Coordinates: `PRIMCOORD` with format `natoms flag` (1=Cartesian, 0=fractional)
   - Evidence: `readstrf.c` handles both variants with keyword matching

2. **DATAGRID3D Block:**
   - Keywords: `BEGIN_BLOCK_DATAGRID3D`, `BEGIN_DATAGRID_3D` (or `DATAGRID_3D_<name>`)
   - Grid header: `nx ny nz` (three integers)
   - Origin: `ox oy oz` (three floats, Cartesian Å)
   - Vectors: `v1x v1y v1z`, `v2x v2y v2z`, `v3x v3y v3z` (defines grid cell in Cartesian Å)
   - Data: `nx*ny*nz` floats, 6 per line
   - **Multiple subgrids:** Same dimensions/origin/vectors, only data differs (e.g., spin-up/down)
   - Evidence: `datagrid.c ReadDataGrid()` lines 140-224

3. **Data Ordering (XSF):**
   - Reading loop: `for k in nz: for j in ny: for i in nx` (k-fastest)
   - Writing to binary: `fwrite(&value, sizeof(float), 1, gridFP)` immediately after parsing
   - Evidence: `datagrid.c ReadDataGrid()` lines 209-218

4. **±iso Semantic:**
   - Not a file format feature: UI choice to render two isosurfaces at `+iso` and `-iso` values
   - Default strategy: For orbitals/MLWF, show both positive and negative lobes
   - Evidence: No format-level support; UI renders two separate isosurface objects

5. **BXSF Format (Fermi Surface):**
   - Header: `BEGIN_BLOCK_BANDGRID3D` (or `BEGIN_BLOCK_BANDGRID_3D`)
   - Grid: `nband` (int), `nx ny nz` (three ints), `kx0 ky0 kz0` (origin in k-space)
   - Vectors: `k1x k1y k1z`, `k2x k2y k2z`, `k3x k3y k3z` (reciprocal vectors in k-space)
   - Per band: `BAND: <index>` followed by `nx*ny*nz` floats (same order as XSF: k-fastest)
   - Evidence: `datagrid.c ReadBandGrid()` lines 229-325

6. **Band Selection & Lazy Loading:**
   - File positions stored: `grid->band_fpos[subindex][band_index]` (ftell before each band data)
   - Only selected bands loaded: `fsReadBand()` seeks to stored position and reads single band
   - Evidence: `datagrid.c ReadBandGrid()` line 293, `fs.c` lazy loading pattern

7. **Energy Shift (Fermi Surface):**
   - Default: E=0 assumed as Fermi level (no explicit Ef in BXSF format)
   - User can set offset: UI input field for "energy shift" (adds to all band values)
   - Isosurface extraction: `band_data == (isolevel - energy_shift)` where isolevel typically 0
   - Evidence: XCrySDen UI (Tcl/FS_Main.tcl) has energy input field, default 0.0

8. **Reciprocal Cell & BZ Clipping:**
   - Reciprocal vectors: From BXSF header (k-space vectors)
   - BZ clipping: Optional (not required for basic display)
   - Implementation: `CropBz()` clips isosurface triangles outside Wigner-Seitz cell
   - Default: Off (shows full grid), user can enable "Clip to BZ"
   - Evidence: `fs.c CropBz()` lines 201-218, UI toggle in FS_Main.tcl

9. **Multi-Band Display:**
   - UI: Tab-based interface, one tab per selected band
   - Rendering: Each band rendered as separate isosurface with distinct color
   - Evidence: FS_Main.tcl tab structure, per-band color cycling

**QMatSuite FermiSurfaceArtifact Contract v1:**

```python
@dataclass
class FermiSurfaceArtifact(VolumeArtifact):
    """Fermi surface data (k-space volumetric with multi-band support)"""
    kind: ArtifactKind = ArtifactKind.VOLUME
    coordinate_system: str = "reciprocal-space"  # Always k-space for Fermi surface
    
    # Multi-band:
    n_bands: int  # Total number of bands in file
    band_indices: List[int]  # Band indices available (may not be consecutive)
    band_file_positions: Dict[int, int]  # {band_index: file_position} for lazy loading
    
    # Fermi energy:
    fermi_energy: Optional[float] = None  # If None, assume E=0 as Fermi level
    energy_shift: float = 0.0  # User-adjustable offset (default 0)
    
    # Reciprocal cell:
    reciprocal_vectors: np.ndarray  # [3, 3] float64, k-space basis in Å⁻¹
    brillouin_zone_clip: bool = False  # Whether to clip to first BZ
    
    # Band selection (for rendering):
    selected_bands: List[int] = field(default_factory=list)  # Bands to display
    per_band_colors: Dict[int, Tuple[float, float, float]] = field(default_factory=dict)
    
    # Binary cache:
    # Override: binary_path stores metadata only; band data loaded on-demand
    band_binary_paths: Dict[int, Path] = field(default_factory=dict)  # {band_index: .npy path}
```

**QMatSuite WannierProperties Contract v1:**

```python
@dataclass
class WannierPropertiesArtifact(BaseArtifact):
    """Wannier center positions and spreads"""
    kind: ArtifactKind = ArtifactKind.PROPERTIES
    
    centers: np.ndarray  # [n_wannier, 3] float64, Cartesian coordinates in Å
    spreads: np.ndarray  # [n_wannier] float64, spread in Å²
    unit_cell_centers: Optional[np.ndarray] = None  # [n_wannier, 3] float64, fractional coords
    
    # Metadata:
    n_wannier: int
    lattice_vectors: Optional[np.ndarray] = None  # [3, 3] float64, for fractional conversion
```

**Missing Information & Validation:**
- How to parse Wannier90 .wout for centers/spreads? (Text parsing: "Final State" section, format varies)
- Validation: Verify `band_indices` match file structure; check `reciprocal_vectors` orthogonality

---

### A4) Planar Average / Line Profile

**What We Need to Implement:**
- Extract 2D slice (plane) from 3D volume along specified axis
- Compute statistics per plane: min/max/mean/integrated (sum over plane)
- Compute line profile along arbitrary path (interpolation required)
- Handle units and normalization (voxel volume, per-unit-length)

**Evidence from p4vasp (Chgcar.cpp, SystemPM.py, LocalPotentialApplet.py):**

1. **Plane Extraction:**
   - `Chgcar.getPlaneX/Y/Z(n)`: Returns FArray2D (2D float array)
   - For X-plane: Extract slice at x=n, all y and z values
   - For Y-plane: Extract slice at y=n, all x and z values
   - For Z-plane: Extract slice at z=n, all x and y values
   - Evidence: Referenced in `ChgcarStatisticsLateList` (SystemPM.py lines 248-273)

2. **Plane Statistics:**
   - `Chgcar.calculatePlaneStatisticsX/Y/Z(n)`: Computes min/max/avg/variance for plane
   - Uses `getRaw()` to iterate over all points in plane
   - Evidence: `Chgcar.calculatePlaneStatisticsX()` lines 731-764 (for X-plane)

3. **Planar Average (1D profile):**
   - Not directly implemented in Chgcar, but pattern:
   - For each plane index n, compute average over plane: `avg = sum(plane) / (ny*nz)`
   - Result: 1D array of length nx (for X-direction average)
   - Evidence: `LocalPotentialApplet` references plane statistics but doesn't show full implementation

4. **Units & Normalization:**
   - Raw values: Per-voxel (not normalized by voxel volume)
   - Planar average: Average per voxel in plane (units: same as raw data)
   - If normalized by volume: Multiply by `voxel_volume = det(grid_vectors) / (nx*ny*nz)`
   - Evidence: `Chgcar.sumElectrons()` returns `N/(nx*ny*nz)` (not multiplied by volume)

5. **Line Profile:**
   - Not implemented in p4vasp (no arbitrary path interpolation)
   - Would require: 3D interpolation along path (trilinear or higher-order)

**QMatSuite MapArtifact Contract v1 (for 2D slices):**

```python
@dataclass
class MapArtifact(BaseArtifact):
    """2D map data: k-slice, plane slice, planar average"""
    kind: ArtifactKind = ArtifactKind.MAP
    
    # 2D grid:
    grid_shape: Tuple[int, int]  # (nx, ny) for 2D slice
    data: np.ndarray  # [nx, ny] float64 (or path to binary)
    
    # Coordinate system:
    origin: np.ndarray  # [3] float64, Cartesian origin of 2D plane
    plane_vectors: np.ndarray  # [2, 3] float64, defines 2D plane in 3D space
    normal_vector: Optional[np.ndarray] = None  # [3] float64, plane normal (for 3D overlay)
    
    # For planar average (1D profile):
    is_1d_profile: bool = False  # True if this is averaged over one dimension
    profile_axis: Optional[int] = None  # 0=X, 1=Y, 2=Z (if 1D profile)
    profile_values: Optional[np.ndarray] = None  # [n_points] float64 (if 1D profile)
    
    # Metadata:
    source_volume: Optional[str] = None  # Reference to source VolumeArtifact
    slice_position: Optional[float] = None  # Position along normal (for 3D slicing)
    
    # Units:
    length_units: str = "Å"
    value_units: str = "e/voxel"  # Inherited from source volume
```

**QMatSuite LineArtifact Extension (for line profiles):**

```python
# Add to LineArtifact:
line_profile_path: Optional[np.ndarray] = None  # [n_points, 3] float64, 3D path coordinates
line_profile_values: Optional[np.ndarray] = None  # [n_points] float64, interpolated values
interpolation_method: str = "trilinear"  # "trilinear", "cubic", etc.
```

**Missing Information & Validation:**
- How to compute voxel volume for normalization? (`voxel_vol = abs(det(grid_vectors)) / prod(grid_shape)`)
- Validation: Verify `plane_vectors` span 2D space (rank=2); check `slice_position` within volume bounds

---

## 2. Evidence Pointers

### p4vasp Evidence:

1. **Bands/Eigenvalues:**
   - File: `lib/p4vasp/applet/ElectronicApplet.py`
   - Function: `updateEigenvaluesGen()` (lines 451-487)
   - Observation: Fermi energy subtracted from all eigenvalues before plotting
   - Function: `updateKpointsGen()` (lines 406-449)
   - Observation: k-path distance computed from reciprocal basis vectors

2. **DOS:**
   - File: `lib/p4vasp/SystemPM.py`
   - Function: `readDOSCAR()` (lines 151-183)
   - Observation: DOS data structure `Array[gridpoints, spin]` with fields `[energy, total, integrated]`
   - File: `lib/p4vasp/applet/ElectronicApplet.py`
   - Function: `updateDataGen()` (lines 512-522)
   - Observation: DOS energies shifted by Fermi energy, spin channels separated

3. **Volume Data:**
   - File: `src/Chgcar.cpp`
   - Function: `read()` (lines 168-257)
   - Observation: Grid dimensions read after structure header, data in C-style `data[i+(j+k*ny)*nx]`
   - Function: `get()` (lines 358-372)
   - Observation: Periodic wrapping via modulo arithmetic
   - Function: `downSampleByFactors()` (lines 303-356)
   - Observation: Block averaging (sum, not average) for downsampling

4. **Plane Statistics:**
   - File: `lib/p4vasp/SystemPM.py`
   - Class: `ChgcarStatisticsLateList` (lines 248-273)
   - Observation: Lazy evaluation of plane statistics (min/max/avg/variance)

### XCrySDen Evidence:

1. **XSF Parsing:**
   - File: `C/datagrid.c`
   - Function: `ReadDataGrid()` (lines 140-224)
   - Observation: Data reading order `for k in nz: for j in ny: for i in nx` (k-fastest)
   - Observation: Immediate binary write after text parsing (`fwrite(&value, sizeof(float), 1, gridFP)`)

2. **BXSF Parsing:**
   - File: `C/datagrid.c`
   - Function: `ReadBandGrid()` (lines 229-325)
   - Observation: File positions stored per band (`ftell(gridFP)` before each band data block)
   - Observation: Band indices stored in `grid->band_index[subindex][ib]`

3. **Fermi Surface Clipping:**
   - File: `C/fs.c`
   - Function: `CropBz()` (lines 201-218)
   - Observation: BZ clipping optional (not required), clips triangles outside Wigner-Seitz cell

4. **Data Ordering:**
   - File: `C/datagrid.c`
   - Function: `ReadBandGrid()` (lines 309-318)
   - Observation: 3D data loop `for i in nx: for j in ny: for k in nz` (i-fastest, k-slowest)

---

## 3. QMatSuite Contract Updates

### LineArtifact v1 (Complete):

```python
@dataclass
class LineArtifact(BaseArtifact):
    kind: ArtifactKind = ArtifactKind.LINE
    type_name: str  # "bands", "dos", "pdos", "scf_convergence", etc.
    
    # Bands-specific:
    k_distances: Optional[np.ndarray] = None  # [n_kpoints] float64
    energies: Optional[np.ndarray] = None  # [n_spins?, n_kpoints, n_bands] or [n_kpoints, n_bands]
    high_symmetry_points: Optional[List[Tuple[float, str]]] = None  # [(distance, label)]
    
    # DOS-specific:
    energy_axis: Optional[np.ndarray] = None  # [n_points] float64, Fermi-shifted
    dos_values: Optional[np.ndarray] = None  # [n_spins?, n_points] or [n_points]
    
    # Projection (fatband):
    projection_weights: Optional[np.ndarray] = None  # [n_spins?, n_kpoints, n_bands]
    
    # Line profile (from volume):
    line_profile_path: Optional[np.ndarray] = None  # [n_points, 3] float64
    line_profile_values: Optional[np.ndarray] = None  # [n_points] float64
    interpolation_method: str = "trilinear"
    
    # Metadata:
    fermi_energy: float = 0.0
    fermi_shift_applied: bool = True
    spin_channels: List[str] = field(default_factory=lambda: ["total"])
    orbital_indices: Optional[List[int]] = None
    atom_indices: Optional[List[int]] = None
    
    # Units:
    energy_units: str = "eV"  # MUST be explicit
    distance_units: str = "Å⁻¹"  # For k-path
    
    def to_metadata(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "type_name": self.type_name,
            "fermi_energy": self.fermi_energy,
            "fermi_shift_applied": self.fermi_shift_applied,
            "spin_channels": self.spin_channels,
            "energy_units": self.energy_units,
            "distance_units": self.distance_units,
            # Shape hints (not full data):
            "k_distances_shape": list(self.k_distances.shape) if self.k_distances is not None else None,
            "energies_shape": list(self.energies.shape) if self.energies is not None else None,
        }
    
    def serialize(self, path: Path) -> None:
        # Write metadata JSON + binary data (numpy arrays)
        metadata = self.to_metadata()
        metadata_path = path / f"{self.type_name}_metadata.json"
        binary_path = path / f"{self.type_name}_data.npz"
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        np.savez_compressed(
            binary_path,
            k_distances=self.k_distances,
            energies=self.energies,
            energy_axis=self.energy_axis,
            dos_values=self.dos_values,
            projection_weights=self.projection_weights,
        )
    
    @classmethod
    def deserialize(cls, path: Path) -> "LineArtifact":
        # Read metadata JSON + binary data
        pass
```

### MapArtifact v1 (Complete):

```python
@dataclass
class MapArtifact(BaseArtifact):
    kind: ArtifactKind = ArtifactKind.MAP
    type_name: str  # "k_slice", "plane_slice", "planar_average", etc.
    
    grid_shape: Tuple[int, int]  # (nx, ny)
    binary_path: Path  # Path to .npy file with shape (nx, ny)
    
    origin: np.ndarray  # [3] float64
    plane_vectors: np.ndarray  # [2, 3] float64
    normal_vector: Optional[np.ndarray] = None
    
    is_1d_profile: bool = False
    profile_axis: Optional[int] = None
    profile_values: Optional[np.ndarray] = None
    
    source_volume: Optional[str] = None
    slice_position: Optional[float] = None
    
    length_units: str = "Å"
    value_units: str = "e/voxel"
    
    def to_metadata(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "type_name": self.type_name,
            "grid_shape": list(self.grid_shape),
            "binary_path": str(self.binary_path),
            "origin": self.origin.tolist(),
            "plane_vectors": self.plane_vectors.tolist(),
            "normal_vector": self.normal_vector.tolist() if self.normal_vector is not None else None,
            "is_1d_profile": self.is_1d_profile,
            "profile_axis": self.profile_axis,
            "length_units": self.length_units,
            "value_units": self.value_units,
        }
    
    def serialize(self, path: Path) -> None:
        # Write metadata JSON + binary data
        pass
    
    @classmethod
    def deserialize(cls, path: Path) -> "MapArtifact":
        pass
```

### VolumeMetadata v1 (Complete):

```python
@dataclass
class VolumeMetadata:
    grid_shape: Tuple[int, int, int]  # (nx, ny, nz) - MUST match binary
    
    coordinate_system: str  # "real-space" or "reciprocal-space"
    origin: np.ndarray  # [3] float64, Cartesian Å
    grid_vectors: np.ndarray  # [3, 3] float64, defines grid cell in Å
    lattice_vectors: Optional[np.ndarray] = None  # [3, 3] float64, unit cell in Å
    
    # CRITICAL: Data ordering
    data_order: str  # "k-fastest" (C-style) or "i-fastest" (Fortran-style)
    # MUST be explicit to avoid silent wrong rendering
    
    # Units (MUST be explicit):
    length_units: str = "Å"
    value_units: str = "e/voxel"
    value_normalized: bool = False
    
    # Multi-channel:
    n_channels: int = 1
    channel_names: List[str] = field(default_factory=lambda: ["total"])
    channel_indices: Optional[Dict[str, int]] = None
    
    # Binary cache:
    binary_path: Path
    binary_format: str = "numpy"
    preview_path: Optional[Path] = None
    
    # Lazy statistics:
    value_min: Optional[float] = None
    value_max: Optional[float] = None
    value_mean: Optional[float] = None
    
    # Structure:
    structure_path: Optional[Path] = None
    structure_embedded: bool = True
```

### Catalog/Index Contract:

```python
@dataclass
class ArtifactCatalog:
    """Catalog of all artifacts for a calculation"""
    calculation_dir: Path
    
    # Index by kind:
    line_artifacts: List[LineArtifact] = field(default_factory=list)
    map_artifacts: List[MapArtifact] = field(default_factory=list)
    volume_artifacts: List[VolumeArtifact] = field(default_factory=list)
    properties_artifacts: List[PropertiesArtifact] = field(default_factory=list)
    
    # Metadata:
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    qms_version: str = __version__
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "calculation_dir": str(self.calculation_dir),
            "line_artifacts": [a.to_metadata() for a in self.line_artifacts],
            "map_artifacts": [a.to_metadata() for a in self.map_artifacts],
            "volume_artifacts": [a.to_metadata() for a in self.volume_artifacts],
            "properties_artifacts": [a.to_metadata() for a in self.properties_artifacts],
            "created_at": self.created_at,
            "qms_version": self.qms_version,
        }
    
    def save(self, path: Path) -> None:
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load(cls, path: Path) -> "ArtifactCatalog":
        with open(path, 'r') as f:
            data = json.load(f)
        # Deserialize artifacts from metadata
        pass
```

---

## 4. Open Questions & How to Resolve

1. **Question:** How does p4vasp detect spin-polarized vs non-spin-polarized calculations from file headers?
   - **Resolution:** Check `vasprun.xml` for `<parameters>/<i name="ISPIN">` or check DOSCAR header (line count). Test with known spin-polarized and non-spin-polarized VASP outputs.

2. **Question:** How to handle LORBIT=12 (complex projections) vs LORBIT=11 (real projections) for PDOS?
   - **Resolution:** Check `vasprun.xml` `<parameters>/<i name="LORBIT">`. For LORBIT=12, use squared projections (`**2`), for LORBIT=11 use absolute (`abs()`). Test with both LORBIT values.

3. **Question:** What is the exact format of Wannier90 .wout for centers/spreads?
   - **Resolution:** Parse example .wout files from Wannier90 tutorial. Look for "Final State" section and parse table format. Create test fixtures from tutorial examples.

4. **Question:** How to detect data ordering (k-fastest vs i-fastest) from file format alone?
   - **Resolution:** Use synthetic test fixture: Generate volume with `f(i,j,k) = i + 10*j + 100*k`. Parse and check if values match expected pattern. If not, try alternative ordering. Add ordering auto-detection to parser with fallback to user selection.

5. **Question:** How to compute voxel volume for normalization (especially for non-orthogonal grids)?
   - **Resolution:** `voxel_volume = abs(det(grid_vectors)) / (nx*ny*nz)`. Verify with known charge density integral (should equal number of electrons). Test with orthogonal and non-orthogonal grids.

6. **Question:** What is the exact BXSF format variant for energy shift (does file contain Ef)?
   - **Resolution:** Parse copper.bxsf from Wannier90 examples. Check if `BEGIN_INFO` block contains `E_FERMI` field. If not, assume E=0. Test with known Fermi surface files.

7. **Question:** How to handle PARCHG files with band/energy window labels in filename?
   - **Resolution:** Parse filename pattern: `PARCHG.nnn.band` or `PARCHG.nnn` (band index). Store band index in metadata. Test with VASP PARCHG outputs.

8. **Question:** What is the performance impact of lazy loading vs full loading for BXSF with many bands?
   - **Resolution:** Benchmark: Load copper.bxsf (N bands) and time lazy load (1 band) vs full load (all bands). Measure file seek time vs parse time. Determine threshold for lazy loading strategy.

9. **Question:** How to validate reciprocal vectors in BXSF (should they match structure reciprocal lattice)?
   - **Resolution:** Compare BXSF reciprocal vectors with structure reciprocal basis (from PRIMVEC in XSF header). Check if they match within tolerance (1e-6). If not, warn user but don't fail (may be intentional for extended k-grid).

---

## Summary: Implementation Priorities

**M0 (Contract & Safety):**
1. Define VolumeMetadata with explicit `data_order`, `length_units`, `value_units`
2. Implement ordering auto-detection with synthetic test fixture
3. Add unit validation (check Å vs Bohr, warn on mismatch)
4. Create ArtifactCatalog index structure

**M1 (Volume Basic):**
1. Implement XSF/Cube parser with ordering detection
2. Generate binary cache (.npy) during parse
3. Implement VolumeViewer3D with MarchingCubes
4. Add iso value slider and structure overlay

**M2 (Fermi Surface):**
1. Implement BXSF parser with lazy band loading
2. Add band selection UI (tab-based)
3. Implement BZ clipping (optional, off by default)
4. Add energy shift input field

**M3 (Advanced):**
1. Add planar average computation
2. Add line profile interpolation
3. Add multi-channel support (spin selection)
4. Add Wannier90 properties parser

---

**End of Pipeline Dataflow Analysis**

