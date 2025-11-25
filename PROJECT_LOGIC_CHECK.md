# 项目逻辑检查报告

## 检查项

### 1. ✅ step1 然后 test step1 + step2 然后 test step2...
**状态**: 部分符合

**符合的地方**:
- `test_si_dos_workflow.py`: ✅ step1 -> test step1 -> step2 -> test step2
- `test_si_bands_workflow.py`: ✅ step1 -> test step1 -> step2 -> test step2

**需要修复的地方**:
- `test_ph_quick_tests.py` 使用 `run_test_category`，它在循环中运行所有步骤，但每个步骤都会立即验证（通过 `run_module_test` 返回结果）
- `extended-tests/utils/qe_module_base.py` 中的 `run_test_category` 在循环中运行步骤，每个步骤都会立即验证

### 2. ✅ 所有 pseudo 指向一个文件夹，先检查有没有，没有再下载
**状态**: 符合

**实现**:
- `set_pseudo_dir_to_temp`: 设置为 `project_root/pseudo` ✅
- `ensure_pseudopotentials`: 先检查 `pseudo_dir`，没有再下载 ✅
- `extended-tests/utils/qe_module_base.py`: 也使用统一的 `pseudo_dir` ✅

### 3. ✅ 所有 step 逻辑在 src 里面
**状态**: 符合

**实现**:
- `src/quantumvitas/core/engines/qe_workflow.py`: `run_step`, `run_workflow` ✅
- `src/quantumvitas/core/engines/qe.py`: `detect_step_type`, `run_step` ✅

### 4. ✅ test 逻辑中心化在 tests/core 里面
**状态**: 符合

**实现**:
- `tests/core/qe_step_runner.py`: `run_and_verify_step`, `run_and_verify_step_with_assert` ✅
- `tests/core/qe_step_verification.py`: 验证逻辑 ✅
- `tests/core/qe_test_utils.py`: 工具函数 ✅

### 5. ✅ outdir 始终在 temp/outdir
**状态**: 符合

**实现**:
- `set_outdir_to_temp`: 设置为 `temp/outdir` ✅
- `extended-tests/utils/qe_module_base.py`: 也使用 `set_outdir_to_temp` ✅

### 6. ✅ 顺序看 jobconfig
**状态**: 符合

**实现**:
- `test_si_dos_workflow.py`: 从 jobconfig 读取顺序 ✅
- `test_si_bands_workflow.py`: 从 jobconfig 读取顺序 ✅
- `test_ph_quick_tests.py`: 从 jobconfig 读取顺序 ✅
