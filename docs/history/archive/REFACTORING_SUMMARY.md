# test_qe_roundtrip_execution.py 重构总结

## 已完成的重构

### 1. ✅ 创建 `src/quantumvitas/core/engines/qe_pseudopotentials.py`
- **移动的函数**:
  - `download_pseudopotential()` - 从网络下载赝势文件
  - `ensure_pseudopotentials()` - 确保所有需要的赝势文件可用
- **理由**: 这些是通用的 QE 功能，用户也可能需要，应该作为主程序的一部分
- **状态**: ✅ 已完成并导出到 `__init__.py`

### 2. ✅ 更新 `tests/core/qe_test_utils.py`
- **添加的函数**:
  - `run_command_with_timeout()` - 运行命令并设置超时
  - `TimeoutError` - 超时异常类
- **理由**: 这是测试工具函数，应该放在测试核心模块中
- **状态**: ✅ 已完成并导出到 `tests/core/__init__.py`

### 3. ✅ 已迁移的输入准备功能
- `set_outdir_to_temp()` / `set_pseudo_dir_to_temp()` → `quantumvitas.calculation.input_runner`
- `prepare_input_step()` / `run_prepared_step()` 供 CLI 与测试共享
- `verify_qe_output()` - 已被 `tests/core/qe_step_verification.py::verify_step_result()` 替代

### 4. ✅ Parse 和 Generate 功能
- **位置**: `src/quantumvitas/core/engines/qe_input.py`
- **函数**:
  - `QEInputParser.parse_file()` - 解析 QE 输入文件
  - `QEInputParser.parse_string()` - 从字符串解析
  - `QEInputGenerator.generate()` - 生成输入文件字符串
  - `QEInputGenerator.write_file()` - 写入文件
- **状态**: ✅ 已存在，无需移动

## 新的导入方式

### 从主程序导入（src/）
```python
from quantumvitas.core.engines import (
    ensure_pseudopotentials,
    download_pseudopotential,
    QEInputParser,
    QEInputGenerator,
)
```

### 从测试核心导入（tests/core/）
```python
from tests.core import (
    run_command_with_timeout,
    TimeoutError,
    set_outdir_to_temp,  # 通过 qe_step_runner
    set_pseudo_dir_to_temp,  # 通过 qe_step_runner
    verify_step_result,  # 替代 verify_qe_output
)
```

## 最新整理

### Roundtrip 入口
- ✅ `QEInputParser.roundtrip_file()` 提供解析 + 重写的正式入口
- ✅ 文档 (`README.md`, `tests/core/README_STEP_VERIFICATION.md`) 已更新推荐新入口
- ✅ `extended-tests/utils/test_qe_roundtrip_execution.py` 仅保留向后兼容 re-export

## 文件结构

### 新的文件结构

```
src/quantumvitas/core/engines/
├── qe_input.py              # ✅ 已有：解析和生成
├── qe_pseudopotentials.py   # ✅ 新建：赝势管理
├── qe_calculation.py           # ✅ 已有：calculation 执行
└── qe.py                    # ✅ 已有：QE 引擎

tests/core/
├── qe_test_utils.py        # ✅ 更新：添加 run_command_with_timeout
├── qe_step_runner.py       # ✅ 已有：step 执行和验证
└── qe_step_verification.py # ✅ 已有：验证逻辑

extended-tests/utils/
└── test_qe_roundtrip_execution.py  # ✅ 仅保留向后兼容 re-export
```

## 使用建议

### 对于新代码
- **赝势管理**: 使用 `from quantumvitas.core.engines import ensure_pseudopotentials`
- **测试执行**: 使用 `from tests.core import run_and_verify_step_with_assert`
- **命令执行**: 使用 `from tests.core import run_command_with_timeout`

### 对于旧代码
- 逐步迁移到新的导入方式
- 使用 `run_and_verify_step_with_assert()` 运行 calculation；使用
  `QEInputParser.roundtrip_file()` 进行快速 roundtrip 检查

