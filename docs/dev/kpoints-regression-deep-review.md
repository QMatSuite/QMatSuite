# K_POINTS.data 回归问题深度 Code Review

**日期**: 2025-01-XX  
**问题**: JobRunner 迁移后，3个 daemon 测试失败，K_POINTS.data 在 materialization 过程中丢失

---

## 问题定位

### 错误发生位置
```
apply_card_overrides_to_qe_input(qe_input, overrides)
  ↓
for card_name, payload in overrides.items():
  ↓
payload = {'option': 'crystal_b'}  # ❌ data 字段丢失
```

### 数据流路径分析

#### 路径1: 正常 materialization 路径
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ StructureStepSpec.from_yaml()
spec.cards = {'K_POINTS': {'option': 'crystal_b', 'data': [...]}} ✅
  ↓ materialize_step_spec()
  ↓ generate_qe_input_from_spec(structure, spec)
  ↓ apply_card_overrides_to_qe_input(qe_input, spec.cards)
payload = {'option': 'crystal_b'}  # ❌ data 丢失
```

#### 路径2: JobRunner 执行路径
```
step.yaml (有 cards.K_POINTS.data) ✅
  ↓ Step.resolve_input_path()
input_file = Path(...)  # 指向已生成的 .in 文件？
  ↓ Step.run()
  ↓ run_input_step(engine, input_file, ...)
  ↓ prepare_input_step(input_file, ..., card_overrides=?)
```

---

## 关键发现

### 1. Step.resolve_input_path() 的行为

**代码位置**: `src/quantumvitas/calculation/step.py:34-60`

```python
def resolve_input_path(self, calculation_raw_dir: Path) -> Path:
    path = Path(self.input_file)
    if not path.is_absolute():
        path = (calculation_raw_dir / path).resolve()
    return path
```

**关键点**:
- `Step.input_file` 指向的是**已生成的输入文件**（如 `bands.in`），不是 `step.yaml`
- 这个文件是在 `_build_step_from_spec` → `materialize_step_spec` 时生成的
- **问题**: 如果这个 `.in` 文件已经存在，`Step.run()` 会直接使用它，而不是重新从 `step.yaml` 生成

### 2. prepare_input_step() 的参数

**代码位置**: `src/quantumvitas/calculation/input_runner.py:199-209`

```python
def prepare_input_step(
    input_file: Path,
    working_dir: Path,
    project_root: Optional[Path] = None,
    parameter_overrides: Optional[Sequence[ParameterOverride]] = None,
    card_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,  # ← 这里
    species_overrides: Optional[Mapping[str, Mapping[str, Any]]] = None,
    ...
)
```

**关键点**:
- `card_overrides` 参数用于覆盖/合并 cards
- **问题**: `Step.run()` 调用 `run_input_step()` 时，**没有传递 `card_overrides`**
- 这意味着如果 `.in` 文件已经存在且不完整，不会用 `step.yaml` 中的 cards 来更新它

### 3. Step.run() 的调用链

**代码位置**: `src/quantumvitas/calculation/step.py:62-127`

```python
def run(self, ...):
    input_path = self.resolve_input_path(calculation_raw_dir)  # 指向 .in 文件
    result, _ = run_input_step(
        engine=engine.backend,
        input_file=input_path,  # ← 直接使用 .in 文件
        working_dir=calculation_raw_dir,
        project_root=project_root,
        step_type=step_type_value,
        timeout=timeout,
        species_map=species_map,
        # ❌ 没有传递 card_overrides！
    )
```

**关键点**:
- `Step.run()` **不传递 `card_overrides`**
- 如果 `input_file` 指向的 `.in` 文件已经存在，`prepare_input_step()` 会解析它
- 如果这个 `.in` 文件中的 K_POINTS 只有 `option` 没有 `data`，错误就会发生

---

## 根本原因假设

### 假设1: 第一次 materialization 时 data 就丢失了

**场景**:
1. `_build_step_from_spec` 调用 `materialize_step_spec`
2. `materialize_step_spec` 调用 `generate_qe_input_from_spec`
3. `generate_qe_input_from_spec` 调用 `apply_card_overrides_to_qe_input(qe_input, spec.cards)`
4. **此时 `spec.cards['K_POINTS']` 只有 `{'option': 'crystal_b'}`，没有 `data`**

**需要验证**: `spec.cards` 在传递给 `apply_card_overrides_to_qe_input` 时是否完整

### 假设2: 已存在的 .in 文件覆盖了 step.yaml

**场景**:
1. 第一次运行生成了不完整的 `bands.in`（只有 `option`，没有 `data`）
2. 第二次运行时，`Step.resolve_input_path()` 返回这个已存在的 `.in` 文件
3. `prepare_input_step()` 解析这个 `.in` 文件，得到不完整的 K_POINTS
4. 因为没有传递 `card_overrides`，所以不会用 `step.yaml` 中的完整 cards 来更新

**需要验证**: 
- daemon 测试中是否会有已存在的 `.in` 文件？
- JobRunner 迁移是否改变了 materialization 的时机？

### 假设3: JobRunner 迁移引入了新的代码路径

**场景**:
- JobRunner 迁移可能改变了何时/如何 materialize steps
- 可能在某些情况下跳过了正常的 materialization 路径
- 可能直接从已存在的 `.in` 文件读取，而不是从 `step.yaml` 生成

**需要验证**: 
- `execution/recipes.py` 和 `execution/handlers.py` 中的 materialization 逻辑
- 是否有新的代码路径直接读取 `.in` 文件而不是从 `step.yaml` 生成

---

## 需要检查的关键代码位置

### 1. materialize_step_spec() 中的 cards 处理
**文件**: `src/quantumvitas/calculation/structure_steps.py:1112`
```python
qe_input, _ = generate_qe_input_from_spec(structure, spec_obj, species_map=calculation_species_map)
```
- **检查**: `spec_obj.cards` 在此时是否完整？

### 2. generate_qe_input_from_spec() 中的 cards 传递
**文件**: `src/quantumvitas/calculation/structure_steps.py:571`
```python
apply_card_overrides_to_qe_input(qe_input, spec.cards)
```
- **检查**: `spec.cards` 在此时是否完整？

### 3. Step.run() 中是否传递 card_overrides
**文件**: `src/quantumvitas/calculation/step.py:99-107`
- **检查**: 是否应该从 `step.yaml` 读取 cards 并作为 `card_overrides` 传递？

### 4. JobRunner handler 中的 materialization
**文件**: `src/quantumvitas/execution/handlers.py:112`
```python
result = step.run(...)
```
- **检查**: 在调用 `step.run()` 之前，是否应该确保 input 文件是最新的？

---

## 建议的修复方向

### 方向1: 确保 materialization 时 cards 完整
- 在 `generate_qe_input_from_spec` 中添加断言，确保 `spec.cards['K_POINTS']` 有 `data`
- 如果缺失，从 `step.yaml` 重新加载

### 方向2: Step.run() 时从 step.yaml 读取 cards
- 修改 `Step.run()`，在调用 `run_input_step()` 之前，从 `step.yaml` 读取 cards
- 将 cards 作为 `card_overrides` 传递给 `run_input_step()`

### 方向3: 确保 input 文件总是从 step.yaml 生成
- 修改 `Step.run()`，总是从 `step.yaml` 重新生成 input 文件
- 或者检查 input 文件的时间戳，如果 `step.yaml` 更新了，重新生成

---

## 下一步行动

1. **添加调试日志**，在关键位置记录 `spec.cards` 和 `overrides` 的值
2. **检查 JobRunner 迁移的变更**，看是否引入了新的代码路径
3. **验证假设2**，检查 daemon 测试中是否有已存在的 `.in` 文件
4. **实现修复**，根据根本原因选择合适的修复方向

