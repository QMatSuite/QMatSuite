# Bugfix: pw2wannier90 Errno 21 完整修复总结

## 问题

pw2wannier90 步骤执行时出现：
```
Error [Errno 21] Is a directory: '.'
```

且日志中没有 pw2wannier90 的 `[RUN_STEP]` 日志，说明可能在调用 `run_step` 之前就失败了。

## 根本原因

可能的原因：
1. **路径解析问题**: `input_file` 被错误地解析为 `'.'` 或目录路径
2. **ensure_qe_pseudos 被意外调用**: 虽然 Wannier90 步骤应该跳过，但可能在某些路径下被调用
3. **Path.resolve() 问题**: `Path.resolve()` 在某些情况下可能返回 `'.'`

## 完整修复

### 1. `build_command` 中的路径处理 (`src/quantumvitas/core/engines/qe.py`)

- 使用新变量 `input_file_resolved` 和 `input_file_rel`，不修改原始参数
- 添加安全检查，防止 `'.'` 或目录路径
- 确保正确转换为相对路径

### 2. `run_step` 中的验证和日志 (`src/quantumvitas/core/engines/qe_calculation.py`)

- 详细的路径验证（检查 `'.'`, `'./'`, `'..'`）
- 验证文件不是目录
- 验证文件存在
- 列出 working_dir 中的文件用于调试
- 详细的日志记录（INFO 级别）

### 3. `prepare_input_step` 中的安全检查 (`src/quantumvitas/calculation/input_runner.py`)

- 对于 Wannier90 步骤，添加完整的安全检查
- 验证 `input_file` 不是 `'.'` 或目录
- 验证文件存在
- 详细的日志记录

### 4. `run_prepared_step` 中的路径转换 (`src/quantumvitas/calculation/input_runner.py`)

- 确保传递给 `run_step` 的路径是相对路径（相对于 working_dir）
- 详细的日志记录

### 5. `ensure_qe_pseudos` 中的安全检查 (`src/quantumvitas/core/pseudo.py`)

- 添加安全检查，防止 `'.'` 或目录路径
- 对于有 `species_map` 的情况，跳过不必要的 QE 输入解析
- 详细的日志记录

## 关键安全检查点

1. **prepare_input_step**: 验证 `input_file` 不是 `'.'` 或目录
2. **build_command**: 验证路径并转换为相对路径
3. **run_step**: 验证命令中的输入文件路径
4. **ensure_qe_pseudos**: 验证 `qe_input_file` 不是 `'.'` 或目录

## 日志输出

修复后，应该看到详细的日志：

```
[PREPARE_INPUT_STEP] Wannier90 step detected: step_type=pw2wannier90
[PREPARE_INPUT_STEP] input_file: /path/to/raw/pw2wan.in
[PREPARE_INPUT_STEP] input_path_resolved: /path/to/raw/pw2wan.in
[PREPARE_INPUT_STEP] working_dir_input: /path/to/raw/pw2wan.in
[PREPARE_INPUT_STEP] Wannier90 step prepared: modified_input=/path/to/raw/pw2wan.in

[RUN_PREPARED_STEP] pw2wannier90: converted absolute path to relative: pw2wan.in

[RUN_STEP] Starting step execution: step_type=pw2wannier90, input_file=pw2wan.in, working_dir=/path/to/raw
[RUN_STEP] Built command: pw2wannier90.x -i pw2wan.in
[RUN_STEP] uses_stdin: False (step_type=pw2wannier90)
[RUN_STEP] pw2wannier90 input file validation:
[RUN_STEP]   Command arg: 'pw2wan.in'
[RUN_STEP]   Resolved path: /path/to/raw/pw2wan.in
[RUN_STEP]   Exists: True
[RUN_STEP]   Is dir: False
[RUN_STEP]   Is file: True
[RUN_STEP] Started process for pw2wannier90, PID: ...
```

## 如果仍然失败

如果修复后仍然失败，日志会清楚显示：
1. `input_file` 的值是什么
2. 是否被错误地解析为 `'.'`
3. working_dir 中实际有哪些文件
4. 路径解析的每一步
5. 在哪一步失败

这将帮助定位问题的确切位置。

