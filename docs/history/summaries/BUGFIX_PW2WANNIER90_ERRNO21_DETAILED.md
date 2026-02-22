# Bugfix: pw2wannier90 Errno 21 "Is a directory: '.'" 详细修复

## 问题描述

pw2wannier90 步骤执行时出现错误：
```
Error [Errno 21] Is a directory: '.'
```

从日志看，pw2wannier90 步骤的 `[RUN_STEP]` 日志根本没有出现，说明可能在调用 `run_step` 之前就失败了。

## 根本原因分析

1. **路径解析问题**: `build_command` 中修改了 `input_file` 参数，可能导致路径变成 `'.'` 或目录
2. **相对路径转换**: 将绝对路径转换为相对路径时，如果 `working_dir` 和 `input_file` 路径不匹配，可能出现问题
3. **缺少验证**: 在构建命令和验证路径时，缺少对 `'.'` 或目录路径的检查

## 修复内容

### 1. 修复 `build_command` 中的路径处理 (`src/qmatsuite/core/engines/qe.py`)

**Before** (有问题):
```python
elif step_type == "pw2wannier90":
    if input_file.is_absolute():
        try:
            input_file = input_file.relative_to(working_dir)  # 修改了参数！
        except ValueError:
            pass
    command.append("-i")
    command.append(str(input_file))
```

**After** (修复):
```python
elif step_type == "pw2wannier90":
    # pw2wannier90.x -i input.in (use -i flag, NOT stdin)
    # IMPORTANT: Use relative path from working_dir to avoid path issues
    input_file_resolved = Path(input_file)
    if input_file_resolved.is_absolute():
        try:
            input_file_rel = input_file_resolved.relative_to(working_dir.resolve())
            # Use just the filename (relative path from working_dir)
            command.append("-i")
            command.append(str(input_file_rel))
        except ValueError:
            # Not relative to working_dir, use absolute path as fallback
            command.append("-i")
            command.append(str(input_file_resolved))
    else:
        # Already relative, use as-is
        command.append("-i")
        command.append(str(input_file_resolved))
```

**关键改进**:
- 使用新变量 `input_file_resolved` 和 `input_file_rel`，不修改原始参数
- 确保使用 `working_dir.resolve()` 进行比较
- 明确处理相对和绝对路径

### 2. 增强 `run_step` 中的验证和日志 (`src/qmatsuite/core/engines/qe_calculation.py`)

添加了详细的验证逻辑：

```python
if step_type == "pw2wannier90":
    if "-i" in command:
        input_idx = command.index("-i")
        if input_idx + 1 < len(command):
            cmd_input_file_str = command[input_idx + 1]
            # ... 路径解析 ...
            
            # Safety checks
            if cmd_input_file_str in (".", "./", ".."):
                logger.error(f"ERROR: pw2wannier90 input file is '.' or invalid: '{cmd_input_file_str}'")
                raise ValueError(...)
            
            if cmd_input_file_resolved.exists() and cmd_input_file_resolved.is_dir():
                logger.error(f"ERROR: pw2wannier90 input file is a directory: {cmd_input_file_resolved}")
                raise ValueError(...)
            
            if not cmd_input_file_resolved.exists():
                logger.error(f"ERROR: pw2wannier90 input file does not exist: {cmd_input_file_resolved}")
                # List files in working_dir for debugging
                if working_dir.exists():
                    files_in_workdir = list(working_dir.glob("*"))
                    logger.error(f"Files in working_dir: {[f.name for f in files_in_workdir]}")
                raise FileNotFoundError(...)
```

**关键改进**:
- 检查 `'.'`, `'./'`, `'..'` 等无效路径
- 验证路径不是目录
- 验证文件存在
- 列出 working_dir 中的文件用于调试
- 详细的日志记录

### 3. 修复 `run_prepared_step` 中的路径处理 (`src/qmatsuite/calculation/input_runner.py`)

确保传递给 `run_step` 的路径是正确的：

```python
if step_type == "pw2wannier90":
    # Use filename relative to working_dir for -i flag
    if prepared_step.modified_input.is_absolute():
        try:
            rel_path = prepared_step.modified_input.relative_to(prepared_step.working_dir.resolve())
            input_file_for_command = rel_path
        except ValueError:
            input_file_for_command = prepared_step.modified_input
    else:
        input_file_for_command = prepared_step.modified_input
else:
    input_file_for_command = prepared_step.modified_input

step_result = engine.run_step(
    input_file=input_file_for_command,  # 使用处理后的路径
    working_dir=prepared_step.working_dir,
    step_type=step_type,
    timeout=timeout,
)
```

## 执行流程（修复后）

1. **Materialization**: 生成 `pw2wan.in` 在 `raw/` 目录
2. **prepare_input_step**: 对于 pw2wannier90，直接复制文件到 working_dir（如果不在）
3. **run_prepared_step**: 将绝对路径转换为相对路径（相对于 working_dir）
4. **build_command**: 使用相对路径构建命令: `pw2wannier90.x -i pw2wan.in`
5. **run_step**: 验证路径，确保不是 `'.'` 或目录，然后执行

## 日志输出（修复后）

修复后应该看到详细的日志：

```
[RUN_STEP] Starting step execution: step_type=pw2wannier90, input_file=pw2wan.in, working_dir=/path/to/raw
[RUN_STEP] Built command: pw2wannier90.x -i pw2wan.in
[RUN_STEP] uses_stdin: False (step_type=pw2wannier90)
[RUN_STEP] pw2wannier90 input file validation:
[RUN_STEP]   Command arg: 'pw2wan.in'
[RUN_STEP]   Resolved path: /path/to/raw/pw2wan.in
[RUN_STEP]   Exists: True
[RUN_STEP]   Is dir: False
[RUN_STEP]   Is file: True
[RUN_STEP]   Working dir: /path/to/raw
[RUN_STEP] Started process for pw2wannier90, PID: ...
```

## 如果仍然失败

如果修复后仍然失败，日志会显示：
1. 输入文件路径是什么
2. 是否被错误地解析为 `'.'`
3. working_dir 中实际有哪些文件
4. 路径解析的每一步

这将帮助定位问题的确切位置。

