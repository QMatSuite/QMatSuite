# 中心化验证系统迁移总结

## 已完成迁移的文件

### 1. `tests/integration/test_si_dos_workflow.py`
- ✅ `test_run_scf_calculation` - 使用 `run_and_verify_step_with_assert()`
- ✅ `test_run_nscf_calculation` - 使用 `run_and_verify_step_with_assert()`
- ✅ `test_run_full_workflow` - SCF 和 NSCF 步骤使用新系统

### 2. `tests/integration/test_si_bands_workflow.py`
- ✅ `test_run_scf_calculation` - 使用 `run_and_verify_step_with_assert()`
- ✅ `test_run_nscf_calculation` - 使用 `run_and_verify_step_with_assert()`
- ✅ `test_run_full_workflow` - SCF、NSCF 和 Bands 步骤使用新系统

### 3. `tests/integration/test_pw_quick_tests_ci.py`
- ✅ `test_pw_quick_execution` - 使用 `run_and_verify_step_with_assert()`

## 迁移效果

### 代码减少
- **之前**: 每个测试方法 ~100-150 行代码（包含手动能量提取、对比、断言）
- **之后**: 每个测试方法 ~10-20 行代码（只需调用一个函数）

### 功能改进
1. **自动 step type 检测**: 无需手动指定
2. **自动验证**: 根据 step type 自动选择验证方式（scf→能量，nscf→费米能，其他→JOB DONE）
3. **统一 outdir/pseudo_dir**: 自动设置为 `temp/outdir` 和 `temp/pseudo`
4. **中心化维护**: 所有验证逻辑在 `tests/core/qe_step_verification.py`

## 核心函数

### `run_and_verify_step_with_assert()`
```python
from tests.core import run_and_verify_step_with_assert

step_result = run_and_verify_step_with_assert(
    input_file=Path("si.1_scf.in"),
    qe_engine=qe_engine,
    working_dir=tmp_path,
    reference_file=Path("reference/si.1_scf.out"),  # 可选
    category="4_Si_DOS",  # 可选，用于阈值选择
    timeout=300,  # 可选
    project_root=project_root  # 可选，自动检测
)
```

### 验证逻辑
- **scf**: 自动对比总能量（tolerance: 3e-6 Ry）
- **nscf**: 自动对比费米能（tolerance: 0.01 Ry）
- **ph**: 自动对比频率（tolerance: 0.015 THz）
- **其他**: 检查 JOB DONE

## 使用建议

1. **新测试**: 直接使用 `run_and_verify_step_with_assert()`
2. **旧测试**: 逐步迁移到新系统
3. **参考**: 查看 `tests/core/README_STEP_VERIFICATION.md` 获取详细文档

## 测试状态

所有迁移的测试都已通过验证：
- ✅ `test_si_dos_workflow.py::test_run_scf_calculation` - PASSED
- ✅ `test_si_dos_workflow.py::test_run_nscf_calculation` - PASSED
- ✅ `test_pw_quick_tests_ci.py::test_pw_quick_execution` - 已更新

