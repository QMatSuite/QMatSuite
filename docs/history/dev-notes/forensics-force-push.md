# Force Push / 历史改写事故排查报告

**报告日期**: 2026-01-13  
**仓库**: QMatSuite/QMatSuite  
**调查范围**: 检查是否发生过 `git push --force` 或非快进更新，并尝试找回被覆盖的提交

---

## A. 基础信息收集

### A1) 仓库配置

**Remote 配置**:
```
origin	https://github.com/QMatSuite/QMatSuite (fetch)
origin	https://github.com/QMatSuite/QMatSuite (push)
```

**当前分支状态**:
- **当前分支**: `v2-python`
- **跟踪关系**: `origin/v2-python` (ahead 4 commits)
- **工作目录**: 有未提交的修改（多个文件 modified，包括 docs/dev/ 等新文件）

**远程分支列表**:
- `origin/HEAD` -> `origin/v2-python`
- `origin/v1-java-legacy`
- `origin/v2-python`

**主要分支候选**:
- `v2-python` (主分支，对应 `origin/v2-python`)

---

## B. 查证是否发生过强制更新（核心证据）

### B1) 远端跟踪分支 reflog（最重要）

#### B1.1 origin/v2-python reflog 分析

**关键发现**: ✅ **发现一次 forced-update 记录**

```
31a4fe3 refs/remotes/origin/v2-python@{2026-01-04 10:39:54 -0500}: fetch: forced-update
```

**时间线分析**:
- **2026-01-01 16:52:09**: `baac796` - `update by push` (正常推送)
- **2026-01-04 10:39:54**: `31a4fe3` - `fetch: forced-update` ⚠️ **强制更新**

**可疑条目完整记录**:
```
31a4fe3 refs/remotes/origin/v2-python@{2026-01-04 10:39:54 -0500}: fetch: forced-update
baac796 refs/remotes/origin/v2-python@{2026-01-01 16:52:09 -0500}: update by push
```

**分析**:
- `baac796` 在 2026-01-01 被正常推送到 `origin/v2-python`
- 3 天后（2026-01-04），`origin/v2-python` 被强制更新到 `31a4fe3`
- 这意味着 `baac796` 及其后续提交被覆盖

### B2) 全局 reflog 搜关键字

**搜索命令**: `git reflog --date=iso --all | grep -i "forced-update\|update by push\|push\|rebase\|reset"`

**关键命中**:
1. **forced-update**:
   ```
   31a4fe3 refs/remotes/origin/v2-python@{2026-01-04 10:39:54 -0500}: fetch: forced-update
   ```

2. **reset** (本地操作，不影响远端):
   ```
   28ec1ab refs/heads/v2-python@{2026-01-12 21:05:02 -0500}: reset: moving to origin/v2-python
   28ec1ab HEAD@{2026-01-12 21:05:02 -0500}: reset: moving to origin/v2-python
   ```

**结论**: ✅ **确认发生过一次 forced-update**，发生在 2026-01-04 10:39:54，将 `origin/v2-python` 从 `baac796` 强制更新到 `31a4fe3`。

---

## C. 寻找"被覆盖的提交"并尝试恢复

### C1) 从 reflog 提取旧 SHA

#### C1.1 被覆盖的提交分析

**被覆盖的提交**: `baac796` (2026-01-01 16:52:04)

**提交信息**:
```
Implement key access enforcement for ParamSpace: Introduced a comprehensive key-access enforcement mechanism in accordance with Constitution 10.8.9, ensuring that each ParamSpace can only access its owned keys and preventing unauthorized access. Updated the ParamSpace class to register owned keys and validate ownership during operations. Enhanced error handling with KeyAccessError for violations. Adjusted related functions and tests to reflect these changes, ensuring compliance and stability across the application.
```

**提交统计**:
```
13 files changed, 1775 insertions(+), 193 deletions(-)
```

**关键文件变更**:
- `CONSTITUTION_ZH.md` (+58 lines) - 添加了 §10.8.9 ParamSpace Key Access 规则
- `OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md` (+336 lines) - **新增诊断文档**
- `YAML_DICT_USAGE_REVIEW.md` (+679 lines) - **新增审查文档**
- `src/qmatsuite/presets/paramspace.py` (大幅修改，+511 lines)
- `tests/unit/test_key_access_enforcement.py` (+267 lines) - **新增测试文件**

**父提交**: `b4a7b0f` - "Merge ParamSpace Constitution into global framework"

#### C1.2 提交关系分析

**共同祖先**: `616d837` (2025-12-31 19:06:51)

**分支差异**:
- **baac796 分支独有提交** (2 个):
  - `baac796` - "Implement key access enforcement for ParamSpace"
  - `b4a7b0f` - "Merge ParamSpace Constitution into global framework"

- **31a4fe3 分支独有提交** (12 个):
  - `31a4fe3` - "Implement unified output file naming convention"
  - `e4bcb23` - "Enhance Calculation Analysis Panel"
  - `c8196ff` - "Implement prefix/outdir injection handling"
  - `3d2b4d2` - "Enhance logging and parameter handling"
  - `05fb6cf` - "Refactor PySCF Engine for Subprocess Execution"
  - `b8471a6` - "Add PySCF integration"
  - `8d1f745` - "Update development notes for PySCF"
  - `b8800e4` - "Refactor Calculation Handling to Use ULID"
  - `94cedee` - "Enhance YAML Document Handling and Introduce Convergence Dimension"
  - `4248dab` - "Add workflow template support"
  - `917eac2` - "Integrate Journal System"
  - `37d7cdf` - "Refactor step parameter loading using StepDoc"

**结论**: `baac796` 和 `31a4fe3` 是两个不同的开发分支，在 `616d837` 之后分叉。强制更新导致 `baac796` 分支的工作丢失。

### C2) 查 dangling commits（强推/重写历史常见残留）

**搜索命令**: `git fsck --lost-found`

**结果**: ✅ **发现 1 个 dangling commit**

```
dangling commit baac796e5b26149fcb26ae909362caed5de68faa
```

**分析**:
- 这正是被覆盖的提交 `baac796`
- 由于强制更新，这个提交在远端分支历史中消失，但在本地 reflog 和对象数据库中仍然存在
- 这是一个"孤立的提交"（orphaned commit），可以通过 reflog 或对象数据库找回

**已创建救援分支**:
```bash
git branch rescue/baac796-key-access-enforcement baac796
```

**救援分支信息**:
- **分支名**: `rescue/baac796-key-access-enforcement`
- **指向提交**: `baac796`
- **提交摘要**: "Implement key access enforcement for ParamSpace"
- **关键内容**:
  - ParamSpace key access enforcement 实现
  - `OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md` 诊断文档
  - `YAML_DICT_USAGE_REVIEW.md` 审查文档
  - `test_key_access_enforcement.py` 测试文件
  - CONSTITUTION_ZH.md §10.8.9 章节

---

## D. （可选但推荐）确认是否存在非快进 push 的外部迹象

**GitHub 检查**: ⚠️ **未检查**（无法访问 GitHub 网页界面）

**建议**: 在 GitHub 仓库的 `origin/v2-python` 分支页面查看：
- Branch timeline / commit history
- 是否有 "force-pushed" 事件标记
- 2026-01-04 前后的提交历史变化

---

## E. 报告结论格式

### E1 是否发生过强推/历史改写？

**结论**: ✅ **是**

**证据**:
- **时间**: 2026-01-04 10:39:54 -0500
- **操作**: `fetch: forced-update`
- **从**: `baac796` (2026-01-01 16:52:09 推送)
- **到**: `31a4fe3` (2026-01-04 10:39:54 强制更新)
- **reflog 记录**: `31a4fe3 refs/remotes/origin/v2-python@{2026-01-04 10:39:54 -0500}: fetch: forced-update`

### E2 影响范围

**受影响分支**: `origin/v2-python`

**可能覆盖的提交范围**:
- **From**: `baac796` (2026-01-01 16:52:04)
- **To**: `31a4fe3` (2026-01-04 10:39:54)

**被覆盖的提交** (2 个):
1. `baac796` - "Implement key access enforcement for ParamSpace"
2. `b4a7b0f` - "Merge ParamSpace Constitution into global framework"

**共同祖先**: `616d837` (2025-12-31 19:06:51)

### E3 可恢复性

**是否找到 old HEAD**: ✅ **是**
- **SHA**: `baac796e5b26149fcb26ae909362caed5de68faa`
- **提交信息**: "Implement key access enforcement for ParamSpace"
- **恢复来源**: reflog + dangling commit

**是否找到 dangling commits**: ✅ **是**
- **数量**: 1 个
- **SHA**: `baac796e5b26149fcb26ae909362caed5de68faa`
- **状态**: 已创建救援分支

**已创建的救援分支列表**:
- `rescue/baac796-key-access-enforcement` (指向 `baac796`)

### E4 下一步建议（只给命令，不做操作）

#### E4.1 如何 checkout 对比

```bash
# 查看救援分支内容
git checkout rescue/baac796-key-access-enforcement

# 查看被覆盖的提交详情
git show baac796

# 查看被覆盖的提交列表
git log --oneline baac796 --not 31a4fe3

# 对比两个分支的差异
git diff 31a4fe3..baac796
```

#### E4.2 如何把救援分支内容拣回当前主线

**选项 1: Cherry-pick（推荐）**
```bash
# 切换到目标分支
git checkout v2-python

# Cherry-pick 被覆盖的提交
git cherry-pick b4a7b0f  # 先 cherry-pick 父提交
git cherry-pick baac796   # 再 cherry-pick 关键提交

# 如果有冲突，解决后继续
git cherry-pick --continue
```

**选项 2: Merge**
```bash
# 切换到目标分支
git checkout v2-python

# 合并救援分支
git merge rescue/baac796-key-access-enforcement

# 解决冲突（如果有）
# 然后提交
```

**选项 3: Rebase（谨慎使用）**
```bash
# 切换到救援分支
git checkout rescue/baac796-key-access-enforcement

# Rebase 到当前主线
git rebase v2-python

# 解决冲突后
git rebase --continue

# 然后 merge 回主线
git checkout v2-python
git merge rescue/baac796-key-access-enforcement
```

**建议**: 
- 如果只需要 `baac796` 的特定变更，使用 **cherry-pick**
- 如果需要完整保留 `baac796` 分支的历史，使用 **merge**
- 如果需要线性历史，使用 **rebase**（但要注意这会改写历史）

#### E4.3 关键文件恢复建议

被覆盖的提交包含以下重要内容，建议优先恢复：

1. **诊断文档**:
   - `OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md` (336 lines)
   - `YAML_DICT_USAGE_REVIEW.md` (679 lines)

2. **代码实现**:
   - `src/qmatsuite/presets/paramspace.py` (key access enforcement)
   - `tests/unit/test_key_access_enforcement.py` (267 lines)

3. **宪法更新**:
   - `CONSTITUTION_ZH.md` §10.8.9 章节

**恢复命令**:
```bash
# 查看特定文件
git show baac796:OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md > OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md
git show baac796:YAML_DICT_USAGE_REVIEW.md > YAML_DICT_USAGE_REVIEW.md

# 或直接 checkout 整个提交的文件
git checkout rescue/baac796-key-access-enforcement -- OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md
git checkout rescue/baac796-key-access-enforcement -- YAML_DICT_USAGE_REVIEW.md
```

---

## 附录：Git 命令执行记录

### 基础信息收集
```bash
git remote -v
git status
git branch -vv
git rev-parse --abbrev-ref HEAD
git branch -r
```

### Reflog 检查
```bash
git reflog show --date=iso origin/v2-python
git reflog --date=iso --all | grep -i "forced-update\|update by push\|push\|rebase\|reset"
```

### Dangling Commits 检查
```bash
git fsck --lost-found
```

### 提交分析
```bash
git show --stat baac796
git show -1 --pretty=fuller baac796
git log --oneline baac796 --not 31a4fe3
git log --oneline 31a4fe3 --not baac796
git merge-base baac796 31a4fe3
```

### 救援分支创建
```bash
git branch rescue/baac796-key-access-enforcement baac796
```

---

## 总结

**确认发生过一次 force push**，发生在 2026-01-04 10:39:54，将 `origin/v2-python` 从 `baac796` 强制更新到 `31a4fe3`。

**成功找回被覆盖的提交** `baac796`，包含重要的 ParamSpace key access enforcement 实现和相关诊断文档。

**已创建救援分支** `rescue/baac796-key-access-enforcement`，可以通过 cherry-pick、merge 或 rebase 的方式将内容拣回当前主线。

