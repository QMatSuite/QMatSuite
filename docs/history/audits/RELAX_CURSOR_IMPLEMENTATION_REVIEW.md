# RELAX Cursor Auto 实现审查报告

**Version**: 1.0.0
**Date**: 2026-01-18
**Reviewer**: Opus (Senior Architect)

---

## 1. 审查范围

基于 RELAX_SPEC.md 规范，对 Cursor Auto 已实现的 6 个 PR（57 个测试）进行逐条对照审查。

---

## 2. 逐条对照结果

### 2.1 Job Scoped Cleanup

**规范要求** (§4.2): 每次 job 开始只清理"该 job 覆盖到的 relax steps"的 `current.json`

**当前实现**: `src/qmatsuite/execution/relax_artifacts.py`

```python:110:126
def clean_generated_structure(calc_dir: Path, step_ulid: str) -> bool:
    """Delete a generated structure's current.json."""
    artifact_path = get_generated_structure_path(calc_dir, step_ulid)
    if artifact_path.exists():
        artifact_path.unlink()
        logger.info(f"[RELAX_ARTIFACTS] Cleaned {artifact_path}")
        return True
    return False
```

**发现**: 
- ✅ `clean_generated_structure()` 函数已实现
- ⚠️ **未在 executor 中调用**: `executor.py` 中没有在 job 开始时调用 cleanup

**状态**: ❌ **Must-fix** - 需要在 executor 的 job 执行前添加 scoped cleanup

**定位点**: `src/qmatsuite/execution/executor.py:140-229` (job 执行循环)

---

### 2.2 Relax 成功条件 (current.json 必须生成)

**规范要求** (§4.3): relax 成功后必须生成 `current.json`，否则 fail-fast

**当前实现**: `src/qmatsuite/execution/relax_artifacts.py`

```python:37:81
def write_generated_structure(
    structure: "PMGStructure",
    calc_dir: Path,
    step_ulid: str,
    step_type: str,
    ...
) -> Path:
    """Write a relaxed structure to generated_structures directory."""
```

**发现**:
- ✅ `write_generated_structure()` 函数已实现
- ⚠️ **未被调用**: executor/handlers 中没有在 relax step 成功后调用此函数
- ⚠️ **缺少 output parsing**: 没有调用 `read_final_geometry_from_output_text()` 解析 QE 输出

**状态**: ❌ **Must-fix** - 需要在 relax handler 中集成输出解析和 current.json 写入

**定位点**: `src/qmatsuite/execution/handlers.py` (添加 relax 后处理)

---

### 2.3 MissingArtifactError 触发

**规范要求** (§5.2): 需要 effective structure 时若 current.json 不存在，触发 MissingArtifactError

**当前实现**: `src/qmatsuite/core/exceptions.py`

```python:24:32
class MissingArtifactError(Exception):
    """Raised when a required artifact (e.g., generated structure) is missing."""
    pass
```

**发现**:
- ✅ `MissingArtifactError` 异常类已定义
- ⚠️ **未被抛出**: 没有代码实际检查 current.json 并抛出此异常
- ⚠️ **错误信息未实现**: 规范要求的详细错误信息未在代码中

**状态**: ❌ **Must-fix** - 需要在 executor 中添加 missing artifact 检查

**定位点**: `src/qmatsuite/execution/executor.py` (在依赖 effective structure 前检查)

---

### 2.4 QC Verify (Relax as Chain Breaker)

**规范要求** (§6.1): relax 视为 chain breaker，non-relax step 的 SCF 追溯不能穿过 relax

**当前实现**: `src/qmatsuite/execution/recipes.py`

```python:38:103
def verify_qc_topology(steps: List["Step"], registry) -> None:
    """Verify QC topology before execution."""
    for i, step in enumerate(steps):
        ...
        if step_public_type in RELAX_STEP_TYPES:
            continue  # Relax is standalone, always valid
        ...
        if ancestor_public_type in RELAX_STEP_TYPES:
            raise TopologyError(
                f"TOPOLOGY_ERROR: Step '{step_name}' (index {i}) cannot trace to SCF root. "
                f"A relax step at index {j} blocks the dependency chain. "
                "Relax steps are not electronic state providers; they must be in standalone chains."
            )
```

**发现**:
- ✅ `verify_qc_topology()` 已实现
- ✅ 正确检查 relax 阻断 SCF 链
- ✅ 在 `ORCARecipe.materialize()` 和 `PySCFRecipe.materialize()` 中调用

**状态**: ✅ **Compliant**

**定位点**: `src/qmatsuite/execution/recipes.py:278` (ORCA), `src/qmatsuite/execution/recipes.py:388` (PySCF)

---

### 2.5 QE 不被 QC Verify 误伤

**规范要求** (§6.2): QE 不执行 strong-chain topology check

**当前实现**: `src/qmatsuite/execution/recipes.py`

```python:156:233
class QERecipe(BaseRecipe):
    def materialize(self, steps, calc_raw_dir, step_shas=None):
        # 无 verify_qc_topology() 调用
        jobs: List[Job] = []
        for idx, step in enumerate(steps):
            ...
```

**发现**:
- ✅ `QERecipe.materialize()` 不调用 `verify_qc_topology()`
- ✅ QE 步骤可以任意排列

**状态**: ✅ **Compliant**

---

### 2.6 Canonicalize/SHA 唯一入口

**规范要求** (§4.3): 使用统一的 canonicalize 入口，禁止第二套

**当前实现**:

1. `src/qmatsuite/calculation/geometry.py:461-506`
```python
def structure_from_qe_geometry_snapshot(snapshot, species) -> PMGStructure:
    ...
    # CRITICAL: Canonicalize exactly once
    from qmatsuite.analysis.structure_viz import canonicalize_structure_in_place
    canonicalize_structure_in_place(structure)
    return structure
```

2. `src/qmatsuite/core/structure_fingerprint.py`
```python
def structure_fingerprint(structure: Structure, tol: float = 1e-5) -> str:
    """Generate stable fingerprint (SHA256) for a structure."""
```

**发现**:
- ✅ QE parser 使用 `canonicalize_structure_in_place()`
- ⚠️ ORCA/PySCF 尚未实现，需确保也使用相同入口

**状态**: ⚠️ **Should-fix** - ORCA/PySCF parser 需要显式调用 canonicalize

---

### 2.7 Promote API 必须传 Relax Step Selector

**规范要求** (§7.1): promote 使用 step_selector (dropdown)，而非 latest

**当前实现**: `src/qmatsuite/api.py`

```python
@staticmethod
def promote_relax_structure(
    project_root: Path,
    calculation_selector: str,
    step_selector: str,  # ✅ 必需参数
    name: Optional[str] = None,
    ...
) -> ResolvedResource:
```

**发现**:
- ✅ `step_selector` 是必需参数
- ✅ 验证 step 是 relax 类型
- ✅ 检查 current.json 存在

**状态**: ✅ **Compliant**

**定位点**: `src/qmatsuite/api.py` (promote_relax_structure 方法)

---

### 2.8 RELAX_STEP_TYPES 语义漂移检查

**规范要求**: GEN step 只有一个 public type: `relax`

**当前实现**: `src/qmatsuite/engine/qc_engine_base.py`

```python:23:25
# Step types that are structure transforms (relax/opt)
RELAX_STEP_TYPES = {"relax", "vc-relax", "opt", "geomopt"}
```

**发现**:
- ⚠️ **存在多个 public type**: `relax`, `vc-relax`, `opt`, `geomopt`
- ⚠️ `vc-relax` 应该是 `relax` 的 option，不是独立 public type
- ⚠️ `opt`, `geomopt` 应该映射到 `relax`

**影响面**:

| 文件 | 行号 | 问题 |
|------|------|------|
| `registry.py` | 204-214 | `qe_vc_relax` 有独立 `id="vc-relax"` |
| `qc_engine_base.py` | 25 | `RELAX_STEP_TYPES` 包含 4 种 |
| `recipes.py` | 67, 87 | 检查 `RELAX_STEP_TYPES` 包含多种 |

**状态**: ❌ **Must-fix** - 需要统一 GEN step 为单一 `relax` public type

---

## 3. 问题清单

### 3.1 Must-Fix (阻断)

| # | 问题 | 定位点 | 修复方案 |
|---|------|--------|----------|
| M1 | Job scoped cleanup 未实现 | `executor.py` | 在 job 开始前调用 `clean_generated_structure()` |
| M2 | Relax 成功后未写 current.json | `handlers.py` | 添加 relax post-processing |
| M3 | MissingArtifactError 未触发 | `executor.py` | 在依赖 effective structure 前检查 |
| M4 | 多个 GEN step public type | `registry.py`, `qc_engine_base.py` | 统一为 `relax`，vc 作为 option |

### 3.2 Should-Fix (建议)

| # | 问题 | 定位点 | 修复方案 |
|---|------|--------|----------|
| S1 | ORCA/PySCF parser 未实现 | 新增 | 添加 ORCA/PySCF relax output parser |
| S2 | ORCA/PySCF 未调用 canonicalize | 新增 parser | 在 parser 中调用 `canonicalize_structure_in_place()` |
| S3 | effective_structure_sha 未使用 | `manifest.py`, `executor.py` | 集成到 skip logic |

### 3.3 Nice-to-Have (优化)

| # | 问题 | 定位点 | 修复方案 |
|---|------|--------|----------|
| N1 | QE lenient topology warning | `recipes.py` | 添加 warning 日志 |
| N2 | Promote UI preview | GUI | 添加结构对比预览 |

---

## 4. 现有测试覆盖

### 4.1 通过的测试 (57 个)

| 测试文件 | 数量 | 覆盖点 |
|----------|------|--------|
| `test_step_type_mapping.py` | 20 | Registry 配置 |
| `test_qc_topology.py` | 9 | QC 拓扑验证 |
| `test_relax_artifacts.py` | 12 | 生成结构工具 |
| `test_manifest_effective_structure.py` | N/A | Manifest 字段 |
| `test_promote_relax_structure.py` | 4 | Promote API |
| `test_relax_e2e.py` | 7 | 集成测试 |

### 4.2 缺失的测试

| 测试类别 | 缺失项 |
|----------|--------|
| 真实 QE relax | 未调用真实 pw.x |
| 真实 ORCA opt | 未调用真实 orca |
| 真实 PySCF geomopt | 未调用真实 pyscf.geomopt |
| current.json 内容验证 | 仅验证存在，未验证内容 |
| Scoped cleanup | 未测试 job 开始时的清理 |

---

## 5. 结论

当前实现建立了良好的基础架构，但存在以下关键差距：

1. **执行层缺失**: relax 步骤的输出解析和 current.json 写入未集成
2. **语义漂移**: 存在多个 GEN step public type，需要统一
3. **真实测试缺失**: 未真正调用三引擎执行 relax

下一步需要：
1. Patch PR: 统一 GEN step 为 `relax`
2. Integration PR: 集成 relax post-processing 到 executor
3. E2E PR: 添加真实引擎调用测试

