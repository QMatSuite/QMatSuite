# Implementation Notes: Constitution Alignment

This document contains implementation details, evidence, and location references that support the Constitution (`CONSTITUTION_ZH.md`). It serves as a reference for developers and AI assistants to understand where the constitutional rules are implemented in the codebase.

**Note**: This document tracks implementation details that may change over time. The Constitution (`CONSTITUTION_ZH.md`) contains only the rules and definitions, not implementation details.

---

## [A] Resource Index & Cache Implementation

### A1: Project Root Marker
- **Marker file**: `project.qv.yml` (must exist in project root directory)
- **Finder function**: `require_project_root()` in `src/quantumvitas/core/project_utils.py`
- **Logic**: Walks upward from current directory, finds directory containing `project.qv.yml`

### A2: Resource Index Building
- **Entry function**: `build_resource_index()` in `src/quantumvitas/core/resolution.py:368-523`
- **Index class**: `ResourceIndex` in `src/quantumvitas/core/resolution.py:162-320`
- **Current implementation**: Full filesystem scan of:
  - `calculations/**/calculation.yaml`
  - `calculations/**/steps/*.step.yaml`
  - `structures/*.json`
- **No persistent cache**: Each call does full scan (see TODO: A1)

### A3: Cache Implementation (Current)
- **In-memory cache**: `DaemonState._caches` in `src/quantumvitas/daemon/server.py:82-156`
- **Cache class**: `ProjectCache` (dataclass) in `src/quantumvitas/daemon/server.py:83-93`
- **Invalidation**: Manual via `invalidate_cache()` (no automatic mtime/hash-based invalidation)
- **Location**: `src/quantumvitas/daemon/server.py:148-156`

### A4: Resource Resolution
- **Resolution functions**: `resolve_structure()`, `resolve_calculation()`, `resolve_step()` in `src/quantumvitas/core/resolution.py`
- **Selector resolution order** (in `ResourceIndex.resolve_id()`):
  1. ULID (if selector is ULID-like)
  2. Slug (exact match)
  3. Name (case-insensitive exact match)
  4. Path (legacy, for backward compatibility)
- **Location**: `src/quantumvitas/core/resolution.py:279-320`

---

## [B] Geometry & Canonicalization Implementation

### B1: Canonicalization Constants
- **WRAP_TOL**: `1e-4` defined in `src/quantumvitas/analysis/structure_viz.py:154`
- **BOUNDARY_TOL**: `0.01` defined in `src/quantumvitas/analysis/structure_viz.py:157`
- **BOUNDARY_FRAC_TOL**: `1e-6` defined in `src/quantumvitas/analysis/structure_viz.py:160` (legacy, only for debug checks)

**Verification command**:
```bash
grep -n "WRAP_TOL\|BOUNDARY_TOL\|BOUNDARY_FRAC_TOL" src/quantumvitas/analysis/structure_viz.py
```

### B2: Canonicalization Entry Points
- **Main function**: `canonicalize_structure_in_place()` in `src/quantumvitas/analysis/structure_viz.py:208`
- **Core logic**: `canonicalize_frac_coords()` in `src/quantumvitas/analysis/structure_viz.py:256`
- **Allowed call sites** (from code comments):
  - `build_display_atoms()` - GUI visualization entry (line ~1352)
  - `visualize_structure()` - High-level API entry (line ~1604)
  - `plot_structure_3d()` - Matplotlib visualization entry (line ~1835)
- **Forbidden**: Internal helpers (bond detection, supercell, boundary atoms) must NOT call canonicalization

**Verification command**:
```bash
grep -n "canonicalize_structure_in_place\|canonicalize_frac_coords" src/quantumvitas/analysis/structure_viz.py
```

### B3: Bond Detection Functions
- **Main entry**: `build_bonds()` in `src/quantumvitas/analysis/structure_viz.py` (around line 591)
- **Pure function implementations**:
  - `build_bonds_bruteforce()` - Gold standard O(N²) (line ~450)
  - `build_bonds_cell_list()` - Accelerated cell-list algorithm (line ~525)
- **Wrapper**: `detect_bonds()` - Legacy API wrapper (line ~693)
- **Contract**: All bond functions are pure geometric functions, no canonicalization/wrap/snap

**Verification command**:
```bash
grep -n "def build_bonds\|def detect_bonds" src/quantumvitas/analysis/structure_viz.py
```

### B4: Atom List Construction
- **Single source of truth**: `build_display_atoms()` in `src/quantumvitas/analysis/structure_viz.py:1320`
- **Primary/boundary derivation**: Implemented in `build_display_atoms()`, all atoms in single list with `is_boundary` flag
- **Location**: `src/quantumvitas/analysis/structure_viz.py:1320-1907`

---

## [C] QE Schema Storage Implementation

### C1: Structure I/O Functions
- **Read function**: `read_structure()` in `src/quantumvitas/io/structure_io.py:34`
- **Write function**: `write_structure()` in `src/quantumvitas/io/structure_io.py:70`
- **QE input parser**: `structure_from_qe_input()` in `src/quantumvitas/io/structure_io.py:324`
- **QE input writer**: `qe_input_from_structure()` in `src/quantumvitas/io/structure_io.py:134`

### C2: Lattice Unit Evidence
**Unit is Å (angstrom)** - Evidence from code:
1. `src/quantumvitas/io/structure_io.py:141` - Comment: "ATOMIC_POSITIONS (angstrom), CELL_PARAMETERS (angstrom)"
2. `src/quantumvitas/io/structure_io.py:192` - QE output uses `option="angstrom"`
3. `src/quantumvitas/io/structure_io.py:403` - Comment: "Quantize lattice matrix (3x3, in Angstrom)"
4. pymatgen `Structure.as_dict()` default unit is Å (pymatgen standard)

**Verification command**:
```bash
grep -n "angstrom\|Angstrom\|Å" src/quantumvitas/io/structure_io.py
```

### C3: JSON Storage Format
- **Format**: Uses pymatgen `Structure.as_dict()` format
- **Lattice**: `lattice.matrix` (3×3 matrix in Å)
- **Positions**: `sites[].abc` (fractional coordinates)
- **No QE-specific fields**: ibrav, alat, celldm are never stored in JSON
- **Location**: `src/quantumvitas/io/structure_io.py:92-104` (write_structure JSON path)

---

## [D] Pseudopotential SHA/SHATOKEN Implementation

### D1: SHA256 Implementation
- **Function**: `compute_sha256_file()` in `src/quantumvitas/core/pseudo_provenance.py:56-67`
- **Also**: `compute_sha256_bytes()` in `src/quantumvitas/core/pseudo_libinfo.py:58-68`
- **Usage**: Bitwise identical identity, deduplication, reproducible locking

### D2: SHATOKEN Implementation
- **Function**: `compute_sha_token_file()` in `src/quantumvitas/core/pseudo_libinfo.py:95-110`
- **Text function**: `compute_sha_token_text()` in `src/quantumvitas/core/pseudo_libinfo.py:71-92`
- **Algorithm** (from code):
  1. Read file as UTF-8 text (errors="replace")
  2. Split on any whitespace: `tokens = text.split()`
  3. Join with single space: `norm = " ".join(tokens)`
  4. SHA256 hash: `hashlib.sha256(norm.encode("utf-8")).hexdigest()`

**Verification command**:
```bash
grep -A 20 "def compute_sha_token" src/quantumvitas/core/pseudo_libinfo.py
```

### D3: Provenance Matching
- **Function**: `resolve_pseudo_provenance()` in `src/quantumvitas/core/pseudo_provenance.py:253-344`
- **Matching strategy**:
  1. First try SHA256 match (exact)
  2. Fallback to SHATOKEN match (semantic equivalence)
  3. Return match kind: "sha256", "sha_token", or "none"

---

## [E] Windows Toolchain Implementation

### E1: Windows Path Handling
- **Executable detection**: Handles `.exe` extension in `src/quantumvitas/core/engines/qe.py:154`
- **Test coverage**: `tests/unit/test_qe_executable_detection.py` has Windows-specific tests
- **No MinGW code**: Codebase search shows no MinGW-related code or documentation

**Verification command**:
```bash
grep -r "MinGW\|mingw" --include="*.py" --include="*.md" src/ docs/ | head -5
```

### E2: CI Configuration
- **Current CI**: `.github/workflows/tests.yml` only has `ubuntu-22.04` and `macos-14`
- **Windows CI**: Not yet implemented (acknowledged in Constitution as "not yet done")
- **Location**: `.github/workflows/tests.yml`

### E3: Windows Build Scripts
- **Status**: No Windows build/packaging scripts found in repository
- **Note**: If needed, should be documented in separate guide (see TODO: E2)

---

## Verification Commands Reference

For quick verification of implementation details:

```bash
# Resource index
grep -n "build_resource_index\|ResourceIndex" src/quantumvitas/core/resolution.py | head -10

# Canonicalization constants
grep -n "WRAP_TOL\|BOUNDARY_TOL" src/quantumvitas/analysis/structure_viz.py

# Canonicalization entry points
grep -n "canonicalize_structure_in_place" src/quantumvitas/analysis/structure_viz.py

# Bond detection
grep -n "def build_bonds\|def detect_bonds" src/quantumvitas/analysis/structure_viz.py

# Structure I/O
grep -n "def read_structure\|def write_structure" src/quantumvitas/io/structure_io.py

# Pseudopotential hashing
grep -n "compute_sha256\|compute_sha_token" src/quantumvitas/core/pseudo*.py

# Windows toolchain
grep -r "Windows\|MinGW" --include="*.py" --include="*.md" src/ docs/ | wc -l
```

---

## Notes

- This document should be updated when implementation details change.
- Line numbers may shift as code evolves - use grep commands for current locations.
- For constitutional rules, see `CONSTITUTION_ZH.md`.
- For improvement suggestions, see `docs/TODO_ADR_ALIGNMENT.md`.

