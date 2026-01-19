# VASP Integration Implementation Plan

**Purpose**: Staged PR plan for Cursor auto implementation with test pyramid.

---

## Implementation Overview

### Target End State

High-level integration tests that run three workflows (SCF, bands, DOS) through the API/daemon layer using a temp project structure under `.tmp/`, analogous to QE's highest-level tests.

### Test Pyramid Strategy

```
Level 4: Daemon/Project Tests          [PR6+]
  └── Full workflow through QVService API
Level 3: Runner Tests with fake_vasp   [PR4-5]
  └── Manifest, history, locking integration
Level 2: Materialization Tests         [PR3]
  └── Input file determinism (POSCAR/INCAR/KPOINTS/POTCAR)
Level 1: Unit Tests                    [PR1-2]
  └── Pure functions: parsing, mapping, resolution
```

---

## PR0: Documentation + Repository Scaffolding (Optional)

### Purpose
Prepare the repository structure for VASP integration.

### Files to Create/Modify

| File | Action | Description |
|------|--------|-------------|
| `docs/engines/vasp/` | CREATE | Directory for VASP documentation |
| `docs/engines/vasp/01_qe_backend_code_review.md` | CREATE | This document |
| `docs/engines/vasp/02_vasp_research_and_specs.md` | CREATE | Specs document |
| `docs/engines/vasp/03_vasp_integration_implementation_plan.md` | CREATE | This plan |
| `src/quantumvitas/engines/vasp/` | CREATE | Empty directory with `__init__.py` |
| `tests/integration/vasp/` | CREATE | Empty directory with `__init__.py` |
| `tests/utils/fake_vasp.py` | STUB | Empty file with docstring |

### Acceptance Criteria
- [ ] All documentation files committed
- [ ] Directory structure created
- [ ] No production code changes

---

## PR1: Engine Discovery + Member Selection

### Purpose
Implement VASP binary discovery and executable selection logic.

### Files to Create

```
src/quantumvitas/core/engines/vasp_resolver.py
src/quantumvitas/engine/vasp_engine.py
tests/unit/vasp/test_vasp_resolver.py
tests/unit/vasp/test_vasp_engine_registration.py
```

### Key Functions/Classes

#### `core/engines/vasp_resolver.py`

```python
"""VASP binary resolution."""

from pathlib import Path
from typing import Optional
import os

def resolve_vasp_bin_dir() -> Path:
    """
    Resolve VASP binary directory.
    
    Resolution order:
    1. QMATSUITE_VASP_BIN environment variable
    2. ~/.qmatsuite/engines/vasp/*/bin/vasp_std
    3. System PATH (vasp_std)
    
    Returns:
        Path to directory containing VASP binaries
        
    Raises:
        RuntimeError: If VASP not found
    """
    # Implementation...

def resolve_vasp_bin(variant: str = "vasp_std") -> Path:
    """
    Resolve specific VASP executable.
    
    Args:
        variant: "vasp_std", "vasp_gam", or "vasp_ncl"
    """
    # Implementation...

def resolve_potcar_library() -> Optional[Path]:
    """
    Resolve POTCAR library path.
    
    Resolution order:
    1. QMATSUITE_VASP_POTCAR_DIR environment variable
    2. ~/.qmatsuite/engines/vasp/potpaw_*/
    """
    # Implementation...

def is_vasp_available() -> bool:
    """Check if VASP is available (binary + POTCAR library)."""
    try:
        resolve_vasp_bin()
        potcar = resolve_potcar_library()
        return potcar is not None and potcar.exists()
    except RuntimeError:
        return False

def select_vasp_executable(step_params: dict) -> str:
    """
    Select VASP variant based on calculation parameters.
    
    Returns: "vasp_std", "vasp_gam", or "vasp_ncl"
    """
    # SOC/Noncollinear → vasp_ncl
    if step_params.get("LSORBIT") or step_params.get("LNONCOLLINEAR"):
        return "vasp_ncl"
    
    # Gamma-only → vasp_gam
    kpoints = step_params.get("kpoints", {})
    if kpoints.get("type") == "gamma":
        return "vasp_gam"
    
    return "vasp_std"
```

#### `engine/vasp_engine.py`

```python
"""VASP engine wrapper."""

from pathlib import Path
from typing import Optional, List
from quantumvitas.engine.base import Engine, EngineConfig, StepResult
from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin, is_vasp_available

class VaspEngine(Engine):
    """VASP engine implementation."""
    
    name = "vasp"
    
    def __init__(self, config: Optional[EngineConfig] = None, defer_binary_resolution: bool = False):
        super().__init__(config or EngineConfig(name="vasp"))
        self._defer_binary_resolution = defer_binary_resolution
        self._vasp_bin: Optional[Path] = None
        
        if not defer_binary_resolution:
            self._vasp_bin = resolve_vasp_bin()
    
    @property
    def supported_presets(self) -> List[str]:
        """VASP supports same preset dimensions as QE (for now)."""
        return ["precision"]  # Start minimal, expand later
    
    def run_step(self, step, working_dir: Path) -> StepResult:
        """Execute a VASP step."""
        # Deferred implementation in PR4
        raise NotImplementedError("VASP execution not yet implemented")
```

#### `engine/registry.py` (Modify)

```python
# Add to create_default_registry()
from .vasp_engine import VaspEngine

def create_default_registry(...) -> EngineRegistry:
    registry = EngineRegistry()
    registry.register(QeEngine(config))
    registry.register(PySCFEngine())
    if include_orca:
        registry.register(ORCAEngine(defer_binary_resolution=True))
    # NEW: Always register VASP (binary resolution deferred)
    registry.register(VaspEngine(defer_binary_resolution=True))
    return registry
```

### Unit Tests

#### `tests/unit/vasp/test_vasp_resolver.py`

```python
"""Tests for VASP resolver."""

import pytest
from pathlib import Path
from quantumvitas.core.engines.vasp_resolver import (
    resolve_vasp_bin,
    resolve_potcar_library,
    is_vasp_available,
    select_vasp_executable,
)

class TestVaspResolver:
    def test_select_executable_default(self):
        """Default params → vasp_std."""
        result = select_vasp_executable({})
        assert result == "vasp_std"
    
    def test_select_executable_soc(self):
        """LSORBIT=True → vasp_ncl."""
        result = select_vasp_executable({"LSORBIT": True})
        assert result == "vasp_ncl"
    
    def test_select_executable_gamma(self):
        """Gamma k-points → vasp_gam."""
        result = select_vasp_executable({"kpoints": {"type": "gamma"}})
        assert result == "vasp_gam"
    
    def test_is_available_returns_bool(self):
        """is_vasp_available should not raise."""
        result = is_vasp_available()
        assert isinstance(result, bool)

class TestVaspResolverWithEnv:
    def test_env_var_override(self, tmp_path, monkeypatch):
        """QMATSUITE_VASP_BIN overrides default."""
        fake_vasp = tmp_path / "vasp_std"
        fake_vasp.write_text("#!/bin/bash\necho fake")
        fake_vasp.chmod(0o755)
        
        monkeypatch.setenv("QMATSUITE_VASP_BIN", str(tmp_path))
        
        result = resolve_vasp_bin("vasp_std")
        assert result == fake_vasp
```

#### `tests/unit/vasp/test_vasp_engine_registration.py`

```python
"""Tests for VASP engine registration."""

import pytest
from quantumvitas.engine.registry import create_default_registry

def test_vasp_engine_registered():
    """VASP engine should be in default registry."""
    registry = create_default_registry()
    assert registry.has("vasp")

def test_vasp_engine_deferred_resolution():
    """VASP engine should not fail without binary."""
    registry = create_default_registry()
    vasp = registry.get("vasp")
    assert vasp.name == "vasp"
    # Should not raise (deferred resolution)
```

### Acceptance Criteria
- [ ] `resolve_vasp_bin()` works with environment variable
- [ ] `select_vasp_executable()` returns correct variant
- [ ] `VaspEngine` registers in default registry
- [ ] All unit tests pass
- [ ] No execution yet (deferred)

---

## PR2: Step Types + Gen→Spec Mapping

### Purpose
Define VASP step types and ensure bijection with public types.

### Files to Create/Modify

```
src/quantumvitas/workflow/registry.py  (MODIFY)
tests/unit/vasp/test_vasp_step_types.py
tests/unit/vasp/test_vasp_gen_spec_bijection.py
```

### Changes to `workflow/registry.py`

```python
# Add to _STEP_TYPES dictionary

"vasp_scf": StepTypeSpec(
    id="scf",
    machine_type="vasp_scf",
    public_type="scf",
    engine="vasp",
    executable="vasp_std",
    description="VASP static SCF calculation",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=True,
),
"vasp_bands": StepTypeSpec(
    id="bands",
    machine_type="vasp_bands",
    public_type="bands",
    engine="vasp",
    executable="vasp_std",
    description="VASP band structure (non-SCF along k-path)",
    requires_structure=True,
    requires_charge_density=True,
    produces_charge_density=False,
),
"vasp_dos": StepTypeSpec(
    id="dos",
    machine_type="vasp_dos",
    public_type="dos",
    engine="vasp",
    executable="vasp_std",
    description="VASP density of states",
    requires_structure=True,
    requires_charge_density=True,
    produces_charge_density=False,
),
"vasp_relax": StepTypeSpec(
    id="relax",
    machine_type="vasp_relax",
    public_type="relax",
    engine="vasp",
    executable="vasp_std",
    description="VASP geometry optimization",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    is_structure_transform=True,
),
```

### Unit Tests

#### `tests/unit/vasp/test_vasp_step_types.py`

```python
"""Tests for VASP step type definitions."""

import pytest
from quantumvitas.workflow.registry import get_registry

class TestVaspStepTypes:
    @pytest.fixture
    def registry(self):
        return get_registry()
    
    def test_vasp_scf_exists(self, registry):
        spec = registry.get("vasp_scf")
        assert spec is not None
        assert spec.engine == "vasp"
        assert spec.executable == "vasp_std"
    
    def test_vasp_bands_requires_charge(self, registry):
        spec = registry.get("vasp_bands")
        assert spec.requires_charge_density is True
    
    def test_vasp_relax_is_structure_transform(self, registry):
        spec = registry.get("vasp_relax")
        assert spec.is_structure_transform is True
    
    @pytest.mark.parametrize("machine_type", [
        "vasp_scf", "vasp_bands", "vasp_dos", "vasp_relax"
    ])
    def test_vasp_types_have_public_type(self, registry, machine_type):
        spec = registry.get(machine_type)
        assert spec.public_type is not None
```

#### `tests/unit/vasp/test_vasp_gen_spec_bijection.py`

```python
"""Test gen→spec bijection for VASP step types."""

import pytest
from quantumvitas.workflow.registry import get_registry, normalize_step_type_to_public

class TestVaspGenSpecBijection:
    @pytest.fixture
    def registry(self):
        return get_registry()
    
    def test_vasp_machine_to_public(self, registry):
        """Machine types map to public types correctly."""
        assert normalize_step_type_to_public("vasp_scf") == "scf"
        assert normalize_step_type_to_public("vasp_bands") == "bands"
        assert normalize_step_type_to_public("vasp_dos") == "dos"
        assert normalize_step_type_to_public("vasp_relax") == "relax"
    
    def test_vasp_public_lookup(self, registry):
        """Public types resolve to VASP specs when requested."""
        # Note: Need to specify engine for disambiguation
        vasp_specs = registry.list_by_engine_machine("vasp")
        assert "vasp_scf" in vasp_specs
        assert "vasp_bands" in vasp_specs
    
    def test_no_duplicate_machine_types(self, registry):
        """Each machine type is unique."""
        all_machine_types = registry.list_all_machine()
        assert len(all_machine_types) == len(set(all_machine_types))
```

### Acceptance Criteria
- [ ] All 4 VASP step types defined
- [ ] Machine→public type mapping works
- [ ] Bijection tests pass
- [ ] No conflicts with existing QE types

---

## PR3: Writer/Materialize (Input Files)

### Purpose
Implement VASP input file generation with species_map integration.

### Files to Create

```
src/quantumvitas/engines/vasp/__init__.py
src/quantumvitas/engines/vasp/input_writer.py
src/quantumvitas/engines/vasp/potcar_assembly.py
tests/unit/vasp/test_vasp_poscar_writer.py
tests/unit/vasp/test_vasp_incar_writer.py
tests/unit/vasp/test_vasp_kpoints_writer.py
tests/unit/vasp/test_vasp_potcar_assembly.py
tests/unit/vasp/test_vasp_materialize_determinism.py
```

### Key Functions

#### `engines/vasp/input_writer.py`

```python
"""VASP input file writers."""

from pathlib import Path
from typing import Dict, Any, List, Optional
from pymatgen.core import Structure
from pymatgen.io.vasp import Poscar, Incar, Kpoints

def write_poscar(structure: Structure, path: Path) -> Path:
    """
    Write POSCAR file from Structure.
    
    Uses pymatgen for format compatibility.
    """
    poscar = Poscar(structure)
    poscar.write_file(str(path))
    return path

def write_incar(params: Dict[str, Any], path: Path, system_name: str = "QMatSuite") -> Path:
    """
    Write INCAR file from parameters dict.
    
    Args:
        params: Dict of INCAR tags (e.g., {"ENCUT": 400, "EDIFF": 1e-6})
        path: Output path
        system_name: SYSTEM tag value
    """
    incar = Incar(params)
    incar["SYSTEM"] = system_name
    incar.write_file(str(path))
    return path

def write_kpoints(kpoints_spec: Dict[str, Any], path: Path) -> Path:
    """
    Write KPOINTS file from specification.
    
    Supports:
    - automatic: Monkhorst-Pack or Gamma-centered mesh
    - line-mode: High-symmetry path for band structure
    """
    ktype = kpoints_spec.get("type", "monkhorst-pack").lower()
    
    if ktype in ("monkhorst-pack", "gamma", "automatic"):
        mesh = kpoints_spec.get("mesh", [4, 4, 4])
        shift = kpoints_spec.get("shift", [0, 0, 0])
        kpoints = Kpoints.monkhorst_automatic(kpts=mesh, shift=shift)
        if ktype == "gamma":
            kpoints = Kpoints.gamma_automatic(kpts=mesh, shift=shift)
    
    elif ktype == "line-mode":
        # Band structure path
        path_spec = kpoints_spec.get("path", [])
        divisions = kpoints_spec.get("divisions", 20)
        kpoints = _build_line_mode_kpoints(path_spec, divisions)
    
    else:
        raise ValueError(f"Unknown KPOINTS type: {ktype}")
    
    kpoints.write_file(str(path))
    return path

def _build_line_mode_kpoints(path_spec: List, divisions: int) -> Kpoints:
    """Build line-mode KPOINTS for band structure."""
    # Implementation using pymatgen or manual format
    # ...

def materialize_vasp_inputs(
    structure: Structure,
    step_params: Dict[str, Any],
    species_map: Dict[str, Dict[str, Any]],
    working_dir: Path,
    potcar_library: Path,
    system_name: str = "QMatSuite",
) -> Dict[str, Path]:
    """
    Materialize all VASP input files.
    
    Returns:
        Dict of {"POSCAR": path, "INCAR": path, "KPOINTS": path, "POTCAR": path}
    """
    working_dir.mkdir(parents=True, exist_ok=True)
    
    poscar_path = write_poscar(structure, working_dir / "POSCAR")
    incar_path = write_incar(step_params.get("incar", {}), working_dir / "INCAR", system_name)
    kpoints_path = write_kpoints(step_params.get("kpoints", {}), working_dir / "KPOINTS")
    
    from quantumvitas.engines.vasp.potcar_assembly import assemble_potcar
    potcar_path = assemble_potcar(structure, species_map, potcar_library, working_dir)
    
    return {
        "POSCAR": poscar_path,
        "INCAR": incar_path,
        "KPOINTS": kpoints_path,
        "POTCAR": potcar_path,
    }
```

#### `engines/vasp/potcar_assembly.py`

```python
"""POTCAR assembly from library."""

from pathlib import Path
from typing import Dict, Any
from pymatgen.core import Structure
from quantumvitas.core.pseudo_provenance import compute_sha256_file

def assemble_potcar(
    structure: Structure,
    species_map: Dict[str, Dict[str, Any]],
    potcar_library: Path,
    working_dir: Path,
) -> Path:
    """
    Assemble POTCAR by concatenating element POTCARs.
    
    Order matches element order in Structure (as written to POSCAR).
    """
    # Get unique elements in POSCAR order
    elements = []
    seen = set()
    for site in structure:
        el = str(site.specie)
        if el not in seen:
            elements.append(el)
            seen.add(el)
    
    potcar_path = working_dir / "POTCAR"
    with open(potcar_path, "wb") as out_f:
        for element in elements:
            spec = species_map.get(element, {})
            variant = spec.get("potcar_variant", element)
            expected_sha = spec.get("potcar_sha256")
            
            # Find element POTCAR
            element_potcar = potcar_library / variant / "POTCAR"
            if not element_potcar.exists():
                raise RuntimeError(
                    f"POTCAR not found for {element} (variant={variant}): {element_potcar}"
                )
            
            # Verify SHA if pinned
            if expected_sha:
                actual_sha = compute_sha256_file(element_potcar)
                if actual_sha != expected_sha:
                    raise ValueError(
                        f"POTCAR SHA mismatch for {element}: expected {expected_sha[:16]}..."
                    )
            
            # Append to assembled POTCAR
            with open(element_potcar, "rb") as in_f:
                out_f.write(in_f.read())
    
    return potcar_path

def compute_vasp_pseudo_set_sha(
    elements: List[str],
    species_map: Dict[str, Dict[str, Any]],
) -> str:
    """Compute pseudo_set_sha for manifest."""
    import hashlib
    
    sha_parts = []
    for element in sorted(elements):
        spec = species_map.get(element, {})
        sha = spec.get("potcar_sha256", "")
        sha_parts.append(f"{element}:{sha}")
    
    combined = "\n".join(sha_parts)
    return hashlib.sha256(combined.encode()).hexdigest()[:16]
```

### Unit Tests

#### `tests/unit/vasp/test_vasp_poscar_writer.py`

```python
"""Tests for POSCAR writer."""

import pytest
from pymatgen.core import Structure, Lattice
from quantumvitas.engines.vasp.input_writer import write_poscar

@pytest.fixture
def si_structure():
    lattice = Lattice.cubic(5.43)
    return Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])

class TestPoscarWriter:
    def test_write_poscar_creates_file(self, si_structure, tmp_path):
        path = write_poscar(si_structure, tmp_path / "POSCAR")
        assert path.exists()
    
    def test_poscar_content_valid(self, si_structure, tmp_path):
        path = write_poscar(si_structure, tmp_path / "POSCAR")
        content = path.read_text()
        assert "Si" in content
        assert "Direct" in content or "Cartesian" in content
    
    def test_poscar_roundtrip(self, si_structure, tmp_path):
        """Structure survives write→read cycle."""
        from pymatgen.io.vasp import Poscar
        
        path = write_poscar(si_structure, tmp_path / "POSCAR")
        poscar = Poscar.from_file(str(path))
        
        assert len(poscar.structure) == len(si_structure)
```

#### `tests/unit/vasp/test_vasp_materialize_determinism.py`

```python
"""Test materialization determinism."""

import pytest
from pymatgen.core import Structure, Lattice
from quantumvitas.engines.vasp.input_writer import materialize_vasp_inputs

class TestMaterializeDeterminism:
    @pytest.fixture
    def si_structure(self):
        lattice = Lattice.cubic(5.43)
        return Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    @pytest.fixture
    def fake_potcar_lib(self, tmp_path):
        """Create fake POTCAR library."""
        lib = tmp_path / "potpaw_PBE"
        si_dir = lib / "Si"
        si_dir.mkdir(parents=True)
        (si_dir / "POTCAR").write_text("FAKE POTCAR Si\n")
        return lib
    
    def test_same_input_same_output(self, si_structure, fake_potcar_lib, tmp_path):
        """Same inputs produce identical outputs."""
        params = {"incar": {"ENCUT": 400}, "kpoints": {"mesh": [4, 4, 4]}}
        species_map = {"Si": {"potcar_variant": "Si"}}
        
        # First materialization
        dir1 = tmp_path / "run1"
        result1 = materialize_vasp_inputs(
            si_structure, params, species_map, dir1, fake_potcar_lib
        )
        
        # Second materialization
        dir2 = tmp_path / "run2"
        result2 = materialize_vasp_inputs(
            si_structure, params, species_map, dir2, fake_potcar_lib
        )
        
        # Compare file contents
        for key in ["POSCAR", "INCAR", "KPOINTS", "POTCAR"]:
            content1 = result1[key].read_text()
            content2 = result2[key].read_text()
            assert content1 == content2, f"{key} differs between runs"
```

### Acceptance Criteria
- [ ] POSCAR writer produces valid files
- [ ] INCAR writer handles all common tags
- [ ] KPOINTS writer supports automatic and line-mode
- [ ] POTCAR assembly concatenates in correct order
- [ ] SHA verification works for pinned POTCARs
- [ ] Materialization is deterministic

---

## PR4: Runner Execution + History/Manifest Integration

### Purpose
Implement VASP execution with fake_vasp harness for testing.

### Files to Create

```
src/quantumvitas/engines/vasp/runner.py
src/quantumvitas/execution/vasp_handler.py
tests/utils/fake_vasp.py
tests/integration/vasp/conftest.py
tests/integration/vasp/test_vasp_runner_fake.py
tests/integration/vasp/test_vasp_manifest_integration.py
```

### Key Functions

#### `engines/vasp/runner.py`

```python
"""VASP calculation runner."""

import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass

from quantumvitas.core.engines.vasp_resolver import resolve_vasp_bin, select_vasp_executable

@dataclass
class VaspStepResult:
    """Result of a VASP step execution."""
    step_type: str
    success: bool
    return_code: int
    working_dir: Path
    stdout_file: Optional[Path] = None
    stderr_file: Optional[Path] = None
    execution_time: float = 0.0
    error: Optional[str] = None

def run_vasp_step(
    step_type: str,
    step_params: Dict[str, Any],
    working_dir: Path,
    timeout: Optional[float] = None,
) -> VaspStepResult:
    """
    Run a VASP step.
    
    Args:
        step_type: Machine step type (e.g., "vasp_scf")
        step_params: Step parameters (incar, kpoints, etc.)
        working_dir: Directory with input files
        timeout: Optional timeout in seconds
    """
    start_time = time.time()
    
    # Select executable
    variant = select_vasp_executable(step_params.get("incar", {}))
    vasp_bin = resolve_vasp_bin(variant)
    
    # Prepare output files
    stdout_path = working_dir / f"{step_type}.out"
    stderr_path = working_dir / f"{step_type}.err"
    
    # Execute VASP
    try:
        with open(stdout_path, "w") as stdout_f, open(stderr_path, "w") as stderr_f:
            proc = subprocess.Popen(
                [str(vasp_bin)],
                cwd=str(working_dir),
                stdout=stdout_f,
                stderr=stderr_f,
            )
            
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                proc.kill()
                return VaspStepResult(
                    step_type=step_type,
                    success=False,
                    return_code=-1,
                    working_dir=working_dir,
                    stdout_file=stdout_path,
                    stderr_file=stderr_path,
                    execution_time=time.time() - start_time,
                    error=f"Timeout after {timeout}s",
                )
        
        return VaspStepResult(
            step_type=step_type,
            success=(proc.returncode == 0),
            return_code=proc.returncode,
            working_dir=working_dir,
            stdout_file=stdout_path,
            stderr_file=stderr_path,
            execution_time=time.time() - start_time,
        )
    
    except Exception as e:
        return VaspStepResult(
            step_type=step_type,
            success=False,
            return_code=-1,
            working_dir=working_dir,
            execution_time=time.time() - start_time,
            error=str(e),
        )
```

#### `tests/utils/fake_vasp.py`

```python
"""Fake VASP for testing without real binary."""

from pathlib import Path
from typing import Dict, Any

FAKE_OSZICAR_SCF = """       N       E                     dE             d eps       ncg     rms
DAV:   1    -0.100000000000E+02   -0.10000E+02   -0.10000E+02   100   0.100E+01
DAV:   2    -0.100100000000E+02   -0.10000E-01   -0.10000E-02   100   0.100E+00
   1 F= -.10010000E+02 E0= -.10010000E+02  d E =-.100100E+02
"""

FAKE_OUTCAR_SCF = """
 vasp.6.1.0 11Aug20 (build May 01 2021)
 running on    4 total cores
 ...
 free  energy   TOTEN  =       -10.010000 eV
 ...
 TOTAL-FORCE (eV/Angst)
 -----------------------------------------------------------------------------------
     0.00000    0.00000    0.00000   0.000000   0.000000   0.000000
     0.00000    0.00000    0.00000   0.000000   0.000000   0.000000
 -----------------------------------------------------------------------------------
 ...
 Elapsed time (sec):        1.234
"""

def fake_vasp_scf(working_dir: Path, params: Dict[str, Any] = None) -> int:
    """Create fake VASP SCF outputs. Returns exit code."""
    (working_dir / "OSZICAR").write_text(FAKE_OSZICAR_SCF)
    (working_dir / "OUTCAR").write_text(FAKE_OUTCAR_SCF)
    
    # Copy POSCAR to CONTCAR
    poscar = working_dir / "POSCAR"
    if poscar.exists():
        (working_dir / "CONTCAR").write_text(poscar.read_text())
    
    # Create fake CHGCAR
    (working_dir / "CHGCAR").write_text("FAKE CHGCAR for testing\n")
    
    return 0

def fake_vasp_bands(working_dir: Path, params: Dict[str, Any] = None) -> int:
    """Create fake VASP bands outputs."""
    fake_vasp_scf(working_dir, params)
    
    # Fake EIGENVAL
    eigenval = """    1    1    1
  1   1   1
    4
  0.0000000E+00  0.0000000E+00  0.0000000E+00  1.0000000E+00
   1      -5.0000
   2       0.0000
   3       2.5000
   4       5.0000
"""
    (working_dir / "EIGENVAL").write_text(eigenval)
    return 0

def fake_vasp_dos(working_dir: Path, params: Dict[str, Any] = None) -> int:
    """Create fake VASP DOS outputs."""
    fake_vasp_scf(working_dir, params)
    
    # Fake DOSCAR
    doscar = """  System
   1   1   1
  10.0000  -10.0000  100  0.0000  1.0000
  -10.0000   0.0000   0.0000
   -5.0000   0.5000   0.2500
    0.0000   1.0000   0.5000
    5.0000   0.5000   0.7500
   10.0000   0.0000   1.0000
"""
    (working_dir / "DOSCAR").write_text(doscar)
    return 0

def fake_vasp_relax(working_dir: Path, params: Dict[str, Any] = None) -> int:
    """Create fake VASP relax outputs with modified structure."""
    # Multi-step OSZICAR
    oszicar = """       N       E                     dE             d eps       ncg     rms
   1 F= -.10000000E+02 E0= -.10000000E+02  d E =-.100000E+02
   2 F= -.10100000E+02 E0= -.10100000E+02  d E =-.100000E-01
   3 F= -.10110000E+02 E0= -.10110000E+02  d E =-.100000E-02
"""
    (working_dir / "OSZICAR").write_text(oszicar)
    (working_dir / "OUTCAR").write_text(FAKE_OUTCAR_SCF.replace("-10.010000", "-10.110000"))
    
    # Modified CONTCAR (slightly different positions)
    poscar = working_dir / "POSCAR"
    if poscar.exists():
        content = poscar.read_text()
        # Modify slightly to simulate relaxation
        (working_dir / "CONTCAR").write_text(content.replace("0.25", "0.251"))
    
    return 0
```

#### `tests/integration/vasp/test_vasp_runner_fake.py`

```python
"""Tests for VASP runner with fake binary."""

import pytest
from pathlib import Path
from pymatgen.core import Structure, Lattice

from quantumvitas.engines.vasp.input_writer import materialize_vasp_inputs
from tests.utils.fake_vasp import fake_vasp_scf

class TestVaspRunnerFake:
    @pytest.fixture
    def si_structure(self):
        lattice = Lattice.cubic(5.43)
        return Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    @pytest.fixture
    def fake_potcar_lib(self, tmp_path):
        lib = tmp_path / "potpaw_PBE"
        si_dir = lib / "Si"
        si_dir.mkdir(parents=True)
        (si_dir / "POTCAR").write_text("FAKE POTCAR Si\n")
        return lib
    
    def test_fake_scf_produces_outputs(self, si_structure, fake_potcar_lib, tmp_path):
        """fake_vasp_scf creates expected output files."""
        workdir = tmp_path / "vasp_run"
        params = {"incar": {"ENCUT": 400}, "kpoints": {"mesh": [4, 4, 4]}}
        species_map = {"Si": {"potcar_variant": "Si"}}
        
        # Materialize inputs
        materialize_vasp_inputs(si_structure, params, species_map, workdir, fake_potcar_lib)
        
        # Run fake VASP
        exit_code = fake_vasp_scf(workdir)
        
        assert exit_code == 0
        assert (workdir / "OUTCAR").exists()
        assert (workdir / "OSZICAR").exists()
        assert (workdir / "CONTCAR").exists()
        assert (workdir / "CHGCAR").exists()
```

### Acceptance Criteria
- [ ] `run_vasp_step()` executes subprocess correctly
- [ ] Timeout handling works
- [ ] fake_vasp creates all expected files
- [ ] Manifest integration matches QE pattern
- [ ] Locking behavior correct

---

## PR5: Parser/Digest MVP

### Purpose
Implement output parsing for OSZICAR, OUTCAR, and optional vasprun.xml.

### Files to Create

```
src/quantumvitas/engines/vasp/output_parser.py
src/quantumvitas/engines/vasp/digest.py
tests/unit/vasp/test_vasp_oszicar_parser.py
tests/unit/vasp/test_vasp_outcar_parser.py
tests/unit/vasp/test_vasp_digest.py
```

### Key Functions

#### `engines/vasp/output_parser.py`

```python
"""VASP output file parsers."""

import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass

@dataclass
class OszicarData:
    """Parsed OSZICAR data."""
    final_energy_eV: Optional[float]
    n_ionic_steps: int
    converged: bool
    energies: List[float]  # Energy per ionic step

def parse_oszicar(path: Path) -> OszicarData:
    """Parse OSZICAR for energy and convergence."""
    if not path.exists():
        return OszicarData(None, 0, False, [])
    
    content = path.read_text()
    
    # Find all F= lines (one per ionic step)
    pattern = r"^\s*\d+\s+F=\s*([\d\.\-+Ee]+)"
    energies = [float(m.group(1)) for m in re.finditer(pattern, content, re.MULTILINE)]
    
    if not energies:
        return OszicarData(None, 0, False, [])
    
    return OszicarData(
        final_energy_eV=energies[-1],
        n_ionic_steps=len(energies),
        converged=True,  # If we have energies, assume converged
        energies=energies,
    )

@dataclass
class OutcarData:
    """Parsed OUTCAR data."""
    final_energy_eV: Optional[float]
    forces: Optional[List[List[float]]]  # Per-atom forces [[fx, fy, fz], ...]
    stress_kB: Optional[List[float]]     # 6-component stress tensor
    walltime_sec: Optional[float]
    vasp_version: Optional[str]

def parse_outcar(path: Path) -> OutcarData:
    """Parse OUTCAR for detailed results."""
    if not path.exists():
        return OutcarData(None, None, None, None, None)
    
    content = path.read_text()
    
    # Energy
    energy_match = re.search(r"free\s+energy\s+TOTEN\s*=\s*([\d\.\-+Ee]+)\s*eV", content)
    energy = float(energy_match.group(1)) if energy_match else None
    
    # Walltime
    time_match = re.search(r"Elapsed time \(sec\):\s*([\d\.]+)", content)
    walltime = float(time_match.group(1)) if time_match else None
    
    # VASP version
    version_match = re.search(r"vasp\.([\d\.]+)", content)
    version = version_match.group(1) if version_match else None
    
    # Forces (simplified - just check if present)
    forces = None
    if "TOTAL-FORCE" in content:
        forces = []  # Would parse actual forces here
    
    return OutcarData(
        final_energy_eV=energy,
        forces=forces,
        stress_kB=None,  # Parse if needed
        walltime_sec=walltime,
        vasp_version=version,
    )
```

#### `engines/vasp/digest.py`

```python
"""VASP step digest computation."""

from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from .output_parser import parse_oszicar, parse_outcar

@dataclass
class VaspStepDigest:
    """Digest of a VASP step execution."""
    success: bool
    final_energy_eV: Optional[float]
    converged: bool
    n_ionic_steps: int
    walltime_sec: Optional[float]
    vasp_version: Optional[str]
    forces_max_eV_A: Optional[float]
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

def compute_vasp_step_digest(working_dir: Path) -> VaspStepDigest:
    """
    Compute digest from VASP outputs.
    
    Always produces a digest, even on parse failure.
    """
    oszicar = working_dir / "OSZICAR"
    outcar = working_dir / "OUTCAR"
    
    # Parse OSZICAR first (fastest)
    oszicar_data = parse_oszicar(oszicar)
    
    # Parse OUTCAR for details
    outcar_data = parse_outcar(outcar)
    
    # Determine success
    success = oszicar_data.converged and oszicar_data.final_energy_eV is not None
    
    return VaspStepDigest(
        success=success,
        final_energy_eV=oszicar_data.final_energy_eV or outcar_data.final_energy_eV,
        converged=oszicar_data.converged,
        n_ionic_steps=oszicar_data.n_ionic_steps,
        walltime_sec=outcar_data.walltime_sec,
        vasp_version=outcar_data.vasp_version,
        forces_max_eV_A=None,  # Would compute from outcar_data.forces
    )
```

### Unit Tests

```python
# tests/unit/vasp/test_vasp_oszicar_parser.py

import pytest
from quantumvitas.engines.vasp.output_parser import parse_oszicar

SAMPLE_OSZICAR = """       N       E                     dE             d eps       ncg     rms
DAV:   1    -0.100000000000E+02   -0.10000E+02   -0.10000E+02   100   0.100E+01
   1 F= -.10000000E+02 E0= -.10000000E+02  d E =-.100000E+02
"""

def test_parse_oszicar_energy(tmp_path):
    path = tmp_path / "OSZICAR"
    path.write_text(SAMPLE_OSZICAR)
    
    result = parse_oszicar(path)
    
    assert result.final_energy_eV == pytest.approx(-10.0, abs=0.01)
    assert result.n_ionic_steps == 1
    assert result.converged is True
```

### Acceptance Criteria
- [ ] OSZICAR parsing extracts energy correctly
- [ ] OUTCAR parsing extracts timing, version
- [ ] Digest always produces a value (no exceptions)
- [ ] Missing files handled gracefully

---

## PR6: Workflow Expansion (SCF, Bands, DOS)

### Purpose
Complete VASP workflow support with all three target workflows.

### Files to Create/Modify

```
src/quantumvitas/engines/vasp/workflows.py
src/quantumvitas/execution/vasp_handler.py (EXTEND)
tests/integration/vasp/test_vasp_scf_workflow.py
tests/integration/vasp/test_vasp_bands_workflow.py
tests/integration/vasp/test_vasp_dos_workflow.py
tests/integration/vasp/test_vasp_project_runs.py
```

### Workflow Implementations

#### `engines/vasp/workflows.py`

```python
"""VASP workflow handling."""

from pathlib import Path
from typing import Dict, Any

def setup_bands_workflow(
    scf_workdir: Path,
    bands_workdir: Path,
) -> None:
    """
    Setup bands workflow by copying CHGCAR from SCF.
    
    ICHARG=11 in INCAR tells VASP to read CHGCAR.
    """
    chgcar_src = scf_workdir / "CHGCAR"
    if not chgcar_src.exists():
        raise RuntimeError(f"SCF CHGCAR not found: {chgcar_src}")
    
    # Copy or symlink CHGCAR
    import shutil
    shutil.copy2(chgcar_src, bands_workdir / "CHGCAR")

def setup_dos_workflow(
    scf_workdir: Path,
    dos_workdir: Path,
) -> None:
    """Setup DOS workflow by copying CHGCAR from SCF."""
    setup_bands_workflow(scf_workdir, dos_workdir)  # Same logic
```

### Integration Tests (Level 3)

```python
# tests/integration/vasp/test_vasp_scf_workflow.py

import pytest
from pathlib import Path
from pymatgen.core import Structure, Lattice

from quantumvitas.engines.vasp.input_writer import materialize_vasp_inputs
from quantumvitas.engines.vasp.digest import compute_vasp_step_digest
from tests.utils.fake_vasp import fake_vasp_scf

class TestVaspScfWorkflow:
    @pytest.fixture
    def si_structure(self):
        lattice = Lattice.cubic(5.43)
        return Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
    
    @pytest.fixture
    def fake_potcar_lib(self, tmp_path):
        lib = tmp_path / "potpaw_PBE"
        si_dir = lib / "Si"
        si_dir.mkdir(parents=True)
        (si_dir / "POTCAR").write_text("FAKE POTCAR Si\n")
        return lib
    
    def test_scf_workflow_complete(self, si_structure, fake_potcar_lib, tmp_path):
        """Full SCF workflow: materialize → execute → digest."""
        workdir = tmp_path / "vasp_scf"
        params = {
            "incar": {"ENCUT": 400, "EDIFF": 1e-6, "ISMEAR": 0},
            "kpoints": {"mesh": [4, 4, 4]},
        }
        species_map = {"Si": {"potcar_variant": "Si"}}
        
        # Materialize
        inputs = materialize_vasp_inputs(
            si_structure, params, species_map, workdir, fake_potcar_lib
        )
        assert all(p.exists() for p in inputs.values())
        
        # Execute (fake)
        exit_code = fake_vasp_scf(workdir)
        assert exit_code == 0
        
        # Digest
        digest = compute_vasp_step_digest(workdir)
        assert digest.success
        assert digest.final_energy_eV is not None
```

```python
# tests/integration/vasp/test_vasp_bands_workflow.py

import pytest
from tests.utils.fake_vasp import fake_vasp_scf, fake_vasp_bands
from quantumvitas.engines.vasp.workflows import setup_bands_workflow

class TestVaspBandsWorkflow:
    def test_bands_requires_chgcar(self, tmp_path):
        """Bands workflow fails without SCF CHGCAR."""
        scf_dir = tmp_path / "scf"
        bands_dir = tmp_path / "bands"
        scf_dir.mkdir()
        bands_dir.mkdir()
        
        with pytest.raises(RuntimeError, match="CHGCAR not found"):
            setup_bands_workflow(scf_dir, bands_dir)
    
    def test_bands_workflow_complete(self, tmp_path):
        """Full bands workflow: SCF → bands."""
        scf_dir = tmp_path / "scf"
        bands_dir = tmp_path / "bands"
        scf_dir.mkdir()
        bands_dir.mkdir()
        
        # Setup fake inputs
        (scf_dir / "POSCAR").write_text("POSCAR content\n")
        (bands_dir / "POSCAR").write_text("POSCAR content\n")
        (bands_dir / "INCAR").write_text("ICHARG = 11\n")
        (bands_dir / "KPOINTS").write_text("Line-mode KPOINTS\n")
        
        # Run SCF (produces CHGCAR)
        fake_vasp_scf(scf_dir)
        assert (scf_dir / "CHGCAR").exists()
        
        # Setup bands (copies CHGCAR)
        setup_bands_workflow(scf_dir, bands_dir)
        assert (bands_dir / "CHGCAR").exists()
        
        # Run bands
        fake_vasp_bands(bands_dir)
        assert (bands_dir / "EIGENVAL").exists()
```

### Level 4: Project Tests

```python
# tests/integration/vasp/test_vasp_project_runs.py

import pytest
from pathlib import Path
from quantumvitas.api import QVService

pytestmark = pytest.mark.skipif(
    not is_vasp_available(),
    reason="VASP not available"
)

class TestVaspProjectRuns:
    """Level 4: Full project runs through API (requires real VASP)."""
    
    @pytest.fixture
    def vasp_project(self, tmp_path):
        """Create minimal VASP project."""
        project_root = QVService.init_project(tmp_path / "vasp_test_project")
        # ... setup structure, calculation, steps ...
        return project_root
    
    def test_scf_through_api(self, vasp_project):
        """Run SCF through QVService.run_step()."""
        result = QVService.run_step(
            vasp_project,
            calc_selector="si_scf",
            step_selector="scf",
        )
        assert result["success"] is True
```

### Acceptance Criteria
- [ ] SCF workflow complete (materialize → execute → digest)
- [ ] Bands workflow handles CHGCAR dependency
- [ ] DOS workflow handles CHGCAR dependency
- [ ] All three workflows pass with fake_vasp
- [ ] Project-level tests run with real VASP (local only)

---

## Local Experiment Protocol

### For Cursor Auto Validation

1. **Verify VASP Installation**
   ```bash
   # Check VASP binary
   ls ~/.qmatsuite/engines/vasp/*/bin/vasp_std
   
   # Check POTCAR library
   ls ~/.qmatsuite/engines/vasp/potpaw_*/Si/POTCAR
   ```

2. **Manual Test Run**
   ```bash
   # Create test directory
   mkdir -p /tmp/vasp_test && cd /tmp/vasp_test
   
   # Create minimal inputs (using pymatgen)
   python << 'EOF'
   from pymatgen.core import Structure, Lattice
   from pymatgen.io.vasp import Poscar, Incar, Kpoints
   
   # Structure
   lattice = Lattice.cubic(5.43)
   struct = Structure(lattice, ["Si", "Si"], [[0,0,0], [0.25,0.25,0.25]])
   Poscar(struct).write_file("POSCAR")
   
   # INCAR
   Incar({"ENCUT": 300, "EDIFF": 1e-5, "ISMEAR": 0, "SIGMA": 0.05}).write_file("INCAR")
   
   # KPOINTS
   Kpoints.gamma_automatic([2, 2, 2]).write_file("KPOINTS")
   EOF
   
   # Assemble POTCAR (manual)
   cat ~/.qmatsuite/engines/vasp/potpaw_PBE/Si/POTCAR > POTCAR
   
   # Run VASP
   ~/.qmatsuite/engines/vasp/*/bin/vasp_std
   
   # Check outputs
   cat OSZICAR
   grep "TOTEN" OUTCAR
   ```

3. **Verify Parser Outputs**
   ```python
   # After VASP run
   from quantumvitas.engines.vasp.output_parser import parse_oszicar, parse_outcar
   from pathlib import Path
   
   workdir = Path("/tmp/vasp_test")
   oszicar = parse_oszicar(workdir / "OSZICAR")
   outcar = parse_outcar(workdir / "OUTCAR")
   
   print(f"Energy: {oszicar.final_energy_eV} eV")
   print(f"Walltime: {outcar.walltime_sec} s")
   print(f"VASP version: {outcar.vasp_version}")
   ```

4. **NEVER Commit**:
   - POTCAR files (proprietary)
   - Real OUTCAR/CHGCAR/WAVECAR (large, contains licensed content)
   - Any file from `~/.qmatsuite/engines/vasp/`

---

## Summary: PR Dependency Graph

```
PR0 (docs/scaffold)
    ↓
PR1 (resolver/engine) → PR2 (step types)
    ↓                        ↓
PR3 (writers/materialize) ←──┘
    ↓
PR4 (runner/fake_vasp)
    ↓
PR5 (parsers/digest)
    ↓
PR6 (workflows: SCF → bands → DOS)
```

Each PR is independently testable and landable. Tests grow from unit to integration to project-level.

---

## Appendix: File Summary by PR

### PR1
- `src/quantumvitas/core/engines/vasp_resolver.py`
- `src/quantumvitas/engine/vasp_engine.py`
- `tests/unit/vasp/test_vasp_resolver.py`
- `tests/unit/vasp/test_vasp_engine_registration.py`

### PR2
- `src/quantumvitas/workflow/registry.py` (modify)
- `tests/unit/vasp/test_vasp_step_types.py`
- `tests/unit/vasp/test_vasp_gen_spec_bijection.py`

### PR3
- `src/quantumvitas/engines/vasp/__init__.py`
- `src/quantumvitas/engines/vasp/input_writer.py`
- `src/quantumvitas/engines/vasp/potcar_assembly.py`
- `tests/unit/vasp/test_vasp_poscar_writer.py`
- `tests/unit/vasp/test_vasp_incar_writer.py`
- `tests/unit/vasp/test_vasp_kpoints_writer.py`
- `tests/unit/vasp/test_vasp_potcar_assembly.py`
- `tests/unit/vasp/test_vasp_materialize_determinism.py`

### PR4
- `src/quantumvitas/engines/vasp/runner.py`
- `src/quantumvitas/execution/vasp_handler.py`
- `tests/utils/fake_vasp.py`
- `tests/integration/vasp/conftest.py`
- `tests/integration/vasp/test_vasp_runner_fake.py`
- `tests/integration/vasp/test_vasp_manifest_integration.py`

### PR5
- `src/quantumvitas/engines/vasp/output_parser.py`
- `src/quantumvitas/engines/vasp/digest.py`
- `tests/unit/vasp/test_vasp_oszicar_parser.py`
- `tests/unit/vasp/test_vasp_outcar_parser.py`
- `tests/unit/vasp/test_vasp_digest.py`

### PR6
- `src/quantumvitas/engines/vasp/workflows.py`
- `src/quantumvitas/execution/vasp_handler.py` (extend)
- `tests/integration/vasp/test_vasp_scf_workflow.py`
- `tests/integration/vasp/test_vasp_bands_workflow.py`
- `tests/integration/vasp/test_vasp_dos_workflow.py`
- `tests/integration/vasp/test_vasp_project_runs.py`

---

*Document generated for VASP integration planning. Follow this plan for incremental implementation with working tests at each stage.*

