# RELAX 实现审计报告

**审计日期**: 2026-01-18  
**审计员**: Cursor Auto (严格代码审计员)  
**审计范围**: RELAX 实现 vs RELAX_SPEC 契约对齐

---

## 1. Executive Summary

### 结论
**整体状态**: **MOSTLY** - 大部分契约已满足，但存在关键风险点需要立即处理

### Top 5 未对齐点（按严重程度排序）

1. **HIGH**: ORCA/PySCF relax 输出未调用 canonicalize（违反 B6 契约）
   - 位置: `pyscf_relax_handler.py:57-72`, `orca_relax_parser.py:205-218`
   - 风险: 可能导致 fingerprint 不一致，破坏去重/历史语义

2. **HIGH**: `import_structure` 对 Molecule 使用不同 fingerprint 逻辑（违反 B6 契约）
   - 位置: `api.py:437-446`
   - 风险: 引入第二套 fingerprint 系统，与 Structure 不一致

3. **MEDIUM**: `qe_vc_relax` 在 registry 中缺失（只有 alias）
   - 位置: `registry.py:166-203` (只有 `qe_relax`，`qe_vc_relax` 通过 `STEP_TYPE_ALIASES` 映射)
   - 风险: 可能导致某些路径无法正确识别 vc-relax

4. **MEDIUM**: `RELAX_STEP_TYPES` 只包含 `{"relax"}`，不包含 `"vc-relax"`
   - 位置: `qc_engine_base.py:25`
   - 风险: 依赖 normalize 处理，但某些路径可能直接检查集合

5. **LOW**: 文档声称 ORCA/PySCF 会调用 canonicalize，但代码未实现
   - 位置: `docs/research/RELAX_ENGINE_RESEARCH.md:416-426` vs 实际代码
   - 风险: 文档与实现不一致

### 是否存在"可能破坏核心数学逻辑/SSOT"的改动

**是**，存在以下风险：

1. **import_structure 对 Molecule 的 fingerprint 逻辑** (`api.py:437-446`)
   - 使用 `hashlib.sha256(json.dumps(structure_dict))` 而非统一的 `structure_fingerprint()`
   - 这违反了 B6 契约："必须复用唯一入口"
   - **风险评估**: **HIGH** - 可能导致 Molecule 与 Structure 的 fingerprint 语义不一致

2. **ORCA/PySCF relax 输出未 canonicalize**
   - `pyscf_relax_handler.py` 和 `orca_relax_parser.py` 直接创建 Molecule 并写入，未调用 `canonicalize_structure_in_place`
   - 虽然 Molecule 没有 fractional coords，但可能影响后续 fingerprint 计算
   - **风险评估**: **MEDIUM** - 如果后续有基于坐标的 canonicalize 需求，会不一致

---

## 2. Contract Checklist 对照表

### B1) GEN step 只有一个：relax

**状态**: **PASS** (with caveats)

**证据**:
- `registry.py:192-203`: `qe_relax` 的 `public_type="relax"` ✓
- `registry.py:419-430`: `pyscf_relax` 的 `public_type="relax"` ✓
- `registry.py:480-491`: `orca_relax` 的 `public_type="relax"` ✓
- `registry.py:698-705`: `STEP_TYPE_ALIASES` 将 `"vc-relax"`, `"opt"`, `"geomopt"` 映射到 `"relax"` ✓

**风险**: 
- `qe_vc_relax` 不在 `_STEP_TYPES` 中，只有 alias。如果某些代码直接查找 `qe_vc_relax` 而不经过 normalize，可能失败。
- `RELAX_STEP_TYPES = {"relax"}` (`qc_engine_base.py:25`) 不包含 `"vc-relax"`，依赖 normalize 处理。

**建议**: 确认所有路径都经过 `normalize_step_type()` 或直接检查 `is_structure_transform` flag。

---

### B2) relax 只产 structure，不产可依赖电子态

**状态**: **PASS**

**证据**:
- `registry.py:201`: `qe_relax` 的 `produces_charge_density=False` ✓
- `registry.py:428`: `pyscf_relax` 的 `produces_charge_density=False` ✓
- `registry.py:489`: `orca_relax` 的 `produces_charge_density=False` ✓

**风险**: 无

**建议**: 无

---

### B3) artifact 路径：calc/generated_structures/step_<relax_ulid>/current.json

**状态**: **PASS**

**证据**:
- `relax_artifacts.py:24-35`: `get_generated_structure_path()` 返回正确路径 ✓
- `relax_artifacts.py:62`: `write_generated_structure()` 写入到正确路径 ✓
- Schema: `relax_artifacts.py:66-77` 包含 `__qv_meta__` 和 provenance ✓

**风险**: 无

**建议**: 无

---

### B4) job scoped cleanup

**状态**: **PASS**

**证据**:
- `executor.py:489-519`: `_pre_clean_relax_steps()` 只清理本 job 覆盖的 relax steps ✓
- `executor.py:144`: 在 job 执行前调用 `_pre_clean_relax_steps()` ✓

**风险**: 无

**建议**: 无

---

### B5) missing current.json：hard error

**状态**: **PASS**

**证据**:
- `executor.py:668-756`: `_load_effective_structure_for_step()` 在 missing current.json 时抛出 `MissingArtifactError` ✓
- `executor.py:730-740`: Error message 符合 spec 格式 ✓
- `executor.py:181-184`: Job 失败时 fail-fast (break loop) ✓

**风险**: 无

**建议**: 无

---

### B6) structure canonicalize/fingerprint：必须复用唯一入口

**状态**: **FAIL** (部分违反)

**证据**:

**违反点 1**: `import_structure` 对 Molecule 使用不同 fingerprint
- `api.py:437-446`: 
  ```python
  if isinstance(structure, Molecule):
      # For molecules, use a simple hash of the structure dict
      import hashlib
      structure_dict = structure.as_dict()
      structure_dict.pop("__qv_meta__", None)
      structure_str = json.dumps(structure_dict, sort_keys=True)
      fingerprint = hashlib.sha256(structure_str.encode('utf-8')).hexdigest()
  else:
      fingerprint = structure_fingerprint(structure)
  ```
- **问题**: 这引入了第二套 fingerprint 逻辑，违反 B6 契约

**违反点 2**: ORCA/PySCF relax 输出未调用 canonicalize
- `pyscf_relax_handler.py:57-72`: 直接创建 Molecule，未调用 `canonicalize_structure_in_place`
- `orca_relax_parser.py:205-218`: 直接创建 Molecule，未调用 `canonicalize_structure_in_place`
- **对比**: QE 正确调用 `structure_from_qe_geometry_snapshot()` → `canonicalize_structure_in_place()` (`geometry.py:612-614`)

**正确实现**:
- QE: `handlers.py:520` → `structure_from_qe_geometry_snapshot()` → `canonicalize_structure_in_place()` ✓

**风险**: 
- **HIGH**: `import_structure` 的 Molecule fingerprint 可能导致去重/历史语义不一致
- **MEDIUM**: ORCA/PySCF 未 canonicalize 可能影响后续 fingerprint 计算（虽然 Molecule 没有 fractional coords）

**建议**: 
1. 立即修复 `import_structure` 的 Molecule fingerprint 逻辑，统一使用 `structure_fingerprint()`（如果支持 Molecule）或明确文档说明为什么 Molecule 需要不同逻辑
2. 确认 ORCA/PySCF 是否需要 canonicalize（Molecule 没有 fractional coords，但可能影响坐标排序）

---

### B7) QC topology 规则（强制）

**状态**: **PASS**

**证据**:
- `recipes.py:38-103`: `verify_qc_topology()` 实现正确 ✓
- `recipes.py:278`: `ORCARecipe.materialize()` 开头调用 `verify_qc_topology()` ✓
- `recipes.py:388`: `PySCFRecipe.materialize()` 开头调用 `verify_qc_topology()` ✓
- `recipes.py:67-68`: Relax steps 被跳过（standalone）✓
- `recipes.py:87-93`: 非 relax/非 SCF 步骤检查 relax 阻塞 ✓
- `recipes.py:98-103`: 非 relax/非 SCF 步骤检查 SCF root 存在 ✓

**风险**: 
- `RELAX_STEP_TYPES = {"relax"}` 不包含 `"vc-relax"`，但通过 normalize 应该能处理

**建议**: 确认所有 step type 都经过 normalize 或直接检查 `is_structure_transform` flag

---

### B8) fail-fast

**状态**: **PASS**

**证据**:
- `executor.py:181-184`: Job 失败时 `execution_success = False` 并 `break` ✓
- `executor.py:173-176`: Post-process 只在 `job_result.success` 时调用 ✓
- `executor.py:528-666`: `_post_process_relax_steps()` 成功时写入 current.json ✓

**风险**: 无

**建议**: 无

---

### B9) promote 语义

**状态**: **PASS**

**证据**:
- `api.py:4664-4756`: `promote_relax_structure()` 实现正确 ✓
- `api.py:4709`: 检查 `is_structure_transform` flag ✓
- `api.py:4720-4726`: 检查 current.json 存在 ✓
- `api.py:4747-4752`: 调用 `import_structure()` 创建新资源 ✓
- `api.py:4730`: 移除 `__qv_meta__` 后导入（不保留 artifact metadata）✓

**风险**: 
- `promote_relax_structure()` 调用 `import_structure()` 时 `index=None` (`api.py:4751`)，会重建 index。这可能影响性能，但不违反契约。

**建议**: 考虑传递 index 以优化性能（但需要确保 index 更新正确）

---

## 3. "只有一个 public GEN type = relax" 专项审计

### Registry 中所有与 relax 相关的条目

**Machine Types**:
1. `qe_relax` (`registry.py:192-203`)
   - `public_type="relax"` ✓
   - `is_structure_transform=True` ✓
   - `produces_charge_density=False` ✓

2. `pyscf_relax` (`registry.py:419-430`)
   - `public_type="relax"` ✓
   - `is_structure_transform=True` ✓
   - `produces_charge_density=False` ✓

3. `orca_relax` (`registry.py:480-491`)
   - `public_type="relax"` ✓
   - `is_structure_transform=True` ✓
   - `produces_charge_density=False` ✓

**Aliases** (`registry.py:698-705`):
- `"vc-relax"` → `"relax"`
- `"qe_vc_relax"` → `"qe_relax"`
- `"opt"` → `"relax"`
- `"geomopt"` → `"relax"`

**缺失**: `qe_vc_relax` 不在 `_STEP_TYPES` 中，只有 alias。

### public_type 目前有哪些值？

从 registry 代码看，所有 relax 相关步骤的 `public_type` 都是 `"relax"`。不存在 `"vc-relax"`, `"opt"`, `"geomopt"` 作为 public_type。

### UI/CLI selector 层暴露了哪些 type？

**需要检查** (未在本次审计范围内，但建议检查):
- CLI: `cli/main.py` 可能暴露 machine types
- UI: 需要检查前端代码

### QC Topology / is_structure_transform / RELAX_STEP_TYPES 当前依赖谁？

**当前实现**:
- `verify_qc_topology()` (`recipes.py:67`): 使用 `RELAX_STEP_TYPES` 集合 (`{"relax"}`)
- `is_relax_step_type()` (`relax_artifacts.py:138-154`): 使用 registry 的 `is_structure_transform` flag
- `RELAX_STEP_TYPES` (`qc_engine_base.py:25`): 硬编码 `{"relax"}`

**问题**: 
- `RELAX_STEP_TYPES` 不包含 `"vc-relax"`，但通过 `normalize_step_type()` 应该能处理
- 某些路径可能直接检查 `RELAX_STEP_TYPES` 而不经过 normalize

### 结论：现在是否已达到"对外只有 relax 一个入口"？

**状态**: **MOSTLY** - 基本达到，但存在边缘情况

**差距**:
1. `qe_vc_relax` 不在 registry 中，只有 alias。如果代码直接查找 `qe_vc_relax` 而不经过 normalize，可能失败。
2. `RELAX_STEP_TYPES` 只包含 `{"relax"}`，不包含 `"vc-relax"`。虽然通过 normalize 能处理，但某些路径可能直接检查集合。

**最小化差距**:
- 确保所有代码路径都使用 `is_relax_step_type()` 或检查 `is_structure_transform` flag，而不是直接检查 `RELAX_STEP_TYPES` 集合
- 或者将 `RELAX_STEP_TYPES` 扩展为 `{"relax", "vc-relax"}` 并通过 normalize 统一处理

---

## 4. import_structure() 深度审计

### import_structure 的职责是什么？

**定义**: `api.py:338-477`

**职责**:
1. 从外部文件导入结构资源（CIF, QE input, JSON 等）
2. 用于 promote relax structure（`promote_relax_structure()` 调用它）
3. 用于用户导入结构（CLI/UI）
4. 用于测试

### 谁在调用它？

**全 repo 搜索调用点**:
1. `api.py:4747`: `promote_relax_structure()` 调用（用于 promote relax output）
2. `daemon/server.py:2204`: `_handle_import_structure()` RPC handler
3. `cli/main.py:1354`: `import_structure_command()` CLI 命令
4. 测试文件: 多处测试调用

### 近期改动是什么？

**PR12 相关改动** (从代码推断):
- `api.py:437-446`: 对 Molecule 使用不同的 fingerprint 逻辑
  ```python
  if isinstance(structure, Molecule):
      # For molecules, use a simple hash of the structure dict
      fingerprint = hashlib.sha256(json.dumps(structure_dict, sort_keys=True)).hexdigest()
  else:
      fingerprint = structure_fingerprint(structure)
  ```

**问题**: 这引入了第二套 fingerprint 系统。

### 是否触及/改变了"核心数学逻辑"？

**是**，存在以下改动：

1. **Fingerprint 逻辑分裂** (`api.py:437-446`):
   - Structure: 使用 `structure_fingerprint()` (统一入口)
   - Molecule: 使用 `hashlib.sha256(json.dumps())` (第二套逻辑)
   - **违反**: B6 契约要求"必须复用唯一入口"

2. **Canonicalize**: `import_structure()` 不直接调用 canonicalize，但 `read_structure()` 可能调用（需要检查 `structure_io.py`）

### 改动是否可能引入第二套 fingerprint/canonicalize？

**是**，已引入：

1. **第二套 fingerprint** (`api.py:437-446`):
   - Molecule 使用 `hashlib.sha256(json.dumps())`
   - Structure 使用 `structure_fingerprint()`
   - **风险**: 两种 fingerprint 语义不一致，可能导致去重/历史语义变化

2. **Canonicalize**: 未发现第二套 canonicalize（但需要确认 `read_structure()` 的行为）

### 改动是否可能引入与旧 Structure fingerprint 不一致？

**是**，存在风险：

- Molecule 的 fingerprint 与 Structure 的 fingerprint 使用不同算法
- 如果后续有代码依赖 fingerprint 一致性（例如去重、历史比较），可能出问题

### 风险评估

**等级**: **HIGH**

**理由**:
1. 违反了 B6 契约的核心要求："必须复用唯一入口"
2. 可能导致去重/历史语义不一致
3. `promote_relax_structure()` 调用 `import_structure()`，如果 promote 的是 Molecule，会使用不同的 fingerprint

**证据**:
- `api.py:437-446`: Molecule fingerprint 逻辑
- `api.py:4747`: `promote_relax_structure()` 调用 `import_structure()`

### 如果需要回滚：精确指出"回滚的最小边界"

**回滚边界**: `api.py:437-446`

**具体代码**:
```python
# 当前代码 (需要回滚)
if isinstance(structure, Molecule):
    # For molecules, use a simple hash of the structure dict
    import hashlib
    structure_dict = structure.as_dict()
    structure_dict.pop("__qv_meta__", None)
    structure_str = json.dumps(structure_dict, sort_keys=True)
    fingerprint = hashlib.sha256(structure_str.encode('utf-8')).hexdigest()
else:
    fingerprint = structure_fingerprint(structure)
```

**回滚到**:
```python
# 应该统一使用 structure_fingerprint (如果支持 Molecule)
# 或者明确文档说明为什么 Molecule 需要不同逻辑
fingerprint = structure_fingerprint(structure)  # 如果支持
# 或者
if isinstance(structure, Molecule):
    # TODO: 实现 molecule_fingerprint() 或扩展 structure_fingerprint() 支持 Molecule
    raise NotImplementedError("Molecule fingerprint not yet implemented")
else:
    fingerprint = structure_fingerprint(structure)
```

**影响范围**:
- 只影响 `import_structure()` 方法
- 不影响其他代码路径

---

## 5. ORCA/PySCF/QE real relax e2e 的契约一致性

### ORCA: run_step_with_chain → handler → executor post-process → 解析输出 → 写 current.json

**实现路径**:
1. `handlers.py:346-469`: `orca_chain_handler()` 调用 `engine.run_step_with_chain()`
2. `orca_engine.py:199-220`: `run_step()` 委托给 `run_step_with_chain()`
3. `orca_engine.py:863-1015` (推断): `run_step_with_chain()` 执行 chain
4. `executor.py:630-658`: `_post_process_relax_steps()` 调用 `handle_orca_relax_output()`
5. `orca_relax_parser.py:118-222`: `handle_orca_relax_output()` 解析并写入 current.json

**契约核对**:

✅ **relax 成功是否强制生成 current.json？**
- `executor.py:173`: Post-process 只在 `job_result.success` 时调用
- `orca_relax_parser.py:209-218`: 成功时写入 current.json
- **结论**: PASS

✅ **失败是否 fail-fast？**
- `executor.py:181-184`: Job 失败时 break
- **结论**: PASS

✅ **scoped cleanup 是否只清理本 job 覆盖 relax steps？**
- `executor.py:489-519`: `_pre_clean_relax_steps()` 只清理本 job 的 steps
- **结论**: PASS

✅ **missing current.json 是否 hard error？**
- `executor.py:730-740`: 抛出 `MissingArtifactError`
- **结论**: PASS

❌ **current.json schema 是否真复用 project/structure schema？**
- `relax_artifacts.py:66-77`: 使用 `structure.as_dict()`，包含 `__qv_meta__`
- `relax_artifacts.py:107`: `read_generated_structure()` 移除 `__qv_meta__` 后使用 `Structure.from_dict()` 或 `Molecule.from_dict()`
- **结论**: PASS (pymatgen 可读)

❌ **ORCA parser 是否可能误取中间坐标块而不是最终？**
- `orca_relax_parser.py:44-50`: 从后往前搜索 "CARTESIAN COORDINATES"，取最后一个
- `orca_relax_parser.py:90-115`: 如果找到 .xyz 文件，直接解析（应该是最终结构）
- **风险**: 如果 .xyz 文件不存在，从 .out 文件解析时，搜索逻辑可能不够严格
- **建议**: 确认 ORCA .out 文件的 "CARTESIAN COORDINATES" 块是否总是最后一个

---

### PySCF: geomopt/working_dir/写 current.json

**实现路径**:
1. `handlers.py:230-343`: `pyscf_chain_handler()` 调用 `engine.run_step_with_chain()`
2. `executor.py:595-629`: `_post_process_relax_steps()` 调用 `handle_pyscf_relax_output()`
3. `pyscf_relax_handler.py:19-76`: `handle_pyscf_relax_output()` 从 `results.json` 读取并写入 current.json

**契约核对**:

✅ **relax 成功是否强制生成 current.json？**
- `executor.py:173`: Post-process 只在 `job_result.success` 时调用
- `pyscf_relax_handler.py:64-72`: 成功时写入 current.json
- **结论**: PASS

✅ **失败是否 fail-fast？**
- `executor.py:181-184`: Job 失败时 break
- **结论**: PASS

✅ **scoped cleanup 是否只清理本 job 覆盖 relax steps？**
- `executor.py:489-519`: `_pre_clean_relax_steps()` 只清理本 job 的 steps
- **结论**: PASS

✅ **missing current.json 是否 hard error？**
- `executor.py:730-740`: 抛出 `MissingArtifactError`
- **结论**: PASS

❌ **current.json schema 是否真复用 project/structure schema？**
- `pyscf_relax_handler.py:57-62`: 创建 Molecule，使用 `write_generated_structure()`
- `relax_artifacts.py:66-77`: 使用 `structure.as_dict()`，pymatgen 可读
- **结论**: PASS

❌ **ORCA/PySCF 是否调用 canonicalize？**
- `pyscf_relax_handler.py:57-72`: **未调用** `canonicalize_structure_in_place()`
- `orca_relax_parser.py:205-218`: **未调用** `canonicalize_structure_in_place()`
- **对比**: QE 正确调用 (`handlers.py:520` → `structure_from_qe_geometry_snapshot()` → `canonicalize_structure_in_place()`)
- **结论**: **FAIL** - 违反 B6 契约

---

### QE: 如果已有 real relax e2e，指出；若没有，说明当前 coverage 缺口

**实现路径**:
1. `handlers.py:87-227`: `qe_step_handler()` 执行单个 QE step
2. `executor.py:571-593`: `_post_process_relax_steps()` 调用 `handle_qe_relax_output()`
3. `handlers.py:480-535`: `handle_qe_relax_output()` 解析输出并写入 current.json

**契约核对**:

✅ **relax 成功是否强制生成 current.json？**
- `executor.py:173`: Post-process 只在 `job_result.success` 时调用
- `handlers.py:523-531`: 成功时写入 current.json
- **结论**: PASS

✅ **失败是否 fail-fast？**
- `executor.py:181-184`: Job 失败时 break
- **结论**: PASS

✅ **scoped cleanup 是否只清理本 job 覆盖 relax steps？**
- `executor.py:489-519`: `_pre_clean_relax_steps()` 只清理本 job 的 steps
- **结论**: PASS

✅ **missing current.json 是否 hard error？**
- `executor.py:730-740`: 抛出 `MissingArtifactError`
- **结论**: PASS

✅ **current.json schema 是否真复用 project/structure schema？**
- `handlers.py:520`: 调用 `structure_from_qe_geometry_snapshot()` → 返回 pymatgen Structure
- `relax_artifacts.py:66-77`: 使用 `structure.as_dict()`，pymatgen 可读
- **结论**: PASS

✅ **QE 是否调用 canonicalize？**
- `handlers.py:520`: 调用 `structure_from_qe_geometry_snapshot()`
- `geometry.py:612-614`: `structure_from_qe_geometry_snapshot()` 内部调用 `canonicalize_structure_in_place()`
- **结论**: PASS

---

## 6. 需要我拍板的关键问题（最多 10 条）

### 问题 1: import_structure 对 Molecule 的 fingerprint 逻辑是否允许？

**背景证据**:
- `api.py:437-446`: Molecule 使用 `hashlib.sha256(json.dumps())`，Structure 使用 `structure_fingerprint()`
- B6 契约要求"必须复用唯一入口"
- `promote_relax_structure()` 调用 `import_structure()`，如果 promote 的是 Molecule，会使用不同的 fingerprint

**决策选项**:
- **A**: 立即修复，统一使用 `structure_fingerprint()`（如果支持 Molecule）或实现 `molecule_fingerprint()`
  - **后果**: 需要扩展 `structure_fingerprint()` 支持 Molecule，或实现新的 `molecule_fingerprint()` 函数
- **B**: 保持现状，但明确文档说明为什么 Molecule 需要不同逻辑
  - **后果**: 违反 B6 契约，可能导致去重/历史语义不一致

**建议**: 选择 A，因为违反核心契约。

---

### 问题 2: ORCA/PySCF relax 输出是否需要调用 canonicalize？

**背景证据**:
- `pyscf_relax_handler.py:57-72`: 未调用 `canonicalize_structure_in_place()`
- `orca_relax_parser.py:205-218`: 未调用 `canonicalize_structure_in_place()`
- QE 正确调用 (`geometry.py:612-614`)
- Molecule 没有 fractional coords，但可能影响坐标排序

**决策选项**:
- **A**: 立即修复，为 ORCA/PySCF 添加 canonicalize 调用（即使 Molecule 没有 fractional coords，也要确保一致性）
  - **后果**: 需要确认 `canonicalize_structure_in_place()` 是否支持 Molecule，或实现 Molecule 版本的 canonicalize
- **B**: 保持现状，文档说明 Molecule 不需要 canonicalize（因为没有 fractional coords）
  - **后果**: 与 QE 行为不一致，可能影响后续 fingerprint 计算

**建议**: 选择 A，确保一致性。

---

### 问题 3: qe_vc_relax 是否需要在 registry 中作为独立条目？

**背景证据**:
- `registry.py:166-203`: 只有 `qe_relax`，没有 `qe_vc_relax`
- `registry.py:698-705`: `qe_vc_relax` 通过 alias 映射到 `qe_relax`
- 某些代码可能直接查找 `qe_vc_relax` 而不经过 normalize

**决策选项**:
- **A**: 添加 `qe_vc_relax` 到 `_STEP_TYPES`，但 `public_type="relax"`，`is_structure_transform=True`
  - **后果**: 更明确，但增加 registry 条目
- **B**: 保持现状，确保所有代码路径都使用 `normalize_step_type()` 或检查 `is_structure_transform` flag
  - **后果**: 需要审计所有代码路径，确保没有直接查找 `qe_vc_relax`

**建议**: 选择 B（如果确认所有路径都正确），或选择 A（如果发现直接查找的路径）。

---

### 问题 4: RELAX_STEP_TYPES 是否应该包含 "vc-relax"？

**背景证据**:
- `qc_engine_base.py:25`: `RELAX_STEP_TYPES = {"relax"}`
- `recipes.py:67`: `verify_qc_topology()` 使用 `RELAX_STEP_TYPES` 集合
- 通过 `normalize_step_type()` 应该能处理，但某些路径可能直接检查集合

**决策选项**:
- **A**: 扩展为 `RELAX_STEP_TYPES = {"relax", "vc-relax"}`，通过 normalize 统一处理
  - **后果**: 更明确，但需要确保 normalize 逻辑正确
- **B**: 保持现状，确保所有代码路径都使用 `is_relax_step_type()` 或检查 `is_structure_transform` flag
  - **后果**: 需要审计所有代码路径

**建议**: 选择 B（如果确认所有路径都正确），或选择 A（如果发现直接检查的路径）。

---

### 问题 5: ORCA parser 的 "CARTESIAN COORDINATES" 搜索逻辑是否足够严格？

**背景证据**:
- `orca_relax_parser.py:44-50`: 从后往前搜索 "CARTESIAN COORDINATES"，取最后一个
- 如果 .xyz 文件不存在，从 .out 文件解析时，可能误取中间坐标块

**决策选项**:
- **A**: 更严格地识别 "FINAL" 块，例如搜索 "FINAL CARTESIAN COORDINATES" 或 "OPTIMIZED CARTESIAN COORDINATES"
  - **后果**: 需要了解 ORCA 输出格式，确保能正确识别最终结构
- **B**: 保持现状，接受"最后一次 coordinates"
  - **后果**: 如果 ORCA 输出中有多个 "CARTESIAN COORDINATES" 块，可能误取中间块

**建议**: 选择 A，更严格地识别最终结构。

---

### 问题 6: promote_relax_structure 是否应该在 run.lock 持有时改写 SSOT？

**背景证据**:
- `api.py:4747-4752`: `promote_relax_structure()` 调用 `import_structure()` 创建新资源
- 如果 calculation 正在运行（持有 run.lock），promote 可能并发执行

**决策选项**:
- **A**: 添加锁检查，禁止在 run.lock 持有时 promote
  - **后果**: 更安全，但可能影响用户体验
- **B**: 保持现状，允许并发 promote（因为创建新资源，不修改原 calculation）
  - **后果**: 理论上安全（创建新资源），但需要确认没有竞态条件

**建议**: 选择 B（如果确认创建新资源不会影响原 calculation），或选择 A（如果需要更严格的并发控制）。

---

### 问题 7: 是否要立即收敛 public_type 只剩 relax？

**背景证据**:
- 当前所有 relax 相关步骤的 `public_type` 都是 `"relax"` ✓
- 但 `RELAX_STEP_TYPES` 只包含 `{"relax"}`，不包含 `"vc-relax"`
- 某些路径可能直接检查 `RELAX_STEP_TYPES` 集合

**决策选项**:
- **A**: 立即收敛，确保所有代码路径都使用 `is_relax_step_type()` 或检查 `is_structure_transform` flag
  - **后果**: 需要审计所有代码路径
- **B**: 保持现状，逐步迁移
  - **后果**: 可能存在边缘情况

**建议**: 选择 A，立即收敛以确保一致性。

---

### 问题 8: 如何处理历史 vc-relax 步骤？

**背景证据**:
- 历史项目中可能存在 `step_type="qe_vc_relax"` 的步骤
- 当前通过 alias 映射到 `qe_relax`，但某些代码可能直接查找

**决策选项**:
- **A**: 添加 `qe_vc_relax` 到 registry，但标记为 deprecated
  - **后果**: 支持历史步骤，但增加 registry 条目
- **B**: 保持现状，通过 alias 和 normalize 处理
  - **后果**: 需要确保所有代码路径都经过 normalize

**建议**: 选择 B（如果确认所有路径都正确），或选择 A（如果需要更好的向后兼容性）。

---

### 问题 9: effective_structure_sha 的 tolerance 是否应该与 init structure 一致？

**背景证据**:
- `executor.py:751`: `effective_structure_sha = structure_fingerprint(structure, tol=1e-5)`
- B6 契约要求："effective_structure_sha tolerance（如 1e-5）对 init 与 generated 一视同仁"

**决策选项**:
- **A**: 保持现状，使用 `tol=1e-5`（与 `structure_fingerprint()` 默认值一致）
  - **后果**: 符合契约
- **B**: 明确指定 tolerance，确保与 init structure 一致
  - **后果**: 更明确，但需要确认 init structure 的 tolerance

**建议**: 选择 A（如果确认默认值一致），或选择 B（如果需要更明确的控制）。

---

### 问题 10: 是否应该为 Molecule 实现统一的 fingerprint 函数？

**背景证据**:
- `api.py:437-446`: Molecule 使用 `hashlib.sha256(json.dumps())`
- `structure_fingerprint()` 可能不支持 Molecule（需要确认）

**决策选项**:
- **A**: 扩展 `structure_fingerprint()` 支持 Molecule，或实现 `molecule_fingerprint()` 函数
  - **后果**: 统一 fingerprint 逻辑，符合 B6 契约
- **B**: 保持现状，但明确文档说明为什么 Molecule 需要不同逻辑
  - **后果**: 违反 B6 契约

**建议**: 选择 A，统一 fingerprint 逻辑。

---

## 附录：检查的文件清单

### 核心实现文件
- `src/quantumvitas/workflow/registry.py` (828 lines)
- `src/quantumvitas/execution/recipes.py` (486 lines)
- `src/quantumvitas/execution/relax_artifacts.py` (156 lines)
- `src/quantumvitas/execution/executor.py` (818 lines)
- `src/quantumvitas/execution/handlers.py` (566 lines)
- `src/quantumvitas/execution/pyscf_relax_handler.py` (77 lines)
- `src/quantumvitas/execution/orca_relax_parser.py` (224 lines)
- `src/quantumvitas/engine/orca_engine.py` (641 lines)
- `src/quantumvitas/engine/qc_engine_base.py` (197 lines)
- `src/quantumvitas/api.py` (8214 lines, 部分读取)
- `src/quantumvitas/calculation/geometry.py` (620 lines, 部分读取)

### 规范文档
- `docs/specs/RELAX_SPEC.md` (356 lines)
- `docs/dev/RELAX_IMPLEMENTATION_PLAN.md` (2119 lines)
- `docs/dev/RELAX_TEST_MATRIX.md` (43 lines)

### 测试文件（未详细审计，但已检查存在性）
- `tests/integration/test_orca_relax_real.py`
- `tests/integration/test_pyscf_relax_real.py`
- `tests/integration/test_qe_relax_real.py`
- `tests/integration/test_relax_promote_e2e.py`
- `tests/unit/execution/test_relax_artifacts.py`
- `tests/unit/execution/test_orca_relax_parser.py`
- `tests/unit/execution/test_pyscf_relax_handler.py`

---

**审计完成时间**: 2026-01-18  
**审计员签名**: Cursor Auto (严格代码审计员)

