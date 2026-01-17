# 诊断报告：被 Skip 的测试分析

## 问题概述

全量测试中有 2 个测试被 skip：
1. `tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_get_band_structure_data`
2. `tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_analyze_bands_and_generate_plot`

**Skip 原因：** `Band structure data not found - calculation may have failed`

## 根本原因分析

### 1. 测试依赖关系

这两个测试都依赖于 `test_run_calculation_via_job_manager` 成功完成，因为：
- 它们需要 `si.bands.dat.gnu` 文件存在（由 `bands.x` 后处理步骤生成）
- 该文件应该在 `calculation_dir / "raw" / "si.bands.dat.gnu"`

### 2. 测试执行顺序

从测试输出看：
```
test_list_calculations PASSED
test_run_calculation_via_job_manager PASSED  ← 计算运行了
test_job_list PASSED
test_get_band_structure_data SKIPPED         ← 找不到文件
test_analyze_bands_and_generate_plot SKIPPED ← 找不到文件
```

**关键发现：** `test_run_calculation_via_job_manager` 虽然 PASSED，但这**不意味着所有步骤都成功完成**。

### 3. 代码审查发现的问题

#### 问题 1: `test_run_calculation_via_job_manager` 的断言不够严格

**位置：** `tests/daemon/test_si_bands_calculation_daemon.py:362-384`

```python
def test_run_calculation_via_job_manager(self, ...):
    # ...
    final_status = wait_for_job(daemon, job_id, timeout=300.0)
    
    # Check job completed successfully
    assert final_status["status"] in ("completed", "failed"), \
        f"Job ended with unexpected status: {final_status['status']}"
    
    if final_status["status"] == "failed":
        pytest.skip(f"Calculation failed: {final_status.get('error', 'Unknown error')}")
```

**问题：**
- 测试只检查 job status 是否为 "completed" 或 "failed"
- **即使 job status 是 "completed"，也不意味着所有步骤都成功**
- QE 计算可能部分失败（例如：scf 成功，但 bands_pw 或 bands.x 失败）
- 测试没有验证每个步骤的状态

#### 问题 2: 缺少步骤级别的验证

**位置：** `tests/daemon/test_si_bands_calculation_daemon.py:394-404`

```python
def test_get_band_structure_data(self, ...):
    # Check if bands data exists
    raw_dir = calculation_dir / "raw"
    bands_gnu = raw_dir / "si.bands.dat.gnu"
    
    if not bands_gnu.exists():
        pytest.skip("Band structure data not found - calculation may have failed")
```

**问题：**
- 测试直接检查文件是否存在，如果不存在就 skip
- **没有诊断为什么文件不存在**（是计算失败？还是路径不对？）
- 没有检查 `bands.x` 步骤的执行状态

#### 问题 3: 测试配置可能有问题

**位置：** `tests/daemon/test_si_bands_calculation_daemon.py:327-347`

测试创建了 4 个步骤：
1. `scf` (step_type="scf")
2. `nscf` (step_type="nscf")
3. `bands` (step_type="bands_pw", name="bands")
4. `bandspp` (step_type="bands", name="bandspp")

**潜在问题：**
- `bands.x` 步骤（bandspp）需要 `bands_pw` 步骤的输出（`si.save` 目录）
- 如果 `bands_pw` 步骤失败，`bands.x` 无法生成 `si.bands.dat.gnu`
- 测试没有验证步骤之间的依赖关系是否满足

### 4. 可能的失败场景

#### 场景 A: `bands_pw` 步骤失败
- `pw.x` 计算可能因为配置错误、收敛问题等原因失败
- 导致没有生成 `si.save` 目录
- `bands.x` 无法运行，无法生成 `si.bands.dat.gnu`

#### 场景 B: `bands.x` 步骤失败
- `bands_pw` 成功，但 `bands.x` 后处理失败
- 可能原因：
  - `filband` 参数配置错误
  - `bands.x` 输入文件格式问题
  - 文件路径问题

#### 场景 C: 文件路径问题
- `bands.x` 成功运行，但输出文件不在预期位置
- `filband` 配置为 `"si.bands.dat"`，但实际可能输出到其他位置
- `raw_dir` 路径可能不正确

## 建议的修复方案

### 方案 1: 增强 `test_run_calculation_via_job_manager` 的验证（推荐）

**修改位置：** `tests/daemon/test_si_bands_calculation_daemon.py:362-384`

**建议：**
1. 检查 job result 中每个步骤的状态
2. 验证关键步骤（特别是 `bands_pw` 和 `bands`）是否成功
3. 如果关键步骤失败，应该 FAIL 而不是让后续测试 skip

```python
def test_run_calculation_via_job_manager(self, ...):
    # ... existing code ...
    
    final_status = wait_for_job(daemon, job_id, timeout=300.0)
    
    assert final_status["status"] in ("completed", "failed"), \
        f"Job ended with unexpected status: {final_status['status']}"
    
    if final_status["status"] == "failed":
        pytest.skip(f"Calculation failed: {final_status.get('error', 'Unknown error')}")
    
    # NEW: Verify all steps completed successfully
    if "result" in final_status and "steps" in final_status["result"]:
        step_results = final_status["result"]["steps"]
        for step in step_results:
            step_status = step.get("status", "unknown")
            step_type = step.get("step_type", "unknown")
            if step_status != "success":
                pytest.fail(
                    f"Step {step_type} failed with status {step_status}. "
                    f"Error: {step.get('error', 'No error message')}"
                )
    
    # NEW: Verify expected output files exist
    raw_dir = calculation_dir / "raw"
    expected_files = [
        raw_dir / "si.bands.dat.gnu",  # From bands.x
    ]
    missing_files = [f for f in expected_files if not f.exists()]
    if missing_files:
        pytest.fail(
            f"Expected output files not found after calculation: {missing_files}. "
            f"Calculation may have partially failed."
        )
```

### 方案 2: 改进 skip 消息，添加诊断信息

**修改位置：** `tests/daemon/test_si_bands_calculation_daemon.py:394-404` 和 `422-436`

**建议：**
- 当文件不存在时，检查相关步骤的状态
- 提供更详细的诊断信息（哪些步骤失败了，文件应该在哪里）

```python
def test_get_band_structure_data(self, ...):
    raw_dir = calculation_dir / "raw"
    bands_gnu = raw_dir / "si.bands.dat.gnu"
    
    if not bands_gnu.exists():
        # Diagnose why file is missing
        diagnosis = []
        
        # Check if bands_pw step output exists
        bands_pw_out = list(raw_dir.glob("*bands*.out"))
        if not bands_pw_out:
            diagnosis.append("No bands_pw output files found")
        
        # Check if bands.x step output exists
        bands_x_out = list(raw_dir.glob("*bandspp*.out")) + list(raw_dir.glob("*bands.x*.out"))
        if not bands_x_out:
            diagnosis.append("No bands.x output files found")
        
        # Check if si.save exists (required for bands.x)
        save_dir = raw_dir / "si.save"
        if not save_dir.exists():
            diagnosis.append(f"si.save directory not found at {save_dir}")
        
        skip_msg = f"Band structure data not found at {bands_gnu}. "
        if diagnosis:
            skip_msg += f"Diagnosis: {'; '.join(diagnosis)}"
        else:
            skip_msg += "Calculation may have failed or file path is incorrect."
        
        pytest.skip(skip_msg)
```

### 方案 3: 使用 pytest 的依赖标记（可选）

**建议：**
- 使用 `pytest.mark.dependency` 标记测试依赖关系
- 确保 `test_get_band_structure_data` 只在 `test_run_calculation_via_job_manager` 成功时运行

```python
@pytest.mark.dependency(depends=["test_run_calculation_via_job_manager"])
def test_get_band_structure_data(self, ...):
    # ...
```

## 立即行动建议

### 优先级 1: 诊断当前失败原因

运行以下命令，查看实际的计算结果：

```bash
# 运行单个测试，查看详细输出
pytest tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_run_calculation_via_job_manager -v -s

# 检查计算目录中的实际文件
# （需要找到测试创建的临时目录）
```

### 优先级 2: 检查 JobManager 返回的步骤状态

**位置：** `src/quantumvitas/daemon/jobs.py` 和 `src/quantumvitas/daemon/server.py`

**需要确认：**
- `run_calculation` RPC 返回的 result 中是否包含每个步骤的状态
- 如果包含，`test_run_calculation_via_job_manager` 应该验证这些状态

### 优先级 3: 验证 bands.x 配置

**需要确认：**
- `filband` 参数是否正确配置为 `"si.bands.dat"`
- `bands.x` 实际输出文件路径是什么
- 是否有其他配置问题导致 `bands.x` 无法生成 `.gnu` 文件

## 结论

**根本问题：** 测试的验证逻辑不够严格，导致：
1. `test_run_calculation_via_job_manager` 通过，但不保证所有步骤成功
2. 后续测试因为找不到文件而 skip，但没有诊断原因
3. 无法区分是"计算失败"还是"测试配置问题"

**建议：** 按照方案 1 增强验证逻辑，确保测试能够：
- 检测部分失败的计算
- 提供清晰的失败原因
- 避免不必要的 skip（应该 FAIL 而不是 SKIP）

