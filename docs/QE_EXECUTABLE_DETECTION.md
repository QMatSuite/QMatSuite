# QE Executable Detection and Path Resolution

## Overview

The QE engine automatically detects and locates Quantum ESPRESSO executables across different platforms (Mac, Linux, Windows) and installation locations.

## Features

- **Cross-platform support**: Automatically handles `.x` (Linux/Mac) and `.exe` (Windows) extensions
- **Flexible path resolution**: 
  - Searches in specified installation directory
  - Checks `bin` subdirectory if QE root is provided
  - Falls back to system PATH
- **Helpful error messages**: Clear error messages when executables are not found

## QE Home Detection Order

When no explicit path is provided, the `QEInstallation` class auto-detects QE using this priority order:

| Priority | Source | Description |
|----------|--------|-------------|
| 1 | `QE_HOME` environment variable | Most explicit; recommended for CI/CD |
| 2 | System PATH | Uses `which pw.x` and infers `QE_HOME` from `../bin/pw.x` |
| 3 | Shell config files | Parses `~/.zshrc`, `~/.bashrc`, etc. for `QE_HOME` exports or PATH entries |
| 4 | Home directory scan | Searches `$HOME` (up to 3 levels) for `q-e-qe*` or `quantum-espresso` folders |

This order ensures that:
- **CI/CD environments** (GitHub Actions, etc.) work reliably when `QE_HOME` is set
- **Local development** benefits from shell config parsing for convenience
- **Fallback heuristics** find common installation patterns

## Usage

### Basic Usage

```python
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig
from pathlib import Path

# Option 1: Let auto-detection find QE (recommended)
# Uses QE_HOME env var, PATH, shell configs, or home directory scan
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)

# Option 2: Specify QE home directory explicitly
config = EngineConfig(
    name="qe",
    qe_home=Path.home() / "src" / "q-e-qe-7.5"
)
engine = QuantumEspressoEngine(config)

# Option 3: Specify bin directory (backward compatibility)
config = EngineConfig(
    name="qe",
    executable_path=Path.home() / "src" / "q-e-qe-7.5" / "bin"
)
engine = QuantumEspressoEngine(config)
```

### Detecting Executables

```python
# Check if pw.x is available
if engine.detect_executable("pw.x"):
    print("pw.x found!")
else:
    print("pw.x not found")

# Check other executables
engine.detect_executable("ph.x")
engine.detect_executable("bands.x")
```

### Getting Executable Path

```python
try:
    pw_path = engine.get_executable_path("pw.x")
    print(f"pw.x found at: {pw_path}")
except FileNotFoundError as e:
    print(f"Error: {e}")
```

### Building Commands

```python
from pathlib import Path

input_file = Path("scf.in")
working_dir = Path(".")

# Build command for SCF calculation
command = engine.build_command("scf", input_file, working_dir)
print(f"Command: {' '.join(command)}")
# Output: /path/to/pw.x -inp scf.in

# With MPI support
config.mpi_command = "mpirun"
config.mpi_cores = 4
engine = QuantumEspressoEngine(config)
command = engine.build_command("scf", input_file, working_dir)
print(f"Command: {' '.join(command)}")
# Output: mpirun -np 4 /path/to/pw.x -inp scf.in
```

## Search Order

When looking for a specific executable (e.g., `pw.x`), the engine searches in this order:

1. **QE_HOME/bin** (from auto-detected or explicitly provided `qe_home`)
2. **Specified bin directory** (`executable_path` if configured)
3. **System PATH** (using `which`/`shutil.which`)

### Environment Variable

Set `QE_HOME` to ensure reliable detection in scripts and CI:

```bash
export QE_HOME=$HOME/src/q-e-qe-7.5
export PATH="$QE_HOME/bin:$PATH"
```

The `QEInstallation` class automatically sets `QE_HOME` in the current process once a valid installation is found.

## Platform-Specific Behavior

### Mac / Linux
- Looks for executables with `.x` extension (e.g., `pw.x`, `ph.x`)
- Checks executable permissions

### Windows
- Looks for executables with `.exe` extension (e.g., `pw.exe`, `ph.exe`)
- Automatically converts `.x` to `.exe` when searching

## Error Handling

If an executable is not found, `get_executable_path()` raises a `FileNotFoundError` with a helpful message:

```python
try:
    engine.get_executable_path("pw.x")
except FileNotFoundError as e:
    print(e)
    # Output:
    # QE executable 'pw.x' not found.
    # Searched in: /path/to/qe/bin, /path/to/qe, system PATH
    # Please set executable_path in EngineConfig or ensure 'pw.x' is in PATH.
```

## Examples

### Example 1: Using QE Installation in Home Directory

```python
from pathlib import Path
from quantumvitas.core.engines.qe import QuantumEspressoEngine
from quantumvitas.core.engines.base import EngineConfig

# QE installed at $HOME/src/q-e-qe-7.5
qe_bin = Path.home() / "src" / "q-e-qe-7.5" / "bin"

config = EngineConfig(name="qe", executable_path=qe_bin)
engine = QuantumEspressoEngine(config)

# Verify installation
if engine.detect_executable("pw.x"):
    print("✓ QE installation detected")
    pw_path = engine.get_executable_path("pw.x")
    print(f"  Location: {pw_path}")
else:
    print("✗ QE installation not found")
```

### Example 2: Using System PATH

```python
# If QE is in PATH, no need to specify path
config = EngineConfig(name="qe")
engine = QuantumEspressoEngine(config)

if engine.detect_executable("pw.x"):
    print("✓ Found pw.x in PATH")
```

### Example 3: Building and Running a Calculation

```python
from pathlib import Path
import subprocess

# Setup engine
config = EngineConfig(
    name="qe",
    executable_path=Path.home() / "src" / "q-e-qe-7.5" / "bin"
)
engine = QuantumEspressoEngine(config)

# Generate input file
input_data = {
    'namelists': {
        'control': {'calculation': 'scf', 'prefix': 'si'},
        'system': {'nat': 2, 'ecutwfc': 30.0}
    },
    'cards': [
        {'type': 'ATOMIC_SPECIES', 'data': [['Si', '28.086', 'Si.UPF']]}
    ]
}

working_dir = Path("calculation")
input_file = engine.generate_input("scf", input_data, working_dir)

# Build command
command = engine.build_command("scf", input_file, working_dir)

# Run calculation
result = subprocess.run(command, cwd=working_dir, capture_output=True)
print(f"Return code: {result.returncode}")
```

## Testing

Unit tests are available in `tests/unit/test_qe_executable_detection.py`:

```bash
pytest tests/unit/test_qe_executable_detection.py -v
```

Integration tests are in `tests/integration/test_qe_executable_integration.py`:

```bash
pytest tests/integration/test_qe_executable_integration.py -v
```

