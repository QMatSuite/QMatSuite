# CP2K Implementation Notes

**Last reviewed**: 2025-01-19
**CP2K version target**: 2025.1
**Purpose**: Implementation-ready notes for CP2K engine integration

---

## 1. Engine Discovery

### 1.1 Executable Variants

| Variant | Description | Use Case |
|---------|-------------|----------|
| `cp2k.ssmp` | Serial + OpenMP | Default for single-node |
| `cp2k.psmp` | MPI + OpenMP | Multi-node HPC |
| `cp2k.sopt` | Serial only | Debugging |
| `cp2k.popt` | MPI only | Pure MPI parallel |

### 1.2 Discovery Strategy

```python
# src/qmatsuite/core/engines/cp2k_resolver.py

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

# Priority order for binary discovery
CP2K_BINARY_NAMES = [
    "cp2k.ssmp",   # Preferred: OpenMP parallel
    "cp2k.psmp",   # MPI + OpenMP
    "cp2k.sopt",   # Serial
    "cp2k",        # Generic name
]

def resolve_cp2k_bin() -> Path:
    """
    Resolve CP2K binary path.

    Search order:
    1. CP2K_BIN environment variable
    2. PATH search for known binary names
    3. Common installation locations

    Returns:
        Path to CP2K binary

    Raises:
        RuntimeError: If no CP2K binary found
    """
    import os

    # Check environment variable
    cp2k_bin_env = os.environ.get("CP2K_BIN")
    if cp2k_bin_env:
        path = Path(cp2k_bin_env)
        if path.exists() and _is_cp2k_binary(path):
            return path

    # Search PATH
    for name in CP2K_BINARY_NAMES:
        path = shutil.which(name)
        if path and _is_cp2k_binary(Path(path)):
            return Path(path)

    # Common installation locations
    common_paths = [
        Path("/opt/homebrew/bin"),          # macOS Homebrew
        Path("/usr/local/bin"),              # Linux local
        Path("/usr/bin"),                    # System
        Path.home() / "cp2k" / "exe" / "local",  # Source build
    ]

    for base in common_paths:
        for name in CP2K_BINARY_NAMES:
            path = base / name
            if path.exists() and _is_cp2k_binary(path):
                return path

    raise RuntimeError(
        "CP2K binary not found. Install CP2K or set CP2K_BIN environment variable. "
        f"Searched for: {', '.join(CP2K_BINARY_NAMES)}"
    )


def _is_cp2k_binary(path: Path) -> bool:
    """Verify path is a CP2K binary by running --version."""
    try:
        result = subprocess.run(
            [str(path), "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return "CP2K" in result.stdout or "CP2K" in result.stderr
    except Exception:
        return False


def probe_cp2k() -> Tuple[bool, str]:
    """
    Probe for CP2K availability and version.

    Returns:
        Tuple of (available, version_string_or_error)
    """
    try:
        binary = resolve_cp2k_bin()
        result = subprocess.run(
            [str(binary), "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # Parse version from output
        for line in (result.stdout + result.stderr).split("\n"):
            if "CP2K version" in line:
                return True, line.strip()

        return True, f"CP2K at {binary}"
    except RuntimeError as e:
        return False, str(e)
    except Exception as e:
        return False, f"CP2K probe failed: {e}"
```

### 1.3 Platform-Specific Notes

| Platform | Default Location | Notes |
|----------|------------------|-------|
| macOS (Homebrew) | `/opt/homebrew/bin/cp2k.ssmp` | `brew install cp2k` |
| Linux (apt) | `/usr/bin/cp2k` | `apt install cp2k` |
| HPC modules | Varies | Use `module load cp2k` |
| Source build | `~/cp2k/exe/local/` | Architecture-specific subdirs |

---

## 2. Runner Invocation

### 2.1 Command Line Template

```python
def build_cp2k_command(
    binary: Path,
    input_file: str = "input.inp",
    output_file: str = "output.log",
) -> list[str]:
    """Build CP2K command line."""
    return [
        str(binary),
        "-i", input_file,
        "-o", output_file,
    ]
```

### 2.2 Execution Pattern

```python
def run_cp2k(
    working_dir: Path,
    binary: Path,
    timeout: Optional[int] = None,
) -> subprocess.CompletedProcess:
    """
    Execute CP2K in working directory.

    Args:
        working_dir: Directory containing input.inp
        binary: Path to CP2K binary
        timeout: Optional timeout in seconds

    Returns:
        CompletedProcess with return code and output
    """
    import os

    cmd = build_cp2k_command(binary)

    # Environment setup
    env = os.environ.copy()

    # Ensure CP2K_DATA_DIR is set
    if "CP2K_DATA_DIR" not in env:
        # Try to find data directory relative to binary
        data_dir = _find_data_dir(binary)
        if data_dir:
            env["CP2K_DATA_DIR"] = str(data_dir)

    # OpenMP settings
    if "OMP_NUM_THREADS" not in env:
        env["OMP_NUM_THREADS"] = "1"  # Default to single thread
    if "OMP_STACKSIZE" not in env:
        env["OMP_STACKSIZE"] = "512M"  # Prevent stack overflow

    result = subprocess.run(
        cmd,
        cwd=working_dir,
        capture_output=True,
        text=True,
        env=env,
        timeout=timeout,
    )

    return result


def _find_data_dir(binary: Path) -> Optional[Path]:
    """Find CP2K data directory from binary location."""
    # Homebrew pattern: /opt/homebrew/bin/cp2k.ssmp -> /opt/homebrew/share/cp2k/data
    if "homebrew" in str(binary):
        data_dir = binary.parent.parent / "share" / "cp2k" / "data"
        if data_dir.exists():
            return data_dir

    # Source build pattern: ~/cp2k/exe/local/cp2k.ssmp -> ~/cp2k/data
    if "exe" in str(binary):
        data_dir = binary.parent.parent.parent / "data"
        if data_dir.exists():
            return data_dir

    return None
```

### 2.3 Stdout/Stderr Capture

CP2K outputs to both stdout (via `-o` flag) and stderr (for some errors):

```python
def run_step(self, step, working_dir: Path) -> StepResult:
    result = run_cp2k(working_dir, self._binary)

    # Check for errors
    error = None
    if result.returncode != 0:
        error = f"CP2K exited with code {result.returncode}"
        if result.stderr:
            error += f"\nStderr: {result.stderr[:500]}"

    # Check output file exists
    output_file = working_dir / "output.log"
    success = result.returncode == 0 and output_file.exists()

    # Parse output for additional error messages
    if output_file.exists():
        output_content = output_file.read_text()
        if "ABORT" in output_content or "ERROR" in output_content:
            success = False
            error_lines = [l for l in output_content.split("\n")
                         if "ABORT" in l or "ERROR" in l]
            error = (error or "") + "\n" + "\n".join(error_lines[:5])

    return StepResult(
        step_type=step.step_type,
        input_file=working_dir / "input.inp",
        output_file=output_file if output_file.exists() else None,
        success=success,
        error=error,
        return_code=result.returncode,
    )
```

---

## 3. Data File Management

### 3.1 Basis Set and Potential Files

CP2K uses two main data categories:

| Category | Files | Location |
|----------|-------|----------|
| Basis sets | `BASIS_MOLOPT`, `GTH_BASIS_SETS`, etc. | `$CP2K_DATA_DIR/` |
| Potentials | `GTH_POTENTIALS`, `POTENTIAL`, etc. | `$CP2K_DATA_DIR/` |

### 3.2 QMatSuite Management Strategy

**Recommended**: Reference by filename only, rely on `CP2K_DATA_DIR`.

```python
def validate_data_files(env: dict) -> list[str]:
    """
    Validate CP2K data files are accessible.

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []
    data_dir = env.get("CP2K_DATA_DIR")

    if not data_dir:
        errors.append("CP2K_DATA_DIR not set")
        return errors

    data_path = Path(data_dir)
    if not data_path.exists():
        errors.append(f"CP2K_DATA_DIR does not exist: {data_dir}")
        return errors

    # Check for common data files
    required_files = ["BASIS_MOLOPT", "GTH_POTENTIALS"]
    for filename in required_files:
        if not (data_path / filename).exists():
            errors.append(f"Missing data file: {filename}")

    return errors
```

### 3.3 Analogy to QE Pseudopotentials

| QE | CP2K | QMatSuite Handling |
|----|------|-------------------|
| `pseudo_dir` | `CP2K_DATA_DIR` | Environment variable |
| `.upf` files | Basis/potential files | Referenced by name |
| `species_map` | `&KIND` sections | Element → basis/potential |

**Key difference**: CP2K's basis sets and potentials are distributed with CP2K and referenced by name (not by file path). No need for user-managed pseudo directory.

---

## 4. Output Parsing

### 4.1 Minimal Parsing Targets

| Target | Source | Parsing Method |
|--------|--------|----------------|
| Total energy | `output.log` | Regex on "ENERGY\| Total" |
| SCF convergence | `output.log` | Check for "SCF run converged" |
| Forces | `output.log` or `-frc-1.xyz` | Parse force section |
| Final geometry | `-pos-1.xyz` | Last frame of XYZ |
| Trajectory | `-pos-1.xyz` | All frames |

### 4.2 Energy Parsing

```python
import re
from typing import Optional

def parse_total_energy(output_path: Path) -> Optional[float]:
    """
    Parse total energy from CP2K output.

    Returns:
        Total energy in Hartree, or None if not found
    """
    content = output_path.read_text()

    # Pattern: "ENERGY| Total FORCE_EVAL ( QS ) energy (a.u.):      -17.157456789"
    pattern = r"ENERGY\| Total FORCE_EVAL.*energy.*:\s+([-\d.]+)"
    matches = re.findall(pattern, content)

    if matches:
        return float(matches[-1])  # Last occurrence (final energy)
    return None


def parse_scf_converged(output_path: Path) -> bool:
    """Check if SCF converged."""
    content = output_path.read_text()
    return "SCF run converged" in content


def parse_optimization_converged(output_path: Path) -> bool:
    """Check if geometry optimization converged."""
    content = output_path.read_text()
    patterns = [
        "GEOMETRY OPTIMIZATION COMPLETED",
        "Minimum structure found",
    ]
    return any(p in content for p in patterns)
```

### 4.3 Structure Extraction

```python
from typing import List, Tuple

def parse_xyz_trajectory(xyz_path: Path) -> List[Tuple[List[str], List[List[float]]]]:
    """
    Parse XYZ trajectory file.

    Returns:
        List of (elements, coordinates) tuples for each frame
    """
    content = xyz_path.read_text()
    lines = content.strip().split("\n")

    frames = []
    i = 0

    while i < len(lines):
        # Read atom count
        n_atoms = int(lines[i].strip())
        i += 1

        # Skip comment line
        i += 1

        # Read coordinates
        elements = []
        coords = []
        for _ in range(n_atoms):
            parts = lines[i].split()
            elements.append(parts[0])
            coords.append([float(x) for x in parts[1:4]])
            i += 1

        frames.append((elements, coords))

    return frames


def get_final_structure(xyz_path: Path) -> Tuple[List[str], List[List[float]]]:
    """Get final structure from trajectory (last frame)."""
    frames = parse_xyz_trajectory(xyz_path)
    if not frames:
        raise ValueError(f"No frames found in {xyz_path}")
    return frames[-1]
```

### 4.4 Energy File Parsing

```python
from dataclasses import dataclass
from typing import List

@dataclass
class MDStep:
    step: int
    time_fs: float
    kinetic_au: float
    temperature_k: float
    potential_au: float
    total_au: float
    cpu_time_s: float

def parse_energy_file(ener_path: Path) -> List[MDStep]:
    """Parse CP2K .ener file."""
    content = ener_path.read_text()
    steps = []

    for line in content.split("\n"):
        if line.startswith("#") or not line.strip():
            continue

        parts = line.split()
        if len(parts) >= 7:
            steps.append(MDStep(
                step=int(parts[0]),
                time_fs=float(parts[1]),
                kinetic_au=float(parts[2]),
                temperature_k=float(parts[3]),
                potential_au=float(parts[4]),
                total_au=float(parts[5]),
                cpu_time_s=float(parts[6]),
            ))

    return steps
```

---

## 5. Testing Strategy

### 5.1 Minimal Integration Tests

```python
# tests/integration/test_cp2k_engine.py

import pytest
from pathlib import Path

# Skip if CP2K not available
pytestmark = pytest.mark.skipif(
    not _cp2k_available(),
    reason="CP2K not installed"
)

def _cp2k_available() -> bool:
    try:
        from qmatsuite.core.engines.cp2k_resolver import probe_cp2k
        available, _ = probe_cp2k()
        return available
    except Exception:
        return False


class TestCp2kEngine:
    """Integration tests for CP2K engine."""

    def test_probe(self):
        """Test CP2K binary detection."""
        from qmatsuite.core.engines.cp2k_resolver import probe_cp2k
        available, version = probe_cp2k()
        assert available
        assert "CP2K" in version

    def test_scf_h2o(self, tmp_path):
        """Test SCF calculation on water molecule."""
        # Create minimal H2O structure
        structure = self._create_h2o_structure()

        # Create step
        step = self._create_scf_step()

        # Run
        engine = Cp2kEngine()
        result = engine.run_step(step, tmp_path)

        assert result.success
        assert (tmp_path / "cp2k_calc-RESTART.wfn").exists()

    def test_relax_h2(self, tmp_path):
        """Test geometry optimization on H2 molecule."""
        # Minimal H2 at non-equilibrium distance
        structure = self._create_h2_structure(distance=1.0)  # Too long

        step = self._create_relax_step()

        engine = Cp2kEngine()
        result = engine.run_step(step, tmp_path)

        assert result.success
        # Check geometry changed
        final = get_final_structure(tmp_path / "cp2k_calc-pos-1.xyz")
        # H2 equilibrium ~0.74 Å
        assert final is not None
```

### 5.2 Fast/CI-Friendly Tests

| Test | System | Atoms | Expected Time |
|------|--------|-------|---------------|
| SCF smoke | H2 | 2 | <5s |
| SCF convergence | H2O | 3 | <10s |
| Relax smoke | H2 | 2 | <10s |
| MD smoke | H2 (5 steps) | 2 | <15s |

### 5.3 Test Fixtures

```python
@pytest.fixture
def h2_structure():
    """Minimal H2 structure for fast tests."""
    return {
        "cell": [[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]],
        "coords": [[0.0, 0.0, 0.0], [0.74, 0.0, 0.0]],
        "elements": ["H", "H"],
    }

@pytest.fixture
def minimal_cp2k_params():
    """Minimal parameters for fast tests."""
    return {
        "method": "Quickstep",
        "functional": "PADE",  # Fast LDA
        "basis_set": "SZV-GTH",  # Minimal basis
        "potential": "GTH-PADE-q1",
        "cutoff": 100,  # Low cutoff for speed
        "rel_cutoff": 30,
        "eps_scf": 1.0E-4,  # Loose convergence
        "max_scf": 50,
    }
```

---

## 6. Implementation Checklist

### 6.1 Phase 1: cp2k_scf (MVP)

- [ ] `cp2k_resolver.py`: Binary discovery
- [ ] `cp2k_writer.py`: Input file generator for SCF
- [ ] `cp2k_parser.py`: Energy/convergence parsing
- [ ] `cp2k_engine.py`: Engine class with `run_step()`
- [ ] Registry entries in `workflow/registry.py`
- [ ] Engine registration in `engine/registry.py`
- [ ] Unit tests for writer/parser
- [ ] Integration test for H2 SCF

### 6.2 Phase 2: cp2k_relax

- [ ] Add GEO_OPT input generation
- [ ] Structure artifact extraction
- [ ] Optimization convergence parsing
- [ ] `restart_from` handling
- [ ] Integration test for H2 relax

### 6.3 Phase 3: cp2k_md

- [ ] Add MD input generation
- [ ] Trajectory parsing
- [ ] Energy file parsing
- [ ] Restart file handling
- [ ] Integration test for H2 MD (5 steps)

### 6.4 Phase 4: Polish

- [ ] Preset system integration
- [ ] Error message improvements
- [ ] Documentation
- [ ] Extended test coverage

---

## 7. File Manifest

Files to create for CP2K integration:

```
src/qmatsuite/
├── core/engines/
│   └── cp2k_resolver.py       # Binary discovery
├── engine/
│   ├── cp2k_engine.py         # Engine backend
│   ├── cp2k_writer.py         # Input generator
│   └── cp2k_parser.py         # Output parser
└── workflow/
    └── registry.py            # (modify) Add step types

tests/
├── unit/
│   ├── test_cp2k_writer.py
│   └── test_cp2k_parser.py
└── integration/
    └── test_cp2k_engine.py    # Requires CP2K installed

docs/engines/cp2k/
├── CP2K_CAPABILITIES.md
├── CP2K_WORKFLOWS.md
├── CP2K_IO_AND_FILES.md
├── CP2K_INTEGRATION_FIT.md
├── CP2K_MINIMAL_SPEC.md
└── CP2K_IMPLEMENTATION_NOTES.md
```
