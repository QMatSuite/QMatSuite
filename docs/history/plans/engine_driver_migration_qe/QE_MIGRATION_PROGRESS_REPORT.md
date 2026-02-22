# QE Migration Progress Report

**Date**: 2026-01-21  
**Status**: PR 1-5 Completed, Test Failures Identified  
**Test Suite**: 5 failed, 2 errors, 2357 passed

---

## 1. 已完成的工作总结

### PR 1: QE Driver Bundle Foundation ✅

**状态**: 已完成

**完成的工作**:
- ✅ 创建了 `src/qmatsuite/drivers/qe/` 目录结构
- ✅ 创建了 `src/qmatsuite/drivers/qe/__init__.py` (不注册，仅导出QEDriver)
- ✅ 创建了 `src/qmatsuite/drivers/qe/driver.py` (stub，委托给qe_shim)
- ✅ 创建了 `src/qmatsuite/drivers/qe/step_types.py` (初始为空列表)

**验证结果**:
- ✅ `from qmatsuite.drivers.qe import QEDriver` 导入成功
- ✅ 所有现有测试通过

---

### PR 2: Move Step Type Specifications ✅

**状态**: 已完成

**完成的工作**:
- ✅ 从 `drivers/qe_shim/__init__.py` 复制了20个QE step type specs到 `drivers/qe/step_types.py`
- ✅ 更新了 `QEDriver.get_step_type_specs()` 使用本地 `step_types.py`
- ✅ 更新了 `qe_shim` 委托到新的 `drivers/qe.step_types`

**验证结果**:
- ✅ `len(QE_STEP_TYPE_SPECS) == 20`
- ✅ 所有现有测试通过

---

### PR 3: Move QERecipe ✅

**状态**: 已完成

**完成的工作**:
- ✅ 从 `execution/recipes.py` 复制了 `QERecipe` 类到 `drivers/qe/recipe.py`
- ✅ 更新了 `QEDriver.get_recipe_class()` 使用本地recipe
- ✅ 在 `execution/recipes.py` 中添加了向后兼容的重新导出（通过 `__getattr__`）

**验证结果**:
- ✅ `from qmatsuite.drivers.qe.recipe import QERecipe` 导入成功
- ✅ `from qmatsuite.execution.recipes import QERecipe` 向后兼容导入成功
- ✅ 所有现有测试通过

---

### PR 4: Move QE Handler ✅

**状态**: 已完成

**完成的工作**:
- ✅ 从 `execution/handlers.py` 复制了以下函数到 `drivers/qe/handler.py`:
  - `qe_step_handler()` - 主handler函数
  - `handle_qe_relax_output()` - QE relax输出处理
  - `_get_step_input_from_calculation_yaml()` - 辅助函数
  - `_find_step_by_ulid()` - 辅助函数
- ✅ 更新了 `QEDriver.get_handler()` 使用本地handler
- ✅ 在 `execution/handlers.py` 中添加了向后兼容的deprecation wrapper

**验证结果**:
- ✅ `from qmatsuite.drivers.qe.handler import qe_step_handler` 导入成功
- ✅ 所有现有测试通过

---

### PR 5: Move QE Engine Files ✅

**状态**: 已完成（但存在向后兼容问题）

**完成的工作**:
- ✅ 创建了 `src/qmatsuite/drivers/qe/engine/` 子目录
- ✅ 移动了以下7个文件：
  - `core/engines/qe.py` → `drivers/qe/engine/qe_engine.py`
  - `core/engines/qe_calculation.py` → `drivers/qe/engine/qe_calculation.py`
  - `core/engines/qe_installation.py` → `drivers/qe/engine/qe_installation.py`
  - `core/engines/qe_resolver.py` → `drivers/qe/engine/qe_resolver.py`
  - `core/engines/qe_binary_locator.py` → `drivers/qe/engine/qe_binary_locator.py`
  - `core/engines/qe_diagnostics.py` → `drivers/qe/engine/qe_diagnostics.py`
  - `core/engines/qe_pseudopotentials.py` → `drivers/qe/engine/qe_pseudopotentials.py`
- ✅ 更新了移动文件中的内部导入：
  - `qe_engine.py`: 修复了 `base`, `qe_installation`, `qe_calculation` 的导入
  - `qe_binary_locator.py`: 修复了 `qe_resolver` 的导入
  - `qe_resolver.py`: 修复了 `paths` 的导入
  - `qe_diagnostics.py`: 修复了 `qe_resolver` 的导入
- ✅ 创建了向后兼容的重新导出模块：
  - `core/engines/qe.py` - 重新导出 `QuantumEspressoEngine`
  - `core/engines/qe_calculation.py` - 重新导出 `StepResult`, `CalculationResult`, `QECalculationRunner`
  - `core/engines/qe_installation.py` - 重新导出 `QEInstallation`, `get_qe_home`, `set_qe_home`, `reset_qe_home`
  - `core/engines/qe_resolver.py` - 重新导出 `resolve_qe_bin_dir`, `find_internal_qe_bin_dir`, `validate_qe_bin_dir`
  - `core/engines/qe_pseudopotentials.py` - 重新导出 `download_pseudopotential`, `PseudoManager`, `_find_qmatsuite_root`
- ✅ 更新了 `core/engines/__init__.py` 使用 `__getattr__` 进行延迟导入

**验证结果**:
- ✅ `from qmatsuite.drivers.qe.engine import QuantumEspressoEngine` 导入成功
- ✅ `from qmatsuite.core.engines import QuantumEspressoEngine` 向后兼容导入成功
- ⚠️ 部分测试失败（见下方分析）

---

## 2. 测试失败分析

### 2.1 失败统计

- **总测试数**: 2364
- **通过**: 2357 (99.7%)
- **失败**: 5 (0.2%)
- **错误**: 2 (0.1%)

### 2.2 失败分类

#### Category 1: `home_qe_engines_dir` 属性缺失 (5个失败)

**失败测试**:
- `tests/core/test_qe_resolver.py::test_find_internal_qe_bin_dir_empty`
- `tests/core/test_qe_resolver.py::test_find_internal_qe_bin_dir_selection`
- `tests/core/test_qe_resolver.py::test_find_internal_qe_bin_dir_with_meta_json`
- `tests/core/test_qe_resolver.py::test_resolve_qe_bin_dir_internal`
- `tests/core/test_qe_resolver.py::test_resolve_qe_bin_dir_no_qe`

**错误信息**:
```
AttributeError: module 'qmatsuite.core.engines.qe_resolver' has no attribute 'home_qe_engines_dir'
```

**根本原因分析**:

1. **测试代码的monkey patch模式**:
   测试代码 (`tests/core/test_qe_resolver.py:58-67`) 使用monkey patch来替换 `home_qe_engines_dir` 函数：
   ```python
   from qmatsuite.core.engines import qe_resolver
   from qmatsuite.core.paths import home_qe_engines_dir
   original_func = qe_resolver.home_qe_engines_dir  # ❌ 这里访问模块属性
   qe_resolver.home_qe_engines_dir = lambda: engines_dir  # ❌ 尝试设置模块属性
   ```
   
   测试假设 `qe_resolver` 模块有一个 `home_qe_engines_dir` 属性，但实际上：
   - `home_qe_engines_dir` 定义在 `core.paths` 中
   - `qe_resolver` 模块内部使用它，但不导出它
   - 迁移后，`core/engines/qe_resolver.py` 是一个重新导出模块，只导出3个函数，不包含 `home_qe_engines_dir`

2. **向后兼容模块问题**:
   `core/engines/qe_resolver.py` 是一个重新导出模块，只导出了3个函数：
   ```python
   from qmatsuite.drivers.qe.engine.qe_resolver import (
       resolve_qe_bin_dir,
       find_internal_qe_bin_dir,
       validate_qe_bin_dir,
   )
   ```
   它**没有**导出 `home_qe_engines_dir`，因为这不是 `qe_resolver` 模块的公共API。

3. **原始代码的依赖关系**:
   在迁移前，`core/engines/qe_resolver.py` 直接导入并使用 `home_qe_engines_dir`，但测试代码通过monkey patch `qe_resolver.home_qe_engines_dir` 来替换它。迁移后，这个属性不再存在于模块中。

**证据**:
- `home_qe_engines_dir` 定义在 `src/qmatsuite/core/paths.py:127`
- `drivers/qe/engine/qe_resolver.py:17` 使用 `from qmatsuite.core.paths import home_qe_engines_dir`
- `core/engines/qe_resolver.py` 重新导出模块不包含 `home_qe_engines_dir`
- 测试代码在5个地方尝试访问 `qe_resolver.home_qe_engines_dir` (lines 60, 92, 131, 185, 201)

**建议修复方法**:

**选项A（推荐）**: 修改测试代码，使用 `unittest.mock.patch` 或 `pytest monkeypatch` 来mock `core.paths.home_qe_engines_dir`，而不是尝试monkey patch `qe_resolver` 模块属性：

```python
# 修改前 (错误的方式)
from qmatsuite.core.engines import qe_resolver
original_func = qe_resolver.home_qe_engines_dir  # ❌ 属性不存在
qe_resolver.home_qe_engines_dir = lambda: engines_dir

# 修改后 (正确的方式)
from qmatsuite.core.paths import home_qe_engines_dir
import unittest.mock
with unittest.mock.patch('qmatsuite.core.paths.home_qe_engines_dir', return_value=engines_dir):
    result = find_internal_qe_bin_dir()
```

或者使用 `pytest monkeypatch`:
```python
def test_find_internal_qe_bin_dir_empty(monkeypatch):
    from qmatsuite.core.paths import home_qe_engines_dir
    engines_dir = Path(tmpdir) / ".qmatsuite" / "engines" / "qe"
    monkeypatch.setattr('qmatsuite.core.paths.home_qe_engines_dir', lambda: engines_dir)
    result = find_internal_qe_bin_dir()
```

**选项B**: 在 `core/engines/qe_resolver.py` 中添加 `home_qe_engines_dir` 的重新导出（不推荐，因为这不是模块的职责）：
```python
from qmatsuite.core.paths import home_qe_engines_dir
__all__ = [..., "home_qe_engines_dir"]
```

**推荐**: 选项A，因为：
1. `home_qe_engines_dir` 是路径工具函数，属于 `core.paths` 模块
2. Mock应该作用于函数的定义位置，而不是使用位置
3. 这样更符合Python的mock最佳实践

---

#### Category 2: 导入错误 (2个错误)

##### Error 1: `test_qe_resolution_diagnostics.py`

**错误信息**:
```
ImportError while importing test module 'tests/test_qe_resolution_diagnostics.py'
```

**根本原因分析**:

测试文件 (`tests/test_qe_resolution_diagnostics.py:12-17`) 尝试导入：
```python
from qmatsuite.core.engines.qe_diagnostics import (
    diagnose_qe_resolution,
    check_settings_for_external_engines,
    check_environment_variables,
    check_managed_engines,
)
```

**问题**: `qe_diagnostics.py` 已经移动到 `drivers/qe/engine/qe_diagnostics.py`，但**没有**创建向后兼容的重新导出模块 `core/engines/qe_diagnostics.py`。

**证据**:
- `drivers/qe/engine/qe_diagnostics.py` 存在且包含这些函数
- `core/engines/` 目录中没有 `qe_diagnostics.py` 重新导出文件
- `core/engines/__init__.py` 的 `__getattr__` 中没有包含 `qe_diagnostics` 相关的导出

**建议修复方法**:

创建 `src/qmatsuite/core/engines/qe_diagnostics.py`:
```python
"""Backward-compatibility re-export for qe_diagnostics (moved to drivers/qe/engine/)."""

from qmatsuite.drivers.qe.engine.qe_diagnostics import (
    diagnose_qe_resolution,
    check_settings_for_external_engines,
    check_environment_variables,
    check_managed_engines,
    QEResolutionReport,
)

__all__ = [
    "diagnose_qe_resolution",
    "check_settings_for_external_engines",
    "check_environment_variables",
    "check_managed_engines",
    "QEResolutionReport",
]
```

同时更新 `core/engines/__init__.py` 的 `__getattr__` 添加 `qe_diagnostics` 相关的导出。

---

##### Error 2: `test_pw2wannier90_stderr_output.py`

**错误信息**:
```
ImportError while importing test module 'tests/unit/test_pw2wannier90_stderr_output.py'
```

**根本原因分析**:

测试文件 (`tests/unit/test_pw2wannier90_stderr_output.py:15-16`) 导入：
```python
from qmatsuite.core.engines.qe_calculation import QECalculationRunner
from qmatsuite.core.engines.qe import QuantumEspressoEngine, EngineConfig
```

**问题**: 
1. `EngineConfig` 应该从 `core.engines.base` 导入，不是从 `qe` 模块
2. 向后兼容模块可能没有正确导出所有需要的符号

**证据**:
- `core/engines/qe.py` 只导出了 `QuantumEspressoEngine`，没有 `EngineConfig`
- `EngineConfig` 定义在 `core/engines/base.py` 中
- `core/engines/__init__.py` 应该导出 `EngineConfig`，但可能测试尝试从 `qe` 子模块导入

**建议修复方法**:

**选项A（推荐）**: 修复测试文件的导入：
```python
from qmatsuite.core.engines.qe_calculation import QECalculationRunner
from qmatsuite.core.engines.qe import QuantumEspressoEngine
from qmatsuite.core.engines.base import EngineConfig  # 从正确的位置导入
```

**选项B**: 在 `core/engines/qe.py` 中也重新导出 `EngineConfig`（不推荐，因为 `EngineConfig` 不是QE特定的）：
```python
from qmatsuite.core.engines.base import EngineConfig
__all__ = ["QuantumEspressoEngine", "EngineConfig"]
```

**推荐**: 选项A，因为 `EngineConfig` 是基础类，不应该从QE特定模块导入。

---

## 3. 代码审查发现的问题

### 3.1 向后兼容性不完整

**问题**: PR 5 移动了7个引擎文件，但只创建了5个向后兼容重新导出模块，缺少：
- `core/engines/qe_diagnostics.py` - 导致 `test_qe_resolution_diagnostics.py` 导入失败
- `core/engines/qe_binary_locator.py` - 可能被某些代码使用（需要检查）
- `core/engines/qe_registry.py` - 可能被某些代码使用（需要检查）
- `core/engines/qe_seed.py` - 可能被某些代码使用（需要检查）

**建议**: 
1. 检查哪些文件被外部代码导入（使用grep搜索）
2. 为所有被导入的文件创建向后兼容重新导出模块

### 3.2 模块属性访问错误

**问题**: 测试代码可能错误地尝试从 `qe_resolver` 模块访问 `home_qe_engines_dir` 作为属性，但这是一个函数，应该从 `core.paths` 导入。

**建议**: 
1. 检查 `tests/core/test_qe_resolver.py` 中所有对 `home_qe_engines_dir` 的使用
2. 确保所有引用都使用从 `core.paths` 导入的版本

### 3.3 导入路径不一致

**问题**: 某些测试文件可能混合使用了不同的导入路径（从 `core.engines` 子模块导入 vs 从 `core.engines` 根模块导入）。

**建议**: 
1. 统一导入路径：优先使用 `from qmatsuite.core.engines import X`（通过 `__getattr__`）
2. 如果必须从子模块导入，确保子模块存在向后兼容重新导出

---

## 4. 建议的修复优先级

### Priority 1: 修复导入错误（必须立即修复）

1. **创建 `core/engines/qe_diagnostics.py` 重新导出模块**
   - 影响: 修复 `test_qe_resolution_diagnostics.py` 导入错误
   - 风险: 低
   - 工作量: 5分钟

2. **修复 `test_pw2wannier90_stderr_output.py` 的导入**
   - 将 `EngineConfig` 的导入改为从 `core.engines.base` 导入
   - 影响: 修复导入错误
   - 风险: 低
   - 工作量: 2分钟

### Priority 2: 修复 `home_qe_engines_dir` 问题（高优先级）

3. **检查并修复 `tests/core/test_qe_resolver.py`**
   - 查找所有对 `qe_resolver.home_qe_engines_dir` 的引用
   - 改为使用从 `core.paths` 导入的 `home_qe_engines_dir`
   - 影响: 修复5个测试失败
   - 风险: 低
   - 工作量: 10分钟

### Priority 3: 完善向后兼容性（中等优先级）

4. **检查其他可能缺失的重新导出模块**
   - 使用grep搜索 `from qmatsuite.core.engines.qe_` 的所有导入
   - 为所有被导入的模块创建重新导出
   - 影响: 防止未来导入错误
   - 风险: 低
   - 工作量: 15分钟

---

## 5. 下一步工作

### 待完成的PR（按顺序）

- **PR 6**: Move I/O Layer - 尚未开始
- **PR 7**: Move IR Backend - 尚未开始
- **PR 8**: Move Parsers and Data - 尚未开始
- **PR 9**: Register QE Driver (Replace Shim) - 尚未开始
- **PR 10**: Kernel Cleanup - Remove QE Defaults - 尚未开始
- **PR 11**: Final Cleanup - 尚未开始

### 当前状态

- ✅ PR 1-5 已完成
- ⚠️ PR 5 存在向后兼容性问题，需要修复
- 🔄 等待修复当前测试失败后再继续PR 6

---

## 6. 总结

### 已完成的工作
- 成功创建了QE driver bundle基础结构
- 移动了step types, recipe, handler到driver bundle
- 移动了所有7个引擎文件到 `drivers/qe/engine/`
- 创建了向后兼容重新导出（部分）

### 发现的问题
- 5个测试失败：`home_qe_engines_dir` 属性访问错误
- 2个导入错误：缺少 `qe_diagnostics` 重新导出，测试导入路径错误

### 修复建议
- 所有问题都有明确的修复方法
- 修复工作量小（总计约30分钟）
- 风险低，主要是添加缺失的重新导出和修复测试代码

### 建议行动
1. **立即修复** Priority 1 和 Priority 2 的问题
2. **验证修复** 运行完整测试套件确认所有测试通过
3. **继续迁移** 修复后继续PR 6（Move I/O Layer）

