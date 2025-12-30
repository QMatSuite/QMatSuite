# Demo Snapshot Pseudo Family Fix Report

**Date**: Code-only audit and fix  
**Scope**: Ensure demo generation scripts write `pseudo_sha_family` (not `pseudo_sha_token`)  
**Method**: Extract behavior from code, fix scripts, add regression tests

---

## 任务 A：定位生成 demo 的两个脚本

### 找到的脚本

1. **`tools/generate_demo_snapshots.py`**
   - **入口**: `main()` 函数
   - **运行方式**: `python tools/generate_demo_snapshots.py`
   - **用途**: 从 `tests/data/project_examples/` 导出多个 demo 项目到 `resources/demo_projects/`
   - **生成的 demo**: `si_bands_demo.yml`, `si_dos_demo.yml`
   - **调用**: `export_project_to_snapshot()` (来自 `src/quantumvitas/project/snapshot.py`)

2. **`tools/regenerate_si_bands_demo.py`**
   - **入口**: `main()` 函数
   - **运行方式**: `python tools/regenerate_si_bands_demo.py`
   - **用途**: 仅重新生成 `si_bands_demo.yml`
   - **调用**: `export_project_to_snapshot()` (来自 `src/quantumvitas/project/snapshot.py`)

### 核心函数

两个脚本都调用 `export_project_to_snapshot()` 函数（位于 `src/quantumvitas/project/snapshot.py`），这是真正写入 `species_map` 的地方。

---

## 任务 B：审计脚本输出是否包含 sha_family

### 审计结果

**修复前**:
- `export_project_to_snapshot()` 在第 380-391 行调用 `migrate_species_overrides_to_calc()`
- `migrate_species_overrides_to_calc()` 只迁移 `pseudopot` 和 `mass`，不计算 `sha256` 或 `sha_family`
- 生成的 snapshot 只有 `pseudopot`，缺少 `pseudo_sha256` 和 `pseudo_sha_family`

**修复后**:
- 在 `export_project_to_snapshot()` 中添加了增强逻辑（第 393-428 行）
- 如果 `species_map` 只有 `pseudopot` 但缺少 `sha256` 或 `sha_family`，从 `project_root/pseudo/` 读取文件并计算
- 生成的 snapshot 现在包含完整的 triplet: `pseudo_basename`, `pseudo_sha256`, `pseudo_sha_family`

### 验证结果

运行 `python tools/generate_demo_snapshots.py` 后：

```yaml
# resources/demo_projects/si_bands_demo.yml (修复后)
species_map:
  Si:
    mass: 28.0855
    pseudopot: Si.pbe-n-rrkjus_psl.1.0.0.UPF
    pseudo_sha256: <computed>
    pseudo_sha_family: 9d5fdea5cc45742d1254e8023b481a202b0022642b381478e6195db3d81e2723
    pseudo_basename: Si.pbe-n-rrkjus_psl.1.0.0.UPF
```

**确认**: ✅ 生成的 YAML 包含 `pseudo_sha_family`，且没有 `pseudo_sha_token`

---

## 任务 C：修复脚本（只改字段与 hash，不改语义）

### 修改的文件

1. **`src/quantumvitas/project/snapshot.py`**

   **修改位置**: `export_project_to_snapshot()` 函数（第 393-428 行）

   **修改内容**:
   - 在导出 `species_map` 之前，检查每个元素是否缺少 `pseudo_sha256` 或 `pseudo_sha_family`
   - 如果缺少且项目中有对应的 pseudo 文件，从文件计算并填充
   - 使用 `compute_sha256_file()` 和 `compute_sha_family_file()`（whitespace-strip 算法）

   **代码片段**:
   ```python
   # Enhance species_map with sha256 and sha_family if missing (migration from legacy format)
   if calc_species_map:
       from quantumvitas.core.pseudo_provenance import compute_sha256_file
       from quantumvitas.core.pseudo_libinfo import compute_sha_family_file
       
       project_pseudo_dir = project_root / "pseudo"
       for element, entry in calc_species_map.items():
           # ... compute sha256 and sha_family from file if missing ...
   ```

2. **`src/quantumvitas/project/snapshot.py`**

   **修改位置**: `materialize_project_from_snapshot()` 函数（第 682-693 行）

   **修改内容**:
   - 在 materialize 时清理遗留的 `pseudo_sha_token` 字段
   - 如果 snapshot 中有 `pseudo_sha_token`，删除它（因为 `sha_family` 应该被使用）

   **代码片段**:
   ```python
   # Clean up legacy pseudo_sha_token field if present (migration: sha_token → sha_family)
   if calc_species_map:
       for element, entry in calc_species_map.items():
           if "pseudo_sha_token" in entry:
               del entry["pseudo_sha_token"]
   ```

### 语义保持不变

- ✅ 不改变 selection/Step0/UI 的语义
- ✅ 只修复字段名和 hash 计算
- ✅ 使用现有的 `compute_sha_family_file()` 函数（whitespace-strip 算法）

---

## 任务 D：添加回归测试

### 新增测试文件

**`tests/unit/test_demo_snapshot_pseudo_family.py`**

### 测试用例

1. **`test_export_project2_bands_has_sha_family`**
   - 验证导出 `project2_bands` 生成的 snapshot 包含 `pseudo_sha_family`
   - 断言：如果有 `pseudo_sha256` 或 `pseudo_basename`，必须同时有 `pseudo_sha_family`
   - 断言：不能有 `pseudo_sha_token`

2. **`test_export_project1_has_sha_family`**
   - 验证导出 `project1` 生成的 snapshot 包含 `pseudo_sha_family`
   - 同样的断言规则

3. **`test_materialize_removes_sha_token`**
   - 验证 materialize 时移除 `pseudo_sha_token`（如果存在）
   - 手动注入 `pseudo_sha_token` 到 snapshot，验证 materialize 后已移除

4. **`test_snapshot_yaml_no_sha_token`**
   - 验证生成的 YAML 文件不包含 `pseudo_sha_token`
   - 扫描 YAML 文本，计数 `pseudo_sha_token` 出现次数（必须为 0）

### 测试特性

- ✅ Deterministic（无随机性）
- ✅ 无网络依赖（使用本地测试项目）
- ✅ 无 skip（所有测试必须运行）

---

## 任务 E：测试结果

### pytest 结果

```bash
$ python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v
```

**结果**: ✅ **4 passed in 13.62s**

```
tests/unit/test_demo_snapshot_pseudo_family.py::TestDemoSnapshotPseudoFamily::test_export_project2_bands_has_sha_family PASSED
tests/unit/test_demo_snapshot_pseudo_family.py::TestDemoSnapshotPseudoFamily::test_export_project1_has_sha_family PASSED
tests/unit/test_demo_snapshot_pseudo_family.py::TestDemoSnapshotPseudoFamily::test_materialize_removes_sha_token PASSED
tests/unit/test_demo_snapshot_pseudo_family.py::TestDemoSnapshotPseudoFamily::test_snapshot_yaml_no_sha_token PASSED
```

### 生成的 Demo 文件验证

运行 `python tools/generate_demo_snapshots.py` 后：

```bash
$ grep -r "pseudo_sha_token" resources/demo_projects/
# 无结果（0 occurrences）✅

$ grep "pseudo_sha_family" resources/demo_projects/si_bands_demo.yml
      pseudo_sha_family: 9d5fdea5cc45742d1254e8023b481a202b0022642b381478e6195db3d81e2723

$ grep "pseudo_sha_family" resources/demo_projects/si_dos_demo.yml
      pseudo_sha_family: 9d5fdea5cc45742d1254e8023b481a202b0022642b381478e6195db3d81e2723
```

**确认**: ✅ 所有 demo 文件包含 `pseudo_sha_family`，且没有 `pseudo_sha_token`

---

## 修改摘要

### 修改的文件

1. **`src/quantumvitas/project/snapshot.py`**
   - **行 393-428**: 在 `export_project_to_snapshot()` 中添加增强逻辑，计算并填充 `pseudo_sha256` 和 `pseudo_sha_family`
   - **行 682-693**: 在 `materialize_project_from_snapshot()` 中添加清理逻辑，移除遗留的 `pseudo_sha_token` 字段

2. **`tests/unit/test_demo_snapshot_pseudo_family.py`** (新增)
   - 4 个测试用例，验证 demo 生成脚本的正确性

### 新增测试

- **文件**: `tests/unit/test_demo_snapshot_pseudo_family.py`
- **测试类**: `TestDemoSnapshotPseudoFamily`
- **测试数量**: 4
- **断言点**:
  - `pseudo_sha_family` 存在性规则（如果有 `pseudo_sha256` 或 `pseudo_basename`，必须同时有 `pseudo_sha_family`）
  - `pseudo_sha_token` 必须为 0 occurrences
  - Materialize 时移除 `pseudo_sha_token`

---

## 执行提示

### 如何运行 demo 生成脚本

```bash
# 生成所有 demo snapshots
python tools/generate_demo_snapshots.py

# 仅重新生成 si_bands_demo.yml
python tools/regenerate_si_bands_demo.py
```

### 如何运行回归测试

```bash
# 运行所有相关测试
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py -v

# 运行特定测试
python -m pytest tests/unit/test_demo_snapshot_pseudo_family.py::TestDemoSnapshotPseudoFamily::test_export_project2_bands_has_sha_family -v
```

### 验证生成的 Demo 文件

```bash
# 检查是否有 pseudo_sha_token（应该为 0）
grep -r "pseudo_sha_token" resources/demo_projects/

# 检查是否有 pseudo_sha_family（应该有）
grep -r "pseudo_sha_family" resources/demo_projects/
```

---

## 总结

✅ **任务完成**: 所有 demo 生成脚本现在写入 `pseudo_sha_family`（使用 whitespace-strip 算法），且不再出现 `pseudo_sha_token`

✅ **测试通过**: 4 个回归测试全部通过，确保未来不会回归

✅ **语义不变**: 只修改字段名和 hash 计算，不改变 selection/Step0/UI 的语义

✅ **向后兼容**: Materialize 时会自动清理遗留的 `pseudo_sha_token` 字段

