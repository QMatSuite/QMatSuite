# Volume/Fermi Surface Viewer MVP Implementation Plan

**Target:** Implement blob compiler + dev sandbox viewer for XSF/BXSF visualization using fixtures.

---

## Step 1: Repo Code Review (Read-Only)

### 1.1 Existing Analysis Artifacts System

**Location:** `src/quantumvitas/analysis/artifacts.py`

**Current Pattern:**
- **Storage:** `<calculation_dir>/analysis/<type>.json` (JSON artifacts)
- **Functions:**
  - `write_artifact(calc_dir, type, data)` → writes JSON with `_artifact_meta`
  - `read_artifact(calc_dir, type)` → reads JSON, returns dict
  - `get_analysis_dir(calc_dir)` → returns `calc_dir / "analysis"`
- **Types:** `AnalysisType` enum: `SCF`, `DOS`, `BANDS`
- **Metadata:** Each artifact includes `_artifact_meta: {analysis_type, created_at, qv_version}`

**Finding:** Artifacts are JSON-only. No binary blob storage yet. Need new directory: `<calc_dir>/analysis/blobs/` for binary data.

### 1.2 RPC Daemon Implementation

**Location:** `src/quantumvitas/daemon/server.py`

**Current Pattern:**
- **Protocol:** JSON-RPC via stdin/stdout (one JSON per line)
- **Handler Registration:** `self._handlers: Dict[str, Callable]` dictionary
- **Request/Response:** `RPCRequest(id, type, payload)` → `RPCResponse(id, ok, data/error)`
- **Handler Signature:** `def _handle_xxx(payload: Dict[str, Any]) -> Dict[str, Any]`
- **Existing Analysis Handlers:**
  - `ensure_calculation_analysis` (line 324)
  - `get_structure_vis`, `get_scf_convergence`, `get_dos_data`, `get_band_structure_data` (lines 327-331)

**Finding:** Need to add new handlers in `_handlers` dict (around line 210-363). RPC responses must be JSON-serializable (cannot return binary data directly).

### 1.3 Electron Preload API

**Location:** `gui/electron/preload.ts`

**Current Pattern:**
- **API:** `window.qv.request(type, payload)` → Promise<QVResponse>
- **Context Bridge:** `contextBridge.exposeInMainWorld('qv', qvApi)`
- **No Binary API:** Currently only has `qv.request()` for JSON-RPC, no file reading API

**Finding:** Need to add `readBlob(blob_id: string)` → Promise<ArrayBuffer> via IPC to main process. Main process must validate blob_id against allowlist before reading.

### 1.4 Existing 3D Viewer (StructureViewer3D)

**Location:** `gui/src/components/panels/StructureViewer3D.tsx`

**Current Pattern:**
- **Library:** `@react-three/fiber` + `@react-three/drei` + `three`
- **Components:** Canvas, OrbitControls, Mesh (spheres for atoms, cylinders for bonds)
- **Structure:** Props-based data flow (no RPC calls inside component)
- **Styling:** CSS file: `StructureViewer3D.css`

**Finding:** Can reuse Three.js setup pattern. Need to add MarchingCubes isosurface mesh. Component receives data as props, renders in Canvas.

### 1.5 File Locations for New Code

**Recommended Structure (Avoiding Circular Dependencies):**

```
Backend (Python):
├── src/quantumvitas/analysis/
│   ├── volume_parsers.py          # NEW: parse_xsf(), parse_bxsf()
│   ├── blob_store.py              # NEW: BlobStore (blob_id → path, allowlist)
│   └── volume_artifacts.py        # NEW: VolumeMetadata, VolumeArtifact, FermiSurfaceArtifact
├── src/quantumvitas/daemon/
│   └── server.py                  # MODIFY: Add volume compilation RPC handlers
└── tests/unit/
    ├── test_volume_parsers.py     # NEW: Parser tests
    └── test_blob_store.py         # NEW: Blob store security tests

Frontend (TypeScript/React):
├── gui/electron/
│   ├── preload.ts                 # MODIFY: Add readBlob() API
│   └── main.ts                    # MODIFY: Add IPC handler for blob reading (with allowlist)
└── gui/src/
    ├── components/panels/
    │   ├── VolumeViewerSandbox.tsx    # NEW: Dev sandbox viewer
    │   └── VolumeViewer3D.tsx         # NEW: 3D isosurface viewer (can be reused later)
    └── types/
        └── qv.ts                  # MODIFY: Add VolumeMetadata, BlobId types
```

**Dependency Direction:**
```
volume_parsers.py → volume_artifacts.py (produces artifacts)
blob_store.py → (standalone, no deps)
server.py → volume_parsers.py, blob_store.py (consumes)
preload.ts → (exposes API)
main.ts → (validates blob_id, reads file)
VolumeViewerSandbox.tsx → preload.ts (uses readBlob)
```

**Avoiding Circular Deps:**
- Parsers don't depend on daemon/server
- Blob store is standalone utility
- Artifacts are data classes (no business logic)
- Server consumes parsers (one-way)

---

## Step 2: Implementation Plan (Detailed Checklist)

### Phase 1: Backend - Blob Compiler Foundation

#### Task 1.1: Create BlobStore with Security Allowlist (index.json)
- **File:** `src/quantumvitas/analysis/blob_store.py` (NEW)
- **Deliverable:**
  - `BlobStore` class: Manages blob_id → path mapping via persistent index.json
  - `register_blob(blob_id: str, calc_dir: Path, filename: str) -> Path` - Creates blob file, registers in index.json
  - `get_blob_path(blob_id: str, calc_dir: Path) -> Optional[Path]` - Returns path if blob_id is registered (reads from index.json)
  - `validate_blob_id(blob_id: str, calc_dir: Path) -> bool` - Checks if blob_id exists in index.json
  - Storage: `<calc_dir>/analysis/blobs/<blob_id>.f32` (raw float32 little-endian binary, NOT .npy)
  - Index file: `<calc_dir>/analysis/blobs/index.json` - Format: `{"blob_id": "relative_path", ...}`
  - **Security:** All paths must be relative to `analysis/blobs/` directory. No `../` allowed. realpath validation required.
- **Blob Format:** Raw float32 little-endian binary (`.f32`). Metadata (shape, dtype, data_order) stored separately in artifact metadata JSON.
- **Security:** Only allow blob_ids registered in index.json. Path resolution must validate realpath is within `<calc_dir>/analysis/blobs/`. Reject path traversal attempts.
- **Tests:** `tests/unit/test_blob_store.py` - Registration, index.json persistence, validation, path resolution, security (reject unregistered blob_id, reject path traversal)

#### Task 1.2: Create VolumeMetadata Contract
- **File:** `src/quantumvitas/analysis/volume_artifacts.py` (NEW)
- **Deliverable:**
  - `@dataclass VolumeMetadata` with fields:
    - `grid_shape: Tuple[int, int, int]`
    - `coordinate_system: Literal["real-space", "reciprocal-space"]`
    - `origin_cart: np.ndarray` (3 float64)
    - `grid_vectors_cart: np.ndarray` (3×3 float64)
    - `lattice_vectors_cart: Optional[np.ndarray]` (3×3 float64)
    - `data_order: Literal["fortran_i_fastest", "c_k_fastest"]` (MUST be explicit, determined via format default + self-check)
      - **XSF DATAGRID_3D:** `"fortran_i_fastest"` (FORTRAN/column-major: i varies fastest)
      - **BXSF BANDGRID_3D:** `"c_k_fastest"` (C/row-major: k varies fastest)
    - `data_order_format_default: str` (the default for this format type: "XSF_DATAGRID" → "fortran_i_fastest", "BXSF_BANDGRID" → "c_k_fastest")
    - `data_order_self_check_passed: bool` (whether strict count validation passed)
    - `length_units: str = "Å"`
    - `value_units: str = "e/voxel"`
    - `blob_id: str`
    - `preview_blob_id: Optional[str]`
    - `value_min/max/mean: Optional[float]`
  - `to_dict()` method (JSON-serializable)
- **Tests:** `tests/unit/test_volume_artifacts.py` - Metadata validation, to_dict serialization

#### Task 1.3: Implement XSF Parser
- **File:** `src/quantumvitas/io/parser/volume_parsers.py` (NEW, or extend existing `io/parser/`)
- **Function:** `parse_xsf_datagrid_3d(path: Path, calc_dir: Path, blob_store: BlobStore) -> VolumeMetadata`
- **Requirements:**
  - Parse `CRYSTAL` or `ATOMS` block (structure)
  - Parse `BEGIN_BLOCK_DATAGRID3D` / `BEGIN_DATAGRID_3D` or `BEGIN_DATAGRID_3D_UNKNOWN`
  - Extract: grid dimensions (nx, ny, nz), origin, grid_vectors (3 vectors)
  - Read data values: `nx*ny*nz` floats (6 per line, handle whitespace)
  - **Data order handling (CRITICAL - NO SILENT WRONG):**
    - **Format default:** XSF DATAGRID_3D uses **FORTRAN/column-major order** = `"fortran_i_fastest"` (i varies fastest)
      - **XCrySDen specification:** "datagrid values are specified in column-major (i.e. FORTRAN) order"
      - **Equivalent Fortran:** `(((value(ix,iy,iz),ix=1,nx),iy=1,ny),iz=1,nz)`
      - **Index formula:** `idx = i + nx*(j + ny*k)` where `i ∈ [0, nx-1]`, `j ∈ [0, ny-1]`, `k ∈ [0, nz-1]`
    - **Strict count validation:** Verify `len(data) == nx*ny*nz` **exactly**. If mismatch → raise `ValueError(f"Data count mismatch: expected {nx*ny*nz}, got {len(data)}. Possible data_order issue.")`
    - **No tolerance:** Do NOT allow "~63988-64001" tolerance. Mismatch = error.
    - **Metadata:** Record `data_order="fortran_i_fastest"`, `data_order_format_default="fortran_i_fastest"`, `data_order_self_check_passed=True` (if count matches)
  - **Count validation:** Verify `len(data) == nx*ny*nz`, raise `ValueError` if mismatch (this is critical self-check)
  - Write to blob: `blob_store.register_blob(...)` → returns blob_id
  - Generate preview: Downsample by 4× (block average), register preview blob
  - Compute statistics: min/max/mean (lazy, but compute during parse)
  - Return: `VolumeMetadata` with blob_id and preview_blob_id
- **Fixtures:** Use `tests/data/wannier_3d_test/example01/gaas_00001.xsf`
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_xsf`
  - Parse gaas_00001.xsf, verify dims (40×40×40), verify data count, verify metadata fields
  - Test structure extraction (GaAs: 2 atoms)

#### Task 1.4: Implement BXSF Parser
- **File:** `src/quantumvitas/io/parser/volume_parsers.py`
- **Function:** `parse_bxsf_bandgrid_3d(path: Path, calc_dir: Path, blob_store: BlobStore) -> Dict[str, Any]`
- **Requirements:**
  - Parse `BEGIN_INFO` block (optional, extract Fermi Energy if present)
  - Parse `BEGIN_BLOCK_BANDGRID3D` / `BEGIN_BANDGRID_3D_fermi`
  - Extract: nbands, grid dimensions (nx, ny, nz), origin (k-space), reciprocal_vectors (3×3)
  - **Lazy band reading (MANDATORY for MVP):**
    - **Scan phase:** Read file once to locate all band headers and record file positions:
      - `band_file_positions: Dict[int, int] = {band_index: file_offset, ...}`
      - Use `f.tell()` before each `BAND: N` marker to record position
    - **Band extraction:** `get_band_data(band_index: int) -> np.ndarray`:
      - Seek to `band_file_positions[band_index]`
      - Read only `nx*ny*nz` floats for that band
      - Do NOT read entire file. Do NOT read all bands into memory.
  - **Data order handling (CRITICAL - NO SILENT WRONG):**
    - **Format default:** BXSF BANDGRID_3D uses **C/row-major order** = `"c_k_fastest"` (k varies fastest)
      - **XCrySDen specification:** "values inside a bandgrid are specified in row-major (i.e. C) order"
      - **Equivalent C loop:** `for i for j for k` (k varies fastest)
      - **Index formula:** `idx = k + nz*(j + ny*i)` where `i ∈ [0, nx-1]`, `j ∈ [0, ny-1]`, `k ∈ [0, nz-1]`
    - **Strict count validation:** Verify `len(band_data) == nx*ny*nz` **exactly** per band. If mismatch → raise `ValueError(f"Band {band_index} data count mismatch: expected {nx*ny*nz}, got {len(band_data)}. Possible data_order issue.")`
    - **Metadata:** Record `data_order="c_k_fastest"`, `data_order_format_default="c_k_fastest"`, `data_order_self_check_passed=True` (if count matches)
  - **Count validation:** Verify `len(band_data) == nx*ny*nz` per band, raise `ValueError` if mismatch
  - Write band 1 blob: `blob_store.register_blob(...)`
  - Generate preview: Downsample band 1 by 4×
  - Return: Metadata dict with `{artifact_id, kind: "fermi_surface", metadata: {...}, blob_id_band_1, preview_blob_id, n_bands, band_indices: [1], fermi_energy: float | None}`
- **Fixtures:** Use `tests/data/wannier_3d_test/example04/copper.bxsf` (7 bands)
- **Tests:** `tests/unit/test_volume_parsers.py::test_parse_bxsf`
  - Parse copper.bxsf, verify nbands=7, verify dims (51×51×51), verify Fermi Energy from BEGIN_INFO
  - Verify band 1 blob is written and count matches

#### Task 1.5: Downsampling Utility (with grid_vectors scaling)
- **File:** `src/quantumvitas/analysis/volume_parsers.py` (or separate `volume_utils.py`)
- **Function:** `downsample_grid(data: np.ndarray, grid_shape: Tuple[int, int, int], grid_vectors_cart: np.ndarray, factor: int = 4) -> Tuple[np.ndarray, Tuple[int, int, int], np.ndarray]`
- **Requirements:**
  - Block average: Group `factor×factor×factor` voxels, average values
  - Handle non-divisible dimensions: Use floor division `(nx // factor, ny // factor, nz // factor)`
  - Preserve data order (fortran_i_fastest remains fortran_i_fastest, c_k_fastest remains c_k_fastest)
  - **CRITICAL:** Scale grid_vectors_cart: `preview_grid_vectors = full_grid_vectors * factor` (element-wise multiplication)
  - **Origin unchanged:** `preview_origin = full_origin` (no scaling)
  - **Lattice vectors unchanged:** `preview_lattice_vectors = full_lattice_vectors` (not scaled)
- **Return:** `(downsampled_data, preview_shape, preview_grid_vectors_cart)`
- **Tests:** `tests/unit/test_volume_parsers.py::test_downsample`
  - Synthetic test: 40×40×40 grid, downsample by 4 → 10×10×10, verify averages
  - **Grid vectors test:** Verify `preview_grid_vectors[i] == full_grid_vectors[i] * factor` for all i

### Phase 2: Backend - RPC Handlers

#### Task 2.1: Add RPC Handler for Fixture Compilation
- **File:** `src/quantumvitas/daemon/server.py`
- **Handler:** `_handle_compile_fixture_volume(self, payload: Dict) -> Dict`
- **Payload:** `{"file_path": str, "calc_dir": str}` (calc_dir is dev sandbox directory)
- **Logic:**
  - Detect file type (`.xsf` → XSF, `.bxsf` → BXSF)
  - Call appropriate parser (`parse_xsf_datagrid_3d` or `parse_bxsf_bandgrid_3d`)
  - Return: `{artifact_id: str, kind: "volume" | "fermi_surface", metadata: {...}, blob_id: str, preview_blob_id: str}`
  - **No binary data in response** (only metadata + blob_id)
- **Registration:** Add to `self._handlers` dict: `"compile_fixture_volume": self._handle_compile_fixture_volume`
- **Tests:** `tests/integration/test_volume_rpc.py` - Call RPC, verify response format, verify blob files exist

#### Task 2.2: Add RPC Handler for Listing Fixtures
- **File:** `src/quantumvitas/daemon/server.py`
- **Handler:** `_handle_list_wannier_3d_fixtures(self, payload: Dict) -> Dict`
- **Payload:** (none required, or `{"fixture_dir": str}` for custom path)
- **Logic:**
  - Return fixed list of fixture paths (for dev sandbox)
  - Format: `[{"id": "gaas_00001", "name": "GaAs MLWF #1", "file_path": ".../gaas_00001.xsf", "type": "xsf"}, ...]`
  - Only return file paths that exist. Do not expose arbitrary paths to renderer.
- **Registration:** Add to `self._handlers`: `"list_wannier_3d_fixtures": self._handle_list_wannier_3d_fixtures`
- **Tests:** Verify fixture list returns expected files

### Phase 3: Frontend - Electron IPC & Preload

#### Task 3.1: Add IPC Handler in Main Process (index.json allowlist)
- **File:** `gui/electron/main.ts`
- **IPC Handler:** `ipcMain.handle('qv-read-blob', async (event, blob_id: string, calc_dir: string) => ArrayBuffer)`
- **Security Logic (MANDATORY):**
  1. Read `<calc_dir>/analysis/blobs/index.json`
  2. Lookup `blob_id` → get `relative_path` (must be relative, no `../`)
  3. Join: `blob_path = path.join(calc_dir, "analysis", "blobs", relative_path)`
  4. **realpath validation:** Resolve realpath and verify it is within `<calc_dir>/analysis/blobs/`
  5. If validation fails → throw error (reject path traversal)
  6. Read file: `fs.readFile(blob_path)` → return `ArrayBuffer`
  7. If blob_id not in index.json → throw error
- **No token mechanism:** Removed. Security via index.json allowlist + realpath validation.
- **Tests:** E2E test: Attempt to read unregistered blob_id → should fail. Attempt path traversal → should fail.

#### Task 3.2: Add readBlob API to Preload (no token)
- **File:** `gui/electron/preload.ts`
- **API:** `readBlob(blob_id: string, calc_dir: string): Promise<ArrayBuffer>`
- **Implementation:** `return ipcRenderer.invoke('qv-read-blob', blob_id, calc_dir)`
- **Expose:** Add to `qvApi` object, expose via `contextBridge`
- **TypeScript:** Update `gui/src/types/qv.ts` to include `readBlob` signature
- **Frontend usage:** After receiving blob_id from RPC, call `qv.readBlob(blob_id, calc_dir)` directly (no token needed)

### Phase 4: Frontend - Dev Sandbox Viewer

#### Task 4.1: Create VolumeViewerSandbox Component
- **File:** `gui/src/components/panels/VolumeViewerSandbox.tsx` (NEW)
- **Purpose:** Standalone dev viewer (not integrated into calculation panel yet)
- **UI Layout:**
  - Left sidebar: Fixture list (example01, example02, example04, example05)
  - Main area: 3D Canvas with isosurface
  - Right sidebar: Controls (iso value, ±iso toggle, opacity, structure overlay)
- **Data Flow:**
  - User clicks fixture → call `qv.request('compile_fixture_volume', {file_path, calc_dir})`
  - Receive metadata + blob_id_preview
  - Call `qv.readBlob(blob_id_preview, calc_dir)` → load ArrayBuffer (no token needed)
  - Parse ArrayBuffer to Float32Array (raw float32 little-endian, shape from metadata)
  - Render isosurface in Three.js

#### Task 4.2: Create VolumeViewer3D Component (Reusable)
- **File:** `gui/src/components/panels/VolumeViewer3D.tsx` (NEW)
- **Purpose:** 3D isosurface viewer (can be reused in calculation panel later)
- **Props:**
  - `volumeData: Float32Array` (1D array, reshape to grid_shape)
  - `metadata: VolumeMetadata`
  - `isoValue: number`
  - `showPositiveIso: boolean`
  - `showNegativeIso: boolean`
  - `opacity: number`
  - `showStructure: boolean`
- **Implementation:**
  - Use `@react-three/fiber` Canvas
  - Use `three-stdlib` MarchingCubes or custom implementation
  - Generate mesh from volumeData + isoValue
  - Render positive/negative isosurfaces with different colors
  - Overlay structure (atoms from metadata.structure_path or embedded structure)
- **Dependencies:** Need to check if `three-stdlib` is available, or implement basic MarchingCubes

#### Task 4.3: Add Dev Sandbox Route
- **File:** `gui/src/App.tsx` or router config
- **Route:** `/dev/volume-viewer` or `/sandbox/volume`
- **Component:** Render `VolumeViewerSandbox`
- **Navigation:** Add dev menu item or direct URL access

### Phase 5: Testing

#### Task 5.1: Parser Unit Tests
- **File:** `tests/unit/test_volume_parsers.py`
- **Tests:**
  - [ ] `test_parse_xsf_gaas_00001`: Parse gaas_00001.xsf, verify dims=40×40×40, verify structure (2 atoms), verify data count
  - [ ] `test_parse_xsf_all_gaas`: Parse all 4 gaas_*.xsf files in loop
  - [ ] `test_parse_xsf_diamond`: Parse diamond_00001.xsf (different structure)
  - [ ] `test_parse_bxsf_copper`: Parse copper.bxsf, verify nbands=7, dims=51×51×51, verify Fermi Energy=12.21
  - [ ] `test_parse_bxsf_lead`: Parse lead.bxsf, verify nbands and dims
  - [ ] `test_bxsf_lazy_band_read`: Verify that `get_band_data(1)` does not read all bands (use file position tracking or mock to verify)
  - [ ] `test_data_order_self_check_fails`: If count mismatch → raises ValueError with clear message
  - [ ] `test_downsample_40x40x40_to_10x10x10`: Synthetic grid, verify downsampling
  - [ ] `test_data_count_validation`: Invalid data count → raises error
  - [ ] `test_xsf_order_contract`: Parse XSF, verify `metadata.data_order == "fortran_i_fastest"`
  - [ ] `test_bxsf_order_contract`: Parse BXSF, verify `metadata.data_order == "c_k_fastest"`
  - [ ] `test_strict_count_validation_xsf`: If count != nx*ny*nz → raises ValueError (use `pytest.raises`)
  - [ ] `test_strict_count_validation_bxsf_band1`: Per-band count must match exactly, mismatch → raises ValueError

#### Task 5.2: Blob Store Security Tests
- **File:** `tests/unit/test_blob_store.py`
- **Tests:**
  - [ ] `test_register_blob`: Register blob, verify path exists
  - [ ] `test_get_blob_path`: Valid blob_id returns path
  - [ ] `test_validate_blob_id`: Registered blob_id → True, unregistered → False
  - [ ] `test_security_unregistered_blob_id`: Attempt to get path for unregistered blob_id → None/error
  - [ ] `test_blob_store_rejects_path_traversal`: If index.json contains `../` → must reject during validation

#### Task 5.3: RPC Integration Tests
- **File:** `tests/integration/test_volume_rpc.py`
- **Tests:**
  - [ ] `test_compile_fixture_volume_xsf`: RPC compiles XSF, returns metadata + blob_id
  - [ ] `test_compile_fixture_volume_bxsf`: RPC compiles BXSF, returns metadata + band info
  - [ ] `test_list_wannier_3d_fixtures`: RPC returns fixture list with correct paths

#### Task 5.4: E2E Tests (Optional, Post-MVP)
- **File:** `gui/tests/volume-viewer.spec.ts` (Playwright)
- **Tests:**
  - [ ] Load gaas_00001.xsf in sandbox, verify isosurface renders
  - [ ] Adjust iso slider, verify mesh updates
  - [ ] Toggle ±iso, verify both surfaces render

---

## Step 3: Acceptance Checklist

### Backend Acceptance
- [ ] XSF parser: gaas_00001.xsf parses correctly, dims=40×40×40, data count matches
- [ ] XSF parser: All 4 gaas_*.xsf files parse successfully
- [ ] BXSF parser: copper.bxsf parses, nbands=7, dims=51×51×51, Fermi Energy extracted
- [ ] BXSF parser: lead.bxsf parses successfully
- [ ] Downsampling: 40×40×40 → 10×10×10 preview generated
- [ ] Blob storage: Blobs written to `<calc_dir>/analysis/blobs/<blob_id>.f32` (raw float32)
- [ ] Blob index: `index.json` exists and contains blob_id → relative_path mapping
- [ ] Blob security: Unregistered blob_id cannot be accessed
- [ ] RPC: `compile_fixture_volume` returns metadata + blob_id (no binary data)
- [ ] Blob reading: `readBlob` validates blob_id via index.json + realpath before reading

### Frontend Acceptance
- [ ] Dev sandbox: Fixture list displays (example01, example02, example04, example05)
- [ ] XSF loading: Click gaas_00001.xsf → compiles → loads blob → renders isosurface
- [ ] ±iso rendering: Positive and negative isosurfaces render with different colors
- [ ] Iso slider: Adjusting iso value updates mesh (with debounce)
- [ ] Structure overlay: Atoms render on top of volume (if structure in XSF)
- [ ] BXSF loading: Click copper.bxsf → compiles (lazy band scan) → loads band 1 → renders Fermi surface (E=0)
- [ ] BXSF lazy loading: Band 1 extraction does not read entire file (verified via test or file position tracking)
- [ ] Band selector: UI shows band dropdown (even if only band 1 available)

### Test Coverage
- [ ] All parser tests pass (`pytest tests/unit/test_volume_parsers.py`)
- [ ] All blob store tests pass (`pytest tests/unit/test_blob_store.py`)
- [ ] All RPC tests pass (`pytest tests/integration/test_volume_rpc.py`)

---

## Step 4: Implementation Notes & Risks

### Risk 1: Data Ordering (CRITICAL - NO SILENT WRONG)
- **Risk:** XSF and BXSF use **OPPOSITE** ordering conventions. Wrong order = completely wrong visualization.
- **XCrySDen Official Specification:**
  - **XSF DATAGRID_3D:** FORTRAN/column-major = `"fortran_i_fastest"` (i varies fastest)
    - Index: `idx = i + nx*(j + ny*k)`
    - Source: https://www.xcrysden.org/doc/XSF.html
  - **BXSF BANDGRID_3D:** C/row-major = `"c_k_fastest"` (k varies fastest)
    - Index: `idx = k + nz*(j + ny*i)`
    - Source: https://www.xcrysden.org/doc/XSF.html
- **Mitigation:**
  - **Format defaults:** XSF → "fortran_i_fastest", BXSF → "c_k_fastest" (from official spec)
  - **Strict count validation:** `len(data) == nx*ny*nz` **exactly**. No tolerance. Mismatch → raise ValueError.
  - **Metadata:** Always record `data_order`, `data_order_format_default`, `data_order_self_check_passed` for transparency.
- **No fallback:** Do NOT allow override in MVP. If count mismatch, raise error (file may be corrupted or wrong format).

### Risk 2: Three.js MarchingCubes Library
- **Risk:** `three-stdlib` may not be available or incompatible
- **Mitigation:** Check package.json first. If not available, implement basic MarchingCubes (reference algorithm, not copy GPL code)

### Risk 3: Large Binary Files in Electron
- **Risk:** Loading 40×40×40 Float32Array (2.5 MB) or 51×51×51 (5.3 MB) may be slow
- **Mitigation:** Always use preview first (10×10×10 = 40 KB for 4× downsampling). Full resolution on-demand with loading indicator.
- **Blob format:** Raw float32 (.f32) is simpler than .npy for frontend parsing. Just read ArrayBuffer → Float32Array(buffer).

### Risk 4: Fixture Directory Structure
- **Risk:** Fixtures may be in different locations
- **Mitigation:** Use absolute path from repo root: `tests/data/wannier_3d_test/`

---

## Step 5: Final Delivery Instructions

### How to Start Dev Sandbox
1. Start daemon: `python -m quantumvitas.daemon.server` (or via Electron main process)
2. Start frontend: `npm run dev` (in `gui/` directory)
3. Open browser: Navigate to `http://localhost:5173/dev/volume-viewer` (or route as configured)

### How to Load Fixtures
1. In dev sandbox, left sidebar shows fixture list:
   - `example01 - GaAs MLWF (4 XSF files)`
   - `example02 - Lead Fermi Surface`
   - `example04 - Copper Fermi Surface`
   - `example05 - Diamond MLWF (4 XSF files)`
2. Click on fixture name → automatically compiles first file (gaas_00001.xsf or copper.bxsf)
3. Wait for compilation → blob loads → isosurface appears

### Expected Visualization
- **XSF (MLWF):** Isosurface shows orbital lobes. Enable ±iso to see both positive and negative lobes in different colors.
- **BXSF (Fermi Surface):** Isosurface at E=0 shows Fermi surface. Should be continuous surface (no holes).

### How to Run Tests
```bash
# Parser tests
pytest tests/unit/test_volume_parsers.py -v

# Blob store tests
pytest tests/unit/test_blob_store.py -v

# RPC integration tests
pytest tests/integration/test_volume_rpc.py -v

# All volume-related tests
pytest tests/unit/test_volume_parsers.py tests/unit/test_blob_store.py tests/integration/test_volume_rpc.py -v
```

### Known Limitations (MVP)
- [ ] Full-resolution refine not implemented (only preview)
- [ ] BZ clipping not implemented (explicitly deferred)
- [ ] Multiple band display (BXSF) not implemented (only band 1, but lazy loading infrastructure is in place)
- [ ] Supercell tiling not implemented
- [ ] Line profile / planar average not implemented
- [ ] Not integrated into calculation panel (dev sandbox only)
- [ ] Data order self-check is minimal (count validation only). Synthetic fixture check (f(i,j,k)=i+10j+100k) deferred.

---

## Step 6: Revised Milestones (Human-Verifiable)

### Milestone 1: XSF Basic Isosurface (MVP Gate)
**Goal:** Sandbox can load gaas_00001.xsf and display a single isosurface. UI does not crash.

**Acceptance:**
- [ ] Open dev sandbox route (e.g., `/dev/volume-viewer`)
- [ ] Click "gaas_00001.xsf" in fixture list
- [ ] Compilation completes (RPC returns metadata + blob_id_preview)
- [ ] Blob loads via preload.readBlob()
- [ ] 3D canvas renders an isosurface (does not need to be perfect/l漂亮, just visible)
- [ ] Iso slider works (with debounce)
- [ ] Page does not crash or freeze

**Tests (must pass):**
```bash
pytest -q tests/unit/test_volume_parsers.py::test_parse_xsf_gaas_00001_count_and_shape
pytest -q tests/unit/test_volume_parsers.py::test_compile_xsf_writes_f32_and_index
pytest -q tests/integration/test_volume_rpc.py::test_rpc_compile_fixture_returns_blob_ids
```

**How to verify:**
1. Start daemon: `python -m quantumvitas.daemon.server`
2. Start frontend: `cd gui && npm run dev`
3. Open browser: `http://localhost:5173/dev/volume-viewer`
4. Click "gaas_00001.xsf" → wait → see isosurface

---

### Milestone 2: ±iso Rendering (XSF Dual Surface)
**Goal:** Sandbox can load diamond_00001.xsf and display both positive and negative isosurfaces.

**Acceptance:**
- [ ] Load diamond_00001.xsf
- [ ] Toggle "Show positive iso" → positive surface appears (one color)
- [ ] Toggle "Show negative iso" → negative surface appears (different color)
- [ ] Both surfaces can be visible simultaneously
- [ ] Iso value slider affects both surfaces

**Tests (must pass):**
- All Milestone 1 tests still pass
- New test: `test_parse_xsf_diamond_count_and_shape`

**How to verify:**
1. Same as Milestone 1, but click "diamond_00001.xsf"
2. Enable both ±iso toggles
3. Adjust iso slider → both surfaces update

---

### Milestone 3: BXSF Fermi Surface (Lazy Band Loading)
**Goal:** Sandbox can load lead.bxsf/copper.bxsf band 1 Fermi surface. BXSF parser does NOT read entire file.

**Acceptance:**
- [ ] Load copper.bxsf → compiles (records band offsets, does not read all bands)
- [ ] Band selector UI appears (shows band 1 selected)
- [ ] Energy level input (default 0, corresponds to Fermi surface)
- [ ] Isosurface renders at E=0
- [ ] Adjust iso value → surface updates
- [ ] **Lazy loading verified:** BXSF parser only reads band 1 data (not all 7 bands)

**Tests (must pass):**
```bash
pytest -q tests/unit/test_volume_parsers.py::test_parse_bxsf_header_dims_nbands
pytest -q tests/unit/test_volume_parsers.py::test_bxsf_lazy_band_read_does_not_load_all
pytest -q tests/unit/test_volume_parsers.py::test_compile_bxsf_band1_blob_count
```

**How to verify:**
1. Same setup as Milestone 1
2. Click "copper.bxsf" or "lead.bxsf"
3. See Fermi surface (continuous surface, no holes ideally)
4. Adjust energy level / iso value → surface updates
5. Check logs/verify that parser only read band 1 (not all bands)

---

**End of Implementation Plan**

