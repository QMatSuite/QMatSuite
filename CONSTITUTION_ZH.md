# QMatSuite 宪法（Constitution）

**版本**: 1.1  
**最后更新**: 2025-12-28  
**适用范围**: QMatSuite / QuantumVITAS v2 代码库

---

## 前言

本文档是 QMatSuite 项目的“宪法”（Constitution）。它只定义项目的最高规则、不变量、术语与真相层（Truth vs Info）。  
所有代码修改、架构决策、AI 辅助开发都必须遵守这些规则。

**重要说明**
- 本文档是仓库内**唯一的中文文档**，用于项目作者快速阅读。
- 除本文档外，所有代码、注释、文档默认语言为**英文**。除非作者明确要求，不新增其它中文文档或注释。
- 本文档只记录**规则与定义**，不记录实现细节（文件路径、行号、函数列表、证据摘录等应放入英文文档/ TODO）。

---

## 术语与真相层

### Truth vs Info
- **Truth（真相层）**：用于计算、可复现、必须稳定的事实与键（例如：ULID、SHA256、结构的 canonical form、单位约定）。
- **Info（信息层）**：用于展示、理解、提示、搜索的可变信息（例如：文件名、路径、slug、来源描述、UI 文案）。

### 身份（Identity）
- 资源身份以 **ULID** 为唯一标识。
- 伪势身份以 **SHA256（严格）** / **SHATOKEN（物理）** 为核心判定键（见第 6 节）。

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

### 6.2 SHATOKEN（物理相同 / 语义等价）
- SHATOKEN 用于“物理相同”的判定（语义等价）。
- 算法（宪法定义）：
  1) 以“任何空白字符”（空格/tab/换行/CRLF 等）对内容 split
  2) 丢弃空 token，仅保留非空白 token
  3) 用单个空格 join
  4) 对 join 后的文本做 SHA256
- 因此：
  - `"1    23"` 与 `"1 23"` → shatoken 相同
  - `"1    23"` 与 `"12  3"` → shatoken 不同

### 6.3 判定规则（必须）
- **shatoken 不同**：视为完全不同，不可混用。
- **shatoken 相同但 sha 不同**：视为物理一致；默认以标准库/权威来源的版本覆盖用户导入副本（例如 CRLF/LF 差异导致 sha 不同）。

---

## 7. Windows Toolchain：oneAPI + MKL + MPI（拒绝 MinGW 作为主路线）

### 7.1 主路线（必须）
- Windows 下专业/HPC 可交付路线：**原生 oneAPI + MKL + (MS-MPI / Intel MPI)**。

### 7.2 MinGW 不是主路线（政策）
- MinGW 路线不是主路线：往往更难（可能需要修改 QE 源码以通过）且性能不如 oneAPI+MKL。
- 本仓库当前未接入 Windows CI：不是技术不可行，仅为尚未完成；但路线选择必须明确写入宪法以防误导。

---

## 最后条款：修改原则
- 宪法的修改需谨慎，任何修改必须由项目作者审核。
- 实现细节、证据、TODO、改进建议等请放在英文文档中维护（避免宪法过时）。
