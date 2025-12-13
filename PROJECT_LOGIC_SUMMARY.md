# 项目逻辑总结

## ✅ 已实现的逻辑

### 1. step1 然后 test step1 + step2 然后 test step2...
**实现方式**:
- `test_si_dos_calculation.py`: 使用 `run_and_verify_step_with_assert`，每个步骤立即验证 ✅
- `test_si_bands_calculation.py`: 使用 `run_and_verify_step_with_assert`，每个步骤立即验证 ✅
- `test_ph_quick_tests.py`: 使用 `run_test_category`，每个步骤立即验证（已修复：失败时停止）✅

### 2. 所有 pseudo 指向一个文件夹，先检查有没有，没有再下载
**实现位置**:
- `tests/core/qe_step_runner.py::set_pseudo_dir_to_temp`: 设置为 `project_root/pseudo` ✅
- `src/quantumvitas/core/engines/qe_pseudopotentials.py::ensure_pseudopotentials`: 
  - 先检查 `pseudo_dir` (project_root/pseudo)
  - 再检查 test_suite_dir (fallback)
  - 最后下载 ✅
- `extended-tests/utils/qe_module_base.py`: 也使用统一的 `pseudo_dir` ✅

### 3. 所有 step 逻辑在 src 里面
**实现位置**:
- `src/quantumvitas/core/engines/qe_calculation.py`: 
  - `QECalculationRunner.run_step()`: 执行单个步骤 ✅
  - `QECalculationRunner.run_calculation()`: 执行计算 ✅
- `src/quantumvitas/core/engines/qe.py`: 
  - `detect_step_type()`: 检测步骤类型 ✅
  - `run_step()`: 执行步骤（调用 calculation_runner）✅

### 4. test 逻辑中心化在 tests/core 里面
**实现位置**:
- `tests/core/qe_step_runner.py`: 
  - `run_and_verify_step()`: 运行并验证步骤 ✅
  - `run_and_verify_step_with_assert()`: 运行并验证步骤（带断言）✅
  - `set_outdir_to_temp()`: 设置 outdir ✅
  - `set_pseudo_dir_to_temp()`: 设置 pseudo_dir ✅
- `tests/core/qe_step_verification.py`: 
  - `verify_step_result()`: 验证步骤结果 ✅
- `tests/core/qe_test_utils.py`: 
  - `parse_jobconfig()`: 解析 jobconfig ✅
  - 其他工具函数 ✅

### 5. outdir 始终在 temp/outdir
**实现位置**:
- `tests/core/qe_step_runner.py::set_outdir_to_temp`: 设置为 `temp/outdir` ✅
- `extended-tests/utils/qe_module_base.py::run_module_test`: 也使用 `set_outdir_to_temp` ✅
- `src/quantumvitas/core/engines/qe_calculation.py::run_step`: 使用统一的 outdir ✅

### 6. 顺序看 jobconfig
**实现位置**:
- `tests/core/qe_test_utils.py::parse_jobconfig`: 解析 jobconfig 文件 ✅
- `test_si_dos_calculation.py`: 从 jobconfig 读取 `4_Si_DOS` 顺序 ✅
- `test_si_bands_calculation.py`: 从 jobconfig 读取 `7_Si_bandStructure` 顺序 ✅
- `test_ph_quick_tests.py`: 从 jobconfig 读取 `ph_1d`, `ph_2d` 顺序 ✅

## 📋 文件组织

### src/ (Step 逻辑)
- `src/quantumvitas/core/engines/qe_calculation.py`: Step 执行逻辑
- `src/quantumvitas/core/engines/qe.py`: QE 引擎，调用 calculation runner
- `src/quantumvitas/core/engines/qe_pseudopotentials.py`: 伪势管理

### tests/core/ (Test 逻辑)
- `tests/core/qe_step_runner.py`: 统一的步骤运行和验证接口
- `tests/core/qe_step_verification.py`: 步骤结果验证逻辑
- `tests/core/qe_test_utils.py`: 测试工具函数（jobconfig 解析等）

### tests/integration/ (测试用例)
- 使用 `run_and_verify_step_with_assert` 从 `tests.core`
- 从 `jobconfig` 读取工作流顺序
- 每个步骤立即验证

## 🔄 工作流执行模式

```
for each step in jobconfig:
    1. run step (src/quantumvitas/core/engines/qe_calculation.py)
    2. verify step (tests/core/qe_step_verification.py)
    3. if failed: stop calculation
    4. continue to next step
```

## 📁 统一路径

- **outdir**: `temp/outdir` (所有步骤共享)
- **pseudo_dir**: `project_root/pseudo` (统一伪势目录)
- **工作流顺序**: 从 `jobconfig` 读取
