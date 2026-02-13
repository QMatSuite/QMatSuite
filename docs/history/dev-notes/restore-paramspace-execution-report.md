# ParamSpace恢复执行报告

**日期**: 2025-01-XX  
**分支**: `restore/paramspace-baac796`  
**基线HEAD**: `1793134142275bc707b800c6086b225e53f5312e`  
**目标**: 恢复baac796/b4a7b0f的ParamSpace语义，并与现有IR/GenStep系统对接

---

## 1. Cherry-pick执行记录

### 1.1 实际Cherry-pick的Commits

**Commit 1**: `b4a7b0f` - "Merge ParamSpace Constitution into global framework"
- **状态**: ✅ 成功
- **冲突文件**: `src/quantumvitas/presets/integration.py`
- **解决方式**: 保留b4a7b0f的compile顺序和apply_invariants逻辑，适配HEAD的StepDoc使用方式

**Commit 2**: `baac796` - "Implement key access enforcement for ParamSpace"
- **状态**: ✅ 成功
- **冲突文件**: 
  - `.DS_Store` (二进制，忽略)
  - `src/quantumvitas/presets/variants_registry.py`
- **解决方式**: 保留baac796的ParamSpace内核和key access enforcement，添加IR↔QE转换适配层

### 1.2 冲突文件列表及解决方式

#### integration.py冲突

**冲突位置**: 
- 行378-392: step_type获取和step_yaml构建
- 行421-445: compile顺序逻辑
- 行662-717: apply_invariants调用

**解决方式**:
1. **StepDoc适配**: 使用HEAD的StepDoc加载方式，但添加step_type映射（machine→public）
2. **Compile顺序保留**: 保留b4a7b0f的Phase 1（prerequisite）→ Phase 2（dependent）顺序
3. **Apply_invariants集成**: 保留b4a7b0f的apply_invariants调用，但适配到StepDoc的unified_patch方式

**关键修改**:
- 添加step_type映射：`registry.get(step_type).public_type`
- 保留compile顺序：`prerequisite_dimensions` → `dependent_dimensions`
- 集成apply_invariants：在unified_patch构建后、应用前调用

#### variants_registry.py冲突

**冲突位置**:
- 行313-344: `compile_dimension_patch_for_step()`中的IR转换
- 行515-529: `detect_dimension_for_step()`中的IR转换
- 行625-641: `_detect_precision_for_step()`中的IR转换

**解决方式**:
1. **保留baac796的ParamSpace内核**: 直接调用`compile_profile_patch()`和`match_profile()`
2. **添加IR转换适配层**: 在调用ParamSpace前插入`qe_yaml_to_ir_yaml()`，调用后插入`ir_patch_to_qe_patch()`
3. **添加ParamSpaceContext**: 所有ParamSpace操作都使用`ParamSpaceContext`进行key access enforcement

**关键修改**:
- 编译适配：`qe_yaml_to_ir_yaml()` → `compile_profile_patch()` → `ir_patch_to_qe_patch()`
- 检测适配：`qe_yaml_to_ir_yaml()` → `match_profile()`（在ParamSpaceContext中）
- Key enforcement：所有操作都包装在`ParamSpaceContext(variant.space)`中

---

## 2. IR/QE适配点选择

### 2.1 选择方案A

**方案**: 保持现有IR工作流，适配在ParamSpace调用边界

**原因**:
1. **单点适配**：所有转换集中在`variants_registry.py`的两个函数中
2. **不破坏内核**：ParamSpace内核（baac796）完全不变
3. **易于维护**：未来IR非1:1时只需修改适配层

### 2.2 具体入口函数

**编译适配入口**:
- **文件**: `src/quantumvitas/presets/variants_registry.py`
- **函数**: `compile_dimension_patch_for_step()` (行260-346)
- **适配代码**:
  ```python
  # ADAPTER LAYER: Convert QE YAML → IR YAML
  ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")
  
  # ParamSpace kernel (baac796) - with key access enforcement
  with ParamSpaceContext(variant.space):
      ir_patch, deletions = compile_profile_patch(
          variant.space, profile_name, ir_yaml, explicit_defaults=explicit_defaults
      )
  
  # ADAPTER LAYER: Convert IR patch → QE patch
  patch = ir_patch_to_qe_patch(ir_patch)
  ```

**检测适配入口**:
- **文件**: `src/quantumvitas/presets/variants_registry.py`
- **函数**: `detect_dimension_for_step()` (行499-529)
- **适配代码**:
  ```python
  # ADAPTER LAYER: Convert QE YAML → IR YAML
  ir_yaml = qe_yaml_to_ir_yaml(step_yaml, qe_module="pw")
  
  # ParamSpace kernel (baac796) - with key access enforcement
  with ParamSpaceContext(variant.space):
      matched_profile = match_profile(variant.space, ir_yaml)
  ```

---

## 3. Step Type映射点

### 3.1 映射位置

**文件**: `src/quantumvitas/presets/variants_registry.py`  
**函数**: `get_variant(dimension: str, step_type: str)` (行245-258)

**实现**:
```python
# STEP TYPE MAPPING: Map machine_type to public_type for variant lookup
from quantumvitas.workflow.registry import get_registry
registry = get_registry()
spec = registry.get(step_type)
if spec and spec.public_type:
    step_type = spec.public_type  # Use public_type for variant lookup
```

### 3.2 映射路径

**调用链**:
```
apply_presets_to_step(step_path, options)
  → doc.get(["step_type"]) → machine_type (e.g., "qe_scf")
  → registry.get(step_type).public_type → public_type (e.g., "scf")
  → get_variant(dimension, public_type) → variant lookup
```

**证据**: `src/quantumvitas/presets/integration.py:378-380`

---

## 4. Oracle/顺序/apply_invariants生效证据

### 4.1 Oracle生效证据

**位置**: `src/quantumvitas/presets/integration.py:619`

**代码**:
```python
oracle = Oracle(current_yaml_state)
```

**使用位置**:
- `src/quantumvitas/presets/variants_registry.py:445` - precision编译时检查degauss适用性
- `src/quantumvitas/presets/paramspace.py:967` - precision_apply_invariants中检查degauss适用性

**验证**: `tests/unit/test_key_access_enforcement.py::test_precision_uses_oracle_for_occupations` ✅ 通过

### 4.2 Compile顺序生效证据

**位置**: `src/quantumvitas/presets/integration.py:414-424, 436-573`

**实现**:
```python
# Phase 1: Prerequisite dimensions (occupations_scheme, magnetism)
prerequisite_dimensions = [
    d for d in applied_dimensions 
    if d in (DIMENSION_OCCUPATIONS_SCHEME, DIMENSION_MAGNETISM)
]

# Phase 2: Dependent dimensions (precision, convergence)
dependent_dimensions = [
    d for d in applied_dimensions 
    if d in (DIMENSION_PRECISION, DIMENSION_CONVERGENCE)
]

# Apply Phase 1 patches to step_yaml (for oracle to read latest state in Phase 2)
step_yaml["SYSTEM"].update(unified_patch["parameters"]["SYSTEM"])
step_yaml["ELECTRONS"].update(unified_patch["parameters"]["ELECTRONS"])
```

**验证**: `tests/unit/test_paramspace_invariants.py::test_d2_apply_order_occupation_before_precision` ✅ 通过

### 4.3 apply_invariants生效证据

**位置**: `src/quantumvitas/presets/integration.py:621-626`

**代码**:
```python
from quantumvitas.presets.spaces_registry import SPACES
for dimension_name, paramspace in SPACES.items():
    paramspace.apply_invariants(current_yaml_state, oracle)
```

**precision_apply_invariants实现**:
- **位置**: `src/quantumvitas/presets/paramspace.py:957-974`
- **逻辑**: 检查`oracle.degauss_applicability()`，如果不适用则删除degauss

**验证**: 
- `tests/unit/test_paramspace_invariants.py::test_a1_smearing_to_fixed_deletes_degauss` ✅ 通过
- `tests/unit/test_paramspace_invariants.py::test_a2_precision_custom_still_deletes_degauss` ✅ 通过

---

## 5. 测试结果

### 5.1 必须通过的测试（baac796带来的测试）

**test_key_access_enforcement.py**: ✅ **11/11 passed**
- test_illegal_key_access_raises_error
- test_occupation_detect_no_degauss_dependency
- test_occupation_detect_without_degauss
- test_precision_uses_oracle_for_occupations
- test_duplicate_ownership_fails_immediately
- test_owned_keys_access_allowed
- test_foreign_key_access_raises_error
- test_oracle_access_allowed
- test_no_context_allows_access
- test_degauss_owned_by_precision
- test_degauss_not_owned_by_occupations

**test_paramspace_invariants.py**: ✅ **8/8 passed**
- test_a1_smearing_to_fixed_deletes_degauss
- test_a2_precision_custom_still_deletes_degauss
- test_b1_smearing_plus_precision_preset_writes_degauss
- test_b2_smearing_no_precision_apply_does_not_auto_fill
- test_d1_oracle_reads_updated_yaml_not_stale_state
- test_d2_apply_order_occupation_before_precision
- test_e1_invariants_run_even_when_custom
- test_e2_invariants_run_even_when_no_preset_applied

### 5.2 现有相关测试

**test_paramspace_contract.py**: ✅ **16/16 passed**

**test_detector_b.py**: ✅ **63/63 passed**

**test_preset_broadcast.py**: ✅ **16/16 passed**

**test_preset_integration.py**: ✅ **34/34 passed** (包括convergence测试)

### 5.3 总测试结果

**总计**: ✅ **148 passed, 0 failed**

---

## 6. 修复项清单

### 6.1 冲突解决修复

1. **integration.py冲突**:
   - ✅ 保留b4a7b0f的compile顺序（Phase 1 → Phase 2）
   - ✅ 保留b4a7b0f的apply_invariants调用
   - ✅ 适配HEAD的StepDoc使用方式
   - ✅ 添加step_type映射（machine→public）

2. **variants_registry.py冲突**:
   - ✅ 保留baac796的ParamSpace内核（直接调用compile_profile_patch/match_profile）
   - ✅ 添加IR↔QE转换适配层
   - ✅ 添加ParamSpaceContext进行key access enforcement

### 6.2 功能修复

1. **KeyError修复**:
   - ✅ 修复`unified_patch["parameters"]["ELECTRONS"]`访问时的KeyError
   - ✅ 修复`step_yaml["ELECTRONS"]`访问时的KeyError
   - ✅ 确保所有sections在访问前已初始化

2. **apply_invariants修复**:
   - ✅ 修复unified_patch更新逻辑，正确处理删除的值（设置为None）
   - ✅ 确保current_yaml_state正确反映所有phase的更改

3. **Convergence支持**:
   - ✅ 将convergence添加到dependent_dimensions
   - ✅ 在Phase 2中处理convergence选项

---

## 7. 关键设计决策

### 7.1 适配层位置

**决策**: 在`variants_registry.py`的`compile_dimension_patch_for_step()`和`detect_dimension_for_step()`中实现

**理由**: 
- 单点适配，易于维护
- 不破坏ParamSpace内核
- 符合"薄层适配"原则

### 7.2 Step Type映射位置

**决策**: 在`get_variant()`函数中实现

**理由**:
- 所有variant查找都通过`get_variant()`
- 单点映射，避免重复代码
- 符合"只改边界"原则

### 7.3 apply_invariants调用位置

**决策**: 在`apply_presets_to_step()`中，所有phase完成后、应用patch前调用

**理由**:
- 符合b4a7b0f的语义（无条件执行）
- 可以读取所有phase的最终状态
- 可以修改current_yaml_state并反映到unified_patch

---

## 8. 必须向Owner确认的3个问题

### 问题1: ownership registry（key单归属）新增key的更新流程是否要写成CI gate（缺失即fail）？

**为什么关键**: 
- 当前ownership registry在ParamSpace `__post_init__()`时自动注册
- 如果IR层新增keys但未在ParamSpace中定义，ownership registry会缺失
- 需要明确：是否要求所有IR keys都必须有对应的ParamSpace ownership？

**影响恢复策略**: 
- 如果需要CI gate，需要建立IR keys → ownership registry的同步检查机制
- 如果不需要，可以允许某些IR keys没有ownership（但key access enforcement会报错）

### 问题2: gen step string的SSOT是否只认public_type，并要求所有preset/paramspace永远不接触machine_type？

**为什么关键**: 
- 当前实现：`get_variant()`中映射machine_type → public_type
- 但其他代码路径可能直接使用machine_type
- 需要明确：preset/paramspace系统是否应该完全隔离machine_type？

**影响恢复策略**: 
- 如果要求完全隔离，需要审查所有preset相关代码，确保不接触machine_type
- 如果允许边界接触，当前实现（在get_variant中映射）即可

### 问题3: 未来IR非1:1时，是否允许引入显式映射层而保持ParamSpace内核不变？

**为什么关键**: 
- 当前适配层假设IR 1:1映射（keys和sections都同名）
- 未来如果IR keys改名（如`nspin` → `spin_polarization`），需要映射
- 需要明确：是否允许在适配层中引入显式映射表，而不修改ParamSpace内核？

**影响恢复策略**: 
- 如果允许，当前适配层设计（方案A）是正确的
- 如果不允许，需要重新设计（可能需要修改ParamSpace内核，但这违反规则）

---

## 9. 总结

### 9.1 完成状态

- ✅ Cherry-pick b4a7b0f和baac796成功
- ✅ 所有冲突按规则解决（ParamSpace内核以baac796为准）
- ✅ IR/QE薄层适配实现（方案A）
- ✅ Step type映射实现（machine→public）
- ✅ Oracle/顺序/apply_invariants完整恢复并生效
- ✅ 所有测试通过（148 passed）

### 9.2 关键成果

1. **ParamSpace内核完全保留**: baac796的ParamSpace实现未修改一行
2. **适配层单点实现**: 所有IR↔QE转换集中在`variants_registry.py`
3. **Key access enforcement生效**: 所有ParamSpace操作都使用ParamSpaceContext
4. **Compile顺序正确**: Phase 1（prerequisite）→ Phase 2（dependent）
5. **apply_invariants生效**: 无条件执行，正确删除不适用的degauss

### 9.3 验证证据

- **Oracle**: `test_precision_uses_oracle_for_occupations` ✅
- **顺序**: `test_d2_apply_order_occupation_before_precision` ✅
- **apply_invariants**: `test_a1_smearing_to_fixed_deletes_degauss` ✅
- **Key enforcement**: `test_illegal_key_access_raises_error` ✅

---

## 10. 后续建议

1. **监控IR keys变化**: 如果IR层新增keys，需要同步更新ParamSpace ownership registry
2. **文档化适配层**: 确保未来开发者理解适配层的职责和边界
3. **测试覆盖**: 考虑添加IR非1:1场景的测试（虽然当前是1:1）

