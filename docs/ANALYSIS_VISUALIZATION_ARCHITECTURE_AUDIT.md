# QMatSuite Analysis/Visualization Architecture Audit + Incremental Design

## 1. Review Findings

### 1.1 Current Analysis Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              CURRENT DATA FLOW                                       │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  QE Outputs          Parser Layer           Storage/Cache        RPC Layer   UI     │
│  ──────────          ────────────           ─────────────        ─────────   ──     │
│                                                                                      │
│  *.out              parsers.py              analysis/            server.py          │
│  *.dat      ──────► parse_scf_output() ──► scf.json    ──────► get_scf_*    ──►    │
│  *.gnu              parse_dos_data()        dos.json            get_dos_*         │
│                     parse_bands_gnu()       bands.json          get_bands_*        │
│                            │                    │                   │               │
│                            └── dataclasses ─────┴─── JSON ──────────┘               │
│                             (SCFResult,        (via artifacts.py)  (via QVService)  │
│                              DOSData,                                               │
│                              BandStructureData)                                     │
│                                                                                      │
│  UI Components:                                                                      │
│  ──────────────                                                                      │
│  AnalysisPanel.tsx ──► ScfConvergenceChart (Recharts LineChart)                     │
│                    ──► DosChart (Recharts AreaChart)                                │
│                    ──► BandsChart (Recharts LineChart)                              │
│                                                                                      │
│  StructureViewer3D.tsx ──► Three.js/react-three-fiber (spheres, cylinders, lines)   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Current Schema & Storage Conventions

**Directory Convention:**
```
<calculation_dir>/analysis/<type>.json
```

**Current AnalysisType enum** (`src/quantumvitas/analysis/artifacts.py`):

```python
class AnalysisType(str, Enum):
    SCF = "scf"
    DOS = "dos"
    BANDS = "bands"
```

**Key Data Structures** (`src/quantumvitas/analysis/parsers.py`):

| Dataclass | Fields | Storage |
|-----------|--------|---------|
| `SCFResult` | iterations, total_energy, fermi_energy, converged | JSON arrays |
| `DOSData` | energies (ndarray), dos (ndarray), idos, fermi_energy | JSON arrays via `.tolist()` |
| `BandStructureData` | k_distances, energies (2D ndarray), high_symmetry_points | JSON nested arrays |

**Caching Strategy** (in `artifacts.py`):
1. Check if artifact exists via `artifact_exists()`
2. If exists and not `force=True`: read from cache via `read_artifact()`
3. If not exists or `force`: parse raw output, write via `write_artifact()`
4. Artifacts include metadata: `_artifact_meta: {analysis_type, created_at, qv_version}`

### 1.3 Missing "Unified Artifact Abstraction"

**Current State: NO unified abstraction exists.** Each analysis type has its own:
- Parser function
- Dataclass
- Write/read logic
- RPC handler

**What's needed:**

```python
# Proposed: src/quantumvitas/analysis/artifact_types.py

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, Optional
from pathlib import Path

class ArtifactKind(str, Enum):
    """High-level artifact categories."""
    LINE = "line"       # 1D: bands, DOS, SCF convergence, AHC curves
    MAP = "map"         # 2D: k-slice heatmap, Fermi contours, planar average
    VOLUME = "volume"   # 3D: charge density, potential, ELF, MLWF
    PROPERTIES = "properties"  # Scalar/structured: Wannier centers, spreads

class BaseArtifact(ABC):
    """Base class for all analysis artifacts."""
    
    @property
    @abstractmethod
    def kind(self) -> ArtifactKind:
        """Return the artifact kind."""
        
    @property
    @abstractmethod
    def type_name(self) -> str:
        """Return the specific artifact type (e.g., 'bands', 'charge_density')."""
        
    @abstractmethod
    def to_metadata(self) -> Dict[str, Any]:
        """Return JSON-serializable metadata (small, for index)."""
        
    @abstractmethod
    def serialize(self, path: Path) -> None:
        """Write artifact to disk (may include binary data)."""
        
    @classmethod
    @abstractmethod
    def deserialize(cls, path: Path) -> "BaseArtifact":
        """Read artifact from disk."""
```

### 1.4 File Locations for New Abstractions

**Recommended placement (following existing module boundaries):**

| Component | Location | Rationale |
|-----------|----------|-----------|
| `ArtifactKind`, `BaseArtifact` | `src/quantumvitas/analysis/artifact_types.py` | New file, alongside existing `artifacts.py` |
| `VolumeArtifact` | `src/quantumvitas/analysis/volume_artifacts.py` | Separate due to size/complexity |
| `MapArtifact` | `src/quantumvitas/analysis/map_artifacts.py` | Separate file for 2D data |
| XSF/Cube/BXSF parsers | `src/quantumvitas/io/parser/volume_parsers.py` | Following existing `qe_parser.py` pattern |
| Volume viewer component | `gui/src/components/panels/VolumeViewer3D.tsx` | Alongside `StructureViewer3D.tsx` |
| Binary cache utils | `src/quantumvitas/analysis/binary_cache.py` | Separate binary I/O from JSON logic |

**Dependency Direction:**
```
analysis/artifact_types.py  ← analysis/artifacts.py (extends)
                           ← analysis/volume_artifacts.py
                           ← analysis/map_artifacts.py
                           
io/parser/volume_parsers.py → analysis/volume_artifacts.py (produces)

daemon/server.py → analysis/* (consumes, no circular deps)
```

### 1.5 UI Layer Changes Needed

**Current Navigation Structure** (implicit in `CalculationAnalysisPanel.tsx`):
- Step tabs (SCF, DOS, BANDS, etc.)
- View mode toggle (Text / Plot)

**Proposed Navigation Extension:**

```
┌─────────────────────────────────────────────────────────────┐
│  Analysis Panel                                              │
├──────────────────────────────────────────────────────────────┤
│  Category:   [Lines ▼]  [Maps ▼]  [Volumes ▼]  [Properties] │
├──────────────────────────────────────────────────────────────┤
│  Lines:                                                      │
│    ├─ Bands (from bands step)                               │
│    ├─ DOS / PDOS (from dos step)                            │
│    ├─ SCF Convergence (from scf step)                       │
│    └─ AHC / Berry (future)                                  │
│                                                              │
│  Maps:                                                       │
│    ├─ k-slice Fermi surface (from pp.x / Wannier90)         │
│    └─ Planar average (from pp.x)                            │
│                                                              │
│  Volumes:                                                    │
│    ├─ Charge density (.xsf / .cube)                         │
│    ├─ MLWF isosurfaces (.xsf from Wannier90)                │
│    ├─ ELF / Potential (.cube)                               │
│    └─ Fermi surface (.bxsf)                                 │
│                                                              │
│  Properties:                                                 │
│    ├─ Wannier centers & spreads                             │
│    └─ Band character / orbital weights                       │
└─────────────────────────────────────────────────────────────┘
```

**New Component Locations:**

| Component | File | Purpose |
|-----------|------|---------|
| `VolumeViewer3D` | `gui/src/components/panels/VolumeViewer3D.tsx` | Isosurface + slice viewer using Three.js |
| `MapViewer2D` | `gui/src/components/panels/MapViewer2D.tsx` | Heatmap + contour viewer |
| `PropertiesPanel` | `gui/src/components/panels/PropertiesPanel.tsx` | Table/list of scalar properties |
| `ArtifactNavigator` | `gui/src/components/panels/ArtifactNavigator.tsx` | Category + artifact selector |

**State Management:**
- Use existing pattern: `useState` for local UI state, RPC calls for data
- Add `useVolumeData` hook mirroring existing `useQVClient` pattern
- For large volumes: streaming/chunked loading with progress indicator

### 1.6 Performance & File Size Concerns

**Critical Issue: Current JSON-over-IPC architecture cannot handle large volumes.**

Analysis of current IPC path:
```typescript
// gui/electron/preload.ts
qvApi.request = async (type, payload) => {
  return ipcRenderer.invoke('qv-request', request);
};

// daemon/server.py - all responses go through JSON
def _send_response(self, response: RPCResponse) -> None:
    line = json.dumps(response_dict) + "\n"
    self.stdout.write(line)
```

**Volume data sizes:**
- Typical charge density: 100×100×100 grid = 1M points × 8 bytes = 8 MB
- Fine MLWF grid: 200×200×200 = 64 MB
- Multiple spin/orbital components: multiply by 4-8x

**Proposed Solutions:**

```
┌─────────────────────────────────────────────────────────────────┐
│  Binary Cache + Streaming Strategy                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. BINARY CACHE (Python side):                                  │
│     ┌─────────────────────────────────────────────────────────┐ │
│     │ analysis/                                                │ │
│     │   ├─ volume_metadata.json  (small, ~1KB)                │ │
│     │   │   {                                                  │ │
│     │   │     "type": "charge_density",                        │ │
│     │   │     "grid": [100, 100, 100],                         │ │
│     │   │     "origin": [0, 0, 0],                             │ │
│     │   │     "voxel_size": [0.1, 0.1, 0.1],                   │ │
│     │   │     "value_range": [-0.5, 2.3],                      │ │
│     │   │     "binary_path": "charge.npy"                      │ │
│     │   │   }                                                  │ │
│     │   └─ charge.npy  (binary, 8MB)                          │ │
│     └─────────────────────────────────────────────────────────┘ │
│                                                                  │
│  2. RPC RETURNS FILE PATH (not data):                           │
│     get_volume_artifact() → {                                    │
│       "metadata": {...},                                         │
│       "binary_path": "/abs/path/to/charge.npy",                 │
│       "format": "numpy"                                          │
│     }                                                            │
│                                                                  │
│  3. FRONTEND LOADS BINARY DIRECTLY (via Node fs or fetch):      │
│     VolumeViewer3D reads binary via Electron's fs.readFile      │
│     OR: Python serves via HTTP streaming (future)               │
│                                                                  │
│  4. DOWNSAMPLING FOR PREVIEW:                                    │
│     Parser writes both:                                          │
│       - charge_full.npy (original resolution)                   │
│       - charge_preview.npy (downsampled 4x)                     │
│     UI loads preview first, then full on demand                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.7 Test Coverage Gaps

**Current test coverage:**

| Area | File | Status |
|------|------|--------|
| SCF parser | `tests/unit/test_analysis_parsers.py` | ✅ Good |
| DOS parser | `tests/unit/test_analysis_parsers.py` | ✅ Good |
| Bands parser | `tests/unit/test_analysis_parsers.py` | ✅ Good |
| Artifact read/write | `tests/unit/test_analysis_artifacts.py` | ✅ Exists |
| API band structure | `tests/unit/test_api_get_band_structure_data.py` | ✅ Exists |
| **Volume parsers** | - | ❌ Missing |
| **XSF/Cube/BXSF parsing** | - | ❌ Missing |
| **Binary cache** | - | ❌ Missing |
| **RPC volume handlers** | - | ❌ Missing |
| **UI smoke tests for volume** | - | ❌ Missing |

---

## 2. Proposed Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                           PROPOSED ARCHITECTURE                                      │
├─────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                             BACKEND (Python)                                  │   │
│  ├──────────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                               │   │
│  │  io/parser/                  analysis/                 daemon/                │   │
│  │  ─────────────               ─────────                 ───────                │   │
│  │  qe_parser.py               artifact_types.py          server.py             │   │
│  │  volume_parsers.py ──────►  │ ArtifactKind            │ get_volume_list()   │   │
│  │  │ parse_xsf()              │ BaseArtifact            │ get_volume_meta()   │   │
│  │  │ parse_cube()             │ LineArtifact            │ get_volume_path()   │   │
│  │  │ parse_bxsf()        ───► │ MapArtifact         ───►│ ensure_volume()     │   │
│  │  │ downsample_grid()        │ VolumeArtifact          │                     │   │
│  │                             │ PropertiesArtifact       │                     │   │
│  │                             └─────────────────────────                       │   │
│  │                                                                               │   │
│  │                             artifacts.py (extended)                           │   │
│  │                             │ ensure_analysis_artifact()                     │   │
│  │                             │ ensure_volume_artifact()  ← NEW                │   │
│  │                             │ write_binary_artifact()   ← NEW                │   │
│  │                             │ read_volume_metadata()    ← NEW                │   │
│  │                                                                               │   │
│  │                             binary_cache.py ← NEW                             │   │
│  │                             │ write_numpy_array()                            │   │
│  │                             │ read_numpy_array()                             │   │
│  │                             │ compute_downsampled()                          │   │
│  │                                                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │                            FRONTEND (React/Electron)                          │   │
│  ├──────────────────────────────────────────────────────────────────────────────┤   │
│  │                                                                               │   │
│  │  types/qv.ts                components/panels/                               │   │
│  │  ──────────                 ─────────────────                                │   │
│  │  + VolumeMetadata          + VolumeViewer3D.tsx                              │   │
│  │  + MapMetadata               │ Three.js isosurface                           │   │
│  │  + ArtifactCatalog           │ MarchingCubes / GPU                           │   │
│  │  + BinaryLoadStatus          │ Slice planes                                  │   │
│  │                              │ Supercell tiling                              │   │
│  │                                                                               │   │
│  │  hooks/                     + MapViewer2D.tsx                                │   │
│  │  ───────                      │ Heatmap canvas                               │   │
│  │  + useVolumeData.ts           │ Fermi contour overlay                        │   │
│  │  + useBinaryLoader.ts                                                        │   │
│  │                             + ArtifactNavigator.tsx                          │   │
│  │                               │ Category tabs                                │   │
│  │                               │ Artifact list                                │   │
│  │                                                                               │   │
│  │  electron/                                                                    │   │
│  │  ─────────                                                                    │   │
│  │  + preload.ts                                                                │   │
│  │    + readBinaryFile()  ← NEW (fs.readFile for local numpy)                   │   │
│  │                                                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                      │
└─────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Milestones + Tasks

### Milestone 1: VolumeArtifact + XSF/Cube + Basic Isosurface

**Goal:** Parse XSF/Cube files from QE pp.x or Wannier90, display isosurfaces in UI.

**Duration:** ~2 weeks

| Task | Description | File(s) |
|------|-------------|---------|
| **M1.1** | Create `ArtifactKind` enum and `BaseArtifact` ABC | `analysis/artifact_types.py` |
| **M1.2** | Implement XSF parser | `io/parser/volume_parsers.py` |
| **M1.3** | Implement Cube parser | `io/parser/volume_parsers.py` |
| **M1.4** | Create `VolumeArtifact` dataclass | `analysis/volume_artifacts.py` |
| **M1.5** | Implement binary cache (numpy save/load) | `analysis/binary_cache.py` |
| **M1.6** | Add `ensure_volume_artifact()` with downsampling | `analysis/artifacts.py` |
| **M1.7** | Add RPC handlers: `get_volume_list`, `get_volume_metadata` | `daemon/server.py` |
| **M1.8** | Add Electron IPC for binary file reading | `gui/electron/preload.ts` |
| **M1.9** | Create `VolumeViewer3D` component with MarchingCubes | `gui/src/components/panels/VolumeViewer3D.tsx` |
| **M1.10** | Add isosurface controls (±iso value slider) | `VolumeViewer3D.tsx` |
| **M1.11** | Add slice plane controls | `VolumeViewer3D.tsx` |
| **M1.12** | Add TypeScript types for volume data | `gui/src/types/qv.ts` |
| **M1.13** | Unit tests: XSF/Cube parsers | `tests/unit/test_volume_parsers.py` |
| **M1.14** | Unit tests: Binary cache | `tests/unit/test_binary_cache.py` |
| **M1.15** | Integration test: RPC volume workflow | `tests/integration/test_volume_rpc.py` |

### Milestone 2: BXSF (Fermi Surface) + MapArtifact + k-slice

**Goal:** Parse BXSF Fermi surface files, add 2D k-slice heatmap viewer.

**Duration:** ~1.5 weeks

| Task | Description | File(s) |
|------|-------------|---------|
| **M2.1** | Implement BXSF parser | `io/parser/volume_parsers.py` |
| **M2.2** | Create `FermiSurfaceArtifact` (extends VolumeArtifact) | `analysis/volume_artifacts.py` |
| **M2.3** | Add Fermi surface rendering (3D isosurface at E=0) | `VolumeViewer3D.tsx` |
| **M2.4** | Create `MapArtifact` dataclass | `analysis/map_artifacts.py` |
| **M2.5** | Add k-slice extraction from BXSF | `analysis/map_artifacts.py` |
| **M2.6** | Create `MapViewer2D` component | `gui/src/components/panels/MapViewer2D.tsx` |
| **M2.7** | Add Fermi contour overlay on k-slice | `MapViewer2D.tsx` |
| **M2.8** | Add RPC handlers: `get_fermi_surface`, `get_kslice` | `daemon/server.py` |
| **M2.9** | Unit tests: BXSF parser | `tests/unit/test_volume_parsers.py` |
| **M2.10** | E2E test: Load copper.bxsf and display | `gui/tests/volume-viewer.spec.ts` |

### Milestone 3: Engine Adapters + Properties Panel

**Goal:** Add pp.x workflow integration, VASP support, Wannier90 properties display.

**Duration:** ~2 weeks

| Task | Description | File(s) |
|------|-------------|---------|
| **M3.1** | Create `pp.x` step type and template | `calculation/step_defaults.py`, `workflow/templates.py` |
| **M3.2** | Add pp.x input generator | `io/generator/qe_generator.py` |
| **M3.3** | Add automatic pp.x output detection | `calculation/step_artifacts.py` |
| **M3.4** | Add VASP CHGCAR parser | `io/parser/volume_parsers.py` |
| **M3.5** | Add VASP ELFCAR/LOCPOT parser | `io/parser/volume_parsers.py` |
| **M3.6** | Create `PropertiesArtifact` for Wannier90 data | `analysis/properties_artifacts.py` |
| **M3.7** | Parse Wannier90 .wout for centers/spreads | `io/parser/wannier90_parsers.py` |
| **M3.8** | Create `PropertiesPanel` component | `gui/src/components/panels/PropertiesPanel.tsx` |
| **M3.9** | Add supercell tiling for MLWF display | `VolumeViewer3D.tsx` |
| **M3.10** | Add navigation tabs (Lines/Maps/Volumes/Properties) | `gui/src/components/panels/ArtifactNavigator.tsx` |
| **M3.11** | Integration test: pp.x workflow end-to-end | `tests/integration/test_ppx_workflow.py` |
| **M3.12** | Add quantum chemistry Cube import (Gaussian/ORCA) | `io/parser/volume_parsers.py` |

---

## 4. Concrete TODO List (GitHub Issues)

### Epic: Volume/Map Visualization Support

#### Backend: Parsers & Artifacts

- [ ] **#VOL-001**: Create `ArtifactKind` enum and `BaseArtifact` ABC in `analysis/artifact_types.py`
- [ ] **#VOL-002**: Implement XSF file parser (`parse_xsf()`) in `io/parser/volume_parsers.py`
- [ ] **#VOL-003**: Implement Gaussian Cube parser (`parse_cube()`) in `io/parser/volume_parsers.py`
- [ ] **#VOL-004**: Implement BXSF (XCrySDen Fermi surface) parser in `io/parser/volume_parsers.py`
- [ ] **#VOL-005**: Create `VolumeArtifact` dataclass with grid metadata
- [ ] **#VOL-006**: Implement binary cache module (`binary_cache.py`) with numpy I/O
- [ ] **#VOL-007**: Add grid downsampling utility for preview generation
- [ ] **#VOL-008**: Extend `artifacts.py` with `ensure_volume_artifact()`
- [ ] **#VOL-009**: Create `MapArtifact` for 2D data (k-slice, planar average)
- [ ] **#VOL-010**: Add Wannier90 .wout parser for centers/spreads

#### Backend: RPC Layer

- [ ] **#VOL-011**: Add RPC handler `list_volume_artifacts` (returns metadata only)
- [ ] **#VOL-012**: Add RPC handler `get_volume_metadata` (returns grid info + binary path)
- [ ] **#VOL-013**: Add RPC handler `get_fermi_surface_metadata`
- [ ] **#VOL-014**: Add RPC handler `get_kslice_data` (returns 2D array for specific kz)
- [ ] **#VOL-015**: Add RPC handler `get_wannier_properties` (centers, spreads)

#### Frontend: TypeScript Types

- [ ] **#VOL-016**: Add `VolumeMetadata` interface to `types/qv.ts`
- [ ] **#VOL-017**: Add `MapData` interface to `types/qv.ts`
- [ ] **#VOL-018**: Add `WannierProperties` interface to `types/qv.ts`
- [ ] **#VOL-019**: Extend `QVCommandMap` with volume RPC types

#### Frontend: Electron IPC

- [ ] **#VOL-020**: Add `readBinaryFile` method to preload API for local numpy loading
- [ ] **#VOL-021**: Add binary file streaming support for large volumes (>50MB)

#### Frontend: Volume Viewer Component

- [ ] **#VOL-022**: Create `VolumeViewer3D.tsx` shell with Three.js Canvas
- [ ] **#VOL-023**: Implement MarchingCubes isosurface extraction (use `three-stdlib`)
- [ ] **#VOL-024**: Add dual isosurface rendering (±iso for orbitals)
- [ ] **#VOL-025**: Add iso value slider control with real-time update
- [ ] **#VOL-026**: Add slice plane controls (XY/XZ/YZ at specified position)
- [ ] **#VOL-027**: Add structure overlay (atoms rendered on top of volume)
- [ ] **#VOL-028**: Add supercell tiling for MLWF (repeat based on k-mesh)
- [ ] **#VOL-029**: Add loading state and progress indicator for large volumes

#### Frontend: Map Viewer Component

- [ ] **#VOL-030**: Create `MapViewer2D.tsx` shell with canvas
- [ ] **#VOL-031**: Implement heatmap rendering (color scale for band values)
- [ ] **#VOL-032**: Add Fermi contour overlay extraction and rendering
- [ ] **#VOL-033**: Add kz slice selector for 3D → 2D projection

#### Frontend: Navigation & Integration

- [ ] **#VOL-034**: Create `ArtifactNavigator.tsx` with category tabs (Lines/Maps/Volumes/Properties)
- [ ] **#VOL-035**: Integrate ArtifactNavigator into CalculationAnalysisPanel
- [ ] **#VOL-036**: Create `PropertiesPanel.tsx` for Wannier centers/spreads table

#### Testing

- [ ] **#VOL-037**: Unit tests for XSF parser with real test data
- [ ] **#VOL-038**: Unit tests for Cube parser with real test data
- [ ] **#VOL-039**: Unit tests for BXSF parser with copper.bxsf from Wannier90 examples
- [ ] **#VOL-040**: Unit tests for binary cache (write/read roundtrip)
- [ ] **#VOL-041**: Integration test for volume RPC handlers
- [ ] **#VOL-042**: E2E test: Load XSF file and display isosurface
- [ ] **#VOL-043**: E2E test: Load BXSF and display Fermi surface

#### Engine Integration

- [ ] **#VOL-044**: Add `pp` step type for pp.x post-processing
- [ ] **#VOL-045**: Create pp.x input template (plot_num, filplot options)
- [ ] **#VOL-046**: Add automatic artifact detection for pp.x outputs
- [ ] **#VOL-047**: Add VASP CHGCAR/ELFCAR/LOCPOT parsers
- [ ] **#VOL-048**: Add quantum chemistry Cube import (Gaussian, ORCA)

---

## 5. Verification Criteria (from Requirements)

### Wannier90 Solution Booklet Workflow

- [ ] MLWF isosurfaces display with ±iso values
- [ ] Supercell periodic images rendered based on k-mesh (e.g., 4×4×4 → 4×4×4 copies)
- [ ] copper.bxsf Fermi surface displays correctly

### QE pp.x Integration

- [ ] Cube/XSF files from pp.x open in UI and display isosurface
- [ ] Slice planes work for charge density inspection

### Performance Requirements

- [ ] Large data (>10MB) does NOT go through JSON
- [ ] Binary files stored on disk, path returned via RPC
- [ ] Frontend loads binary directly via Electron fs
- [ ] Preview downsampling for initial load < 1 second

### Test Coverage

- [ ] Parser tests: XSF, Cube, BXSF
- [ ] Binary cache tests: roundtrip integrity
- [ ] RPC contract tests: volume handlers
- [ ] UI smoke tests: VolumeViewer3D renders

---

## 6. Design Considerations for Volume Data Handling

**Note:** This section outlines high-level design requirements for QMatSuite volume visualization. For comprehensive product intelligence on UI controls, interaction patterns, data models, format specifications, and performance strategies derived from analysis of established visualization tools, see `docs/PRODUCT_INTELLIGENCE_P4VASP_XCRYSDEN.md`.

### 6.1 Volume Data Access Requirements

**Periodic Boundary Handling:**
- Volume artifacts should support both wrapped and unwrapped grid access
- Wrapped access: Automatic periodic boundary conditions (essential for supercell visualization)
- Unwrapped access: Direct grid indexing without wrapping (for gradient calculations)
- Support for negative indices with proper wrapping behavior

### 6.2 Isosurface Generation Considerations

**Algorithm Options:**
- Standard Marching Cubes (WebGL-compatible via three-stdlib) - recommended for MVP
- Alternative: Tetrahedral decomposition (6-tetrahedron per cube) - more control, post-MVP
- Both approaches generate triangle meshes with normals

**Quality Controls:**
- Vertex deduplication: Merge duplicate vertices to avoid surface cracks
- Surface smoothing: Optional Laplacian smoothing for refinement (configurable steps/weight)
- Normal computation: Gradient-based (smoother) vs face-based (faster)
- Shade model: Smooth (Gouraud) vs flat shading

**Supercell Visualization:**
- Support tiling isosurface in multiple unit cells
- Use basis vector translation for periodic repeats
- Auto-detect tiling from k-mesh metadata when available

### 6.3 Format Parsing Requirements

**XSF/BXSF Format Handling:**
- Support keyword variants (case-insensitive, with/without underscores)
- Handle multiple subgrids in single file (spin channels, orbitals)
- Extract structure information from XSF file (avoid requiring separate structure file)
- Store grid data in binary cache immediately after parsing text

**Data Order Detection:**
- Validate grid data count (expected vs actual)
- Support different reading orders (k-fastest vs i-fastest)
- Provide clear error messages if data count mismatches

**Multi-Band Support (BXSF):**
- Parse header to get band count and indices
- Store file positions for each band (lazy loading)
- Support loading selected bands without parsing entire file

### 6.4 Binary Cache Strategy

**Storage Pattern:**
- Write grid data to binary file (`.npy`) immediately during text parsing
- Store only metadata in JSON (grid dimensions, origin, vectors, file path)
- Keep metadata in memory, load grid data on-demand from binary cache
- Support preview generation: Downsampled version for fast initial display

**Performance Optimization:**
- Generate 4× downsampled preview during parse
- Store both full and preview binary files
- UI loads preview first (< 1 second), full resolution on-demand

---

This architecture builds incrementally on QMatSuite's existing patterns while adding the capability to handle large volumetric data essential for MLWF visualization and Fermi surface analysis. The key innovation is the binary cache layer that avoids JSON serialization of large arrays, combined with a unified artifact abstraction that scales to future analysis types.

**Reference:** For detailed product intelligence on UI controls, data models, format specifications, and performance strategies derived from analysis of established visualization tools, see `docs/PRODUCT_INTELLIGENCE_P4VASP_XCRYSDEN.md`.

