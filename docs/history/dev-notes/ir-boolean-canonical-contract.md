# IR 布尔值 Canonical 契约修复

**日期**: 2025-01-XX  
**问题**: 6 个 magnetism 相关测试失败，根因是 IR patch 中出现了 Python bool True/False，但 IR 契约要求 QE canonical boolean string：`.true.` / `.false.`

---

## 问题描述

### 失败测试

1. `tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_explicit_noncolin`
2. `tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_soc_explicit`
3. `tests/unit/test_detector_b.py::TestCompilerStringOptions::test_compile_presets_string_noncollinear_soc`
4. `tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_deletes_nspin`
5. `tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_soc_deletes_nspin`
6. `tests/presets/test_paramspace_ir.py::TestParamSpaceReversibility::test_magnetism_round_trip`

**根因**: IR patch 中包含 Python bool (`True`/`False`)，但测试期望 IR canonical boolean string (`.true.`/`.false.`)

### IR 布尔值 Canonical 契约

**当前 IR（QE backend）boolean 的 canonical 表示是 `.true.`/`.false.`（字符串）**

这是 IR 稳定契约的一部分（不是 engine 序列化）：
- IR 是 SSOT，IR 值必须是 canonical 格式
- 对于 QE backend，布尔值必须是 Fortran 格式字符串：`.true.` / `.false.`
- 这不是 engine mapping 的职责，而是 IR 本身的契约

**Engine mapping 仍然属于 engine**：
- 对 QE 来说，mapping 对 bool 是 identity（或 minimal）
- Engine writer 从 IR 读取 canonical 值，直接写入 QE input

**未来 typed IR**：
- 若未来要引入 typed IR（bool/int/float），那是单独的"IR refactor"
- 需要迁移与测试更新
- 当前阶段：IR 布尔值必须是字符串 `.true.`/`.false.`

---

## 定位问题

### True/False 进入 IR 的位置

1. **ParamSpace profiles**: `src/qmatsuite/presets/paramspace.py`
   - 行 818-843: profiles 中使用 `Cell.VALUE(True)` 和 `Cell.VALUE(False)`
   - 这些是 Python bool 值

2. **compile_profile_patch**: `src/qmatsuite/presets/paramspace.py`
   - 行 604: `patch[key.section][key.key] = value`
   - 直接写入 Python bool，未转换为 IR canonical 格式

3. **integration.py apply_invariants**: 
   - 可能也有直接写入 bool 的地方

---

## 修复策略

### A. 建立 IR Canonical Boolean Encoder（单点 SSOT）

**文件**: `src/qmatsuite/ir/backends/qe/mapping.py`  
**函数**: `ir_bool(v: bool | str) -> str`

**职责**:
- `True` → `".true."`
- `False` → `".false."`
- 若输入已经是 `".true."` / `".false."` 则原样返回
- 其它输入直接 raise（确保不 silent）

**这是 IR 契约工具，不是 ParamSpace 逻辑**

### B. 修复 compile_profile_patch

在写入 patch 之前，对于布尔类型的 key，通过 `ir_bool()` 转换值。

**关键**: 只修复"写入 dict 的那一行"，不改变 apply 顺序/oracle/invariants/ownership 的任何逻辑。

### C. 修复 apply_invariants（如果有）

如果 `apply_invariants` 也有直接写入 bool 的地方，同样修复。

---

## 实现细节

### 修改文件清单

1. **src/qmatsuite/ir/backends/qe/mapping.py**
   - 新增 `ir_bool()` 函数

2. **src/qmatsuite/presets/paramspace.py**
   - 修复 `compile_profile_patch()` 中的值写入
   - 修复 `apply_invariants()` 中的值写入（如果有）

3. **docs/dev/ir-boolean-canonical-contract.md**
   - 本文档

---

## 验收

### 测试结果

```bash
pytest tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_explicit_noncolin -q
pytest tests/unit/test_detector_b.py::TestCompilerCanonicalEncoding::test_compile_magnetism_noncollinear_soc_explicit -q
pytest tests/unit/test_detector_b.py::TestCompilerStringOptions::test_compile_presets_string_noncollinear_soc -q
pytest tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_deletes_nspin -q
pytest tests/unit/test_magnetism_paramspace_contract.py::TestMagnetismApplyCanonicalization::test_apply_noncollinear_soc_deletes_nspin -q
pytest tests/presets/test_paramspace_ir.py::TestParamSpaceReversibility::test_magnetism_round_trip -q
pytest -q
```

**预期**: 全绿

---

## 影响面

- **仅影响 IR 值编码**: 不影响 ParamSpace 语义，不影响 engine mapping
- **向后兼容**: IR 布尔值从 Python bool 变为 canonical string（符合 IR 契约）
- **测试**: 测试期望保持不变（`.true.`/`.false.`）

