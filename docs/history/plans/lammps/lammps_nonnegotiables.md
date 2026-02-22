# LAMMPS 集成不可妥协清单

本文档是 Auto 执行修复时的 checklist，**每条都必须满足**。

---

## 1. Recipe 架构

### ✅ LAMMPS 必须有独立的 LAMMPSRecipe

```python
# ✅ 正确
"lammps": LAMMPSRecipe,

# ❌ 绝对禁止
"lammps": VASPRecipe,
```

**理由**：
- VASPRecipe 硬编码 VASP 文件布局（POSCAR/INCAR/OUTCAR）
- LAMMPS 有完全不同的文件布局（in.lammps/log.lammps）
- 复用导致 metadata 错误、输入输出路径错误

### ✅ LAMMPSRecipe 必须包含

- `working_dir = calc_raw_dir / step.meta.id`（isolated workdir）
- `command = [executable, "-in", "in.lammps", "-log", "log.lammps"]`
- `metadata["engine"] = "lammps"`
- 正确的 `input_files` 和 `expected_outputs`

---

## 2. structure_steps.py 纯净性

### ✅ 禁止 LAMMPS 特殊处理

```python
# ❌ 绝对禁止以下代码存在于 structure_steps.py
LAMMPS_STEP_TYPES = {...}
is_lammps_step = ...
if is_lammps_step:
    return ...
```

**理由**：
- `structure_steps.py` 是 QE 特定的 materialize 函数
- LAMMPS 的 materialize 由 `LammpsEngine.materialize_inputs()` 处理
- 添加 early return 是污染和绕路

### ✅ LAMMPS step 不应进入 materialize_step_spec()

正确的调用路径：
```
runner → recipe.materialize() → LammpsEngine.materialize_inputs()
```

不应出现：
```
runner → materialize_step_spec() → [LAMMPS early return]
```

---

## 3. species_map Gate 条件化

### ✅ Gate 必须在正确的入口

**正确位置**：`runner.py` Step0 pseudo preparation

```python
# runner.py:154
if calculation.species_map:  # ✅ 条件化：无 species_map 则跳过
    # ... pseudo preparation
```

**错误位置**：`structure_steps.py` QE PATH 内部

```python
# ❌ 这是绕路做法，但如果必须保留，确保 LAMMPS 不进入此路径
if is_project_run and requires_pseudopotentials:
    raise ValueError("Pseudopotential not configured...")
```

### ✅ LAMMPS 不应触发 pseudo validation

- LAMMPS 使用 `potential_map`，不使用 `species_map`
- LAMMPS calculation 应该设置 `species_map = None` 或 `{}`
- runner 应该检测 engine_family 并跳过 pseudo gate

---

## 4. 测试真实性

### ✅ Integration Tests 必须真实运行

```python
# ❌ 禁止
pytest.skip("LAMMPS not installed")  # 当 brew 已安装时

# ✅ 正确
try:
    resolve_lammps_bin()
except FileNotFoundError:
    pytest.skip("LAMMPS not installed")  # 仅当真的找不到时
```

### ✅ 诊断优先于 Skip

如果 tests 报"缺二进制"但本机已安装：

1. **先诊断**：
   ```bash
   brew --prefix lammps
   ls -l /opt/homebrew/opt/lammps/bin
   python -c "from qmatsuite.core.engines.lammps_resolver import resolve_lammps_bin; print(resolve_lammps_bin())"
   ```

2. **再修复**：修 discovery/marker，不改 tests 去 skip

### ✅ sha256 Import 统一

```python
# ✅ 正确（从 pseudo_provenance 导入）
from qmatsuite.core.pseudo_provenance import compute_sha256_file

# ❌ 错误（不存在的函数）
from qmatsuite.calculation.hash_utils import compute_file_sha256
```

---

## 5. 不削弱现有引擎

### ✅ QE species_map 强制不变

移除 LAMMPS 污染后，QE 的 pseudo 逻辑**必须保持不变**：
- `species_map` 对 QE project-run 仍然强制
- pseudo staging 仍然按需执行
- 相关测试全部通过

### ✅ VASP/ORCA/PySCF 无回归

- VASPRecipe 继续用于 VASP
- ORCA/PySCF recipes 不受影响
- 所有现有测试通过

---

## 6. 验收命令

### 每个 PR 必须执行

```bash
source .venv/bin/activate
python -m pytest tests/ -v --tb=short -n auto --dist=loadfile
```

### 最终交付标准

```
============ X passed, 0 failed, 0 errors in Y seconds ============
```

其中 LAMMPS integration tests 必须在 passed 中，不在 skipped 中。

---

## 7. 宪法/规章对照

| 规章 | LAMMPS 实现 | 状态 |
|------|-------------|------|
| SSOT: calculation.yaml + step.yaml | potential_map 在 calculation.yaml | ✅ |
| Manifest 非 SSOT | 复用 pseudo_set_sha 字段 | ✅ |
| ULID 内部 ID | step_ulid 用于 workdir | ✅ |
| A/B 类参数 | A: units/atom_style; B: 透传 | ✅ |
| Recipe 独立 | LAMMPSRecipe 类 | 待实现 |
| Engine 独立 | LammpsEngine 类 | ✅ |
| 无 structure_steps 污染 | is_lammps_step 移除 | 待实现 |

---

## 8. Stop Conditions

如果遇到以下情况，**停止执行，报告证据**：

1. **移除 is_lammps_step 导致 > 10 个测试失败**
   - 说明：LAMMPS 路径可能有隐藏依赖
   - 动作：收集失败测试列表和堆栈

2. **LAMMPSRecipe 无法正确生成 JobGraph**
   - 说明：可能需要更大的 recipe 重构
   - 动作：收集 recipe 调用链和错误

3. **LAMMPS 二进制在 pytest 环境下始终无法发现**
   - 说明：PATH/subprocess 隔离问题
   - 动作：收集环境变量和 resolver 日志

4. **species_map gate 移除影响 QE 测试**
   - 说明：gate 位置可能不止一处
   - 动作：收集 QE 测试失败和调用链

