# CP2K Implementation Plan

**Version**: v2.0 (Alignment Update)
**Last Updated**: 2026-01-20
**Target**: QMatSuite v2-python branch

---

## Critical Directives

1. **DO NOT reuse existing recipe classes** - Create `CP2KRecipe` from scratch
2. **DO NOT add workdir cleanup** - CP2K accumulates artifacts (unlike VASP)
3. **DO NOT create new variant_id algorithm** - Use existing SHA256 machinery
4. **DO NOT stage CP2K data files** - Rely on CP2K_DATA_DIR
5. **DO NOT persist restart_from** - Resolve predecessor at runtime
6. **DO NOT reference raw/scan/ for dependencies** - Always use runtime SSOT (`raw/<step_ulid>/`)
7. **USE mtime-based artifact selection** - NOT numeric suffix parsing
8. **INCLUDE cell file output** - For trajectory cell information
9. **DISABLE MD incremental skip** - `supports_incremental_skip=False` for cp2k_md
10. **IMPLEMENT preflight checks** - As general feature with CP2K declarations

---

## Alignment Summary (v4)

| Decision | Implementation |
|----------|----------------|
| Runtime SSOT | `raw/<step_ulid>/` - ALWAYS the source of truth |
| Scan archive | `raw/scan/<variant_key>/` - POST-RUN ARCHIVE ONLY |
| Latest selection | **mtime-based** (NOT numeric suffix) |
| Cell handling | Separate `.cell` file for MD/relax |
| MD skip | **Disabled** (`supports_incremental_skip=False`) |
| Preflight | General feature, CP2K declares requirements |

---

## Phase 0: Heuristic Exploration (Auto)

**Goal**: Run CP2K locally, capture outputs, understand file patterns.

### 0.1 Prerequisites

```bash
# Verify CP2K is available
which cp2k.ssmp
# Expected: /opt/homebrew/bin/cp2k.ssmp

cp2k.ssmp --version
# Expected: CP2K version 2025.1 ...

# Verify data directory
ls /opt/homebrew/share/cp2k/data/
# Should contain: BASIS_MOLOPT, GTH_POTENTIALS, etc.
```

### 0.2 Smoke Test 1: SCF Single-Point

**Purpose**: Verify basic execution and output parsing.

**Test Structure**: 2-atom silicon (diamond)

**Input file** (`test_scf.inp`):
```
&GLOBAL
  PROJECT cp2k_calc
  RUN_TYPE ENERGY_FORCE
  PRINT_LEVEL MEDIUM
&END GLOBAL

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 300
      REL_CUTOFF 50
    &END MGRID
    &QS
      EPS_DEFAULT 1.0E-10
    &END QS
    &SCF
      EPS_SCF 1.0E-6
      MAX_SCF 50
      &DIAGONALIZATION
        ALGORITHM STANDARD
      &END DIAGONALIZATION
      &MIXING
        METHOD BROYDEN_MIXING
        ALPHA 0.4
      &END MIXING
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
    &PRINT
      &MO
        &EACH
          QS_SCF 0
        &END EACH
      &END MO
    &END PRINT
  &END DFT
  &SUBSYS
    &CELL
      A 5.431 0.0 0.0
      B 0.0 5.431 0.0
      C 0.0 0.0 5.431
    &END CELL
    &COORD
      Si 0.0 0.0 0.0
      Si 1.3578 1.3578 1.3578
    &END COORD
    &KIND Si
      BASIS_SET SZV-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
  &END SUBSYS
  &PRINT
    &FORCES ON
    &END FORCES
  &END PRINT
&END FORCE_EVAL
```

**Run command**:
```bash
mkdir -p /tmp/cp2k_smoke_scf
cd /tmp/cp2k_smoke_scf
# Create test_scf.inp with content above
cp2k.ssmp -i test_scf.inp -o output.log
```

**Expected files**:
| File | Must Exist | Content Check |
|------|------------|---------------|
| `output.log` | Yes | Contains "SCF CONVERGED" |
| `cp2k_calc-RESTART.wfn` | Yes | Binary file > 0 bytes |

**Parse targets**:
- Total energy: `ENERGY| Total FORCE_EVAL ( QS ) energy:`
- Forces: `ATOMIC FORCES in` section
- SCF convergence: iteration count

**Acceptance criteria**:
- [ ] `output.log` created
- [ ] Contains "SCF run converged"
- [ ] Energy extracted (approximately -7.8 Ha for Si2)
- [ ] `.wfn` file created

### 0.3 Smoke Test 2: Geometry Optimization (with Cell Output)

**Purpose**: Verify GEO_OPT and structure extraction with cell information.

**Input file** (`test_relax.inp`):
```
&GLOBAL
  PROJECT cp2k_calc
  RUN_TYPE GEO_OPT
&END GLOBAL

&MOTION
  &GEO_OPT
    OPTIMIZER BFGS
    MAX_ITER 50
    MAX_FORCE 1.0E-4
    MAX_DR 1.0E-3
    RMS_FORCE 5.0E-5
    RMS_DR 5.0E-4
  &END GEO_OPT
  &PRINT
    &TRAJECTORY
      FORMAT XYZ
      &EACH
        GEO_OPT 1
      &END EACH
    &END TRAJECTORY
    &CELL
      &EACH
        GEO_OPT 1
      &END EACH
    &END CELL
    &RESTART
      &EACH
        GEO_OPT 1
      &END EACH
    &END RESTART
  &END PRINT
&END MOTION

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 300
      REL_CUTOFF 50
    &END MGRID
    &SCF
      EPS_SCF 1.0E-6
      MAX_SCF 50
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      A 5.431 0.0 0.0
      B 0.0 5.431 0.0
      C 0.0 0.0 5.431
    &END CELL
    &COORD
      Si 0.0 0.0 0.0
      Si 1.4 1.4 1.4
    &END COORD
    &KIND Si
      BASIS_SET SZV-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
```

**Run command**:
```bash
mkdir -p /tmp/cp2k_smoke_relax
cd /tmp/cp2k_smoke_relax
cp2k.ssmp -i test_relax.inp -o output.log
```

**Expected files**:
| File | Must Exist | Content Check |
|------|------------|---------------|
| `output.log` | Yes | Contains "GEOMETRY OPTIMIZATION COMPLETED" |
| `cp2k_calc-pos-1.xyz` | Yes | XYZ trajectory |
| `cp2k_calc-1.cell` | **Yes (NEW)** | Cell vectors per step |
| `cp2k_calc.restart` or `cp2k_calc-N.restart` | Maybe | Full restart |
| `cp2k_calc-RESTART.wfn` | Yes | Wavefunction |

**Parse targets**:
- Final structure: Last frame of `cp2k_calc-pos-1.xyz` + cell from `.cell`
- Optimization converged: "GEOMETRY OPTIMIZATION COMPLETED"
- Energy history: From trajectory comment lines
- Cell evolution: From `.cell` file

**Acceptance criteria**:
- [ ] Trajectory file created (`cp2k_calc-pos-1.xyz`)
- [ ] **Cell file created (`cp2k_calc-1.cell`)**
- [ ] Contains multiple frames
- [ ] Last frame extractable as Structure with correct cell
- [ ] Final coordinates ≠ initial (optimization occurred)

### 0.4 Smoke Test 3: Short MD (with Cell Output for NPT)

**Purpose**: Verify MD trajectory, energy parsing, and cell evolution.

**Input file** (`test_md.inp`):
```
&GLOBAL
  PROJECT cp2k_calc
  RUN_TYPE MD
&END GLOBAL

&MOTION
  &MD
    ENSEMBLE NVT
    STEPS 10
    TIMESTEP 1.0
    TEMPERATURE 300
    &THERMOSTAT
      TYPE CSVR
      &CSVR
        TIMECON 50
      &END CSVR
    &END THERMOSTAT
  &END MD
  &PRINT
    &TRAJECTORY
      FORMAT XYZ
      &EACH
        MD 1
      &END EACH
    &END TRAJECTORY
    &CELL
      &EACH
        MD 1
      &END EACH
    &END CELL
    &RESTART
      &EACH
        MD 5
      &END EACH
    &END RESTART
    &ENERGY
      &EACH
        MD 1
      &END EACH
    &END ENERGY
  &END PRINT
&END MOTION

&FORCE_EVAL
  METHOD Quickstep
  &DFT
    BASIS_SET_FILE_NAME BASIS_MOLOPT
    POTENTIAL_FILE_NAME GTH_POTENTIALS
    &MGRID
      CUTOFF 200
      REL_CUTOFF 40
    &END MGRID
    &SCF
      EPS_SCF 1.0E-5
      MAX_SCF 30
    &END SCF
    &XC
      &XC_FUNCTIONAL PBE
      &END XC_FUNCTIONAL
    &END XC
  &END DFT
  &SUBSYS
    &CELL
      A 5.431 0.0 0.0
      B 0.0 5.431 0.0
      C 0.0 0.0 5.431
    &END CELL
    &COORD
      Si 0.0 0.0 0.0
      Si 1.3578 1.3578 1.3578
    &END COORD
    &KIND Si
      BASIS_SET SZV-MOLOPT-SR-GTH
      POTENTIAL GTH-PBE-q4
    &END KIND
  &END SUBSYS
&END FORCE_EVAL
```

**Run command**:
```bash
mkdir -p /tmp/cp2k_smoke_md
cd /tmp/cp2k_smoke_md
cp2k.ssmp -i test_md.inp -o output.log
```

**Expected files**:
| File | Must Exist | Content Check |
|------|------------|---------------|
| `output.log` | Yes | 10 MD steps logged |
| `cp2k_calc-pos-1.xyz` | Yes | 11 frames (initial + 10 steps) |
| `cp2k_calc-1.ener` | Yes | Energy table |
| `cp2k_calc-1.cell` | **Yes (NEW)** | Cell vectors (static for NVT) |
| `cp2k_calc-1.restart` | Maybe | At step 5 |

**Parse targets**:
- Trajectory: All frames from `cp2k_calc-pos-1.xyz`
- Cell: From `cp2k_calc-1.cell`
- Energies: From `cp2k_calc-1.ener` (step, time, kinetic, temp, potential)
- Temperature: From `.ener` file

**Acceptance criteria**:
- [ ] Trajectory has 11 frames
- [ ] **Cell file has matching entries**
- [ ] Energy file has 10+ rows
- [ ] Temperature values reasonable (~300K)
- [ ] Energy values consistent between log and .ener

---

## Phase 1: Engine Skeleton

**Goal**: Create CP2K engine class with binary discovery.

### 1.1 Create CP2K Resolver

**File**: `src/qmatsuite/core/engines/cp2k_resolver.py`

```python
"""CP2K binary resolver."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional


def find_cp2k_executable() -> Optional[Path]:
    """
    Find CP2K executable.

    Search order:
    1. CP2K_EXECUTABLE environment variable
    2. cp2k.ssmp in PATH
    3. cp2k in PATH (fallback)
    4. Homebrew location: /opt/homebrew/bin/cp2k.ssmp

    Returns:
        Path to executable, or None if not found.
    """
    # 1. Environment variable
    env_path = os.environ.get("CP2K_EXECUTABLE")
    if env_path:
        p = Path(env_path)
        if p.exists() and os.access(p, os.X_OK):
            return p

    # 2. cp2k.ssmp in PATH (preferred for OpenMP)
    ssmp = shutil.which("cp2k.ssmp")
    if ssmp:
        return Path(ssmp)

    # 3. cp2k in PATH (generic)
    generic = shutil.which("cp2k")
    if generic:
        return Path(generic)

    # 4. Homebrew default
    homebrew = Path("/opt/homebrew/bin/cp2k.ssmp")
    if homebrew.exists():
        return homebrew

    return None


def get_cp2k_version(executable: Path) -> Optional[str]:
    """Get CP2K version string."""
    try:
        result = subprocess.run(
            [str(executable), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Parse version from output
        for line in result.stdout.split("\n"):
            if "CP2K version" in line:
                return line.strip()
        return result.stdout.split("\n")[0] if result.stdout else None
    except Exception:
        return None


def get_cp2k_data_dir() -> Optional[Path]:
    """
    Get CP2K data directory.

    Search order:
    1. CP2K_DATA_DIR environment variable
    2. Homebrew location: /opt/homebrew/share/cp2k/data
    """
    env_dir = os.environ.get("CP2K_DATA_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.is_dir():
            return p

    homebrew = Path("/opt/homebrew/share/cp2k/data")
    if homebrew.is_dir():
        return homebrew

    return None
```

**Acceptance criteria**:
- [ ] `find_cp2k_executable()` returns `/opt/homebrew/bin/cp2k.ssmp` locally
- [ ] `get_cp2k_version()` returns version string
- [ ] `get_cp2k_data_dir()` returns data path

### 1.2 Create mtime-based Latest Selector

**File**: `src/qmatsuite/execution/latest_selector.py`

```python
"""mtime-based latest artifact selection."""

from pathlib import Path
from typing import Optional


def find_latest_by_mtime(workdir: Path, pattern: str) -> Optional[Path]:
    """
    Find latest file matching pattern by modification time.

    Args:
        workdir: Directory to search (Runtime SSOT: raw/<step_ulid>/)
        pattern: Glob pattern (e.g., "cp2k_calc-*.restart", "*.wfn")

    Returns:
        Path to file with most recent mtime, or None if no matches.

    Note:
        This is a GENERAL mechanism, not CP2K-specific.
        Can be used by any engine that accumulates artifacts.
    """
    candidates = list(workdir.glob(pattern))
    if not candidates:
        return None

    # Select by mtime (most recent)
    return max(candidates, key=lambda p: p.stat().st_mtime)
```

### 1.3 Create CP2K Engine Class

**File**: `src/qmatsuite/engine/cp2k_engine.py`

```python
"""CP2K engine implementation."""

from pathlib import Path
from typing import TYPE_CHECKING, Optional, Any
from dataclasses import dataclass

from qmatsuite.engine.base import Engine, StepResult
from qmatsuite.core.engines.cp2k_resolver import (
    find_cp2k_executable,
    get_cp2k_version,
)
from qmatsuite.execution.latest_selector import find_latest_by_mtime

if TYPE_CHECKING:
    from qmatsuite.calculation.calculation import Calculation


@dataclass
class Cp2kStepResult(StepResult):
    """Result from CP2K step execution."""
    output_file: Optional[Path] = None
    trajectory_file: Optional[Path] = None
    cell_file: Optional[Path] = None  # NEW: for cell information
    energy_file: Optional[Path] = None
    wfn_file: Optional[Path] = None
    restart_file: Optional[Path] = None


class Cp2kEngine(Engine):
    """
    CP2K engine for DFT and molecular dynamics.

    Uses directory-state pattern with isolated workdirs per step.
    Artifacts accumulate (no cleanup).

    IMPORTANT: All artifact lookups use mtime-based selection.
    """

    name = "cp2k"

    def __init__(self):
        self._executable: Optional[Path] = None
        self._version: Optional[str] = None

    @property
    def executable(self) -> Path:
        """Get CP2K executable path."""
        if self._executable is None:
            self._executable = find_cp2k_executable()
            if self._executable is None:
                raise RuntimeError("CP2K executable not found")
        return self._executable

    @property
    def version(self) -> Optional[str]:
        """Get CP2K version."""
        if self._version is None and self._executable:
            self._version = get_cp2k_version(self._executable)
        return self._version

    def probe(self) -> bool:
        """Check if CP2K is available."""
        try:
            return self.executable is not None
        except RuntimeError:
            return False

    def materialize_inputs(
        self,
        step,
        working_dir: Path,
        calculation: "Calculation",
    ) -> None:
        """
        Materialize CP2K input files.

        Creates:
        - input.inp (CP2K input file)

        Args:
            step: Step specification (StructureStepSpec)
            working_dir: Directory to write inputs
            calculation: Calculation context
        """
        from qmatsuite.engine.cp2k_writer import write_cp2k_input

        working_dir.mkdir(parents=True, exist_ok=True)

        # Get structure from calculation
        structure = calculation.get_structure()

        # Generate input file
        input_path = working_dir / "input.inp"
        write_cp2k_input(
            step=step,
            structure=structure,
            output_path=input_path,
        )

    def run_step(
        self,
        step,
        working_dir: Path,
        calculation: "Calculation",
    ) -> Cp2kStepResult:
        """
        Execute CP2K step.

        Args:
            step: Step specification
            working_dir: Working directory (must contain input.inp)
            calculation: Calculation context

        Returns:
            Cp2kStepResult with execution status and artifact paths.
        """
        import subprocess
        import os

        # Build command
        input_file = "input.inp"
        output_file = "output.log"
        command = [str(self.executable), "-i", input_file, "-o", output_file]

        # Execute CP2K
        try:
            result = subprocess.run(
                command,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=step.parameters.get("timeout", 3600),  # 1 hour default
                env={
                    **os.environ,
                    "OMP_NUM_THREADS": str(step.parameters.get("omp_threads", 1)),
                },
            )
        except subprocess.TimeoutExpired:
            return Cp2kStepResult(
                success=False,
                error="CP2K execution timed out",
                return_code=-1,
            )
        except Exception as e:
            return Cp2kStepResult(
                success=False,
                error=f"CP2K execution failed: {e}",
                return_code=-1,
            )

        # Find output artifacts using mtime-based selection
        output_path = working_dir / output_file
        wfn_path = self._find_latest_wfn(working_dir)
        traj_path = self._find_latest_trajectory(working_dir)
        cell_path = self._find_latest_cell(working_dir)  # NEW
        ener_path = self._find_latest_ener(working_dir)
        restart_path = self._find_latest_restart(working_dir)

        # Check success
        success = result.returncode == 0
        if success and output_path.exists():
            success = self._check_success(output_path, step.step_type)

        return Cp2kStepResult(
            success=success,
            error=result.stderr if not success else None,
            return_code=result.returncode,
            output_file=output_path if output_path.exists() else None,
            wfn_file=wfn_path,
            trajectory_file=traj_path,
            cell_file=cell_path,  # NEW
            energy_file=ener_path,
            restart_file=restart_path,
        )

    def _find_latest_wfn(self, workdir: Path) -> Optional[Path]:
        """Find latest wavefunction file (non-backup)."""
        wfn = workdir / "cp2k_calc-RESTART.wfn"
        return wfn if wfn.exists() else None

    def _find_latest_trajectory(self, workdir: Path) -> Optional[Path]:
        """Find latest trajectory file by mtime."""
        return find_latest_by_mtime(workdir, "cp2k_calc-pos-*.xyz")

    def _find_latest_cell(self, workdir: Path) -> Optional[Path]:
        """Find latest cell file by mtime."""
        return find_latest_by_mtime(workdir, "cp2k_calc-*.cell")

    def _find_latest_restart(self, workdir: Path) -> Optional[Path]:
        """Find latest restart file by mtime."""
        return find_latest_by_mtime(workdir, "cp2k_calc-*.restart")

    def _find_latest_ener(self, workdir: Path) -> Optional[Path]:
        """Find latest energy file by mtime."""
        return find_latest_by_mtime(workdir, "cp2k_calc-*.ener")

    def _check_success(self, output_path: Path, step_type: str) -> bool:
        """Check if CP2K run succeeded based on output."""
        content = output_path.read_text()

        if step_type == "cp2k_scf":
            return "SCF run converged" in content

        elif step_type == "cp2k_relax":
            return "GEOMETRY OPTIMIZATION COMPLETED" in content

        elif step_type == "cp2k_md":
            # MD doesn't have explicit completion message
            # Check for energy output or normal termination
            return "PROGRAM ENDED" in content or "Total wall" in content

        return True  # Default: trust return code
```

**Acceptance criteria**:
- [ ] Engine `probe()` returns True locally
- [ ] `executable` property returns path
- [ ] `materialize_inputs()` creates `input.inp`
- [ ] `run_step()` executes and returns result
- [ ] **Uses mtime-based selection for all artifacts**
- [ ] **Returns cell_file in result**

---

## Phase 2: Input Writer

**Goal**: Generate CP2K input files from step.yaml parameters.

### 2.1 Create CP2K Writer

**File**: `src/qmatsuite/engine/cp2k_writer.py`

Key functions:
- `write_cp2k_input(step, structure, output_path)`
- `_write_global_section(f, step_type)`
- `_write_force_eval_section(f, params, structure)`
- `_write_motion_section(f, step_type, params)`
- **`_write_print_section(f, step_type, params)` - MUST include CELL print**

**Size**: ~350-450 lines

**Critical requirement**: Always enable CELL output for relax/md steps:
```python
def _write_print_section(f, step_type, params):
    """Write MOTION/PRINT section."""
    f.write("  &PRINT\n")

    # Trajectory
    f.write("    &TRAJECTORY\n")
    f.write("      FORMAT XYZ\n")
    f.write("    &END TRAJECTORY\n")

    # CELL - ALWAYS enabled for relax/md
    if step_type in ("cp2k_relax", "cp2k_md"):
        f.write("    &CELL\n")
        f.write("      &EACH\n")
        if step_type == "cp2k_md":
            f.write(f"        MD {params.get('cell_freq', 1)}\n")
        else:
            f.write(f"        GEO_OPT {params.get('cell_freq', 1)}\n")
        f.write("      &END EACH\n")
        f.write("    &END CELL\n")

    f.write("  &END PRINT\n")
```

**Acceptance criteria**:
- [ ] Generates valid `input.inp` for cp2k_scf
- [ ] Generates valid `input.inp` for cp2k_relax (with MOTION + CELL print)
- [ ] Generates valid `input.inp` for cp2k_md (with MOTION/MD + CELL print)
- [ ] Handles species (KIND) correctly
- [ ] Respects user parameters from step.yaml
- [ ] **CELL output enabled by default for relax/md**

---

## Phase 3: Output Parser

**Goal**: Parse CP2K output files to extract data.

### 3.1 Create CP2K Parser

**File**: `src/qmatsuite/engine/cp2k_parser.py`

Key functions:
- `parse_cp2k_output(output_path) -> dict` - Main log parsing
- `parse_cp2k_trajectory(xyz_path, cell_path, initial_structure) -> CP2KTrajectory` - XYZ + cell parsing
- `parse_cp2k_ener(ener_path) -> list[dict]` - Energy file parsing
- `parse_cp2k_cell(cell_path) -> list[dict]` - **NEW: Cell file parsing**
- `extract_final_structure(xyz_path, cell_path, initial_structure) -> Structure` - For relax

**Cell file parser**:
```python
def parse_cp2k_cell(cell_path: Path) -> list[dict]:
    """
    Parse CP2K .cell file.

    Format:
    #  Step   Time [fs]       Ax   Ay   Az   Bx   By   Bz   Cx   Cy   Cz   Volume
         1    0.5000        10.0  0.0  0.0  0.0 10.0  0.0  0.0  0.0 10.0  1000.0

    Returns:
        List of dicts with step, time, cell vectors (A, B, C), volume.
    """
    data = []
    with open(cell_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 11:
                data.append({
                    "step": int(parts[0]),
                    "time_fs": float(parts[1]),
                    "A": [float(parts[2]), float(parts[3]), float(parts[4])],
                    "B": [float(parts[5]), float(parts[6]), float(parts[7])],
                    "C": [float(parts[8]), float(parts[9]), float(parts[10])],
                    "volume": float(parts[11]) if len(parts) > 11 else None,
                })
    return data
```

**Acceptance criteria**:
- [ ] Extracts total energy from output.log
- [ ] Parses trajectory XYZ (all frames)
- [ ] **Parses .cell file and merges with trajectory**
- [ ] Parses .ener file (columns)
- [ ] **Extracts final structure from relax trajectory with correct cell**

---

## Phase 4: Recipe, Handler, and Preflight

**Goal**: Integrate with QMatSuite execution system with preflight checks.

### 4.1 Create Preflight Checker (General Feature)

**File**: `src/qmatsuite/execution/preflight.py`

```python
"""General preflight checker for missing artifacts."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from qmatsuite.calculation.calculation import Calculation


@dataclass
class PreflightRequirement:
    """Declaration of required artifact for preflight check."""
    artifact_type: str  # e.g., "restart", "wfn", "chgcar"
    pattern: str        # Glob pattern
    source_step: str    # "predecessor" or specific step_ulid
    required: bool      # Hard error if missing?
    message: str        # Error message template


@dataclass
class PreflightError:
    """Preflight check failure."""
    requirement: PreflightRequirement
    message: str


class PreflightChecker:
    """
    General preflight checker for missing artifacts.

    CRITICAL: Always searches in Runtime SSOT (raw/<step_ulid>/),
    NEVER in scan archive (raw/scan/).
    """

    def check(
        self,
        requirements: List[PreflightRequirement],
        calculation: "Calculation",
        current_step,
    ) -> List[PreflightError]:
        """Check all requirements before launching engine."""
        errors = []
        for req in requirements:
            source_dir = self._resolve_source_dir(req, calculation, current_step)
            if source_dir is None:
                if req.required:
                    errors.append(PreflightError(
                        requirement=req,
                        message=f"No predecessor step found for {req.artifact_type}",
                    ))
                continue

            matches = list(source_dir.glob(req.pattern))
            if not matches and req.required:
                errors.append(PreflightError(
                    requirement=req,
                    message=req.message.format(
                        pattern=req.pattern,
                        source_dir=source_dir,
                    )
                ))
        return errors

    def _resolve_source_dir(
        self,
        req: PreflightRequirement,
        calculation: "Calculation",
        current_step,
    ) -> Optional[Path]:
        """Resolve source directory for artifact lookup."""
        if req.source_step == "predecessor":
            predecessor = self._get_linear_predecessor(current_step, calculation)
            if predecessor is None:
                return None
            # CRITICAL: Use Runtime SSOT, NOT scan archive
            return calculation.io.raw_dir / predecessor.meta.id
        else:
            return calculation.io.raw_dir / req.source_step

    def _get_linear_predecessor(self, current_step, calculation) -> Optional:
        """Get topological predecessor step."""
        steps = calculation.steps
        current_idx = None
        for i, step in enumerate(steps):
            if step.meta.id == current_step.meta.id:
                current_idx = i
                break
        if current_idx is None or current_idx == 0:
            return None
        return steps[current_idx - 1]
```

### 4.2 Create CP2KRecipe

**File**: `src/qmatsuite/execution/recipes.py` (add class)

```python
class CP2KRecipe(BaseRecipe):
    """
    CP2K-Recipe: Isolated workdir per step, directory-state model.

    Creates one job per step. Each step runs in:
    `calc/raw/<step_ulid>/`  (Runtime SSOT)

    NO workdir cleanup (accumulates artifacts).

    File layout:
    - Input: input.inp
    - Output: output.log, cp2k_calc-* artifacts
    """

    def get_preflight_requirements(self, step) -> List[PreflightRequirement]:
        """
        Get preflight requirements based on step parameters.

        CP2K declares requirements based on restart_policy.
        """
        from qmatsuite.execution.preflight import PreflightRequirement

        reqs = []
        params = step.parameters
        restart_policy = params.get("restart_policy", {})

        if restart_policy.get("use_restart"):
            reqs.append(PreflightRequirement(
                artifact_type="restart",
                pattern="cp2k_calc-*.restart",
                source_step="predecessor",
                required=True,
                message="Restart file required but not found in {source_dir}",
            ))

        if restart_policy.get("use_wfn_guess"):
            reqs.append(PreflightRequirement(
                artifact_type="wfn",
                pattern="cp2k_calc-RESTART.wfn",
                source_step="predecessor",
                required=True,
                message="WFN file required but not found in {source_dir}",
            ))

        return reqs

    def materialize(
        self,
        steps: List["Step"],
        calc_raw_dir: Path,
        step_shas: Optional[Dict[str, str]] = None,
    ) -> JobGraph:
        """Materialize jobs for CP2K steps."""
        if not steps:
            return JobGraph(jobs=[])

        registry = get_registry()
        jobs: List[Job] = []

        for step in steps:
            step_type = step.step_type
            spec = registry.get(step_type) if step_type else None
            public_type = spec.public_type if spec else "unknown"

            job_id = step.meta.id
            working_dir = calc_raw_dir / step.meta.id

            # CP2K command
            command = ["cp2k.ssmp", "-i", "input.inp", "-o", "output.log"]

            input_files = [working_dir / "input.inp"]
            expected_outputs = [working_dir / "output.log"]

            # Add trajectory and cell for relax/md
            if public_type in ("relax", "md"):
                expected_outputs.append(working_dir / "cp2k_calc-pos-1.xyz")
                expected_outputs.append(working_dir / "cp2k_calc-1.cell")  # NEW

            step_sha = self._get_step_sha(step, step_shas)

            deps = []
            if len(jobs) > 0:
                deps = [jobs[-1].id]

            job = Job(
                id=job_id,
                step_ids=[step.meta.id],
                working_dir=working_dir,
                command=command,
                input_files=input_files,
                expected_outputs=expected_outputs,
                deps=deps,
                fingerprint=step_sha,
                metadata={
                    "engine": "cp2k",
                    "spec_step_type": spec.machine_type if spec else None,
                    "public_type": public_type,
                },
            )
            jobs.append(job)

        return JobGraph(jobs=jobs)
```

### 4.3 Create cp2k_step_handler

**File**: `src/qmatsuite/execution/handlers.py` (add function)

```python
def cp2k_step_handler(
    job: Job,
    calculation: "Calculation",
    engine_registry: "EngineRegistry",
    context: Dict[str, Any],
) -> JobResult:
    """
    Execute a single CP2K step job.

    CRITICAL NOTES:
    - NO workdir cleanup (artifacts accumulate)
    - Uses mtime-based artifact selection
    - Preflight checks run before execution
    - Dependencies resolved from Runtime SSOT only (never raw/scan/)
    """
    from datetime import datetime, timezone
    from qmatsuite.execution.preflight import PreflightChecker
    from qmatsuite.execution.recipes import CP2KRecipe

    started = datetime.now(timezone.utc)

    # 1. Validate single-step job
    if len(job.step_ids) != 1:
        return JobResult(...)

    step_ulid = job.step_ids[0]
    step = _find_step_by_ulid(calculation, step_ulid)

    # 2. Get engine
    engine = engine_registry.get("cp2k")

    # 3. Create workdir (NO CLEANUP - CP2K accumulates)
    working_dir = job.working_dir
    working_dir.mkdir(parents=True, exist_ok=True)
    # DO NOT add shutil.rmtree() here - critical alignment decision

    # 4. Load step spec (like LAMMPS)
    from qmatsuite.calculation.structure_steps import StructureStepSpec
    from qmatsuite.core.resolution import require_step

    step_resolved = require_step(...)
    step_spec = StructureStepSpec.from_yaml(step_resolved.absolute_path)

    # 5. Run preflight checks
    recipe = CP2KRecipe()
    requirements = recipe.get_preflight_requirements(step_spec)
    if requirements:
        checker = PreflightChecker()
        errors = checker.check(requirements, calculation, step_spec)
        if errors:
            error_msgs = [e.message for e in errors]
            return JobResult(
                job_id=job.id,
                success=False,
                error=f"Preflight check failed: {'; '.join(error_msgs)}",
                started_at=started,
                finished_at=datetime.now(timezone.utc),
                step_results={step_ulid: {"success": False}},
            )

    # 6. Handle restart artifacts (if predecessor exists)
    # CRITICAL: Read from Runtime SSOT (raw/<predecessor_ulid>/), NOT raw/scan/
    restart_info = _resolve_cp2k_restart_artifacts(step_spec, calculation)
    if restart_info:
        # Update step parameters or input generation with restart info
        pass

    # 7. Materialize inputs
    engine.materialize_inputs(step_spec, working_dir, calculation)

    # 8. Execute
    result = engine.run_step(step_spec, working_dir, calculation)

    # 9. Build JobResult with relax artifact spec if applicable
    step_result_data = {
        "success": result.success,
        "output_file": str(result.output_file) if result.output_file else None,
    }

    if result.success and is_relax_step_type(step_spec.step_type):
        if result.trajectory_file:
            step_result_data["relax_artifact_spec"] = RelaxArtifactSpec(
                artifact_type="cp2k_trajectory",
                artifact_path=result.trajectory_file,
                cell_path=result.cell_file,  # NEW: include cell file
                step_ulid=step_ulid,
                step_type=str(step_spec.step_type),
            ).to_dict()

    return JobResult(
        job_id=job.id,
        success=result.success,
        error=result.error,
        started_at=started,
        finished_at=datetime.now(timezone.utc),
        step_results={step_ulid: step_result_data},
    )


def _resolve_cp2k_restart_artifacts(step_spec, calculation) -> Optional[Dict]:
    """
    Resolve restart artifacts from predecessor step.

    CRITICAL: Always reads from Runtime SSOT (raw/<predecessor_ulid>/),
    NEVER from scan archive (raw/scan/).
    """
    from qmatsuite.execution.latest_selector import find_latest_by_mtime

    params = step_spec.parameters
    restart_policy = params.get("restart_policy", {})

    if not restart_policy.get("use_restart") and not restart_policy.get("use_wfn_guess"):
        return None

    # Find predecessor
    predecessor = _get_linear_predecessor(step_spec, calculation)
    if predecessor is None:
        return None

    # CRITICAL: Use Runtime SSOT
    predecessor_dir = calculation.io.raw_dir / predecessor.meta.id

    result = {}

    if restart_policy.get("use_restart"):
        restart_file = find_latest_by_mtime(predecessor_dir, "cp2k_calc-*.restart")
        if restart_file:
            result["restart_file"] = restart_file

    if restart_policy.get("use_wfn_guess"):
        wfn_file = predecessor_dir / "cp2k_calc-RESTART.wfn"
        if wfn_file.exists():
            result["wfn_file"] = wfn_file

    return result if result else None
```

### 4.4 Update Handler Map

**File**: `src/qmatsuite/execution/handlers.py` (modify `create_handler_map`)

```python
return {
    ...
    "cp2k": make_handler(cp2k_step_handler),
}
```

### 4.5 Update Recipe Factory

**File**: `src/qmatsuite/execution/recipes.py` (modify `get_recipe_for_engine`)

```python
recipes = {
    ...
    "cp2k": CP2KRecipe,
}
```

**Acceptance criteria**:
- [ ] PreflightChecker implemented as general feature
- [ ] CP2KRecipe declares preflight requirements
- [ ] cp2k_step_handler runs preflight checks
- [ ] **Handler never references raw/scan/**
- [ ] **Uses mtime-based artifact selection**
- [ ] Handler registered in create_handler_map

---

## Phase 5: Registry Integration

### 5.1 Add Step Types

**File**: `src/qmatsuite/workflow/registry.py` (add to `_STEP_TYPES`)

```python
"cp2k_scf": StepTypeSpec(
    id="scf",
    machine_type="cp2k_scf",
    public_type="scf",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K single-point energy/force calculation",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    supports_incremental_skip=True,
    is_structure_transform=False,
),
"cp2k_relax": StepTypeSpec(
    id="relax",
    machine_type="cp2k_relax",
    public_type="relax",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K geometry optimization",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    supports_incremental_skip=True,
    is_structure_transform=True,
),
"cp2k_md": StepTypeSpec(
    id="md",
    machine_type="cp2k_md",
    public_type="md",
    engine="cp2k",
    executable="cp2k.ssmp",
    description="CP2K molecular dynamics",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    supports_incremental_skip=False,  # CRITICAL: MD skip disabled
    is_structure_transform=False,
),
```

### 5.2 Add MATERIALIZATION_MAP Entries

**File**: `src/qmatsuite/workflow/generalized_steps.py` (add to `MATERIALIZATION_MAP`)

```python
# CP2K family mappings
("cp2k", "SCF"): "cp2k_scf",
("cp2k", "RELAX"): "cp2k_relax",
("cp2k", "VC_RELAX"): "cp2k_relax",
("cp2k", "MD"): "cp2k_md",
("cp2k", "VC_MD"): "cp2k_md",
```

### 5.3 Register Engine

**File**: `src/qmatsuite/engine/registry.py` (add to `create_default_registry`)

```python
from qmatsuite.engine.cp2k_engine import Cp2kEngine

registry.register("cp2k", Cp2kEngine())
```

**Acceptance criteria**:
- [ ] Step types in registry
- [ ] **cp2k_md has supports_incremental_skip=False**
- [ ] MATERIALIZATION_MAP entries work
- [ ] Engine registered

---

## Phase 6: Testing

### 6.1 Unit Tests (Mock)

**File**: `tests/unit/engine/test_cp2k_engine.py`

```python
def test_find_latest_by_mtime():
    """Test mtime-based selection for artifacts."""
    ...

def test_preflight_checker():
    """Test preflight requirement checking."""
    ...

def test_cp2k_input_generation_with_cell():
    """Test input file generation includes CELL print."""
    ...
```

### 6.2 Integration Tests (Local)

**File**: `tests/integration/test_cp2k_integration.py`

```python
@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_scf_silicon():
    """End-to-end SCF test with real CP2K."""
    ...

@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_relax_silicon_with_cell():
    """End-to-end relax test with structure and cell extraction."""
    ...

@pytest.mark.skipif(not CP2K_AVAILABLE, reason="CP2K not installed")
def test_cp2k_md_incremental_skip_disabled():
    """Verify MD steps are always executed when targeted."""
    ...
```

### 6.3 CI Strategy

- **CI**: Mock tests only (no CP2K binary)
- **Local**: Real CP2K tests via pytest marker
- **Manual**: Full calculation workflow tests

**Acceptance criteria**:
- [x] Unit tests pass in CI
- [x] Integration tests pass locally
- [x] Relax produces current.json artifact **with correct cell**
- [x] **MD skip disabled is tested**

---

## Phase 7: Relax Artifact Handler

### 7.1 Add CP2K Relax Handler

**File**: `src/qmatsuite/execution/relax_artifacts.py` (add handler)

```python
def _handle_cp2k_trajectory_artifact(
    artifact_path: Path,
    calc_dir: Path,
    step_ulid: str,
    step_type: str,
    run_context: dict,
) -> Path:
    """
    Handle CP2K trajectory artifact -> current.json.

    Args:
        artifact_path: Path to cp2k_calc-pos-N.xyz
        ...

    Returns:
        Path to current.json
    """
    from qmatsuite.engine.cp2k_parser import extract_final_structure
    from qmatsuite.execution.latest_selector import find_latest_by_mtime

    # Find cell file in same directory
    workdir = artifact_path.parent
    cell_path = find_latest_by_mtime(workdir, "cp2k_calc-*.cell")

    # Get initial structure for fallback cell
    initial_structure = run_context.get("initial_structure")

    # Extract final structure from trajectory with cell
    structure = extract_final_structure(
        xyz_path=artifact_path,
        cell_path=cell_path,
        initial_structure=initial_structure,
    )

    # Canonicalize
    from qmatsuite.core.structure_canonicalize import canonicalize_structure_like_in_place
    canonicalize_structure_like_in_place(structure)

    # Write current.json
    return write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_context.get("run_id"),
        calculation_ulid=run_context.get("calculation_ulid", ""),
        input_structure_ulid=run_context.get("input_structure_ulid", ""),
    )


# Add to RELAX_ARTIFACT_HANDLERS
RELAX_ARTIFACT_HANDLERS["cp2k_trajectory"] = _handle_cp2k_trajectory_artifact
```

**Acceptance criteria**:
- [ ] Handler registered
- [ ] Produces current.json from trajectory
- [ ] **Structure has correct cell from .cell file**
- [ ] Falls back to initial structure cell if no .cell file

---

## Summary: Files to Create/Modify

### New Files

| File | Lines (est.) |
|------|--------------|
| `src/qmatsuite/core/engines/cp2k_resolver.py` | 80 |
| `src/qmatsuite/execution/latest_selector.py` | 30 |
| `src/qmatsuite/execution/preflight.py` | 100 |
| `src/qmatsuite/engine/cp2k_engine.py` | 220 |
| `src/qmatsuite/engine/cp2k_writer.py` | 400 |
| `src/qmatsuite/engine/cp2k_parser.py` | 250 |
| `tests/unit/engine/test_cp2k_engine.py` | 150 |
| `tests/integration/test_cp2k_integration.py` | 120 |

### Modified Files

| File | Change |
|------|--------|
| `src/qmatsuite/workflow/registry.py` | Add 3 StepTypeSpec entries (md skip=False) |
| `src/qmatsuite/workflow/generalized_steps.py` | Add 5 MATERIALIZATION_MAP entries |
| `src/qmatsuite/execution/recipes.py` | Add CP2KRecipe class with preflight, update factory |
| `src/qmatsuite/execution/handlers.py` | Add cp2k_step_handler with preflight, update handler map |
| `src/qmatsuite/execution/relax_artifacts.py` | Add cp2k_trajectory handler with cell support |
| `src/qmatsuite/engine/registry.py` | Register Cp2kEngine |

---

## Implementation Checklist

- [x] Phase 0: Smoke tests completed with **cell output verified**
- [x] Phase 1: Engine skeleton with binary discovery + **mtime selector**
- [x] Phase 2: Input writer generates valid CP2K input **with CELL print**
- [x] Phase 3: Parser extracts energy, structure, trajectory **with cell data**
- [x] Phase 4: Recipe, handler, **preflight checker** integrated
- [x] Phase 5: Registry entries added, **MD skip disabled**
- [x] Phase 6: Tests pass (mock in CI, real locally)
- [x] Phase 7: Relax artifact handler works **with cell extraction**

---

## Non-Negotiable Rules (Summary)

1. **Runtime SSOT**: Always `raw/<step_ulid>/`, never `raw/scan/`
2. **mtime selection**: Use `find_latest_by_mtime()`, not numeric suffix
3. **No workdir cleanup**: `mkdir(exist_ok=True)`, no `rmtree()`
4. **Cell output**: Always enabled for relax/md steps
5. **MD skip disabled**: `supports_incremental_skip=False`
6. **Preflight checks**: General feature with CP2K declarations
7. **Dedicated recipe**: `CP2KRecipe`, not reusing VASP/LAMMPS
