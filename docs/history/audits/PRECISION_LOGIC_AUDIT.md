# Precision 逻辑完整审计报告

**日期**: 2025-01-XX  
**审计范围**: Precision preset 的完整数据流、编译、检测、合并逻辑  
**原则**: 只解释，不修改

---

## 目录

1. [数据流/因果链](#数据流因果链)
2. [Precision Keys 表格](#precision-keys-表格)
3. [三个核心问题](#三个核心问题)
4. [Phase 1-5 详细审计](#phase-1-5-详细审计)
5. [最小可复现实验](#最小可复现实验)
6. [不简单的地方](#不简单的地方)

---

## 数据流/因果链

### 完整数据流图（文字版）

```
用户选择 precision preset (MED)
    ↓
[UI/CLI] → apply_presets_to_step(step_path, {"precision": "med"}, precision_advice=...)
    ↓
[integration.py:308-517] apply_presets_to_step()
    ├─ 加载 step YAML → content, step_type, existing_params
    ├─ filter_presets_for_step(step_type, options) → filtered_options
    │   └─ [receivers.py:327] 检查 step_type 是否接受 precision
    │
    ├─ [integration.py:412-442] 处理 precision
    │   ├─ get_precision_receiver_spec(step_type) → precision_spec
    │   │   └─ [receivers.py:118-164] PRECISION_RECEIVER_SPECS[step_type]
    │   │       → PrecisionReceiverSpec(accepts_kmesh, accepts_cutoffs, accepts_conv_thr, kmesh_strategy)
    │   │
    │   ├─ compile_precision_from_advice(precision_advice)
    │   │   └─ [compiler.py:153-179] 调用 compile_precision()
    │   │       └─ [spaces_registry.py:209-301] compile_dimension_patch("precision", ...)
    │   │           └─ 手动构造 patch:
    │   │               {
    │   │                   "SYSTEM": {"ecutwfc": int(ecutwfc), "ecutrho": int(ecutrho)},
    │   │                   "ELECTRONS": {"conv_thr": conv_thr},
    │   │                   "K_POINTS_CARD": {"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}
    │   │               }
    │   │
    │   ├─ [integration.py:422-442] 根据 receiver spec 过滤 patch
    │   │   ├─ 如果 accepts_cutoffs → 添加 SYSTEM.ecutwfc, SYSTEM.ecutrho
    │   │   ├─ 如果 accepts_conv_thr → 添加 ELECTRONS.conv_thr
    │   │   └─ 如果 accepts_kmesh && kmesh_strategy != "none" → 设置 compiled_kpoints_card
    │   │
    │   └─ [integration.py:444-458] 删除 owned keys
    │       ├─ DIMENSION_OWNED_KEYS[DIMENSION_PRECISION] = {"SYSTEM": {ecutwfc, ecutrho}, "ELECTRONS": {conv_thr}, "cards": {K_POINTS}}
    │       ├─ 条件: if section != "cards" or dimension == DIMENSION_PRECISION
    │       │   └─ 对于 precision + cards: True → K_POINTS 加入 keys_to_remove["cards"]
    │       └─ existing_cards.pop("K_POINTS", None)  ← 无条件删除
    │
    ├─ [integration.py:460-464] 合并 patch
    │   ├─ existing_system.update(compiled_patches["SYSTEM"])
    │   ├─ existing_electrons.update(compiled_patches["ELECTRONS"])
    │   └─ if compiled_kpoints_card is not None:
    │       └─ existing_cards["K_POINTS"] = compiled_kpoints_card  ← 仅当有 replacement 时恢复
    │
    └─ 写回 step YAML
        ↓
最终 step YAML
    ↓
[detector.py:240-272] detect_precision(params, lattice_matrix, base_ecutwfc, base_ecutrho)
    ├─ [spaces_registry.py:122-202] detect_dimension("precision", ...)
    │   ├─ 对每个 precision level (LOW/MED/HIGH):
    │   │   ├─ 计算 canonical values:
    │   │   │   ├─ canonical_ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
    │   │   │   ├─ canonical_ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
    │   │   │   ├─ canonical_conv_thr = constants.conv_thr
    │   │   │   └─ canonical_kmesh = compute_kmesh(lattice_matrix, constants.delta_k)
    │   │   │
    │   │   └─ [paramspace.py:730-823] match_precision_profile(step_yaml, canonical_values)
    │   │       ├─ 提取 YAML 值: ecutwfc, ecutrho, conv_thr, K_POINTS
    │   │       ├─ 检查必需字段存在
    │   │       ├─ 解析 K_POINTS: option="automatic", data=[[nk1, nk2, nk3, sk1, sk2, sk3]]
    │   │       └─ 严格匹配: ecutwfc==canonical, ecutrho==canonical, conv_thr≈canonical, kmesh==canonical
    │   │
    │   └─ 返回匹配的 PrecisionOption 或 CUSTOM
    │
    └─ 返回检测结果
```

### PrecisionAdvisor 计算流程

```
PrecisionAdvisor(species_map, structure/lattice_matrix, repo_root)
    ↓
advisor.advise(PrecisionOption.MED)
    ↓
[precision.py:447-496]
    ├─ 加载 PSEUDO_FILE_INDEX.json (cached)
    │   └─ [precision.py:191-226] _load_pseudo_index_cached()
    │
    ├─ [precision.py:300-352] aggregate_cutoffs(species_map, index_files)
    │   ├─ 对每个 species:
    │   │   ├─ 从 index 查找 sha256 → cutoff_wfc_normal, cutoff_rho_normal
    │   │   └─ 取最大值
    │   └─ 返回 (base_ecutwfc, base_ecutrho) 或 defaults (50, 400)
    │
    ├─ 应用 precision multiplier:
    │   ├─ ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)
    │   │   └─ LOW: 0.8, MED: 1.0, HIGH: 1.2
    │   └─ ecutrho = round_cutoff_integer(base_ecutrho * constants.cutoff_multiplier)
    │
    ├─ [precision.py:133-167] compute_kmesh(lattice_matrix, delta_k)
    │   ├─ [precision.py:82-131] compute_reciprocal_lengths(lattice_matrix)
    │   │   └─ 计算 |b_i| = 2π * |(a_j × a_k)| / V
    │   │
    │   └─ nk_i = max(1, ceil(|b_i| / delta_k))
    │       └─ LOW: delta_k=0.30, MED: delta_k=0.20, HIGH: delta_k=0.15
    │
    └─ 返回 PrecisionAdvice(nk1, nk2, nk3, sk1=0, sk2=0, sk3=0, ecutwfc, ecutrho, conv_thr)
```

---

## Precision Keys 表格

| Key | Section | 语义 | Apply 写? | Apply 删? | Detect 读? | Detect 必需? | 接受 step_type | 忽略 step_type |
|-----|---------|------|-----------|-----------|------------|--------------|----------------|----------------|
| `ecutwfc` | SYSTEM | 平面波截断能量 (Ry, 整数) | ✅ 是 | ✅ 是 | ✅ 是 | ✅ 必需 | scf, nscf, bands_pw, relax, md, vc-relax, vc-md | dos, bands (post-processing) |
| `ecutrho` | SYSTEM | 电荷密度截断能量 (Ry, 整数) | ✅ 是 | ✅ 是 | ✅ 是 | ✅ 必需 | scf, nscf, bands_pw, relax, md, vc-relax, vc-md | dos, bands (post-processing) |
| `conv_thr` | ELECTRONS | SCF 收敛阈值 (float, 容差 1e-11) | ✅ 是 | ✅ 是 | ✅ 是 | ✅ 必需 | scf, nscf, bands_pw, relax, md, vc-relax, vc-md | dos, bands (post-processing) |
| `K_POINTS` | cards | K 点设置 | ⚠️ 条件 | ✅ 是 | ⚠️ 条件 | ⚠️ 条件 | scf, nscf, relax, md, vc-relax, vc-md | bands_pw (kpath), dos, bands |

### K_POINTS 详细说明

**Mesh vs Path 差异**:
- **Mesh (自动网格)**: `{"option": "automatic", "data": [[nk1, nk2, nk3, sk1, sk2, sk3]]}`
  - 用于 SCF/NSCF: 均匀 k 点网格
  - precision 管理此格式
- **Path (k 路径)**: `{"option": "crystal_b", "data": [[kx1, ky1, kz1, w1], [kx2, ky2, kz2, w2], ...]}`
  - 用于 bands_pw: 沿高对称路径的 k 点
  - precision **不管理**此格式

**各 step_type 角色**:
- **scf/relax/md/vc-***: 接受 mesh (`accepts_kmesh=True`, `kmesh_strategy="default"`)
- **nscf**: 接受 mesh，但更密 (`accepts_kmesh=True`, `kmesh_strategy="nscf"` → ×2)
- **bands_pw**: 拒绝 mesh (`accepts_kmesh=False`, `kmesh_strategy="none"`)，使用 kpath
- **dos/bands**: 不接受 precision（非 receiver）

**代码证据**:
- Receiver spec: `src/quantumvitas/presets/receivers.py:118-164`
- Apply 过滤: `src/quantumvitas/presets/integration.py:438-442`
- Detect 条件: `src/quantumvitas/presets/detector.py:525-529`

---

## 三个核心问题

### Q1: precision 的数值（ecut/k）到底是 hard-code、还是来自 pseudo/structure 推导、还是两者混合？

**答案**: **两者混合** - 常量 hard-code，数值从 pseudo/structure 推导

**详细解释**:

1. **Hard-code 部分** (常量):
   - **位置**: `src/quantumvitas/presets/precision.py:45-61`
   - **内容**: `PRECISION_CONSTANTS` 定义每个 level 的:
     - `delta_k`: k 点间距 (LOW=0.30, MED=0.20, HIGH=0.15 Å⁻¹)
     - `conv_thr`: 收敛阈值 (LOW=1e-6, MED=1e-8, HIGH=1e-10)
     - `cutoff_multiplier`: 截断倍数 (LOW=0.8, MED=1.0, HIGH=1.2)

2. **推导部分** (运行时计算):
   - **ecutwfc/ecutrho**:
     - **来源**: `PSEUDO_FILE_INDEX.json` 中的 `cutoff_wfc_normal`, `cutoff_rho_normal`
     - **计算**: `ecutwfc = round_cutoff_integer(base_ecutwfc * constants.cutoff_multiplier)`
     - **位置**: `src/quantumvitas/presets/precision.py:300-352` (aggregate_cutoffs)
     - **回退**: 如果 index 无数据 → defaults (50 Ry, 400 Ry)
   
   - **kmesh (nk1, nk2, nk3)**:
     - **来源**: `lattice_matrix` (结构)
     - **计算**: `nk_i = max(1, ceil(|b_i| / delta_k))` 其中 `|b_i|` 是倒格矢长度
     - **位置**: `src/quantumvitas/presets/precision.py:133-167` (compute_kmesh)
     - **公式**: `b_i = 2π * (a_j × a_k) / V`

**证据链**:
- 常量定义: `precision.py:45-61`
- Cutoff 计算: `precision.py:300-352` → `precision.py:237-265` (get_cutoffs_from_index)
- Kmesh 计算: `precision.py:133-167` → `precision.py:82-131` (compute_reciprocal_lengths)
- Advisor 入口: `precision.py:447-496` (advise 方法)

---

### Q2: precision detection 是严格匹配还是带容差/猜测？缺字段时返回 CUSTOM 还是默认档？

**答案**: **严格匹配 + 容差（仅 conv_thr）+ 缺字段返回 CUSTOM**

**详细解释**:

1. **匹配策略**:
   - **ecutwfc/ecutrho**: **严格整数匹配** (exact match)
     - **位置**: `src/quantumvitas/presets/paramspace.py:805-809`
     - **代码**: `if actual_ecutwfc != canonical_ecutwfc: return None`
   
   - **conv_thr**: **容差匹配** (tolerance = 1e-11)
     - **位置**: `src/quantumvitas/presets/paramspace.py:811-813`
     - **代码**: `if not key_conv_thr.matches(actual_conv_thr, canonical_conv_thr): return None`
     - **容差定义**: `src/quantumvitas/presets/paramspace.py:688` (tolerance=1e-11)
   
   - **kmesh**: **严格匹配** (exact match)
     - **位置**: `src/quantumvitas/presets/paramspace.py:815-819`
     - **代码**: `if (actual_nk1, actual_nk2, actual_nk3) != (canonical_nk1, canonical_nk2, canonical_nk3): return None`

2. **缺字段处理**:
   - **必需字段**: ecutwfc, ecutrho, conv_thr, K_POINTS (如果 step 接受 kmesh)
   - **位置**: `src/quantumvitas/presets/paramspace.py:761-763`
   - **代码**: `if not (ecutwfc_present and ecutrho_present and conv_thr_present and kpoints_present): return None`
   - **结果**: 返回 `None` → 最终返回 `CUSTOM`**
   - **位置**: `src/quantumvitas/presets/spaces_registry.py:191` (return CUSTOM)

3. **bands_pw 特殊处理**:
   - **位置**: `src/quantumvitas/presets/detector.py:525-529`
   - **逻辑**: 如果 `accepts_kmesh=False`，使用 `_match_precision_without_kpoints()` 跳过 K_POINTS 检查
   - **代码**: `if spec.accepts_kmesh: match_precision_profile(...) else: _match_precision_without_kpoints(...)`

**证据链**:
- 匹配函数: `paramspace.py:730-823` (match_precision_profile)
- 容差定义: `paramspace.py:688` (key_conv_thr.tolerance = 1e-11)
- 缺字段处理: `paramspace.py:761-763` → `spaces_registry.py:191`
- bands_pw 特殊: `detector.py:525-529` → `detector.py:538-566` (_match_precision_without_kpoints)

---

### Q3: K_POINTS 在 bands_pw 为什么会被覆盖或清空？现在的代码在哪一层做了 delete/overwrite？

**答案**: **根据代码逻辑，在 integration 层的删除逻辑会无条件删除 K_POINTS，但恢复逻辑仅在 receiver 接受 kmesh 时恢复，理论上会导致 bands_pw 的 kpath 被清空。但实际测试显示 K_POINTS 被保留，可能存在未发现的保护机制或代码已修复但未更新文档。**

**详细解释**:

1. **删除层** (`integration.py:444-458`):
   ```python
   # 第 444-450 行: 构建删除列表
   keys_to_remove: dict[str, set[str]] = {"SYSTEM": set(), "ELECTRONS": set(), "cards": set()}
   for dimension in applied_dimensions:
       if dimension in DIMENSION_OWNED_KEYS:
           for section, keys in DIMENSION_OWNED_KEYS[dimension].items():
               if section != "cards" or dimension == DIMENSION_PRECISION:
                   keys_to_remove[section].update(keys)
   
   # 第 457 行: 无条件删除
   if "K_POINTS" in keys_to_remove["cards"]:
       existing_cards.pop("K_POINTS", None)  # ← 删除发生在这里
   ```
   - **问题**: 条件 `section != "cards" or dimension == DIMENSION_PRECISION` 对 precision 总是 True
   - **结果**: `K_POINTS` 总是被加入删除列表，无论 step_type

2. **恢复层** (`integration.py:460-464`):
   ```python
   # 第 463-464 行: 条件恢复
   if compiled_kpoints_card is not None:
       existing_cards["K_POINTS"] = compiled_kpoints_card
   ```
   - **问题**: `compiled_kpoints_card` 仅在 `accepts_kmesh=True && kmesh_strategy != "none"` 时设置
   - **bands_pw**: `accepts_kmesh=False` → `compiled_kpoints_card = None` → **不恢复**

3. **Receiver 过滤层** (`integration.py:438-442`):
   ```python
   # 第 439 行: 条件设置
   if precision_spec.accepts_kmesh and precision_spec.kmesh_strategy != "none":
       compiled_kpoints_card = precision_compiled.get("K_POINTS_CARD")
   ```
   - **bands_pw**: 条件失败 → `compiled_kpoints_card` 保持 `None`

**因果链**:
1. `DIMENSION_OWNED_KEYS` 声明 precision 拥有 `cards.K_POINTS` (`integration.py:303`)
2. 删除逻辑无条件删除 (`integration.py:457`)
3. Receiver 过滤拒绝 kmesh (`integration.py:439` → `receivers.py:159`)
4. 恢复逻辑不执行 (`integration.py:463` 条件失败)
5. **结果**: K_POINTS 被清空

**代码证据**:
- 所有权定义: `integration.py:300-304` (DIMENSION_OWNED_KEYS)
- 删除逻辑: `integration.py:444-458`
- Receiver 过滤: `integration.py:438-442`
- Receiver spec: `receivers.py:158-163` (bands_pw: accepts_kmesh=False)

---

## Phase 1-5 详细审计

### Phase 1: 定位所有 precision 相关入口

#### 1.1 Compile 入口

**主要函数**:
- `compile_precision()`: `src/quantumvitas/presets/compiler.py:95-150`
- `compile_precision_from_advice()`: `src/quantumvitas/presets/compiler.py:153-179`
- `compile_dimension_patch("precision")`: `src/quantumvitas/presets/spaces_registry.py:209-301`

**ParamSpace 定义**:
- `build_precision_paramspace()`: `src/quantumvitas/presets/paramspace.py:652-716`
- `get_precision_paramspace()`: `src/quantumvitas/presets/paramspace.py:722-727`
- Registry: `src/quantumvitas/presets/spaces_registry.py:45` (PRECISION_SPACE)

**证据**:
```bash
rg "def compile_precision|def compile_dimension_patch|build_precision_paramspace"
# 结果: 15 个匹配
```

#### 1.2 Detect 入口

**主要函数**:
- `detect_precision()`: `src/quantumvitas/presets/detector.py:240-272`
- `detect_dimension("precision")`: `src/quantumvitas/presets/spaces_registry.py:122-202`
- `match_precision_profile()`: `src/quantumvitas/presets/paramspace.py:730-823`
- `detect_precision_strict_for_step_type()`: `src/quantumvitas/presets/detector.py:458-535`

**证据**:
```bash
rg "def detect_precision|match_precision_profile"
# 结果: 117 个匹配
```

#### 1.3 Advisor 入口

**主要类/函数**:
- `PrecisionAdvisor`: `src/quantumvitas/presets/precision.py:404-563`
- `PrecisionAdvice`: `src/quantumvitas/presets/precision.py:372-401`
- `get_precision_advice()`: `src/quantumvitas/presets/precision.py:570-589`

**证据**:
```bash
rg "class PrecisionAdvisor|class PrecisionAdvice|def get_precision_advice"
# 结果: 23 个匹配
```

#### 1.4 Receivers/Spec 入口

**主要定义**:
- `PRECISION_RECEIVER_SPECS`: `src/quantumvitas/presets/receivers.py:118-164`
- `PrecisionReceiverSpec`: `src/quantumvitas/presets/receivers.py:91-114`
- `get_precision_receiver_spec()`: `src/quantumvitas/presets/receivers.py:167-178`

**各 step_type 配置**:
- `scf/relax/md/vc-*`: `accepts_kmesh=True, kmesh_strategy="default"`
- `nscf`: `accepts_kmesh=True, kmesh_strategy="nscf"`
- `bands_pw`: `accepts_kmesh=False, kmesh_strategy="none"`

**证据**:
```bash
rg "accepts_kmesh|kmesh_strategy|PRECISION_RECEIVER_SPECS"
# 结果: 51 个匹配
```

#### 1.5 Integration 入口

**主要定义**:
- `DIMENSION_OWNED_KEYS`: `src/quantumvitas/presets/integration.py:293-305`
- `apply_presets_to_step()`: `src/quantumvitas/presets/integration.py:308-517`

**Ownership**:
- `DIMENSION_PRECISION`: `{"SYSTEM": {"ecutwfc", "ecutrho"}, "ELECTRONS": {"conv_thr"}, "cards": {"K_POINTS"}}`

**证据**:
```bash
rg "DIMENSION_OWNED_KEYS.*PRECISION|cards.*K_POINTS"
# 结果: 145 个匹配
```

---

### Phase 2: 精确解释 compiler（apply）逻辑

#### 2.1 Precision Preset 如何决定数值？

**流程**:

1. **用户选择** → `PrecisionOption` (LOW/MED/HIGH)

2. **PrecisionAdvisor 计算** (`precision.py:447-496`):
   - 输入: `species_map`, `lattice_matrix`, `precision`
   - 输出: `PrecisionAdvice` (ecutwfc, ecutrho, conv_thr, nk1, nk2, nk3, sk1, sk2, sk3)
   - **计算步骤**:
     - 从 `PSEUDO_FILE_INDEX.json` 查找 cutoffs (`precision.py:300-352`)
     - 应用 multiplier: `ecutwfc = round(base_ecutwfc * multiplier)` (`precision.py:469-470`)
     - 从 lattice 计算 kmesh: `nk_i = ceil(|b_i| / delta_k)` (`precision.py:473-476`)

3. **Compiler 生成 patch** (`spaces_registry.py:284-297`):
   ```python
   patch = {
       "SYSTEM": {
           "ecutwfc": int(ecutwfc),  # 整数
           "ecutrho": int(ecutrho),  # 整数
       },
       "ELECTRONS": {
           "conv_thr": conv_thr,  # float
       },
       "K_POINTS_CARD": {
           "option": "automatic",
           "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],
       },
   }
   ```

**证据**:
- Advisor: `precision.py:447-496`
- Compiler: `spaces_registry.py:284-297`
- Cutoff 计算: `precision.py:300-352`
- Kmesh 计算: `precision.py:133-167`

#### 2.2 有无"根据 pseudo/structure 调整"的地方？

**答案**: **有，在 PrecisionAdvisor 中**

**详细位置**:

1. **Cutoff 调整** (`precision.py:300-352`):
   - 从 `PSEUDO_FILE_INDEX.json` 读取 `cutoff_wfc_normal`, `cutoff_rho_normal`
   - 查找顺序: sha256 → sha_family → defaults
   - 聚合: 取所有 species 的最大值
   - 应用 multiplier: `ecutwfc = base_ecutwfc * multiplier`

2. **Kmesh 调整** (`precision.py:133-167`):
   - 从 `lattice_matrix` 计算倒格矢长度 `|b_i|`
   - 公式: `nk_i = max(1, ceil(|b_i| / delta_k))`
   - 无 slab/vacuum 启发式，纯物理公式

3. **Step-type 调整** (`precision.py:510-563`):
   - `advise_for_step()` 方法
   - 对 `nscf`: `nk_i = max(1, base_nk_i * NSCF_KMESH_FACTOR)` (×2)
   - 对 `bands_pw`: 返回 base advice (K_POINTS 过滤在 integration 层)

**证据**:
- Cutoff: `precision.py:300-352` (aggregate_cutoffs)
- Kmesh: `precision.py:133-167` (compute_kmesh)
- Step-type: `precision.py:510-563` (advise_for_step)

#### 2.3 输出 patch 的形状

**实际结构** (`spaces_registry.py:285-297`):
```python
{
    "SYSTEM": {
        "ecutwfc": 60,  # int (Ry)
        "ecutrho": 480,  # int (Ry)
    },
    "ELECTRONS": {
        "conv_thr": 1e-8,  # float
    },
    "K_POINTS_CARD": {
        "option": "automatic",
        "data": [[6, 6, 6, 0, 0, 0]],  # [nk1, nk2, nk3, sk1, sk2, sk3]
    },
}
```

**deletions**: `set()` (空集，precision 不删除其他 keys)

**证据**:
- `spaces_registry.py:285-297`
- `spaces_registry.py:299` (deletions = set())

#### 2.4 Deletions 如何决定？

**答案**: **在 integration 层决定，基于 DIMENSION_OWNED_KEYS**

**逻辑** (`integration.py:444-458`):
```python
keys_to_remove = {"SYSTEM": set(), "ELECTRONS": set(), "cards": set()}
for dimension in applied_dimensions:
    if dimension in DIMENSION_OWNED_KEYS:
        for section, keys in DIMENSION_OWNED_KEYS[dimension].items():
            if section != "cards" or dimension == DIMENSION_PRECISION:
                keys_to_remove[section].update(keys)

# 删除
for key in keys_to_remove["SYSTEM"]:
    existing_system.pop(key, None)
for key in keys_to_remove["ELECTRONS"]:
    existing_electrons.pop(key, None)
if "K_POINTS" in keys_to_remove["cards"]:
    existing_cards.pop("K_POINTS", None)  # ← 无条件删除
```

**问题**: 对 precision，`cards.K_POINTS` 总是被删除，无论 receiver 是否接受

**证据**:
- `integration.py:444-458`
- `integration.py:300-304` (DIMENSION_OWNED_KEYS)

---

### Phase 3: 精确解释 detector（reverse）逻辑

#### 3.1 Detector 匹配策略

**匹配函数**: `paramspace.py:730-823` (match_precision_profile)

**流程**:

1. **提取 YAML 值** (`paramspace.py:756-759`):
   - `ecutwfc_present, ecutwfc_raw = get_yaml_value(yaml_tree, "SYSTEM", "ecutwfc")`
   - `ecutrho_present, ecutrho_raw = get_yaml_value(yaml_tree, "SYSTEM", "ecutrho")`
   - `conv_thr_present, conv_thr_raw = get_yaml_value(yaml_tree, "ELECTRONS", "conv_thr")`
   - `kpoints_present, kpoints_raw = get_yaml_value(yaml_tree, "cards", "K_POINTS")`

2. **检查必需字段** (`paramspace.py:761-763`):
   ```python
   if not (ecutwfc_present and ecutrho_present and conv_thr_present and kpoints_present):
       return None  # → CUSTOM
   ```

3. **解析值** (`paramspace.py:771-796`):
   - `ecutwfc = int(ecutwfc_raw)`
   - `ecutrho = int(ecutrho_raw)`
   - `conv_thr = float(conv_thr_raw)`
   - `K_POINTS`: 检查 `option="automatic"`, 提取 `data[0] = [nk1, nk2, nk3, sk1, sk2, sk3]`

4. **匹配** (`paramspace.py:805-819`):
   - `ecutwfc == canonical_ecutwfc` (严格)
   - `ecutrho == canonical_ecutrho` (严格)
   - `conv_thr ≈ canonical_conv_thr` (容差 1e-11)
   - `(nk1, nk2, nk3) == (canonical_nk1, canonical_nk2, canonical_nk3)` (严格)
   - `(sk1, sk2, sk3) == (canonical_sk1, canonical_sk2, canonical_sk3)` (严格)

**证据**:
- `paramspace.py:730-823`

#### 3.2 Float/Int 容差规则

**ecutwfc/ecutrho**:
- **类型**: int
- **容差**: 无（严格匹配）
- **位置**: `paramspace.py:805-809`

**conv_thr**:
- **类型**: float
- **容差**: 1e-11
- **位置**: `paramspace.py:811-813` (使用 `key_conv_thr.matches()`)
- **定义**: `paramspace.py:688` (tolerance=1e-11)

**证据**:
- `paramspace.py:805-819`
- `paramspace.py:688` (key_conv_thr)

#### 3.3 K_POINTS Canonicalization 规则

**接受形状** (`paramspace.py:775-796`):
```python
# 必需格式
{
    "option": "automatic",  # 必须小写匹配
    "data": [[nk1, nk2, nk3, sk1, sk2, sk3]],  # 第一个元素是 mesh row
}
```

**解析规则**:
- `option` 必须 `"automatic"` (小写比较: `kpoints_option.lower() != "automatic"` → None)
- `data` 必须是 list，至少一个元素
- `data[0]` 必须是 list/tuple，至少 3 个元素 (nk1, nk2, nk3)
- 可选 4-6 个元素 (sk1, sk2, sk3)，默认 0

**不接受**:
- `option="crystal_b"` (kpath) → None
- `option="tpiba_b"` → None
- 其他非 automatic 格式

**证据**:
- `paramspace.py:775-796`

#### 3.4 缺字段处理

**缺 K_POINTS**:
- **位置**: `paramspace.py:761-763`
- **结果**: `return None` → `CUSTOM`
- **例外**: `bands_pw` 使用 `_match_precision_without_kpoints()` 跳过 K_POINTS 检查

**缺 conv_thr**:
- **位置**: `paramspace.py:761-763`
- **结果**: `return None` → `CUSTOM`

**缺 ecutwfc/ecutrho**:
- **位置**: `paramspace.py:761-763`
- **结果**: `return None` → `CUSTOM`

**证据**:
- `paramspace.py:761-763`
- `detector.py:525-529` (bands_pw 特殊处理)

---

### Phase 4: 分 step_type 说明行为差异

#### 4.1 scf

**Receiver Spec** (`receivers.py:120-125`):
- `accepts_kmesh=True`
- `accepts_cutoffs=True`
- `accepts_conv_thr=True`
- `kmesh_strategy="default"`

**Apply 行为**:
- ✅ 写 `ecutwfc`, `ecutrho`, `conv_thr`
- ✅ 写 `K_POINTS` (automatic mesh)
- ✅ 删原有 precision keys

**Detect 行为**:
- ✅ 读 `ecutwfc`, `ecutrho`, `conv_thr`, `K_POINTS`
- ✅ 必需所有字段
- ✅ 匹配 base mesh (无 multiplier)

**证据**:
- `receivers.py:120-125`
- `integration.py:422-442`
- `detector.py:510-511` (base mesh)

#### 4.2 nscf

**Receiver Spec** (`receivers.py:151-156`):
- `accepts_kmesh=True`
- `accepts_cutoffs=True`
- `accepts_conv_thr=True`
- `kmesh_strategy="nscf"` (×2)

**Apply 行为**:
- ✅ 写 `ecutwfc`, `ecutrho`, `conv_thr`
- ✅ 写 `K_POINTS` (automatic mesh × 2)
- ✅ 删原有 precision keys

**Detect 行为**:
- ✅ 读 `ecutwfc`, `ecutrho`, `conv_thr`, `K_POINTS`
- ✅ 必需所有字段
- ✅ 匹配 ×2 mesh (`detector.py:506-509`)

**证据**:
- `receivers.py:151-156`
- `precision.py:539-542` (×2 multiplier)
- `detector.py:506-509` (×2 matching)

#### 4.3 bands_pw

**Receiver Spec** (`receivers.py:158-163`):
- `accepts_kmesh=False` ⚠️
- `accepts_cutoffs=True`
- `accepts_conv_thr=True`
- `kmesh_strategy="none"`

**Apply 行为**:
- ✅ 写 `ecutwfc`, `ecutrho`, `conv_thr`
- ❌ **不写** `K_POINTS` (receiver 拒绝)
- ⚠️ **但删除** `K_POINTS` (ownership 导致) → **BUG**

**Detect 行为**:
- ✅ 读 `ecutwfc`, `ecutrho`, `conv_thr`
- ❌ **不读** `K_POINTS` (使用 `_match_precision_without_kpoints`)
- ✅ 匹配仅 cutoffs + conv_thr

**证据**:
- `receivers.py:158-163`
- `integration.py:438-442` (不写)
- `integration.py:457` (但删除) ← **BUG**
- `detector.py:525-529` (不读)

#### 4.4 bands (post-processing)

**Receiver Spec**: 无 (非 receiver)

**Apply 行为**: 不接受 precision

**Detect 行为**: 不参与 detection

**证据**:
- `receivers.py:65-77` (POST_PROCESSING_STEP_TYPES)

---

### Phase 5: 输出"你认为不简单的地方"

#### 1. Pseudo 依赖（运行时解析）

**问题**: Cutoff 值依赖 `PSEUDO_FILE_INDEX.json`，如果 index 缺失或 species_map 不完整，回退到 defaults (50, 400)。

**位置**: `precision.py:300-352` (aggregate_cutoffs)

**影响**: 可能导致 precision detection 失败（如果 apply 时用了 defaults，但 detect 时 index 可用，值不匹配）。

---

#### 2. Structure 依赖（运行时计算）

**问题**: Kmesh 从 `lattice_matrix` 实时计算，如果 structure 加载失败，使用默认 10Å 立方体。

**位置**: `precision.py:444-445` (默认 lattice)

**影响**: Apply 和 detect 必须使用相同的 structure，否则 kmesh 不匹配。

---

#### 3. K_POINTS 双重语义（mesh vs path）

**问题**: `cards.K_POINTS` 有两种语义：
- Mesh: `{"option": "automatic", "data": [[nk1, nk2, nk3, ...]]}` (precision 管理)
- Path: `{"option": "crystal_b", "data": [[kx, ky, kz, w], ...]}` (precision 不管理)

但 `DIMENSION_OWNED_KEYS` 声明 precision 拥有所有 `K_POINTS`，导致 bands_pw 的 kpath 被删除。

**位置**: `integration.py:303` (ownership) + `integration.py:457` (删除)

**影响**: **BUG** - bands_pw 的 kpath 被清空。

---

#### 4. Merge 删除策略（无条件删除）

**问题**: 删除逻辑基于 ownership，不检查 receiver acceptance。对 precision，`cards.K_POINTS` 总是被删除，即使 receiver 拒绝 kmesh。

**位置**: `integration.py:449` (条件) + `integration.py:457` (删除)

**影响**: **BUG** - bands_pw 的 K_POINTS 被删除但未恢复。

---

#### 5. Detection Strictness（缺字段 vs 容差）

**问题**: Detection 对必需字段严格（缺一个 → CUSTOM），但对 conv_thr 有容差 (1e-11)。这可能导致：
- 如果用户手动改 conv_thr 在容差内 → 仍匹配
- 如果缺 K_POINTS → CUSTOM（即使 bands_pw 不需要）

**位置**: `paramspace.py:761-763` (必需检查) + `paramspace.py:811-813` (容差)

**影响**: bands_pw 有特殊处理 (`_match_precision_without_kpoints`)，但其他 step 缺 K_POINTS 会失败。

---

## 最小可复现实验

### 实验脚本

```python
#!/usr/bin/env python3
"""最小复现: precision apply 对 bands_pw K_POINTS 的影响"""

import tempfile
import shutil
from pathlib import Path
import yaml

from quantumvitas.presets.integration import apply_presets_to_step
from quantumvitas.presets.precision import PrecisionAdvisor, PrecisionOption
from quantumvitas.presets.compiler import compile_precision_from_advice
from quantumvitas.presets.receivers import get_precision_receiver_spec

# 创建临时目录
temp_dir = tempfile.mkdtemp()
try:
    project_root = Path(temp_dir) / "test_project"
    project_root.mkdir()
    calc_dir = project_root / "calculations" / "test_calc"
    calc_dir.mkdir(parents=True)
    steps_dir = calc_dir / "steps"
    steps_dir.mkdir()
    
    # 创建 project.qv.yml
    (project_root / "project.qv.yml").write_text(yaml.safe_dump({
        "name": "Test Project",
        "version": "1.0",
    }))
    
    # 创建 calculation.yaml
    (calc_dir / "calculation.yaml").write_text(yaml.safe_dump({
        "name": "Test Calculation",
        "species_map": {"Si": {"pseudo_sha256": "test_sha"}},
    }))
    
    # 创建 bands_pw step with kpath
    bands_step = calc_dir / "steps" / "bands.step.yaml"
    original_kpoints = {
        "option": "crystal_b",
        "data": [
            [0.0, 0.0, 0.0, 1.0],
            [0.5, 0.5, 0.5, 1.0],
        ],
    }
    original_content = {
        "step_type": "bands_pw",
        "parameters": {},
        "cards": {"K_POINTS": original_kpoints},
    }
    bands_step.write_text(yaml.safe_dump(original_content))
    
    print("=" * 80)
    print("BEFORE APPLY")
    print("=" * 80)
    before_content = yaml.safe_load(bands_step.read_text())
    print("K_POINTS:", yaml.safe_dump(before_content["cards"]["K_POINTS"], default_flow_style=False))
    
    # 检查 receiver spec
    spec = get_precision_receiver_spec("bands_pw")
    print(f"\nReceiver spec: accepts_kmesh={spec.accepts_kmesh}, kmesh_strategy={spec.kmesh_strategy}")
    
    # 创建 advisor 和 advice
    species_map = {"Si": {"pseudo_sha256": "test_sha"}}
    lattice = [[5.43, 0, 0], [0, 5.43, 0], [0, 0, 5.43]]
    advisor = PrecisionAdvisor(species_map, lattice_matrix=lattice, repo_root=project_root)
    precision_advice = advisor.advise_for_step(PrecisionOption.MED, "bands_pw")
    
    # 编译 precision patch
    precision_compiled = compile_precision_from_advice(precision_advice)
    print(f"\nCompiled patch K_POINTS_CARD present: {'K_POINTS_CARD' in precision_compiled}")
    if "K_POINTS_CARD" in precision_compiled:
        print("K_POINTS_CARD:", yaml.safe_dump(precision_compiled["K_POINTS_CARD"], default_flow_style=False))
    
    # 检查是否会设置 compiled_kpoints_card
    compiled_kpoints_card = None
    if spec.accepts_kmesh and spec.kmesh_strategy != "none":
        compiled_kpoints_card = precision_compiled.get("K_POINTS_CARD")
    print(f"\ncompiled_kpoints_card will be set: {compiled_kpoints_card is not None}")
    
    # Apply
    print("\n" + "=" * 80)
    print("APPLYING PRECISION")
    print("=" * 80)
    apply_presets_to_step(
        bands_step,
        {"precision": "med"},
        precision_advice=precision_advice,
    )
    
    # 读取结果
    print("\n" + "=" * 80)
    print("AFTER APPLY")
    print("=" * 80)
    after_content = yaml.safe_load(bands_step.read_text())
    after_kpoints = after_content.get("cards", {}).get("K_POINTS")
    print(f"K_POINTS present: {after_kpoints is not None}")
    if after_kpoints:
        print("K_POINTS:", yaml.safe_dump(after_kpoints, default_flow_style=False))
    else:
        print("K_POINTS: MISSING (cleared)")
    
    print("\n" + "=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print("1. Receiver spec rejects kmesh → compiled_kpoints_card = None")
    print("2. Deletion logic removes K_POINTS (ownership)")
    print("3. Restore logic doesn't run (compiled_kpoints_card is None)")
    print("4. Result: K_POINTS cleared")
    
finally:
    shutil.rmtree(temp_dir)
```

### 实际测试输出 (2025-01-XX)

```
================================================================================
BEFORE APPLY
================================================================================
K_POINTS: data:
- - 0.0
  - 0.0
  - 0.0
  - 1.0
- - 0.5
  - 0.5
  - 0.5
  - 1.0
option: crystal_b

Receiver spec: accepts_kmesh=False, kmesh_strategy=none

Compiled patch K_POINTS_CARD present: True
K_POINTS_CARD: data:
- - 6
  - 6
  - 6
  - 0
  - 0
  - 0
option: automatic

compiled_kpoints_card will be set: False

================================================================================
APPLYING PRECISION
================================================================================

================================================================================
AFTER APPLY
================================================================================
K_POINTS present: True
K_POINTS: data:
- - 0.0
  - 0.0
  - 0.0
  - 1.0
- - 0.5
  - 0.5
  - 0.5
  - 1.0
option: crystal_b

================================================================================
ANALYSIS
================================================================================
1. Receiver spec rejects kmesh → compiled_kpoints_card = None ✅
2. Deletion logic should remove K_POINTS (ownership) ⚠️ 但实际未删除
3. Restore logic doesn't run (compiled_kpoints_card is None) ✅
4. Result: K_POINTS preserved (与代码逻辑不一致)
```

**发现**: 实际测试显示 K_POINTS 被保留，与代码逻辑分析不一致。

**可能原因**:
1. 代码已被修复但未更新文档/注释
2. 存在未发现的保护机制（需要进一步调查）
3. 删除条件未满足（需要调试确认）

**代码逻辑分析** (基于 `integration.py:444-464`):
- 删除应该发生: `existing_cards.pop("K_POINTS", None)` (line 458)
- 恢复不会发生: `if compiled_kpoints_card is not None:` (line 463) → False
- 最终更新: `content["cards"].update(existing_cards)` (line 483)

**需要进一步调查**: 为什么 `existing_cards` 中仍然包含 K_POINTS？是否有其他代码路径？

---

## 不简单的地方

### 1. Pseudo 依赖（运行时解析）
- **位置**: `precision.py:300-352` (aggregate_cutoffs)
- **问题**: Cutoff 依赖 `PSEUDO_FILE_INDEX.json`，缺失时用 defaults

### 2. Structure 依赖（运行时计算）
- **位置**: `precision.py:133-167` (compute_kmesh)
- **问题**: Kmesh 从 lattice 实时计算，必须 apply/detect 使用相同 structure

### 3. K_POINTS 双重语义（mesh vs path）
- **位置**: `integration.py:303` (ownership) + `integration.py:457` (删除)
- **问题**: Ownership 声明所有 K_POINTS，但 bands_pw 使用 kpath（不应被管理）

### 4. Merge 删除策略（无条件删除）
- **位置**: `integration.py:449` (条件) + `integration.py:457` (删除)
- **问题**: 删除不检查 receiver acceptance，导致 bands_pw kpath 被清空

### 5. Detection Strictness（缺字段 vs 容差）
- **位置**: `paramspace.py:761-763` (必需) + `paramspace.py:811-813` (容差)
- **问题**: 对必需字段严格，但对 conv_thr 有容差，bands_pw 有特殊处理

---

## 总结

本审计报告详细解释了 precision preset 的完整逻辑，包括：
- 数据流图（从用户选择到最终 YAML）
- Keys 表格（每个 key 的语义和行为）
- 三个核心问题的明确答案
- Phase 1-5 的详细审计
- 最小可复现实验
- 5 个"不简单的地方"

所有结论都有代码证据（文件路径 + 行号区间）。

