# IR→Engine 序列化修复：apply preset 落盘必须走 engine backend

**日期**: 2025-01-XX  
**问题**: `test_apply_can_skip_physics_validation` 失败：期望 `.true.`，但得到 `True`

---

## 问题描述

### 复现

```bash
pytest tests/unit/test_preset_integration.py::TestApplyPresetsToStep::test_apply_can_skip_physics_validation -q
```

**失败输出**:
```
AssertionError: assert True == '.true.'
```

### 根因分析

1. **IR patch 包含原生类型**: ParamSpace 返回 IR patch，包含 Python 原生类型（`True`/`False`，`int`，`float`，`str`）
2. **step.yaml 需要 engine 格式**: step.yaml 是 spec step，parameters 必须是 engine-specific 格式（QE Fortran bool = `.true.`/`.false.`）
3. **落盘边界未序列化**: `apply_presets_to_step` 在 `doc.apply_patch(unified_patch)` 时直接写入 IR 原生值，未经过 engine backend 序列化

### 当前错误写入路径

**文件**: `src/quantumvitas/presets/integration.py`  
**函数**: `apply_presets_to_step()`  
**位置**: 行 712 `doc.apply_patch(unified_patch)`

`unified_patch` 结构：
```python
{
    "parameters": {
        "SYSTEM": {"noncolin": True, "lspinorb": True},  # IR 原生类型
        "ELECTRONS": {...}
    },
    "cards": {...}
}
```

直接写入 step.yaml 导致：
```yaml
parameters:
  SYSTEM:
    noncolin: true  # YAML 布尔值，不是 ".true." 字符串
    lspinorb: true
```

但测试期望：
```yaml
parameters:
  SYSTEM:
    noncolin: ".true."  # QE Fortran 格式字符串
    lspinorb: ".true."
```

---

## 修复策略

### 架构原则

1. **ParamSpace 只产 IR patch（原生类型）**: ParamSpace 内核不负责 engine 格式化
2. **Engine backend 负责序列化**: IR→engine 参数映射与序列化必须在 engine backend
3. **落盘边界调用 backend**: `apply_presets_to_step` 在落盘前调用 engine backend 序列化

### 实现方案

#### 1. QE Backend 序列化入口（SSOT）

**文件**: `src/quantumvitas/ir/backends/qe/mapping.py`  
**函数**: `ir_params_to_qe_params(ir_params: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]`

**职责**:
- 输入: IR parameters dict（包含 bool/int/float/str 等原生类型）
- 输出: QE parameters dict（值已序列化为 QE 期望格式）

**序列化规则**:
- `bool`: `True` → `".true."`, `False` → `".false."`
- 其它类型: 保持现状（pass-through）

**实现**: 复用 `ir_patch_to_qe_patch`，但适配 `unified_patch` 结构（`parameters` + `cards`）

#### 2. 落盘前调用序列化

**文件**: `src/quantumvitas/presets/integration.py`  
**函数**: `apply_presets_to_step()`  
**位置**: 在 `doc.apply_patch(unified_patch)` 之前

**流程**:
1. 获取 step 的 engine 信息（从 `step_type` 推断，目前都是 QE）
2. 调用 QE backend 序列化函数，将 `unified_patch` 转换为 QE 格式
3. 使用序列化后的 patch 调用 `doc.apply_patch()`

**关键**: `integration.py` 只负责"选择 backend 并调用"，不包含序列化逻辑

---

## 实现细节

### 修改文件清单

1. **src/quantumvitas/ir/backends/qe/mapping.py**
   - 新增/确认 `ir_params_to_qe_params()` 函数（处理 `parameters` + `cards` 结构）

2. **src/quantumvitas/presets/integration.py**
   - 在 `doc.apply_patch()` 之前调用序列化
   - 从 `step_type` 推断 engine（目前都是 QE）

3. **docs/dev/ir-engine-serialization-fix.md**
   - 本文档

---

## 验收

### 测试结果

```bash
pytest tests/unit/test_preset_integration.py::TestApplyPresetsToStep::test_apply_can_skip_physics_validation -q
pytest -q
```

**预期**: 全绿

### 验证点

1. **ParamSpace 仍只产 IR patch（原生类型）**
   - `compile_magnetism()` 返回 `True`/`False`，不返回 `".true."`
   - 验证方法: 调用 `compile_magnetism()` 并检查返回值类型

2. **Engine backend 负责序列化**
   - `ir_params_to_qe_params()` 将 `True` → `".true."`
   - 验证方法: 单元测试或临时 print

3. **Apply preset 立刻落盘 spec step 的 engine parameters**
   - step.yaml 中 `noncolin: ".true."`（字符串）
   - 验证方法: 读取落盘后的 step.yaml

---

## 影响面

- **仅影响 apply preset 落盘**: 不影响 ParamSpace 语义，不影响 runner
- **向后兼容**: step.yaml 格式从 IR 原生类型变为 engine 格式（符合 spec step 要求）
- **测试**: 需要更新期望值（但用户要求不改测试，所以修复必须让测试通过）

---

## 自检确认

**ParamSpace 仍只产 IR patch（原生类型），engine backend 负责序列化，apply preset 立刻落盘 spec step 的 engine parameters。**

