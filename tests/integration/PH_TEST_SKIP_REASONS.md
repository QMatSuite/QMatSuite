# PH 测试跳过原因列表

本文档列出了 `test_ph_quick_tests.py` 中所有可能导致测试跳过的原因，以及相应的解决方案。

## 跳过原因列表

### 1. QE 安装未找到

**位置**: `qe_engine` fixture

**条件**: `QE_BIN_DIR` 环境变量未设置且默认位置不存在

**原因**: 
```
QE installation not found. QE_BIN_DIR environment variable not set and default location does not exist. 
Please set QE_BIN_DIR or install QE at the default location.
```

**解决方案**: 
- 设置 `QE_BIN_DIR` 环境变量指向 QE bin 目录
- 或在默认位置安装 QE: `$HOME/src/q-e-qe-7.5/bin`

---

### 2. 必需的 QE 可执行文件未找到

**位置**: `qe_engine` fixture

**条件**: `pw.x` 或 `ph.x` 在 QE bin 目录中不存在

**原因**: 
```
Required QE executables not found. Missing executables: pw.x, ph.x in QE bin directory. 
These are required for PH calculation tests.
```

**解决方案**: 
- 确保 `pw.x` 和 `ph.x` 存在于 QE bin 目录中
- 检查 QE 安装是否完整

---

### 3. 引擎无法定位可执行文件

**位置**: `qe_engine` fixture

**条件**: 引擎无法找到可执行文件，即使文件存在

**原因**: 
```
Cannot find required QE executables. Engine cannot locate pw.x or ph.x even though files exist. 
This may indicate a configuration issue.
```

**解决方案**: 
- 检查 QE 引擎配置
- 验证可执行文件路径
- 检查文件权限

---

### 4. QE test-suite 未找到且本地测试数据不可用

**位置**: `test_suite_dir` fixture

**条件**: QE test-suite 目录不存在且 `ci_test_data/` 中也没有测试数据

**原因**: 
```
QE test-suite not found and local test data not available. 
Test suite directory does not exist and local test data in ci_test_data/ is not available. 
Either install QE with test-suite or ensure ci_test_data/ contains test files.
```

**解决方案**: 
- 安装带有 test-suite 的 QE
- 或确保 `tests/data/` 包含 `ph_1d` 和 `ph_2d` 目录

---

### 5. 测试类别目录未找到

**位置**: `test_ph_quick` 测试方法

**条件**: 测试类别目录在 test-suite 或 ci_test_data 中不存在

**原因**: 
```
Test category directory not found: {category_dir}. 
Reason: Category '{category}' does not exist in test suite.
```

**解决方案**: 
- 确保类别目录存在于 test-suite 或 `ci_test_data/` 中
- 检查类别名称是否正确（ph_1d, ph_2d）

---

### 6. jobconfig 文件未找到

**位置**: `test_ph_quick` 测试方法

**条件**: 无法定位 QE test-suite 的 jobconfig 文件

**原因**: 
```
jobconfig file not found. 
Reason: Cannot locate QE test-suite jobconfig file. 
This file is required to determine test order and files.
```

**解决方案**: 
- 确保 jobconfig 文件存在于 QE test-suite 目录中
- 检查以下位置：
  - `test_suite_dir/jobconfig`
  - `$HOME/src/q-e-qe-7.5/test-suite/jobconfig`

---

### 7. 类别在 jobconfig 中未找到

**位置**: `test_ph_quick` 测试方法

**条件**: 类别名称在 jobconfig 文件中未定义

**原因**: 
```
Category '{category}' not found in jobconfig. 
Reason: The category '{category}' is not defined in the jobconfig file. 
Available categories: {list of categories}
```

**解决方案**: 
- 检查 jobconfig 文件中的可用类别
- 确保类别名称正确（ph_1d, ph_2d）
- 检查 jobconfig 文件格式是否正确

---

### 8. 类别中没有测试文件

**位置**: `test_ph_quick` 测试方法

**条件**: 类别在 jobconfig 中存在，但没有定义测试文件

**原因**: 
```
No test files found for category '{category}'. 
Reason: Category '{category}' exists in jobconfig but has no test files defined.
```

**解决方案**: 
- 检查 jobconfig 文件中该类别的 `inputs_args` 配置
- 确保测试文件在类别目录中存在

---

## 频率比较阈值

### ph_1d
- **阈值**: 0.015 THz
- **原因**: 容忍并行/串行计算差异
- **说明**: 使用 NPROCS=1 运行测试时，与使用 NPROCS=4 生成的基准文件可能存在差异

### ph_2d 和其他类别
- **阈值**: 0.01 THz
- **说明**: 标准阈值，适用于大多数情况

---

## 如何查看跳过原因

运行测试时，pytest 会显示详细的跳过原因：

```bash
pytest tests/integration/test_ph_quick_tests.py -v
```

跳过的测试会显示为 `SKIPPED`，并包含详细的跳过原因。

---

## 常见问题

### Q: 为什么 ph_1d 需要更高的阈值？
A: ph_1d 测试使用 NPROCS=1 运行（CI 环境），而基准文件可能使用 NPROCS=4 生成，导致并行/串行计算差异。0.015 THz 的阈值可以容忍这种差异。

### Q: 如何避免测试被跳过？
A: 
1. 确保 QE 已安装并配置正确
2. 设置 `QE_BIN_DIR` 环境变量
3. 确保 `tests/data/` 包含必要的测试文件
4. 或安装完整的 QE test-suite

### Q: 测试跳过会影响 CI 吗？
A: 不会。跳过的测试不会导致 CI 失败。但如果所有测试都被跳过，可能需要检查环境配置。

