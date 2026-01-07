# Product Intelligence: p4vasp & XCrySDen → QMatSuite Design Insights

**Purpose**: Extract product-level features, UI patterns, data models, and performance strategies from p4vasp and XCrySDen for QMatSuite analysis/visualization enhancement.

**License Compliance**: This document contains only conceptual design insights, not implementation code. All third-party code patterns have been converted to interface requirements for QMatSuite.

---

## A) Feature Matrix: Analysis Visualization Coverage

### Lines (1D Data)

| Feature | p4vasp | XCrySDen | QMatSuite Status | Priority |
|---------|--------|----------|------------------|----------|
| Band structure | ✅ (from EIGENVAL) | ❌ | ✅ Implemented | - |
| DOS / PDOS | ✅ | ❌ | ✅ Implemented | - |
| SCF convergence | ✅ | ❌ | ✅ Implemented | - |
| Phonon dispersion | ✅ | ✅ (limited) | ❌ Missing | M3+ |
| AHC / Berry curves | ❌ | ❌ | ❌ Missing | Future |
| Fatband / orbital weights | ✅ (projected bands) | ❌ | ❌ Missing | M3+ |

### Maps (2D Data)

| Feature | p4vasp | XCrySDen | QMatSuite Status | Priority |
|---------|--------|----------|------------------|----------|
| k-slice Fermi surface (2D) | ✅ (from BXSF) | ✅ (primary) | ❌ Missing | M2 |
| Planar average (real-space) | ✅ (charge/potential) | ✅ | ❌ Missing | M2 |
| Planar average statistics | ✅ (min/max/avg per plane) | ✅ | ❌ Missing | M2 |
| Charge density slice | ✅ (XY/XZ/YZ planes) | ✅ | ❌ Missing | M1 |
| ELF slice | ✅ | ✅ | ❌ Missing | M3 |
| Potential slice | ✅ | ✅ | ❌ Missing | M3 |
| Potential planar average (LOCPOT) | ✅ (X/Y/Z direction) | ✅ | ❌ Missing | M3 |
| Phonon mode visualization | ✅ (2D slice) | ❌ | ❌ Missing | Future |

### Volumes (3D Data)

| Feature | p4vasp | XCrySDen | QMatSuite Status | Priority |
|---------|--------|----------|------------------|----------|
| Charge density (CHGCAR) | ✅ | ✅ (via XSF) | ❌ Missing | M1 |
| ELF (ELFCAR) | ✅ | ✅ | ❌ Missing | M3 |
| Potential (LOCPOT) | ✅ | ✅ | ❌ Missing | M3 |
| Partial charge (PARCHG) | ✅ | ✅ (multi-component) | ❌ Missing | M3 |
| MLWF isosurfaces (XSF) | ❌ | ✅ (from Wannier90) | ❌ Missing | M1 |
| Fermi surface (BXSF) | ❌ | ✅ | ❌ Missing | M2 |
| Spin-polarized density | ✅ (up/down channels) | ✅ | ❌ Missing | M3 |

### Overlays (Structure + Data)

| Feature | p4vasp | XCrySDen | QMatSuite Status | Priority |
|---------|--------|----------|------------------|----------|
| Atoms on volume | ✅ | ✅ | ✅ (StructureViewer3D exists) | M1 |
| Bonds on volume | ✅ | ✅ | ✅ (StructureViewer3D exists) | M1 |
| Unit cell overlay | ✅ | ✅ | ✅ (StructureViewer3D exists) | M1 |
| Supercell tiling | ✅ (configurable) | ✅ (auto based on k-mesh) | ❌ Missing | M3 |
| Periodic images | ✅ (manual control) | ✅ (auto) | ❌ Missing | M3 |
| Forces/arrows overlay | ✅ | ✅ | ❌ Missing | Future |

### Properties (Scalar/Structured Data)

| Feature | p4vasp | XCrySDen | QMatSuite Status | Priority |
|---------|--------|----------|------------------|----------|
| Wannier centers | ❌ | ✅ (from .wout) | ❌ Missing | M3 |
| Wannier spreads | ❌ | ✅ | ❌ Missing | M3 |
| Band character | ✅ (projection) | ❌ | ❌ Missing | Future |
| Atomic charges | ✅ (Bader) | ✅ | ❌ Missing | Future |
| Magnetic moments | ✅ | ❌ | ❌ Missing | Future |

---

## B) UI/UX Checklist: Volume/Map/Line Viewer Controls

### Volume Viewer (3D Isosurface)

**Core Controls (M1 MVP):**
- [ ] **Iso value slider**: Continuous control (min/max from data stats)
- [ ] **Iso value text input**: For exact numeric entry (with Return key update)
- [ ] **Auto-iso suggestion**: Default to percentile (e.g., 90th percentile for charge density)
- [ ] **Dual isosurface toggle**: ±iso for orbitals (positive/negative values, different colors)
- [ ] **Dual iso values**: Two text inputs for +value and -value (can be different magnitudes)
- [ ] **Opacity control**: Alpha blending (0-100% slider)
- [ ] **Color picker**: Per-isosurface color selection (RGB)
- [ ] **Structure overlay toggle**: Show/hide atoms/bonds
- [ ] **Slice plane toggle**: Show/hide orthogonal slice planes (XY/XZ/YZ)
- [ ] **Draw as points toggle**: Render isosurface as point cloud (for quick preview)

**Advanced Controls (Post-M1):**
- [ ] **Multiple isovalues**: Add/remove isosurface layers with different values
- [ ] **Colormap by value**: Map isosurface color to local volume value (not uniform)
- [ ] **Smoothing level**: Low/Medium/High triangle count (affects performance)
- [ ] **Slice plane position**: Drag slider to move slice along axis
- [ ] **Supercell tiling**: Manual control (mx, my, mz) or auto (from k-mesh metadata)
- [ ] **Coordinate system indicator**: Show real-space vs k-space label
- [ ] **Export mesh**: STL/OBJ export for isosurface
- [ ] **Export slice**: PNG/CSV export for 2D slice data

**User Expectations (from p4vasp/XCrySDen):**
- Auto-detect reasonable default iso value on load
- Real-time update when dragging iso slider (with performance throttling)
- Preserve iso value when switching between volumes in same session
- Show grid dimensions and data statistics in sidebar
- Warn if iso value is outside data range

### Map Viewer (2D Heatmap + Contour)

**Core Controls (M2 MVP):**
- [ ] **Colormap selector**: Viridis/Plasma/Inferno/Jet/User-defined
- [ ] **Value range control**: Min/max clipping for colormap (auto or manual)
- [ ] **Fermi contour overlay**: Toggle for E=0 contour lines on k-slice
- [ ] **Contour levels**: Multiple contour lines at different energy values
- [ ] **Slice selector**: kz slider for 3D → 2D projection (if source is 3D)
- [ ] **Axis labels**: kx/ky or x/y with units
- [ ] **Crosshair cursor**: Show value at mouse position (real-time)
- [ ] **Planar average plot**: 1D line plot showing min/max/average per plane (for potential/charge)

**Planar Average Viewer (from p4vasp LocalPotentialApplet):**
- [ ] **Direction selector**: X/Y/Z axis selection (radio buttons or dropdown)
- [ ] **1D plot**: Line chart showing planar statistics vs position
- [ ] **Multiple series**: Min/Max/Average as separate colored lines
- [ ] **Axis scaling**: Length in Å (from basis vector)
- [ ] **Legend**: Color-coded lines with labels
- [ ] **Auto-update**: Recompute statistics when switching direction

**2D Slice Viewer (from p4vasp STMWindowApplet):**
- [ ] **Slice direction**: XY/XZ/YZ plane selection
- [ ] **Slice position**: Slider or text input (grid index, percentage, or absolute position)
- [ ] **Slice value format**: Grid index (#n), percentage (n%), or absolute position (z Å)
- [ ] **Interpolation options**: None, linear, cubic (for smoother slice visualization)
- [ ] **Brightness/Contrast**: Adjust slice colormap range
- [ ] **Structure offset**: Shift structure visualization relative to slice plane

**Advanced Controls (Post-M2):**
- [ ] **Multiple contour levels**: Add contours at different energy values
- [ ] **Interpolation toggle**: Linear/cubic for smoother contours
- [ ] **Crosshair cursor**: Show value at mouse position
- [ ] **Profile line**: Draw line and show 1D profile plot
- [ ] **Export image**: PNG/SVG at high resolution

**User Expectations:**
- Auto-scale colormap to data range
- Smooth contour lines (not pixelated)
- Clear indication of slice position in 3D context

### Line Viewer (1D Plots)

**Current Implementation (SCF/DOS/Bands):**
- ✅ Basic line/area charts with Recharts
- ✅ Reference data overlay
- ✅ Zoom/pan

**Enhancements Needed (from p4vasp patterns):**
- [ ] **Fatband display**: Line thickness proportional to orbital weight
- [ ] **Multiple y-axes**: For combined plots (e.g., DOS + PDOS)
- [ ] **Band coloring**: Color by orbital character (s/p/d projection)
- [ ] **Export options**: PNG/SVG/CSV
- [ ] **Interactive legend**: Click to show/hide series

### Overlays (Structure Integration)

**Current (StructureViewer3D):**
- ✅ Atom spheres with element colors
- ✅ Bonds (ball-and-stick)
- ✅ Unit cell wireframe
- ✅ Display mode: primitive/supercell/conventional

**Volume Integration Requirements:**
- [ ] **Z-ordering**: Atoms rendered on top of volume (depth sorting)
- [ ] **Atom opacity**: Adjustable when overlapping with volume
- [ ] **Bond visibility**: Option to hide bonds inside volume
- [ ] **Coordinate alignment**: Ensure structure coords match volume coordinate system

### Properties Panel

**Wannier90 Properties (M3):**
- [ ] **Centers table**: List of Wannier center positions (fractional/Cartesian)
- [ ] **Spreads table**: Spread values per Wannier function
- [ ] **Visualization**: Show centers as spheres in structure viewer
- [ ] **Filtering**: Filter by spread range, center location
- [ ] **Export**: CSV export of centers/spreads

---

## C) Data Model Deltas: Schema Gaps for Volume/Map Support

### Current Schema (SCF/DOS/Bands)

```python
# Existing (analysis/parsers.py)
SCFResult: iterations, total_energy, fermi_energy, converged
DOSData: energies, dos, idos, fermi_energy
BandStructureData: k_distances, energies, high_symmetry_points
```

### Required Additions

#### VolumeArtifact Schema

**Missing Fields:**
- `grid_shape: Tuple[int, int, int]` - (nx, ny, nz)
- `origin: np.ndarray[3]` - Cartesian origin
- `basis_vectors: np.ndarray[3, 3]` - Lattice vectors defining grid cell
- `coordinate_system: Literal["real_space", "k_space"]` - Critical for Fermi surfaces
- `units: Dict[str, str]` - {"value": "e/Å³", "length": "Å"} or {"energy": "eV", "k": "2π/a"}
- `statistics: Dict` - min, max, mean, std (lazy-computed, cached)
- `binary_cache_path: Optional[Path]` - Path to .npy file (not in JSON)
- `components: List[str]` - ["total"], ["spin_up", "spin_down"], ["orbital_1", ...]
- `multi_grid: bool` - True if multiple subgrids (spin channels, orbitals)

**Metadata Only in JSON:**
- Grid dimensions and origin (small)
- Statistics summary (min/max/mean)
- Binary file path (string)
- Component names

**Not in JSON (Binary Cache):**
- Full grid data array (potentially 100s of MB)

#### MapArtifact Schema (2D)

**Missing Fields:**
- `shape: Tuple[int, int]` - (nx, ny)
- `origin: np.ndarray[2]` - 2D origin
- `basis_vectors: np.ndarray[2, 2]` - 2D grid vectors
- `data: np.ndarray` - 2D array (smaller, but still binary cache recommended)
- `source_3d: Optional[str]` - If extracted from 3D, store slice position
- `contour_levels: List[float]` - Pre-computed contour values (optional)

#### FermiSurfaceArtifact Schema (extends VolumeArtifact)

**Additional Fields:**
- `n_bands: int` - Number of bands
- `band_indices: List[int]` - Available band indices
- `fermi_energy: float` - Fermi energy (for E=0 reference)
- `reciprocal_vectors: np.ndarray[3, 3]` - Reciprocal lattice vectors
- `band_file_positions: Dict[int, int]` - File byte offsets for lazy loading
- `brillouin_zone_bounds: Optional[np.ndarray]` - Wigner-Seitz cell vertices (for clipping)

#### Channel Selection Abstraction

**User Selection Path (UI → Parser):**
- Spin channel: "total" | "spin_up" | "spin_down" | "spin_diff"
- Orbital index: For multi-orbital MLWF (0, 1, 2, ...)
- Band index: For Fermi surface (band selection UI)
- Component selector UI should query artifact metadata for available channels

**Parser Responsibility:**
- Detect available channels during parsing
- Store channel metadata in artifact JSON
- Support lazy loading of selected channel from binary cache

---

## D) Performance Strategy Recommendations

### Short-Term MVP (M1)

**Binary Cache Layer:**
- Write grid data to `.npy` immediately after parsing text
- Store metadata (grid shape, origin, vectors) in JSON
- RPC returns metadata + binary file path (not data)
- Frontend loads binary via Electron `fs.readFile` (Node.js Buffer → typed array)

**Downsampling for Preview:**
- Generate 4× downsampled preview during parsing
- Store both `volume_full.npy` and `volume_preview.npy`
- UI loads preview first (< 1 second), full on-demand
- User can toggle: "Preview" vs "Full Resolution"

**Isosurface Generation:**
- Use `three-stdlib` MarchingCubes (WebGL-compatible)
- Generate mesh on-demand when iso value changes (debounced)
- Cache mesh geometry in WebGL (dispose when iso changes)

**Memory Management:**
- Release preview grid after full load
- Unload volume from frontend memory when not visible (keep metadata)
- Python side: Keep binary files, don't keep arrays in memory after parse

### Mid-Term (M2-M3)

**Progressive Loading:**
- Load volume in chunks (tiles) for very large grids (>200³)
- Stream chunks to frontend via HTTP endpoint (if needed) or chunked file reads
- Show loading progress: "Loading chunk 3/8..."

**Mesh Optimization:**
- Vertex deduplication after Marching Cubes (reduce triangle count)
- Optional surface smoothing (Laplacian) for quality
- Mesh decimation if triangle count > 100k (LOD levels)

**Band Selection Optimization (BXSF):**
- Parse BXSF header only (band indices, grid metadata)
- Load selected band on-demand from binary cache using file positions
- Support multi-band visualization: "Show bands 5-10"

**Slice Plane Caching:**
- Pre-compute slice planes for common orientations (XY/XZ/YZ)
- Cache slice data in 2D array (separate from 3D volume)
- Update slice when volume data changes or slice position changes

### Long-Term (Post-M3)

**GPU Acceleration:**
- Use WebGL compute shaders for isosurface generation (if available)
- Offload mesh generation to GPU for real-time iso updates
- Consider WASM-based Marching Cubes for better performance

**Multi-Volume Overlay:**
- Support multiple volumes in same viewer (charge + ELF)
- Use WebGL layers or separate geometries with alpha blending
- Optimize rendering order (opaque volumes first, then transparent)

**Background Processing:**
- Parse volumes in background worker thread (Python multiprocessing)
- Show parsing progress in UI
- Queue multiple volume loads

---

## E) Updates to Architecture Plan

### New Tasks (Based on Product Intelligence)

#### M1 Additions

**Volume Viewer UI Controls:**
- [ ] **#VOL-064**: Implement auto-iso value suggestion (percentile-based)
- [ ] **#VOL-065**: Add dual isosurface toggle (±iso with separate colors)
- [ ] **#VOL-066**: Add opacity control for isosurface alpha blending
- [ ] **#VOL-067**: Add color picker per isosurface layer
- [ ] **#VOL-068**: Implement slice plane toggle and position slider

**Data Model:**
- [ ] **#VOL-069**: Add `coordinate_system` field to VolumeArtifact (real-space vs k-space)
- [ ] **#VOL-070**: Add `units` metadata dictionary to VolumeArtifact
- [ ] **#VOL-071**: Add `components` list for multi-channel volumes (spin/orbital)

**Performance:**
- [ ] **#VOL-072**: Implement 4× downsampling for preview generation
- [ ] **#VOL-073**: Add preview/full resolution toggle in UI
- [ ] **#VOL-074**: Cache mesh geometry in WebGL (dispose on iso change)

#### M2 Additions

**Fermi Surface Specific:**
- [ ] **#VOL-075**: Implement band selection UI (dropdown or range selector)
- [ ] **#VOL-076**: Add Fermi energy display and E=0 reference line
- [ ] **#VOL-077**: Implement Brillouin zone clipping for Fermi surfaces
- [ ] **#VOL-078**: Store band file positions in BXSF metadata for lazy loading

**Map Viewer:**
- [ ] **#VOL-079**: Add colormap selector (Viridis/Plasma/etc.)
- [ ] **#VOL-080**: Implement Fermi contour extraction and overlay on k-slice
- [ ] **#VOL-081**: Add kz slice selector for 3D → 2D projection

#### M3 Additions

**Multi-Component Support:**
- [ ] **#VOL-082**: Add channel selector UI (spin up/down/total/diff)
- [ ] **#VOL-083**: Implement parser detection of available channels
- [ ] **#VOL-084**: Support multiple DATAGRID_3D subgrids in XSF parser

**Supercell & Advanced Features:**
- [ ] **#VOL-085**: Add supercell tiling UI control (manual mx/my/mz or auto from k-mesh)
- [ ] **#VOL-086**: Implement coordinate system indicator in viewer UI
- [ ] **#VOL-087**: Add mesh export (STL/OBJ) functionality
- [ ] **#VOL-088**: Add slice data export (PNG/CSV)

**Properties Panel:**
- [ ] **#VOL-089**: Create PropertiesPanel component for Wannier centers/spreads table
- [ ] **#VOL-090**: Add visualization of Wannier centers as spheres in structure viewer

### Format Parser Enhancements

**XSF/BXSF Format Variants:**
- [ ] **#VOL-091**: Handle keyword variants (BEGIN_BLOCK_DATAGRID3D vs BEGIN_BLOCK_DATAGRID_3D)
- [ ] **#VOL-092**: Implement format auto-detection from file header (not just extension)
- [ ] **#VOL-093**: Add parser self-check: validate grid data order (k-fastest vs i-fastest)
- [ ] **#VOL-094**: Detect units from file metadata (e.g., "e/Å³" vs "a.u.")

**VASP Format:**
- [ ] **#VOL-095**: Detect CHG vs CHGCAR (spin-polarized) from file header
- [ ] **#VOL-096**: Support PARCHG format (partial charge, multi-component)
- [ ] **#VOL-097**: Handle ELFCAR and LOCPOT formats (different data interpretation)

### Removed/Deferred Tasks

**From Original Plan:**
- **#VOL-020** (binary streaming >50MB): Deferred to M2+ (chunked loading)
- **#VOL-021**: Same as above

**Reason**: MVP focus on binary file path return + direct file read. Streaming can be added later if needed.

### Modified Task Priorities

**Elevated to M1:**
- Dual isosurface (±iso) - Critical for MLWF visualization
- Slice planes - Essential for volume inspection
- Auto-iso suggestion - User expectation from p4vasp/XCrySDen

**Deferred to Post-M3:**
- Interactive slice plane dragging (start with fixed planes + slider)
- Color mapping by local value (start with uniform color)
- Surface smoothing (use three-stdlib default, add later if needed)

---

## License Risk Assessment

### p4vasp
- **License**: GPL v2
- **Risk**: High - Cannot copy implementation code
- **Mitigation**: Extract only product concepts (features, UI patterns, data model structure). All implementation will be original QMatSuite code.

### XCrySDen
- **License**: GPL v2 (with LGPL components)
- **Risk**: High - Cannot copy implementation code
- **Mitigation**: Extract only file format specifications (from documentation, not code). Parser implementation must be original.

### Safe Approach
1. Use format specifications from documentation/public sources (not code)
2. Design interfaces based on product needs, not implementation details
3. Implement parsers independently (test against known example files)
4. UI patterns are generic (sliders, color pickers) - not copyrighted

---

## Key Takeaways for QMatSuite

1. **Volume Viewer Must-Haves**: Auto-iso, dual ±iso, opacity, structure overlay, slice planes
2. **Data Model**: Track coordinate system, units, and multi-component channels explicitly
3. **Performance**: Binary cache + preview downsampling are essential for MVP
4. **User Expectations**: Auto-detect defaults, real-time updates, export options
5. **Multi-band Fermi Surfaces**: Lazy loading strategy is critical (don't load all bands)

This product intelligence forms the foundation for implementing volume/map visualization in QMatSuite without copying any third-party code.

---

## F) Deep Dive: Critical User Interaction Patterns

### F.1 p4vasp Volume Viewer: Complete Control Inventory

**Primary Controls (Volume Rendering):**
1. **Iso Value Control**:
   - Input: Slider (continuous) or text input (exact value)
   - Default: Auto-suggested based on data statistics (typically 90th percentile for charge density)
   - Range: Data min to max (with ±10% padding)
   - Update: Real-time (debounced for performance)
   - Multiple values: Support adding/removing iso layers (each with own color/opacity)

2. **Dual Isosurface (±iso)**:
   - Toggle: Enable/disable negative isosurface
   - Default: Disabled (only positive iso shown)
   - Behavior: When enabled, shows two isosurfaces at +iso and -iso
   - Color: Separate color pickers for positive/negative
   - Use case: Critical for orbital visualization (positive/negative lobes)

3. **Opacity Control**:
   - Input: Slider (0-100%)
   - Default: 80% (semi-transparent)
   - Effect: Alpha blending for overlapping volumes/structures

4. **Color Mapping**:
   - Mode 1: Uniform color (one color per isosurface)
   - Mode 2: Color by value (map isosurface color to local volume value at surface)
   - Colormap: Viridis/Plasma/Inferno/Jet/User-defined
   - Default: Uniform blue (#4A90E2) for charge density

5. **Supercell Tiling**:
   - Control: Three integer inputs (mx, my, mz) or auto-detect from k-mesh
   - Default: 1×1×1 (single unit cell)
   - Auto mode: If k-mesh metadata available, set tiling to match k-grid (4×4×4 k-mesh → 4×4×4 tiles)
   - Visualization: Repeat isosurface in all directions using basis vector translation

6. **Structure Overlay**:
   - Toggle: Show/hide atoms
   - Toggle: Show/hide bonds
   - Atom opacity: Adjustable when overlapping with volume
   - Bond visibility: Option to hide bonds inside volume
   - Z-ordering: Atoms always rendered on top of volume

7. **Slice Planes**:
   - Orientation: XY, XZ, YZ (orthogonal planes)
   - Position: Slider for each plane (0-100% of axis length)
   - Display mode: Line (wireframe) or filled (colormap)
   - Value display: Show volume value at slice position
   - Export: Save slice as 2D image/data

**Advanced Controls (Post-MVP):**
8. **Grid Resolution**:
   - Option: Use full grid or downsampled preview
   - Toggle: "Preview Mode" vs "Full Resolution"
   - Effect: Preview uses 4× downsampled grid (64× fewer voxels, faster rendering)

9. **Smoothing Quality**:
   - Options: Low/Medium/High triangle count
   - Effect: Low = decimated mesh (fewer triangles, faster), High = detailed (slower)
   - Default: Medium

10. **Mesh Export**:
    - Formats: STL, OBJ
    - Options: Export current iso value, or multiple values

**Additional Controls Discovered (from p4vasp StructureWindowControlApplet):**
11. **Draw as Points Toggle**:
    - Option: Render isosurface as point cloud instead of mesh
    - Use case: Quick preview, debugging mesh quality
    - Performance: Faster rendering for very dense meshes

12. **Background/Cell Color Presets**:
    - Black/White toggle buttons
    - Cell wireframe color adjustment
    - Useful for publication-quality rendering

**XCrySDen Isosurface Controls (from xc_iso command interface):**
13. **Isosurface Algorithm Selection**:
    - Options: Marching Cubes vs Tetrahedral decomposition
    - Default: Marching Cubes (standard)
    - Tetrahedral: Alternative algorithm (may produce different topology)

14. **Shade Model**:
    - Options: Smooth (Gouraud) vs Flat shading
    - Default: Smooth
    - Flat: Faster, useful for debugging normals

15. **Normal Computation**:
    - Options: Gradient-based vs Triangle face normals
    - Default: Gradient-based (smoother)
    - Triangle normals: Faster computation

16. **Smoothing Steps & Weight**:
    - Smoothing steps: Integer (0-10 typical)
    - Smoothing weight: Float (0.0-1.0)
    - Default: 0 steps (no smoothing)
    - Effect: Laplacian smoothing for surface refinement

17. **Isoplane Configuration**:
    - Multiple slice planes (ISOOBJ_PLANE1/2/3 = XY/XZ/YZ)
    - Per-plane color scheme
    - Isoline overlay on planes
    - Line width and dash style configuration

**Default Values (from XCrySDen FS_InitVar):**
- Cell type: BZ (Brillouin zone) mode (not parallelepiped)
- Crop BZ: Enabled (clip to first BZ boundaries)
- Cell display: Wireframe (not solid, not hidden)
- Draw style: Solid (not wire, not dot)
- Transparency: Disabled (opaque)
- Shade model: Smooth (not flat)
- Smoothing steps: 0 (no smoothing by default)
- Smoothing weight: 0.2 (if smoothing enabled)
- Interpolation degree: 1 (linear, per axis: [1, 1, 1])
- Front face: CW (clockwise winding)
- Revert normals: 0 (disabled)
- Antialiasing: Disabled
- Depth cuing: Disabled
- Color rotation: Per-band color cycling (6-color rainbow palette)

**Default Strategy Summary:**
- Load volume → Compute statistics → Auto-suggest iso at 90th percentile
- Show single positive isosurface with 80% opacity, blue color
- Overlay structure (atoms + bonds)
- No supercell tiling unless k-mesh metadata present
- No slice planes by default
- Marching Cubes algorithm with smooth shading and gradient normals
- BZ clipping enabled for Fermi surfaces

### F.2 p4vasp: VASP Grid File Multi-Channel Organization

**File Types & Channel Structure:**

1. **CHG** (non-spin-polarized):
   - Single channel: "total"
   - Data: One grid array

2. **CHGCAR** (spin-polarized):
   - Structure: Total charge + spin-up + spin-down
   - Format: Three consecutive grids in file
   - Channels: ["total", "spin_up", "spin_down"]
   - User selection: Choose which channel to visualize

3. **PARCHG** (partial charge):
   - Multiple orbitals: Each orbital has separate grid
   - Channels: ["orbital_0", "orbital_1", ..., "orbital_N"]
   - User selection: Select orbital index (0 to N-1)

4. **ELFCAR**:
   - Single channel: "elf" (Electron Localization Function)
   - Sometimes multi-component if spin-polarized

5. **LOCPOT**:
   - Single channel: "potential" (electrostatic potential)
   - May have multiple components for different contributions

**User Selection Path (UI Layer):**
```
File Loaded → Parser Detects Channels → UI Shows Channel Selector
  ↓
User Selects Channel → Parser Returns Selected Channel Data
  ↓
Volume Viewer Renders Selected Channel
```

**Channel Selector UI Requirements (from p4vasp ElectronicControlApplet):**
- **Spin selection** (if spin-polarized): Radio buttons or checkboxes
  - "Up" (spin 1): Show only spin-up channel
  - "Down" (spin 2): Show only spin-down channel  
  - "Up+Down" (spin 3): Show combined or both channels
- **Orbital selection** (if partial charge): Multi-select checkboxes
  - Individual orbitals: s, px, py, pz, dxy, dyz, dxz, dz2, dx2, f1-f7
  - Grouped selection: "p" selects all p-orbitals, "d" selects all d-orbitals
- **Channel detection**: UI should query artifact metadata to show available options
- **Default**: "Total" or "Up+Down" if spin-polarized, first orbital if partial charge

**UI Layout Pattern:**
- Separate controls for spin vs orbital selection
- Show/hide controls based on detected file type
- Persist user selection in session state

**Parser Responsibility (Interface Requirements for QMatSuite):**
- Parse file header to detect channel structure during initial parse
- Store channel metadata in artifact JSON: List of channel names, types, file positions, and data ranges
- Support lazy loading: Only load selected channel from file/binary cache when requested
- For multi-channel files, store channel file positions or indices for random access
- Provide channel-specific statistics (min/max/mean per channel)

**Channel Metadata Schema Requirements:**
- Channel list: Array of channel identifiers (string names)
- Channel metadata per channel:
  - File position/offset: Where to read channel data
  - Data range: Min/max values for auto-scaling
  - Channel type: "total", "spin_up", "spin_down", "orbital_N", etc.
  - Grid dimensions: Must match across all channels

**UI Channel Selection Requirements:**
- Dropdown or tab selector displaying available channels
- Per-channel metadata display (grid size, data range)
- Default selection: "Total" or first available channel
- Channel switching should be fast (lazy load, not full reparse)

### F.3 XCrySDen: XSF/BXSF Format Variants & Self-Check Strategy

**XSF Format Keyword Variants:**

1. **Structure Block Keywords:**
   - `CRYSTAL` or `ATOMS` (for molecules)
   - `PRIMVEC` (primitive lattice vectors)
   - `PRIMCOORD` or `CONVCOORD` (conventional cell)
   - Case-insensitive matching recommended

2. **DATAGRID Block Keywords:**
   - `BEGIN_BLOCK_DATAGRID3D` or `BEGIN_BLOCK_DATAGRID_3D`
   - `BEGIN_DATAGRID_3D` or `DATAGRID_3D_<name>` or `DATAGRID3D`
   - `END_DATAGRID_3D` or `END_DATAGRID3D`
   - Comment line: Optional descriptive text after BEGIN_BLOCK

3. **BXSF Format Keywords:**
   - `BEGIN_BLOCK_BANDGRID3D` or `BEGIN_BLOCK_BANDGRID_3D`
   - `BEGIN_BANDGRID_3D` or `BANDGRID_3D` or `BANDGRID3D`
   - `BAND: <index>` (band declaration)
   - `END_BANDGRID_3D` or `END_BANDGRID3D`

**Data Order Variants:**

1. **Grid Data Reading Order:**
   - XCrySDen standard: `for k in nz: for j in ny: for i in nx` (k-fastest)
   - Some variants: `for i in nx: for j in ny: for k in nz` (i-fastest)
   - **Self-check**: Compare expected count (nx*ny*nz) with actual values read
   - If mismatch: Try alternative order

2. **Value Format:**
   - Scientific notation: `1.234E-05` or `1.234e-05`
   - Fixed point: `0.00001234`
   - Values per line: Typically 6, but may vary (check line breaks)

**Parser Self-Check Strategy:**

1. **Header Validation:**
   - Check grid dimensions are positive integers
   - Check origin and vectors are valid floats
   - Verify structure block exists (for coordinate system reference)

2. **Data Count Validation:**
   - Expected: `nx * ny * nz` values
   - Actual: Count values read
   - If mismatch: Report error with context (file position, expected vs actual)

3. **Data Range Sanity Check:**
   - Compute min/max while reading
   - Flag if values are all zero, all same, or extreme outliers
   - Warn if range seems unreasonable for data type (e.g., charge density should be positive)

4. **Coordinate System Validation:**
   - Check if basis vectors form valid cell (non-zero volume)
   - Verify origin is within reasonable bounds (0-100 Å for real-space)
   - Detect k-space: If reciprocal vectors present, verify units

5. **Multi-Component Consistency:**
   - For multi-subgrid files: Verify all subgrids have same dimensions/origin/vectors
   - Only data values should differ between subgrids

**Error Handling Recommendations:**
- Graceful degradation: If variant detected, try alternative parsing
- Clear error messages: "Expected 125000 values, found 124999. Check data order or file corruption."
- Validation report: Log warnings (non-fatal) vs errors (fatal)

### F.4 XCrySDen: Fermi Surface Interaction Semantics

**Core User Interactions:**

1. **Band Selection:**
   - Input: Dropdown or list selector showing available band indices
   - Default: First band (band 0 or band 1, depending on indexing)
   - Multi-select: Option to show multiple bands simultaneously (different colors)
   - Range selection: "Show bands 5-10" for multi-band visualization

2. **Energy Reference (Fermi Energy):**
   - Display: Show Fermi energy value in UI (from BXSF metadata or user input)
   - Shift control: Optional energy offset slider (±0.5 eV range typical)
   - Default: E = 0 (Fermi energy reference)
   - Isosurface: Extract surface at selected energy (default: 0.0 eV)

3. **Brillouin Zone Cell View:**
   - Toggle: "Show BZ boundaries" (wireframe of Wigner-Seitz cell)
   - Clipping: Auto-clip isosurface to BZ boundaries (default: enabled)
   - BZ visualization: Show reciprocal lattice vectors and BZ polyhedron
   - Option: "Show full k-space grid" (disable clipping, see periodic images)

**Multi-Band Display Feature (from XCrySDen FS_Multi.tcl):**
- **Merged Bands tab**: Separate visualization showing multiple bands simultaneously
- **Band selection for merge**: User selects which bands to include in merged view
- **Per-band rendering**: Each band rendered with distinct color/opacity
- **Independent controls**: Each band tab has its own isolevel, color, transparency

**Must-Have Features (MVP):**
- Band index selector (single or multiple)
- Fermi energy display
- Isosurface at E=0 (Fermi surface)
- BZ boundary clipping (critical for correct visualization)
- Tab-based interface: One tab per selected band

**Can Defer to Later:**
- Energy shift slider (start with E=0 only)
- BZ boundary wireframe overlay (nice-to-have, not essential)
- Multi-band simultaneous display (advanced use case)
- k-space path overlay (for band structure context)

**Complete Fermi Surface UI Controls (from XCrySDen FS_Main.tcl):**

**Cell Type Selection (Radio buttons):**
- BZ mode: Display in Brillouin zone (Wigner-Seitz cell)
- Para mode: Display in reciprocal unit cell (parallelepiped)
- Default: BZ mode

**BZ Clipping Toggle:**
- Checkbox: "No crop BZ" (toggle BZ boundary clipping)
- Default: Clipping enabled
- When disabled: Shows periodic images beyond first BZ

**Cell Display Style (Radio buttons):**
- None: No cell visualization
- Wire: Wireframe of BZ/unit cell
- Solid: Solid cell with transparency
- Solid+Wire: Combined display
- Default: Wire

**Fermi Surface Display Options:**
- Draw style: Solid / Wire / Dot (point cloud)
- Transparency: 0 (opaque) or 1 (transparent) toggle
- Shade model: Smooth (default) or Flat
- Interpolation degree: Integer (1-3, affects contour smoothness)
- Front face: CW (clockwise) or CCW (counter-clockwise)
- Revert normals: 0 or 1 (flip surface orientation)

**Visualization Quality Controls:**
- Antialiasing: Enable/disable
- Depth cuing: Enable/disable (distance-based fog)
- Wire cell color: RGBA tuple (default: magenta)
- Solid cell color: RGBA tuple (default: cyan with 40% alpha)

**Status Bar Display:**
- Fermi energy value (from file)
- Min/Max energy per band
- Isolevel entry field (text input for energy value, with Return key binding)
- Spin channel indicator (if spin-polarized)

**Keyboard Shortcuts:**
- `t`: Toggle transparency
- `c`: Toggle cell display
- `p`: Toggle BZ clipping
- `d`: Toggle depth cuing
- `a`: Toggle antialiasing
- `S`: Set surface color
- `C`: Set cell color
- `L`: Toggle lighting

**User Expectations:**
- Load BXSF → Auto-select first band → Show Fermi surface (E=0)
- Band selector should list all available bands (from metadata)
- Clipping should be on by default (shows only first BZ)
- Clear indication: "Fermi surface" vs "arbitrary energy surface"
- Status bar shows Fermi energy and band energy range
- Tab-based interface: One tab per selected band
- Real-time update when changing isolevel (energy value)

**Implementation Notes:**
- Fermi surface = isosurface at E=0 (or user-selected energy)
- BZ clipping requires Wigner-Seitz cell calculation (from reciprocal vectors)
- Band data lazy-loading: Only load selected band(s) from binary cache
- Multi-band: Render each band's surface with distinct color/opacity

---

## Summary: Critical Design Decisions

**Volume Viewer MVP Must-Haves:**
1. Auto-iso suggestion (percentile-based)
2. Dual ±iso toggle (for orbitals)
3. Opacity control (alpha blending)
4. Structure overlay (atoms on volume)
5. Slice planes (XY/XZ/YZ with position slider)

**Multi-Channel Support:**
1. Parser detects available channels during parse
2. Store channel metadata in artifact JSON
3. UI provides channel selector dropdown
4. Lazy load only selected channel from binary cache

**Format Parsing Robustness:**
1. Handle keyword variants (case-insensitive, underscore variants)
2. Validate data count (expected vs actual)
3. Detect data order (k-fastest vs i-fastest)
4. Sanity check data range and coordinate system

**Fermi Surface MVP:**
1. Band selector (single or multiple, tab-based interface)
2. Fermi energy display (from file metadata)
3. Isosurface at E=0 with BZ clipping (enabled by default)
4. Lazy load bands (don't parse all bands on file open)
5. Per-band color cycling (different color for each band tab)
6. Status bar: Show min/max energy per band, isolevel input field

**Additional Fermi Surface Controls (Post-MVP, from XCrySDen):**
- Interpolation degree per axis: [1, 1, 1] to [3, 3, 3] (affects contour smoothness)
- Front/back face color: Separate color for front vs back of surface
- Surface color model: Monocolor (one color) vs front/back (two colors)
- Wire/solid/dot rendering style per band
- Toolbox/status frame show/hide toggles

