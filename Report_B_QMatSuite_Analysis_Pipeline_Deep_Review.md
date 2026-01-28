# Report B: QMatSuite Analysis Pipeline Deep Review

**Date**: 2026-01-19  
**Source**: `<HOME>/QMatSuite` (current workspace)  
**Purpose**: Deep review of QMatSuite's analysis pipeline to identify gaps, inconsistencies, and opportunities for unification

---

## Executive Summary

QMatSuite has a **partially unified** analysis pipeline. The trajectory domain is fully implemented with the intended architecture: engine-specific parsers → canonical `Trajectory` objects → `to_visual_primitives()` → visualization. However, **bands and DOS bypass this unified pipeline**: they use standalone parsers that produce non-canonical data models (`DOSData`, `BandStructureData` in `analysis/parsers.py`), which are consumed directly by plotting functions and the GUI without going through the canonical object layer. This creates architectural inconsistencies and prevents cross-engine generalization.

**Critical Findings**:
1. **Trajectory**: ✅ Fully unified (parser → canonical object → visual primitives)
2. **Bands/DOS**: ❌ Bypass canonical objects (parser → direct plotting/GUI consumption)
3. **Duplicate data models**: `DOSData`/`BandStructureData` exist in both `analysis/parsers.py` and `viz/data_models.py`
4. **Missing parser registry integration**: Bands/DOS parsers not registered in `parsers/registry.py`
5. **Inconsistent provenance**: Bands/DOS artifacts don't use `AnalysisObjectMeta`

---

## 1. Current Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Raw Output Files                          │
│  QE: relax.out, bands.dat.gnu, dos.dat, scf.out             │
│  VASP: vasprun.xml, EIGENVAL, DOSCAR                        │
│  ORCA: .out, .molden                                        │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
        ▼              ▼              ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Trajectory  │ │    Bands     │ │     DOS      │
│   Parser     │ │   Parser     │ │   Parser     │
│ (registered) │ │ (standalone) │ │ (standalone) │
└──────┬───────┘ └──────┬───────┘ └──────┬───────┘
       │                │                 │
       ▼                ▼                 ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│  Trajectory  │ │BandStructure│ │   DOSData     │
│ (canonical)   │ │    Data      │ │ (non-canonical)│
│ + Analysis    │ │(non-canonical)│ │               │
│ ObjectMeta    │ └──────┬───────┘ └──────┬───────┘
└──────┬───────┘         │                 │
       │                 │                 │
       ▼                 │                 │
┌──────────────┐         │                 │
│to_visual_    │         │                 │
│primitives()  │         │                 │
└──────┬───────┘         │                 │
       │                 │                 │
       ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────┐
│         Visualization Layer                                  │
│  - Trajectory: Uses primitives (GeometryFrames, Series1D)  │
│  - Bands/DOS: Direct consumption of DOSData/BandStructureData│
└─────────────────────────────────────────────────────────────┘
```

**Key Observation**: Trajectory follows the intended unified pipeline, but bands/DOS bypass it entirely.

---

## 2. Canonical Analysis Object Inventory

| Object Type | Location | Fields | Meta Support | Visual Primitives | Status |
|-------------|----------|--------|--------------|-------------------|--------|
| `Trajectory` | `core/analysis/trajectory/model.py:130` | `meta: AnalysisObjectMeta`, `frames: List[Frame]`, `trajectory_type: str` | ✅ `AnalysisObjectMeta` | ✅ `to_visual_primitives()` → `GeometryFrames`, `Series1D` | ✅ **Unified** |
| `DOSData` | `analysis/parsers.py:434` | `energies: np.ndarray`, `dos: np.ndarray`, `fermi_energy: float`, `idos: Optional[np.ndarray]` | ❌ No meta | ❌ No `to_visual_primitives()` | ❌ **Bypass** |
| `BandStructureData` | `analysis/parsers.py:559` | `k_distances: np.ndarray`, `energies: np.ndarray`, `high_symmetry_points: List[HighSymmetryPoint]`, `fermi_energy: float` | ❌ No meta | ❌ No `to_visual_primitives()` | ❌ **Bypass** |
| `SCFResult` | `analysis/parsers.py:89` | `iterations: List[SCFIteration]`, `fermi_energy: float`, `converged: bool` | ❌ No meta | ❌ No `to_visual_primitives()` | ❌ **Bypass** |

**Evidence**:
- **Trajectory**: `src/quantumvitas/core/analysis/trajectory/model.py:130-303`
  - Has `meta: AnalysisObjectMeta` field
  - Implements `to_visual_primitives()` method (line 255)
  - Returns `GeometryFrames` and `Series1D` primitives

- **DOSData**: `src/quantumvitas/analysis/parsers.py:434-479`
  - No `meta` field
  - No `to_visual_primitives()` method
  - Direct consumption by `plot_dos()` function

- **BandStructureData**: `src/quantumvitas/analysis/parsers.py:559-618`
  - No `meta` field
  - No `to_visual_primitives()` method
  - Direct consumption by `plot_bands()` function

---

## 3. Parser/Extractor Inventory

| Engine | Domain | Parser Class/Function | Location | Registry | Status |
|--------|--------|----------------------|----------|----------|--------|
| QE | trajectory | `QETrajectoryParser` | `drivers/qe/parsers/trajectory.py:26` | ✅ `@register_parser("qe", "trajectory")` | ✅ **Registered** |
| QE | bands | `parse_bands_gnu()` | `analysis/parsers.py:620` | ❌ Not registered | ❌ **Standalone** |
| QE | dos | `parse_dos_data()` | `analysis/parsers.py:481` | ❌ Not registered | ❌ **Standalone** |
| QE | scf | `parse_scf_output()` | `analysis/parsers.py:89` | ❌ Not registered | ❌ **Standalone** |
| VASP | dos | `parse_doscar()` | `engine/vasp_parser.py:364` | ❌ Not registered | ❌ **Standalone** |
| VASP | bands | `parse_eigenval()` | `engine/vasp_parser.py:220` | ❌ Not registered | ❌ **Standalone** |

**Evidence**:
- **Trajectory parser registration**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:25`
  ```python
  @register_parser("qe", "trajectory")
  class QETrajectoryParser:
      ...
  ```

- **Bands parser (no registration)**: `src/quantumvitas/analysis/parsers.py:620`
  ```python
  def parse_bands_gnu(...) -> BandStructureData:
      # Standalone function, not a class, not registered
  ```

- **DOS parser (no registration)**: `src/quantumvitas/analysis/parsers.py:481`
  ```python
  def parse_dos_data(path: Path | str) -> DOSData:
      # Standalone function, not a class, not registered
  ```

---

## 4. Pipeline Coverage Matrix

| Domain | Raw Discovery | Parse | Canonical Object | Derived Compute | Viz | Pin/History | Status |
|--------|--------------|-------|------------------|----------------|-----|-------------|--------|
| **trajectory** | ✅ `QETrajectoryParser.can_parse()` | ✅ `QETrajectoryParser.parse()` | ✅ `Trajectory` + `AnalysisObjectMeta` | ✅ `get_observable_series()` | ✅ `to_visual_primitives()` | ✅ Via artifact system | ✅ **OK** |
| **bands** | ⚠️ `find_bands_files()` (standalone) | ✅ `parse_bands_gnu()` | ❌ `BandStructureData` (no meta) | ⚠️ `shift_to_fermi()` (method, not layer) | ❌ Direct `plot_bands()` | ⚠️ Artifact system (no meta) | ❌ **Bypass** |
| **dos** | ⚠️ `find_dos_files()` (standalone) | ✅ `parse_dos_data()` | ❌ `DOSData` (no meta) | ⚠️ `shift_to_fermi()` (method, not layer) | ❌ Direct `plot_dos()` | ⚠️ Artifact system (no meta) | ❌ **Bypass** |
| **scf** | ⚠️ Manual file search | ✅ `parse_scf_output()` | ❌ `SCFResult` (no meta) | ❌ None | ❌ Direct `plot_scf_convergence()` | ❌ No artifact system | ❌ **Bypass** |
| **pdos** | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ **Missing** |
| **projbands** | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ **Missing** |
| **grid3d** | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ Not implemented | ❌ **Missing** |

**Evidence for each cell**:

### Trajectory (✅ OK)
- **Raw Discovery**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:34-40`
  ```python
  def can_parse(self, raw_dir: Path) -> bool:
      for pattern in ["relax.out", "vc-relax.out", "md.out"]:
          if list(raw_dir.glob(pattern)):
              return True
  ```
- **Parse**: `src/quantumvitas/drivers/qe/parsers/trajectory.py:42-92`
- **Canonical Object**: `src/quantumvitas/core/analysis/trajectory/model.py:130`
- **Derived Compute**: `src/quantumvitas/core/analysis/trajectory/model.py:158-232`
- **Viz**: `src/quantumvitas/core/analysis/trajectory/model.py:255-283`
- **Pin/History**: Via artifact system (trajectory artifacts use `AnalysisObjectMeta`)

### Bands (❌ Bypass)
- **Raw Discovery**: `src/quantumvitas/analysis/parsers.py:700-750` (`find_bands_files()`)
- **Parse**: `src/quantumvitas/analysis/parsers.py:620-697` (`parse_bands_gnu()`)
- **Canonical Object**: ❌ `BandStructureData` has no `meta` field
- **Derived Compute**: ⚠️ `shift_to_fermi()` is a method, not a separate layer
- **Viz**: `src/quantumvitas/analysis/plotting.py:200-277` (direct consumption)
- **Pin/History**: `src/quantumvitas/analysis/artifacts.py:482-656` (artifact system exists but doesn't use `AnalysisObjectMeta`)

### DOS (❌ Bypass)
- **Raw Discovery**: `src/quantumvitas/analysis/parsers.py:750-800` (`find_dos_files()`)
- **Parse**: `src/quantumvitas/analysis/parsers.py:481-543` (`parse_dos_data()`)
- **Canonical Object**: ❌ `DOSData` has no `meta` field
- **Derived Compute**: ⚠️ `shift_to_fermi()` is a method, not a separate layer
- **Viz**: `src/quantumvitas/analysis/plotting.py:68-145` (direct consumption)
- **Pin/History**: `src/quantumvitas/analysis/artifacts.py:392-479` (artifact system exists but doesn't use `AnalysisObjectMeta`)

---

## 5. Findings

### 5.1 Critical Wiring Gaps

#### Finding 1: Bands/DOS Bypass Canonical Object Layer

**Evidence**:
- `BandStructureData` and `DOSData` are defined in `analysis/parsers.py` (parsing layer)
- They are consumed directly by plotting functions (`plot_bands()`, `plot_dos()`)
- They are consumed directly by GUI via artifact JSON (`get_dos_data()`, `get_bands_data()`)

**Impact**:
- No provenance tracking (`AnalysisObjectMeta` missing)
- No unified visualization contract (`to_visual_primitives()` missing)
- Engine-specific logic leaks into visualization (plotting functions know about QE-specific formats)
- Cannot generalize to multi-engine (VASP, ORCA parsers would need separate plotting paths)

**Locations**:
- `src/quantumvitas/analysis/parsers.py:434-479` (DOSData definition)
- `src/quantumvitas/analysis/parsers.py:559-618` (BandStructureData definition)
- `src/quantumvitas/analysis/plotting.py:68-145` (plot_dos consumes DOSData directly)
- `src/quantumvitas/analysis/plotting.py:200-277` (plot_bands consumes BandStructureData directly)
- `src/quantumvitas/api.py:3338-3425` (get_dos_data returns raw dict, not canonical object)

---

#### Finding 2: Duplicate Data Models

**Evidence**:
- `DOSData` exists in both:
  - `src/quantumvitas/analysis/parsers.py:434` (parsing layer)
  - `src/quantumvitas/viz/data_models.py:33` (visualization layer)
- `BandStructureData` exists in both:
  - `src/quantumvitas/analysis/parsers.py:559` (parsing layer)
  - `src/quantumvitas/viz/data_models.py:16` (visualization layer)

**Impact**:
- Schema drift risk (two definitions can diverge)
- Confusion about which one to use
- Violates DRY principle

**Locations**:
- `src/quantumvitas/analysis/parsers.py:434` vs `src/quantumvitas/viz/data_models.py:33`
- `src/quantumvitas/analysis/parsers.py:559` vs `src/quantumvitas/viz/data_models.py:16`

---

#### Finding 3: Parser Registry Not Used for Bands/DOS

**Evidence**:
- Trajectory parser is registered: `@register_parser("qe", "trajectory")`
- Bands/DOS parsers are standalone functions, not classes, not registered
- Registry exists: `src/quantumvitas/parsers/registry.py`

**Impact**:
- Cannot auto-discover parsers for multi-engine support
- Manual routing required in API/daemon layer
- Inconsistent with trajectory pattern

**Locations**:
- `src/quantumvitas/parsers/registry.py:16-21` (registration decorator)
- `src/quantumvitas/drivers/qe/parsers/trajectory.py:25` (trajectory uses it)
- `src/quantumvitas/analysis/parsers.py:481,620` (bands/dos don't use it)

---

### 5.2 Medium Inconsistencies

#### Finding 4: Inconsistent Provenance Tracking

**Evidence**:
- Trajectory artifacts use `AnalysisObjectMeta` with `source_files`, `parser_name`, `parser_version`
- Bands/DOS artifacts are plain JSON dicts without meta structure

**Impact**:
- Cannot detect stale artifacts for bands/DOS
- Cannot track parser version changes
- Inconsistent with SSOT/history requirements

**Locations**:
- `src/quantumvitas/core/analysis/trajectory/model.py:136` (Trajectory has meta)
- `src/quantumvitas/analysis/artifacts.py:456-461` (DOS artifact is plain dict)
- `src/quantumvitas/analysis/artifacts.py:570-580` (Bands artifact is plain dict)

---

#### Finding 5: Visualization Directly Consumes Parsed Data

**Evidence**:
- `plot_dos()` accepts `DOSData` directly
- `plot_bands()` accepts `BandStructureData` directly
- Trajectory visualization uses `to_visual_primitives()` output

**Impact**:
- Visualization layer knows about parsing-layer data structures
- Cannot swap parsers without updating visualization
- Violates separation of concerns

**Locations**:
- `src/quantumvitas/analysis/plotting.py:68` (`plot_dos(dos_data: DOSData)`)
- `src/quantumvitas/analysis/plotting.py:200` (`plot_bands(band_data: BandStructureData)`)
- `src/quantumvitas/core/analysis/trajectory/model.py:255` (Trajectory uses primitives)

---

#### Finding 6: Derived Computations Mixed into Data Models

**Evidence**:
- `DOSData.shift_to_fermi()` is a method on the data model
- `BandStructureData.shift_to_fermi()` is a method on the data model
- Trajectory has `get_observable_series()` which is more like derived compute

**Impact**:
- Data models contain computation logic (should be in separate layer)
- Inconsistent with trajectory pattern (which has separate `utils.py`)

**Locations**:
- `src/quantumvitas/analysis/parsers.py:453-463` (DOSData.shift_to_fermi)
- `src/quantumvitas/analysis/parsers.py:585-595` (BandStructureData.shift_to_fermi)
- `src/quantumvitas/core/analysis/trajectory/utils.py` (separate utils module)

---

### 5.3 Minor Cleanup Opportunities

#### Finding 7: Inconsistent Unit Conventions

**Evidence**:
- Trajectory: Explicit units in docstrings (eV, Å, fs)
- Bands/DOS: Units in docstrings but not enforced in types
- No centralized unit validation

**Impact**:
- Risk of unit confusion
- No runtime validation

**Locations**:
- `src/quantumvitas/core/analysis/trajectory/model.py:42` (Frame.energy: Optional[float] = None  # eV)
- `src/quantumvitas/analysis/parsers.py:446` (energies: np.ndarray  # Energy values in eV - comment only)

---

#### Finding 8: Artifact System Bypasses Canonical Objects

**Evidence**:
- `parse_and_write_dos_artifact()` calls `parse_dos_data()` and writes `dos_data.to_dict()`
- `parse_and_write_bands_artifact()` calls `parse_bands_gnu()` and writes `band_data.to_dict()`
- No canonical object creation step

**Impact**:
- Artifacts don't have `AnalysisObjectMeta`
- Cannot use unified stale detection
- Inconsistent with trajectory artifacts

**Locations**:
- `src/quantumvitas/analysis/artifacts.py:438-461` (DOS artifact creation)
- `src/quantumvitas/analysis/artifacts.py:534-580` (Bands artifact creation)

---

## 6. Comparison with p4vasp Patterns

### 6.1 What p4vasp Patterns Could Help

#### Pattern 1: Lazy Parsing for Large Sequences

**p4vasp**: Uses `LateList` to parse sequence elements on-demand.

**QMatSuite Gap**: Bands/DOS are parsed eagerly (all k-points/energies loaded at once).

**Recommendation**: Implement lazy parsing for bands (per-k-point) and DOS (chunked) if memory becomes an issue. Not critical for current use cases.

---

#### Pattern 2: Unified Property Access

**p4vasp**: `SystemPM` provides all analysis data via properties.

**QMatSuite Gap**: Bands/DOS access is via standalone functions, not unified API.

**Recommendation**: Create `AnalysisManager` class that provides `get_bands()`, `get_dos()`, `get_trajectory()` with engine routing. This aligns with the parser registry pattern.

---

#### Pattern 3: Best-Effort Parsing

**p4vasp**: Returns `None` if parsing fails, doesn't crash.

**QMatSuite Gap**: Parsers raise exceptions on failure.

**Recommendation**: Consider returning `None` or partial results for graceful degradation, but maintain explicit error reporting for provenance.

---

### 6.2 What p4vasp Patterns Are Dangerous

#### Pattern 1: UI-Driven Parsing

**p4vasp**: Applets trigger parsing directly.

**QMatSuite Status**: ✅ Already avoids this - GUI consumes artifacts/API, not raw files.

---

#### Pattern 2: No Provenance Tracking

**p4vasp**: Doesn't track source file versions.

**QMatSuite Gap**: Bands/DOS artifacts don't use `AnalysisObjectMeta` for provenance.

**Recommendation**: ✅ Fix by adding `AnalysisObjectMeta` to bands/DOS canonical objects.

---

#### Pattern 3: Hidden Caching

**p4vasp**: May cache in hidden files (not explicitly documented).

**QMatSuite Status**: ✅ Already avoids this - explicit `.analysis/` cache with manifest.

---

## 7. Recommendations (Non-Plan)

### Recommendation 1: Unify Bands Data Model

**What**: Create canonical `Bands` object with `AnalysisObjectMeta` and `to_visual_primitives()`.

**Motivation**: 
- `src/quantumvitas/analysis/parsers.py:559` (BandStructureData has no meta)
- `src/quantumvitas/analysis/plotting.py:200` (plot_bands consumes BandStructureData directly)
- `src/quantumvitas/viz/data_models.py:16` (duplicate BandStructureData definition)

**Alignment Points**:
- Follow trajectory pattern: `core/analysis/trajectory/model.py:130`
- Add `meta: AnalysisObjectMeta` field
- Implement `to_visual_primitives()` returning `Series1D` or 2D primitives
- Move to `core/analysis/bands/model.py`

---

### Recommendation 2: Unify DOS Data Model

**What**: Create canonical `DOS` object with `AnalysisObjectMeta` and `to_visual_primitives()`.

**Motivation**:
- `src/quantumvitas/analysis/parsers.py:434` (DOSData has no meta)
- `src/quantumvitas/analysis/plotting.py:68` (plot_dos consumes DOSData directly)
- `src/quantumvitas/viz/data_models.py:33` (duplicate DOSData definition)

**Alignment Points**:
- Follow trajectory pattern: `core/analysis/trajectory/model.py:130`
- Add `meta: AnalysisObjectMeta` field
- Implement `to_visual_primitives()` returning `Series1D`
- Move to `core/analysis/dos/model.py`

---

### Recommendation 3: Move Parsing Out of UI Module

**What**: Register bands/DOS parsers in `parsers/registry.py` and route through registry.

**Motivation**:
- `src/quantumvitas/analysis/parsers.py:481,620` (standalone functions, not registered)
- `src/quantumvitas/drivers/qe/parsers/trajectory.py:25` (trajectory uses registry)
- `src/quantumvitas/parsers/registry.py:16` (registry exists but underused)

**Alignment Points**:
- Convert `parse_bands_gnu()` to `QEBandsParser` class
- Convert `parse_dos_data()` to `QEDOSParser` class
- Register with `@register_parser("qe", "bands")` and `@register_parser("qe", "dos")`
- Update API/daemon to use registry: `get_parser(engine, "bands")`

---

### Recommendation 4: Make Visualization Only Depend on Canonical Primitives

**What**: Update `plot_bands()` and `plot_dos()` to consume `to_visual_primitives()` output, not raw data models.

**Motivation**:
- `src/quantumvitas/analysis/plotting.py:68` (plot_dos accepts DOSData)
- `src/quantumvitas/analysis/plotting.py:200` (plot_bands accepts BandStructureData)
- `src/quantumvitas/core/analysis/trajectory/model.py:255` (Trajectory uses primitives)

**Alignment Points**:
- Change `plot_dos()` signature to accept `Series1D` (from `DOS.to_visual_primitives()`)
- Change `plot_bands()` signature to accept 2D primitives (from `Bands.to_visual_primitives()`)
- Remove direct `DOSData`/`BandStructureData` dependencies from plotting module

---

### Recommendation 5: Centralize Fermi Alignment / Projection Aggregation

**What**: Move `shift_to_fermi()` and projection logic to derived compute layer, not data model methods.

**Motivation**:
- `src/quantumvitas/analysis/parsers.py:453` (DOSData.shift_to_fermi is method)
- `src/quantumvitas/analysis/parsers.py:585` (BandStructureData.shift_to_fermi is method)
- `src/quantumvitas/core/analysis/trajectory/utils.py` (trajectory has separate utils)

**Alignment Points**:
- Create `core/analysis/dos/utils.py` with `shift_dos_to_fermi(dos: DOS) -> DOS`
- Create `core/analysis/bands/utils.py` with `shift_bands_to_fermi(bands: Bands) -> Bands`
- Remove methods from data models (keep data models data-only)

---

### Recommendation 6: Remove Duplicate Data Models

**What**: Delete `DOSData` and `BandStructureData` from `viz/data_models.py`, use canonical objects only.

**Motivation**:
- `src/quantumvitas/viz/data_models.py:16,33` (duplicate definitions)
- `src/quantumvitas/analysis/parsers.py:434,559` (original definitions)

**Alignment Points**:
- After creating canonical `Bands` and `DOS` objects, remove `viz/data_models.py` duplicates
- Update GUI TypeScript types to match canonical object schemas
- Ensure GUI consumes `to_visual_primitives()` output via API

---

### Recommendation 7: Add AnalysisObjectMeta to Artifact System

**What**: Update `parse_and_write_dos_artifact()` and `parse_and_write_bands_artifact()` to create canonical objects with `AnalysisObjectMeta`.

**Motivation**:
- `src/quantumvitas/analysis/artifacts.py:456` (DOS artifact is plain dict, no meta)
- `src/quantumvitas/analysis/artifacts.py:570` (Bands artifact is plain dict, no meta)
- `src/quantumvitas/core/analysis/trajectory/model.py:136` (Trajectory has meta)

**Alignment Points**:
- After creating canonical `DOS` and `Bands` objects, update artifact creation to:
  1. Parse raw files → canonical object (with `AnalysisObjectMeta`)
  2. Write canonical object to artifact (JSON serialization)
  3. Use `AnalysisObjectMeta.source_files` for stale detection

---

## 8. Evidence Citations

### Key Files

- **Trajectory Model**: `src/quantumvitas/core/analysis/trajectory/model.py`
- **Trajectory Parser**: `src/quantumvitas/drivers/qe/parsers/trajectory.py`
- **Bands Parser**: `src/quantumvitas/analysis/parsers.py:620`
- **DOS Parser**: `src/quantumvitas/analysis/parsers.py:481`
- **Bands Data Model**: `src/quantumvitas/analysis/parsers.py:559`
- **DOS Data Model**: `src/quantumvitas/analysis/parsers.py:434`
- **Duplicate Models**: `src/quantumvitas/viz/data_models.py:16,33`
- **Parser Registry**: `src/quantumvitas/parsers/registry.py`
- **Plotting Functions**: `src/quantumvitas/analysis/plotting.py`
- **Artifact System**: `src/quantumvitas/analysis/artifacts.py`
- **API Layer**: `src/quantumvitas/api.py:3338-3425` (get_dos_data, get_bands_data)

### Key Functions/Classes

- **Trajectory.to_visual_primitives**: `trajectory/model.py:255-283`
- **QETrajectoryParser**: `drivers/qe/parsers/trajectory.py:26`
- **parse_bands_gnu**: `analysis/parsers.py:620-697`
- **parse_dos_data**: `analysis/parsers.py:481-543`
- **plot_bands**: `analysis/plotting.py:200-277`
- **plot_dos**: `analysis/plotting.py:68-145`
- **parse_and_write_bands_artifact**: `analysis/artifacts.py:482-656`
- **parse_and_write_dos_artifact**: `analysis/artifacts.py:392-479`

---

**End of Report B**





