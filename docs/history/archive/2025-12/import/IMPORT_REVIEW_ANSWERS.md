# Demo Importer Review - 代码定位结果

## 问题 1: Structure 提取逻辑

### 定位结果：

1. **文件路径**: `src/qmatsuite/io/structure_io.py`
   - **函数名**: `structure_from_qe_input(qe_input: QEInput) -> PMGStructure`
   - **说明**: 从 QEInput 对象提取 pymatgen Structure，处理 ibrav 规则和 CELL_PARAMETERS/ATOMIC_POSITIONS

2. **文件路径**: `src/qmatsuite/calculation/importers.py`
   - **函数名**: `build_step_spec_from_qe_input()`
   - **说明**: 从单个 QE input 文件创建 step spec，内部调用 `structure_from_qe_input()` 提取 structure（第138行），每个 input 文件都会提取一次 structure

3. **文件路径**: `tools/import_tutorial_datasets.py`
   - **函数名**: `materialize_project_from_input_folder()`
   - **说明**: 核心函数，从第一个完整的 .in 文件提取 structure（第204-212行），使用 `find_structure_file()` 找到第一个有完整结构信息的文件，然后只从该文件导入 structure 到 project

4. **文件路径**: `src/qmatsuite/calculation/importers.py`
   - **函数名**: `build_calculation_from_qe_inputs()`
   - **说明**: 从多个 QE input 文件创建 calculation，**固定一个 structure_id 传给所有 steps**（第330-345行）：
     - 第330行：生成一个 ULID 作为 `structure_id`
     - 第343行：所有 step 都使用同一个 `structure_id`
     - 第348-351行：验证所有 steps 共享同一个 `structure_id`

5. **文件路径**: `src/qmatsuite/api.py`
   - **函数名**: `QMSService.import_step_from_qe_input()`
   - **说明**: 导入 step 时，每个 input 文件都会调用 `build_step_spec_from_qe_input()`（第4220行），但会检查 structure 是否已存在（第4237-4245行），如果已存在则复用，否则注册新 structure（第4247-4291行）

**结论**：
- **当前 importer 只从第一个 .in 文件建立 structure**（`materialize_project_from_input_folder()` 中）
- `build_calculation_from_qe_inputs()` **固定一个 structure_id 传给所有 steps**
- 但 `QMSService.import_step_from_qe_input()` 每个 step 都会尝试提取 structure，然后去重注册

---

## 问题 2: 多 Structure 支持

### 定位结果：

1. **文件路径**: `src/qmatsuite/project/snapshot.py`
   - **数据结构**: `ProjectSnapshot.structures: List[Dict[str, Any]]`（第61行）
   - **说明**: snapshot 里 `structures` 是 **List**，支持多个 structure

2. **文件路径**: `src/qmatsuite/calculation/structure_steps.py`
   - **数据结构**: `StructureStepSpec.structure_id: Optional[str]`（第46行）
   - **说明**: step spec 里 `structure_id` 是 **单值字段**（Optional[str]），每个 step 只能引用一个 structure

3. **文件路径**: `src/qmatsuite/api.py`
   - **函数名**: `QMSService.import_structure()`（第338行）
   - **说明**: **有"新增 structure 并返回 id"的接口**，返回 `ResolvedResource`，包含 structure 的 meta.id（ULID）

4. **文件路径**: `src/qmatsuite/api.py`
   - **函数名**: `QMSService.import_step_from_qe_input()`（第4247-4291行）
   - **说明**: 导入 step 时会自动检查并注册 structure，如果 structure 已存在则复用其 ID，否则创建新的并返回 ID

**结论**：
- ✅ **数据模型支持一个 project/calc 多个 structure**（snapshot.structures 是 List）
- ✅ **step spec 的 structure_id 是单值字段**（每个 step 只能引用一个 structure）
- ✅ **QMSService 有"新增 structure 并返回 id"的接口**（`import_structure()` 和 `import_step_from_qe_input()` 内部逻辑）

---

## 问题 3: Structure 等价/去重逻辑

### 定位结果：

1. **文件路径**: `src/qmatsuite/api.py`
   - **函数名**: `QMSService.import_step_from_qe_input()`（第4237-4245行）
   - **说明**: 有简单的去重逻辑：通过 `struct_file.samefile(structure_path)` 检查文件是否相同，如果相同则复用现有 structure_id

2. **搜索关键词**: `canonical`, `fingerprint`, `structure.*equal`, `structure.*compare`
   - **结果**: 未找到结构等价性比较或 fingerprint 工具

**结论**：
- ⚠️ **没有现成的 structure 等价/去重逻辑**（只有文件路径比较，没有结构内容比较）
- ❌ **没有 canonicalization / wrap 的统一入口**
- ❌ **没有结构 fingerprint（composition + lattice + frac coords）工具**
- 💡 **建议位置**: 如果实现，应该放在 `src/qmatsuite/core/structure_utils.py` 或 `src/qmatsuite/io/structure_io.py`

---

## 问题 4: Exporter 的 ATOMIC_SPECIES 来源

### 定位结果：

1. **文件路径**: `src/qmatsuite/calculation/structure_steps.py`
   - **函数名**: `generate_qe_input_from_spec()`（第311-387行）
   - **说明**: 生成 QE input 的流程：
     - 第332行：调用 `generate_qe_input_from_structure()` 从 structure 生成基础 QEInput（包含 ATOMIC_SPECIES card，使用 placeholder）
     - 第386行：调用 `apply_species_overrides_to_qe_input(qe_input, spec.species_overrides)` 应用 overrides

2. **文件路径**: `src/qmatsuite/io/structure_io.py`
   - **函数名**: `qe_input_from_structure()`（第130-208行）
   - **说明**: 从 structure 生成基础 QEInput，第154-163行创建 ATOMIC_SPECIES card，使用 `make_missing_pseudo_placeholder()` 作为默认 pseudo 文件名

3. **文件路径**: `src/qmatsuite/calculation/input_runner.py`
   - **函数名**: `apply_species_overrides_to_qe_input()`（第461-503行）
   - **说明**: 从 `species_overrides` 更新 ATOMIC_SPECIES card，**需要 QEInput 中已存在 ATOMIC_SPECIES card**（第470-472行），如果不存在则直接返回（不创建）

4. **文件路径**: `src/qmatsuite/calculation/structure_steps.py`
   - **函数名**: `generate_qe_input_from_structure()`（被 `generate_qe_input_from_spec()` 调用）
   - **说明**: 从 structure 生成 QEInput 时，会调用 `qe_input_from_structure()` 创建包含 ATOMIC_SPECIES 的基础 input

**结论**：
- ✅ **Exporter 从 `species_overrides` 更新 ATOMIC_SPECIES**（通过 `apply_species_overrides_to_qe_input()`）
- ✅ **基础 ATOMIC_SPECIES card 来自 `qe_input_from_structure()`**（使用 placeholder 作为默认）
- ⚠️ **当 step 没 overrides 时**：使用 `qe_input_from_structure()` 生成的默认值（placeholder pseudo 文件名）
- ❌ **没有 calc-level 或 project-level 的 pseudo map 作为默认值**

---

## 问题 5: Verify 流程实现位置

### 定位结果：

1. **文件路径**: `tools/import_tutorial_datasets.py`
   - **函数名**: `main()`（第1347行）
   - **说明**: `--verify` flag 入口，第1360-1363行定义 argparse，第1410-1418行调用 `verify_demo_project()` 进行详细验证

2. **文件路径**: `tools/import_tutorial_datasets.py`
   - **函数名**: `verify_demo_consistency()`（第1217行）
   - **说明**: 基础一致性验证，检查必需字段和结构

3. **文件路径**: `tools/import_tutorial_datasets.py`
   - **函数名**: `verify_demo_project()`（第1293行）
   - **说明**: 详细验证，使用 `ProjectSnapshot.from_dict()` 加载 demo，检查结构/计算/步骤数量

4. **文件路径**: `src/qmatsuite/calculation/structure_steps.py`
   - **函数名**: `generate_qe_input_from_spec()`（第311行）
   - **说明**: **Exporter 的调用点**，从 step spec 生成 QE input

5. **文件路径**: `src/qmatsuite/calculation/input_runner.py`
   - **函数名**: `prepare_qe_input()`（第200-276行）
   - **说明**: 准备 QE input 文件，内部调用 `generate_qe_input_from_spec()`（第240行），然后写入文件（第263行）

6. **文件路径**: `tools/import_tutorial_datasets.py`
   - **函数名**: `validate_roundtrip()`（在 `create_demo_from_dataset()` 中调用）
   - **说明**: Round-trip 验证的调用点，但目前是在 demo 创建后验证，不是在 materialize 过程中

**结论**：
- ✅ **`--verify` flag 入口在 `tools/import_tutorial_datasets.py` 的 `main()` 函数**
- ✅ **Materialize 后 exporter 的调用点在 `generate_qe_input_from_spec()`**（`structure_steps.py`）
- 💡 **Round-trip 验证目前不在 materialize 流程中**，而是在 demo 创建后单独验证
- 💡 **如果要插入 round-trip 验证**，应该在 `materialize_project_from_snapshot()` 之后，或直接在 `generate_qe_input_from_spec()` 调用后

---

## 总结

### 关键发现：

1. **Structure 提取**：当前只从第一个 .in 文件提取，但每个 step import 都会尝试提取（然后去重）
2. **多 Structure 支持**：✅ 数据模型支持，但 step 只能引用单个 structure
3. **Structure 去重**：❌ 只有文件路径比较，没有结构内容比较
4. **ATOMIC_SPECIES 来源**：从 `species_overrides` 更新，基础值来自 structure（placeholder）
5. **Verify 流程**：在 importer 脚本中实现，exporter 调用点在 `generate_qe_input_from_spec()`

### 潜在改进点：

1. 实现 structure 等价性比较（fingerprint）以支持真正的去重
2. 支持 step 级别的 structure 更新（relax 后使用新 structure）
3. 添加 calc/project 级别的 pseudo 默认配置
4. 在 materialize 流程中集成 round-trip 验证

