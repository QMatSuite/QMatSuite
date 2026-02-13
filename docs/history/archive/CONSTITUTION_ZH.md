> **DEPRECATED — This document is no longer authoritative.**
> **The authoritative English constitution is now: `CONSTITUTION.md` (repo root).**
> **This Chinese version is retained for historical reference only. If conflicts exist, `CONSTITUTION.md` governs.**

# QMatSuite 宪法（Constitution）— 已废弃

**版本**: 2.0 (已废弃；权威版本为 `CONSTITUTION.md` v2.1)
**最后更新**: 2026-02-03
**适用范围**: QMatSuite / QuantumVITAS v2 代码库

---

## 前言

> ⚠️ **本文档已废弃。权威宪法现为英文版 `CONSTITUTION.md`（仓库根目录）。**

本文档是 QMatSuite 项目旧版中文"宪法"（Constitution）。
权威版本已迁移至英文 `CONSTITUTION.md`，以消除双语漂移风险。

**给 AI 的一句话指令**
> 遵守根目录 **CONSTITUTION.md**（英文）；详细规范见 docs/governance/；可做改进按小 PR 走。

---

## 术语与真相层

### Truth vs Info
- **Truth（真相层）**：用于计算、可复现、必须稳定的事实与键（ULID、SHA256、结构的 canonical form、单位约定）。
- **Info（信息层）**：用于展示、理解、提示、搜索的可变信息（文件名、路径、slug、来源描述、UI 文案）。

### 身份（Identity）
- 资源身份以 **ULID** 为唯一标识。
- 伪势身份以 **SHA256（严格）** / **SHA_FAMILY（物理）** 为核心判定键（见第 7 节）。

---

## 1. 语言规则（Language Policy）

1) 本仓库所有代码、注释、文档默认语言为**英文**。
2) 只有根目录 `CONSTITUTION_ZH.md` 为中文。
3) 除非作者明确要求，不新增其它中文文档或注释。

---

## 2. SSOT 与持久化（Single Source of Truth）

### 2.1 唯一可执行真相

SSOT 仅为：**calculation.yaml** + **step.yaml**。

- step.yaml 是唯一可执行真相；任何计算结果的可复现性只能由 step 参数保证。
- step.yaml 必须保持纯粹输入，不得包含 workflow / preset / provenance 等元数据。
- calculation.yaml 负责：structure、species_map（伪势三元组）、step 拓扑。

### 2.2 Input 文件是中间产物

Input 文件（如 QE `.in` 文件）是中间产物：
- materialize 时通过 clean rewrite 写入 `raw/`。
- run 只读取 `raw/`。
- 运行期间修改 YAML 不影响当前 run（仅影响下次 run）。

### 2.3 禁止扫描 outdir/.save

不得扫描/清理 `outdir/.save`（wavefunction 等），不得将其用于增量跳过决策。

### 2.4 YAML IO 必须通过 Doc + yaml_io

所有 project/calc/step YAML 的读写必须使用 Doc 层和集中化的 yaml_io。禁止直接使用 `yaml.safe_load`/`yaml.safe_dump`。

> 详细规范：[KERNEL_DEPENDENCY_SPEC.md](docs/governance/KERNEL_DEPENDENCY_SPEC.md) §2.1 (Domain: ssot)

---

## 3. Present vs Past（History 世界分离）

### 3.1 Present = 工作目录真相

当前计算状态只存在于工作目录中的 SSOT 文件（calculation.yaml + step.yaml）。

### 3.2 Past = .history/（唯一）

- `.history/` 是唯一允许持久化派生叙事工件（digests / thumbnails / 快照）的位置。
- `.history/` 为 append-only、immutable。
- 删除 `.history/` 意味着历史 UI 变空，**不得**从其他地方"重建"。

### 3.3 Job == Run

- 每次引擎调用 = 一个 Job = 一个 Run；job_id == run_id（同一 ULID）。
- 每次 run 产生一个 immutable **RunRevision**（inputs snapshot + run digest + step digests）。
- Digest 是 best-effort，不得因 digest 失败而 crash。

---

## 4. 并发与锁（Concurrency & Locks）

每个 calculation 有两个跨进程文件锁：

| 锁 | 持有时长 | 用途 |
|----|---------|------|
| `edit.lock` | 短锁 | 仅用于 YAML 写入（via `save_yaml_doc()`） |
| `run.lock` | 长锁 | 从 materialize 到执行结束 |

**锁不可重入**：持有 `edit.lock` 时不得再次调用 `save_yaml_doc()`（portalocker non-reentrant → deadlock）。

---

## 5. 增量运行 Manifest（Incremental Run）

### 5.1 Manifest = 运行时 bookkeeping（非 SSOT）

每个 calc 的 manifest 是运行时 bookkeeping，可删除，不是 UI cache，不是 SSOT。

### 5.2 Skip 决策

Skip 判定只使用：`(kind/step_type, pseudo_set_sha, structure_sha, step_sha, done==true)`。永远不使用 output hashes。

### 5.3 运行模式

- **Run Calculation**：增量运行为默认；full run 先 reconcile 并清除 done 标记，然后从 step0 开始。
- **Run Single Step**：目标 step 必须总是执行（no skip）。成功后保守地将下游 steps 标记为 `done=false`。

### 5.4 StepDonePolicy 集中化

"Step done" 逻辑必须集中在 `StepDonePolicy`（runner + skip 的单一入口点）。

---

## 6. 身份：ULID-only

### 6.1 ULID 引用规则

- 资源之间只允许通过 **ULID** 引用。
- 路径、文件名、slug 只能作为 Info，不得作为跨资源引用依据。
- DTO/meta **不得**包含遗留身份字段（`id`, `calc_id`, `step_id`, `run_id` 等）。
- 规范字段：`project_ulid`, `calc_ulid`, `step_ulid`, `run_ulid`。
- Slug 仅为资源自身的 `meta.slug`，不得在跨资源引用中持久化；内部引用只用 ULID。

### 6.2 Project Root

- Project root marker 固定为：`project.qv.yml`。
- 查找逻辑：向上遍历目录树找到包含 marker 的目录。

### 6.3 身份不变性

- rename / move / 目录重排不应改变资源身份（ULID 不变）。

### 6.4 不变性范围

**不变性真相键**（初始化后必须不变）：ULID、step_type_spec、engine。

**可变信息键**：name、slug、path、description。

> 门禁：`tests/gates/test_no_legacy_identity_fields.py`

---

## 7. Step Type 宪法（GEN/SPEC only）

### 7.1 两个且仅两个命名空间

| 字段 | 层 | 用途 | 示例 |
|------|---|------|------|
| `step_type_gen` | Intent/UI/workflow/preset/ParamSpace/文件命名 | 引擎无关 | `scf`, `relax`, `bandspw` |
| `step_type_spec` | SSOT 执行/step.yaml/runner/dispatch/handler | 引擎特定 | `qe_scf`, `vasp_relax`, `w90_wannier` |

### 7.2 推导规则（核心法则）

```
step_type_spec = f"{engine_prefix}_{step_type_gen}"
```

- `engine_prefix` 和 `step_type_gen` **不得**包含下划线 `_`（下划线禁令 → 可靠拆分）。
- 反向推导使用 `split(spec)` 在首个下划线处拆分。
- 转换工具函数必须集中在 `workflow/step_type_convert.py`。

### 7.3 禁令

- **别名 step type 全面禁止**：DTO/YAML/tests/tools 中不得出现 `vc-relax`, `opt`, `w90_preproc`, `w90_run` 等别名。
- **禁止裸 `step_type` 字段**：必须显式使用 `step_type_gen` 或 `step_type_spec`。
- **禁止手动 split/join**：不得在代码中手动拆分/拼接下划线；必须使用规范转换函数。
- **Daemon/CLI 禁止转换**：上层不得导入/调用转换函数；DTO 同时携带双字段。

### 7.4 Wannier 工作流

- GEN: `wannierprep` → `pw2wannier` → `wannier`
- SPEC: `w90_wannierprep` → `qe_pw2wannier` → `w90_wannier`

### 7.5 Bands 语义

- `bandspw` 是计算步骤（qe/vasp 可实现）。
- `bands` 是后处理步骤（qe 可实现；vasp 可能没有，允许 gen→spec=0 映射）。

> 详细规范：[STEP_TYPE_GEN_SPEC_CONSTITUTION.md](docs/governance/STEP_TYPE_GEN_SPEC_CONSTITUTION.md)
> 门禁：`tests/gates/test_step_type_constitution.py`, `test_no_bare_step_type.py`, `test_underscore_ban.py`, `test_no_manual_join_split.py`, `test_banned_legacy_aliases.py`

---

## 8. Preset / ParamSpace / IR（非持久化意图层）

### 8.1 非实体原则

Preset / Workflow / IR **不持久化**。它们仅是对当前 step DAG 的运行时解释和对 step 参数集合的正向生成/反向解释。

### 8.2 ParamSpace 编译流程

ParamSpace 将 preset profile 编译为 IR patch，写入 step.yaml（SSOT）。

### 8.3 反向推断

Preset 仅通过"精确持久化模式匹配"来推断；不匹配 → `custom`。

### 8.4 ParamSpace 核心约束

- **Single-writer 原则**：每个 YAML key 只能由一个 ParamSpace 写/删。
- **三态 Cell**：每个 profile 对每个 key 必须为 `VALUE(v)` / `NOT_APPLICABLE`（must-absent）/ `WILDCARD`（不参与匹配）。
- **Compiler/Detector 等价性**：`detect(compile_one(step_type, options))` 必须等于原始 options 值。
- **禁止猜测**：关键参数缺失且无可靠默认语义时，Detector 必须返回 `CUSTOM`。

### 8.5 Apply 规则

- Apply 是**局部精确修改**：只修改该维度 Variant 声明的 keys。
- NOT_APPLICABLE → 必须删除该 key。
- 其他维度/用户手写参数必须保持原样。
- 执行顺序：先 Prerequisite ParamSpaces（改变 applicability 的），再 Dependent ParamSpaces（依赖 Oracle 的）。

> 详细定义见宪法旧版 §10（ParamSpace 完整框架）在 `docs/governance/PARAMSPACE_SPEC.md` 中独立维护。

---

## 9. Species / 伪势 SSOT

### 9.1 Project-run 伪势 SSOT

- SSOT 在 `calculation.yaml`: `species_map`（element / mass / pseudo filename + hash，可扩展）。
- Step-level `species_overrides` 为 warning+ignored（仅用于 legacy/standalone）。

### 9.2 pseudo_dir 运行时管理

- `pseudo_dir` 是运行时管理的，强制指向 `project/pseudo`。
- Runner 仅 stage 所需伪势。

### 9.3 伪势三源

仅允许三类来源：
- **internal**：`repo/resources/pseudo`
- **lib**：用户安装在 `.qmatsuite/libraries/pseudo/` 下
- **project runtime**：`project/pseudo`

禁止第四来源。

### 9.4 SHA256 vs SHA_FAMILY

- **SHA256**：bitwise identical（严格）。
- **SHA_FAMILY**：物理等价（移除所有空白字符后的 SHA256）。
- UI 下拉选择主键是 SHA256。SHA_FAMILY 仅用于冲突处理 / 警告 / 跨 calc 引用更新。

---

## 10. Scan 规则（硬法则）

### 10.1 YamlDoc 不变量

`dict` 总是子树 patch；dict-leaf 禁止（scan 无例外）。

### 10.2 ScanRef

ScanRef leaf 仅为标量 token 字符串 `"@scan:<scan_id>"`。禁止 `{scan_ref: ...}` 旧格式。

### 10.3 parameter_scan 结构

`step.yaml` 中顶层 `parameter_scan.<scan_id>.values:[...]`。

- Values 仅为显式枚举；`linspace/logspace` 仅为 UI 工具，不持久化。
- Fingerprint/manifest hash 仅包含解析后的有效引擎参数；`parameter_scan` 段本身不参与 hash。

### 10.4 Scan 范围与排序

- Scan 展开在单个 job 内进行；scan 不跨 job。
- Variant 排序确定性：later-step / faster-changing dimensions 在 inner loop（最大化复用）。

### 10.5 孤儿 scan 删除

需要完整替换语义；UI 移除所有 scan 时必须发送 `parameter_scan:{}`。UI 必须在 Apply 时 flush scan values（commit-on-apply）。

---

## 11. Managed / Injected 参数 UI 策略

运行时管理的 keys（如 QE CONTROL: `prefix`/`outdir`/`pseudo_dir`）和 step-type-owned keys（如 `CONTROL.calculation`）在 UI 中为**只读**：不可编辑 / scan / unset / remove。

优先使用引擎元数据 `is_managed` + `managed_reason` 驱动 UI（MVP 可为 QE）。

---

## 12. UI input → YAML → Writer 类型契约

### 12.1 两类 Keys

| 类 | 定义 | 类型规则 |
|----|------|---------|
| **A-class** | Preset/IR/ParamSpace 拥有/映射的 keys | 严格类型 + 规范化；无效解析阻止持久化 |
| **B-class** | 自由引擎 keys | 无类型强制；任意字符串允许 |

### 12.2 A-class key set SSOT

来自 ParamSpace/IR registry export，**不是** `qeparameters.json`。

### 12.3 Writer 契约

- typed bool → QE 输出 `.true.`/`.false.`
- string `".true."` 保持字面值，不重新解释。

---

## 13. RELAX 审计法则

### 13.1 Relax 是结构变换器

Input structure → output structure；无电子态 / 无 SCF 引用。

### 13.2 唯一 GEN step

只有一个公开 GEN step: `relax`。引擎内部 spec: `qe_relax`, `orca_relax`, `pyscf_relax`。

### 13.3 输出结构

Output structure 是 calc-private artifact；不是 project structure resource，除非显式 promote。

### 13.4 QC 强链边界（ORCA/PySCF）

- SCF chain 不得跨越 relax。
- `run_step(non-relax)` 必须找到 relax 之前的 SCF，否则硬错误。
- `run_calc` 验证拓扑并 fail-fast。

### 13.5 缺失结构 = 硬错误

缺少生成的结构 artifact → 硬错误；不自动重跑 relax。

---

## 14. LAMMPS 集成宪法

### 14.1 结构变换引擎

LAMMPS 是结构变换引擎。GEN steps: `relax`, `md`；SPEC: `lammps_relax`, `lammps_md`（显式映射）。

### 14.2 restart_from

`restart_from` 引用上游 artifacts，不引用 structure resources。不跨 calculation 引用；跨 calc 复用需 promote structure。

### 14.3 potential_map SSOT

`calculation.yaml`: `potential_map` 为 SSOT；assets 在 `project/potentials/`。

### 14.4 Fingerprint 必须包含 potentials

Inline dict → `step_sha`；external files → `potential_assets_sha`（未来统一为 `engine_assets_sha`）。

### 14.5 真实执行 smoke tests

必须有 LJ relax、EAM MD external、relax→md chain、md restart_from 四类真实执行测试。

---

## 15. 几何宪法

### 15.1 单次 Canonicalization

Structure canonicalization 只允许发生一次（在几何入口/准备层）。之后不允许再 snap / wrap / fold。

### 15.2 Canonicalization 区间

分数坐标映射到 `[-wrap_tol, 1 - wrap_tol)`，`wrap_tol = 1e-4`（默认）。

### 15.3 Boundary atoms

双侧判定（`0 ± boundary_tol`、`1 ± boundary_tol`），`boundary_tol = 0.01`（默认）。

---

## 16. QE 结构 Schema

### 16.1 内部存储

- 只存 cell parameters（绝对单位，Å）。
- 原子位置一律存 frac 坐标。
- 永不在 JSON 中存储 QE 特定表示（ibrav / alat / celldm 等）。

### 16.2 输出文件命名不变量

输入可版本化（`scf.in`, `scf-1.in`），输出固定为 `{step_type}.out/.err` 并覆盖。禁止由 input 推导 output 文件名。

---

## 17. 引擎执行语义

### 17.1 两类引擎模型

| 模型 | 引擎 | 状态传递 |
|------|------|---------|
| 会话链（Session-chain） | PySCF/ORCA | 内存态链，线性有序 |
| 工件桥接（Artifact-bridged） | QE/W90/LAMMPS | 磁盘文件桥接，步骤可独立 |

### 17.2 会话链引擎的严格线性依赖

- 每步必须 consume 最近合法前序 state；state 不存在 → 硬失败。
- 禁止 DAG 执行、跳跃依赖、隐式补全。
- SCF 是唯一 consume structure 并 produce mf 的步骤。
- SCF checkpoint 仅作 initial guess，必须重跑 SCF。
- 除 SCF 外不存在可靠序列化/复用/恢复的中间态。

### 17.3 引擎集成不变量

- 所有路由必须是显式 registry lookup，未知 step type → 硬错误。
- 添加新引擎不得修改 kernel 代码（只新增 `drivers/<engine>/` + tests）。
- Driver 自包含：所有引擎特定逻辑在 driver bundle 内。

> 详细规范：[ENGINE_INTEGRATION_CONSTITUTION.md](docs/governance/ENGINE_INTEGRATION_CONSTITUTION.md)

---

## 18. API 分层与 Facade

### 18.1 三层模型

| 层 | 包 | 导入规则 |
|----|---|---------|
| **Frontend** | daemon, CLI, GUI | 只能从 `quantumvitas.api` 导入 |
| **API Facade** | `quantumvitas.api` | DTOs + Errors + Utils + Service |
| **Core/Runtime** | 其余所有包 | Frontend 不可直接导入 |

### 18.2 Utils 策略

默认不允许 utils reexport。例外仅限于：
- 真正的 frontend boundary helper
- 不能合理地成为 QVService capability method
- 有 docstring justification

### 18.3 DTO 边界

所有跨 API 边界的数据必须为 DTO 或 primitive types。

### 18.4 Filesystem Access Control（Law H9）

仅 kernel 允许修改 SSOT 文件系统。Frontend 不得直接写 YAML / 创建项目结构 / 修改 calculation/step/structure 文件。

> 详细规范：[API_CONSTITUTION.md](docs/governance/API_CONSTITUTION.md)
> 门禁：`tests/gates/test_import_gate.py`, `test_frontend_no_yaml_write.py`, `test_daemon_kernel_ban.py`

---

## 19. Kernel 内部依赖

### 19.1 Kernel → API 禁止

Kernel 不得反向导入 API facade。

### 19.2 七域模型

Kernel 组织为 7 个 domain（ssot, resources, models, runtime, engines, analysis, workflow），各有明确职责边界和禁止导入规则。

### 19.3 YAML 读取

Resolution 只允许读取 `meta.*` 子树（元数据），不得读取非 meta 字段。

> 详细规范：[KERNEL_DEPENDENCY_SPEC.md](docs/governance/KERNEL_DEPENDENCY_SPEC.md)
> 例外：[KERNEL_EXCEPTIONS.md](docs/governance/KERNEL_EXCEPTIONS.md)
> 门禁：`tests/gates/test_kernel_no_api_import.py`, `test_engine_no_ssot_import.py`, `test_resolution_meta_only.py`

---

## 20. 数据根目录与临时目录

### 20.1 两类根目录

| 目录 | 语义 | 可删除 |
|------|------|--------|
| `.qmatsuite/` | 持久化资产（engines, libraries, seeds, config, logs） | 否 |
| `.tmp/` | 临时文件（runs, downloads, locks） | 是 |

### 20.2 废弃 temp/

代码中不得再使用 `repo_root/temp/`。任何新代码引用 `temp/` 视为违宪。

### 20.3 settings.json

唯一全局配置（极简）。QE 引擎两态模型：`qe.bin_dir` 为 null → Internal QE；非 null → External QE。禁止隐式 fallback（PATH / QE_HOME / shell discover / disk scan）。

---

## 最后条款

### 修改原则
- 宪法修改需项目作者审核。
- 实现细节、证据、TODO、改进建议放在英文文档中维护。

### 解释权
- 宪法优先。
- 简洁性优先。
- 数学可证明性优先于 UX 便利。

### 总结性原则

**Execution is concrete; intention is inferred.**

所有计算只相信 step 参数；workflow 与 preset 只是对现状的解释，而非事实。

---

## 修订摘要 v2.0（2026-02-03）

### 从 v1.2 到 v2.0 的主要变化

**结构重组**：
- 宪法从 ~1400 行"全量详细"重写为 ~380 行"薄宪法"。
- 详细机制规范迁移至 `docs/governance/` 下的独立文档。
- 新增文档层级体系（宪法 > governance specs > implementation docs）。

**新增法则**（对齐 13 条已实施的 final laws）：
1. **§3 History 世界分离**：Present vs Past，`.history/` append-only，Job == Run，RunRevision。
2. **§4 并发与锁**：edit.lock / run.lock 两锁模型，不可重入。
3. **§5 增量运行 Manifest**：非 SSOT bookkeeping，skip 决策规则，StepDonePolicy 集中化。
4. **§10 Scan 规则**：ScanRef `@scan:<id>` 标量 token，dict-leaf 禁止，scan 不跨 job。
5. **§11 Managed 参数**：UI read-only 策略。
6. **§12 类型契约**：A-class / B-class key 分类，writer 契约。
7. **§13 RELAX 审计**：结构变换器语义，QC 强链边界，缺失结构 = 硬错误。
8. **§14 LAMMPS 集成**：potential_map SSOT，fingerprint 包含 potentials。
9. **§18 API 分层**：三层模型，Utils 策略，H9 filesystem access control。
10. **§19 Kernel 依赖**：七域模型，反向导入禁止，meta-only 读取。

**语义更新**：
- Step type 章节（§7）对齐 GEN_SPEC_CONSTITUTION，取消旧"StepTypeRegistry 集中化"叙述。
- SSOT（§2）明确 calculation.yaml + step.yaml（非 step.yml / calc.yml）。
- Identity（§6）对齐 ULID-only 法则：禁止 `id`, `calc_id`, `step_id`。
- Species/pseudo（§9）对齐 project-run species_map SSOT。

**删除/折叠的旧章节**：
- 旧 §10（ParamSpace 全文 ~400 行）→ 瘦化为 §8（核心约束），详细定义迁入 `PARAMSPACE_SPEC.md`。
- 旧 §11-14 → 折叠进相应新章节或迁入 governance specs。
- 旧修订历史列表（~200 行）→ 删除，仅保留 v2.0 摘要。

**旧语义中的过时内容**（已修正）：
- `step.yml` / `calc.yml` → 正确为 `step.yaml` / `calculation.yaml`
- 旧"StepTypeRegistry 叙述"→ 对齐 GEN/SPEC 两命名空间法则
- 缺失的 history / locks / scan / manifest 规则 → 已新增
- 缺失的 LAMMPS / RELAX / API / Kernel 规则 → 已新增
