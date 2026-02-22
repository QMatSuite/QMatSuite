# Plan v2: Revised Implementation Plan for Volume/Map Visualization

**Purpose:** Corrected and gate-locked implementation plan based on deep source code analysis of p4vasp and XCrySDen, ensuring physical correctness, performance, and maintainability.

**Key Corrections:**
- M0 gate added: Ordering detection, VolumeMetadata contract, security boundaries
- BZ clipping explicitly deferred (not MVP)
- Binary blob security with allowlist (no arbitrary file access)
- Test fixtures for ordering validation

---

## Part A: Plan v2 - Revised Milestones

### M0: Gate - Foundation & Safety (CRITICAL, MUST COMPLETE FIRST)

**Duration:** ~1 week

**Goal:** Establish contract boundaries, security, and validation before any volume parsing.

**Tasks:**

#### M0.1: ArtifactKind & BaseArtifact ABC
- **File:** `src/qmatsuite/analysis/artifact_types.py`
- **Deliverable:** `ArtifactKind` enum, `BaseArtifact` ABC with `to_metadata()`, `serialize()`, `deserialize()`
- **Tests:** `tests/unit/test_artifact_types.py` - ABC compliance, serialization roundtrip

#### M0.2: ArtifactCatalog & Index Structure
- **File:** `src/qmatsuite/analysis/artifact_catalog.py`
- **Deliverable:** `ArtifactCatalog` dataclass with `line_artifacts`, `map_artifacts`, `volume_artifacts`, `properties_artifacts` lists
- **Storage:** `<calc_dir>/analysis/catalog.json` (metadata only, no binary paths in JSON)
- **Tests:** `tests/unit/test_artifact_catalog.py` - catalog persistence, artifact registration

#### M0.3: VolumeMetadata Contract v1 (HARD CONSTRAINT)
- **File:** `src/qmatsuite/analysis/volume_artifacts.py`
- **Contract Fields (MUST BE EXPLICIT):**
  ```python
  @dataclass
  class VolumeMetadata:
      # Grid shape:
      grid_shape: Tuple[int, int, int]  # (nx, ny, nz)
      
      # Coordinate system (MUST be explicit):
      coordinate_system: Literal["real-space", "reciprocal-space"]
      
      # Geometry:
      origin_cart: np.ndarray  # [3] float64, Cartesian in Å
      grid_vectors_cart: np.ndarray  # [3, 3] float64, voxel step vectors (NOT lattice)
      lattice_vectors_cart: Optional[np.ndarray]  # [3, 3] float64, unit cell (for overlay)
      
      # CRITICAL: Data ordering (MUST be explicit to avoid silent wrong):
      data_order: Literal["k-fastest", "i-fastest"]  # C-style vs Fortran-style
      
      # Units (MUST be explicit):
      length_units: str = "Å"  # "Å" or "Bohr"
      value_units: str = "e/voxel"  # "e/voxel", "eV", "dimensionless", etc.
      value_normalized: bool = False  # Whether normalized by voxel volume
      
      # Multi-channel:
      n_channels: int = 1
      channel_names: List[str] = field(default_factory=lambda: ["total"])
      channel_indices: Optional[Dict[str, int]] = None
      
      # Binary cache (blob_id, not absolute path):
      blob_id: str  # UUID or hash-based identifier
      binary_format: str = "numpy"  # "numpy" or "zarr" (future)
      preview_blob_id: Optional[str] = None  # Downsampled preview
      
      # Lazy statistics:
      value_min: Optional[float] = None
      value_max: Optional[float] = None
      value_mean: Optional[float] = None
  ```
- **Tests:** `tests/unit/test_volume_metadata.py` - validation, unit checking, coordinate system checks

#### M0.4: Binary Blob Security & Allowlist
- **File:** `src/qmatsuite/analysis/binary_cache.py`, `gui/electron/preload.ts`
- **Deliverable:**
  - `BinaryCache` class: `write_blob()`, `get_blob_path(blob_id)`, `validate_blob_id()`
  - Storage: `<calc_dir>/analysis/blobs/<blob_id>.npy` (only in analysis directory)
  - Preload allowlist: Only allow `readBinaryFile(blob_id)` where `blob_id` is registered in catalog
  - **Security:** RPC returns `blob_id`, NOT absolute path. Preload validates `blob_id` against catalog before fs.readFile
- **Tests:** `tests/unit/test_binary_cache.py` - blob registration, path validation, security boundary tests
- **Tests:** `tests/integration/test_blob_security.py` - preload allowlist enforcement

#### M0.5: Ordering Detection Fixture & Parser Sanity Checks
- **File:** `src/qmatsuite/io/parser/volume_parsers.py`, `tests/fixtures/ordering_test.py`
- **Deliverable:**
  - Synthetic test fixture generator: `generate_ordering_test_fixture(nx, ny, nz)` → creates volume with `f(i,j,k) = i + 10*j + 100*k`
  - Ordering auto-detection: Parse fixture, check if values match expected pattern
  - Parser sanity checks: Data count validation, bbox sanity (origin + vectors span reasonable volume)
  - Planar average sanity: Extract plane, check statistics are reasonable
  - **Fallback:** If auto-detection fails, UI allows manual override (dropdown: "k-fastest" vs "i-fastest")
- **Tests:** `tests/unit/test_ordering_detection.py` - fixture generation, pattern matching, failure cases
- **Tests:** `tests/unit/test_parser_sanity.py` - data count, bbox, planar average validation

**Acceptance Criteria:**
- [ ] All M0 tasks complete with tests passing
- [ ] VolumeMetadata contract enforces explicit units/ordering/coordinate system
- [ ] Blob security: No absolute paths in RPC responses, preload allowlist enforced
- [ ] Ordering fixture detects k-fastest vs i-fastest correctly
- [ ] Parser sanity checks catch invalid data early

---

### M1: Volume Basic - XSF/Cube Parser + Isosurface Viewer

**Duration:** ~2 weeks

**Goal:** Parse XSF/Cube files, display isosurfaces with basic controls (MLWF ±iso from Wannier90).

**Tasks:**

#### M1.1: XSF Parser with Ordering Detection
- **File:** `src/qmatsuite/io/parser/volume_parsers.py`
- **Function:** `parse_xsf(path: Path) -> VolumeArtifact`
- **Requirements:**
  - Parse `CRYSTAL` or `ATOMS` structure block
  - Parse `BEGIN_BLOCK_DATAGRID3D` / `BEGIN_DATAGRID_3D` blocks
  - Default ordering: `data_order="k-fastest"` (XCrySDen convention: `for k in nz: for j in ny: for i in nx`)
  - Auto-detect ordering using fixture pattern (if ambiguous, default to k-fastest with warning)
  - Validate data count: `len(data) == nx*ny*nz`
  - Extract structure from XSF (avoid requiring separate file)
  - Write binary blob immediately: `write_blob(data, blob_id)`, store `blob_id` in metadata
  - Generate preview: 4× downsampling, write separate blob
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_xsf` - real XSF files, ordering detection, structure extraction

#### M1.2: Cube Parser with Ordering Detection
- **File:** `src/qmatsuite/io/parser/volume_parsers.py`
- **Function:** `parse_cube(path: Path) -> VolumeArtifact`
- **Requirements:**
  - Parse Cube header (comment lines, natoms, origin, vectors)
  - Default ordering: Check Cube format spec (typically k-fastest, but verify)
  - Auto-detect ordering using fixture pattern
  - Handle non-orthogonal grids (grid_vectors may not be axis-aligned)
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_cube` - Gaussian/ORCA cube files

#### M1.3: VolumeArtifact Dataclass
- **File:** `src/qmatsuite/analysis/volume_artifacts.py`
- **Deliverable:** `VolumeArtifact` extends `BaseArtifact`, contains `VolumeMetadata`
- **Methods:**
  - `get(i, j, k, wrap: bool = True) -> float` - Periodic wrapping (p4vasp pattern)
  - `getRaw(i, j, k) -> float` - No wrapping (for gradient calculations)
  - `downsample(factors: Tuple[int, int, int]) -> VolumeArtifact` - Block averaging
- **Tests:** `tests/unit/test_volume_artifacts.py` - get/getRaw wrapping, downsampling

#### M1.4: Binary Cache Module
- **File:** `src/qmatsuite/analysis/binary_cache.py`
- **Deliverable:** `BinaryCache` class
- **Methods:**
  - `write_blob(data: np.ndarray, blob_id: str, calc_dir: Path) -> Path`
  - `read_blob(blob_id: str, calc_dir: Path) -> np.ndarray`
  - `generate_preview(data: np.ndarray, factors: Tuple[int, int, int]) -> np.ndarray`
- **Tests:** `tests/unit/test_binary_cache.py` - write/read roundtrip, preview generation

#### M1.5: RPC Handlers for Volume Metadata
- **File:** `src/qmatsuite/daemon/server.py`
- **Handlers:**
  - `list_volume_artifacts(calc_id: str) -> List[Dict]` - Returns metadata only (no blob data)
  - `get_volume_metadata(calc_id: str, artifact_id: str) -> Dict` - Returns VolumeMetadata JSON (includes blob_id, not path)
  - `get_blob_token(calc_id: str, blob_id: str) -> str` - Returns validation token for preload allowlist
- **Tests:** `tests/integration/test_volume_rpc.py` - RPC contract, metadata format, security boundary

#### M1.6: Electron Preload Binary File Reading (Secure)
- **File:** `gui/electron/preload.ts`
- **Deliverable:** `readBinaryFile(blob_id: string, token: string) -> Promise<ArrayBuffer>`
- **Security:**
  - Validate `blob_id` against catalog (must be registered in `catalog.json`)
  - Validate `token` matches RPC-issued token for this blob_id
  - Only allow reading from `<calc_dir>/analysis/blobs/` directory (no arbitrary paths)
  - Throw error if blob_id not in allowlist
- **Tests:** `tests/integration/test_preload_security.ts` - allowlist enforcement, token validation

#### M1.7: VolumeViewer3D Component
- **File:** `gui/src/components/panels/VolumeViewer3D.tsx`
- **Deliverable:**
  - Three.js Canvas with `react-three-fiber`
  - MarchingCubes isosurface extraction (use `three-stdlib`)
  - Load binary blob via `readBinaryFile(blob_id, token)`
  - Preview-first loading: Load preview blob, then full on demand
- **Tests:** `gui/tests/volume-viewer.spec.ts` - component renders, binary loading

#### M1.8: Isosurface Controls
- **File:** `VolumeViewer3D.tsx`
- **Controls:**
  - Iso value slider (min/max from metadata statistics)
  - Auto-iso suggestion (percentile-based, e.g., 90th percentile)
  - Dual ±iso toggle (two isosurfaces: +value and -value, different colors)
  - Dual iso value inputs (separate sliders for positive/negative)
  - Opacity slider (alpha blending)
  - Color picker per isosurface
- **Tests:** UI smoke tests - controls update isosurface in real-time

#### M1.9: Axis-Aligned Slice Planes
- **File:** `VolumeViewer3D.tsx`
- **Deliverable:**
  - XY/XZ/YZ slice plane controls
  - Position slider (0-100% or grid index)
  - Slice rendering as 2D texture on plane
  - Structure overlay toggle (show/hide atoms)
- **Tests:** UI smoke tests - slice planes render, position updates

#### M1.10: Structure Overlay
- **File:** `VolumeViewer3D.tsx`
- **Deliverable:**
  - Render atoms from structure (from VolumeMetadata.structure_path or embedded)
  - Z-ordering: Atoms on top of volume (depth sorting)
  - Coordinate alignment: Ensure structure coords match volume coordinate system
- **Tests:** UI smoke tests - structure displays correctly on volume

**Acceptance Criteria:**
- [ ] XSF/Cube files parse correctly with ordering detection
- [ ] Isosurfaces render with ±iso support (MLWF positive/negative lobes)
- [ ] Slice planes work for inspection
- [ ] Structure overlay displays atoms on volume
- [ ] Binary data does NOT go through JSON-RPC
- [ ] Blob security enforced (no arbitrary file access)

---

### M2: Fermi Surface (BXSF) + k-slice Map

**Duration:** ~1.5 weeks

**Goal:** Parse BXSF files, display Fermi surface with band selection, add k-slice 2D viewer (BZ clipping deferred).

**Tasks:**

#### M2.1: BXSF Parser with Lazy Band Loading
- **File:** `src/qmatsuite/io/parser/volume_parsers.py`
- **Function:** `parse_bxsf(path: Path) -> FermiSurfaceArtifact`
- **Requirements:**
  - Parse `BEGIN_BLOCK_BANDGRID3D` / `BEGIN_BANDGRID_3D` header
  - Store file positions per band: `band_file_positions[band_index] = file_position` (like XCrySDen)
  - Parse band metadata only (n_bands, grid_shape, reciprocal_vectors)
  - **Lazy loading:** Do NOT parse all band data on file open
  - Write band data to separate blobs: `band_blob_ids[band_index] = blob_id`
  - Default ordering: `data_order="k-fastest"` (same as XSF: `for i in nx: for j in ny: for k in nz`)
- **Evidence:** XCrySDen `datagrid.c ReadBandGrid()` lines 293 (ftell before each band), 309-318 (i-fastest loop)
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_bxsf` - copper.bxsf, band file positions, lazy loading

#### M2.2: FermiSurfaceArtifact Dataclass
- **File:** `src/qmatsuite/analysis/volume_artifacts.py`
- **Deliverable:** `FermiSurfaceArtifact` extends `VolumeArtifact`
- **Additional Fields:**
  - `n_bands: int`
  - `band_indices: List[int]`
  - `band_blob_ids: Dict[int, str]` - Map band_index → blob_id
  - `fermi_energy: Optional[float] = None` - If None, assume E=0
  - `energy_shift: float = 0.0` - User-adjustable offset
  - `reciprocal_vectors: np.ndarray` - [3, 3] k-space basis
  - `brillouin_zone_clip: bool = False` - **Deferred to M4**
- **Method:** `get_band_data(band_index: int) -> np.ndarray` - Lazy load from blob
- **Tests:** `tests/unit/test_volume_artifacts.py::test_fermi_surface_artifact` - lazy band loading

#### M2.3: Band Selection UI
- **File:** `VolumeViewer3D.tsx` (Fermi surface mode)
- **Deliverable:**
  - Band selector dropdown or tab interface
  - Load only selected band(s) from binary cache
  - Per-band color cycling (different color per band)
  - Multi-band selection (show multiple bands simultaneously)
- **Tests:** UI smoke tests - band selection updates display

#### M2.4: Energy Shift Control
- **File:** `VolumeViewer3D.tsx`
- **Deliverable:**
  - Energy shift input field (default: 0.0)
  - Isosurface extraction: `band_data == (isolevel - energy_shift)` where isolevel typically 0 (Fermi level)
  - Status bar: Show min/max energy per band, current isolevel
- **Evidence:** XCrySDen UI has energy input field (default 0.0), Fermi surface = isosurface at E=0
- **Tests:** UI smoke tests - energy shift updates isosurface

#### M2.5: Reciprocal Cell Visualization (No BZ Clipping)
- **File:** `VolumeViewer3D.tsx`
- **Deliverable:**
  - Display reciprocal cell as wireframe (primitive parallelepiped)
  - Option: Show/hide reciprocal cell
  - **BZ clipping explicitly deferred:** Not implemented in M2 (see M4)
- **Evidence:** XCrySDen has BZ clipping as optional feature (default off), not required for basic display
- **Tests:** UI smoke tests - reciprocal cell displays correctly

#### M2.6: MapArtifact for k-slice
- **File:** `src/qmatsuite/analysis/map_artifacts.py`
- **Deliverable:** `MapArtifact` extends `BaseArtifact`
- **Fields:**
  - `grid_shape: Tuple[int, int]` - (nx, ny) for 2D slice
  - `blob_id: str` - Binary blob for 2D data
  - `origin: np.ndarray` - [3] float64, origin of 2D plane
  - `plane_vectors: np.ndarray` - [2, 3] float64, defines 2D plane
  - `source_volume: str` - Reference to source VolumeArtifact
  - `slice_position: Optional[float]` - Position along normal
- **Tests:** `tests/unit/test_map_artifacts.py` - map artifact creation, plane extraction

#### M2.7: k-slice Extraction from BXSF
- **File:** `src/qmatsuite/analysis/map_artifacts.py`
- **Function:** `extract_kslice(fermi_surface: FermiSurfaceArtifact, band_index: int, kz_index: int) -> MapArtifact`
- **Requirements:**
  - Extract 2D slice from 3D band data at specified kz index
  - Store as separate blob (2D array)
  - Preserve plane vectors and origin for visualization
- **Tests:** `tests/unit/test_map_artifacts.py::test_kslice_extraction` - extract slice, verify plane vectors

#### M2.8: MapViewer2D Component (Basic)
- **File:** `gui/src/components/panels/MapViewer2D.tsx`
- **Deliverable:**
  - Canvas-based 2D heatmap rendering
  - Colormap selector (Viridis/Plasma/Inferno)
  - Value range control (min/max clipping)
  - kz slice selector (slider for 3D → 2D projection)
  - Axis labels (kx/ky with units Å⁻¹)
- **Tests:** UI smoke tests - heatmap renders, colormap updates

#### M2.9: RPC Handlers for Fermi Surface
- **File:** `src/qmatsuite/daemon/server.py`
- **Handlers:**
  - `get_fermi_surface_metadata(calc_id: str, artifact_id: str) -> Dict`
  - `get_band_blob_token(calc_id: str, artifact_id: str, band_index: int) -> str`
  - `extract_kslice(calc_id: str, artifact_id: str, band_index: int, kz_index: int) -> Dict`
- **Tests:** `tests/integration/test_fermi_surface_rpc.py` - RPC contract, lazy band loading

**Acceptance Criteria:**
- [ ] copper.bxsf parses and displays Fermi surface
- [ ] Band selection works (lazy loading, no full file parse)
- [ ] Energy shift control updates isosurface
- [ ] k-slice extraction works (3D → 2D)
- [ ] MapViewer2D displays k-slice heatmap
- [ ] **BZ clipping NOT implemented** (explicitly deferred to M4)

---

### M3: Engine Adapters + Properties Panel

**Duration:** ~2 weeks

**Goal:** Add QE pp.x workflow integration, VASP support, Wannier90 properties display.

**Tasks:**

#### M3.1: QE pp.x Step Type & Template
- **File:** `src/qmatsuite/calculation/step_defaults.py`, `src/qmatsuite/workflow/templates.py`
- **Deliverable:** `pp` step type for pp.x post-processing
- **Template:** pp.x input generator (plot_num, filplot options)
- **Tests:** `tests/unit/test_ppx_generator.py` - input generation, plot_num selection

#### M3.2: Automatic pp.x Output Detection
- **File:** `src/qmatsuite/calculation/step_artifacts.py`
- **Deliverable:** Auto-detect cube/xsf files from pp.x output
- **Tests:** `tests/unit/test_step_artifacts.py::test_ppx_artifact_detection`

#### M3.3: VASP CHGCAR/ELFCAR/LOCPOT Parsers
- **File:** `src/qmatsuite/io/parser/volume_parsers.py`
- **Functions:** `parse_chgcar()`, `parse_elfcar()`, `parse_locpot()`
- **Requirements:**
  - Parse VASP format (structure header + grid dimensions + data)
  - Default ordering: `data_order="k-fastest"` (p4vasp: `data[i+(j+k*ny)*nx]`)
  - Extract structure from CHGCAR header
  - Handle spin-polarized (CHGCAR + CHGCAR_spin)
- **Evidence:** p4vasp `Chgcar.cpp read()` lines 191-238 (structure then grid then data), 371 (k-fastest indexing)
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_chgcar` - real VASP files

#### M3.4: Wannier90 .wout Parser for Centers/Spreads
- **File:** `src/qmatsuite/io/parser/wannier90_parsers.py`
- **Function:** `parse_wannier90_wout(path: Path) -> WannierPropertiesArtifact`
- **Requirements:**
  - Parse "Final State" section from .wout
  - Extract centers (Cartesian and fractional)
  - Extract spreads
- **Tests:** `tests/unit/test_wannier90_parsers.py` - tutorial .wout files

#### M3.5: PropertiesArtifact & PropertiesPanel
- **Files:** `src/qmatsuite/analysis/properties_artifacts.py`, `gui/src/components/panels/PropertiesPanel.tsx`
- **Deliverable:**
  - `PropertiesArtifact` dataclass (centers, spreads)
  - Table UI for Wannier centers/spreads
  - Visualization: Show centers as spheres in structure viewer
- **Tests:** UI smoke tests - properties panel displays data

#### M3.6: Supercell Tiling for MLWF Display
- **File:** `VolumeViewer3D.tsx`
- **Deliverable:**
  - Supercell tiling control (mx, my, mz) or auto (from k-mesh metadata)
  - Use basis vector translation for periodic repeats
  - Evidence: p4vasp uses `setMultiple(mx, my, mz)` with basis vector translation
- **Tests:** UI smoke tests - supercell tiling renders correctly

#### M3.7: ArtifactNavigator Component
- **File:** `gui/src/components/panels/ArtifactNavigator.tsx`
- **Deliverable:**
  - Category tabs: Lines / Maps / Volumes / Properties
  - Artifact list per category
  - Integration into CalculationAnalysisPanel
- **Tests:** UI smoke tests - navigation works, artifacts listed

#### M3.8: Integration Test: pp.x Workflow
- **File:** `tests/integration/test_ppx_workflow.py`
- **Deliverable:** End-to-end test: pp.x execution → cube/xsf detection → volume artifact → viewer
- **Tests:** Full workflow from step execution to visualization

**Acceptance Criteria:**
- [ ] pp.x workflow integrates with step execution
- [ ] VASP CHGCAR/ELFCAR/LOCPOT parse correctly
- [ ] Wannier90 properties display (centers/spreads)
- [ ] Supercell tiling works for MLWF visualization

---

### M4: Advanced Features (Stretch Goals / Post-MVP)

**BZ Clipping (Deferred from M2):**
- Implement Wigner-Seitz cell calculation from reciprocal vectors
- Clip isosurface triangles outside BZ boundaries
- UI toggle: Enable/disable BZ clipping (default: off)

**Planar Average & Line Profile:**
- Implement `get_plane_x/y/z()` methods (p4vasp pattern)
- Compute planar statistics (min/max/avg/variance)
- 1D profile plot for planar average
- Line profile along arbitrary path (3D interpolation)

**Multi-channel Support:**
- Spin channel selection UI
- Partial charge summation
- Derived quantities (up-down difference)

---

## Part B: Deep-Dive Answers (B1-B6)

### B1) p4vasp: Volumetric Grid Metadata & Units/Ordering

**Conclusion:**
- p4vasp stores grid as `data[i + (j + k*ny)*nx]` (C-style, k-fastest)
- Units: Ångström (from Structure.basis vectors), no explicit unit conversion
- Origin: Implicit (0,0,0) in fractional, grid covers unit cell
- Lattice vectors: `structure.basis1/2/3` (3×3 float64 in Å)
- Multi-channel: Separate Chgcar objects per channel (no internal multi-component array)
- No lazy/chunk reading: Loads entire grid into memory

**Evidence:**
- File: `p4vasp-master/src/Chgcar.cpp`
- Function: `Chgcar::get()` (line 371) - Indexing `data[i+(j+k*ny)*nx]` (k-fastest)
- Function: `Chgcar::sumElectrons()` (line 467) - Returns `N/(nx*ny*nz)` (not normalized by voxel volume)
- File: `p4vasp-master/src/Chgcar.cpp`
- Function: `Chgcar::read()` (lines 191-238) - Structure header, then grid dimensions, then data

**QMatSuite Implementation:**
- **VolumeMetadata.data_order:** MUST be "k-fastest" for VASP files (default, auto-detect with fixture)
- **VolumeMetadata.length_units:** MUST be "Å" (explicit, no "default guess")
- **VolumeMetadata.value_units:** "e/voxel" (not normalized by voxel volume, like p4vasp)
- **VolumeMetadata.grid_vectors_cart:** From `structure.basis1/2/3` (same as lattice_vectors for CHGCAR)
- **VolumeMetadata.lattice_vectors_cart:** Same as grid_vectors (typical for VASP)

**Caching:**
- No lazy reading needed for MVP (p4vasp loads all)
- Future: zarr/chunked storage for very large grids (>500MB)

---

### B2) p4vasp: Bands/DOS Ef Alignment & Projection Organization

**Conclusion:**
- Fermi energy always subtracted from eigenvalues/DOS before plotting
- Default: Ef = 0.0 if not found in file
- DOS energies shifted: `map(lambda x,e=e:(x[0]-e, x[1]), tdos[0])`
- Projection: `[spin][k][band][ion][orbital]` array structure
- Weight calculation: Sum over selected ions and orbital indices (absolute or squared)

**Evidence:**
- File: `p4vasp-master/lib/p4vasp/applet/ElectronicApplet.py`
- Function: `updateDataGen()` (lines 494-498) - Default Ef = 0.0 if not found
- Function: `updateDataGen()` (lines 516-519) - DOS energies shifted: `x[0]-e`
- Function: `updateEigenvaluesGen()` (lines 225, 232) - Eigenvalues shifted: `ev[i][k][j][0]-e`
- Function: `updateEigenvaluesGen()` (lines 222-232) - Projection weights: sum over ions and orbitals

**QMatSuite Implementation:**
- **LineArtifact.fermi_energy:** Original Ef from source (before shift)
- **LineArtifact.fermi_shift_applied:** MUST be `True` (energies already relative to Ef)
- **LineArtifact.energy_axis:** Already shifted (relative to Ef=0)
- **LineArtifact.projection_weights:** `[n_spins?, n_kpoints, n_bands]` float64, computed from `[spin][k][band][ion][orbital]`
- **LineArtifact.orbital_indices:** Selected orbital field indices
- **LineArtifact.atom_indices:** Selected atom indices

---

### B3) XCrySDen: XSF DATAGRID Parser Tolerance & data_order Evidence

**Conclusion:**
- Default ordering: `data_order="k-fastest"` (loop: `for k in nz: for j in ny: for i in nx`)
- Reading loop: `for i in nz: for j in ny: for k in nx` (k-fastest, i-slowest)
- Data written to binary immediately: `fwrite(&value, sizeof(float), 1, gridFP)`
- Multiple subgrids: Same dimensions/origin/vectors, only data differs

**Evidence:**
- File: `xcrysden-1.6.2/C/datagrid.c`
- Function: `ReadDataGrid()` (lines 209-218) - Loop order: `for i in nz: for j in ny: for k in nx` (k-fastest)
- Function: `ReadDataGrid()` (line 216) - Immediate binary write: `fwrite(&value, sizeof(float), 1, gridFP)`
- Function: `ReadDataGrid()` (line 221) - Multiple subgrids handled via `datagrid_subindex`

**QMatSuite Implementation:**
- **parse_xsf() default:** `data_order="k-fastest"` (XCrySDen convention)
- **Auto-detection:** Use synthetic fixture `f(i,j,k)=i+10j+100k`, try k-fastest first
- **Fallback:** If auto-detection fails, UI dropdown for manual selection
- **Self-check:** Validate data count `len(data) == nx*ny*nz`, warn if mismatch
- **Test fixture:** `tests/fixtures/xsf_ordering_test.xsf` - Generated with known pattern

---

### B4) XCrySDen: BXSF BANDGRID Band Management & Lazy Loading

**Conclusion:**
- File positions stored per band: `grid->band_fpos[subindex][band_index] = ftell(gridFP)` before each band data
- Lazy loading: Only load selected band(s) via `fseek()` to stored position
- Energy shift: Default E=0 assumed (no explicit Ef in BXSF format), user can set offset
- Multi-band display: Each band rendered separately with distinct color

**Evidence:**
- File: `xcrysden-1.6.2/C/datagrid.c`
- Function: `ReadBandGrid()` (line 293) - Store file position: `grid->band_fpos[subindex][ib] = ftell(gridFP)`
- File: `xcrysden-1.6.2/C/fs.c`
- Function: `fsReadBand()` (lines 52-54) - Lazy load: `fseek(grid->fp, grid->band_fpos[...][...], SEEK_SET)`
- Function: `fsReadBand()` (lines 309-318) - Reading loop: `for i in nx: for j in ny: for k in nz` (i-fastest, k-slowest)

**QMatSuite Implementation:**
- **FermiSurfaceArtifact.band_blob_ids:** `Dict[int, str]` - Map band_index → blob_id
- **FermiSurfaceArtifact.fermi_energy:** `Optional[float] = None` - If None, assume E=0
- **FermiSurfaceArtifact.energy_shift:** `float = 0.0` - User-adjustable offset
- **Lazy loading:** Parse header only, write each band to separate blob, load on-demand
- **UI:** Band selector dropdown, load only selected band(s) from blobs

---

### B5) XCrySDen: Fermi Surface Geometry Semantics (BZ Clipping Deferred)

**Conclusion:**
- Reciprocal cell: Primitive parallelepiped from BXSF vectors (default visualization)
- BZ clipping: Optional feature (default off), not required for basic display
- BZ clipping uses Wigner-Seitz cell vertices to determine boundaries
- Critical operations: Band select + E iso + view cell (must have)
- BZ clipping: Advanced feature (deferred to M4)

**Evidence:**
- File: `xcrysden-1.6.2/C/fs.c`
- Function: `CropBz()` (lines 201-218) - BZ clipping is optional (not called by default)
- Function: `fsReadBand()` (lines 67-197) - BZ clipping section is conditional (`if (mols->fs.celltype == XCR_BZ)`)
- File: `xcrysden-1.6.2/Tcl/FS_Main.tcl` - UI has BZ clipping toggle (default off)

**QMatSuite Implementation:**
- **M2 MVP:** Reciprocal cell wireframe display (primitive parallelepiped), NO BZ clipping
- **BZ clipping:** Explicitly deferred to M4 (stretch goal)
- **UI:** Show/hide reciprocal cell toggle
- **Reason:** BZ clipping requires Wigner-Seitz cell calculation (complex geometry), not essential for basic Fermi surface display

---

### B6) Planar Average / Slice / Profile: Definition & Unit Normalization

**Conclusion:**
- Planar statistics: min/max/avg/variance computed per plane (not normalized by voxel volume)
- Planar average: Average per voxel in plane (`avg = sum(plane) / (ny*nz)`)
- Units: Same as raw data (not normalized by voxel volume)
- p4vasp: No explicit normalization, values are "per voxel" (not per unit volume)

**Evidence:**
- File: `p4vasp-master/src/Chgcar.cpp`
- Function: `calculatePlaneStatisticsX()` (lines 731-760) - Computes min/max/avg/variance without volume normalization
- Function: `calculatePlaneStatisticsX()` (line 758) - `plane_average = avg/N` where `N=ny*nz` (number of voxels in plane)
- Function: `sumElectrons()` (line 467) - Returns `N/(nx*ny*nz)` (average per voxel, not multiplied by voxel volume)

**QMatSuite Implementation:**
- **MapArtifact.is_1d_profile:** `bool = False` - True if this is averaged over one dimension
- **MapArtifact.profile_values:** `Optional[np.ndarray]` - 1D array of averages per plane
- **Calculation:** Backend computes planar average (not frontend)
- **Units:** Inherited from source volume (no normalization by default)
- **Normalization:** Optional future feature (multiply by voxel volume if needed)
- **Test:** Synthetic volume with known planar average (e.g., constant value per plane)

---

## Part C: Evidence Table

| Question | Path / Symbol | Behavior (One Sentence) | QMatSuite Conclusion |
|----------|---------------|------------------------|---------------------|
| B1: Grid ordering | `Chgcar.cpp::get()` line 371 | Indexing `data[i+(j+k*ny)*nx]` (k-fastest, C-style) | Default `data_order="k-fastest"` for VASP |
| B1: Units | `Chgcar.cpp::sumElectrons()` line 467 | Returns `N/(nx*ny*nz)` (per voxel, not normalized) | `value_units="e/voxel"`, `value_normalized=False` |
| B1: Multi-channel | `SystemPM.py::getChargeFile()` line 330 | Loads single Chgcar object per file (no internal array) | Separate VolumeArtifacts per channel |
| B2: Ef alignment | `ElectronicApplet.py::updateDataGen()` lines 516-519 | DOS energies shifted: `x[0]-e` (e = Fermi energy) | `fermi_shift_applied=True`, energies relative to Ef=0 |
| B2: Ef default | `ElectronicApplet.py::updateDataGen()` lines 494-498 | Default Ef = 0.0 if not found in file | `fermi_energy` can be None, default to 0.0 |
| B3: XSF ordering | `datagrid.c::ReadDataGrid()` lines 209-218 | Loop: `for i in nz: for j in ny: for k in nx` (k-fastest) | Default `data_order="k-fastest"` for XSF |
| B4: BXSF lazy load | `datagrid.c::ReadBandGrid()` line 293 | Store file position: `ftell(gridFP)` before each band | Store `band_blob_ids`, load on-demand |
| B4: BXSF load | `fs.c::fsReadBand()` lines 52-54 | Lazy load via `fseek()` to stored position | Load only selected band(s) from blobs |
| B4: Energy shift | XCrySDen UI (FS_Main.tcl) | Energy input field (default 0.0), Fermi surface = E=0 | `energy_shift=0.0` (user-adjustable) |
| B5: BZ clipping | `fs.c::CropBz()` lines 201-218 | Optional feature (not called by default) | **Deferred to M4** (not MVP) |
| B6: Planar stats | `Chgcar.cpp::calculatePlaneStatisticsX()` line 758 | `plane_average = avg/N` (not normalized by volume) | Planar average computed per voxel, units inherited |

---

## Part D: Open Questions & Resolution Methods

1. **Question:** How to validate reciprocal vectors in BXSF match structure reciprocal lattice?
   - **Resolution:** Compare BXSF reciprocal vectors with structure reciprocal basis (from XSF PRIMVEC). Check if match within tolerance (1e-6). If not, warn but don't fail (may be intentional for extended k-grid).
   - **Test:** Parse copper.bxsf + structure, compare vectors

2. **Question:** What is exact Wannier90 .wout format for centers/spreads?
   - **Resolution:** Parse tutorial .wout files, look for "Final State" section, extract table format. Create test fixtures from examples.
   - **Test:** Parse Wannier90 tutorial .wout files

3. **Question:** How to detect spin-polarized CHGCAR (separate file vs single file)?
   - **Resolution:** Check if CHGCAR_spin exists or parse ISPIN from OUTCAR. Store channel metadata in artifact.
   - **Test:** Test with spin-polarized and non-spin-polarized VASP outputs

4. **Question:** What is performance threshold for lazy loading vs full loading (BXSF)?
   - **Resolution:** Benchmark: Load copper.bxsf (N bands), time lazy load (1 band) vs full load (all bands). Measure file seek vs parse time.
   - **Test:** Performance benchmark with varying band counts

5. **Question:** How to handle PARCHG files with band/energy window labels in filename?
   - **Resolution:** Parse filename pattern: `PARCHG.nnn.band` or `PARCHG.nnn` (band index). Store band index in metadata.
   - **Test:** Test with VASP PARCHG outputs

6. **Question:** What is voxel volume calculation for normalization (non-orthogonal grids)?
   - **Resolution:** `voxel_volume = abs(det(grid_vectors)) / (nx*ny*nz)`. Verify with known charge density integral.
   - **Test:** Synthetic volume with known integral, verify calculation

7. **Question:** How to handle LORBIT=12 (complex projections) vs LORBIT=11 (real)?
   - **Resolution:** Check `vasprun.xml` `<parameters>/<i name="LORBIT">`. For LORBIT=12, use squared (`**2`), for LORBIT=11 use absolute (`abs()`).
   - **Test:** Test with both LORBIT values

8. **Question:** What is Cube format default ordering (Gaussian vs ORCA)?
   - **Resolution:** Check Cube format spec, test with known Gaussian/ORCA files. Use ordering fixture to detect.
   - **Test:** Parse Gaussian and ORCA cube files, verify ordering

---

## Summary: Changes from Original Plan

### Deletions / Postponements:
- **Deleted:** BZ clipping from M2 (moved to M4)
- **Deleted:** Supercell tiling from M1 (moved to M3, after basic volume works)
- **Postponed:** Planar average from M2 (moved to M4)
- **Postponed:** Line profile interpolation (M4)

### Additions / Prepositions:
- **Added:** M0 gate (ordering detection, VolumeMetadata contract, blob security)
- **Added:** Ordering auto-detection with synthetic fixture
- **Added:** Binary blob security (allowlist, no absolute paths)
- **Added:** Parser sanity checks (data count, bbox, planar average validation)

### Modifications:
- **Modified:** VolumeMetadata contract (explicit units, ordering, coordinate system)
- **Modified:** RPC returns blob_id (not absolute path)
- **Modified:** Preload validates blob_id against catalog allowlist
- **Modified:** BXSF lazy loading (band file positions → band blob_ids)

### New Tests (Minimum 12):
1. `test_ordering_detection.py` - Synthetic fixture, pattern matching
2. `test_parser_sanity.py` - Data count, bbox, planar average validation
3. `test_binary_cache.py` - Blob registration, path validation
4. `test_blob_security.py` - Preload allowlist enforcement
5. `test_volume_metadata.py` - Validation, unit checking
6. `test_volume_parsers.py::test_parse_xsf` - XSF parsing, ordering
7. `test_volume_parsers.py::test_parse_cube` - Cube parsing
8. `test_volume_parsers.py::test_parse_bxsf` - BXSF, lazy loading
9. `test_volume_parsers.py::test_parse_chgcar` - VASP parsing
10. `test_volume_artifacts.py` - get/getRaw, downsampling
11. `test_fermi_surface_artifact.py` - Lazy band loading
12. `test_volume_rpc.py` - RPC contract, security boundary

---

**End of Plan v2**

