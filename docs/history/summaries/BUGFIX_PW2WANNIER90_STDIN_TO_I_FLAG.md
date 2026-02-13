# Bugfix: pw2wannier90 使用 -i 标志而不是 stdin

## 问题

pw2wannier90 步骤在执行时出现错误：
```
Error [Errno 21] Is a directory: '.'
```

用户手动运行 `pw2wannier90.x -i pw2wan.in > pw2wan.out 2>&1` 没有问题，说明 pw2wannier90.x 应该使用 `-i` 选项来指定输入文件，而不是从 stdin 读取。

## 根本原因

1. **pw2wannier90.x 支持两种输入方式**：
   - `pw2wannier90.x < input.in` (stdin 重定向) - 在某些情况下会导致路径解析问题
   - `pw2wannier90.x -i input.in` (命令行选项) - 更可靠，用户验证可用

2. **代码问题**：
   - `uses_stdin("pw2wannier90")` 返回 `True`，导致代码尝试使用 stdin 重定向
   - stdin 重定向时，`input_file` 路径解析可能出错，导致 `stdin_file` 被设置为 `'.'` 或目录路径

3. **与 pw.x 的区别**：
   - `pw.x` 标准使用 stdin 重定向 (`pw.x < input.in`)
   - `pw2wannier90.x` 虽然也支持 stdin，但使用 `-i` 选项更可靠，避免了路径解析问题

## 修复

### 1. 修改命令构建 (`src/quantumvitas/core/engines/qe.py`)

**Before**:
```python
# pw2wannier90 uses stdin like regular QE, no special handling needed
```

**After**:
```python
elif step_type == "pw2wannier90":
    # pw2wannier90.x -i input.in (use -i flag, NOT stdin)
    # Resolve input file path relative to working_dir
    if input_file.is_absolute():
        # Make relative to working_dir if possible
        try:
            input_file = input_file.relative_to(working_dir)
        except ValueError:
            pass  # Keep absolute if not relative
    command.append("-i")
    command.append(str(input_file))
```

### 2. 更新 `uses_stdin` 方法 (`src/quantumvitas/core/engines/qe.py`)

**Before**:
```python
def uses_stdin(self, step_type: str) -> bool:
    return step_type not in ["w90_preproc", "w90_run"]
```

**After**:
```python
def uses_stdin(self, step_type: str) -> bool:
    """
    Check if step type uses stdin for input (vs command-line arguments).
    
    Wannier90 steps (w90_preproc, w90_run, pw2wannier90) use command-line arguments,
    while most QE steps (pw.x, ph.x, etc.) use stdin redirection.
    
    pw2wannier90.x uses -i flag (not stdin) to avoid Errno 21 issues.
    """
    return step_type not in ["w90_preproc", "w90_run", "pw2wannier90"]
```

### 3. 添加详细日志 (`src/quantumvitas/core/engines/qe_calculation.py`)

在 `run_step` 方法中添加了详细的日志记录：
- 步骤开始和参数
- 输入文件路径解析
- 命令构建
- stdin 使用判断
- 文件存在性检查
- 进程执行状态
- 结果返回

特别是对于 pw2wannier90：
- 验证 `-i` 选项后的输入文件路径
- 检查输入文件是否为目录
- 记录 stdout/stderr 写入

### 4. 修复 stdout/stderr 处理

**Before**: pw2wannier90 在非 stdin 分支，但 stdout/stderr 处理不完整

**After**:
```python
# For pw2wannier90, write stdout and stderr to files
if step_type == "pw2wannier90":
    output_file.write_text(stdout)
    if stderr_file and stderr_file.exists():
        stderr_file.write_text(stderr)
```

## 执行命令对比

### 修复前
```bash
pw2wannier90.x < pw2wan.in > pw2wan.out 2> pw2wan.stderr
# 问题: stdin 重定向可能导致路径解析错误 (Errno 21)
```

### 修复后
```bash
pw2wannier90.x -i pw2wan.in > pw2wan.out 2> pw2wan.stderr
# 使用 -i 选项，避免路径解析问题
```

## 对比 pw.x 和 pw2wannier90.x

| 步骤类型 | 输入方式 | 命令格式 |
|---------|---------|---------|
| `scf`, `nscf` (pw.x) | stdin | `pw.x < input.in > output.out` |
| `pw2wannier90` | `-i` 选项 | `pw2wannier90.x -i input.in > output.out` |
| `w90_preproc` | 命令行参数 | `wannier90.x -pp seedname` |
| `w90_run` | 命令行参数 | `wannier90.x seedname` |

**为什么 pw.x 和 pw2wannier90.x 不同？**
- `pw.x` 是 QE 的核心程序，设计为从 stdin 读取输入（这是 QE 的标准做法）
- `pw2wannier90.x` 虽然也支持 stdin，但它也支持 `-i` 选项，使用选项更可靠，避免了 stdin 重定向时的路径解析问题

## 验证

修复后：
- ✅ `uses_stdin("pw2wannier90")` 返回 `False`
- ✅ 命令构建为 `pw2wannier90.x -i pw2wan.in`
- ✅ 不再使用 stdin 重定向
- ✅ 添加了详细的日志记录，便于调试路径解析问题
- ✅ 正确处理 stdout/stderr 文件写入

## 日志输出示例

修复后，运行 pw2wannier90 步骤时会看到类似日志：

```
[RUN_STEP] Starting step execution: step_type=pw2wannier90, input_file=pw2wan.in, working_dir=/path/to/raw
[RUN_STEP] Built command: pw2wannier90.x -i pw2wan.in
[RUN_STEP] uses_stdin: False (step_type=pw2wannier90)
[RUN_STEP] Using command-line arguments for pw2wannier90 (no stdin)
[RUN_STEP] pw2wannier90 input file from command: pw2wan.in
[RUN_STEP] pw2wannier90 input file resolved: /path/to/raw/pw2wan.in
[RUN_STEP] pw2wannier90 input file exists: True
[RUN_STEP] pw2wannier90 input file is_file: True
[RUN_STEP] Started process for pw2wannier90, PID: 12345
[RUN_STEP] Process completed, returncode: 0
[RUN_STEP] pw2wannier90 wrote stdout to /path/to/raw/pw2wan.out
[RUN_STEP] pw2wannier90 wrote stderr to /path/to/raw/pw2wan.stderr
[RUN_STEP] Step completed: step_type=pw2wannier90, success=True, time=2.34s
```

## 相关文件

- `src/quantumvitas/core/engines/qe.py`: 命令构建和 stdin 判断
- `src/quantumvitas/core/engines/qe_calculation.py`: 执行逻辑和日志

