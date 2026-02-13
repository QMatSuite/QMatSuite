# QE Parameter JSON 使用边界 + 输入系统全链路风险审计报告

**审计日期**: 2025-01-XX  
**审计范围**: QuantumVITAS/QMatSuite 输入参数系统端到端审计  
**审计目标**: 识别 QE parameters JSON、namelist/card 分组、step/calc/structure YAML 体系的隐患

---

## Part 1 — 系统组件总览图

### 数据流链路

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. QE Input 文件 → Parser → step.yml                            │
└─────────────────────────────────────────────────────────────────┘

QE Input (.in)
    │
    ├─> QEInputParser.parse_file()
    │   └─> QEInput (namelists[], cards[], extra_data_lines[])
    │
    ├─> _extract_parameters(qe_input)
    │   └─> Dict[str, Dict[str, object]]  # {SECTION: {key: value}}
    │       └─> 直接从 namelist.name.upper() 提取，无 JSON 依赖
    │
    ├─> _extract_cards(qe_input)
    │   └─> Dict[str, Dict[str, object]]  # {CARD_NAME: {option, data}}
    │
    └─> step.yml
        └─> parameters: {SYSTEM: {...}, ELECTRONS: {...}}
            cards: {K_POINTS: {...}, ...}

┌─────────────────────────────────────────────────────────────────┐
│ 2. step.yml + presets → integration merge → generator → QE Input│
└─────────────────────────────────────────────────────────────────┘

step.yml (parameters: {SYSTEM: {...}, ELECTRONS: {...}})
    │
    ├─> parameter_dict_to_overrides(spec.parameters)
    │   └─> List[ParameterOverride]  # 保留 section 信息
    │
    ├─> generate_qe_input_from_structure()
    │   └─> qe_input_from_structure()  # 创建基础 QEInput
    │       └─> apply_parameter_overrides(qe_input, overrides)
    │           └─> _apply_parameter_overrides()  # ⚠️ 使用 JSON 验证
    │               └─> get_module_param_sections(module)  # JSON 查询
    │                   └─> 验证参数是否属于指定 section
    │
    └─> QEInputGenerator.write_file()
        └─> 直接写入 namelist.parameters，无 JSON 依赖

┌─────────────────────────────────────────────────────────────────┐
│ 3. UI → daemon RPC → presets catalog/detect/apply              │
└─────────────────────────────────────────────────────────────────┘

UI (Electron)
    │
    ├─> QVDaemon._handle_list_qe_parameter_metadata()
    │   └─> get_module_param_sections(module)  # JSON 查询
    │       └─> 返回 section → [param_names] 映射（用于 UI 展示）
    │
    ├─> detect_presets_from_calculation()
    │   └─> 直接从 step.yml parameters 读取，无 JSON 依赖
    │
    └─> apply_presets_to_step()
        └─> compile_dimension_patch_for_step()
            └─> 硬编码的 variant profiles（不依赖 JSON）

```

### 关键数据结构

**QEInput (内存模型)**
```python
class QEInput:
    namelists: List[QENamelist]  # [{name: "SYSTEM", parameters: {key: value}}]
    cards: List[QECard]
    extra_data_lines: List[str]
```

**step.yml (YAML 格式)**
```yaml
parameters:
  SYSTEM:
    ecutwfc: 60.0
    ecutrho: 240.0
  ELECTRONS:
    conv_thr: 1e-6
cards:
  K_POINTS:
    option: "automatic"
    data: [[4, 4, 4, 0, 0, 0]]
```

**ParameterOverride (中间转换)**
```python
@dataclass
class ParameterOverride:
    name: str
    value: Any
    section: Optional[str]  # 保留 section 信息
```

---

## Part 2 — QE parameters JSON 使用点清单

### 使用点分类

| 文件路径 | 函数/类名 | 行号范围 | 用途 | 是否违反"JSON 不是真相" | 建议 |
|---------|----------|---------|------|----------------------|------|
| `src/quantumvitas/data/qe_metadata.py` | `get_module_param_sections()` | 378-402 | **A** - 返回 section → [params] 映射 | ⚠️ **可能违反** | 改为 warning-only |
| `src/quantumvitas/calculation/input_runner.py` | `_apply_parameter_overrides()` | 442-512 | **A** - 验证参数是否属于指定 section | ⚠️ **可能违反** | 改为 warning-only |
| `src/quantumvitas/daemon/server.py` | `_handle_list_qe_parameter_metadata()` | 1519-1665 | **C** - UI 展示参数列表 | ✅ 合规 | 保留 |
| `src/quantumvitas/daemon/server.py` | `_handle_list_qe_ui_parameters()` | 1462-1517 | **C** - UI 展示 UI 参数 | ✅ 合规 | 保留 |
| `src/quantumvitas/presets/variants_registry.py` | `_compile_precision_patch_for_step()` | 297-393 | **B** - 读取 JSON 获取参数类型（用于 precision 计算） | ✅ 合规 | 保留 |
| `src/quantumvitas/data/qe_metadata.py` | `validate_ui_parameters()` | 547-597 | **B** - 验证 UI 参数是否存在于 JSON | ✅ 合规 | 保留 |

### 详细分析

#### ⚠️ 高风险使用点 1: `_apply_parameter_overrides()`

**位置**: `src/quantumvitas/calculation/input_runner.py:442-512`

**行为**:
```python
# 使用 JSON 验证参数是否属于指定 section
sections = get_module_param_sections(module_key)
param_to_sections: Dict[str, list[str]] = {}
for section_name, params in sections.items():
    for param in params:
        param_to_sections.setdefault(param.lower(), []).append(canonical_section)

# 如果参数不在 JSON 定义的 section 中，抛出 ValueError
if available_sections and candidate not in available_sections:
    raise ValueError(
        f"Parameter '{param_name}' does not belong to section '{override.section}' "
        f"for module '{module_key}'."
    )
```

**问题**: 
- **违反"JSON 不是真相"原则**：如果用户从 QE input 导入时，`ecutwfc` 被放在 `ELECTRONS`，系统会保留它（parser 是 schema-agnostic）
- 但如果用户通过 CLI 或 API 设置 `--ELECTRONS.ecutwfc=60`，`_apply_parameter_overrides()` 会**拒绝**它（因为 JSON 说 `ecutwfc` 属于 `SYSTEM`）
- **结果**: 导入路径和 CLI/API 路径行为不一致

**证据**: 实验 1 显示 parser 保留 `ecutwfc` 在 `ELECTRONS`，但 `_apply_parameter_overrides()` 会拒绝这种放置。

#### ⚠️ 高风险使用点 2: `get_module_param_sections()`

**位置**: `src/quantumvitas/data/qe_metadata.py:378-402`

**行为**:
```python
def get_module_param_sections(module: str) -> Dict[str, List[str]]:
    """Return mapping: section_name (e.g. 'CONTROL') -> list of parameter names."""
    sections: Dict[str, List[str]] = {}
    for meta in _iter_params(module):
        namelist = meta.get("namelist")
        section_name = f"&{namelist.upper()}"
        sections.setdefault(section_name, []).append(name)
    return {k: sorted(v) for k, v in sections.items()}
```

**问题**:
- 这个函数被广泛用于**推断**参数应该属于哪个 section
- 但 parser/generator **不依赖它**（它们直接从 QEInput.namelists 读取/写入）
- **结果**: 存在两个"真相"来源：
  1. QEInput.namelists（parser 提取的，来自实际 QE input）
  2. JSON（从 QE 文档提取的，理论上的归属）

**证据**: 实验 3 显示 JSON 定义 `ecutwfc` 属于 `&SYSTEM`，但 parser 可以保留它在 `ELECTRONS`。

### 合规使用点（C 类：UI 展示）

- `daemon/server.py:_handle_list_qe_parameter_metadata()`: 仅用于 UI 展示参数列表，不驱动行为
- `daemon/server.py:_handle_list_qe_ui_parameters()`: 仅用于 UI 展示，不驱动行为

### 合规使用点（B 类：诊断/提示）

- `presets/variants_registry.py:_compile_precision_patch_for_step()`: 读取 JSON 获取参数类型信息（如 `ecutwfc` 是 REAL），用于 precision 计算，这是**元数据查询**，不是行为驱动
- `qe_metadata.py:validate_ui_parameters()`: 验证 UI 参数定义是否与 JSON 一致，这是**一致性检查**，不是行为驱动

---

## Part 3 — "section 归属"真相审计

### 当前 YAML 为什么要区分 SYSTEM/ELECTRONS/cards？

**答案**: 
1. **QE input 语法要求**: QE 输入文件确实区分 namelist（`&SYSTEM`, `&ELECTRONS`）和 card（`K_POINTS`, `ATOMIC_POSITIONS`）
2. **Parser 保留结构**: `_extract_parameters()` 直接从 `QEInput.namelists` 提取，保留原始 section 信息
3. **Generator 需要 section**: `parameter_dict_to_overrides()` 保留 section 信息，`_apply_parameter_overrides()` 需要知道参数应该写入哪个 namelist

### ecutwfc 为何必须在 SYSTEM？如果用户放到别处会怎样？

**答案**:
1. **QE 实际要求**: 根据 QE 文档，`ecutwfc` 确实属于 `&SYSTEM` namelist
2. **如果用户放到别处**:
   - **Parser**: ✅ 会保留（实验 1 证明）
   - **Generator**: ✅ 会写入到用户指定的 section（`parameter_dict_to_overrides()` 保留 section）
   - **CLI/API**: ❌ `_apply_parameter_overrides()` 会拒绝（如果 JSON 说它不属于该 section）
   - **QE 执行**: ⚠️ QE 可能忽略或报错（取决于 QE 版本和参数）

**关键发现**: 
- **Parser/Generator 是 schema-agnostic**（不纠正错误放置）
- **但 `_apply_parameter_overrides()` 是 schema-enforcing**（拒绝错误放置）
- **结果**: 导入路径和 CLI/API 路径行为不一致

### 是否要求"写在正确 section 才会被 QE 接受"？

**答案**: 
- **QE 语法**: QE 确实要求参数在正确的 namelist 中
- **但 QE 的容错性**: 某些 QE 版本可能容忍参数在错误位置（忽略或警告），但这不是标准行为
- **我们的系统**: 
  - Parser 不验证（保留原样）
  - Generator 不验证（写入到用户指定的 section）
  - 只有 `_apply_parameter_overrides()` 验证（但仅用于 CLI/API 路径）

### Generator 如何确保写到正确位置？

**答案**: 
- **Generator 不确保**: `QEInputGenerator.generate_namelist()` 直接写入 `namelist.parameters`，不验证
- **确保的责任在**:
  1. `parameter_dict_to_overrides()`: 保留 step.yml 中的 section 信息
  2. `_apply_parameter_overrides()`: 验证参数是否属于指定 section（但仅用于 CLI/API 路径）

**问题**: 
- 如果 step.yml 中 `ecutwfc` 在 `ELECTRONS`，generator 会写入 `&ELECTRONS` namelist
- 没有机制纠正这种错误放置（除非通过 `_apply_parameter_overrides()`，但它不用于从 step.yml 生成）

---

## Part 4 — Parser/Generator 的 generality 证明

### 实验 1: 参数放错 section

**输入**: QE input 中 `ecutwfc` 在 `&ELECTRONS`

**结果**:
```
1. PARSED: ecutwfc 在 ELECTRONS ✓
2. EXTRACTED: ecutwfc 在 ELECTRONS ✓
3. GENERATED: ecutwfc 在 &ELECTRONS ✓
4. RE-PARSED: ecutwfc 在 ELECTRONS ✓
5. RE-EXTRACTED: ecutwfc 在 ELECTRONS ✓
```

**结论**: ✅ **Parser/Generator 是 schema-agnostic** - 它们保留参数在原始位置，不纠正

### 实验 2: 未知参数

**输入**: QE input 中 `unknown_key` 在 `&SYSTEM`

**结果**:
```
1. PARSED: unknown_key 在 SYSTEM ✓
2. EXTRACTED: unknown_key 在 SYSTEM ✓
3. GENERATED: unknown_key 在 &SYSTEM ✓
4. RE-PARSED: unknown_key 在 SYSTEM ✓
```

**结论**: ✅ **未知参数被保留** - roundtrip 成功

### 实验 3: JSON 依赖

**发现**:
- JSON 定义 `ecutwfc` 属于 `&SYSTEM`
- 但 parser 可以保留它在 `ELECTRONS`（如果 QE input 中就在那里）
- `_apply_parameter_overrides()` 使用 JSON 验证，但 parser/generator 不使用

**结论**: ⚠️ **部分 schema-dependent** - `_apply_parameter_overrides()` 依赖 JSON，但 parser/generator 不依赖

### 反证: Generator 的 schema 依赖

**场景**: 从 step.yml 生成 QE input

**流程**:
1. `step.yml` → `parameter_dict_to_overrides()` → 保留 section 信息
2. `generate_qe_input_from_structure()` → 创建基础 QEInput
3. `apply_parameter_overrides()` → 调用 `_apply_parameter_overrides()`
4. `_apply_parameter_overrides()` → **使用 JSON 验证** section 归属

**结论**: ⚠️ **Generator 路径部分依赖 JSON** - 虽然 `QEInputGenerator` 本身不验证，但 `_apply_parameter_overrides()` 在生成路径中被调用，会验证 section 归属

---

## Part 5 — 风险清单（≥10条）+ 最小防护策略

### 风险 1: Parser/Generator 与 `_apply_parameter_overrides()` 行为不一致 ⚠️⚠️⚠️

**影响**: 
- 导入路径（parser）允许参数在错误 section
- CLI/API 路径（`_apply_parameter_overrides()`）拒绝参数在错误 section
- 用户可能通过导入创建"无效"的 step.yml，但无法通过 CLI/API 修改

**触发条件**:
- 用户导入包含参数在错误 section 的 QE input
- 或手动编辑 step.yml 将参数放到错误 section

**最小防护策略**:
1. **Contract test**: 验证 parser → generator roundtrip 与 `_apply_parameter_overrides()` 行为一致
2. **Enforcement test**: 在 `_apply_parameter_overrides()` 中添加 `--warn-only` 模式，允许但警告错误放置
3. **文档约束**: 明确说明导入路径和 CLI/API 路径的行为差异

### 风险 2: step.yml 中参数在错误 section 会被保留并生成无效 QE input ⚠️⚠️⚠️

**影响**:
- step.yml 中 `ecutwfc` 在 `ELECTRONS` → generator 写入 `&ELECTRONS` → QE 可能忽略或报错
- 用户可能不知道参数放错了位置

**触发条件**:
- 导入包含错误 section 的 QE input
- 手动编辑 step.yml

**最小防护策略**:
1. **Contract test**: 验证生成的 QE input 中参数在正确 section
2. **Enforcement test**: 在 `generate_qe_input_from_spec()` 中添加验证步骤，检查参数是否在正确 section（使用 JSON），警告但不阻止
3. **CI grep tripwire**: 检查测试用例中是否有参数在错误 section 的示例

### 风险 3: JSON 与 QE 实际行为 drift ⚠️⚠️

**影响**:
- JSON 是从 QE 文档提取的，可能与实际 QE 行为不一致
- 如果 QE 新版本允许参数在多个 section，JSON 可能过时

**触发条件**:
- QE 版本更新
- JSON 未及时更新

**最小防护策略**:
1. **Contract test**: 定期验证 JSON 与 QE 实际行为一致（运行 QE 测试）
2. **文档约束**: 明确说明 JSON 来源和更新流程
3. **CI grep tripwire**: 检查 JSON schema version 是否更新

### 风险 4: `parameter_dict_to_overrides()` 不验证 section 归属 ⚠️⚠️

**影响**:
- step.yml 中的 section 信息直接传递到 generator，无验证
- 如果 step.yml 中 `ecutwfc` 在 `ELECTRONS`，generator 会写入 `&ELECTRONS`

**触发条件**:
- step.yml 中参数在错误 section

**最小防护策略**:
1. **Enforcement test**: 在 `parameter_dict_to_overrides()` 中添加可选验证（警告模式）
2. **文档约束**: 明确说明 step.yml 中 section 归属的约束

### 风险 5: 未知参数可能被 QE 忽略但系统保留 ⚠️

**影响**:
- 系统保留未知参数（实验 2 证明）
- 但 QE 可能忽略它们，用户可能不知道

**触发条件**:
- 用户添加未知参数到 step.yml 或 QE input

**最小防护策略**:
1. **Contract test**: 验证未知参数在 roundtrip 中被保留
2. **文档约束**: 明确说明未知参数的处理策略

### 风险 6: `_extract_parameters()` 不验证 section 归属 ⚠️

**影响**:
- 从 QE input 提取参数时，不验证参数是否在正确 section
- 错误放置的参数会被保留到 step.yml

**触发条件**:
- 导入包含错误 section 的 QE input

**最小防护策略**:
1. **Enforcement test**: 在 `_extract_parameters()` 中添加可选验证（警告模式）
2. **文档约束**: 明确说明导入时的行为

### 风险 7: Presets 编译不验证 section 归属 ⚠️

**影响**:
- `compile_dimension_patch_for_step()` 生成的参数可能被放到错误 section（如果 variant profile 定义错误）

**触发条件**:
- Variant profile 定义错误

**最小防护策略**:
1. **Contract test**: 验证 presets 编译生成的参数在正确 section
2. **Enforcement test**: 在 presets 编译时验证 section 归属

### 风险 8: UI 参数列表依赖 JSON，可能与实际 step.yml 不一致 ⚠️

**影响**:
- UI 显示参数列表来自 JSON
- 但 step.yml 可能包含 JSON 中不存在的参数（未知参数）

**触发条件**:
- step.yml 包含未知参数

**最小防护策略**:
1. **Contract test**: 验证 UI 参数列表与实际 step.yml 一致
2. **文档约束**: 明确说明 UI 参数列表的来源

### 风险 9: `_apply_parameter_overrides()` 的验证逻辑可能过于严格 ⚠️

**影响**:
- 如果 QE 实际允许参数在多个 section，但 JSON 只定义一个，`_apply_parameter_overrides()` 会拒绝
- 用户可能无法使用某些合法的 QE 配置

**触发条件**:
- QE 允许参数在多个 section（某些参数可能确实如此）
- JSON 只定义一个 section

**最小防护策略**:
1. **Contract test**: 验证 `_apply_parameter_overrides()` 的验证逻辑与 QE 实际行为一致
2. **Enforcement test**: 添加 `--warn-only` 模式，允许但警告

### 风险 10: step.yml 中 section 名称大小写不一致 ⚠️

**影响**:
- `_extract_parameters()` 使用 `namelist.name.upper()`，统一为大写
- 但如果用户手动编辑 step.yml，可能使用小写
- `parameter_dict_to_overrides()` 保留原始大小写

**触发条件**:
- 手动编辑 step.yml 使用小写 section 名称

**最小防护策略**:
1. **Contract test**: 验证 section 名称大小写处理一致
2. **Enforcement test**: 在 `parameter_dict_to_overrides()` 中规范化 section 名称

### 风险 11: Cards 与 Namelists 的区分可能模糊 ⚠️

**影响**:
- Cards 和 Namelists 在 YAML 中分开存储（`parameters` vs `cards`）
- 但如果用户混淆，可能导致问题

**触发条件**:
- 用户手动编辑 step.yml

**最小防护策略**:
1. **文档约束**: 明确说明 cards 和 namelists 的区别
2. **Enforcement test**: 验证 cards 不会被误放到 parameters

### 风险 12: `_remove_structure_parameters()` 可能移除必要的参数 ⚠️

**影响**:
- `_extract_parameters()` 调用 `_remove_structure_parameters()` 移除结构相关参数
- 但如果某些参数既用于结构又用于其他目的，可能被误移除

**触发条件**:
- 参数既用于结构又用于其他目的

**最小防护策略**:
1. **Contract test**: 验证 `_remove_structure_parameters()` 不会误移除参数
2. **文档约束**: 明确说明哪些参数会被移除

---

## 实验输出

### 实验 1: 参数放错 section

```
EXPERIMENT 1: Misplaced Parameter (ecutwfc in ELECTRONS)
✓ RESULT: ecutwfc STAYED in ELECTRONS (preserved as-is)
```

**结论**: Parser/Generator 是 schema-agnostic，保留参数在原始位置。

### 实验 2: 未知参数

```
EXPERIMENT 2: Unknown Parameter (unknown_key in SYSTEM)
✓ RESULT: unknown_key PRESERVED (roundtrip successful)
```

**结论**: 未知参数被保留，roundtrip 成功。

### 实验 3: JSON 依赖

```
EXPERIMENT 3: Section Assignment Source (JSON dependency)
✓ Found in &SYSTEM: [...]
✓ NOT in &ELECTRONS: [...]
CONCLUSION: JSON defines which section each parameter belongs to.
This is used by _apply_parameter_overrides() to validate placement.
```

**结论**: JSON 定义 section 归属，但 parser/generator 不依赖它。

---

## 总结与建议

### 关键发现

1. **Parser/Generator 是 schema-agnostic**: 它们保留参数在原始位置，不纠正错误放置
2. **`_apply_parameter_overrides()` 是 schema-enforcing**: 它使用 JSON 验证参数是否属于指定 section
3. **行为不一致**: 导入路径（parser）允许错误放置，CLI/API 路径（`_apply_parameter_overrides()`）拒绝错误放置
4. **JSON 使用边界**: JSON 主要用于 UI 展示和验证，但 `_apply_parameter_overrides()` 使用它驱动行为（可能违反"JSON 不是真相"原则）

### 建议

1. **统一行为**: 让 `_apply_parameter_overrides()` 的行为与 parser 一致（允许但警告错误放置）
2. **明确文档**: 明确说明导入路径和 CLI/API 路径的行为差异
3. **添加验证**: 在生成路径中添加可选验证（警告模式），但不阻止
4. **Contract tests**: 添加测试验证 parser → generator roundtrip 与 `_apply_parameter_overrides()` 行为一致

---

**审计完成**

