# K_POINTS.data 回归问题修复尝试记录

**日期**: 2025-01-XX  
**问题**: 3个 daemon 测试失败，错误信息：`K_POINTS option 'crystal_b' requires 'data' to be provided`

---

## 问题描述

### 失败的测试
1. `test_run_calculation_via_job_manager`
2. `test_get_band_structure_data` (依赖测试1)
3. `test_analyze_bands_and_generate_plot` (依赖测试1)

### 错误信息
```
K_POINTS option 'crystal_b' requires 'data' to be provided. 
K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data.
```

### 测试配置
测试在 `bands` step 中配置了：
```python
cards={
    "K_POINTS": {
        "option": "crystal_b",
        "data": [[5], [0.5, 0.5, 0.5, 20], ...]
    },
}
```

---

## 尝试1: 添加调试日志

### 修改文件
- `src/quantumvitas/calculation/structure_steps.py`
- `src/quantumvitas/calculation/input_runner.py`

### 修改内容
在 `generate_qe_input_from_spec` 和 `apply_card_overrides_to_qe_input` 中添加了调试日志。

### 结果
- **发现**: 错误日志显示 `payload keys=['option'], payload={'option': 'crystal_b'}`，确认 `data` 字段丢失
- **结论**: 问题发生在 `apply_card_overrides_to_qe_input` 接收到的 payload 中，`data` 字段已经丢失

---

## 尝试2: 检查数据流路径

### 验证点
1. **StepDoc 加载**: ✅ 正确加载 cards，包含 `option` 和 `data`
2. **StructureStepSpec.from_yaml**: ✅ 正确加载 cards，包含 `option` 和 `data`
3. **apply_patch**: ✅ 正确保存 cards 到 step.yaml
4. **_extract_cards**: ✅ 正确提取 cards，包含 `option` 和 `data`
5. **apply_card_overrides_to_qe_input**: ✅ 当输入正确时，能正确处理

### 结果
- **发现**: 所有单独组件都工作正常
- **结论**: 问题可能发生在数据传递的某个中间环节

---

## 尝试3: 检查 existing_input_file 合并逻辑

### 修改文件
- `src/quantumvitas/calculation/calculation.py`

### 修改内容
在 `_build_step_from_spec` 中添加了逻辑，当 existing_input_file 存在且提取的 cards 缺少 `data` 时，保留 step.yaml 中的 `data`。

### 修改代码
```python
# For K_POINTS with k-path formats, preserve step.yaml data if existing input doesn't have it
if "K_POINTS" in spec_preview.cards and "K_POINTS" in extracted_cards:
    step_kp = spec_preview.cards["K_POINTS"]
    extracted_kp = extracted_cards["K_POINTS"]
    kpath_formats = ["crystal_b", "crystal_c", "tpiba_b", "tpiba_c"]
    step_option = (step_kp.get("option") or "").lower()
    if step_option in kpath_formats and "data" in step_kp:
        if "data" not in extracted_kp or not extracted_kp.get("data"):
            extracted_cards["K_POINTS"] = step_kp
```

### 结果
- **问题**: daemon 测试**没有** existing_input_file，所以这个修复不会生效
- **结论**: 问题不在 existing_input_file 合并路径

---

## 关键发现

### 1. 数据丢失的位置
- 错误发生在 `apply_card_overrides_to_qe_input` 中
- 接收到的 `payload` 只有 `{'option': 'crystal_b'}`，缺少 `data`

### 2. 数据流路径
```
step.yaml (有 data)
  ↓ StructureStepSpec.from_yaml
spec.cards (有 data) ✅
  ↓ generate_qe_input_from_spec
apply_card_overrides_to_qe_input(qe_input, spec.cards)
  ↓ 遍历 overrides.items()
payload = {'option': 'crystal_b'} ❌ (data 丢失)
```

### 3. 可能的问题点
- `spec.cards` 在传递给 `apply_card_overrides_to_qe_input` 时，`K_POINTS` 的值可能被修改
- 或者在 `apply_card_overrides_to_qe_input` 内部，遍历 `overrides.items()` 时，只读取了部分字段

---

## 未完成的调查

### 需要检查的点
1. **`spec.cards` 在传递过程中是否被修改？**
   - 检查是否有代码在 `generate_qe_input_from_spec` 之前修改了 `spec.cards`
   - 检查是否有代码在 `apply_card_overrides_to_qe_input` 调用之前修改了 `spec.cards`

2. **`apply_card_overrides_to_qe_input` 的遍历逻辑**
   - 检查 `for card_name, payload in overrides.items()` 是否正确获取了完整的 payload
   - 检查是否有代码在遍历过程中过滤了 `data` 字段

3. **`materialize_step_spec` 中的处理**
   - 检查 `materialize_step_spec` 是否在调用 `generate_qe_input_from_spec` 之前修改了 `spec.cards`
   - 检查是否有其他代码路径在 materialization 过程中修改了 cards

4. **JobRunner 迁移后的变化**
   - 检查 JobRunner 迁移是否引入了新的代码路径
   - 检查是否有新的序列化/反序列化逻辑丢失了 `data` 字段

---

## 下一步建议

1. **添加更详细的调试日志**
   - 在 `materialize_step_spec` 中记录 `spec.cards` 的值
   - 在 `generate_qe_input_from_spec` 中记录 `spec.cards` 的值
   - 在 `apply_card_overrides_to_qe_input` 入口处记录 `overrides` 的值

2. **检查 JobRunner 迁移相关代码**
   - 检查 `execution/recipes.py` 和 `execution/handlers.py`
   - 检查是否有新的代码路径在 materialization 过程中处理 cards

3. **检查是否有字典更新/合并操作**
   - 搜索所有 `cards.update()` 调用
   - 搜索所有 `cards[key] = value` 赋值
   - 检查是否有代码只设置了 `option` 而没有设置 `data`

---

## 回滚状态

所有修改已回滚：
- ✅ `src/quantumvitas/calculation/structure_steps.py`
- ✅ `src/quantumvitas/calculation/input_runner.py`
- ✅ `src/quantumvitas/calculation/calculation.py`

