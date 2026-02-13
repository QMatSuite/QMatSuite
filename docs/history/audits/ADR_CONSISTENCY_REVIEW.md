# ADR 一致性审查报告

**审查日期**: 2025-01-XX  
**审查范围**: QMatSuite / QuantumVITAS v2 代码库  
**审查目标**: 验证代码实现是否符合 ADR 宪法/决策记录

---

## 执行摘要

本报告对代码库进行了全面审查，检查了 5 个核心 ADR 的实现情况。总体而言，代码库在 ULID 引用、几何规范化、bond detection 纯函数等方面有良好实现，但在以下方面需要改进：

1. **资源索引缓存机制缺失**：`build_resource_index()` 每次全量扫描，无持久化缓存
2. **QE Schema 存储不统一**：存在 ibrav/alat/lattice 混用，需要明确统一 schema
3. **SHATOKEN 实现存在但需文档化**：已有 sha_token 实现，但缺少 ADR 文档说明
4. **Windows Toolchain 文档缺失**：无明确文档说明 oneAPI + MKL 路线选择

---

## [A] ADR-001: ULID-only + Cache 索引

### 现状检查

#### ✅ 已实现部分

1. **ULID 引用机制**：
   - `src/quantumvitas/core/resolution.py` 实现了完整的 ULID 解析
   - `ResourceIndex` 类支持 ULID/slug/name/path 多策略解析
   - `project.qv.yml` 使用 ID-only 模型（见 `docs/SCHEMA.md`）

2. **项目根查找**：
   - `require_project_root()` 在 `src/quantumvitas/core/project_utils.py` 实现
   - 向上遍历查找 `project.qv.yml` marker

3. **资源扫描**：
   - `build_resource_index()` 扫描所有资源文件
   - 支持 calculations、steps、structures

#### ❌ 问题与缺失

1. **无持久化缓存**（Blocker）
   - **现象**：`build_resource_index()` 每次全量扫描文件系统
   - **位置**：`src/quantumvitas/core/resolution.py:368-523`
   - **影响**：大型项目（100+ 计算/结构）每次操作都扫描，性能差
   - **违反**：ADR-001 要求"必须有 cache（并且缓存失效策略要明确）"

2. **无缓存失效机制**（Important）
   - **现象**：Daemon 有内存缓存（`DaemonState._caches`），但无基于 mtime/hash 的持久化缓存失效
   - **位置**：`src/quantumvitas/daemon/server.py:82-156`
   - **影响**：文件修改后缓存可能过期，需要手动重建
   - **违反**：ADR-001 要求"缓存失效策略要明确"

3. **无一致性校验**（Nice）
   - **现象**：无检查重复 ULID、丢失实体、悬挂引用的机制
   - **位置**：`build_resource_index()` 仅扫描，不校验
   - **影响**：项目损坏时无法及时发现
   - **违反**：ADR-001 要求"一致性校验（重复 ULID、丢失实体、悬挂引用）"

4. **路径引用残留**（Nice）
   - **现象**：`resolve_id()` 仍支持 path 解析（策略 4）
   - **位置**：`src/quantumvitas/core/resolution.py:312-318`
   - **影响**：虽然向后兼容，但可能被误用
   - **建议**：保留但标记为 legacy，优先使用 ULID

### 修改建议

#### PR1: 实现资源索引持久化缓存

**目标**：添加基于 SQLite/JSON 的持久化缓存，支持 mtime/hash 失效

**改动文件**：
- `src/quantumvitas/core/resolution.py` - 添加 `ResourceIndexCache` 类
- `src/quantumvitas/core/cache.py` (新建) - 缓存管理逻辑
- `tests/unit/test_resource_index_cache.py` (新建) - 缓存测试

**实现方式**：
```python
# 伪代码示例
class ResourceIndexCache:
    def __init__(self, cache_dir: Path):
        self.cache_file = cache_dir / ".qv_index_cache.json"
        self.mtime_map: Dict[Path, float] = {}
    
    def is_valid(self, project_root: Path) -> bool:
        """检查缓存是否有效（基于 mtime）"""
        if not self.cache_file.exists():
            return False
        cache_data = json.loads(self.cache_file.read_text())
        for resource_path, cached_mtime in cache_data["mtime_map"].items():
            if Path(resource_path).stat().st_mtime != cached_mtime:
                return False
        return True
    
    def load(self) -> ResourceIndex:
        """从缓存加载索引"""
        ...
    
    def save(self, index: ResourceIndex, mtime_map: Dict[Path, float]):
        """保存索引到缓存"""
        ...
```

**验收**：
- `pytest tests/unit/test_resource_index_cache.py -v`
- 手动测试：修改资源文件后缓存自动失效

#### PR2: 添加一致性校验

**目标**：在 `build_resource_index()` 中添加校验逻辑

**改动文件**：
- `src/quantumvitas/core/resolution.py` - 添加 `validate_resource_index()` 函数
- `tests/unit/test_resource_index_validation.py` (新建)

**验收**：
- 测试重复 ULID 检测
- 测试悬挂引用检测（calculation.yaml 引用不存在的 structure_id）

---

## [B] ADR-002/003: 几何宪法 + Bond 纯函数

### 现状检查

#### ✅ 已实现部分

1. **单次 Canonicalization**：
   - `canonicalize_structure_in_place()` 仅在入口点调用
   - 文档明确：`docs/CANONICALIZATION_DESIGN.md`、`docs/BOND_DETECTION_NOTES.md`
   - 入口点：`build_display_atoms()`, `visualize_structure()`, `plot_structure_3d()`

2. **Bond Detection 纯函数**：
   - `build_bonds_bruteforce()`, `build_bonds_cell_list()` 无副作用
   - 文档明确说明：`docs/BOND_DETECTION_NOTES.md:102-106`
   - 测试覆盖：`tests/unit/test_canonicalization_contract.py`

3. **Boundary Atoms 处理**：
   - `generate_boundary_atoms()` 不 canonicalize 图像原子
   - 使用 `BOUNDARY_FRAC_TOL = 1e-6`（文档中为 1e-8，需确认）

#### ⚠️ 潜在问题

1. **Canonicalization 算法不一致**（Important）
   - **现象**：`CANONICALIZATION_DESIGN.md` 描述与代码实现可能不一致
   - **位置**：
     - 文档：`docs/CANONICALIZATION_DESIGN.md:57-95` 描述"整数 snapping + modulo + boundary snapping"
     - 代码：`src/quantumvitas/analysis/structure_viz.py:256-291` 使用 `wrap_fractional_coords_shifted()`
   - **影响**：文档与实现不同步，可能导致误解
   - **建议**：检查代码实现，更新文档或代码使其一致

2. **BOUNDARY_FRAC_TOL 值不一致**（Nice）
   - **现象**：
     - 文档：`BOND_DETECTION_NOTES.md:72` 说 `BOUNDARY_FRAC_TOL = 1e-8`
     - 代码：`src/quantumvitas/analysis/structure_viz.py:160` 为 `BOUNDARY_FRAC_TOL = 1e-6`
   - **影响**：文档与代码不一致
   - **建议**：统一为 1e-8（文档值更保守）

3. **跨平台 Bond Count 测试缺失**（Nice）
   - **现象**：无专门测试验证不同平台（Linux/macOS/Windows）bond count 一致性
   - **位置**：`tests/unit/test_structure_viz.py` 有测试但无跨平台标记
   - **建议**：添加 `@pytest.mark.platform` 标记的跨平台测试

### 修改建议

#### PR3: 统一 Canonicalization 文档与实现

**目标**：确保文档描述与代码实现一致

**改动文件**：
- `src/quantumvitas/analysis/structure_viz.py` - 检查并统一 `BOUNDARY_FRAC_TOL` 值
- `docs/CANONICALIZATION_DESIGN.md` - 更新算法描述以匹配实现
- `docs/BOND_DETECTION_NOTES.md` - 统一 `BOUNDARY_FRAC_TOL` 值

**验收**：
- `pytest tests/unit/test_canonicalization_contract.py -v`
- 手动验证：Si 2×2×2 supercell bond count = 18（稳定）

#### PR4: 添加跨平台 Bond Count 测试

**目标**：确保 bond detection 在不同平台结果一致

**改动文件**：
- `tests/unit/test_structure_viz.py` - 添加跨平台测试
- `tests/integration/test_cross_platform_bonds.py` (新建)

**验收**：
- CI 在 Linux/macOS 上运行，验证 bond count 一致

---

## [C] ADR-002 扩展: QE 输入/JSON 存储 Schema

### 现状检查

#### ✅ 已实现部分

1. **QE 输入解析**：
   - `structure_from_qe_input()` 支持 ibrav 和 CELL_PARAMETERS
   - 位置：`src/quantumvitas/io/structure_io.py:324-372`

2. **JSON 存储**：
   - Structure JSON 使用 pymatgen 标准格式
   - 包含 `lattice.matrix`（绝对单位）和 `sites[].abc`（frac 坐标）

#### ❌ 问题与缺失

1. **Schema 不统一**（Important）
   - **现象**：
     - QE 输入：支持 ibrav、alat、CELL_PARAMETERS 多种表示
     - JSON 存储：使用 lattice matrix + frac coords（正确）
     - 但无明确文档说明"JSON 只存 lattice + frac，不存 ibrav"
   - **位置**：
     - `src/quantumvitas/io/structure_io.py:324-372` - QE 解析
     - `src/quantumvitas/io/structure_io.py:70-110` - JSON 写入
   - **影响**：可能有人误以为 JSON 也存 ibrav
   - **违反**：ADR-002 要求"JSON 只存 cell parameters（绝对单位）+ frac 坐标"

2. **Unit 真相不明确**（Nice）
   - **现象**：无明确文档说明 lattice matrix 单位（应为 Å）
   - **位置**：`docs/SCHEMA.md` 未明确说明单位
   - **建议**：在 `docs/SCHEMA.md` 中明确说明

3. **向后兼容迁移策略缺失**（Nice）
   - **现象**：如果未来需要迁移旧项目（假设有 ibrav 存储），无迁移脚本
   - **建议**：当前无问题，但应记录在 ADR 文档中

### 修改建议

#### PR5: 明确 QE Schema 存储规范

**目标**：在文档中明确 JSON 存储规范，添加 schema 验证

**改动文件**：
- `docs/SCHEMA.md` - 添加 Structure JSON Schema 章节
- `src/quantumvitas/io/structure_io.py` - 添加 schema 验证注释
- `docs/QE_SCHEMA_STORAGE.md` (新建) - 详细说明 QE → JSON 转换规则

**Schema 文档示例**：
```markdown
## Structure JSON Schema

### 规范
- `lattice.matrix`: 3×3 矩阵，单位：Å（绝对单位）
- `sites[].abc`: 分数坐标 [0, 1)
- **不存储**：ibrav、alat、celldm 等 QE 特定表示

### QE → JSON 转换
- ibrav != 0 → 转换为 lattice matrix
- alat 单位 → 转换为 Å
- 所有坐标 → 转换为 frac coords
```

**验收**：
- 手动验证：QE 输入（ibrav=1）→ JSON → 读取，结果一致

---

## [D] ADR-004/005: Pseudopotential SHA vs SHATOKEN

### 现状检查

#### ✅ 已实现部分

1. **SHA256 实现**：
   - `compute_sha256_file()` 在 `src/quantumvitas/core/pseudo_provenance.py:56-67`
   - 用于去重存储

2. **SHATOKEN 实现**：
   - `compute_sha_token_file()` 在 `src/quantumvitas/core/pseudo_libinfo.py:95-110`
   - 算法：whitespace 规范化（split + join）→ SHA256
   - 用于"物理相同"判定

3. **Provenance 匹配**：
   - `resolve_pseudo_provenance()` 支持 sha256 和 sha_token 匹配
   - 位置：`src/quantumvitas/core/pseudo_provenance.py:253-344`

#### ⚠️ 潜在问题

1. **SHATOKEN 算法风险未评估**（Important）
   - **现象**：当前算法（whitespace 规范化）可能无法处理所有"物理相同"情况
   - **位置**：`src/quantumvitas/core/pseudo_libinfo.py:71-92`
   - **风险**：
     - 注释差异（如 `# comment`）会导致 sha_token 不同
     - 字段顺序差异（如 XML 属性顺序）会导致 sha_token 不同
   - **建议**：在 ADR 文档中明确算法边界和风险

2. **无 ADR 文档**（Important）
   - **现象**：代码已实现，但无 `docs/adr/ADR-004.md` 或 `docs/adr/ADR-005.md`
   - **影响**：后来者可能不理解 SHA vs SHATOKEN 的区别
   - **建议**：创建 ADR 文档

3. **Alias → SHA 映射不完整**（Nice）
   - **现象**：`PseudoOccurrenceRef` 有 `basename`，但无全局 alias 映射
   - **位置**：`src/quantumvitas/core/pseudo_provenance.py:26-40`
   - **建议**：如果需要，可以添加 alias 索引

4. **Manifest 驱动下载未检查**（Nice）
   - **现象**：未找到 manifest 驱动的下载实现
   - **建议**：如果未实现，应在 ADR 中标记为 TODO

### 修改建议

#### PR6: 创建 ADR-004/005 文档并评估 SHATOKEN 风险

**目标**：文档化 SHA vs SHATOKEN 设计决策，评估算法风险

**改动文件**：
- `docs/adr/ADR-004.md` (新建) - SHA256 身份设计
- `docs/adr/ADR-005.md` (新建) - SHATOKEN 语义等价设计
- `src/quantumvitas/core/pseudo_libinfo.py` - 添加算法边界注释

**ADR-005 内容示例**：
```markdown
# ADR-005: Pseudopotential SHATOKEN for Semantic Equivalence

## 状态
Accepted

## 上下文
需要区分"bitwise identical"（SHA256）和"物理相同"（SHATOKEN）。

## 决策
使用 whitespace 规范化 + SHA256 作为 sha_token。

## 算法
1. 读取文件为 UTF-8 文本
2. 按任意 whitespace split
3. 用单个空格 join
4. SHA256 hash

## 已知限制
- **注释差异**：`# comment` 会导致 sha_token 不同
- **字段顺序**：XML 属性顺序差异会导致 sha_token 不同
- **风险等级**：Low（大多数物理相同文件仅 whitespace 差异）

## 后果
- ✅ 处理 CRLF/LF、多余空格
- ⚠️ 无法处理注释/顺序差异（需要更复杂的解析）
```

**验收**：
- 文档审查
- 运行现有测试：`pytest tests/unit/test_pseudo_provenance.py -v`

---

## [E] ADR-007: Windows Toolchain (oneAPI + MKL)

### 现状检查

#### ✅ 已实现部分

1. **Windows 支持**：
   - 代码中有 Windows 路径处理（`.exe` 扩展名）
   - 位置：`src/quantumvitas/core/engines/qe.py:154`, `tests/unit/test_qe_executable_detection.py`

#### ❌ 问题与缺失

1. **无 ADR 文档**（Blocker）
   - **现象**：无 `docs/adr/ADR-007.md` 说明 Windows toolchain 选择
   - **影响**：后来者/AI 可能误选 MinGW 路线
   - **违反**：ADR-007 要求"需要补充决策记录/文档"

2. **无 Windows CI 测试**（Important）
   - **现象**：`.github/workflows/tests.yml` 只有 ubuntu-22.04 和 macos-14
   - **影响**：无法验证 Windows 构建
   - **建议**：添加 Windows runner（如果 GitHub Actions 支持）

3. **无 Windows Staging 文档**（Important）
   - **现象**：无文档说明 Windows 下的 dll 收集、dumpbin 探测
   - **建议**：创建 `docs/WINDOWS_TOOLCHAIN.md`

4. **MinGW 残留检查**（Nice）
   - **现象**：代码库中无 MinGW 相关代码（✅ 好）
   - **建议**：在 ADR 文档中明确说明"拒绝 MinGW"的原因

### 修改建议

#### PR7: 创建 ADR-007 文档和 Windows Toolchain 指南

**目标**：文档化 Windows toolchain 选择，防止误选 MinGW

**改动文件**：
- `docs/adr/ADR-007.md` (新建) - Windows Toolchain 决策记录
- `docs/WINDOWS_TOOLCHAIN.md` (新建) - Windows 构建指南
- `README.md` - 添加 Windows 构建说明链接

**ADR-007 内容示例**：
```markdown
# ADR-007: Windows Toolchain - oneAPI + MKL (拒绝 MinGW)

## 状态
Accepted

## 上下文
Windows 上构建 QE 需要选择 toolchain。

## 决策
使用原生 oneAPI + MKL + (MS-MPI/Intel MPI)，拒绝 MinGW。

## 理由
1. **MinGW 路线更难**：
   - 需要改 QE 源码（UPF XML reader、动态分配数组等）
   - 存在 allocate/shape/解析相关的坑
2. **性能更差**：
   - 编译出来性能不如 oneAPI+MKL
3. **可交付性**：
   - oneAPI + MKL 是"可交付 + HPC 级别"的路线

## 后果
- ✅ 性能好、稳定
- ⚠️ 需要安装 oneAPI（较大）
- ✅ 与 HPC 环境一致
```

**验收**：
- 文档审查
- 如果有 Windows 环境，手动验证构建流程

---

## 最小补丁计划（分 6 个小 PR）

### PR1: 资源索引持久化缓存
- **目标**：实现基于 JSON 的持久化缓存，支持 mtime 失效
- **改动文件**：
  - `src/quantumvitas/core/cache.py` (新建)
  - `src/quantumvitas/core/resolution.py` - 集成缓存
  - `tests/unit/test_resource_index_cache.py` (新建)
- **验收**：`pytest tests/unit/test_resource_index_cache.py -v`

### PR2: 资源索引一致性校验
- **目标**：添加重复 ULID、悬挂引用检测
- **改动文件**：
  - `src/quantumvitas/core/resolution.py` - 添加 `validate_resource_index()`
  - `tests/unit/test_resource_index_validation.py` (新建)
- **验收**：`pytest tests/unit/test_resource_index_validation.py -v`

### PR3: 统一 Canonicalization 文档与实现
- **目标**：确保文档与代码一致
- **改动文件**：
  - `src/quantumvitas/analysis/structure_viz.py` - 统一 `BOUNDARY_FRAC_TOL = 1e-8`
  - `docs/CANONICALIZATION_DESIGN.md` - 更新算法描述
  - `docs/BOND_DETECTION_NOTES.md` - 统一值
- **验收**：`pytest tests/unit/test_canonicalization_contract.py -v`

### PR4: 跨平台 Bond Count 测试
- **目标**：确保 bond detection 跨平台一致
- **改动文件**：
  - `tests/integration/test_cross_platform_bonds.py` (新建)
- **验收**：CI 在 Linux/macOS 上运行

### PR5: 明确 QE Schema 存储规范
- **目标**：文档化 JSON 存储规范
- **改动文件**：
  - `docs/SCHEMA.md` - 添加 Structure JSON Schema 章节
  - `docs/QE_SCHEMA_STORAGE.md` (新建)
- **验收**：文档审查

### PR6: 创建 ADR-004/005/007 文档
- **目标**：文档化 Pseudopotential 和 Windows Toolchain 决策
- **改动文件**：
  - `docs/adr/ADR-004.md` (新建)
  - `docs/adr/ADR-005.md` (新建)
  - `docs/adr/ADR-007.md` (新建)
  - `docs/WINDOWS_TOOLCHAIN.md` (新建)
- **验收**：文档审查

---

## 测试与验收

### 需要新增的测试

1. **资源索引缓存测试**：
   - `tests/unit/test_resource_index_cache.py`
   - 测试：缓存创建、mtime 失效、并发访问

2. **资源索引一致性校验测试**：
   - `tests/unit/test_resource_index_validation.py`
   - 测试：重复 ULID、悬挂引用、丢失实体

3. **跨平台 Bond Count 测试**：
   - `tests/integration/test_cross_platform_bonds.py`
   - 测试：Si 2×2×2 supercell bond count = 18（Linux/macOS）

4. **Pseudopotential SHA/SHATOKEN 测试**（已有，需加强）：
   - `tests/unit/test_pseudo_provenance.py`
   - 建议：添加注释差异、字段顺序差异的边界测试

### Smoke 测试命令

```bash
# PR1: 资源索引缓存
pytest tests/unit/test_resource_index_cache.py -v

# PR2: 一致性校验
pytest tests/unit/test_resource_index_validation.py -v

# PR3: Canonicalization
pytest tests/unit/test_canonicalization_contract.py -v
pytest tests/unit/test_structure_viz.py::test_si_supercell_bond_count_stability -v

# PR4: 跨平台 Bond Count（需 CI）
pytest tests/integration/test_cross_platform_bonds.py -v

# PR5: Schema（手动验证）
python -c "from quantumvitas.io import read_structure, write_structure; ..."

# PR6: 文档（手动审查）
# 检查 docs/adr/ADR-*.md 是否存在且内容完整
```

### Regression 测试

运行完整测试套件确保无回归：
```bash
pytest tests/unit/ tests/integration/ -v --tb=short
```

---

## 文档补全建议

### 必须创建的文档

1. **`docs/adr/ADR-001.md`** - ULID-only + Cache 索引
   - 说明：为什么需要 ULID、为什么需要缓存、缓存失效策略

2. **`docs/adr/ADR-002.md`** - 几何宪法（已有 `CANONICALIZATION_DESIGN.md`，可链接）

3. **`docs/adr/ADR-003.md`** - Bond 纯函数（已有 `BOND_DETECTION_NOTES.md`，可链接）

4. **`docs/adr/ADR-004.md`** - Pseudopotential SHA256 身份

5. **`docs/adr/ADR-005.md`** - Pseudopotential SHATOKEN 语义等价

6. **`docs/adr/ADR-007.md`** - Windows Toolchain 选择

### 建议增强的文档

1. **`docs/SCHEMA.md`** - 添加 Structure JSON Schema 详细说明（单位、格式）

2. **`docs/QE_SCHEMA_STORAGE.md`** (新建) - QE → JSON 转换规则

3. **`docs/WINDOWS_TOOLCHAIN.md`** (新建) - Windows 构建指南

4. **`docs/CACHE_STRATEGY.md`** (新建) - 资源索引缓存策略（mtime/hash 失效）

---

## 风险等级总结

| ADR | 问题 | 风险等级 | 优先级 |
|-----|------|---------|--------|
| A | 无持久化缓存 | **Blocker** | P0 |
| A | 无缓存失效机制 | Important | P1 |
| A | 无一致性校验 | Nice | P2 |
| B | Canonicalization 文档不一致 | Important | P1 |
| B | BOUNDARY_FRAC_TOL 值不一致 | Nice | P2 |
| C | Schema 不统一 | Important | P1 |
| D | SHATOKEN 算法风险未评估 | Important | P1 |
| D | 无 ADR 文档 | Important | P1 |
| E | 无 ADR 文档 | **Blocker** | P0 |
| E | 无 Windows CI | Important | P1 |

---

## 总结

代码库在核心功能（ULID 引用、canonicalization、bond detection）方面实现良好，但在以下方面需要改进：

1. **缓存机制**：必须实现持久化缓存以支持大型项目
2. **文档完整性**：需要创建 ADR 文档，特别是 Windows Toolchain 和 Pseudopotential 设计
3. **一致性**：统一文档与实现，确保跨平台行为一致

建议按优先级执行 6 个 PR，预计工作量：
- PR1 (缓存): 2-3 天
- PR2 (校验): 1 天
- PR3 (文档统一): 0.5 天
- PR4 (跨平台测试): 1 天
- PR5 (Schema 文档): 0.5 天
- PR6 (ADR 文档): 1-2 天

**总计**: 约 6-8 个工作日

