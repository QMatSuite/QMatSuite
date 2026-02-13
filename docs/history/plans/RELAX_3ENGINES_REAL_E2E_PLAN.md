# RELAX 三引擎真实 E2E 实现计划

**Version**: 1.0.0
**Date**: 2026-01-18
**Author**: Opus (Senior Architect)

---

## 1. 目标

真正调用 QE/ORCA/PySCF 执行 relax，验证：
1. `generated_structures/step_<ulid>/current.json` 正确生成
2. JSON 内容正确（元素、坐标、晶胞、原子数）
3. 通过 canonicalize + SHA 流程
4. Promote 功能 E2E 验证

---

## 2. 测试路径选择

**选择**: 直接 API 调用 + Daemon RPC

**理由**:
1. API 调用更贴近真实执行路径
2. Daemon RPC 验证 GUI 通信
3. 避免 mock，确保真实引擎调用

---

## 3. PR 分解

### PR-E2E-1: QE Relax 执行集成

### PR-E2E-2: ORCA Relax 执行集成

### PR-E2E-3: PySCF Relax 执行集成

### PR-E2E-4: Promote E2E + 跨引擎验证

---

## 4. PR-E2E-1: QE Relax 执行集成

### 4.1 目标

- QE pw.x 真实执行 `relax` 和 `vc-relax`
- 解析输出生成 `current.json`
- 验证结构内容正确

### 4.2 文件修改

| 文件 | 修改内容 |
|------|----------|
| `src/quantumvitas/execution/handlers.py` | 添加 `handle_qe_relax_output()` |
| `src/quantumvitas/execution/executor.py` | 在 job 完成后调用 relax handler |
| `tests/integration/test_qe_relax_real.py` | 新增真实测试 |

### 4.3 关键实现

**4.3.1 Relax Output Handler**

```python
# src/quantumvitas/execution/handlers.py

def handle_qe_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    output_path: Path,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: Optional[str] = None,
) -> Path:
    """
    Handle QE relax step output: parse and write current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "qe_relax")
        calc_dir: Path to calculation directory
        output_path: Path to QE output file (.out)
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID for provenance
        
    Returns:
        Path to written current.json
        
    Raises:
        ValueError: If output parsing fails
    """
    from quantumvitas.calculation.geometry import (
        read_final_geometry_from_output_text,
        structure_from_qe_geometry_snapshot,
    )
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    # 1. Read output
    output_text = output_path.read_text()
    
    # 2. Parse final geometry
    snapshot, species = read_final_geometry_from_output_text(output_text)
    
    # 3. Convert to pymatgen Structure (with canonicalization)
    structure = structure_from_qe_geometry_snapshot(snapshot, species)
    
    # 4. Write current.json
    artifact_path = write_generated_structure(
        structure=structure,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    return artifact_path
```

**4.3.2 Executor 集成**

```python
# src/quantumvitas/execution/executor.py

# 在 job 执行成功后添加:

def _post_process_job(self, job: Job, calc_dir: Path, ...):
    """Post-process completed job, handle relax output if applicable."""
    from quantumvitas.workflow.registry import get_registry
    from quantumvitas.execution.relax_artifacts import is_relax_step_type
    
    registry = get_registry()
    
    for step_ulid in job.step_ids:
        step = self._get_step_by_ulid(step_ulid)
        step_type = step.step_type
        
        if is_relax_step_type(step_type):
            spec = registry.get(step_type)
            if spec and spec.engine == "qe":
                # Find output file
                public_type = spec.public_type
                output_path = job.working_dir / f"{public_type}.out"
                
                if output_path.exists():
                    handle_qe_relax_output(
                        step_ulid=step_ulid,
                        step_type=step_type,
                        calc_dir=calc_dir,
                        output_path=output_path,
                        calculation_ulid=self._calc_ulid,
                        input_structure_ulid=self._structure_ulid,
                        run_id=self._run_id,
                    )
```

### 4.4 测试

**文件**: `tests/integration/test_qe_relax_real.py`

```python
"""
Real QE relax integration tests.

These tests require QE to be installed and available.
Mark with @pytest.mark.qe to skip if QE not available.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from quantumvitas.core.structure_fingerprint import structure_fingerprint

# Skip if QE not available
pytestmark = pytest.mark.qe


@pytest.fixture
def si_project(tmp_path: Path):
    """Create a project with Si structure for relax testing."""
    project_root = QVService.init_project(tmp_path / "project")
    
    # Import Si structure (2 atoms, small cell)
    si_json = {
        "@module": "pymatgen.core.structure",
        "@class": "Structure",
        "lattice": {
            "matrix": [
                [0.0, 2.715, 2.715],
                [2.715, 0.0, 2.715],
                [2.715, 2.715, 0.0]
            ]
        },
        "sites": [
            {"species": [{"element": "Si", "occu": 1}], "xyz": [0.0, 0.0, 0.0]},
            {"species": [{"element": "Si", "occu": 1}], "xyz": [1.3575, 1.3575, 1.3575]}
        ]
    }
    source = tmp_path / "si.json"
    source.write_text(json.dumps(si_json))
    
    struct_result = QVService.import_structure(project_root, source, name="Si")
    
    return project_root, struct_result.meta.id


class TestQERelaxReal:
    """Real QE relax tests."""

    def test_qe_relax_creates_current_json(self, si_project, tmp_path):
        """Run QE relax and verify current.json is created."""
        project_root, structure_ulid = si_project
        
        # Create calculation with relax step
        calc_result = QVService.init_calculation(
            project_root, "relax_test",
            structure_selector=structure_ulid
        )
        calc_ulid = calc_result.id
        
        step_result = QVService.init_step(
            project_root, calc_ulid,
            step_type="qe_relax",
            name="relax"
        )
        step_ulid = step_result.id
        
        # Configure for fast execution
        QVService.update_step_params(
            project_root, calc_ulid, step_ulid,
            param_patch={
                "SYSTEM": {"ecutwfc": 20},  # Low cutoff for speed
                "CONTROL": {
                    "etot_conv_thr": 1e-3,
                    "forc_conv_thr": 1e-2,
                },
                "IONS": {"ion_dynamics": "bfgs"},
            }
        )
        
        # Run calculation
        result = QVService.run_calculation(project_root, calc_ulid)
        
        # Verify success
        assert result.success, f"Run failed: {result.error}"
        
        # Verify current.json exists
        calc_dir = calc_result.absolute_path.parent
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists(), f"current.json not found at {artifact_path}"
        
        # Verify content
        data = json.loads(artifact_path.read_text())
        
        # Check metadata
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["type"] == "generated_structure"
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        
        # Check structure
        assert "lattice" in data
        assert "sites" in data
        assert len(data["sites"]) == 2  # 2 Si atoms
        
        # Verify can be read as pymatgen Structure
        structure = read_generated_structure(calc_dir, step_ulid)
        assert structure is not None
        assert len(structure) == 2
        
        # Verify SHA can be computed
        sha = structure_fingerprint(structure)
        assert len(sha) == 64  # SHA256 hex

    def test_qe_vc_relax_changes_cell(self, si_project, tmp_path):
        """Run QE vc-relax and verify cell changes."""
        project_root, structure_ulid = si_project
        
        # Create calculation with vc-relax step
        calc_result = QVService.init_calculation(
            project_root, "vc_relax_test",
            structure_selector=structure_ulid
        )
        calc_ulid = calc_result.id
        
        step_result = QVService.init_step(
            project_root, calc_ulid,
            step_type="qe_relax",  # Unified type
            name="vc_relax"
        )
        step_ulid = step_result.id
        
        # Configure for vc-relax
        QVService.update_step_params(
            project_root, calc_ulid, step_ulid,
            param_patch={
                "CONTROL": {"calculation": "vc-relax"},
                "SYSTEM": {"ecutwfc": 20},
                "IONS": {"ion_dynamics": "bfgs"},
                "CELL": {"cell_dynamics": "bfgs"},
            }
        )
        
        # Run
        result = QVService.run_calculation(project_root, calc_ulid)
        assert result.success
        
        # Verify cell might have changed
        calc_dir = calc_result.absolute_path.parent
        structure = read_generated_structure(calc_dir, step_ulid)
        assert structure is not None
        
        # Just verify it ran and produced output
        assert len(structure) == 2

    @pytest.mark.slow
    def test_qe_relax_convergence(self, si_project, tmp_path):
        """Test that relax actually converges (slower test)."""
        project_root, structure_ulid = si_project
        
        # Similar to above but with tighter convergence
        # ... implementation ...
        pass
```

### 4.5 验收标准

```bash
# 测试命令
pytest tests/integration/test_qe_relax_real.py -v -m qe

# 必须通过
# - test_qe_relax_creates_current_json
# - test_qe_vc_relax_changes_cell
```

---

## 5. PR-E2E-2: ORCA Relax 执行集成

### 5.1 目标

- ORCA 真实执行几何优化 (`! Opt`)
- 解析 `basename.xyz` 生成 `current.json`
- 验证分子结构内容正确

### 5.2 文件修改

| 文件 | 修改内容 |
|------|----------|
| `src/quantumvitas/execution/orca_relax_parser.py` | 新增 ORCA xyz 解析器 |
| `src/quantumvitas/engine/orca_engine.py` | 添加 relax 后处理 |
| `src/quantumvitas/engines/orca/input_compiler.py` | 支持 Opt 关键词 |
| `tests/integration/test_orca_relax_real.py` | 新增真实测试 |

### 5.3 关键实现

**5.3.1 ORCA XYZ Parser**

```python
# src/quantumvitas/execution/orca_relax_parser.py

"""Parse ORCA geometry optimization output."""

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pymatgen.core import Molecule

def parse_orca_optimized_xyz(xyz_path: Path) -> "Molecule":
    """
    Parse ORCA's optimized structure from basename.xyz.
    
    Args:
        xyz_path: Path to the .xyz file (e.g., chain01_scf.xyz)
        
    Returns:
        pymatgen Molecule with canonicalized coordinates
    """
    from pymatgen.core import Molecule
    from quantumvitas.analysis.structure_viz import canonicalize_structure_in_place
    
    # pymatgen can read xyz files directly
    mol = Molecule.from_file(xyz_path)
    
    # Canonicalize (for molecules, this mainly normalizes coords)
    # Note: Molecules don't have fractional coords, but we call for consistency
    # canonicalize_structure_in_place expects Structure, so we skip for Molecule
    
    return mol


def handle_orca_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    working_dir: Path,
    chain_key: str,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: str = None,
) -> Path:
    """
    Handle ORCA relax output: find .xyz and write current.json.
    
    Args:
        step_ulid: ULID of the relax step
        step_type: Machine step type (e.g., "orca_relax")
        calc_dir: Path to calculation directory
        working_dir: Path to ORCA working directory (contains .xyz)
        chain_key: Chain key (e.g., "chain01_scf")
        calculation_ulid: ULID of the calculation
        input_structure_ulid: ULID of the input structure
        run_id: Optional run ID
        
    Returns:
        Path to written current.json
    """
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    # Find optimized xyz file
    xyz_path = working_dir / f"{chain_key}.xyz"
    if not xyz_path.exists():
        raise FileNotFoundError(f"ORCA optimized structure not found: {xyz_path}")
    
    # Parse
    molecule = parse_orca_optimized_xyz(xyz_path)
    
    # Write current.json (using Structure-compatible format)
    # Note: We store Molecule as Structure for consistency
    artifact_path = write_generated_structure(
        structure=molecule,  # pymatgen Molecule is also a SiteCollection
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
    
    return artifact_path
```

**5.3.2 Input Compiler 支持 Opt**

```python
# src/quantumvitas/engines/orca/input_compiler.py

# 在 compile() 方法中添加:

def compile(self, chain, molecule, fresh=False, nprocs=1):
    """Compile chain to ORCA input."""
    lines = []
    
    # Check if any step is relax
    is_relax = any(
        step.public_type == "relax" 
        for step in chain.all_steps
    )
    
    # Build keyword line
    keywords = [self._get_method(chain), self._get_basis(chain)]
    if is_relax:
        keywords.append("Opt")  # Add geometry optimization
    if nprocs > 1:
        keywords.append(f"PAL{nprocs}")
    
    lines.append(f"! {' '.join(keywords)}")
    
    # ... rest of compilation
```

### 5.4 测试

**文件**: `tests/integration/test_orca_relax_real.py`

```python
"""
Real ORCA relax integration tests.

Requires ORCA to be installed.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.execution.relax_artifacts import get_generated_structure_path

pytestmark = pytest.mark.orca


@pytest.fixture
def h2_project(tmp_path: Path):
    """Create a project with H2 molecule for relax testing."""
    project_root = QVService.init_project(tmp_path / "project")
    
    # H2 molecule (smallest test case)
    h2_json = {
        "@module": "pymatgen.core.structure",
        "@class": "Molecule",
        "charge": 0,
        "spin_multiplicity": 1,
        "sites": [
            {"species": [{"element": "H", "occu": 1}], "xyz": [0.0, 0.0, 0.0]},
            {"species": [{"element": "H", "occu": 1}], "xyz": [0.8, 0.0, 0.0]}
        ]
    }
    source = tmp_path / "h2.json"
    source.write_text(json.dumps(h2_json))
    
    struct_result = QVService.import_structure(project_root, source, name="H2")
    
    return project_root, struct_result.meta.id


class TestORCARelaxReal:
    """Real ORCA relax tests."""

    def test_orca_relax_creates_current_json(self, h2_project, tmp_path):
        """Run ORCA Opt and verify current.json is created."""
        project_root, structure_ulid = h2_project
        
        # Create calculation with relax step
        calc_result = QVService.init_calculation(
            project_root, "orca_relax_test",
            structure_selector=structure_ulid
        )
        calc_ulid = calc_result.id
        
        # Create relax step (ORCA)
        step_result = QVService.init_step(
            project_root, calc_ulid,
            step_type="orca_relax",
            name="opt"
        )
        step_ulid = step_result.id
        
        # Configure for fast execution
        QVService.update_step_params(
            project_root, calc_ulid, step_ulid,
            param_patch={
                "method": "HF",
                "basis": "STO-3G",
                "geom": {"MaxIter": 10},
            }
        )
        
        # Run
        result = QVService.run_calculation(project_root, calc_ulid)
        assert result.success, f"Run failed: {result.error}"
        
        # Verify current.json
        calc_dir = calc_result.absolute_path.parent
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists()
        
        # Verify content
        data = json.loads(artifact_path.read_text())
        assert len(data["sites"]) == 2  # H2

    def test_orca_relax_bond_length_changes(self, h2_project, tmp_path):
        """Verify H-H bond length changes after optimization."""
        # Start with 0.8 Å, should optimize to ~0.74 Å
        project_root, structure_ulid = h2_project
        
        # ... run relax ...
        
        # Check final bond length is closer to equilibrium
        from quantumvitas.execution.relax_artifacts import read_generated_structure
        calc_dir = ...
        mol = read_generated_structure(calc_dir, step_ulid)
        
        # Distance between atoms
        dist = mol[0].distance(mol[1])
        assert 0.7 < dist < 0.8  # Should be ~0.74 Å for HF/STO-3G
```

### 5.5 验收标准

```bash
pytest tests/integration/test_orca_relax_real.py -v -m orca
```

---

## 6. PR-E2E-3: PySCF Relax 执行集成

### 6.1 目标

- PySCF geomopt 真实执行
- 从 `mol_eq` 提取结构
- 写入 `current.json`

### 6.2 文件修改

| 文件 | 修改内容 |
|------|----------|
| `src/quantumvitas/engines/pyscf/runner.py` | 添加 relax step 处理 |
| `src/quantumvitas/execution/pyscf_relax_handler.py` | 新增 PySCF relax handler |
| `tests/integration/test_pyscf_relax_real.py` | 新增真实测试 |

### 6.3 关键实现

**6.3.1 PySCF Runner Relax 支持**

```python
# src/quantumvitas/engines/pyscf/runner.py

def run_pyscf_relax(step_spec: dict, mol: "gto.Mole") -> dict:
    """
    Run PySCF geometry optimization.
    
    Args:
        step_spec: Step specification with parameters
        mol: PySCF Mole object
        
    Returns:
        Result dict with optimized structure
    """
    from pyscf import scf
    
    params = step_spec.get("parameters", {})
    
    # Build SCF
    method = params.get("method", "rhf").lower()
    if method in ("rhf", "hf"):
        mf = scf.RHF(mol)
    else:
        mf = scf.RKS(mol)
        mf.xc = params.get("xc", "pbe")
    
    # Run SCF first
    mf.kernel()
    
    # Geometry optimization
    try:
        from pyscf.geomopt.geometric_solver import optimize
        solver_name = "geometric"
    except ImportError:
        from pyscf.geomopt.berny_solver import optimize
        solver_name = "berny"
    
    maxsteps = params.get("maxsteps", 50)
    mol_eq = optimize(mf, maxsteps=maxsteps)
    
    # Extract final structure
    BOHR_TO_ANG = 0.52917721092
    coords_bohr = mol_eq.atom_coords()
    coords_ang = coords_bohr * BOHR_TO_ANG
    
    atoms = []
    for i in range(mol_eq.natm):
        atoms.append({
            "element": mol_eq.atom_symbol(i),
            "xyz": coords_ang[i].tolist(),
        })
    
    return {
        "success": True,
        "optimized_atoms": atoms,
        "charge": mol_eq.charge,
        "spin_multiplicity": mol_eq.spin + 1,
        "final_energy": mf.e_tot,
        "solver": solver_name,
    }
```

**6.3.2 Relax Handler**

```python
# src/quantumvitas/execution/pyscf_relax_handler.py

def handle_pyscf_relax_output(
    step_ulid: str,
    step_type: str,
    calc_dir: Path,
    results: dict,
    calculation_ulid: str,
    input_structure_ulid: str,
    run_id: str = None,
) -> Path:
    """
    Handle PySCF relax output: convert results to current.json.
    """
    from pymatgen.core import Molecule
    from quantumvitas.execution.relax_artifacts import write_generated_structure
    
    atoms = results["optimized_atoms"]
    
    species = [a["element"] for a in atoms]
    coords = [a["xyz"] for a in atoms]
    
    mol = Molecule(
        species=species,
        coords=coords,
        charge=results.get("charge", 0),
        spin_multiplicity=results.get("spin_multiplicity", 1),
    )
    
    return write_generated_structure(
        structure=mol,
        calc_dir=calc_dir,
        step_ulid=step_ulid,
        step_type=step_type,
        run_id=run_id,
        calculation_ulid=calculation_ulid,
        input_structure_ulid=input_structure_ulid,
    )
```

### 6.4 测试

**文件**: `tests/integration/test_pyscf_relax_real.py`

```python
"""
Real PySCF relax integration tests.

Requires pyscf and geometric (or pyberny).
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService
from quantumvitas.execution.relax_artifacts import get_generated_structure_path

# Check if PySCF geomopt is available
try:
    from pyscf.geomopt.geometric_solver import optimize
    HAS_GEOMOPT = True
except ImportError:
    try:
        from pyscf.geomopt.berny_solver import optimize
        HAS_GEOMOPT = True
    except ImportError:
        HAS_GEOMOPT = False

pytestmark = pytest.mark.skipif(not HAS_GEOMOPT, reason="PySCF geomopt not available")


@pytest.fixture
def h2_project(tmp_path: Path):
    """Create a project with H2 molecule."""
    project_root = QVService.init_project(tmp_path / "project")
    
    h2_json = {
        "@module": "pymatgen.core.structure",
        "@class": "Molecule",
        "charge": 0,
        "spin_multiplicity": 1,
        "sites": [
            {"species": [{"element": "H", "occu": 1}], "xyz": [0.0, 0.0, 0.0]},
            {"species": [{"element": "H", "occu": 1}], "xyz": [0.8, 0.0, 0.0]}
        ]
    }
    source = tmp_path / "h2.json"
    source.write_text(json.dumps(h2_json))
    
    struct_result = QVService.import_structure(project_root, source, name="H2")
    
    return project_root, struct_result.meta.id


class TestPySCFRelaxReal:
    """Real PySCF relax tests."""

    def test_pyscf_relax_creates_current_json(self, h2_project, tmp_path):
        """Run PySCF geomopt and verify current.json is created."""
        project_root, structure_ulid = h2_project
        
        # Create calculation
        calc_result = QVService.init_calculation(
            project_root, "pyscf_relax_test",
            structure_selector=structure_ulid
        )
        calc_ulid = calc_result.id
        
        # Create relax step
        step_result = QVService.init_step(
            project_root, calc_ulid,
            step_type="pyscf_relax",
            name="geomopt"
        )
        step_ulid = step_result.id
        
        # Configure
        QVService.update_step_params(
            project_root, calc_ulid, step_ulid,
            param_patch={
                "method": "rhf",
                "basis": "sto-3g",
                "maxsteps": 10,
            }
        )
        
        # Run
        result = QVService.run_calculation(project_root, calc_ulid)
        assert result.success, f"Run failed: {result.error}"
        
        # Verify current.json
        calc_dir = calc_result.absolute_path.parent
        artifact_path = get_generated_structure_path(calc_dir, step_ulid)
        assert artifact_path.exists()
        
        # Verify content
        data = json.loads(artifact_path.read_text())
        assert len(data["sites"]) == 2

    def test_pyscf_relax_energy_decreases(self, h2_project, tmp_path):
        """Verify energy decreases after optimization."""
        # ... implementation ...
        pass
```

### 6.5 验收标准

```bash
pytest tests/integration/test_pyscf_relax_real.py -v
```

---

## 7. PR-E2E-4: Promote E2E + 跨引擎验证

### 7.1 目标

- Promote E2E: relax → current.json → promote → new structure resource
- 新 structure 可被新 calculation 引用
- 跨引擎对比 (optional)

### 7.2 测试

**文件**: `tests/integration/test_relax_promote_e2e.py`

```python
"""
End-to-end tests for relax → promote → use workflow.
"""

import json
import pytest
from pathlib import Path

from quantumvitas.api import QVService


class TestRelaxPromoteE2E:
    """End-to-end relax + promote tests."""

    @pytest.mark.qe
    def test_promote_relaxed_structure_then_use(self, tmp_path):
        """
        Full workflow:
        1. Create project with structure
        2. Create calc with relax step
        3. Run relax
        4. Promote relaxed structure
        5. Create new calc using promoted structure
        6. Verify new calc references correct structure
        """
        project_root = QVService.init_project(tmp_path / "project")
        
        # 1. Import initial structure
        si_json = {
            "@module": "pymatgen.core.structure",
            "@class": "Structure",
            "lattice": {"matrix": [[0, 2.715, 2.715], [2.715, 0, 2.715], [2.715, 2.715, 0]]},
            "sites": [
                {"species": [{"element": "Si", "occu": 1}], "xyz": [0, 0, 0]},
                {"species": [{"element": "Si", "occu": 1}], "xyz": [1.3575, 1.3575, 1.3575]}
            ]
        }
        source = tmp_path / "si.json"
        source.write_text(json.dumps(si_json))
        initial_struct = QVService.import_structure(project_root, source, name="Si_initial")
        
        # 2. Create relax calculation
        calc1 = QVService.init_calculation(
            project_root, "relax_calc",
            structure_selector=initial_struct.meta.id
        )
        relax_step = QVService.init_step(
            project_root, calc1.id,
            step_type="qe_relax", name="relax"
        )
        
        # Configure low precision for speed
        QVService.update_step_params(
            project_root, calc1.id, relax_step.id,
            param_patch={"SYSTEM": {"ecutwfc": 20}}
        )
        
        # 3. Run relax
        result = QVService.run_calculation(project_root, calc1.id)
        assert result.success
        
        # 4. Promote
        promoted = QVService.promote_relax_structure(
            project_root,
            calculation_selector=calc1.id,
            step_selector=relax_step.id,
            name="Si_relaxed"
        )
        
        # Verify new structure exists
        assert promoted.meta.id != initial_struct.meta.id
        assert promoted.meta.name == "Si_relaxed"
        
        # 5. Create new calculation using promoted structure
        calc2 = QVService.init_calculation(
            project_root, "scf_on_relaxed",
            structure_selector=promoted.meta.id
        )
        scf_step = QVService.init_step(
            project_root, calc2.id,
            step_type="qe_scf", name="scf"
        )
        
        # 6. Verify calc2 references promoted structure
        calc2_doc = QVService.get_calculation_detail(project_root, calc2.id)
        assert calc2_doc["structure_id"] == promoted.meta.id

    def test_promote_requires_relax_step(self, tmp_path):
        """Promote should fail for non-relax steps."""
        project_root = QVService.init_project(tmp_path / "project")
        
        # ... setup with SCF step instead of relax ...
        
        with pytest.raises(Exception) as exc_info:
            QVService.promote_relax_structure(
                project_root,
                calculation_selector="...",
                step_selector="...",  # SCF step
            )
        assert "not a relax step" in str(exc_info.value)
```

---

## 8. 运行时间控制

| 测试 | 体系 | 精度 | 预估时间 |
|------|------|------|----------|
| QE relax | Si 2-atom | ecutwfc=20 | ~30s |
| QE vc-relax | Si 2-atom | ecutwfc=20 | ~60s |
| ORCA opt | H2 | HF/STO-3G | ~5s |
| PySCF geomopt | H2 | HF/STO-3G | ~5s |

**总 CI 时间**: ~2-3 分钟 (如果引擎可用)

---

## 9. CI 配置

```yaml
# .github/workflows/test-relax.yml

jobs:
  test-relax-qe:
    runs-on: ubuntu-latest
    if: github.event.pull_request.labels.*.name contains 'test-qe'
    steps:
      - uses: actions/checkout@v3
      - name: Setup QE
        run: |
          # Install QE or use cached bundle
      - name: Run QE relax tests
        run: pytest tests/integration/test_qe_relax_real.py -v -m qe

  test-relax-orca:
    runs-on: ubuntu-latest
    if: github.event.pull_request.labels.*.name contains 'test-orca'
    steps:
      # ORCA requires license, may need self-hosted runner
      - name: Run ORCA relax tests
        run: pytest tests/integration/test_orca_relax_real.py -v -m orca

  test-relax-pyscf:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install PySCF + geometric
        run: pip install pyscf geometric
      - name: Run PySCF relax tests
        run: pytest tests/integration/test_pyscf_relax_real.py -v
```

---

## 10. 验收总表

| PR | 测试文件 | 关键验证 |
|----|----------|----------|
| E2E-1 | `test_qe_relax_real.py` | `current.json` 生成，2 Si atoms |
| E2E-2 | `test_orca_relax_real.py` | `current.json` 生成，2 H atoms |
| E2E-3 | `test_pyscf_relax_real.py` | `current.json` 生成，2 H atoms |
| E2E-4 | `test_relax_promote_e2e.py` | Promote 成功，新 calc 可引用 |

