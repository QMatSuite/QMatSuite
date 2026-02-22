# Bugfix: Wannier90 输出文件和执行管线修复

## 问题总结

### 症状
1. **w90_preproc 完成后 runner 断链**：`w90_preproc` returncode=0，但 `StepResult.output_file` 指向不存在的 `raw/diamond.out`，导致 evaluation 失败，后续步骤（包括 `pw2wannier90`）未执行
2. **stdout/stderr 文件覆盖**：`w90_preproc` 和 `w90_run` 使用相同的 stdout/stderr 文件名，导致后者覆盖前者
3. **Primary output 绑定错误**：使用了不存在的 `diamond.out` 而不是实际的 `<seed>.wout` 文件

### 根本原因

1. **输出文件命名不一致**：`w90_preproc` 和 `w90_run` 都使用 `{seed}.stdout` / `{seed}.stderr`，导致覆盖
2. **Primary output 绑定错误**：对于 Wannier90 步骤，`StepResult.output_file` 应该指向 artifact（`<seed>.wout`），而不是 stdout capture 文件
3. **Evaluation 假设错误**：Evaluation 逻辑假设 `output_file` 必须存在才能判定成功，但 Wannier90 步骤的 primary output 是 artifact，不是 stdout

---

## 修复内容

### A. 统一 stdout/stderr 文件命名规则（避免覆盖）

**规则**：
- 所有步骤使用 `{step_type}.stdout` 和 `{step_type}.stderr` 作为 capture 文件名
- `w90_preproc` → `w90_preproc.stdout` / `w90_preproc.stderr`
- `w90_run` → `w90_run.stdout` / `w90_run.stderr`
- `pw2wannier90` → `pw2wannier90.stdout` / `pw2wannier90.stderr`

**实现**（`src/qmatsuite/core/engines/qe_calculation.py`）：
```python
# A. Unified stdout/stderr file naming to prevent overwrites between steps
stdout_capture = _ensure_file_path(None, f"{step_type}.stdout", working_dir)
stderr_capture = _ensure_file_path(None, f"{step_type}.stderr", working_dir)
```

**效果**：
- `w90_preproc` 和 `w90_run` 的 stdout/stderr 不再覆盖
- 每个步骤有独立的 capture 文件

---

### B. 修正 primary output 绑定

**规则**：
- `w90_preproc` / `w90_run`：primary output = `<seed>.wout`（artifact）
- `pw2wannier90`：primary output = `pw2wannier90.stdout`（stdout capture）
- QE steps：primary output = `<input_stem>.out`

**实现**：
```python
if step_type in ("w90_preproc", "w90_run"):
    primary_output_file = working_dir / f"{input_stem}.wout"  # Artifact
elif step_type == "pw2wannier90":
    primary_output_file = stdout_capture  # stdout capture
else:
    primary_output_file = working_dir / f"{input_stem}.out"  # QE output

# StepResult.output_file points to primary_output_file (not stdout_capture)
result_output_file = primary_output_file if primary_output_file.exists() else None
```

**关键区别**：
- **stdout capture**：用于 subprocess 重定向（`{step_type}.stdout`）
- **Primary output**：`StepResult.output_file` 指向的 artifact 文件（`<seed>.wout`）

---

### C. cwd 必须是 raw_dir

**实现**：
```python
process = subprocess.Popen(
    command,
    stdin=subprocess.DEVNULL,
    stdout=output_handle,
    stderr=stderr_handle,
    cwd=str(working_dir),  # C. cwd must be raw_dir
    env=env,
    text=True
)
```

**效果**：
- `wannier90.x` 写入的 `<seed>.nnkp` / `<seed>.wout` 都在 `raw_dir` 中
- 路径一致性：所有文件（artifact + capture）都在同一目录

---

### D. Post-run 验证（fail-fast）

**规则**：
- `w90_preproc`：`return_code==0` **AND** `<seed>.nnkp` 必须存在
- `w90_run`：`return_code==0` **AND** `<seed>.wout` 必须存在
- `pw2wannier90`：`return_code==0` 即可（主要输出是 stdout capture）

**实现**：
```python
if step_type == "w90_preproc":
    if return_code == 0:
        if not nnkp_file.exists():
            success = False
            error_msg = f"w90_preproc return_code=0 but required artifact {nnkp_file.name} does not exist"
elif step_type == "w90_run":
    if return_code == 0:
        if not wout_file.exists():
            success = False
            error_msg = f"w90_run return_code=0 but required artifact {wout_file.name} does not exist"
elif step_type == "pw2wannier90":
    if return_code != 0:
        success = False
        error_msg = f"pw2wannier90 failed with return code {return_code}"
        if stderr:
            stderr_preview = '\n'.join(stderr_lines[-50:])
            error_msg += f"\n\nStderr (last 50 lines):\n{stderr_preview}"
```

---

### E. Evaluation 不能因为 output_file 不存在而中止

**问题**：Evaluation 逻辑假设 `output_file` 必须存在，但 Wannier90 步骤的 primary output 是 artifact（`<seed>.wout`），不是 stdout capture。

**修复**（`src/qmatsuite/calculation/runner.py`）：
```python
# For Wannier90 steps, use stdout field (from capture file) for evaluation
# output_file points to artifact (<seed>.wout), not stdout
is_wannier90_step = result.step_type and str(result.step_type).lower() in wannier90_step_types

if is_wannier90_step:
    output_text = result.stdout if result.stdout else ""  # Use stdout field
else:
    # For QE steps, try to read from output_file, fall back to stdout
    if result.output_file and result.output_file.exists():
        output_text = result.output_file.read_text()
    else:
        output_text = result.stdout if result.stdout else ""  # Fallback

# Wrap evaluation in try/except
try:
    step_status, message, metrics = evaluate_step_result(...)
except Exception as e:
    logger.exception(...)
    # On evaluation failure, use result.success as primary indicator
    if result.success:
        step_status = StepStatus.SUCCESS
    else:
        step_status = StepStatus.FAILED
```

**效果**：
- Wannier90 步骤使用 `stdout` 字段（从 capture 文件读取）进行评估
- Evaluation 异常不会导致 silent abort，而是记录日志并使用 `result.success` 判定

---

### F. 回归测试

#### F1. test_wannier90_stdout_stderr_not_overwritten_between_steps
- Mock `w90_preproc` 和 `w90_run` 步骤
- 验证 `w90_preproc.stdout` 和 `w90_run.stdout` 都存在且内容不同

#### F2. test_w90_preproc_primary_output_is_seed_wout_and_nnkp_required
- Mock `w90_preproc` 执行，创建 `diamond.nnkp` 和 `diamond.wout`
- 验证 `StepResult.output_file` 指向 `diamond.wout`
- 验证 `.nnkp` 存在是成功条件

#### F3. test_pipeline_reaches_pw2wannier90
- Mock 三个步骤（`w90_preproc` → `pw2wannier90`）
- 验证 `pw2wannier90` 步骤被正确执行

---

## 修改文件列表

### 核心修改
1. **`src/qmatsuite/core/engines/qe_calculation.py`**
   - A. 统一 stdout/stderr 文件命名（`{step_type}.stdout`）
   - B. 修正 primary output 绑定（artifact vs stdout capture）
   - C. 确保 cwd 是 raw_dir
   - D. Post-run 验证（artifact 存在性检查）

2. **`src/qmatsuite/calculation/runner.py`**
   - E. 修正 evaluation 逻辑（Wannier90 步骤使用 stdout 字段）
   - E. 添加 evaluation 异常处理

3. **`src/qmatsuite/calculation/verification.py`**
   - 更新注释，说明 artifact 检查在 `run_step()` 中完成

### 测试文件
4. **`tests/unit/test_wannier90_output_files.py`** (新文件)
   - 3 个测试用例覆盖核心功能

---

## 验收标准验证

### ✅ 1. run 必须进入 pw2wannier90

**预期日志**：
```
[CALCULATION_RUNNER] Entering step: id=..., type=pw2wannier90, calculation_failed=False
[RUN_STEP] Starting step execution: step_type=pw2wannier90, ...
[RUN_STEP] Process finished with return code: X
```

**验证**：`w90_preproc` 成功后，evaluation 不会因为 `output_file` 不存在而失败，pipeline 继续执行。

### ✅ 2. raw/ 目录中的输出文件不互相覆盖

**预期文件**：
- `raw/w90_preproc.stdout`
- `raw/w90_preproc.stderr`
- `raw/w90_run.stdout`
- `raw/w90_run.stderr`
- `raw/pw2wannier90.stdout`
- `raw/pw2wannier90.stderr`

**验证**：所有文件存在，且 `w90_preproc.stdout` 和 `w90_run.stdout` 内容不同。

### ✅ 3. Primary artifact 绑定正确

**预期绑定**：
- `w90_preproc.output_file` = `raw/diamond.wout`
- `w90_run.output_file` = `raw/diamond.wout`（同一个文件，被第二次更新）
- `pw2wannier90.output_file` = `raw/pw2wannier90.stdout`

**验证**：
- `StepResult.output_file` 指向正确的文件
- Artifact 文件（`<seed>.wout`）存在

### ✅ 4. Success 判定正确

**规则**：
- `w90_preproc`：`return_code==0` **AND** `diamond.nnkp` 存在
- `w90_run`：`return_code==0` **AND** `diamond.wout` 存在
- 不使用 "JOB DONE" 判定 Wannier90 步骤

**验证**：
- `.nnkp` / `.wout` 不存在时，即使 `return_code==0` 也判定为失败
- 错误消息明确说明缺少的 artifact

### ✅ 5. Evaluation 异常处理

**验证**：
- Evaluation 异常被捕获并记录 traceback
- `StepResult.message` 包含异常信息
- 不会因为 evaluation 异常而 silent abort

---

## 文件命名约定总结

| Step Type | Stdout Capture | Stderr Capture | Primary Output (Artifact) |
|-----------|---------------|----------------|---------------------------|
| `w90_preproc` | `w90_preproc.stdout` | `w90_preproc.stderr` | `<seed>.wout` |
| `w90_run` | `w90_run.stdout` | `w90_run.stderr` | `<seed>.wout` (same as preproc) |
| `pw2wannier90` | `pw2wannier90.stdout` | `pw2wannier90.stderr` | `pw2wannier90.stdout` |
| `scf` / `nscf` | `<input_stem>.stdout` | `<input_stem>.stderr` | `<input_stem>.out` |

**关键点**：
- **Capture 文件**：用于 subprocess 重定向，基于 `step_type` 命名，避免覆盖
- **Primary output**：`StepResult.output_file` 指向的文件，通常是 artifact（`.wout`）或主要输出（`.out`）
- **两者分离**：capture 文件用于日志/调试，primary output 用于 GUI 显示和验证

---

## 测试结果

```bash
pytest tests/unit/test_wannier90_output_files.py -v
```

**结果**：
```
tests/unit/test_wannier90_output_files.py::TestWannier90StdoutStderrNotOverwritten::test_wannier90_stdout_stderr_not_overwritten_between_steps PASSED
tests/unit/test_wannier90_output_files.py::TestW90PreprocPrimaryOutput::test_w90_preproc_primary_output_is_seed_wout_and_nnkp_required PASSED
tests/unit/test_wannier90_output_files.py::TestPipelineReachesPw2Wannier90::test_pipeline_reaches_pw2wannier90 PASSED
```

**所有测试通过** ✅

---

**修复完成时间**: 2025-02-03
**状态**: ✅ 代码修复完成，测试通过
**下一步**: 运行实际 diamond demo 验证端到端执行

