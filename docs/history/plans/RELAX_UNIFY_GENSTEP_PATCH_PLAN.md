# RELAX GEN Step 统一 Patch 计划

**Version**: 1.0.0
**Date**: 2026-01-18
**Author**: Opus (Senior Architect)

---

## 1. 目标

将所有引擎的 relax/vc-relax/opt/geomopt 统一到单一 GEN step：
- **Public Type**: `relax` (唯一)
- **Machine Types**: `qe_relax`, `orca_relax`, `pyscf_relax`
- **VC 控制**: 通过 `relax.vc=true` option 控制，而非独立 step type

---

## 2. 现状分析

### 2.1 当前 Registry 中的 Relax 相关类型

| Machine Type | Public Type | Engine | 问题 |
|--------------|-------------|--------|------|
| `qe_relax` | `relax` | qe | ✅ 正确 |
| `qe_vc_relax` | `vc-relax` | qe | ❌ 应合并到 `qe_relax` |
| (未定义) | `opt` | orca | ❌ ORCA 缺失 relax 支持 |
| (未定义) | `geomopt` | pyscf | ❌ PySCF 缺失 relax 支持 |

### 2.2 RELAX_STEP_TYPES 常量

**文件**: `src/qmatsuite/engine/qc_engine_base.py:25`

```python
RELAX_STEP_TYPES = {"relax", "vc-relax", "opt", "geomopt"}
```

**问题**: 包含多个 public type，应只包含 `relax`

### 2.3 Topology Verify 检查

**文件**: `src/qmatsuite/execution/recipes.py:67,87`

检查 `step_public_type in RELAX_STEP_TYPES`，若常量包含多种，逻辑正确。
统一后仍正确，但更简洁。

---

## 3. 迁移策略

### 3.1 Phase 1: Registry 合并 (PR-PATCH-1)

**目标**: 将 `qe_vc_relax` 合并到 `qe_relax`，通过参数区分

**文件修改**: `src/qmatsuite/workflow/registry.py`

**Before**:
```python
"qe_relax": StepTypeSpec(
    id="relax",
    machine_type="qe_relax",
    public_type="relax",
    ...
),
"qe_vc_relax": StepTypeSpec(
    id="vc-relax",
    machine_type="qe_vc_relax",
    public_type="vc-relax",
    ...
),
```

**After**:
```python
"qe_relax": StepTypeSpec(
    id="relax",
    machine_type="qe_relax",
    public_type="relax",
    engine="qe",
    executable="pw.x",
    description="Structure relaxation (positions and optionally cell)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    is_structure_transform=True,
),
# 删除 qe_vc_relax，添加 compat alias
```

**VC 控制方式**:
```yaml
# step.yaml
step_type: qe_relax
parameters:
  relax:
    vc: true  # 启用 vc-relax
    cell_dofree: "all"  # 可选
```

### 3.2 Phase 2: 添加 ORCA/PySCF Relax (PR-PATCH-2)

**目标**: 添加 `orca_relax` 和 `pyscf_relax` machine types

**文件修改**: `src/qmatsuite/workflow/registry.py`

**新增**:
```python
"orca_relax": StepTypeSpec(
    id="relax",
    machine_type="orca_relax",
    public_type="relax",
    engine="orca",
    executable="orca",
    description="ORCA geometry optimization",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    is_structure_transform=True,
),
"pyscf_relax": StepTypeSpec(
    id="relax",
    machine_type="pyscf_relax",
    public_type="relax",
    engine="pyscf",
    executable="python",
    description="PySCF geometry optimization (geomopt)",
    requires_structure=True,
    requires_charge_density=False,
    produces_charge_density=False,
    is_structure_transform=True,
),
```

### 3.3 Phase 3: 简化 RELAX_STEP_TYPES (PR-PATCH-3)

**目标**: 常量只包含 `relax`

**文件修改**: `src/qmatsuite/engine/qc_engine_base.py`

**Before**:
```python
RELAX_STEP_TYPES = {"relax", "vc-relax", "opt", "geomopt"}
```

**After**:
```python
RELAX_STEP_TYPES = {"relax"}
```

### 3.4 Phase 4: Compat Shim for `vc-relax` (PR-PATCH-4)

**目标**: 向后兼容旧的 `vc-relax` step type

**文件修改**: `src/qmatsuite/workflow/registry.py`

**添加别名映射**:
```python
# Compatibility aliases (deprecated, will be removed in v2.0)
STEP_TYPE_ALIASES = {
    "vc-relax": "relax",  # Map to relax with vc=true
    "qe_vc_relax": "qe_relax",
    "opt": "relax",
    "geomopt": "relax",
}

def normalize_step_type(step_type: str) -> str:
    """Normalize step type, applying compatibility aliases."""
    if step_type in STEP_TYPE_ALIASES:
        import warnings
        warnings.warn(
            f"Step type '{step_type}' is deprecated. Use 'relax' instead.",
            DeprecationWarning,
        )
        return STEP_TYPE_ALIASES[step_type]
    return step_type
```

---

## 4. 文件修改清单

### 4.1 PR-PATCH-1: Registry 合并

| 文件 | 修改 |
|------|------|
| `src/qmatsuite/workflow/registry.py` | 删除 `qe_vc_relax`，更新 `qe_relax` 描述 |
| `tests/unit/test_step_type_mapping.py` | 更新测试，移除 `vc-relax` 检查 |

### 4.2 PR-PATCH-2: ORCA/PySCF Relax

| 文件 | 修改 |
|------|------|
| `src/qmatsuite/workflow/registry.py` | 添加 `orca_relax`, `pyscf_relax` |
| `src/qmatsuite/engine/orca_engine.py` | 添加 `orca_relax` 到 `supported_step_types()` |
| `src/qmatsuite/engine/pyscf_engine.py` | (无需修改，通过 runner 支持) |
| `tests/unit/test_step_type_mapping.py` | 添加新 step type 测试 |

### 4.3 PR-PATCH-3: 简化常量

| 文件 | 修改 |
|------|------|
| `src/qmatsuite/engine/qc_engine_base.py` | 简化 `RELAX_STEP_TYPES` |
| `tests/unit/execution/test_qc_topology.py` | 更新测试用例 |

### 4.4 PR-PATCH-4: Compat Shim

| 文件 | 修改 |
|------|------|
| `src/qmatsuite/workflow/registry.py` | 添加 `STEP_TYPE_ALIASES`, `normalize_step_type()` |
| `src/qmatsuite/core/resolution.py` | 在解析时调用 `normalize_step_type()` |
| `tests/unit/test_registry_compat.py` | 新增兼容性测试 |

---

## 5. 测试要求

### 5.1 必须通过的现有测试

```bash
pytest tests/unit/test_step_type_mapping.py -v
pytest tests/unit/execution/test_qc_topology.py -v
pytest tests/unit/execution/test_relax_artifacts.py -v
```

### 5.2 新增测试

**文件**: `tests/unit/test_registry_genstep_unified.py`

```python
"""Test unified GEN step (relax only)."""

class TestUnifiedGenStep:
    def test_only_one_gen_public_type(self):
        """Only 'relax' should be the GEN step public type."""
        registry = get_registry()
        gen_public_types = set()
        for spec in registry._types.values():
            if spec.is_structure_transform:
                gen_public_types.add(spec.public_type)
        assert gen_public_types == {"relax"}

    def test_qe_relax_covers_vc(self):
        """qe_relax should handle both relax and vc-relax."""
        registry = get_registry()
        spec = registry.get("qe_relax")
        assert spec is not None
        assert spec.public_type == "relax"
        # vc-relax should not exist as separate type
        assert registry.get("vc-relax") is None
        assert registry.get("qe_vc_relax") is None

    def test_orca_relax_exists(self):
        """orca_relax should be registered."""
        registry = get_registry()
        spec = registry.get("orca_relax")
        assert spec is not None
        assert spec.public_type == "relax"
        assert spec.is_structure_transform is True

    def test_pyscf_relax_exists(self):
        """pyscf_relax should be registered."""
        registry = get_registry()
        spec = registry.get("pyscf_relax")
        assert spec is not None
        assert spec.public_type == "relax"
        assert spec.is_structure_transform is True

    def test_compat_alias_vc_relax(self):
        """vc-relax should map to relax with deprecation warning."""
        with pytest.warns(DeprecationWarning):
            normalized = normalize_step_type("vc-relax")
        assert normalized == "relax"
```

---

## 6. UI 影响

### 6.1 Step Type 下拉菜单

**Before**: 显示 `relax`, `vc-relax`, `opt`, `geomopt`

**After**: 仅显示 `relax`

### 6.2 VC-Relax 控制

**Before**: 选择 `vc-relax` step type

**After**: 选择 `relax` step type，启用 "Variable Cell" 开关

### 6.3 参数面板

添加 `relax` 专属参数：
- Variable Cell (bool) → `relax.vc`
- Cell DOF (dropdown) → `relax.cell_dofree`
- Max Steps (int) → `relax.max_steps`

---

## 7. 迁移路径

### 7.1 现有项目兼容

项目中已有 `step_type: qe_vc_relax` 的 step.yaml 文件：

1. **加载时**: `normalize_step_type()` 自动映射到 `qe_relax`
2. **警告**: 发出 deprecation warning
3. **保存时**: 写入 `qe_relax` + `parameters.relax.vc: true`

### 7.2 时间表

| 版本 | 行为 |
|------|------|
| v1.x (当前) | 兼容警告，自动映射 |
| v2.0 | 移除 compat shim，`vc-relax` 报错 |

---

## 8. 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 现有项目 step.yaml 失效 | Compat shim 自动映射 |
| API 调用使用旧 type | `normalize_step_type()` 处理 |
| 测试覆盖不足 | 添加 compat 测试套件 |
| UI 未更新 | 同步更新 step type selector |

