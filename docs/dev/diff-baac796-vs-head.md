# baac796 vs HEAD 详细差异审计报告

**报告日期**: 2026-01-13  
**对比范围**: `baac796` (被覆盖的提交) vs `HEAD` (当前代码线)  
**目标**: 评估恢复 baac796 的设计与测试的风险与策略

---

## 1. 基线信息

### 1.1 当前状态

**当前所在分支**: `v2-python`  
**当前 HEAD SHA**: `9ef4b868620e59b2ee0cf557ba4b831f0e4d6f84`  
**origin/v2-python SHA**: `820f48696d4883b0905b9dce3bc07d3f00b255c0`  
**本地领先**: 4 commits

**Working tree 状态**: ⚠️ **不干净**
- 有未提交的修改（多个文件 modified）
- 有未跟踪的文件（docs/dev/, docs/reviews/ 等）
- **建议**: 在恢复操作前需要 `git stash` 或提交当前工作

### 1.2 被覆盖的提交信息

**baac796** (2026-01-01 16:52:04):
```
Implement key access enforcement for ParamSpace: Introduced a comprehensive key-access enforcement mechanism in accordance with Constitution 10.8.9, ensuring that each ParamSpace can only access its owned keys and preventing unauthorized access. Updated the ParamSpace class to register owned keys and validate ownership during operations. Enhanced error handling with KeyAccessError for violations. Adjusted related functions and tests to reflect these changes, ensuring compliance and stability across the application.
```

**b4a7b0f** (2026-01-01 10:48:42):
```
Merge ParamSpace Constitution into global framework: Introduced a comprehensive section on ParamSpace, detailing the Single-writer principle, unified responsibilities for Detect, Preset Apply, and Invariant Enforcement. Updated the application logic to enforce invariants unconditionally, ensuring compliance with the new rules for parameter overrides. Enhanced the handling of precision parameters and their context, including degauss enforcement. Updated tests to validate the new parameter handling rules and ensure stability across the application.
```

### 1.3 命令证据

```bash
$ git status
On branch v2-python
Your branch is ahead of 'origin/v2-python' by 4 commits.
Changes not staged for commit: (多个文件 modified)

$ git branch -vv
* v2-python 9ef4b86 [origin/v2-python: ahead 4] feat(execution): Add JobExecutor

$ git rev-parse HEAD
9ef4b868620e59b2ee0cf557ba4b831f0e4d6f84

$ git rev-parse origin/v2-python
820f48696d4883b0905b9dce3bc07d3f00b255c0
```

---

## 2. 文件级 diff 总览

### 2.1 差异统计

**总变更**: 66 commits 差异（baac796..HEAD）  
**文件变更统计** (presets 目录):
- `paramspace.py`: -807 lines (baac796 更大)
- `integration.py`: -389 lines (大幅简化)
- `variants_registry.py`: +143 lines
- `oracle.py`: -55 lines (文件被删除)
- `spaces_registry.py`: +111 lines

### 2.2 文件变更表格

| 文件路径 | 变更类型 | 是否核心 | 说明 |
|---------|---------|---------|------|
| **src/quantumvitas/presets/paramspace.py** | M | ✅ **是** | 删除了 key access enforcement 机制（~163 行），degauss 从 precision 移回 occupations_scheme |
| **src/quantumvitas/presets/integration.py** | M | ✅ **是** | 删除了 apply_invariants() 调用和 Oracle 使用，大幅简化 apply 逻辑 |
| **src/quantumvitas/presets/variants_registry.py** | M | ✅ **是** | 删除了 Oracle 使用，degauss 写入逻辑从 precision 移除 |
| **src/quantumvitas/presets/oracle.py** | D | ✅ **是** | **文件被删除** - Oracle 类完全移除 |
| **src/quantumvitas/presets/dimensions.py** | M | ⚠️ 部分 | 添加了 ConvergenceOption enum |
| **CONSTITUTION_ZH.md** | M | ✅ **是** | 删除了 §10.8.9 Key Access 规则章节 |
| **OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md** | D | ⚠️ 重要 | **文件被删除** - 诊断文档丢失 |
| **YAML_DICT_USAGE_REVIEW.md** | D | ⚠️ 重要 | **文件被删除** - YAML 使用审查文档丢失 |
| **tests/unit/test_key_access_enforcement.py** | D | ✅ **是** | **文件被删除** - 267 行测试丢失 |
| **tests/unit/test_paramspace_invariants.py** | D | ✅ **是** | **文件被删除** - 445 行测试丢失 |
| **tests/unit/test_detector_b.py** | M | ⚠️ 部分 | 修改了 degauss 相关测试断言 |
| **tests/unit/test_paramspace_contract.py** | M | ⚠️ 部分 | 修改了 NOT_APPLICABLE 测试 |
| **tests/integration/test_preset_broadcast.py** | M | ⚠️ 部分 | 修改了 degauss 写入断言 |

### 2.3 核心文件详细差异摘要

#### 2.3.1 src/quantumvitas/presets/paramspace.py

**关键变化** (baac796 → HEAD):

1. **删除了 key access enforcement 机制** (~163 行):
   - 删除了 `KeyAccessError` 异常类
   - 删除了 `ParamSpaceContext` 上下文管理器
   - 删除了 `register_paramspace()` 函数
   - 删除了 `check_key_access()` 函数
   - 删除了全局注册表 `_PARAMSPACE_REGISTRY`, `_KEY_OWNERSHIP`
   - 删除了 `ParamSpace.owned_keys()` 方法
   - `get_yaml_value()` 不再检查 key access
   - `match_profile()` 不再使用 `ParamSpaceContext`

2. **degauss 归属变化**:
   - **baac796**: degauss **不属于** occupations_scheme（注释明确说明 "owned by Precision"）
   - **HEAD**: degauss **属于** occupations_scheme（`key_degauss` 在 `build_occupations_scheme_paramspace()` 中定义）

3. **profile 名称变化**:
   - **baac796**: `SMEARING_GAUSSIAN` (无 degauss 值)
   - **HEAD**: `SMEARING_GAUSSIAN_0.02` (要求 degauss=0.02)

4. **precision ParamSpace**:
   - **baac796**: precision 包含 `key_degauss`，有 `apply_invariants()` 覆盖删除 degauss
   - **HEAD**: precision 不包含 degauss

**代码行数变化**:
- baac796: 1087 行
- HEAD: 940 行
- **差异**: -147 行（主要是 key access enforcement 代码）

#### 2.3.2 src/quantumvitas/presets/integration.py

**关键变化**:

1. **删除了 apply_invariants() 调用**:
   - **baac796**: 在 apply 后调用所有 ParamSpace 的 `apply_invariants()`
   - **HEAD**: 完全移除

2. **删除了 Oracle 使用**:
   - **baac796**: 创建 `Oracle(current_yaml_state)` 并传递给 `apply_invariants()`
   - **HEAD**: 无 Oracle

3. **简化了 apply 逻辑**:
   - **baac796**: 分阶段 apply（prerequisite → dependent），使用 Oracle
   - **HEAD**: 单阶段 apply，无顺序控制

**代码行数变化**:
- baac796: ~700+ 行（包含 apply_invariants 逻辑）
- HEAD: ~568 行
- **差异**: -132 行

#### 2.3.3 src/quantumvitas/presets/variants_registry.py

**关键变化**:

1. **删除了 Oracle 使用**:
   - **baac796**: `_compile_precision_patch_for_step()` 使用 `Oracle(step_yaml).degauss_applicability()` 检查
   - **HEAD**: 直接读取 `step_yaml.get("SYSTEM", {}).get("occupations")`

2. **degauss 写入逻辑**:
   - **baac796**: precision 写入 degauss（通过 Oracle 检查适用性）
   - **HEAD**: precision 不写入 degauss（degauss 属于 occupations_scheme）

3. **detect 逻辑**:
   - **baac796**: occupations_scheme detect 不读取 degauss（key access enforcement 阻止）
   - **HEAD**: occupations_scheme detect 读取 degauss（要求 degauss=0.02）

#### 2.3.4 src/quantumvitas/presets/oracle.py

**文件状态**: ❌ **被删除**

**baac796 中的内容** (55 行):
- `Oracle` 类：只读的语义前提查询
- `degauss_applicability()` 方法：检查 `SYSTEM.occupations == "smearing"`

**HEAD 中**: 文件不存在

#### 2.3.5 CONSTITUTION_ZH.md

**关键变化**:

1. **删除了 §10.8.9 章节** (~64 行):
   - 10.8.9.1: ParamSpace Detect/Compile/Apply Key Access 规则（强制）
   - 10.8.9.2: Key Ownership 唯一性规则（运行时强制）
   - 10.8.9.3: 非法行为的明确判定
   - 10.8.9.4: Rationale（设计依据）

2. **章节重新编号**:
   - 原 10.8.9 → 删除
   - 原 10.9 → 10.8
   - 原 10.10 → 10.9
   - 原 10.11 → 10.10
   - 原 10.12 → 10.11
   - 原 10.13 → 10.12
   - 原 10.14 → 10.13

#### 2.3.6 测试文件

**被删除的测试文件**:

1. **tests/unit/test_key_access_enforcement.py** (267 行):
   - 测试 key access enforcement 规则
   - 测试 illegal key access 抛出 `KeyAccessError`
   - 测试 occupation detect 不依赖 degauss
   - 测试 duplicate ownership 检测
   - 测试 Oracle 访问允许

2. **tests/unit/test_paramspace_invariants.py** (445 行):
   - 测试 `apply_invariants()` 无条件执行
   - 测试 degauss 删除（smearing → fixed）
   - 测试 precision CUSTOM 仍删除 degauss
   - 测试 Strategy A（不自动填充 degauss）
   - 测试 Oracle 读取最新 YAML 状态
   - 测试 apply 顺序（occupation before precision）

**修改的测试文件**:

1. **tests/unit/test_detector_b.py**:
   - `test_smearing_wrong_degauss`: 从 `CUSTOM` 改为 `SMEARING_GAUSSIAN`（不再检查 degauss）

2. **tests/unit/test_paramspace_contract.py**:
   - `test_not_applicable_strictness_fixed_degauss`: 从 `CUSTOM` 改为 `FIXED`（不再检查 degauss）

3. **tests/integration/test_preset_broadcast.py**:
   - 断言 degauss **不在**结果中（occupations_scheme 不写入 degauss）

---

## 3. 行为差异审计

### 3.1 key ownership / key access enforcement

#### 3.1.1 baac796 中的机制

**定义与 enforce**:

1. **owned_keys() 方法**:
   ```python
   def owned_keys(self) -> Set[Tuple[str, str]]:
       """Return the set of (section, key) tuples owned by this ParamSpace."""
       return {(key.section, key.key) for key in self.keys}
   ```

2. **全局注册表**:
   - `_PARAMSPACE_REGISTRY`: `Dict[str, Set[Tuple[str, str]]]` - 每个 ParamSpace 的 owned keys
   - `_KEY_OWNERSHIP`: `Dict[Tuple[str, str], str]` - 每个 key 的 owner
   - `register_paramspace()`: 注册 ParamSpace 并检查重复所有权

3. **运行时检查**:
   - `check_key_access(section, key, allow_oracle=False)`: 检查当前 ParamSpace 是否允许访问 key
   - `ParamSpaceContext`: 上下文管理器设置当前 ParamSpace
   - `get_yaml_value()`: 调用 `check_key_access()` 检查

4. **抛错类型**:
   - `KeyAccessError(RuntimeError)`: 当 ParamSpace 访问非 owned key 时抛出

**入口函数**:
- `get_yaml_value()`: 在读取 YAML 时检查
- `match_profile()`: 在匹配时使用 `ParamSpaceContext`
- `compile_profile_patch()`: 在编译时使用 `ParamSpaceContext`

#### 3.1.2 HEAD 中的状态

**结论**: ❌ **完全缺失**

**证据**:
- 无 `KeyAccessError` 类
- 无 `ParamSpaceContext` 类
- 无 `register_paramspace()` 函数
- 无 `check_key_access()` 函数
- 无全局注册表
- `get_yaml_value()` 不检查 key access
- `match_profile()` 不使用 context

**替代机制**: ⚠️ **只有约定**
- `DIMENSION_OWNED_KEYS` (integration.py:307) 已标记 `DEPRECATED`
- 注释说明："This is no longer used for deletion decisions"
- 仅用于 UI 显示

#### 3.1.3 对 preset 可逆性的影响

**baac796**:
- ✅ **强保证**: key access enforcement 确保每个 ParamSpace 只能访问自己的 keys
- ✅ **可逆性**: 由于隔离，detect 和 compile 不会相互干扰
- ✅ **对称性**: 如果 ParamSpace A 不能读取 ParamSpace B 的 keys，则 detect 和 compile 行为对称

**HEAD**:
- ⚠️ **弱保证**: 只有约定，无运行时检查
- ⚠️ **可逆性风险**: 如果不同 ParamSpace 读取相同 key，可能导致 detect/compile 不对称
- ⚠️ **实际影响**: occupations_scheme 读取 degauss，precision 也写入 degauss，存在隐式耦合

**结论**: HEAD 中 key access enforcement 的缺失**降低了可逆性的保证强度**，但当前实现（degauss 属于 occupations_scheme）仍然可以工作，只是失去了架构层面的隔离保证。

### 3.2 occupation-smearing 与 degauss 的依赖处理

#### 3.2.1 baac796 中的设计

**degauss 归属**: ✅ **属于 precision ParamSpace**

**证据**:
- `build_precision_paramspace()` 包含 `key_degauss`
- `build_occupations_scheme_paramspace()` **不包含** `key_degauss`（注释明确说明 "owned by Precision"）
- precision 的 `apply_invariants()` 删除 degauss（当不适用时）

**依赖处理**:
- **Oracle 机制**: precision 使用 `Oracle(step_yaml).degauss_applicability()` 检查是否写入 degauss
- **apply 顺序**: 分阶段执行（prerequisite → dependent），确保 Oracle 读取最新 YAML 状态
- **occupations_scheme detect**: **不读取** degauss（key access enforcement 阻止）

**OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md 要点** (总结):
- **问题**: 当 precision = LOW/HIGH (degauss = 0.01/0.03) 时，occupation 检测为 CUSTOM
- **根因**: occupations_scheme ParamSpace 只有一个 profile `SMEARING_GAUSSIAN_0.02`，要求 degauss=0.02
- **解决方案**: baac796 将 degauss 移出 occupations_scheme，occupation detect 不再读取 degauss
- **耦合类型**: 间接耦合（通过共享 YAML 状态），但通过 key access enforcement 隔离

#### 3.2.2 HEAD 中的设计

**degauss 归属**: ⚠️ **属于 occupations_scheme ParamSpace**

**证据**:
- `build_occupations_scheme_paramspace()` 包含 `key_degauss`
- profile `SMEARING_GAUSSIAN_0.02` 要求 `degauss = 0.02`
- precision ParamSpace 不包含 degauss

**依赖处理**:
- **无 Oracle**: precision 直接读取 `step_yaml.get("SYSTEM", {}).get("occupations")`
- **无 apply 顺序控制**: 按字典迭代顺序（不确定）
- **occupations_scheme detect**: **读取** degauss（要求 degauss=0.02）

**问题**:
- 当 precision 写入 degauss=0.01 或 0.03 时，occupation detect 失败（因为 profile 要求 0.02）
- 这导致 occupation 变为 CUSTOM，即使 smearing 是活跃的

#### 3.2.3 两者差异对"编译顺序/两阶段/oracle"的影响

**baac796**:
- ✅ **有 Oracle**: 提供 `degauss_applicability()` 查询
- ✅ **有 apply 顺序**: 分阶段执行（prerequisite → dependent）
- ⚠️ **无两阶段编译**: 仍然是单阶段，但通过顺序保证 Oracle 读取最新状态

**HEAD**:
- ❌ **无 Oracle**: 直接读取 YAML
- ❌ **无编译顺序控制**: 按字典迭代
- ❌ **无两阶段编译**: 单阶段

**对"两阶段编译"的需求**:
- **baac796**: 不需要严格的两阶段编译，因为通过 apply 顺序（prerequisite → dependent）已经保证 Oracle 读取最新状态
- **HEAD**: 也不需要两阶段编译，因为 degauss 属于 occupations_scheme，precision 不写入 degauss

**对"oracle"的需求**:
- **baac796**: **需要 Oracle** - precision 需要检查 degauss 是否适用，但不能直接读取 occupations（key access enforcement 阻止）
- **HEAD**: **不需要 Oracle** - precision 不写入 degauss，直接读取 occupations 无问题（无 key access enforcement）

**结论**: baac796 的设计**需要 Oracle 和 apply 顺序**来保证 precision 可以安全地写入 degauss，而 HEAD 的设计**不需要这些机制**，因为 degauss 属于 occupations_scheme。

### 3.3 match_profile/custom 的严格规则

#### 3.3.1 baac796 中的规则

**match_profile 算法**:
- 使用 `ParamSpaceContext` 设置当前 ParamSpace
- 在 `get_yaml_value()` 时检查 key access
- 如果访问非 owned key，抛出 `KeyAccessError`

**custom 判定**:
- 如果 `match_profile()` 返回 `None` → `CUSTOM`
- occupations_scheme detect **不读取** degauss（key access enforcement 阻止）
- 因此，occupation detect 只检查 `occupations` 和 `smearing`，不检查 `degauss`

**锁定粒度**:
- 每个 ParamSpace 只能访问自己的 keys
- 通过 `ParamSpaceContext` 在运行时 enforce

#### 3.3.2 HEAD 中的规则

**match_profile 算法**:
- 不使用 context，直接读取 YAML
- 无 key access 检查

**custom 判定**:
- 如果 `match_profile()` 返回 `None` → `CUSTOM`
- occupations_scheme detect **读取** degauss（要求 degauss=0.02）
- 如果 degauss != 0.02，detect 失败 → `CUSTOM`

**锁定粒度**:
- 无运行时 enforce，只有约定

#### 3.3.3 兼容性风险

**恢复 enforcement 的风险**:

1. **现有 preset 更容易变 custom**:
   - 如果现有 YAML 中有跨 dimension 的 key 访问，恢复 enforcement 会导致 `KeyAccessError`
   - 例如：如果某个 ParamSpace 在 detect 时读取了非 owned key，恢复后会失败

2. **测试兼容性**:
   - 现有测试可能假设无 key access enforcement
   - 恢复后需要更新测试以使用 `ParamSpaceContext`

3. **degauss 归属冲突**:
   - HEAD 中 degauss 属于 occupations_scheme
   - baac796 中 degauss 属于 precision
   - 恢复时需要决定归属，可能导致现有 YAML 不兼容

**结论**: ⚠️ **存在兼容性风险**，但可以通过以下方式缓解：
- 先恢复测试作为 guardrail
- 逐步恢复 enforcement（先 warning，后 error）
- 明确 degauss 归属决策

### 3.4 tests

#### 3.4.1 baac796 新增/修改的测试

**新增测试文件**:

1. **test_key_access_enforcement.py** (267 行):
   - `test_illegal_key_access_raises_error`: 测试非法访问抛出 `KeyAccessError`
   - `test_occupation_detect_no_degauss_dependency`: 测试 occupation detect 不依赖 degauss
   - `test_occupation_detect_without_degauss`: 测试 occupation detect 在 degauss 缺失时仍工作
   - `test_precision_uses_oracle_for_occupations`: 测试 precision 使用 Oracle
   - `test_duplicate_ownership_fails_immediately`: 测试重复所有权检测
   - `test_owned_keys_access_allowed`: 测试 owned keys 访问允许
   - `test_foreign_key_access_raises_error`: 测试 foreign key 访问抛出错误
   - `test_oracle_access_allowed`: 测试 Oracle 访问允许
   - `test_no_context_allows_access`: 测试无 context 时允许访问（向后兼容）
   - `test_degauss_owned_by_precision`: 测试 degauss 属于 precision
   - `test_degauss_not_owned_by_occupations`: 测试 degauss 不属于 occupations

2. **test_paramspace_invariants.py** (445 行):
   - `test_a1_smearing_to_fixed_deletes_degauss`: 测试 smearing → fixed 删除 degauss
   - `test_a2_precision_custom_still_deletes_degauss`: 测试 precision CUSTOM 仍删除 degauss
   - `test_b1_smearing_plus_precision_preset_writes_degauss`: 测试 smearing + precision preset 写入 degauss
   - `test_b2_smearing_no_precision_apply_does_not_auto_fill`: 测试 Strategy A（不自动填充）
   - `test_c1_smearing_missing_degauss_detect_custom`: 测试 detect 行为（已修改）
   - `test_c2_fixed_plus_degauss_present_detect_custom`: 测试 detect 行为（已修改）
   - `test_d1_oracle_reads_updated_yaml_not_stale_state`: 测试 Oracle 读取最新状态
   - `test_d2_apply_order_occupation_before_precision`: 测试 apply 顺序

**修改的测试**:
- `test_detector_b.py`: 修改了 degauss 相关断言
- `test_paramspace_contract.py`: 修改了 NOT_APPLICABLE 测试
- `test_preset_integration.py`: 修改了 degauss 写入断言

#### 3.4.2 HEAD 中的测试覆盖

**丢失的测试**:
- ❌ `test_key_access_enforcement.py`: 完全丢失
- ❌ `test_paramspace_invariants.py`: 完全丢失

**修改的测试**:
- ⚠️ `test_detector_b.py`: 断言已修改（不再检查 degauss）
- ⚠️ `test_paramspace_contract.py`: 断言已修改（不再检查 degauss）

**覆盖的 invariants**:
- ✅ Profile 互斥性: 仍有测试（`test_paramspace_contract.py`）
- ✅ NOT_APPLICABLE presence/absence: 仍有测试（但断言已修改）
- ❌ Custom 判定: 无专门测试
- ❌ 编译顺序依赖: 无测试
- ❌ Key access enforcement: 无测试
- ❌ Invariant enforcement: 无测试

#### 3.4.3 优先恢复的测试

**作为 guardrail，应优先恢复**:

1. **test_key_access_enforcement.py** (高优先级):
   - 验证 key access enforcement 机制
   - 验证 degauss 归属（precision vs occupations_scheme）
   - 验证 Oracle 访问允许

2. **test_paramspace_invariants.py** (高优先级):
   - 验证 `apply_invariants()` 无条件执行
   - 验证 degauss 删除逻辑
   - 验证 apply 顺序

3. **test_detector_b.py 的 degauss 相关测试** (中优先级):
   - 恢复对 degauss 的检查（如果恢复 baac796 设计）

---

## 4. 恢复策略建议（可执行）

### 4.1 Path A（推荐）：在新分支上 cherry-pick b4a7b0f + baac796，解决冲突，跑测试

**步骤**:

```bash
# 1. 创建恢复分支
git checkout -b restore-key-access-enforcement

# 2. Cherry-pick 父提交
git cherry-pick b4a7b0f

# 3. Cherry-pick 关键提交
git cherry-pick baac796

# 4. 解决冲突（预期冲突文件见下）
# 5. 运行测试
pytest tests/unit/test_key_access_enforcement.py tests/unit/test_paramspace_invariants.py -v
```

**预期冲突文件**:

1. **src/quantumvitas/presets/paramspace.py** (高冲突风险):
   - **冲突点**: 
     - key access enforcement 代码（baac796 有，HEAD 无）
     - degauss 归属（baac796: precision, HEAD: occupations_scheme）
     - profile 名称（baac796: `SMEARING_GAUSSIAN`, HEAD: `SMEARING_GAUSSIAN_0.02`）
   - **解决策略**: 
     - 保留 baac796 的 key access enforcement 代码
     - 决定 degauss 归属（建议：precision，符合 baac796 设计）
     - 更新 profile 名称映射

2. **src/quantumvitas/presets/integration.py** (高冲突风险):
   - **冲突点**: 
     - `apply_invariants()` 调用（baac796 有，HEAD 无）
     - Oracle 使用（baac796 有，HEAD 无）
     - apply 顺序（baac796: 分阶段，HEAD: 单阶段）
   - **解决策略**: 
     - 恢复 `apply_invariants()` 调用
     - 恢复 Oracle 使用
     - 恢复分阶段 apply 顺序

3. **src/quantumvitas/presets/variants_registry.py** (中冲突风险):
   - **冲突点**: 
     - Oracle 使用（baac796 有，HEAD 无）
     - degauss 写入逻辑（baac796: precision 写入，HEAD: 不写入）
   - **解决策略**: 
     - 恢复 Oracle 使用
     - 恢复 precision 写入 degauss 的逻辑

4. **CONSTITUTION_ZH.md** (低冲突风险):
   - **冲突点**: 
     - §10.8.9 章节（baac796 有，HEAD 无）
     - 章节编号（baac796: 10.8.9, HEAD: 10.8 是其他内容）
   - **解决策略**: 
     - 恢复 §10.8.9 章节
     - 调整章节编号

5. **tests/** (中冲突风险):
   - **冲突点**: 
     - 测试文件存在性（baac796 有，HEAD 无）
     - 测试断言（baac796 和 HEAD 不同）
   - **解决策略**: 
     - 恢复测试文件
     - 更新断言以匹配 baac796 设计

**风险点**:

1. **SSOT**: 
   - degauss 归属冲突（precision vs occupations_scheme）
   - 需要明确决策：恢复 baac796 设计（precision）还是保持 HEAD（occupations_scheme）

2. **Step 类型**: 
   - `applies_to_step_types` 可能不同
   - 需要检查是否有新增 step 类型

3. **IR mapping**: 
   - baac796 可能使用 IR keys，HEAD 可能使用 QE keys
   - 需要检查 IR↔QE 映射兼容性

4. **现有 refactor 影响**: 
   - HEAD 可能有其他 refactor（如 StepDoc、ULID-only 等）
   - 需要确保 key access enforcement 与这些 refactor 兼容

**验收测试清单**:

```bash
# 1. Key access enforcement 测试
pytest tests/unit/test_key_access_enforcement.py -v

# 2. Invariant enforcement 测试
pytest tests/unit/test_paramspace_invariants.py -v

# 3. ParamSpace 契约测试
pytest tests/unit/test_paramspace_contract.py -v

# 4. Detector 测试
pytest tests/unit/test_detector_b.py -v

# 5. Preset integration 测试
pytest tests/integration/test_preset_broadcast.py -v
pytest tests/unit/test_preset_integration.py -v

# 6. 完整 preset 系统测试
pytest tests/unit/test_paramspace*.py tests/integration/test_preset*.py -v
```

### 4.2 Path B：只 cherry-pick tests/diagnostic doc，先恢复 guardrail 再恢复 enforcement

**步骤**:

```bash
# 1. 创建恢复分支
git checkout -b restore-tests-first

# 2. 只恢复测试文件（不恢复代码）
git checkout baac796 -- tests/unit/test_key_access_enforcement.py
git checkout baac796 -- tests/unit/test_paramspace_invariants.py

# 3. 恢复诊断文档
git checkout baac796 -- OCCUPATION_DEGAUSS_DEPENDENCY_DIAGNOSTIC.md
git checkout baac796 -- YAML_DICT_USAGE_REVIEW.md

# 4. 修改测试以适配当前代码（临时）
# - 注释掉 key access enforcement 相关测试
# - 保留 invariant enforcement 测试框架

# 5. 运行测试（应该失败，但作为 guardrail）
pytest tests/unit/test_key_access_enforcement.py tests/unit/test_paramspace_invariants.py -v

# 6. 逐步恢复 enforcement 代码，使测试通过
```

**预期冲突**: 低（只恢复测试文件）

**风险点**:
- 测试可能无法运行（依赖的代码不存在）
- 需要临时修改测试以适配当前代码

**验收测试清单**:
- 同 Path A，但测试可能暂时失败

### 4.3 Path C：手工移植（不推荐）——只在冲突极大时备用

**步骤**:
1. 手动复制 baac796 中的关键代码片段
2. 手动适配到 HEAD 的代码结构
3. 逐步测试

**预期冲突**: 极高（需要大量手工工作）

**风险点**:
- 容易遗漏关键逻辑
- 难以保证完整性
- 维护成本高

**验收测试清单**:
- 同 Path A

---

## 5. 输出补丁附件

**补丁文件路径**:
- `/tmp/baac796.patch` (107KB) - baac796 提交的完整补丁
- `/tmp/b4a7b0f.patch` (90KB) - b4a7b0f 提交的完整补丁

**查看补丁**:
```bash
# 查看 baac796 补丁
cat /tmp/baac796.patch | less

# 查看 b4a7b0f 补丁
cat /tmp/b4a7b0f.patch | less

# 应用补丁（仅用于阅读，不要实际应用）
git apply --check /tmp/baac796.patch  # 检查是否可以应用
```

---

## 6. 最后一句话总结

**恢复 baac796 的最小风险路径是 Path A（在新分支上 cherry-pick）；主要冲突点在 `paramspace.py`（key access enforcement 代码和 degauss 归属）和 `integration.py`（apply_invariants 和 Oracle 使用）；最关键需要先保住的 invariant tests 是 `test_key_access_enforcement.py` 和 `test_paramspace_invariants.py`，它们验证了 key access enforcement 机制和 invariant enforcement 行为，是恢复设计的 guardrail。**

