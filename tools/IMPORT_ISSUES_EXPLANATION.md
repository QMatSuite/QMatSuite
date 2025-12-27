# 导入问题详细解释

## 问题概述

当前导入器成功处理了 **12/28** 个数据集，失败 **16/28** 个。主要失败原因是 `CELL_PARAMETERS card required when ibrav == 0` 错误。

## 核心问题分析

### 问题 1: LR/TDDFT 计算文件缺少结构信息

**示例：`10_benzene_TDDFT` 数据集**

```python
# 文件结构分析
C6H6.0_relax.in:  # 参考文件
  - 模块: PW
  - ibrav = 6 (使用 celldm(1) = 32.0, celldm(3) = 0.83)
  - 有 ATOMIC_POSITIONS
  - 无 CELL_PARAMETERS (因为 ibrav != 0)

C6H6.1_scf.in:  # SCF 计算
  - 模块: PW
  - ibrav = 6
  - 有 ATOMIC_POSITIONS
  - 无 CELL_PARAMETERS

C6H6.2_tl.in:  # ❌ 失败的文件
  - 模块: UNKNOWN (实际上是 LR/TDDFT)
  - 只有 &LR_INPUT 和 &LR_CONTROL namelists
  - 没有 &SYSTEM namelist
  - 没有 CELL_PARAMETERS
  - 没有 ATOMIC_POSITIONS
```

**错误发生位置：**

```python
# src/quantumvitas/calculation/importers.py:138
def build_step_spec_from_qe_input(...):
    qe_input = QEInputParser.parse_file(input_path)
    structure = structure_from_qe_input(qe_input)  # ❌ 这里失败
    # ...
```

```python
# src/quantumvitas/io/structure_io.py:221
def structure_from_qe_input(qe_input: QEInput) -> PMGStructure:
    # ...
    lattice = _lattice_from_cell_card(cell_card, system)
    # ...
```

```python
# src/quantumvitas/io/structure_io.py:307
def _lattice_from_cell_card(cell_card, system):
    if not cell_card:
        raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")  # ❌ 错误在这里
```

**根本原因：**
- `C6H6.2_tl.in` 是 LR (TDDFT) 后处理计算，它不需要结构信息（使用之前计算的输出）
- 但 `build_step_spec_from_qe_input` 强制要求从每个输入文件中提取结构
- 当文件没有 `SYSTEM` namelist 或结构信息时，解析失败

### 问题 2: ibrav != 0 到 ibrav = 0 的转换

**场景：参考文件使用 ibrav != 0，后续文件使用 ibrav = 0**

```python
# 当前预处理逻辑 (folder_import.py:175-201)
if ibrav == 0 and not cell_card and reference_qe_input:
    ref_cell_card = reference_qe_input.get_card(QECardType.CELL_PARAMETERS)
    if ref_cell_card:
        # ✅ 情况1: 参考文件有 CELL_PARAMETERS，直接使用
        qe_input.cards.append(ref_cell_card)
    else:
        # ⚠️ 情况2: 参考文件使用 ibrav != 0，需要转换
        # 当前代码尝试提取结构并生成 CELL_PARAMETERS
        # 但可能在某些情况下失败
```

**问题：**
- 当参考文件使用 `ibrav=6`（或其他非零值）时，它没有 `CELL_PARAMETERS` 卡片
- 代码尝试从参考文件提取结构并生成 `CELL_PARAMETERS`，但：
  1. 如果提取失败（异常），文件被跳过
  2. 如果生成的 `CELL_PARAMETERS` 为空，文件被跳过
  3. 某些 LR 计算文件根本没有 `SYSTEM` namelist，无法确定 `ibrav`

### 问题 3: 预处理逻辑的局限性

**当前预处理流程：**

```python
# folder_import.py:112-149
# 1. 查找参考结构文件（第一个有完整结构的文件）
for input_file in input_files:
    if has_complete_structure:  # ibrav != 0 有参数，或 ibrav == 0 有 CELL_PARAMETERS
        reference_qe_input = qe_input
        break

# 2. 处理每个文件 (folder_import.py:151-201)
for input_file in input_files:
    if ibrav == 0 and not cell_card and reference_qe_input:
        # 尝试注入 CELL_PARAMETERS
        # ...
```

**局限性：**
1. **LR 计算文件**：没有 `SYSTEM` namelist，无法确定 `ibrav`，预处理逻辑无法处理
2. **异常处理**：当提取结构失败时，文件被跳过，但错误信息不够清晰
3. **模块检测**：LR 计算被识别为 `UNKNOWN` 模块，可能需要特殊处理

## 具体失败案例

### 案例 1: `10_benzene_TDDFT`

```
文件顺序：
1. C6H6.0_relax.in (ibrav=6, 有结构) ✅ 作为参考
2. C6H6.1_scf.in (ibrav=6, 有结构) ✅ 成功
3. C6H6.2_tl.in (LR 计算，无 SYSTEM) ❌ 失败
   - 没有 SYSTEM namelist
   - 无法确定 ibrav
   - structure_from_qe_input() 无法提取结构
```

### 案例 2: `12_NMR_gipaw__1_TMS_reference`

```
类似问题：某些文件是后处理计算（gipaw），不需要完整结构信息
```

### 案例 3: `04_Si_DOS`

```
文件顺序：
1. si.1_scf.in (有完整结构) ✅ 作为参考
2. si.2_nscf.in (可能有结构) ✅ 可能成功
3. si.3_dos.in (ibrav=0, 无 CELL_PARAMETERS) ❌ 失败
   - 需要从参考文件注入 CELL_PARAMETERS
   - 但可能注入失败或未执行
```

## 解决方案建议

### 方案 1: 跳过不需要结构的后处理步骤（推荐）

对于 LR、DOS、bands 等后处理计算，它们不需要结构信息，应该：
1. 检测文件类型（通过模块或 namelist）
2. 如果是后处理计算且没有结构信息，跳过结构提取
3. 或者使用前一步的结构

**代码位置：**
- `src/quantumvitas/calculation/importers.py:138` - 需要条件检查
- `src/quantumvitas/api.py:4254` - `import_step_from_qe_input` 可能需要特殊处理

### 方案 2: 改进预处理逻辑

1. **更好的参考文件选择**：优先选择有 `CELL_PARAMETERS` 的文件作为参考
2. **更健壮的转换**：从 `ibrav != 0` 到 `ibrav = 0` 的转换需要更完善的错误处理
3. **LR 计算处理**：检测 LR 计算并特殊处理（可能需要从之前的步骤获取结构）

### 方案 3: 允许结构可选

修改 `build_step_spec_from_qe_input` 允许某些步骤类型没有结构：
- 后处理步骤（dos, bands, projwfc, lr）可以使用前一步的结构
- 或者标记为"无结构"步骤

## 当前代码关键片段

### 错误触发点

```python
# src/quantumvitas/io/structure_io.py:307
def _lattice_from_cell_card(cell_card, system):
    if not cell_card:
        raise ValueError("CELL_PARAMETERS card required when ibrav == 0.")
    # ...
```

### 预处理逻辑

```python
# src/quantumvitas/calculation/folder_import.py:175-201
# Inject missing structure cards for ibrav=0 if a reference is available
cell_card = qe_input.get_card(QECardType.CELL_PARAMETERS)
if ibrav == 0 and not cell_card and reference_qe_input:
    ref_cell_card = reference_qe_input.get_card(QECardType.CELL_PARAMETERS)
    if ref_cell_card:
        # Reference has CELL_PARAMETERS, use it
        qe_input.cards.append(ref_cell_card)
    else:
        # Reference has ibrav != 0, extract structure and generate CELL_PARAMETERS
        try:
            ref_structure = structure_from_qe_input(reference_qe_input)
            # ... 生成 CELL_PARAMETERS
        except Exception:
            # Extraction failed, skip this file
            processed_input_files.append(input_file)
            continue
```

### 导入流程

```python
# src/quantumvitas/api.py:4254
import_result = build_step_spec_from_qe_input(
    input_file=input_file,
    # ...
)
# build_step_spec_from_qe_input 内部调用 structure_from_qe_input
# 如果文件没有结构信息，这里会失败
```

## 总结

主要问题：
1. **LR/TDDFT 计算文件**没有结构信息，但导入逻辑强制要求结构
2. **预处理逻辑**在某些情况下无法正确注入 `CELL_PARAMETERS`
3. **错误处理**不够完善，导致文件被静默跳过或失败

建议优先实现**方案 1**：检测后处理计算类型，允许它们使用前一步的结构或跳过结构提取。

