> ⚠️ **本文档已合并入根目录 CONSTITUTION_ZH.md，**
> **不再作为独立宪法来源。**
> **如有冲突，以 CONSTITUTION_ZH.md 为准。**

# ParamSpace / Oracle / Apply 体系设计宪法（v1）

## 0. 核心目标

- 保证 detect / apply 正反对称
- 保证 CUSTOM 友好
- 保证 无 entanglement / 无后门
- 保证 Single-writer
- 保证 复杂度单调增长，不指数爆炸

## 1. Single-writer 原则（不可违反）

**每一个 YAML key 只能由一个 ParamSpace 写/删**

任何"多个 ParamSpace 共同管理同一 key"的设计都是非法的

**语义归属 ≠ 写入归属**
（例如：degauss 语义依赖 occupation，但 writer 仍归 precision）

## 2. ParamSpace 的统一职责模型

每个 ParamSpace 必须且只做三件事：

### Detect
- 使用 matrix 判定 preset / CUSTOM
- 只依赖 YAML 真相 + Oracle（只读）

### Preset Apply
- 仅当用户显式选择该 ParamSpace 的 preset 时执行
- 使用同一套 matrix 写入值
- NOT_APPLICABLE ⇒ must-absent

### Custom Apply（Invariant Enforcement）
- **永远执行**
- 即使 detect 结果是 CUSTOM
- 即使用户没有修改该 ParamSpace
- 用于维护该 ParamSpace 负责 keys 的定义域 / 适用性不变量
- 默认行为是 no-op（pass）

❗️**禁止 "CUSTOM ⇒ 什么都不做" 的隐式假设**

## 3. NOT_APPLICABLE 的强语义

NOT_APPLICABLE ≠ wildcard

它隐含 **must-absent**

- apply：必须删除该 key
- detect：若 present ⇒ 冲突 ⇒ CUSTOM

## 4. Oracle 的定位（极窄）

Oracle 不是 guard

Oracle 不负责 preset 判定

Oracle 只提供"语义前提（semantic prerequisite）"

Oracle 必须满足：
- 只读
- 只返回小离散值（bool / 小 enum）
- 不返回 preset id
- 不返回"建议值"

目前允许的 oracle 函数：
- `degauss_applicability() -> bool`

## 5. Oracle 的信息源

Oracle 只看 **YAML 真相**（当前内存态）

不看 preset intention

不看 detect 的命中结果（可能是 CUSTOM）

## 6. Apply 执行顺序（必须）

Apply 必须分阶段执行：

1. **Prerequisite ParamSpaces**
   - 会改变 applicability 的（如 occupation、step_type）

2. **Dependent ParamSpaces**
   - 依赖 oracle 的（如 precision）

这是为了保证：
- Oracle 在 apply 时永远只读"最新 YAML 真相"

## 7. Precision / degauss 的宪法级约束

**SYSTEM.degauss 的唯一 writer 是 Precision ParamSpace**

Precision ParamSpace 在 apply 时必须：

1. **永远执行 invariant enforcement**
   - 若 `degauss_applicability == false` ⇒ 删除 degauss

2. **仅在用户显式设置 precision preset 时写入 degauss 值**
   - LOW / MED / HIGH ⇒ 0.01 / 0.02 / 0.03

3. **smearing 时 不强制自动补 degauss（策略 A）**

## 8. 禁止事项（红线）

- ParamSpace 读取其他 ParamSpace 的 preset 结果
- Oracle 返回 preset id / 参数值
- 为了方便 detect/apply 而引入共享写入
- 为 custom case 写隐式特判逻辑而不通过 ParamSpace 统一接口

## 一句话宪法总结

**Matrix 决定"写什么 / 判什么"，**
**Custom Apply 决定"即使不写也要维护定义域"，**
**Oracle 只回答"现在适不适用"，**
**顺序保证 Oracle 永远只看真相。**

