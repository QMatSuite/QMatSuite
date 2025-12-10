# 稳健性测试总结（修正版）

## 验证结果

### 测试数量
- **实际新增测试数量：9 个**（原摘要错误地说是 10 个）

### 新增/修改的测试

#### 1. 工作流失败处理 (`tests/daemon/test_gui_job_and_step_flows.py`)
- `test_workflow_stops_after_step_failure`: 验证多步工作流中，中间步骤失败后，后续步骤被标记为 `SKIPPED`，工作流状态为 `FAILED`。

#### 2. 资源重命名边界情况 (`tests/unit/test_resource_rename_safety.py`)
- `test_rename_structure_slug_conflict_is_rejected`: 重命名结构时，若新 slug 与现有结构冲突，操作被拒绝，项目元数据保持不变。
- `test_rename_workflow_across_directories_updates_all_references`: 跨目录重命名工作流时，所有引用（project.qv.yml、workflow.yaml）正确更新。
- `test_multiple_consecutive_renames_keep_selector_stable`: 多次连续重命名后，基于稳定 ID/ULID 的选择器仍能正确解析。

#### 3. 快照边界情况 (`tests/unit/test_project_snapshot.py`)
- `test_restore_snapshot_with_missing_step_reports_issues`: 恢复快照后，若手动删除步骤文件，工作流应能加载（即使步骤文件缺失），如果加载失败则错误信息应明确提及缺失的步骤。
- `test_restore_snapshot_into_nonempty_project_handles_conflicts`: 恢复到非空项目目录时，创建新项目目录（不覆盖现有项目），两个项目可共存。

#### 4. 伪势解析边界情况 (`tests/unit/test_pseudopotential_resolution.py`)
- `test_pp_resolution_missing_element_reports_clear_error`: 在 strict 模式下，当元素缺少伪势文件时，抛出 `FileNotFoundError`，错误信息包含缺失元素、文件名和搜索路径。
- `test_pp_resolution_multiple_candidates_uses_defined_priority`: 当同一元素存在多个候选伪势文件时，解析器使用输入文件中明确指定的确切文件名（确定性行为）。注意：这不是自动优先级规则，而是尊重输入文件中的显式指定。
- `test_pp_resolution_bad_file_is_reported`: 当伪势文件不可读时，函数不会静默失败，会报告 I/O 错误或返回明确的错误状态。

### 实现更改

1. **工作流运行器** (`src/quantumvitas/workflow/runner.py`):
   - 添加 `SKIPPED` 状态到 `StepStatus` 枚举
   - 更新运行器：当步骤失败时，后续步骤被标记为 `SKIPPED` 而非跳过

2. **伪势解析** (`src/quantumvitas/core/pseudo.py`):
   - 在 strict 模式下，当伪势文件缺失时，抛出 `FileNotFoundError`，错误信息包含缺失元素、文件名和搜索路径

3. **资源重命名** (`src/quantumvitas/core/project_utils.py`):
   - 已实现 slug 冲突检查（`apply_structure_rename` 和 `apply_workflow_rename`）
   - 测试验证了这些行为

### 测试结果

所有 **9 个新测试**均通过：
- 3 个资源重命名边界情况测试
- 2 个快照边界情况测试
- 3 个伪势解析边界情况测试
- 1 个工作流失败处理测试

### 行为保证

每个新测试保证的行为：

1. **工作流失败处理**：多步工作流中，中间步骤失败后，后续步骤被标记为 `SKIPPED`，工作流状态为 `FAILED`。
2. **资源重命名安全性**：slug 冲突被拒绝；跨目录重命名更新所有引用；多次重命名后 ID 选择器仍有效。
3. **快照恢复稳健性**：缺失资源时工作流应能加载（数据不一致但可容忍），如果加载失败则错误信息明确；恢复到非空项目时创建新项目而非覆盖。
4. **伪势解析清晰性**：缺失元素时报告明确的错误；多个候选时使用输入文件中指定的确切文件名（确定性行为）；不可读文件时报告 I/O 错误。

所有现有测试继续通过，未引入回归。
