# QMatSuite 宪法（Constitution）

**版本**: 1.2  
**最后更新**: 2025-01-XX  
**适用范围**: QMatSuite / QuantumVITAS v2 代码库

---

## 前言

本文档是 QMatSuite 项目的“宪法”（Constitution）。它只定义项目的最高规则、不变量、术语与真相层（Truth vs Info）。  
所有代码修改、架构决策、AI 辅助开发都必须遵守这些规则。

**重要说明**
- 本文档是仓库内**唯一的中文文档**，用于项目作者快速阅读。
- 除本文档外，所有代码、注释、文档默认语言为**英文**。除非作者明确要求，不新增其它中文文档或注释。
- 本文档只记录**规则与定义**，不记录实现细节（文件路径、行号、函数列表、证据摘录等应放入英文文档/ TODO）。

**给 AI 的一句话指令（复制粘贴即可）**
> 遵守根目录 CONSTITUTION_ZH.md；实现入口/证据看 docs/IMPLEMENTATION_NOTES.md；可做改进按 docs/TODO_ADR_ALIGNMENT.md 走小 PR。

---

## 术语与真相层

### Truth vs Info
- **Truth（真相层）**：用于计算、可复现、必须稳定的事实与键（例如：ULID、SHA256、结构的 canonical form、单位约定）。
- **Info（信息层）**：用于展示、理解、提示、搜索的可变信息（例如：文件名、路径、slug、来源描述、UI 文案）。

### 身份（Identity）
- 资源身份以 **ULID** 为唯一标识。
- 伪势身份以 **SHA256（严格）** / **SHA_FAMILY（物理）** 为核心判定键（见第 6 节）。

---

## 1. 语言规则（Language Policy）

1) 本仓库所有代码、注释、文档默认语言为**英文**。  
2) 只有根目录 `CONSTITUTION_ZH.md` 为中文。  
3) 除非作者明确要求，不新增其它中文文档或注释。（GUI 国际化不在本条约束范围内。）

---

## 2. 资源图谱与引用（ULID-only DAG + Index + Cache）

### 2.1 ULID-only 引用规则
- 资源之间只允许通过 **ULID** 引用（ID-only）。
- 路径、文件名、slug 只能作为 **Info**，不得作为跨资源引用依据与真相。

### 2.2 必然代价与缓存原则
- ULID-only 的必然代价：需要从 **project root** 向下扫描所有资源，构建 registry/index，进而构造 DAG。
- 因此必须存在 **cache**：
  - 至少要有内存缓存；
  - 当项目规模增长时，必须具备可行的持久化缓存方案；
  - 缓存失效策略必须明确（例如基于 mtime/hash 或显式手动失效）。

### 2.3 Project Root 约定
- Project root marker 固定为：`project.qv.yml`（存在即代表项目根目录）。
- root 查找逻辑：向上遍历目录树，找到包含 marker 的目录。

### 2.4 身份不变性
- rename / move / 目录重排不应改变资源身份（ULID 不变）。

---

## 3. 几何宪法：Canonicalization 只做一次；之后不 snap

### 3.1 单次 Canonicalization
- Structure canonicalization **只允许发生一次**（在几何入口/准备层）。
- canonicalize 之后：不允许再次对原子分数坐标做 snap / wrap / fold。
- 后续若需表达等价单胞，只允许通过改变 lattice vectors 来实现。

### 3.2 Canonicalization 的区间规则与 wrap_tol
- 分数坐标必须被映射到：`[-wrap_tol, 1 - wrap_tol)`。
- `wrap_tol` 的意义：仅用于覆盖浮点 knife-edge（0/1 附近），应较小。
- 当前宪法默认：`wrap_tol = 1e-4`。

### 3.3 Boundary atoms 判定与 boundary_tol
- Boundary atoms 判定采用“双侧判定”：
  - 近 0：`0 ± boundary_tol`
  - 近 1：`1 ± boundary_tol`
- `boundary_tol` 可稍大，因为它只影响“是否额外加入边界显示原子”，不应影响主物理与主结构。
- 当前宪法默认：`boundary_tol = 0.01`。

---

## 4. Atom list 与 Bonds：一等公民模型 + 纯数学函数

### 4.1 统一计算路径（必须）
不论 prim / supercell / conventional cell / QE 的 ibrav 表示差异，最终必须走同一条数学路径：

`canonicalized geometry → atom list（primary + optional boundary，皆一等公民）→ bonds(atom_list)`

### 4.2 Atom list 一等公民
- primary atoms 与 boundary atoms 均为一等公民（first-class citizens），以“同一 atom list”表达。
- boundary atoms 只能通过“扩展 atom list”进入显示/统计，不得引入特殊的“boundary-only 成键逻辑”。

### 4.3 Bonds 的纯函数契约
- bonds 必须由纯数学函数从 atom list 生成。
- bond detection 不得产生几何副作用（不得 canonicalize / wrap / snap / 修改结构）。

---

## 5. QE 结构 Schema：JSON 只存绝对单位 cell + frac coords

### 5.1 输入解析 vs 内部存储
- QE 输入层允许解析多种表示（ibrav、alat、CELL_PARAMETERS 等）。
- 但进入我们的 JSON/内部结构存储后，必须统一为单一真相表示。

### 5.2 内部存储规范（必须）
- **只存 cell parameters（绝对单位）**
- **原子位置一律存 frac 坐标**
- **永不在 JSON 中存储 QE 特定表示**：ibrav / alat / celldm 等。

### 5.3 单位真相（必须）
- 内部 lattice / cell parameters 的绝对单位统一为：**Å（angstrom）**。

---

## 6. Pseudopotential 身份：SHA（严格相同）vs SHATOKEN（物理相同）

### 6.1 SHA256（严格身份）
- SHA256 表示 bitwise identical 的严格身份，用于去重存储与可复现锁定。

### 6.2 SHA_FAMILY（物理相同 / 语义等价）
- SHA_FAMILY 用于"物理相同"的判定（语义等价）。
- 算法（宪法定义）：
  1) 将 UPF 文本中所有空白字符（isspace()）移除
  2) 把剩余字符拼接为字符串
  3) 对该字符串的 UTF-8 bytes 计算 SHA256
- 因此：
  - `"1    23"` 与 `"1 23"` → sha_family 相同（空白被移除）
  - `"1    23"` 与 `"12  3"` → sha_family 相同（空白被移除，都变成 "123"）
  - `"1    23"` 与 `"1    24"` → sha_family 不同（非空白字符不同）

### 6.3 判定规则（必须）
- **sha_family 不同**：视为完全不同，不可混用。
- **sha_family 相同但 sha256 不同**：视为物理一致；默认以标准库/权威来源的版本覆盖用户导入副本（例如 CRLF/LF 差异导致 sha256 不同）。

---

## 7. 伪势管理（Pseudopotentials）不变量

### 7.1 伪势三源（唯一来源模型）
- 仅允许三类来源：
  - **internal**：仅指 `repo/resources/pseudo`（禁止使用 `tests/demo` 等其它目录）。
  - **lib**：用户安装在 `temp/pseudo/...` 下的库（例如 `temp/pseudo/sssp/1.3.0/efficiency` 的结构）。
  - **project runtime**：`project/pseudo`（项目运行目录）。
- **禁止**引入第四来源（如 cache、seed、或任何隐式目录）。
- 如历史代码/文档出现 `repo_root/pseudo`、`tests/demo`、其它 pseudo 缓存目录等概念，必须清理。

### 7.2 唯一运行目录：project/pseudo
- QE 运行时（输入文件中的 pseudo 路径）**永远只指向** `project/pseudo`。
- lib/internal 的 pseudo 仅作为“可被选择/拷贝”的外部候选；实际运行前**必须落地到** `project/pseudo`。
- **禁止**在 repo root 创建/使用 `repo_root/pseudo`。

### 7.3 UI 与 Run 的职责边界
- **UI/设置页面/预览页面**：不得执行任何文件系统写操作（不得 copy / rename / 覆盖 / mkdir pseudo）。
- 所有涉及 `project/pseudo` 的文件系统变更，**只允许**在用户点击 Run 后的“Step0/准备阶段”统一执行。
- 目的：保证 UI 与 Run 不分叉语义，避免“双逻辑”。

### 7.4 sha256 vs sha_family 的语义与用途
- **sha256**：严格字节一致性（打开保存、换行 CRLF、空格变化都会变）。
- **sha_family**：物理等价指纹（将 UPF 文本中所有空白字符移除后，把剩余字符拼接为字符串，再对该字符串的 UTF-8 bytes 计算 sha256）。
- **重要**：UI 下拉选择主键是 **sha256**，不是 sha_family。
- **sha_family 仅用于**：
  - 冲突处理（Step0 rename/overwrite 决策）
  - 警告/提示（family-match、family-mismatch）
  - 跨 calc 引用一致性更新（rename 后按 sha_family 更新 calc 引用的 filename）

### 7.5 UI 选择与 calc.yml 持久化规则

#### 7.5.1 UI 展示/可选项规则
- Dropdown 中“可选条目”必须对应文件系统真实存在的 UPF（project 或 internal 或已安装 lib 中能解析得到的文件）。
- UI 允许展示 provenance chips（project/internal/lib），但不要求展示“未安装库”的 disabled 条目；未安装库可以只在右侧 chip/提示中出现为 provenance 信息（例如“属于某未安装库”）。
- UI 默认选择优先级：project → internal → lib（优先贴近 runtime 实际，减少“无意覆盖”）。

#### 7.5.1.1 确定性优先级（tie-break）规则
- 当 sha256 命中多个候选（多来源或多路径/多 basename），用以下规则选“默认展示/默认选中”的那一个：
  - **若 calc.yml 里有 pseudo_filename**，优先选择 filename 完全匹配的候选（同 sha256 下可能多个候选，先 filename 命中）。
  - **若 filename 命中仍有多个，或没有任何 filename 命中**：按来源优先级 project → internal → lib。
  - **若仍有多个**（例如同为 lib 且 sha256 命中多库），按 library/asset 名称字母序（ascending）稳定排序选第一个。
  - **若同一 lib 内仍有多个**（极少见），按 relative_path / basename 字母序稳定排序选第一个。

#### 7.5.2 默认选中（恢复选择）规则：不写 yml
- 打开 calc 时，UI 根据 calc.yml 里的记录恢复选择：
  - **优先按 pseudo_sha256 精确匹配**（命中则选中该 sha256 对应条目；若同 sha256 有多来源，按 7.5.1.1 tie-break 规则选定）。
  - **若 sha256 找不到**（库未安装/文件改名/迁移等），fallback 按 pseudo_filename：
    - 先在 project/pseudo/<filename> 找
    - 再在 internal/resources/pseudo/<filename> 找
    - 再在已安装 lib 中按 filename 找（若多条则按 7.5.1.1 tie-break 规则选定，并给 warning）
- **以上“自动恢复默认选中”的过程绝对不能写回 calc.yml**（只读恢复，不做持久化变更）。

#### 7.5.3 用户主动选择时：写 triplet，三元必须一起写
- 只有当用户在 UI 中手动点击改变选择时，才写回 calc.yml。
- 写回时必须一次性更新三元组（triplet）：
  - `pseudo_filename`
  - `pseudo_sha256`
  - `pseudo_sha_family`
- 并要求在 UI debug log 输出一条"写 yml"的日志（用于排查）。

#### 7.5.4 Family-match edge case 的 UI 规则
- 若 project/pseudo/<basename> 与某 external（lib/internal）：
  - sha256 不同但 sha_family 相同（family-match）
- 则 UI 不得合并成一个条目（避免"用户没选却被替换"的隐式行为）。应表现为：
  - **project 本地条目**：显示 project chip，并额外提示"family-match with <lib/internal>（仅物理等价）"
  - **external 条目**：显示 lib/internal chip，并额外提示"family-match with project（仅物理等价）"
- 这样用户只有在显式选择 external 条目时，Run 才会发生覆盖行为（见 Step0 规则）。

### 7.6 Calculation 必须记录 pseudo 三元组
- 每个 calc **必须记录**：
  - `pseudo_filename`（在 `project/pseudo` 下的文件名）
  - `pseudo_sha256`（严格字节哈希）
  - `pseudo_sha_family`（"物理等价"哈希）
- Run 前 Step0 结束后，**必须刷新写回**上述记录。
- 允许 calc 存在 stale sha256 状态：未重新 Run 前可以与当前文件不一致（见 7.7.3）。

### 7.7 Step0 冲突规则（以 sha_family 做语义分歧）

#### 7.7.1 Step0 总原则
- Step0 的职责：根据 UI/calc 选中的 pseudo，把所需 pseudo 准备到 project/pseudo，并刷新 calc 记录（sha256/sha_family/filename）。
- **如果用户选择的是 project/pseudo 自身的文件（project source）**：
  - Step0 必须 noop（不覆盖/不改名），但仍需计算并刷新 calc 的 sha256/sha_family（用于修复 stale 记录）。

#### 7.7.2 当选择的是 external（internal/lib）并需要落地到 project/pseudo/<basename> 时
- 若目标 basename 已存在于 project/pseudo：
  - **若 sha256 相同**：noop
  - **若 sha_family 相同但 sha256 不同**：overwrite（只有在用户显式选择 external 时才发生；"标准库版本"= 用户所选 external）
  - **若 sha_family 不同**：rename_existing
    - 必须把已存在的旧文件改名为不冲突的新名字（例如追加 `__fam-<old_family[:10]>` 之类），保证 project/pseudo 内同名文件不对应不同 sha_family
    - 并且必须基于旧文件的 sha_family，对项目内所有 calcs 做引用更新：只更新 filename，不改变其 sha_family 身份（保持物理身份不变）

#### 7.7.3 stale sha 的定义与允许性
- calc 可以存在 stale sha256：文件被打开保存/换行改变导致 sha256 变化但 sha_family 不变，这并不表示"物理改变"。
- 只有当 sha_family 也变化才表示物理改变，需要更强 warning；但处理仍然遵循上述 Step0 规则。

---

## 8. Windows Toolchain：oneAPI + MKL + MPI（拒绝 MinGW 作为主路线）

### 8.1 主路线（必须）
- Windows 下专业/HPC 可交付路线：**原生 oneAPI + MKL + (MS-MPI / Intel MPI)**。

### 8.2 MinGW 不是主路线（政策）
- MinGW 路线不是主路线：往往更难（可能需要修改 QE 源码以通过）且性能不如 oneAPI+MKL。
- 本仓库当前未接入 Windows CI：不是技术不可行，仅为尚未完成；但路线选择必须明确写入宪法以防误导。

---

## 9. 数据根目录、临时目录与可复现资产

### 9.1 两类根目录（dev 阶段固定在 repo root，且都 gitignore）

#### 9.1.1 `.qmatsuite/`：持久化、可迁移、可复现资产
- **语义**：持久化资产目录，包含可迁移、可复现的数据。
- **位置**：`repo_root/.qmatsuite/`（dev 阶段固定）。
- **内容**：
  - `engines/`：已安装的 QE 引擎（managed engines）
  - `libraries/`：已安装的库（如伪势库）
  - `seeds/`：可重装介质（QE seed、伪势 seed）
  - `config/`：全局配置（`settings.json`）
  - `logs/`：日志文件
- **特性**：
  - 可迁移（可复制到其他机器）
  - 可复现（seed 支持离线重装）
  - 必须 gitignore

#### 9.1.2 `.tmp/`：临时目录
- **语义**：临时文件目录，任何时候可删除。
- **位置**：`repo_root/.tmp/`（dev 阶段固定）。
- **内容**：
  - `runs/`：计算运行目录（`<calc_ulid>/`）
  - `downloads/`：下载缓存
  - `unpack/`：解包临时目录
  - `probe/`：自动搜索缓存
  - `locks/`：文件锁
- **特性**：
  - 可随时删除
  - 必须 gitignore

#### 9.1.3 废弃 `temp/`
- **禁止**：代码中不得再使用 `repo_root/temp/`。
- **迁移**：所有 `temp/` 下的内容必须迁入 `.qmatsuite/` 或 `.tmp/`。
- **规则**：新代码若出现 `temp/`，视为违反宪法。

### 9.2 目录结构标准化

```
repo_root/
  .qmatsuite/                    # 持久化资产（gitignore）
    config/
      settings.json              # 唯一全局配置（极简）
    engines/
      qe/
        <opaque_folder_name>/    # QE 引擎文件夹（名称不具语义）
          bin/                   # 语义单元：包含 pw* 可执行文件的 bin 目录
          test-suite/
          ...
    libraries/
      pseudo/                    # 已安装伪势库
        sssp/
          1.3.0/
            precision/
            efficiency/
    seeds/
      qe/
        <seed_id>/               # QE seed：压缩包/安装介质/校验信息
          archive.tar.gz
          manifest.json
          sha256.txt
      pseudo/                    # 伪势 seed
        sssp/
          1.3.0/
            precision/
            efficiency/
    logs/
      ...
  .tmp/                          # 临时目录（gitignore）
    runs/
      <calc_ulid>/               # 计算运行目录
    downloads/                   # 下载缓存
    unpack/                      # 解包临时目录
    probe/                       # 自动搜索缓存
    locks/                       # 文件锁
    e2e_projects/                # E2E 测试项目目录
```

**重要说明**：
- 在 `.qmatsuite/engines/qe/**/bin` 下，**包含 pw* 可执行文件的 bin 目录是唯一的语义单元**。
- 引擎文件夹名称（`<opaque_folder_name>`）不具语义，仅作为组织用途。

### 9.3 QE Seed 机制

#### 9.3.1 定义与用途
- **QE seed**：可重装介质，用于离线/快速重装 engine。
- **功能**：
  - 校验 hash（SHA256）
  - 支持回滚
  - 离线安装（无需重新下载）

#### 9.3.2 安装流程（设计级定义）
1. **下载阶段**：下载到 `.tmp/downloads/`
2. **校验阶段**：校验 SHA256
3. **落盘阶段**：保存到 `.qmatsuite/seeds/qe/<seed_id>/`
4. **解包/安装阶段**：解包/安装到 `.qmatsuite/engines/qe/<opaque_folder_name>/`

#### 9.3.3 当前状态
- **当前版本尚未支持通过 seed 在程序内自动重装 QE；seed 仅作为未来可复现机制的占位定义。**
- 灾难恢复功能（从 `seeds/qe/` 重新安装）尚未实现。

### 9.4 QE 引擎解析（两态模型）

#### 9.4.1 唯一真相：settings.qe.bin_dir
- QE 引擎选择的唯一真相来源是 `settings.json` 中的 `qe.bin_dir` 字段。
- `bin_dir` 必须是绝对路径，指向包含 `pw*` 可执行文件的 bin 目录。

#### 9.4.2 两态模型

**状态 1：External QE（外部 QE）**
- 若 `settings.qe.bin_dir != null`：
  - 视为 External QE
  - 必须是包含 `pw*` 可执行文件的 bin 目录
  - 若无效（目录不存在或缺少 `pw*` 可执行文件）→ 直接报错，不回退

**状态 2：Internal QE（内部 QE）**
- 若 `settings.qe.bin_dir == null`：
  - 使用 Internal QE
  - 从 `.qmatsuite/engines/qe/**/bin` 中自动选择
  - 若不存在 → 报错并提示安装

#### 9.4.3 禁止隐式 fallback
- **禁止任何隐式 fallback**：
  - 禁止搜索系统 PATH
  - 禁止搜索 QE_HOME 环境变量
  - 禁止 shell 自动发现
  - 禁止磁盘扫描自动发现
- 所有引擎选择必须通过显式配置（`settings.qe.bin_dir`）或内部引擎自动选择完成。

### 9.5 settings.json 最小 Schema

```json
{
  "version": "1.0",
  "qe": {
    "bin_dir": null
  }
}
```

**字段说明**：
- `version`：配置版本号
- `qe.bin_dir`：QE bin 目录的绝对路径
  - 若为 `null`：使用 Internal QE（从 `.qmatsuite/engines/qe/**/bin` 自动选择）
  - 若为非 `null`：使用 External QE（必须指向包含 `pw*` 可执行文件的 bin 目录）

**原则**：
- `settings.json` 是 machine-local 配置，不可移植。
- `bin_dir` 是绝对路径，绑定到特定机器的文件系统。
- Project 配置不记录 engine 信息。
- 可复现性来自 raw in/out 中的 QE version 记录，而非 settings。
- `settings.json` 是唯一全局配置（极简）。
- 禁止引入多个配置文件。

### 9.6 迁移说明

#### 9.6.1 历史目录迁移对照表

| 历史路径 | 新路径 | 说明 |
|---------|--------|------|
| `temp/pseudo_seed/` | `.qmatsuite/seeds/pseudo/` | 伪势 seed 迁移 |
| `temp/pseudo/` | `.qmatsuite/libraries/pseudo/` | 伪势库迁移 |
| `temp/test_outputs/` | `.tmp/runs/` | 测试运行目录迁移 |
| `temp/matplotlib_tests/` | `.tmp/runs/` | 测试运行目录迁移 |
| `temp/e2e/` | `.tmp/e2e_projects/` | E2E 测试项目目录迁移 |

#### 9.6.2 迁移规则
- 所有 `temp/` 下的持久化资产（pseudo_seed、pseudo 解包库）→ `.qmatsuite/`
- 所有 `temp/` 下的临时文件（test_outputs、e2e、matplotlib_tests、e2e_projects）→ `.tmp/`
- 迁移后，代码中禁止再出现 `temp/` 路径。
- **明确规则**：任何新代码引用 `repo_root/temp` 视为违反宪法。

---

## 10. 计算模型与 Preset / Workflow 宪法

本宪法用于约束 QMatSuite 中 proj / calc / step 计算模型，以及 preset / workflow / compiler / detector 的设计边界。  
本宪法优先级高于任何具体实现、UI 便利或短期工程优化。

### 10.1 唯一真相原则（Single Source of Truth）

#### 10.1.1 执行真相
系统中**唯一的可执行真相**是 step.yml 中记录的 input parameters。  
任何计算结果的可复现性，只能且必须由 step 参数保证。

#### 10.1.2 文件系统纯度
step.yml 必须保持纯粹输入，不得包含以下任何信息：

- workflow 标识
- preset / option / provenance
- 参数来源、继承关系、生成历史
- compiler / detector 相关元数据

违反本条视为模型污染。

#### 10.1.3 calc 职责边界
calc 仅负责：

- structure
- pseudopotentials

calc 不得持有任何计算参数、preset 状态或 workflow 状态。

### 10.2 Preset / Workflow 的法律地位

#### 10.2.1 非实体原则
workflow 与 preset 不是一等公民，不得作为持久化实体存在于文件系统中。

它们仅是：

- 对当前 step DAG 的运行时解释
- 对 step 参数集合的正向生成与反向解释

### 10.3 Compiler（正向生成）的宪法约束

#### 10.3.1 Compiler 定义与职责
Compiler 是一个纯函数族，其职责是**规范化写入器**：将用户选项映射为 step 的 input parameters。

其形式为：

```
compile_one(step_type, options) -> full_parameter_dict
```

或等价的批量形式。

**职责定位**：Compiler 是规范化写入器，负责将用户意图转换为显式、完整的参数表示。

#### 10.3.2 输入独立性
Compiler 不得依赖以下任何信息：

- step 拓扑 / DAG
- workflow
- structure
- pseudopotential
- calc 状态

Compiler 仅允许依赖：

- step_type
- 用户 options（spin / soc / material / accuracy 等）

**例外：precision resolver 的 context 依赖**：
一般维度的 compiler 不得依赖 structure/pseudo；但允许少数维度（如 precision）通过明确命名的 resolver 依赖 context。resolver 必须纯函数、可审计、有合同测试。

#### 10.3.3 局部精确修改原则
Preset Apply 必须是局部精确修改：只允许修改该维度 ParamSpace Variant 明确声明的 keys（包括写入 VALUE 和删除 NOT_APPLICABLE）。所有不归该 preset 维度管理的参数必须保持原样（不得被重置、不得被删除、不得被覆盖）。该规则用于保证 canonical form 与数学等价性，同时确保用户手写/其他维度参数不会被清空。

如果未来需要"清理/归一化/删除多余参数"，应通过一个独立的清理功能实现，而不是 preset apply 的职责。

#### 10.3.4 Canonical Encoding（必须显式写出）
Compiler 输出必须采用规范化参数表示，**必须显式写出所有关键参数**：

- 所有关键语义（如 spin / soc / material / accuracy）必须显式写出
- 不得依赖默认值（即使 QE 有默认值，也必须显式写入）
- 不得留下与当前 option 冲突的残留参数
- 不得省略任何影响语义的参数

**示例**：若 option 为 nonspin，Compiler 必须显式写入 `nspin = 1`，不得依赖 QE 默认值。

### 10.4 Detector B（反向检测）的宪法地位

#### 10.4.1 Detector 核心性与职责
Detector B 是系统中**唯一合法的 preset / option 状态判定来源**。  
UI 不得基于用户"选择历史"显示状态。

**职责定位**：Detector B 是语义解释器，负责从 step 参数反向推断用户意图，包括隐式默认语义。

#### 10.4.2 无 A 原则
系统中**不存在"Selected vs Detected"双轨状态模型**。  
所有状态均由 Detector B 从 step 参数实时推断。

### 10.5 Detector B 的数学定义

#### 10.5.1 维度判定
每个 preset 维度（如 Spin / SOC / Material / Accuracy）独立判定。

对任一维度 d：

1. 选取相关 step 集合 R_d
2. 从每个 step 提取值 v_d(step)（见 10.5.3 隐式默认语义）
3. 构造集合 V = unique(v_d(step) for step in R_d)

判定规则为：

- 若 |V| == 1 → Detected = 该唯一值
- 若 |V| > 1 → Detected = Custom

不存在 Unknown 状态。

#### 10.5.2 单步合法性
若 R_d 中仅包含一个 step，则该 step 的值即为 Detected 值。  
单步合法，不构成 Custom。

#### 10.5.3 隐式默认语义的反向解释（必须支持）
Detector B 必须支持隐式默认语义的反向解释。

**规则**：当 step 参数中未显式写出某个关键参数时，Detector 必须按照 QE 默认语义进行解释。

**示例**：
- 若 step 中未写 `nspin`，Detector 必须解释为 `nonspin`（等价于 `nspin = 1`）
- 若 step 中未写 `lspinorb`，Detector 必须解释为 `no_soc`（等价于 `lspinorb = .false.`）

**目的**：保证 Detector 能够正确解释非 Compiler 生成的 step（如用户手动编辑、从 QE input 导入等）。

### 10.6 Compiler 与 Detector 的数学等价性

#### 10.6.1 职责不对称性
Compiler 与 Detector 在职责上具有不对称性：

- **Compiler（规范化写入器）**：将用户意图转换为显式、完整的参数表示
- **Detector（语义解释器）**：从参数反向推断用户意图，包括隐式默认语义

这种不对称性导致等价性要求的不同严格程度。

#### 10.6.2 等价性公理（区分 Compiler 输出与非 Compiler 输出）

**对 Compiler 输出（严格等价）**：
对任意 options 与 step_type，必须满足：

```
detect( compile_one(step_type, options) ) == options 在该维度的值
```

该等价性是强制不变量，必须严格满足。

**对非 Compiler 输出（宽容语义推断）**：
对非 Compiler 生成的 step（如用户手动编辑、从 QE input 导入），Detector 允许更宽容的语义推断：

- 允许基于隐式默认语义进行解释（见 10.5.3）
- 允许处理参数缺失、参数冗余等情况
- 目标是在语义等价的前提下，尽可能推断出合理的 preset / option 状态

**示例**：
- Compiler 输出：`nspin = 1` → Detector 必须检测为 `nonspin`
- 非 Compiler 输出：未写 `nspin` → Detector 应推断为 `nonspin`（基于隐式默认）

**QE 参数 JSON / schema 的定位（仅诊断工具）**：
QE 参数 JSON / schema 仅作为诊断工具：当 Variant 声称写入的 key 不被该 step_type 接受时，发出 warning。但 warning 不改变 apply/detect 的行为。禁止用 JSON 推导/决定：某维度是否应用、某 key 是否应该被写入/删除、某 step 是否属于某 variant。行为真相必须来自 ParamSpace Variant 的显式声明（见 10.7.9）。该规则确保 apply/detect 逻辑的唯一真相来源，避免 JSON schema 成为第二真相。

运行时可发 warning；对核心 step_types / 核心维度，必须有 enforcement tests（或 CI 约束）确保：variant 声称写入的 key 在 schema 中被接受，否则视为配置错误（fail）。

#### 10.6.3 禁止 Guessing（猜测式识别）

当某维度的关键参数缺失，且不存在可靠的 QE 隐式默认语义可映射到某个 profile 时：

- Detector 必须返回 CUSTOM
- 不得"猜一个最可能的 preset"

容忍缺失只允许以两种方式出现：

1. 该维度在 ParamSpace 中明确声明 defaults，并用 present vs effective 区分语义（见 10.7.4）
2. 该 key 在该 space 之外（无关参数）或被声明为 WILDCARD（无语义，见 10.7.3）

禁止任何基于"最可能值"、"常见值"、"历史经验"的猜测行为。该规则防止未来再出现"缺 conv_thr 就 MED"等猜测式识别，确保 detect 的严格性与可复现性。

#### 10.6.4 等价性验证
等价性必须通过 unit tests 验证，而非经验保证：

- **Compiler 输出等价性**：必须通过严格的 unit tests 验证
- **非 Compiler 输出语义推断**：必须通过测试覆盖常见场景（参数缺失、默认值、冗余参数等）

### 10.7 Preset Space 统一框架（声明式数据结构 + 通用算法）

#### 10.7.1 统一框架原则
Preset Space = 声明式数据结构 + 通用算法。

**目标**：避免每个维度各写一套 compiler/detector/receiver 导致反复出现"apply 能写、detect 读不出"的 bug。

**核心要求**：
- 每个 preset 维度必须由一个"参数空间声明（ParamSpace）"描述
- 禁止为某个维度单独写"特判 detector/特判 compiler"
- 允许维度提供 ParamSpace 声明 + （可选）少量纯函数 canonicalizer，但核心逻辑必须复用通用框架

#### 10.7.2 ParamSpace 声明结构
每个 preset 维度必须声明一个 ParamSpace，包含以下要素：

**keys（固定有序列表）**：
- 完整定义本空间允许读写的参数键
- 必须是有序列表（用于确定性匹配与写入顺序）

**defaults（隐式默认值字典）**：
- 每个 key 的隐式默认值，用于 detect 时补全 effective_value
- 当 YAML 中未显式包含某 key 时，使用对应的 default 值

**aliases/canonicalizers（同义词表/规范化规则）**：
- 同义词表：例如 `gaussian` 与 `gauss` 等价
- 规范化规则：必须属于 ParamSpace，而不是散落在 detector 中
- 每个 key 可以有独立的 canonicalizer 函数（纯函数）

**profiles（用户可选项的矩阵）**：
- 对 keys 的每一项给出 cell（见 10.7.3）
- profiles 必须是"满矩阵"：对 keys 全覆盖
- 任何漏填在构造时必须自动补 WILDCARD 或直接报错（实现由代码决定，但宪法必须要求"不可漏 key"）

**numeric tolerances（数值容差）**：
- 如 float 的 abs_tol
- 用于 detect 时的数值比较

#### 10.7.3 Cell 语义（三态）
每个 profile 对每个 key 必须给出一个 cell，且只能是以下三种之一：

**VALUE(v)**：
- 该 key 的期望值为 v
- detect 用 effective_value 比较（带 canonicalize/容差）
- apply 根据 explicit_defaults 决定是否显式写入（见 10.7.5）

**NOT_APPLICABLE**：
- 该 key 在此 profile 下不应显式存在
- apply 必须删除该 key
- detect 若 present==True 则不匹配（见 10.7.4）

**WILDCARD**：
- 该 key 在此 profile 下不参与匹配
- detect 不检查该 key
- apply 默认不写、不删，保持原样

**满矩阵要求**：
- profiles 必须对 keys 全覆盖
- 任何漏填在构造时必须自动补 WILDCARD 或直接报错
- 实现由代码决定，但宪法必须要求"不可漏 key"

#### 10.7.4 present vs effective_value（detect 必须区分）
detect 必须区分两个概念：

**present**：
- YAML 是否显式包含该 key
- 布尔值：True 表示 YAML 中存在该 key，False 表示不存在

**effective_value**：
- 若 present 则取 YAML 值，否则取 defaults 值
- 取值后必须经过 canonicalize（应用同义词表/规范化规则）

**匹配规则**：
- **VALUE**：比较 effective_value（带 canonicalize/容差）
- **NOT_APPLICABLE**：检查 present 必须为 False（不看 effective_value）
- **WILDCARD**：不检查

**目的**：解决"apply 能写、detect 读不出"的根本原因——detect 必须正确处理参数缺失与默认值。

#### 10.7.5 apply 的 explicit_defaults 开关
apply(profile, explicit_defaults=True|False) 的行为：

**VALUE**：
- explicit_defaults=True：必写（即使 value == default 也显式写入）
- explicit_defaults=False：若 value == default 则不写（删除该 key，依赖隐式默认）

**NOT_APPLICABLE**：
- 必须删除该 key（无论 explicit_defaults 值）

**WILDCARD**：
- 默认不写不删（不触碰该 key）

**目的**：允许 Compiler 在"显式写入所有参数"与"依赖 QE 默认值"之间选择，同时保证 detect 的一致性。

**Policy 澄清（explicit_defaults 与显式写入原则）**：
Production compiler 默认必须使用 explicit_defaults=True，以满足宪法里"显式写出关键参数、不依赖 QE 默认值"的原则（见 10.3.4 Canonical Encoding）。explicit_defaults=False 只能作为 advanced/compact encoding 的可选模式存在：不能成为默认路径、必须有独立合同测试覆盖、不能影响 detect 的严格可逆性（尤其是 strict detector）。该政策确保所有关键参数可审计、可追溯，避免依赖隐式默认导致的语义模糊。

**Apply 契约：精确修改，不 reset 众生**：
apply 只能修改该 Variant 的 parameter space 中的 key（profile 指定的 VALUE/NOT_APPLICABLE）。任何不在该 space 的 key 必须保持原样（不得被重置、不得被删除、不得被覆盖）。这是为了保证用户手写/其他维度参数（如 DFT+U 等）不会因为应用其它 preset 而被清空。该规则确保 apply 的局部性：只影响显式声明的 keys，不影响其他参数。

**删除规则：禁止"因为 owned 就先删"**：
删除只能由两类原因触发：profile cell == NOT_APPLICABLE（明确要求清理）、本次 apply 将写入该 key（覆盖语义）。禁止为了"归属/owned keys"而先删除，但最终又不写回 replacement（这会导致数据丢失）。必须有合同测试覆盖此规则（尤其是 cards 类参数的安全性），确保不会出现"先删后不写"的数据丢失场景。

#### 10.7.6 零技术债原则
本系统是新功能：不允许"向后兼容两种 YAML 表示法"。

**规则**：
- 出现不规范旧表示必须通过一次性 migration 或直接重写生成
- 禁止在运行时 silently fallback 到旧表示法
- 新增/修改 schema 必须配套更新测试与迁移策略

**目的**：避免"apply 能写、detect 读不出"的另一个根本原因——YAML 表示法不一致。

#### 10.7.7 合同测试（必须）
每个 preset space 必须有 roundtrip contract tests。

**必须覆盖的测试场景**：
1. **对每个 profile**：apply → detect 必须命中同一 profile
2. **对 NOT_APPLICABLE**：若强行写入该 key（即使写默认值），detect 必须变 CUSTOM
3. **对 aliases**：同义词写法必须 detect 命中同一 profile

**要求**：
- 没有这些测试，不允许 merge
- 测试必须作为 CI 的一部分，不允许跳过

**目的**：通过自动化测试保证等价性公理（10.6.2）的严格执行，避免"apply 能写、detect 读不出"的 bug 进入代码库。

#### 10.7.8 单一注册表 + 薄封装 + 强制执行（Enforced）

**Single Source of Truth（单一真源）**：
所有 preset 维度必须在一个集中注册表中注册（声明式、唯一真源）。禁止"分散声明"或"临时绕过注册表"的维度实现。

**Thin Wrapper（薄封装）**：
compiler/detector 的每个维度入口必须是薄封装：只能把参数转交给通用引擎（ParamSpace），不得写维度特判逻辑。维度特判（aliases/tolerance/defaults/present/effective）只能存在于 ParamSpace 声明中。

**Enforcement Tests（强制执行测试）**：
必须有 CI/enforcement tests 防止回归：新增维度未注册 → 失败；wrapper 变厚/出现特判逻辑 → 失败；出现旧路径/猜测式识别 → 失败。这些测试必须可强制、可自动化，不允许手动审查替代。

#### 10.7.9 ParamSpace Variant 与适用范围

每个 preset 维度允许有多个 ParamSpace Variant。每个 Variant 必须显式声明 applies_to_step_types（适用 step_type 列表）。适用范围是唯一真相：apply/detect 只对该列表中的 step 生效；不在范围内的 step 视为 N/A（不 apply、不 detect、不参与 custom 判定）。禁止把"适用范围真相"散落在别处（例如 registry 映射表/receiver 隐式过滤）形成第二真相。

允许实现层从 variants 自动导出 step_type→variant 的索引/缓存用于查询或性能；但索引必须完全可由 variants 推导生成，不允许手工维护额外语义；真相仍在 variant 的 applies_to_step_types。

必须有 enforcement tests 保证：同一 (dimension, step_type) 不能被多个 variant 覆盖（禁止 overlap）、关键 step_type 必须被覆盖或明确声明 N/A。

### 10.8 ParamSpace / Preset Apply / Invariant Enforcement 宪法

#### 10.8.1 Single-writer 原则（不可违反）
每一个 YAML key 只能由一个 ParamSpace 写/删。任何"多个 ParamSpace 共同管理同一 key"的设计都是非法的。

**语义归属 ≠ 写入归属**：例如 degauss 语义依赖 occupation，但 writer 仍归 precision。

#### 10.8.2 ParamSpace 的统一职责模型
每个 ParamSpace 必须且只做三件事：

**Detect**：使用 matrix 判定 preset / CUSTOM，只依赖 YAML 真相 + Oracle（只读）。

**Preset Apply**：仅当用户显式选择该 ParamSpace 的 preset 时执行，使用同一套 matrix 写入值，NOT_APPLICABLE ⇒ must-absent。

**Custom Apply（Invariant Enforcement）**：永远执行，即使 detect 结果是 CUSTOM，即使用户没有修改该 ParamSpace，用于维护该 ParamSpace 负责 keys 的定义域 / 适用性不变量。默认行为是 no-op（pass）。

**禁止 "CUSTOM ⇒ 什么都不做" 的隐式假设**。

#### 10.8.3 NOT_APPLICABLE 的强语义
NOT_APPLICABLE ≠ WILDCARD。它隐含 must-absent：apply 必须删除该 key，detect 若 present ⇒ 冲突 ⇒ CUSTOM。

#### 10.8.4 Oracle 的定位（极窄）
Oracle 不是 guard，不负责 preset 判定，只提供"语义前提（semantic prerequisite）"。

Oracle 必须满足：
- 只读
- 只返回小离散值（bool / 小 enum）
- 不返回 preset id
- 不返回"建议值"

Oracle 只看 YAML 真相（当前内存态），不看 preset intention，不看 detect 的命中结果。

#### 10.8.5 Apply 执行顺序（必须）
Apply 必须分阶段执行：
1. **Prerequisite ParamSpaces**：会改变 applicability 的（如 occupation、step_type）
2. **Dependent ParamSpaces**：依赖 oracle 的（如 precision）

这是为了保证 Oracle 在 apply 时永远只读"最新 YAML 真相"。

#### 10.8.6 Precision / degauss 的宪法级约束（示例）
SYSTEM.degauss 的唯一 writer 是 Precision ParamSpace。

Precision ParamSpace 在 apply 时必须：
1. **永远执行 invariant enforcement**：若 degauss_applicability == false ⇒ 删除 degauss
2. **仅在用户显式设置 precision preset 时写入 degauss 值**：LOW / MED / HIGH ⇒ 0.01 / 0.02 / 0.03
3. **smearing 时不强制自动补 degauss（策略 A）**

#### 10.8.7 禁止事项（红线）
- ParamSpace 读取其他 ParamSpace 的 preset 结果
- Oracle 返回 preset id / 参数值
- 为了方便 detect/apply 而引入共享写入
- 为 custom case 写隐式特判逻辑而不通过 ParamSpace 统一接口

#### 10.8.8 Rationale（设计理由）
以下规则存在的理由，确保未来修改不显得任意：

- **CUSTOM 不能意味着 no-op**：即使 detect 结果为 CUSTOM，ParamSpace 仍必须维护其负责 keys 的定义域不变量（如 degauss 在非 smearing 时必须删除）。这保证 YAML 状态始终符合物理语义，避免残留无效参数。

- **Invariant enforcement 必须无条件执行**：不因 detect 结果、用户选择或 preset 应用状态而跳过。这确保系统始终处于一致状态，避免"部分应用"导致的不一致。

- **Oracle 必须读取 YAML 真相，而非 preset intention**：Oracle 只读当前内存中的 YAML 状态，不读取用户意图或 detect 结果。这保证 Oracle 的纯函数性质，避免循环依赖和状态不一致。

- **Single-writer 不可协商**：每个 key 只能由一个 ParamSpace 写入/删除，避免多写者导致的冲突、覆盖和数据丢失。即使语义上相关（如 degauss 与 occupation），写入权也必须唯一归属。

#### 10.8.9 ParamSpace Key Access 与 Ownership 强制规则

##### 10.8.9.1 ParamSpace Detect / Compile / Apply Key Access 规则（强制）

在 detect、compile、apply 的整个生命周期中：

**任一 ParamSpace 只能访问**：

- 自身声明的 owned keys；以及
- Oracle 明确暴露的语义前提（semantic prerequisites）。

**禁止**任何形式的：

- 直接读取；
- 间接读取；
- 或基于派生状态、缓存、聚合结果的方式，

访问其他 ParamSpace 的 owned keys。

**任何违反上述规则的行为，必须在运行时立即报错并中止执行。**

##### 10.8.9.2 Key Ownership 唯一性规则（运行时强制）

任一 YAML key 必须且只能被一个 ParamSpace 声明为 owned key。

若发生以下任一情况：

- 同一 key 被多个 ParamSpace 声明为 owned；或
- 同一 key 在系统生命周期内被多个 ParamSpace 作为 writer 访问；

**系统必须在初始化或运行时立即失败。**

该规则不可降级为 warning。

##### 10.8.9.3 非法行为的明确判定

以下行为均视为**非法的 ParamSpace 行为**：

- 访问未声明为自身 owned 的 YAML key（例如：occupation ParamSpace 读取或写入 degauss）；
- 通过 detect 结果、preset ID、聚合状态等方式绕过 key ownership 规则；
- 任何"语义等价但路径非法"的访问方式。

##### 10.8.9.4 Rationale（设计依据）

以下规则存在的依据，用于解释为何规则存在，而非指导实现：

- **Key ownership 是防止 ParamSpace 之间隐式耦合与语义污染的唯一可靠机制**：若无强制规则，不同 ParamSpace 可能通过共享 key 产生隐式依赖，导致系统行为不可预测、难以维护。

- **Detect 阶段的越权读取会导致 UI 状态不稳定、preset 结果不对称**：若 detect 阶段允许读取其他 ParamSpace 的 owned keys，会导致 detect 结果依赖于其他维度的状态，破坏 detect 的独立性与可复现性。

- **即使语义等价，绕过 Oracle 的直接访问仍然是非法的**：Oracle 是唯一合法的跨 ParamSpace 语义查询通道。直接访问虽然可能功能等价，但破坏了架构边界，导致未来无法统一管理跨维度依赖。

- **非-YAML 输入（如 structure、pseudo、派生 cutoff）不属于 ParamSpace key space**：
  - 它们是只读的、不可变的外部事实；
  - 不参与 detect / apply 写入；
  - 不存在 ownership 冲突的可能；
  - 因此不受 key-access 规则约束。

### 10.9 Advanced 用户路径

#### 10.9.1 Step 自治
Advanced 用户对 step 的任何手动修改：

- 直接写入 step.yml
- 不触发隐式继承、联动或修正

#### 10.9.2 显式继承
如提供继承能力，必须通过显式 UI 行为（如 dropdown copy），且仅为一次性复制。

### 10.10 Precision 的制度化（Context-dependent 参数）

#### 10.10.1 策略与数值分离
precision 的 ecut/kmesh 是 context-dependent（pseudo/structure），因此：ParamSpace profiles 存"策略参数"（如 multiplier / delta_k / conv_thr / nscf factor 等），具体数值由 resolver 在 apply/detect 时计算得到。

#### 10.10.2 Variant 适用范围
precision 必须用多个 variant 明确适用范围（例如 default PW steps / nscf / bands_pw）。每个 variant 必须显式声明 applies_to_step_types（见 10.7.9）。

#### 10.10.3 bands_pw 的 K_POINTS 排除规则
关键硬约束：bands_pw 的 precision variant 必须移除 K_POINTS（因为 bands_pw 的 K_POINTS 语义属于 kpath，不由 precision 管）。必须有回归测试保证：对 bands_pw 应用 precision 不得改变其 kpath K_POINTS（内容完全不变）。bands_pw 的 K_POINTS 属于 kpath 语义；若要 preset 化，应由独立的 kpath 维度管理，而非 precision。

### 10.11 读写策略（非宪法核心）

#### 10.11.1 当前实现
当前阶段允许：

- UI 操作即刻读写 step.yml

#### 10.11.2 未来优化
未来可引入内存缓冲、延迟写入等优化，但不得改变前述宪法语义。

### 10.12 禁止事项

禁止引入以下概念进入持久模型：

- **preset / workflow 的持久化**：preset 与 workflow 不得作为持久化实体存在于文件系统中（见 10.2.1）
- **anchor**：禁止引入 anchor 概念
- **family state**：禁止引入 family state 概念
- **baseline**：禁止引入 baseline 概念
- **implicit inheritance**：禁止引入隐式继承机制
- **A/B 双轨状态**：禁止引入"Selected vs Detected"双轨状态模型（见 10.4.2）
- **compiler version / schema version 作为运行语义依赖**：禁止将版本号作为运行语义依赖

### 10.13 解释权

当实现与宪法存在冲突时：

- 宪法优先
- 简洁性优先
- 数学可证明性优先于 UX 便利

### 10.14 宪法总结性原则（一句话）

**Execution is concrete; intention is inferred.**

所有计算只相信 step 参数；  
workflow 与 preset 只是对现状的解释，而非事实。

---

## 最后条款：修改原则
- 宪法的修改需谨慎，任何修改必须由项目作者审核。
- 实现细节、证据、TODO、改进建议等请放在英文文档中维护（避免宪法过时）。

---

## 本次修订摘要（2025-01-XX）

### 新增条款（ParamSpace / Preset Apply / Invariant Enforcement）
- **10.8 ParamSpace / Preset Apply / Invariant Enforcement 宪法**（全新章节）
  - **10.8.1 Single-writer 原则**：每个 YAML key 只能由一个 ParamSpace 写/删
  - **10.8.2 ParamSpace 的统一职责模型**：Detect、Preset Apply、Custom Apply（Invariant Enforcement）
  - **10.8.3 NOT_APPLICABLE 的强语义**：must-absent 规则
  - **10.8.4 Oracle 的定位**：只读、极窄、基于 YAML 真相
  - **10.8.5 Apply 执行顺序**：Prerequisite → Dependent 分阶段执行
  - **10.8.6 Precision / degauss 的宪法级约束**：作为示例说明 Single-writer 与 Invariant Enforcement
  - **10.8.7 禁止事项**：红线规则
  - **10.8.8 Rationale**：设计理由说明

### 历史新增条款（Preset Space 统一框架）
- **10.7 Preset Space 统一框架（声明式数据结构 + 通用算法）**
  - **10.7.1 统一框架原则**：禁止各维度单独写特判逻辑，必须使用声明式 ParamSpace
    - 解决的问题：避免每个维度各写一套 compiler/detector/receiver 导致反复出现"apply 能写、detect 读不出"的 bug
  - **10.7.2 ParamSpace 声明结构**：keys、defaults、aliases/canonicalizers、profiles、numeric tolerances
    - 解决的问题：occupations_scheme 类问题（gaussian/gauss 同义词、degauss 容差）、precision 类问题（数值容差、同义词处理）
  - **10.7.3 Cell 语义（三态）**：VALUE(v)、NOT_APPLICABLE、WILDCARD，满矩阵要求
    - 解决的问题：维度交叉污染（通过 keys 隔离）、NOT_APPLICABLE 的明确语义
  - **10.7.4 present vs effective_value**：detect 必须区分，解决参数缺失与默认值问题
    - 解决的问题：occupations_scheme 类问题（缺失 smearing/degauss 时的检测）、precision 类问题（缺失参数时的处理）
  - **10.7.5 apply 的 explicit_defaults 开关**：控制是否显式写入默认值
    - 解决的问题：Compiler 在"显式写入所有参数"与"依赖 QE 默认值"之间的选择
  - **10.7.6 零技术债原则**：禁止向后兼容两种 YAML 表示法，必须 migration
    - 解决的问题：YAML 表示法不一致导致的"apply 能写、detect 读不出"
  - **10.7.7 合同测试（必须）**：roundtrip 测试、NOT_APPLICABLE 测试、aliases 测试
    - 解决的问题：通过自动化测试保证等价性公理的严格执行，避免 bug 进入代码库

**解决的问题类型总结**：
- **occupations_scheme 类问题**：`gaussian`/`gauss` 同义词、`degauss=0.02` 容差匹配、缺失 `smearing`/`degauss` 时的检测
- **precision 类问题**：`ecutwfc`/`ecutrho` 整数舍入、`conv_thr` 容差、K_POINTS 匹配、缺失结构时的错误处理
- **维度交叉污染**：apply 一个维度影响其他维度（通过 ParamSpace 的 keys 隔离解决）
- **apply/detect 不一致**：通过统一框架和合同测试保证等价性

### 新增章节（历史）
- **第 10 章：计算模型与 Preset / Workflow 宪法**（全新章节）
  - 10.1 唯一真相原则（step.yml 是唯一可执行真相）
  - 10.2 Preset / Workflow 的法律地位（非实体原则）
  - 10.3 Compiler（正向生成）的宪法约束
  - 10.4 Detector B（反向检测）的宪法地位
  - 10.5 Detector B 的数学定义
  - 10.6 Compiler 与 Detector 的数学等价性
  - 10.7 Preset Space 统一框架（声明式数据结构 + 通用算法）
  - 10.8 ParamSpace / Preset Apply / Invariant Enforcement 宪法**新增**
  - 10.9 Advanced 用户路径
  - 10.10 Precision 的制度化（Context-dependent 参数）
  - 10.11 读写策略（非宪法核心）
  - 10.12 禁止事项（anchor / family state / baseline / implicit inheritance）
  - 10.13 解释权
  - 10.14 宪法总结性原则

### 历史新增章节
- **第 9 章：数据根目录、临时目录与可复现资产**（历史章节）
  - 9.1 两类根目录定义（`.qmatsuite/` 与 `.tmp/`）
  - 9.2 目录结构标准化
  - 9.3 QE Seed 机制
  - 9.4 QE 引擎解析（两态模型）
  - 9.5 settings.json 最小 Schema
  - 9.6 迁移说明

### 修改章节
- **第 7 章：伪势管理（Pseudopotentials）不变量**（全面重写）
- **第 9 章：数据根目录、临时目录与可复现资产**（QE 两态模型重构）
  - 9.2：移除 engine_id 语义，明确 bin 目录为唯一语义单元
  - 9.3：明确 QE seed 当前尚未支持程序内自动重装
  - 9.4：完全重写为"QE 引擎解析（两态模型）"，移除所有 engine_id、PATH fallback、自动发现逻辑
  - 9.5：简化为极简两态 schema（仅 `qe.bin_dir`）
  - 9.6：更新迁移规则，明确禁止 `repo_root/temp` 引用

### 关键语义变化
1. **选择主键改为 sha256**：明确 UI 下拉选择主键是 sha256（不是 sha_family）；sha_family 仅用于冲突处理、警告、跨 calc 引用更新。
2. **新增 7.5 小节：UI 选择与 calc.yml 持久化规则**：
   - 7.5.1 UI 展示/可选项规则（文件系统真实存在要求）
   - 7.5.2 默认选中（恢复选择）规则：不写 yml（只读恢复）
   - 7.5.3 用户主动选择时：写 triplet（三元必须一起写）
   - 7.5.4 Family-match edge case 的 UI 规则（不合并条目）
3. **重写 7.7 小节：Step0 冲突规则**：
   - 7.7.1 Step0 总原则（project source = noop）
   - 7.7.2 external 选择落地规则（sha256 相同/noop，sha_family 相同/overwrite，sha_family 不同/rename）
   - 7.7.3 stale sha 的定义与允许性
4. **更新 7.4 小节**：明确 sha256 vs sha_family 的语义与用途（sha256 是选择主键）。
5. **删除旧 7.5 小节**：移除"以 sha_family 为物理身份"的旧表述（已整合到 7.4 和 7.7）。
6. **删除旧 7.6 小节**：冲突规则已整合到 7.7。
7. **明确 UI 默认优先级动机**：在 7.5.1 中说明"优先贴近 runtime 实际，减少无意覆盖"。
8. **强调 project source noop**：在 7.7.1 中明确用户选择 project/pseudo 自身文件时 Step0 必须 noop。

### 变更摘要（sha_token → sha_family，历史）
- **sha_token 重命名为 sha_family**：术语更清晰，表示"家族"（物理等价组）而非"令牌"。
- **算法变更**：从"token 边界敏感"改为"空白字符完全移除"：
  - 旧算法：空白字符 split → 保留非空白 token → 单空格 join → SHA256
  - 新算法：移除所有空白字符（isspace()）→ 拼接剩余字符 → SHA256
  - 影响：`"12 3"` 和 `"1 23"` 现在产生相同的 sha_family（都变成 `"123"`），这是预期的行为。
- **其他语义不变**：dropdown 仍以 sha256 为选择主键；sha_family 仍仅用于警告、冲突处理、跨 calc 引用更新。

### 本次修订关键原则（第 10 章）
1. **唯一真相原则**：step.yml 是唯一可执行真相，不得包含 workflow / preset / provenance 等元数据。
2. **非实体原则**：workflow 与 preset 不是持久化实体，仅为运行时解释。
3. **Compiler 纯函数约束**：Compiler 是纯函数，仅依赖 step_type 和用户 options，必须完全重写参数。
4. **Detector B 唯一性**：Detector B 是唯一合法的状态判定来源，不存在 Selected vs Detected 双轨模型。
5. **数学等价性**：Compiler 与 Detector 必须满足数学等价性，并通过 unit tests 验证。
6. **禁止事项**：禁止 anchor / family state / baseline / implicit inheritance 等概念进入持久模型。

### 本次修订（2025-01-XX）：职责不对称性与等价性细化

#### 新增内容
- **10.3.1**：明确 Compiler 是规范化写入器的职责定位
- **10.3.4**：强化 Canonical Encoding 要求，必须显式写出所有关键参数（不得依赖默认值）
- **10.4.1**：明确 Detector B 是语义解释器的职责定位
- **10.5.3**：新增隐式默认语义的反向解释规则（Detector 必须支持）
- **10.6.1**：新增职责不对称性说明
- **10.6.2**：修订等价性公理，区分 Compiler 输出（严格等价）与非 Compiler 输出（宽容语义推断）
- **10.6.3**：细化等价性验证要求
- **10.9**：明确禁止 preset/workflow 持久化和 A/B 双轨状态

#### 关键变化
1. **职责不对称性**：
   - Compiler（规范化写入器）：将用户意图转换为显式、完整的参数表示
   - Detector（语义解释器）：从参数反向推断用户意图，包括隐式默认语义

2. **等价性要求细化**：
   - **Compiler 输出**：Detector 必须严格等价（`detect(compile_one(...)) == options`）
   - **非 Compiler 输出**：Detector 允许更宽容的语义推断（基于隐式默认语义）

3. **Canonical Encoding 强化**：
   - 必须显式写出所有关键参数
   - 不得依赖默认值（即使 QE 有默认值，也必须显式写入）

4. **隐式默认语义支持**：
   - Detector 必须支持隐式默认语义的反向解释
   - 示例：未写 `nspin` → 解释为 `nonspin`（等价于 `nspin = 1`）

### 本次修订（2025-01-XX）：ParamSpace Invariant Enforcement 宪法合并

#### 变更摘要
1. **新增 10.8 章节：ParamSpace / Preset Apply / Invariant Enforcement 宪法**：将独立的 ParamSpace Constitution 合并入全局宪法，作为第 10 章的子章节。包含 Single-writer 原则、ParamSpace 统一职责模型（Detect、Preset Apply、Custom Apply/Invariant Enforcement）、NOT_APPLICABLE 强语义、Oracle 定位（只读、极窄、基于 YAML 真相）、Apply 执行顺序（Prerequisite → Dependent）、Precision/degauss 示例、禁止事项和 Rationale（设计理由说明）。

2. **章节重新编号**：原 10.8-10.13 调整为 10.9-10.14。

3. **源文档标记为已合并**：`docs/paramspace_constitution_cn.md` 已添加弃用说明，指向全局宪法。

### 历史修订（2025-01-XX）：精确 apply、清理按钮、precision resolver 例外、variant 索引澄清、JSON enforcement、kpath 归属

#### 变更摘要
1. **修订 10.3.3：从"完全重写"改为"局部精确修改"**：Preset Apply 必须是局部精确修改，只允许修改该维度 ParamSpace Variant 明确声明的 keys，所有不归该 preset 维度管理的参数必须保持原样。明确说明如果未来需要"清理/归一化/删除多余参数"，应通过独立的清理功能实现，而不是 preset apply 的职责。

2. **修订 10.3.2：加入 precision resolver 的例外条款**：保留"通常 compiler 不得依赖 structure/pseudo"的原则，但允许少数维度（如 precision）通过明确命名的 resolver 依赖 context。resolver 必须纯函数、可审计、有合同测试。

3. **10.7.9 补一句：允许导出索引，但索引不是第二真相**：允许实现层从 variants 自动导出 step_type→variant 的索引/缓存用于查询或性能，但索引必须完全可由 variants 推导生成，不允许手工维护额外语义；真相仍在 variant 的 applies_to_step_types。

4. **JSON sanity-check 章节补充 enforcement 政策**：在"JSON 仅用于诊断工具"条款下补充：运行时可发 warning；对核心 step_types / 核心维度，必须有 enforcement tests（或 CI 约束）确保 variant 声称写入的 key 在 schema 中被接受，否则视为配置错误（fail）。

5. **precision 的 K_POINTS 规则补充 kpath 归属提示**：在 bands_pw 的 precision variant 必须移除 K_POINTS 的规则后补充：bands_pw 的 K_POINTS 属于 kpath 语义；若要 preset 化，应由独立的 kpath 维度管理，而非 precision。
