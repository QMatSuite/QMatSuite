# GEN/SPEC Step Type 分层深度 Review

**日期**: 2025-01-28  
**Reviewer**: AI Assistant  
**范围**: 全代码库 GEN/SPEC 使用和转换分析  
**目标**: 评估分层是否真正实现，转换是否发生在正确位置

---

## 执行摘要

**结论**: 代码库在 GEN/SPEC 分层方面存在**严重混乱**，虽然 constitution 定义了清晰的分层规则，但实际实现中：

1. ✅ **部分正确**: Workflow/Preset 层确实主要使用 GEN，Engine/Execution 层确实主要使用 SPEC
2. ❌ **严重问题**: 转换发生在**太多地方**，而不是在清晰的边界
3. ❌ **严重问题**: 存在大量"本应传 SPEC 但传了 GEN+engine 来合成 SPEC"的情况
4. ❌ **严重问题**: 存在大量"本应传 GEN 但直接 strip prefix 成为 GEN"的情况（其实不需要，因为已经有 `step_type_gen` 字段）
5. ❌ **严重问题**: Registry API 混乱，`StepTypeRegistry.get()` 期望 GEN，但很多地方传入 SPEC

---

## 第一部分：理想的分层架构（Constitution 定义）

### 1.1 分层规则（来自 Constitution）

| 层 | 应使用 | 示例 | 说明 |
|---|--------|------|------|
| **UI / Preset / ParamSpace / Workflow Templates** | `step_type_gen` ONLY | `"scf"`, `"relax"`, `"wannierprep"` | Engine-agnostic |
| **step.yaml / Runner / Dispatch / Execution** | `step_type_spec` ONLY | `"qe_scf"`, `"vasp_relax"`, `"w90_wannierprep"` | Engine-specific |

### 1.2 理想转换点

转换应该只发生在**两个明确的边界**：

1. **GEN → SPEC 边界**: 当从 Workflow/Preset 层进入 Execution/Persistence 层时
   - 位置：`workflow/step_factory.py` 创建 step.yaml 时
   - 方法：`spec_from(prefix, gen)`
   - 触发：`init_step(step_type_gen="scf", engine_family="qe")` → 写入 `step_type_spec="qe_scf"` 到 step.yaml

2. **SPEC → GEN 边界**: 当从 Execution/Persistence 层读取数据用于 Workflow/Preset 层时
   - 位置：`presets/integration.py` 读取 step.yaml 用于 preset detection
   - 位置：`workflow/templates.py` 读取 step.yaml 用于 workflow detection
   - 方法：`gen_from(spec)` 或 `step_type_gen_from_spec(spec)`
   - 触发：读取 `step_type_spec="qe_scf"` → 转换为 `step_type_gen="scf"` 用于 workflow/preset 匹配

### 1.3 理想的数据流

```
┌─────────────────────────────────────────────────────────────┐
│ UI/Preset/Workflow Layer (GEN only)                         │
│                                                              │
│  User: "Create SCF step"                                    │
│  → step_type_gen="scf"                                       │
│                                                              │
│  Workflow Template: ["scf", "nscf", "dos"]                  │
│  → step_type_gen="scf"                                       │
│                                                              │
│  Preset Detection: reads step.yaml                           │
│  → step_type_spec="qe_scf" (from YAML)                       │
│  → converts to step_type_gen="scf" (for matching)           │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ GEN → SPEC conversion
                          │ (only at step creation)
                          ▼
┌─────────────────────────────────────────────────────────────┐
│ Execution/Persistence Layer (SPEC only)                      │
│                                                              │
│  step.yaml: step_type_spec="qe_scf"                         │
│                                                              │
│  Engine.run_step(step): reads step_type_spec                │
│  → step_type_spec="qe_scf"                                   │
│                                                              │
│  Handler dispatch: uses step_type_spec                      │
│  → step_type_spec="qe_scf"                                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 第二部分：现实中的使用情况

### 2.1 Workflow/Preset 层使用情况

#### ✅ 正确使用 GEN 的地方

**`workflow/templates.py`**:
- `detect_workflow()`: 从 `step_type_spec` 读取，转换为 `step_type_gen` 用于 workflow 匹配 ✅
- `instantiate_workflow()`: 使用 `step_type_gen` 从 workflow template，然后 materialize 为 `step_type_spec` ✅

**`presets/integration.py`**:
- `_load_step_parameters()`: 从 `step_type_spec` 读取，转换为 `step_type_gen` 用于 receiver lookup ✅
- `apply_presets_to_step()`: 从 `step_type_spec` 读取，转换为 `step_type_gen` 用于 variant lookup ✅
- `detect_workflow_type()`: 从 `step_type_spec` 读取，转换为 `step_type_gen` ✅

**`presets/variants_registry.py`**:
- `get_variant(dimension, step_type_gen)`: 接受 `step_type_gen` ✅

#### ❌ 问题：Registry API 混乱

**`workflow/registry.py`**:
- `StepTypeRegistry.get(step_type_gen)`: **期望 GEN 类型**，但很多地方传入 SPEC
- `normalize_step_type_to_gen()`: 有 fallback 逻辑 strip prefix，但应该只使用 `gen_from()`

**问题代码**:
```python
# workflow/registry.py:833-867
def normalize_step_type_to_gen(step_type_spec: str) -> str:
    # ...
    # Fallback: strip known engine prefixes (e.g., "qe_vc-relax" -> "vc-relax")
    ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")
    lower = normalized.lower()
    for prefix in ENGINE_PREFIXES:
        if lower.startswith(prefix):
            return normalized[len(prefix):]  # ❌ 直接 strip，应该用 gen_from()
```

**问题**: 这个函数有复杂的 fallback 逻辑，应该只使用 `gen_from()` 进行纯字符串转换。

---

### 2.2 Engine/Execution 层使用情况

#### ✅ 正确使用 SPEC 的地方

**`engine/pyscf_engine.py`**:
- `run_step_with_chain()`: 从 `step.yaml` 读取 `step_type_spec` ✅

**`engine/orca_engine.py`**:
- `run_step_with_chain()`: 从 `step.yaml` 读取 `step_type_spec` ✅

**`execution/relax_artifacts.py`**:
- `write_generated_structure()`: 接受 `step_type_spec` 参数 ✅

**`execution/handlers.py`**:
- `get_handler_for_step(step_type_spec)`: 接受 SPEC 类型 ✅

**`execution/verification.py`**:
- `evaluate_step_result(step_type_spec)`: 接受 SPEC 类型 ✅

#### ❌ 问题：Execution 层内部还在做转换

**`execution/recipes.py`**:
```python
# execution/recipes.py:54-75
def verify_qc_topology(steps: List["Step"], registry) -> None:
    for i, step in enumerate(steps):
        # Get step type - prefer step_type_gen, fallback to step_type_spec
        step_type_gen = getattr(step, 'step_type_gen', None)
        if not step_type_gen:
            # If no step_type_gen, try to extract from step_type_spec
            step_type_spec = getattr(step, 'step_type_spec', None)
            if step_type_spec:
                # Convert SPEC to GEN for registry lookup
                from quantumvitas.api.utils import step_type_gen_from_spec
                step_type_gen = step_type_gen_from_spec(step_type_spec)  # ❌ 转换发生在 execution 层内部
```

**问题**: Execution 层应该只使用 `step_type_spec`，不应该做转换。如果 Step 对象没有 `step_type_gen`，说明它不应该在 execution 层使用。

**`execution/reference_resolver.py`**:
```python
# execution/reference_resolver.py:75-97
def get_gen_type(step: Any, registry: Optional[StepTypeRegistry] = None) -> Optional[str]:
    step_type = getattr(step, 'step_type_spec', None)
    if not step_type:
        return None

    spec = registry.get(str(step_type))  # ❌ registry.get() 期望 GEN，但传入的是 SPEC
    if spec:
        return spec.step_type_gen
    return str(step_type)  # ❌ Fallback 返回 SPEC 类型
```

**问题**: 
1. `registry.get()` 期望 GEN 类型，但传入的是 `step_type_spec`（SPEC）
2. 这个函数在 execution 层，但返回 GEN 类型，说明它被 workflow/preset 层调用

---

### 2.3 API/Service 层使用情况

#### ❌ 严重问题：API 层混合使用 GEN 和 SPEC

**`api/service.py`**:
```python
# api/service.py:2687-2691
# Convert spec to gen for get_default_step_params (which expects gen type)
from quantumvitas.api.utils import step_type_gen_from_spec
step_type_gen = step_type_gen_from_spec(step_type_spec)

# Get defaults for step type (using gen type)
defaults = get_default_step_params(step_type_gen)
```

**问题**: API 层在内部做转换，说明函数签名不一致。

```python
# api/service.py:6985-6991
from quantumvitas.api.utils import is_step_type_spec, step_type_spec_from_gen
if is_step_type_spec(machine_step_type):
    step_type_spec_value = machine_step_type  # Already SPEC
else:
    # It's GEN, convert to SPEC using engine_family
    engine_prefix = engine_family if engine_family else "qe"  # Default to qe if no engine_family
    step_type_spec_value = step_type_spec_from_gen(engine_prefix, machine_step_type)  # ❌ 本应传 SPEC，但传了 GEN+engine
```

**问题**: `init_step()` 应该只接受 `step_type_gen`，然后在内部转换为 SPEC。但这里接受 `machine_step_type`（可能是 GEN 或 SPEC），然后做转换。

**`api/service.py:7547-7561`**:
```python
@staticmethod
def get_default_step_params(step_type_gen: str) -> dict[str, Any]:
    """
    Args:
        step_type_gen: Step type (e.g., "scf", "nscf" - gen type, or "qe_scf", "qe_nscf" - spec type, accepts both)  # ❌ 接受两者
    """
```

**问题**: 函数签名说接受 `step_type_gen`，但文档说"accepts both"，这是不一致的。

---

### 2.4 Calculation 层使用情况

#### ❌ 问题：Calculation 层混合使用

**`calculation/calculation.py`**:
```python
# calculation/calculation.py:559-561
from quantumvitas.workflow.step_type_convert import is_spec, gen_from
if is_spec(step_type_spec):
    # Already spec type, skip materialization
```

**问题**: Calculation 层在检查是否是 SPEC，说明它可能收到 GEN 类型。

**`calculation/step_defaults.py`**:
```python
# calculation/step_defaults.py:229-233
from quantumvitas.workflow.step_type_convert import gen_from, is_spec

# Convert to gen type if spec type provided (backward compatibility)
if is_spec(step_type_gen):  # ❌ 参数名是 step_type_gen，但可能是 SPEC
    step_type_gen = gen_from(step_type_gen)
```

**问题**: 函数参数名是 `step_type_gen`，但实际可能传入 SPEC，需要转换。这说明调用方混乱。

---

## 第三部分：转换发生的位置分析

### 3.1 GEN → SPEC 转换位置

#### ✅ 正确的转换位置

1. **`workflow/step_factory.py`**: 创建 step.yaml 时
   ```python
   # workflow/step_factory.py:47-48
   from quantumvitas.workflow.step_type_convert import spec_from
   step_type_spec = spec_from(prefix, step_type_gen)
   ```

2. **`api/service.py:6991`**: `init_step()` 内部
   ```python
   step_type_spec_value = step_type_spec_from_gen(engine_prefix, machine_step_type)
   ```

#### ❌ 不应该发生的转换

1. **`engine/lammps_writer.py:67-74`**: Engine writer 内部
   ```python
   def get_template_for_step_type(step_type_gen: str) -> str:
       # Convert gen to spec for template lookup
       from quantumvitas.workflow.step_type_convert import spec_from, is_spec
       if is_spec(step_type_gen):  # ❌ 参数名是 step_type_gen，但可能是 SPEC
           step_type_spec = step_type_gen
       else:
           step_type_spec = spec_from("lammps", step_type_gen)  # ❌ 本应传 SPEC，但传了 GEN+engine
   ```

   **问题**: 
   - 函数签名说接受 `step_type_gen`，但内部检查是否是 SPEC
   - 如果传入 GEN，需要知道 engine prefix 来合成 SPEC，但 engine 信息应该已经在 `step_type_spec` 中

2. **`drivers/qe/engine/qe_calculation.py:227-228`**: QE calculation runner
   ```python
   step_type_gen_detected = self.detect_step_type(input_file)
   from quantumvitas.workflow.step_type_convert import spec_from
   step_type_spec = spec_from("qe", step_type_gen_detected)  # ❌ 本应传 SPEC，但传了 GEN+engine
   ```

   **问题**: `detect_step_type()` 返回 GEN，然后合成 SPEC。但调用方应该直接传入 SPEC。

---

### 3.2 SPEC → GEN 转换位置

#### ✅ 正确的转换位置

1. **`presets/integration.py:314-320`**: 读取 step.yaml 用于 preset detection
   ```python
   step_type_spec = doc.get(["step_type_spec"], default="scf")
   # Convert SPEC to GEN for receiver registry lookup (receivers use GEN types)
   step_type_gen = get_step_type_gen(step_type_spec)
   ```

2. **`workflow/templates.py:328-334`**: 读取 step.yaml 用于 workflow detection
   ```python
   if is_step_type_spec(step_type):
       step_type_gen = step_type_gen_from_spec(step_type)
   ```

#### ❌ 不应该发生的转换

1. **`execution/reference_resolver.py:89-97`**: Execution 层内部
   ```python
   def get_gen_type(step: Any, registry: Optional[StepTypeRegistry] = None) -> Optional[str]:
       step_type = getattr(step, 'step_type_spec', None)
       spec = registry.get(str(step_type))  # ❌ registry.get() 期望 GEN，但传入 SPEC
   ```

   **问题**: 
   - Execution 层不应该返回 GEN 类型
   - 如果 workflow/preset 层需要 GEN，应该在读取 step.yaml 时转换，而不是在 execution 层

2. **`execution/recipes.py:62-63`**: Execution 层内部
   ```python
   from quantumvitas.api.utils import step_type_gen_from_spec
   step_type_gen = step_type_gen_from_spec(step_type_spec)  # ❌ 转换发生在 execution 层
   ```

   **问题**: Execution 层应该只使用 `step_type_spec`，不应该转换为 GEN。

3. **`calculation/verification.py:99-104`**: Verification 层内部
   ```python
   step_type_str = step_type_spec.lower() if step_type_spec else ""
   # Strip engine prefix if present (e.g., "w90_wannierprep" -> "wannierprep")
   if "_" in step_type_str:
       step_type_gen = step_type_str.split("_", 1)[1]  # ❌ 直接 strip，应该用 gen_from()
   ```

   **问题**: 
   - 函数参数是 `step_type_spec`，但内部 strip prefix 得到 GEN
   - 应该使用 `gen_from()` 而不是手动 split

---

## 第四部分：关键问题分析

### 4.1 问题：本应传 SPEC，但传了 GEN+engine 来合成 SPEC

**发现的位置**:

1. **`engine/lammps_writer.py:74`**:
   ```python
   step_type_spec = spec_from("lammps", step_type_gen)  # ❌ 函数接受 step_type_gen，但需要 engine prefix
   ```

2. **`drivers/qe/engine/qe_calculation.py:228`**:
   ```python
   step_type_spec = spec_from("qe", step_type_gen_detected)  # ❌ detect_step_type() 返回 GEN，然后合成 SPEC
   ```

3. **`api/service.py:6991`**:
   ```python
   step_type_spec_value = step_type_spec_from_gen(engine_prefix, machine_step_type)  # ❌ 接受 GEN，然后合成 SPEC
   ```

**根本原因**: 
- 函数签名接受 `step_type_gen`，但实际需要 `step_type_spec`
- 调用方传入 GEN，函数内部需要知道 engine prefix 来合成 SPEC
- 但 engine prefix 应该已经在 `step_type_spec` 中

**正确做法**: 
- 函数应该直接接受 `step_type_spec`
- 如果调用方有 GEN，应该在调用前转换为 SPEC（使用 `spec_from(prefix, gen)`）

---

### 4.2 问题：本应传 GEN，但直接 strip prefix 成为 GEN（其实不需要）

**发现的位置**:

1. **`execution/reference_resolver.py:93-97`**:
   ```python
   spec = registry.get(str(step_type))  # step_type 是 step_type_spec
   if spec:
       return spec.step_type_gen
   return str(step_type)  # ❌ Fallback 返回 SPEC 类型（应该是 GEN）
   ```

2. **`calculation/verification.py:101-104`**:
   ```python
   if "_" in step_type_str:
       step_type_gen = step_type_str.split("_", 1)[1]  # ❌ 直接 strip，应该用 gen_from()
   ```

3. **`workflow/registry.py:860-865`**:
   ```python
   # Fallback: strip known engine prefixes
   ENGINE_PREFIXES = ("qe_", "pyscf_", "orca_", "vasp_", "lammps_", "cp2k_", "w90_")
   for prefix in ENGINE_PREFIXES:
       if lower.startswith(prefix):
           return normalized[len(prefix):]  # ❌ 直接 strip，应该用 gen_from()
   ```

**根本原因**: 
- Step 对象已经有 `step_type_gen` 字段，不需要从 `step_type_spec` strip
- 如果 Step 对象没有 `step_type_gen`，说明它不应该在需要 GEN 的层使用
- 手动 strip prefix 容易出错（hardcoded prefix list）

**正确做法**: 
- 如果 Step 对象有 `step_type_gen`，直接使用
- 如果没有，说明不应该在这个层使用，应该报错
- 如果必须转换，使用 `gen_from()` 而不是手动 strip

---

### 4.3 问题：Registry API 混乱

**`StepTypeRegistry.get(step_type_gen)` 期望 GEN，但很多地方传入 SPEC**:

1. **`execution/reference_resolver.py:56, 93`**:
   ```python
   spec = registry.get(str(step_type))  # step_type 是 step_type_spec (SPEC)
   ```

2. **`workflow/registry.py:856`**:
   ```python
   spec = registry.get(normalized)  # normalized 可能是 SPEC（如果 normalize_step_type_to_gen 失败）
   ```

3. **`presets/integration.py:486`**:
   ```python
   spec = registry.get(step_type_spec_from_doc)  # step_type_spec_from_doc 是 SPEC
   ```

**根本原因**: 
- `StepTypeRegistry.get()` 的文档说接受 GEN，但实现可能接受 SPEC（通过 fallback）
- 调用方不清楚应该传什么类型

**正确做法**: 
- `StepTypeRegistry.get()` 应该只接受 GEN，如果传入 SPEC 应该报错
- 或者添加 `get_by_spec(step_type_spec)` 方法，内部转换为 GEN 再 lookup

---

### 4.4 问题：函数参数名和实际类型不一致

**发现的位置**:

1. **`calculation/step_defaults.py:229`**:
   ```python
   def get_default_step_params(step_type_gen: str) -> dict[str, Any]:
       # Convert to gen type if spec type provided (backward compatibility)
       if is_spec(step_type_gen):  # ❌ 参数名是 step_type_gen，但可能是 SPEC
   ```

2. **`engine/lammps_writer.py:56`**:
   ```python
   def get_template_for_step_type(step_type_gen: str) -> str:
       if is_spec(step_type_gen):  # ❌ 参数名是 step_type_gen，但可能是 SPEC
   ```

3. **`api/service.py:7547`**:
   ```python
   def get_default_step_params(step_type_gen: str) -> dict[str, Any]:
       # Args: step_type_gen: Step type (e.g., "scf", "nscf" - gen type, or "qe_scf", "qe_nscf" - spec type, accepts both)  # ❌ 接受两者
   ```

**根本原因**: 
- 函数参数名暗示类型，但实际接受两种类型
- 调用方不清楚应该传什么类型

**正确做法**: 
- 函数应该只接受一种类型（GEN 或 SPEC）
- 如果必须接受两者，参数名应该改为 `step_type`，并在文档中明确说明

---

## 第五部分：转换应该发生在哪里（理想架构）

### 5.1 GEN → SPEC 转换边界

**唯一正确的转换点**:

1. **`workflow/step_factory.py`**: 创建 step.yaml 时
   - 输入：`step_type_gen="scf"`, `engine_family="qe"`
   - 转换：`step_type_spec = spec_from("qe", "scf")` → `"qe_scf"`
   - 输出：写入 `step_type_spec="qe_scf"` 到 step.yaml

2. **`api/service.py:init_step()`**: API 层创建 step 时
   - 输入：`step_type_gen="scf"`, `engine_family="qe"`
   - 转换：`step_type_spec = spec_from("qe", "scf")` → `"qe_scf"`
   - 输出：写入 `step_type_spec="qe_scf"` 到 step.yaml

**不应该发生的转换**:
- ❌ Engine writer 内部（应该直接接受 SPEC）
- ❌ Calculation runner 内部（应该直接接受 SPEC）
- ❌ 任何需要 engine prefix 来合成 SPEC 的地方（说明应该直接传 SPEC）

---

### 5.2 SPEC → GEN 转换边界

**唯一正确的转换点**:

1. **`presets/integration.py:_load_step_parameters()`**: 读取 step.yaml 用于 preset detection
   - 输入：从 step.yaml 读取 `step_type_spec="qe_scf"`
   - 转换：`step_type_gen = gen_from("qe_scf")` → `"scf"`
   - 输出：用于 receiver registry lookup（GEN 类型）

2. **`workflow/templates.py:detect_workflow()`**: 读取 step.yaml 用于 workflow detection
   - 输入：从 step.yaml 读取 `step_type_spec="qe_scf"`
   - 转换：`step_type_gen = gen_from("qe_scf")` → `"scf"`
   - 输出：用于 workflow template matching（GEN 类型）

**不应该发生的转换**:
- ❌ Execution 层内部（应该只使用 SPEC）
- ❌ Verification 层内部（应该只使用 SPEC）
- ❌ 任何在 execution 层返回 GEN 的函数（说明应该在读取时转换）

---

## 第六部分：现实是否混乱？

### 6.1 混乱程度评估

**严重混乱** ⚠️⚠️⚠️

**证据**:

1. **转换发生在太多地方** (20+ 处)
   - 理想：2 个边界（GEN→SPEC, SPEC→GEN）
   - 现实：20+ 处转换，分布在各个层

2. **函数参数类型不一致** (10+ 处)
   - 参数名是 `step_type_gen`，但可能接受 SPEC
   - 参数名是 `step_type_spec`，但可能接受 GEN

3. **Registry API 混乱** (5+ 处)
   - `StepTypeRegistry.get()` 期望 GEN，但很多地方传入 SPEC
   - 需要 fallback 逻辑来处理 SPEC 输入

4. **手动 strip prefix** (3+ 处)
   - 应该使用 `gen_from()`，但手动 split
   - Hardcoded prefix list，容易出错

5. **本应传 SPEC 但传了 GEN+engine** (3+ 处)
   - 函数接受 GEN，但需要 engine prefix 来合成 SPEC
   - 说明函数应该直接接受 SPEC

6. **本应传 GEN 但直接 strip** (3+ 处)
   - Step 对象已经有 `step_type_gen` 字段
   - 不需要从 `step_type_spec` strip

---

### 6.2 混乱的根本原因

1. **历史遗留**: 代码在迁移过程中，有些地方已经更新，有些地方还没有
2. **缺乏清晰的边界**: 没有明确的"转换层"，转换散布在各个模块
3. **Registry API 设计问题**: `StepTypeRegistry.get()` 应该只接受 GEN，但实现允许 SPEC（通过 fallback）
4. **函数签名不一致**: 参数名暗示类型，但实际接受两种类型
5. **Step 对象设计问题**: Step 对象同时有 `step_type_gen` 和 `step_type_spec`，导致调用方不清楚应该用哪个

---

## 第七部分：具体问题清单

### 7.1 必须修复的问题（高优先级）

#### P1: Registry API 混乱
- **位置**: `workflow/registry.py:613`
- **问题**: `StepTypeRegistry.get(step_type_gen)` 期望 GEN，但很多地方传入 SPEC
- **影响**: 调用方不清楚应该传什么类型
- **修复**: 
  - 选项 A: `get()` 只接受 GEN，如果传入 SPEC 报错
  - 选项 B: 添加 `get_by_spec(step_type_spec)` 方法

#### P2: 函数参数类型不一致
- **位置**: `calculation/step_defaults.py:229`, `engine/lammps_writer.py:56`, `api/service.py:7547`
- **问题**: 参数名是 `step_type_gen`，但可能接受 SPEC
- **影响**: 调用方不清楚应该传什么类型
- **修复**: 函数应该只接受一种类型，或参数名改为 `step_type`

#### P3: Execution 层内部做转换
- **位置**: `execution/recipes.py:62`, `execution/reference_resolver.py:89`
- **问题**: Execution 层应该只使用 SPEC，但内部转换为 GEN
- **影响**: 违反分层原则
- **修复**: 如果 Step 对象没有 `step_type_gen`，应该报错，而不是转换

#### P4: 本应传 SPEC 但传了 GEN+engine
- **位置**: `engine/lammps_writer.py:74`, `drivers/qe/engine/qe_calculation.py:228`
- **问题**: 函数接受 GEN，但需要 engine prefix 来合成 SPEC
- **影响**: 函数应该直接接受 SPEC
- **修复**: 函数签名改为接受 `step_type_spec`，调用方在调用前转换

#### P5: 手动 strip prefix
- **位置**: `workflow/registry.py:860-865`, `calculation/verification.py:101-104`
- **问题**: 应该使用 `gen_from()`，但手动 split
- **影响**: Hardcoded prefix list，容易出错
- **修复**: 使用 `gen_from()` 替代手动 split

---

### 7.2 应该修复的问题（中优先级）

#### M1: Step 对象同时有 `step_type_gen` 和 `step_type_spec`
- **问题**: 调用方不清楚应该用哪个
- **影响**: 导致混乱
- **修复建议**: 
  - Workflow/Preset 层：只使用 `step_type_gen`
  - Execution/Persistence 层：只使用 `step_type_spec`
  - 如果 Step 对象在错误的层使用，应该报错

#### M2: API 层混合使用 GEN 和 SPEC
- **位置**: `api/service.py` 多处
- **问题**: API 层在内部做转换
- **影响**: API 层应该只接受 GEN（因为它是 UI 层）
- **修复建议**: API 层函数应该只接受 GEN，内部转换为 SPEC 后调用 kernel

---

### 7.3 可以改进的问题（低优先级）

#### L1: 转换函数使用不一致
- **问题**: 有些地方用 `gen_from()`，有些地方用 `step_type_gen_from_spec()`
- **影响**: 代码不一致
- **修复建议**: 统一使用 `gen_from()` 和 `spec_from()`

#### L2: 文档不清晰
- **问题**: 函数文档说"accepts both"，但参数名暗示单一类型
- **影响**: 调用方不清楚应该传什么类型
- **修复建议**: 文档应该明确说明接受的类型

---

## 第八部分：修复建议

### 8.1 短期修复（不改变架构）

1. **统一转换函数使用**
   - 所有 SPEC→GEN 转换使用 `gen_from()`
   - 所有 GEN→SPEC 转换使用 `spec_from(prefix, gen)`
   - 移除手动 strip prefix 的代码

2. **修复函数参数类型**
   - 如果函数只接受 GEN，参数名改为 `step_type_gen`，内部不检查 SPEC
   - 如果函数只接受 SPEC，参数名改为 `step_type_spec`，内部不检查 GEN
   - 如果函数接受两者，参数名改为 `step_type`，文档明确说明

3. **修复 Registry API**
   - `StepTypeRegistry.get()` 只接受 GEN，如果传入 SPEC 报错
   - 添加 `get_by_spec(step_type_spec)` 方法用于 SPEC lookup

---

### 8.2 长期修复（重构架构）

1. **明确转换边界**
   - 创建 `workflow/step_factory.py` 作为唯一的 GEN→SPEC 转换点
   - 创建 `presets/integration.py` 和 `workflow/templates.py` 作为唯一的 SPEC→GEN 转换点
   - 其他层不应该做转换

2. **Step 对象设计**
   - Workflow/Preset 层的 Step 对象：只有 `step_type_gen`
   - Execution/Persistence 层的 Step 对象：只有 `step_type_spec`
   - 如果需要在不同层之间传递，在边界处转换

3. **API 层设计**
   - API 层函数只接受 GEN（因为它是 UI 层）
   - API 层内部转换为 SPEC 后调用 kernel
   - Kernel 层函数只接受 SPEC

---

## 第九部分：总结

### 9.1 分层实现情况

| 层 | 理想 | 现实 | 评估 |
|---|------|------|------|
| **UI/Preset/Workflow** | 只用 GEN | 主要用 GEN，但内部有转换 | ⚠️ 部分正确 |
| **Execution/Persistence** | 只用 SPEC | 主要用 SPEC，但内部有转换 | ⚠️ 部分正确 |
| **转换边界** | 2 个清晰边界 | 20+ 处转换 | ❌ 严重混乱 |

### 9.2 关键发现

1. ✅ **部分正确**: Workflow/Preset 层确实主要使用 GEN，Engine/Execution 层确实主要使用 SPEC
2. ❌ **严重问题**: 转换发生在太多地方，而不是在清晰的边界
3. ❌ **严重问题**: 存在大量"本应传 SPEC 但传了 GEN+engine 来合成 SPEC"的情况
4. ❌ **严重问题**: 存在大量"本应传 GEN 但直接 strip prefix 成为 GEN"的情况（其实不需要）
5. ❌ **严重问题**: Registry API 混乱，`StepTypeRegistry.get()` 期望 GEN，但很多地方传入 SPEC

### 9.3 混乱程度

**严重混乱** ⚠️⚠️⚠️

虽然 constitution 定义了清晰的分层规则，但实际实现中：
- 转换发生在 20+ 处，而不是 2 个清晰边界
- 函数参数类型不一致（10+ 处）
- Registry API 混乱（5+ 处）
- 手动 strip prefix（3+ 处）

### 9.4 修复优先级

1. **高优先级**: Registry API 混乱、函数参数类型不一致、Execution 层内部做转换
2. **中优先级**: Step 对象设计、API 层混合使用
3. **低优先级**: 转换函数使用不一致、文档不清晰

---

**End of Review**

