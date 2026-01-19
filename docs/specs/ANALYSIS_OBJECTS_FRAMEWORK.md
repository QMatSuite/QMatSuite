# Analysis Objects Framework Specification

**Version**: 1.1.0  
**Date**: 2026-01-19  
**Status**: PROPOSED  
**Constitution Reference**: §2 (ULID-only DAG), §3 (Geometry), §5 (Units)

---

## 0. Big Picture & Motivation

### The Two-Layer Philosophy

QMatSuite manages computational materials science workflows across multiple engines (QE, VASP, LAMMPS, ORCA, PySCF, etc.). Each engine has its own:
- Input format (INCAR vs pw.in vs .inp)
- Output format (OUTCAR vs .out vs .xyz)
- Trajectory format (XDATCAR vs .pos/.vel vs .dcd)
- Units (Ry vs eV, Bohr vs Å)
- Conventions (stress sign, cell vectors)

**Core Principle**: Separation of concerns between engine artifacts and canonical analysis.

```
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 1: Engine Artifacts (raw/)                                │
│                                                                   │
│  • Engine-native inputs and outputs                              │
│  • Engine-specific formats (OUTCAR, .out, XDATCAR, etc.)         │
│  • SSOT for execution                                            │
│  • We do NOT force a universal artifact format                   │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  Parser (one per engine × object type)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2: Canonical Analysis Objects (in-memory)                 │
│                                                                   │
│  • Engine-agnostic dataclasses                                   │
│  • Unified units (Å, eV, eV/Å, fs, GPa, K)                       │
│  • Common schema for same task type                              │
│  • All visualization/analysis targets these objects              │
│  • NO engine-specific fields in core schema                      │
└──────────────────────────────────────────────────────────────────┘
                              │
                              │  Materialization (policy-driven)
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│  LAYER 2a: Analysis Cache (.analysis/)                           │
│                                                                   │
│  • Serialized canonical objects                                  │
│  • Cache enabled by default (user-configurable)                  │
│  • Can be regenerated from raw/ anytime                          │
│  • Deletable, non-SSOT                                           │
└──────────────────────────────────────────────────────────────────┘
```

### Why This Matters Now

1. **Multi-engine MD**: We're adding VASP, LAMMPS trajectory support. Without unified representation, we'd write separate trajectory viewers per engine.

2. **Consistent user experience**: User compares DOS from QE and VASP runs. Same plotting interface, same units.

3. **Future-proofing**: Adding a new engine requires only a parser, not touching UI/viz/analysis code.

---

## 1. System Boundaries (Confirmed Decisions)

### 1.1 `raw/` — Engine Artifacts (Layer 1)

**Location**: `<calc_dir>/raw/`

**Contains**:
- Engine input files (exactly as engine saw them)
- Engine output files (exactly as engine produced them)
- Engine scratch directories (`outdir/`, `.save/`, `WAVECAR`, etc.)
- Engine-native trajectory files (XDATCAR, .pos, etc.)

**Properties**:
- **SSOT for execution**: This is what the engine actually read/wrote
- **Engine-specific format**: No requirement for uniformity
- **Never modified by analysis**: Analysis is read-only on raw/

**Evidence**: `docs/JOB_IO_DIRECTORY_SEMANTICS.md`, `src/quantumvitas/calculation/io.py:27-31`

### 1.2 `.analysis/` — Analysis Object Cache (Layer 2a)

**Location**: `<calc_dir>/.analysis/` (hidden directory, parallel to raw/)

**Contains**:
- Serialized canonical analysis objects
- Object-type subdirectories: `.analysis/trajectory/`, `.analysis/dos/`, `.analysis/bands/`
- Stale metadata for cache validation

**Properties**:
- **Non-SSOT**: Can be deleted and regenerated from raw/
- **Calc-scope**: Belongs to calculation, not project resource DAG
- **Cache enabled by default**: User can disable in Settings/Advanced
- **Deletable**: `rm -rf .analysis/` is always safe

**CONFIRMED DECISION**: Cache location is `.analysis/` (hidden, parallel to raw/).

### 1.3 `.runtime/` — Runtime Bookkeeping

**Location**: `<calc_dir>/.runtime/`

**Contains**:
- `provenance.json` — Current-only provenance map (see §1.4)
- Future: other runtime metadata

**Properties**:
- **Runtime bookkeeping only**: NOT used for run logic or stale detection
- **Current-only**: No history, just latest state
- **UI explanations**: Used for "derived from run_id X at time Y" display

### 1.4 `provenance.json` — Artifact Provenance Map

**Path**: `<calc_dir>/.runtime/provenance.json`

**Schema**:
```json
{
  "schema_version": 1,
  "updated_at": "2026-01-19T10:30:00Z",
  "files": {
    "raw/scf.out": {
      "run_id": "01JXXX...",
      "step_ulid": "01JYYY...",
      "produced_at": "2026-01-19T10:25:00Z",
      "size_bytes": 12345,
      "mtime": 1737286200.123
    },
    "raw/bands.dat.gnu": {
      "run_id": "01JXXX...",
      "step_ulid": "01JZZZ...",
      "produced_at": "2026-01-19T10:28:00Z",
      "size_bytes": 5678,
      "mtime": 1737286280.456
    }
  }
}
```

**Purpose**:
- UI explanation: "This analysis was derived from files last produced by run_id X"
- NOT used for stale detection (stale uses source_files stat directly)
- NOT used for run logic

**CONFIRMED DECISION**: Provenance is current-only, stored at `.runtime/provenance.json`.

### 1.5 `.history/` — NOT Used for Analysis Objects

**Location**: `<project_root>/.history/`

Analysis objects do NOT go into .history/:
- No trajectory caching in history
- No DOS/bands data in history
- Only small digests and pins (existing behavior)

This specification does NOT involve .history/ changes.

### 1.6 Ignore Rules for Scanning

When scanning raw/ for artifact changes, certain paths should be ignored:

**Built-in Defaults** (per engine capability):
```python
QE_SCAN_IGNORE = [
    "outdir/",
    "*.save/",
    "*.wfc*",
    "*.mix*",
]

VASP_SCAN_IGNORE = [
    "WAVECAR",
    "CHGCAR",  # Large scratch files
]
```

**Configuration Overrides** (project policy):
```yaml
# In project.qv.yml or Settings
analysis:
  scan_ignore:
    - "*.tmp"
    - "scratch/"
```

**CONFIRMED DECISION**: Ignore rules support both built-in defaults (per engine) and configuration overrides (project policy).

---

## 2. Core Abstractions

### 2.1 AnalysisObjectMeta — Unified Metadata

All analysis objects share a single metadata structure:

```python
@dataclass
class AnalysisObjectMeta:
    """
    Unified metadata for all analysis objects.
    
    CONFIRMED DECISIONS:
    - source_files paths are calc-relative (e.g., "raw/scf.out")
    - No sha256 in v1; use (size_bytes, mtime) for stale checks
    """
    # Identity
    schema_version: str                    # e.g., "1.0"
    object_type: str                       # "trajectory" | "dos" | "bands" | "scf"
    
    # Timing
    created_at: str                        # ISO 8601 when object was created
    
    # Source tracking (for stale detection)
    source_files: List["SourceFileStat"]   # Files this object was derived from
    
    # Provenance (for UI explanation only)
    run_id: Optional[str] = None           # Run that produced source files
    calc_ulid: Optional[str] = None        # Calculation ULID
    step_ulid: Optional[str] = None        # Primary step ULID
    
    # Parser info
    parser_name: str = ""                  # e.g., "qe_trajectory", "vasp_bands"
    parser_version: str = ""               # For reproducibility


@dataclass
class SourceFileStat:
    """
    Stat of a source file for stale detection.
    
    CONFIRMED DECISION: No sha256 in v1; use only (size_bytes, mtime).
    """
    path: str                              # Calc-relative path, e.g., "raw/scf.out"
    size_bytes: int                        # File size
    mtime: float                           # Modification time (Unix timestamp)
    
    # Extension point for future sha256 support
    # sha256: Optional[str] = None
```

**CONFIRMED DECISION**: `source_files` paths are calc-relative (e.g., `raw/...`), not absolute.

### 2.2 Staleness Detection

**Hard stale criterion**: Source file stat mismatch.

```python
def is_cache_stale(meta: AnalysisObjectMeta, calc_dir: Path) -> Tuple[bool, str]:
    """
    Check if cached analysis object is stale.
    
    CONFIRMED DECISION: Only hard criterion is source file stat mismatch.
    Provenance is for UI explanation only, not a stale gate.
    
    Returns:
        (is_stale, reason)
    """
    for source in meta.source_files:
        source_path = calc_dir / source.path
        
        # File missing → stale
        if not source_path.exists():
            return (True, f"Source file missing: {source.path}")
        
        stat = source_path.stat()
        
        # Size mismatch → stale
        if stat.st_size != source.size_bytes:
            return (True, f"Size changed: {source.path}")
        
        # Mtime mismatch → stale
        if abs(stat.st_mtime - source.mtime) > 0.001:  # Float tolerance
            return (True, f"Modified: {source.path}")
    
    return (False, "")
```

**UI Explanation** (using provenance.json):
```
"This bands analysis was derived from files last produced by run_id 01JXXX at 2026-01-19T10:28:00Z.
A later run_id 01JYYY at 2026-01-19T12:00:00Z updated raw/nscf.out.
Cache will be refreshed on next access."
```

### 2.3 Materialization Policy

**CONFIRMED DECISION**: Cache enabled by default; user can disable in Settings/Advanced.

```python
class MaterializationPolicy(Enum):
    """
    Policy for when to write analysis objects to disk.
    """
    ENABLED = "enabled"    # Default: cache to .analysis/
    DISABLED = "disabled"  # Never cache; always parse on demand
    
    @classmethod
    def from_settings(cls) -> "MaterializationPolicy":
        """Get policy from user settings."""
        # Read from settings; default to ENABLED
        return cls.ENABLED


@dataclass
class CacheConfig:
    """Configuration for analysis caching."""
    policy: MaterializationPolicy = MaterializationPolicy.ENABLED
    format: str = "json"              # "json" or "hdf5" for large objects
```

### 2.4 Visual Primitives — Data Only, No Style

**CONFIRMED DECISION**: Visual primitives contain data + meta only. No style fields.

```python
@dataclass
class Series1D:
    """
    1D data series for line plots.
    
    DATA ONLY - no style (color, linewidth, etc.)
    """
    x: np.ndarray
    y: np.ndarray
    x_label: str
    y_label: str
    x_unit: str
    y_unit: str
    name: Optional[str] = None
    # NO style field - styling is the viz layer's responsibility


@dataclass
class GeometryFrame:
    """
    Single frame of atomic geometry.
    
    DATA ONLY - no style
    """
    positions: np.ndarray            # (N, 3) in Å, UNWRAPPED
    species: List[str]               # N element symbols
    cell: Optional[np.ndarray]       # (3, 3) or None for molecules
    pbc: Tuple[bool, bool, bool]     # See §3.2 for cell/pbc semantics
    
    # Per-atom properties (data, not style)
    forces: Optional[np.ndarray] = None
    velocities: Optional[np.ndarray] = None


@dataclass
class GeometryFrames:
    """Sequence of geometry frames for animation."""
    frames: List[GeometryFrame]
    time: Optional[np.ndarray] = None
    iteration: Optional[np.ndarray] = None


@dataclass  
class Marker:
    """Annotation marker for plots - position only, no style."""
    position: float
    label: str
    axis: str = "x"  # "x" or "y"
    # NO style field
```

---

## 3. Trajectory Specialization

Trajectory is the first fully-specified analysis object instance.

### 3.1 Cell and PBC Semantics

**CONFIRMED DECISION**: Support both molecular (no-box) and molecular-with-box.

| System Type | `cell` | `pbc` | Meaning |
|-------------|--------|-------|---------|
| Periodic crystal | `(3, 3)` array | `(True, True, True)` | Standard PBC in all directions |
| Slab | `(3, 3)` array | `(True, True, False)` | PBC in x,y only |
| Molecule (no box) | `None` | `(False, False, False)` | No periodic images, no cell |
| Molecule with box | `(3, 3)` array | `(False, False, False)` | Cell for visualization only, no PBC |

**Rules**:
```python
def validate_cell_pbc(cell: Optional[np.ndarray], pbc: Tuple[bool, bool, bool]) -> None:
    """
    Validate cell/pbc consistency.
    
    Rules:
    1. If any pbc[i] is True, cell MUST be provided
    2. If cell is None, all pbc must be False
    3. If cell is provided, shape must be (3, 3)
    """
    if any(pbc) and cell is None:
        raise ValueError("PBC requires cell to be provided")
    if cell is None and any(pbc):
        raise ValueError("Cannot have PBC without cell")
    if cell is not None and cell.shape != (3, 3):
        raise ValueError(f"Cell must be (3, 3), got {cell.shape}")
```

### 3.2 Positions: Unwrapped Cartesian

**CONFIRMED DECISION**: Canonical positions are unwrapped Cartesian (Å).

```python
@dataclass
class Frame:
    """
    A single trajectory frame.
    
    CONFIRMED: positions are UNWRAPPED Cartesian coordinates in Å.
    Wrapping is computed later by analysis utilities, never by parser.
    """
    frame_index: int
    positions: np.ndarray              # (N, 3) UNWRAPPED Cartesian in Å
    species: List[str]
    cell: Optional[np.ndarray]         # (3, 3) or None
    pbc: Tuple[bool, bool, bool]
    
    # Time/iteration axis
    time: Optional[float] = None       # fs
    iteration: Optional[int] = None
    
    # Observables
    energy: Optional[float] = None     # eV
    forces: Optional[np.ndarray] = None  # (N, 3) eV/Å
    temperature: Optional[float] = None  # K
    pressure: Optional[float] = None     # GPa
    stress: Optional[np.ndarray] = None  # (3, 3) GPa
    kinetic_energy: Optional[float] = None  # eV
    velocities: Optional[np.ndarray] = None  # (N, 3) Å/fs
    
    # NEB
    image_index: Optional[int] = None
    
    # Atom identity
    atom_ids: Optional[List[str]] = None
```

**Wrapping Utility** (in analysis module, NOT parser):
```python
def wrap_positions(
    positions: np.ndarray,
    cell: np.ndarray,
    pbc: Tuple[bool, bool, bool],
) -> np.ndarray:
    """
    Wrap positions into cell.
    
    Called by visualization/analysis code when needed,
    NOT by parsers during parsing.
    """
    # Implementation wraps only in PBC directions
    ...
```

### 3.3 Parser Contract

```python
class TrajectoryParser(Protocol):
    """
    Contract for engine-specific trajectory parsers.
    
    Parser responsibilities:
    1. Read raw files from raw/
    2. Convert to canonical units (Å, eV, fs, K, GPa)
    3. Return unwrapped Cartesian positions
    4. Populate source_files stat for stale detection
    5. NO wrapping - return positions as-is after unit conversion
    """
    engine: str
    
    def can_parse(self, raw_dir: Path) -> bool:
        """Check if this parser can handle the raw directory."""
    
    def parse(
        self,
        raw_dir: Path,
        calc_dir: Path,
        *,
        run_id: Optional[str] = None,
        step_ulid: Optional[str] = None,
    ) -> "Trajectory":
        """
        Parse raw outputs to canonical Trajectory.
        
        MUST:
        - Convert units to canonical
        - Return unwrapped positions
        - Populate meta.source_files with stat
        - NOT wrap positions
        - NOT store engine-specific fields in Frame
        """
```

### 3.4 Trajectory Class

```python
@dataclass
class Trajectory:
    """
    Canonical trajectory representation.
    
    Supports MD, relax, and NEB.
    """
    meta: AnalysisObjectMeta
    frames: List[Frame]
    trajectory_type: str              # "md" | "relax" | "neb"
    n_images: Optional[int] = None    # For NEB
    
    @property
    def n_frames(self) -> int:
        return len(self.frames)
    
    @property
    def n_atoms(self) -> int:
        return len(self.frames[0].species) if self.frames else 0
    
    def __getitem__(self, index: int) -> Frame:
        return self.frames[index]
    
    def __iter__(self) -> Iterator[Frame]:
        return iter(self.frames)
    
    def to_visual_primitives(self) -> Dict[str, Any]:
        """Convert to visualization primitives (data only, no style)."""
        return {
            "geometry": GeometryFrames(
                frames=[
                    GeometryFrame(
                        positions=f.positions,
                        species=f.species,
                        cell=f.cell,
                        pbc=f.pbc,
                        forces=f.forces,
                    )
                    for f in self.frames
                ],
                time=np.array([f.time for f in self.frames]) if self.frames[0].time else None,
            ),
            "series_energy": self._extract_series("energy", "eV") if self._has("energy") else None,
            # ... other series
        }
```

---

## 4. Provenance Scanning & Staging Compatibility

### 4.1 Centralized Scanning API

**CONFIRMED DECISION**: Centralize scanning logic into a shared API used by provenance and staging.

**Existing code location**: `src/quantumvitas/calculation/step_artifacts.py` has artifact rules.

**New centralized module**: `src/quantumvitas/core/artifact_scanning.py`

```python
def scan_raw_directory(
    raw_dir: Path,
    ignore_patterns: List[str],
) -> Dict[str, "FileStat"]:
    """
    Scan raw directory for files, respecting ignore patterns.
    
    Used by:
    - Provenance tracking (after run)
    - Analysis staleness checks
    - Staging (future)
    
    Args:
        raw_dir: Directory to scan
        ignore_patterns: Glob patterns to ignore (e.g., "outdir/", "*.wfc*")
    
    Returns:
        Dict mapping relative paths to FileStat
    """


@dataclass
class FileStat:
    """Stat of a scanned file."""
    relative_path: str
    size_bytes: int
    mtime: float
```

### 4.2 Provenance Update Flow

**After each run/step**:

```python
def update_provenance_after_step(
    calc_dir: Path,
    run_id: str,
    step_ulid: str,
    engine: str,
) -> None:
    """
    Update provenance.json after a step completes.
    
    Flow:
    1. Get engine ignore patterns
    2. Scan raw/ directory
    3. Diff with previous scan (if any)
    4. Update provenance.json for changed/new files
    """
    ignore = get_engine_ignore_patterns(engine)
    current_files = scan_raw_directory(calc_dir / "raw", ignore)
    
    provenance = load_provenance(calc_dir)
    
    for path, stat in current_files.items():
        old_stat = provenance.files.get(path)
        if old_stat is None or stat_changed(old_stat, stat):
            # File is new or modified
            provenance.files[path] = ProvenanceEntry(
                run_id=run_id,
                step_ulid=step_ulid,
                produced_at=datetime.now(timezone.utc).isoformat(),
                size_bytes=stat.size_bytes,
                mtime=stat.mtime,
            )
    
    save_provenance(calc_dir, provenance)
```

### 4.3 Staging Compatibility

Some steps run → produce files → staging moves artifacts.

**Solution**: Provenance update occurs AFTER staging completes.

```python
# In executor or handler:
def execute_step_with_staging(step, ...):
    # 1. Execute step
    result = run_engine(...)
    
    # 2. Perform staging (e.g., copy CHGCAR)
    if needs_staging(step):
        perform_staging(...)
    
    # 3. Update provenance AFTER staging
    update_provenance_after_step(
        calc_dir=calc_dir,
        run_id=run_id,
        step_ulid=step.meta.id,
        engine=step.engine,
    )
```

**For staged files**: Provenance tracks the final location after staging, not intermediate.

---

## 5. Separation of Concerns (Invariants)

### 5.1 Canonical Core: No Engine-Specific Logic

**INVARIANT**: Core data structures (`Frame`, `Trajectory`, etc.) contain NO engine-specific fields or logic.

Engine-specific differences live ONLY in:
- Parsers (`parsers/qe/trajectory.py`, `parsers/vasp/trajectory.py`)
- Engine capability declarations (ignore patterns, defaults)

### 5.2 Visualization: Data Only

**INVARIANT**: Analysis objects emit visual primitives that are data + metadata only.

- NO style fields (color, linewidth, markers, etc.)
- Styling is the visualization layer's responsibility
- This ensures engine-agnostic analysis produces engine-agnostic visualization data

### 5.3 Materialization: Policy Not Essence

**INVARIANT**: An analysis object's identity and correctness are independent of whether it's cached.

- Object is always computed by parsing raw/ 
- Caching is an optimization
- Deleting cache never breaks functionality

---

## 6. Gap Analysis: Current vs Target

### 6.1 Aligned with Framework ✅

| Component | Evidence | Status |
|-----------|----------|--------|
| Analysis artifacts in `analysis/` | `src/quantumvitas/analysis/artifacts.py:63-75` | ✅ (but not hidden) |
| Engine-agnostic data models | `src/quantumvitas/viz/data_models.py` | ✅ |
| Separate plotting | `src/quantumvitas/analysis/plotting.py` | ✅ |
| Manifest for run tracking | `src/quantumvitas/calculation/manifest.py` | ✅ |

### 6.2 Needs Implementation ⚠️

| Gap | Current State | Target |
|-----|---------------|--------|
| Cache location | `analysis/` (visible) | `.analysis/` (hidden) |
| Provenance map | None | `.runtime/provenance.json` |
| Centralized scanning | Fragmented | `core/artifact_scanning.py` |
| Stale detection | None | source_files stat comparison |
| Trajectory object | None | Full implementation |
| Cache policy settings | None | Settings/Advanced |

---

## 7. Testing Invariants

### 7.1 Staleness Tests

```python
def test_cache_stale_when_source_missing():
    """Cache is stale when source file is deleted."""

def test_cache_stale_when_source_size_changed():
    """Cache is stale when source file size changes."""

def test_cache_stale_when_source_mtime_changed():
    """Cache is stale when source file mtime changes."""

def test_cache_not_stale_when_provenance_differs():
    """Cache NOT stale just because provenance.json has different run_id."""
```

### 7.2 Staging Compatibility Tests

```python
def test_provenance_tracks_staged_files():
    """After staging, provenance shows final file locations."""

def test_provenance_updated_after_staging_not_before():
    """Provenance update occurs after staging completes."""
```

### 7.3 Trajectory Tests

```python
def test_trajectory_cell_none_valid():
    """Trajectory with cell=None and pbc=(False,False,False) is valid."""

def test_trajectory_positions_unwrapped():
    """Parser returns unwrapped positions."""

def test_trajectory_no_engine_specific_fields():
    """Frame has no engine-specific fields."""
```

---

## 8. Open Questions (Resolved)

| Question | Resolution |
|----------|------------|
| Cache location? | `.analysis/` (hidden) |
| Cache policy default? | Enabled, configurable in Settings |
| source_files paths? | Calc-relative |
| Stale detection? | (size_bytes, mtime) only, no sha256 v1 |
| Provenance location? | `.runtime/provenance.json` |
| Visual primitives style? | No style fields |
| cell semantics? | None for molecular, (3,3) for periodic/box |
| positions format? | Unwrapped Cartesian Å |

---

## Appendix A: Code Evidence

| File | Content |
|------|---------|
| `src/quantumvitas/analysis/artifacts.py` | Current analysis caching (`analysis/` visible) |
| `src/quantumvitas/calculation/manifest.py` | Run manifest at `.run_tmp_info/manifest.json` |
| `src/quantumvitas/calculation/step_artifacts.py` | Artifact rules per step type |
| `src/quantumvitas/execution/vasp_staging.py` | VASP staging (CHGCAR, WAVECAR) |
| `src/quantumvitas/calculation/runner.py` | Run orchestration, manifest updates |
| `src/quantumvitas/execution/executor.py` | Job execution, post-processing |

---

**End of Specification**
