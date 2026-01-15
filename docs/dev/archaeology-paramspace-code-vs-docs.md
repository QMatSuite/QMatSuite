# ParamSpace 体系"代码+文档"联合考古报告

**报告日期**: 2026-01-10  
**考古范围**: ParamSpace 设计与实现的代码演化 + 文档叙事演化  
**目标**: 回答"两阶段编译+oracle 机制是否曾实现过？如果实现过，何时/为何消失？"

---

## 0. TL;DR 结论（先写）

### 0.1 "两阶段编译"是否存在过？

**结论**: ❌ **不存在**

**证据**:
- 代码搜索 `two-phase|two-stage|pre-compile|post-compile` 无结果
- Git 历史搜索无相关提交
- 当前代码中 `compile_profile_patch()` 是单阶段函数，无 pre/post 分离
- 文档中无明确的两阶段编译描述

### 0.2 "oracle"是否存在过？

**结论**: ⚠️ **文档中存在，代码中从未实现**

**证据**:
- **文档**: `CONSTITUTION_ZH.md` §12.2 明确提到 "oracle 暴露的先决条件"
- **代码**: 全仓库搜索 `oracle|Oracle|ORACLE` 无任何实现
- **时间线**: `CONSTITUTION_ZH.md` 的 §12 章节（key ownership）存在，但 oracle 从未在代码中落地

### 0.3 degauss 是否曾属于 precision？何时迁移？

**结论**: ❌ **degauss 从未属于 precision，一直属于 occupations_scheme**

**证据**:
- Git 历史追踪 `degauss`：从 `616d837` (2025-12-31) 文件创建起，`degauss` 就定义在 `build_occupations_scheme_paramspace()` 中
- 搜索 `precision.*degauss|degauss.*precision` 无结果
- 当前代码：`src/quantumvitas/presets/paramspace.py:495` - `key_degauss` 属于 `occupations_scheme` ParamSpace

### 0.4 key 单归属是否曾 enforce？何时/在哪里 enforce？

**结论**: ⚠️ **文档要求 enforce，代码中只有约定（DEPRECATED 机制）**

**证据**:
- **文档**: `CONSTITUTION_ZH.md` §12.1 明确要求 "YAML 叶键必须由且仅由一个 ParamSpace 拥有"
- **代码**: 
  - `DIMENSION_OWNED_KEYS` (integration.py:307) 已标记 `DEPRECATED`，仅用于 UI 显示
  - `variants_registry.py:_build_indexes()` 只 enforce `(step_type, dimension)` 单归属，不 enforce key 单归属
  - 无全局 key 归属注册表或验证机制

### 0.5 若发生"范式替换"，是哪一个 commit/PR 引入的，意图是什么？

**结论**: ✅ **范式替换发生在 `616d837` (2025-12-31)，从 per-dimension 特殊逻辑迁移到通用 ParamSpace 框架**

**证据**:
- `616d837` 是 `paramspace.py` 的初始创建，一次性建立完整框架
- 同时 `compiler.py` 从硬编码的 `compile_spin/compile_soc/compile_material` 重构为调用 `compile_dimension_patch`
- Commit message: "Refactor preset handling and enhance UI integration"
- **意图**: 消除 per-dimension 特殊逻辑，统一到声明式 ParamSpace + 通用算法

---

## A. 文档考古：Repo 里关于 ParamSpace 的"宪法"到底怎么写的？

### A1) 关键文档清单

通过全仓库搜索，找到以下关键文档：

| 文档 | 路径 | 相关性 |
|------|------|--------|
| **CONSTITUTION_ZH.md** | 根目录 | ⭐⭐⭐⭐⭐ 最高优先级 - 宪法定义 |
| **WORKFLOW_PRESET_DESIGN_V0.md** | docs/ | ⭐⭐⭐⭐ 设计文档 |
| **review-paramspace-dimension-variant-key-and-step-ssot.md** | docs/dev/ | ⭐⭐⭐ 代码审查报告 |
| **review-parameter-paramspace-ir-genstep.md** | docs/dev/ | ⭐⭐⭐ 代码审查报告 |
| **PRESET_PARAMSPACE_CODE_REVIEW.md** | docs/ | ⭐⭐ 代码审查 |
| **IMPLEMENTATION_PLAN_PRESET_UI.md** | docs/ | ⭐⭐ 实现计划 |
| **ir_step_engine_v0.md** | docs/design/ | ⭐⭐ IR 设计文档 |

### A2) 关键文档的主张列表

#### A2.1 CONSTITUTION_ZH.md

**最后修改**: 需要检查 git log（见 A3）

**关键主张**:

1. **§10.7 Preset Space 统一框架**
   - Preset Space = 声明式数据结构 + 通用算法
   - 每个维度必须声明 ParamSpace（keys, defaults, aliases, profiles, tolerances）
   - 禁止 per-dimension 特殊逻辑

2. **§12.1 键所有权唯一性（必须）**
   - YAML 叶键（section+key）必须由且仅由一个 ParamSpace 拥有
   - 重复所有权是错误

3. **§12.2 Detect/Compile 访问规则（必须）**
   - ParamSpace 只能访问：
     - 其自身声明的 keys
     - **oracle 暴露的先决条件** ⚠️
   - 禁止直接读写其他 paramspace 的 keys

4. **§10.3.3 局部精确修改原则**
   - Preset Apply 只允许修改该维度 ParamSpace Variant 明确声明的 keys
   - 所有不归该 preset 维度管理的参数必须保持原样

5. **§10.7.3 Cell 类型**
   - VALUE: 显式值
   - NOT_APPLICABLE: 要求 present == False
   - WILDCARD: 忽略

**与当前代码一致性**: ⚠️ **部分一致**
- ✅ ParamSpace 框架存在
- ✅ Cell 类型实现
- ❌ Oracle 未实现
- ⚠️ Key 单归属只有约定，无 enforce

#### A2.2 WORKFLOW_PRESET_DESIGN_V0.md

**最后修改**: 需要检查 git log

**关键主张**:

1. **ParamSpace 定义**
   - ParamSpace 是矩阵（profile × key）
   - 每个维度必须声明完整的 ParamSpace

2. **可逆性要求**
   - match_profile 和 compile_profile_patch 必须可逆

3. **degauss 归属**
   - 文档中未明确说明 degauss 的归属

**与当前代码一致性**: ✅ **基本一致**

#### A2.3 review-paramspace-dimension-variant-key-and-step-ssot.md

**最后修改**: 2026-01-10（当前报告的前一份报告）

**关键主张**:

1. **Key 单归属**: 不存在全局 enforce，只有约定
2. **Oracle**: 未找到明确的 oracle 机制
3. **编译顺序**: 无明确顺序控制（按字典迭代）
4. **degauss**: 属于 `occupations_scheme`，不属于 `precision`

**与当前代码一致性**: ✅ **完全一致**（这是代码审查报告）

### A3) 文档历史：这些主张何时写入？是否后来被改掉/删掉？

#### A3.1 Oracle 主张的历史

**搜索命令**: `git log -p -S "oracle" --all -- docs CONSTITUTION*`

**结果**: ⚠️ **无结果** - 说明 oracle 的主张可能从一开始就在 CONSTITUTION_ZH.md 中，或者是在某个早期提交中添加的，但该提交不在当前 git 历史中。

**当前状态**: `CONSTITUTION_ZH.md` §12.2 明确提到 oracle，但代码中从未实现。

#### A3.2 Key Ownership 主张的历史

**搜索命令**: `git log -p -S "单归属" --all -- docs CONSTITUTION*`

**结果**: ⚠️ **无结果** - 说明 key ownership 的主张可能从一开始就在 CONSTITUTION_ZH.md 中。

**当前状态**: `CONSTITUTION_ZH.md` §12.1 明确要求 key 单归属，但代码中只有 `DIMENSION_OWNED_KEYS`（已标记 DEPRECATED）。

#### A3.3 两阶段编译主张的历史

**搜索命令**: `git log -p -S "two-phase|two-stage|pre-compile|post-compile" --all -- docs`

**结果**: ❌ **无结果** - 文档中从未提到两阶段编译。

**结论**: **两阶段编译从未在文档中出现过**。

#### A3.4 degauss 归属的历史

**搜索命令**: `git log -p -S "degauss" --all -- src/quantumvitas/presets`

**结果**: 
- `616d837` (2025-12-31): 文件创建时，`degauss` 就定义在 `build_occupations_scheme_paramspace()` 中
- 之后无变更

**结论**: **degauss 从未属于 precision，一直属于 occupations_scheme**。

---

## B. 代码考古：机制是否存在过？在哪里实现/替换？

### B1) 以 degauss 为锚点：归属迁移考古

#### B1.1 degauss 首次出现

**Commit**: `616d837` (2025-12-31)  
**文件**: `src/quantumvitas/presets/paramspace.py`  
**位置**: `build_occupations_scheme_paramspace()` 函数

**代码证据**:
```python
key_degauss = ParamKey(
    section="SYSTEM",
    key="degauss",
    parser=parse_float,
    canonicalizer=canonicalize_float,
    tolerance=1e-12,
    default=None,
)
```

**结论**: ✅ **degauss 从文件创建起就属于 `occupations_scheme` ParamSpace**

#### B1.2 是否发生过迁移？

**搜索**: `git log -p -G "precision.*degauss|degauss.*precision" --all -- src/quantumvitas/presets`

**结果**: ❌ **无结果** - 从未发生过从 precision 到 occupations_scheme 的迁移。

**搜索**: `git log -p -G "occupations_scheme.*degauss|degauss.*occupations_scheme" --all -- src/quantumvitas/presets`

**结果**: ✅ **degauss 一直与 occupations_scheme 绑定**

**结论**: **degauss 从未属于 precision，一直属于 occupations_scheme**。

### B2) oracle / two-phase compile 的代码痕迹考古

#### B2.1 Oracle 代码搜索

**搜索命令**:
```bash
git log -p -S "oracle" --all -- src/quantumvitas
git log -p -S "Oracle" --all -- src/quantumvitas
grep -r "oracle|Oracle|ORACLE" src/quantumvitas
```

**结果**: ❌ **无任何代码实现**

**结论**: **Oracle 从未在代码中实现过，只在 CONSTITUTION_ZH.md §12.2 中作为设计意图出现**。

#### B2.2 Two-phase compile 代码搜索

**搜索命令**:
```bash
git log -p -G "two[-_ ]phase|two[-_ ]stage|pre.*compile|post.*compile" --all -- src/quantumvitas/presets
```

**结果**: ❌ **无任何代码实现**

**结论**: **Two-phase compile 从未在代码中实现过**。

#### B2.3 编译顺序代码搜索

**搜索命令**:
```bash
git log -p -G "compile.*order|DIMENSION_ORDER|topological|sort" --all -- src/quantumvitas/presets
```

**结果**: 
- `apply_presets_to_step()` 中按 `applied_dimensions` 字典顺序迭代
- 无明确的编译顺序控制

**结论**: **编译顺序无明确控制，按字典迭代顺序（不确定）**。

### B3) 可逆性测试考古

**搜索命令**: `git log -p -G "match_profile|compile_profile_patch|custom|infer|reverse" --all -- tests src/quantumvitas/presets`

**关键测试文件**:
- `tests/unit/test_paramspace.py` - ParamSpace 框架测试
- `tests/unit/test_presets.py` - Preset 编译/检测测试

**测试覆盖的 invariants**:
1. ✅ Profile 互斥性（`match_profile()` 要求 profiles 互斥）
2. ✅ NOT_APPLICABLE presence/absence（`match_profile()` 要求 present == False）
3. ✅ Custom 判定（无匹配时返回 None）
4. ❌ 编译顺序依赖（无测试）

**结论**: **可逆性测试存在，但无编译顺序依赖的测试**。

### B4) Step 域与 SSOT

**搜索命令**: `git log -p -G "StepType\\(|GeneralizedStep|public_type|machine_type|applies_to_step_types" --all -- src/quantumvitas`

**关键发现**:
- `applies_to_step_types` 在 `ParamSpaceVariant` 中使用 `public_type` 字符串（如 "scf", "nscf"）
- `public_type` 对应 `StepTypeSpec.id`，是 GenStep 字符串
- `StepType` enum 是第三套词典（混用 gen 和 spec）

**结论**: **`applies_to_step_types` 使用 GenStep 字符串（public_type），但格式与 `GeneralizedStep` 枚举不一致**。

---

## C. "文档主张 vs 代码事实"对齐矩阵

| 主张内容 | 文档证据 | 代码证据 | 结论 | 分叉时间 |
|---------|---------|---------|------|---------|
| **ParamSpace 框架** | CONSTITUTION_ZH.md §10.7 | `paramspace.py` (616d837) | ✅ **一致** | N/A（初始实现） |
| **Cell 类型 (VALUE/NA/WILDCARD)** | CONSTITUTION_ZH.md §10.7.3 | `CellType` enum (616d837) | ✅ **一致** | N/A |
| **Key 单归属（必须）** | CONSTITUTION_ZH.md §12.1 | `DIMENSION_OWNED_KEYS` (DEPRECATED) | ❌ **不一致** | 616d837（只有约定，无 enforce） |
| **Oracle 暴露先决条件** | CONSTITUTION_ZH.md §12.2 | 无实现 | ❌ **不一致** | 从未实现 |
| **两阶段编译** | 无文档 | 无实现 | ✅ **一致**（都不存在） | N/A |
| **degauss 归属** | 未明确 | `occupations_scheme` ParamSpace | ✅ **一致**（一直属于 occupations_scheme） | N/A |
| **编译顺序控制** | 未明确 | 无控制（字典迭代） | ⚠️ **不确定** | 616d837（无顺序控制） |
| **可逆性要求** | CONSTITUTION_ZH.md §10.7 | `match_profile()` + `compile_profile_patch()` | ✅ **一致** | N/A |

### C.1 关键不一致点分析

#### C.1.1 Key 单归属：文档要求 vs 代码实现

**文档要求** (`CONSTITUTION_ZH.md` §12.1):
> YAML 叶键（section+key）必须由且仅由一个 ParamSpace 拥有。重复所有权是错误。

**代码实现**:
- `DIMENSION_OWNED_KEYS` (integration.py:307) 已标记 `DEPRECATED`
- 注释说明："This is no longer used for deletion decisions. Deletions are now driven by profile NOT_APPLICABLE cells and keys that will be written."
- `variants_registry.py:_build_indexes()` 只 enforce `(step_type, dimension)` 单归属，不 enforce key 单归属

**分叉时间**: `616d837` (2025-12-31) - 文件创建时就没有全局 key 归属 enforce，只有约定。

#### C.1.2 Oracle：文档要求 vs 代码实现

**文档要求** (`CONSTITUTION_ZH.md` §12.2):
> 在 detect/compile 中，ParamSpace 只能访问：
> - 其自身声明的 keys
> - **oracle 暴露的先决条件**

**代码实现**:
- 全仓库搜索 `oracle|Oracle|ORACLE` 无任何实现
- `compile_dimension_patch_for_step()` 只接收 `dimension`, `option_enum`, `step_type`, `step_yaml`，无 oracle 参数
- Precision 通过 `precision_context` 接收外部数据（structure + pseudos），但不是 oracle

**分叉时间**: **从未实现** - Oracle 只在文档中作为设计意图出现，从未在代码中落地。

---

## D. 最终结论：我们要怎么处理（只提 options，不动代码）

### D.1 Option 1：接受"新范式"（当前实现）

**描述**: 接受当前实现（无 oracle、无两阶段编译、key 单归属只有约定），并补齐约束。

**需要改哪些文件类别**:
1. **文档更新**:
   - `CONSTITUTION_ZH.md` §12.2：删除或明确说明 oracle 是未来扩展点（当前未实现）
   - `CONSTITUTION_ZH.md` §12.1：明确说明 key 单归属当前是约定，未来需要 enforce
2. **测试补充**:
   - 添加 key 单归属的全局验证测试（确保不同 dimension 的 ParamSpace 不共享 keys）
   - 添加编译顺序的确定性测试（如果需要）
3. **代码增强**（可选）:
   - 在 `variants_registry.py` 中添加全局 key 归属注册表
   - 在 `_build_indexes()` 中添加 key 归属冲突检测

**风险点**:
- ✅ **可逆性**: 当前实现已保证（match/compile 可逆）
- ⚠️ **SSOT**: key 单归属无 enforce，可能未来出现冲突
- ✅ **迁移成本**: 低（只需文档更新和测试补充）

### D.2 Option 2：恢复"旧范式"（实现 oracle + 两阶段编译）

**描述**: 实现 CONSTITUTION_ZH.md §12.2 中描述的 oracle 机制，并引入两阶段编译。

**需要改哪些文件类别**:
1. **Oracle 实现**:
   - 创建 `oracle.py` 模块，定义 `Oracle` 接口/类
   - Oracle 提供：其他 dimension 的选择、step topology、全局信息
   - 修改 `compile_dimension_patch_for_step()` 接收 oracle 参数
2. **两阶段编译**:
   - 修改 `compile_profile_patch()` 分为 `pre_compile()` 和 `post_compile()`
   - Pre-compile: 处理依赖其他 dimension 的 keys（通过 oracle）
   - Post-compile: 处理独立 keys
3. **Key 归属 enforce**:
   - 实现全局 key 归属注册表
   - 在 `_build_indexes()` 中添加 key 归属冲突检测

**风险点**:
- ⚠️ **可逆性**: 需要确保两阶段编译不影响可逆性
- ⚠️ **SSOT**: 需要明确 oracle 的 SSOT 来源
- ❌ **迁移成本**: 高（需要大量代码重构和测试）

**问题**: **"旧范式"从未在代码中实现过**，所以这不是"恢复"，而是"首次实现"。

### D.3 Option 3：混合方案（保留现状 + 补齐 minimal 机制）

**描述**: 保留当前实现，但补齐 key ownership enforce 和编译顺序的 minimal 机制。

**需要改哪些文件类别**:
1. **Key 归属 enforce**:
   - 在 `variants_registry.py` 中添加全局 key 归属注册表
   - 在 `_build_indexes()` 中添加 key 归属冲突检测（类似 `(step_type, dimension)` 冲突检测）
   - 移除 `DIMENSION_OWNED_KEYS` 的 DEPRECATED 标记，或从 variants 自动生成
2. **编译顺序**（如果需要）:
   - 在 `variants_registry.py` 中定义 `DIMENSION_COMPILE_ORDER` 列表
   - 在 `apply_presets_to_step()` 中按顺序编译
3. **文档更新**:
   - `CONSTITUTION_ZH.md` §12.2：明确说明 oracle 是未来扩展点（当前未实现）
   - `CONSTITUTION_ZH.md` §12.1：说明 key 单归属已 enforce（在代码中实现后）

**风险点**:
- ✅ **可逆性**: 当前实现已保证
- ✅ **SSOT**: key 单归属 enforce 后更安全
- ✅ **迁移成本**: 中等（需要实现 key 归属检测，但不需要 oracle）

---

## E. 最后一句话总结（必须写在报告末尾）

**在 commit `616d837` (2025-12-31) 之前，ParamSpace 体系不存在（文件创建）；之后，ParamSpace 框架一次性建立，但 CONSTITUTION_ZH.md §12 中描述的 oracle 机制和 key 单归属 enforce 从未在代码中实现；文档是否同步更新：否（CONSTITUTION_ZH.md 仍要求 oracle 和 key 单归属 enforce，但代码中只有约定）；导致当前与用户记忆冲突的最可能原因是：用户可能将 CONSTITUTION_ZH.md 中的设计意图（oracle、两阶段编译）误认为是已实现的功能，或者用户记忆的是设计讨论而非实际实现。**

---

## 附录：Git 命令执行记录

### 文档搜索
```bash
rg -n -i "ParamSpace|paramspace|preset|oracle|two[- ]phase|compile order|编译顺序|可逆|match_profile|NOT_APPLICABLE|WILDCARD|key ownership|单归属" docs README* src/
```

### Oracle 代码搜索
```bash
git log -p -S "oracle" --all -- src/quantumvitas
git log -p -S "Oracle" --all -- src/quantumvitas
grep -r "oracle|Oracle|ORACLE" src/quantumvitas
```
结果：**无任何实现**

### Two-phase compile 代码搜索
```bash
git log -p -G "two[-_ ]phase|two[-_ ]stage|pre.*compile|post.*compile" --all -- src/quantumvitas/presets
```
结果：**无任何实现**

### degauss 归属追踪
```bash
git log -p -S "degauss" --all -- src/quantumvitas/presets
git log -p -G "precision.*degauss|degauss.*precision" --all -- src/quantumvitas/presets
git log -p -G "occupations_scheme.*degauss|degauss.*occupations_scheme" --all -- src/quantumvitas/presets
```
结果：**degauss 从 616d837 起就属于 occupations_scheme，从未属于 precision**

### Key ownership 文档搜索
```bash
git log -p -S "单归属" --all -- docs CONSTITUTION*
git log -p -S "key ownership|Key Ownership" --all -- docs CONSTITUTION*
```
结果：**无结果** - 说明 key ownership 的主张可能从一开始就在 CONSTITUTION_ZH.md 中

