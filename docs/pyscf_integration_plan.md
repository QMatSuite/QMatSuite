# PySCF Integration Plan

**Date**: 2025-01-XX  
**Status**: In Progress  
**Goal**: Integrate PySCF as a subprocess-based engine for molecular calculations

---

## 1. Discovered Existing Schemas & Contracts

### 1.1 StepResult Schema

**Location**: `src/quantumvitas/core/engines/qe_calculation.py:23-36`

```python
@dataclass
class StepResult:
    step_type: str                          # e.g., "pyscf_scf"
    input_file: Path                        # Path to input script
    output_file: Optional[Path] = None      # Path to results.json
    success: bool = False                   # Whether calculation succeeded
    return_code: Optional[int] = None       # Subprocess return code
    stdout: str = ""                        # Captured stdout
    stderr: str = ""                        # Captured stderr
    error: Optional[str] = None             # Error message if failed
    execution_time: float = 0.0             # Wall time in seconds
    parsed_output: Optional[Dict] = None    # Parsed results (energy, etc.)
```

### 1.2 Engine Interface

**Location**: `src/quantumvitas/engine/base.py`

```python
class Engine:
    name: str = "engine"
    
    def __init__(self, config: EngineConfig):
        self.config = config
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        raise NotImplementedError
```

### 1.3 Engine Registry

**Location**: `src/quantumvitas/engine/registry.py`

```python
class EngineRegistry:
    def register(self, engine: Engine) -> None
    def get(self, name: str) -> Engine

def create_default_registry() -> EngineRegistry:
    # Returns registry with QE engine registered
```

### 1.4 Step Type Registry

**Location**: `src/quantumvitas/workflow/registry.py`

The `pyscf_scf` step type is already registered:

```python
"pyscf_scf": StepTypeSpec(
    id="pyscf_scf",
    engine="pyscf",
    executable="python",  # Python-native
    description="PySCF single-point calculation (HF/DFT)",
    ...
)
```

### 1.5 QE Subprocess Execution Pattern

**Location**: `src/quantumvitas/core/engines/qe_calculation.py:227-266`

```python
process = subprocess.Popen(
    cmd,
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    cwd=working_dir,
    env=env,
)
stdout, stderr = process.communicate(timeout=timeout)
```

---

## 2. Implemented Integration Points

### 2.1 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ Daemon Process (never imports pyscf)                        │
│                                                             │
│  ┌──────────────┐    ┌───────────────────┐                 │
│  │ EngineRegistry│───▶│ PySCFEngine       │                 │
│  └──────────────┘    │   .probe()        │                 │
│                      │   .run_step()     │                 │
│                      └────────┬──────────┘                 │
│                               │ subprocess.Popen()          │
└───────────────────────────────┼─────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────┐
│ Runner Subprocess (imports pyscf)                           │
│                                                             │
│  python -m quantumvitas.engines.pyscf.runner job.json       │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ 1. Read job.json                                      │  │
│  │ 2. import pyscf                                       │  │
│  │ 3. Build Mole, run SCF                                │  │
│  │ 4. Write results.json                                 │  │
│  │ 5. Exit with return code                              │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 File Structure

```
src/quantumvitas/
├── engine/
│   ├── base.py              # Engine interface (unchanged)
│   ├── registry.py          # Engine registry (add PySCF)
│   ├── pyscf_engine.py      # Subprocess-based engine (refactored)
│   └── qe_engine.py         # QE engine (unchanged)
│
└── engines/
    └── pyscf/
        ├── __init__.py      # Package marker
        └── runner.py        # Subprocess entrypoint (imports pyscf)
```

### 2.3 Job Spec Schema

**job.json** written by engine, read by runner:

```json
{
  "step_type": "pyscf_scf",
  "working_dir": "/path/to/raw",
  "parameters": {
    "atoms": [
      {"element": "O", "x": 0.0, "y": 0.0, "z": 0.117790},
      {"element": "H", "x": 0.0, "y": 0.755453, "z": -0.471161},
      {"element": "H", "x": 0.0, "y": -0.755453, "z": -0.471161}
    ],
    "basis": "sto-3g",
    "method": "rhf",
    "charge": 0,
    "spin": 0,
    "unit": "Angstrom",
    "max_cycle": 50,
    "conv_tol": 1e-9
  },
  "resources": {
    "max_memory_mb": 4000,
    "scratch_dir": "/tmp/pyscf_scratch"
  }
}
```

### 2.4 Results Schema

**results.json** written by runner:

```json
{
  "success": true,
  "energy": -74.96590119,
  "energy_unit": "Hartree",
  "converged": true,
  "method": "rhf",
  "basis": "sto-3g",
  "n_electrons": 10,
  "n_atoms": 3,
  "homo_index": 4,
  "lumo_index": 5,
  "homo_energy": -0.3876,
  "lumo_energy": 0.5981,
  "gap": 0.9857,
  "gap_ev": 26.82,
  "mo_energies": [...],
  "mo_occupations": [...],
  "dipole_moment": [...],
  "error": null,
  "execution_time": 1.23,
  "pyscf_version": "2.4.0"
}
```

---

## 3. Molecule vs PBC Detection

### 3.1 Rule

```
IF structure has no lattice/cell → MOLECULAR (PySCF Mole)
ELSE → PERIODIC (currently unsupported, return clear error)
```

### 3.2 Implementation

**In runner** (when reading structure from parameters):

```python
def detect_system_type(params: Dict) -> str:
    """Detect if system is molecular or periodic."""
    # Check for cell/lattice in parameters
    if "cell" in params or "lattice" in params:
        return "periodic"
    return "molecular"
```

**For periodic systems**, runner returns:

```json
{
  "success": false,
  "error": "PBC/periodic systems not yet supported by PySCF engine. Use QE for periodic calculations."
}
```

---

## 4. Platform Detection

### 4.1 Windows Handling

**In PySCFEngine.probe():**

```python
import sys

def probe(self) -> Dict[str, Any]:
    if sys.platform == "win32":
        return {
            "available": False,
            "reason": "PySCF native Windows is not supported. Use WSL or Docker.",
            "version": None,
        }
    # ... continue with subprocess probe
```

### 4.2 Probe via Subprocess

```python
def probe(self) -> Dict[str, Any]:
    """Check if PySCF is available without importing it."""
    try:
        result = subprocess.run(
            [sys.executable, "-c", "import pyscf; print(pyscf.__version__)"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return {
                "available": True,
                "version": result.stdout.strip(),
            }
        else:
            return {
                "available": False,
                "reason": f"PySCF import failed: {result.stderr}",
            }
    except Exception as e:
        return {"available": False, "reason": str(e)}
```

---

## 5. Future Managed Engine Bundle Plan

### 5.1 What Would Change

**Engine resolution** (future `resolve_pyscf_executable()`):

```python
def resolve_pyscf_executable() -> Path:
    """Resolve PySCF runner executable."""
    # 1. Check for managed engine bundle
    managed = find_managed_pyscf_bundle()
    if managed:
        return managed / "bin" / "pyscf-runner"
    
    # 2. Fallback to dev-mode (current venv)
    return Path(sys.executable)
```

**Managed bundle structure**:

```
.qmatsuite/engines/pyscf/
└── managed:pyscf-2.11.0:darwin-arm64/
    ├── meta.json           # Version, platform, dependencies
    ├── bin/
    │   └── pyscf-runner    # Wrapper script
    └── venv/               # Isolated Python environment
        └── bin/python
```

### 5.2 What Stays Stable

- **Job schema** (job.json format)
- **Results schema** (results.json format)
- **Subprocess contract** (stdin/stdout/stderr handling)
- **StepResult dataclass**
- **Engine interface** (probe(), run_step())

### 5.3 Migration Path

1. **Phase 1 (now)**: Dev-mode only, uses `sys.executable`
2. **Phase 2 (future)**: Add managed bundle download
3. **Phase 3 (future)**: Add bundle resolution priority

---

## 6. What to Run Locally

### 6.1 Install PySCF (macOS/Linux only)

```bash
# In QMatSuite venv
pip install --prefer-binary pyscf

# Verify installation
python -c "import pyscf; print(pyscf.__version__)"
```

### 6.2 Run Integration Tests

```bash
# Run all PySCF tests
pytest tests/integration/test_pyscf_execution.py -v

# Run a single test
pytest tests/integration/test_pyscf_execution.py::TestPySCFH2OCalculation::test_h2o_rhf_sto3g -v
```

### 6.3 Run Sample Calculation from CLI

```bash
# Run the water demo project
cd resources/demo_projects
qv run water_pyscf_scf.yml

# Or generate and run
python tools/generate_pyscf_demo.py
cd resources/demo_projects
qv run water-pyscf-scf
```

### 6.4 Check Engine Availability

```bash
# From Python
python -c "
from quantumvitas.engine.pyscf_engine import PySCFEngine
engine = PySCFEngine()
print(engine.probe())
"
```

---

## 7. Resource Mapping

| QMatSuite Resource | PySCF Setting | Default |
|--------------------|---------------|---------|
| `resources.max_memory_mb` | `PYSCF_MAX_MEMORY` | 4000 |
| `resources.scratch_dir` | `PYSCF_TMPDIR` | system temp |
| `resources.threads` | `OMP_NUM_THREADS` | system default |

---

## 8. Error Messages

| Condition | User-Facing Message |
|-----------|---------------------|
| Windows native | "PySCF native Windows is not supported. Use WSL or Docker." |
| PySCF not installed | "PySCF not installed. Install with: pip install pyscf" |
| PBC structure | "PBC/periodic systems not yet supported by PySCF engine. Use QE for periodic calculations." |
| SCF not converged | "SCF did not converge after N cycles. Try increasing max_cycle or using a different guess." |
| Invalid method | "Unknown method: X. Supported: rhf, uhf, rohf, rks, uks, roks" |

---

## 9. Checklist

- [x] Document existing schemas/contracts
- [x] Design subprocess architecture
- [x] Implement subprocess runner (`engines/pyscf/runner.py`)
- [x] Refactor `PySCFEngine` to use subprocess
- [x] Register PySCF engine in `create_default_registry()`
- [x] Add Windows platform detection
- [x] Add PBC detection and error
- [x] Update unit/integration tests
- [x] Test on macOS/Linux (22 unit tests, 11 integration tests pass)
- [x] Document Windows limitation

## 10. Files Modified/Created

| File | Action | Description |
|------|--------|-------------|
| `src/quantumvitas/engines/__init__.py` | Created | Package marker for engine subprocess runners |
| `src/quantumvitas/engines/pyscf/__init__.py` | Created | PySCF runner package marker |
| `src/quantumvitas/engines/pyscf/runner.py` | Created | Subprocess entrypoint that imports PySCF |
| `src/quantumvitas/engines/pyscf/__main__.py` | Created | Allow `python -m quantumvitas.engines.pyscf` |
| `src/quantumvitas/engine/pyscf_engine.py` | Refactored | Now uses subprocess instead of direct import |
| `src/quantumvitas/engine/registry.py` | Modified | Added PySCF engine registration |
| `tests/unit/test_pyscf_integration.py` | Updated | Tests for new subprocess architecture |
| `docs/pyscf_integration_plan.md` | Created | This documentation |

## 11. Test Summary

**Unit Tests** (`tests/unit/test_pyscf_integration.py`):
- 22 tests, all passing
- Tests step type registration, engine probe, subprocess runner

**Integration Tests** (`tests/integration/test_pyscf_execution.py`):
- 11 tests, all passing
- Tests actual PySCF calculations (H2O, H2, radicals)
- Skip automatically if PySCF not installed

