# pw2wannier90 Errno 21 根因分析报告

## 执行摘要

**问题**: pw2wannier90 步骤在执行时出现 `Error [Errno 21] Is a directory: '.'`，并且该步骤的 `[RUN_STEP]` 日志从未出现。

**关键发现**: 从日志分析看，pw2wannier90 步骤根本没有被执行。日志显示：
- ✅ SCF 步骤执行成功
- ✅ NSCF 步骤执行成功  
- ✅ w90_preproc 步骤开始执行（有 PREPARE_INPUT_STEP 和 RUN_STEP 日志）
- ❌ **pw2wannier90 步骤的日志完全缺失**

**结论**: 问题不在 pw2wannier90 本身的执行逻辑，而是**该步骤根本没有被调用**。可能的原因：
1. w90_preproc 步骤失败，导致后续步骤被跳过
2. 步骤执行逻辑中的错误处理/依赖关系问题
3. 步骤结果检查逻辑导致步骤被静默跳过

---

## 一、问题症状

### 1.1 用户报告的日志

```
[qv-daemon] [INFO] [quantumvitas.core.engines.qe_calculation] [RUN_STEP] Starting step execution: step_type=scf, ...
[qv-daemon] [INFO] [quantumvitas.core.engines.qe_calculation] [RUN_STEP] Starting step execution: step_type=nscf, ...
[qv-daemon] [INFO] [quantumvitas.calculation.input_runner] [PREPARE_INPUT_STEP] Wannier90 step detected: step_type=w90_preproc
[qv-daemon] [INFO] [quantumvitas.calculation.input_runner] [PREPARE_INPUT_STEP] Wannier90 step prepared: modified_input=.../diamond.win
[qv-daemon] [INFO] [quantumvitas.core.engines.qe_calculation] [RUN_STEP] Starting step execution: step_type=w90_preproc, ...
[qv-daemon] [INFO] [quantumvitas.core.engines.qe_calculation] [RUN_STEP] Built command: .../wannier90.x -pp diamond
[qv-daemon] [INFO] [quantumvitas.core.engines.qe_calculation] [RUN_STEP] uses_stdin: False (step_type=w90_preproc)

# ❌ 缺失：pw2wannier90 的 PREPARE_INPUT_STEP 和 RUN_STEP 日志
# ❌ 缺失：w90_run 的日志
```

### 1.2 关键观察

1. **w90_preproc 步骤启动了，但没有完成日志**
   - 有 `[RUN_STEP] Starting step execution`
   - 有 `Built command` 和 `uses_stdin: False`
   - **但没有看到** `Process finished with return code` 或 `Step execution completed`

2. **pw2wannier90 步骤完全没有日志**
   - 没有 `[PREPARE_INPUT_STEP]` 日志
   - 没有 `[RUN_STEP]` 日志
   - 说明该步骤从未被调用

3. **步骤执行链断裂**
   - w90_preproc → pw2wannier90 → w90_run
   - 链在 w90_preproc 执行后就中断了

---

## 二、我们做了什么修复

### 2.1 修复列表（按时间顺序）

#### 修复 1: pw2wannier90 命令格式 (`src/quantumvitas/core/engines/qe.py`)
- **问题**: 使用 stdin 重定向导致 Errno 21
- **修复**: 改为 `pw2wannier90.x -i pw2wan.in` 格式
- **状态**: ✅ 已实施

#### 修复 2: uses_stdin 方法 (`src/quantumvitas/core/engines/qe.py`)
- **问题**: pw2wannier90 被标记为使用 stdin
- **修复**: `uses_stdin("pw2wannier90")` 返回 `False`
- **状态**: ✅ 已实施

#### 修复 3: build_command 路径处理 (`src/quantumvitas/core/engines/qe.py`)
- **问题**: 路径可能被错误解析为 `'.'`
- **修复**: 使用新变量，添加安全检查，确保转换为相对路径
- **状态**: ✅ 已实施

#### 修复 4: run_step 验证逻辑 (`src/quantumvitas/core/engines/qe_calculation.py`)
- **问题**: 缺少对 `'.'` 或目录路径的验证
- **修复**: 添加详细的路径验证和日志
- **状态**: ✅ 已实施

#### 修复 5: prepare_input_step 安全检查 (`src/quantumvitas/calculation/input_runner.py`)
- **问题**: Wannier90 步骤缺少路径验证
- **修复**: 添加完整的安全检查和日志
- **状态**: ✅ 已实施

#### 修复 6: run_prepared_step 路径转换 (`src/quantumvitas/calculation/input_runner.py`)
- **问题**: 绝对路径可能传递给 `-i` 选项
- **修复**: 确保转换为相对路径
- **状态**: ✅ 已实施

#### 修复 7: ensure_qe_pseudos 安全检查 (`src/quantumvitas/core/pseudo.py`)
- **问题**: 可能被调用时传入 `'.'` 路径
- **修复**: 添加安全检查，跳过 Wannier90 文件的解析
- **状态**: ✅ 已实施

### 2.2 修复统计

- **文件修改**: 4 个文件
- **新增安全检查**: 7 处
- **新增日志**: 20+ 处
- **修复时间**: 多次迭代

---

## 三、Code Review 发现

### 3.1 步骤执行流程 (`src/quantumvitas/calculation/runner.py`)

```python
class CalculationRunner:
    def run(self, calculation: Calculation) -> CalculationResult:
        # ...
        for step in calculation.steps:
            # 如果前一步失败且为 strict 模式，跳过后续步骤
            if calculation_failed:
                step_summaries.append(StepResultSummary(
                    status=StepStatus.SKIPPED,
                    message="Step skipped because a previous step failed",
                ))
                continue
            
            # 执行步骤
            result = step.run(...)
            
            # 检查结果
            step_status, message, metrics = self._determine_step_status(
                result, step_mode
            )
            
            # 如果失败，设置 calculation_failed
            if step_status != StepStatus.SUCCESS:
                calculation_failed = True
```

### 3.2 关键问题点

#### 问题点 1: 步骤执行后的状态检查

从代码看，如果 `w90_preproc` 步骤执行后返回的 `result.success` 为 `False`，那么：
1. `step_status` 会被设置为非 `SUCCESS`
2. `calculation_failed = True`
3. **后续步骤会被跳过（包括 pw2wannier90）**

#### 问题点 2: 异常处理可能吞掉错误

如果 `step.run()` 抛出异常，可能：
1. 被上层捕获
2. 返回一个失败的 `StepResult`
3. 或者导致整个计算中断

但从日志看，没有看到异常日志，说明可能是：
- 步骤返回了 `success=False`，但没有详细的错误信息
- 或者异常被静默捕获了

#### 问题点 3: w90_preproc 的执行可能失败

从日志看：
- w90_preproc 启动了（`[RUN_STEP] Starting step execution`）
- 命令构建成功（`Built command: wannier90.x -pp diamond`）
- **但没有看到执行完成日志**

可能的原因：
1. `wannier90.x -pp diamond` 执行失败
2. `run_step` 返回了 `success=False`
3. 但没有详细的错误日志被记录

### 3.3 缺失的日志点

应该有的日志但没有出现：

1. **w90_preproc 执行完成后**:
   ```
   [RUN_STEP] Process for w90_preproc finished with return code: X
   [RUN_STEP] Step execution completed: success=True/False
   ```

2. **步骤状态检查后**:
   ```
   [CALCULATION_RUNNER] Step w90_preproc status: SUCCESS/FAILED
   [CALCULATION_RUNNER] calculation_failed: True/False
   ```

3. **pw2wannier90 步骤开始前**:
   ```
   [CALCULATION_RUNNER] Starting step pw2wannier90 (step_id=...)
   [PREPARE_INPUT_STEP] Wannier90 step detected: step_type=pw2wannier90
   ```

---

## 四、根本原因分析

### 4.1 最可能的根因

**假设**: w90_preproc 步骤执行失败（或返回 `success=False`），导致：
1. `calculation_failed = True`
2. pw2wannier90 步骤被标记为 `SKIPPED`
3. 但错误信息没有被正确记录/显示

### 4.2 验证假设需要的证据

需要检查以下内容：

1. **w90_preproc 步骤的实际返回码**:
   - `wannier90.x -pp diamond` 是否成功执行？
   - 是否生成了 `diamond.nnkp` 文件？

2. **步骤结果对象**:
   - `result.success` 的值是什么？
   - `result.error` 或 `result.stderr` 中有什么？

3. **计算运行状态**:
   - `calculation_failed` 是否被设置为 `True`？
   - 是否有 `SKIPPED` 状态的步骤？

### 4.3 为什么 Errno 21 没有出现？

**关键发现**: 从最新日志看，**Errno 21 错误根本没有出现**！

之前的 Errno 21 可能是：
1. 在之前的代码版本中出现的
2. 或者出现在不同的执行路径中（例如直接调用 pw2wannier90，而不是通过 CalculationRunner）

现在的真实问题是：**pw2wannier90 步骤根本没有被执行**。

---

## 五、问题定位建议

### 5.1 需要检查的日志/文件

1. **检查 w90_preproc 的输出文件**:
   ```bash
   ls -la <HOME>/Documents/diamond-wannier90-demo/calculations/diamond-mlwfs/raw/
   # 应该看到 diamond.nnkp（如果成功）
   # 应该看到 diamond.wout 或 diamond.werr（如果有错误）
   ```

2. **检查步骤执行结果**:
   - 查看 `CalculationResult` 对象中的 `steps` 列表
   - 检查每个步骤的 `status` 和 `message`

3. **检查计算模式**:
   - `calculation.mode` 是否为 `strict`？
   - 如果是 `strict`，一个步骤失败会导致后续步骤被跳过

### 5.2 需要添加的诊断日志

在 `CalculationRunner.run()` 中添加：

```python
logger.info(f"[CALCULATION_RUNNER] Starting step {step.id} (type={step.step_type})")
result = step.run(...)
logger.info(f"[CALCULATION_RUNNER] Step {step.id} result: success={result.success}, error={result.error}")
step_status, message, metrics = self._determine_step_status(result, step_mode)
logger.info(f"[CALCULATION_RUNNER] Step {step.id} status: {step_status}, message={message}")
if step_status != StepStatus.SUCCESS:
    logger.warning(f"[CALCULATION_RUNNER] Step {step.id} failed, calculation_failed will be set to True")
    calculation_failed = True
```

### 5.3 需要检查的代码路径

1. **`step.run()` 的实现** (`src/quantumvitas/calculation/step.py`):
   - 是否正确处理异常？
   - 是否正确返回 `StepResult`？

2. **`run_input_step()` 的实现** (`src/quantumvitas/calculation/input_runner.py`):
   - 是否正确处理 Wannier90 步骤？
   - 是否可能抛出异常？

3. **`QECalculationRunner.run_step()` 的实现** (`src/quantumvitas/core/engines/qe_calculation.py`):
   - 对于非 stdin 步骤，是否正确处理？
   - 是否可能返回 `success=False` 但没有错误信息？

---

## 六、结论与下一步

### 6.1 结论

1. **之前的 Errno 21 修复是必要的**，但这些修复解决的是一个不同的问题（pw2wannier90 执行时的路径问题）。

2. **当前的真实问题是**: pw2wannier90 步骤根本没有被执行，而不是执行时出错。

3. **可能的原因**: w90_preproc 步骤失败，导致后续步骤被跳过。

4. **缺失的关键信息**: 
   - w90_preproc 的执行结果
   - 步骤状态检查的日志
   - 计算失败的原因

### 6.2 下一步行动

1. **立即检查**:
   - w90_preproc 的输出文件（`.nnkp`, `.wout`, `.werr`）
   - 计算结果的步骤状态列表

2. **添加诊断日志**:
   - 在 `CalculationRunner.run()` 中添加步骤执行前后的日志
   - 在 `step.run()` 中添加异常捕获和日志

3. **验证假设**:
   - 手动运行 `wannier90.x -pp diamond` 验证命令是否正确
   - 检查 `diamond.win` 文件内容是否正确

4. **修复策略**:
   - 如果 w90_preproc 确实失败，修复该步骤的问题
   - 如果 w90_preproc 成功但被误判为失败，修复状态检查逻辑
   - 确保错误信息被正确传播和记录

---

## 七、经验教训

### 7.1 调试方法论

1. **症状 vs 根因**: 
   - 症状: "Errno 21" 错误
   - 根因: 步骤没有被执行
   - 教训: 需要区分症状和根本问题

2. **日志的重要性**:
   - 缺失的关键日志阻碍了问题定位
   - 应该在关键决策点添加日志（步骤开始、完成、状态检查）

3. **假设验证**:
   - 多次修复基于"pw2wannier90 执行时出错"的假设
   - 但实际问题是"pw2wannier90 没有被执行"
   - 应该先验证假设，再实施修复

### 7.2 代码质量

1. **错误处理**:
   - 需要确保所有异常都被捕获和记录
   - 需要确保步骤失败的状态被正确传播

2. **日志完整性**:
   - 关键执行路径应该有完整的日志覆盖
   - 错误情况应该有详细的诊断信息

3. **测试覆盖**:
   - 应该添加集成测试验证完整的步骤执行链
   - 应该测试步骤失败时的行为

---

## 附录：相关文件列表

### 修改的文件
- `src/quantumvitas/core/engines/qe.py`
- `src/quantumvitas/core/engines/qe_calculation.py`
- `src/quantumvitas/calculation/input_runner.py`
- `src/quantumvitas/core/pseudo.py`

### 关键代码位置
- `src/quantumvitas/calculation/runner.py:150` - 步骤执行循环
- `src/quantumvitas/calculation/step.py:69` - Step.run() 方法
- `src/quantumvitas/calculation/input_runner.py:389` - run_input_step() 方法
- `src/quantumvitas/core/engines/qe_calculation.py:122` - run_step() 方法

### 相关文档
- `docs/BUGFIX_PW2WANNIER90_FILENAME.md`
- `docs/BUGFIX_PW2WANNIER90_ERRNO21_DETAILED.md`
- `docs/BUGFIX_PW2WANNIER90_ERRNO21_FINAL.md`

---

**报告生成时间**: 2025-02-03
**问题状态**: 待定位根因（pw2wannier90 步骤未被执行）
**下一步**: 检查 w90_preproc 执行结果，添加诊断日志

