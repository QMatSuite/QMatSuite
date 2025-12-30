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
        <engine_id>/             # managed QE 引擎
          bin/
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
```

### 9.3 QE Seed 机制

#### 9.3.1 定义与用途
- **QE seed**：可重装介质，用于离线/快速重装 engine。
- **功能**：
  - 校验 hash（SHA256）
  - 支持回滚
  - 离线安装（无需重新下载）

#### 9.3.2 安装流程
1. **下载阶段**：下载到 `.tmp/downloads/`
2. **校验阶段**：校验 SHA256
3. **落盘阶段**：保存到 `.qmatsuite/seeds/qe/<seed_id>/`
4. **解包/安装阶段**：解包/安装到 `.qmatsuite/engines/qe/<engine_id>/`

#### 9.3.3 灾难恢复
- 如果 `engines/` 损坏：从 `seeds/qe/` 重新安装，无需重新下载。

### 9.4 引擎选择优先级

#### 9.4.1 优先级顺序（必须严格按此顺序）
1. **Project override**：若项目声明 `engine_id`，优先使用。
2. **用户显式选择**：`settings.json` 中记录的 `qe.discovered_engine_id`。
3. **用户默认**：`settings.json` 中的 `defaults.qe_engine_id`。
4. **Managed fallback**：最新已安装的 managed engine（`.qmatsuite/engines/qe/` 下）。
5. **PATH fallback**（可选）：仅当 `qe.allow_path_fallback=true` 时，搜索系统 PATH。
6. **否则**：提示安装/添加引擎。

#### 9.4.2 自动搜索规则
- **仅作为导入器/登记器**：搜索功能仅用于“导入/登记”外部引擎。
- **禁止“发现即启用”**：自动搜索到的引擎不得自动成为默认引擎。
- **搜索缓存**：写到 `.tmp/probe/`。

### 9.5 settings.json 最小 Schema

```json
{
  "version": "1.0",
  "defaults": {
    "qe_engine_id": "qe-7.5",
    "pseudo_set_id": "sssp-1.3.0-precision"
  },
  "qe": {
    "allow_path_fallback": false,
    "allow_auto_discover": false,
    "discovered_engine_id": null
  },
  "external_engines": []
}
```

**字段说明**：
- `version`：配置版本号
- `defaults.qe_engine_id`：默认 QE 引擎 ID
- `defaults.pseudo_set_id`：默认伪势集 ID
- `qe.allow_path_fallback`：是否允许 PATH fallback
- `qe.allow_auto_discover`：是否允许自动发现
- `qe.discovered_engine_id`：用户显式选择的 discovered engine ID
- `external_engines[]`：显式登记的外部引擎列表

**原则**：
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
| `temp/e2e/` | `.tmp/runs/` | E2E 测试运行目录迁移 |

#### 9.6.2 迁移规则
- 所有 `temp/` 下的持久化资产（pseudo_seed、pseudo 解包库）→ `.qmatsuite/`
- 所有 `temp/` 下的临时文件（test_outputs、e2e、matplotlib_tests）→ `.tmp/`
- 迁移后，代码中禁止再出现 `temp/` 路径。

---

## 最后条款：修改原则
- 宪法的修改需谨慎，任何修改必须由项目作者审核。
- 实现细节、证据、TODO、改进建议等请放在英文文档中维护（避免宪法过时）。

---

## 本次修订摘要（2025-01-XX）

### 新增章节
- **第 9 章：数据根目录、临时目录与可复现资产**（全新章节）
  - 9.1 两类根目录定义（`.qmatsuite/` 与 `.tmp/`）
  - 9.2 目录结构标准化
  - 9.3 QE Seed 机制
  - 9.4 引擎选择优先级
  - 9.5 settings.json 最小 Schema
  - 9.6 迁移说明

### 修改章节
- **第 7 章：伪势管理（Pseudopotentials）不变量**（全面重写）

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

### 变更摘要（sha_token → sha_family，2025-01-XX）
- **sha_token 重命名为 sha_family**：术语更清晰，表示"家族"（物理等价组）而非"令牌"。
- **算法变更**：从"token 边界敏感"改为"空白字符完全移除"：
  - 旧算法：空白字符 split → 保留非空白 token → 单空格 join → SHA256
  - 新算法：移除所有空白字符（isspace()）→ 拼接剩余字符 → SHA256
  - 影响：`"12 3"` 和 `"1 23"` 现在产生相同的 sha_family（都变成 `"123"`），这是预期的行为。
- **其他语义不变**：dropdown 仍以 sha256 为选择主键；sha_family 仍仅用于警告、冲突处理、跨 calc 引用更新。
