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

### 3. ✅ 已存在的功能（无需移动）
- `set_outdir_to_temp()` - 已在 `tests/core/qe_step_runner.py`
- `set_pseudo_dir_to_temp()` - 已在 `tests/core/qe_step_runner.py`
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

## 待处理事项

### 1. 更新 `extended-tests/utils/test_qe_roundtrip_execution.py`
- [ ] 更新导入，使用新的位置
- [ ] 移除重复的 `set_outdir_to_temp()` 和 `set_pseudo_dir_to_temp()` 实现
- [ ] 更新 `ensure_pseudopotentials()` 调用，使用 `src/` 中的版本
- [ ] 更新 `run_with_timeout()` 调用，使用 `tests/core/` 中的版本

### 2. 更新所有调用者
- [ ] `extended-tests/utils/qe_module_base.py`
- [ ] `extended-tests/scripts/run_pw_tests_official_style.py`
- [ ] `extended-tests/scripts/run_multiple_pw_tests.py`
- [ ] `generate_si_dos_reference.py` (如果存在)

### 3. 标记废弃的函数
- [ ] `run_input_roundtrip_execution()` - 标记为 deprecated，建议使用 `run_and_verify_step_with_assert()`

## 文件结构

### 新的文件结构

```
src/quantumvitas/core/engines/
├── qe_input.py              # ✅ 已有：解析和生成
├── qe_pseudopotentials.py   # ✅ 新建：赝势管理
├── qe_workflow.py           # ✅ 已有：workflow 执行
└── qe.py                    # ✅ 已有：QE 引擎

tests/core/
├── qe_test_utils.py        # ✅ 更新：添加 run_command_with_timeout
├── qe_step_runner.py        # ✅ 已有：step 执行和验证
└── qe_step_verification.py  # ✅ 已有：验证逻辑

extended-tests/utils/
└── test_qe_roundtrip_execution.py  # ⏳ 待更新：使用新的导入
```

## 使用建议

### 对于新代码
- **赝势管理**: 使用 `from quantumvitas.core.engines import ensure_pseudopotentials`
- **测试执行**: 使用 `from tests.core import run_and_verify_step_with_assert`
- **命令执行**: 使用 `from tests.core import run_command_with_timeout`

### 对于旧代码
- 逐步迁移到新的导入方式
- `run_input_roundtrip_execution()` 仍然可用，但建议迁移到 `run_and_verify_step_with_assert()`

