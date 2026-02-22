# test_qe_roundtrip_execution.py 重构计划

## 函数分类分析

### 1. 应该移到 `src/qmatsuite/core/engines/` 的函数

这些是核心功能，应该作为主程序的一部分：

#### `ensure_pseudopotentials()` → `src/qmatsuite/core/engines/qe_pseudopotentials.py`
- **功能**: 确保所有需要的赝势文件可用（下载、查找、复制）
- **理由**: 这是通用的 QE 功能，不仅测试需要，用户也可能需要
- **新位置**: `src/qmatsuite/core/engines/qe_pseudopotentials.py`
- **新名称**: `ensure_pseudopotentials()` (保持不变)

#### `download_pseudopotential()` → `src/qmatsuite/core/engines/qe_pseudopotentials.py`
- **功能**: 从网络下载赝势文件
- **理由**: 赝势管理是核心功能
- **新位置**: `src/qmatsuite/core/engines/qe_pseudopotentials.py`
- **新名称**: `download_pseudopotential()` (保持不变)

### 2. 应该移到 `tests/core/` 的函数

这些是测试特定的功能：

#### `set_outdir_to_temp()` → `tests/core/qe_step_runner.py` ✅ (已存在)
- **功能**: 设置 outdir 到 temp/outdir
- **状态**: 已经在 `tests/core/qe_step_runner.py` 中
- **建议**: 移除 `extended-tests/utils/test_qe_roundtrip_execution.py` 中的重复实现

#### `set_pseudo_dir_to_temp()` → `tests/core/qe_step_runner.py` ✅ (已存在)
- **功能**: 设置 pseudo_dir 到 temp/pseudo
- **状态**: 已经在 `tests/core/qe_step_runner.py` 中
- **建议**: 移除 `extended-tests/utils/test_qe_roundtrip_execution.py` 中的重复实现

#### `run_with_timeout()` → `tests/core/qe_test_utils.py`
- **功能**: 运行命令并设置超时
- **理由**: 主要用于测试执行
- **新位置**: `tests/core/qe_test_utils.py`
- **新名称**: `run_command_with_timeout()`

#### `verify_qe_output()` → `tests/core/qe_step_verification.py` ✅ (已存在更完善的版本)
- **功能**: 验证 QE 输出文件
- **状态**: 已经被 `verify_step_result()` 替代
- **建议**: 移除旧版本，使用新的 `verify_step_result()`

### 3. 应该废弃的函数

#### `run_input_roundtrip_execution()` → 已被替代
- **功能**: 完整的 roundtrip 执行（parse -> generate -> run -> verify）
- **状态**: 已经被 `tests/core/qe_step_runner.py::run_and_verify_step_with_assert()` 替代
- **建议**: 
  - 标记为 deprecated
  - 更新所有调用者使用新函数
  - 最终移除

### 4. 应该移到 `src/qmatsuite/core/engines/` 的新功能

#### Roundtrip 功能 → `qmatsuite.io`
- **功能**: 解析 -> 生成的基本 roundtrip
- **实现**: 
  ```python
  from qmatsuite.io import QEInputParser
  qe_input = QEInputParser.roundtrip_file(input_file, output_file)
  ```
- **理由**: 这是核心功能，用户可能需要

## 重构步骤

### 步骤 1: 创建 `src/qmatsuite/core/engines/qe_pseudopotentials.py`
- 移动 `download_pseudopotential()`
- 移动 `ensure_pseudopotentials()`
- 更新导入

### 步骤 2: 更新 `tests/core/qe_test_utils.py`
- 添加 `run_command_with_timeout()`
- 从 `test_qe_roundtrip_execution.py` 移动代码

### 步骤 3: 更新 `src/qmatsuite/core/engines/qe_input.py`
- 添加 `roundtrip_file()` 方法（如果需要）

### 步骤 4: 更新所有调用者
- 更新 `extended-tests/` 中的脚本
- 更新 `tests/` 中的测试文件
- 移除对 `test_qe_roundtrip_execution.py` 的依赖

### 步骤 5: 清理
- `extended-tests/utils/test_qe_roundtrip_execution.py` 仅做向后兼容 re-export
- 引导所有调用者迁移到 `QEInputParser.roundtrip_file()` 或
  `run_and_verify_step_with_assert()`

## 文件结构

### 新的文件结构

```
src/qmatsuite/core/engines/
├── qe_input.py          # 已有：解析和生成
├── qe_pseudopotentials.py  # 新建：赝势管理
├── qe_calculation.py       # 已有：calculation 执行
└── qe.py                # 已有：QE 引擎

tests/core/
├── qe_test_utils.py     # 已有：测试工具（添加 run_command_with_timeout）
├── qe_step_runner.py    # 已有：step 执行和验证
└── qe_step_verification.py  # 已有：验证逻辑

extended-tests/utils/
└── test_qe_roundtrip_execution.py  # 保留但简化（仅向后兼容）
```

## 迁移优先级

1. **高优先级**: 移动赝势管理功能到 `src/`（用户可能需要）
2. **中优先级**: 移动 `run_with_timeout()` 到 `tests/core/`
3. **低优先级**: 清理重复代码，标记 deprecated 函数

