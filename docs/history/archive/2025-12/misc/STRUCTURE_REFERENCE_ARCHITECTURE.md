# Project/Calculation/Step 结构引用关系总结

## 1. ProjectSnapshot 结构

**文件**: `src/quantumvitas/project/snapshot.py:61-62`

```python
structures: List[Dict[str, Any]] = field(default_factory=list)
calculations: List[Dict[str, Any]] = field(default_factory=list)
```

- **structures**: 是一个 **List**（不是 Map/Dict）
- 每个元素是 `{"meta": {...}, "data": {...}}` 字典
- `meta.id` 是结构的 ULID（唯一标识符）

## 2. Calculation 的 structure 字段

**文件**: `src/quantumvitas/calculation/calculation.py:30, 47-77`

```python
structure: Optional[StructureRef] = None  # Legacy reference (backwards compat)
_structure_id: Optional[str] = None  # Cached structure_id from model

@property
def structure_id(self) -> Optional[str]:
    # 从 calculation.yaml 中的 structure_id 字段读取
    wf_model = load_calculation(calculation_yaml, self.project.root)
    self._structure_id = wf_model.structure_id
```

**文件**: `src/quantumvitas/core/models.py` (CalculationModel)

- Calculation 模型有 `structure_id: Optional[str]` 字段
- 存储在 `calculation.yaml` 中
- **Calculation 级别的 structure_id 是主要的引用方式**

## 3. StepSpec/Step YAML 的 structure 字段

**文件**: `src/quantumvitas/calculation/structure_steps.py:34-46`

```python
@dataclass(slots=True)
class StructureStepSpec:
    structure: str  # Legacy selector (backwards compat, not authoritative)
    structure_id: Optional[str] = None  # Canonical structure reference (ULID)
```

**关键注释** (line 97-99):
```python
# DAG + ID-only model: Step YAML does NOT contain structure_id.
# Structure is resolved from calculation.structure_id at execution time.
# Legacy structure_id/structure fields are accepted for backwards compatibility only.
```

**to_dict() 方法** (line 177):
- **明确排除 structure_id**：`if key in ["structure_id", "parent_calculation_id", "structure"]: continue`
- Step YAML **不保存** structure_id，完全继承自 calculation

## 4. 强制所有 steps 共用一个 structure 的硬约束

**文件**: `src/quantumvitas/calculation/importers.py:268-614`

**之前有约束** (已移除):
```python
# 之前可能有类似这样的代码（已移除）:
# assert all(r.structure_id == actual_structure_id for r in step_results), \
#     "All steps must share the same structure_id"
```

**当前状态**: 
- `build_calculation_from_qe_inputs()` **不再强制**所有 steps 共享同一个 structure_id
- 每个 step 可以有自己的 `structure_id`（从 `build_step_spec_from_qe_input` 返回）
- **没有 enforce 逻辑**

## 5. generate_qe_input_from_spec() 的结构来源

**文件**: `src/quantumvitas/calculation/structure_steps.py:311-336`

```python
def generate_qe_input_from_spec(
    structure: PMGStructure,  # ← 结构作为参数传入
    spec: StructureStepSpec,
    ...
) -> tuple[QEInput, list[ParameterOverride]]:
```

**调用链** (api.py:1239):
```python
# api.py:1216-1226
structure_resolved = require_structure(project_root, calculation.structure_id, ...)
structure = read_structure(structure_resolved.absolute_path)

# api.py:1239
qe_input, _ = generate_qe_input_from_spec(structure, spec)
```

**关键**: 
- `generate_qe_input_from_spec()` **从 calculation.structure_id 解析结构**，不是从 `spec.structure_id`
- 如果 `calculation.structure_id` 为 None，会失败

**结构解析逻辑** (`structure_steps.py:599-1065`):
```python
def _resolve_structure_for_spec(...):
    # 解析顺序：
    # 1. Step-local structure (legacy): spec.structure_id 或 spec.structure
    # 2. Calculation-based structure (preferred): calculation.structure_id
    # 3. Registry-based resolution
    # 4. Last-resort filesystem search
```

## 6. 如果 step 没有 structure (None) 会如何

**当前行为**:
- `generate_qe_input_from_spec(structure, spec)` **要求 structure 参数**
- 如果 `calculation.structure_id` 为 None，`require_structure()` 会失败
- `_resolve_structure_for_spec()` 如果所有解析都失败，会抛出 `FileNotFoundError`

**对于后处理步骤** (structure_steps.py:325):
```python
if step_type_lower in POST_PROCESSING_STEP_TYPES:
    return _generate_postprocessing_input(spec, extra_overrides)
```
- 某些后处理步骤（dos, bands, projwfc）使用 `_generate_postprocessing_input()`，**不依赖 structure 参数**
- 但 `generate_qe_input_from_spec()` 的签名仍然要求 `structure: PMGStructure` 参数

## 7. 最小结论

**当前架构**: **混合模式（calc-level + step-level structure supported）**

- **设计意图**: DAG + ID-only 模型，steps 继承 calculation.structure_id
- **实际实现**: 
  - Calculation 有 `structure_id` (Optional)
  - StepSpec 有 `structure_id` (Optional)，但 **不写入 YAML**（to_dict 时排除）
  - 执行时优先使用 calculation.structure_id，fallback 到 step.structure_id
  - **没有硬约束**强制所有 steps 共享同一个 structure

**最小可改动点**:

1. **`generate_qe_input_from_spec()` 签名** (`structure_steps.py:311`):
   - `structure: PMGStructure` → `structure: Optional[PMGStructure] = None`
   - 当 `structure is None` 且是后处理步骤时，使用 `_generate_postprocessing_input()`

2. **`_resolve_structure_for_spec()`** (`structure_steps.py:599`):
   - 允许返回 `None`（对于结构无关的步骤）
   - 调用方需要处理 `None` 情况

3. **`api.py:run_step()`** (`api.py:1216-1239`):
   - 当 `calculation.structure_id` 为 None 时，不调用 `require_structure()`
   - 对于结构无关的步骤，直接调用 `generate_qe_input_from_spec(None, spec)`

4. **`build_step_spec_from_qe_input()`** (`importers.py:138`):
   - 已修改：检查 `qe_input_has_structure()`，如果没有结构，`structure_id` 可以为 None

5. **`StepImportResult`** (`importers.py:30`):
   - 已修改：`structure_id: Optional[str]`，`structure_path: Optional[Path]`

## 关键文件路径总结

- **ProjectSnapshot**: `src/quantumvitas/project/snapshot.py:61` - `structures: List[Dict]`
- **Calculation.structure_id**: `src/quantumvitas/calculation/calculation.py:47` - `@property def structure_id()`
- **CalculationModel.structure_id**: `src/quantumvitas/core/models.py` - CalculationModel 类
- **StepSpec.structure_id**: `src/quantumvitas/calculation/structure_steps.py:46` - `structure_id: Optional[str]`
- **Step YAML 不保存 structure_id**: `src/quantumvitas/calculation/structure_steps.py:177` - `to_dict()` 排除
- **generate_qe_input_from_spec**: `src/quantumvitas/calculation/structure_steps.py:311` - 需要 `structure` 参数
- **结构解析**: `src/quantumvitas/calculation/structure_steps.py:599` - `_resolve_structure_for_spec()`
- **没有 enforce 约束**: `src/quantumvitas/calculation/importers.py:268` - `build_calculation_from_qe_inputs()` 不再强制

