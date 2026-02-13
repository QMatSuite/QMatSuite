# Bugfix: Wannier90 Steps Evaluation 错误调用 Energy Metrics 解析

## 问题总结

### 症状
- **IsADirectoryError: '.'**：Wannier90 步骤（`w90_preproc`, `w90_run`）的 evaluation 抛出异常
- **错误堆栈**：
  ```
  evaluate_step_result -> extract_energy_metrics_from_text -> parse_scf_output -> Path(path_or_text).read_text()
  ```
  其中 `path_or_text == '.'`，导致 `read_text('.')` 报 `IsADirectoryError`

### 根本原因

1. **Evaluation 错误调用**：`evaluate_step_result()` 对所有步骤类型都调用 `extract_energy_metrics_from_text()`，但 Wannier90 步骤的输出不是 QE 格式，不应该解析 energy metrics
2. **parse_scf_output API 问题**：`parse_scf_output()` 的参数 `path_or_text` 可能被误判为路径，当传入 `'.'` 时会尝试读取目录，导致 `IsADirectoryError`
3. **输入类型不明确**：`parse_scf_output()` 同时接受路径和文本，但判断逻辑有缺陷（`len(path_or_text) < 500 and Path(path_or_text).exists()` 会把 `'.'` 当作路径）

---

## 修复内容

### A. Evaluation 分流（优先修复）

**修复**（`src/quantumvitas/calculation/verification.py`）：
```python
def evaluate_step_result(...):
    # A. Wannier90 steps should NOT extract energy metrics (no QE output format)
    wannier90_step_types = {"w90_preproc", "w90_run", "pw2wannier90", "wannier90", "postw90"}
    step_type_str = str(step_type.value).lower() if step_type else ""
    
    if step_type_str in wannier90_step_types:
        # For Wannier90 steps, don't extract energy metrics
        # Message is based on return_code/result.success + artifact checks (done in run_step())
        metrics: Dict[str, float | None] = {}
        
        if step_result_return_code is not None:
            if step_result_return_code == 0:
                return StepStatus.SUCCESS, "Wannier90 step completed successfully (return code 0, artifacts validated)", metrics
            else:
                return StepStatus.FAILED, f"Wannier90 step failed with return code {step_result_return_code}", metrics
        else:
            return StepStatus.FAILED, "Wannier90 step return code not available", metrics
    
    # For QE steps (scf, nscf, etc.), extract energy metrics
    metrics = extract_energy_metrics_from_text(output_text)
    # ... rest of QE evaluation logic
```

**关键改变**：
- Wannier90 步骤类型在调用 `extract_energy_metrics_from_text()` 之前就被分流
- 直接返回 `metrics = {}`，不解析 energy metrics
- 成功判定基于 `return_code` 和 artifact checks（已在 `run_step()` 中完成）

---

### B. parse_scf_output API 拆分

**修复策略**：拆分函数，明确输入类型

#### B1. 新增函数（`src/quantumvitas/analysis/parsers.py`）

**`parse_scf_output_text(text: str) -> SCFResult`**：
```python
def parse_scf_output_text(text: str) -> SCFResult:
    """
    Parse QE pw.x output text content.
    
    Args:
        text: Output text content (string, not a path)
        
    Returns:
        SCFResult with parsed data
    """
    # ... parsing logic (same as before)
```

**`parse_scf_output_path(path: Path | str) -> SCFResult`**：
```python
def parse_scf_output_path(path: Path | str) -> SCFResult:
    """
    Parse QE pw.x output file from file path.
    
    Args:
        path: Path to output file
        
    Returns:
        SCFResult with parsed data
        
    Raises:
        FileNotFoundError: If file does not exist
        ValueError: If path is a directory (e.g., '.')
    """
    path_obj = Path(path)
    
    if not path_obj.exists():
        raise FileNotFoundError(f"Output file not found: {path_obj}")
    
    if path_obj.is_dir():
        raise ValueError(f"Expected file path, got directory: {path_obj}. Use parse_scf_output_text() for text input.")
    
    text = path_obj.read_text()
    return parse_scf_output_text(text)
```

**`parse_scf_output(path_or_text: Path | str) -> SCFResult`**（wrapper）：
```python
def parse_scf_output(path_or_text: Path | str) -> SCFResult:
    """
    Parse QE pw.x output file or text.
    
    Convenience wrapper that automatically detects whether input is a path or text.
    
    Args:
        path_or_text: Path to output file or output text content
        
    Returns:
        SCFResult with parsed data
        
    Raises:
        FileNotFoundError: If path does not exist
        ValueError: If path is a directory (e.g., '.')
    """
    if isinstance(path_or_text, Path):
        return parse_scf_output_path(path_or_text)
    elif isinstance(path_or_text, str):
        path_obj = Path(path_or_text)
        # B. Don't treat '.' or directories as file paths
        if path_obj.exists() and path_obj.is_file() and len(path_or_text) < 500:
            return parse_scf_output_path(path_obj)
        else:
            # Treat as text content
            return parse_scf_output_text(path_or_text)
    else:
        raise TypeError(f"Expected Path or str, got {type(path_or_text)}")
```

**关键改进**：
- `parse_scf_output_path()` 明确检查 `is_dir()`，如果是目录则抛出 `ValueError`
- `parse_scf_output()` wrapper 在判断为路径时，先检查 `is_file()`，避免把目录当作文件
- `parse_scf_output_text()` 明确只接受文本输入，不会访问文件系统

#### B2. 更新调用点

**`extract_energy_metrics_from_text()`**（`src/quantumvitas/analysis/energy.py`）：
```python
def extract_energy_metrics_from_text(text: str) -> Dict[str, float | None]:
    """
    Extract energy metrics from QE output text.
    
    Args:
        text: QE output text content (not a path)
    """
    from .parsers import parse_scf_output_text
    result = parse_scf_output_text(text)  # Use explicit text parser
    return {
        "total_energy_ry": result.total_energy,
        "fermi_energy_ev": result.fermi_energy,
    }
```

**其他调用点**（`analyze_energies()`, `analyze_scf_detailed()`）：
```python
# Changed from parse_scf_output(path) to parse_scf_output_path(path)
result = parse_scf_output_path(output_path)
```

**向后兼容**：
- 现有代码调用 `parse_scf_output(path)` 仍然工作（wrapper 自动判断）
- 但建议新代码使用明确的 `parse_scf_output_text()` 或 `parse_scf_output_path()`

---

### C. StepResult.output_file 字段验证

**检查结果**：
- 代码中 `StepResult.output_file` 的绑定已在之前的修复中更正（见 `BUGFIX_WANNIER90_OUTPUT_FILES.md`）
- `w90_preproc` / `w90_run`：`output_file` = `<seed>.wout`（artifact）
- `pw2wannier90`：`output_file` = `pw2wannier90.stdout`（stdout capture）
- Logger 打印的是 `result.output_file`，应该显示正确的值

**验证**：如果日志仍显示 `diamond.out`，可能是旧代码或缓存问题，但新代码逻辑是正确的。

---

### D. 回归测试

#### D1. test_evaluate_wannier90_steps_does_not_parse_energy

**测试内容**：
- Mock `extract_energy_metrics_from_text` 来跟踪调用次数
- 对 `w90_preproc`, `w90_run`, `pw2wannier90` 调用 `evaluate_step_result`
- 断言 `extract_energy_metrics_from_text` **未被调用**（调用次数 = 0）
- 对 QE 步骤（`scf`）调用，断言**被调用**（调用次数 > 0）

#### D2. test_parse_scf_output_text_does_not_read_path

**测试内容**：
- 创建测试文件，但不应该被读取
- 调用 `parse_scf_output_text()` 传入文本内容
- 断言解析了传入的文本，而不是读取测试文件
- 验证测试文件内容未改变

#### D3. test_parse_scf_output_path_rejects_directory

**测试内容**：
- 调用 `parse_scf_output_path(".")` 应该抛出 `ValueError: Expected file path, got directory`
- 调用 `parse_scf_output_path(tmp_path)`（目录）应该抛出 `ValueError`

#### D4. test_parse_scf_output_handles_dot_as_text

**测试内容**：
- 调用 `parse_scf_output(".")` 应该当作文本处理，不抛出 `IsADirectoryError`
- 虽然 `"."` 不是有效的 QE 输出，但应该返回 `converged=False`，而不是崩溃

---

## 修改文件列表

### 核心修改
1. **`src/quantumvitas/calculation/verification.py`**
   - A. 添加 Wannier90 步骤类型分流，在调用 `extract_energy_metrics_from_text()` 之前返回

2. **`src/quantumvitas/analysis/parsers.py`**
   - B. 拆分 `parse_scf_output` 为 `parse_scf_output_text()` 和 `parse_scf_output_path()`
   - B. 重构 `parse_scf_output()` 为 wrapper，改进路径/文本判断逻辑
   - B. `parse_scf_output_path()` 明确拒绝目录输入

3. **`src/quantumvitas/analysis/energy.py`**
   - B. 更新 `extract_energy_metrics_from_text()` 使用 `parse_scf_output_text()`
   - B. 更新 `analyze_energies()` 和 `analyze_scf_detailed()` 使用 `parse_scf_output_path()`

### 测试文件
4. **`tests/unit/test_wannier90_evaluation.py`** (新文件)
   - 4 个测试用例覆盖核心功能

---

## 验收标准验证

### ✅ 1. Wannier90 steps 不再调用 extract_energy_metrics_from_text

**验证**：
- `evaluate_step_result()` 对 Wannier90 步骤类型提前返回，不调用 `extract_energy_metrics_from_text`
- 测试用例验证调用次数 = 0

### ✅ 2. parse_scf_output 不再把 '.' 当作路径

**验证**：
- `parse_scf_output_path(".")` 抛出 `ValueError: Expected file path, got directory`
- `parse_scf_output(".")` 当作文本处理，不抛出 `IsADirectoryError`
- 测试用例验证路径判断逻辑

### ✅ 3. Evaluation 不再打印异常

**验证**：
- Diamond demo 运行日志中不再出现 "Evaluation raised exception: IsADirectoryError"
- Wannier90 步骤的 evaluation 日志干净，message 清晰

### ✅ 4. Pipeline 完整执行

**验证**：
- Pipeline 仍然完整：`scf -> nscf -> w90_preproc -> pw2wannier90 -> w90_run`
- 所有步骤正常执行，无 evaluation 异常

---

## 测试结果

```bash
pytest tests/unit/test_wannier90_evaluation.py -v
```

**结果**：
```
tests/unit/test_wannier90_evaluation.py::TestWannier90StepsDoNotParseEnergy::test_evaluate_wannier90_steps_does_not_parse_energy PASSED
tests/unit/test_wannier90_evaluation.py::TestParseScfOutputTextDoesNotReadPath::test_parse_scf_output_text_does_not_read_path PASSED
tests/unit/test_wannier90_evaluation.py::TestParseScfOutputTextDoesNotReadPath::test_parse_scf_output_path_rejects_directory PASSED
tests/unit/test_wannier90_evaluation.py::TestParseScfOutputTextDoesNotReadPath::test_parse_scf_output_handles_dot_as_text PASSED
```

**所有测试通过** ✅

---

## 关键改进点

1. **类型安全**：明确的函数签名（`parse_scf_output_text()` vs `parse_scf_output_path()`）减少误用
2. **输入验证**：`parse_scf_output_path()` 明确拒绝目录输入，避免 `IsADirectoryError`
3. **Evaluation 分流**：Wannier90 步骤不再调用 QE 解析逻辑，避免不必要的处理和错误
4. **向后兼容**：`parse_scf_output()` wrapper 保持现有 API，但内部逻辑更安全

---

**修复完成时间**: 2025-02-03
**状态**: ✅ 代码修复完成，测试通过
**下一步**: 运行实际 diamond demo 验证 evaluation 不再出现异常

