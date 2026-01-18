# RELAX Implementation Plan

**Date**: 2026-01-18
**Status**: IN PROGRESS

---

## PR Overview (给 Cursor Auto 的执行顺序)

| PR | 名称 | 状态 | 测试命令 |
|----|------|------|----------|
| PR1 | Registry Updates + Type Foundation | ✅ 完成 | `pytest tests/unit/test_step_type_mapping.py -v` |
| PR2 | QC Topology Verification | ✅ 完成 | `pytest tests/unit/execution/test_qc_topology.py -v` |
| PR3 | Generated Structures Helper Functions | 🔄 待做 | `pytest tests/unit/execution/test_relax_artifacts.py -v` |
| PR3b | Executor Integration | ⏸️ 延后 | (PR6 一起做) |
| PR4 | Missing Artifact Hard Error + Manifest | 🔄 待做 | `pytest tests/unit/test_manifest_effective_structure.py -v` |
| PR5 | Promote API + Daemon RPC | 🔄 待做 | `pytest tests/daemon/test_promote_relax_structure.py -v` |
| PR6 | Integration Tests + Documentation | 🔄 待做 | `pytest tests/integration/test_relax_e2e.py -v` |

**执行顺序**: PR1 → PR2 → PR3 → PR4 → PR5 → PR6 (PR3b 包含在 PR6 中)

**当前进度**: PR1 和 PR2 已完成，继续执行 PR3。

---

## PR 1: Registry Updates + Type Foundation (1-2 days) ✅ 完成

**目的**: 为 relax 步骤添加类型基础，不改变运行时行为

**改动文件**:
- `src/quantumvitas/workflow/registry.py`
- `src/quantumvitas/engine/qc_engine_base.py`
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
- `src/quantumvitas/execution/recipes.py` (ORCARecipe, PySCFRecipe)
- `src/quantumvitas/execution/executor.py` (添加 verify 调用)
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
- `src/quantumvitas/execution/relax_artifacts.py` (新建)
- `tests/unit/execution/test_relax_artifacts.py` (新建)

### Step 3.1: 创建 relax_artifacts.py

在 `src/quantumvitas/execution/` 下新建 `relax_artifacts.py`：

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
    structure_dict["__qv_meta__"] = {
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
    structure_dict.pop("__qv_meta__", None)
    
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
    from quantumvitas.workflow.registry import get_registry
    
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

from quantumvitas.execution.relax_artifacts import (
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
        assert "__qv_meta__" in data
        assert data["__qv_meta__"]["type"] == "generated_structure"
        assert data["__qv_meta__"]["source_step_ulid"] == step_ulid
        assert data["__qv_meta__"]["provenance"]["method"] == "qe_relax"

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

## PR 3b: Executor Integration (Optional - 可延后)

**目的**: 将 relax_artifacts 集成到 executor 的执行流程中

**前置条件**: PR3 完成且测试通过

**注意**: 此 PR 涉及真实执行流程，建议在有实际 QE relax 测试环境后再实现。
可以先实现 PR4 和 PR5，它们不依赖此 PR。

**改动文件**:
- `src/quantumvitas/execution/executor.py` - 在 job 循环中调用 relax_artifacts 函数
- `tests/integration/test_relax_execution.py` (新建)

**关键修改点** (executor.py 第 136-170 行附近):

```python
# 在 for job in jobs_to_execute: 循环内部

# Step 1: Pre-clean (在执行前)
from quantumvitas.execution.relax_artifacts import (
    clean_generated_structure,
    write_generated_structure,
    is_relax_step_type,
)

for step_id in job.step_ids:
    step = self._find_step_by_id(calculation, step_id)
    if step and is_relax_step_type(step.step_type):
        calc_dir = calculation.dir if hasattr(calculation, 'dir') else calculation.path.parent
        clean_generated_structure(calc_dir, step_id)

# Step 2: Execute job (现有代码)
result = self._execute_single_job(job, calculation, ...)

# Step 3: Post-process (在执行后，成功时)
if result.success:
    for step_id in job.step_ids:
        step = self._find_step_by_id(calculation, step_id)
        if step and is_relax_step_type(step.step_type):
            # Parse and write generated structure
            # 这需要从 handler 返回 parsed structure，暂时跳过
            pass
```

**由于此 PR 需要真实 QE 执行环境，建议延后到 PR6 集成测试阶段一起做。**

---

## PR 4: Missing Artifact Hard Error + Manifest Enhancement (2 days)

**目的**: 实现缺失 current.json 的硬错误，manifest 添加 effective_structure_sha

**改动文件**:
- `src/quantumvitas/execution/executor.py`
- `src/quantumvitas/calculation/manifest.py`
- `src/quantumvitas/calculation/manifest_reconcile.py`
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
            meta = structure_dict.pop("__qv_meta__", {})
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
- `src/quantumvitas/api.py`
- `src/quantumvitas/daemon/server.py`
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
    from quantumvitas.core.resolution import resolve_calculation, resolve_step
    from quantumvitas.workflow.registry import get_registry
    
    project_root = Path(project_root).resolve()
    
    # Resolve calculation and step
    calc_resolved = resolve_calculation(project_root, calculation_selector, config=config, index=index)
    step_resolved = resolve_step(project_root, calculation_selector, step_selector, config=config, index=index)
    
    # Verify step is a relax step
    registry = get_registry()
    step_spec = registry.get(step_resolved.meta.step_type)
    if not step_spec or not getattr(step_spec, 'is_structure_transform', False):
        raise QVServiceError(
            f"Step '{step_selector}' is not a relax step (step_type: {step_resolved.meta.step_type}). "
            "Only relax/vc-relax steps can be promoted."
        )
    
    # Check for current.json
    calc_dir = calc_resolved.absolute_path
    if calc_dir.name == "calculation.yaml":
        calc_dir = calc_dir.parent
    
    artifact_path = calc_dir / "generated_structures" / f"step_{step_resolved.meta.id}" / "current.json"
    if not artifact_path.exists():
        raise QVServiceError(
            f"No generated structure found for step '{step_selector}'. "
            f"Expected file: {artifact_path}\n"
            "The relax step may not have been executed or may have failed."
        )
    
    # Load structure
    structure_dict = json.loads(artifact_path.read_text())
    provenance_meta = structure_dict.pop("__qv_meta__", {})
    
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
        result = QVService.import_structure(
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
    
    result = QVService.promote_relax_structure(
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

