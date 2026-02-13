# LAMMPS 集成修复审计报告

## 1. 执行摘要

当前 LAMMPS 集成存在**架构污染**问题，必须回滚并重新实现。关键问题：

1. **错误复用 VASPRecipe**：`recipes.py` 把 `"lammps": VASPRecipe` 是严重错误
2. **structure_steps.py 污染**：添加 `is_lammps_step` early return 是绕路做法
3. **species_map gate 位置错误**：条件化检查放在 QE PATH 内部，而非正确的入口

---

## 2. 组件完整度评估

### 2.1 Engine Discovery

| 项目 | 状态 | 说明 |
|------|------|------|
| `lammps_resolver.py` | ✅ 已满足 | 正确实现优先级：ENV → brew → apt → conda → PATH |
| 可执行名搜索 | ✅ 已满足 | 支持 `lmp_serial`, `lmp_mpi`, `lmp` |
| brew 路径检测 | ✅ 已满足 | `/opt/homebrew/opt/lammps/bin/lmp_serial` |

**位置**：`src/quantumvitas/core/engines/lammps_resolver.py:19-117`

### 2.2 Recipe / JobGraph

| 项目 | 状态 | 说明 |
|------|------|------|
| Recipe 映射 | ❌ 错误 | `"lammps": VASPRecipe` 必须替换 |
| LAMMPSRecipe 类 | ❌ 缺失 | 需要实现独立的 LAMMPSRecipe |
| 文件布局 | ❌ 不兼容 | VASPRecipe 硬编码 POSCAR/INCAR/OUTCAR |

**问题证据**：
```python
# src/quantumvitas/execution/recipes.py:572-578
recipes = {
    "qe": QERecipe,
    "orca": ORCARecipe,
    "pyscf": PySCFRecipe,
    "vasp": VASPRecipe,
    "lammps": VASPRecipe,  # ❌ 必须回滚
}
```

VASPRecipe 硬编码：
- 输入文件：`POSCAR`, `INCAR`, `KPOINTS`, `POTCAR`（第293-298行）
- 输出文件：`OUTCAR`, `OSZICAR`（第301-304行）
- metadata：`"engine": "vasp"`（第326行）

LAMMPS 需要：
- 输入文件：`in.lammps`, `structure.data`, `*.eam`/`*.tersoff`
- 输出文件：`log.lammps`, `*.lammpstrj`, `final.data`
- metadata：`"engine": "lammps"`

### 2.3 Runner Integration

| 项目 | 状态 | 说明 |
|------|------|------|
| Step0 pseudo prep 条件化 | ⚠️ 部分 | `if calculation.species_map:` 仅跳过 prep，不阻止后续 |
| engine_family 检测 | ✅ 已满足 | runner.py:376 正确检测 `engine_family == "lammps"` |
| potential_assets_sha | ✅ 已满足 | runner.py:378-379 正确计算 |

### 2.4 Materialize

| 项目 | 状态 | 说明 |
|------|------|------|
| `LammpsEngine.materialize_inputs()` | ✅ 已满足 | 正确生成 `in.lammps`, `structure.data` |
| `structure_steps.py` early return | ❌ 污染 | 必须移除 `is_lammps_step` 检测 |
| Jinja2 模板 | ✅ 已满足 | `minimize.in.j2`, `md_*.in.j2` |

**污染证据**：
```python
# src/quantumvitas/calculation/structure_steps.py:785-787
LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}
is_lammps_step = step_type_lower in LAMMPS_STEP_TYPES or calculation_engine_family == "lammps"

# src/quantumvitas/calculation/structure_steps.py:1099-1118
if is_lammps_step:  # ❌ 必须移除
    logger.info(...)
    # ... 返回 dummy input file path
    return generated_input, spec_obj
```

**正确的架构**：LAMMPS 的 materialize 应该完全由 `LammpsEngine.materialize_inputs()` 处理，不应进入 `materialize_step_spec()`。

### 2.5 Assets Staging

| 项目 | 状态 | 说明 |
|------|------|------|
| `lammps_potentials.py` | ✅ 已满足 | `stage_potentials()` 正确实现 |
| `potential_map` schema | ✅ 已满足 | 类比 `species_map` |
| `compute_potential_assets_sha()` | ✅ 已满足 | hash_utils.py:371+ |

### 2.6 Output Parsing

| 项目 | 状态 | 说明 |
|------|------|------|
| `lammps_parser.py` | ✅ 已满足 | `parse_lammps_log()`, `parse_lammps_dump()` |
| Thermo 解析 | ✅ 已满足 | 支持多种 thermo_style |
| Trajectory 解析 | ✅ 已满足 | dump 格式支持 |
| 单位转换 | ✅ 已满足 | LJ/real/metal 单位 |

### 2.7 Relax Handler

| 项目 | 状态 | 说明 |
|------|------|------|
| `lammps_relax_handler.py` | ✅ 已满足 | 解析 `final.data`，生成 `current.json` |
| 与 runner 集成 | ⚠️ 未验证 | 需要在 handler 分发逻辑中检查 |

### 2.8 Manifest/Digest

| 项目 | 状态 | 说明 |
|------|------|------|
| pseudo_set_sha 复用 | ✅ 已满足 | LAMMPS 用 potential_assets_sha 填充 |
| step_sha | ✅ 已满足 | 通用逻辑 |
| structure_sha | ✅ 已满足 | 通用逻辑 |

### 2.9 Tests

| 项目 | 状态 | 说明 |
|------|------|------|
| 单元测试 | ✅ 已满足 | `test_lammps_engine.py` 25+ tests |
| 集成测试 | ❌ 失败 | 报"缺二进制"但 brew 已安装 |
| `requires_lammps` marker | ⚠️ 需检查 | marker 与 discovery 逻辑可能不一致 |
| sha256 import | ⚠️ 需统一 | 从 `pseudo_provenance` 导入是正确的 |

### 2.10 CI

| 项目 | 状态 | 说明 |
|------|------|------|
| GitHub Actions jobs | ✅ 已满足 | `test-lammps-mac`, `test-lammps-ubuntu` |
| brew/apt 安装 | ✅ 已满足 | CI 配置正确 |

---

## 3. 关键问题分析

### 3.1 为什么系统会把 LAMMPS 当 QE？

**调用链分析**：

1. `QVService.run_calculation()` 或 `CalculationRunner.run()` 被调用
2. `runner.py:154` 检查 `if calculation.species_map:` - 对 LAMMPS 跳过 pseudo prep
3. `runner.py:422` 调用 `execute_calculation_steps()` 传入 engine_family
4. `execute_calculation_steps()` 获取 recipe 并 materialize
5. `get_recipe_for_engine()` 返回 VASPRecipe（❌ 错误）
6. VASPRecipe.materialize() 生成错误的 Job（VASP 文件布局）

**species_map gate 误伤的根源**：

在之前的修复中，species_map gate 被放在 `structure_steps.py:1193`（QE PATH 内部）：
```python
if is_project_run and requires_pseudopotentials:
    if not calculation_species_map:
        raise ValueError("Pseudopotential not configured...")
```

但问题是：
- 如果没有 `is_lammps_step` early return，LAMMPS 会进入 QE PATH
- 在 QE PATH 内，`requires_pseudopotentials` 会检测 engine_family
- 但这是**绕路做法**，因为 LAMMPS 根本不应该进入 `materialize_step_spec()`

**正确的架构**：
- LAMMPS 的 materialize 应该完全由 `LammpsEngine.materialize_inputs()` 处理
- `materialize_step_spec()` 是 QE 特定的函数，不应被其他引擎调用
- species_map gate 应该在 runner 层面的 Step0 条件化

### 3.2 为什么 integration tests 报"缺二进制"？

**可能原因**：

1. **marker 检测逻辑**：fixture 中的 `pytest.skip("LAMMPS not installed")` 可能被触发
2. **resolver 问题**：`resolve_lammps_bin()` 可能在 pytest 环境下行为不同
3. **PATH 问题**：pytest 子进程的 PATH 可能与 shell 不同

**验证步骤**（由 Auto 执行）：
```bash
brew --prefix lammps
ls -l /opt/homebrew/opt/lammps/bin
/opt/homebrew/opt/lammps/bin/lmp_serial -h | head -n 5
python -c "from quantumvitas.core.engines.lammps_resolver import resolve_lammps_bin; print(resolve_lammps_bin())"
```

### 3.3 Job/Recipe 泛化分析

**当前状态**：
- `QERecipe`：共享 workdir，step-run 模型
- `VASPRecipe`：isolated workdir per step，VASP 文件布局
- `ORCARecipe`：QC strong-chain 模型
- `PySCFRecipe`：QC weak-chain 模型

**LAMMPS 需求**：
- isolated workdir per step（与 VASP 类似）
- 但文件布局完全不同（`in.lammps`, `log.lammps` vs `INCAR`, `OUTCAR`）

**建议**：实现独立的 `LAMMPSRecipe`，不抽象 `IsolatedSingleStepRecipe`。
- 理由：过度抽象增加复杂度，VASP 和 LAMMPS 的差异大于相似
- 风险：两个引擎的文件布局、command、metadata 都不同

---

## 4. 必须修复的问题清单

| 优先级 | 问题 | 位置 | 修复 |
|--------|------|------|------|
| P0 | VASPRecipe 映射 | `recipes.py:577` | 替换为 LAMMPSRecipe |
| P0 | `is_lammps_step` 污染 | `structure_steps.py:785-787,1099-1118` | 完全移除 |
| P1 | 缺少 LAMMPSRecipe | `recipes.py` | 新增类实现 |
| P1 | species_map gate 位置 | - | 验证 runner 层面已正确条件化 |
| P2 | integration tests skip | `test_lammps_*.py` | 修复 discovery/marker |
| P2 | sha256 import 统一 | `test_lammps_*.py` | 已统一到 `pseudo_provenance` |

---

## 5. 文件变更清单

### 需要回滚/移除的代码

1. **`src/quantumvitas/execution/recipes.py:577`**
   ```python
   # 删除这一行
   "lammps": VASPRecipe,  # LAMMPS uses same recipe pattern as VASP (isolated workdirs)
   ```

2. **`src/quantumvitas/calculation/structure_steps.py:785-787`**
   ```python
   # 删除这三行
   LAMMPS_STEP_TYPES = {"lammps_relax", "lammps_md"}
   is_lammps_step = step_type_lower in LAMMPS_STEP_TYPES or calculation_engine_family == "lammps"
   ```

3. **`src/quantumvitas/calculation/structure_steps.py:1099-1118`**
   ```python
   # 删除整个 if is_lammps_step: 块
   if is_lammps_step:
       logger.info(...)
       ...
       return generated_input, spec_obj
   ```

### 需要新增的代码

1. **`src/quantumvitas/execution/recipes.py`**：新增 `LAMMPSRecipe` 类

### 需要验证的代码

1. **`src/quantumvitas/calculation/runner.py:154`**：`if calculation.species_map:` 已正确条件化
2. **`src/quantumvitas/execution/handlers.py`**：需要检查是否有 LAMMPS handler 分发

---

## 6. 结论

LAMMPS 集成**不是半截引擎**，核心组件（engine、parser、writer、resolver、potentials、handler）都已实现。但当前存在**架构污染**问题：

1. 错误复用 VASPRecipe
2. 在 structure_steps.py 添加 early return 绕路

修复后，LAMMPS 应该是完整接入的引擎，与 QE/VASP/ORCA/PySCF 并列。

