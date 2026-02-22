# RELAX Implementation Plan

**Date**: 2026-01-18
**Status**: IN PROGRESS

---

## PR Overview (给 Cursor Auto 的执行顺序)

| PR | 名称 | 状态 | 测试命令 |
|----|------|------|----------|
| PR1 | Registry Updates + Type Foundation | ✅ 完成 | `pytest tests/unit/test_step_type_mapping.py -v` |
| PR2 | QC Topology Verification | ✅ 完成 | `pytest tests/unit/execution/test_qc_topology.py -v` |
| PR3 | Generated Structures Helper Functions | ✅ 完成 | `pytest tests/unit/execution/test_relax_artifacts.py -v` |
| PR3b | Executor Integration | ✅ 完成 | `pytest tests/integration/test_relax_execution.py -v` |
| PR4 | Missing Artifact Hard Error + Manifest | ✅ 完成 | `pytest tests/unit/test_manifest_effective_structure.py -v` |
| PR5 | Promote API + Daemon RPC | ✅ 完成 | `pytest tests/daemon/test_promote_relax_structure.py -v` |
| PR6 | Integration Tests + Documentation | ✅ 完成 | `pytest tests/integration/test_relax_e2e.py -v` |
| PR7 | ORCA Relax Parser | ✅ 完成 | `pytest tests/unit/execution/test_orca_relax_parser.py -v` |
| PR8 | PySCF Relax Handler | ✅ 完成 | `pytest tests/unit/execution/test_pyscf_relax_handler.py -v` |
| PR9 | Real QE Relax Test | ✅ 完成 | `pytest tests/integration/test_qe_relax_real.py -v` |
| **PR10** | **Real ORCA Relax Test** | ⏳ 待做 | `pytest tests/integration/test_orca_relax_real.py -v` |
| **PR11** | **Real PySCF Relax Test** | ⏳ 待做 | `pytest tests/integration/test_pyscf_relax_real.py -v` |
| PR12 | Promote E2E Test | ⏳ 待做 | `pytest tests/integration/test_relax_promote_e2e.py -v` |

**执行顺序**: PR1 → ... → PR9 → PR10 → PR11 → PR12

**当前进度**: PR1-PR9 完成，PR10-PR12 待做

---

## PR 1: Registry Updates + Type Foundation (1-2 days) ✅ 完成

**目的**: 为 relax 步骤添加类型基础，不改变运行时行为

**改动文件**:
- `src/qmatsuite/workflow/registry.py`
- `src/qmatsuite/engine/qc_engine_base.py`
- `tests/unit/test_step_type_mapping.py`

**关键实现**:

```python
# registry.py
@dataclass(frozen=True)
class StepTypeSpec:
    # ... existing fields ...
    is_structure_transform: bool = False  # NEW: True for relax/vc-relax

# Update existing specs
"qe_relax": StepTypeSpec(
    id="relax",
    machine_type="qe_relax",
    public_type="relax",
    engine="qe",
    executable="pw.x",
    description="Atomic relaxation (optimize positions, fixed cell)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,  # CHANGED from True
    is_structure_transform=True,     # NEW
),
"qe_vc_relax": StepTypeSpec(
    id="vc-relax",
    machine_type="qe_vc_relax",
    public_type="vc-relax",
    engine="qe",
    executable="pw.x",
    description="Variable-cell relaxation (optimize positions and cell)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,  # CHANGED from True
    is_structure_transform=True,     # NEW
),

# qc_engine_base.py
RELAX_STEP_TYPES = {"relax", "vc-relax", "opt", "geomopt"}  # NEW
```

**测试**:
- 现有 registry 测试通过
- 新增: `test_relax_step_types_have_is_structure_transform_true`
- 新增: `test_relax_step_types_do_not_produce_charge_density`

**风险点**:
- 修改 `produces_charge_density` 可能影响现有依赖检查 → 验证无现有代码依赖此字段判断 relax

**测试命令**: `pytest tests/unit/test_step_type_mapping.py -v`

---

## PR 2: QC Topology Verification (2-3 days) ✅ 完成

**目的**: 在 QC run 前验证拓扑，阻止非法 relax 位置

**改动文件**:
- `src/qmatsuite/execution/recipes.py` (ORCARecipe, PySCFRecipe)
- `src/qmatsuite/execution/executor.py` (添加 verify 调用)
- `tests/unit/execution/test_qc_topology.py` (新建)

**关键实现**:

```python
# recipes.py - 添加到 ORCARecipe 和 PySCFRecipe

class TopologyError(Exception):
    """Raised when step topology violates QC chain rules."""
    pass


def verify_qc_topology(steps: List["Step"], registry) -> None:
    """
    Verify QC topology before execution.
    
    Rules:
    - Relax steps are standalone (length=1 chains)
    - Non-relax, non-SCF steps must trace to SCF root without crossing relax
    
    Raises:
        TopologyError: If topology is invalid
    """
    for i, step in enumerate(steps):
        step_type = step.public_type or step.step_type
        
        if step_type in RELAX_STEP_TYPES:
            continue  # Relax is standalone, always valid
        
        if step_type in SCF_ROOT_TYPES:
            continue  # SCF root starts new chain, always valid
        
        # Non-relax, non-SCF: must find SCF ancestor without intervening relax
        found_scf = False
        for j in range(i - 1, -1, -1):
            ancestor_type = steps[j].public_type or steps[j].step_type
            if ancestor_type in RELAX_STEP_TYPES:
                raise TopologyError(
                    f"TOPOLOGY_ERROR: Step '{step.name}' (index {i}) cannot trace to SCF root. "
                    f"A relax step at index {j} blocks the dependency chain. "
                    "Relax steps are not electronic state providers; they must be in standalone chains."
                )
            if ancestor_type in SCF_ROOT_TYPES:
                found_scf = True
                break
        
        if not found_scf:
            raise TopologyError(
                f"TOPOLOGY_ERROR: Step '{step.name}' (index {i}) requires SCF root but none found. "
                "Add an SCF step before this step."
            )


# ORCARecipe.materialize() - 添加在开头
def materialize(self, steps, calc_raw_dir, step_shas=None):
    verify_qc_topology(steps, get_registry())
    # ... existing code ...
```

**测试**:
- `test_qc_topo_verify_*` (见测试矩阵 §3.1)
- 至少 8 个拓扑验证测试

**风险点**:
- 可能阻断现有用户的非法拓扑 workflow → 这是预期行为，需在 release notes 说明

**测试命令**: `pytest tests/unit/execution/test_qc_topology.py -v`

---

## PR 3: Generated Structures Helper Functions (2 days)

**目的**: 添加 relax 输出结构写入的 helper 函数（纯函数，不改变 executor 主逻辑）

**注意**: 这是一个 **桩 PR**，只添加工具函数和测试，不改变运行时行为。这样可以锁定接口，让后续 PR 直接调用。

**改动文件**:
- `src/qmatsuite/execution/relax_artifacts.py` (新建)
- `tests/unit/execution/test_relax_artifacts.py` (新建)

### Step 3.1: 创建 relax_artifacts.py

在 `src/qmatsuite/execution/` 下新建 `relax_artifacts.py`：

```python
"""
Relax artifacts: Generated structure write/read utilities.

This module provides utilities for writing and reading generated structures
from relax steps. These are artifacts (not ULID resources) stored at:
  calculations/<calc>/generated_structures/step_<relax_ulid>/current.json
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from pymatgen.core import Structure as PMGStructure

logger = logging.getLogger(__name__)


def get_generated_structure_path(calc_dir: Path, step_ulid: str) -> Path:
    """
    Get the canonical path for a relax step's generated structure.
    
    Args:
        calc_dir: Path to calculation directory (parent of calculation.yaml)
        step_ulid: ULID of the relax step
        
    Returns:
        Path to current.json (may not exist)
    """
    return calc_dir / "generated_structures" / f"step_{step_ulid}" / "current.json"


def write_generated_structure(
    structure: "PMGStructure",
    calc_dir: Path,
    step_ulid: str,
    step_type: str,
    run_id: Optional[str] = None,
    calculation_ulid: Optional[str] = None,
    input_structure_ulid: Optional[str] = None,
) -> Path:
    """
    Write a relaxed structure to generated_structures directory.
    
    Args:
        structure: pymatgen Structure to write
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        step_type: Step type (e.g., "qe_relax", "qe_vc_relax")
        run_id: Optional run ID for provenance
        calculation_ulid: Optional calculation ULID for provenance
        input_structure_ulid: Optional input structure ULID for provenance
        
    Returns:
        Path to written current.json
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build structure dict with metadata
    structure_dict = structure.as_dict()
    structure_dict["__qms_meta__"] = {
        "type": "generated_structure",
        "source_step_ulid": step_ulid,
        "source_run_id": run_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provenance": {
            "method": step_type,
            "input_structure_ulid": input_structure_ulid,
            "calculation_ulid": calculation_ulid,
        },
    }
    
    artifact_path.write_text(json.dumps(structure_dict, indent=2))
    logger.info(f"[RELAX_ARTIFACTS] Wrote generated structure to {artifact_path}")
    
    return artifact_path


def read_generated_structure(
    calc_dir: Path,
    step_ulid: str,
) -> Optional["PMGStructure"]:
    """
    Read a generated structure from current.json.
    
    Args:
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        
    Returns:
        pymatgen Structure, or None if file doesn't exist
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if not artifact_path.exists():
        return None
    
    structure_dict = json.loads(artifact_path.read_text())
    # Remove our metadata before parsing
    structure_dict.pop("__qms_meta__", None)
    
    from pymatgen.core import Structure
    return Structure.from_dict(structure_dict)


def clean_generated_structure(calc_dir: Path, step_ulid: str) -> bool:
    """
    Delete a generated structure's current.json.
    
    Args:
        calc_dir: Path to calculation directory
        step_ulid: ULID of the relax step
        
    Returns:
        True if file was deleted, False if it didn't exist
    """
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if artifact_path.exists():
        artifact_path.unlink()
        logger.info(f"[RELAX_ARTIFACTS] Cleaned {artifact_path}")
        return True
    return False


def is_relax_step_type(step_type: str) -> bool:
    """
    Check if a step type is a relax type.
    
    Uses registry lookup to check is_structure_transform flag.
    """
    from qmatsuite.workflow.registry import get_registry
    
    registry = get_registry()
    spec = registry.get(step_type)
    if spec is None:
        return False
    return getattr(spec, 'is_structure_transform', False)
```

### Step 3.2: 创建测试文件

在 `tests/unit/execution/` 下新建 `test_relax_artifacts.py`：

```python
"""
Unit tests for relax artifact utilities.
"""

import json
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from qmatsuite.execution.relax_artifacts import (
    get_generated_structure_path,
    write_generated_structure,
    read_generated_structure,
    clean_generated_structure,
    is_relax_step_type,
)


class TestGeneratedStructurePath:
    """Test path generation for generated structures."""

    def test_path_format(self, tmp_path):
        """Path follows the canonical format."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01ABC123XYZ"
        
        path = get_generated_structure_path(calc_dir, step_ulid)
        
        assert path == calc_dir / "generated_structures" / f"step_{step_ulid}" / "current.json"


class TestWriteGeneratedStructure:
    """Test writing generated structures."""

    def test_write_creates_file(self, tmp_path):
        """Writing creates current.json with correct structure."""
        # Create a mock pymatgen structure
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.5, 0.5, 0.5]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01TESTULID123456789012"
        
        result_path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
            run_id="run001",
            calculation_ulid="calc001",
            input_structure_ulid="struct001",
        )
        
        assert result_path.exists()
        
        # Check content
        data = json.loads(result_path.read_text())
        assert "__qms_meta__" in data
        assert data["__qms_meta__"]["type"] == "generated_structure"
        assert data["__qms_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qms_meta__"]["provenance"]["method"] == "qe_relax"

    def test_write_creates_parent_dirs(self, tmp_path):
        """Writing creates parent directories if needed."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        # calc_dir doesn't exist yet
        calc_dir = tmp_path / "nonexistent" / "calc"
        step_ulid = "01TESTULID"
        
        result_path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_vc_relax",
        )
        
        assert result_path.exists()


class TestReadGeneratedStructure:
    """Test reading generated structures."""

    def test_read_existing_file(self, tmp_path):
        """Reading an existing file returns a Structure."""
        from pymatgen.core import Structure, Lattice
        
        # Write a structure first
        lattice = Lattice.cubic(5.43)
        original = Structure(lattice, ["Si", "Si"], [[0, 0, 0], [0.25, 0.25, 0.25]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01READTEST"
        
        write_generated_structure(
            structure=original,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
        )
        
        # Read it back
        loaded = read_generated_structure(calc_dir, step_ulid)
        
        assert loaded is not None
        assert len(loaded) == 2
        assert loaded.lattice.a == pytest.approx(5.43)

    def test_read_nonexistent_returns_none(self, tmp_path):
        """Reading a nonexistent file returns None."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01NONEXISTENT"
        
        result = read_generated_structure(calc_dir, step_ulid)
        
        assert result is None


class TestCleanGeneratedStructure:
    """Test cleaning generated structures."""

    def test_clean_existing_file(self, tmp_path):
        """Cleaning an existing file deletes it and returns True."""
        from pymatgen.core import Structure, Lattice
        
        lattice = Lattice.cubic(5.0)
        structure = Structure(lattice, ["Si"], [[0, 0, 0]])
        
        calc_dir = tmp_path / "calc"
        step_ulid = "01CLEANTEST"
        
        path = write_generated_structure(
            structure=structure,
            calc_dir=calc_dir,
            step_ulid=step_ulid,
            step_type="qe_relax",
        )
        
        assert path.exists()
        
        result = clean_generated_structure(calc_dir, step_ulid)
        
        assert result is True
        assert not path.exists()

    def test_clean_nonexistent_returns_false(self, tmp_path):
        """Cleaning a nonexistent file returns False."""
        calc_dir = tmp_path / "calc"
        step_ulid = "01NONEXISTENT"
        
        result = clean_generated_structure(calc_dir, step_ulid)
        
        assert result is False


class TestIsRelaxStepType:
    """Test relax step type detection."""

    def test_qe_relax_is_relax(self):
        """qe_relax is detected as relax."""
        assert is_relax_step_type("qe_relax") is True

    def test_qe_vc_relax_is_relax(self):
        """qe_vc_relax is detected as relax."""
        assert is_relax_step_type("qe_vc_relax") is True

    def test_qe_scf_is_not_relax(self):
        """qe_scf is not a relax step."""
        assert is_relax_step_type("qe_scf") is False

    def test_unknown_type_is_not_relax(self):
        """Unknown step type is not relax."""
        assert is_relax_step_type("unknown_type") is False
```

**测试命令**: `pytest tests/unit/execution/test_relax_artifacts.py -v`

**验证**:
- 所有 12 个测试通过
- `is_relax_step_type` 正确识别 qe_relax 和 qe_vc_relax

---

## PR 3b: Executor Integration ✅ 完成

**目的**: 将 relax_artifacts 集成到 executor 的执行流程中

**改动文件**:
- `src/qmatsuite/execution/executor.py` - 在 job 循环中调用 relax_artifacts 函数
- `tests/integration/test_relax_execution.py` (新建)

**关键实现**:

已在 `executor.py` 中实现：

1. **Pre-clean**: `_pre_clean_relax_steps()` 方法
   - 在 job 执行前调用
   - 删除本 job 覆盖的所有 relax steps 的 `current.json`
   - 确保 `current.json` 存在意味着本次运行成功

2. **Post-process**: `_post_process_relax_steps()` 方法
   - 在 job 成功后调用
   - 支持 QE, ORCA, PySCF 三种引擎
   - 解析输出文件并写入 `current.json`

3. **集成点**:
   - 在 `execute()` 方法的 job 循环中：
     - 执行前：`self._pre_clean_relax_steps(job, calculation)`
     - 执行后（成功时）：`self._post_process_relax_steps(job, job_result, calculation, context)`

**测试**:
- `tests/integration/test_relax_execution.py` 包含 4 个测试：
  - `test_executor_pre_clean_before_job_execution`: 验证 pre-clean 功能
  - `test_executor_post_process_after_successful_job`: 验证 post-process 功能
  - `test_executor_post_process_only_on_success`: 验证失败时不 post-process
  - `test_executor_pre_clean_only_affects_job_steps`: 验证 pre-clean 只影响当前 job 的 steps

**测试命令**: `pytest tests/integration/test_relax_execution.py -v`

---

## PR 4: Missing Artifact Hard Error + Manifest Enhancement (2 days)

**目的**: 实现缺失 current.json 的硬错误，manifest 添加 effective_structure_sha

**改动文件**:
- `src/qmatsuite/execution/executor.py`
- `src/qmatsuite/calculation/manifest.py`
- `src/qmatsuite/calculation/manifest_reconcile.py`
- `tests/unit/test_manifest_effective_structure.py` (新建)

**关键实现**:

```python
# manifest.py - 修改 ManifestStepEntry

@dataclass
class ManifestStepEntry:
    kind: str
    step_ulid: str
    pseudo_set_sha: str
    structure_sha: str  # 现有: init structure SHA
    step_sha: str
    effective_structure_sha: Optional[str] = None  # NEW: effective structure at execution
    run_id: Optional[str] = None
    done: bool = False
    started_at: Optional[str] = None
    done_at: Optional[str] = None


# executor.py - 添加 effective structure 恢复逻辑

def _load_effective_structure_for_step(self, step_idx, calculation, context):
    """Load effective structure for step, considering prior relax steps."""
    # Find all relax steps before this one
    for j in range(step_idx - 1, -1, -1):
        step = calculation.steps[j]
        if self._is_relax_step(step):
            # Check for current.json
            artifact_path = context.generated_structures_dir / f"step_{step.meta.id}" / "current.json"
            if not artifact_path.exists():
                raise MissingArtifactError(
                    f"MISSING_ARTIFACT_ERROR: Step '{calculation.steps[step_idx].name}' requires "
                    f"the relaxed structure from step '{step.name}' (ULID: {step.meta.id}), but "
                    f"generated_structures/step_{step.meta.id}/current.json is missing.\n\n"
                    "This typically means:\n"
                    "- The relax step has not been executed yet\n"
                    "- The relax step failed before producing output\n"
                    "- The generated_structures directory was deleted\n\n"
                    "To fix: Run the calculation from the beginning, or run the relax step first.\n"
                    "DO NOT manually create this file."
                )
            # Load and update context
            structure_dict = json.loads(artifact_path.read_text())
            # Remove meta for pymatgen parsing
            meta = structure_dict.pop("__qms_meta__", {})
            from pymatgen.core import Structure
            context.effective_structure = Structure.from_dict(structure_dict)
            context.effective_structure_sha = structure_fingerprint(context.effective_structure)
            break  # Use most recent relax
    
    return context.effective_structure
```

**测试**:
- `test_missing_current_json_hard_error`
- `test_effective_structure_sha_in_manifest`
- `test_incremental_skip_with_changed_effective_structure`

**风险点**:
- Manifest schema 变更 → 向后兼容：缺少 `effective_structure_sha` 字段时 fallback 到 `structure_sha`

**测试命令**: `pytest tests/unit/test_manifest_effective_structure.py -v`

---

## PR 5: Promote API + Daemon RPC (2 days)

**目的**: 实现 promote 功能，将 relax 输出升格为项目结构资源

**改动文件**:
- `src/qmatsuite/api.py`
- `src/qmatsuite/daemon/server.py`
- `tests/daemon/test_promote_relax_structure.py` (新建)

**关键实现**:

```python
# api.py

@staticmethod
def promote_relax_structure(
    project_root: Path,
    calculation_selector: str,
    step_selector: str,
    name: Optional[str] = None,
    index: Optional["ResourceIndex"] = None,
    config: Optional[dict] = None,
) -> ResolvedResource:
    """
    Promote a relax step's generated structure to a project resource.
    """
    from qmatsuite.core.resolution import resolve_calculation, resolve_step
    from qmatsuite.workflow.registry import get_registry
    
    project_root = Path(project_root).resolve()
    
    # Resolve calculation and step
    calc_resolved = resolve_calculation(project_root, calculation_selector, config=config, index=index)
    step_resolved = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
    
    # Verify step is a relax step
    registry = get_registry()
    step_spec = registry.get(step_resolved.meta.step_type)
    if not step_spec or not getattr(step_spec, 'is_structure_transform', False):
        raise QMSServiceError(
            f"Step '{step_selector}' is not a relax step (step_type: {step_resolved.meta.step_type}). "
            "Only relax/vc-relax steps can be promoted."
        )
    
    # Check for current.json
    calc_dir = calc_resolved.absolute_path
    if calc_dir.name == "calculation.yaml":
        calc_dir = calc_dir.parent
    
    artifact_path = calc_dir / "generated_structures" / f"step_{step_resolved.meta.id}" / "current.json"
    if not artifact_path.exists():
        raise QMSServiceError(
            f"No generated structure found for step '{step_selector}'. "
            f"Expected file: {artifact_path}\n"
            "The relax step may not have been executed or may have failed."
        )
    
    # Load structure
    structure_dict = json.loads(artifact_path.read_text())
    provenance_meta = structure_dict.pop("__qms_meta__", {})
    
    # Write to temp file for import
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(structure_dict, f)
        temp_path = Path(f.name)
    
    try:
        # Generate name if not provided
        if name is None:
            calc_name = calc_resolved.meta.name or calc_resolved.meta.slug or "calc"
            step_name = step_resolved.meta.name or "relax"
            name = f"{calc_name}_{step_name}_relaxed"
        
        # Import as new structure
        result = QMSService.import_structure(
            project_root=project_root,
            source=temp_path,
            name=name,
            index=index,
        )
        
        # Add provenance to the new structure's meta
        # (This would require updating the structure file, implementation detail)
        
        return result
    finally:
        temp_path.unlink()


# server.py - 添加 RPC handler

def _handle_promote_relax_structure(self, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Promote a relax step's generated structure to a project resource."""
    project_root = self._require_path(payload, "project_root")
    calculation = self._require_str(payload, "calculation")
    step = self._require_str(payload, "step")
    name = payload.get("name")
    
    result = QMSService.promote_relax_structure(
        project_root=project_root,
        calculation_selector=calculation,
        step_selector=step,
        name=name,
    )
    
    return {
        "success": True,
        "structure": {
            "id": result.meta.id,
            "name": result.meta.name,
            "path": str(result.absolute_path.relative_to(project_root)),
        },
    }
```

**测试**:
- `test_promote_creates_new_resource`
- `test_promote_requires_current_json`
- `test_promote_requires_relax_step`
- `test_daemon_promote_rpc`

**风险点**:
- Structure 导入复用 `import_structure` → 验证 fingerprint dedup 不会意外去重

**测试命令**: `pytest tests/daemon/test_promote_relax_structure.py -v`

---

## PR 6: Integration Tests + Documentation (2 days)

**目的**: 完整集成测试，文档更新

**改动文件**:
- `tests/integration/test_relax_e2e.py` (新建)
- `docs/specs/RELAX_SPEC.md` (新建，即 §2 的内容)
- 更新相关 README

**测试**:
- 所有 §3.2 集成测试
- 完整端到端流程验证

**测试命令**: `pytest tests/integration/test_relax_e2e.py -v`

---

---

## PR 10: Real ORCA Relax Test (完整实现)

**目的**: 修复 ORCA Relax 执行流程并创建真实 ORCA geometry optimization 集成测试

**重要**: 本地已安装 ORCA，所有测试必须实际运行，**不允许 skip**。

### 问题分析 (Code Review 结果)

PR10 存在三个相互关联的问题，必须全部解决：

#### 问题 1: ORCA Engine 的 `run_step` 方法抛出 NotImplementedError

**位置**: `src/qmatsuite/engine/orca_engine.py:175-202`

```python
def run_step(self, step, working_dir: Path) -> StepResult:
    # ...
    raise NotImplementedError(
        "ORCA steps must be executed through chain handler. "
        "Use orca_chain_handler in execution/handlers.py instead of calling run_step directly."
    )
```

**问题**: 当 `orca_chain_handler` 调用 `target_step.run(engine=engine, ...)` 时，会触发此错误。

#### 问题 2: ORCA Handler 使用错误的调用路径

**位置**: `src/qmatsuite/execution/handlers.py:409-415`

```python
# 当前代码 (错误)
result = target_step.run(  # ❌ 调用 step.run() → engine.run_step() → NotImplementedError
    engine=engine,
    calculation_raw_dir=raw_dir,
    ...
)
```

**对比 PySCF Handler (正确)**:
```python
# PySCF handler (handlers.py:307-313)
result = engine.run_step_with_chain(  # ✅ 直接调用 engine 的 chain 方法
    target_step=target_step,
    chain_steps=steps,
    ...
)
```

#### 问题 3: Executor Post-Process 未实现 ORCA Relax

**位置**: `src/qmatsuite/execution/executor.py:630-632`

```python
else:
    # Other engines (ORCA) handled separately
    continue  # ❌ 直接跳过，没有实现
```

**需要的信息** (来自 `orca_relax_parser.py:47-56`):
- `working_dir`: ORCA 工作目录（包含 `.xyz` 文件）
- `chain_key`: Chain key（如 `"chain01_scf"`）

---

### 解决方案: 类似 PySCF，为 ORCA 实现 `run_step_with_chain()`

#### 改动文件 (按顺序)

1. `src/qmatsuite/engine/orca_engine.py` - 添加 `run_step_with_chain()` 方法
2. `src/qmatsuite/execution/handlers.py` - 修改 `orca_chain_handler` 调用 `run_step_with_chain()`
3. `src/qmatsuite/execution/executor.py` - 实现 ORCA relax post-process
4. `tests/integration/test_orca_relax_real.py` - 集成测试

---

### 阶段 1: 修改 ORCAEngine，添加 `run_step_with_chain()` 方法

**文件**: `src/qmatsuite/engine/orca_engine.py`

**在 `run_step` 方法后添加新方法**:

```python
def run_step_with_chain(
    self,
    target_step,
    chain_steps: List[Any],
    calculation_raw_dir: Path,
    structure_id: Optional[str] = None,
    project_root: Optional[Path] = None,
) -> "StepResult":
    """
    Run an ORCA dependency chain.
    
    This method adapts the ORCA chain execution model to match the
    pyscf_engine.run_step_with_chain() interface used by handlers.
    
    Args:
        target_step: Target Step object
        chain_steps: List of Step objects in dependency order (from root to target)
        calculation_raw_dir: Base working directory (calc/raw/)
        structure_id: Structure resource ID (for Molecule loading)
        project_root: Project root path (for structure resolution)
        
    Returns:
        StepResult for the target step
    """
    import time
    from qmatsuite.engine.base import StepResult
    from qmatsuite.engine.qc_engine_base import QCChain, detect_chains
    from qmatsuite.io.structure_io import read_structure
    from qmatsuite.core.resolution import require_structure
    from pymatgen.core import Molecule as PMGMolecule
    
    start_time = time.time()
    calculation_raw_dir = Path(calculation_raw_dir)
    
    # 1. Validate inputs
    if not structure_id:
        return StepResult(
            step_type="orca_relax",
            input_file=calculation_raw_dir / "chain.inp",
            success=False,
            error="Structure ID is required for ORCA chain execution",
            execution_time=time.time() - start_time,
        )
    if not project_root:
        return StepResult(
            step_type="orca_relax",
            input_file=calculation_raw_dir / "chain.inp",
            success=False,
            error="Project root is required for structure resolution",
            execution_time=time.time() - start_time,
        )
    
    # 2. Load Molecule
    try:
        structure_resolved = require_structure(project_root, structure_id)
        structure_path = structure_resolved.absolute_path
        molecule = read_structure(structure_path)
        
        if not isinstance(molecule, PMGMolecule):
            return StepResult(
                step_type="orca_relax",
                input_file=calculation_raw_dir / "chain.inp",
                success=False,
                error=f"Expected Molecule for ORCA, got {type(molecule)}",
                execution_time=time.time() - start_time,
            )
    except Exception as e:
        return StepResult(
            step_type="orca_relax",
            input_file=calculation_raw_dir / "chain.inp",
            success=False,
            error=f"Failed to load molecule: {e}",
            execution_time=time.time() - start_time,
        )
    
    # 3. Build QCChain from chain_steps
    # For ORCA, we detect chains from steps (SCF root + downstream)
    chains = detect_chains(chain_steps)
    if not chains:
        return StepResult(
            step_type="orca_relax",
            input_file=calculation_raw_dir / "chain.inp",
            success=False,
            error="No valid QCChain detected from steps",
            execution_time=time.time() - start_time,
        )
    
    # Use the first (and usually only) chain
    chain = chains[0]
    
    # 4. Set up working directory
    # ORCA chains run in: calc/raw/chains/{chain_key}/
    from qmatsuite.engine.qc_engine_base import get_chain_working_dir_name
    chain_dir_name = get_chain_working_dir_name(chain)
    working_dir = calculation_raw_dir / "chains" / chain_dir_name
    working_dir.mkdir(parents=True, exist_ok=True)
    
    # 5. Execute chain
    try:
        orca_results = self.run_chain(
            chain=chain,
            working_dir=working_dir,
            molecule=molecule,
            fresh=True,  # Always fresh for explicit runs
        )
    except Exception as e:
        return StepResult(
            step_type="orca_relax",
            input_file=working_dir / f"{chain.key}.inp",
            success=False,
            error=f"ORCA chain execution failed: {e}",
            execution_time=time.time() - start_time,
        )
    
    # 6. Convert ORCAStepResult to StepResult
    # Find result for target step
    target_result = None
    for orca_result in orca_results:
        if orca_result.step_id == target_step.meta.id:
            target_result = orca_result
            break
    
    if target_result is None and orca_results:
        # Use last result if target not found explicitly
        target_result = orca_results[-1]
    
    if target_result is None:
        return StepResult(
            step_type="orca_relax",
            input_file=working_dir / f"{chain.key}.inp",
            success=False,
            error="No result found for target step",
            execution_time=time.time() - start_time,
        )
    
    # Store chain_key and working_dir in parsed_output for post-processing
    parsed_output = {
        "chain_key": chain.key,
        "working_dir": str(working_dir),
        "metrics": target_result.metrics,
        "artifacts": target_result.artifacts,
    }
    
    return StepResult(
        step_type=target_step.step_type or "orca_relax",
        input_file=Path(target_result.artifacts.get("input", working_dir / f"{chain.key}.inp")),
        output_file=Path(target_result.artifacts.get("output", working_dir / f"{chain.key}.out")),
        success=target_result.success,
        error=target_result.error,
        execution_time=time.time() - start_time,
        parsed_output=parsed_output,
    )
```

**同时删除 `run_step` 中的 `NotImplementedError`，改为调用 `run_step_with_chain`**:

```python
def run_step(self, step, working_dir: Path) -> StepResult:
    """
    Execute a single ORCA step.
    
    For ORCA, single steps are executed as chains of length 1.
    This method delegates to run_step_with_chain with a single-step chain.
    """
    # Extract structure_id and project_root from step.options (set by handler)
    structure_id = None
    project_root = None
    
    if hasattr(step, 'options'):
        structure_id = step.options.get('structure_id')
        project_root_str = step.options.get('project_root')
        if project_root_str:
            project_root = Path(project_root_str)
    
    return self.run_step_with_chain(
        target_step=step,
        chain_steps=[step],  # Chain of length 1
        calculation_raw_dir=working_dir,
        structure_id=structure_id,
        project_root=project_root,
    )
```

---

### 阶段 2: 修改 orca_chain_handler 调用 run_step_with_chain

**文件**: `src/qmatsuite/execution/handlers.py`

**找到 `orca_chain_handler` 函数 (约第 346 行)**

**将**:
```python
# Execute the chain using existing ORCA engine
target_step = steps[-1]  # Last step is the target

try:
    result = target_step.run(
        engine=engine,
        calculation_raw_dir=raw_dir,
        project_root=calculation.project.root,
        species_map=calculation.species_map,
    )

    success = result.success if hasattr(result, "success") else False

    # Record results for all steps in the chain
    for step in steps:
        if step is None:
            continue
        step_results[step.meta.id] = {
            "success": success,
            "executed_in_chain": True,
        }
```

**替换为**:
```python
# Execute the chain using ORCA engine's run_step_with_chain
# (matches PySCF handler pattern)
target_step = steps[-1]  # Last step is the target

try:
    # Call run_step_with_chain directly (like PySCF handler)
    result = engine.run_step_with_chain(
        target_step=target_step,
        chain_steps=steps,
        calculation_raw_dir=raw_dir,
        structure_id=calculation.structure_id if hasattr(calculation, 'structure_id') else None,
        project_root=calculation.project.root,
    )

    success = result.success if hasattr(result, "success") else False
    
    # Extract chain_key and working_dir from parsed_output for post-processing
    chain_key = None
    chain_working_dir = None
    if hasattr(result, 'parsed_output') and result.parsed_output:
        chain_key = result.parsed_output.get('chain_key')
        chain_working_dir = result.parsed_output.get('working_dir')

    # Record results for all steps in the chain
    for step in steps:
        if step is None:
            continue
        step_results[step.meta.id] = {
            "success": success,
            "executed_in_chain": True,
            "working_dir": chain_working_dir,  # For post-processing relax steps
            "chain_key": chain_key,  # For finding .xyz file
        }
```

---

### 阶段 3: 实现 Executor ORCA Relax Post-Process

**文件**: `src/qmatsuite/execution/executor.py`

**找到 `_post_process_relax_steps` 方法中的**:
```python
else:
    # Other engines (ORCA) handled separately
    continue
```

**替换为**:
```python
elif job.engine == "orca":
    # ORCA: parse .xyz file from chain working directory
    step_result = job_result.step_results.get(step_ulid, {})
    working_dir_str = step_result.get("working_dir")
    chain_key = step_result.get("chain_key")
    
    if not working_dir_str:
        logger.warning(f"[EXECUTOR] No working_dir found for ORCA relax step {step_ulid}, skipping post-process")
        continue
    if not chain_key:
        logger.warning(f"[EXECUTOR] No chain_key found for ORCA relax step {step_ulid}, skipping post-process")
        continue
    
    working_dir = Path(working_dir_str)
    
    # Import ORCA relax handler
    from qmatsuite.execution.orca_relax_parser import handle_orca_relax_output
    
    artifact_path = handle_orca_relax_output(
        step_ulid=step_ulid,
        step_type=str(step_type),
        calc_dir=calc_dir,
        working_dir=working_dir,
        chain_key=chain_key,
        calculation_ulid=calculation_ulid or "",
        input_structure_ulid=input_structure_ulid or "",
        run_id=run_id,
    )
    logger.info(f"[EXECUTOR] Successfully processed ORCA relax output for step {step_ulid}: {artifact_path}")
else:
    # Unknown engine
    logger.warning(f"[EXECUTOR] Unknown engine '{job.engine}' for relax step {step_ulid}, skipping post-process")
    continue
```

---

### 阶段 4: 验证并创建集成测试

**启发式编程步骤 (必须按顺序执行)**:

#### 步骤 1: 运行单次 ORCA relax 验证修复

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

python3 << 'PYEOF'
from pathlib import Path
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.api import QMSService
from pymatgen.core import Molecule
import shutil

# 1. 创建测试项目
test_dir = tmp_runs_dir() / "orca_relax_pr10_test"
if test_dir.exists():
    shutil.rmtree(test_dir)
test_dir.mkdir(parents=True, exist_ok=True)

project_root = QMSService.init_project(test_dir / "orca_project")

# 2. 创建 H2 分子
h2 = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])
h2_file = test_dir / "h2.xyz"
h2.to(filename=h2_file, fmt="xyz")

# 3. 导入结构
struct_result = QMSService.import_structure(project_root, h2_file, name="H2")
print(f"Structure ID: {struct_result.meta.id}")

# 4. 创建 calculation
calc = QMSService.init_calculation(
    project_root, "h2_relax",
    structure_selector=struct_result.meta.id,
    engine_family="orca",
    structure_kind="molecule",
)
print(f"Calculation ID: {calc.id}")

# 5. 创建 relax step
step = QMSService.init_step(project_root, calc.id, "orca_relax", name="relax")
print(f"Step ID: {step.id}")

# 6. 配置 step
QMSService.configure_step(
    project_root, calc.id, step.id,
    parameters={
        "method": "HF",
        "basis": "STO-3G",
        "geom": {"MaxIter": 50},
    },
)

# 7. 运行
print("\n=== Running ORCA relax ===")
result = QMSService.run_step(project_root, calc.id, step.id, verbose=True)
print(f"\nResult: {result}")

# 8. 检查 current.json
from qmatsuite.execution.relax_artifacts import get_generated_structure_path, read_generated_structure
calc_dir = project_root / "calculations" / "h2_relax"
artifact_path = get_generated_structure_path(calc_dir, step.id)
print(f"\nArtifact path: {artifact_path}")
print(f"Exists: {artifact_path.exists()}")

if artifact_path.exists():
    mol = read_generated_structure(calc_dir, step.id)
    print(f"Relaxed molecule: {len(mol)} atoms")
    print(f"H-H distance: {mol.get_distance(0, 1):.4f} Angstrom")
    print("\n=== SUCCESS ===")
else:
    print("\n=== FAILED: current.json not created ===")
PYEOF
```

#### 步骤 2: 如果步骤 1 失败，检查日志定位问题

```bash
# 检查 ORCA 输出文件
find .tmp/runs/orca_relax_pr10_test -name "*.out" -o -name "*.xyz" | head -20

# 检查 handler 日志
grep -r "ORCA\|orca" .tmp/runs/orca_relax_pr10_test/ 2>/dev/null | head -20
```

#### 步骤 3: 创建集成测试文件

**文件**: `tests/integration/test_orca_relax_real.py`

```python
"""
Real ORCA relax integration test.

This test actually runs ORCA to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.

IMPORTANT: ORCA is REQUIRED for these tests. They will NOT be skipped.
"""

import json
import pytest
import time
import uuid
import shutil
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration]


@pytest.fixture(scope="module")
def orca_available():
    """Verify ORCA is available. This fixture will FAIL if ORCA is not installed."""
    from qmatsuite.core.engines.orca_resolver import resolve_orca_bin
    
    orca_bin = resolve_orca_bin()
    assert orca_bin is not None, (
        "ORCA binary not found. ORCA is REQUIRED for these tests. "
        "Install ORCA or set ORCA_PATH environment variable."
    )
    assert Path(orca_bin).exists(), f"ORCA binary does not exist: {orca_bin}"
    return orca_bin


@pytest.fixture
def orca_project_with_h2(orca_available):
    """Create a project with H2 molecule for ORCA relax test."""
    unique_id = f"orca_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QMSService.init_project(test_dir / "orca_project")
    
    # Create H2 molecule with non-equilibrium bond length
    h2 = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])  # 0.8 Å (far from equilibrium ~0.74 Å)
    h2_file = test_dir / "h2.xyz"
    h2.to(filename=h2_file, fmt="xyz")
    
    # Import structure
    struct_result = QMSService.import_structure(project_root, h2_file, name="H2")
    
    # Create calculation
    calc = QMSService.init_calculation(
        project_root, "h2_relax",
        structure_selector=struct_result.meta.id,
        engine_family="orca",
        structure_kind="molecule",
    )
    
    # Create relax step
    step = QMSService.init_step(project_root, calc.id, "orca_relax", name="relax")
    
    # Configure with minimal parameters
    QMSService.configure_step(
        project_root, calc.id, step.id,
        parameters={
            "method": "HF",
            "basis": "STO-3G",
            "geom": {"MaxIter": 50},
        },
    )
    
    yield {
        "project_root": project_root,
        "calc_id": calc.id,
        "step_id": step.id,
        "structure_path": project_root / "structures" / f"{struct_result.meta.id}.json",
        "initial_h2_distance": 0.8,
    }
    
    # Cleanup
    if test_dir.exists():
        shutil.rmtree(test_dir, ignore_errors=True)


class TestORCARelaxReal:
    """Real ORCA relax integration tests."""
    
    def test_orca_relax_creates_current_json(self, orca_project_with_h2):
        """Test that ORCA relax creates current.json with relaxed structure."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_id"]
        
        # Run relax
        result = QMSService.run_step(project_root, calc_id, step_id)
        
        # Verify success
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Verify current.json exists
        calc_dir = project_root / "calculations" / "h2_relax"
        artifact_path = get_generated_structure_path(calc_dir, step_id)
        
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            "Check executor logs for post-processing errors."
        )
    
    def test_orca_relax_structure_changes(self, orca_project_with_h2):
        """Test that relaxed structure has different geometry."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_id"]
        initial_distance = orca_project_with_h2["initial_h2_distance"]
        
        # Run relax
        result = QMSService.run_step(project_root, calc_id, step_id)
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Read relaxed structure
        calc_dir = project_root / "calculations" / "h2_relax"
        relaxed_mol = read_generated_structure(calc_dir, step_id)
        
        assert relaxed_mol is not None, "Failed to read relaxed structure"
        assert len(relaxed_mol) == 2, f"Expected 2 atoms, got {len(relaxed_mol)}"
        
        # Check that geometry changed (relaxed H-H should be ~0.735 Å for HF/STO-3G)
        relaxed_distance = relaxed_mol.get_distance(0, 1)
        
        # The relaxed distance should be different from initial
        assert abs(relaxed_distance - initial_distance) > 0.01, (
            f"Geometry did not change significantly. "
            f"Initial: {initial_distance:.4f} Å, Relaxed: {relaxed_distance:.4f} Å"
        )
        
        # HF/STO-3G equilibrium H-H distance is approximately 0.735 Å
        assert 0.7 < relaxed_distance < 0.8, (
            f"Relaxed H-H distance {relaxed_distance:.4f} Å is outside expected range [0.7, 0.8] Å"
        )
    
    def test_orca_relax_molecule_composition(self, orca_project_with_h2):
        """Test that relaxed molecule has same composition as input."""
        project_root = orca_project_with_h2["project_root"]
        calc_id = orca_project_with_h2["calc_id"]
        step_id = orca_project_with_h2["step_id"]
        
        # Run relax
        result = QMSService.run_step(project_root, calc_id, step_id)
        assert result.get("success"), f"Step failed: {result.get('error')}"
        
        # Read relaxed structure
        calc_dir = project_root / "calculations" / "h2_relax"
        relaxed_mol = read_generated_structure(calc_dir, step_id)
        
        # Composition should be H2
        from pymatgen.core import Composition
        expected = Composition("H2")
        assert relaxed_mol.composition == expected, (
            f"Expected composition {expected}, got {relaxed_mol.composition}"
        )
```

#### 步骤 4: 运行集成测试

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
pytest tests/integration/test_orca_relax_real.py -v --tb=short
```

---

### 完成检查清单

- [x] `orca_engine.py`: 添加 `run_step_with_chain()` 方法
- [x] `orca_engine.py`: 修改 `run_step()` 调用 `run_step_with_chain()`
- [x] `handlers.py`: 修改 `orca_chain_handler` 调用 `engine.run_step_with_chain()`
- [x] `handlers.py`: 在 `step_results` 中添加 `working_dir` 和 `chain_key` (优先使用 parsed_output 中的 chain_key)
- [x] `executor.py`: 实现 ORCA relax post-process，调用 `handle_orca_relax_output()`
- [x] `orca_relax_parser.py`: 实现从 `.out` 文件解析最终结构（ORCA 不生成 `.xyz` 文件）
- [x] `orca_engine.py`: 添加 pymatgen Molecule 到 MoleculeLike 适配器
- [x] 创建 `test_orca_relax_real.py`
- [x] 所有测试通过 (3/3)

**实现说明**:
- `run_step_with_chain()` 使用传入的 `calculation_raw_dir` (即 `job.working_dir`) 作为工作目录
- Handler 优先使用 `parsed_output.chain_key` (如 "chain01_relax")，fallback 到 `job.metadata.subchain_basename`
- Post-process 使用 `chain_key` 查找 `.xyz` 文件，如果不存在则从 `.out` 文件解析最终结构
- ORCA 不生成 `.xyz` 文件，需要从 `.out` 文件的 "CARTESIAN COORDINATES" 部分解析
- 添加了 pymatgen Molecule 到 MoleculeLike 适配器（处理 `spin_multiplicity` vs `multiplicity`）

**测试命令**: `pytest tests/integration/test_orca_relax_real.py -v --tb=short`

---

### 测试文件模板 (DEPRECATED - 使用上面的新版本)

```python
"""
Real ORCA relax integration test.

This test actually runs ORCA to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.
"""

import json
import pytest
import time
import uuid
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration, pytest.mark.requires_orca]


@pytest.fixture(scope="module")
def orca_engine():
    """Create an ORCA engine instance and validate required executables."""
    from qmatsuite.engine.orca_engine import ORCAEngine
    from qmatsuite.core.engines.base import EngineConfig
    
    config = EngineConfig(name="orca")
    try:
        engine = ORCAEngine(config)
        
        if not engine.is_available():
            raise RuntimeError(
                "ORCA installation not found. ORCA is required for these tests."
            )
        
        return engine
    except Exception as e:
        raise RuntimeError(f"ORCA engine initialization failed: {e}") from e


@pytest.fixture
def orca_project_with_h2():
    """Create a project with H2 molecule for ORCA relax test."""
    # Use .tmp/runs/ directory with unique name
    unique_id = f"orca_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QMSService.init_project(test_dir / "orca_relax_project")
    
    # Create H2 molecule (simple case for quick test)
    h2_molecule = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])
    
    # Save molecule to file
    h2_file = test_dir / "h2.xyz"
    h2_molecule.to(filename=h2_file, fmt="xyz")
    
    # Import structure
    struct_result = QMSService.import_structure(project_root, h2_file, name="H2")
    
    return {
        "project_root": project_root,
        "structure_id": struct_result.meta.id,
        "structure_path": struct_result.absolute_path,
        "test_dir": test_dir,
    }


@pytest.fixture
def orca_calculation_with_relax(orca_project_with_h2):
    """Create a calculation with a relax step, configured for ORCA."""
    project_root = orca_project_with_h2["project_root"]
    structure_id = orca_project_with_h2["structure_id"]
    
    # Create calculation with molecule/orca settings
    calc_result = QMSService.init_calculation(
        project_root=project_root,
        name="h2_relax",
        structure_selector=structure_id,
        engine_family="orca",
        structure_kind="molecule",
    )
    calc_ulid = calc_result.id
    if calc_result.absolute_path.is_dir():
        calc_dir = calc_result.absolute_path
    else:
        calc_dir = calc_result.absolute_path.parent
    
    # Create relax step
    relax_step_result = QMSService.init_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_type="orca_relax",
        name="relax",
    )
    relax_step_ulid = relax_step_result.id
    
    # Configure relax step with minimal parameters for quick test
    QMSService.configure_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_selector=relax_step_ulid,
        parameters={
            "method": "HF",
            "basis": "STO-3G",  # Minimal basis for speed
            "geom": {"MaxIter": 50},
        },
    )
    
    return {
        "project_root": project_root,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
        "relax_step_ulid": relax_step_ulid,
        "structure_id": structure_id,
    }


class TestORCARelaxReal:
    """Real ORCA relax integration tests."""
    
    def test_orca_relax_execution_creates_current_json(
        self,
        orca_calculation_with_relax,
        orca_engine,
    ):
        """
        Test that running an ORCA relax step actually executes ORCA,
        and the output is parsed and written to current.json.
        """
        
        calc_ulid = orca_calculation_with_relax["calc_ulid"]
        relax_step_ulid = orca_calculation_with_relax["relax_step_ulid"]
        calc_dir = orca_calculation_with_relax["calc_dir"]
        project_root = orca_calculation_with_relax["project_root"]
        
        # Run the relax step
        result = QMSService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        # Verify step completed
        assert result.get("success") is True, f"Step failed: {result.get('error')}"
        
        # Verify current.json was created
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            "Check executor logs for post-processing errors."
        )
        
        # Verify structure can be read
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None, "Failed to read generated structure"
        assert len(relaxed_structure) == 2, "Expected 2 H atoms"
        
        # Verify H-H bond distance is reasonable (around 0.74 Angstrom for HF/STO-3G)
        bond_distance = relaxed_structure.get_distance(0, 1)
        assert 0.6 < bond_distance < 1.0, f"H-H bond distance {bond_distance} seems wrong"
        
        # Verify metadata
        data = json.loads(artifact_path.read_text())
        assert "__qms_meta__" in data
        assert data["__qms_meta__"]["source_step_ulid"] == relax_step_ulid
        assert data["__qms_meta__"]["provenance"]["method"] == "orca_relax"
```

### 关键约束

1. **不允许 skip**: 本地已安装 ORCA，测试必须实际运行
2. **使用 `.tmp/runs/`**: 所有测试目录在 `.tmp/runs/` 下
3. **最小测试 case**: 使用 H2 + HF/STO-3G，几秒钟完成
4. **解析器**:  `parse_orca_optimized_xyz()` 必须能正确解析 ORCA 的 `.xyz` 输出

### 测试命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
pytest tests/integration/test_orca_relax_real.py -v
```

---

## PR 11: Real PySCF Relax Test (启发式编程方法)

**目的**: 创建真实 PySCF geometry optimization 集成测试，验证完整执行流程

**重要**: 本地已安装 PySCF，所有测试必须实际运行，**不允许 skip**。

### 启发式编程方法 (Critical!)

**步骤 1**: 先运行一次 PySCF relax，保存输出文件

```bash
# 激活虚拟环境
cd <HOME>/QMatSuite && source .venv/bin/activate

# 创建一个最小的 PySCF geometry optimization 任务并运行
python3 << 'PYEOF'
from pathlib import Path
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.api import QMSService
from pymatgen.core import Molecule
import shutil
import json

# 1. 创建测试项目
test_dir = tmp_runs_dir() / "pyscf_relax_analysis"
test_dir.mkdir(parents=True, exist_ok=True)
project_root = QMSService.init_project(test_dir / "pyscf_relax_project")

# 2. 创建 H2 分子 (最简单的 geometry optimization)
h2 = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])  # 初始距离故意设远一点
h2_file = test_dir / "h2.xyz"
h2.to(filename=h2_file, fmt="xyz")

# 3. 导入结构
struct_result = QMSService.import_structure(project_root, h2_file, name="H2")

# 4. 创建 calculation (engine_family=pyscf, structure_kind=molecule)
calc = QMSService.init_calculation(
    project_root, "h2_relax",
    structure_selector=struct_result.meta.id,
    engine_family="pyscf",
    structure_kind="molecule",
)

# 5. 创建 relax step
step = QMSService.init_step(project_root, calc.id, "pyscf_relax", name="relax")

# 6. 配置 step (最小参数)
QMSService.configure_step(
    project_root, calc.id, step.id,
    parameters={
        "method": "rhf",  # 或 "rks" for DFT
        "basis": "sto-3g",  # 最小基组，速度快
        "maxsteps": 50,
    },
)

# 7. 运行
print(f"Project: {project_root}")
print(f"Calculation: {calc.id}")
print(f"Step: {step.id}")
result = QMSService.run_step(project_root, calc.id, step.id, verbose=True)

print(f"\nResult: {result}")

# 8. 保存输出文件用于分析
if result.get("success"):
    print("\n=== SUCCESS ===")
    # 查找输出文件
    calc_dir = project_root / "calculations" / "h2_relax"
    raw_dir = calc_dir / "raw"
    if raw_dir.exists():
        # PySCF 输出文件通常是 results.json, pyscf.log, checkpoint.chk
        for f in raw_dir.rglob("*"):
            if f.is_file():
                print(f"Found: {f}")
                if f.suffix in [".json", ".log", ".chk"]:
                    # 复制到分析目录
                    dest = Path("/tmp") / f"pyscf_relax_output_{f.name}"
                    shutil.copy2(f, dest)
                    print(f"  -> Saved to: {dest}")
                    # 如果是 json，打印内容
                    if f.suffix == ".json":
                        print(f"  Content: {json.loads(f.read_text())}")
else:
    print(f"\n=== FAILED ===")
    print(result.get("error"))
PYEOF
```

**步骤 2**: 分析输出文件格式

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate

# 查看 PySCF 输出文件结构
echo "=== PySCF Output Files ==="
ls -la /tmp/pyscf_relax_output_* 2>/dev/null || echo "No output files found yet"

# 分析 results.json 文件 (PySCF runner 的输出)
if [ -f /tmp/pyscf_relax_output_results.json ]; then
    echo ""
    echo "=== Content of results.json ==="
    cat /tmp/pyscf_relax_output_results.json | python3 -m json.tool
fi

# 分析 pyscf.log 文件
if [ -f /tmp/pyscf_relax_output_pyscf.log ]; then
    echo ""
    echo "=== Last 50 lines of pyscf.log ==="
    tail -50 /tmp/pyscf_relax_output_pyscf.log
fi
```

**步骤 3**: 确认 `results.json` 格式

PySCF runner (`src/qmatsuite/engines/pyscf/runner.py`) 的 `run_pyscf_relax()` 函数应该输出：

```json
{
  "success": true,
  "optimized_atoms": [
    {"element": "H", "xyz": [0.0, 0.0, 0.0]},
    {"element": "H", "xyz": [0.74, 0.0, 0.0]}
  ],
  "final_energy": -1.1336,
  "charge": 0,
  "spin_multiplicity": 1,
  "solver": "geometric",
  "method": "rhf",
  "basis": "sto-3g"
}
```

**步骤 4**: 测试 handler

```python
# 直接测试 handler 函数
from pathlib import Path
from qmatsuite.execution.pyscf_relax_handler import handle_pyscf_relax_output

# 模拟 results 数据
results = {
    "success": True,
    "optimized_atoms": [
        {"element": "H", "xyz": [0.0, 0.0, 0.0]},
        {"element": "H", "xyz": [0.74, 0.0, 0.0]},
    ],
}

calc_dir = Path("/tmp/test_calc")
artifact_path = handle_pyscf_relax_output(
    step_ulid="01TEST",
    step_type="pyscf_relax",
    calc_dir=calc_dir,
    results=results,
    calculation_ulid="calc001",
    input_structure_ulid="struct001",
    run_id="test_run",
)
print(f"Wrote: {artifact_path}")
print(f"Exists: {artifact_path.exists()}")
```

**步骤 5**: 运行完整集成测试

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
pytest tests/integration/test_pyscf_relax_real.py -v --tb=short
```

### 改动文件

- `tests/integration/test_pyscf_relax_real.py` (新建)
- `src/qmatsuite/execution/pyscf_relax_handler.py` (可能需要修复)
- `src/qmatsuite/engines/pyscf/runner.py` (确认 `run_pyscf_relax()` 输出格式)

### 测试文件模板

```python
"""
Real PySCF relax integration test.

This test actually runs PySCF to perform a geometry optimization
and verifies that the output is correctly parsed and written to current.json.
"""

import json
import pytest
import time
import uuid
from pathlib import Path

from qmatsuite.api import QMSService
from qmatsuite.core.paths import tmp_runs_dir
from qmatsuite.execution.relax_artifacts import (
    get_generated_structure_path,
    read_generated_structure,
)
from pymatgen.core import Molecule


pytestmark = [pytest.mark.integration]  # PySCF is always available


@pytest.fixture
def pyscf_project_with_h2():
    """Create a project with H2 molecule for PySCF relax test."""
    # Use .tmp/runs/ directory with unique name
    unique_id = f"pyscf_relax_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    test_dir = tmp_runs_dir() / unique_id
    test_dir.mkdir(parents=True, exist_ok=True)
    
    project_root = QMSService.init_project(test_dir / "pyscf_relax_project")
    
    # Create H2 molecule (simple case for quick test)
    h2_molecule = Molecule(["H", "H"], [[0, 0, 0], [0.8, 0, 0]])
    
    # Save molecule to file
    h2_file = test_dir / "h2.xyz"
    h2_molecule.to(filename=h2_file, fmt="xyz")
    
    # Import structure
    struct_result = QMSService.import_structure(project_root, h2_file, name="H2")
    
    return {
        "project_root": project_root,
        "structure_id": struct_result.meta.id,
        "structure_path": struct_result.absolute_path,
        "test_dir": test_dir,
    }


@pytest.fixture
def pyscf_calculation_with_relax(pyscf_project_with_h2):
    """Create a calculation with a relax step, configured for PySCF."""
    project_root = pyscf_project_with_h2["project_root"]
    structure_id = pyscf_project_with_h2["structure_id"]
    
    # Create calculation with molecule/pyscf settings
    calc_result = QMSService.init_calculation(
        project_root=project_root,
        name="h2_relax",
        structure_selector=structure_id,
        engine_family="pyscf",
        structure_kind="molecule",
    )
    calc_ulid = calc_result.id
    if calc_result.absolute_path.is_dir():
        calc_dir = calc_result.absolute_path
    else:
        calc_dir = calc_result.absolute_path.parent
    
    # Create relax step
    relax_step_result = QMSService.init_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_type="pyscf_relax",
        name="relax",
    )
    relax_step_ulid = relax_step_result.id
    
    # Configure relax step with minimal parameters for quick test
    QMSService.configure_step(
        project_root=project_root,
        calculation_selector=calc_ulid,
        step_selector=relax_step_ulid,
        parameters={
            "method": "rhf",
            "basis": "sto-3g",  # Minimal basis for speed
            "maxsteps": 50,
        },
    )
    
    return {
        "project_root": project_root,
        "calc_ulid": calc_ulid,
        "calc_dir": calc_dir,
        "relax_step_ulid": relax_step_ulid,
        "structure_id": structure_id,
    }


class TestPySCFRelaxReal:
    """Real PySCF relax integration tests."""
    
    def test_pyscf_relax_execution_creates_current_json(
        self,
        pyscf_calculation_with_relax,
    ):
        """
        Test that running a PySCF relax step actually executes PySCF,
        and the output is parsed and written to current.json.
        """
        
        calc_ulid = pyscf_calculation_with_relax["calc_ulid"]
        relax_step_ulid = pyscf_calculation_with_relax["relax_step_ulid"]
        calc_dir = pyscf_calculation_with_relax["calc_dir"]
        project_root = pyscf_calculation_with_relax["project_root"]
        
        # Run the relax step
        result = QMSService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        # Verify step completed
        assert result.get("success") is True, f"Step failed: {result.get('error')}"
        
        # Verify current.json was created
        artifact_path = get_generated_structure_path(calc_dir, relax_step_ulid)
        assert artifact_path.exists(), (
            f"current.json not found at {artifact_path}. "
            "Check executor logs for post-processing errors."
        )
        
        # Verify structure can be read
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None, "Failed to read generated structure"
        assert len(relaxed_structure) == 2, "Expected 2 H atoms"
        
        # Verify H-H bond distance is reasonable (around 0.74 Angstrom for RHF/STO-3G)
        bond_distance = relaxed_structure.get_distance(0, 1)
        assert 0.6 < bond_distance < 1.0, f"H-H bond distance {bond_distance} seems wrong"
        
        # Verify metadata
        data = json.loads(artifact_path.read_text())
        assert "__qms_meta__" in data
        assert data["__qms_meta__"]["source_step_ulid"] == relax_step_ulid
        assert data["__qms_meta__"]["provenance"]["method"] == "pyscf_relax"
    
    def test_pyscf_relax_structure_changes(
        self,
        pyscf_calculation_with_relax,
        pyscf_project_with_h2,
    ):
        """
        Test that the relaxed structure has a reasonable H-H bond distance.
        """
        
        calc_ulid = pyscf_calculation_with_relax["calc_ulid"]
        relax_step_ulid = pyscf_calculation_with_relax["relax_step_ulid"]
        calc_dir = pyscf_calculation_with_relax["calc_dir"]
        project_root = pyscf_calculation_with_relax["project_root"]
        
        # Load initial structure
        from qmatsuite.io import read_structure
        initial_structure = read_structure(pyscf_project_with_h2["structure_path"])
        initial_distance = initial_structure.get_distance(0, 1)
        
        # Run the relax step
        result = QMSService.run_step(
            project_root=project_root,
            calculation_selector=calc_ulid,
            step_selector=relax_step_ulid,
            verbose=False,
        )
        
        assert result.get("success") is True, f"Step failed: {result.get('error')}"
        
        # Load relaxed structure
        relaxed_structure = read_generated_structure(calc_dir, relax_step_ulid)
        assert relaxed_structure is not None
        
        relaxed_distance = relaxed_structure.get_distance(0, 1)
        
        # Verify structure changed
        assert relaxed_distance != pytest.approx(initial_distance, abs=0.01), (
            f"Structure should have changed. "
            f"Initial: {initial_distance:.4f}, Relaxed: {relaxed_distance:.4f}"
        )
        
        # Verify relaxed distance is closer to equilibrium (~0.74 A for H2)
        assert 0.70 < relaxed_distance < 0.80, (
            f"H-H bond distance {relaxed_distance:.4f} A is not near equilibrium (~0.74 A)"
        )
```

### 关键约束

1. **不允许 skip**: PySCF 是 Python 库，总是可用
2. **使用 `.tmp/runs/`**: 所有测试目录在 `.tmp/runs/` 下
3. **最小测试 case**: 使用 H2 + RHF/STO-3G，几秒钟完成
4. **Handler**:  `handle_pyscf_relax_output()` 从 `results.json` 的 `optimized_atoms` 构建 Molecule

### 测试命令

```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
pytest tests/integration/test_pyscf_relax_real.py -v
```

---

## PR 12: Promote E2E Test (1 day)

**目的**: 完整的 promote 功能端到端测试

**改动文件**:
- `tests/integration/test_relax_promote_e2e.py` (新建)

**测试流程**:
1. 创建项目 → 导入结构 → 创建 calculation → 创建 relax step
2. 运行 relax step (QE/ORCA/PySCF 任选)
3. 调用 `promote_relax_structure`
4. 验证新结构资源创建成功
5. 验证新结构可用于创建新 calculation

**测试命令**:
```bash
cd <HOME>/QMatSuite && source .venv/bin/activate
pytest tests/integration/test_relax_promote_e2e.py -v
```

---

## Review Checklist

每个 PR 必须满足以下不变量:

### Registry 相关
- [ ] `is_structure_transform=True` 仅用于 relax/vc-relax 类型步骤
- [ ] `produces_charge_density=False` 对于所有 relax 步骤
- [ ] 没有引入第二套 step type 分类系统

### Canonicalize 相关
- [ ] relax 输出结构使用 `structure_from_qe_geometry_snapshot()` 归一化
- [ ] 没有为 relax 输出引入新的 canonicalize 函数
- [ ] SHA 计算使用统一的 `structure_fingerprint(tol=1e-5)`

### QC Topology 相关
- [ ] `verify_qc_topology()` 在 recipe materialize 开头调用
- [ ] Relax 步骤总是 standalone chain (length=1)
- [ ] 非 relax/非 SCF 步骤必须追溯到 SCF，不能跨 relax

### Artifact 相关
- [ ] `current.json` 路径遵循 `generated_structures/step_<ulid>/current.json`
- [ ] `current.json` 不进入 ResourceIndex
- [ ] `current.json` 不分配 ULID（promote 前）
- [ ] Pre-clean 只删除本 job 覆盖的 relax steps 的 current.json

### Error 语义
- [ ] 缺失 `current.json` 是 hard error，不自动重跑
- [ ] QC topo error 在 run 前抛出，不是跑到一半才报
- [ ] Error message 包含明确的修复建议

### Promote 相关
- [ ] Promote 必须选择具体的 relax step（不是默认最后一个自动执行）
- [ ] Promote 创建新 ULID，记录 provenance
- [ ] Promote 不修改原 calculation.structure

### 锁语义
- [ ] `generated_structures` 写入在 `run.lock` 保护下
- [ ] 无需额外锁机制

### Manifest 相关
- [ ] `effective_structure_sha` 字段可选，向后兼容
- [ ] Skip 逻辑考虑 `effective_structure_sha` 变化

