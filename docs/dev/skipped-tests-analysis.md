# 被跳过测试分析

**日期**: 2025-01-XX  
**测试总数**: 1755 passed, 4 skipped

---

## 被跳过的测试列表

### 1. `tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_run_calculation_via_job_manager`

**原因**: 计算失败
```
SKIPPED [1] tests/daemon/test_si_bands_calculation_daemon.py:385: 
Calculation failed: K_POINTS option 'crystal_b' requires 'data' to be provided. 
K-path formats (crystal_b, crystal_c, tpiba_b, tpiba_c) cannot use automatic grid data.
```

**根因**: K_POINTS 配置问题 - `crystal_b` 格式需要显式提供 `data`，不能使用自动网格数据。

**代码位置**: `tests/daemon/test_si_bands_calculation_daemon.py:385`
```python
if final_status["status"] == "failed":
    pytest.skip(f"Calculation failed: {final_status.get('error', 'Unknown error')}")
```

---

### 2. `tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_get_band_structure_data`

**原因**: 依赖测试1的计算结果，因为测试1失败，没有生成band structure数据
```
SKIPPED [1] tests/daemon/test_si_bands_calculation_daemon.py:405: 
Band structure data not found - calculation may have failed
```

**代码位置**: `tests/daemon/test_si_bands_calculation_daemon.py:405`
```python
if not bands_gnu.exists():
    pytest.skip("Band structure data not found - calculation may have failed")
```

---

### 3. `tests/daemon/test_si_bands_calculation_daemon.py::TestDaemonCalculationExecution::test_analyze_bands_and_generate_plot`

**原因**: 依赖测试1的计算结果，因为测试1失败，没有生成band structure数据
```
SKIPPED [1] tests/daemon/test_si_bands_calculation_daemon.py:437: 
Band structure data not found - calculation may have failed
```

**代码位置**: `tests/daemon/test_si_bands_calculation_daemon.py:437`
```python
if not bands_gnu.exists():
    pytest.skip("Band structure data not found - calculation may have failed")
```

---

### 4. `tests/unit/test_pw2wannier90_stderr_output.py::test_pw2wannier90_actual_stderr_output`

**原因**: 故意标记为跳过 - 需要实际的 pw2wannier90 二进制文件
```
SKIPPED [1] tests/unit/test_pw2wannier90_stderr_output.py:82: 
Requires actual pw2wannier90 binary - integration test
```

**代码位置**: `tests/unit/test_pw2wannier90_stderr_output.py:82`
```python
@pytest.mark.skip(reason="Requires actual pw2wannier90 binary - integration test")
def test_pw2wannier90_actual_stderr_output(tmp_path):
```

**这是预期的**: 这是一个集成测试，需要实际的 pw2wannier90 二进制文件，在CI环境中可能不可用。

---

## 总结

- **3个测试被跳过** 因为同一个根因：daemon测试中的计算失败（K_POINTS配置问题）
- **1个测试被跳过** 是预期的（需要实际二进制文件的集成测试）

### 需要修复的问题

**K_POINTS配置问题**: `crystal_b` 格式需要显式提供 `data`，不能使用自动网格数据。这导致daemon测试中的计算失败。

**建议修复方向**:
1. 检查daemon测试中的K_POINTS配置
2. 确保 `crystal_b` 格式正确提供 `data` 字段
3. 或者改用支持自动网格的K_POINTS格式（如 `automatic`）

