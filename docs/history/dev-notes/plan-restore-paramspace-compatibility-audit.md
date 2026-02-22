# ParamSpace 恢复兼容性审计报告

**日期**: 2025-01-XX  
**目的**: 对比旧救援链（baac796/b4a7b0f）与当前HEAD，评估"直接置换ParamSpace回旧版"对IR层、runner、step_type(gen/spec)、compile顺序、StepDoc的影响，并给出最小落地方案。

**审计原则**: 只review，不改代码。提供代码证据和接口契约分析。

---

## 0) 基线信息

### 当前HEAD
- **SHA**: `1793134142275bc707b800c6086b225e53f5312e`
- **分支**: `v2-python`

### 旧基线
- **baac796**: "Implement key access enforcement for ParamSpace: Introduced a comprehensive key-access enforcement mechanism in accordance with Constitution 10.8.9"
- **b4a7b0f**: "Merge ParamSpace Constitution into global framework: Introduced a comprehensive section on ParamSpace, detailing the Single-writer principle, unified responsibilities for Detect, Preset Apply, and Invariant Enforcement"

### 对比命令摘要
```bash
# 文件变更统计
git diff --name-status baac796..HEAD

# ParamSpace核心模块对比
git diff baac796..HEAD -- src/qmatsuite/presets/paramspace.py
git diff baac796..HEAD -- src/qmatsuite/presets/variants_registry.py
git diff baac796..HEAD -- src/qmatsuite/presets/integration.py

# IR层存在性检查
git ls-tree -r baac796 --name-only | grep -E "(ir|IR)"
git show baac796:src/qmatsuite/presets/paramspace.py | head -200

# 关键接口搜索
rg -n "ir_|qe_yaml_to_ir|IR_TO_QE|StepDoc|GeneralizedStep|public_type|machine_type|apply_invariants|oracle" -S src/qmatsuite
```

---

## 1) IR层：当时 vs 现在

### 1.1 当时（baac796时代）IR是否存在？

**答案**: ❌ **NO - IR层在baac796时代不存在**

**证据**:
1. **文件系统检查**: `git ls-tree -r baac796 --name-only | grep -E "(ir|IR)"` 返回结果中没有IR相关文件
2. **ParamSpace实现**: `git show baac796:src/qmatsuite/presets/paramspace.py` 显示ParamSpace直接操作QE参数（section/key），没有IR转换层
3. **ParamKey定义**: 旧版ParamKey的`key`字段注释为"Parameter key name (lowercase canonical)"，没有提到IR概念

**结论**: baac796时代，ParamSpace直接操作QE参数（如`SYSTEM.nspin`），没有IR中间层。

### 1.2 现在IR层的边界在哪里？

**答案**: IR层已完全实现，边界清晰。

**证据位置**:
- `src/qmatsuite/ir/parameters.py`: IR参数定义（IRParameter dataclass）
- `src/qmatsuite/ir/backends/qe/mapping.py`: IR↔QE映射表（IR_TO_QE_MAPPING, QE_TO_IR_MAPPING）
- `src/qmatsuite/presets/variants_registry.py:311-343`: 编译流程中的IR转换

**关键发现**:

#### 1.2.1 ParamSpace编译输出的是什么？

**答案**: ParamSpace编译输出**IR patch**，然后通过`ir_patch_to_qe_patch()`转换为QE patch。

**证据**: `src/qmatsuite/presets/variants_registry.py:311-343`
```python
# 标准ParamSpace编译
# 转换 QE YAML → IR YAML 在编译前（ParamSpace操作IR keys）
from qmatsuite.ir.backends.qe.mapping import qe_yaml_to_ir_yaml, ir_patch_to_qe_patch
ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")

ir_patch, deletions = compile_profile_patch(
    variant.space, profile_name, ir_yaml, explicit_defaults=explicit_defaults
)

# 转换 IR patch → QE patch（ParamSpace产生IR keys，但step.yaml需要QE keys）
patch = ir_patch_to_qe_patch(ir_patch)
```

**结论**: ParamSpace内部操作IR keys，输出IR patch，然后在YAML I/O边界转换为QE参数。

#### 1.2.2 IR → QE参数是否仍为1:1 string mapping？

**答案**: ✅ **YES - 当前是1:1映射**

**证据**: `src/qmatsuite/ir/backends/qe/mapping.py:16-44`
```python
IR_TO_QE_MAPPING: Dict[str, Tuple[str, str, str]] = {
    "nspin": ("pw", "SYSTEM", "nspin"),
    "ecutwfc": ("pw", "SYSTEM", "ecutwfc"),
    "K_POINTS": ("pw", "cards", "K_POINTS"),
    # ... 所有映射都是1:1
}
```

**结论**: v0阶段，IR keys与QE keys基本同名（如`nspin`→`nspin`），映射是机械的1:1查找表。

#### 1.2.3 runner消费的是IR还是engine params？

**答案**: runner消费**engine params**（QE parameters），不消费IR。

**证据**: `src/qmatsuite/calculation/runner.py:132-480`
- runner读取`step.yaml`的`parameters`字段（QE格式）
- 没有IR相关的读取逻辑
- `src/qmatsuite/workflow/step_factory.py:106-118`显示`step.yaml`存储的是QE parameters

**结论**: runner完全独立于IR层，只消费已落盘的QE parameters。

---

## 2) "直接置换ParamSpace回旧版"对IR的影响：只是string match还是有结构性耦合？

### 2.1 ParamSpace与IR的契约点

**核心问题**: 旧版ParamSpace直接操作QE参数，新版ParamSpace操作IR参数。置换后会不会破坏IR层？

#### 接口对比表

| 接口点 | baac796 行为/类型 | HEAD 行为/类型 | 是否兼容 | 不兼容原因 |
|--------|------------------|----------------|----------|-----------|
| **ParamKey.key字段** | QE参数名（如`"nspin"`） | IR参数名（概念上IR，但v0中与QE同名） | ⚠️ **部分兼容** | 语义不同：旧版是"QE key"，新版是"IR key"（虽然值相同） |
| **compile_profile_patch()输入** | QE YAML dict | IR YAML dict（通过`qe_yaml_to_ir_yaml()`转换） | ❌ **不兼容** | 旧版直接接受QE YAML，新版需要IR YAML |
| **compile_profile_patch()输出** | QE patch dict | IR patch dict（需通过`ir_patch_to_qe_patch()`转换） | ❌ **不兼容** | 旧版直接输出QE patch，新版输出IR patch |
| **match_profile()输入** | QE YAML dict | IR YAML dict（通过`qe_yaml_to_ir_yaml()`转换） | ❌ **不兼容** | 旧版直接接受QE YAML，新版需要IR YAML |
| **ParamKey.section** | QE section（如`"SYSTEM"`） | QE section（v0中IR section == QE section） | ✅ **兼容** | v0阶段IR section与QE section相同 |
| **NOT_APPLICABLE/WILDCARD/DEFAULT语义** | 相同 | 相同 | ✅ **兼容** | Cell类型语义未变 |
| **key ownership enforcement** | ✅ 存在（`register_paramspace()`, `check_key_access()`） | ❌ **已删除** | ⚠️ **部分兼容** | 旧版有key ownership，新版已移除 |

#### 重点检查项

**1. ParamKey的表示（section/key/canonicalizer）是否一致？**

**答案**: ⚠️ **部分一致，但语义不同**

- `section`: 一致（都是QE section，如`"SYSTEM"`）
- `key`: **语义不同** - 旧版是"QE key"，新版是"IR key"（虽然v0中值相同）
- `canonicalizer`: 一致（解析逻辑相同）

**证据**: 
- 旧版注释: `key: Parameter key name (lowercase canonical)`
- 新版注释: `key: IR parameter key name (conceptually IR, but values same as QE in v0)`

**2. NOT_APPLICABLE/WILDCARD/DEFAULT的语义是否一致？**

**答案**: ✅ **完全一致**

**证据**: `CellType`枚举和`Cell`类定义在旧版和新版中完全相同。

**3. key ownership enforcement对现有IR mapping会不会报错？**

**答案**: ⚠️ **潜在问题**

**分析**:
- 旧版有`register_paramspace()`和`check_key_access()`机制，限制每个ParamSpace只能访问其拥有的keys
- 新版已删除此机制（`git diff`显示删除了163行key access enforcement代码）
- 如果恢复旧版ParamSpace，会重新引入key ownership enforcement

**潜在冲突**:
- IR层可能引入新的IR keys（不在旧版ParamSpace的owned_keys中）
- 如果IR mapping新增了keys，但旧版ParamSpace的ownership registry未注册，`check_key_access()`会报`KeyAccessError`

**证据**: 旧版代码（baac796）:
```python
def check_key_access(section: str, key: str, allow_oracle: bool = False) -> None:
    # ... 检查当前ParamSpace是否拥有该key
    if (section, key) not in owned:
        raise KeyAccessError(...)
```

### 2.2 结论：置换后会不会"只要字符串一样就行"？

**答案**: ❌ **B) 还有结构性坑**

**原因清单**:

1. **输入输出格式不兼容**:
   - 旧版`compile_profile_patch()`接受QE YAML，输出QE patch
   - 新版调用链期望IR YAML输入，IR patch输出
   - 如果直接置换，需要在调用点插入`qe_yaml_to_ir_yaml()`和`ir_patch_to_qe_patch()`转换

2. **key ownership enforcement回归**:
   - 旧版有key ownership机制，新版已删除
   - 如果恢复，需要确保所有IR keys都在ownership registry中注册
   - 否则`check_key_access()`会在IR转换时报错

3. **ParamKey.key字段语义变化**:
   - 虽然v0中IR keys与QE keys同名，但语义不同
   - 旧版代码可能假设`key`是QE key，新版假设是IR key
   - 需要检查所有使用`ParamKey.key`的地方

4. **写入路径未变**:
   - 最终写入`step.yaml`的路径相同（`parameters`字段）
   - 这部分兼容

**最小适配需求**:
- 在`variants_registry.py`的调用点插入IR↔QE转换适配层
- 确保key ownership registry包含所有IR keys
- 或者：禁用key ownership enforcement（如果IR层不需要）

---

## 3) Runner：是否只跟IR有关？ParamSpace置换会不会影响运行时？

### 3.1 Runner参数消费链路

**完整调用链**:
```
CalculationRunner.run()
  → Step.run(engine, ...)
  → 读取 step.yaml (StepDoc.load())
  → step.yaml["parameters"] (QE parameters, 已落盘)
  → Engine.write_input_file(parameters)
  → 生成 QE input 文件
```

**关键发现**:

1. **Runner何时读取参数？**
   - 执行时读取，从`step.yaml`文件读取
   - 不运行时重新apply preset/paramspace

2. **从哪里读取？**
   - 从`step.yaml`的`parameters`字段读取
   - 格式：QE parameters（`{SYSTEM: {nspin: 2, ...}, ELECTRONS: {...}}`）

3. **是否会运行时重新apply preset/paramspace？**
   - ❌ **不会** - runner只消费已落盘的参数
   - preset apply发生在step创建/修改时（`apply_presets_to_step()`），不在运行时

**证据**: `src/qmatsuite/calculation/runner.py:132-480`
- runner加载calculation和steps
- 对每个step，调用`step.run(engine, ...)`
- `step.run()`读取`step.spec.parameters`（已落盘的QE parameters）

### 3.2 ParamSpace变化是否会改变runner的输入结构/字段名？

**答案**: ❌ **不会**

**原因**:
- runner读取的是`step.yaml`的`parameters`字段
- 无论ParamSpace内部如何变化（QE直接操作 vs IR转换），最终写入`step.yaml`的格式都是QE parameters
- `step.yaml`的schema未变：`{parameters: {SYSTEM: {...}, ELECTRONS: {...}}, cards: {...}}`

**证据**: `src/qmatsuite/workflow/step_factory.py:106-118`
- `step.yaml`存储的是QE parameters（不是IR）
- IR只是中间态，在YAML I/O边界转换

### 3.3 结论

**答案**: ✅ **ParamSpace置换对runner是0影响**

**原因**:
- runner完全独立于ParamSpace和IR层
- runner只消费已落盘的`step.yaml`（QE格式）
- ParamSpace的变化只影响preset apply/detect阶段，不影响运行时

---

## 4) Step SSOT：当时 vs 现在（qe-only → gen/spec 分化）

### 4.1 当时step_type是什么？

**答案**: baac796时代是**qe-only step_type**（没有gen/spec分化）

**证据**:
- `git show baac796:src/qmatsuite/presets/integration.py`显示`step_type`是简单字符串（如`"scf"`, `"nscf"`）
- 没有`public_type`/`machine_type`概念
- `ParamSpaceVariant.applies_to_step_types`使用简单字符串集合（如`frozenset({"scf", "nscf"})`）

**StepDoc/Step YAML当时step_type字段存什么？**

**答案**: 存储qe-only step_type（如`"scf"`, `"qe_scf"`可能不存在）

**证据**: 需要检查旧版step_factory，但根据代码演进历史，baac796时代应该是简单字符串。

### 4.2 现在step体系是什么？

**答案**: 现在有**gen/spec分化**（public_type vs machine_type）

**证据**: `src/qmatsuite/workflow/registry.py:24-50`
```python
@dataclass(frozen=True)
class StepTypeSpec:
    id: str  # Public type (for backward compatibility)
    machine_type: str  # Machine type (engine-prefixed, used in step.yaml)
    public_type: str  # Public type (alias for id)
    engine: str
    # ...
```

**gen step（public_type）与spec step（machine_type）如何定义？**

- **public_type**: 通用step类型（如`"scf"`, `"nscf"`），用于API/UI
- **machine_type**: 引擎特定step类型（如`"qe_scf"`, `"w90_run"`），用于`step.yaml`存储

**证据**: `src/qmatsuite/workflow/step_factory.py:48-55`
```python
# Phase 2: Normalize step_type to machine_type for step.yaml
# step.yaml stores machine types only (qe_scf, w90_run, etc.)
spec = registry.get(step_type)  # Accepts both public and machine types
if spec:
    machine_step_type = spec.machine_type  # Use machine type for step.yaml
```

**ParamSpace applies_to现在绑定哪一个（gen or spec）？**

**答案**: 绑定**spec step types**（machine_type）

**证据**: `src/qmatsuite/presets/variants_registry.py:70-89`
```python
PRECISION_PW_DEFAULT_VARIANT = ParamSpaceVariant(
    name="PRECISION_PW_DEFAULT",
    dimension="precision",
    space=PRECISION_PW_DEFAULT_SPACE,
    applies_to_step_types=frozenset({"scf", "nscf", "relax", "vc-relax", "bands_pw", "md", "vc-md"}),
)
```

**注意**: `applies_to_step_types`中的值（如`"scf"`, `"bands_pw"`）看起来像public_type，但根据registry，`"bands_pw"`实际上是machine_type（`qe_bands_pw`的简化形式？需要确认）。

### 4.3 如果直接恢复旧ParamSpace（以旧applies_to体系为准）

**答案**: ⚠️ **可能出现applies_to无法命中新体系的问题**

**分析**:
- 旧版`applies_to_step_types`使用qe-only step_type（如`"scf"`）
- 新版`step.yaml`存储machine_type（如`"qe_scf"`）
- 如果旧版ParamSpace的`applies_to`是`{"scf"}`，而新版的`step_type`是`"qe_scf"`，匹配会失败

**证据**: `src/qmatsuite/presets/variants_registry.py:245-258`
```python
def get_variant(dimension: str, step_type: str) -> Optional[ParamSpaceVariant]:
    """
    Get variant for dimension and step_type.
    """
    key = (step_type, dimension)
    return VARIANT_BY_STEP_AND_DIMENSION.get(key)
```

**如果旧版applies_to是`{"scf"}`，但新版step_type是`"qe_scf"`，`get_variant("precision", "qe_scf")`会返回None**。

**最小兼容层建议**（只写建议不改代码）:

1. **在materialize/dematerialize边界做映射**:
   - 在`get_variant()`调用前，将machine_type转换为public_type
   - 或者在variant registry构造时，同时支持gen/spec两种key

2. **在variant registry构造时同时支持gen/spec两种key**:
   - 修改`_build_indexes()`，为每个variant同时注册`(public_type, dimension)`和`(machine_type, dimension)`
   - 但要保持SSOT（variant定义中`applies_to_step_types`只定义一次）

**推荐方案**: 方案1（在调用点做映射），因为更简单，不需要修改variant定义。

---

## 5) Compile顺序/两阶段/oracle：当时存在吗？现在缺什么？会卡在哪一层？

### 5.1 当时是否存在这些机制？

**答案**: ✅ **部分存在**

#### Oracle

**答案**: ✅ **存在**

**证据**: `git show baac796:src/qmatsuite/presets/oracle.py`
```python
class Oracle:
    """Read-only helper for semantic prerequisite queries."""
    
    def degauss_applicability(self) -> bool:
        """Check if degauss is applicable based on current YAML state."""
        # ...
```

**结论**: baac796时代已有Oracle类，用于语义前提查询（如degauss是否适用）。

#### apply_invariants()

**答案**: ✅ **存在（在ParamSpace类中）**

**证据**: `git show baac796:src/qmatsuite/presets/paramspace.py`显示`ParamSpace`类有`apply_invariants()`方法：
```python
def apply_invariants(self, yaml_state: dict[str, dict[str, Any]], oracle: Any) -> None:
    """
    Enforce invariants for keys owned by this ParamSpace.
    This method is called unconditionally during apply, even when:
    - detect result is CUSTOM
    - user has not modified this ParamSpace
    - no preset is being applied
    """
    pass  # default no-op
```

**结论**: 旧版有`apply_invariants()`机制，用于无条件执行invariant enforcement。

#### prerequisite → dependent compile/apply顺序

**答案**: ⚠️ **部分存在（通过Oracle机制）**

**证据**: 旧版precision编译中使用Oracle检查degauss适用性：
```python
# Per ParamSpace Constitution v1 §7: degauss is owned by Precision ParamSpace
# When user explicitly sets precision preset, write degauss value
# But only if degauss is applicable (smearing is active)
oracle = Oracle(step_yaml)
if oracle.degauss_applicability():
    patch["SYSTEM"]["degauss"] = degauss_map[profile_name]
```

**结论**: 旧版通过Oracle机制实现prerequisite检查（如degauss需要smearing active），但没有显式的两阶段编译顺序。

#### 两阶段编译（pre/post）是否真的实现

**答案**: ❌ **未明确实现**

**证据**: 搜索`apply_invariants|prerequisite|dependent|two.phase|pre.post`未找到明确的两阶段编译实现。

**结论**: 旧版没有显式的两阶段编译机制，只有通过Oracle的prerequisite检查。

### 5.2 现在这些机制是否被删掉/替代？

**答案**: ⚠️ **部分删除，部分替代**

#### Oracle

**答案**: ✅ **仍然存在**

**证据**: `grep -r "class Oracle" src/qmatsuite/presets/`显示Oracle类仍然存在。

#### apply_invariants()

**答案**: ❌ **已删除**

**证据**: `git diff baac796..HEAD -- src/qmatsuite/presets/paramspace.py`显示删除了`apply_invariants()`方法。

#### prerequisite检查（degauss）

**答案**: ⚠️ **已删除，但可能有替代**

**证据**: `git diff baac796..HEAD -- src/qmatsuite/presets/variants_registry.py`显示删除了degauss的Oracle检查代码：
```diff
- # Per ParamSpace Constitution v1 §7: degauss is owned by Precision ParamSpace
- from qmatsuite.presets.oracle import Oracle
- oracle = Oracle(step_yaml)
- if oracle.degauss_applicability():
-     patch["SYSTEM"]["degauss"] = degauss_map[profile_name]
```

**替代方案**: 需要检查是否移到occupations dimension。搜索显示degauss现在可能由occupations_scheme dimension处理。

### 5.3 如果恢复旧ParamSpace：compile顺序机制需要挂在哪一层？

**答案**: **挂载点候选：presets integration层**

**分析**:
- `apply_invariants()`应该在preset apply时调用，而不是在runner执行时
- 最佳挂载点：`apply_presets_to_step()`函数（`src/qmatsuite/presets/integration.py:327`）
- 在应用patch后、保存前，调用每个dimension的`apply_invariants()`

**证据**: `src/qmatsuite/presets/integration.py:327-569`
- `apply_presets_to_step()`是preset apply的入口点
- 已经处理了多个dimension的apply顺序
- 可以在这里插入`apply_invariants()`调用

**不建议的挂载点**:
- ❌ runner层：runner只消费已落盘参数，不应该再apply preset
- ❌ stepdoc build时：stepdoc build时可能还没有preset信息

---

## 6) StepDoc：当时有没有？现在怎么用？ParamSpace置换会不会影响StepDoc生成/反推？

### 6.1 baac796时代是否已有StepDoc？

**答案**: ✅ **存在**

**证据**: `src/qmatsuite/core/yamldoc.py:454-505`显示`StepDoc`类定义，但需要确认baac796时代是否已有。

**假设**: StepDoc在baac796时代已存在（因为它是YAML I/O的基础抽象）。

**StepDoc字段是否包含IR？**

**答案**: ❌ **不包含IR字段**

**证据**: `src/qmatsuite/core/yamldoc.py:454-505`
- `StepDoc`继承自`YamlDoc`，是通用的YAML文档包装器
- 没有专门的IR字段
- `step.yaml`的schema是：`{meta: {...}, step_type: "...", parameters: {...}, cards: {...}}`

**结论**: StepDoc不包含IR字段，IR只是中间态，不持久化。

### 6.2 现在StepDoc在哪里生成、包含哪些字段？

**答案**: 在`step_factory.py`生成，包含gen/spec、engine params，但不包含IR。

**证据**: `src/qmatsuite/workflow/step_factory.py:24-118`
```python
def create_step_doc(
    step_type: str,  # 可以是public_type或machine_type
    name: str,
    # ...
) -> StepDoc:
    # 转换为machine_type存储
    spec = registry.get(step_type)
    if spec:
        machine_step_type = spec.machine_type  # 存储machine_type
    # ...
    # 生成step.yaml: {meta: {...}, step_type: machine_type, parameters: QE_params, ...}
```

**字段清单**:
- `meta`: 元数据（id, name, slug等）
- `step_type`: machine_type（如`"qe_scf"`）
- `parameters`: QE parameters（`{SYSTEM: {...}, ELECTRONS: {...}}`）
- `cards`: QE cards（`{K_POINTS: {...}}`）
- **不包含IR字段**

### 6.3 ParamSpace apply发生在StepDoc生成之前还是之后？

**答案**: **之后** - ParamSpace apply修改已存在的StepDoc

**证据**: `src/qmatsuite/presets/integration.py:327-569`
```python
def apply_presets_to_step(
    step_path: Path,  # step.yaml已存在
    options: Dict[str, Any],
    # ...
) -> Dict[str, Any]:
    # Load step using StepDoc
    doc = StepDoc.load(step_path, access_control=True, owner="compiler")
    # Apply patch
    doc.apply_patch(patch, deletions)
    # Save
    save_step_doc(doc, step_path)
```

**结论**: ParamSpace apply是**修改操作**，不是创建操作。StepDoc先创建（可能带默认参数），然后preset apply修改它。

### 6.4 恢复旧ParamSpace后，StepDoc需要的最小适配是什么？

**答案**: ✅ **几乎不需要适配**

**原因**:
- StepDoc是YAML I/O抽象，不关心ParamSpace内部实现
- StepDoc只关心最终写入的格式（QE parameters），不关心如何生成
- 只要最终patch格式正确（`{SYSTEM: {...}, ELECTRONS: {...}}`），StepDoc就能正常工作

**潜在问题**:
- 如果旧版ParamSpace的patch格式与新版不同（如bool值格式），可能需要适配
- 但根据代码，bool值格式化在`variants_registry.py`中处理，不在ParamSpace内部

**结论**: StepDoc层不需要适配，适配应该在ParamSpace调用点（`variants_registry.py`）。

---

## 7) 对"恢复旧ParamSpace + 正向重做IR refactor"的实现计划评估（含坑点清单）

### 7.1 这个plan是否可行？

**答案**: ⚠️ **Yes-but**（可行，但有条件）

**条件**:
1. 必须在调用点插入IR↔QE转换适配层
2. 必须处理key ownership enforcement与IR keys的兼容性
3. 必须处理step_type匹配问题（gen/spec映射）

### 7.2 最大坑点 Top 5

#### 坑点1: IR↔QE转换适配层缺失

**位置**: `src/qmatsuite/presets/variants_registry.py:311-343`

**问题**: 旧版ParamSpace接受QE YAML，输出QE patch。新版调用链期望IR YAML输入，IR patch输出。

**影响面**: 
- `compile_dimension_patch_for_step()`函数
- 所有调用`compile_profile_patch()`的地方

**解决方案**: 在调用`compile_profile_patch()`前插入`qe_yaml_to_ir_yaml()`，在输出后插入`ir_patch_to_qe_patch()`。

#### 坑点2: key ownership enforcement与IR keys不兼容

**位置**: `src/qmatsuite/presets/paramspace.py`（旧版的`check_key_access()`）

**问题**: 旧版有key ownership机制，如果IR层引入新keys但未在ownership registry注册，会报`KeyAccessError`。

**影响面**: 
- 所有ParamSpace操作（match/compile）
- IR mapping新增keys时

**解决方案**: 
- 选项A: 禁用key ownership enforcement（如果IR层不需要）
- 选项B: 确保所有IR keys都在ownership registry中注册

#### 坑点3: step_type匹配失败（gen vs spec）

**位置**: `src/qmatsuite/presets/variants_registry.py:245-258` (`get_variant()`)

**问题**: 旧版`applies_to_step_types`使用qe-only step_type（如`"scf"`），新版`step.yaml`存储machine_type（如`"qe_scf"`），匹配会失败。

**影响面**: 
- 所有variant查找
- preset apply/detect

**解决方案**: 在`get_variant()`调用前，将machine_type转换为public_type（通过registry）。

#### 坑点4: apply_invariants()调用点缺失

**位置**: `src/qmatsuite/presets/integration.py:327-569` (`apply_presets_to_step()`)

**问题**: 旧版有`apply_invariants()`机制，新版已删除。恢复后需要在合适位置调用。

**影响面**: 
- preset apply流程
- invariant enforcement（如degauss与smearing的依赖）

**解决方案**: 在`apply_presets_to_step()`中，每个dimension apply后调用`apply_invariants()`。

#### 坑点5: ParamKey.key字段语义变化

**位置**: `src/qmatsuite/presets/paramspace.py` (`ParamKey`类)

**问题**: 旧版`key`是QE key，新版`key`是IR key（虽然v0中值相同）。如果代码中有地方假设`key`是QE key，会出问题。

**影响面**: 
- 所有使用`ParamKey.key`的地方
- 自定义ParamSpace定义

**解决方案**: 审查所有使用`ParamKey.key`的代码，确保理解语义变化。

### 7.3 最小实现路径（3-6步）

**步骤1**: 恢复旧版ParamSpace代码
- **模块**: `src/qmatsuite/presets/paramspace.py`
- **操作**: 从baac796恢复ParamSpace类定义（包括key ownership enforcement）

**步骤2**: 在variants_registry插入IR↔QE转换适配层
- **模块**: `src/qmatsuite/presets/variants_registry.py`
- **操作**: 在`compile_dimension_patch_for_step()`中，调用`compile_profile_patch()`前插入`qe_yaml_to_ir_yaml()`，输出后插入`ir_patch_to_qe_patch()`

**步骤3**: 处理step_type匹配问题
- **模块**: `src/qmatsuite/presets/variants_registry.py`
- **操作**: 在`get_variant()`中，如果step_type是machine_type，转换为public_type（通过registry）

**步骤4**: 恢复apply_invariants()调用
- **模块**: `src/qmatsuite/presets/integration.py`
- **操作**: 在`apply_presets_to_step()`中，每个dimension apply后调用`apply_invariants()`

**步骤5**: 处理key ownership与IR keys兼容性
- **模块**: `src/qmatsuite/presets/paramspace.py`
- **操作**: 选项A（推荐）: 禁用key ownership enforcement（如果IR层不需要）；选项B: 确保所有IR keys注册

**步骤6**: 测试与验证
- **模块**: 测试套件
- **操作**: 运行preset apply/detect测试，验证IR转换正确性

---

## 8) 你认为我还必须问的5个关键问题

### 问题1: key ownership registry的SSOT放哪里？与IR新增key的流程如何对齐？

**为什么关键**: 
- 旧版有key ownership机制，新版已删除
- 如果恢复，需要明确：当IR层新增keys时，如何同步更新ownership registry？
- 如果ownership registry是SSOT，IR mapping新增keys时需要同时注册

**影响恢复策略**: 
- 如果ownership是SSOT，恢复后需要建立IR keys → ownership registry的同步机制
- 如果ownership不是SSOT，可以禁用或简化

### 问题2: StepType(enum)是否必须退场？如果退场，边界在哪？

**为什么关键**: 
- 代码中仍有`StepType`枚举（`src/qmatsuite/calculation/types.py`）
- 但registry使用字符串（`public_type`/`machine_type`）
- 如果恢复旧ParamSpace，需要明确：`applies_to_step_types`应该用枚举还是字符串？

**影响恢复策略**: 
- 如果用枚举，需要将旧版的字符串集合转换为枚举
- 如果用字符串，需要确保与registry的public_type/machine_type对齐

### 问题3: preset反推域到底以IR keys还是engine params为准？

**为什么关键**: 
- 旧版detect直接读QE params，新版detect先转IR再match
- 如果恢复旧ParamSpace，detect流程应该用哪个？
- 如果IR keys与QE keys不同（未来可能），detect结果会不同

**影响恢复策略**: 
- 如果以IR为准，detect需要先转IR（与新版一致）
- 如果以QE为准，detect直接读QE（与旧版一致）
- 需要明确SSOT

### 问题4: degauss的所有权归属：precision还是occupations_scheme？

**为什么关键**: 
- 旧版degauss由precision dimension通过Oracle检查适用性后写入
- 新版已删除此逻辑，degauss可能由occupations_scheme处理
- 如果恢复旧ParamSpace，degauss应该归哪个dimension？

**影响恢复策略**: 
- 如果归precision，需要恢复Oracle检查逻辑
- 如果归occupations_scheme，需要修改occupations_scheme ParamSpace定义
- 需要明确Constitution规定

### 问题5: IR层的"v0等价性"保证会持续多久？何时会打破？

**为什么关键**: 
- 当前IR keys与QE keys同名（v0等价性）
- 如果恢复旧ParamSpace，依赖这个等价性
- 如果未来IR keys改名（如`nspin`→`spin_polarization`），旧ParamSpace会失效

**影响恢复策略**: 
- 如果等价性是临时保证，恢复旧ParamSpace是短期方案
- 如果等价性是长期保证，恢复是可行方案
- 需要明确IR演进路线图

---

## 总结（3句话）

1. **置换旧ParamSpace对现有IR层是"有结构耦合坑"**：需要插入IR↔QE转换适配层，处理key ownership enforcement兼容性，以及step_type匹配问题。

2. **runner不会受影响**：runner完全独立于ParamSpace和IR层，只消费已落盘的QE parameters，ParamSpace变化不影响运行时。

3. **最大风险点是IR↔QE转换适配层缺失和key ownership enforcement回归**，最小适配层应该放在`variants_registry.py`的`compile_dimension_patch_for_step()`函数中，在调用旧版ParamSpace前后插入转换逻辑。

