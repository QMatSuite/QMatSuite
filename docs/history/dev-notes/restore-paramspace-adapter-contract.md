# ParamSpace IR/QE 适配层契约文档

**日期**: 2025-01-XX  
**目的**: 明确旧ParamSpace（baac796）与现有IR层的适配契约，定义输入输出数据形状和转换规则。

---

## 1. ParamSpace输入输出契约

### 1.1 ParamSpace期望的YAML数据形状

**ParamSpace内核（baac796）期望**:
- 输入：`dict[str, dict[str, Any]]`，格式为 `{section: {key: value}}`
- 例如：`{"SYSTEM": {"nspin": 2, "ecutwfc": 50}, "ELECTRONS": {"conv_thr": 1e-6}}`
- Section名称：QE section名称（如`"SYSTEM"`, `"ELECTRONS"`, `"cards"`）
- Key名称：**概念上IR key**，但在v0中与QE key同名（如`"nspin"`, `"ecutwfc"`）

**证据**: `src/qmatsuite/presets/paramspace.py:241-309` - `match_profile()`和`compile_profile_patch()`接受`yaml_tree: dict[str, dict[str, Any]]`

### 1.2 当前系统IR YAML数据形状

**IR YAML结构**:
- 格式：`dict[str, dict[str, Any]]`，格式为 `{section: {ir_key: value}}`
- Section名称：在v0中与QE section相同（`"SYSTEM"`, `"ELECTRONS"`, `"cards"`）
- Key名称：IR key（如`"nspin"`, `"ecutwfc"`），在v0中与QE key同名

**证据**: `src/qmatsuite/ir/backends/qe/mapping.py:16-44` - `IR_TO_QE_MAPPING`显示IR keys与QE keys在v0中同名

### 1.3 IR 1:1映射下的字段对应关系

**完全同名的字段**（v0阶段）:
- Section名称：完全一致（`"SYSTEM"`, `"ELECTRONS"`, `"cards"`）
- Key名称：完全一致（`"nspin"`, `"ecutwfc"`, `"conv_thr"`, `"K_POINTS"`等）

**容器结构差异**:
- 无差异：两者都使用`dict[str, dict[str, Any]]`结构
- 唯一差异：语义层面（IR key是"概念上IR"，QE key是"实际QE参数"）

**结论**: 在IR 1:1映射下，IR YAML与ParamSpace期望的YAML在结构上完全兼容，只需要类型标注/语义对齐，不需要重命名。

---

## 2. 适配实现位置（方案A）

### 2.1 选择方案A的原因

**方案A（推荐）**: 保持现有IR工作流，适配在ParamSpace调用边界

**选择原因**:
1. **单点适配**：所有IR↔QE转换集中在`variants_registry.py`的`compile_dimension_patch_for_step()`和`detect_dimension_for_step()`函数中
2. **不破坏ParamSpace内核**：ParamSpace内核（baac796）保持不变，只在外围做适配
3. **易于维护**：未来IR非1:1时，只需修改适配层，不需要修改ParamSpace内核

### 2.2 适配入口函数

**编译适配**:
- **位置**: `src/qmatsuite/presets/variants_registry.py:260-346`
- **函数**: `compile_dimension_patch_for_step()`
- **适配逻辑**:
  1. 输入：QE YAML（从step.yaml读取）
  2. 转换：`qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")` → IR YAML
  3. ParamSpace操作：`compile_profile_patch(variant.space, profile_name, ir_yaml, ...)` → IR patch
  4. 转换：`ir_patch_to_qe_patch(ir_patch)` → QE patch
  5. 输出：QE patch（写入step.yaml）

**检测适配**:
- **位置**: `src/qmatsuite/presets/variants_registry.py:499-529`
- **函数**: `detect_dimension_for_step()`
- **适配逻辑**:
  1. 输入：QE YAML（从step.yaml读取）
  2. 转换：`qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")` → IR YAML
  3. ParamSpace操作：`match_profile(variant.space, ir_yaml)` → profile name
  4. 输出：enum option（通过profile_to_enum映射）

**精度检测适配**:
- **位置**: `src/qmatsuite/presets/variants_registry.py:556-648`
- **函数**: `_detect_precision_for_step()`
- **适配逻辑**:
  1. 输入：QE YAML
  2. 转换：`qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")` → IR YAML
  3. ParamSpace操作：`match_precision_profile(ir_yaml, canonical_values)` → profile name
  4. 输出：PrecisionOption enum

---

## 3. Key Access Enforcement适配

### 3.1 ParamSpaceContext使用

**位置**: 所有调用ParamSpace操作的地方

**实现**:
```python
from qmatsuite.presets.paramspace import ParamSpaceContext

with ParamSpaceContext(variant.space):
    # ParamSpace operations (match_profile, compile_profile_patch)
    matched_profile = match_profile(variant.space, ir_yaml)
```

**证据**: 
- `src/qmatsuite/presets/variants_registry.py:318-320` - compile时使用
- `src/qmatsuite/presets/variants_registry.py:533-534` - detect时使用
- `src/qmatsuite/presets/variants_registry.py:637-638` - precision detect时使用

### 3.2 Key Ownership Registry

**位置**: `src/qmatsuite/presets/paramspace.py:360-375`

**机制**: 
- ParamSpace在`__post_init__()`时自动注册owned keys
- 只注册canonical ParamSpaces（`"magnetism"`, `"occupations_scheme"`, `"precision"`）
- Variants不注册（它们共享canonical space的keys）

**IR keys兼容性**:
- 当前所有IR keys都在ParamSpace的owned_keys中（因为v0中IR keys == QE keys）
- 未来如果IR keys改名，需要同步更新ownership registry

---

## 4. Step Type映射契约

### 4.1 映射点位置

**位置**: `src/qmatsuite/presets/variants_registry.py:245-258`

**函数**: `get_variant(dimension: str, step_type: str)`

**映射逻辑**:
```python
# Map machine_type to public_type for variant lookup
from qmatsuite.workflow.registry import get_registry
registry = get_registry()
spec = registry.get(step_type)
if spec and spec.public_type:
    step_type = spec.public_type  # Use public_type for variant lookup
```

**原因**: 
- Presets使用gen/public step types（如`"scf"`, `"nscf"`）
- Variants的`applies_to_step_types`使用public types
- 如果传入machine_type（如`"qe_scf"`），需要映射到public_type（`"scf"`）

### 4.2 映射规则

**输入**: step_type（可能是public_type或machine_type）

**处理**:
1. 尝试registry lookup
2. 如果找到spec且spec.public_type存在，使用public_type
3. 否则使用原始step_type（向后兼容）

**输出**: public_type（用于variant lookup）

---

## 5. 数据流图

### 5.1 Compile流程

```
step.yaml (QE params)
  ↓
StepDoc.load() → QE YAML dict
  ↓
qe_yaml_to_ir_yaml() → IR YAML dict
  ↓
[ParamSpaceContext] compile_profile_patch() → IR patch dict
  ↓
ir_patch_to_qe_patch() → QE patch dict
  ↓
StepDoc.apply_patch() → step.yaml (QE params)
```

### 5.2 Detect流程

```
step.yaml (QE params)
  ↓
StepDoc.load() → QE YAML dict
  ↓
qe_yaml_to_ir_yaml() → IR YAML dict
  ↓
[ParamSpaceContext] match_profile() → profile name
  ↓
PROFILE_TO_ENUM[dimension][profile_name] → enum option
```

---

## 6. 未来IR非1:1时的适配策略

### 6.1 当前假设

- IR keys == QE keys（v0等价性）
- IR sections == QE sections（v0等价性）
- 转换函数（`qe_yaml_to_ir_yaml`, `ir_patch_to_qe_patch`）主要是identity mapping

### 6.2 未来扩展点

**如果IR keys改名**（如`nspin` → `spin_polarization`）:
- 修改`IR_TO_QE_MAPPING`和`QE_TO_IR_MAPPING`
- 修改ParamSpace的ParamKey定义（key字段使用新IR key）
- 适配层自动处理转换

**如果IR sections改名**:
- 修改mapping中的section映射
- ParamSpace的ParamKey.section字段需要更新
- 适配层需要处理section转换

**关键原则**: 适配层保持ParamSpace内核不变，只修改转换函数。

---

## 7. 验证检查清单

- [x] ParamSpace内核（baac796）未修改
- [x] IR↔QE转换在单点（variants_registry.py）实现
- [x] Key access enforcement通过ParamSpaceContext生效
- [x] Step type映射在get_variant()中实现
- [x] 所有测试通过（148 passed）

