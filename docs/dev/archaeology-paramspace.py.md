# ParamSpace Git 考古报告

**文件**: `src/quantumvitas/presets/paramspace.py`  
**报告日期**: 2026-01-10  
**考古范围**: 仅限 `paramspace.py` 文件本身，不涉及其他文件

---

## 1. 当前版本 paramspace.py 行为摘要（基线）

基于当前文件内容，核心职责与规则如下：

### 核心数据结构

- **`CellType` (Enum)**: 定义三种 cell 类型：`VALUE`, `NOT_APPLICABLE`, `WILDCARD`
- **`Cell` (dataclass)**: 不可变的 cell 对象，包含 `cell_type` 和可选的 `value`
- **`ParamKey` (dataclass)**: 参数定义，包含：
  - `section`: YAML section 名称（如 "SYSTEM", "ELECTRONS", "cards"）
  - `key`: IR 参数 key 名称（概念上为 IR，v0 中与 QE key 相同）
  - `parser`: 解析函数（str -> Any）
  - `canonicalizer`: 规范化函数（Any -> Any）
  - `tolerance`: 数值比较的绝对容差（可选）
  - `aliases`: 别名映射（frozenset of tuples）
  - `default`: 默认值（可选）
  - 方法：`canonicalize()`, `matches()`
- **`ParamSpace` (dataclass)**: 预设维度的声明，包含：
  - `name`: 维度名称
  - `keys`: 有序的 `ParamKey` 列表
  - `profiles`: 完整的 profile 矩阵（profile_name -> dict[ParamKey, Cell]）
  - `__post_init__()`: 验证 profile 形成完整矩阵，自动填充缺失 cell 为 WILDCARD

### 核心算法

- **`get_yaml_value()`**: 从 YAML tree 获取值，返回 `(present: bool, raw_value: Any)`，支持大小写不敏感查找
- **`compute_effective_value()`**: 计算有效值（考虑 present、raw_value、default、canonicalizer）
- **`match_profile()`**: 通用匹配逻辑
  - `VALUE`: 比较 `effective_value` 与规范化后的期望值
  - `NOT_APPLICABLE`: 要求 `present == False`
  - `WILDCARD`: 忽略（不检查）
  - 如果多个 profile 匹配，抛出 `ValueError`（设计错误）
- **`compile_profile_patch()`**: 通用编译逻辑
  - `VALUE`: 根据 `explicit_defaults` 决定是否写入（如果 `explicit_defaults=False` 且值等于 default，则跳过）
  - `NOT_APPLICABLE`: 总是删除
  - `WILDCARD`: 不做任何操作
  - 返回 `(patch_dict, deletions_set)`

### 关键规则

- **完整矩阵约束**: 每个 profile 必须为所有 keys 定义 cell（缺失自动填充为 WILDCARD，但不鼓励）
- **互斥性约束**: `match_profile()` 要求 profiles 必须互斥（多个匹配视为设计错误）
- **present vs effective_value 区分**: YAML 访问明确区分 key 是否存在（present）和有效值（effective_value = present ? raw_value : default）
- **IR key 概念**: `ParamKey.key` 在概念上是 IR key，但 v0 中与 QE key 相同；IR↔QE 转换发生在 YAML I/O 边界（在 `spaces_registry/variants_registry` 中）

### 编译/应用顺序

**此文件内无法证明编译顺序**。`compile_profile_patch()` 只处理单个 profile 的编译，不涉及多个 dimension 的编译顺序。编译顺序应在调用方（如 `variants_registry.py` 或 `integration.py`）中定义。

### 内置 ParamSpace 定义

- `build_occupations_scheme_paramspace()`: occupations_scheme 维度（keys: occupations, smearing, degauss）
- `build_magnetism_paramspace()`: magnetism 维度（keys: nspin, noncolin, lspinorb）
- `build_precision_paramspace()`: precision 维度（keys: ecutwfc, ecutrho, conv_thr, K_POINTS），使用特殊匹配函数 `match_precision_profile()`
- `build_convergence_paramspace()`: convergence 维度（keys: mixing_beta, electron_maxstep, mixing_mode, mixing_ndim, diagonalization）

---

## 2. 时间线：关键语义变更的提交列表

| Commit Hash | 日期 | 作者 | 提交信息 | 变更类型 | 对行为的影响 |
|------------|------|------|---------|---------|------------|
| `616d837` | 2025-12-31 | quantumNerd | Refactor preset handling and enhance UI integration | **Refactor** (文件创建) | **初始创建**：引入完整的 ParamSpace 框架，包括 `CellType`, `Cell`, `ParamKey`, `ParamSpace` 类，以及 `match_profile()` 和 `compile_profile_patch()` 通用算法。定义了 occupations_scheme、magnetism、precision 三个维度的 ParamSpace。所有核心逻辑在此提交中一次性建立。 |
| `94cedee` | 2026-01-01 | QuantumNerd | Enhance YAML Document Handling and Introduce Convergence Dimension | **Refactor** (功能扩展) | **添加新维度**：新增 `build_convergence_paramspace()` 函数和 `get_convergence_paramspace()` 单例，添加了 convergence 维度的完整定义。**不改变核心逻辑**，只是扩展了维度数量。 |
| `5c1993d` | 2026-01-10 | QuantumNerd | feat(ir): Update IR implementation plan and enhance parameter handling | **Refactor** (文档更新) | **文档注释更新**：更新了 `ParamKey` 类的 docstring，明确说明 `key` 字段是 IR key（概念上），但 v0 中与 QE key 相同。**不改变任何代码逻辑**，只是澄清了设计意图。 |

### 关键语义变更定义检查

根据定义，关键语义变更应影响：
- ✅ **Preset 可逆性**: 无变更（所有提交都保持相同的 match/compile 逻辑）
- ✅ **匹配/自定义判定**: 无变更（`match_profile()` 逻辑从未修改）
- ✅ **Key 归属/约束**: 无变更（`ParamKey` 结构从未修改）
- ✅ **Profile 定义方式**: 无变更（`Cell` 和 profile 矩阵结构从未修改）
- ✅ **Presence/NA 语义**: 无变更（`NOT_APPLICABLE` 的语义从未修改）
- ✅ **Step 适用域处理**: 无变更（此文件不涉及 step 适用域，由 `variants_registry.py` 处理）

**结论**: **未发现关键语义变更**。所有提交都是功能扩展（添加新维度）或文档更新，核心算法和数据结构保持稳定。

---

## 3. 重点深挖：最可能导致"腐化/范式变更"的提交

### 3.1 Commit `616d837` (2025-12-31) - 文件初始创建

**Diff 摘要**:
- 文件从无到有，一次性添加 823 行代码
- 包含完整的框架：`CellType`, `Cell`, `ParamKey`, `ParamSpace` 类
- 包含核心算法：`match_profile()`, `compile_profile_patch()`
- 包含 YAML 访问器：`get_yaml_value()`, `compute_effective_value()`
- 包含三个维度的 ParamSpace 定义：occupations_scheme, magnetism, precision
- 包含辅助函数：parser/canonicalizer 函数

**具体改变了什么规则**:
- **无**：这是文件的初始创建，不存在"改变"的概念。所有规则在此提交中一次性建立。

**判断意图**:
- ✅ **看起来是故意迁移/重构**：
  - Commit message 明确说明 "Refactor preset handling"
  - 代码结构清晰，遵循 Constitution Chapter 10.7 的设计原则
  - 有完整的 docstring 和类型注解
  - 一次性建立完整框架，而非渐进式修改
- ❌ **不是意外/merge 覆盖**：
  - 这是文件创建，不是 merge
  - 没有冲突标记
  - 代码结构完整，没有临时 hack 痕迹

**结论**: 这是**有意的设计迁移**，从旧的 per-dimension 特殊逻辑迁移到通用的 ParamSpace 框架。这是**设计范式的一次性建立**，而非腐化。

### 3.2 Commit `94cedee` (2026-01-01) - 添加 Convergence 维度

**Diff 摘要**:
- 在文件末尾添加 114 行代码
- 新增 `build_convergence_paramspace()` 函数
- 新增 `get_convergence_paramspace()` 单例函数
- 定义了 5 个 keys 和 4 个 profiles（FAST, NORMAL, ROBUST, VERY_ROBUST）

**具体改变了什么规则**:
- **无**：只是添加了新的维度定义，不改变任何现有逻辑。所有核心算法（`match_profile()`, `compile_profile_patch()`）保持不变。

**判断意图**:
- ✅ **看起来是故意功能扩展**：
  - Commit message 明确说明 "Introduce Convergence Dimension"
  - 遵循了与现有维度相同的模式
  - 没有修改任何核心逻辑
- ❌ **不是意外/merge 覆盖**：
  - 这是纯添加，不是替换
  - 没有冲突标记
  - 代码风格与现有代码一致

**结论**: 这是**有意的功能扩展**，添加新维度以支持更多预设选项。**不涉及范式变更**。

### 3.3 Commit `5c1993d` (2026-01-10) - IR key 注释更新

**Diff 摘要**:
- 仅修改了 `ParamKey` 类的 docstring（7 行变更，5 行新增，2 行删除）
- 明确说明 `key` 字段是 IR key（概念上），但 v0 中与 QE key 相同
- 添加了关于 IR↔QE 转换发生在 YAML I/O 边界的说明

**具体改变了什么规则**:
- **无**：只更新了文档，不改变任何代码逻辑。

**判断意图**:
- ✅ **看起来是故意文档澄清**：
  - Commit message 说明 "enhance parameter handling" 和 "ensure IR keys are conceptually aligned"
  - 这是为 IR 框架落地做准备，澄清设计意图
- ❌ **不是意外/merge 覆盖**：
  - 只修改了注释，没有代码变更
  - 没有冲突标记

**结论**: 这是**有意的文档更新**，为 IR 框架落地做准备。**不涉及任何行为变更**。

---

## 4. Merge/覆盖风险审计

### 4.1 Merge Commits 检查

**结果**: **未发现任何 merge commits**。

```bash
git log --merges --oneline -- src/quantumvitas/presets/paramspace.py
# 输出为空
```

### 4.2 覆盖风险分析

**所有提交都是线性提交**（无分支合并）：
- `616d837` → `94cedee` → `5c1993d`

**每个提交的 diff 特征**：
- `616d837`: 文件创建（`new file mode 100644`），无冲突标记
- `94cedee`: 纯添加（`+114` 行），无冲突标记
- `5c1993d`: 仅文档更新（`+5 -2` 行），无冲突标记

**结论**: **无 merge 覆盖风险**。所有提交都是干净的线性提交，没有冲突解决痕迹，没有大段替换。

---

## 5. 结论与建议

### 5.1 考古发现总结

**核心发现**: **未发现任何"范式变更"或"腐化"的证据**。

1. **文件历史极短**: 文件仅存在 3 个提交（2025-12-31 至 2026-01-10），所有提交都是同一作者（quantumNerd/QuantumNerd）。
2. **核心逻辑稳定**: 所有核心算法（`match_profile()`, `compile_profile_patch()`）在第一个提交（`616d837`）中一次性建立，之后**从未修改**。
3. **无语义变更**: 所有后续提交都是功能扩展（添加新维度）或文档更新，不改变任何行为。
4. **无 merge 风险**: 没有 merge commits，所有提交都是线性提交，无冲突解决痕迹。

### 5.2 三种可能路径的建议

#### A) "这是设计迁移，不算腐化" ✅ **最可能**

**证据**:
- 文件从创建开始就遵循了当前的设计范式（Constitution Chapter 10.7）
- 所有核心逻辑在第一个提交中一次性建立，结构清晰
- 后续提交都是功能扩展，不改变核心逻辑

**建议**（如果接受当前范式）:
1. **补充约束/测试**:
   - 添加测试确保 `match_profile()` 的互斥性约束（多个 profile 匹配应抛出异常）
   - 添加测试确保 `compile_profile_patch()` 的 `explicit_defaults` 行为
   - 添加测试确保 `NOT_APPLICABLE` 的正确删除行为
   - 添加测试确保 profile 矩阵的完整性验证
2. **文档完善**:
   - 明确说明 IR key 与 QE key 的关系（v0 中相同，未来可能不同）
   - 明确说明 IR↔QE 转换的边界（在 `variants_registry.py` 中）
3. **Key 归属约束**:
   - 当前没有全局 enforce key 单归属，建议在 `variants_registry.py` 中添加全局 key 归属检查
   - 或添加测试确保不同 dimension 的 ParamSpace 不共享 keys

#### B) "这是无意破坏/merge 覆盖" ❌ **不可能**

**证据**:
- 没有 merge commits
- 所有提交都是线性提交
- 没有冲突解决痕迹
- 代码结构完整，无临时 hack

**结论**: **此路径不适用**。没有证据支持"无意破坏"或"merge 覆盖"的假设。

#### C) "仅凭 paramspace.py 不足以判定" ⚠️ **部分适用**

**限制**:
- 此文件只包含**声明式数据结构**和**通用算法**
- **编译顺序**在此文件中不可见（应在 `variants_registry.py` 或 `integration.py` 中）
- **Key 归属约束**在此文件中不可见（应在 `variants_registry.py` 中）
- **Step 适用域**在此文件中不可见（应在 `variants_registry.py` 中）

**下一步必须检查的文件/线索**（最多 5 条）:
1. **`src/quantumvitas/presets/variants_registry.py`**:
   - 检查 `(step_type, dimension)` 单归属的 enforce 逻辑
   - 检查编译顺序（dimension 遍历顺序）
   - 检查 key 归属的全局约束（如果存在）
2. **`src/quantumvitas/presets/integration.py`**:
   - 检查 `apply_presets_to_step()` 的编译顺序
   - 检查 `DIMENSION_OWNED_KEYS` 的维护历史（是否被废弃）
3. **`src/quantumvitas/presets/spaces_registry.py`**（如果存在）:
   - 检查 ParamSpace 的注册逻辑
   - 检查是否有 key 归属的全局注册表
4. **测试文件**（如 `tests/unit/test_presets*.py`）:
   - 检查是否有测试覆盖 key 归属约束
   - 检查是否有测试覆盖编译顺序
5. **Git 历史中的其他相关文件**:
   - 检查是否有旧的 preset 处理逻辑被删除或替换
   - 检查 `616d837` 提交中是否有其他文件的重构（可能揭示迁移路径）

---

## 6. 一句话总结

**最可能的范式/语义变更发生在 commit `616d837`（2025-12-31，quantumNerd），它建立了完整的 ParamSpace 框架（从无到有）；是否像 merge 覆盖：否，理由是这是文件的初始创建，所有核心逻辑一次性建立，结构清晰，无冲突标记，后续提交都是功能扩展或文档更新，核心算法从未修改。**

---

## 附录：Git 命令执行记录

### 文件历史
```bash
git log --follow --date=short --pretty=format:"%h %ad %an %s" -- src/quantumvitas/presets/paramspace.py
```
输出：
```
5c1993d 2026-01-10 QuantumNerd feat(ir): Update IR implementation plan and enhance parameter handling
94cedee 2026-01-01 QuantumNerd Enhance YAML Document Handling and Introduce Convergence Dimension
616d837 2025-12-31 quantumNerd Refactor preset handling and enhance UI integration
```

### Merge Commits 检查
```bash
git log --merges --oneline -- src/quantumvitas/presets/paramspace.py
```
输出：**空**（无 merge commits）

### 文件创建检查
```bash
git log --all --diff-filter=A --oneline -- src/quantumvitas/presets/paramspace.py
```
输出：
```
616d837 Refactor preset handling and enhance UI integration
```

### 关键函数 Blame
```bash
git blame -L 241,310 -n src/quantumvitas/presets/paramspace.py
```
结果：`match_profile()` 函数的所有行都来自 `616d837`（初始创建）

```bash
git blame -L 316,377 -n src/quantumvitas/presets/paramspace.py
```
结果：`compile_profile_patch()` 函数的所有行都来自 `616d837`（初始创建）

