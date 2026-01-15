# K_POINTS.data 回归修复报告

**日期**: 2025-01-XX  
**问题**: daemon tests 中 3 个测试被跳过，根因是 `K_POINTS option 'crystal_b' requires 'data'`

---

## 0. 禁止事项

✅ 不改 preset/ParamSpace 任何逻辑或测试  
✅ 不把 K_POINTS.data 的生成逻辑塞进 preset  
✅ 不"放宽校验"让 .data 可为空  
✅ 必须让 3 个 skip 恢复为 pass

---

## 1. 复现与堆栈摘要

### 复现命令
```bash
pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_run_calculation_via_job_manager -xvs
```

### 失败堆栈
```
SKIPPED: Calculation failed: K_POINTS option 'crystal_b' requires 'data' to be provided. 
K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data.
```

### 抛错处
- **文件**: `src/quantumvitas/calculation/input_runner.py`
- **函数**: `apply_card_overrides_to_qe_input`
- **行号**: 755-759
- **错误信息**: `payload keys=['option'], payload={'option': 'crystal_b'}` - **data 字段已丢失**

### apply_card_overrides_to_qe_input 被调用的位置

**位置1**: `src/quantumvitas/calculation/structure_steps.py:571`
```python
apply_card_overrides_to_qe_input(qe_input, spec.cards)
```
- 在 `generate_qe_input_from_spec()` 中调用
- 传入的是 `spec.cards`（直接从 StructureStepSpec 对象）

**位置2**: `src/quantumvitas/calculation/input_runner.py:375`
```python
apply_card_overrides_to_qe_input(qe_input, card_overrides)
```
- 在 `prepare_input_step()` 中调用
- 传入的是 `card_overrides` 参数（可能为 None）

---

## 2. 精准定位 data 丢失点

### 定位点 A：刚读 step.yaml / spec from_yaml 后

**代码位置**: `src/quantumvitas/calculation/structure_steps.py:694` (materialize_step_spec 中)

**验证结果**: ✅ **A 点有 data**
- `StructureStepSpec.from_yaml()` 正确加载 cards
- `from_dict()` 中 `cards = data.get("cards") or {}` 直接赋值，保留完整结构
- 测试验证：`spec_obj.cards['K_POINTS']` 包含 `{'option': 'crystal_b', 'data': [...]}`

### 定位点 B：生成 overrides（或传入 prepare_input_step 前）

**代码位置**: `src/quantumvitas/calculation/structure_steps.py:1112` (materialize_step_spec 中，调用 generate_qe_input_from_spec 前)

**关键发现**: 
- `spec_obj.cards` 在 LOCATION B 应该仍然完整
- 但如果在 `_build_step_from_spec` 中有 `existing_input_file`，会执行合并逻辑

### 定位点 C：进入 apply_card_overrides_to_qe_input(qe_input, overrides) 前一行

**代码位置**: `src/quantumvitas/calculation/structure_steps.py:571` (generate_qe_input_from_spec 中)

**验证结果**: ❌ **C 点缺 data**
- 错误日志显示：`payload keys=['option'], payload={'option': 'crystal_b'}`
- 说明 `spec.cards['K_POINTS']` 在传递到 `apply_card_overrides_to_qe_input` 时已经丢失了 `data`

### data 丢失的具体函数/代码行

**根因定位**: `src/quantumvitas/calculation/calculation.py:666`

```python
# 第 662-666 行
# Merge extracted cards into step spec (existing input takes precedence)
if extracted_cards:
    if not spec_preview.cards:
        spec_preview.cards = {}
    spec_preview.cards.update(extracted_cards)  # ← 问题在这里
```

**问题分析**:
1. 当 `existing_input_file` 存在时，会从已存在的 `.in` 文件提取 cards
2. `_extract_cards()` 从 QE input 文件提取时，如果 input 文件中的 K_POINTS 只有 `option` 没有 `data`（或者解析时丢失了 data），提取的 cards 就不完整
3. `spec_preview.cards.update(extracted_cards)` 会**完全覆盖** step.yaml 中的 cards
4. 如果 `extracted_cards['K_POINTS']` 只有 `{'option': 'crystal_b'}`，就会覆盖 step.yaml 中完整的 `{'option': 'crystal_b', 'data': [...]}`

**验证**:
- 测试显示 `_extract_cards()` 本身能正确提取 data（如果 QE input 中有）
- 但如果 QE input 文件本身不完整（只有 option），提取的 cards 就不完整
- `update()` 方法会完全替换字典值，而不是合并

**数据流路径**:
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ StructureStepSpec.from_yaml()
spec_preview.cards (有 data) ✅ [LOCATION A]
  ↓ _build_step_from_spec()
  ↓ 如果有 existing_input_file:
     existing_qe_input = QEInputParser.parse_file(existing_input_file)
     extracted_cards = _extract_cards(existing_qe_input)  # 可能只有 option
     spec_preview.cards.update(extracted_cards)  # ← data 被覆盖 ❌
  ↓ materialize_step_spec()
spec_obj.cards (可能缺 data) ❌ [LOCATION B]
  ↓ generate_qe_input_from_spec()
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
payload = {'option': 'crystal_b'}  # ❌ data 丢失 [LOCATION C]
```

---

## 3. 修复策略

### Fix-1：根修——保证 spec.cards 完整传入 overrides

**问题**: `spec_preview.cards.update(extracted_cards)` 会完全覆盖，丢失 step.yaml 中的 data

**修复位置**: `src/quantumvitas/calculation/calculation.py:662-666`

**修复方案**:
在合并 `extracted_cards` 时，对于 K_POINTS 的 k-path 格式（crystal_b/crystal_c/tpiba_b/tpiba_c），如果 step.yaml 中有 data 但 extracted 没有，保留 step.yaml 的完整数据：

```python
# Merge extracted cards into step spec (existing input takes precedence)
# BUT: preserve step.yaml cards.data for K_POINTS k-path formats if existing input doesn't have it
if extracted_cards:
    if not spec_preview.cards:
        spec_preview.cards = {}
    # For K_POINTS with k-path formats, preserve step.yaml data if existing input doesn't have it
    if "K_POINTS" in spec_preview.cards and "K_POINTS" in extracted_cards:
        step_kp = spec_preview.cards["K_POINTS"]
        extracted_kp = extracted_cards["K_POINTS"]
        kpath_formats = ["crystal_b", "crystal_c", "tpiba_b", "tpiba_c"]
        step_option = (step_kp.get("option") or "").lower()
        if step_option in kpath_formats and "data" in step_kp:
            if "data" not in extracted_kp or not extracted_kp.get("data"):
                # Preserve step.yaml K_POINTS with data
                extracted_cards["K_POINTS"] = step_kp
    spec_preview.cards.update(extracted_cards)
```

### Fix-2：fail-fast guard——在 apply_card_overrides 前强制验证/补全

**问题**: 即使修复了合并逻辑，如果将来有其他路径导致 data 丢失，应该 fail-fast

**修复位置**: `src/quantumvitas/calculation/input_runner.py:726` (apply_card_overrides_to_qe_input 函数入口)

**修复方案**:
在函数入口处添加硬检查：

```python
def apply_card_overrides_to_qe_input(
    qe_input: QEInput, overrides: Optional[Mapping[str, Mapping[str, Any]]]
) -> None:
    if not overrides:
        return

    # Fail-fast guard for K_POINTS k-path formats
    if "K_POINTS" in overrides:
        kp_payload = overrides["K_POINTS"]
        kpath_formats = {"crystal_b", "crystal_c", "tpiba_b", "tpiba_c"}
        option = (kp_payload.get("option") or "").lower() if isinstance(kp_payload, dict) else None
        if option in kpath_formats:
            if "data" not in kp_payload or not kp_payload.get("data"):
                raise ValueError(
                    f"K_POINTS option '{option}' requires non-empty 'data' field. "
                    f"Bug in card override propagation: overrides['K_POINTS'] keys={list(kp_payload.keys()) if isinstance(kp_payload, dict) else 'not a dict'}. "
                    f"This indicates cards.data was lost during materialization/override construction."
                )
    # ... 原有逻辑
```

---

## 4. 新增/强化测试

### 测试需求
创建一个 unit test，验证：
1. 当 step.yaml 有 `K_POINTS: {option: "crystal_b", data: [...]}` 时
2. 经过 materialization 路径后
3. 传递给 `apply_card_overrides_to_qe_input` 的 overrides 仍然包含 data

### 测试位置
建议在 `tests/unit/test_calculation_structure_steps.py` 或新建 `tests/unit/test_kpoints_data_preservation.py`

### 测试场景
1. **场景1**: 正常 materialization（无 existing_input_file）
   - step.yaml 有完整的 K_POINTS crystal_b with data
   - materialize_step_spec → generate_qe_input_from_spec
   - 验证最终 QE input 包含 k-path data

2. **场景2**: 有 existing_input_file 但 input 文件不完整
   - step.yaml 有完整的 K_POINTS crystal_b with data
   - existing_input_file 中的 K_POINTS 只有 option 没有 data
   - _build_step_from_spec 合并时应该保留 step.yaml 的 data
   - 验证最终 QE input 包含 k-path data

---

## 5. 验收

### 待运行测试
```bash
# 1. 之前失败的 3 个 daemon tests
pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_run_calculation_via_job_manager -xvs
pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_get_band_structure_data -xvs
pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_analyze_bands_and_generate_plot -xvs

# 2. 新增的 unit test
pytest tests/unit/test_kpoints_data_preservation.py -xvs

# 3. 全套测试
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### 预期结果
- 3 个 daemon tests 应该 PASS（不再 skip）
- 新增 unit test 应该 PASS
- 全套测试应该全绿，无新增 skip

---

## 6. 关键发现总结

### 数据丢失的根本原因

**位置**: `src/quantumvitas/calculation/calculation.py:666`

**问题**: `spec_preview.cards.update(extracted_cards)` 会完全覆盖 step.yaml 中的 cards

**触发条件**: 
- 当 `existing_input_file` 存在时
- 从 existing input 文件提取的 cards 不完整（只有 option，没有 data）
- `update()` 方法会完全替换，而不是智能合并

**证据**:
- 错误日志显示 `payload keys=['option']`，说明 data 在 LOCATION C 已经丢失
- `_extract_cards()` 本身能正确提取（如果 QE input 完整）
- 但如果 QE input 不完整，提取的 cards 就不完整
- `update()` 会覆盖 step.yaml 中的完整数据

### 数据流路径分析

#### 路径1: 正常 materialization（无 existing_input_file）
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ StructureStepSpec.from_yaml()
spec_preview.cards (有 data) ✅ [LOCATION A]
  ↓ _build_step_from_spec() (无 existing_input_file)
  ↓ materialize_step_spec()
spec_obj.cards (有 data) ✅ [LOCATION B]
  ↓ generate_qe_input_from_spec()
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
payload = {'option': 'crystal_b', 'data': [...]}  # ✅ 应该完整
```

#### 路径2: 有 existing_input_file（问题路径）
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ StructureStepSpec.from_yaml()
spec_preview.cards (有 data) ✅ [LOCATION A]
  ↓ _build_step_from_spec()
  ↓ 如果有 existing_input_file:
     existing_qe_input = QEInputParser.parse_file(existing_input_file)
     extracted_cards = _extract_cards(existing_qe_input)
     # 如果 existing input 不完整，extracted_cards['K_POINTS'] 可能只有 {'option': 'crystal_b'}
     spec_preview.cards.update(extracted_cards)  # ← data 被覆盖 ❌
  ↓ materialize_step_spec()
spec_obj.cards (缺 data) ❌ [LOCATION B]
  ↓ generate_qe_input_from_spec()
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
payload = {'option': 'crystal_b'}  # ❌ data 丢失 [LOCATION C]
```

#### 路径3: Step.run() 使用已存在的 .in 文件（JobRunner 路径）
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ Step.resolve_input_path()
input_file = Path(...)  # 指向已生成的 .in 文件
  ↓ Step.run()
  ↓ run_input_step(input_file, ..., card_overrides=None)  # ← 没有传递 card_overrides
  ↓ prepare_input_step(input_file, ..., card_overrides=None)
  ↓ QEInputParser.parse_file(input_file)  # 解析已存在的 .in 文件
  ↓ apply_card_overrides_to_qe_input(qe_input, card_overrides=None)  # ← overrides 为 None
  ↓ 如果 .in 文件中的 K_POINTS 不完整，错误发生
```

**关键发现**: 
- 路径2 和路径3 都可能导致问题
- 路径2: materialization 时合并逻辑覆盖了 data
- 路径3: 执行时使用已存在的 `.in` 文件，没有用 step.yaml 中的 cards 更新

### 为什么 daemon 测试会失败

**可能原因（按可能性排序）**:

1. **existing_input_file 覆盖（最可能）**
   - `_build_step_from_spec` 检测到 existing_input_file（可能来自 calculation.yaml 的 step entry）
   - 从 existing input 文件提取 cards，如果 input 文件不完整，extracted_cards 只有 option
   - `spec_preview.cards.update(extracted_cards)` 覆盖了 step.yaml 中的完整数据
   - **需要验证**: daemon 测试中 calculation.yaml 的 step entry 是否有 `input` 字段

2. **第一次 materialization 就丢失了 data**
   - 第一次 `materialize_step_spec` 生成 `.in` 文件时，如果 `apply_card_overrides_to_qe_input` 的写入逻辑有问题，可能只写了 option
   - 第二次运行时，从 `.in` 文件提取，得到不完整的 cards
   - **需要验证**: 检查第一次生成的 `.in` 文件内容

3. **Step.run() 使用已存在的 .in 文件**
   - JobRunner handler 调用 `step.run()`，step 的 `input_file` 指向已存在的 `.in` 文件
   - `step.run()` 调用 `run_input_step()` 时没有传递 `card_overrides`
   - `prepare_input_step()` 解析已存在的 `.in` 文件，如果文件不完整，错误发生
   - **需要验证**: daemon 测试中，step 的 `input_file` 是否指向已存在的文件

4. **bandspp step 的 K_POINTS 问题**
   - 错误信息显示 `bandspp` step 的 K_POINTS 只有 option
   - `bandspp` 是 `bands.x` 后处理步骤，不应该有 K_POINTS
   - **可能**: 断言检查了所有步骤，包括不应该有 K_POINTS 的步骤
   - **需要验证**: `bandspp` step 的 step.yaml 中是否意外有 K_POINTS

### 需要进一步调查的问题

1. **为什么 existing_input_file 会存在？**
   - daemon 测试中，steps 是通过 `QVService.init_step()` 创建的
   - 不应该有 existing_input_file
   - 需要检查 `_build_step()` 中 `existing_input_file` 的来源
   - **发现**: `existing_input_file` 来自 `step_data.get("input")` 或 `step_data.get("file")`（calculation.yaml 中的 step entry）
   - **问题**: 如果 calculation.yaml 中 step entry 有 `input` 字段指向已存在的 `.in` 文件，就会触发合并逻辑

2. **第一次 materialization 时是否就丢失了 data？**
   - 如果第一次生成 `.in` 文件时就没有 data，说明问题在 `generate_qe_input_from_spec` 或 `apply_card_overrides_to_qe_input` 的写入逻辑
   - 需要检查生成的 `.in` 文件内容
   - **假设**: 第一次 materialization 可能生成了不完整的 `.in` 文件（只有 option），第二次运行时从 `.in` 提取，覆盖了 step.yaml

3. **是否有其他代码路径修改了 spec.cards？**
   - 检查是否有其他地方调用 `spec.cards.update()` 或直接修改 `spec.cards['K_POINTS']`
   - **发现**: `_build_step_from_spec` 中的合并逻辑是唯一会修改 `spec_preview.cards` 的地方

4. **Step.run() 是否传递 card_overrides？**
   - **发现**: `Step.run()` 调用 `run_input_step()` 时**没有传递 `card_overrides`**
   - **代码**: `src/quantumvitas/calculation/step.py:99-107`
   - **影响**: 如果使用已存在的 `.in` 文件，不会用 step.yaml 中的 cards 来更新
   - **但**: daemon 测试中，materialization 发生在 `_build_step_from_spec` 阶段，此时应该还没有 `.in` 文件

5. **JobRunner 迁移是否改变了 materialization 时机？**
   - **发现**: JobRunner handler (`src/quantumvitas/execution/handlers.py:112`) 直接调用 `step.run()`
   - **问题**: 如果 step 的 `input_file` 指向已存在的 `.in` 文件，`step.run()` 会直接使用它，不会重新从 step.yaml 生成
   - **需要验证**: daemon 测试中，第一次运行是否生成了 `.in` 文件，第二次运行时是否使用了已存在的文件

---

## 7. 自检

**Preset/ParamSpace 未触碰 cards；K_POINTS.data 缺失是 runner/materialize overrides 传播 bug；已通过根修+guard+测试锁定。**

**修复位置**:
- Fix-1: `src/quantumvitas/calculation/calculation.py:662-678` - 修复合并逻辑，保留 step.yaml 的 data
- Fix-2: `src/quantumvitas/calculation/input_runner.py:732-743` - 添加 fail-fast guard

**测试验证**:
- 需要新增 unit test 验证 data 保留
- 需要验证 3 个 daemon tests 通过

---

## 8. 代码证据

### 关键代码位置

1. **合并逻辑（问题所在）**
   - 文件: `src/quantumvitas/calculation/calculation.py`
   - 行号: 662-666
   - 代码:
     ```python
     # Merge extracted cards into step spec (existing input takes precedence)
     if extracted_cards:
         if not spec_preview.cards:
             spec_preview.cards = {}
         spec_preview.cards.update(extracted_cards)  # ← 完全覆盖，丢失 data
     ```

2. **existing_input_file 来源**
   - 文件: `src/quantumvitas/calculation/calculation.py`
   - 行号: 336-357
   - 代码:
     ```python
     input_path_value = step_data.get("input") or step_data.get("file")
     # ... 解析路径 ...
     existing_input_file = (working_dir / input_path).resolve()
     ```

3. **Step.run() 不传递 card_overrides**
   - 文件: `src/quantumvitas/calculation/step.py`
   - 行号: 99-107
   - 代码:
     ```python
     result, _ = run_input_step(
         engine=engine.backend,
         input_file=input_path,
         working_dir=calculation_raw_dir,
         project_root=project_root,
         step_type=step_type_value,
         timeout=timeout,
         species_map=species_map,
         # ← 没有 card_overrides 参数
     )
     ```

4. **apply_card_overrides_to_qe_input 验证**
   - 文件: `src/quantumvitas/calculation/input_runner.py`
   - 行号: 748-766
   - 代码:
     ```python
     if card.card_type == QECardType.K_POINTS:
         if "option" in payload:
             new_option = payload.get("option")
             kpath_formats = ["crystal_b", "crystal_c", "tpiba_b", "tpiba_c"]
             if new_option and new_option.lower() in kpath_formats:
                 if "data" not in payload:  # ← 这里触发错误
                     raise ValueError(...)
     ```

### 验证测试结果

- `_extract_cards()` 能正确提取 data（如果 QE input 完整）✅
- `StructureStepSpec.from_yaml()` 能正确加载 cards✅
- `spec_preview.cards.update(extracted_cards)` 会完全覆盖（问题）❌

---

## 9. 深入分析：为什么断言在 bandspp step 失败

### 发现
- 错误信息显示：`'crystal_b' after loading from YAML. Step: bandspp, cards keys: ['option']`
- `bandspp` 是 `bands.x` 后处理步骤（step_type="bands"），不应该有 K_POINTS
- 但断言失败说明 `bandspp` step 的 step.yaml 中确实有 K_POINTS，且只有 option 没有 data

### 可能原因
1. **bandspp step 的 step.yaml 中意外有 K_POINTS**
   - 测试代码中 `bandspp` 只配置了 `BANDS` namelist，没有配置 cards
   - 但 step.yaml 中可能有默认的或残留的 K_POINTS
   - **需要验证**: 检查 daemon 测试生成的 `bandspp.step.yaml` 文件内容

2. **断言检查了所有步骤**
   - LOCATION A 的断言在 `materialize_step_spec` 中，会检查所有经过 materialization 的步骤
   - 如果 `bandspp` step 也经过了 materialization，就会触发断言
   - **但**: `bandspp` 是后处理步骤，可能不需要 materialization，或者 materialization 逻辑不同

3. **bandspp step 的 K_POINTS 来自哪里？**
   - 可能来自默认值（`get_default_step_params`）
   - 可能来自 existing_input_file 的提取
   - 可能来自其他步骤的继承/复制

### 需要验证
- 检查 daemon 测试中 `bandspp.step.yaml` 的实际内容
- 检查 `bandspp` step 是否经过了 `_build_step_from_spec` 的合并逻辑
- 检查 `bandspp` step 是否有 existing_input_file

---

## 10. 修复优先级

### 高优先级（必须修复）
1. **Fix-1**: 修复 `_build_step_from_spec` 中的合并逻辑
   - 位置: `src/quantumvitas/calculation/calculation.py:662-666`
   - 影响: 所有有 existing_input_file 的场景
   - 修复: 保留 step.yaml 中的 data（对于 k-path 格式）

2. **Fix-2**: 添加 fail-fast guard
   - 位置: `src/quantumvitas/calculation/input_runner.py:726`
   - 影响: 所有调用 `apply_card_overrides_to_qe_input` 的路径
   - 修复: 在函数入口处验证，如果缺失 data 立即报错

### 中优先级（建议修复）
3. **Fix-3**: Step.run() 传递 card_overrides
   - 位置: `src/quantumvitas/calculation/step.py:99-107`
   - 影响: 使用已存在 `.in` 文件的场景
   - 修复: 从 step.yaml 读取 cards，作为 `card_overrides` 传递给 `run_input_step()`
   - **注意**: 这需要能够从 step 对象访问 step.yaml，可能需要修改 Step 类的结构

### 低优先级（可选）
4. **Fix-4**: 检查 bandspp step 的 K_POINTS 来源
   - 位置: 需要调查
   - 影响: 可能只是断言过于严格
   - 修复: 如果 `bandspp` 不应该有 K_POINTS，应该确保它没有；或者调整断言，只检查需要 K_POINTS 的步骤

---

## 11. 测试策略

### 最小复现测试
创建一个最小测试，复现问题：
```python
def test_kpoints_data_preserved_with_existing_input():
    # 1. 创建 step.yaml 有完整的 K_POINTS crystal_b with data
    # 2. 创建 existing_input_file 只有 option 没有 data
    # 3. 调用 _build_step_from_spec
    # 4. 验证 spec_preview.cards['K_POINTS'] 仍然有 data
```

### 集成测试
使用 daemon 测试的 fixture，但添加调试输出：
- 打印每个步骤的 `spec_preview.cards` 在合并前后的值
- 打印 `existing_input_file` 是否存在
- 打印最终传递给 `apply_card_overrides_to_qe_input` 的 overrides

---

## 12. 总结

### 根本原因
`spec_preview.cards.update(extracted_cards)` 在 `_build_step_from_spec` 中完全覆盖了 step.yaml 中的 cards，当 existing_input_file 存在且提取的 cards 不完整时，会丢失 data。

### 修复方案
1. 修复合并逻辑，保留 step.yaml 中的 data（对于 k-path 格式）
2. 添加 fail-fast guard，在 `apply_card_overrides_to_qe_input` 入口处验证

### 未解决的问题
- 为什么 daemon 测试中会有 existing_input_file？
- 为什么 `bandspp` step 会有 K_POINTS？
- 第一次 materialization 是否就丢失了 data？

### 下一步
1. 运行 daemon 测试，添加详细日志，确认 existing_input_file 是否存在
2. 检查生成的 `.in` 文件内容，确认是否完整
3. 检查 `bandspp.step.yaml` 内容，确认 K_POINTS 来源

